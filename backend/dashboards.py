"""Personal, revisioned dashboards; no provider credentials or network access."""

import json
import re
import sqlite3
import uuid
from pathlib import Path

from flask import g, jsonify, request, session
from werkzeug.exceptions import RequestEntityTooLarge

from backend.app_icons import validate_icon
from backend.dashboard_modules import validate_module, validate_module_access
from backend.auth import database, filter_configuration
from backend.configuration import load_config
from backend.homepage import validate_homepage_link
from backend.dashboard_apps import available_apps, validate_app_references

MAX_DASHBOARDS = 20
MAX_ITEMS = 100
MAX_SECTIONS = 20
MAX_BODY = 256 * 1024
LANES = ("left", "main", "right")



def validate_dashboard(value):
    """Validate the complete document, including references and grid collisions."""
    if not isinstance(value, dict) or set(value) != {"title", "sections", "items"}:
        raise ValueError("Ongeldig dashboard.")
    title = value["title"]
    if not isinstance(title, str) or not title.strip() or len(title) > 100 or any(ord(c) < 32 for c in title):
        raise ValueError("Gebruik een dashboardnaam van 1 tot 100 tekens.")
    sections, items = value["sections"], value["items"]
    if not isinstance(sections, list) or not 1 <= len(sections) <= MAX_SECTIONS:
        raise ValueError("Gebruik 1 tot 20 groepen.")
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise ValueError("Maximaal 100 tegels per dashboard.")
    ids, result_sections = set(), []
    for section in sections:
        if not isinstance(section, dict) or set(section) != {"id", "title", "lane", "collapsed"}:
            raise ValueError("Ongeldige groep.")
        sid = section["id"]
        if not isinstance(sid, str) or not re.fullmatch(r"[a-zA-Z0-9-]{1,64}", sid) or sid in ids:
            raise ValueError("Groep-ID ontbreekt of is dubbel.")
        label = section["title"]
        if not isinstance(label, str) or not label.strip() or len(label) > 100 or any(ord(c) < 32 for c in label):
            raise ValueError("Gebruik een groepsnaam van 1 tot 100 tekens.")
        if section["lane"] not in LANES or type(section["collapsed"]) is not bool:
            raise ValueError("Ongeldige groepsindeling.")
        ids.add(sid)
        result_sections.append({**section, "title": label.strip()})
    item_ids, occupied, result_items = set(), set(), []
    for item in items:
        common = {"id", "sectionId", "type", "x", "y", "width", "height"}
        if not isinstance(item, dict) or item.get("type") not in ("link", "app", "module"):
            raise ValueError("Onbekend tegeltype of ongeldige tegel.")
        required = common | ({"moduleId", "settings"} if item["type"] == "module" else {"appId"} if item["type"] == "app" else {"title", "url", "description"})
        if set(item) - {"icon"} != required:
            raise ValueError("Ongeldige tegelvelden.")
        if "icon" in item:
            validate_icon(item["icon"])
        iid = item["id"]
        if not isinstance(iid, str) or not re.fullmatch(r"[a-zA-Z0-9-]{1,64}", iid) or iid in item_ids:
            raise ValueError("Tegel-ID ontbreekt of is dubbel.")
        if not isinstance(item["sectionId"], str) or item["sectionId"] not in ids:
            raise ValueError("De groep van deze tegel bestaat niet.")
        if any(type(item[key]) is not int for key in ("x", "y", "width", "height")):
            raise ValueError("Tegelposities moeten gehele getallen zijn.")
        x, y, width, height = (item[key] for key in ("x", "y", "width", "height"))
        if not (0 <= x < 12 and 0 <= y < 100 and 1 <= width <= 12 and 1 <= height <= 6 and x + width <= 12 and y + height <= 100):
            raise ValueError("Tegel valt buiten het raster (12 kolommen, 100 rijen).")
        cells = {(item["sectionId"], col, row) for col in range(x, x + width) for row in range(y, y + height)}
        if occupied & cells:
            raise ValueError("Tegels mogen elkaar niet overlappen.")
        if item["type"] == "module":
            result_items.append(validate_module(item))
        elif item["type"] == "app":
            if type(item["appId"]) is not int or item["appId"] < 1:
                raise ValueError("Ongeldige appverwijzing.")
            result_items.append(dict(item))
        else:
            url = item["url"]
            if not isinstance(url, str) or any(c.isspace() or ord(c) < 32 or c == "\\" for c in url):
                raise ValueError("Gebruik een geldig HTTP- of HTTPS-adres.")
            link = validate_homepage_link({"name": item["title"], "url": url, "description": item["description"], "collection": "Dashboard"})
            result_items.append({**item, "title": link["name"], "url": link["url"], "description": link["description"]})
        occupied.update(cells)
        item_ids.add(iid)
    return {"title": title.strip(), "sections": result_sections, "items": result_items}


