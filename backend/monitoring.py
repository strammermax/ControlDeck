"""Monitoring: are the connections between apps still up? (docs/MONITORING.md)

A connection is "source app → host:port". Connections come from two places:

* discovered: the *arr apps' download clients, indexers and applications (their own API), and the ingress
  rules of a Cloudflare tunnel (cloudflared's local config). Sources and API keys live in Infisical
  (`CONTROLDECK_MONITORING`), never in Git or the browser;
* manual: added by a manager on the page, stored in SQLite;
* learned: outbound TCP connections the node agent sees open in each running container (`net.connections`),
  internal and internet. A learned endpoint is checked while it was seen in the last LEARNED_TTL seconds.

Each connection is checked from the source itself when it is an LXC on an enrolled node: the node agent
connects from inside the container's network namespace (`net.probe`), so firewall, routing and the
container's own DNS are part of the test. Everything else is checked from ControlDeck, and says so.
"""
import hashlib
import ipaddress
import json
import os
import re
import smtplib
import socket
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlsplit

from flask import g, jsonify, request

from backend.agent_client import AgentUnavailable, proxy_request
from backend.auth import filter_configuration, is_manager
from backend.configuration import ConfigurationError, load_config
from backend.guest_inventory import config_ip, project_guests
from backend.proxmox import Client as ProxmoxClient, ProxmoxError
from backend.vault import VaultError
from backend.widgets.transport import ProviderError, Transport

ARR_KINDS = {"sonarr": "/api/v3", "radarr": "/api/v3", "lidarr": "/api/v1", "readarr": "/api/v1", "prowlarr": "/api/v1"}
KINDS = set(ARR_KINDS) | {"cloudflared"}
HOST = re.compile(r"(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9_-]{0,62})(?:\.[A-Za-z0-9_-]{1,63})*\.?")
SOURCE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
APP = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,62}")
CHECK_TIMEOUT = 3.0
DISCOVERY_SECONDS = 600
LEARN_SECONDS = 300
LEARNED_TTL = 86400
LEARNED_KEEP = 7 * 86400
NAME_TTL = 86400
# Cloudflare's published IPv4 ranges: reverse DNS says nothing there, so they get a label.
CDN_RANGES = [("Cloudflare (CDN)", ipaddress.ip_network(net)) for net in (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22", "141.101.64.0/18", "108.162.192.0/18",
    "190.93.240.0/20", "188.114.96.0/20", "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22")]
# Public destinations on high ports are peers (BitTorrent, Soulseek): they change constantly and are not a dependency.
PEER_PORT_FROM = 10000
INTERVAL_SECONDS = 60
KEEP_EVENTS = 2000
MAX_CONNECTIONS = 500


class MonitorError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


def valid_host(value):
    if not isinstance(value, str):
        return False
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return bool(HOST.fullmatch(value))


def connection_id(origin, source, host, port):
    return hashlib.sha256(json.dumps([origin, source, host.lower(), port]).encode()).hexdigest()[:16]


def target(host, port):
    """Normalised host/port, or None when it is not something we can test."""
    if not valid_host(host) or type(port) is not int or not 1 <= port <= 65535:
        return None
    return host.rstrip(".").lower(), port


def url_target(value):
    """host/port from a URL as apps store it (`http://prowlarr:9696/1/`); default ports by scheme."""
    try:
        parts = urlsplit(value.strip())
        port = parts.port or {"http": 80, "https": 443, "ws": 80, "wss": 443, "tcp": None}.get(parts.scheme)
    except (AttributeError, ValueError):
        return None
    return target(parts.hostname or "", port) if port else None


# --- configuration ----------------------------------------------------------------------------------------

def validate_sources(value):
    if not isinstance(value, dict) or not isinstance(value.get("sources", {}), dict) or len(value.get("sources", {})) > 32:
        raise MonitorError("Ongeldige monitoringconfiguratie.")
    sources = {}
    for identifier, source in value.get("sources", {}).items():
        if not SOURCE_ID.fullmatch(identifier) or not isinstance(source, dict) or source.get("kind") not in KINDS:
            raise MonitorError("Ongeldige monitoringbron.")
        title = source.get("title", identifier)
        vmid = source.get("vmid")
        if not isinstance(title, str) or not 1 <= len(title) <= 100 or (vmid is not None and (type(vmid) is not int or not 100 <= vmid <= 999999999)):
            raise MonitorError("Ongeldige monitoringbron.")
        if "app" in source and (not isinstance(source["app"], str) or not APP.fullmatch(source["app"]) or vmid is None):
            raise MonitorError("Ongeldige appnaam (alleen samen met een container-ID).")
        if source["kind"] in ARR_KINDS:
            if not isinstance(source.get("apiKey"), str) or not 1 <= len(source["apiKey"]) <= 200 or any(ord(c) < 33 for c in source["apiKey"]):
                raise MonitorError("Toegangsgegevens ontbreken.")
            try:
                Transport({"url": source.get("url"), "allowHttp": source.get("allowHttp") is True}).close()
            except ProviderError:
                raise MonitorError("Ongeldig bronadres.") from None
        elif vmid is None:
            raise MonitorError("Een tunnelbron heeft een container-ID nodig.")
        sources[identifier] = {**source, "title": title}
    return sources


