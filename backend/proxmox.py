"""Read-only Proxmox VE connection: admin-managed API token, certificate pinning and cluster tasks."""
import hashlib
import json
import os
import re
import socket
import ssl
import tempfile
import time
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from flask import g, jsonify, request

from backend.auth import filter_configuration
from backend.configuration import ConfigurationError, load_config

TOKEN_ID = re.compile(r"[A-Za-z0-9._-]{1,64}@[A-Za-z0-9._-]{1,64}![A-Za-z][A-Za-z0-9._-]{0,63}")
SECRET = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
FINGERPRINT = re.compile(r"(?:[0-9A-F]{2}:){31}[0-9A-F]{2}")
HOST = re.compile(r"(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?")
TIMEOUT = 5
CACHE_SECONDS = 30
TASK_LIMIT = 50


class ProxmoxError(Exception):
    """Message is safe to show; it never contains the token or upstream response bodies."""


def normalize_url(value, default_port=8006):
    """Accepts a pasted address such as https://pve-amd.home:8006/# and returns https://host:port."""
    if not isinstance(value, str) or len(value) > 300:
        raise ValueError("Ongeldig adres.")
    parts = urlsplit(value.strip())
    try:
        port = parts.port or default_port
    except ValueError:
        raise ValueError("Ongeldige poort.") from None
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.path not in ("", "/") or not HOST.fullmatch(parts.hostname):
        raise ValueError("Gebruik een https-adres zonder pad, bijvoorbeeld https://pve-amd.home:8006.")
    return f"https://{parts.hostname}:{port}"


def validate_credentials(token_id, secret):
    if not isinstance(token_id, str) or not TOKEN_ID.fullmatch(token_id):
        raise ValueError("Ongeldige token-ID. Verwacht gebruiker@realm!tokennaam.")
    if not isinstance(secret, str) or not SECRET.fullmatch(secret):
        raise ValueError("Ongeldig tokengeheim.")


def validate_fingerprint(value):
    if value is None:
        return None
    if not isinstance(value, str) or not FINGERPRINT.fullmatch(value.upper()):
        raise ValueError("Ongeldige certificaatvingerafdruk.")
    return value.upper()


def read_certificate(url):
    """Returns the SHA-256 fingerprint and whether the certificate is publicly trusted for this host."""
    parts = urlsplit(url)
    unverified = ssl.create_default_context()
    unverified.check_hostname = False
    unverified.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((parts.hostname, parts.port), TIMEOUT) as raw, unverified.wrap_socket(raw, server_hostname=parts.hostname) as tls:
            der = tls.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError):
        raise ProxmoxError("Proxmox is niet bereikbaar op dit adres.") from None
    digest = hashlib.sha256(der).hexdigest().upper()
    trusted = True
    try:
        with socket.create_connection((parts.hostname, parts.port), TIMEOUT) as raw, ssl.create_default_context().wrap_socket(raw, server_hostname=parts.hostname):
            pass
    except (OSError, ssl.SSLError):
        trusted = False
    return {"fingerprint": ":".join(digest[i:i + 2] for i in range(0, 64, 2)), "trusted": trusted}


class PinnedAdapter(HTTPAdapter):
    """Accepts exactly one certificate; urllib3 rejects any other certificate before sending the token."""

    def __init__(self, fingerprint):
        self.fingerprint = fingerprint
        super().__init__()

    def init_poolmanager(self, *args, **kwargs):
        kwargs["assert_fingerprint"] = self.fingerprint
        super().init_poolmanager(*args, **kwargs)


