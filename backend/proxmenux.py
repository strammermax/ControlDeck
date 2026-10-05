"""Read-only ProxMenux Monitor connection per node, verified against the Proxmox cluster CA."""
import json
import os
import re
import ssl
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock, Thread

import requests
from requests.adapters import HTTPAdapter
from cryptography import x509
from flask import g, jsonify, request

from backend.auth import filter_configuration
from backend.configuration import ConfigurationError, load_config
from backend.proxmox import NODE, Client as ProxmoxClient, ProxmoxError, normalize_url

TOKEN = re.compile(r"[A-Za-z0-9_-]{1,2048}\.[A-Za-z0-9_-]{1,2048}\.[A-Za-z0-9_-]{1,2048}")
STATUS = {"OK": "ok", "INFO": "ok", "WARNING": "warning", "CRITICAL": "error", "ERROR": "error"}
TIMEOUT = 15
# health/details runs all checks on the node and can take well over 15 s on small hosts.
PART_TIMEOUTS = {"health/details": 30}
CACHE_SECONDS = 30
STALE_SECONDS = 180
PARTS = ("health/details", "storage", "system", "hardware", "vms")
PART_LABELS = {"health/details": "gezondheid", "storage": "schijven", "system": "systeem", "hardware": "hardware", "vms": "containers"}
MAX_NODES = 16


class MonitorError(Exception):
    """Message is safe to show; it never contains tokens or upstream response bodies."""


def validate_ca(value):
    """Exactly one PEM certificate that is a certificate authority, such as /etc/pve/pve-root-ca.pem."""
    if not isinstance(value, str) or len(value) > 10000 or value.count("-----BEGIN CERTIFICATE-----") != 1:
        raise ValueError("Plak precies één certificaat: de inhoud van /etc/pve/pve-root-ca.pem.")
    try:
        certificate = x509.load_pem_x509_certificate(value.strip().encode("ascii"))
        constraints = certificate.extensions.get_extension_for_class(x509.BasicConstraints).value
    except (ValueError, UnicodeEncodeError, x509.ExtensionNotFound):
        raise ValueError("Dit is geen geldig CA-certificaat.") from None
    if not constraints.ca:
        raise ValueError("Dit is een node-certificaat, geen CA. Gebruik /etc/pve/pve-root-ca.pem.")
    return value.strip() + "\n"


def validate_nodes(nodes, stored):
    """Validates node rows; an omitted token reuses the stored one for the same node and address."""
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= MAX_NODES:
        raise ValueError("Geef minstens één node op.")
    known = {(node["name"], node["url"]): node["token"] for node in (stored or {}).get("nodes", [])}
    result, names = [], set()
    for node in nodes:
        if not isinstance(node, dict) or not set(node) <= {"name", "url", "token"}:
            raise ValueError("Ongeldige nodegegevens.")
        name = node.get("name")
        if not isinstance(name, str) or not NODE.fullmatch(name) or name in names:
            raise ValueError("Ongeldige of dubbele nodenaam.")
        url = normalize_url(node.get("url"), 8008)
        token = node.get("token") or known.get((name, url))
        if not isinstance(token, str) or not TOKEN.fullmatch(token):
            raise ValueError(f"Ongeldig of ontbrekend API-token voor {name}.")
        names.add(name)
        result.append({"name": name, "url": url, "token": token})
    return result


class ClusterCAAdapter(HTTPAdapter):
    """Uses one prepared TLS context: only the cluster CA is trusted and the hostname is checked."""

    def __init__(self, context):
        self.context = context
        super().__init__()

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self.context
        super().init_poolmanager(*args, **kwargs)


def cluster_session(ca_path):
    """Session that trusts only the Proxmox cluster CA.

    urllib3 enables VERIFY_X509_STRICT on Python 3.13+. The self-generated Proxmox root CA has no keyUsage
    extension, which that profile requires, so valid node certificates were rejected. The chain to the cluster CA and
    the hostname/IP are still verified; only the profile check is relaxed.
    """
    context = ssl.create_default_context(cafile=str(ca_path))
    context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    session = requests.Session()
    session.mount("https://", ClusterCAAdapter(context))
    return session


