"""Dashboard module catalog: references to existing features, never copied credentials."""
from backend.modules.launch_urls import empty_settings
from backend.modules.linkwarden import validate_settings as validate_linkwarden

MODULES = {"linkwarden": {"title": "Linkwarden", "permission": "bookmarks", "validate": validate_linkwarden}, "kasm": {"title": "Kasm", "permission": "kasm", "validate": empty_settings}, "nextcloud": {"title": "Nextcloud", "permission": "nextcloud", "validate": empty_settings}}


def validate_module(item):
    if not isinstance(item.get("moduleId"), str) or item["moduleId"] not in MODULES:
        raise ValueError("Onbekende dashboardmodule.")
    MODULES[item["moduleId"]]["validate"](item.get("settings"))
    return dict(item)


def validate_module_access(document, previous, allowed_modules):
    """Existing inaccessible modules can be moved/removed; new references require access."""
    for item in document["items"]:
        if item["type"] != "module":
            continue
        unchanged_source = any(old["id"] == item["id"] and old.get("type") == "module" and old.get("moduleId") == item["moduleId"] and old.get("settings") == item["settings"] for old in previous["items"])
        if not unchanged_source and MODULES[item["moduleId"]]["permission"] not in allowed_modules:
            raise ValueError("Geen toegang tot deze module.")
