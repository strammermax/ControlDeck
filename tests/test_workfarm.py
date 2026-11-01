import json

import pytest
from backend.app import create_app
from backend.configuration import DEFAULT_PATH, load_config


@pytest.fixture
def farm(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTROLDECK_BASE_URL", "https://control.example.test")
    path = tmp_path / "config.json"
    path.write_text(json.dumps(load_config(DEFAULT_PATH)))
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([{"email": "admin@example.test", "role": "admin"},
                                    {"email": "viewer@example.test", "role": "user", "modules": ["workfarm"]},
                                    {"email": "other@example.test", "role": "user", "modules": ["bookmarks"]}]))
    app = create_app(config_path=path, data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True
    def client(email):
        c = app.test_client()
        with c.session_transaction() as session:
            session["identity"] = {"email": email, "sub": email}
        return c
    return client


def authorize(client, method="GET", uri="/workfarm/api/overview", origin=None):
    headers = {"X-Original-URI": uri, "X-Original-Method": method}
    if origin:
        headers["Origin"] = origin
    return client.get("/api/workfarm/authorize", headers=headers).status_code


def test_granted_user_may_read(farm):
    assert authorize(farm("viewer@example.test")) == 204


def test_user_without_grant_or_wrong_path_is_refused(farm):
    assert authorize(farm("other@example.test")) == 403
    assert authorize(farm("viewer@example.test"), uri="/termix/") == 403


def test_worker_actions_need_editor_and_controldeck_origin(farm):
    action = "/workfarm/api/workers/pc-47/pause"
    assert authorize(farm("viewer@example.test"), "POST", action, "https://control.example.test") == 403
    assert authorize(farm("admin@example.test"), "POST", action, "https://evil.example") == 403
    assert authorize(farm("admin@example.test"), "POST", action, "https://control.example.test") == 204
