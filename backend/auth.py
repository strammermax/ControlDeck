"""Cloudflare Access or Google OIDC login, local account permissions and persistent per-user preferences."""

import json
import os
from pathlib import Path
import secrets
import re
import tempfile
import time
from contextlib import contextmanager
from threading import Lock
import sqlite3
from datetime import timedelta

import requests
from authlib.integrations.flask_client import OAuth
from flask import g, jsonify, redirect, request, session
from joserfc import jwt as jose_jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet

from backend.configuration import ConfigurationError, identifier, require
from backend.vault import Vault, VaultError

ACCESS_LOGOUT_URL = "/cdn-cgi/access/logout"
ROLES = ("admin", "editor", "user")
# Editors manage modules, providers and connections; only admins manage accounts.
MANAGER_ROLES = ("admin", "editor")


def is_manager(account):
    return isinstance(account, dict) and account.get("role") in MANAGER_ROLES


class CloudflareAccess:
    """Verifies the signed identity Cloudflare Access adds to every proxied request.

    The assertion is only trusted after checking its RS256 signature against the
    team's published keys, the issuer, this application's audience tag and the
    validity window. A forged or replayed header from inside the LAN is rejected.
    """

    def __init__(self, team_domain, audience, key_ttl=3600):
        self.issuer = team_domain.rstrip("/")
        self.audience = audience
        self.key_ttl = key_ttl
        self._keys, self._fetched, self._lock = None, 0.0, Lock()

    def keys(self, refresh=False):
        with self._lock:
            if refresh or self._keys is None or time.time() - self._fetched > self.key_ttl:
                response = requests.get(self.issuer + "/cdn-cgi/access/certs", timeout=5)
                response.raise_for_status()
                self._keys, self._fetched = KeySet.import_key_set(response.json()), time.time()
            return self._keys

    def verify(self, assertion):
        """Returns {"email", "sub"} for a valid assertion, otherwise None."""
        if not isinstance(assertion, str) or not 0 < len(assertion) <= 8192:
            return None
        registry = jose_jwt.JWTClaimsRegistry(leeway=30, iss={"essential": True, "value": self.issuer},
                                              aud={"essential": True, "value": self.audience},
                                              exp={"essential": True}, email={"essential": True}, sub={"essential": True})
        # A key rotation shows up as an unknown key id: refresh the key set once.
        for refresh in (False, True):
            try:
                claims = jose_jwt.decode(assertion, self.keys(refresh), algorithms=["RS256"]).claims
                registry.validate(claims)
            except (JoseError, ValueError, requests.RequestException):
                continue
            email, subject = claims["email"], claims["sub"]
            if isinstance(email, str) and isinstance(subject, str) and 0 < len(subject) <= 255:
                return {"email": email.casefold(), "sub": subject}
            return None
        return None


def validate_accounts(data):
    require(isinstance(data, list) and len(data) <= 200, "accounts: expected at most 200 profiles")
    emails, result = set(), []
    for original in data:
        require(isinstance(original, dict) and set(original) <= {"firstName", "lastName", "email", "role", "enabled", "ssoType", "modules"} and {"email", "role"} <= set(original), "Invalid account fields")
        account = {"firstName": "", "lastName": "", "enabled": True, "ssoType": "google", "modules": ["*"], **original}
        for name in ("firstName", "lastName"):
            require(isinstance(account[name], str) and len(account[name]) <= 100, "Invalid profile name")
        email = account["email"]
        require(isinstance(email, str) and len(email) <= 254 and re.fullmatch(r"[^\s@,]+@[^\s@,]+\.[^\s@,]+", email), "Invalid account email")
        email = email.casefold()
        require(email not in emails, "Duplicate account email")
        emails.add(email)
        account["email"] = email
        require(account["role"] in ROLES, "Invalid role")
        require(type(account["enabled"]) is bool, "enabled must be boolean")
        require(account["ssoType"] in ("google", "windows"), "Invalid SSO type")
        require(isinstance(account["modules"], list) and len(account["modules"]) <= 100, "account.modules: expected an array")
        for mid in account["modules"]:
            if mid != "*":
                identifier(mid, "account.modules")
        result.append(account)
    return result


def load_accounts(path):
    try:
        with Path(path).open("rb") as source:
            raw = source.read(64 * 1024 + 1)
        require(len(raw) <= 64 * 1024, "Accounts file too large")
        return validate_accounts(json.loads(raw.decode("utf-8-sig")))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConfigurationError("Cannot read accounts file") from error


