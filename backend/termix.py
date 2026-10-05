"""Termix bridge with a fixed, private loopback upstream."""
import os
import secrets
from urllib.parse import urlsplit

import requests
from flask import g, jsonify, request
from backend.auth import filter_configuration
from backend.configuration import ConfigurationError, load_config

UPSTREAM = "http://127.0.0.1:8090"


def setup_termix(app, configuration_path):
    def permitted():
        try:
            config = filter_configuration(load_config(configuration_path), g.account)
            return any(m["id"] == "terminal" for m in config["modules"]) and any(p["id"] == "termix" and p["type"] == "termix" and p["enabled"] for p in config["providers"])
        except ConfigurationError:
            return False

    @app.post("/api/termix/session")
    def start_session():
        if not permitted():
            return jsonify(error="Termix is niet ingeschakeld of niet toegestaan."), 403
        try:
            # The gateway blocks public registration. Provision only the verified
            # ControlDeck email; random passwords are never returned or retained.
            created = requests.post(UPSTREAM + "/users/create", json={"username": g.account["email"], "password": secrets.token_urlsafe(48)}, timeout=5)
            if created.status_code not in (200, 201, 409):
                raise ValueError("Provisioning rejected")
            response = requests.post(UPSTREAM + "/users/proxy-login", headers={"X-Forwarded-Username": g.account["email"], "X-Forwarded-Role": g.account["role"], "X-Forwarded-Proto": "https"}, timeout=5)
            data = response.json()
            if response.status_code != 200 or not isinstance(data, dict) or not data.get("success") or not isinstance(data.get("token"), str) or not data["token"]:
                raise ValueError("Login rejected")
            result = jsonify(token=data["token"])
            result.set_cookie("jwt", data["token"], secure=True, httponly=True, samesite="Lax", path="/termix/")
            return result
        except (requests.RequestException, ValueError):
            return jsonify(error="Termix is momenteel niet beschikbaar. Probeer opnieuw."), 503

    @app.get("/api/termix/authorize")
    def authorize():
        if not permitted():
            return jsonify(error="Terminal niet toegestaan."), 403
        path = urlsplit(request.headers.get("X-Original-URI", "")).path
        if not path.startswith("/termix/"):
            return jsonify(error="Ongeldig pad."), 403
        method = request.headers.get("X-Original-Method", "GET")
        if method not in ("GET", "HEAD", "OPTIONS") or request.headers.get("X-Original-Upgrade", "").lower() == "websocket":
            origin = os.environ.get("CONTROLDECK_BASE_URL", "").rstrip("/")
            if not origin.startswith("https://") or request.headers.get("Origin") != origin:
                return jsonify(error="Ongeldige herkomst."), 403
        bootstrap = path in ("/termix/", "/termix/index.html", "/termix/users/proxy-login") or path.startswith(("/termix/assets/", "/termix/fonts/", "/termix/icons/"))
        if not bootstrap:
            tokens = []
            if request.cookies.get("jwt"):
                tokens.append(request.cookies["jwt"])
            authorization = request.headers.get("Authorization", "")
            if authorization.startswith("Bearer "):
                tokens.append(authorization[7:])
            tokens.extend(p.strip()[11:] for p in request.headers.get("Sec-WebSocket-Protocol", "").split(",") if p.strip().startswith("termix.jwt."))
            if not tokens:
                return jsonify(error="Termix-sessie vereist."), 401
            try:
                for token in set(tokens):
                    response = requests.get(UPSTREAM + "/users/me", headers={"Authorization": "Bearer " + token}, timeout=3)
                    user = response.json()
                    if response.status_code != 200 or not isinstance(user, dict) or user.get("username") != g.account["email"] or bool(user.get("is_admin")) != (g.account["role"] == "admin"):
                        return jsonify(error="Termix-sessie hoort niet bij dit profiel."), 403
            except (requests.RequestException, ValueError):
                return jsonify(error="Termix niet beschikbaar."), 503
        result = app.response_class(status=204)
        result.headers["X-Forwarded-Username"] = g.account["email"]
        result.headers["X-Forwarded-Role"] = g.account["role"]
        return result