def migrate_dashboards(path):
    """Back up SQLite before atomically installing or upgrading personal-state schemas."""
    with database(path) as db:
        db.execute("BEGIN IMMEDIATE")
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='dashboard_schema'").fetchone()
        version = 0
        if exists:
            versions = db.execute("SELECT version FROM dashboard_schema").fetchall()
            if versions not in ([(1,)], [(2,)], [(3,)]):
                raise ValueError("Onbekende dashboardschemaversie; start geweigerd.")
            version = versions[0][0]
            if version == 3:
                return
        # A separate reader snapshots the committed pre-migration state. Never back
        # up from the connection holding this write transaction (would wait on itself).
        backup_dir = Path(path).parent / "backups"
        backup_dir.mkdir(mode=0o700, exist_ok=True)
        destination = backup_dir / f"pre-dashboard-v{version + 1}-{uuid.uuid4().hex}.sqlite3"
        destination.touch(mode=0o600, exist_ok=False)
        with sqlite3.connect(path) as source, sqlite3.connect(destination) as target:
            source.backup(target)
        if version == 0:
            db.execute("CREATE TABLE dashboard_schema (version INTEGER NOT NULL)")
            db.execute("INSERT INTO dashboard_schema VALUES (1)")
            db.execute("CREATE TABLE dashboards (id TEXT PRIMARY KEY, owner TEXT NOT NULL, revision INTEGER NOT NULL, document TEXT NOT NULL)")
            db.execute("CREATE INDEX dashboards_owner ON dashboards(owner)")
            db.execute("CREATE TABLE dashboard_preferences (owner TEXT PRIMARY KEY, default_id TEXT)")
        if version < 2:
            db.execute("CREATE TABLE search_engines (id TEXT PRIMARY KEY, owner TEXT NOT NULL, revision INTEGER NOT NULL, document TEXT NOT NULL)")
            db.execute("CREATE INDEX search_engines_owner ON search_engines(owner)")
        # Preserve IDs still referenced by older documents even if their JSON
        # source was deleted before the permanent allocator was introduced.
        identifiers = [0]
        for row in db.execute("SELECT document FROM dashboards"):
            try:
                document = json.loads(row[0])
                if isinstance(document, dict) and isinstance(document.get("items"), list):
                    identifiers.extend(item["appId"] for item in document["items"] if isinstance(item, dict) and item.get("type") == "app" and type(item.get("appId")) is int and item["appId"] > 0)
            except ValueError:
                pass
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='homepage_integrations'").fetchone():
            for row in db.execute("SELECT metadata FROM homepage_integrations"):
                try:
                    record = json.loads(row[0])
                    if isinstance(record, dict) and type(record.get("linkId")) is int and record["linkId"] > 0:
                        identifiers.append(record["linkId"])
                except ValueError:
                    pass
        for filename in ("links.json", "links.previous.json"):
            try:
                links = json.loads((Path(path).parent / "homepage" / filename).read_text(encoding="utf-8"))
                if isinstance(links, list):
                    identifiers.extend(link["id"] for link in links if isinstance(link, dict) and type(link.get("id")) is int and link["id"] > 0)
            except (OSError, ValueError):
                pass
        db.execute("CREATE TABLE homepage_link_sequence (singleton INTEGER PRIMARY KEY CHECK(singleton=1), last_id INTEGER NOT NULL)")
        db.execute("INSERT INTO homepage_link_sequence VALUES (1,?)", (max(identifiers),))
        db.execute("UPDATE dashboard_schema SET version=3")


