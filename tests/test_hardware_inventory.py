"""Hardware cards: byte units, signed temperatures, private projection and module rights."""
import json
import time
import pytest
from backend.hardware_inventory import hardware_snapshot
from backend import proxmenux
from backend.proxmox import ProxmoxError
from test_proxmox import env, CONNECTION
from test_proxmenux import env as monitor_env, CA, NODES, H, settled


def hardware():
    return {"cpu": {"model": "Example CPU", "sockets": 1, "cores_per_socket": 12, "total_threads": 24},
            "motherboard": {"model": "Board", "serial": "PRIVATE-SERIAL", "bios": {"version": "1.2"}},
            "memory_modules": [{"slot": "DIMM 0", "size": 64*1024**2, "type": "DDR5", "serial": "PRIVATE-SERIAL"}]*2,
            "temperatures": [{"name": "CPU Package", "current": 46.4, "high": 80, "critical": 95, "serial": "PRIVATE-SERIAL"}],
            "gpus": [{"name": "GPU", "pci_driver": "amdgpu", "serial": "PRIVATE-SERIAL"}], "pci_devices": [], "usb_devices": [],
            "fans": [{"name": "CPU Fan", "speed": 1200, "unit": "RPM"}], "power_meter": {"name": "CPU", "watts": 24.5}}


def test_hardware_normal_memory_kib_to_bytes_and_no_serials():
    result = hardware_snapshot("pve-amd", hardware())
    assert result["memory"][0]["size"] == 64*1024**3
    assert result["memory"][0]["id"] != result["memory"][1]["id"]  # Same slot label is not a unique DIMM identity.
    assert result["sensors"][0]["kind"] == "cpu" and result["sensors"][0]["current"] == 46.4
    assert result["gpus"][0]["driver"] == "amdgpu" and result["power"][0]["watts"] == 24.5
    assert "PRIVATE" not in json.dumps(result) and "serial" not in json.dumps(result)


def test_hardware_boundary_zero_negative_temperature_and_empty_lists():
    value = hardware()
    value["temperatures"] = [{"name": "Cold sensor", "current": -5}, {"name": "CPU", "current": 0}]
    value["fans"][0]["speed"] = 0
    result = hardware_snapshot("pve-amd", value)
    assert [s["current"] for s in result["sensors"]] == [-5, 0]
    assert result["fans"][0]["speed"] == 0
    empty = hardware_snapshot("pve-amd", {"memory_modules": [], "temperatures": []})
    assert empty["memoryAvailable"] and empty["sensorsAvailable"] and not empty["hardwareAvailable"]


def test_hardware_failure_nonfinite_missing_and_malformed_fields():
    value = hardware()
    value.update(memory_modules=[None, {"size": float("inf"), "slot": "x\nprivate"}], temperatures=[None, {"name": "Broken sensor", "current": 999}, {"current": True}], gpus="bad", motherboard="bad")
    value["cpu"]["sockets"] = True
    result = hardware_snapshot("pve-amd", value)
    assert result["memory"][0]["size"] is None and result["memory"][0]["slot"] is None
    assert all(s["current"] is None for s in result["sensors"])
    assert result["cpu"]["sockets"] is None and result["gpus"] == []
    assert not hardware_snapshot("pve-amd", None)["hardwareAvailable"]


@pytest.mark.parametrize("case", ["normal", "boundary", "failure"])
def test_hardware_node_inventory_access_cache_and_invalid_upstream(env, case):
    client, api, calls, path = env
    assert client("other@example.test").get("/api/proxmox/hardware").status_code == 403
    assert client().application.test_client().get("/api/proxmox/hardware").status_code == 401
    assert client().get("/api/proxmox/hardware").status_code == 409
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(CONNECTION))
    api["/cluster/resources"] = ProxmoxError("Unavailable") if case == "failure" else [] if case == "boundary" else [{"type": "node", "node": "pve-amd", "status": "online"}]
    response = client("viewer@example.test").get("/api/proxmox/hardware")
    if case == "failure":
        assert response.status_code == 502
    else:
        assert len(response.json["hardware"]["nodes"]) == (1 if case == "normal" else 0)
        assert client().get("/api/proxmox/hardware").status_code == 200 and calls.count("/cluster/resources") == 1


@pytest.mark.parametrize("case", ["normal", "boundary", "failure"])
def test_hardware_monitor_isolated_cache_and_failure_per_host(monitor_env, monkeypatch, case):
    client, hosts, failing, stored = monitor_env
    original = proxmenux.monitor_get
    def monitor(node, ca, endpoint, timeout=None):
        if endpoint == "hardware":
            if case == "failure" and node["name"] == "pve-nas":
                raise proxmenux.MonitorError("Monitor niet bereikbaar.")
            return hardware() if case != "boundary" else {"cpu": {"model": "CPU"}, "memory_modules": [], "temperatures": []}
        return original(node, ca, endpoint, timeout)
    monkeypatch.setattr(proxmenux, "monitor_get", monitor)
    assert client("other@example.test").get("/api/proxmenux/hardware").status_code == 403
    assert client().application.test_client().get("/api/proxmenux/hardware").status_code == 401
    assert client().get("/api/proxmenux/hardware").status_code == 409
    assert client().put("/api/proxmenux/connection", json={"nodes": NODES, "ca": CA}, headers=H).status_code == 200
    for _ in range(200):
        nodes = client("viewer@example.test").get("/api/proxmenux/hardware").json["nodes"]
        if not any(n.get("loading") for n in nodes):
            break
        time.sleep(.01)
    assert next(n for n in nodes if n["name"] == "pve-amd")["hardwareAvailable"]
    if case == "failure":
        assert next(n for n in nodes if n["name"] == "pve-nas")["error"]
    if case == "boundary":
        assert all(n["memory"] == [] for n in nodes)
        # Cache namespace regression: hardware inventory must not replace summary health categories.
        assert "categories" in settled(client())[0]
    assert "PRIVATE" not in json.dumps(nodes)
    assert client().delete("/api/proxmenux/connection", headers=H).status_code == 200
    assert client().get("/api/proxmenux/hardware").status_code == 409
