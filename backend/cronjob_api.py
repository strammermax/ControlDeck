"""Module Cronjobs, step 4: the cronjob manager (docs/NODE-AGENT.md §4).

Reading (jobs, schedules, results, cluster-wide run history) is allowed for users with the `proxmox` module.
Commands and logs can contain secrets and are admin-only, as are all changes. Every node call goes through the
agent proxy; the agent itself validates input again and keeps its own audit log.
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

from flask import g, jsonify, request

from backend.agent_client import AgentUnavailable, proxy_request
from backend.auth import filter_configuration
from backend.configuration import ConfigurationError, load_config
from backend.proxmox import NODE, Client as ProxmoxClient, ProxmoxError

JOB_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
RUN_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{6}")
REF = re.compile(r"[0-9a-f]{16}")
RUNS_CACHE_SECONDS = 15
JOB_FIELDS = {"description", "schedule", "user", "command", "enabled", "logs", "timeoutMinutes"}


class CronError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


def call_agent(node, action, payload=None, actor=""):
    """Agent action on one node through the proxy; returns the agent's data or raises CronError."""
    try:
        response = proxy_request({"op": "call", "node": node, "action": action, "payload": payload or {}, "actor": actor})
    except AgentUnavailable as error:
        raise CronError(str(error), 503) from None
    if not response.get("ok"):
        raise CronError(response.get("message") or "De node is niet bereikbaar.", 502)
    answer = response.get("data") or {}
    if not answer.get("ok"):
        status = 404 if answer.get("error") == "not_found" else 400
        raise CronError(answer.get("message") or "De agent weigerde de opdracht.", status)
    return answer.get("data")


def enrolled_nodes():
    try:
        response = proxy_request({"op": "status"}, timeout=5)
    except AgentUnavailable as error:
        raise CronError(str(error), 503) from None
    if not response.get("ok"):
        raise CronError("De agent-proxy is niet beschikbaar.", 503)
    return sorted(node["node"] for node in (response.get("data") or {}).get("nodes", []) if isinstance(node, dict) and isinstance(node.get("node"), str))


def redact_job(job, admin):
    """Viewers see schedule and results, never the command (it can contain passwords or tokens)."""
    if admin:
        return job
    return {key: value for key, value in job.items() if key != "command"}


def redact_entry(entry, admin):
    if admin:
        return entry
    return {key: value for key, value in entry.items() if key not in ("command", "line")}


def proxmox_backup_runs(data_dir, since):
    """vzdump tasks from the Proxmox API (existing read-only connection), as runs in the cluster timeline."""
    try:
        connection = json.loads((Path(data_dir) / "proxmox/connection.json").read_text(encoding="utf-8"))
        tasks = ProxmoxClient(connection).get("/cluster/tasks")
    except (OSError, ValueError, KeyError, TypeError, ProxmoxError):
        return None
    runs = []
    for task in tasks if isinstance(tasks, list) else []:
        if not isinstance(task, dict) or task.get("type") != "vzdump" or not isinstance(task.get("starttime"), int) or task["starttime"] < since:
            continue
        status = task.get("status")
        end = task.get("endtime") if isinstance(task.get("endtime"), int) else None
        runs.append({"source": "proxmox", "node": str(task.get("node", "")), "jobId": "vzdump", "description": f"Backup {task.get('id') or 'alle gasten'}".strip(),
                     "start": task["starttime"], "end": end, "duration": (end - task["starttime"]) if end else None,
                     "status": "running" if end is None else "succeeded" if status == "OK" else "failed", "message": None if status in (None, "OK") else str(status)[:200]})
    return runs


