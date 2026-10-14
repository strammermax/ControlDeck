import copy
import json
from pathlib import Path

import pytest

from backend.app import create_app
from backend.auth import database
from backend.dashboard_apps import available_apps, validate_app_references
from backend.dashboards import validate_dashboard
from backend.homepage import read_homepage_links
from backend.search import search_items

H = {"X-CSRF-Token": "csrf"}
LINK = {"id": 1, "name": "Jellyfin", "url": "https://media.example.test", "collection": "Media", "description": "Films en series", "icon": "jellyfin.png"}
APP = {"id": "app", "sectionId": "apps", "type": "app", "appId": 1, "x": 0, "y": 0, "width": 4, "height": 2}
DOC = {"title": "Mediawerk", "sections": [{"id": "apps", "title": "Apps", "lane": "main", "collapsed": False}], "items": [APP]}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.auth.Vault.from_env", classmethod(lambda cls: None))
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([
        {"email": "user@example.test", "role": "user", "modules": ["dashboard", "bookmarks"]},
        {"email": "other@example.test", "role": "user", "modules": ["dashboard", "bookmarks"]},
        {"email": "limited@example.test", "role": "user", "modules": ["dashboard"]},
        {"email": "bookmarks@example.test", "role": "user", "modules": ["bookmarks"]},
        {"email": "admin@example.test", "role": "admin"},
    ]))
    data = tmp_path / "data"
    app = create_app(data_dir=data, accounts_path=accounts)
    app.config["TESTING"] = True
    path = data / "homepage/links.json"
    path.parent.mkdir()
    path.write_text(json.dumps([LINK]))
    metadata = {"type": "jellyfin", "linkId": 1, "showApp": True, "summary": [{"label": "Films", "value": 12}], "apiKey": "synthetic-not-public"}
    with database(data / "users.sqlite3") as db:
        db.execute("INSERT INTO homepage_integrations (metadata,credentials) VALUES (?,?)", (json.dumps(metadata), "synthetic-encrypted-secret"))

    def client(email="user@example.test", application=app):
        c = application.test_client()
        if email:
            with c.session_transaction() as session:
                session["identity"] = {"sub": email, "email": email}
                session["csrf"] = "csrf"
        return c
    return client, data, accounts, path


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_shared_homepage_reader(setup, case):
    _, _, _, path = setup
    if case == "normaal":
        assert read_homepage_links(path)[0]["name"] == "Jellyfin"
    elif case == "boundary":
        assert read_homepage_links(path.with_name("missing.json")) == []
        path.write_text("[]")
        assert read_homepage_links(path) == []
        path.write_text(json.dumps([{**LINK, "id": i + 1} for i in range(500)]))
        assert len(read_homepage_links(path)) == 500
    else:
        for value in [{}, [LINK, LINK], [{**LINK, "url": "javascript:alert(1)"}], [{**LINK, "id": True}], [LINK] * 501]:
            path.write_text(json.dumps(value))
            with pytest.raises(ValueError):
                read_homepage_links(path)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_app_catalog_projection(setup, case):
    clients, data, _, path = setup
    c = clients()
    if case == "normaal":
        result = c.get("/api/dashboards/apps")
        assert result.status_code == 200
        assert result.json["apps"][0]["summary"] == [{"label": "Films", "value": 12}]
        assert "synthetic-not-public" not in result.text and "synthetic-encrypted-secret" not in result.text
    elif case == "boundary":
        assert clients("limited@example.test").get("/api/dashboards/apps").json == {"apps": [], "available": False, "warning": None}
        path.write_text("[]")
        assert c.get("/api/dashboards/apps").json["apps"] == []
    else:
        path.write_text("invalid json")
        result = c.get("/api/dashboards/apps")
        assert result.status_code == 503 and "invalid json" not in result.text


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_summary_failure_keeps_links(setup, case):
    clients, data, _, _ = setup
    if case == "normaal":
        metadata = {"linkId": 1, "showApp": True, "summary": [{"label": "Films", "value": 0}]}
    elif case == "boundary":
        metadata = {"linkId": 999, "showApp": True, "summary": []}
    else:
        metadata = {"linkId": 1, "showApp": True, "summary": [{"label": "Films", "value": True}]}
    with database(data / "users.sqlite3") as db:
        db.execute("UPDATE homepage_integrations SET metadata=?", (json.dumps(metadata),))
    value = clients().get("/api/dashboards/apps").json
    assert value["apps"][0]["url"] == LINK["url"]
    assert value["apps"][0]["summary"] == ([{"label": "Films", "value": 0}] if case == "normaal" else [])
    assert bool(value["warning"]) is (case == "faal")


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_reference_document_contract(case):
    if case == "normaal":
        assert validate_dashboard(DOC)["items"] == [APP]
        assert validate_app_references(DOC, [{"id": 1}]) == DOC
    elif case == "boundary":
        previous = copy.deepcopy(DOC)
        document = {**DOC, "items": [{**APP, "x": 8}]}
        assert validate_app_references(document, [], previous)["items"][0]["x"] == 8
        assert validate_app_references({**DOC, "items": []}, [], previous)["items"] == []
    else:
        for patch in [{"appId": 0}, {"appId": True}, {"appId": "1"}, {"url": "https://copied.example.test"}, {"title": "Copied"}]:
            with pytest.raises(ValueError):
                validate_dashboard({**DOC, "items": [{**APP, **patch}]})
        with pytest.raises(ValueError):
            validate_app_references(DOC, [])
        with pytest.raises(ValueError):
            validate_app_references({**DOC, "items": [{**APP, "appId": 2}]}, [], DOC)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_reference_save_and_source_changes(setup, case):
    clients, data, accounts, path = setup
    c = clients()
    bid = c.get("/api/dashboards").json["defaultId"]
    body = {**DOC, "revision": 1}
    if case == "normaal":
        response = c.put(f"/api/dashboards/{bid}", json=body, headers=H)
        assert response.status_code == 200 and response.json["dashboard"]["items"] == [APP]
        path.write_text(json.dumps([{**LINK, "name": "Media nieuw", "url": "https://new.example.test"}]))
        assert c.get("/api/dashboards/apps").json["apps"][0]["url"] == "https://new.example.test"
        assert c.get(f"/api/dashboards/{bid}").json["dashboard"]["items"] == [APP]
        duplicate = c.post("/api/dashboards", json={"title": "Copy", "sourceId": bid}, headers=H)
        assert duplicate.json["dashboard"]["items"] == [APP]
    elif case == "boundary":
        assert c.put(f"/api/dashboards/{bid}", json=body, headers=H).status_code == 200
        values = json.loads(accounts.read_text())
        next(row for row in values if row["email"] == "user@example.test")["modules"] = ["dashboard"]
        accounts.write_text(json.dumps(values))
        assert c.get("/api/dashboards/apps").json["apps"] == []
        assert c.put(f"/api/dashboards/{bid}", json={**DOC, "revision": 2, "title": "Renamed"}, headers=H).status_code == 200
        with database(data / "users.sqlite3") as db:
            raw = db.execute("SELECT document FROM dashboards WHERE id=?", (bid,)).fetchone()[0]
            assert "media.example.test" not in raw and "Jellyfin" not in raw
    else:
        assert clients("limited@example.test").get("/api/dashboards").status_code == 200
        limited = clients("limited@example.test")
        lid = limited.get("/api/dashboards").json["defaultId"]
        assert limited.put(f"/api/dashboards/{lid}", json=body, headers=H).status_code == 400
        assert c.put(f"/api/dashboards/{bid}", json={**body, "items": [{**APP, "appId": 999}]}, headers=H).status_code == 400
        path.write_text("invalid")
        assert c.put(f"/api/dashboards/{bid}", json=body, headers=H).status_code == 503
        assert c.get(f"/api/dashboards/{bid}").json["dashboard"]["revision"] == 1


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_search_matching(case):
    items = [{"title": "Jellyfin", "description": "Films en series"}, {"title": "Één werkplek", "description": "Portaal"}]
    if case == "normaal":
        assert search_items(items, "series JELLYFIN") == [items[0]]
    elif case == "boundary":
        assert search_items(items, "  ") == []
        assert search_items(items, "ÉÉN") == [items[1]]
        assert len(search_items(items * 30, "films")) == 30
        assert len(search_items(items * 60, "films")) == 50
    else:
        for query in [None, 1, "x" * 201, "secret\nvalue"]:
            with pytest.raises(ValueError):
                search_items(items, query)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_search_endpoint_and_partial_failure(setup, case):
    clients, _, _, path = setup
    c = clients()
    bid = c.get("/api/dashboards").json["defaultId"]
    assert c.put(f"/api/dashboards/{bid}", json={**DOC, "revision": 1}, headers=H).status_code == 200
    if case == "normaal":
        results = c.get("/api/search?q=Media").json["results"]
        assert {row["kind"] for row in results} == {"app", "dashboard"}
        assert next(row for row in results if row["kind"] == "dashboard")["dashboardId"] == bid
        assert "synthetic-" not in c.get("/api/search?q=Media").text
        assert c.get("/api/search?q=Bookmarks").json["results"][0]["route"] == "bookmarks"
    elif case == "boundary":
        assert c.get("/api/search?q=").json == {"results": [], "warnings": []}
        assert c.get("/api/search", query_string={"q": "x" * 200}).status_code == 200
        path.write_text("invalid")
        value = c.get("/api/search?q=Mediawerk").json
        assert value["results"][0]["dashboardId"] == bid and value["warnings"]
    else:
        for url in ["/api/search", "/api/search?q=a&q=b", "/api/search?q=x&extra=y", "/api/search?q=%0A"]:
            assert c.get(url).status_code == 400
        assert c.get("/api/search", query_string={"q": "x" * 201}).status_code == 400


