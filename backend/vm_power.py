"""Wake the VM behind a Kasm workspace and report whether it is reachable. Start only; never stop."""

import json
import re
import socket
import time
from pathlib import Path
from threading import Lock

from backend.proxmox import Client, ProxmoxError

NODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,62}")
HOST = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}")
SERVER_ID = re.compile(r"[0-9a-f]{32}")
CACHE_SECONDS = 10


def _vm(value):
    if not isinstance(value, dict) or not {"node", "vmid"} <= set(value) <= {"node", "vmid", "host", "port", "before"}:
        raise ValueError("Ongeldige VM-koppeling.")
    node, vmid = value["node"], value["vmid"]
    if not isinstance(node, str) or not NODE.fullmatch(node) or type(vmid) is not int or not 100 <= vmid <= 999999999:
        raise ValueError("Ongeldige VM-koppeling.")
    result = {"node": node, "vmid": vmid}
    if "host" in value:
        port = value.get("port", 3389)
        if not isinstance(value["host"], str) or not HOST.fullmatch(value["host"]) or type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Ongeldige VM-koppeling.")
        result.update(host=value["host"], port=port)
    return result


def vm_links(config):
    """Kasm server id -> VM to wake (with an optional RDP check and VMs to start first, e.g. a domain controller)."""
    raw = config.get("vms", {}) if isinstance(config, dict) else {}
    if not isinstance(raw, dict) or len(raw) > 50:
        raise ValueError("Ongeldige VM-koppelingen.")
    links = {}
    for server_id, value in raw.items():
        key = str(server_id).replace("-", "").lower()
        if not SERVER_ID.fullmatch(key):
            raise ValueError("Ongeldige Kasm-server-ID in de VM-koppelingen.")
        vm = _vm({k: v for k, v in value.items() if k != "before"} if isinstance(value, dict) else value)
        before = value.get("before", [])
        if not isinstance(before, list) or len(before) > 5:
            raise ValueError("Ongeldige VM-koppeling.")
        vm["before"] = [_vm(item) for item in before]
        links[key] = vm
    return links


def port_open(host, port, timeout=1.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class VmPower:
    """Status per VM: 'online' (running and service reachable), 'booting', 'offline' or 'unknown'."""

    def __init__(self, data_dir, probe=port_open, clock=time.monotonic):
        self.path = Path(data_dir) / "proxmox" / "connection.json"
        self.probe, self.clock = probe, clock
        self.cache, self.lock = {}, Lock()

    def client(self):
        try:
            connection = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ProxmoxError("Proxmox is nog niet gekoppeld.") from None
        return Client(connection)

    def running(self, client, vm):
        status = client.get(f"/nodes/{vm['node']}/qemu/{vm['vmid']}/status/current")
        return isinstance(status, dict) and status.get("status") == "running"

    def state(self, vm, client=None):
        key = (vm["node"], vm["vmid"])
        with self.lock:
            hit = self.cache.get(key)
            if hit and self.clock() - hit[0] < CACHE_SECONDS:
                return hit[1]
        try:
            if not self.running(client or self.client(), vm):
                value = "offline"
            elif "host" in vm and not self.probe(vm["host"], vm["port"]):
                value = "booting"
            else:
                value = "online"
        except ProxmoxError:
            value = "unknown"
        with self.lock:
            self.cache[key] = (self.clock(), value)
        return value

    def wake(self, vm):
        """Start the VMs it depends on first, then the VM itself. Returns the names of started VMs."""
        client = self.client()
        started = []
        for target in [*vm["before"], vm]:
            if not self.running(client, target):
                try:
                    client.post(f"/nodes/{target['node']}/qemu/{target['vmid']}/status/start")
                except ProxmoxError as error:
                    if "onvoldoende rechten" in str(error):
                        raise ProxmoxError(f"ControlDeck mag VM {target['vmid']} niet starten: het Proxmox-token mist het recht VM.PowerMgmt.") from None
                    raise
                started.append(target["vmid"])
        with self.lock:
            self.cache.clear()
        return started
