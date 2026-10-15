"""Independent system widgets reuse Proxmox resources without granting access."""
import json
import pytest
from backend.dashboards import validate_dashboard
from test_dashboard_apps_search import setup, DOC, H
from test_dashboard_modules import MODULE


@pytest.mark.parametrize("metric", ["cpu", "memory", "temperature", "power"])
@pytest.mark.parametrize("node", ["", "pve-test", "a" * 64])
def test_system_settings_normal_and_boundary(metric, node):
    item = {**MODULE, "moduleId": "system", "settings": {"metric": metric, "node": node}}
    assert validate_dashboard({**DOC, "items": [item]})["items"] == [item]


@pytest.mark.parametrize("settings", [None, {}, {"metric": "cpu"}, {"metric": [], "node": ""}, {"metric": "token", "node": ""}, {"metric": "cpu", "node": True}, {"metric": "cpu", "node": "../secret"}, {"metric": "cpu", "node": "a" * 65}, {"metric": "cpu", "node": "", "url": "https://example.test"}])
def test_system_settings_failure_rejects_unknown_fields_and_browser_targets(settings):
    with pytest.raises(ValueError):
        validate_dashboard({**DOC, "items": [{**MODULE, "moduleId": "system", "settings": settings}]})


def test_system_widgets_save_independently_duplicate_restart_and_authorization(setup):
    clients, data, accounts, _ = setup
    rows = json.loads(accounts.read_text())
    rows[0]["modules"].append("proxmox")
    accounts.write_text(json.dumps(rows))
    user = clients()
    board = user.get("/api/dashboards").json["dashboards"][0]
    url = "/api/dashboards/" + board["id"]
    items = [{**MODULE, "id": "cpu", "moduleId": "system", "settings": {"metric": "cpu", "node": "pve-test"}}, {**MODULE, "id": "sensor", "y": 5, "moduleId": "system", "settings": {"metric": "temperature", "node": ""}}]
    body = {**DOC, "items": items, "revision": board["revision"]}
    assert user.put(url, json=body).status_code == 403
    saved = user.put(url, json=body, headers=H)
    assert saved.status_code == 200
    assert user.get(url).json["dashboard"]["items"] == items
    copy = user.post("/api/dashboards", json={"title": "Copy", "sourceId": board["id"]}, headers=H)
    assert copy.status_code == 201 and copy.json["dashboard"]["items"] == items
    from backend.app import create_app
    assert clients(application=create_app(data_dir=data, accounts_path=accounts)).get(url).json["dashboard"]["items"] == items
    assert clients(None).get(url).status_code == 401
    assert clients("other@example.test").get(url).status_code == 404
    rows[0]["modules"].remove("proxmox")
    accounts.write_text(json.dumps(rows))
    for endpoint in ("/api/proxmox/summary", "/api/proxmenux/summary"):
        assert user.get(endpoint).status_code == 403
    changed = {**body, "revision": saved.json["dashboard"]["revision"], "items": [{**items[0], "settings": {"metric": "memory", "node": ""}}]}
    assert user.put(url, json=changed, headers=H).status_code == 400
    assert user.put(url, json={**changed, "items": []}, headers=H).status_code == 200
