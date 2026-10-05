"""Authenticated ControlDeck runtime with configuration and module integrations."""

import json
import os
import time
from pathlib import Path

from flask import Flask, g, jsonify, send_from_directory
from backend.configuration import ConfigurationError, DEFAULT_PATH, load_config
from backend.auth import filter_configuration, setup_auth
from backend.termix import setup_termix
from backend.installations import setup_installations
from backend.proxmox import setup_proxmox
from backend.proxmenux import setup_proxmenux
from backend.linkwarden import setup_linkwarden
from backend.homepage import setup_homepage

ROOT = Path(__file__).resolve().parent.parent


def create_app(static_directory=None, config_path=None, data_dir=None, accounts_path=None):
    static_root = Path(static_directory or ROOT / "frontend" / "out")
    app = Flask(__name__, static_folder=None)
    started_at = time.monotonic()
    configuration_path = config_path or os.environ.get("CONTROLDECK_CONFIG") or DEFAULT_PATH
    setup_auth(app, data_dir or os.environ.get("CONTROLDECK_DATA_DIR") or ROOT / "data", accounts_path or os.environ.get("CONTROLDECK_ACCOUNTS") or ROOT / "config/accounts.json")
    setup_termix(app, configuration_path)
    setup_installations(app, configuration_path, data_dir or os.environ.get("CONTROLDECK_DATA_DIR") or ROOT / "data")
    setup_proxmox(app, configuration_path, data_dir or os.environ.get("CONTROLDECK_DATA_DIR") or ROOT / "data")
    setup_proxmenux(app, configuration_path, data_dir or os.environ.get("CONTROLDECK_DATA_DIR") or ROOT / "data")
    setup_linkwarden(app, configuration_path, data_dir or os.environ.get("CONTROLDECK_DATA_DIR") or ROOT / "data")
    setup_homepage(app, configuration_path, data_dir or os.environ.get("CONTROLDECK_DATA_DIR") or ROOT / "data")
    metadata_path = ROOT / "build-info.json"
    metadata = (
        json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata_path.exists()
        else {"version": (ROOT / "VERSION").read_text().strip(), "commit": "development"}
    )

    @app.get("/health")
    def health():
        return jsonify(status="ok", uptime_seconds=int(time.monotonic() - started_at), **metadata)

    @app.get("/ready")
    def ready():
        index_path = static_root / "index.html"
        status = index_path.is_file() and index_path.stat().st_size > 0
        try:
            load_config(configuration_path)
        except ConfigurationError:
            status = False
        return jsonify(status="ready" if status else "not_ready"), 200 if status else 503

    @app.get("/api/config")
    def configuration():
        try:
            return jsonify(filter_configuration(load_config(configuration_path), g.account))
        except ConfigurationError as error:
            app.logger.error("Invalid UI configuration: %s", error)
            return jsonify(error="De configuratie kan niet worden geladen. Controleer het JSON-bestand."), 503

    @app.get("/")
    def index():
        return send_from_directory(static_root, "index.html")

    @app.get("/<path:filename>")
    def static_file(filename):
        return send_from_directory(static_root, filename)

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if response.mimetype == "text/html" or response.is_json:
            response.headers["Cache-Control"] = "no-store"
        return response

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("CONTROLDECK_PORT", "8080")))
