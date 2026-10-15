"""Session-protected widgets and one narrowly scoped machine ingestion endpoint."""
import hashlib
import json
import re
import secrets
import sqlite3
import time
from xml.etree.ElementTree import ParseError
from pathlib import Path
from threading import Lock
from flask import g, jsonify, request
from backend.configuration import ConfigurationError
from backend.widget_sources import FAMILIES, sources, permitted
from backend.widgets.adapters import ADAPTERS, statistics_payload, result
from backend.widgets.calendar import nextcloud
from backend.widgets.transport import ProviderError, Transport


def setup_service_widgets(app, configuration_path, data_dir):
    cache, lock = {}, Lock()
    db_path = Path(data_dir) / "widget-statistics.sqlite3"

    def database():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(db_path, timeout=5)
        db.execute("CREATE TABLE IF NOT EXISTS readings (source TEXT PRIMARY KEY, payload TEXT NOT NULL, received REAL NOT NULL)")
        return db

    def response(body, status=200):
        output = jsonify(body)
        output.headers["Cache-Control"] = "no-store"
        return output, status

    @app.get("/api/widget-sources")
    def widget_sources():
        family = request.args.get("family")
        if family not in FAMILIES:
            return response({"error": "Onbekend widgettype."}, 400)
        try:
            rows = [{"id": key, "title": source["title"], "kind": source["kind"]} for key, source in sources(app).items()
                    if source["family"] == family and permitted(source, g.account, configuration_path)]
            return response({"sources": rows})
        except (ProviderError, ConfigurationError):
            return response({"error": "Widgetbronnen zijn niet beschikbaar."}, 503)

    @app.get("/api/widgets/<family>/<source_id>")
    def service_widget(family, source_id):
        try:
            source = sources(app).get(source_id)
            if not source or source["family"] != family or not permitted(source, g.account, configuration_path):
                return response({"error": "Widgetbron niet beschikbaar."}, 404)
            def served(body):
                return response({**body, "sourceTitle": source["title"]})
            if source["kind"] == "homeassistant-dashboard":
                return served({"embedUrl": source["url"], "title": source["title"]})
            if source["kind"] == "statistics":
                with database() as db:
                    row = db.execute("SELECT payload, received FROM readings WHERE source=?", (source_id,)).fetchone()
                if row is None:
                    return served({**result([]), "pending": True, "updatedAt": None, "stale": False})
                value = statistics_payload(json.loads(row[0]))
                items = [{"id": o["id"], "title": o["title"], "subtitle": o["site"], "status": "Nieuw", "date": o["firstSeenAt"], "url": o["url"], "priceCents": o["priceCents"], "currency": o["currency"]} for o in value["offers"]]
                return served({**result(items), "updatedAt": row[1], "stale": time.time() - row[1] > 300})
            # The full connection fingerprint prevents reuse after credentials/ACL changes.
            key = hashlib.sha256(json.dumps([source_id, source], sort_keys=True).encode()).hexdigest()
            with lock:
                entry = cache.get(key)
                if entry and time.time() - entry[0] < 30:
                    return served({**entry[1], "updatedAt": entry[0], "stale": False})
            transport = Transport(source)
            try:
                adapter = nextcloud if source["kind"] == "nextcloud-calendar" else ADAPTERS[source["kind"]]
                value = adapter(transport, source)
            finally:
                transport.close()
            stamp = time.time()
            with lock:
                if len(cache) >= 64:
                    cache.clear()
                cache[key] = (stamp, value)
            return served({**value, "updatedAt": stamp, "stale": False})
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, ParseError, ConfigurationError, sqlite3.Error):
            # Do not return a previous account's data or raw transport/parser exceptions.
            return response({"error": "Widgetgegevens zijn niet beschikbaar. Controleer de bron en toegang."}, 503)

    @app.post("/api/widget-ingest/<source_id>")
    def ingest_widget_statistics(source_id):
        """Machine auth only: the browser session never substitutes for this source's token."""
        try:
            source = sources(app).get(source_id)
            supplied = request.headers.get("Authorization", "")
            if not source or source["kind"] != "statistics" or not re.fullmatch(r"Bearer [A-Za-z0-9_-]{32,256}", supplied) or not secrets.compare_digest(supplied[7:], source["ingestToken"]):
                return response({"error": "Aanlevertoegang geweigerd."}, 401)
            value = statistics_payload(request.get_json(silent=True))
            with database() as db:
                db.execute("INSERT INTO readings(source,payload,received) VALUES(?,?,?) ON CONFLICT(source) DO UPDATE SET payload=excluded.payload,received=excluded.received", (source_id, json.dumps(value), time.time()))
            return response({"accepted": True})
        except (ValueError, TypeError, sqlite3.Error):
            return response({"error": "Ongeldige of niet beschikbare statistiekaanlevering."}, 400)
