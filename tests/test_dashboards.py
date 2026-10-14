import copy
import json
import sqlite3

import pytest

from backend.app import create_app
from backend.auth import database
from backend.dashboards import MAX_BODY, migrate_dashboards, validate_dashboard

H = {"X-CSRF-Token": "csrf"}
DOCUMENT = {"title": "Werk", "sections": [{"id": "apps", "title": "Apps", "lane": "main", "collapsed": False}], "items": []}
ITEM = {"id": "app-1", "sectionId": "apps", "type": "link", "title": "Portal", "url": "https://portal.example.test", "description": "Werkplek", "x": 0, "y": 0, "width": 4, "height": 1}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.auth.Vault.from_env", classmethod(lambda cls: None))
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([
        {"email": "admin@example.test", "role": "admin"},
        {"email": "editor@example.test", "role": "editor"},
        {"email": "user@example.test", "role": "user", "modules": ["dashboard"]},
        {"email": "other@example.test", "role": "user", "modules": ["dashboard"]},
        {"email": "denied@example.test", "role": "user", "modules": ["bookmarks"]},
    ]))
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True

    def client(email="user@example.test", application=app):
        c = application.test_client()
        if email:
            with c.session_transaction() as session:
                session["identity"] = {"sub": "subject-" + email, "email": email}
                session["csrf"] = "csrf"
        return c
    return client, tmp_path, accounts


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_document_validation(case):
    if case == "normaal":
        result = validate_dashboard({**DOCUMENT, "title": " Werk ", "items": [ITEM]})
        assert result["title"] == "Werk" and result["items"][0]["url"] == ITEM["url"]
    elif case == "boundary":
        value = {**DOCUMENT, "title": "n" * 100, "items": [{**ITEM, "x": 0, "y": 94, "width": 12, "height": 6}]}
        assert validate_dashboard(value)["items"][0]["y"] == 94
        assert validate_dashboard(DOCUMENT)["items"] == []
        sections = [{"id": f"s-{i}", "title": "S", "lane": "left" if i % 2 else "right", "collapsed": True} for i in range(20)]
        assert len(validate_dashboard({**DOCUMENT, "sections": sections})["sections"]) == 20
    else:
        for patch in [{"title": " "}, {"title": "n" * 101}, {"sections": []}, {"sections": DOCUMENT["sections"] * 2}, {"extra": True}]:
            with pytest.raises(ValueError):
                validate_dashboard({**DOCUMENT, **patch})
        with pytest.raises(ValueError):
            validate_dashboard(None)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_grid_and_link_validation(case):
    if case == "normaal":
        items = [ITEM, {**ITEM, "id": "app-2", "x": 4}]
        assert len(validate_dashboard({**DOCUMENT, "items": items})["items"]) == 2
    elif case == "boundary":
        items = [{**ITEM, "id": f"app-{i}", "x": 0, "y": i, "width": 12} for i in range(100)]
        assert len(validate_dashboard({**DOCUMENT, "items": items})["items"]) == 100
    else:
        for patch in [{"x": -1}, {"x": 9}, {"y": 100}, {"height": 7}, {"width": True}, {"x": 0.5}, {"sectionId": "missing"}, {"type": "script"},
                      {"url": "javascript:alert(1)"}, {"url": "https://user:secret@example.test"}, {"url": "https://example.test/?api_key=private"},
                      {"url": "https://example.test/a b"}, {"url": "https://example.test:99999"}]:
            with pytest.raises(ValueError):
                validate_dashboard({**DOCUMENT, "items": [{**ITEM, **patch}]})
        for second in [ITEM, {**ITEM, "id": "overlap"}]:
            with pytest.raises(ValueError):
                validate_dashboard({**DOCUMENT, "items": [ITEM, second]})


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_dashboards_create_duplicate_limits(setup, case):
    clients, _, _ = setup
    c = clients()
    initial = c.get("/api/dashboards").json
    assert [b["title"] for b in initial["dashboards"]] == ["Werk", "Homelab"]
    assert initial["defaultId"] == initial["dashboards"][0]["id"]
    if case == "normaal":
        bid = initial["defaultId"]
        assert c.put(f"/api/dashboards/{bid}", json={**DOCUMENT, "items": [ITEM], "revision": 1}, headers=H).status_code == 200
        duplicate = c.post("/api/dashboards", json={"title": "Kopie", "sourceId": bid}, headers=H)
        assert duplicate.status_code == 201
        assert duplicate.json["dashboard"]["items"] == [ITEM]
        assert duplicate.json["dashboard"]["id"] != bid
    elif case == "boundary":
        for i in range(18):
            assert c.post("/api/dashboards", json={"title": f"Board {i}"}, headers=H).status_code == 201
        assert c.post("/api/dashboards", json={"title": "Too many"}, headers=H).status_code == 400
        assert len(c.get("/api/dashboards").json["dashboards"]) == 20
    else:
        for body in [{"title": ""}, {"title": "New", "sourceId": 1}, {"title": "New", "unexpected": True}, []]:
            assert c.post("/api/dashboards", json=body, headers=H).status_code == 400
        assert c.post("/api/dashboards", json={"title": "New", "sourceId": "missing"}, headers=H).status_code == 404
        assert len(c.get("/api/dashboards").json["dashboards"]) == 2


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_edit_revision_and_persistence(setup, case):
    clients, tmp, accounts = setup
    c = clients()
    bid = c.get("/api/dashboards").json["defaultId"]
    body = {**DOCUMENT, "revision": 1, "items": [ITEM]}
    if case == "normaal":
        edited = c.put(f"/api/dashboards/{bid}", json=body, headers=H)
        assert edited.status_code == 200 and edited.json["dashboard"]["revision"] == 2
        restarted = create_app(data_dir=tmp / "data", accounts_path=accounts)
        assert clients(application=restarted).get(f"/api/dashboards/{bid}").json["dashboard"]["items"] == [ITEM]
    elif case == "boundary":
        assert c.put(f"/api/dashboards/{bid}", json={**body, "title": "X" * 100}, headers=H).status_code == 200
        stale = c.put(f"/api/dashboards/{bid}", json=body, headers=H)
        assert stale.status_code == 409 and stale.json["code"] == "revision_conflict"
        assert c.delete(f"/api/dashboards/{bid}", json={"revision": 1}, headers=H).status_code == 409
        assert c.get(f"/api/dashboards/{bid}").json["dashboard"]["title"] == "X" * 100
    else:
        assert c.put(f"/api/dashboards/{bid}", json={**body, "items": [{**ITEM, "url": "file:///secret"}]}, headers=H).status_code == 400
        assert c.get(f"/api/dashboards/{bid}").json["dashboard"]["revision"] == 1
        assert c.put(f"/api/dashboards/{bid}", data="invalid", content_type="application/json", headers=H).status_code == 400
        assert c.put(f"/api/dashboards/{bid}", data="x" * (MAX_BODY + 1), content_type="application/json", headers=H).status_code == 413


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_defaults_and_deletion(setup, case):
    clients, _, _ = setup
    c = clients()
    boards = c.get("/api/dashboards").json["dashboards"]
    bid = boards[1]["id"]
    if case == "normaal":
        assert c.put("/api/dashboards/default", json={"id": bid}, headers=H).json["defaultId"] == bid
        assert c.get("/api/dashboards").json["defaultId"] == bid
        assert c.delete(f"/api/dashboards/{bid}", json={"revision": 1}, headers=H).status_code == 200
        assert c.get("/api/dashboards").json["defaultId"] == boards[0]["id"]
    elif case == "boundary":
        for board in boards:
            assert c.delete(f"/api/dashboards/{board['id']}", json={"revision": 1}, headers=H).status_code == 200
        assert c.get("/api/dashboards").json == {"dashboards": [], "defaultId": None}
        assert c.post("/api/dashboards", json={"title": "Fresh"}, headers=H).status_code == 201
        assert len(c.get("/api/dashboards").json["dashboards"]) == 1
    else:
        assert c.put("/api/dashboards/default", json={"id": "missing"}, headers=H).status_code == 404
        assert c.put("/api/dashboards/default", json={"id": 1}, headers=H).status_code == 400
        assert c.delete(f"/api/dashboards/{bid}", json={"revision": 1, "extra": True}, headers=H).status_code == 400


