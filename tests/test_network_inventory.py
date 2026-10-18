"""ProxMenux network: physical-only cluster counters, bounded projection and access."""
import json
import time
import pytest
from backend.network_inventory import network_snapshot, network_rates, LATENCY_PATH
from backend import proxmenux
from backend.proxmox import ProxmoxError
from test_proxmox import env, CONNECTION
from test_proxmenux import env as monitor_env, CA, NODES, H, settled


def network():
    return {"physical_interfaces": [{"name": "nic0", "status": "up", "speed": 2500, "rx_Bps": 0, "bytes_recv": 1000, "bytes_sent": 250,
                                      "bond_role": "active", "bond_link": "up", "vm_status": "running", "addresses": [{"ip": "192.0.2.1"}], "used_by_bridges": ["vmbr0"], "password": "PRIVATE-PASSWORD"}],
            "bridge_interfaces": [{"name": "vmbr0", "status": "up", "bytes_recv": 1000}], "bond_interfaces": [], "vm_lxc_interfaces": [], "dns_servers": ["192.0.2.53"]}


def test_network_normal_safe_projection_and_byte_units():
    body = network_snapshot("pve-amd", network(), {"stats": {"current": .7}, "data": [{"timestamp": 100, "value": .7}]})
    nic = body["interfaces"][0]
    assert nic["bytes_recv"] == 1000 and nic["speed"] == 2500 and nic["rx_Bps"] == 0
    assert nic["bond_role"] == "active" and nic["bond_link"] == "up"
    assert nic["addresses"] == ["192.0.2.1"] and nic["used_by_bridges"] == ["vmbr0"]
    assert body["latency"]["current"] == .7 and body["networkAvailable"]
    assert "PRIVATE" not in json.dumps(body) and "password" not in json.dumps(body)


def test_network_boundary_missing_rates_zero_latency_and_duplicate_interfaces():
    value = network()
    value["bond_interfaces"] = value["physical_interfaces"]  # Monitor can include the same object in multiple views.
    result = network_snapshot("pve-amd", value, {"stats": {"current": 0}, "data": []})
    assert len(result["interfaces"]) == 2
    assert result["interfaces"][0]["tx_Bps"] is None and result["latency"]["current"] == 0
    empty = network_snapshot("pve-amd", {"physical_interfaces": []}, None)
    assert empty["networkAvailable"] and empty["interfaces"] == [] and empty["latency"]["current"] is None


def test_network_failure_bad_collections_nonfinite_values_and_unsafe_fields():
    value = network()
    value["physical_interfaces"].extend([None, {"name": "../secret"}, {"name": "nic1", "speed": float("nan"), "rx_Bps": -1, "addresses": [None, {"ip": "bad"}], "mac_address": "bad"}])
    value["dns_servers"] = ["bad", "192.0.2.53"]
    result = network_snapshot("pve-amd", value, {"data": [None, {"timestamp": 1, "value": float("inf")}]})
    nic = next(i for i in result["interfaces"] if i["name"] == "nic1")
    assert nic["speed"] is None and nic["rx_Bps"] is None and nic["addresses"] == []
    assert result["dns"] == ["192.0.2.53"] and result["latency"]["history"] == []
    assert not network_snapshot("pve-amd", "bad", None)["networkAvailable"]


@pytest.mark.parametrize("case", ["normal", "boundary", "failure"])
def test_network_rates_consecutive_samples_missing_and_counter_reset(case):
    before = network_snapshot("pve-amd", network(), None)
    current = network_snapshot("pve-amd", network(), None)
    current["interfaces"][0].update(bytes_recv=1300, bytes_sent=550)
    if case == "normal":
        nic = network_rates(current, before, 30)["interfaces"][0]
        assert nic["tx_Bps"] == 10 and nic["rx_Bps"] == 0  # Supplied zero rate is authoritative.
    elif case == "boundary":
        assert network_rates(current, None, 30)["interfaces"][0]["tx_Bps"] is None
        assert network_rates(current, before, 181)["interfaces"][0]["tx_Bps"] is None
        assert network_rates(current, before, .1)["interfaces"][0]["tx_Bps"] is None
    else:
        current["interfaces"][0].update(bytes_sent=0, rx_Bps=None, bytes_recv=None)
        nic = network_rates(current, before, 30)["interfaces"][0]
        assert nic["tx_Bps"] is None and nic["rx_Bps"] is None


@pytest.mark.parametrize("case", ["normal", "boundary", "failure"])
def test_network_node_inventory_permissions_cache_and_upstream(env, case):
    client, api, calls, path = env
    assert client("other@example.test").get("/api/proxmox/network").status_code == 403
    assert client().application.test_client().get("/api/proxmox/network").status_code == 401
    assert client().get("/api/proxmox/network").status_code == 409
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(CONNECTION))
    api["/cluster/resources"] = ProxmoxError("Unavailable") if case == "failure" else [] if case == "boundary" else [{"type": "node", "node": "pve-amd", "status": "online"}]
    response = client("viewer@example.test").get("/api/proxmox/network")
    if case == "failure":
        assert response.status_code == 502
    else:
        assert len(response.json["network"]["nodes"]) == (1 if case == "normal" else 0)
        assert client().get("/api/proxmox/network").status_code == 200 and calls.count("/cluster/resources") == 1


@pytest.mark.parametrize("case", ["normal", "boundary", "failure"])
def test_network_monitor_partial_independent_cache_and_authorization(monitor_env, monkeypatch, case):
    client, hosts, failing, stored = monitor_env
    original = proxmenux.monitor_get
    calls = []
    def monitor(node, ca, endpoint, timeout=None):
        if endpoint in ("network", LATENCY_PATH):
            calls.append(endpoint)
            if case == "failure" and endpoint == LATENCY_PATH:
                raise proxmenux.MonitorError("Latency unavailable")
            return network() if endpoint == "network" else {"stats": {"current": .7}, "data": []}
        return original(node, ca, endpoint, timeout)
    monkeypatch.setattr(proxmenux, "monitor_get", monitor)
    assert client("other@example.test").get("/api/proxmenux/network").status_code == 403
    assert client().application.test_client().get("/api/proxmenux/network").status_code == 401
    assert client().get("/api/proxmenux/network").status_code == 409
    assert client().put("/api/proxmenux/connection", json={"nodes": NODES, "ca": CA}, headers=H).status_code == 200
    for _ in range(200):
        nodes = client("viewer@example.test").get("/api/proxmenux/network").json["nodes"]
        if not any(n.get("loading") for n in nodes):
            break
        time.sleep(.01)
    assert all(n["networkAvailable"] for n in nodes)
    if case == "failure":
        assert all(LATENCY_PATH in n["partial"] and n["latency"]["current"] is None for n in nodes)
    else:
        assert all(n["latency"]["current"] == .7 for n in nodes)
    before = len(calls)
    client().get("/api/proxmenux/network")
    assert len(calls) == before
    if case == "boundary":
        # Namespace regression: network cache must not replace health/guest summary fields.
        assert "categories" in settled(client())[0]
    assert client().delete("/api/proxmenux/connection", headers=H).status_code == 200
    assert client().get("/api/proxmenux/network").status_code == 409
