"""Historical traffic: interval units, gaps, safe RRD projection and per-period access/cache."""
import json
import time
import pytest
from backend.network_inventory import network_history
from backend import proxmenux
from test_proxmenux import env as monitor_env, CA, NODES, H


def test_history_normal_sorted_rates_and_private_fields_removed():
    body = network_history("pve-amd", {"node": "pve-amd", "timeframe": "day", "password": "PRIVATE", "data": [{"time": 900, "netin": 20, "netout": 30, "cpu": .5}, {"time": 600, "netin": 10, "netout": 0}]}, "day")
    assert body["historyAvailable"] and body["step"] == 300
    assert body["history"] == [{"time": 600, "received": 10, "sent": 0}, {"time": 900, "received": 20, "sent": 30}]
    assert "PRIVATE" not in json.dumps(body) and "cpu" not in json.dumps(body)


def test_history_boundary_null_empty_single_point_and_gap_never_widen_interval():
    assert network_history("pve-amd", {"data": []}, "day")["historyAvailable"]
    single = network_history("pve-amd", {"data": [{"time": 600, "netin": None, "netout": 0}]}, "day")
    assert single["step"] == 300 and single["history"][0]["received"] is None
    # Gap regression: inferring a 900-second interval from missing samples inflated byte totals.
    gap = network_history("pve-amd", {"data": [{"time": 600}, {"time": 1500}]}, "day")
    assert gap["step"] == 300


def test_history_failure_wrong_host_period_malformed_duplicates_and_nonfinite():
    for value in (None, {"data": {}}, {"node": "wrong", "data": []}, {"timeframe": "year", "data": []}, {"data": [None]}, {"data": [{"time": 600}, {"time": 600}]}, {"data": [None]*5001}):
        assert not network_history("pve-amd", value, "day")["historyAvailable"]
    result = network_history("pve-amd", {"data": [{"time": 600, "netin": float("inf"), "netout": -1}]}, "day")
    assert result["history"][0]["received"] is None and result["history"][0]["sent"] is None


@pytest.mark.parametrize("case", ["normal", "boundary", "failure"])
def test_history_api_period_validation_permissions_cache_and_host_failure(monitor_env, monkeypatch, case):
    client, hosts, failing, stored = monitor_env
    original = proxmenux.monitor_get
    calls = []
    def monitor(node, ca, endpoint, timeout=None):
        if endpoint.startswith("node/metrics?timeframe="):
            calls.append(endpoint)
            if case == "failure" and node["name"] == "pve-nas":
                raise proxmenux.MonitorError("Monitor niet bereikbaar.")
            period = endpoint.split("=")[-1]
            return {"node": node["name"], "timeframe": period, "data": [] if case == "boundary" else [{"time": 600, "netin": 10, "netout": 0}]}
        return original(node, ca, endpoint, timeout)
    monkeypatch.setattr(proxmenux, "monitor_get", monitor)
    route = "/api/proxmenux/network/history"
    assert client("other@example.test").get(route).status_code == 403
    assert client().application.test_client().get(route).status_code == 401
    assert client().get(route).status_code == 409
    for query in ("?timeframe=invalid", "?timeframe=day&timeframe=year", "?timeframe=../secret", "?url=http://internal"):
        assert client().get(route+query).status_code == 400
    assert client().put("/api/proxmenux/connection", json={"nodes": NODES, "ca": CA}, headers=H).status_code == 200
    for period in ("day", "hour"):
        for _ in range(200):
            nodes = client("viewer@example.test").get(route+"?timeframe="+period).json["nodes"]
            if not any(n.get("loading") for n in nodes):
                break
            time.sleep(.01)
        assert next(n for n in nodes if n["name"] == "pve-amd")["timeframe"] == period
        if case == "failure":
            assert next(n for n in nodes if n["name"] == "pve-nas")["error"]
        before = len(calls)
        client().get(route+"?timeframe="+period)
        # A failed first snapshot can retry, but the successful host stays cached.
        if case != "failure":
            assert len(calls) == before
    assert set(calls) <= {"node/metrics?timeframe=day", "node/metrics?timeframe=hour"}
    assert client().delete("/api/proxmenux/connection", headers=H).status_code == 200
    assert client().get(route).status_code == 409
