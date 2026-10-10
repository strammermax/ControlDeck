"""Optional Infisical keyvault for ControlDeck settings and the account list.

All Infisical access goes through the `infisical-secrets` CLI from
infisical-secret-client, the only component that talks to Infisical. Only the
Infisical bootstrap (INFISICAL_* environment) lives on the server; ControlDeck
passes it on to the CLI. Values travel via stdout/stdin, never via arguments,
and are never logged.
"""

import json
import os
import shutil
import subprocess


class VaultError(Exception):
    """Message is safe to show; it never contains secrets or CLI output."""


class Vault:
    def __init__(self, cli, path="/apps/controldeck", timeout=30):
        self.cli, self.path, self.timeout = cli, path, timeout

    @classmethod
    def from_env(cls):
        required = ("INFISICAL_ADDR", "INFISICAL_CLIENT_ID", "INFISICAL_CLIENT_SECRET", "INFISICAL_PROJECT_ID")
        if not all(os.environ.get(name) for name in required):
            return None
        cli = os.environ.get("CONTROLDECK_INFISICAL_CLI") or shutil.which("infisical-secrets")
        if not cli:
            raise VaultError("infisical-secrets (infisical-secret-client) is niet geïnstalleerd")
        return cls(cli, os.environ.get("CONTROLDECK_INFISICAL_PATH", "/apps/controldeck"))

    def _run(self, args, stdin=None):
        try:
            result = subprocess.run([self.cli, "--path", self.path, "--shared-path", "", *args], input=stdin,
                                    capture_output=True, text=True, timeout=self.timeout)
        except (OSError, subprocess.TimeoutExpired):
            raise VaultError("Keyvault niet bereikbaar") from None
        if result.returncode != 0:
            raise VaultError("Keyvault-opdracht mislukt")
        return result.stdout

    def read(self):
        """All settings in the configured path as {name: value}."""
        script = "import json,os,sys; json.dump({k: os.environ[k] for k in sys.argv[1:]}, sys.stdout)"
        names = [line.strip() for line in self._run(["list"]).splitlines() if line.strip()]
        if not names:
            return {}
        python = os.path.join(os.path.dirname(self.cli), "python")
        try:
            return json.loads(self._run(["run", "--", python, "-c", script, *names]))
        except ValueError:
            raise VaultError("Ongeldig antwoord van de keyvault") from None

    def write(self, name, value):
        """Create or update one setting in the configured path."""
        self._run(["set", name], stdin=value)
