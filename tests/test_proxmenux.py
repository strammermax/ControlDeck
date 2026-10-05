import datetime
import json
import os
import ssl

import pytest
import requests
from unittest.mock import Mock
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from backend import proxmenux
from backend.app import create_app
from backend.proxmenux import MonitorError, node_summary, validate_ca, validate_nodes

H = {"X-CSRF-Token": "csrf"}
TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJjb250cm9sZGVjayJ9.c2lnbmF0dXJl"


def certificate(ca=True):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "PVE Cluster Manager CA")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(1)
            .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True).sign(key, hashes.SHA256()))
    return cert.public_bytes(serialization.Encoding.PEM).decode()


CA = certificate()
NODES = [{"name": "pve-amd", "url": "https://192.168.1.98:8008", "token": TOKEN}, {"name": "pve-nas", "url": "https://192.168.1.97:8008", "token": TOKEN}]
HEALTH = {"overall": "CRITICAL", "summary": "1 critical", "details": {
    "cpu": {"status": "OK", "checks": {}}, "lxc_mounts": {"status": "CRITICAL", "reason": "CT 113 mount missing"}, "remote_mounts": {"status": "WARNING", "reason": "x" * 500}}}
STORAGE = {"disks": [{"name": "sda", "model": "WD Red", "serial": "SECRET-SERIAL", "health": "healthy", "smart_status": "passed", "temperature": 34, "percentage_used": None, "ssd_life_left": 93,
                      "reallocated_sectors": 0, "pending_sectors": 0, "standby": True, "size_formatted": "4 TB"}],
           "zfs_pools": [{"name": "Storage", "health": "ONLINE", "size": "3.6T", "free": "1T", "allocated": "2.6T"}]}
SYSTEM = {"hostname": "pve-amd", "temperature": 48.5, "load_average": [1.5, 1, 1], "available_updates": 3, "ip": "192.168.1.98"}
HARDWARE = {"power_meter": {"watts": 61.2, "name": "x"}, "motherboard": {"serial": "SECRET-BOARD"}}
VMS = [{"vmid": 129, "name": "plex", "update_check": {"available": True, "count": 4, "security_count": 2, "latest": "1.2"}}, {"vmid": 100, "name": "dns", "update_check": {"available": False}}]


@pytest.fixture
def env(tmp_path, monkeypatch):
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([
        {"email": "admin@example.test", "role": "admin"},
        {"email": "viewer@example.test", "role": "user", "modules": ["proxmox"]},
        {"email": "other@example.test", "role": "user", "modules": ["terminal"]},
    ]))
    responses = {"system": SYSTEM, "health": {"version": "1.2.6"}, "health/details": HEALTH, "storage": STORAGE, "hardware": HARDWARE, "vms": VMS}
    hosts = {"https://192.168.1.98:8008": "pve-amd", "https://192.168.1.97:8008": "pve-nas"}
    failing = set()
    def fake(node, ca_path, path):
        assert ca_path.read_text() == CA.strip() + "\n"
        if node["url"] in failing:
            raise MonitorError("Monitor niet bereikbaar.")
        return {**SYSTEM, "hostname": hosts.get(node["url"])} if path == "system" else responses[path]
    monkeypatch.setattr(proxmenux, "monitor_get", fake)
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True
    def client(email="admin@example.test"):
        test_client = app.test_client()
        with test_client.session_transaction() as session:
            session["identity"] = {"email": email, "sub": email}
            session["csrf"] = "csrf"
        return test_client
    return client, hosts, failing, tmp_path / "data/proxmenux/connection.json"


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_validate_ca(case):
    if case == "normaal":
        assert validate_ca(CA) == CA.strip() + "\n"
    elif case == "boundary":
        assert validate_ca("\n\n" + CA + "\n\n").startswith("-----BEGIN CERTIFICATE-----")
    else:
        for invalid in (None, "", "not a cert", CA + CA, certificate(ca=False), "-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----", CA + "x" * 10000):
            with pytest.raises(ValueError):
                validate_ca(invalid)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_validate_nodes(case):
    if case == "normaal":
        assert validate_nodes([{"name": "pve-amd", "url": "https://192.168.1.98:8008/#/", "token": TOKEN}], None)[0]["url"] == "https://192.168.1.98:8008"
    elif case == "boundary":
        assert validate_nodes([{"name": "pve-amd", "url": "https://192.168.1.98"}], {"nodes": NODES})[0]["token"] == TOKEN
        assert len(validate_nodes([{"name": f"n{i}", "url": f"https://10.0.0.{i}", "token": TOKEN} for i in range(16)], None)) == 16
    else:
        for invalid in ([], None, [{"name": "pve-amd", "url": "http://192.168.1.98:8008", "token": TOKEN}],
                        [{"name": "../x", "url": "https://h", "token": TOKEN}], [NODES[0], NODES[0]],
                        [{"name": "pve-amd", "url": "https://h", "token": "not-a-token"}],
                        [{"name": "pve-amd", "url": "https://other:8008"}],  # stored token is only reused for the same address
                        [{"name": f"n{i}", "url": f"https://10.0.0.{i}", "token": TOKEN} for i in range(17)]):
            with pytest.raises(ValueError):
                validate_nodes(invalid, {"nodes": NODES})


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_node_summary(case):
    if case == "normaal":
        result = node_summary(HEALTH, STORAGE, SYSTEM, HARDWARE, VMS)
        assert result["overall"] == "error"
        assert {c["id"]: c["status"] for c in result["categories"]} == {"cpu": "ok", "lxc_mounts": "error", "remote_mounts": "warning"}
        assert result["temperature"] == 48.5 and result["powerWatts"] == 61.2 and result["hostUpdates"] == 3 and result["load"] == 1.5
        assert result["disks"][0]["wear"] == 7 and result["zfsPools"][0]["health"] == "ONLINE"
        assert result["lxcUpdates"] == [{"id": 129, "name": "plex", "count": 4, "security": 2, "latest": "1.2"}]
        dumped = json.dumps(result)
        assert "SECRET" not in dumped and "192.168.1.98" not in dumped
    elif case == "boundary":
        empty = node_summary({}, {}, {}, {}, [])
        assert empty["overall"] == "unknown" and empty["categories"] == [] and empty["temperature"] is None and empty["disks"] == []
        assert len(node_summary(HEALTH, STORAGE, SYSTEM, HARDWARE, VMS)["categories"][2]["reason"]) == 200
    else:
        result = node_summary("x", {"disks": "x", "zfs_pools": [None]}, {"temperature": "hot", "load_average": "x"}, {"power_meter": "x"}, [None, {"update_check": "x"}])
        assert result["overall"] == "unknown" and result["temperature"] is None and result["powerWatts"] is None and result["lxcUpdates"] == []
        assert node_summary({"overall": "SOMETHING"}, {}, {}, {}, [])["overall"] == "unknown"


