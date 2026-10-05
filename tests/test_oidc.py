import json
import time

import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey

from backend.app import create_app


@pytest.fixture
def oidc(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTROLDECK_GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("CONTROLDECK_GOOGLE_CLIENT_SECRET", "test-secret-not-a-real-credential")
    monkeypatch.setenv("CONTROLDECK_BASE_URL", "https://controldeck.example.test")
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([{"email":"admin@example.test","role":"admin"}]))
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    google = app.extensions["controldeck_google"]
    key = RSAKey.generate_key(parameters={"kid":"test-signing-key"})
    monkeypatch.setattr(google,"load_server_metadata",lambda: {"issuer":"https://accounts.google.com","id_token_signing_alg_values_supported":["RS256"]})
    monkeypatch.setattr(google,"fetch_jwk_set",lambda **kwargs: {"keys":[key.as_dict()]})
    return app, google, key


def run_callback(oidc, monkeypatch, changes=None, wrong_state=False, signing_key=None):
    app, google, key = oidc
    now = int(time.time())
    claims = {"iss":"https://accounts.google.com","aud":"test-client","sub":"test-subject","iat":now,"exp":now+300,"nonce":"expected-nonce","email":"admin@example.test","email_verified":True}
    claims.update(changes or {})
    signed = jwt.encode({"alg":"RS256","kid":"test-signing-key"},claims,signing_key or key)
    monkeypatch.setattr(google,"fetch_access_token",lambda **kwargs: {"id_token":signed,"access_token":"test-token"})
    client = app.test_client()
    with client.session_transaction() as session:
        session["_state_google_expected-state"] = {"data":{"nonce":"expected-nonce","redirect_uri":"https://controldeck.example.test/auth/google/callback"},"exp":now+300}
    response = client.get("/auth/google/callback?code=test-code&state=" + ("wrong-state" if wrong_state else "expected-state"))
    return client, response


def test_valid_signed_oidc_callback_opens_only_approved_account(oidc, monkeypatch):
    client, response = run_callback(oidc,monkeypatch)
    assert response.location == "/"
    assert client.get("/api/session").json["authenticated"] is True
    assert client.get("/api/config").status_code == 200
    with client.session_transaction() as session:
        assert "access_token" not in session
        assert "id_token" not in session


@pytest.mark.parametrize("claims", [
    {"nonce":"wrong-nonce"},
    {"aud":"another-client"},
    {"iss":"https://attacker.example.test"},
    {"exp":1},
    {"email_verified":False},
    {"email":"unknown@example.test"},
])
def test_invalid_oidc_claims_never_open_session(oidc, monkeypatch, claims):
    client,response = run_callback(oidc,monkeypatch,claims)
    assert response.location.endswith("login=denied")
    assert client.get("/api/config").status_code == 401


def test_wrong_state_never_opens_session(oidc,monkeypatch):
    client,response = run_callback(oidc,monkeypatch,wrong_state=True)
    assert response.location.endswith("login=denied")
    assert client.get("/api/session").json["authenticated"] is False


def test_wrong_signing_key_never_opens_session(oidc,monkeypatch):
    attacker = RSAKey.generate_key(parameters={"kid":"test-signing-key"})
    client,response = run_callback(oidc,monkeypatch,signing_key=attacker)
    assert response.location.endswith("login=denied")
    assert client.get("/api/config").status_code == 401

@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_google_callback_three_cases(oidc, monkeypatch, case):
    # Fix time so the exact Authlib 120-second clock-skew boundary is deterministic.
    monkeypatch.setattr(time,"time",lambda:1700000000)
    changes = {} if case == "normaal" else {"exp":1700000000-(120 if case == "boundary" else 121)}
    client,response = run_callback(oidc,monkeypatch,changes)
    assert client.get("/api/session").json["authenticated"] is (case != "faal")


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_google_login_start_three_cases(oidc, monkeypatch, tmp_path, case):
    from flask import redirect
    app, google, _ = oidc
    if case == "boundary":
        monkeypatch.delenv("CONTROLDECK_GOOGLE_CLIENT_SECRET")
        app = create_app(data_dir=tmp_path / "unconfigured",accounts_path=tmp_path / "accounts.json")
    elif case == "normaal":
        def authorize(redirect_uri, **kwargs):
            assert redirect_uri == "https://controldeck.example.test/auth/google/callback"
            return redirect("https://accounts.google.com/o/oauth2/v2/auth")
        monkeypatch.setattr(google,"authorize_redirect",authorize)
    else:
        def unavailable(*args,**kwargs): raise RuntimeError("Google unavailable")
        monkeypatch.setattr(google,"authorize_redirect",unavailable)
    response = app.test_client().get("/auth/google/login")
    if case == "normaal": assert response.location.startswith("https://accounts.google.com/")
    elif case == "boundary": assert response.location.endswith("login=unavailable")
    else: assert response.location.endswith("login=failed")
