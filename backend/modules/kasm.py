"""Kasm's supported Developer API; API credentials stay on the server.

The public `url` is what the browser opens. When it sits behind a login proxy (e.g. Cloudflare Access),
`apiUrl` points the server at Kasm's internal address, optionally with a pinned certificate
(`apiFingerprint`, SHA-256) for Kasm's default self-signed certificate."""
import re
import uuid
from urllib.parse import urlsplit
import requests
from backend.modules.launch_urls import secure_origin, empty_settings
from backend.proxmox import PinnedAdapter, validate_fingerprint

validate_settings = empty_settings
REQUIRED = {"url", "apiKey", "apiSecret", "users"}
OPTIONAL = {"apiUrl", "apiFingerprint"}


def kasm_config(config):
    """Validated settings: public origin, API origin, optional pin, credentials and user links."""
    if not isinstance(config, dict) or not REQUIRED <= set(config) <= REQUIRED | OPTIONAL:
        raise ValueError("Kasm-aanmelding is nog niet ingericht.")
    origin = secure_origin(config["url"])
    api = secure_origin(config.get("apiUrl") or config["url"])
    fingerprint = validate_fingerprint(config.get("apiFingerprint"))
    if any(not isinstance(config[key], str) or not config[key] or len(config[key]) > 4096 for key in ("apiKey", "apiSecret")) or not isinstance(config["users"], dict):
        raise ValueError("Ongeldige Kasm-inrichting.")
    return {"origin": origin, "api": api, "fingerprint": fingerprint, "users": config["users"],
            "auth": {"api_key": config["apiKey"], "api_key_secret": config["apiSecret"]}}


def kasm_post(settings, endpoint, timeout=(5, 30), **body):
    """POST to /api/public/<endpoint>; with a pin, urllib3 rejects any other certificate before sending the key."""
    url = f"{settings['api']}/api/public/{endpoint}"
    payload = {**settings["auth"], **body}
    if not settings["fingerprint"]:
        return requests.post(url, json=payload, timeout=timeout, allow_redirects=False)
    with requests.Session() as session:
        session.mount(settings["api"], PinnedAdapter(settings["fingerprint"]))
        return session.post(url, json=payload, timeout=timeout, allow_redirects=False, verify=False)


def linked_user(settings, account):
    user_id = settings["users"].get(account["email"])
    if not isinstance(user_id, str):
        raise PermissionError("Geen Kasm-account gekoppeld aan dit profiel.")
    try:
        uuid.UUID(user_id)
    except ValueError:
        raise ValueError("Ongeldige Kasm-profielkoppeling.") from None
    return user_id


def launch_login(config, account):
    settings = kasm_config(config)
    user_id = linked_user(settings, account)
    response = kasm_post(settings, "get_login", timeout=10, target_user={"user_id": user_id})
    if response.status_code != 200:
        raise ValueError("Kasm heeft de aanmelding geweigerd.")
    result = response.json()
    if not isinstance(result, dict) or result.get("error_message") or not isinstance(result.get("url"), str):
        raise ValueError("Kasm heeft geen geldige aanmeldlink geleverd.")
    url = result["url"]
    origin = settings["origin"]
    if url.startswith("/"):
        url = origin + url  # Kasm builds links from its own address; the browser uses the public one.
    parsed, expected = urlsplit(url), urlsplit(origin)
    if (parsed.scheme, parsed.netloc) != (expected.scheme, expected.netloc) and settings["api"] != origin and (parsed.scheme, parsed.netloc) == urlsplit(settings["api"])[:2]:
        url = origin + url[len(settings["api"]):]
        parsed = urlsplit(url)
    if len(url) > 4096 or any(c.isspace() or c == "\\" for c in url) or (parsed.scheme, parsed.netloc) != (expected.scheme, expected.netloc) or parsed.path not in ("", "/") or parsed.query or not re.fullmatch(r"/connect/login/dash/[a-zA-Z0-9_-]{1,128}/[a-zA-Z0-9_-]{1,512}", parsed.fragment):
        raise ValueError("Kasm heeft een ongeldige aanmeldlink geleverd.")
    return url
