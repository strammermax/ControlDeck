"""Virtual Apps: start and stop the user's own Kasm workspaces. Kasm API credentials stay on the server."""

import base64
import binascii
import json
import re
import time
from threading import Lock
from urllib.parse import urlsplit

import requests
from flask import g, jsonify, request

from backend.auth import filter_configuration
from backend.configuration import ConfigurationError, load_config
from backend.modules.kasm import kasm_config, kasm_post, linked_user
from backend.vault import VaultError

KASM_ID = re.compile(r"[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
IMAGE_SRC = re.compile(r"[A-Za-z0-9_./-]{1,300}\.(?:png|jpg|jpeg|svg|webp)")
DATA_ICON = re.compile(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/]+={0,2})")
MAX_DATA_ICON = 256 * 1024
SIGNATURES = {"png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"), "jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
              "webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP"}
CONNECT = re.compile(r"/connect/kasm/[A-Za-z0-9_-]{1,128}/[A-Za-z0-9_-]{1,128}/[A-Za-z0-9_.-]{1,512}")


class KasmError(Exception):
    status = 424  # Not 502: Cloudflare would replace the message with its own page.


class NotLinked(KasmError):
    status = 403


class NotConfigured(KasmError):
    status = 503


def kasm_settings(settings, email):
    """Validated Kasm settings (shared with the login module) and the Kasm user linked to this account."""
    config = settings.get("kasm") if isinstance(settings, dict) else None
    if config is None:
        raise NotConfigured("Kasm is nog niet ingericht. Vraag je beheerder de Kasm-koppeling in Infisical in te stellen.")
    try:
        kasm = kasm_config(config)
    except ValueError:
        raise NotConfigured("Ongeldige Kasm-inrichting.") from None
    try:
        return kasm, linked_user(kasm, {"email": email})
    except (PermissionError, ValueError):
        raise NotLinked("Er is geen Kasm-account aan jouw profiel gekoppeld.") from None


def kasm_call(kasm, endpoint, **body):
    try:
        response = kasm_post(kasm, endpoint, **body)
        if response.status_code in (301, 302, 303, 307, 308):
            raise KasmError("Kasm is niet bereikbaar: het adres stuurt door naar een aanmeldpagina. Stel apiUrl in op het interne adres.")
        value = response.json() if response.status_code == 200 else None
    except (requests.RequestException, ValueError):
        raise KasmError("Kasm is niet bereikbaar of geeft geen API-antwoord. Controleer apiUrl en apiFingerprint.") from None
    if not isinstance(value, dict):
        raise KasmError("Kasm weigert de aanvraag. Controleer de rechten van de API-sleutel.")
    if value.get("error_message"):
        raise KasmError("Kasm weigert de aanvraag: " + str(value["error_message"])[:200])
    return value


def workspace_icon(origin, source):
    """A Kasm thumbnail path on the Kasm origin, or an embedded PNG/JPEG/WebP that really is that image.
    External icon URLs are never loaded (same policy as Bookmarks)."""
    if not isinstance(source, str):
        return None
    if source.startswith("data:"):
        match = DATA_ICON.fullmatch(source) if len(source) <= MAX_DATA_ICON * 4 // 3 + 40 else None
        if not match:
            return None
        try:
            data = base64.b64decode(match.group(2), validate=True)
        except (binascii.Error, ValueError):
            return None
        return source if len(data) <= MAX_DATA_ICON and SIGNATURES[match.group(1)](data) else None
    path = source.lstrip("/")
    return origin + "/" + path if IMAGE_SRC.fullmatch(path) and ".." not in path else None


def project_images(origin, value):
    """Enabled workspaces only, with display fields; icons are public files on the Kasm origin."""
    rows = value.get("images")
    if not isinstance(rows, list):
        raise KasmError("Kasm gaf een ongeldige lijst met workspaces.")
    apps = []
    for image in rows[:200]:
        if not isinstance(image, dict) or image.get("enabled") is False:
            continue
        identifier, name = str(image.get("image_id", "")), image.get("friendly_name")
        if not KASM_ID.fullmatch(identifier) or not isinstance(name, str) or not name.strip():
            continue
        icon = workspace_icon(origin, image.get("image_src"))
        categories = [str(c)[:60] for c in image.get("categories") or [] if isinstance(c, str)][:10]
        apps.append({"id": identifier, "name": name.strip()[:100], "description": str(image.get("description") or "")[:300],
                     "icon": icon, "categories": categories})
    return sorted(apps, key=lambda app: app["name"].casefold())


