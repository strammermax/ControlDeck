"""Personal page layouts (position and size of tiles) in local SQLite; layout only, never content."""

import json
import re
from pathlib import Path

from flask import g, jsonify, request, session
from werkzeug.exceptions import RequestEntityTooLarge

from backend.auth import database, filter_configuration
from backend.configuration import load_config

# Page id -> module the account needs. The frontend keeps the same list (lib/page-layouts.ts).
PAGES = {"bookmarks": "bookmarks", "proxmox": "proxmox", "media": "media"}
COLUMNS = 12
MAX_HEIGHT = 12
MAX_ROWS = 300
MAX_CELLS = 500
MAX_BODY = 128 * 1024
CELL_ID = re.compile(r"[A-Za-z0-9:_.-]{1,100}")


def validate_layout(value):
    """Validate a complete layout: bounded integer cells, unique ids per group, no overlap within a group."""
    if not isinstance(value, dict) or set(value) != {"cells"} or not isinstance(value["cells"], list):
        raise ValueError("Ongeldige indeling.")
    if len(value["cells"]) > MAX_CELLS:
        raise ValueError(f"Maximaal {MAX_CELLS} tegels per pagina.")
    result, by_group = [], {}
    for cell in value["cells"]:
        if not isinstance(cell, dict) or set(cell) != {"id", "group", "x", "y", "width", "height"}:
            raise ValueError("Ongeldige tegel in de indeling.")
        group, cid = cell["group"], cell["id"]
        if not isinstance(cid, str) or not CELL_ID.fullmatch(cid):
            raise ValueError("Ongeldige tegel-ID.")
        if not isinstance(group, str) or not 1 <= len(group) <= 100 or any(ord(c) < 32 for c in group):
            raise ValueError("Ongeldige groepsnaam.")
        x, y, width, height = (cell[key] for key in ("x", "y", "width", "height"))
        if not all(type(n) is int for n in (x, y, width, height)) or x < 0 or y < 0 or width < 1 or height < 1 \
                or height > MAX_HEIGHT or x + width > COLUMNS or y + height > MAX_ROWS:
            raise ValueError("De tegel past niet binnen het raster.")
        siblings = by_group.setdefault(group, [])
        for other in siblings:
            if other["id"] == cid:
                raise ValueError("Tegel-ID is dubbel.")
            if x < other["x"] + other["width"] and x + width > other["x"] and y < other["y"] + other["height"] and y + height > other["y"]:
                raise ValueError("Tegels overlappen elkaar.")
        clean = {"id": cid, "group": group, "x": x, "y": y, "width": width, "height": height}
        siblings.append(clean)
        result.append(clean)
    return {"cells": result}


def setup_page_layouts(app, configuration_path, data_dir):
    db_path = Path(data_dir) / "users.sqlite3"
    with database(db_path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS page_layouts (subject TEXT NOT NULL, page TEXT NOT NULL, layout TEXT NOT NULL, PRIMARY KEY(subject, page))")

    @app.route("/api/layouts/<page>", methods=["GET", "PUT", "DELETE"])
    def page_layout(page):
        if page not in PAGES:
            return jsonify(error="Onbekende pagina."), 404
        if not any(m["id"] == PAGES[page] for m in filter_configuration(load_config(configuration_path), g.account)["modules"]):
            return jsonify(error="Geen toegang tot deze pagina."), 403
        subject = session["identity"]["sub"]
        with database(db_path) as db:
            if request.method == "GET":
                row = db.execute("SELECT layout FROM page_layouts WHERE subject=? AND page=?", (subject, page)).fetchone()
                return jsonify(cells=json.loads(row[0])["cells"] if row else [])
            if request.method == "DELETE":
                db.execute("DELETE FROM page_layouts WHERE subject=? AND page=?", (subject, page))
                return jsonify(cells=[])
            if (request.content_length or 0) > MAX_BODY:
                return jsonify(error="Indeling is te groot."), 413
            try:
                layout = validate_layout(request.get_json(silent=True))
            except RequestEntityTooLarge:
                return jsonify(error="Indeling is te groot."), 413
            except ValueError as failure:
                return jsonify(error=str(failure)), 400
            db.execute("INSERT INTO page_layouts(subject,page,layout) VALUES(?,?,?) ON CONFLICT(subject,page) DO UPDATE SET layout=excluded.layout",
                       (subject, page, json.dumps(layout)))
            return jsonify(layout)
