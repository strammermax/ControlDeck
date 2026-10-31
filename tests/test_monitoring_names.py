"""Readable names for learned connections: Docker container names, reverse DNS and CDN labels."""
import importlib.util
import json
import socket
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from backend import monitoring
from backend.app import create_app

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("controldeck_agent_names", ROOT / "scripts/controldeck-agent.py")
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)
H = {"X-CSRF-Token": "csrf"}


def test_docker_info_maps_container_ips_to_names(monkeypatch):
    output = "qbittorrent 4026538083 172.18.0.8 \nsonarr 4026536642 172.18.0.5 10.10.0.2\nkapot\n../x 12 1.2.3.4\nradarr 4026538699 niet-een-ip\n"
    monkeypatch.setattr(agent.subprocess, "run", lambda *a, **k: Mock(stdout=output, returncode=0))
    names, addresses = agent.docker_info(137)
    assert names == {4026538083: "qbittorrent", 4026536642: "sonarr", 4026538699: "radarr"}
    assert addresses == {"172.18.0.8": "qbittorrent", "172.18.0.5": "sonarr", "10.10.0.2": "sonarr"}
    monkeypatch.setattr(agent.subprocess, "run", Mock(side_effect=OSError))
    assert agent.docker_info(137) == ({}, {})


def test_reverse_name_normal_cdn_and_failure(monkeypatch):
    monkeypatch.setattr(monitoring.socket, "gethostbyaddr", lambda ip: ("arrsuite.home.", [], [ip]))
    assert monitoring.reverse_name("192.168.20.137") == "arrsuite.home"
    assert monitoring.reverse_name("172.67.70.98") == "Cloudflare (CDN)", "no lookup needed for known CDN ranges"
    monkeypatch.setattr(monitoring.socket, "gethostbyaddr", Mock(side_effect=socket.herror))
    assert monitoring.reverse_name("8.8.4.4") == ""
    monkeypatch.setattr(monitoring.socket, "gethostbyaddr", lambda ip: ("bad name;rm", [], [ip]))
    assert monitoring.reverse_name("8.8.4.4") == "", "only valid hostnames are shown"


def test_resolve_names_boundary_slow_dns_does_not_block_and_cache_is_used(monkeypatch):
    calls = []

    def lookup(ip):
        calls.append(ip)
        if ip == "10.0.0.9":
            time.sleep(2)
        return (f"host-{ip.split('.')[-1]}.home", [], [ip])
    monkeypatch.setattr(monitoring.socket, "gethostbyaddr", lookup)
    cache = {}
    started = time.monotonic()
    names = monitoring.resolve_names(["10.0.0.1", "10.0.0.9"], cache, timeout=0.5)
    assert time.monotonic() - started < 1.5
    assert names == {"10.0.0.1": "host-1.home"}, "slow answers stay unknown this round"
    calls.clear()
    assert monitoring.resolve_names(["10.0.0.1"], cache)["10.0.0.1"] == "host-1.home" and calls == [], "cached"


@pytest.fixture
def env(tmp_path, monkeypatch):
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([{"email": "admin@example.test", "role": "admin"}]))
    monkeypatch.setattr(monitoring, "enrolled_nodes", lambda: {"pve-amd"})
    monkeypatch.setattr(monitoring, "guests", lambda data_dir: {137: {"vmid": 137, "node": "pve-amd", "type": "lxc", "status": "running", "name": "arrsuite"}})
    monkeypatch.setattr(monitoring, "probe_all", lambda connections, placement: {})
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True
    app.extensions["controldeck_vault"] = Mock(read=lambda: {})
    client = app.test_client()
    with client.session_transaction() as session:
        session["identity"] = {"email": "admin@example.test", "sub": "admin@example.test"}
        session["csrf"] = "csrf"
    return client, app.extensions["controldeck_monitor"]


def answer(names=None, endpoints=None):
    return {"ok": True, "data": {"ok": True, "data": {
        "containers": {"137": [{"app": "sonarr", "endpoints": endpoints or [{"ip": "172.18.0.8", "port": 8080}, {"ip": "192.168.20.137", "port": 7878}, {"ip": "172.67.70.98", "port": 443}]}]},
        **({"names": names} if names is not None else {})}}}


