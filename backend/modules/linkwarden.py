"""Linkwarden module configuration; provider access stays in backend.linkwarden."""

def validate_settings(settings):
    if not isinstance(settings, dict) or set(settings) != {"collectionId"}:
        raise ValueError("Ongeldige module-instellingen.")
    collection = settings["collectionId"]
    if collection is not None and (type(collection) is not int or not 1 <= collection <= 9999999999):
        raise ValueError("Kies een geldige Linkwarden-collectie.")