def configured_sources(app):
    vault = app.extensions.get("controldeck_vault")
    if vault is None:
        return {}
    try:
        return validate_sources(json.loads(vault.read().get("CONTROLDECK_MONITORING", "{}")))
    except (ValueError, TypeError, VaultError):
        raise MonitorError("Monitoringbronnen zijn niet beschikbaar. Controleer Infisical.", 503) from None


# --- discovery --------------------------------------------------------------------------------------------

def fields(item):
    return {field.get("name"): field.get("value") for field in item.get("fields", []) if isinstance(field, dict)} if isinstance(item, dict) else {}


def discover_arr(source):
    """Download clients, indexers and (Prowlarr) applications from the app's own API."""
    transport = Transport({"url": source["url"], "allowHttp": source.get("allowHttp") is True})
    api, headers, found = ARR_KINDS[source["kind"]], {"X-Api-Key": source["apiKey"]}, []
    try:
        paths = [("downloadclient", "Downloadclient")] + ([("applications", "App")] if source["kind"] == "prowlarr" else [("indexer", "Indexer")])
        for path, label in paths:
            items = transport.call(f"{api}/{path}", headers=headers)
            for item in items if isinstance(items, list) else []:
                if not isinstance(item, dict) or item.get("enable", True) is False:
                    continue
                values = fields(item)
                found_target = target(str(values.get("host", "")), values.get("port")) if values.get("host") else \
                    url_target(values.get("baseUrl") if source["kind"] == "prowlarr" or label == "Indexer" else "")
                if found_target:
                    found.append({"host": found_target[0], "port": found_target[1], "label": f"{label}: {str(item.get('name', ''))[:80]}"})
    finally:
        transport.close()
    return found


def discover_tunnel(source, node):
    data = call_agent(node, "net.tunnel", {"vmid": source["vmid"]})
    found = []
    for rule in data.get("ingress") or []:
        found_target = url_target(rule.get("service", ""))
        if found_target:
            found.append({"host": found_target[0], "port": found_target[1], "label": f"Tunnel: {rule.get('hostname', '')[:120]}"})
    if data.get("ingress") is None:
        raise MonitorError("cloudflared geeft geen tunnelconfiguratie (metrics-poort niet gevonden).", 502)
    return found


# --- probing ----------------------------------------------------------------------------------------------

def call_agent(node, action, payload):
    try:
        response = proxy_request({"op": "call", "node": node, "action": action, "payload": payload}, timeout=75)
    except AgentUnavailable as error:
        raise MonitorError(str(error), 503) from None
    if not response.get("ok"):
        raise MonitorError(response.get("message") or "De node is niet bereikbaar.", 502)
    answer = response.get("data") or {}
    if not answer.get("ok"):
        raise MonitorError(answer.get("message") or "De agent weigerde de opdracht.", 502)
    return answer.get("data") or {}


def enrolled_nodes():
    try:
        response = proxy_request({"op": "status"}, timeout=5)
    except AgentUnavailable:
        return set()
    return {node["node"] for node in (response.get("data") or {}).get("nodes", []) if isinstance(node, dict) and isinstance(node.get("node"), str)} if response.get("ok") else set()


def guests(data_dir):
    """vmid → {node, type, name} from the existing read-only Proxmox connection; empty when unavailable."""
    try:
        connection = json.loads((Path(data_dir) / "proxmox/connection.json").read_text(encoding="utf-8"))
        return {guest["vmid"]: guest for guest in project_guests(ProxmoxClient(connection).get("/cluster/resources"))}
    except (OSError, ValueError, KeyError, TypeError, ProxmoxError):
        return {}