def test_learned_connections_get_docker_dns_and_cdn_names(env, monkeypatch):
    client, monitor = env
    monkeypatch.setattr(monitoring, "proxy_request", lambda request, timeout=75: answer({"137": {"172.18.0.8": "qbittorrent", "bad": "../x"}}))
    monkeypatch.setattr(monitoring.socket, "gethostbyaddr", lambda ip: ("arrsuite.home", [], [ip]) if ip == "192.168.20.137" else (_ for _ in ()).throw(socket.herror()))
    monitor.check(force_discovery=True)
    rows = {row["host"]: row["name"] for row in client.get("/api/monitoring").get_json()["connections"]}
    assert rows == {"172.18.0.8": "qbittorrent", "192.168.20.137": "arrsuite.home", "172.67.70.98": "Cloudflare (CDN)"}


def test_older_agent_without_names_and_failed_lookup_keep_known_name(env, monkeypatch):
    client, monitor = env
    monkeypatch.setattr(monitoring, "proxy_request", lambda request, timeout=75: answer({"137": {"172.18.0.8": "qbittorrent"}}))
    monkeypatch.setattr(monitoring.socket, "gethostbyaddr", Mock(side_effect=socket.herror))
    monitor.check(force_discovery=True)
    monkeypatch.setattr(monitoring, "proxy_request", lambda request, timeout=75: answer(None))
    monitor.names.clear()
    monitor.check(force_discovery=True)
    rows = {row["host"]: row["name"] for row in client.get("/api/monitoring").get_json()["connections"]}
    assert rows["172.18.0.8"] == "qbittorrent", "a name once found is not wiped by a round without names"
    assert rows["192.168.20.137"] == "", "unknown stays empty, never invented"


def test_earlier_seen_connection_gets_a_name_in_a_later_round(env, monkeypatch):
    """Regression: only connections open in the current round were named; ones seen earlier stayed bare IPs
    (in production 74 of 92 had no name although their Docker container or CDN was known)."""
    client, monitor = env
    monkeypatch.setattr(monitoring.socket, "gethostbyaddr", Mock(side_effect=socket.herror))
    monkeypatch.setattr(monitoring, "proxy_request", lambda request, timeout=75: answer(None, [{"ip": "172.18.0.8", "port": 8080}, {"ip": "104.26.0.248", "port": 443}]))
    monkeypatch.setattr(monitoring, "CDN_RANGES", [])
    monitor.check(force_discovery=True)
    monkeypatch.setattr(monitoring, "CDN_RANGES", [("Cloudflare (CDN)", monitoring.ipaddress.ip_network("104.24.0.0/14"))])
    monkeypatch.setattr(monitoring, "proxy_request", lambda request, timeout=75: answer({"137": {"172.18.0.8": "qbittorrent"}}, [{"ip": "10.9.9.9", "port": 22}]))
    monitor.names.clear()
    monitor.check(force_discovery=True)
    rows = {row["host"]: row["name"] for row in client.get("/api/monitoring").get_json()["connections"]}
    assert rows["172.18.0.8"] == "qbittorrent" and rows["104.26.0.248"] == "Cloudflare (CDN)"


def test_lan_ip_named_from_proxmox_guest_table_when_reverse_dns_has_no_answer(env, monkeypatch):
    """Regression: 192.168.20.137 stayed nameless because OPNsense resolves arrsuite.home → IP but not IP → name.
    The guest table from the Proxmox LXC configs fills that in before reverse DNS."""
    client, monitor = env
    monkeypatch.setattr(monitoring, "guest_addresses", lambda data_dir: {"192.168.20.137": ("arrsuite", 137)})
    lookups = []
    monkeypatch.setattr(monitoring.socket, "gethostbyaddr", lambda ip: lookups.append(ip) or (_ for _ in ()).throw(socket.herror()))
    monkeypatch.setattr(monitoring, "proxy_request", lambda request, timeout=75: answer({}, [{"ip": "192.168.20.137", "port": 8383}, {"ip": "10.1.1.1", "port": 22}]))
    monitor.check(force_discovery=True)
    rows = {row["host"]: row["name"] for row in client.get("/api/monitoring").get_json()["connections"]}
    assert rows == {"192.168.20.137": "arrsuite", "10.1.1.1": ""}
    assert "192.168.20.137" not in lookups, "the own table is used first, no DNS query needed"