def setup_dashboards(app, configuration_path, data_dir):
    path = Path(data_dir) / "users.sqlite3"
    migrate_dashboards(path)

    @app.before_request
    def dashboard_access():
        if request.path == "/api/dashboards" or request.path.startswith("/api/dashboards/"):
            # The global authentication/CSRF hook runs before this module hook.
            if g.account is None:
                return jsonify(error="Aanmelden vereist."), 401
            if not any(m["id"] == "dashboard" for m in filter_configuration(load_config(configuration_path), g.account)["modules"]):
                return jsonify(error="Geen toegang tot Dashboard."), 403
            request.max_content_length = MAX_BODY

    def owner():
        return session["identity"]["sub"]

    def payload():
        try:
            body = request.get_json(silent=True)
        except RequestEntityTooLarge:
            raise
        if not isinstance(body, dict):
            raise ValueError("Verwacht een JSON-object.")
        return body

    def project(row):
        return {"id": row[0], "revision": row[1], **json.loads(row[2])}

    def insert(db, title, document=None):
        if db.execute("SELECT COUNT(*) FROM dashboards WHERE owner=?", (owner(),)).fetchone()[0] >= MAX_DASHBOARDS:
            raise ValueError("Maximaal 20 dashboards per gebruiker.")
        document = validate_dashboard({**(document or {"sections": [{"id": "apps", "title": "Toepassingen", "lane": "main", "collapsed": False}], "items": []}), "title": title})
        # Duplication preserves references, never copies source metadata or grants access.
        bid = uuid.uuid4().hex
        db.execute("INSERT INTO dashboards VALUES (?, ?, 1, ?)", (bid, owner(), json.dumps(document)))
        return {"id": bid, "revision": 1, **document}

    @app.route("/api/dashboards", methods=["GET", "POST"])
    def dashboard_list():
        try:
            with database(path) as db:
                db.execute("BEGIN IMMEDIATE")
                if not db.execute("SELECT 1 FROM dashboard_preferences WHERE owner=?", (owner(),)).fetchone():
                    first = insert(db, "Werk")
                    insert(db, "Homelab")
                    db.execute("INSERT INTO dashboard_preferences VALUES (?, ?)", (owner(), first["id"]))
                if request.method == "POST":
                    body = payload()
                    if set(body) - {"title", "sourceId"} or "title" not in body:
                        raise ValueError("Vul een dashboardnaam in.")
                    original = None
                    if "sourceId" in body:
                        if not isinstance(body["sourceId"], str):
                            raise ValueError("Ongeldig brondashboard.")
                        row = db.execute("SELECT document FROM dashboards WHERE id=? AND owner=?", (body["sourceId"], owner())).fetchone()
                        if row is None:
                            return jsonify(error="Dashboard niet gevonden."), 404
                        original = json.loads(row[0])
                    return jsonify(dashboard=insert(db, body["title"], original)), 201
                rows = db.execute("SELECT id, revision, document FROM dashboards WHERE owner=? ORDER BY rowid", (owner(),)).fetchall()
                default = db.execute("SELECT default_id FROM dashboard_preferences WHERE owner=?", (owner(),)).fetchone()[0]
                return jsonify(dashboards=[project(row) for row in rows], defaultId=default)
        except ValueError as error:
            return jsonify(error=str(error)), 400

    @app.put("/api/dashboards/default")
    def dashboard_default():
        try:
            body = payload()
            if set(body) != {"id"} or not isinstance(body["id"], str):
                raise ValueError("Ongeldige dashboardkeuze.")
            with database(path) as db:
                db.execute("BEGIN IMMEDIATE")
                if not db.execute("SELECT 1 FROM dashboards WHERE id=? AND owner=?", (body["id"], owner())).fetchone():
                    return jsonify(error="Dashboard niet gevonden."), 404
                db.execute("INSERT INTO dashboard_preferences VALUES (?, ?) ON CONFLICT(owner) DO UPDATE SET default_id=excluded.default_id", (owner(), body["id"]))
            return jsonify(defaultId=body["id"])
        except ValueError as error:
            return jsonify(error=str(error)), 400

    @app.route("/api/dashboards/<bid>", methods=["GET", "PUT", "DELETE"])
    def dashboard_record(bid):
        try:
            with database(path) as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT id, revision, document FROM dashboards WHERE id=? AND owner=?", (bid, owner())).fetchone()
                if row is None:
                    return jsonify(error="Dashboard niet gevonden."), 404
                if request.method in ("GET", "HEAD"):
                    return jsonify(dashboard=project(row))
                body = payload()
                if type(body.get("revision")) is not int or body["revision"] != row[1]:
                    return jsonify(error="Dit dashboard is elders gewijzigd. Herlaad de opgeslagen versie; je bewerking blijft staan.", code="revision_conflict"), 409
                if request.method == "DELETE":
                    if set(body) != {"revision"}:
                        raise ValueError("Ongeldige verwijderaanvraag.")
                    db.execute("DELETE FROM dashboards WHERE id=?", (bid,))
                    next_row = db.execute("SELECT id FROM dashboards WHERE owner=? ORDER BY rowid LIMIT 1", (owner(),)).fetchone()
                    db.execute("UPDATE dashboard_preferences SET default_id=? WHERE owner=? AND default_id=?", (next_row[0] if next_row else None, owner(), bid))
                    return jsonify(deleted=True)
                document = validate_dashboard({key: value for key, value in body.items() if key != "revision"})
                validate_module_access(document, json.loads(row[2]), {module["id"] for module in filter_configuration(load_config(configuration_path), g.account)["modules"]})
                if any(item["type"] == "app" for item in document["items"]):
                    previous = json.loads(row[2])
                    added = any(item["type"] == "app" and not any(old["id"] == item["id"] and old.get("appId") == item["appId"] for old in previous["items"]) for item in document["items"])
                    # Unrelated edits remain possible during source failure/revocation.
                    try:
                        apps = available_apps(configuration_path, data_dir, g.account)["apps"] if added else []
                    except (OSError, ValueError):
                        return jsonify(error="De app-bron is tijdelijk niet beschikbaar. Je bewerking is niet opgeslagen."), 503
                    validate_app_references(document, apps, previous)
                db.execute("UPDATE dashboards SET revision=revision+1, document=? WHERE id=?", (json.dumps(document), bid))
                return jsonify(dashboard={"id": bid, "revision": row[1] + 1, **document})
        except ValueError as error:
            return jsonify(error=str(error)), 400

    @app.get("/api/dashboards/apps")
    def dashboard_app_sources():
        try:
            return jsonify(available_apps(configuration_path, data_dir, g.account))
        except (OSError, ValueError):
            return jsonify(error="De app-lijst kan niet worden geladen. Probeer later opnieuw."), 503