def monitor_get(node, ca_path, path, timeout=TIMEOUT):
    try:
        with cluster_session(ca_path) as session:
            # verify is the same CA file, so no public CA bundle is ever added to the context.
            response = session.get(f"{node['url']}/api/{path}", headers={"Authorization": f"Bearer {node['token']}"}, timeout=timeout, verify=str(ca_path), allow_redirects=False)
    except requests.exceptions.SSLError:
        raise MonitorError("Het certificaat past niet bij de cluster-CA of het adres.") from None
    except requests.RequestException:
        raise MonitorError("Monitor niet bereikbaar.") from None
    except (OSError, ssl.SSLError):
        raise MonitorError("De cluster-CA kan niet worden gelezen. Koppel ProxMenux opnieuw.") from None
    if response.status_code == 401:
        raise MonitorError("Monitor weigert het API-token.")
    if response.status_code != 200:
        raise MonitorError("Monitor gaf een onverwacht antwoord.")
    try:
        return response.json()
    except ValueError:
        raise MonitorError("Monitor gaf een onverwacht antwoord.") from None


# Official channels from https://proxmenux.com/en/docs/installation/ (stable is recommended for production).
INSTALL_COMMANDS = {
    "stable": 'bash -c "$(wget -qLO - https://raw.githubusercontent.com/MacRimi/ProxMenux/main/install_proxmenux.sh)"',
    "beta": 'bash -c "$(wget -qLO - https://raw.githubusercontent.com/MacRimi/ProxMenux/develop/install_proxmenux_beta.sh)"',
}


def detect(url, ca_path):
    """Read-only probe without token: absent, http_only, untrusted_tls, auth_disabled or ready."""
    try:
        with cluster_session(ca_path) as session:
            response = session.get(f"{url}/api/auth/status", timeout=6, verify=str(ca_path), allow_redirects=False)
        status = response.json() if response.status_code == 200 else None
    except (requests.exceptions.SSLError, ssl.SSLError):
        return {"state": "untrusted_tls"}
    except ValueError:
        return {"state": "absent"}  # Something answers over https, but it is not ProxMenux Monitor.
    except requests.RequestException:
        try:
            # Only a public health probe; no token is ever sent over http.
            plain = requests.get(url.replace("https://", "http://", 1) + "/api/health", timeout=4, allow_redirects=False)
            if plain.status_code == 200:
                return {"state": "http_only"}
        except requests.RequestException:
            pass
        return {"state": "absent"}
    if not isinstance(status, dict):
        return {"state": "absent"}
    return {"state": "ready" if status.get("auth_enabled") is True else "auth_disabled"}


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def text(value, limit=200):
    return value[:limit] if isinstance(value, str) else None