def guest_addresses(data_dir):
    """{IP: (name, vmid)} for the Proxmox nodes (/cluster/status), every LXC (config net*: ip=...) and running VMs with a
    guest agent. An own lookup table, because the LAN's DNS answers name → IP but often not IP → name. Empty when Proxmox
    is unavailable."""
    try:
        connection = json.loads((Path(data_dir) / "proxmox/connection.json").read_text(encoding="utf-8"))
        client = ProxmoxClient(connection)
        inventory = project_guests(client.get("/cluster/resources"))
    except (OSError, ValueError, KeyError, TypeError, ProxmoxError):
        return {}
    table = {}
    try:
        for item in client.get("/cluster/status") or []:
            if isinstance(item, dict) and item.get("type") == "node" and isinstance(item.get("ip"), str) and valid_host(item["ip"]):
                table[item["ip"]] = (str(item.get("name", ""))[:63], None)
    except (ProxmoxError, ValueError, TypeError):
        pass
    for guest in inventory[:500]:
        try:
            if guest["type"] == "lxc":
                addresses = [config_ip(client.get(f"/nodes/{guest['node']}/lxc/{guest['vmid']}/config") or {})]
            elif guest["status"] == "running":
                # VMs: only with a running QEMU guest agent; IPv4, not loopback.
                interfaces = (client.get(f"/nodes/{guest['node']}/qemu/{guest['vmid']}/agent/network-get-interfaces") or {}).get("result") or []
                addresses = [a.get("ip-address") for i in interfaces if isinstance(i, dict) for a in i.get("ip-addresses") or []
                             if isinstance(a, dict) and a.get("ip-address-type") == "ipv4" and not str(a.get("ip-address", "")).startswith("127.")]
            else:
                continue
        except (ProxmoxError, ValueError, TypeError, KeyError, AttributeError):
            continue
        for address in addresses[:8]:
            if isinstance(address, str) and valid_host(address):
                table.setdefault(address, (guest["name"], guest["vmid"]))
    return table


def probe_central(host, port):
    """From ControlDeck itself: its own resolver and network path."""
    started = time.monotonic()
    try:
        address = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)[0][4][0]
    except (OSError, UnicodeError):
        return {"ok": False, "ip": None, "error": f"{host} is niet op te lossen."}
    try:
        with socket.create_connection((address, port), timeout=CHECK_TIMEOUT):
            pass
        return {"ok": True, "ip": address, "ms": round((time.monotonic() - started) * 1000)}
    except socket.timeout:
        return {"ok": False, "ip": address, "error": "Time-out (geen antwoord, mogelijk firewall)."}
    except ConnectionRefusedError:
        return {"ok": False, "ip": address, "error": "Verbinding geweigerd (dienst draait niet op deze poort)."}
    except OSError as failure:
        return {"ok": False, "ip": address, "error": f"Niet bereikbaar: {failure.strerror or 'netwerkfout'}."}


def probe_all(connections, placement):
    """{connection id: result}; LXC sources via the agent per container, the rest from ControlDeck."""
    by_container, central, results = {}, [], {}
    for connection in connections:
        where = placement.get(connection["vmid"]) if connection.get("vmid") else None
        if where:
            by_container.setdefault((where["node"], connection["vmid"], connection.get("app") or ""), []).append(connection)
        else:
            central.append(connection)

    def container(key):
        node, vmid, app = key
        items, via = by_container[key], f"bron ({node}/{vmid}{'/' + app if app else ''})"
        unique = sorted({(item["host"], item["port"]) for item in items})
        try:
            answers = []
            for start in range(0, len(unique), 64):
                chunk = [{"host": host, "port": port} for host, port in unique[start:start + 64]]
                answers += call_agent(node, "net.probe", {"vmid": vmid, "targets": chunk, **({"app": app} if app else {})}).get("results", [])
            by_target = {(a.get("host"), a.get("port")): a for a in answers if isinstance(a, dict)}
            return {item["id"]: {**by_target.get((item["host"], item["port"]), {"ok": False, "error": "Geen antwoord van de agent."}), "via": via} for item in items}
        except MonitorError as error:
            # The check itself failed: not the connection. Never report it as up or down.
            return {item["id"]: {"ok": None, "error": f"Controle vanaf de bron mislukt: {error.message}", "via": via} for item in items}

    with ThreadPoolExecutor(max_workers=8) as pool:
        for answer in pool.map(container, list(by_container)):
            results.update(answer)
        central_answers = pool.map(lambda item: probe_central(item["host"], item["port"]), central)
        for item, answer in zip(central, central_answers):
            results[item["id"]] = {**answer, "via": "ControlDeck"}
    return results


def reverse_name(address):
    """Hostname for an IP via reverse DNS (OPNsense knows the LAN), a CDN label, or "" when unknown."""
    ip = ipaddress.ip_address(address)
    label = next((name for name, network in CDN_RANGES if ip in network), "")
    if label:
        return label
    try:
        name = socket.gethostbyaddr(address)[0].rstrip(".").lower()
    except (OSError, UnicodeError):
        return ""
    return name if HOST.fullmatch(name) and name != address else ""


def resolve_names(addresses, cache, timeout=5.0):
    """{ip: name} for addresses, in parallel and bounded in time; unanswered lookups stay unknown this round."""
    now, result, missing = time.time(), {}, []
    for address in addresses:
        hit = cache.get(address)
        if hit and now - hit[1] < NAME_TTL:
            result[address] = hit[0]
        else:
            missing.append(address)
    if missing:
        pool = ThreadPoolExecutor(max_workers=8)
        futures = {pool.submit(reverse_name, address): address for address in missing[:200]}
        try:
            for future in as_completed(futures, timeout=timeout):
                name = future.result()
                cache[futures[future]] = (name, now)
                result[futures[future]] = name
        except TimeoutError:
            pass
        pool.shutdown(wait=False, cancel_futures=True)
    return result


