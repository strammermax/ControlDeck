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
        if not SERVER_ID.fullmatch(key) or not isinstance(value, dict):
            raise ValueError("Ongeldige Kasm-server-ID in de VM-koppelingen.")
        before = value.get("before", [])
        if not isinstance(before, list) or len(before) > 5:
            raise ValueError("Ongeldige VM-koppeling.")
        own = {k: v for k, v in value.items() if k != "before"}
        # Only "before" (no node/vmid): the VM itself is discovered automatically.
        vm = _vm(own) if own else {}
        vm["before"] = [_vm(item) for item in before]
        links[key] = vm
    return links


MAC = re.compile(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")


def arp_mac(ip, table="/proc/net/arp"):
    """MAC of an address on the local network, from the kernel neighbour table (complete entries only)."""
    try:
        lines = Path(table).read_text(encoding="ascii").splitlines()[1:]
    except OSError:
        return None
    for line in lines:
        parts = line.split()
        if len(parts) >= 4 and parts[0] == ip and parts[2] == "0x2" and MAC.fullmatch(parts[3].lower()):
            return parts[3].lower()
    return None


def reverse_name(ip):
    """Short DNS name of an address (e.g. 'winserver' for winserver.home); works while the VM is off."""
    try:
        return socket.gethostbyaddr(ip)[0].split(".")[0].lower()
    except (OSError, UnicodeError):
        return None


def resolve(host):
    try:
        return socket.gethostbyname(host)
    except (OSError, UnicodeError):
        return None


def vm_macs(config):
    """MAC addresses from a Proxmox VM config (net0, net1, …: 'virtio=BC:24:11:…,bridge=vmbr0')."""
    macs = set()
    for key, value in (config or {}).items():
        if re.fullmatch(r"net\d+", str(key)) and isinstance(value, str):
            for part in value.split(","):
                name, _, mac = part.partition("=")
                if MAC.fullmatch(mac.lower()) and name not in ("bridge", "tag", "firewall"):
                    macs.add(mac.lower())
    return macs


def port_open(host, port, timeout=1.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class VmPower:
    """Status per VM: 'online' (running and service reachable), 'booting', 'offline' or 'unknown'."""

    def __init__(self, data_dir, probe=port_open, clock=time.monotonic, arp=arp_mac, rname=reverse_name, lookup=resolve):
        self.path = Path(data_dir) / "proxmox" / "connection.json"
        self.learned_path = Path(data_dir) / "virtual-apps" / "vm-links.json"
        self.probe, self.clock, self.arp, self.rname, self.lookup = probe, clock, arp, rname, lookup
        self.cache, self.lock = {}, Lock()
        self.discovered = (None, None, {})

    def learned(self):
        try:
            value = json.loads(self.learned_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def discover(self, servers, explicit):
        """Kasm server id -> VM, found from the server address: MAC on the local network (VM on) or
        DNS name = VM name (also while off). Learned links are kept for when the VM is off.
        Explicit links from the vault win; their 'before' list is added to discovered VMs."""
        now, key = self.clock(), tuple(sorted(servers.items()))
        with self.lock:
            stamp, cached_key, links = self.discovered
            if stamp is not None and cached_key == key and now - stamp < 60:
                return self._merge(links, explicit)
        learned = self.learned()
        found = {}
        try:
            client = self.client()
            vms = [vm for vm in client.get("/cluster/resources", type="vm")
                   if isinstance(vm, dict) and vm.get("type") == "qemu" and not vm.get("template") and type(vm.get("vmid")) is int]
        except ProxmoxError:
            vms, client = [], None
        macs = {}
        for server_id, host in servers.items():
            ip = self.lookup(host) if host else None
            match = None
            if ip and client:
                self.probe(ip, 3389)  # Refreshes the neighbour table when the VM is on.
                mac = self.arp(ip)
                if mac:
                    for vm in vms:
                        key = (vm.get("node"), vm["vmid"])
                        if key not in macs:
                            try:
                                macs[key] = vm_macs(client.get(f"/nodes/{vm.get('node')}/qemu/{vm['vmid']}/config"))
                            except ProxmoxError:
                                macs[key] = set()
                        if mac in macs[key]:
                            match = vm
                            break
                if match is None:
                    name = self.rname(ip)
                    match = next((vm for vm in vms if name and str(vm.get("name", "")).lower() == name), None)
            if match is not None and NODE.fullmatch(str(match.get("node", ""))):
                found[server_id] = {"node": match["node"], "vmid": match["vmid"], "host": ip, "port": 3389}
            elif isinstance(learned.get(server_id), dict):
                try:
                    found[server_id] = {**_vm(learned[server_id]), "before": []}
                except ValueError:
                    pass
        for value in found.values():
            value.setdefault("before", [])
        if found and found != {k: v for k, v in learned.items() if k in found}:
            try:
                self.learned_path.parent.mkdir(parents=True, exist_ok=True)
                self.learned_path.write_text(json.dumps({**learned, **{k: {x: v[x] for x in ("node", "vmid", "host", "port")} for k, v in found.items()}}), encoding="utf-8")
            except OSError:
                pass
        with self.lock:
            self.discovered = (now, key, found)
        return self._merge(found, explicit)

    @staticmethod
    def _merge(found, explicit):
        links = {key: dict(value) for key, value in found.items()}
        for key, value in explicit.items():
            if "vmid" in value:
                links[key] = value
            elif key in links:
                links[key]["before"] = value.get("before", [])
        return links

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
