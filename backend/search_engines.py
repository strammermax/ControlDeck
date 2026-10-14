"""Personal external search shortcuts. URLs are generated only in the browser after selection."""
import json
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from flask import jsonify, request, session

from backend.auth import database
from backend.homepage import validate_homepage_link


def validate_search_engine(value):
    if not isinstance(value, dict) or set(value) != {"name", "urlTemplate"}:
        raise ValueError("Vul een naam en zoekadres in.")
    name, template = value["name"], value["urlTemplate"]
    if not isinstance(name, str) or not name.strip() or len(name) > 80 or any(ord(char) < 32 for char in name):
        raise ValueError("Gebruik een naam van 1 tot 80 tekens.")
    if not isinstance(template, str) or len(template) > 2048 or template.count("%s") != 1 or any(char.isspace() or char == "\\" for char in template):
        raise ValueError("Gebruik een HTTP(S)-zoekadres met precies één %s voor de zoekterm.")
    if "%s" in urlsplit(template).netloc:
        raise ValueError("De zoekterm moet in het pad, de query of het fragment staan.")
    validate_homepage_link({"name": name, "url": template.replace("%s", "query"), "collection": "Search"})
    return {"name": name.strip(), "urlTemplate": template}


def setup_search_engines(app, data_dir):
    path = Path(data_dir) / "users.sqlite3"

    @app.route("/api/search-engines", methods=["GET", "POST"])
    @app.route("/api/search-engines/<engine_id>", methods=["PUT", "DELETE"])
    def personal_search_engines(engine_id=None):
        try:
            owner = session["identity"]["sub"]
            with database(path) as db:
                db.execute("BEGIN IMMEDIATE")
                if request.method in ("GET", "HEAD"):
                    rows = db.execute("SELECT id,revision,document FROM search_engines WHERE owner=? ORDER BY rowid", (owner,)).fetchall()
                    return jsonify(engines=[{"id": row[0], "revision": row[1], **json.loads(row[2])} for row in rows])
                body = request.get_json(silent=True)
                if not isinstance(body, dict):
                    raise ValueError("Verwacht een JSON-object.")
                if request.method == "POST":
                    if db.execute("SELECT COUNT(*) FROM search_engines WHERE owner=?", (owner,)).fetchone()[0] >= 10:
                        raise ValueError("Maximaal 10 zoekmachines per gebruiker.")
                    document = validate_search_engine(body)
                    engine_id = uuid.uuid4().hex
                    db.execute("INSERT INTO search_engines VALUES (?,?,1,?)", (engine_id, owner, json.dumps(document)))
                    return jsonify(engine={"id": engine_id, "revision": 1, **document}), 201
                row = db.execute("SELECT revision FROM search_engines WHERE id=? AND owner=?", (engine_id, owner)).fetchone()
                if row is None:
                    return jsonify(error="Zoekmachine niet gevonden."), 404
                if type(body.get("revision")) is not int or body["revision"] != row[0]:
                    return jsonify(error="Deze zoekmachine is elders gewijzigd. Herlaad de lijst."), 409
                if request.method == "DELETE":
                    if set(body) != {"revision"}:
                        raise ValueError("Ongeldige verwijderaanvraag.")
                    db.execute("DELETE FROM search_engines WHERE id=?", (engine_id,))
                    return jsonify(deleted=True)
                document = validate_search_engine({key: value for key, value in body.items() if key != "revision"})
                db.execute("UPDATE search_engines SET revision=revision+1,document=? WHERE id=?", (json.dumps(document), engine_id))
                return jsonify(engine={"id": engine_id, "revision": row[0] + 1, **document})
        except ValueError as error:
            return jsonify(error=str(error)), 400
