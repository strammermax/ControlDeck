"""One-click login uses trusted vault targets and the current verified identity only."""
import json
import shutil
from pathlib import Path
from unittest.mock import Mock
import pytest
import requests
from backend.app import create_app
from backend.modules.kasm import launch_login as kasm_login
from backend.modules.nextcloud import launch_login as nextcloud_login

H = {"X-CSRF-Token": "csrf"}
USER_ID = "12345678-1234-4234-8234-123456789abc"
KASM = {"url": "https://kasm.example.test", "apiKey": "synthetic-api-key", "apiSecret": "synthetic-api-secret", "users": {"user@example.test": USER_ID}}
NEXTCLOUD = {"url": "https://cloud.example.test", "loginPath": "/index.php/apps/user_oidc/login/1"}
LOGIN_URL = "https://kasm.example.test/#/connect/login/dash/test-user/synthetic-login-token"


@pytest.fixture
def launch_env(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.auth.Vault.from_env", classmethod(lambda cls: None))
    config = tmp_path / "config"
    shutil.copytree(Path(__file__).resolve().parents[1] / "config", config)
    for module in ("kasm", "nextcloud"):
        p = config / "providers" / (module + ".json")
        value = json.loads(p.read_text());value.update(enabled=True, url=f"https://{module}.example.test")
        p.write_text(json.dumps(value))
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([{"email":"user@example.test","role":"user","modules":["dashboard","kasm","nextcloud"]},{"email":"denied@example.test","role":"user","modules":["dashboard"]},{"email":"admin@example.test","role":"admin"}]))
    app = create_app(config_path=config / "controldeck.json", data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True
    vault = Mock();vault.read.return_value = {"CONTROLDECK_APP_LAUNCHES": json.dumps({"kasm": KASM, "nextcloud": NEXTCLOUD})}
    app.extensions["controldeck_vault"] = vault
    post = Mock(return_value=Mock(status_code=200,json=Mock(return_value={"url": LOGIN_URL})))
    monkeypatch.setattr("backend.modules.kasm.requests.post", post)
    def client(email="user@example.test"):
        c=app.test_client()
        if email:
            with c.session_transaction() as session:
                session["identity"]={"sub":email,"email":email};session["csrf"]="csrf"
        return c
    return client,app,vault,post


def test_kasm_launch_normal_personal_account_and_no_secret_response(launch_env):
    # Regression: the global response hook overwrote a launch adapter's stricter no-referrer policy.
    client,_,_,post=launch_env
    response=client().post("/api/app-launches/kasm",json={},headers=H)
    assert response.status_code==200 and response.json=={"url":LOGIN_URL}
    assert response.headers["Cache-Control"]=="no-store" and response.headers["Referrer-Policy"]=="no-referrer"
    assert post.call_args.kwargs["json"]["target_user"]=={"user_id":USER_ID}
    assert post.call_args.kwargs["allow_redirects"] is False and post.call_args.kwargs["timeout"]==10
    assert "verify" not in post.call_args.kwargs
    assert KASM["apiKey"] not in response.get_data(as_text=True) and KASM["apiSecret"] not in response.get_data(as_text=True)


def test_nextcloud_launch_normal_uses_configured_oidc_and_no_upstream_password(launch_env):
    client,_,_,post=launch_env
    response=client().post("/api/app-launches/nextcloud",json={},headers=H)
    assert response.status_code==200 and response.json["url"]==NEXTCLOUD["url"]+NEXTCLOUD["loginPath"]
    post.assert_not_called()


def test_launch_authentication_authorization_and_csrf(launch_env):
    client,_,vault,post=launch_env
    assert client(None).post("/api/app-launches/kasm",json={},headers=H).status_code==401
    assert client("denied@example.test").post("/api/app-launches/kasm",json={},headers=H).status_code==403
    assert client().post("/api/app-launches/kasm",json={}).status_code==403
    assert client("admin@example.test").post("/api/app-launches/kasm",json={},headers=H).status_code==403
    post.assert_not_called()


@pytest.mark.parametrize("body",[None,[],{"email":"admin@example.test"},{"url":"https://other.example.test"},{"user_id":USER_ID}])
def test_launch_failure_browser_cannot_select_identity_or_target(launch_env,body):
    client,_,vault,post=launch_env
    assert client().post("/api/app-launches/kasm",json=body,headers=H).status_code==400
    post.assert_not_called();vault.read.assert_not_called()


def test_launch_boundary_missing_vault_unknown_module_and_bad_configuration(launch_env):
    client,app,vault,post=launch_env
    assert client().post("/api/app-launches/unknown",json={},headers=H).status_code==404
    vault.read.return_value={"CONTROLDECK_APP_LAUNCHES":"[]"}
    assert client().post("/api/app-launches/kasm",json={},headers=H).status_code==503
    app.extensions["controldeck_vault"]=None
    assert client().post("/api/app-launches/kasm",json={},headers=H).status_code==503
    post.assert_not_called()


@pytest.mark.parametrize("url",["https://evil.example.test/#/connect/login/dash/a/b","javascript:alert(1)","https://kasm.example.test/?password=secret","https://kasm.example.test/#/admin","https://u:p@kasm.example.test/#/connect/login/dash/a/b"])
def test_kasm_failure_rejects_redirects_to_untrusted_hosts_or_routes(launch_env,url):
    client,_,_,post=launch_env
    post.return_value.json.return_value={"url":url}
    response=client().post("/api/app-launches/kasm",json={},headers=H)
    assert response.status_code==503 and "url" not in response.json and "evil" not in response.get_data(as_text=True)


@pytest.mark.parametrize("failure",[requests.Timeout(),requests.exceptions.SSLError(),ValueError("synthetic-private-error")])
def test_launch_upstream_failure_never_reflects_details(launch_env,failure):
    client,_,_,post=launch_env;post.side_effect=failure
    response=client().post("/api/app-launches/kasm",json={},headers=H)
    assert response.status_code==503 and "synthetic-private-error" not in response.get_data(as_text=True)


def test_kasm_boundary_maximum_supported_login_fragment(launch_env):
    client,_,_,post=launch_env
    post.return_value.json.return_value={"url":"https://kasm.example.test/#/connect/login/dash/"+"a"*128+"/"+"b"*512}
    assert client().post("/api/app-launches/kasm",json={},headers=H).status_code==200


@pytest.mark.parametrize("patch",[{"url":"http://kasm.example.test"},{"url":"https://kasm.example.test:bad"},{"apiSecret":""},{"users":{}},{"users":{"user@example.test":"bad"}}])
def test_kasm_configuration_rejection(launch_env,patch):
    client,_,vault,post=launch_env
    vault.read.return_value={"CONTROLDECK_APP_LAUNCHES":json.dumps({"kasm":{**KASM,**patch}})}
    assert client().post("/api/app-launches/kasm",json={},headers=H).status_code in (403,503)
    post.assert_not_called()


@pytest.mark.parametrize("path",["/apps/user_oidc/login/1","/index.php/apps/user_oidc/login/9999999999"])
def test_nextcloud_boundary_supported_routes(path):
    assert nextcloud_login({**NEXTCLOUD,"loginPath":path},{})==NEXTCLOUD["url"]+path


@pytest.mark.parametrize("patch",[{"url":"http://cloud.example.test"},{"loginPath":"//evil.example.test"},{"loginPath":"/login?user=x&password=y"},{"loginPath":"/apps/user_oidc/login/0"},{"password":"synthetic"}])
def test_nextcloud_failure_no_arbitrary_or_password_login(patch):
    with pytest.raises(ValueError):nextcloud_login({**NEXTCLOUD,**patch},{})


def test_disabled_provider_and_vault_failure_fail_closed(launch_env, tmp_path):
    from backend.vault import VaultError
    client,_,vault,post=launch_env
    vault.read.side_effect=VaultError("synthetic-private-vault-detail")
    response=client().post("/api/app-launches/kasm",json={},headers=H)
    assert response.status_code==503 and "synthetic-private-vault-detail" not in response.get_data(as_text=True)
    post.assert_not_called()
    vault.read.reset_mock()
    provider = tmp_path / "config/providers/kasm.json"
    value = json.loads(provider.read_text());value["enabled"] = False
    provider.write_text(json.dumps(value))
    assert client().post("/api/app-launches/kasm",json={},headers=H).status_code == 403
    vault.read.assert_not_called()


@pytest.mark.parametrize("module_id",["kasm","nextcloud"])
def test_launch_modules_accept_only_empty_dashboard_settings(module_id):
    from backend.dashboards import validate_dashboard
    from test_dashboard_apps_search import DOC
    module={"id":"launch","sectionId":"apps","type":"module","moduleId":module_id,"settings":{},"x":0,"y":0,"width":4,"height":2}
    assert validate_dashboard({**DOC,"items":[module]})["items"][0]["moduleId"]==module_id
    for settings in [{"password":"synthetic"},{"user_id":USER_ID},None]:
        with pytest.raises(ValueError):validate_dashboard({**DOC,"items":[{**module,"settings":settings}]})