def write_accounts(path, accounts):
    data = json.dumps(validate_accounts(accounts), indent=2, ensure_ascii=False) + "\n"
    require(len(data.encode("utf-8")) <= 64 * 1024, "Accounts file too large")
    destination = Path(path)
    handle, temporary = tempfile.mkstemp(dir=destination.parent, prefix=".accounts-", suffix=".json")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def filter_configuration(config, account):
    """Server-side projection; UI hiding alone is not an authorization boundary."""
    if account["role"] == "admin":
        return config
    if account["role"] == "editor":
        return _without_user_management(config)
    allowed = set(account["modules"])
    # Administrative configuration remains admin-only even with a wildcard grant.
    modules = [module for module in config["modules"] if module["id"] != "admin" and ("*" in allowed or module["id"] in allowed)]
    routes = {route for module in modules for route in [module["id"], *(f"{module['id']}/{page['id']}" for page in module.get("pages", []))]}
    def entry(item):
        if "children" in item:
            children = [child for child in (entry(child) for child in item["children"]) if child]
            return {**item, "children": children} if children else None
        if "route" in item:
            return item if item["route"] in routes else None
        # External menu links are shared links, not provider permissions.
        return item
    provider_ids = {module["provider"] for module in modules if "provider" in module}
    if any(module.get("view") == "terminal" for module in modules):
        provider_ids.add("termix")
    return {**config, "modules": modules, "menu": [item for item in (entry(item) for item in config["menu"]) if item], "providers": [p for p in config["providers"] if p["id"] in provider_ids], "widgets": [w for w in config["widgets"] if w["route"] in routes and w["provider"] in provider_ids]}


def _without_user_management(config):
    """Everything an admin sees, minus the account management page."""
    hidden = "admin/users"
    modules = [{**module, "pages": [p for p in module.get("pages", []) if f"{module['id']}/{p['id']}" != hidden]} if module["id"] == "admin" else module
               for module in config["modules"]]
    def entry(item):
        if "children" in item:
            children = [child for child in (entry(child) for child in item["children"]) if child]
            return {**item, "children": children} if children else None
        return None if item.get("route") == hidden else item
    return {**config, "modules": modules, "menu": [item for item in (entry(item) for item in config["menu"]) if item],
            "widgets": [w for w in config["widgets"] if w.get("route") != hidden]}


@contextmanager
def database(path):
    connection = sqlite3.connect(path, timeout=5)
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS users (subject TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, preferences TEXT NOT NULL DEFAULT '{}')")
        with connection:
            yield connection
    finally:
        connection.close()


def establish_identity(db_path, claims):
    require(claims.get("email_verified") is True, "Google email must be verified")
    email, subject = claims.get("email"), claims.get("sub")
    require(isinstance(email, str) and isinstance(subject, str) and 0 < len(subject) <= 255, "Missing identity claims")
    email = email.casefold()
    with database(db_path) as db:
        # An approved email is bound to the stable Google subject on its first login.
        existing = db.execute("SELECT subject FROM users WHERE email = ?", (email,)).fetchone()
        require(existing is None or existing[0] == subject, "Email belongs to a different identity")
        db.execute("INSERT INTO users(subject,email) VALUES(?,?) ON CONFLICT(subject) DO UPDATE SET email=excluded.email", (subject, email))
    return {"sub": subject, "email": email}


def establish_access_identity(db_path, identity):
    """Cloudflare Access already proved the e-mail address. An existing profile keeps
    its subject (and preferences); a new one is stored under the Access subject."""
    with database(db_path) as db:
        existing = db.execute("SELECT subject FROM users WHERE email = ?", (identity["email"],)).fetchone()
        if existing is not None:
            return {"sub": existing[0], "email": identity["email"]}
        subject = "cloudflare:" + identity["sub"]
        db.execute("INSERT INTO users(subject,email) VALUES(?,?) ON CONFLICT(subject) DO UPDATE SET email=excluded.email", (subject, identity["email"]))
    return {"sub": subject, "email": identity["email"]}


LOGIN_TYPES = ("both", "cloudflare", "google")


def sync_from_vault(app, vault, accounts_path):
    """The vault is leading: CONTROLDECK_* settings become the environment and
    CONTROLDECK_ACCOUNTS replaces the local account file. When the vault is
    unreachable the last known account file keeps ControlDeck usable."""
    try:
        values = vault.read()
    except VaultError as error:
        app.logger.warning("Keyvault niet gelezen (%s); laatst bekende instellingen blijven actief", error)
        return False
    for name, value in values.items():
        if name.startswith("CONTROLDECK_") and name not in ("CONTROLDECK_ACCOUNTS", "CONTROLDECK_INFISICAL_PATH"):
            os.environ[name] = value
    raw_accounts = values.get("CONTROLDECK_ACCOUNTS")
    if raw_accounts is None and "ACCESS_USERS" in values:
        # The shared per-app access list: e-mail + role, all modules.
        try:
            raw_accounts = json.dumps([{"email": item["email"], "role": item.get("role", "user")}
                                       for item in json.loads(values["ACCESS_USERS"]) if isinstance(item, dict) and "email" in item])
        except (ValueError, TypeError):
            raw_accounts = "invalid"
    if raw_accounts is not None:
        try:
            write_accounts(accounts_path, json.loads(raw_accounts))
        except (ConfigurationError, ValueError, OSError):
            app.logger.warning("Accountlijst (CONTROLDECK_ACCOUNTS/ACCESS_USERS) in de keyvault is ongeldig; laatst bekende accounts blijven actief")
            return False
    return True


