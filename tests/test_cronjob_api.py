"""End-to-end through the real node agent: API → (fake transport instead of SSH) → controldeck-agent on a temp root."""
import importlib.util
import json
import os
import threading
import time
from pathlib import Path

import pytest

from backend import cronjob_api
from backend.app import create_app

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("controldeck_agent_e2e", ROOT / "scripts/controldeck-agent.py")
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)
H = {"X-CSRF-Token": "csrf"}
JOB = {"schedule": "30 2 * * *", "command": "/usr/local/bin/backup.sh --token=SECRET", "description": "Nachtelijke backup"}


class Transport:
    """Plays the agent proxy: one temp file system per node, the real agent answers."""
    def __init__(self, base, nodes):
        self.roots = {node: base / node for node in nodes}
        for root in self.roots.values():
            (root / "etc/cron.d").mkdir(parents=True)
        self.lock, self.down, self.actors = threading.Lock(), set(), []

    def __call__(self, request, timeout=75):
        if request["op"] == "status":
            return {"ok": True, "data": {"nodes": [{"node": node} for node in self.roots]}}
        node = request["node"]
        if node in self.down:
            return {"ok": False, "error": "ssh_failed", "message": "De verbinding met de node is mislukt."}
        with self.lock:
            os.environ["CONTROLDECK_AGENT_ROOT"] = str(self.roots[node])
            try:
                self.actors.append(request.get("actor"))
                payload = {**request.get("payload", {}), **({"actor": request["actor"]} if request.get("actor") else {})}
                return {"ok": True, "data": agent.handle(request["action"], json.dumps(payload))}
            finally:
                del os.environ["CONTROLDECK_AGENT_ROOT"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([
        {"email": "admin@example.test", "role": "admin"},
        {"email": "viewer@example.test", "role": "user", "modules": ["proxmox"]},
        {"email": "other@example.test", "role": "user", "modules": ["terminal"]},
    ]))
    transport = Transport(tmp_path / "nodes", ["pve-amd", "pve-nas"])
    monkeypatch.setattr(cronjob_api, "proxy_request", transport)
    monkeypatch.setattr(agent, "user_exists", lambda name: name != "ghost")
    monkeypatch.setattr(cronjob_api, "proxmox_backup_runs", lambda data_dir, since: [{"source": "proxmox", "node": "pve-amd", "jobId": "vzdump", "start": int(time.time()) - 60, "status": "succeeded"}])
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True
    def client(email="admin@example.test"):
        test_client = app.test_client()
        with test_client.session_transaction() as session:
            session["identity"] = {"email": email, "sub": email}
            session["csrf"] = "csrf"
        return test_client
    return client, transport


def write_run(transport, node, job_id, run_id, start, status="succeeded", code=0, log=b"klaar\n"):
    directory = transport.roots[node] / "var/lib/controldeck-agent/runs" / job_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{run_id}.json").write_text(json.dumps({"runId": run_id, "jobId": job_id, "start": start, "end": start + 3, "duration": 3, "exitCode": code, "status": status}))
    (directory / f"{run_id}.log").write_bytes(log)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_create_list_edit_delete(env, case):
    client, transport = env
    admin = client()
    if case == "faal":
        assert admin.put("/api/cronjobs/nodes/pve-amd/jobs/backup", headers=H, json={**JOB, "schedule": "99 * * * *"}).status_code == 400
        assert admin.put("/api/cronjobs/nodes/pve-amd/jobs/Bad_Name", headers=H, json=JOB).status_code == 404
        assert admin.put("/api/cronjobs/nodes/pve-amd/jobs/backup", headers=H, json={**JOB, "shell": "x"}).status_code == 400
        assert admin.put("/api/cronjobs/nodes/pve-xyz/jobs/backup", headers=H, json=JOB).status_code == 404
        assert admin.delete("/api/cronjobs/nodes/pve-amd/jobs/unknown", headers=H).status_code == 404
        return
    created = admin.put("/api/cronjobs/nodes/pve-amd/jobs/backup", headers=H, json=JOB)
    assert created.status_code == 200 and created.json["schedule"] == "30 2 * * *"
    assert "run backup" in (transport.roots["pve-amd"] / "etc/cron.d/controldeck").read_text()
    assert transport.actors[-1] == "admin@example.test"
    listed = admin.get("/api/cronjobs/nodes/pve-amd").json
    assert [job["id"] for job in listed["jobs"]] == ["backup"] and listed["jobs"][0]["command"].startswith("/usr/local/bin/backup.sh")
    if case == "boundary":
        paused = admin.post("/api/cronjobs/nodes/pve-amd/jobs/backup/pause", headers=H, json={"enabled": False}).json
        assert paused["enabled"] is False and paused["command"] == JOB["command"]  # pausing keeps every other field
        assert "# paused:" in (transport.roots["pve-amd"] / "etc/cron.d/controldeck").read_text()
        assert admin.post("/api/cronjobs/nodes/pve-amd/jobs/backup/pause", headers=H, json={"enabled": "no"}).status_code == 400
    assert admin.delete("/api/cronjobs/nodes/pve-amd/jobs/backup", headers=H).json["deleted"] is True
    assert admin.get("/api/cronjobs/nodes/pve-amd").json["jobs"] == []


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_history_log_and_cluster_runs(env, case):
    client, transport = env
    admin = client()
    admin.put("/api/cronjobs/nodes/pve-amd/jobs/backup", headers=H, json=JOB)
    admin.put("/api/cronjobs/nodes/pve-nas/jobs/scrub", headers=H, json={**JOB, "command": "zpool scrub Storage"})
    now = time.time()
    write_run(transport, "pve-amd", "backup", "20261005T020000Z-aaaaaa", now - 600, log=b"gestart\nklaar\n")
    write_run(transport, "pve-nas", "scrub", "20261005T030000Z-bbbbbb", now - 300, "failed", 2)
    if case == "normaal":
        history = admin.get("/api/cronjobs/nodes/pve-amd/jobs/backup/history").json["runs"]
        assert history[0]["status"] == "succeeded"
        log = admin.get("/api/cronjobs/nodes/pve-amd/jobs/backup/runs/20261005T020000Z-aaaaaa/log?offset=8").json
        assert log["content"] == "klaar\n"
        runs = admin.get("/api/cronjobs/runs?hours=24").json
        assert [(r["node"], r["status"]) for r in runs["runs"]] == [("pve-amd", "succeeded"), ("pve-nas", "failed"), ("pve-amd", "succeeded")]
        assert runs["runs"][0]["source"] == "proxmox" and runs["unavailable"] == []
    elif case == "boundary":
        assert admin.get("/api/cronjobs/runs?hours=336").status_code == 200
        assert admin.get("/api/cronjobs/runs?hours=337").status_code == 400
        assert admin.get("/api/cronjobs/runs?hours=0").status_code == 400
    else:
        # One node down: the others still answer, the missing node is reported, never counted as OK.
        transport.down.add("pve-nas")
        runs = admin.get("/api/cronjobs/runs?hours=12").json
        assert runs["unavailable"] == [{"node": "pve-nas", "error": "De verbinding met de node is mislukt."}]
        assert all(r["node"] != "pve-nas" for r in runs["runs"])
        assert admin.get("/api/cronjobs/nodes/pve-amd/jobs/backup/runs/../../etc/log").status_code == 404
        assert admin.get("/api/cronjobs/nodes/pve-amd/jobs/backup/runs/20261005T020000Z-aaaaaa/log?offset=-1").status_code == 404