def test_monitor_get_maps_errors_without_leaking_token(monkeypatch, tmp_path):
    node = {"name": "pve-amd", "url": "https://192.168.1.98:8008", "token": TOKEN}
    with pytest.raises(MonitorError, match="cluster-CA kan niet"):
        proxmenux.monitor_get(node, tmp_path / "missing.pem", "system")
    (tmp_path / "ca.pem").write_text(CA)
    for side_effect, text in ((requests.exceptions.SSLError(TOKEN), "certificaat"), (requests.ConnectionError(TOKEN), "bereikbaar")):
        monkeypatch.setattr(proxmenux.requests.Session, "get", Mock(side_effect=side_effect))
        with pytest.raises(MonitorError) as error:
            proxmenux.monitor_get(node, tmp_path / "ca.pem", "system")
        assert text in str(error.value) and TOKEN not in str(error.value)
    get = Mock(return_value=Mock(status_code=401))
    monkeypatch.setattr(proxmenux.requests.Session, "get", get)
    with pytest.raises(MonitorError, match="weigert"):
        proxmenux.monitor_get(node, tmp_path / "ca.pem", "system")
    assert get.call_args.kwargs["verify"] == str(tmp_path / "ca.pem") and get.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_connect(env, case):
    client, hosts, failing, stored = env
    admin = client()
    body = {"ca": CA, "nodes": NODES}
    if case == "normaal":
        assert [n["ok"] for n in admin.post("/api/proxmenux/connection/test", headers=H, json=body).json["nodes"]] == [True, True]
        assert admin.put("/api/proxmenux/connection", headers=H, json=body).status_code == 200
        state = admin.get("/api/proxmenux/connection")
        assert state.json["connected"] is True and TOKEN not in state.get_data(as_text=True)
        assert json.loads(stored.read_text())["nodes"][0]["token"] == TOKEN
        if os.name == "posix":
            assert stored.stat().st_mode & 0o777 == 0o600
        assert admin.get("/api/installations").json["modules"]
    elif case == "boundary":
        admin.put("/api/proxmenux/connection", headers=H, json=body)
        # Re-saving without tokens keeps the stored tokens for the same node and address.
        assert admin.put("/api/proxmenux/connection", headers=H, json={"ca": CA, "nodes": [{"name": n["name"], "url": n["url"]} for n in NODES]}).status_code == 200
        assert admin.delete("/api/proxmenux/connection", headers=H).json == {"connected": False} and not stored.exists()
    else:
        # A swapped address/token is detected through the hostname and nothing is stored.
        hosts["https://192.168.1.97:8008"] = "pve-intel"
        result = admin.put("/api/proxmenux/connection", headers=H, json=body)
        assert result.status_code == 400 and "pve-intel" in result.json["nodes"][1]["error"]
        failing.add("https://192.168.1.98:8008")
        assert admin.post("/api/proxmenux/connection/test", headers=H, json=body).json["nodes"][0]["ok"] is False
        assert admin.put("/api/proxmenux/connection", headers=H, json={"ca": "nope", "nodes": NODES}).status_code == 400
        assert not stored.exists()


