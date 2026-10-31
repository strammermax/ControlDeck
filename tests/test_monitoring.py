"""Monitoring of app connections: agent probe in the container namespace, discovery, API and access."""
import importlib.util
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import Mock

import pytest

from backend import monitoring
from backend.app import create_app
from backend.vault import VaultError

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("controldeck_agent_monitoring", ROOT / "scripts/controldeck-agent.py")
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)
H = {"X-CSRF-Token": "csrf"}


@pytest.fixture
def listener():
    """A local TCP port that accepts, and one that is closed."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(256)
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    closed_port = closed.getsockname()[1]
    closed.close()
    yield server.getsockname()[1], closed_port
    server.close()


@pytest.fixture
def in_namespace(monkeypatch):
    """Plays nsenter: the probe runs in this process with the given container files."""
    files = {"hosts": "127.0.0.1 localhost\n127.0.0.1 qbittorrent.home qbittorrent\n", "resolv.conf": ""}
    monkeypatch.setattr(agent, "container_pid", lambda vmid: 4242 if vmid == 137 else None)
    monkeypatch.setattr(agent, "container_file", lambda pid, name, limit=65536: files[name])
    monkeypatch.setattr(agent, "netns_run", lambda pid, mode, data: agent.probe_targets(data) if mode == "__probe" else agent.tunnel_ingress(data))
    return files


def probe(payload):
    return agent.handle("net.probe", json.dumps(payload))


# --- agent ------------------------------------------------------------------------------------------------

def test_agent_probe_normal_resolves_with_container_hosts_and_connects(in_namespace, listener):
    open_port, closed_port = listener
    answer = probe({"vmid": 137, "targets": [{"host": "qbittorrent.home", "port": open_port}, {"host": "127.0.0.1", "port": closed_port}]})
    assert answer["ok"], answer
    first, second = answer["data"]["results"]
    assert first["ok"] and first["ip"] == "127.0.0.1" and isinstance(first["ms"], int)
    assert second["ok"] is False and "geweigerd" in second["error"]


def test_agent_probe_boundary_short_name_uses_hosts_and_64_targets_allowed(in_namespace, listener):
    open_port, _ = listener
    answer = probe({"vmid": 137, "targets": [{"host": "qbittorrent", "port": open_port}] * 64})
    assert answer["ok"] and len(answer["data"]["results"]) == 64 and all(r["ok"] for r in answer["data"]["results"])
    assert probe({"vmid": 137, "targets": [{"host": "x", "port": 1}] * 65})["error"] == "invalid_input"


@pytest.mark.parametrize("payload", [
    {"vmid": 137, "targets": [{"host": "a b", "port": 80}]},
    {"vmid": 137, "targets": [{"host": "ok.home", "port": 0}]},
    {"vmid": 137, "targets": [{"host": "ok.home", "port": 80, "cmd": "id"}]},
    {"vmid": 137, "targets": []},
    {"vmid": "137", "targets": [{"host": "ok.home", "port": 80}]},
    {"vmid": 99, "targets": [{"host": "ok.home", "port": 80}]},
])
def test_agent_probe_failure_rejects_malformed_input(in_namespace, payload):
    assert probe(payload)["error"] == "invalid_input"


def test_agent_probe_failure_stopped_container_and_unresolvable_name(in_namespace, listener):
    assert probe({"vmid": 555, "targets": [{"host": "x.home", "port": 80}]})["error"] == "not_running"
    in_namespace["resolv.conf"] = "nameserver 127.0.0.1\n"
    result = probe({"vmid": 137, "targets": [{"host": "nergens.home", "port": 80}]})["data"]["results"][0]
    assert result["ok"] is False and "niet op te lossen" in result["error"] and result["ip"] is None


def test_agent_probe_is_read_only_and_never_audited(in_namespace, listener, tmp_path, monkeypatch):
    monkeypatch.setenv("CONTROLDECK_AGENT_ROOT", str(tmp_path))
    probe({"vmid": 137, "targets": [{"host": "127.0.0.1", "port": listener[0]}]})
    assert not (tmp_path / "var/log/controldeck-agent.log").exists()


def test_dns_query_normal_boundary_and_failure(monkeypatch):
    """A tiny DNS server: one A answer, NXDOMAIN, and a reply with a foreign id."""
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]

    def serve():
        for mode in ("answer", "nxdomain", "wrong-id"):
            data, peer = server.recvfrom(512)
            ident = data[:2] if mode != "wrong-id" else b"\x00\x00"
            flags = b"\x81\x80" if mode == "answer" else b"\x81\x83"
            body = data[12:]
            answer = (b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04" + bytes([192, 168, 20, 137])) if mode == "answer" else b""
            real(server, ident + flags + b"\x00\x01" + (b"\x00\x01" if answer else b"\x00\x00") + b"\x00\x00\x00\x00" + body + answer, peer)
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    real = socket.socket.sendto
    monkeypatch.setattr(socket.socket, "sendto", lambda self, packet, address: real(self, packet, ("127.0.0.1", port)))
    assert agent.dns_query("10.0.0.1", "arrsuite.home", 2) == "192.168.20.137"
    assert agent.dns_query("10.0.0.1", "nergens.home", 2) is None
    assert agent.dns_query("10.0.0.1", "arrsuite.home", 2) is None
    server.close()


def test_resolve_search_domains_and_literal_ips():
    servers, search = agent.parse_resolv("nameserver 192.168.20.1\nsearch home lan\n")
    assert servers == ["192.168.20.1"] and search == ["home", "lan"]
    assert agent.resolve("192.168.1.96", {}, [], [], 1) == ("192.168.1.96", None)
    assert agent.resolve("Plex.Home.", {"plex.home": "192.168.20.129"}, [], [], 1) == ("192.168.20.129", None)
    assert agent.resolve("plex.home", {}, [], [], 1)[1] == "Geen DNS-server in de container."


def test_tunnel_ingress_reads_rules_without_other_config(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"config": {"ingress": [{"hostname": "ha.vanburik.info", "service": "http://192.168.20.106:8123", "originRequest": {"secret": "x"}},
                                                      {"service": "http_status:404"}]}}).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    monkeypatch.setattr(agent, "TUNNEL_PORTS", [1, server.server_address[1]])
    assert agent.tunnel_ingress({}) == {"ingress": [{"hostname": "ha.vanburik.info", "service": "http://192.168.20.106:8123"}]}
    monkeypatch.setattr(agent, "TUNNEL_PORTS", [1])
    assert agent.tunnel_ingress({}) == {"ingress": None}
    server.server_close()


def test_internal_probe_mode_is_not_reachable_over_ssh(monkeypatch, capsys):
    """Over SSH only SSH_ORIGINAL_COMMAND counts; '__probe' is not an action name there."""
    monkeypatch.setenv("SSH_ORIGINAL_COMMAND", "__probe")
    monkeypatch.setattr("sys.stdin", Mock(buffer=Mock(read=lambda n: b"{}")))
    assert agent.main(["__probe"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "unknown_action"


# --- backend ----------------------------------------------------------------------------------------------

class FakeTransport:
    """Plays a Sonarr/Prowlarr API."""
    answers = {}

    def __init__(self, source):
        self.url = source["url"]

    def call(self, path, headers=None, **kwargs):
        assert headers == {"X-Api-Key": "geheim0123456789abcdef"}
        value = self.answers.get(path)
        if isinstance(value, Exception):
            raise value
        return value or []

    def close(self):
        pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([
        {"email": "admin@example.test", "role": "admin"},
        {"email": "viewer@example.test", "role": "user", "modules": ["monitoring"]},
        {"email": "other@example.test", "role": "user", "modules": ["terminal"]},
    ]))
    vault = {"CONTROLDECK_MONITORING": json.dumps({"sources": {"sonarr": {"kind": "sonarr", "title": "Sonarr", "url": "http://192.168.20.137:8989", "allowHttp": True, "apiKey": "geheim0123456789abcdef", "vmid": 137}}})}
    monkeypatch.setattr(monitoring, "Transport", FakeTransport)
    monkeypatch.setattr(monitoring, "enrolled_nodes", lambda: set())
    monkeypatch.setattr(monitoring, "guests", lambda data_dir: {})
    FakeTransport.answers = {}
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True
    holder = {"vault": vault, "fail": False}

    def read():
        if holder["fail"]:
            raise VaultError("weg")
        return holder["vault"]
    app.extensions["controldeck_vault"] = Mock(read=read)

    def client(email="admin@example.test"):
        test_client = app.test_client()
        with test_client.session_transaction() as session:
            session["identity"] = {"email": email, "sub": email}
            session["csrf"] = "csrf"
        return test_client
    return client, app, holder


def test_api_requires_login_module_permission_manager_role_and_csrf(env):
    client, app, _ = env
    assert app.test_client().get("/api/monitoring").status_code == 401
    assert client("other@example.test").get("/api/monitoring").status_code == 403
    viewer = client("viewer@example.test")
    assert viewer.get("/api/monitoring").status_code == 200
    assert viewer.post("/api/monitoring/check", headers=H).status_code == 403
    assert viewer.post("/api/monitoring/connections", json={"source": "x", "host": "a.home", "port": 1}, headers=H).status_code == 403
    assert client().post("/api/monitoring/connections", json={"source": "x", "host": "a.home", "port": 1}).status_code == 403


def test_manual_connection_normal_checked_from_controldeck_with_state_changes(env, listener):
    client, app, _ = env
    admin, (open_port, closed_port) = client(), listener
    created = admin.post("/api/monitoring/connections", json={"source": "Home Assistant", "host": "127.0.0.1", "port": open_port, "label": "Zigbee"}, headers=H)
    assert created.status_code == 201
    down = admin.post("/api/monitoring/connections", json={"source": "Lidarr", "host": "127.0.0.1", "port": closed_port}, headers=H).get_json()["id"]
    data = admin.post("/api/monitoring/check", headers=H).get_json()
    rows = {row["source"]: row for row in data["connections"]}
    assert rows["Home Assistant"]["ok"] is True and rows["Home Assistant"]["via"] == "ControlDeck" and rows["Home Assistant"]["label"] == "Zigbee"
    assert rows["Lidarr"]["ok"] is False and "geweigerd" in rows["Lidarr"]["error"]
    assert {event["source"] for event in data["events"]} == {"Home Assistant", "Lidarr"}
    since = rows["Home Assistant"]["since"]
    again = {row["source"]: row for row in admin.post("/api/monitoring/check", headers=H).get_json()["connections"]}
    assert again["Home Assistant"]["since"] == since, "unchanged state keeps its 'since'"
    assert admin.delete(f"/api/monitoring/connections/{down}", headers=H).status_code == 200
    assert [row["source"] for row in admin.get("/api/monitoring").get_json()["connections"]] == ["Home Assistant"]


@pytest.mark.parametrize("body", [
    {"source": "", "host": "a.home", "port": 80},
    {"source": "HA", "host": "a b", "port": 80},
    {"source": "HA", "host": "a.home", "port": 70000},
    {"source": "HA", "host": "a.home", "port": "80"},
    {"source": "HA", "host": "a.home", "port": 80, "vmid": 5},
    {"source": "HA", "host": "a.home", "port": 80, "command": "x"},
])
def test_manual_connection_failure_rejects_invalid_input(env, body):
    client, _, _ = env
    assert client().post("/api/monitoring/connections", json=body, headers=H).status_code == 400


def test_manual_connection_boundary_duplicate_and_unknown_delete(env):
    client, _, _ = env
    admin, body = client(), {"source": "HA", "host": "SLZB.home.", "port": 6638}
    assert admin.post("/api/monitoring/connections", json=body, headers=H).get_json()["host"] == "slzb.home"
    assert admin.post("/api/monitoring/connections", json=body, headers=H).status_code == 409
    assert admin.delete("/api/monitoring/connections/0000000000000000", headers=H).status_code == 404
    assert admin.delete("/api/monitoring/connections/../../etc", headers=H).status_code in (404, 405)


def test_discovery_from_arr_api_lists_clients_and_indexers_without_leaking_keys(env, monkeypatch):
    client, _, _ = env
    monkeypatch.setattr(monitoring, "probe_central", lambda host, port: {"ok": True, "ip": "192.168.20.137", "ms": 1})
    FakeTransport.answers = {
        "/api/v3/downloadclient": [{"name": "qBittorrent", "fields": [{"name": "host", "value": "localhost"}, {"name": "port", "value": 8080}]},
                                   {"name": "Uit", "enable": False, "fields": [{"name": "host", "value": "x"}, {"name": "port", "value": 1}]}],
        "/api/v3/indexer": [{"name": "Prowlarr", "fields": [{"name": "baseUrl", "value": "http://prowlarr.home:9696/1/"}, {"name": "apiKey", "value": "idx"}]}],
    }
    response = client("viewer@example.test").get("/api/monitoring")
    assert response.get_json()["connections"] == []
    data = client().post("/api/monitoring/check", headers=H).get_json()
    found = sorted((row["label"], row["host"], row["port"], row["source"]) for row in data["connections"])
    assert found == [("Downloadclient: qBittorrent", "localhost", 8080, "Sonarr"), ("Indexer: Prowlarr", "prowlarr.home", 9696, "Sonarr")]
    text = client("viewer@example.test").get("/api/monitoring").get_data(as_text=True)
    assert "geheim0123456789abcdef" not in text and "idx" not in text


def test_vault_outage_keeps_discovered_connections(env, monkeypatch):
    """Regression guard: an unreachable Infisical must not wipe the discovered list (it would look like everything vanished)."""
    client, _, holder = env
    monkeypatch.setattr(monitoring, "probe_central", lambda host, port: {"ok": True, "ip": "1.2.3.4", "ms": 1})
    FakeTransport.answers = {"/api/v3/downloadclient": [{"name": "SAB", "fields": [{"name": "host", "value": "sab.home"}, {"name": "port", "value": 8080}]}]}
    admin = client()
    assert len(admin.post("/api/monitoring/check", headers=H).get_json()["connections"]) == 1
    holder["fail"] = True
    data = admin.post("/api/monitoring/check", headers=H).get_json()
    assert len(data["connections"]) == 1 and data["sourceErrors"] == [{"source": "infisical", "error": "Monitoringbronnen zijn niet beschikbaar. Controleer Infisical."}]


def test_discovery_failure_of_one_source_is_reported_and_keeps_its_previous_list(env, monkeypatch):
    client, _, _ = env
    monkeypatch.setattr(monitoring, "probe_central", lambda host, port: {"ok": True, "ip": "1.2.3.4", "ms": 1})
    FakeTransport.answers = {"/api/v3/downloadclient": [{"name": "SAB", "fields": [{"name": "host", "value": "sab.home"}, {"name": "port", "value": 8080}]}]}
    admin = client()
    admin.post("/api/monitoring/check", headers=H)
    FakeTransport.answers = {"/api/v3/downloadclient": monitoring.ProviderError("De bron weigert de toegangsgegevens.")}
    data = admin.post("/api/monitoring/check", headers=H).get_json()
    assert [row["host"] for row in data["connections"]] == ["sab.home"]
    assert data["sourceErrors"] == [{"source": "sonarr", "error": "De bron weigert de toegangsgegevens."}]


@pytest.mark.parametrize("config", [
    {"sources": {"Sonarr!": {"kind": "sonarr"}}},
    {"sources": {"sonarr": {"kind": "unknown"}}},
    {"sources": {"sonarr": {"kind": "sonarr", "url": "http://x:1", "allowHttp": True}}},
    {"sources": {"sonarr": {"kind": "sonarr", "url": "ftp://x", "apiKey": "k"}}},
    {"sources": {"tunnel": {"kind": "cloudflared"}}},
    {"sources": {"tunnel": {"kind": "cloudflared", "vmid": "127"}}},
])
def test_source_configuration_failure_is_rejected(config):
    with pytest.raises(monitoring.MonitorError):
        monitoring.validate_sources(config)


def test_source_check_goes_through_agent_for_running_lxc(env, monkeypatch, in_namespace, listener):
    """LXC on an enrolled node: the agent probes from the container; a failing agent is 'unknown', never 'down'."""
    client, _, holder = env
    holder["vault"] = {"CONTROLDECK_MONITORING": json.dumps({"sources": {"tunnel": {"kind": "cloudflared", "title": "Cloudflare-tunnel", "vmid": 137}}})}
    monkeypatch.setattr(monitoring, "enrolled_nodes", lambda: {"pve-intel"})
    monkeypatch.setattr(monitoring, "guests", lambda data_dir: {137: {"vmid": 137, "node": "pve-intel", "type": "lxc", "status": "running"}})
    monkeypatch.setattr(agent, "tunnel_ingress", lambda data: {"ingress": [{"hostname": "ha.vanburik.info", "service": f"http://127.0.0.1:{listener[0]}"},
                                                                           {"hostname": "x.vanburik.info", "service": "http_status:404"}]})
    state = {"down": False}

    def proxy(request, timeout=75):
        if state["down"]:
            return {"ok": False, "message": "De node antwoordde niet op tijd."}
        return {"ok": True, "data": agent.handle(request["action"], json.dumps(request["payload"]))}
    monkeypatch.setattr(monitoring, "proxy_request", proxy)
    admin = client()
    row = admin.post("/api/monitoring/check", headers=H).get_json()["connections"][0]
    assert (row["label"], row["ok"], row["via"]) == ("Tunnel: ha.vanburik.info", True, "bron (pve-intel/137)")
    state["down"] = True
    monitoring_app = admin.application.extensions["controldeck_monitor"]
    monitoring_app.check()
    row = admin.get("/api/monitoring").get_json()["connections"][0]
    assert row["ok"] is None and "Controle vanaf de bron mislukt" in row["error"]


def test_url_target_boundaries():
    assert monitoring.url_target("http://prowlarr:9696/1/") == ("prowlarr", 9696)
    assert monitoring.url_target("https://Kasm.home") == ("kasm.home", 443)
    assert monitoring.url_target("http_status:404") is None
    assert monitoring.url_target("http://[::1") is None


# --- learned connections --------------------------------------------------------------------------------

TCP = """  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode
   0: 00000000:3039 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 1 1
   1: 9A14A8C0:C350 0B14A8C0:1F90 01 00000000:00000000 00:00000000 00000000     0        0 2 1
   2: 9A14A8C0:C351 0B14A8C0:1F90 01 00000000:00000000 00:00000000 00000000     0        0 3 1
   3: 9A14A8C0:3039 2F0114C0:D431 01 00000000:00000000 00:00000000 00000000     0        0 4 1
   4: 0100007F:C352 0100007F:1F90 01 00000000:00000000 00:00000000 00000000     0        0 5 1
   5: kapot