def test_search_authorization_and_anonymous_access(setup):
    clients, _, accounts, _ = setup
    c = clients()
    bid = c.get("/api/dashboards").json["defaultId"]
    c.put(f"/api/dashboards/{bid}", json={**DOC, "revision": 1}, headers=H)
    assert clients(None).get("/api/search?q=Media").status_code == 401
    assert clients(None).get("/api/dashboards/apps").status_code == 401
    assert clients("bookmarks@example.test").get("/api/dashboards/apps").status_code == 403
    assert clients("other@example.test").get("/api/search?q=Mediawerk").json["results"] == []
    assert clients("limited@example.test").get("/api/search?q=Jellyfin").json["results"] == []
    assert clients("user@example.test").get("/api/search?q=Admin").json["results"] == []
    assert clients("bookmarks@example.test").get("/api/search?q=Dashboard").json["results"] == []
    assert clients("admin@example.test").get("/api/search?q=Modulebeheer").json["results"]
    rows = json.loads(accounts.read_text())
    next(row for row in rows if row["email"] == "user@example.test")["enabled"] = False
    accounts.write_text(json.dumps(rows))
    assert c.get("/api/search?q=Media").status_code == 401


def test_deleted_app_reference_regression_cannot_point_at_a_new_app_with_reused_id(setup):
    """Deleting the highest link reused max(current)+1, silently retargeting dashboard references."""
    clients, _, _, _ = setup
    c = clients("admin@example.test")
    bid = c.get("/api/dashboards").json["defaultId"]
    assert c.put(f"/api/dashboards/{bid}", json={**DOC, "revision": 1}, headers=H).status_code == 200
    assert c.delete("/api/homepage/links/1", headers=H).status_code == 200
    created = c.post("/api/homepage/links", json={key: value for key, value in {**LINK, "name": "Other app"}.items() if key != "id"}, headers=H)
    assert created.status_code == 201
    assert created.json["links"][0]["id"] > 1
    assert c.get(f"/api/dashboards/{bid}").json["dashboard"]["items"][0]["appId"] == 1
    assert all(row["id"] != 1 for row in c.get("/api/dashboards/apps").json["apps"])