# --- storage ----------------------------------------------------------------------------------------------

def database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS manual (id TEXT PRIMARY KEY, source TEXT NOT NULL, vmid INTEGER, host TEXT NOT NULL,
            port INTEGER NOT NULL, label TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS status (id TEXT PRIMARY KEY, ok INTEGER, since REAL NOT NULL, checked REAL NOT NULL,
            error TEXT, ms INTEGER, ip TEXT, via TEXT);
        CREATE TABLE IF NOT EXISTS events (at REAL NOT NULL, id TEXT NOT NULL, ok INTEGER, error TEXT);
        CREATE TABLE IF NOT EXISTS discovered (id TEXT PRIMARY KEY, payload TEXT NOT NULL, at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS learned (id TEXT PRIMARY KEY, vmid INTEGER NOT NULL, source TEXT NOT NULL, ip TEXT NOT NULL,
            port INTEGER NOT NULL, first REAL NOT NULL, last REAL NOT NULL, app TEXT NOT NULL DEFAULT '', name TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, notified REAL NOT NULL);
    """)
    columns = {row[1] for row in db.execute("PRAGMA table_info(learned)")}
    if "app" not in columns:
        db.execute("ALTER TABLE learned ADD COLUMN app TEXT NOT NULL DEFAULT ''")
    if "name" not in columns:
        db.execute("ALTER TABLE learned ADD COLUMN name TEXT NOT NULL DEFAULT ''")
    return db


def record(db, results, stamp):
    for identifier, result in results.items():
        ok = None if result.get("ok") is None else int(bool(result["ok"]))
        previous = db.execute("SELECT ok, since FROM status WHERE id=?", (identifier,)).fetchone()
        changed = previous is None or previous["ok"] != ok
        since = stamp if changed else previous["since"]
        db.execute("INSERT OR REPLACE INTO status VALUES (?,?,?,?,?,?,?,?)",
                   (identifier, ok, since, stamp, (result.get("error") or "")[:300] or None, result.get("ms"), result.get("ip"), result.get("via")))
        if changed:
            db.execute("INSERT INTO events VALUES (?,?,?,?)", (stamp, identifier, ok, (result.get("error") or "")[:300] or None))
    db.execute("DELETE FROM events WHERE rowid NOT IN (SELECT rowid FROM events ORDER BY at DESC LIMIT ?)", (KEEP_EVENTS,))


# --- notifications (e-mail via the local SMTP relay) ------------------------------------------------------

EMAIL = re.compile(r"[^\s@<>,;\"']{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}")
NOTIFY_DEFAULTS = {"enabled": False, "recipients": [], "sender": "homelab@vanburik.info", "smtpHost": "192.168.20.1",
                   "smtpPort": 25, "delayMinutes": 5, "learned": False}


def validate_notify(value):
    if not isinstance(value, dict) or set(value) - set(NOTIFY_DEFAULTS):
        raise MonitorError("Ongeldige meldinginstellingen.")
    settings = {**NOTIFY_DEFAULTS, **value}
    recipients = settings["recipients"]
    if not isinstance(recipients, list) or len(recipients) > 10 or any(not isinstance(r, str) or not EMAIL.fullmatch(r.strip()) for r in recipients):
        raise MonitorError("Geef maximaal 10 geldige e-mailadressen.")
    if not isinstance(settings["sender"], str) or not EMAIL.fullmatch(settings["sender"].strip()):
        raise MonitorError("Ongeldig afzenderadres.")
    if not valid_host(settings["smtpHost"]) or type(settings["smtpPort"]) is not int or not 1 <= settings["smtpPort"] <= 65535:
        raise MonitorError("Ongeldige SMTP-gateway.")
    if type(settings["delayMinutes"]) is not int or not 1 <= settings["delayMinutes"] <= 1440:
        raise MonitorError("Wachttijd moet tussen 1 en 1440 minuten liggen.")
    if not isinstance(settings["enabled"], bool) or not isinstance(settings["learned"], bool):
        raise MonitorError("Ongeldige meldinginstellingen.")
    if settings["enabled"] and not recipients:
        raise MonitorError("Vul minstens één ontvanger in om meldingen aan te zetten.")
    return {**settings, "recipients": [r.strip() for r in recipients], "sender": settings["sender"].strip()}


def send_mail(settings, subject, body):
    """Plain-text mail through the relay; STARTTLS when the relay offers it. Raises MonitorError on failure."""
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = settings["sender"], ", ".join(settings["recipients"]), subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings["smtpHost"], settings["smtpPort"], timeout=15) as smtp:
            smtp.ehlo("controldeck")
            if smtp.has_extn("starttls"):
                smtp.starttls()
                smtp.ehlo("controldeck")
            smtp.send_message(message)
    except smtplib.SMTPRecipientsRefused as error:
        code, reply = next(iter(error.recipients.values()), (0, b""))
        raise MonitorError(f"Mail versturen mislukt: de gateway weigert de ontvanger ({code} {smtp_text(reply)}).", 502) from None
    except smtplib.SMTPResponseException as error:
        raise MonitorError(f"Mail versturen mislukt: {error.smtp_code} {smtp_text(error.smtp_error)}.", 502) from None
    except (OSError, smtplib.SMTPException) as error:
        raise MonitorError(f"Mail versturen mislukt: {type(error).__name__}.", 502) from None


def smtp_text(reply):
    """The relay's reply text, bounded and printable (it can contain addresses, never credentials: no AUTH is used)."""
    text = reply.decode("utf-8", errors="replace") if isinstance(reply, bytes) else str(reply)
    return "".join(c for c in text if c.isprintable())[:160]


def describe(row):
    via = f", via {row['via']}" if row.get("via") else ""
    label = f" ({row['label']})" if row.get("label") else ""
    target = f"{row['name']} ({row['host']})" if row.get("name") else row["host"]
    return f"{row['source']} → {target}:{row['port']}{label}{via}"


def alert_mail(down, recovered, now):
    parts = ([f"{len(down)} onderbroken"] if down else []) + ([f"{len(recovered)} hersteld"] if recovered else [])
    subject = "ControlDeck monitoring: " + ", ".join(parts)
    lines = []
    if down:
        lines.append("Onderbroken:")
        for row in down:
            since = time.strftime("%d-%m %H:%M", time.localtime(row["since"]))
            lines += [f"  ✗ {describe(row)}", f"    {row.get('error') or 'geen antwoord'} (sinds {since})"]
        lines.append("")
    if recovered:
        lines += ["Hersteld:"] + [f"  ✓ {describe(row)}" for row in recovered] + [""]
    base = os.environ.get("CONTROLDECK_BASE_URL", "").rstrip("/")
    lines.append(f"Overzicht: {base}/#monitoring" if base else "Overzicht: ControlDeck → Monitoring")
    lines.append(f"Gecontroleerd om {time.strftime('%d-%m-%Y %H:%M', time.localtime(now))}.")
    return subject, "\n".join(lines)


# --- service ----------------------------------------------------------------------------------------------

class Monitor:
    def __init__(self, app, data_dir):
        self.app, self.data_dir, self.path = app, data_dir, Path(data_dir) / "monitoring.sqlite3"
        self.lock, self.discovered_at, self.learned_at, self.source_errors = threading.Lock(), 0.0, 0.0, {}
        self.notify_error, self.names = None, {}
        self.guest_table, self.guest_table_at, self.ports = {}, 0.0, {}

    def placement(self):
        nodes, inventory = enrolled_nodes(), guests(self.data_dir)
        return {vmid: guest for vmid, guest in inventory.items() if guest["type"] == "lxc" and guest["node"] in nodes and guest["status"] == "running"}

    def discover(self, sources, placement, force=False):
        """Refreshes the discovered connections at most every DISCOVERY_SECONDS; failures keep the last list."""
        if not force and time.time() - self.discovered_at < DISCOVERY_SECONDS:
            return
        found, errors = {}, {}
        for identifier, source in sources.items():
            try:
                if source["kind"] == "cloudflared":
                    where = placement.get(source["vmid"])
                    if not where:
                        raise MonitorError("De tunnelcontainer draait niet op een gekoppelde node.", 502)
                    items = discover_tunnel(source, where["node"])
                else:
                    items = discover_arr(source)
            except (MonitorError, ProviderError) as error:
                errors[identifier] = getattr(error, "message", None) or str(error)
                continue
            for item in items:
                key = connection_id(identifier, source["title"], item["host"], item["port"])
                found[key] = {"id": key, "origin": identifier, "source": source["title"], "vmid": source.get("vmid"), "app": source.get("app", "").lower(), **item}
        with database(self.path) as db:
            failed = set(errors)
            keep = [row["id"] for row in db.execute("SELECT id, payload FROM discovered") if json.loads(row["payload"])["origin"] in failed]
            db.execute(f"DELETE FROM discovered WHERE id NOT IN ({','.join('?' * len(keep))})" if keep else "DELETE FROM discovered", keep)
            db.executemany("INSERT OR REPLACE INTO discovered VALUES (?,?,?)", [(key, json.dumps(item), time.time()) for key, item in found.items()])
        self.discovered_at, self.source_errors = time.time(), errors

    def learn(self, placement, force=False):
        """Outbound connections per running container, one agent call per node; unreachable nodes keep their list."""
        if not placement or (not force and time.time() - self.learned_at < LEARN_SECONDS):
            return
        by_node = {}
        for vmid, guest in placement.items():
            by_node.setdefault(guest["node"], []).append(vmid)

        def node_call(node):
            try:
                return call_agent(node, "net.connections", {"vmids": sorted(by_node[node])[:200]})
            except MonitorError:
                return {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            answers = list(pool.map(node_call, list(by_node)))
        stamp, rows = time.time(), []
        docker = {}
        for answer in answers:
            for vmid_text, addresses in (answer.get("names") or {}).items() if isinstance(answer.get("names"), dict) else []:
                if str(vmid_text).isdigit() and isinstance(addresses, dict):
                    docker[int(vmid_text)] = {ip: str(name)[:63] for ip, name in list(addresses.items())[:500] if isinstance(name, str) and APP.fullmatch(name)}
            for vmid_text, published in (answer.get("ports") or {}).items() if isinstance(answer.get("ports"), dict) else []:
                if str(vmid_text).isdigit() and isinstance(published, dict):
                    self.ports[int(vmid_text)] = {int(port): str(name)[:63] for port, name in list(published.items())[:500]
                                                  if str(port).isdigit() and isinstance(name, str) and APP.fullmatch(name)}
        for answer in answers:
            containers = answer.get("containers") or {}
            for vmid_text, apps in containers.items():
                vmid = int(vmid_text) if str(vmid_text).isdigit() else None
                if vmid not in placement or not isinstance(apps, list):
                    continue
                guest = placement[vmid].get("name") or str(vmid)
                for namespace in apps[:64]:
                    app = namespace.get("app", "") if isinstance(namespace, dict) else None
                    if not isinstance(app, str) or (app and not APP.fullmatch(app)) or not isinstance(namespace.get("endpoints"), list):
                        continue
                    for endpoint in namespace["endpoints"][:200]:
                        found = target(str(endpoint.get("ip", "")), endpoint.get("port")) if isinstance(endpoint, dict) else None
                        if found and not (found[1] >= PEER_PORT_FROM and ipaddress.ip_address(found[0]).is_global):
                            rows.append([connection_id("learned", f"{vmid}/{app}", *found), vmid, f"{guest} / {app}" if app else guest, found[0], found[1], stamp, stamp, app,
                                         docker.get(vmid, {}).get(found[0], "")])
        # Earlier-seen destinations without a name get one too, not only what is open right now. A guest address
        # named after the guest only ("arrsuite") is upgraded once its port is known ("arrsuite / spottarr").
        if time.time() - self.guest_table_at > NAME_TTL or not self.guest_table:
            self.guest_table, self.guest_table_at = guest_addresses(self.data_dir), time.time()

        def guest_name(ip, port):
            guest = self.guest_table.get(ip)
            if not guest:
                return ""
            app = self.ports.get(guest[1], {}).get(port)
            return f"{guest[0]} / {app}" if app else guest[0]

        with database(self.path) as db:
            unnamed = [(row["id"], row["vmid"], row["ip"], row["port"], row["name"]) for row in db.execute(
                "SELECT id, vmid, ip, port, name FROM learned WHERE last >= ?", (stamp - LEARNED_TTL,))
                if not row["name"] or (row["ip"] in self.guest_table and " / " not in row["name"])]
        wanted = {row[3] for row in rows if not row[8] and row[3] not in self.guest_table} | \
                 {ip for _, vmid, ip, _, _ in unnamed if ip not in docker.get(vmid, {}) and ip not in self.guest_table}
        names = resolve_names(sorted(wanted), self.names)
        for row in rows:
            row[8] = row[8] or guest_name(row[3], row[4]) or names.get(row[3], "")
        with database(self.path) as db:
            db.executemany("UPDATE learned SET name=? WHERE id=? AND ?!=''",
                           [(name, identifier, name) for identifier, vmid, ip, port, current in unnamed
                            for name in [docker.get(vmid, {}).get(ip) or guest_name(ip, port) or names.get(ip, "") or current]])
            db.executemany("INSERT INTO learned (id, vmid, source, ip, port, first, last, app, name) VALUES (?,?,?,?,?,?,?,?,?) "
                           "ON CONFLICT(id) DO UPDATE SET last=excluded.last, source=excluded.source, "
                           "name=CASE WHEN excluded.name != '' THEN excluded.name ELSE learned.name END", rows)
            old = [row["id"] for row in db.execute("SELECT id FROM learned WHERE last < ?", (stamp - LEARNED_KEEP,))]
            for identifier in old:
                db.execute("DELETE FROM learned WHERE id=?", (identifier,))
                db.execute("DELETE FROM status WHERE id=?", (identifier,))
        self.learned_at = stamp

    def notify_settings(self, db=None):
        own = db is None
        db = db or database(self.path)
        try:
            row = db.execute("SELECT value FROM settings WHERE key='notify'").fetchone()
            return {**NOTIFY_DEFAULTS, **(json.loads(row["value"]) if row else {})}
        finally:
            if own:
                db.close()

    def notify(self, now):
        """One mail per round: connections down for at least delayMinutes (not yet mailed) and mailed ones that recovered.
        A failed send changes nothing, so the next round tries again."""
        with database(self.path) as db:
            settings = self.notify_settings(db)
            if not settings["enabled"] or not settings["recipients"]:
                return
            status = {row["id"]: dict(row) for row in db.execute("SELECT * FROM status")}
            alerted = {row["id"] for row in db.execute("SELECT id FROM alerts")}
            rows = [{**item, **status[item["id"]]} for item in self.connections(db) if item["id"] in status]
        known = {row["id"] for row in rows}
        down = [row for row in rows if row["ok"] == 0 and row["id"] not in alerted and now - row["since"] >= settings["delayMinutes"] * 60
                and (settings["learned"] or row["origin"] != "learned")]
        recovered = [row for row in rows if row["ok"] == 1 and row["id"] in alerted]
        with database(self.path) as db:
            for identifier in alerted - known:
                db.execute("DELETE FROM alerts WHERE id=?", (identifier,))
        if not down and not recovered:
            return
        try:
            send_mail(settings, *alert_mail(down, recovered, now))
        except MonitorError as error:
            self.notify_error = error.message
            return
        self.notify_error = None
        with database(self.path) as db:
            db.executemany("INSERT OR REPLACE INTO alerts VALUES (?,?)", [(row["id"], now) for row in down])
            db.executemany("DELETE FROM alerts WHERE id=?", [(row["id"],) for row in recovered])

    def connections(self, db):
        rows = [{"id": row["id"], "origin": "manual", "source": row["source"], "vmid": row["vmid"], "host": row["host"], "port": row["port"], "label": row["label"]}
                for row in db.execute("SELECT * FROM manual ORDER BY created")]
        rows += [json.loads(row["payload"]) for row in db.execute("SELECT payload FROM discovered")]
        rows += [{"id": row["id"], "origin": "learned", "source": row["source"], "vmid": row["vmid"], "app": row["app"], "host": row["ip"], "port": row["port"], "name": row["name"],
                  "label": "Gezien · " + ("intern" if ipaddress.ip_address(row["ip"]).is_private else "internet"), "lastSeen": row["last"]}
                 for row in db.execute("SELECT * FROM learned WHERE last >= ? ORDER BY source, ip, port", (time.time() - LEARNED_TTL,))]
        return rows[:MAX_CONNECTIONS]

    def check(self, force_discovery=False):
        with self.lock:
            try:
                sources = configured_sources(self.app)
                config_error = None
            except MonitorError as error:
                sources, config_error = {}, error.message
            placement = self.placement()
            if config_error:
                # Keep the last discovered list: an unreachable vault is not "all connections are gone".
                self.source_errors = {"infisical": config_error}
            else:
                self.discover(sources, placement, force_discovery)
            self.learn(placement, force_discovery)
            with database(self.path) as db:
                connections = self.connections(db)
            results = probe_all(connections, placement) if connections else {}
            with database(self.path) as db:
                record(db, results, time.time())
            self.notify(time.time())

    def overview(self):
        with database(self.path) as db:
            status = {row["id"]: dict(row) for row in db.execute("SELECT * FROM status")}
            connections = self.connections(db)
            known = {item["id"]: item for item in connections}
            events = [{"at": row["at"], "id": row["id"], "ok": None if row["ok"] is None else bool(row["ok"]), "error": row["error"],
                       "source": known[row["id"]]["source"], "host": known[row["id"]]["host"], "port": known[row["id"]]["port"]}
                      for row in db.execute("SELECT * FROM events ORDER BY at DESC LIMIT 200") if row["id"] in known][:50]
        rows = []
        for item in connections:
            state = status.get(item["id"])
            rows.append({**item, "ok": None if not state or state["ok"] is None else bool(state["ok"]), "checked": state and state["checked"],
                         "since": state and state["since"], "error": state and state["error"], "ms": state and state["ms"],
                         "ip": state and state["ip"], "via": state and state["via"]})
        checked = max((row["checked"] or 0 for row in rows), default=0) or None
        return {"connections": rows, "events": events, "checkedAt": checked,
                "sourceErrors": [{"source": key, "error": value} for key, value in sorted(self.source_errors.items())]}

    def loop(self):
        time.sleep(20)
        while True:
            try:
                self.check()
            except Exception:  # noqa: BLE001 - the loop must survive any single failed round
                self.app.logger.exception("Monitoringronde mislukt")
            time.sleep(INTERVAL_SECONDS)


def validate_manual(body):
    if not isinstance(body, dict) or set(body) - {"source", "vmid", "host", "port", "label"}:
        raise MonitorError("Ongeldige verbinding.")
    source, label, vmid = body.get("source"), body.get("label", ""), body.get("vmid")
    if not isinstance(source, str) or not 1 <= len(source.strip()) <= 100 or any(ord(c) < 32 for c in source):
        raise MonitorError("Vul de bron-app in.")
    if not isinstance(label, str) or len(label) > 120 or any(ord(c) < 32 for c in label):
        raise MonitorError("Ongeldige omschrijving.")
    if vmid is not None and (type(vmid) is not int or not 100 <= vmid <= 999999999):
        raise MonitorError("Ongeldige container-ID.")
    found = target(body.get("host", "").strip() if isinstance(body.get("host"), str) else "", body.get("port"))
    if not found:
        raise MonitorError("Vul een geldige host en poort (1-65535) in.")
    return {"source": source.strip(), "vmid": vmid, "host": found[0], "port": found[1], "label": label.strip()}


def setup_monitoring(app, configuration_path, data_dir):
    monitor = Monitor(app, data_dir)
    app.extensions["controldeck_monitor"] = monitor

    @app.before_request
    def monitoring_access():
        if not request.path.startswith("/api/monitoring") or g.account is None:
            return None
        try:
            allowed = any(module["id"] == "monitoring" for module in filter_configuration(load_config(configuration_path), g.account)["modules"])
        except ConfigurationError:
            allowed = False
        if not allowed:
            return jsonify(error="Geen toegang tot Monitoring."), 403
        if request.method not in ("GET", "HEAD", "OPTIONS") and not is_manager(g.account):
            return jsonify(error="Beheerrechten vereist voor deze actie."), 403
        return None

    def answer(function):
        try:
            return function()
        except MonitorError as error:
            return jsonify(error=error.message), error.status

    @app.get("/api/monitoring")
    def monitoring_overview():
        return answer(lambda: jsonify(monitor.overview()))

    @app.post("/api/monitoring/check")
    def monitoring_check():
        def run():
            monitor.check(force_discovery=True)
            return jsonify(monitor.overview())
        return answer(run)

    @app.get("/api/monitoring/notifications")
    def monitoring_notifications():
        if not is_manager(g.account):
            return jsonify(error="Beheerrechten vereist voor deze actie."), 403
        return jsonify({**monitor.notify_settings(), "lastError": monitor.notify_error})

    @app.put("/api/monitoring/notifications")
    def monitoring_notifications_save():
        def save():
            settings = validate_notify(request.get_json(silent=True))
            with database(monitor.path) as db:
                db.execute("INSERT OR REPLACE INTO settings VALUES ('notify', ?)", (json.dumps(settings),))
            return jsonify({**settings, "lastError": monitor.notify_error})
        return answer(save)

    @app.post("/api/monitoring/notifications/test")
    def monitoring_notifications_test():
        def test():
            settings = monitor.notify_settings()
            if not settings["recipients"]:
                raise MonitorError("Vul eerst een ontvanger in en sla op.")
            send_mail(settings, "ControlDeck monitoring: testmail", "Dit is een testmail van ControlDeck Monitoring.\n"
                      "Komt hij aan, dan werken de meldingen via de SMTP-gateway.")
            return jsonify(sent=True, recipients=settings["recipients"])
        return answer(test)

    @app.post("/api/monitoring/connections")
    def monitoring_add():
        def add():
            item = validate_manual(request.get_json(silent=True))
            identifier = connection_id("manual", item["source"], item["host"], item["port"])
            with database(monitor.path) as db:
                if db.execute("SELECT COUNT(*) FROM manual").fetchone()[0] >= MAX_CONNECTIONS:
                    raise MonitorError("Maximaal aantal verbindingen bereikt.")
                if db.execute("SELECT 1 FROM manual WHERE id=?", (identifier,)).fetchone():
                    raise MonitorError("Deze verbinding bestaat al.", 409)
                db.execute("INSERT INTO manual VALUES (?,?,?,?,?,?,?)", (identifier, item["source"], item["vmid"], item["host"], item["port"], item["label"], time.time()))
            return jsonify({"id": identifier, **item}), 201
        return answer(add)

    @app.delete("/api/monitoring/connections/<identifier>")
    def monitoring_delete(identifier):
        def delete():
            if not re.fullmatch(r"[0-9a-f]{16}", identifier):
                raise MonitorError("Onbekende verbinding.", 404)
            with database(monitor.path) as db:
                if not db.execute("DELETE FROM manual WHERE id=?", (identifier,)).rowcount:
                    raise MonitorError("Alleen handmatige verbindingen kunnen worden verwijderd.", 404)
                db.execute("DELETE FROM status WHERE id=?", (identifier,))
                db.execute("DELETE FROM events WHERE id=?", (identifier,))
            return jsonify(deleted=identifier)
        return answer(delete)

    # Background rounds only in the real server (one Gunicorn worker); tests and scripts call check() themselves.
    if "gunicorn" in sys.modules and app.config.get("MONITORING_LOOP", True):
        threading.Thread(target=monitor.loop, name="controldeck-monitoring", daemon=True).start()
