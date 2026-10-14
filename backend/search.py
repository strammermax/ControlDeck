"""Local cross-module search; no provider requests, credentials or global indexes."""
import json
import sqlite3
from pathlib import Path

from flask import g, jsonify, request, session

from backend.auth import database, filter_configuration
from backend.configuration import load_config
from backend.dashboard_apps import available_apps


def search_items(items, query, limit=50):
    """Match all words, preserve source order, and bound the projected results."""
    if not isinstance(query, str) or len(query) > 200 or any(ord(c) < 32 for c in query):
        raise ValueError("Gebruik een zoekterm van maximaal 200 tekens.")
    words = query.casefold().split()
    if not words:
        return []
    return [item for item in items if all(word in f"{item['title']} {item.get('description', '')}".casefold() for word in words)][:limit]


def setup_search(app, configuration_path, data_dir):
    @app.get("/api/search")
    def global_search():
        try:
            if set(request.args) - {"q"} or len(request.args.getlist("q")) != 1:
                raise ValueError("Geef één zoekterm op.")
            query = request.args.get("q")
            # Validate before reading private sources, including for an empty query.
            search_items([], query)
            if not query.strip():
                return jsonify(results=[], warnings=[])
            config = filter_configuration(load_config(configuration_path), g.account)
            modules = config["modules"]
            items, warnings = [], []
            for module in modules:
                items.append({"id": f"module:{module['id']}", "kind": "module", "title": module["title"], "description": "ControlDeck-onderdeel", "route": module["id"]})
                for page in module.get("pages", []):
                    items.append({"id": f"module:{module['id']}/{page['id']}", "kind": "module", "title": page["title"], "description": module["title"], "route": f"{module['id']}/{page['id']}"})
            if any(module["id"] == "dashboard" for module in modules):
                try:
                    with database(Path(data_dir) / "users.sqlite3") as db:
                        rows = db.execute("SELECT id, document FROM dashboards WHERE owner=? ORDER BY rowid", (session["identity"]["sub"],)).fetchall()
                    for bid, document in rows:
                        document = json.loads(document)
                        if not isinstance(document, dict):
                            raise ValueError("Invalid dashboard document")
                        title = document.get("title")
                        if not isinstance(title, str) or not 0 < len(title) <= 100:
                            raise ValueError("Invalid dashboard title")
                        items.append({"id": f"dashboard:{bid}", "kind": "dashboard", "title": title, "description": "Persoonlijk dashboard", "route": "dashboard", "dashboardId": bid})
                except (ValueError, sqlite3.Error):
                    warnings.append("Persoonlijke dashboards zijn tijdelijk niet volledig doorzoekbaar.")
            try:
                source = available_apps(configuration_path, data_dir, g.account)
                for link in source["apps"]:
                    items.append({"id": f"app:{link['id']}", "kind": "app", "title": link["name"], "description": " · ".join(filter(None, [link["collection"], link["description"]])), "url": link["url"]})
                if source["warning"]:
                    warnings.append(source["warning"])
            except (OSError, ValueError):
                warnings.append("App-links zijn tijdelijk niet doorzoekbaar.")
            return jsonify(results=search_items(items, query), warnings=warnings)
        except ValueError as error:
            return jsonify(error=str(error)), 400