class Client:
    def __init__(self, connection):
        self.url = connection["url"]
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"PVEAPIToken={connection['tokenId']}={connection['secret']}"
        self.verify = True
        if connection.get("fingerprint"):
            self.session.mount(self.url, PinnedAdapter(connection["fingerprint"]))
            self.verify = False  # Replaced by the pinned fingerprint check above.

    def get(self, endpoint, **params):
        try:
            response = self.session.get(f"{self.url}/api2/json{endpoint}", params=params, timeout=TIMEOUT, verify=self.verify, allow_redirects=False)
        except requests.exceptions.SSLError:
            raise ProxmoxError("Het certificaat van Proxmox komt niet overeen. Koppel Proxmox opnieuw via Admin → Modules.") from None
        except requests.RequestException:
            raise ProxmoxError("Proxmox is niet bereikbaar.") from None
        if response.status_code == 401:
            raise ProxmoxError("Proxmox weigert het API-token.")
        if response.status_code == 403:
            raise ProxmoxError("Het API-token heeft onvoldoende rechten.")
        if response.status_code != 200:
            raise ProxmoxError("Proxmox gaf een onverwacht antwoord.")
        try:
            data = response.json()["data"]
        except (ValueError, KeyError, TypeError):
            raise ProxmoxError("Proxmox gaf een onverwacht antwoord.") from None
        return data


def inspect(client):
    """Connection check for the wizard: version, cluster, nodes and token privileges."""
    version = client.get("/version")
    status = client.get("/cluster/status")
    resources = client.get("/cluster/resources", type="vm")
    permissions = client.get("/access/permissions", path="/")
    if not all(isinstance(item, (dict, list)) for item in (version, status, resources, permissions)):
        raise ProxmoxError("Proxmox gaf een onverwacht antwoord.")
    granted = sorted(name for name, value in (permissions.get("/") or {}).items() if value) if isinstance(permissions, dict) else []
    missing = [name for name in ("Sys.Audit", "VM.Audit") if name not in granted]
    cluster = next((item.get("name") for item in status if item.get("type") == "cluster"), None)
    nodes = sorted(({"name": str(item.get("name")), "online": bool(item.get("online"))} for item in status if item.get("type") == "node"), key=lambda node: node["name"])
    return {
        "version": str(version.get("version", "")),
        "cluster": cluster,
        "nodes": nodes,
        "guests": {kind: sum(1 for item in resources if item.get("type") == kind) for kind in ("qemu", "lxc")},
        "missingPrivileges": missing,
        "extraPrivileges": [name for name in granted if not name.endswith(".Audit")],
    }


def task_rows(tasks, resources):
    names = {str(item.get("vmid")): (item.get("type"), item.get("name")) for item in resources if isinstance(item, dict) and item.get("vmid") is not None}
    rows = []
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("upid"), str) or not isinstance(task.get("starttime"), int):
            continue
        target = str(task.get("id") or "")
        kind, name = names.get(target, (None, None))
        status = task.get("status")
        rows.append({
            "id": task["upid"], "node": str(task.get("node", "")), "user": str(task.get("user", "")),
            "type": str(task.get("type", "")), "target": target, "targetType": kind, "targetName": name,
            "start": task["starttime"], "end": task.get("endtime") if isinstance(task.get("endtime"), int) else None,
            "status": "running" if status is None and task.get("endtime") is None else "ok" if status == "OK" else "warning" if isinstance(status, str) and status.startswith("WARNINGS") else "error",
            "message": None if status in (None, "OK") else str(status)[:200],
        })
    return sorted(rows, key=lambda row: row["start"], reverse=True)[:TASK_LIMIT]


NODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,62}")
SUMMARY_WINDOW = 48 * 3600
CATEGORIES = ("migration", "vm", "container", "ceph", "ha", "backup", "other")


def task_category(kind):
    if kind in ("qmigrate", "vzmigrate", "hamigrate") or kind.endswith("migrate"):
        return "migration"
    if kind in ("vzdump", "backup") or kind.startswith("vzdump") or "backup" in kind:
        return "backup"
    if kind.startswith("ceph"):
        return "ceph"
    if kind.startswith("ha"):
        return "ha"
    if kind.startswith("qm"):
        return "vm"
    if kind.startswith("vz") or kind.startswith("pct"):
        return "container"
    return "other"


def task_outcome(task):
    status = task.get("status")
    if status is None or task.get("endtime") is None:
        return None
    return "ok" if status == "OK" else "warning" if isinstance(status, str) and status.startswith("WARNINGS") else "error"


