import json
import time

import pytest
from joserfc import jwt
from joserfc.jwk import KeySet, RSAKey

from backend.app import create_app
from backend.auth import CloudflareAccess, database

TEAM = "https://team.cloudflareaccess.test"
AUD = "test-audience-tag"


@pytest.fixture
def access(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTROLDECK_CF_ACCESS_TEAM_DOMAIN", TEAM)
    monkeypatch.setenv("CONTROLDECK_CF_ACCESS_AUD", AUD)
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([{"email": "admin@example.test", "role": "admin"},
                                    {"email": "off@example.test", "role": "user", "enabled": False}]))
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    key = RSAKey.generate_key(parameters={"kid": "access-key"})
    verifier = app.extensions["controldeck_access"]
    monkeypatch.setattr(verifier, "keys", lambda refresh=False: KeySet([key]))
    return app, key, tmp_path


def assertion(key, **changes):
    now = int(time.time())
    claims = {"iss": TEAM, "aud": [AUD], "sub": "cf-subject", "email": "Admin@Example.test", "iat": now, "exp": now + 300}
    claims.update(changes)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode({"alg": "RS256", "kid": key.kid}, claims, key)


def session_for(app, header=None, cookie=None):
    client = app.test_client()
    if cookie:
        client.set_cookie("CF_Authorization", cookie)
    response = client.get("/api/session", headers={"Cf-Access-Jwt-Assertion": header} if header else {})
    return client, response.get_json()


def test_valid_access_assertion_logs_in_approved_account_once(access):
    app, key, _ = access
    client, body = session_for(app, assertion(key))
    assert body["authenticated"] is True
    assert body["user"]["email"] == "admin@example.test"
    assert body["logoutUrl"] == "/cdn-cgi/access/logout"
    assert body["csrfToken"]
    # Without the header the existing session stays valid.
    assert client.get("/api/session").get_json()["authenticated"] is True


def test_access_cookie_is_accepted_as_well(access):
    app, key, _ = access
    _, body = session_for(app, cookie=assertion(key))
    assert body["authenticated"] is True


@pytest.mark.parametrize("changes", [
    {"aud": ["other-application"]},
    {"iss": "https://evil.cloudflareaccess.test"},
    {"exp": int(time.time()) - 3600},
    {"email": None},
    {"email": "stranger@example.test"},
    {"email": "off@example.test"},
])
def test_invalid_or_unapproved_assertion_never_opens_session(access, changes):
    app, key, _ = access
    _, body = session_for(app, assertion(key, **changes))
    assert body["authenticated"] is False
    assert body["logoutUrl"] is None or changes.get("email") in ("stranger@example.test", "off@example.test")


def test_assertion_signed_with_unknown_key_is_rejected(access):
    app, _, _ = access
    forged = assertion(RSAKey.generate_key(parameters={"kid": "access-key"}))
    _, body = session_for(app, forged)
    assert body["authenticated"] is False


def test_garbage_and_oversized_headers_are_rejected(access):
    app, _, _ = access
    for value in ("not-a-jwt", "a.b.c", "x" * 9000):
        _, body = session_for(app, value)
        assert body["authenticated"] is False


def test_existing_google_profile_keeps_subject_and_preferences(access):
    app, key, tmp_path = access
    with database(tmp_path / "data" / "users.sqlite3") as db:
        db.execute("INSERT INTO users(subject,email,preferences) VALUES(?,?,?)", ("google-sub", "admin@example.test", json.dumps({"theme": "light"})))
    client, body = session_for(app, assertion(key))
    assert body["authenticated"] is True
    assert client.get("/api/preferences").get_json() == {"theme": "light"}


def test_access_identity_replaces_session_of_other_user(access, monkeypatch, tmp_path):
    app, key, _ = access
    accounts = json.loads((tmp_path / "accounts.json").read_text())
    accounts.append({"email": "second@example.test", "role": "user"})
    (tmp_path / "accounts.json").write_text(json.dumps(accounts))
    client, body = session_for(app, assertion(key))
    assert body["user"]["email"] == "admin@example.test"
    body = client.get("/api/session", headers={"Cf-Access-Jwt-Assertion": assertion(key, email="second@example.test", sub="other")}).get_json()
    assert body["user"]["email"] == "second@example.test"


def test_api_requires_login_without_valid_assertion(access):
    app, _, _ = access
    assert app.test_client().get("/api/configuration").status_code == 401


def test_access_disabled_without_configuration(tmp_path, monkeypatch):
    monkeypatch.delenv("CONTROLDECK_CF_ACCESS_TEAM_DOMAIN", raising=False)
    monkeypatch.delenv("CONTROLDECK_CF_ACCESS_AUD", raising=False)
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([{"email": "admin@example.test", "role": "admin"}]))
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    assert app.extensions["controldeck_access"] is None
    key = RSAKey.generate_key(parameters={"kid": "access-key"})
    _, body = session_for(app, assertion(key))
    assert body["authenticated"] is False


def test_key_set_is_refreshed_once_on_unknown_key(monkeypatch):
    verifier = CloudflareAccess(TEAM, AUD)
    old, new = RSAKey.generate_key(parameters={"kid": "old"}), RSAKey.generate_key(parameters={"kid": "new"})
    calls = []
    def keys(refresh=False):
        calls.append(refresh)
        return KeySet([new if refresh else old])
    monkeypatch.setattr(verifier, "keys", keys)
    assert verifier.verify(assertion(new)) == {"email": "admin@example.test", "sub": "cf-subject"}
    assert calls == [False, True]
