"""Modules reuse existing provider access; storing a widget never grants that access."""
import copy
import json
import pytest
from backend.dashboards import validate_dashboard
from test_dashboard_apps_search import setup, DOC, H

MODULE = {"id": "links", "sectionId": "apps", "type": "module", "moduleId": "linkwarden", "settings": {"collectionId": None}, "x": 0, "y": 0, "width": 12, "height": 5}


@pytest.mark.parametrize("view", ["nodes", "guests", "tasks", "all", "health"])
def test_proxmox_module_normal_views(view):
    item = {**MODULE, "moduleId": "proxmox", "settings": {"view": view}}
    assert validate_dashboard({**DOC, "items": [item]})["items"] == [item]


@pytest.mark.parametrize("settings", [None, {}, {"view": []}, {"view": True}, {"view": "unknown"}, {"view": "nodes", "token": "synthetic"}])
def test_proxmox_module_failure_rejects_settings_and_credentials(settings):
    with pytest.raises(ValueError):
        validate_dashboard({**DOC, "items": [{**MODULE, "moduleId": "proxmox", "settings": settings}]})


def test_proxmox_module_permission_persistence_and_revocation(setup):
    clients, _, accounts, _ = setup
    rows = json.loads(accounts.read_text())
    rows[0]["modules"].append("proxmox")
    accounts.write_text(json.dumps(rows))
    user = clients()
    board = user.get("/api/dashboards").json["dashboards"][0]
    url = "/api/dashboards/" + board["id"]
    item = {**MODULE, "moduleId": "proxmox", "settings": {"view": "health"}}
    body = {**DOC, "items": [item], "revision": board["revision"]}
    saved = user.put(url, json=body, headers=H)
    assert saved.status_code == 200
    assert user.get(url).json["dashboard"]["items"] == [item]
    assert clients(None).get("/api/proxmox/summary").status_code == 401
    assert clients(None).get("/api/proxmenux/summary").status_code == 401
    assert clients("other@example.test").get(url).status_code == 404
    assert user.put(url, json={**body, "revision": saved.json["dashboard"]["revision"]}).status_code == 403
    rows[0]["modules"].remove("proxmox")
    accounts.write_text(json.dumps(rows))
    for endpoint in ("/api/proxmox/summary", "/api/proxmenux/summary"):
        assert user.get(endpoint).status_code == 403
    changed = {**body, "revision": saved.json["dashboard"]["revision"], "items": [{**item, "settings": {"view": "nodes"}}]}
    assert user.put(url, json=changed, headers=H).status_code == 400
    # A revoked source remains removable without granting access to its data.
    assert user.put(url, json={**changed, "items": []}, headers=H).status_code == 200


@pytest.mark.parametrize("collection", [None, 1, 9999999999])
def test_linkwarden_module_normal_and_boundary(collection):
    document = validate_dashboard({**DOC, "items": [{**MODULE, "settings": {"collectionId": collection}}]})
    assert document["items"][0]["settings"]["collectionId"] == collection


@pytest.mark.parametrize("patch", [{"moduleId": "unknown"}, {"moduleId": []}, {"settings": None}, {"settings": {}}, {"settings": {"collectionId": True}}, {"settings": {"collectionId": -1}}, {"settings": {"collectionId": 10000000000}}, {"settings": {"collectionId": "1"}}, {"settings": {"collectionId": None, "token": "synthetic"}}])
def test_module_failure_rejects_unknown_features_and_credential_settings(patch):
    with pytest.raises(ValueError):
        validate_dashboard({**DOC, "items": [{**MODULE, **patch}]})


