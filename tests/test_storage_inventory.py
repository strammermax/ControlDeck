"""Storage inventory: shared identity, private projection, partial availability and access."""
import json
import pytest
from backend.storage_inventory import storage_inventory, storage_snapshot
from backend.proxmox import ProxmoxError
from backend import proxmenux
from test_proxmox import env, CONNECTION
from test_proxmenux import env as monitor_env, CA, NODES, H, settled


def resources():
    nodes = [{"type": "node", "node": name, "status": "online"} for name in ("pve-amd", "pve-intel", "pve-nas")]
    return nodes + [{"type": "storage", "storage": storage, "node": node["node"], "plugintype": kind, "shared": shared, "status": "available", "maxdisk": 1000, "disk": 250}
                    for storage, kind, shared in [("local", "dir", 0), ("shared", "cifs", 1)] for node in nodes]


DEFINITIONS = [{"storage": "local", "type": "dir", "path": "/var/lib/vz"}, {"storage": "shared", "type": "cifs", "server": "nas.test", "share": "media", "username": "private-user", "password": "private-password"}]


def test_storage_normal_shared_identity_and_local_node_isolation():
    body = storage_inventory(resources(), DEFINITIONS)
    local = [r for r in body["storage"] if r["name"] == "local"]
    shared = [r for r in body["storage"] if r["name"] == "shared"]
    assert len({r["key"] for r in local}) == 3
    assert len({r["key"] for r in shared}) == 1
    assert shared[0]["available"] == 750
    assert body["identityComplete"]
    for secret in ("private-user", "private-password", "nas.test"):
        assert secret not in json.dumps(body)


def test_storage_boundary_aliases_same_backing_unknown_capacity_and_empty():
    rs = resources()
    alias = {**rs[-1], "storage": "alias"}
    configs = DEFINITIONS + [{**DEFINITIONS[1], "storage": "alias", "path": "/different-local-mount"}]
    body = storage_inventory(rs + [alias], configs)
    assert body["storage"][0]["key"] == next(r for r in body["storage"] if r["name"] == "shared")["key"]
    assert storage_inventory([], []) == {"nodes": [], "storage": [], "identityComplete": True}
    row = storage_inventory([{**alias, "maxdisk": 0}], configs)["storage"][0]
    assert row["total"] is None and row["used"] is None
    assert not storage_inventory(rs, [])["identityComplete"]


def test_storage_failure_bad_collections_nonfinite_duplicate_and_unsafe_ids():
    for bad in ({}, None, [None] * 5001):
        with pytest.raises(ValueError):
            storage_inventory(bad, [])
    for bad in ({}, [None] * 501):
        with pytest.raises(ValueError):
            storage_inventory([], bad)
    row = resources()[-1]
    body = storage_inventory([row, row, {**row, "storage": "../secret"}], DEFINITIONS)
    assert len(body["storage"]) == 1
    for invalid in (float("nan"), True, -1):
        assert storage_inventory([{**row, "maxdisk": invalid}], DEFINITIONS)["storage"][0]["total"] is None


def test_monitor_storage_normal_whitelist_bytes_and_no_mount_options():
    body = storage_snapshot("pve-amd", {"disks": [{"name": "nvme0", "serial": "PRIVATE-SERIAL", "size_bytes": 4096, "size": 1, "temperature": 40, "standby": False, "percentage_used": 3}], "zfs_pools": [{"name": "pool", "health": "ONLINE", "size": "1T"}]},
                            {"available": True, "mounts": [{"source": "//nas/share", "target": "/mnt/media", "fstype": "cifs", "options": "password=PRIVATE-PASSWORD", "reachable": True, "total_bytes": 1000, "used_bytes": 250, "available_bytes": 750}]})
    assert body["disks"][0]["size"] == 4096
    assert body["mounts"][0]["total"] == 1000
    assert "PRIVATE" not in json.dumps(body)
    assert body["pools"][0]["node"] == "pve-amd"