def setup_cronjob_api(app, configuration_path, data_dir):
    cache = {"at": 0.0, "key": None, "data": None}
    lock = Lock()

    def can_view():
        try:
            return any(module["id"] == "proxmox" for module in filter_configuration(load_config(configuration_path), g.account)["modules"])
        except ConfigurationError:
            return False

    @app.before_request
    def cronjob_api_access():
        path = request.path
        if not path.startswith("/api/cronjobs/") or path.startswith("/api/cronjobs/agent") or g.account is None:
            return None
        if not can_view():
            return jsonify(error="Geen toegang tot Proxmox."), 403
        admin_only = request.method != "GET" or path.endswith("/log")
        if admin_only and g.account["role"] != "admin":
            return jsonify(error="Beheerrechten vereist voor deze actie."), 403
        return None

    def is_admin():
        return g.account["role"] == "admin"

    def node_param(node):
        if not NODE.fullmatch(node) or node not in enrolled_nodes():
            raise CronError("Onbekende of niet-gekoppelde node.", 404)
        return node

    def job_param(job_id):
        if not JOB_ID.fullmatch(job_id):
            raise CronError("Ongeldige jobnaam.", 404)
        return job_id

    def respond(function):
        try:
            return function()
        except CronError as error:
            return jsonify(error=error.message), error.status

    @app.get("/api/cronjobs/nodes")
    def cron_nodes():
        return respond(lambda: jsonify(nodes=enrolled_nodes()))

    @app.get("/api/cronjobs/nodes/<node>")
    def cron_node(node):
        def run():
            data = call_agent(node_param(node), "cron.list", actor=g.account["email"])
            admin = is_admin()
            return jsonify(node=node, jobs=[redact_job(job, admin) for job in data.get("jobs", [])],
                           system=[redact_entry(entry, admin) for entry in data.get("system", [])], timers=data.get("timers", []))
        return respond(run)

    @app.get("/api/cronjobs/nodes/<node>/jobs/<job_id>/history")
    def cron_history(node, job_id):
        return respond(lambda: jsonify(call_agent(node_param(node), "cron.history", {"id": job_param(job_id), "limit": 20})))

    @app.get("/api/cronjobs/nodes/<node>/jobs/<job_id>/runs/<run_id>/log")
    def cron_log(node, job_id, run_id):
        def run():
            offset = request.args.get("offset", "0")
            if not RUN_ID.fullmatch(run_id) or not offset.isdigit():
                raise CronError("Ongeldige run.", 404)
            return jsonify(call_agent(node_param(node), "cron.log", {"id": job_param(job_id), "runId": run_id, "offset": int(offset)}))
        return respond(run)

    def invalidate():
        with lock:
            cache.update(at=0.0, data=None)

    @app.put("/api/cronjobs/nodes/<node>/jobs/<job_id>")
    def cron_put(node, job_id):
        def run():
            body = request.get_json(silent=True)
            if not isinstance(body, dict) or not set(body) <= JOB_FIELDS:
                raise CronError("Ongeldige invoer.")
            result = call_agent(node_param(node), "cron.put", {**body, "id": job_param(job_id)}, g.account["email"])
            invalidate()
            return jsonify(result)
        return respond(run)

    @app.post("/api/cronjobs/nodes/<node>/jobs/<job_id>/pause")
    def cron_pause(node, job_id):
        def run():
            body = request.get_json(silent=True)
            if not isinstance(body, dict) or set(body) != {"enabled"} or not isinstance(body["enabled"], bool):
                raise CronError("Ongeldige invoer.")
            node_name, identifier = node_param(node), job_param(job_id)
            job = next((item for item in call_agent(node_name, "cron.list").get("jobs", []) if item.get("id") == identifier), None)
            if job is None:
                raise CronError("Onbekende job.", 404)
            fields = {key: job[key] for key in JOB_FIELDS if job.get(key) is not None}
            result = call_agent(node_name, "cron.put", {**fields, "id": identifier, "enabled": body["enabled"]}, g.account["email"])
            invalidate()
            return jsonify(result)
        return respond(run)

    @app.delete("/api/cronjobs/nodes/<node>/jobs/<job_id>")
    def cron_delete(node, job_id):
        def run():
            result = call_agent(node_param(node), "cron.delete", {"id": job_param(job_id)}, g.account["email"])
            invalidate()
            return jsonify(result)
        return respond(run)

    @app.post("/api/cronjobs/nodes/<node>/jobs/<job_id>/run")
    def cron_run(node, job_id):
        def run():
            result = call_agent(node_param(node), "cron.run", {"id": job_param(job_id)}, g.account["email"])
            invalidate()
            return jsonify(result)
        return respond(run)

    @app.post("/api/cronjobs/nodes/<node>/adopt")
    def cron_adopt(node):
        def run():
            body = request.get_json(silent=True)
            if not isinstance(body, dict) or set(body) != {"ref", "id"} or not isinstance(body["ref"], str) or not REF.fullmatch(body["ref"]):
                raise CronError("Ongeldige invoer.")
            result = call_agent(node_param(node), "cron.adopt", {"ref": body["ref"], "id": job_param(str(body["id"]))}, g.account["email"])
            invalidate()
            return jsonify(result)
        return respond(run)

    @app.post("/api/cronjobs/nodes/<node>/jobs/<job_id>/release")
    def cron_release(node, job_id):
        def run():
            result = call_agent(node_param(node), "cron.release", {"id": job_param(job_id)}, g.account["email"])
            invalidate()
            return jsonify(result)
        return respond(run)

    @app.get("/api/cronjobs/runs")
    def cron_runs():
        """Cluster-wide timeline: ControlDeck jobs (with result), started system cron jobs, and Proxmox backups."""
        def run():
            hours = request.args.get("hours", "24")
            if not hours.isdigit() or not 1 <= int(hours) <= 336:
                raise CronError("Periode moet tussen 1 en 336 uur liggen.")
            since = int(time.time()) - int(hours) * 3600
            admin = is_admin()
            key = (since // RUNS_CACHE_SECONDS, admin)
            with lock:
                if cache["key"] == key and cache["data"] is not None and time.time() - cache["at"] < RUNS_CACHE_SECONDS:
                    return jsonify(cache["data"])
            nodes = enrolled_nodes()
            def one(node):
                try:
                    return node, call_agent(node, "cron.runs", {"since": since, "limit": 500}).get("runs", []), None
                except CronError as error:
                    return node, [], error.message
            with ThreadPoolExecutor(max_workers=max(1, min(8, len(nodes)))) as pool:
                results = list(pool.map(one, nodes))
            runs, unavailable = [], []
            for node, items, error in results:
                if error:
                    unavailable.append({"node": node, "error": error})
                for item in items:
                    entry = {**item, "node": node}
                    runs.append(entry if admin else {k: v for k, v in entry.items() if k != "command"})
            backups = proxmox_backup_runs(data_dir, since)
            runs += backups or []
            runs.sort(key=lambda item: item.get("start") or 0, reverse=True)
            data = {"since": since, "runs": runs[:1000], "unavailable": unavailable, "proxmox": backups is not None}
            with lock:
                cache.update(at=time.time(), key=key, data=data)
            return jsonify(data)
        return respond(run)
