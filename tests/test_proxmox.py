import json
import os
from unittest.mock import Mock

import pytest
import requests

from backend.app import create_app
from backend import proxmox
from backend.proxmox import ProxmoxError, normalize_url, task_rows, validate_credentials, validate_fingerprint

SECRET = "12345678-90ab-cdef-1234-567890abcdef"
CONNECTION = {"url": "https://192.168.1.98:8006", "fingerprint": "AB:" * 31 + "CD", "tokenId": "controldeck@pve!controldeck", "secret": SECRET}
API = {
    "/version": {"version": "9.2.21"},
    "/cluster/status": [{"type": "cluster", "name": "homelab"}, {"type": "node", "name": "pve-intel", "online": 1}, {"type": "node", "name": "pve-amd", "online": 1}],
    "/cluster/resources": [{"vmid": 165, "type": "lxc", "name": "controldeck"}, {"vmid": 200, "type": "qemu", "name": "win"}],
    "/access/permissions": {"/": {"Sys.Audit": 1, "VM.Audit": 1, "Datastore.Audit": 1}},
    "/cluster/tasks": [
        {"upid": "UPID:a", "node": "pve-amd", "user": "root@pam", "type": "vzstart", "id": "165", "starttime": 100, "endtime": 102, "status": "OK"},
        {"upid": "UPID:b", "node": "pve-nas", "user": "root@pam", "type": "vzdump", "id": "200", "starttime": 300, "endtime": 400, "status": "job errors"},
        {"upid": "UPID:c", "node": "pve-amd", "user": "root@pam", "type": "vncshell", "id": "", "starttime": 500},
    ],
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([
        {"email": "admin@example.test", "role": "admin"},
        {"email": "viewer@example.test", "role": "user", "modules": ["proxmox"]},
        {"email": "other@example.test", "role": "user", "modules": ["terminal"]},
    ]))
    api = {key: value for key, value in API.items()}
    calls = []
    def fake_get(self, endpoint, **params):
        path = endpoint
        calls.append(path)
        if isinstance(api.get(path), Exception):
            raise api[path]
        return api[path]
    monkeypatch.setattr(proxmox.Client, "get", fake_get)
    monkeypatch.setattr(proxmox, "read_certificate", lambda url: {"fingerprint": CONNECTION["fingerprint"], "trusted": False})
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True
    def client(email="admin@example.test"):
        test_client = app.test_client()
        with test_client.session_transaction() as session:
            session["identity"] = {"email": email, "sub": email}
            session["csrf"] = "csrf"
        return test_client
    return client, api, calls, tmp_path / "data/proxmox/connection.json"


H = {"X-CSRF-Token": "csrf"}


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_normalize_url(case):
    if case == "normaal":
        assert normalize_url("https://192.168.1.98:8006") == "https://192.168.1.98:8006"
    elif case == "boundary":
        assert normalize_url(" https://pm.vanburik.info/ ") == "https://pm.vanburik.info:8006"
        assert normalize_url("https://192.168.1.98:8006/#") == "https://192.168.1.98:8006"
    else:
        for invalid in (None, "http://192.168.1.98:8006", "https://user:pw@host", "https://host/api2", "https://host:99999", "https://host?x=1", "https://ho st", "x" * 301):
            with pytest.raises(ValueError):
                normalize_url(invalid)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_credentials_and_fingerprint(case):
    if case == "normaal":
        validate_credentials(CONNECTION["tokenId"], SECRET)
        assert validate_fingerprint(CONNECTION["fingerprint"].lower()) == CONNECTION["fingerprint"]
    elif case == "boundary":
        validate_credentials("root@pam!a", SECRET.upper())
        assert validate_fingerprint(None) is None
    else:
        for token, secret in (("root@pam", SECRET), ("root!x", SECRET), (CONNECTION["tokenId"], "short"), (CONNECTION["tokenId"], None), ("a@b!c=d", SECRET)):
            with pytest.raises(ValueError):
                validate_credentials(token, secret)
        with pytest.raises(ValueError):
            validate_fingerprint("AB:CD")


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_task_rows(case):
    if case == "normaal":
        rows = task_rows(API["/cluster/tasks"], API["/cluster/resources"])
        assert [row["status"] for row in rows] == ["running", "error", "ok"]
        assert rows[2]["targetName"] == "controldeck" and rows[2]["targetType"] == "lxc"
        assert rows[1]["message"] == "job errors"
    elif case == "boundary":
        assert task_rows([], []) == []
        many = [{"upid": f"U{i}", "starttime": i, "status": "OK", "endtime": i} for i in range(80)]
        rows = task_rows(many, [])
        assert len(rows) == 50 and rows[0]["start"] == 79
        assert task_rows([{"upid": "W", "starttime": 1, "endtime": 2, "status": "WARNINGS: 1"}], [])[0]["status"] == "warning"
    else:
        assert task_rows([None, {"upid": 5, "starttime": 1}, {"upid": "x", "starttime": "1"}], [None]) == []


