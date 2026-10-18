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


def test_wake_faal_without_power_permission(tmp_path):
    links = vm_links({"vms": {SERVER: WIN}})[SERVER]
    with pytest.raises(ProxmoxError, match="VM.PowerMgmt"):
        power(tmp_path, FakeClient(set(), refuse=True)).wake(links)
