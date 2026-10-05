"""Status of the root-installed parts (installation worker, agent proxy) and the exact command to update them.

These parts are deliberately not replaced by a CI deployment (a taken-over pipeline must not be able to place root
code). ControlDeck therefore tells the admin when they are older than the app needs, with the command for this host.
"""
import json
import re
import shlex
from pathlib import Path

from backend.agent_client import AgentUnavailable, proxy_request

# Raise together with PROXY_VERSION in scripts/controldeck-agent-proxy.py (a test keeps them equal).
REQUIRED_PROXY = 1
DEFAULT_CHECKOUT = "/root/controldeck-bootstrap"


def bootstrap_info(data_dir):
    """Written by install-wizard.sh: where the checkout is and who owns it."""
    try:
        info = json.loads((Path(data_dir) / "bootstrap.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(info, dict) or not isinstance(info.get("checkout"), str) or not re.fullmatch(r"/[A-Za-z0-9._/-]{1,200}", info["checkout"]):
        return None
    owner = info.get("owner")
    return {"checkout": info["checkout"], "owner": owner if isinstance(owner, str) and re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", owner) else "root",
            "commit": info.get("commit") if isinstance(info.get("commit"), str) and re.fullmatch(r"[0-9a-f]{7,40}", info["commit"]) else None}


def update_command(info):
    """Pull as the checkout owner (git refuses root on another user's repository), run the bootstrap as root."""
    checkout = (info or {}).get("checkout") or DEFAULT_CHECKOUT
    owner = (info or {}).get("owner") or "root"
    pull = f"git -C {shlex.quote(checkout)} pull" if owner == "root" else f"sudo -u {shlex.quote(owner)} git -C {shlex.quote(checkout)} pull"
    return f"{pull} && bash {shlex.quote(checkout + '/scripts/install-wizard.sh')}"


def proxy_status():
    try:
        response = proxy_request({"op": "status"}, timeout=3)
    except AgentUnavailable:
        return {"available": False, "version": None, "outdated": False}
    version = (response.get("data") or {}).get("proxyVersion", 0) if response.get("ok") else 0
    version = version if isinstance(version, int) and not isinstance(version, bool) else 0
    return {"available": True, "version": version, "outdated": version < REQUIRED_PROXY}


def root_components(data_dir, worker):
    """worker: the installation status dict (workerAvailable, workerVersion, workerOutdated)."""
    info = bootstrap_info(data_dir)
    proxy = proxy_status()
    issues = []
    if worker.get("workerOutdated"):
        issues.append("installatieworker")
    if not proxy["available"]:
        issues.append("agent-proxy (niet geïnstalleerd)")
    elif proxy["outdated"]:
        issues.append("agent-proxy")
    return {"issues": issues, "proxy": proxy, "checkout": (info or {}).get("checkout"), "command": update_command(info), "installedCommit": (info or {}).get("commit")}