def setup_auth(app, data_dir, accounts_path):
    try:
        vault = Vault.from_env()
    except VaultError as error:
        app.logger.warning("Keyvault niet geconfigureerd: %s", error)
        vault = None
    app.extensions["controldeck_vault"] = vault
    if vault is not None:
        sync_from_vault(app, vault, accounts_path)
    login_type = os.environ.get("CONTROLDECK_LOGIN_TYPE", "both").strip().lower()
    if login_type not in LOGIN_TYPES:
        app.logger.warning("Onbekend CONTROLDECK_LOGIN_TYPE; 'both' wordt gebruikt")
        login_type = "both"
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    key_path = data_dir / "session.key"
    try:
        with key_path.open("x", encoding="ascii") as key_file:
            os.chmod(key_path, 0o600)
            key_file.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    app.secret_key = key_path.read_text(encoding="ascii").strip()
    require(len(app.secret_key) >= 64, "Invalid session key")
    app.config.update(SESSION_COOKIE_NAME="controldeck_session", SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", PERMANENT_SESSION_LIFETIME=timedelta(hours=8), SESSION_REFRESH_EACH_REQUEST=False, MAX_CONTENT_LENGTH=16 * 1024)
    db_path = data_dir / "users.sqlite3"
    with database(db_path):
        pass
    client_id = os.environ.get("CONTROLDECK_GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("CONTROLDECK_GOOGLE_CLIENT_SECRET", "")
    base_url = os.environ.get("CONTROLDECK_BASE_URL", "").rstrip("/")
    configured = login_type != "cloudflare" and bool(client_id and client_secret and base_url.startswith("https://"))
    google = None
    if configured:
        google = OAuth(app).register("google", client_id=client_id, client_secret=client_secret, server_metadata_url="https://accounts.google.com/.well-known/openid-configuration", client_kwargs={"scope": "openid email", "code_challenge_method": "S256", "timeout": 10})
    app.extensions["controldeck_google"] = google
    team_domain = os.environ.get("CONTROLDECK_CF_ACCESS_TEAM_DOMAIN", "").rstrip("/")
    audience = os.environ.get("CONTROLDECK_CF_ACCESS_AUD", "")
    access = CloudflareAccess(team_domain, audience) if login_type != "google" and team_domain.startswith("https://") and audience else None
    app.extensions["controldeck_access"] = access

    def account_for(email):
        try:
            return next((a for a in load_accounts(accounts_path) if a["email"] == email and a["enabled"] and a["ssoType"] == "google"), None)
        except ConfigurationError:
            return None

    @app.before_request
    def authorization():
        g.account = None
        g.via_access = False
        if access is not None:
            assertion = request.headers.get("Cf-Access-Jwt-Assertion") or request.cookies.get("CF_Authorization")
            verified = access.verify(assertion) if assertion else None
            if verified is not None:
                g.via_access = True
                current = session.get("identity")
                # The Access identity always wins over an older session for another user.
                if not (isinstance(current, dict) and current.get("email") == verified["email"]) and account_for(verified["email"]) is not None:
                    session.clear()
                    session["identity"] = establish_access_identity(db_path, verified)
                    session["csrf"] = secrets.token_hex(32)
                    session.permanent = True
        identity = session.get("identity")
        if isinstance(identity, dict) and isinstance(identity.get("email"), str):
            try:
                g.account = next((a for a in load_accounts(accounts_path) if a["email"] == identity["email"] and a["enabled"] and a["ssoType"] == "google"), None)
            except ConfigurationError:
                g.account = None
            if g.account is None:
                session.clear()
        if request.path.startswith("/api/") and request.path != "/api/session":
            if g.account is None:
                return jsonify(error="Aanmelden vereist."), 401
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                expected, supplied = session.get("csrf"), request.headers.get("X-CSRF-Token", "")
                if not isinstance(expected, str) or not secrets.compare_digest(expected, supplied):
                    return jsonify(error="Ongeldige aanvraag."), 403

    @app.get("/api/session")
    def session_info():
        user = {key: g.account[key] for key in ("firstName", "lastName", "email", "role", "ssoType")} if g.account else None
        return jsonify(authenticated=bool(user), loginAvailable=configured, user=user, csrfToken=session.get("csrf") if user else None,
                       logoutUrl=ACCESS_LOGOUT_URL if g.via_access else None, loginType=login_type)

    @app.get("/auth/google/login")
    def login():
        if google is None:
            return redirect("/?login=unavailable")
        try:
            return google.authorize_redirect(base_url + "/auth/google/callback", prompt="select_account")
        except Exception:
            app.logger.warning("Google login initiation failed")
            return redirect("/?login=failed")

    @app.get("/auth/google/callback")
    def callback():
        if google is None:
            return redirect("/?login=unavailable")
        try:
            # Authlib verifies state, nonce and the signed OIDC token using discovery/JWKS.
            token = google.authorize_access_token()
            claims = token.get("userinfo", {})
            require(claims.get("email_verified") is True and isinstance(claims.get("email"), str), "Verified email required")
            account = next((a for a in load_accounts(accounts_path) if a["email"] == claims["email"].casefold() and a["enabled"] and a["ssoType"] == "google"), None)
            require(account is not None, "Account not permitted")
            identity = establish_identity(db_path, claims)
            session.clear()
            session["identity"] = identity
            session["csrf"] = secrets.token_hex(32)
            session.permanent = True
            return redirect("/")
        except Exception:
            # Never log tokens, authorization codes, claims or client credentials.
            app.logger.warning("Google authentication rejected")
            session.clear()
            return redirect("/?login=denied")

    account_lock = Lock()

    @app.route("/api/accounts", methods=["GET", "POST"])
    @app.route("/api/accounts/<path:email>", methods=["PUT"])
    def accounts(email=None):
        if g.account["role"] != "admin":
            return jsonify(error="Beheerrechten vereist."), 403
        try:
            with account_lock:
                if vault is not None and request.method == "GET":
                    sync_from_vault(app, vault, accounts_path)
                values = load_accounts(accounts_path)
                if request.method == "GET":
                    return jsonify(values)
                payload = request.get_json(silent=True)
                account = validate_accounts([payload])[0]
                if request.method == "POST":
                    if any(item["email"] == account["email"] for item in values):
                        return jsonify(error="Dit e-mailadres bestaat al."), 409
                    values.append(account)
                else:
                    index = next((i for i, item in enumerate(values) if item["email"] == email.casefold()), None)
                    if index is None:
                        return jsonify(error="Gebruiker niet gevonden."), 404
                    values[index] = account
                require(any(a["role"] == "admin" and a["enabled"] and a["ssoType"] == "google" for a in values), "At least one enabled Google administrator must remain")
                if vault is not None:
                    # The vault is leading: store there first, then update the local copy.
                    vault.write("CONTROLDECK_ACCOUNTS", json.dumps(validate_accounts(values), ensure_ascii=False))
                write_accounts(accounts_path, values)
                return jsonify(account), 201 if request.method == "POST" else 200
        except ConfigurationError:
            return jsonify(error="Ongeldig profiel. Controleer de velden; minstens één actieve Google-admin moet behouden blijven."), 400
        except VaultError:
            return jsonify(error="Opslaan in de keyvault is mislukt; er is niets gewijzigd."), 503
        except OSError:
            return jsonify(error="Het profiel kan niet worden opgeslagen."), 503

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.route("/api/preferences", methods=["GET", "PUT"])
    def preferences():
        subject = session["identity"]["sub"]
        with database(db_path) as db:
            existing = db.execute("SELECT preferences FROM users WHERE subject=?", (subject,)).fetchone()
            if existing is None:
                return jsonify(error="Gebruiker niet gevonden."), 401
            values = json.loads(existing[0])
            if request.method == "PUT":
                patch = request.get_json(silent=True)
                if not isinstance(patch, dict) or not set(patch) <= {"theme", "lastRoute", "language", "navOrder"}:
                    return jsonify(error="Ongeldige voorkeuren."), 400
                if "theme" in patch and patch["theme"] not in ("dark", "light"):
                    return jsonify(error="Ongeldig thema."), 400
                if "language" in patch and patch["language"] not in ("nl", "en"):
                    return jsonify(error="Ongeldige taal."), 400
                # Only top-level menu ids; unknown or hidden ids are ignored by the UI, never granted.
                order = patch.get("navOrder", [])
                if not isinstance(order, list) or len(order) > 32 or len(set(map(str, order))) != len(order) or not all(isinstance(item, str) and len(item) <= 64 and re.fullmatch(r"[a-z][a-z0-9-]*", item) for item in order):
                    return jsonify(error="Ongeldige menuvolgorde."), 400
                if "lastRoute" in patch and (not isinstance(patch["lastRoute"], str) or len(patch["lastRoute"]) > 130 or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-/" for c in patch["lastRoute"])):
                    return jsonify(error="Ongeldige pagina."), 400
                values.update(patch)
                db.execute("UPDATE users SET preferences=? WHERE subject=?", (json.dumps(values), subject))
        return jsonify(values)