def node_summary(health, storage, system, hardware, vms):
    """Whitelisted fields only; serial numbers, addresses and logs never leave the server."""
    details = health.get("details") if isinstance(health, dict) and isinstance(health.get("details"), dict) else {}
    categories = [{"id": name, "status": STATUS.get(item.get("status"), "unknown"), "reason": text(item.get("reason"))}
                  for name, item in details.items() if isinstance(item, dict)]
    disks = []
    for disk in (storage.get("disks") if isinstance(storage, dict) and isinstance(storage.get("disks"), list) else []):
        if not isinstance(disk, dict):
            continue
        life = number(disk.get("ssd_life_left"))
        temperature = number(disk.get("temperature"))
        disks.append({"name": text(disk.get("name"), 40), "model": text(disk.get("model"), 80), "health": text(disk.get("health"), 20), "smart": text(disk.get("smart_status"), 20),
                      # A sleeping disk reports 0 °C; that is "not measured", not a temperature.
                      "temperature": temperature if temperature not in (None, 0) else None, "wear": number(disk.get("percentage_used")) if number(disk.get("percentage_used")) is not None else (100 - life if life is not None else None),
                      "reallocated": number(disk.get("reallocated_sectors")), "pending": number(disk.get("pending_sectors")), "standby": disk.get("standby") is True, "size": text(disk.get("size_formatted"), 20)})
    pools = [{"name": text(pool.get("name"), 60), "health": text(pool.get("health"), 20), "size": text(pool.get("size"), 20), "free": text(pool.get("free"), 20)}
             for pool in (storage.get("zfs_pools") if isinstance(storage, dict) and isinstance(storage.get("zfs_pools"), list) else []) if isinstance(pool, dict)]
    updates = []
    for guest in vms if isinstance(vms, list) else []:
        check = guest.get("update_check") if isinstance(guest, dict) else None
        if isinstance(check, dict) and check.get("available"):
            # "latest" is "<count>:<security>:<package,package,...>" (truncated), not a version.
            packages = [str(item)[:60] for item in check.get("packages") if isinstance(item, str)][:5] if isinstance(check.get("packages"), list) else []
            packed = re.fullmatch(r"\d+:\d+:(.*)", check.get("latest") or "") if isinstance(check.get("latest"), str) else None
            if not packages and packed:
                packages = [name[:60] for name in packed.group(1).split(",") if re.fullmatch(r"[A-Za-z0-9.+_-]{1,60}", name)][:5]
            updates.append({"id": number(guest.get("vmid")), "name": text(guest.get("name"), 80), "count": number(check.get("count")), "security": number(check.get("security_count")), "packages": packages})
    load = system.get("load_average") if isinstance(system, dict) else None
    return {
        "overall": STATUS.get(health.get("overall") if isinstance(health, dict) else None, "unknown"),
        "summary": text(health.get("summary") if isinstance(health, dict) else None, 300),
        "categories": categories,
        "temperature": number(system.get("temperature")) if isinstance(system, dict) else None,
        "load": number(load[0]) if isinstance(load, list) and load else None,
        "hostUpdates": number(system.get("available_updates")) if isinstance(system, dict) else None,
        "powerWatts": number((hardware.get("power_meter") or {}).get("watts")) if isinstance(hardware, dict) and isinstance(hardware.get("power_meter"), dict) else None,
        "powerSource": text((hardware.get("power_meter") or {}).get("adapter"), 60) if isinstance(hardware, dict) and isinstance(hardware.get("power_meter"), dict) else None,
        "threads": number(system.get("cpu_threads")) if isinstance(system, dict) else None,
        "disks": disks, "zfsPools": pools, "lxcUpdates": sorted(updates, key=lambda item: -(item["security"] or 0)),
    }