def percent(used, total):
    return round(100 * used / total, 1) if isinstance(used, (int, float)) and isinstance(total, (int, float)) and total > 0 else None


def summarize(resources, node_tasks, top=10):
    """Cluster widgets: busiest guests and nodes, task counts of the last 48 hours and SDN zone states."""
    resources = [item for item in resources if isinstance(item, dict)]
    nodes = [{"name": str(item.get("node")), "online": item.get("status") == "online",
              "cpu": percent(item.get("cpu"), 1), "cpus": item.get("maxcpu"),
              "memory": percent(item.get("mem"), item.get("maxmem")), "memoryUsed": item.get("mem"), "memoryTotal": item.get("maxmem")}
             for item in resources if item.get("type") == "node"]
    guests = [{"id": item.get("vmid"), "name": str(item.get("name") or item.get("vmid")), "node": str(item.get("node", "")), "type": item.get("type"),
               "cpu": percent(item.get("cpu"), 1), "cpus": item.get("maxcpu")}
              for item in resources if item.get("type") in ("qemu", "lxc") and item.get("status") == "running" and isinstance(item.get("cpu"), (int, float))]
    categories = {name: {"ok": 0, "warning": 0, "error": 0} for name in CATEGORIES}
    per_node = {}
    for node, tasks in node_tasks.items():
        counts = per_node.setdefault(node, {"ok": 0, "warning": 0, "error": 0})
        for task in tasks:
            outcome = task_outcome(task) if isinstance(task, dict) else None
            if outcome:
                categories[task_category(str(task.get("type", "")))][outcome] += 1
                counts[outcome] += 1
    zones = {"available": 0, "error": 0, "pending": 0}
    for item in resources:
        if item.get("type") == "sdn":
            state = item.get("status")
            zones["available" if state in ("ok", "available") else "error" if state == "error" else "pending"] += 1
    return {
        "guests": sorted(guests, key=lambda guest: guest["cpu"], reverse=True)[:top],
        "nodesByCpu": sorted((node for node in nodes if node["cpu"] is not None), key=lambda node: node["cpu"], reverse=True),
        "nodesByMemory": sorted((node for node in nodes if node["memory"] is not None), key=lambda node: node["memory"], reverse=True),
        "offlineNodes": sorted(node["name"] for node in nodes if not node["online"]),
        "taskCategories": categories,
        "taskNodes": dict(sorted(per_node.items(), key=lambda entry: (-entry[1]["error"], entry[0]))),
        "sdnZones": {**zones, "total": sum(zones.values())},
        "windowHours": SUMMARY_WINDOW // 3600,
    }