def test_connection_is_admin_only_with_csrf(env):
    client, hosts, failing, stored = env
    body = {"ca": CA, "nodes": NODES}
    assert client("nobody@example.test").get("/api/proxmenux/connection").status_code == 401
    assert client("viewer@example.test").get("/api/proxmenux/connection").status_code == 403
    assert client("viewer@example.test").put("/api/proxmenux/connection", headers=H, json=body).status_code == 403
    assert client().put("/api/proxmenux/connection", json=body).status_code == 403
    assert not stored.exists()


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_summary(env, case):
    client, hosts, failing, stored = env
    viewer = client("viewer@example.test")
    if case == "faal":
        assert viewer.get("/api/proxmenux/summary").json["code"] == "not_connected"
        client().put("/api/proxmenux/connection", headers=H, json={"ca": CA, "nodes": NODES})
        failing.add("https://192.168.1.97:8008")
        nodes = viewer.get("/api/proxmenux/summary").json["nodes"]
        # One unreachable node does not block the other and is never shown as healthy.
        assert nodes[0]["overall"] == "error" and nodes[1] == {"name": "pve-nas", "overall": "unknown", "error": "Monitor niet bereikbaar.", "stale": True}
        assert client("other@example.test").get("/api/proxmenux/summary").status_code == 403
        return
    client().put("/api/proxmenux/connection", headers=H, json={"ca": CA, "nodes": NODES})
    first = viewer.get("/api/proxmenux/summary")
    assert first.status_code == 200 and first.json["nodes"][0]["stale"] is False
    assert TOKEN not in first.get_data(as_text=True) and "SECRET" not in first.get_data(as_text=True)
    if case == "boundary":
        # Expired cache: known data is returned at once and marked stale when the refresh fails.
        original = proxmenux.CACHE_SECONDS
        proxmenux.CACHE_SECONDS = -1
        failing.add("https://192.168.1.98:8008")
        try:
            viewer.get("/api/proxmenux/summary")
            import time
            for _ in range(50):
                node = viewer.get("/api/proxmenux/summary").json["nodes"][0]
                if node.get("error"):
                    break
                time.sleep(0.02)
            assert node["stale"] is True and node["temperature"] == 48.5 and "bereikbaar" in node["error"]
        finally:
            proxmenux.CACHE_SECONDS = original


class FakeResponse:
    def __init__(self, status, body=None):
        self.status_code, self.body = status, body
    def json(self):
        if self.body is None:
            raise ValueError
        return self.body


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_detect_states(monkeypatch, tmp_path, case):
    calls = []
    def fake(url, **kwargs):
        calls.append((url, kwargs))
        return responder(url)
    # https goes through the cluster-CA session, the http probe through plain requests.get.
    monkeypatch.setattr(proxmenux.requests.Session, "get", staticmethod(fake))
    monkeypatch.setattr(proxmenux.requests, "get", fake)
    (tmp_path / "ca.pem").write_text(CA)
    url = "https://192.168.1.98:8008"
    if case == "normaal":
        responder = lambda u: FakeResponse(200, {"auth_enabled": True})
        assert proxmenux.detect(url, tmp_path / "ca.pem") == {"state": "ready"}
        assert calls[0][1]["verify"] == str(tmp_path / "ca.pem") and "headers" not in calls[0][1]
    elif case == "boundary":
        responder = lambda u: FakeResponse(200, {"auth_enabled": False})
        assert proxmenux.detect(url, tmp_path / "ca.pem") == {"state": "auth_disabled"}
        def http_only(u):
            if u.startswith("https://"):
                raise requests.ConnectionError()
            return FakeResponse(200, {"status": "healthy"})
        responder = http_only
        assert proxmenux.detect(url, tmp_path / "ca.pem") == {"state": "http_only"}
        assert calls[-1][0] == "http://192.168.1.98:8008/api/health" and "headers" not in calls[-1][1]
    else:
        def untrusted(u):
            raise requests.exceptions.SSLError()
        responder = untrusted
        assert proxmenux.detect(url, tmp_path / "ca.pem") == {"state": "untrusted_tls"}
        def absent(u):
            raise requests.ConnectionError()
        responder = absent
        assert proxmenux.detect(url, tmp_path / "ca.pem") == {"state": "absent"}
        responder = lambda u: FakeResponse(200, None)
        assert proxmenux.detect(url, tmp_path / "ca.pem")["state"] == "absent"


