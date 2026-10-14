"""Authenticated module launch broker. Only trusted vault configuration defines targets."""
import json
import requests
from flask import g, jsonify, request
from backend.auth import filter_configuration
from backend.configuration import load_config, ConfigurationError
from backend.modules import kasm, nextcloud
from backend.vault import VaultError

LAUNCHERS = {"kasm": kasm.launch_login, "nextcloud": nextcloud.launch_login}


def setup_app_launches(app, configuration_path):
    @app.post("/api/app-launches/<module_id>")
    def launch_app(module_id):
        if module_id not in LAUNCHERS:
            return jsonify(error="Onbekende aanmeldmodule."), 404
        try:
            allowed = {module["id"] for module in filter_configuration(load_config(configuration_path), g.account)["modules"]}
        except ConfigurationError:
            return jsonify(error="De moduleconfiguratie is niet beschikbaar."), 503
        if module_id not in allowed:
            return jsonify(error="Geen toegang tot deze module."), 403
        if request.get_json(silent=True) != {}:
            return jsonify(error="Deze aanmelding accepteert geen account of doeladres uit de browser."), 400
        vault = app.extensions.get("controldeck_vault")
        if vault is None:
            return jsonify(error="Automatisch aanmelden is nog niet via de keyvault ingericht."), 503
        try:
            settings = json.loads(vault.read().get("CONTROLDECK_APP_LAUNCHES", "{}"))
            if not isinstance(settings, dict):
                raise ValueError()
            target = LAUNCHERS[module_id](settings.get(module_id), g.account)
            result = jsonify(url=target)
            result.headers["Cache-Control"] = "no-store"
            result.headers["Referrer-Policy"] = "no-referrer"
            return result
        except PermissionError:
            return jsonify(error="Er is geen dienstaccount gekoppeld aan dit profiel."), 403
        except (ValueError, TypeError, requests.RequestException, VaultError):
            return jsonify(error="Automatisch aanmelden is niet beschikbaar. Controleer de module-inrichting en koppeling."), 503
