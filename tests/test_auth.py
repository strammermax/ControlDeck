import json
from pathlib import Path

import pytest

from backend.app import create_app
from backend.auth import database, establish_identity, load_accounts
from backend.configuration import ConfigurationError


@pytest.fixture
def app(tmp_path, monkeypatch):
    for key in ("CONTROLDECK_GOOGLE_CLIENT_ID", "CONTROLDECK_GOOGLE_CLIENT_SECRET", "CONTROLDECK_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([
        {"email":"admin@example.test", "role":"admin"},
        {"email":"user@example.test", "role":"user"},
    ]))
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    app.config.update(TESTING=True)
    app.config["TEST_ACCOUNTS"] = accounts
    app.config["TEST_DATA"] = tmp_path / "data"
    return app


def login(app, client, email="admin@example.test", sub="admin"):
    establish_identity(app.config["TEST_DATA"] / "users.sqlite3", {"email":email, "sub":sub, "email_verified":True})
    with client.session_transaction() as session:
        session["identity"] = {"email":email, "sub":sub}
        session["csrf"] = "valid-csrf"


def test_anonymous_cannot_access_any_private_api(app):
    client = app.test_client()
    for path in ("/api/config", "/api/preferences", "/api/accounts"):
        assert client.get(path).status_code == 401
    assert client.put("/api/preferences", json={"theme":"light"}).status_code == 401
    assert client.get("/api/session").json["authenticated"] is False
    assert client.get("/auth/google/login").location.endswith("login=unavailable")
    assert client.get("/health").status_code == 200


def test_user_has_no_admin_configuration_or_account_access(app):
    client = app.test_client()
    login(app, client, "user@example.test", "user")
    config = client.get("/api/config").json
    assert all(module["id"] != "admin" for module in config["modules"])
    assert all(item["id"] != "admin" for item in config["menu"])
    assert client.get("/api/accounts").status_code == 403
    assert client.post("/api/accounts", headers={"X-CSRF-Token":"valid-csrf"}, json={"email":"new@example.test","role":"admin"}).status_code == 403


def test_admin_can_manage_profiles_and_enabled_defaults_true(app):
    client = app.test_client()
    login(app, client)
    response = client.post("/api/accounts", headers={"X-CSRF-Token":"valid-csrf"}, json={"firstName":"New","lastName":"Person","email":"new@example.test","role":"user","ssoType":"windows"})
    assert response.status_code == 201
    assert response.json["enabled"] is True
    assert response.json["firstName"] == "New"
    assert len(client.get("/api/accounts").json) == 3
    assert "token" not in json.dumps(client.get("/api/accounts").json)


def test_mutations_require_csrf_and_last_google_admin_cannot_be_disabled(app):
    client = app.test_client()
    login(app, client)
    assert client.post("/api/accounts", json={"email":"new@example.test","role":"user"}).status_code == 403
    assert client.put("/api/accounts/admin@example.test", headers={"X-CSRF-Token":"valid-csrf"}, json={"email":"admin@example.test","role":"user"}).status_code == 400
    assert client.put("/api/accounts/admin@example.test", headers={"X-CSRF-Token":"valid-csrf"}, json={"email":"admin@example.test","role":"admin","enabled":False}).status_code == 400
    assert client.put("/api/accounts/admin@example.test", headers={"X-CSRF-Token":"valid-csrf"}, json={"email":"admin@example.test","role":"admin","ssoType":"windows"}).status_code == 400


def test_preferences_are_private_persistent_and_immutable_identity(app):
    admin, user = app.test_client(), app.test_client()
    login(app, admin)
    login(app, user, "user@example.test", "user")
    response = admin.put("/api/preferences", headers={"X-CSRF-Token":"valid-csrf"}, json={"theme":"light","lastRoute":"proxmox/nodes"})
    assert response.status_code == 200
    assert user.get("/api/preferences").json == {}
    assert admin.get("/api/preferences").json["theme"] == "light"
    assert admin.put("/api/preferences", headers={"X-CSRF-Token":"valid-csrf"}, json={"email":"user@example.test"}).status_code == 400
    second_device = app.test_client()
    login(app, second_device)
    assert second_device.get("/api/preferences").json["lastRoute"] == "proxmox/nodes"


def test_revocation_and_windows_profiles_cannot_use_google_session(app):
    client = app.test_client()
    login(app, client, "user@example.test", "user")
    accounts = load_accounts(app.config["TEST_ACCOUNTS"])
    accounts[1]["enabled"] = False
    app.config["TEST_ACCOUNTS"].write_text(json.dumps(accounts))
    assert client.get("/api/config").status_code == 401
    accounts[1].update(enabled=True, ssoType="windows")
    app.config["TEST_ACCOUNTS"].write_text(json.dumps(accounts))
    login(app, client, "user@example.test", "user")
    assert client.get("/api/config").status_code == 401


