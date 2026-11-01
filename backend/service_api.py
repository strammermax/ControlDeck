"""Server-to-server reads for ControlDeckv2 (Homarr Custom Widgets): an API key, never a browser session.

Custom Widgets run their requests on the Homarr server without the viewer's identity, so these
endpoints only return what is the same for everyone (for example which Kasm workspaces exist).
Anything done on behalf of a person stays behind the normal session login.
"""
import hmac

from flask import current_app, jsonify, request

from backend.vault import VaultError

HEADER = "X-ControlDeck-Api-Key"
PREFIX = "/api/service/"
MIN_KEY_LENGTH = 32


def service_key_valid():
    """True when the request carries CONTROLDECK_SERVICE_API_KEY from the keyvault."""
    vault = current_app.extensions.get("controldeck_vault")
    if vault is None:
        return False
    try:
        expected = vault.read().get("CONTROLDECK_SERVICE_API_KEY", "")
    except VaultError:
        return False
    supplied = request.headers.get(HEADER, "")
    return len(expected) >= MIN_KEY_LENGTH and hmac.compare_digest(expected.encode(), supplied.encode())


def setup_service_api(app):
    @app.before_request
    def service_api_key():
        if not request.path.startswith(PREFIX):
            return None
        if request.method not in ("GET", "HEAD"):
            return jsonify(error="Alleen lezen."), 405
        if not service_key_valid():
            return jsonify(error="Geldige servicesleutel vereist."), 401
        return None
