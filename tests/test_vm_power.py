import json

import pytest

from backend.proxmox import ProxmoxError
from backend.vm_power import VmPower, vm_links

SERVER = "f230d0fed5104941abe3fba719fd67eb"
WIN = {"node": "pve-amd", "vmid": 101, "host": "192.168.20.101", "port": 3389, "before": [{"node": "pve-amd", "vmid": 136}]}


class FakeClient:
    def __init__(self, running, refuse=False):
        self.running, self.refuse, self.posts = set(running), refuse, []

    def get(self, endpoint, **params):
        vmid = int(endpoint.split("/")[4])
        return {"status": "running" if vmid in self.running else "stopped"}

    def post(self, endpoint, **data):
        if self.refuse:
            raise ProxmoxError("Het API-token heeft onvoldoende rechten.")
        vmid = int(endpoint.split("/")[4])
        self.posts.append(vmid)
        self.running.add(vmid)


def power(tmp_path, client, probe=lambda host, port: True):
    value = VmPower(tmp_path, probe=probe)
    value.client = lambda: client
    return value


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_vm_links(case):
    if case == "normaal":
        links = vm_links({"vms": {SERVER: WIN}})
        assert links[SERVER]["vmid"] == 101 and links[SERVER]["before"] == [{"node": "pve-amd", "vmid": 136}]
    elif case == "boundary":
        assert vm_links({}) == {} and vm_links({"vms": {}}) == {}
        dashed = "f230d0fe-d510-4941-abe3-fba719fd67eb"
        assert vm_links({"vms": {dashed: {"node": "pve-amd", "vmid": 101}}})[SERVER] == {"node": "pve-amd", "vmid": 101, "before": []}
    else:
        for bad in ({"vms": {"x": WIN}}, {"vms": {SERVER: {**WIN, "vmid": "101"}}}, {"vms": {SERVER: {**WIN, "node": "../x"}}},
                    {"vms": {SERVER: {**WIN, "port": 0}}}, {"vms": {SERVER: {**WIN, "shutdown": True}}}, {"vms": []}):
            with pytest.raises(ValueError):
                vm_links(bad)


def test_state_normaal_boundary_faal(tmp_path):
    links = vm_links({"vms": {SERVER: WIN}})[SERVER]
    assert power(tmp_path, FakeClient({101})).state(links) == "online"
    assert power(tmp_path, FakeClient({101}), probe=lambda h, p: False).state(links) == "booting", "running, but RDP not ready yet"
    assert power(tmp_path, FakeClient(set())).state(links) == "offline"
    broken = VmPower(tmp_path)
    assert broken.state(links) == "unknown", "no Proxmox connection is never shown as online"


def test_wake_starts_dependencies_first_and_only_stopped_vms(tmp_path):
    links = vm_links({"vms": {SERVER: WIN}})[SERVER]
    client = FakeClient(set())
    assert power(tmp_path, client).wake(links) == [136, 101] and client.posts == [136, 101], "domain controller first"
    client = FakeClient({136})
    assert power(tmp_path, client).wake(links) == [101], "a running dependency is left alone"
    client = FakeClient({101, 136})
    assert power(tmp_path, client).wake(links) == [] and client.posts == []


class Cluster:
    """Proxmox with two VMs: WinServer (101) and ZorinPro (107), plus a template that must be ignored."""
    def __init__(self):
        self.calls = []

    def get(self, endpoint, **params):
        self.calls.append(endpoint)
        if endpoint == "/cluster/resources":
            return [{"type": "qemu", "node": "pve-amd", "vmid": 101, "name": "WinServer"},
                    {"type": "qemu", "node": "pve-amd", "vmid": 107, "name": "ZorinPro"},
                    {"type": "qemu", "node": "pve-amd", "vmid": 900, "name": "winserver", "template": 1},
                    {"type": "lxc", "node": "pve-amd", "vmid": 164, "name": "controldeck"}]
        vmid = int(endpoint.split("/")[4])
        return {"net0": {101: "virtio=BC:24:11:95:1E:D9,bridge=vmbr0,firewall=1", 107: "virtio=BC:24:11:82:80:93,bridge=vmbr0"}[vmid]}