"""
TCP6 = """  sl  local_address                         remote_address                        st
   0: 0000000000000000FFFF00009A14A8C0:C353 0000000000000000FFFF000001010101:01BB 01
"""


def test_outbound_normal_boundary_and_failure():
    """Normal: two sockets to 192.168.20.11:8080 counted once. Boundary: IPv4-mapped IPv6. Excluded: inbound
    (local port 12345 listens), loopback, malformed lines."""
    assert agent.outbound([TCP, TCP6]) == [{"ip": "1.1.1.1", "port": 443, "count": 1}, {"ip": "192.168.20.11", "port": 8080, "count": 2}]
    assert agent.outbound(["header only\n"]) == []


@pytest.mark.parametrize("vmids", [[], ["137"], [99], list(range(100, 301)), None])
def test_agent_connections_failure_rejects_invalid_vmids(vmids):
    assert agent.handle("net.connections", json.dumps({"vmids": vmids}))["error"] == "invalid_input"


def test_agent_connections_skips_stopped_containers(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "container_pid", lambda vmid: None)
    assert agent.handle("net.connections", json.dumps({"vmids": [137]}))["data"] == {"containers": {}, "names": {}, "ports": {}}


def test_learned_connections_are_checked_from_the_container_and_expire(env, monkeypatch, in_namespace, listener):
    client, _, holder = env
    holder["vault"] = {}
    monkeypatch.setattr(monitoring, "enrolled_nodes", lambda: {"pve-amd"})
    monkeypatch.setattr(monitoring, "guests", lambda data_dir: {137: {"vmid": 137, "node": "pve-amd", "type": "lxc", "status": "running", "name": "remvebg"}})
    monkeypatch.setattr(agent, "outbound", lambda tables: [{"ip": "127.0.0.2", "port": listener[0], "count": 1}, {"ip": "1.1.1.1", "port": 443, "count": 3},
                                                           {"ip": "158.173.241.24", "port": 55794, "count": 1}, {"ip": "192.168.20.5", "port": 32400, "count": 1}])
    monkeypatch.setattr(agent, "container_pid", lambda vmid: 4242)
    monkeypatch.setattr(agent, "container_namespaces", lambda vmid, init: [{"pid": 4242, "app": ""}])
    calls = []

    def proxy(request, timeout=75):
        calls.append(request["action"])
        if request["action"] == "net.probe":
            return {"ok": True, "data": {"ok": True, "data": {"results": [{"host": t["host"], "port": t["port"], "ok": True, "ip": t["host"], "ms": 2} for t in request["payload"]["targets"]]}}}
        return {"ok": True, "data": agent.handle(request["action"], json.dumps(request["payload"]))}
    monkeypatch.setattr(monitoring, "proxy_request", proxy)
    admin = client()
    rows = {row["host"]: row for row in admin.post("/api/monitoring/check", headers=H).get_json()["connections"]}
    assert rows["1.1.1.1"]["label"] == "Gezien · internet" and rows["127.0.0.2"]["label"] == "Gezien · intern"
    assert rows["1.1.1.1"]["source"] == "remvebg" and rows["1.1.1.1"]["via"] == "bron (pve-amd/137)" and rows["1.1.1.1"]["ok"] is True
    assert "158.173.241.24" not in rows, "public high port = peer (BitTorrent), not a dependency"
    assert "192.168.20.5" in rows, "internal high ports (e.g. Plex 32400) are kept"
    assert calls.count("net.connections") == 1
    monitor = admin.application.extensions["controldeck_monitor"]
    monkeypatch.setattr(monitoring.time, "time", lambda: 10**10)
    with monitoring.database(monitor.path) as db:
        assert monitor.connections(db) == [], "not seen for longer than the TTL: no longer checked"


def test_learning_failure_on_a_node_keeps_previous_list(env, monkeypatch):
    client, _, holder = env
    holder["vault"] = {}
    monkeypatch.setattr(monitoring, "enrolled_nodes", lambda: {"pve-amd"})
    monkeypatch.setattr(monitoring, "guests", lambda data_dir: {137: {"vmid": 137, "node": "pve-amd", "type": "lxc", "status": "running", "name": "remvebg"}})
    monkeypatch.setattr(monitoring, "probe_all", lambda connections, placement: {})
    answers = [{"ok": True, "data": {"ok": True, "data": {"containers": {"137": [{"app": "", "endpoints": [{"ip": "8.8.8.8", "port": 53}]}]}}}},
               {"ok": False, "message": "De node antwoordde niet op tijd."}]
    monkeypatch.setattr(monitoring, "proxy_request", lambda request, timeout=75: answers.pop(0))
    monitor = client().application.extensions["controldeck_monitor"]
    monitor.check(force_discovery=True)
    monitor.check(force_discovery=True)
    with monitoring.database(monitor.path) as db:
        assert [row["host"] for row in monitor.connections(db)] == ["8.8.8.8"]


def test_docker_app_namespaces_label_learned_connections_and_probe_from_that_app(env, monkeypatch):
    """Apps in Docker inside an LXC have their own network: learn and probe per app, so 'qbittorrent'/'localhost' mean what Sonarr sees."""
    client, _, holder = env
    holder["vault"] = {"CONTROLDECK_MONITORING": json.dumps({"sources": {"sonarr": {"kind": "sonarr", "title": "Sonarr", "url": "http://192.168.20.137:8989", "allowHttp": True, "apiKey": "geheim0123456789abcdef", "vmid": 137, "app": "Sonarr"}}})}
    FakeTransport.answers = {"/api/v3/downloadclient": [{"name": "qBittorrent", "fields": [{"name": "host", "value": "qbittorrent"}, {"name": "port", "value": 8080}]}]}
    monkeypatch.setattr(monitoring, "enrolled_nodes", lambda: {"pve-amd"})
    monkeypatch.setattr(monitoring, "guests", lambda data_dir: {137: {"vmid": 137, "node": "pve-amd", "type": "lxc", "status": "running", "name": "arrsuite"}})
    monkeypatch.setattr(agent, "container_pid", lambda vmid: 1000)
    monkeypatch.setattr(agent, "container_namespaces", lambda vmid, init: [{"pid": 1000, "app": ""}, {"pid": 2000, "app": "sonarr"}])
    monkeypatch.setattr(agent, "outbound", lambda tables: [{"ip": "192.168.20.137", "port": 8080, "count": 1}])
    monkeypatch.setattr(agent, "container_file", lambda pid, name, limit=65536: "")
    used = []

    def netns(pid, mode, data):
        used.append(pid)
        return {"results": [{"host": t["host"], "port": t["port"], "ok": True, "ip": "172.18.0.5", "ms": 1} for t in data["targets"]]}
    monkeypatch.setattr(agent, "netns_run", netns)
    monkeypatch.setattr(monitoring, "proxy_request", lambda request, timeout=75: {"ok": True, "data": agent.handle(request["action"], json.dumps(request["payload"]))})
    rows = client().post("/api/monitoring/check", headers=H).get_json()["connections"]
    sonarr = next(row for row in rows if row["source"] == "Sonarr")
    assert sonarr["host"] == "qbittorrent" and sonarr["via"] == "bron (pve-amd/137/sonarr)" and sonarr["ok"] is True
    assert {row["source"] for row in rows if row["origin"] == "learned"} == {"arrsuite", "arrsuite / sonarr"}
    assert 2000 in used, "the Sonarr connection is probed from Sonarr's namespace"


def test_agent_probe_app_boundary_and_failure(in_namespace, monkeypatch):
    monkeypatch.setattr(agent, "container_namespaces", lambda vmid, init: [{"pid": 4242, "app": ""}, {"pid": 5000, "app": "sonarr"}])
    assert probe({"vmid": 137, "app": "radarr", "targets": [{"host": "x.home", "port": 80}]})["error"] == "not_running"
    assert probe({"vmid": 137, "app": "../etc", "targets": [{"host": "x.home", "port": 80}]})["error"] == "invalid_input"
    assert probe({"vmid": 137, "app": 5, "targets": [{"host": "x.home", "port": 80}]})["error"] == "invalid_input"


def test_docker_names_parses_only_valid_lines(monkeypatch):
    output = "sonarr 4026536642\nqbittorrent 4026538083\nkapot\n../x 12\nradarr notanumber\n"
    monkeypatch.setattr(agent.subprocess, "run", lambda *a, **k: Mock(stdout=output, returncode=0))
    assert agent.docker_names(137) == {4026536642: "sonarr", 4026538083: "qbittorrent"}
    monkeypatch.setattr(agent.subprocess, "run", Mock(side_effect=OSError))
    assert agent.docker_names(137) == {}


def test_source_app_requires_vmid():
    with pytest.raises(monitoring.MonitorError):
        monitoring.validate_sources({"sources": {"sonarr": {"kind": "sonarr", "url": "http://x:1", "allowHttp": True, "apiKey": "k", "app": "Sonarr"}}})
