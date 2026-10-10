"""Optional Infisical keyvault for ControlDeck settings and the account list.

Only the Infisical bootstrap (address, machine identity, project, environment,
path) lives on the server. Everything else, including CONTROLDECK_ACCOUNTS, is
read from the vault at startup. Values are never logged.
"""

import os
import urllib.parse

import requests


class VaultError(Exception):
    """Message is safe to show; it never contains secrets or response bodies."""


class Vault:
    def __init__(self, address, client_id, client_secret, project_id, environment="prod", path="/apps/controldeck", ca_bundle=None, timeout=10):
        self.address = address.rstrip("/")
        self.client_id, self.client_secret = client_id, client_secret
        self.project_id, self.environment, self.path = project_id, environment, path
        self.verify = ca_bundle or True
        self.timeout = timeout
        self._token = None

    @classmethod
    def from_env(cls):
        required = ("INFISICAL_ADDR", "INFISICAL_CLIENT_ID", "INFISICAL_CLIENT_SECRET", "INFISICAL_PROJECT_ID")
        if not all(os.environ.get(name) for name in required):
            return None
        address = os.environ["INFISICAL_ADDR"]
        if not address.startswith("https://") and os.environ.get("INFISICAL_ALLOW_HTTP", "").lower() != "true":
            raise VaultError("INFISICAL_ADDR moet https gebruiken (of zet INFISICAL_ALLOW_HTTP=true)")
        return cls(address, os.environ["INFISICAL_CLIENT_ID"], os.environ["INFISICAL_CLIENT_SECRET"], os.environ["INFISICAL_PROJECT_ID"],
                   os.environ.get("INFISICAL_ENVIRONMENT", "prod"), os.environ.get("CONTROLDECK_INFISICAL_PATH", "/apps/controldeck"),
                   os.environ.get("INFISICAL_CA_BUNDLE") or None)

    def _request(self, method, path, **kwargs):
        try:
            response = requests.request(method, self.address + path, timeout=self.timeout, verify=self.verify, **kwargs)
        except requests.RequestException:
            raise VaultError("Keyvault niet bereikbaar") from None
        if response.status_code >= 400:
            raise VaultError(f"Keyvault gaf HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError:
            raise VaultError("Ongeldig antwoord van de keyvault") from None

    def _headers(self):
        if self._token is None:
            payload = self._request("POST", "/api/v1/auth/universal-auth/login",
                                    data={"clientId": self.client_id, "clientSecret": self.client_secret})
            token = payload.get("accessToken")
            if not isinstance(token, str) or not token:
                raise VaultError("Keyvault-login gaf geen token")
            self._token = token
        return {"Authorization": "Bearer " + self._token}

    def _list(self, view_values):
        query = urllib.parse.urlencode({"projectId": self.project_id, "environment": self.environment, "secretPath": self.path,
                                        "viewSecretValue": "true" if view_values else "false", "expandSecretReferences": "true"})
        secrets = self._request("GET", "/api/v4/secrets?" + query, headers=self._headers()).get("secrets", [])
        return {item["secretKey"]: item.get("secretValue", "") for item in secrets if isinstance(item, dict) and "secretKey" in item}

    def read(self):
        """All settings in the configured path as {name: value}."""
        return self._list(view_values=True)

    def write(self, name, value):
        """Create or update one setting in the configured path."""
        exists = name in self._list(view_values=False)
        body = {"projectId": self.project_id, "environment": self.environment, "secretPath": self.path, "secretValue": value}
        self._request("PATCH" if exists else "POST", "/api/v4/secrets/" + urllib.parse.quote(name, safe=""),
                      json=body, headers=self._headers())
