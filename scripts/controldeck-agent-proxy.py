#!/usr/bin/env python3
"""ControlDeck agent proxy: the only holder of the SSH key to the Proxmox nodes.

Runs as the unprivileged system user ``controldeck-ssh`` (no root). The ControlDeck web app talks to it over a
local Unix socket (group ``controldeck-ssh``, mode 0660); the web app can never read the key. Per request the
proxy validates the operation, the node (must be enrolled), the agent action (fixed list) and the input size,
then runs ``ssh`` with the pinned host key and a time-out. Every node call is written to an audit log.

Design: docs/NODE-AGENT.md. Standard library only.
"""
import base64
import datetime
import hashlib
import json
import os
import re
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

# Raise when the proxy gains operations; ControlDeck compares it with REQUIRED_PROXY in backend/root_components.py.
PROXY_VERSION = 1
MAX_REQUEST = 80 * 1024
CALL_TIMEOUT = 60
NODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,62}")
ADDRESS = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}|[0-9A-Fa-f:]{2,39}|[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")
FINGERPRINT = re.compile(r"SHA256:[A-Za-z0-9+/]{43}")
# Must match ACTIONS in scripts/controldeck-agent.py; the agent rejects anything else as well.
AGENT_ACTIONS = {"info", "cron.list", "cron.put", "cron.delete", "cron.run", "cron.history", "cron.log", "cron.runs", "cron.adopt", "cron.release"}
lock = threading.Lock()


class ProxyError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def state():
    base = Path(os.environ.get("CONTROLDECK_PROXY_STATE", "/var/lib/controldeck-ssh"))
    return {"dir": base, "key": base / "id_ed25519", "pub": base / "id_ed25519.pub", "known": base / "known_hosts",
            "nodes": base / "nodes.json", "audit": base / "audit.log"}


def binary(name):
    return os.environ.get(f"CONTROLDECK_PROXY_{name.upper().replace('-', '_')}", name)


def write_atomic(path, text, mode=0o600):
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        os.chmod(temporary, mode)
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            output.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def audit(entry):
    with open(state()["audit"], "a", encoding="utf-8") as log:
        log.write(json.dumps({"at": int(time.time()), **entry}) + "\n")


def load_nodes():
    try:
        nodes = json.loads(state()["nodes"].read_text(encoding="utf-8"))
        return nodes if isinstance(nodes, dict) else {}
    except (OSError, ValueError):
        return {}


def fingerprint(key_line):
    """'<host> ssh-ed25519 <base64>' → 'SHA256:…' (as ssh-keygen -lf shows it)."""
    parts = key_line.split()
    if len(parts) < 3 or parts[1] != "ssh-ed25519":
        raise ProxyError("no_hostkey", "De node gaf geen ed25519-hostsleutel.")
    try:
        blob = base64.b64decode(parts[2], validate=True)
    except ValueError:
        raise ProxyError("no_hostkey", "Ongeldige hostsleutel.") from None
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")


def scan(address):
    try:
        result = subprocess.run([binary("ssh-keyscan"), "-T", "5", "-t", "ed25519", address], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        raise ProxyError("unreachable", "De node is niet bereikbaar via SSH.") from None
    line = next((item for item in result.stdout.splitlines() if item and not item.startswith("#")), "")
    if not line:
        raise ProxyError("unreachable", "De node is niet bereikbaar via SSH.")
    return line, fingerprint(line)


def ssh_command(node):
    files = state()
    return [binary("ssh"), "-i", str(files["key"]), "-o", "IdentitiesOnly=yes", "-o", f"UserKnownHostsFile={files['known']}",
            "-o", "GlobalKnownHostsFile=/dev/null", "-o", "StrictHostKeyChecking=yes", "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=5", "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=2", "-T", f"root@{node['address']}"]


def validate(request):
    if not isinstance(request, dict) or not isinstance(request.get("op"), str):
        raise ProxyError("invalid_request", "Ongeldig verzoek.")
    op = request["op"]
    fields = {"status": set(), "keygen": set(), "scan": {"address"}, "trust": {"node", "address", "fingerprint"},
              "forget": {"node"}, "call": {"node", "action", "payload", "actor"}}
    if op not in fields or not set(request) - {"op"} <= fields[op]:
        raise ProxyError("invalid_request", "Onbekende bewerking of velden.")
    if "node" in request and (not isinstance(request["node"], str) or not NODE.fullmatch(request["node"])):
        raise ProxyError("invalid_node", "Ongeldige nodenaam.")
    if "address" in request and (not isinstance(request["address"], str) or not ADDRESS.fullmatch(request["address"])):
        raise ProxyError("invalid_address", "Ongeldig adres.")
    if "fingerprint" in request and (not isinstance(request["fingerprint"], str) or not FINGERPRINT.fullmatch(request["fingerprint"])):
        raise ProxyError("invalid_fingerprint", "Ongeldige vingerafdruk.")
    if op == "call":
        if request.get("action") not in AGENT_ACTIONS:
            raise ProxyError("unknown_action", "Onbekende agent-actie.")
        if not isinstance(request.get("payload", {}), dict) or not isinstance(request.get("actor", ""), str):
            raise ProxyError("invalid_request", "Ongeldige invoer.")
    return op


def handle(request):
    """One request in, one response out. Never raises."""
    try:
        op = validate(request)
        with lock:
            return {"ok": True, "data": OPERATIONS[op](request)}
    except ProxyError as error:
        return {"ok": False, "error": error.code, "message": error.message}
    except OSError:
        return {"ok": False, "error": "io_error", "message": "Bestandsfout in de agent-proxy."}


def op_status(request):
    files = state()
    public = files["pub"].read_text(encoding="utf-8").strip() if files["pub"].is_file() else None
    return {"proxyVersion": PROXY_VERSION, "keyExists": files["key"].is_file(), "publicKey": public,
            "nodes": [{"node": name, **{k: v for k, v in info.items() if k in ("address", "fingerprint", "enrolledAt")}} for name, info in sorted(load_nodes().items())]}


def op_keygen(request):
    files = state()
    if not files["key"].is_file():
        try:
            subprocess.run([binary("ssh-keygen"), "-q", "-t", "ed25519", "-N", "", "-C", "controldeck-agent", "-f", str(files["key"])],
                           check=True, capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            raise ProxyError("keygen_failed", "Het sleutelpaar kan niet worden gemaakt.") from None
        os.chmod(files["key"], 0o600)
        audit({"op": "keygen", "result": "ok"})
    return op_status(request)


def op_scan(request):
    _, value = scan(request["address"])
    return {"address": request["address"], "fingerprint": value}


def op_trust(request):
    line, value = scan(request["address"])
    if value != request["fingerprint"]:
        audit({"op": "trust", "node": request["node"], "result": "fingerprint_mismatch"})
        raise ProxyError("fingerprint_mismatch", "De hostsleutel komt niet overeen met de bevestigde vingerafdruk.")
    files = state()
    nodes = load_nodes()
    nodes[request["node"]] = {"address": request["address"], "fingerprint": value, "enrolledAt": int(time.time())}
    known = "".join(f"{info['address']} {info.get('key', '')}\n" for name, info in nodes.items() if name != request["node"] and info.get("key"))
    _, key_type, key_blob = line.split()[:3]
    nodes[request["node"]]["key"] = f"{key_type} {key_blob}"
    known += f"{request['address']} {key_type} {key_blob}\n"
    write_atomic(files["known"], known, 0o600)
    write_atomic(files["nodes"], json.dumps(nodes, indent=2), 0o600)
    audit({"op": "trust", "node": request["node"], "address": request["address"], "fingerprint": value, "result": "ok"})
    return {"node": request["node"], "address": request["address"], "fingerprint": value}


def op_forget(request):
    files = state()
    nodes = load_nodes()
    nodes.pop(request["node"], None)
    write_atomic(files["known"], "".join(f"{info['address']} {info['key']}\n" for info in nodes.values() if info.get("key")), 0o600)
    write_atomic(files["nodes"], json.dumps(nodes, indent=2), 0o600)
    audit({"op": "forget", "node": request["node"], "result": "ok"})
    return {"node": request["node"], "forgotten": True}


def op_call(request):
    node = load_nodes().get(request["node"])
    if node is None:
        raise ProxyError("unknown_node", "Deze node is niet gekoppeld.")
    if not state()["key"].is_file():
        raise ProxyError("no_key", "Er is nog geen SSH-sleutel.")
    payload = {**request.get("payload", {}), **({"actor": request["actor"]} if request.get("actor") else {})}
    body = json.dumps(payload).encode()
    if len(body) > 64 * 1024:
        raise ProxyError("too_large", "Invoer te groot.")
    entry = {"op": "call", "node": request["node"], "action": request["action"], "actor": request.get("actor", "")[:120]}
    try:
        result = subprocess.run(ssh_command(node) + [request["action"]], input=body, capture_output=True, timeout=CALL_TIMEOUT)
    except subprocess.TimeoutExpired:
        audit({**entry, "result": "timeout"})
        raise ProxyError("timeout", "De node antwoordde niet op tijd.") from None
    except OSError:
        audit({**entry, "result": "ssh_missing"})
        raise ProxyError("ssh_missing", "SSH-client ontbreekt op de ControlDeck-host.") from None
    try:
        answer = json.loads(result.stdout.decode("utf-8", errors="replace").strip().splitlines()[-1])
        if not isinstance(answer, dict) or "ok" not in answer:
            raise ValueError
    except (ValueError, IndexError):
        # ssh itself failed (host key changed, key not authorised, agent missing): stderr stays in the audit log only.
        audit({**entry, "result": "ssh_failed", "exit": result.returncode, "stderr": result.stderr.decode("utf-8", errors="replace")[-300:]})
        stderr = result.stderr.decode("utf-8", errors="replace")
        if "REMOTE HOST IDENTIFICATION HAS CHANGED" in stderr or "Host key verification failed" in stderr:
            raise ProxyError("hostkey_changed", "De hostsleutel van de node is veranderd. Koppel de node opnieuw na controle.") from None
        if "Permission denied" in stderr:
            raise ProxyError("not_authorized", "De node accepteert de sleutel van ControlDeck niet (agent nog niet geïnstalleerd?).") from None
        raise ProxyError("ssh_failed", "De verbinding met de node is mislukt.") from None
    audit({**entry, "result": "ok" if answer["ok"] else answer.get("error", "error")})
    return answer


OPERATIONS = {"status": op_status, "keygen": op_keygen, "scan": op_scan, "trust": op_trust, "forget": op_forget, "call": op_call}


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        raw = self.rfile.readline(MAX_REQUEST + 1)
        if len(raw) > MAX_REQUEST:
            response = {"ok": False, "error": "too_large", "message": "Verzoek te groot."}
        else:
            try:
                response = handle(json.loads(raw))
            except ValueError:
                response = {"ok": False, "error": "invalid_json", "message": "Ongeldige JSON."}
        self.wfile.write((json.dumps(response) + "\n").encode())


def serve(socket_path):
    path = Path(socket_path)
    path.unlink(missing_ok=True)
    server = socketserver.ThreadingUnixStreamServer(str(path), Handler)
    # Socket 0660: owner and the controldeck-ssh group (which contains the web app user). Set on the file itself:
    # changing the process umask would also affect every other file this process creates (regression, see tests).
    os.chmod(path, 0o660)
    server.daemon_threads = True
    print(f"{datetime.datetime.now().isoformat()} controldeck-agent-proxy listening on {path}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    serve(os.environ.get("CONTROLDECK_PROXY_SOCKET", "/run/controldeck-agent/agent.sock"))
