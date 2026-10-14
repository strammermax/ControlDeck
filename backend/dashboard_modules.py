"""Dashboard module catalog: references to existing features, never copied credentials."""
MODULES = {"linkwarden": {"title": "Linkwarden", "permission": "bookmarks"}}


def validate_module(item):
    if not isinstance(item.get("moduleId"), str) or item["moduleId"] not in MODULES:
        raise ValueError("Onbekende dashboardmodule.")
    settings = item.get("settings")
    if not isinstance(settings, dict) or set(settings) != {"collectionId"}:
        raise ValueError("Ongeldige module-instellingen.")
    collection = settings["collectionId"]
    if collection is not None and (type(collection) is not int or not 1 <= collection <= 9999999999):
        raise ValueError("Kies een geldige Linkwarden-collectie.")
    return dict(item)


def validate_module_access(document, previous, allowed_modules):
    """Existing inaccessible modules can be moved/removed; new references require access."""
    for item in document["items"]:
        if item["type"] != "module":
            continue
        unchanged_source = any(old["id"] == item["id"] and old.get("type") == "module" and old.get("moduleId") == item["moduleId"] and old.get("settings") == item["settings"] for old in previous["items"])
        if not unchanged_source and MODULES[item["moduleId"]]["permission"] not in allowed_modules:
            raise ValueError("Geen toegang tot deze module.")