def setup_proxmox(app, configuration_path, data_dir):
    root = Path(data_dir) / "proxmox"
    path = root / "connection.json"
    lock = Lock()
    caches = {}

    def load():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) and {"url", "tokenId", "secret"} <= set(data) else None
        except (OSError, ValueError):
            return None

    def store(connection):
        root.mkdir(parents=True, exist_ok=True)
        os.chmod(root, 0o700)
        handle, temporary = tempfile.mkstemp(dir=root, prefix=".connection-")
        try:
            os.chmod(temporary, 0o600)
            with os.fdopen(handle, "w", encoding="utf-8") as output:
                json.dump(connection, output)
            os.replace(temporary, path)
        finally:
            if Path(temporary).exists():
                Path(temporary).unlink()

    def public(connection):
        return {"connected": bool(connection), **({key: connection.get(key) for key in ("url", "fingerprint", "tokenId", "connectedAt", "connectedBy")} if connection else {})}

    def candidate(body, stored):
        """Builds a connection from wizard input; an omitted secret reuses the stored one for the same token."""
        if not isinstance(body, dict) or not set(body) <= {"url", "fingerprint", "tokenId", "secret"}:
            raise ValueError("Ongeldige verbindingsgegevens.")
        secret = body.get("secret")
        if secret in (None, "") and stored and stored["tokenId"] == body.get("tokenId"):
            secret = stored["secret"]
        validate_credentials(body.get("tokenId"), secret)
        return {"url": normalize_url(body.get("url")), "fingerprint": validate_fingerprint(body.get("fingerprint")), "tokenId": body["tokenId"], "secret": secret}

    def can_view():
        try:
            config = filter_configuration(load_config(configuration_path), g.account)
        except ConfigurationError:
            return False
        return any(module["id"] == "proxmox" for module in config["modules"])

    @app.before_request
    def proxmox_access():
        if not request.path.startswith("/api/proxmox") or g.account is None:
            return None
        if request.path.startswith("/api/proxmox/connection") and g.account["role"] != "admin":
            return jsonify(error="Beheerrechten vereist om Proxmox te koppelen."), 403
        if not can_view():
            return jsonify(error="Geen toegang tot Proxmox."), 403
        return None

    @app.post("/api/proxmox/connection/certificate")
    def certificate():
        body = request.get_json(silent=True)
        try:
            url = normalize_url(body.get("url") if isinstance(body, dict) else None)
            return jsonify(url=url, **read_certificate(url))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        except ProxmoxError as error:
            return jsonify(error=str(error)), 502

    @app.post("/api/proxmox/connection/test")
    def test_connection():
        try:
            connection = candidate(request.get_json(silent=True), load())
            return jsonify(inspect(Client(connection)))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        except ProxmoxError as error:
            return jsonify(error=str(error)), 502

    @app.route("/api/proxmox/connection", methods=["GET", "PUT", "DELETE"])
    def connection():
        if request.method == "GET":
            return jsonify(public(load()))
        if request.method == "DELETE":
            with lock:
                path.unlink(missing_ok=True)
                caches.clear()
            return jsonify(connected=False)
        try:
            connection = candidate(request.get_json(silent=True), load())
            details = inspect(Client(connection))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        except ProxmoxError as error:
            return jsonify(error=str(error)), 502
        if details["missingPrivileges"]:
            return jsonify(error="Het API-token mist leesrechten: " + ", ".join(details["missingPrivileges"]) + "."), 400
        connection.update(connectedAt=int(time.time()), connectedBy=g.account["email"])
        try:
            with lock:
                store(connection)
                caches.clear()
        except OSError:
            return jsonify(error="De koppeling kan niet worden opgeslagen."), 503
        return jsonify(public(connection))

    def cached(name, fetch):
        """30-second cache per connection; on failure the last known data is returned marked as stale."""
        connection = load()
        if connection is None:
            return jsonify(error="Proxmox is nog niet gekoppeld.", code="not_connected"), 409
        key = (name, connection["url"], connection["tokenId"], connection.get("connectedAt"))
        with lock:
            entry = caches.setdefault(name, {"at": 0.0, "data": None, "key": None})
            if entry["key"] != key or entry["data"] is None or time.time() - entry["at"] >= CACHE_SECONDS:
                try:
                    entry.update(at=time.time(), data=fetch(Client(connection)), key=key)
                except ProxmoxError as error:
                    if entry["key"] != key or entry["data"] is None:
                        return jsonify(error=str(error)), 502
                    return jsonify(**{name: entry["data"]}, updatedAt=int(entry["at"]), stale=True, error=str(error))
            return jsonify(**{name: entry["data"]}, updatedAt=int(entry["at"]), stale=False)

    def summary(client):
        resources = client.get("/cluster/resources")
        since = int(time.time()) - SUMMARY_WINDOW
        node_tasks = {}
        for item in resources:
            name = item.get("node") if isinstance(item, dict) and item.get("type") == "node" and item.get("status") == "online" else None
            if isinstance(name, str) and NODE.fullmatch(name):
                node_tasks[name] = client.get(f"/nodes/{name}/tasks", since=since, limit=5000, source="archive")
        return summarize(resources, node_tasks)

    @app.get("/api/proxmox/tasks")
    def tasks():
        return cached("tasks", lambda client: task_rows(client.get("/cluster/tasks"), client.get("/cluster/resources", type="vm")))

    @app.get("/api/proxmox/summary")
    def cluster_summary():
        return cached("summary", summary)
