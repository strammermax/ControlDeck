"""Minimal deployment foundation; integrations and login are not implemented yet."""

import json
import os
import time
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

ROOT = Path(__file__).resolve().parent.parent


def create_app(static_directory=None):
    static_root = Path(static_directory or ROOT / "frontend" / "out")
    app = Flask(__name__, static_folder=None)
    started_at = time.monotonic()
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
        status = static_root.joinpath("index.html").is_file()
        return jsonify(status="ready" if status else "not_ready"), 200 if status else 503

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