def project_sessions(value, user_id, apps):
    rows = value.get("kasms")
    if not isinstance(rows, list):
        raise KasmError("Kasm gaf een ongeldige lijst met sessies.")
    names = {app["id"]: app["name"] for app in apps}
    sessions = []
    for kasm in rows[:500]:
        if not isinstance(kasm, dict) or str(kasm.get("user_id", "")).replace("-", "") != user_id.replace("-", ""):
            continue  # Never another user's session.
        identifier = str(kasm.get("kasm_id", ""))
        if not KASM_ID.fullmatch(identifier):
            continue
        image = kasm.get("image") if isinstance(kasm.get("image"), dict) else {}
        image_id = str(kasm.get("image_id") or image.get("image_id") or "")
        sessions.append({"id": identifier, "appId": image_id if KASM_ID.fullmatch(image_id) else None,
                         "name": str(image.get("friendly_name") or names.get(image_id) or "Workspace")[:100],
                         "status": str(kasm.get("operational_status") or "")[:40],
                         "started": str(kasm.get("start_date") or "")[:40], "expires": str(kasm.get("expiration_date") or "")[:40]})
    return sessions


def connect_url(origin, value, api=None):
    """Only Kasm's own connect route, opened on the public origin (also when Kasm answers with its internal address)."""
    path = value.get("kasm_url")
    if not isinstance(path, str) or len(path) > 2048 or any(c.isspace() or c == "\\" for c in path):
        raise KasmError("Kasm gaf geen geldige sessielink.")
    if api and api != origin and path.startswith(api + "/"):
        path = path[len(api):]
    target = path if path.startswith("https://") else origin + "/" + path.lstrip("/")
    parts, expected = urlsplit(target), urlsplit(origin)
    if (parts.scheme, parts.netloc) != (expected.scheme, expected.netloc) or parts.query or parts.path not in ("", "/") or not CONNECT.fullmatch(parts.fragment):
        raise KasmError("Kasm gaf geen geldige sessielink.")
    return target


def setup_virtual_apps(app, configuration_path):
    cache, lock = {}, Lock()

    def settings():
        vault = app.extensions.get("controldeck_vault")
        if vault is None:
            raise NotConfigured("De keyvault is niet ingericht.")
        try:
            value = json.loads(vault.read().get("CONTROLDECK_APP_LAUNCHES", "{}"))
        except (VaultError, ValueError):
            raise NotConfigured("De Kasm-inrichting kon niet worden gelezen.") from None
        return kasm_settings(value, g.account["email"])

    def images(kasm):
        origin = kasm["origin"]
        key = (kasm["api"], kasm["auth"]["api_key"])
        with lock:
            hit = cache.get(key)
            if hit and time.time() - hit[0] < 60:
                return hit[1]
        value = project_images(origin, kasm_call(kasm, "get_images"))
        with lock:
            cache.clear()
            cache[key] = (time.time(), value)
        return value

    @app.before_request
    def virtual_apps_access():
        if request.path.startswith("/api/virtual-apps") and g.account is not None:
            try:
                allowed = {m["id"] for m in filter_configuration(load_config(configuration_path), g.account)["modules"]}
            except ConfigurationError:
                return jsonify(error="De moduleconfiguratie is niet beschikbaar."), 503
            if "virtual-apps" not in allowed:
                return jsonify(error="Geen toegang tot Virtual Apps."), 403

    @app.errorhandler(KasmError)
    def kasm_error(error):
        return jsonify(error=str(error), notConfigured=isinstance(error, NotConfigured), notLinked=isinstance(error, NotLinked)), error.status

    @app.get("/api/virtual-apps")
    def virtual_apps():
        kasm, user_id = settings()
        apps = images(kasm)
        sessions = project_sessions(kasm_call(kasm, "get_kasms"), user_id, apps)
        result = jsonify(apps=apps, sessions=sessions, portal=kasm["origin"])
        result.headers["Cache-Control"] = "no-store"
        return result

    @app.post("/api/virtual-apps/<image_id>/start")
    def start_virtual_app(image_id):
        if not KASM_ID.fullmatch(image_id) or request.get_json(silent=True) != {}:
            return jsonify(error="Ongeldige workspace."), 400
        kasm, user_id = settings()
        if not any(app_["id"] == image_id for app_ in images(kasm)):
            return jsonify(error="Deze workspace is niet beschikbaar."), 404
        url = connect_url(kasm["origin"], kasm_call(kasm, "request_kasm", user_id=user_id, image_id=image_id, enable_sharing=False), kasm["api"])
        result = jsonify(url=url)
        result.headers["Cache-Control"] = "no-store"
        result.headers["Referrer-Policy"] = "no-referrer"
        return result

    @app.delete("/api/virtual-apps/sessions/<kasm_id>")
    def stop_virtual_app(kasm_id):
        if not KASM_ID.fullmatch(kasm_id):
            return jsonify(error="Ongeldige sessie."), 400
        kasm, user_id = settings()
        mine = project_sessions(kasm_call(kasm, "get_kasms"), user_id, [])
        if not any(session["id"] == kasm_id for session in mine):
            return jsonify(error="Sessie niet gevonden."), 404
        kasm_call(kasm, "destroy_kasm", kasm_id=kasm_id, user_id=user_id)
        return jsonify(ok=True)