def test_guest_addresses_reads_lxc_configs_and_survives_proxmox_errors(tmp_path, monkeypatch):
    (tmp_path / "proxmox").mkdir()
    (tmp_path / "proxmox/connection.json").write_text("{}")

    class Client:
        def __init__(self, connection):
            pass

        def get(self, path):
            if path == "/cluster/resources":
                return [{"type": "lxc", "vmid": 137, "node": "pve-amd", "name": "arrsuite"}, {"type": "lxc", "vmid": 138, "node": "pve-intel", "name": "infisical"},
                        {"type": "qemu", "vmid": 106, "node": "pve-intel", "name": "haos"}]
            if path.endswith("/137/config"):
                return {"net0": "name=eth0,bridge=vmbr0,ip=192.168.20.137/24,gw=192.168.20.1"}
            raise monitoring.ProxmoxError("geen toegang")
    monkeypatch.setattr(monitoring, "ProxmoxClient", Client)
    assert monitoring.guest_addresses(tmp_path) == {"192.168.20.137": ("arrsuite", 137)}
    assert monitoring.guest_addresses(tmp_path / "bestaat-niet") == {}


def test_docker_ports_parses_published_tcp_ports(monkeypatch):
    output = ("spottarr|0.0.0.0:8383->8383/tcp, [::]:8383->8383/tcp\nqbittorrent|0.0.0.0:6881->6881/tcp, 0.0.0.0:6881->6881/udp, 0.0.0.0:8080->8080/tcp\n"
              "sabnzbd|0.0.0.0:8081->8080/tcp\nmariadb|3306/tcp\n../x|0.0.0.0:1->1/tcp\nkapot\n")
    monkeypatch.setattr(agent.subprocess, "run", lambda *a, **k: Mock(stdout=output, returncode=0))
    assert agent.docker_ports(137) == {8383: "spottarr", 6881: "qbittorrent", 8080: "qbittorrent", 8081: "sabnzbd"}
    monkeypatch.setattr(agent.subprocess, "run", Mock(side_effect=OSError))
    assert agent.docker_ports(137) == {}


def test_guest_ip_plus_published_port_names_the_app_and_upgrades_guest_only_name(env, monkeypatch):
    """192.168.20.137:8383 is spottarr (published port 8383 on arrsuite). A row already named "arrsuite" is upgraded;
    a port without a published app keeps the guest name."""
    client, monitor = env
    monkeypatch.setattr(monitoring, "guest_addresses", lambda data_dir: {"192.168.20.137": ("arrsuite", 137)})
    monkeypatch.setattr(monitoring.socket, "gethostbyaddr", Mock(side_effect=socket.herror))
    endpoints = [{"ip": "192.168.20.137", "port": 8383}, {"ip": "192.168.20.137", "port": 22}]
    monkeypatch.setattr(monitoring, "proxy_request", lambda request, timeout=75: answer({}, endpoints))
    monitor.check(force_discovery=True)
    assert {row["port"]: row["name"] for row in client.get("/api/monitoring").get_json()["connections"]} == {8383: "arrsuite", 22: "arrsuite"}

    def with_ports(request, timeout=75):
        data = answer({}, endpoints)
        data["data"]["data"]["ports"] = {"137": {"8383": "spottarr", "x": "y", "1": "../x"}}
        return data
    monkeypatch.setattr(monitoring, "proxy_request", with_ports)
    monitor.check(force_discovery=True)
    assert {row["port"]: row["name"] for row in client.get("/api/monitoring").get_json()["connections"]} == {8383: "arrsuite / spottarr", 22: "arrsuite"}