@pytest.mark.parametrize("role", ["admin", "editor", "user"])
def test_owner_isolation_and_role_access(setup, role):
    clients, _, _ = setup
    c = clients(f"{role}@example.test")
    bid = c.get("/api/dashboards").json["defaultId"]
    other = clients("other@example.test")
    assert bid not in [b["id"] for b in other.get("/api/dashboards").json["dashboards"]]
    for method, body in [("get", None), ("put", {**DOCUMENT, "revision": 1}), ("delete", {"revision": 1})]:
        assert getattr(other, method)(f"/api/dashboards/{bid}", json=body, headers=H).status_code == 404
    assert other.post("/api/dashboards", json={"title": "Steal", "sourceId": bid}, headers=H).status_code == 404
    assert other.put("/api/dashboards/default", json={"id": bid}, headers=H).status_code == 404


def test_auth_csrf_module_and_revocation(setup):
    clients, _, accounts = setup
    assert clients(None).get("/api/dashboards").status_code == 401
    assert clients("denied@example.test").get("/api/dashboards").status_code == 403
    c = clients()
    bid = c.get("/api/dashboards").json["defaultId"]
    assert c.post("/api/dashboards", json={"title": "No csrf"}).status_code == 403
    assert c.put(f"/api/dashboards/{bid}", json={**DOCUMENT, "revision": 1}, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    values = json.loads(accounts.read_text())
    next(v for v in values if v["email"] == "user@example.test")["enabled"] = False
    accounts.write_text(json.dumps(values))
    assert c.get(f"/api/dashboards/{bid}").status_code == 401


def test_head_regression_does_not_require_a_mutation_body(setup):
    """HEAD was treated as a write because record dispatch checked only GET."""
    clients, _, _ = setup
    c = clients()
    bid = c.get("/api/dashboards").json["defaultId"]
    response = c.head(f"/api/dashboards/{bid}")
    assert response.status_code == 200 and response.data == b""
    assert c.head("/api/dashboards/missing").status_code == 404
    assert clients(None).head(f"/api/dashboards/{bid}").status_code == 401


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_schema_backup_and_recovery(tmp_path, monkeypatch, case):
    path = tmp_path / "users.sqlite3"
    with database(path) as db:
        db.execute("INSERT INTO users VALUES ('subject', 'user@example.test', ?)", (json.dumps({"theme": "dark"}),))
    if case == "faal":
        original = type(path).touch
        def fail_backup(self, *args, **kwargs):
            if self.parent.name == "backups":
                raise PermissionError("simulated read-only backup directory")
            return original(self, *args, **kwargs)
        monkeypatch.setattr(type(path), "touch", fail_backup)
        with pytest.raises(PermissionError):
            migrate_dashboards(path)
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT 1 FROM sqlite_master WHERE name='dashboards'").fetchone() is None
        return
    migrate_dashboards(path)
    snapshots = list((tmp_path / "backups").glob("*.sqlite3"))
    assert len(snapshots) == 1
    # Open the real backup as a fresh database; don't merely check file existence.
    with sqlite3.connect(snapshots[0]) as restored:
        assert json.loads(restored.execute("SELECT preferences FROM users").fetchone()[0]) == {"theme": "dark"}
        assert restored.execute("SELECT 1 FROM sqlite_master WHERE name='dashboards'").fetchone() is None
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    if case == "boundary":
        migrate_dashboards(path)
        assert len(list((tmp_path / "backups").glob("*.sqlite3"))) == 1
        with sqlite3.connect(path) as db:
            db.execute("UPDATE dashboard_schema SET version=99")
        with pytest.raises(ValueError, match="schemaversie"):
            migrate_dashboards(path)


def png_icon(width=1, height=1):
    import base64, struct, zlib
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress((b"\0" + b"\0" * width * 4) * height)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(raw).decode()


@pytest.mark.parametrize("size", [1, 256])
def test_dashboard_png_normal_and_boundary(size):
    icon = png_icon(size, size)
    result = validate_dashboard({**DOCUMENT, "items": [{**ITEM, "icon": icon}]})
    assert result["items"][0]["icon"] == icon


@pytest.mark.parametrize("icon", [None, "", "https://example.test/icon.png", "data:image/svg+xml;base64,PHN2Zz4=", "data:image/png;base64,bad!", "data:image/png;base64," + "A" * 44000], ids=["null", "empty", "remote", "svg", "invalid", "oversize"])
def test_dashboard_png_failure(icon):
    with pytest.raises(ValueError):
        validate_dashboard({**DOCUMENT, "items": [{**ITEM, "icon": icon}]})


def test_dashboard_png_rejects_corrupt_and_oversize_image():
    for icon in [png_icon(257), png_icon()[:-8], png_icon().replace("AAAA", "BBBB", 1)]:
        with pytest.raises(ValueError):
            validate_dashboard({**DOCUMENT, "items": [{**ITEM, "icon": icon}]})


def test_dashboard_png_saved_private_and_csrf_protected(setup):
    client, _, _ = setup
    user = client()
    board = user.get("/api/dashboards").json["dashboards"][0]
    body = {"revision": board["revision"], **DOCUMENT, "items": [{**ITEM, "icon": png_icon()}]}
    url = "/api/dashboards/" + board["id"]
    assert user.put(url, json=body).status_code == 403
    assert user.put(url, json=body, headers={"X-CSRF-Token": "csrf"}).status_code == 200
    assert user.get(url).json["dashboard"]["items"][0]["icon"] == png_icon()
    assert client("other@example.test").get(url).status_code == 404
    assert client(None).get(url).status_code == 401


def test_shared_app_png_normal_boundary_failure_and_permissions(setup):
    from backend.homepage import validate_homepage_link
    link = {"name": "Portal", "url": "https://example.test", "collection": "Apps", "icon": png_icon()}
    assert validate_homepage_link(link)["icon"] == png_icon()
    assert validate_homepage_link({**link, "icon": png_icon(256, 256)})["icon"]
    with pytest.raises(ValueError):
        validate_homepage_link({**link, "icon": "data:image/png;base64,bad!"})
    client, _, _ = setup
    admin = client("admin@example.test")
    response = admin.post("/api/homepage/links", json=link, headers={"X-CSRF-Token": "csrf"})
    assert response.status_code == 201
    assert admin.get("/api/dashboards/apps").json["apps"][0]["icon"] == png_icon()
    assert client().post("/api/homepage/links", json=link, headers={"X-CSRF-Token": "csrf"}).status_code == 403
    assert admin.post("/api/homepage/links", json=link).status_code == 403