def test_detect_endpoint_validation_and_access(env, monkeypatch):
    client, hosts, failing, stored = env
    monkeypatch.setattr(proxmenux, "detect", lambda url, ca_path: {"state": "ready" if url.endswith(".98:8008") else "absent"})
    admin = client()
    body = {"ca": CA, "nodes": [{"name": "pve-amd", "url": "https://192.168.1.98"}, {"name": "pve-new", "url": "https://192.168.1.50"}]}
    result = admin.post("/api/proxmenux/connection/detect", headers=H, json=body).json
    assert [n["state"] for n in result["nodes"]] == ["ready", "absent"] and result["installCommands"]["stable"].endswith('/main/install_proxmenux.sh)"') and "/develop/install_proxmenux_beta.sh" in result["installCommands"]["beta"]
    assert admin.post("/api/proxmenux/connection/detect", headers=H, json={"ca": CA, "nodes": []}).status_code == 400
    assert admin.post("/api/proxmenux/connection/detect", headers=H, json={"ca": "x", "nodes": body["nodes"]}).status_code == 400
    assert admin.post("/api/proxmenux/connection/detect", headers=H, json={"ca": CA, "nodes": [{"name": "../x", "url": "https://h"}]}).status_code == 400
    assert client("viewer@example.test").post("/api/proxmenux/connection/detect", headers=H, json=body).status_code == 403
    assert admin.post("/api/proxmenux/connection/detect", json=body).status_code == 403


def tls_pair(tmp_path, ip="127.0.0.1", critical=False):
    """A Proxmox-like CA (no keyUsage, like pve-root-ca.pem) and a node certificate for one IP."""
    import ipaddress
    from cryptography.x509.oid import ExtendedKeyUsageOID
    now = datetime.datetime.now(datetime.timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Proxmox Virtual Environment"), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PVE Cluster Manager CA")])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key()).serial_number(1)
          .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=2))
          .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=critical).sign(ca_key, hashes.SHA256()))
    key = ec.generate_private_key(ec.SECP256R1())
    leaf = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "pve-amd.home")])).issuer_name(ca_name)
            .public_key(key.public_key()).serial_number(2).not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip))]), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    ca_path, cert_path, key_path = tmp_path / "ca.pem", tmp_path / "node.pem", tmp_path / "node.key"
    ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    cert_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return ca_path, cert_path, key_path


@pytest.fixture
def monitor_server(tmp_path):
    """Real HTTPS server on 127.0.0.1 that answers like ProxMenux /api/auth/status."""
    import http.server, ssl, threading
    def start(ip="127.0.0.1", critical=False):
        ca_path, cert_path, key_path = tls_pair(tmp_path, ip, critical)
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = json.dumps({"auth_enabled": True, "hostname": "pve-amd"}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            def log_message(self, *args):
                pass
        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"https://127.0.0.1:{server.server_address[1]}", ca_path
    servers = []
    yield start
    for server in servers:
        server.shutdown()


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_cluster_ca_tls_against_real_server(monitor_server, tmp_path, case):
    url, ca_path = monitor_server(critical=(case == "boundary"))
    node = {"name": "pve-amd", "url": url, "token": TOKEN}
    if case in ("normaal", "boundary"):
        # A Proxmox-like CA (non-critical basicConstraints) is accepted; the strict profile check is not applied.
        assert proxmenux.monitor_get(node, ca_path, "system")["hostname"] == "pve-amd"
        assert proxmenux.detect(url, ca_path) == {"state": "ready"}
        context = ssl.create_default_context(cafile=str(ca_path))
        context.verify_flags |= ssl.VERIFY_X509_STRICT
        if case == "normaal":
            # Documents the original failure on Python 3.13: the strict profile rejects this CA.
            with pytest.raises(ssl.SSLError):
                import socket
                port = int(url.rsplit(":", 1)[1])
                with socket.create_connection(("127.0.0.1", port), 5) as raw, context.wrap_socket(raw, server_hostname="127.0.0.1"):
                    pass
    else:
        other_ca, _, _ = tls_pair(tmp_path / "x" if (tmp_path / "x").mkdir() is None else tmp_path)
        assert proxmenux.detect(url, other_ca) == {"state": "untrusted_tls"}
        with pytest.raises(MonitorError, match="certificaat"):
            proxmenux.monitor_get(node, other_ca, "system")
        # Certificate for another IP: chain is valid, hostname check still rejects it.
        wrong_url, wrong_ca = monitor_server(ip="192.0.2.10")
        assert proxmenux.detect(wrong_url, wrong_ca) == {"state": "untrusted_tls"}