def test_module_save_restart_duplicate_and_owner_isolation(setup):
    clients, data, accounts, _ = setup
    user = clients()
    board = user.get("/api/dashboards").json["dashboards"][0]
    url = "/api/dashboards/" + board["id"]
    body = {**DOC, "items": [MODULE], "revision": board["revision"]}
    saved = user.put(url, json=body, headers=H)
    assert saved.status_code == 200
    assert user.get(url).json["dashboard"]["items"] == [MODULE]
    assert user.put(url, json=body, headers=H).status_code == 409
    assert clients("other@example.test").get(url).status_code == 404
    assert clients(None).get(url).status_code == 401
    assert user.put(url, json={**body, "revision": saved.json["dashboard"]["revision"]}).status_code == 403
    duplicated = user.post("/api/dashboards", json={"title": "Copy", "sourceId": board["id"]}, headers=H)
    assert duplicated.status_code == 201 and duplicated.json["dashboard"]["items"] == [MODULE]
    from backend.app import create_app
    restarted = create_app(data_dir=data, accounts_path=accounts)
    assert clients(application=restarted).get(url).json["dashboard"]["items"] == [MODULE]


def test_module_permissions_revocation_and_unrelated_edits(setup):
    clients, _, accounts, _ = setup
    limited = clients("limited@example.test")
    board = limited.get("/api/dashboards").json["dashboards"][0]
    assert limited.put("/api/dashboards/" + board["id"], json={**DOC, "items": [MODULE], "revision": board["revision"]}, headers=H).status_code == 400
    user = clients()
    board = user.get("/api/dashboards").json["dashboards"][0]
    url = "/api/dashboards/" + board["id"]
    saved = user.put(url, json={**DOC, "items": [MODULE], "revision": board["revision"]}, headers=H).json["dashboard"]
    rows = json.loads(accounts.read_text())
    for row in rows:
        if row["email"] == "user@example.test": row["modules"] = ["dashboard"]
    accounts.write_text(json.dumps(rows))
    assert user.get("/api/linkwarden/collections").status_code == 403
    assert user.get("/api/linkwarden/bookmarks").status_code == 403
    moved = {**MODULE, "y": 1}
    changed = user.put(url, json={**DOC, "items": [moved], "revision": saved["revision"]}, headers=H)
    assert changed.status_code == 200
    denied = user.put(url, json={**DOC, "items": [{**moved, "settings": {"collectionId": 1}}], "revision": changed.json["dashboard"]["revision"]}, headers=H)
    assert denied.status_code == 400
    assert user.put(url, json={**DOC, "items": [], "revision": changed.json["dashboard"]["revision"]}, headers=H).status_code == 200


from test_linkwarden import env as linkwarden_env, TOKEN


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_module_uses_existing_personal_linkwarden_api(linkwarden_env, case):
    clients, responses, calls, data = linkwarden_env
    accounts = data.parent / "accounts.json"
    rows = json.loads(accounts.read_text())
    rows[1]["modules"] = ["dashboard", "bookmarks"]
    accounts.write_text(json.dumps(rows))
    user = clients()
    assert user.put("/api/linkwarden/token", json={"token": TOKEN}, headers=H).status_code == 200
    board = user.get("/api/dashboards").json["dashboards"][0]
    document = {**DOC, "items": [{**MODULE, "settings": {"collectionId": 1}}], "revision": board["revision"]}
    result = user.put("/api/dashboards/" + board["id"], json=document, headers=H)
    assert result.status_code == 200 and TOKEN not in result.get_data(as_text=True)
    assert len(list((data / "linkwarden/users").glob("*.json"))) == 1
    if case == "boundary":
        responses["/search"] = {"data": {"links": [], "nextCursor": None}}
    if case == "faal":
        responses["/users/me"] = {"response": {"email": "other@example.test"}}
    response = user.get("/api/linkwarden/bookmarks?collection=1")
    if case == "faal":
        assert response.status_code == 502 and "links" not in response.json
    else:
        assert response.status_code == 200
        assert len(response.json["links"]) == (0 if case == "boundary" else 1)
        assert next(call for call in calls if call[1].endswith("/search"))[2]["params"]["collectionId"] == "1"
    assert TOKEN not in response.get_data(as_text=True)