def test_viewers_see_results_but_never_commands_or_logs(env):
    client, transport = env
    client().put("/api/cronjobs/nodes/pve-amd/jobs/backup", headers=H, json=JOB)
    write_run(transport, "pve-amd", "backup", "20261005T020000Z-aaaaaa", time.time() - 60)
    (transport.roots["pve-amd"] / "etc/crontab").write_text("17 * * * * root /opt/sync.sh --password=hunter2\n")
    viewer = client("viewer@example.test")
    listed = viewer.get("/api/cronjobs/nodes/pve-amd")
    body = listed.get_data(as_text=True)
    assert listed.status_code == 200 and listed.json["jobs"][0]["schedule"] == "30 2 * * *"
    assert "SECRET" not in body and "hunter2" not in body and "command" not in listed.json["jobs"][0]
    assert "SECRET" not in viewer.get("/api/cronjobs/runs").get_data(as_text=True)
    assert viewer.get("/api/cronjobs/nodes/pve-amd/jobs/backup/runs/20261005T020000Z-aaaaaa/log").status_code == 403
    for method, path in (("put", "/api/cronjobs/nodes/pve-amd/jobs/x"), ("delete", "/api/cronjobs/nodes/pve-amd/jobs/backup"),
                         ("post", "/api/cronjobs/nodes/pve-amd/jobs/backup/run"), ("post", "/api/cronjobs/nodes/pve-amd/adopt")):
        assert getattr(viewer, method)(path, headers=H, json={}).status_code == 403
    assert client("other@example.test").get("/api/cronjobs/nodes").status_code == 403
    assert client("nobody@example.test").get("/api/cronjobs/nodes").status_code == 401
    assert client().put("/api/cronjobs/nodes/pve-amd/jobs/y", json=JOB).status_code == 403  # missing CSRF


def test_adopt_and_release_through_the_api(env):
    client, transport = env
    admin = client()
    (transport.roots["pve-amd"] / "etc/cron.d/pve-backup").write_text("0 3 * * sun root /usr/bin/vzdump --all\n")
    entry = admin.get("/api/cronjobs/nodes/pve-amd").json["system"][0]
    assert admin.post("/api/cronjobs/nodes/pve-amd/adopt", headers=H, json={"ref": entry["ref"], "id": "weekly-vzdump"}).json["adopted"] is True
    assert "# disabled by ControlDeck" in (transport.roots["pve-amd"] / "etc/cron.d/pve-backup").read_text()
    assert admin.post("/api/cronjobs/nodes/pve-amd/jobs/weekly-vzdump/release", headers=H).status_code == 200
    assert (transport.roots["pve-amd"] / "etc/cron.d/pve-backup").read_text() == "0 3 * * sun root /usr/bin/vzdump --all\n"
    assert admin.post("/api/cronjobs/nodes/pve-amd/adopt", headers=H, json={"ref": "x", "id": "a"}).status_code == 400
