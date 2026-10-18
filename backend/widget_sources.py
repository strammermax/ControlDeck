"""Vault configuration and per-source authorization shared by all service widgets."""
import json
import re
from urllib.parse import urlsplit
from backend.auth import filter_configuration
from backend.configuration import load_config
from backend.vault import VaultError
from backend.widgets.transport import ProviderError, provider_url

FAMILIES = {
    "downloads": {"permission": "media", "kinds": ("qbittorrent", "sabnzbd"), "title": "Downloads"},
    "media-widget": {"permission": "media", "kinds": ("plex", "seerr"), "title": "Media"},
    "tdarr": {"permission": "media", "kinds": ("tdarr",), "title": "Tdarr"},
    "homeassistant-dashboard": {"permission": "monitoring", "kinds": ("homeassistant-dashboard",), "title": "Home Assistant"},
    "calendar": {"permission": "files", "kinds": ("nextcloud-calendar",), "title": "Agenda"},
    "statistics": {"permission": "monitoring", "kinds": ("prefect", "statistics"), "title": "Statistieken"},
}


def validate_sources(value):
    if not isinstance(value, dict) or len(value) > 64:
        raise ProviderError("Ongeldige widgetconfiguratie.")
    for identifier, source in value.items():
        if not re.fullmatch(r"[a-z0-9-]{1,64}", identifier) or not isinstance(source, dict):
            raise ProviderError("Ongeldige widgetbron.")
        family = source.get("family")
        if not isinstance(family, str) or family not in FAMILIES or source.get("kind") not in FAMILIES[family]["kinds"]:
            raise ProviderError("Onbekende widgetbron.")
        if not isinstance(source.get("title"), str) or not 1 <= len(source["title"]) <= 100:
            raise ProviderError("Ongeldige bronnaam.")
        users = source.get("users")
        if not isinstance(users, list) or not 1 <= len(users) <= 200 or any(not isinstance(u, str) or not re.fullmatch(r"[^\s@]+@[^\s@]+", u) or len(u) > 254 for u in users):
            raise ProviderError("Widgetbronnen vereisen expliciete accounts.")
        if "caBundle" in source and (not isinstance(source["caBundle"], str) or not 1 <= len(source["caBundle"]) <= 512):
            raise ProviderError("Ongeldige certificaatinstelling.")
        if "webUrl" in source:
            provider_url(source["webUrl"], source.get("allowHttp") is True)
        if source["kind"] == "statistics":
            token = source.get("ingestToken")
            if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token):
                raise ProviderError("Ongeldige aanlevercredential.")
        else:
            provider_url(source.get("url"), source.get("allowHttp") is True)
        if source["kind"] == "homeassistant-dashboard" and urlsplit(source["url"]).scheme != "https":
            raise ProviderError("Een ingebed dashboard vereist HTTPS.")
        required = {"qbittorrent": ("username", "password"), "sabnzbd": ("apiKey",), "plex": ("apiKey",), "seerr": ("apiKey",), "nextcloud-calendar": ("username", "password")}.get(source["kind"], ())
        if source["kind"] == "qbittorrent" and source.get("apiKey"):
            required = ("apiKey",)
        for name in required:
            if not isinstance(source.get(name), str) or not 1 <= len(source[name]) <= 4096 or any(ord(c) < 32 for c in source[name]):
                raise ProviderError("Toegangsgegevens ontbreken.")
        for name in ("apiKey", "username", "password"):
            if name in source and (not isinstance(source[name], str) or len(source[name]) > 4096 or any(ord(c) < 32 for c in source[name])):
                raise ProviderError("Ongeldige toegangsgegevens.")
    return value


def sources(app):
    vault = app.extensions.get("controldeck_vault")
    if vault is None:
        return {}
    try:
        return validate_sources(json.loads(vault.read().get("CONTROLDECK_WIDGET_SOURCES", "{}")))
    except (ValueError, TypeError, VaultError):
        raise ProviderError("Widgetbronnen zijn niet beschikbaar. Controleer Infisical.") from None


def permitted(source, account, configuration_path):
    if not isinstance(account, dict) or account.get("email", "").casefold() not in {u.casefold() for u in source["users"]}:
        return False
    allowed = {m["id"] for m in filter_configuration(load_config(configuration_path), account)["modules"]}
    return FAMILIES[source["family"]]["permission"] in allowed