def test_monitor_storage_boundary_standby_unknown_fields_and_missing_mounts():
    body = storage_snapshot("pve-amd", {"disks": [{"name": "sda", "size": 100, "temperature": 0, "standby": True, "ssd_life_left": 97}]}, None)
    assert body["disks"][0]["size"] == 102400
    assert body["disks"][0]["temperature"] is None
    assert body["disks"][0]["wear"] == 3
    assert body["mounts"] == [] and not body["mountsAvailable"]


def test_monitor_storage_failure_malformed_and_credential_sources():
    assert storage_snapshot("pve-amd", None, "bad")["disks"] == []
    body = storage_snapshot("pve-amd", {"disks": "bad", "zfs_pools": [None]}, {"mounts": [None, {"source": "user:password@server:/data", "target": "/mnt/data"}]})
    assert body["mounts"] == [] and not body["disksAvailable"]


def test_storage_api_normal_cache_and_safe_projection(env):
    client, api, calls, path = env
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(CONNECTION))
    api["/cluster/resources"], api["/storage"] = resources(), DEFINITIONS
    body = client("viewer@example.test").get("/api/proxmox/storage").json
    assert len(body["storage"]["storage"]) == 6
    assert "password" not in json.dumps(body)
    assert client().get("/api/proxmox/storage").status_code == 200
    assert calls.count("/storage") == 1


def test_storage_api_boundary_restricted_metadata_still_lists_resources(env):
    client, api, calls, path = env
    assert client().get("/api/proxmox/storage").status_code == 409
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(CONNECTION))
    api["/cluster/resources"], api["/storage"] = resources(), ProxmoxError("Denied metadata")
    body = client().get("/api/proxmox/storage").json
    assert not body["storage"]["identityComplete"] and len(body["storage"]["storage"]) == 6


def test_storage_api_failure_session_rights_csrf_and_upstream(env):
    client, api, calls, path = env
    assert client("other@example.test").get("/api/proxmox/storage").status_code == 403
    assert client().application.test_client().get("/api/proxmox/storage").status_code == 401
    assert client().post("/api/proxmox/storage", json={}).status_code == 403
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(CONNECTION))
    api["/cluster/resources"] = ProxmoxError("Unavailable")
    assert client().get("/api/proxmox/storage").status_code == 502


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_monitor_storage_endpoint_partial_cache_and_access(monitor_env, monkeypatch, case):
    client, hosts, failing, stored = monitor_env
    original = proxmenux.monitor_get
    def monitor(node, ca, endpoint, timeout=None):
        if endpoint == "mounts":
            if case == "faal":
                raise proxmenux.MonitorError("Mounts unavailable")
            return {"mounts": [], "available": True}
        return original(node, ca, endpoint, timeout)
    monkeypatch.setattr(proxmenux, "monitor_get", monitor)
    assert client("other@example.test").get("/api/proxmenux/storage").status_code == 403
    assert client().application.test_client().get("/api/proxmenux/storage").status_code == 401
    assert client().get("/api/proxmenux/storage").status_code == 409
    assert client().put("/api/proxmenux/connection", json={"nodes": NODES, "ca": CA}, headers=H).status_code == 200
    import time
    for _ in range(200):
        nodes = client("viewer@example.test").get("/api/proxmenux/storage").json["nodes"]
        if not any(n.get("loading") for n in nodes):
            break
        time.sleep(.01)
    assert all(n.get("disksAvailable") for n in nodes)
    if case == "faal":
        assert all("mounts" in n["partial"] and not n["mountsAvailable"] for n in nodes)
    if case == "boundary":
        # Namespace regression: loading storage must not replace the independent health/guest cache.
        summary = settled(client("viewer@example.test"))
        assert "categories" in summary[0] and "pools" not in summary[0]
    assert client().delete("/api/proxmenux/connection", headers=H).status_code == 200
    assert client().get("/api/proxmenux/storage").status_code == 409
