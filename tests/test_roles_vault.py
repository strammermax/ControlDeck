import json

import pytest

from backend import auth as auth_module
from backend.app import create_app
from backend.auth import filter_configuration
from backend.vault import VaultError

ACCOUNTS = [{"email": "camiel@example.test", "role": "admin"}, {"email": "stram@example.test", "role": "editor"}, {"email": "user@example.test", "role": "user"}]


class FakeVault:
    def __init__(self, values=None, fail_read=False, fail_write=False):
        self.values, self.fail_read, self.fail_write, self.writes = dict(values or {}), fail_read, fail_write, []

    def read(self):
        if self.fail_read:
            raise VaultError("Keyvault niet bereikbaar")
        return dict(self.values)

    def write(self, name, value):
        if self.fail_write:
            raise VaultError("Keyvault gaf HTTP 403")
        self.writes.append((name, value))
        self.values[name] = value


def make_app(tmp_path, monkeypatch, vault=None, accounts=ACCOUNTS, **env):
    for name in ("CONTROLDECK_LOGIN_TYPE", "CONTROLDECK_CF_ACCESS_TEAM_DOMAIN", "CONTROLDECK_CF_ACCESS_AUD", "CONTROLDECK_GOOGLE_CLIENT_ID"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(auth_module.Vault, "from_env", classmethod(lambda cls: vault))
    path = tmp_path / "accounts.json"
    path.write_text(json.dumps(accounts))
    return create_app(data_dir=tmp_path / "data", accounts_path=path), path


def login(app, email):
    client = app.test_client()
    with client.session_transaction() as session:
        session["identity"] = {"sub": "s-" + email, "email": email}
        session["csrf"] = "token"
    return client


CONFIG = {"modules": [{"id": "dashboard"}, {"id": "admin", "pages": [{"id": "modules"}, {"id": "providers"}, {"id": "users"}]}],
          "menu": [{"route": "dashboard"}, {"label": "Admin", "children": [{"route": "admin/modules"}, {"route": "admin/users"}]}],
          "providers": [], "widgets": [{"route": "admin/users", "provider": "x"}, {"route": "dashboard", "provider": "x"}]}


def test_editor_sees_admin_without_user_management():
    view = filter_configuration(CONFIG, {"role": "editor", "modules": ["*"]})
    admin = next(m for m in view["modules"] if m["id"] == "admin")
    assert [p["id"] for p in admin["pages"]] == ["modules", "providers"]
    assert view["menu"][1]["children"] == [{"route": "admin/modules"}]
    assert view["widgets"] == [{"route": "dashboard", "provider": "x"}]
    assert filter_configuration(CONFIG, {"role": "admin", "modules": ["*"]}) is CONFIG
    assert all(m["id"] != "admin" for m in filter_configuration(CONFIG, {"role": "user", "modules": ["*"]})["modules"])


def test_only_admin_manages_accounts(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    assert login(app, "camiel@example.test").get("/api/accounts").status_code == 200
    assert login(app, "stram@example.test").get("/api/accounts").status_code == 403
    assert login(app, "user@example.test").get("/api/accounts").status_code == 403


def test_editor_role_is_accepted_and_reported(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path, monkeypatch)
    body = login(app, "stram@example.test").get("/api/session").get_json()
    assert body["user"]["role"] == "editor"


def test_vault_accounts_and_settings_are_leading(tmp_path, monkeypatch):
    vault = FakeVault({"CONTROLDECK_ACCOUNTS": json.dumps([{"email": "camiel@example.test", "role": "admin"}, {"email": "new@example.test", "role": "editor"}]),
                       "CONTROLDECK_LOGIN_TYPE": "cloudflare", "OTHER_APP_SECRET": "ignored"})
    app, path = make_app(tmp_path, monkeypatch, vault)
    assert [a["email"] for a in json.loads(path.read_text())] == ["camiel@example.test", "new@example.test"]
    assert login(app, "new@example.test").get("/api/session").get_json()["user"]["role"] == "editor"
    assert login(app, "stram@example.test").get("/api/session").get_json()["authenticated"] is False
    import os
    assert "OTHER_APP_SECRET" not in os.environ


def test_unreachable_vault_keeps_last_known_accounts(tmp_path, monkeypatch):
    app, path = make_app(tmp_path, monkeypatch, FakeVault(fail_read=True))
    assert len(json.loads(path.read_text())) == 3
    assert login(app, "camiel@example.test").get("/api/session").get_json()["authenticated"] is True


def test_invalid_vault_accounts_keep_last_known_accounts(tmp_path, monkeypatch):
    app, path = make_app(tmp_path, monkeypatch, FakeVault({"CONTROLDECK_ACCOUNTS": json.dumps([{"email": "x@example.test", "role": "owner"}])}))
    assert len(json.loads(path.read_text())) == 3


def test_account_change_is_written_to_vault_first(tmp_path, monkeypatch):
    vault = FakeVault({"CONTROLDECK_ACCOUNTS": json.dumps(ACCOUNTS)})
    app, path = make_app(tmp_path, monkeypatch, vault)
    client = login(app, "camiel@example.test")
    response = client.post("/api/accounts", json={"email": "Vera@Example.test", "role": "user"}, headers={"X-CSRF-Token": "token"})
    assert response.status_code == 201
    name, value = vault.writes[-1]
    assert name == "CONTROLDECK_ACCOUNTS" and "vera@example.test" in value
    assert "vera@example.test" in path.read_text()


def test_failed_vault_write_changes_nothing(tmp_path, monkeypatch):
    vault = FakeVault({"CONTROLDECK_ACCOUNTS": json.dumps(ACCOUNTS)}, fail_write=True)
    app, path = make_app(tmp_path, monkeypatch, vault)
    before = path.read_text()
    response = login(app, "camiel@example.test").post("/api/accounts", json={"email": "vera@example.test", "role": "user"}, headers={"X-CSRF-Token": "token"})
    assert response.status_code == 503
    assert path.read_text() == before


@pytest.mark.parametrize("login_type, google, access", [("cloudflare", False, True), ("google", True, False), ("both", True, True), ("typo", True, True)])
def test_login_type_controls_available_methods(tmp_path, monkeypatch, login_type, google, access):
    app, _ = make_app(tmp_path, monkeypatch, None, CONTROLDECK_LOGIN_TYPE=login_type,
                      CONTROLDECK_GOOGLE_CLIENT_ID="id", CONTROLDECK_GOOGLE_CLIENT_SECRET="secret", CONTROLDECK_BASE_URL="https://cd.example.test",
                      CONTROLDECK_CF_ACCESS_TEAM_DOMAIN="https://team.example.test", CONTROLDECK_CF_ACCESS_AUD="aud")
    body = app.test_client().get("/api/session").get_json()
    assert body["loginAvailable"] is google
    assert (app.extensions["controldeck_access"] is not None) is access
    assert body["loginType"] == ("both" if login_type == "typo" else login_type)