def test_http_errors_never_expose_token(monkeypatch):
    client = proxmox.Client(CONNECTION)
    for status, text in ((401, "weigert"), (403, "rechten"), (500, "onverwacht")):
        monkeypatch.setattr(requests.Session, "get", Mock(return_value=Mock(status_code=status)))
        with pytest.raises(ProxmoxError) as error:
            client.get("/version")
        assert text in str(error.value) and SECRET not in str(error.value)
    monkeypatch.setattr(requests.Session, "get", Mock(side_effect=requests.exceptions.SSLError(SECRET)))
    with pytest.raises(ProxmoxError) as error:
        client.get("/version")
    assert "certificaat" in str(error.value) and SECRET not in str(error.value)


def test_pinned_client_sends_token_only_with_fingerprint_check():
    client = proxmox.Client(CONNECTION)
    adapter = client.session.get_adapter(CONNECTION["url"] + "/api2/json/version")
    assert isinstance(adapter, proxmox.PinnedAdapter)
    assert adapter.poolmanager.connection_pool_kw["assert_fingerprint"] == CONNECTION["fingerprint"]
    assert client.session.headers["Authorization"] == f"PVEAPIToken={CONNECTION['tokenId']}={SECRET}"
    trusted = proxmox.Client({**CONNECTION, "fingerprint": None})
    assert trusted.verify is True and not isinstance(trusted.session.get_adapter("https://192.168.1.98:8006/"), proxmox.PinnedAdapter)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_connect_flow(env, case):
    client, api, calls, stored = env
    admin = client()
    if case == "normaal":
        assert admin.post("/api/proxmox/connection/certificate", headers=H, json={"url": "https://192.168.1.98:8006/#"}).json["url"] == "https://192.168.1.98:8006"
        details = admin.post("/api/proxmox/connection/test", headers=H, json=CONNECTION).json
        assert details["cluster"] == "homelab" and [n["name"] for n in details["nodes"]] == ["pve-amd", "pve-intel"]
        assert details["guests"] == {"qemu": 1, "lxc": 1} and details["extraPrivileges"] == []
        response = admin.put("/api/proxmox/connection", headers=H, json=CONNECTION)
        assert response.status_code == 200 and response.json["connected"] is True
        assert SECRET not in response.get_data(as_text=True) and SECRET not in admin.get("/api/proxmox/connection").get_data(as_text=True)
        assert json.loads(stored.read_text())["secret"] == SECRET
        if os.name == "posix":
            assert stored.stat().st_mode & 0o777 == 0o600
        assert admin.get("/api/installations").json["connections"]["proxmox"] is True
    elif case == "boundary":
        assert admin.put("/api/proxmox/connection", headers=H, json={**CONNECTION, "fingerprint": None}).status_code == 200
        # Re-testing the same token without retyping the secret reuses the stored one.
        without_secret = {k: v for k, v in CONNECTION.items() if k != "secret"}
        assert admin.post("/api/proxmox/connection/test", headers=H, json=without_secret).status_code == 200
        api["/access/permissions"] = {"/": {"Sys.Audit": 1, "VM.Audit": 1, "VM.PowerMgmt": 1}}
        assert admin.post("/api/proxmox/connection/test", headers=H, json=CONNECTION).json["extraPrivileges"] == ["VM.PowerMgmt"]
        assert admin.delete("/api/proxmox/connection", headers=H).json == {"connected": False}
        assert not stored.exists()
    else:
        assert admin.post("/api/proxmox/connection/test", headers=H, json={k: v for k, v in CONNECTION.items() if k != "secret"}).status_code == 400
        assert admin.put("/api/proxmox/connection", headers=H, json={**CONNECTION, "extra": 1}).status_code == 400
        api["/access/permissions"] = {"/": {"Datastore.Audit": 1}}
        response = admin.put("/api/proxmox/connection", headers=H, json=CONNECTION)
        assert response.status_code == 400 and "Sys.Audit" in response.json["error"]
        api["/version"] = ProxmoxError("Proxmox weigert het API-token.")
        assert admin.post("/api/proxmox/connection/test", headers=H, json=CONNECTION).status_code == 502
        assert not stored.exists()


