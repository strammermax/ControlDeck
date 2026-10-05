"""Module Cronjobs: enrol Proxmox nodes for the ControlDeck node agent (docs/NODE-AGENT.md, step 3).

The web app never holds the SSH key; every node operation goes through the local agent proxy.
Admin-only: key generation, host key scan/trust, install command, connection test and removal.
"""
import hashlib
import json
import os
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import g, jsonify, request

from backend.agent_client import AgentUnavailable, proxy_request
from backend.proxmox import NODE, Client as ProxmoxClient, ProxmoxError

ROOT = Path(__file__).resolve().parent.parent
AGENT_FILE = ROOT / "scripts/controldeck-agent.py"
REPOSITORY = "strammermax/ControlDeck"
ADDRESS = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}")
FINGERPRINT = re.compile(r"SHA256:[A-Za-z0-9+/]{43}")


def required_agent_version():
    match = re.search(r"^AGENT_VERSION = (\d+)$", AGENT_FILE.read_text(encoding="utf-8"), re.M)
    return int(match.group(1)) if match else 1


def agent_checksum():
    return hashlib.sha256(AGENT_FILE.read_bytes()).hexdigest()


def source_address(node_address):
    """The address the node sees ControlDeck coming from (no packet is sent: UDP connect only picks the route)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect((node_address, 22))
        return probe.getsockname()[0]


def install_command(public_key, source, commit):
    """One idempotent root command for the node: verified agent download plus a restricted key line."""
    if not re.fullmatch(r"ssh-ed25519 [A-Za-z0-9+/=]{68} controldeck-agent", public_key or ""):
        raise ValueError("Ongeldige publieke sleutel.")
    if not ADDRESS.fullmatch(source):
        raise ValueError("Ongeldig bronadres.")
    ref = commit if re.fullmatch(r"[0-9a-f]{40}", commit or "") else "main"
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{ref}/scripts/controldeck-agent.py"
    key_blob = public_key.split()[1]
    line = f'restrict,from="{source}",command="/usr/local/sbin/controldeck-agent" {public_key}'
    return (
        "command -v python3 >/dev/null || { echo 'python3 ontbreekt'; exit 1; }; "
        f"curl -fsSL {url} -o /tmp/controldeck-agent && "
        f"echo '{agent_checksum()}  /tmp/controldeck-agent' | sha256sum -c - && "
        "install -m 0755 /tmp/controldeck-agent /usr/local/sbin/controldeck-agent && rm -f /tmp/controldeck-agent && "
        "mkdir -p /root/.ssh && chmod 700 /root/.ssh && "
        f"{{ grep -qF '{key_blob}' /root/.ssh/authorized_keys 2>/dev/null || echo '{line}' >> /root/.ssh/authorized_keys; }} && "
        "echo 'ControlDeck-agent geïnstalleerd.'"
    )


def node_state(info):
    """Proxy answer for an `info` call → wizard state."""
    if not info.get("ok"):
        return {"hostkey_changed": "hostkey_changed", "not_authorized": "not_installed", "unknown_node": "not_enrolled"}.get(info.get("error"), "unreachable")
    data = info.get("data") or {}
    if not data.get("ok"):
        return "unreachable"
    version = (data.get("data") or {}).get("agentVersion")
    return "ready" if isinstance(version, int) and version >= required_agent_version() else "outdated"


def setup_cronjobs(app, data_dir, commit):
    marker = Path(data_dir) / "cronjobs" / "connection.json"

    def proxy(body):
        response = proxy_request(body)
        if not response.get("ok"):
            raise ValueError(response.get("message") or "De agent-proxy weigerde het verzoek.")
        return response["data"]

    def write_marker(nodes):
        if nodes:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps({"nodes": sorted(nodes)}), encoding="utf-8")
        else:
            marker.unlink(missing_ok=True)

    def suggestions():
        try:
            connection = json.loads((Path(data_dir) / "proxmox/connection.json").read_text(encoding="utf-8"))
            status = ProxmoxClient(connection).get("/cluster/status")
            return [{"node": item["name"], "address": item["ip"]} for item in status
                    if isinstance(item, dict) and item.get("type") == "node" and isinstance(item.get("name"), str) and NODE.fullmatch(item["name"])
                    and isinstance(item.get("ip"), str) and ADDRESS.fullmatch(item["ip"])]
        except (OSError, ValueError, KeyError, TypeError, ProxmoxError):
            return []

    @app.before_request
    def cronjobs_access():
        if request.path.startswith("/api/cronjobs/agent") or request.path == "/api/cronjobs/connection":
            if g.account is not None and g.account["role"] != "admin":
                return jsonify(error="Beheerrechten vereist om nodes te koppelen."), 403
        return None

    def failure(error):
        return jsonify(error=str(error)), 503 if isinstance(error, AgentUnavailable) else 400

    @app.get("/api/cronjobs/agent")
    def agent_overview():
        try:
            status = proxy({"op": "status"})
        except (AgentUnavailable, ValueError) as error:
            return jsonify(proxy=False, error=str(error), suggestions=suggestions(), nodes=[])
        def check(node):
            try:
                return {**node, "state": node_state(proxy_request({"op": "call", "node": node["node"], "action": "info"}))}
            except AgentUnavailable:
                return {**node, "state": "unreachable"}
        enrolled = status.get("nodes", [])
        with ThreadPoolExecutor(max_workers=max(1, min(8, len(enrolled)))) as pool:
            nodes = list(pool.map(check, enrolled))
        write_marker([node["node"] for node in nodes if node["state"] == "ready"])
        return jsonify(proxy=True, keyExists=status.get("keyExists"), publicKey=status.get("publicKey"), nodes=nodes,
                       suggestions=suggestions(), agentVersion=required_agent_version())

    @app.post("/api/cronjobs/agent/key")
    def agent_key():
        try:
            return jsonify(proxy({"op": "keygen"}))
        except (AgentUnavailable, ValueError) as error:
            return failure(error)

    def body(fields):
        value = request.get_json(silent=True)
        if not isinstance(value, dict) or set(value) != set(fields):
            raise ValueError("Ongeldige invoer.")
        if "node" in value and (not isinstance(value["node"], str) or not NODE.fullmatch(value["node"])):
            raise ValueError("Ongeldige nodenaam.")
        if "address" in value and (not isinstance(value["address"], str) or not ADDRESS.fullmatch(value["address"])):
            raise ValueError("Gebruik het IPv4-adres van de node.")
        if "fingerprint" in value and (not isinstance(value["fingerprint"], str) or not FINGERPRINT.fullmatch(value["fingerprint"])):
            raise ValueError("Ongeldige vingerafdruk.")
        return value

    @app.post("/api/cronjobs/agent/scan")
    def agent_scan():
        try:
            value = body(("node", "address"))
            return jsonify(proxy({"op": "scan", "address": value["address"]}))
        except (AgentUnavailable, ValueError) as error:
            return failure(error)

    @app.post("/api/cronjobs/agent/trust")
    def agent_trust():
        try:
            return jsonify(proxy({"op": "trust", **body(("node", "address", "fingerprint"))}))
        except (AgentUnavailable, ValueError) as error:
            return failure(error)

    @app.post("/api/cronjobs/agent/install-command")
    def agent_install_command():
        try:
            value = body(("node", "address"))
            status = proxy({"op": "status"})
            return jsonify(command=install_command(status.get("publicKey"), source_address(value["address"]), commit),
                           checksum=agent_checksum(), agentVersion=required_agent_version())
        except OSError:
            return jsonify(error="ControlDeck kan geen route naar deze node bepalen."), 400
        except (AgentUnavailable, ValueError) as error:
            return failure(error)

    @app.post("/api/cronjobs/agent/test")
    def agent_test():
        try:
            value = body(("node",))
            answer = proxy_request({"op": "call", "node": value["node"], "action": "info", "actor": g.account["email"]})
            state = node_state(answer)
            info = ((answer.get("data") or {}).get("data") or {}) if answer.get("ok") else {}
            return jsonify(node=value["node"], state=state, message=None if answer.get("ok") else answer.get("message"),
                           hostname=info.get("hostname"), pveVersion=info.get("pveVersion"), agentVersion=info.get("agentVersion"))
        except (AgentUnavailable, ValueError) as error:
            return failure(error)

    @app.delete("/api/cronjobs/connection")
    def cronjobs_disconnect():
        """Removal: forget all node host keys in the proxy; the node side is cleaned with the shown commands."""
        try:
            for node in proxy({"op": "status"}).get("nodes", []):
                proxy({"op": "forget", "node": node["node"]})
        except (AgentUnavailable, ValueError) as error:
            return failure(error)
        write_marker([])
        return jsonify(connected=False)
