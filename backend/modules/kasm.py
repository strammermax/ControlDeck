"""Kasm's supported get_login API; API credentials stay on the server."""
import re
import uuid
from urllib.parse import urlsplit
import requests
from backend.modules.launch_urls import secure_origin, empty_settings

validate_settings = empty_settings


def launch_login(config, account):
    if not isinstance(config, dict) or set(config) != {"url", "apiKey", "apiSecret", "users"}:
        raise ValueError("Kasm-aanmelding is nog niet ingericht.")
    origin = secure_origin(config["url"])
    if any(not isinstance(config[key], str) or not config[key] or len(config[key]) > 4096 for key in ("apiKey", "apiSecret")) or not isinstance(config["users"], dict):
        raise ValueError("Ongeldige Kasm-inrichting.")
    user_id = config["users"].get(account["email"])
    if not isinstance(user_id, str):
        raise PermissionError("Geen Kasm-account gekoppeld aan dit profiel.")
    try:
        uuid.UUID(user_id)
    except ValueError:
        raise ValueError("Ongeldige Kasm-profielkoppeling.") from None
    response = requests.post(origin + "/api/public/get_login", json={"api_key": config["apiKey"], "api_key_secret": config["apiSecret"], "target_user": {"user_id": user_id}}, timeout=10, allow_redirects=False)
    if response.status_code != 200:
        raise ValueError("Kasm heeft de aanmelding geweigerd.")
    result = response.json()
    if not isinstance(result, dict) or result.get("error_message") or not isinstance(result.get("url"), str):
        raise ValueError("Kasm heeft geen geldige aanmeldlink geleverd.")
    url = result["url"]
    parsed, expected = urlsplit(url), urlsplit(origin)
    if len(url) > 4096 or any(c.isspace() or c == "\\" for c in url) or (parsed.scheme, parsed.netloc) != (expected.scheme, expected.netloc) or parsed.path not in ("", "/") or parsed.query or not re.fullmatch(r"/connect/login/dash/[a-zA-Z0-9_-]{1,128}/[a-zA-Z0-9_-]{1,512}", parsed.fragment):
        raise ValueError("Kasm heeft een ongeldige aanmeldlink geleverd.")
    return url