def discovering(tmp_path, arp=None, names=None, cluster=None):
    value = VmPower(tmp_path, probe=lambda h, p: True, arp=lambda ip: (arp or {}).get(ip), rname=lambda ip: (names or {}).get(ip), lookup=lambda h: h)
    value.client = lambda: cluster or Cluster()
    return value


ZORIN_SERVER = "95cb9fd491914dd9a5514d19a3e910ee"


def test_discover_normaal_by_mac_and_by_name(tmp_path):
    """Requirement 2026-10-18: a VM added as a server in Kasm appears with status and wake-up, without extra config."""
    links = discovering(tmp_path, arp={"192.168.20.101": "bc:24:11:95:1e:d9"}, names={"192.168.20.107": "zorinpro"}).discover(
        {SERVER: "192.168.20.101", ZORIN_SERVER: "192.168.20.107"}, {})
    assert links[SERVER] == {"node": "pve-amd", "vmid": 101, "host": "192.168.20.101", "port": 3389, "before": []}, "MAC on the network"
    assert links[ZORIN_SERVER]["vmid"] == 107, "VM off: DNS name equals the VM name"


def test_discover_boundary_learned_links_and_explicit_dependencies(tmp_path):
    first = discovering(tmp_path, arp={"192.168.20.101": "bc:24:11:95:1e:d9"})
    first.discover({SERVER: "192.168.20.101"}, {})
    # Later: VM off, no DNS name, Proxmox briefly unreachable -> the learned link remains.
    later = VmPower(tmp_path, probe=lambda h, p: False, arp=lambda ip: None, rname=lambda ip: None, lookup=lambda h: h)
    links = later.discover({SERVER: "192.168.20.101"}, {SERVER: {"before": [{"node": "pve-amd", "vmid": 136}]}})
    assert links[SERVER]["vmid"] == 101 and links[SERVER]["before"] == [{"node": "pve-amd", "vmid": 136}], "vault adds only the dependency"
    assert discovering(tmp_path).discover({}, {}) == {}


def test_discover_faal_no_match_templates_and_explicit_wins(tmp_path):
    cluster = Cluster()
    links = discovering(tmp_path, names={"192.168.20.50": "winserver"}, cluster=cluster).discover({SERVER: "192.168.20.50"}, {})
    assert links[SERVER]["vmid"] == 101, "templates are never matched"
    assert discovering(tmp_path / "other", names={"192.168.20.60": "unknown"}).discover({ZORIN_SERVER: "192.168.20.60"}, {}) == {}
    explicit = {ZORIN_SERVER: {"node": "pve-intel", "vmid": 200, "before": []}}
    assert discovering(tmp_path / "x", names={"192.168.20.107": "zorinpro"}).discover({ZORIN_SERVER: "192.168.20.107"}, explicit)[ZORIN_SERVER]["vmid"] == 200


def test_arp_and_mac_parsing(tmp_path):
    from backend.vm_power import arp_mac, vm_macs
    table = tmp_path / "arp"
    table.write_text("IP address HW type Flags HW address Mask Device\n"
                     "192.168.20.101 0x1 0x2 bc:24:11:95:1e:d9 * eth0\n"
                     "192.168.20.107 0x1 0x0 00:00:00:00:00:00 * eth0\n")
    assert arp_mac("192.168.20.101", table) == "bc:24:11:95:1e:d9"
    assert arp_mac("192.168.20.107", table) is None, "incomplete entry"
    assert arp_mac("192.168.20.101", tmp_path / "missing") is None
    assert vm_macs({"net0": "virtio=BC:24:11:95:1E:D9,bridge=vmbr0", "net1": "e1000=AA:BB:CC:DD:EE:FF", "scsi0": "x"}) == {"bc:24:11:95:1e:d9", "aa:bb:cc:dd:ee:ff"}
    assert vm_macs({}) == set() and vm_macs({"net0": "bridge=vmbr0"}) == set()


def test_wake_faal_without_power_permission(tmp_path):
    links = vm_links({"vms": {SERVER: WIN}})[SERVER]
    with pytest.raises(ProxmoxError, match="VM.PowerMgmt"):
        power(tmp_path, FakeClient(set(), refuse=True)).wake(links)
