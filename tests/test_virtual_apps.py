import json
from unittest.mock import Mock

import pytest

from backend import virtual_apps
from backend.app import create_app
from backend.virtual_apps import connect_url, kasm_settings, project_images, project_sessions, NotConfigured, NotLinked, KasmError

H = {"X-CSRF-Token": "csrf"}
ORIGIN = "https://kasm.example.test"
ME = "11111111-2222-3333-4444-555555555555"
OTHER = "99999999-8888-7777-6666-555555555555"
CHROME, FIREFOX = "a" * 32, "b" * 32
CONFIG = {"kasm": {"url": ORIGIN, "apiKey": "key", "apiSecret": "s" * 32, "users": {"user@example.test": ME}}}
IMAGES = {"images": [
    {"image_id": FIREFOX, "friendly_name": "Firefox", "enabled": True, "image_src": "img/thumbnails/firefox.png", "description": "Browser", "categories": ["Browser"]},
    {"image_id": CHROME, "friendly_name": "Chrome", "enabled": True, "image_src": "img/thumbnails/chrome.png"},
    {"image_id": "c" * 32, "friendly_name": "Uit", "enabled": False},
]}
KASMS = {"kasms": [
    {"kasm_id": "d" * 32, "user_id": ME, "image_id": CHROME, "operational_status": "running", "start_date": "2026-10-18 08:00:00"},
    {"kasm_id": "e" * 32, "user_id": OTHER, "image_id": CHROME, "operational_status": "running"},
]}
STARTED = {"kasm_id": "f" * 32, "kasm_url": f"/#/connect/kasm/{'f' * 32}/{ME}/token-abc"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.auth.Vault.from_env", classmethod(lambda cls: None))
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([
        {"email": "user@example.test", "role": "user", "modules": ["virtual-apps"]},
        {"email": "other@example.test", "role": "user", "modules": ["virtual-apps"]},
        {"email": "denied@example.test", "role": "user", "modules": ["bookmarks"]},
    ]))
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True
    vault = {"CONTROLDECK_APP_LAUNCHES": json.dumps(CONFIG)}
    app.extensions["controldeck_vault"] = Mock(read=lambda: vault)
    calls, replies = [], {"get_images": IMAGES, "get_kasms": KASMS, "request_kasm": STARTED, "destroy_kasm": {}}

    def post(url, json=None, **kwargs):
        endpoint = url.rsplit("/", 1)[1]
        calls.append((endpoint, json))
        value = replies[endpoint]
        if isinstance(value, Exception):
            raise value
        return Mock(status_code=200, json=Mock(return_value=value))
    monkeypatch.setattr("backend.modules.kasm.requests.post", post)

    def client(email="user@example.test"):
        c = app.test_client()
        if email:
            with c.session_transaction() as session:
                session["identity"] = {"sub": "subject-" + email, "email": email}
                session["csrf"] = "csrf"
        return c
    return client, calls, replies, vault


def test_overview_normaal_apps_with_icons_and_only_my_sessions(env):
    client, calls, replies, vault = env
    body = client().get("/api/virtual-apps").get_json()
    assert [a["name"] for a in body["apps"]] == ["Chrome", "Firefox"], "disabled workspaces are hidden, sorted by name"
    assert body["apps"][1]["icon"] == ORIGIN + "/img/thumbnails/firefox.png"
    assert [s["id"] for s in body["sessions"]] == ["d" * 32] and body["sessions"][0]["name"] == "Chrome"
    assert "s" * 32 not in json.dumps(body), "the API secret never reaches the browser"


def test_start_normaal_opens_the_connect_link_for_my_user(env):
    client, calls, replies, vault = env
    result = client().post(f"/api/virtual-apps/{CHROME}/start", json={}, headers=H)
    assert result.status_code == 200 and result.get_json()["url"] == f"{ORIGIN}/#/connect/kasm/{'f' * 32}/{ME}/token-abc"
    request = [body for endpoint, body in calls if endpoint == "request_kasm"][-1]
    assert request["user_id"] == ME and request["image_id"] == CHROME and request["enable_sharing"] is False


def test_stop_normaal_and_boundary_only_own_sessions(env):
    client, calls, replies, vault = env
    assert client().delete(f"/api/virtual-apps/sessions/{'d' * 32}", headers=H).status_code == 200
    assert [body for endpoint, body in calls if endpoint == "destroy_kasm"][-1] == {"api_key": "key", "api_key_secret": "s" * 32, "kasm_id": "d" * 32, "user_id": ME}
    assert client().delete(f"/api/virtual-apps/sessions/{'e' * 32}", headers=H).status_code == 404, "another user's session"
    assert len([c for c in calls if c[0] == "destroy_kasm"]) == 1


def test_boundary_empty_kasm_and_dashed_ids(env):
    client, calls, replies, vault = env
    replies["get_images"], replies["get_kasms"] = {"images": []}, {"kasms": []}
    assert client().get("/api/virtual-apps").get_json()["apps"] == []
    dashed = ME
    assert kasm_settings(CONFIG, "user@example.test")[1] == dashed
    assert project_sessions({"kasms": [{"kasm_id": "d" * 32, "user_id": ME.replace("-", "")}]}, ME, [])[0]["id"] == "d" * 32