def setup_proxmenux(app, configuration_path, data_dir):
    root = Path(data_dir) / "proxmenux"
    path, ca_path = root / "connection.json", root / "cluster-ca.pem"
    lock = Lock()
    cache = {}

    def load():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) and isinstance(data.get("nodes"), list) and isinstance(data.get("ca"), str) else None
        except (OSError, ValueError):
            return None

    def write(target, content):
        handle, temporary = tempfile.mkstemp(dir=root, prefix=".tmp-")
        try:
            os.chmod(temporary, 0o600)
            with os.fdopen(handle, "w", encoding="utf-8") as output:
                output.write(content)
            os.replace(temporary, target)
        finally:
            if Path(temporary).exists():
                Path(temporary).unlink()

    def ensure_ca(ca):
        root.mkdir(parents=True, exist_ok=True)
        os.chmod(root, 0o700)
        if not ca_path.is_file() or ca_path.read_text(encoding="utf-8") != ca:
            write(ca_path, ca)

    def check(nodes, ca):
        """Per node: valid certificate, accepted token and a hostname that matches the node name."""
        ensure_ca(ca)
        def one(node):
            try:
                hostname = (monitor_get(node, ca_path, "system") or {}).get("hostname")
                version = (monitor_get(node, ca_path, "health") or {}).get("version")
                if hostname != node["name"]:
                    return {"name": node["name"], "ok": False, "error": f"Dit adres/token hoort bij {text(hostname, 63) or 'een onbekende node'}, niet bij {node['name']}."}
                return {"name": node["name"], "ok": True, "version": text(version, 20)}
            except MonitorError as error:
                return {"name": node["name"], "ok": False, "error": str(error)}
        with ThreadPoolExecutor(max_workers=min(4, len(nodes))) as pool:
            return list(pool.map(one, nodes))

    def can_view():
        try:
            return any(module["id"] == "proxmox" for module in filter_configuration(load_config(configuration_path), g.account)["modules"])
        except ConfigurationError:
            return False

    def suggestions():
        """Node names and addresses from the existing Proxmox connection, to prefill the wizard."""
        try:
            connection = json.loads((Path(data_dir) / "proxmox/connection.json").read_text(encoding="utf-8"))
            status = ProxmoxClient(connection).get("/cluster/status")
            return [{"name": item["name"], "url": f"https://{item['ip']}:8008"} for item in status
                    if isinstance(item, dict) and item.get("type") == "node" and isinstance(item.get("name"), str) and NODE.fullmatch(item["name"]) and isinstance(item.get("ip"), str) and re.fullmatch(r"[0-9a-fA-F.:]{3,45}", item["ip"])]
        except (OSError, ValueError, KeyError, TypeError, ProxmoxError):
            return []

    @app.before_request
    def proxmenux_access():
        if not request.path.startswith("/api/proxmenux") or g.account is None:
            return None
        if request.path.startswith("/api/proxmenux/connection") and g.account["role"] != "admin":
            return jsonify(error="Beheerrechten vereist om ProxMenux te koppelen."), 403
        if not can_view():
            return jsonify(error="Geen toegang tot Proxmox."), 403
        return None

    def candidate():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not set(body) <= {"ca", "nodes"}:
            raise ValueError("Ongeldige verbindingsgegevens.")
        return validate_ca(body.get("ca")), validate_nodes(body.get("nodes"), load())

    @app.route("/api/proxmenux/connection", methods=["GET", "PUT", "DELETE"])
    def monitor_connection():
        if request.method == "GET":
            stored = load()
            return jsonify(connected=bool(stored), ca=stored["ca"] if stored else None,
                           nodes=[{"name": node["name"], "url": node["url"]} for node in stored["nodes"]] if stored else [],
                           suggestions=suggestions(), connectedAt=stored.get("connectedAt") if stored else None)
        if request.method == "DELETE":
            with lock:
                path.unlink(missing_ok=True)
                cache.clear()
            return jsonify(connected=False)
        try:
            ca, nodes = candidate()
            results = check(nodes, ca)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        except OSError:
            return jsonify(error="De koppeling kan niet worden opgeslagen."), 503
        if not all(result["ok"] for result in results):
            return jsonify(error="Niet alle nodes zijn goedgekeurd.", nodes=results), 400
        try:
            with lock:
                write(path, json.dumps({"ca": ca, "nodes": nodes, "connectedAt": int(time.time()), "connectedBy": g.account["email"]}))
                cache.clear()
        except OSError:
            return jsonify(error="De koppeling kan niet worden opgeslagen."), 503
        return jsonify(connected=True, nodes=results)

    @app.post("/api/proxmenux/connection/detect")
    def monitor_detect():
        """Wizard step: finds per node whether the monitor is installed and ready to connect."""
        body = request.get_json(silent=True)
        try:
            if not isinstance(body, dict) or not set(body) <= {"ca", "nodes"} or not isinstance(body.get("nodes"), list) or not 1 <= len(body["nodes"]) <= MAX_NODES:
                raise ValueError("Ongeldige nodegegevens.")
            ca = validate_ca(body.get("ca"))
            nodes = []
            for node in body["nodes"]:
                if not isinstance(node, dict) or not isinstance(node.get("name"), str) or not NODE.fullmatch(node["name"]):
                    raise ValueError("Ongeldige nodenaam.")
                nodes.append({"name": node["name"], "url": normalize_url(node.get("url"), 8008)})
            ensure_ca(ca)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        except OSError:
            return jsonify(error="De detectie kan niet worden uitgevoerd."), 503
        with ThreadPoolExecutor(max_workers=min(4, len(nodes))) as pool:
            found = list(pool.map(lambda node: {**node, **detect(node["url"], ca_path)}, nodes))
        return jsonify(nodes=found, installCommands=INSTALL_COMMANDS)

    @app.post("/api/proxmenux/connection/test")
    def monitor_test_connection():
        try:
            ca, nodes = candidate()
            return jsonify(nodes=check(nodes, ca))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        except OSError:
            return jsonify(error="De test kan niet worden uitgevoerd."), 503

    @app.get("/api/proxmenux/summary")
    def monitor_summary():
        stored = load()
        if stored is None:
            return jsonify(error="ProxMenux is nog niet gekoppeld.", code="not_connected"), 409
        try:
            ensure_ca(stored["ca"])
        except OSError:
            return jsonify(error="De cluster-CA kan niet worden gelezen."), 503

        def fetch(node, key):
            """Fetches the five monitor endpoints in parallel and stores the result or the error."""
            def part(name):
                try:
                    return monitor_get(node, ca_path, name, PART_TIMEOUTS.get(name, TIMEOUT)), None
                except MonitorError as error:
                    return None, str(error)
            try:
                with ThreadPoolExecutor(max_workers=len(PARTS)) as parts:
                    results = dict(zip(PARTS, parts.map(part, PARTS)))
                failed = [name for name, (_, error) in results.items() if error]
                if len(failed) == len(PARTS):
                    raise MonitorError(results[PARTS[0]][1])
                data = node_summary(*(results[name][0] or {} for name in PARTS))
                data["partial"] = [PART_LABELS[name] for name in failed]
                with lock:
                    cache[node["name"]] = {"key": key, "at": time.time(), "data": data, "error": None, "refreshing": False}
            except MonitorError as error:
                with lock:
                    entry = cache.get(node["name"])
                    if entry and entry["key"] == key:
                        entry.update(error=str(error), refreshing=False)
                    else:
                        cache[node["name"]] = {"key": key, "at": 0.0, "data": None, "error": str(error), "refreshing": False}

        def view(node, entry):
            if entry["data"] is None:
                if entry["error"] is None:
                    return {"name": node["name"], "overall": "unknown", "loading": True, "stale": False}
                return {"name": node["name"], "overall": "unknown", "error": entry["error"], "stale": True}
            stale = bool(entry["error"]) or time.time() - entry["at"] > STALE_SECONDS
            return {"name": node["name"], **entry["data"], "updatedAt": int(entry["at"]), "stale": stale, **({"error": entry["error"]} if entry["error"] else {})}

        def one(node):
            # Stale-while-revalidate: known data is returned at once; only the very first load waits.
            key = (node["name"], node["url"], stored.get("connectedAt"))
            with lock:
                entry = cache.get(node["name"])
                known = entry is not None and entry["key"] == key
                if known and (time.time() - entry["at"] < CACHE_SECONDS or entry["refreshing"]):
                    return view(node, entry)
                if known:
                    entry["refreshing"] = True
                if not known:
                    cache[node["name"]] = {"key": key, "at": 0.0, "data": None, "error": None, "refreshing": True}
            Thread(target=fetch, args=(node, key), daemon=True).start()
            with lock:
                return view(node, cache[node["name"]])

        # One unreachable node never blocks the others.
        with ThreadPoolExecutor(max_workers=min(4, len(stored["nodes"]))) as pool:
            return jsonify(nodes=list(pool.map(one, stored["nodes"])))
