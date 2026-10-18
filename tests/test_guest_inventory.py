"""Cluster inventory: safe read-only projection and optional monitor enrichment."""
import json
import pytest
from backend.guest_inventory import project_guests, project_inventory, config_ip
from backend.proxmox import ProxmoxError
from test_proxmox import env, CONNECTION


def resources():
    return [{"type": "node", "node": name, "status": "online", "cpu": cpu, "maxcpu": cores, "mem": 100, "maxmem": 1000} for name, cpu, cores in [("pve-amd", .5, 8), ("pve-intel", .25, 16), ("pve-nas", .1, 4)]] + [
        {"vmid": 101, "node": "pve-amd", "type": "lxc", "name": "Example", "status": "running", "cpu": .1, "maxcpu": 2, "maxmem": 100, "mem": 50, "disk": 10, "maxdisk": 100, "uptime": 300, "netin": 500, "secret": "must-not-leak"},
        {"vmid": 102, "node": "pve-nas", "type": "qemu", "name": "Stopped", "status": "stopped"}]


def test_inventory_normal_projection_and_private_network_fields():
    value = project_inventory(resources())
    assert [n["name"] for n in value["nodes"]] == ["pve-amd", "pve-intel", "pve-nas"]
    assert len(value["guests"]) == 2
    assert value["guests"][0]["netin"] == 500
    assert "secret" not in json.dumps(value)
    assert config_ip({"net0": "name=eth0,ip=192.168.20.101/24,gw=192.168.20.1,password=never"}) == "192.168.20.101"


def test_inventory_boundary_empty_unknown_duplicate_and_nonfinite():
    assert project_inventory([]) == {"guests": [], "nodes": []}
    guest = resources()[-2]
    rows = project_guests([guest, guest, {**guest, "vmid": 103, "cpu": float("nan"), "disk": -1, "mem": True, "status": "unexpected"}])
    assert len(rows) == 2
    assert rows[1]["cpu"] is None and rows[1]["disk"] is None and rows[1]["mem"] is None
    assert rows[1]["status"] == "unknown"
    assert config_ip({"net0": "ip=dhcp", "net1": "ip6=2001:db8::2/64"}) == "2001:db8::2"
    assert config_ip({"net0": "ip=127.0.0.1/8", "net1": "ip=169.254.1.1/16"}) is None


def test_inventory_failure_rejects_malformed_identity_and_unbounded_payload():
    assert project_guests([None, {}, {**resources()[-2], "vmid": True}, {**resources()[-2], "node": "../node"}]) == []
    for bad in (None, {}, [None] * 5001):
        with pytest.raises(ValueError):
            project_inventory(bad)
    assert config_ip({"net0": "ip=999.999.999.999/24"}) is None


def test_guest_api_normal_cache_and_ip_enrichment(env):
    client, api, calls, path = env
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(CONNECTION))
    api["/cluster/resources"] = resources()
    api["/nodes/pve-amd/lxc/101/config"] = {"net0": "ip=192.168.20.101/24", "password": "not-returned"}
    body = client("viewer@example.test").get("/api/proxmox/guests").get_json()
    assert body["inventory"]["guests"][0]["ip"] == "192.168.20.101"
    assert "password" not in json.dumps(body)
    assert client().get("/api/proxmox/guests").status_code == 200
    assert calls.count("/cluster/resources") == 1


def test_guest_api_boundary_missing_connection_and_optional_config_failure(env):
    client, api, calls, path = env
    assert client().get("/api/proxmox/guests").status_code == 409
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(CONNECTION))
    api["/cluster/resources"] = resources()
    api["/nodes/pve-amd/lxc/101/config"] = ProxmoxError("No optional config rights")
    body = client().get("/api/proxmox/guests").get_json()
    assert len(body["inventory"]["guests"]) == 2
    assert body["inventory"]["guests"][0]["ip"] is None


def test_guest_api_failure_auth_permissions_and_upstream(env):
    client, api, calls, path = env
    assert client("other@example.test").get("/api/proxmox/guests").status_code == 403
    assert client().application.test_client().get("/api/proxmox/guests").status_code == 401
    assert client().post("/api/proxmox/guests", json={}).status_code == 403  # CSRF before method handling
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(CONNECTION))
    api["/cluster/resources"] = ProxmoxError("Source unavailable")
    assert client().get("/api/proxmox/guests").status_code == 502


def test_guest_api_regression_malformed_resources_are_safe_not_500(env):
    """Invalid upstream collection must give a safe provider error, not a parser traceback."""
    client, api, calls, path = env
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(CONNECTION))
    api["/cluster/resources"] = {"wrong": "shape"}
    assert client().get("/api/proxmox/guests").status_code == 502
