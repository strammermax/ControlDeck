"""Open the configured Google/OIDC login on Nextcloud; no password forwarding."""
import re
from backend.modules.launch_urls import secure_origin, empty_settings

validate_settings = empty_settings


def launch_login(config, account):
    if not isinstance(config, dict) or set(config) != {"url", "loginPath"}:
        raise ValueError("Nextcloud-aanmelding is nog niet ingericht.")
    origin = secure_origin(config["url"])
    path = config["loginPath"]
    if not isinstance(path, str) or not re.fullmatch(r"/(?:index\.php/)?apps/user_oidc/login/[1-9][0-9]{0,9}", path):
        raise ValueError("Stel de bestaande Google/OIDC-aanmeldroute van Nextcloud in.")
    return origin + path
