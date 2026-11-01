"""Workfarm: the Prefect worker dashboard, proxied by nginx under /workfarm/ behind this check."""
import os
from urllib.parse import urlsplit

from flask import g, jsonify, request
from backend.auth import filter_configuration
from backend.configuration import ConfigurationError, load_config


def setup_workfarm(app, configuration_path):
    def permitted():
        try:
            config = filter_configuration(load_config(configuration_path), g.account)
            return any(m["id"] == "workfarm" for m in config["modules"])
        except ConfigurationError:
            return False

    @app.get("/api/workfarm/authorize")
    def authorize_workfarm():
        if not permitted():
            return jsonify(error="Workfarm niet toegestaan."), 403
        if not urlsplit(request.headers.get("X-Original-URI", "")).path.startswith("/workfarm/"):
            return jsonify(error="Ongeldig pad."), 403
        if request.headers.get("X-Original-Method", "GET") not in ("GET", "HEAD"):
            # Pausing a worker or freeing a GPU changes the farm: editors only, from ControlDeck itself.
            origin = os.environ.get("CONTROLDECK_BASE_URL", "").rstrip("/")
            if g.account["role"] not in ("admin", "editor"):
                return jsonify(error="Alleen beheerders kunnen workers bedienen."), 403
            if not origin.startswith("https://") or request.headers.get("Origin") != origin:
                return jsonify(error="Ongeldige herkomst."), 403
        return "", 204
