"""The Infisical CLI boundary uses the user's client contract, never secret arguments."""
import json
import subprocess
import sys

import pytest

from backend.vault import Vault, VaultError


def test_client_python_path_regression(monkeypatch):
    """Windows vault reads failed because a guessed 'python' sibling lacked .exe."""
    commands = []

    def run(command, **options):
        commands.append(command)
        if command[-1] == "list":
            return subprocess.CompletedProcess(command, 0, "CONTROLDECK_TEST\n")
        executable = command.index("run") + 2
        # Execute the actual extraction script. The surrounding CLI transport alone
        # is replaced, so an invalid executable really fails as it did on Windows.
        return subprocess.run(command[executable:], env={"CONTROLDECK_TEST": "synthetic-value"}, capture_output=True, text=True)

    original = subprocess.run
    # Avoid recursion when exercising the real child process.
    def transport(command, **options):
        if command[0] == sys.executable:
            return original(command, **options)
        return run(command, **options)

    monkeypatch.setattr("backend.vault.subprocess.run", transport)
    assert Vault("X:/separate-tools/infisical-secrets.exe").read() == {"CONTROLDECK_TEST": "synthetic-value"}
    assert "synthetic-value" not in json.dumps(commands)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_client_bootstrap_and_paths(monkeypatch, case):
    for name in ("INFISICAL_ADDR", "INFISICAL_CLIENT_ID", "INFISICAL_CLIENT_SECRET", "INFISICAL_PROJECT_ID"):
        monkeypatch.setenv(name, "synthetic")
    monkeypatch.delenv("CONTROLDECK_INFISICAL_PATH", raising=False)
    monkeypatch.setenv("INFISICAL_SECRET_PATH", "/ControlDeck")
    monkeypatch.setenv("INFISICAL_SHARED_PATH", "/shared")
    monkeypatch.setattr("backend.vault.shutil.which", lambda _: "infisical-secrets")
    monkeypatch.delenv("CONTROLDECK_INFISICAL_CLI", raising=False)
    if case == "normaal":
        vault = Vault.from_env()
        assert vault.path == "/ControlDeck" and vault.shared_path == "/shared"
    elif case == "boundary":
        monkeypatch.setenv("CONTROLDECK_INFISICAL_PATH", "/legacy")
        assert Vault.from_env().path == "/legacy"
        monkeypatch.delenv("INFISICAL_CLIENT_SECRET")
        assert Vault.from_env() is None
    else:
        monkeypatch.setattr("backend.vault.shutil.which", lambda _: None)
        with pytest.raises(VaultError, match="niet geïnstalleerd"):
            Vault.from_env()


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_client_read_write_and_safe_errors(monkeypatch, case):
    calls = []
    def transport(command, **options):
        calls.append((command, options.get("input")))
        if case == "faal":
            return subprocess.CompletedProcess(command, 2, "sensitive-upstream-value", "sensitive-upstream-value")
        if command[-1] == "list":
            return subprocess.CompletedProcess(command, 0, "" if case == "boundary" else "CONTROLDECK_TEST\n")
        return subprocess.CompletedProcess(command, 0, json.dumps({"CONTROLDECK_TEST": "synthetic-value"}))
    monkeypatch.setattr("backend.vault.subprocess.run", transport)
    vault = Vault("infisical-secrets", "/ControlDeck", shared_path="/shared")
    if case == "faal":
        with pytest.raises(VaultError) as error:
            vault.read()
        assert "sensitive-upstream-value" not in str(error.value)
        with pytest.raises(VaultError):
            vault.write("CONTROLDECK_TEST", "synthetic-value")
    else:
        assert vault.read() == ({} if case == "boundary" else {"CONTROLDECK_TEST": "synthetic-value"})
        vault.write("CONTROLDECK_TEST", "synthetic-value")
        assert calls[-1][1] == "synthetic-value"
        assert "synthetic-value" not in json.dumps([command for command, _ in calls])
        assert calls[0][0][1:5] == ["--path", "/ControlDeck", "--shared-path", "/shared"]