def test_connection_requires_admin_login_and_csrf(env):
    client, api, calls, stored = env
    anonymous = client("nobody@example.test")
    assert anonymous.get("/api/proxmox/connection").status_code == 401
    viewer = client("viewer@example.test")
    assert viewer.get("/api/proxmox/connection").status_code == 403
    assert viewer.put("/api/proxmox/connection", headers=H, json=CONNECTION).status_code == 403
    assert viewer.post("/api/proxmox/connection/certificate", headers=H, json={"url": CONNECTION["url"]}).status_code == 403
    admin = client()
    assert admin.put("/api/proxmox/connection", json=CONNECTION).status_code == 403
    assert not stored.exists()


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_tasks(env, case):
    client, api, calls, stored = env
    admin = client()
    if case == "faal":
        response = admin.get("/api/proxmox/tasks")
        assert response.status_code == 409 and response.json["code"] == "not_connected"
        admin.put("/api/proxmox/connection", headers=H, json=CONNECTION)
        api["/cluster/tasks"] = ProxmoxError("Proxmox is niet bereikbaar.")
        response = admin.get("/api/proxmox/tasks")
        assert response.status_code == 502 and SECRET not in response.get_data(as_text=True)
        return
    admin.put("/api/proxmox/connection", headers=H, json=CONNECTION)
    viewer = client("viewer@example.test")
    first = viewer.get("/api/proxmox/tasks").json
    assert first["stale"] is False and first["tasks"][0]["id"] == "UPID:c"
    assert SECRET not in json.dumps(first)
    if case == "normaal":
        before = calls.count("/cluster/tasks")
        viewer.get("/api/proxmox/tasks")
        assert calls.count("/cluster/tasks") == before  # served from the 30 s cache
    else:
        proxmox_cache_expire = proxmox.CACHE_SECONDS
        proxmox.CACHE_SECONDS = -1
        try:
            api["/cluster/tasks"] = ProxmoxError("Proxmox is niet bereikbaar.")
            stale = viewer.get("/api/proxmox/tasks").json
            assert stale["stale"] is True and stale["tasks"] == first["tasks"] and "bereikbaar" in stale["error"]
        finally:
            proxmox.CACHE_SECONDS = proxmox_cache_expire


def test_tasks_authorization(env):
    client, api, calls, stored = env
    client().put("/api/proxmox/connection", headers=H, json=CONNECTION)
    assert client("nobody@example.test").get("/api/proxmox/tasks").status_code == 401
    assert client("other@example.test").get("/api/proxmox/tasks").status_code == 403
    assert client("viewer@example.test").get("/api/proxmox/tasks").status_code == 200