def test_faal_refusals_and_upstream_errors(env):
    client, calls, replies, vault = env
    c = client()
    assert c.post("/api/virtual-apps/not-an-id/start", json={}, headers=H).status_code == 400
    assert c.post(f"/api/virtual-apps/{CHROME}/start", json={"user_id": OTHER}, headers=H).status_code == 400, "no user from the browser"
    assert c.post(f"/api/virtual-apps/{'c' * 32}/start", json={}, headers=H).status_code == 404, "disabled workspace"
    replies["request_kasm"] = {"kasm_url": "https://evil.example.test/#/connect/kasm/x/y/z"}
    assert c.post(f"/api/virtual-apps/{CHROME}/start", json={}, headers=H).status_code == 424
    replies["get_kasms"] = {"error_message": "Unauthorized: missing permission"}
    refused = c.get("/api/virtual-apps")
    assert refused.status_code == 424 and "missing permission" in refused.get_json()["error"]
    replies["get_kasms"] = virtual_apps.requests.ConnectionError()
    assert c.get("/api/virtual-apps").status_code == 424


def test_authentication_authorization_and_configuration(env):
    client, calls, replies, vault = env
    assert client(None).get("/api/virtual-apps").status_code == 401
    assert client().post(f"/api/virtual-apps/{CHROME}/start", json={}).status_code == 403, "CSRF required"
    assert client("denied@example.test").get("/api/virtual-apps").status_code == 403, "no Virtual Apps module"
    unlinked = client("other@example.test").get("/api/virtual-apps")
    assert unlinked.status_code == 403 and unlinked.get_json()["notLinked"] is True
    vault["CONTROLDECK_APP_LAUNCHES"] = "{}"
    missing = client().get("/api/virtual-apps")
    assert missing.status_code == 503 and missing.get_json()["notConfigured"] is True


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_projection_helpers(case):
    if case == "normaal":
        assert connect_url(ORIGIN, STARTED).startswith(ORIGIN + "/#/connect/kasm/")
        assert project_images(ORIGIN, IMAGES)[0]["categories"] == []
    elif case == "boundary":
        assert connect_url(ORIGIN, {"kasm_url": f"{ORIGIN}/#/connect/kasm/a/b/c"}) == f"{ORIGIN}/#/connect/kasm/a/b/c"
        assert project_images(ORIGIN, {"images": [{"image_id": CHROME, "friendly_name": "X", "image_src": "../../etc/passwd.png"}]})[0]["icon"] is None
    else:
        for bad in ({"kasm_url": "/#/connect/kasm/a/b/c?x=1"}, {"kasm_url": "javascript:alert(1)"}, {"kasm_url": "/admin#/connect/kasm/a/b/c"}, {}):
            with pytest.raises(KasmError):
                connect_url(ORIGIN, bad)
        with pytest.raises(KasmError):
            project_images(ORIGIN, {"images": "x"})
        with pytest.raises(NotConfigured):
            kasm_settings({"kasm": {"url": "http://kasm.example.test", "apiKey": "k", "apiSecret": "s", "users": {}}}, "a@b")
        with pytest.raises(NotLinked):
            kasm_settings(CONFIG, "someone@example.test")


FINGERPRINT = ":".join(["06", "A5"] * 16)


def test_regression_internal_api_url_behind_login_proxy(env, monkeypatch):
    """Bug 2026-10-18: Kasm's public address sits behind Cloudflare Access, so every API call was
    redirected to a login page. apiUrl sends API calls to the internal address; links stay public."""
    client, calls, replies, vault = env
    vault["CONTROLDECK_APP_LAUNCHES"] = json.dumps({"kasm": {**CONFIG["kasm"], "apiUrl": "https://kasm.internal.test"}})
    seen = []

    def post(url, json=None, **kwargs):
        seen.append(url.split("/api/public/")[0])
        value = replies[url.rsplit("/", 1)[1]]
        return Mock(status_code=200, json=Mock(return_value=value))
    monkeypatch.setattr("backend.modules.kasm.requests.post", post)
    replies["request_kasm"] = {"kasm_url": f"https://kasm.internal.test/#/connect/kasm/{'f' * 32}/{ME}/t"}
    assert client().get("/api/virtual-apps").status_code == 200
    started = client().post(f"/api/virtual-apps/{CHROME}/start", json={}, headers=H).get_json()
    assert set(seen) == {"https://kasm.internal.test"}
    assert started["url"] == f"{ORIGIN}/#/connect/kasm/{'f' * 32}/{ME}/t", "the browser opens the public address"


def test_login_redirect_faal_gives_a_clear_message(env, monkeypatch):
    client, calls, replies, vault = env
    monkeypatch.setattr("backend.modules.kasm.requests.post", lambda *a, **k: Mock(status_code=302, json=Mock(side_effect=ValueError)))
    answer = client().get("/api/virtual-apps")
    assert answer.status_code == 424 and "aanmeldpagina" in answer.get_json()["error"]


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_pinned_certificate(case, monkeypatch):
    from backend.modules import kasm as module
    sessions = []

    class Session:
        def __init__(self):
            self.mounted = {}
            sessions.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def mount(self, prefix, adapter):
            self.mounted[prefix] = adapter

        def post(self, url, **kwargs):
            self.kwargs = kwargs
            return Mock(status_code=200, json=Mock(return_value={"images": []}))
    monkeypatch.setattr(module.requests, "Session", Session)
    config = {**CONFIG["kasm"], "apiUrl": "https://kasm.internal.test"}
    if case == "normaal":
        settings = module.kasm_config({**config, "apiFingerprint": FINGERPRINT.lower()})
        module.kasm_post(settings, "get_images")
        adapter = sessions[0].mounted["https://kasm.internal.test"]
        assert adapter.fingerprint == FINGERPRINT and sessions[0].kwargs["verify"] is False
    elif case == "boundary":
        settings = module.kasm_config(config)
        assert settings["fingerprint"] is None and settings["origin"] == ORIGIN and settings["api"] == "https://kasm.internal.test"
    else:
        for bad in ({**config, "apiFingerprint": "AA:BB"}, {**config, "apiUrl": "http://kasm.internal.test"}, {**config, "extra": 1}):
            with pytest.raises(ValueError):
                module.kasm_config(bad)
