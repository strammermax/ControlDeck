"""Permission-filtered app references. Only safe link fields and stored counts leave the server."""
import json
import sqlite3
from pathlib import Path

from backend.auth import database, filter_configuration
from backend.configuration import load_config
from backend.homepage import read_homepage_links


def available_apps(configuration_path, data_dir, account):
    """Read the current source on every request; revoked access never uses cached metadata."""
    modules = filter_configuration(load_config(configuration_path), account)["modules"]
    if not any(module["id"] == "bookmarks" for module in modules):
        return {"apps": [], "available": False, "warning": None}
    root = Path(data_dir)
    links = read_homepage_links(root / "homepage/links.json")
    apps = [{key: link[key] for key in ("id", "name", "url", "description", "icon", "collection")} | {"summary": []} for link in links]
    by_id = {item["id"]: item for item in apps}
    warning = None
    try:
        with database(root / "users.sqlite3") as db:
            rows = db.execute("SELECT metadata FROM homepage_integrations ORDER BY id").fetchall()
        for row in rows:
            try:
                record = json.loads(row[0])
                if not isinstance(record, dict):
                    raise ValueError("Invalid metadata")
                link_id = record.get("linkId")
                if type(link_id) is not int or link_id not in by_id or record.get("showApp") is not True:
                    continue
                stats = record.get("summary", [])
                if not isinstance(stats, list) or len(stats) > 20:
                    raise ValueError("Invalid summary")
                for stat in stats:
                    if (not isinstance(stat, dict) or set(stat) != {"label", "value"} or
                        not isinstance(stat["label"], str) or not 0 < len(stat["label"]) <= 200 or
                        any(ord(char) < 32 for char in stat["label"]) or
                        type(stat["value"]) is not int or not 0 <= stat["value"] <= 2**53 - 1):
                        raise ValueError("Invalid statistic")
                by_id[link_id]["summary"] = stats
            except (ValueError, TypeError):
                warning = "Een opgeslagen integratiesamenvatting is niet beschikbaar. App-links blijven bruikbaar."
    except sqlite3.Error:
        warning = "Opgeslagen integratiegegevens zijn tijdelijk niet beschikbaar. App-links blijven bruikbaar."
    return {"apps": apps, "available": True, "warning": warning}


def validate_app_references(document, apps, previous=None):
    """Only newly selected sources need current access; unavailable existing references can be removed or moved."""
    allowed = {app["id"] for app in apps}
    existing = {item["id"]: item.get("appId") for item in (previous or {}).get("items", []) if item.get("type") == "app"}
    for item in document["items"]:
        if item["type"] == "app" and item["appId"] not in allowed and existing.get(item["id"]) != item["appId"]:
            raise ValueError("Deze app is niet beschikbaar of je hebt er geen toegang toe. Kies een andere app.")
    return document