RESOURCES = [
    {"type": "node", "node": "pve-amd", "status": "online", "cpu": 0.25, "maxcpu": 24, "mem": 32, "maxmem": 64},
    {"type": "node", "node": "pve-nas", "status": "offline"},
    {"type": "lxc", "vmid": 165, "name": "controldeck", "node": "pve-amd", "status": "running", "cpu": 0.02, "maxcpu": 2},
    {"type": "qemu", "vmid": 101, "name": "WinServer", "node": "pve-amd", "status": "running", "cpu": 0.5, "maxcpu": 4},
    {"type": "lxc", "vmid": 108, "name": "stopped", "node": "pve-amd", "status": "stopped", "cpu": 0, "maxcpu": 1},
    {"type": "sdn", "sdn": "zone1", "status": "ok"}, {"type": "sdn", "sdn": "zone2", "status": "error"},
]
NODE_TASKS = {"pve-amd": [
    {"type": "qmigrate", "status": "OK", "endtime": 2}, {"type": "vzstart", "status": "command failed", "endtime": 2},
    {"type": "vzdump", "status": "WARNINGS: 1", "endtime": 2}, {"type": "qmstart", "status": "OK", "endtime": 2},
    {"type": "vncshell"},  # still running: not counted
    {"type": "cephcreateosd", "status": "OK", "endtime": 2}, {"type": "hastart", "status": "OK", "endtime": 2},
]}


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_summarize(case):
    if case == "normaal":
        result = proxmox.summarize(RESOURCES, NODE_TASKS)
        assert [g["name"] for g in result["guests"]] == ["WinServer", "controldeck"]
        assert result["guests"][0]["cpu"] == 50.0
        assert result["nodesByCpu"][0] == {"name": "pve-amd", "online": True, "cpu": 25.0, "cpus": 24, "memory": 50.0, "memoryUsed": 32, "memoryTotal": 64}
        assert result["offlineNodes"] == ["pve-nas"]
        categories = result["taskCategories"]
        assert categories["migration"]["ok"] == 1 and categories["container"]["error"] == 1 and categories["backup"]["warning"] == 1
        assert categories["vm"]["ok"] == 1 and categories["ceph"]["ok"] == 1 and categories["ha"]["ok"] == 1
        assert result["taskNodes"]["pve-amd"] == {"ok": 4, "warning": 1, "error": 1}
        assert result["sdnZones"] == {"available": 1, "error": 1, "pending": 0, "total": 2}
    elif case == "boundary":
        empty = proxmox.summarize([], {})
        assert empty["guests"] == [] and empty["nodesByCpu"] == [] and empty["sdnZones"]["total"] == 0
        many = [{"type": "lxc", "vmid": i, "name": f"g{i}", "status": "running", "cpu": i / 100} for i in range(15)]
        assert [g["id"] for g in proxmox.summarize(many, {}, top=10)["guests"]][:2] == [14, 13]
        assert len(proxmox.summarize(many, {})["guests"]) == 10
    else:
        result = proxmox.summarize([None, "x", {"type": "node", "node": "n", "status": "online", "cpu": "high", "mem": 1, "maxmem": 0}], {"n": [None, "bad"]})
        assert result["nodesByCpu"] == [] and result["nodesByMemory"] == []
        assert result["taskNodes"] == {"n": {"ok": 0, "warning": 0, "error": 0}}


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_summary_endpoint(env, case):
    client, api, calls, stored = env
    admin = client()
    admin.put("/api/proxmox/connection", headers=H, json=CONNECTION)
    api["/cluster/resources"] = RESOURCES
    api["/nodes/pve-amd/tasks"] = NODE_TASKS["pve-amd"]
    if case == "faal":
        api["/nodes/pve-amd/tasks"] = ProxmoxError("Proxmox is niet bereikbaar.")
        assert admin.get("/api/proxmox/summary").status_code == 502
        assert client("other@example.test").get("/api/proxmox/summary").status_code == 403
        return
    body = client("viewer@example.test").get("/api/proxmox/summary").json
    assert body["stale"] is False and body["summary"]["taskNodes"]["pve-amd"]["error"] == 1
    # The offline node is not queried; its name never reaches an API path.
    assert "/nodes/pve-nas/tasks" not in calls
    if case == "boundary":
        api["/cluster/resources"] = [{"type": "node", "node": "../../access", "status": "online"}]
        proxmox_cache = proxmox.CACHE_SECONDS
        proxmox.CACHE_SECONDS = -1
        try:
            assert admin.get("/api/proxmox/summary").status_code == 200
            assert not any("access" in call and call.startswith("/nodes/") for call in calls)
        finally:
            proxmox.CACHE_SECONDS = proxmox_cache