def test_homepage_head_regression_is_read_only(setup):
    """HEAD previously fell through the GET check into the mutation/delete dispatch."""
    clients, data, _, _ = setup
    c = clients("admin@example.test")
    with database(data / "users.sqlite3") as db:
        before = db.execute("SELECT last_id FROM homepage_link_sequence").fetchone()[0]
    response = c.head("/api/homepage/links")
    assert response.status_code == 200 and response.data == b""
    with database(data / "users.sqlite3") as db:
        assert db.execute("SELECT last_id FROM homepage_link_sequence").fetchone()[0] == before


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_upgrade_allocator_seeds_existing_and_deleted_references(setup, case):
    clients, data, _, path = setup
    from backend.dashboards import migrate_dashboards
    c = clients("admin@example.test")
    bid = c.get("/api/dashboards").json["defaultId"]
    with database(data / "users.sqlite3") as db:
        db.execute("DROP TABLE homepage_link_sequence")
        db.execute("UPDATE dashboard_schema SET version=2")
        if case == "normaal":
            db.execute("UPDATE dashboards SET document=? WHERE id=?", (json.dumps({**DOC, "items": [{**APP, "appId": 7}]}), bid))
        elif case == "boundary":
            db.execute("UPDATE homepage_integrations SET metadata=?", (json.dumps({"linkId": 8}),))
            path.with_name("links.previous.json").write_text(json.dumps([{**LINK, "id": 9}]))
        else:
            db.execute("UPDATE homepage_integrations SET metadata='invalid'")
            path.with_name("links.previous.json").write_text("invalid")
    migrate_dashboards(data / "users.sqlite3")
    result = c.post("/api/homepage/links", json={key: value for key, value in LINK.items() if key != "id"}, headers=H)
    assert result.status_code == 201
    assert result.json["links"][-1]["id"] == (8 if case == "normaal" else 10 if case == "boundary" else 2)