def test_reject_unverified_or_different_google_subject(app):
    db = app.config["TEST_DATA"] / "users.sqlite3"
    claims = {"email":"admin@example.test", "sub":"admin", "email_verified":True}
    with pytest.raises(ConfigurationError):
        establish_identity(db, {**claims,"email_verified":False})
    establish_identity(db, claims)
    with pytest.raises(ConfigurationError):
        establish_identity(db, {**claims,"sub":"different-google-account"})


def test_logout_clears_access(app):
    client = app.test_client()
    login(app, client)
    assert client.post("/api/logout").status_code == 403
    assert client.post("/api/logout", headers={"X-CSRF-Token":"valid-csrf"}).status_code == 200
    assert client.get("/api/config").status_code == 401

@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_preferences_three_cases(app, case):
    client = app.test_client()
    login(app, client)
    headers = {"X-CSRF-Token":"valid-csrf"}
    if case == "normaal":
        assert client.put("/api/preferences", headers=headers, json={"theme":"light"}).status_code == 200
        assert client.get("/api/preferences").json["theme"] == "light"
    elif case == "boundary":
        route = "a"*130
        assert client.put("/api/preferences", headers=headers, json={"lastRoute":route}).status_code == 200
        assert client.get("/api/preferences").json["lastRoute"] == route
    else:
        assert client.put("/api/preferences", headers=headers, json={"lastRoute":"a"*131}).status_code == 400
        assert client.get("/api/preferences").json == {}


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_account_creation_three_cases(app, case):
    client = app.test_client()
    login(app, client)
    profile = {"email":"new@example.test", "role":"user"}
    if case == "normaal":
        assert client.post("/api/accounts", headers={"X-CSRF-Token":"valid-csrf"}, json=profile).status_code == 201
    elif case == "boundary":
        profile.update(firstName="a"*100,lastName="b"*100,email="NEW@EXAMPLE.TEST")
        response = client.post("/api/accounts", headers={"X-CSRF-Token":"valid-csrf"}, json=profile)
        assert response.status_code == 201 and response.json["email"] == "new@example.test"
    else:
        profile["role"] = "superuser"
        assert client.post("/api/accounts", headers={"X-CSRF-Token":"valid-csrf"}, json=profile).status_code == 400
        assert len(client.get("/api/accounts").json) == 2


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_account_edit_three_cases(app, case):
    client = app.test_client()
    login(app, client)
    headers = {"X-CSRF-Token":"valid-csrf"}
    if case == "normaal":
        response = client.put("/api/accounts/user@example.test", headers=headers, json={"email":"user@example.test","role":"user","firstName":"Updated"})
        assert response.status_code == 200 and response.json["firstName"] == "Updated"
    elif case == "boundary":
        response = client.put("/api/accounts/admin@example.test", headers=headers, json={"email":"admin@example.test","role":"admin","firstName":"a"*100})
        assert response.status_code == 200  # Editing the only administrator's name is permitted.
    else:
        assert client.put("/api/accounts/admin@example.test", headers=headers, json={"email":"admin@example.test","role":"user"}).status_code == 400
        assert client.get("/api/session").json["user"]["role"] == "admin"


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_session_three_cases(app, case):
    client = app.test_client()
    login(app, client)
    if case == "normaal":
        assert client.get("/api/session").json["authenticated"] is True
    elif case == "boundary":
        accounts = load_accounts(app.config["TEST_ACCOUNTS"])
        accounts[0]["enabled"] = False
        app.config["TEST_ACCOUNTS"].write_text(json.dumps(accounts))
        assert client.get("/api/session").json["authenticated"] is False
    else:
        client.set_cookie("controldeck_session", "tampered-cookie")
        assert client.get("/api/session").json["authenticated"] is False
        assert client.get("/api/config").status_code == 401


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_logout_three_cases(app, case):
    client = app.test_client()
    login(app, client)
    if case == "normaal":
        assert client.post("/api/logout", headers={"X-CSRF-Token":"valid-csrf"}).status_code == 200
        assert client.get("/api/config").status_code == 401
    elif case == "boundary":
        client.post("/api/logout", headers={"X-CSRF-Token":"valid-csrf"})
        assert client.post("/api/logout", headers={"X-CSRF-Token":"valid-csrf"}).status_code == 401
    else:
        assert client.post("/api/logout", headers={"X-CSRF-Token":"invalid"}).status_code == 403
        assert client.get("/api/session").json["authenticated"] is True


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_module_permissions_three_cases(app, case):
    client = app.test_client()
    login(app, client,"user@example.test","user")
    if case == "normaal":
        assert any(m["id"] == "dashboard" for m in client.get("/api/config").json["modules"])
    elif case == "boundary":
        accounts = load_accounts(app.config["TEST_ACCOUNTS"])
        accounts[1]["modules"] = []
        app.config["TEST_ACCOUNTS"].write_text(json.dumps(accounts))
        assert client.get("/api/config").json["modules"] == []
    else:
        assert client.get("/api/accounts").status_code == 403
