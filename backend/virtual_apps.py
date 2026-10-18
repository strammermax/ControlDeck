"""Virtual Apps: start and stop the user's own Kasm workspaces. Kasm API credentials stay on the server."""

import json
import re
import time
import uuid
from threading import Lock
from urllib.parse import urlsplit

import requests
from flask import g, jsonify, request

from backend.auth import filter_configuration
from backend.configuration import ConfigurationError, load_config
from backend.modules.launch_urls import secure_origin
from backend.vault import VaultError

KASM_ID = re.compile(r"[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
IMAGE_SRC = re.compile(r"[A-Za-z0-9_./-]{1,300}\.(?:png|jpg|jpeg|svg|webp)")
CONNECT = re.compile(r"/connect/kasm/[A-Za-z0-9_-]{1,128}/[A-Za-z0-9_-]{1,128}/[A-Za-z0-9_.-]{1,512}")


class KasmError(Exception):
    status = 424  # Not 502: Cloudflare would replace the message with its own page.


class NotLinked(KasmError):
    status = 403


class NotConfigured(KasmError):
    status = 503


def kasm_settings(settings, email):
    """Validated origin, API credentials and the Kasm user id linked to this ControlDeck account."""
    config = settings.get("kasm") if isinstance(settings, dict) else None
    if not isinstance(config, dict) or set(config) != {"url", "apiKey", "apiSecret", "users"}:
        raise NotConfigured("Kasm is nog niet ingericht. Vraag je beheerder de Kasm-koppeling in Infisical in te stellen.")
    try:
        origin = secure_origin(config["url"])
    except ValueError:
        raise NotConfigured("Ongeldige Kasm-inrichting.") from None
    if any(not isinstance(config[key], str) or not config[key] or len(config[key]) > 4096 for key in ("apiKey", "apiSecret")) or not isinstance(config["users"], dict):
        raise NotConfigured("Ongeldige Kasm-inrichting.")
    user_id = config["users"].get(email)
    try:
        if not isinstance(user_id, str):
            raise ValueError
        uuid.UUID(user_id)
    except ValueError:
        raise NotLinked("Er is geen Kasm-account aan jouw profiel gekoppeld.") from None
    return origin, {"api_key": config["apiKey"], "api_key_secret": config["apiSecret"]}, user_id


def kasm_call(origin, auth, endpoint, **body):
    try:
        response = requests.post(f"{origin}/api/public/{endpoint}", json={**auth, **body}, timeout=(5, 30), allow_redirects=False)
        value = response.json() if response.status_code == 200 else None
    except (requests.RequestException, ValueError):
        raise KasmError("Kasm is niet bereikbaar.") from None
    if not isinstance(value, dict):
        raise KasmError("Kasm weigert de aanvraag. Controleer de rechten van de API-sleutel.")
    if value.get("error_message"):
        raise KasmError("Kasm weigert de aanvraag: " + str(value["error_message"])[:200])
    return value


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
        source = image.get("image_src")
        icon = origin + "/" + source.lstrip("/") if isinstance(source, str) and IMAGE_SRC.fullmatch(source.lstrip("/")) and ".." not in source else None
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


def connect_url(origin, value):
    """Only Kasm's own connect route on the configured origin."""
    path = value.get("kasm_url")
    if not isinstance(path, str) or len(path) > 2048 or any(c.isspace() or c == "\\" for c in path):
        raise KasmError("Kasm gaf geen geldige sessielink.")
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

    def images(origin, auth):
        key = (origin, auth["api_key"])
        with lock:
            hit = cache.get(key)
            if hit and time.time() - hit[0] < 60:
                return hit[1]
        value = project_images(origin, kasm_call(origin, auth, "get_images"))
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
        origin, auth, user_id = settings()
        apps = images(origin, auth)
        sessions = project_sessions(kasm_call(origin, auth, "get_kasms"), user_id, apps)
        result = jsonify(apps=apps, sessions=sessions, portal=origin)
        result.headers["Cache-Control"] = "no-store"
        return result

    @app.post("/api/virtual-apps/<image_id>/start")
    def start_virtual_app(image_id):
        if not KASM_ID.fullmatch(image_id) or request.get_json(silent=True) != {}:
            return jsonify(error="Ongeldige workspace."), 400
        origin, auth, user_id = settings()
        if not any(app_["id"] == image_id for app_ in images(origin, auth)):
            return jsonify(error="Deze workspace is niet beschikbaar."), 404
        url = connect_url(origin, kasm_call(origin, auth, "request_kasm", user_id=user_id, image_id=image_id, enable_sharing=False))
        result = jsonify(url=url)
        result.headers["Cache-Control"] = "no-store"
        result.headers["Referrer-Policy"] = "no-referrer"
        return result

    @app.delete("/api/virtual-apps/sessions/<kasm_id>")
    def stop_virtual_app(kasm_id):
        if not KASM_ID.fullmatch(kasm_id):
            return jsonify(error="Ongeldige sessie."), 400
        origin, auth, user_id = settings()
        mine = project_sessions(kasm_call(origin, auth, "get_kasms"), user_id, [])
        if not any(session["id"] == kasm_id for session in mine):
            return jsonify(error="Sessie niet gevonden."), 404
        kasm_call(origin, auth, "destroy_kasm", kasm_id=kasm_id, user_id=user_id)
        return jsonify(ok=True)
