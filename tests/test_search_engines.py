import json
import sqlite3

import pytest

from backend.app import create_app
from backend.auth import database
from backend.dashboards import migrate_dashboards
from backend.search_engines import validate_search_engine

ENGINE = {"name": "SearXNG", "urlTemplate": "https://search.example.test/search?q=%s"}
H = {"X-CSRF-Token": "csrf"}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.auth.Vault.from_env", classmethod(lambda cls: None))
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([{"email": "user@example.test", "role": "user", "modules": ["dashboard"]}, {"email": "other@example.test", "role": "admin"}]))
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True
    def client(email="user@example.test", application=app):
        c = application.test_client()
        if email:
            with c.session_transaction() as session:
                session["identity"] = {"sub": email, "email": email}
                session["csrf"] = "csrf"
        return c
    return client, tmp_path, accounts


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_engine_validation(case):
    if case == "normaal":
        assert validate_search_engine({**ENGINE, "name": " SearXNG "}) == ENGINE
    elif case == "boundary":
        assert len(validate_search_engine({**ENGINE, "name": "x" * 80})["name"]) == 80
        for url in ["http://search.example.test/?q=%s", "https://example.test/search/%s", "https://example.test/#search/%s"]:
            assert validate_search_engine({**ENGINE, "urlTemplate": url})["urlTemplate"] == url
    else:
        for patch in [{"name": ""}, {"name": "x" * 81}, {"urlTemplate": "javascript:%s"}, {"urlTemplate": "https://example.test?q=x"},
                      {"urlTemplate": "https://%s.example.test?q=x"}, {"urlTemplate": "https://example.test?q=%s&other=%s"},
                      {"urlTemplate": "https://user:password@example.test?q=%s"}, {"urlTemplate": "https://example.test?q=%s&api_key=private"},
                      {"urlTemplate": "https://example.test:99999?q=%s"}, {"urlTemplate": "https://example.test/a b?q=%s"}, {"extra": True}]:
            with pytest.raises(ValueError):
                validate_search_engine({**ENGINE, **patch})
        with pytest.raises(ValueError):
            validate_search_engine(None)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_engine_create_and_limits(setup, case):
    clients, _, _ = setup
    c = clients()
    if case == "normaal":
        result = c.post("/api/search-engines", json=ENGINE, headers=H)
        assert result.status_code == 201 and result.json["engine"]["revision"] == 1
        assert c.get("/api/search-engines").json["engines"] == [result.json["engine"]]
    elif case == "boundary":
        assert c.get("/api/search-engines").json == {"engines": []}
        for i in range(10):
            assert c.post("/api/search-engines", json={**ENGINE, "name": f"Engine {i}"}, headers=H).status_code == 201
        assert c.post("/api/search-engines", json=ENGINE, headers=H).status_code == 400
        assert len(c.get("/api/search-engines").json["engines"]) == 10
    else:
        assert c.post("/api/search-engines", json={**ENGINE, "urlTemplate": "file:///%s"}, headers=H).status_code == 400
        assert c.post("/api/search-engines", json=[], headers=H).status_code == 400
        assert c.get("/api/search-engines").json == {"engines": []}


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_engine_change_delete_and_restart(setup, case):
    clients, tmp, accounts = setup
    c = clients()
    engine = c.post("/api/search-engines", json=ENGINE, headers=H).json["engine"]
    route = f"/api/search-engines/{engine['id']}"
    if case == "normaal":
        changed = c.put(route, json={**ENGINE, "name": "Werk zoeken", "revision": 1}, headers=H)
        assert changed.status_code == 200 and changed.json["engine"]["revision"] == 2
        application = create_app(data_dir=tmp / "data", accounts_path=accounts)
        assert clients(application=application).get("/api/search-engines").json["engines"][0]["name"] == "Werk zoeken"
        assert c.delete(route, json={"revision": 2}, headers=H).status_code == 200
    elif case == "boundary":
        assert c.put(route, json={**ENGINE, "revision": 1}, headers=H).status_code == 200
        assert c.put(route, json={**ENGINE, "revision": 1}, headers=H).status_code == 409
        assert c.delete(route, json={"revision": 1}, headers=H).status_code == 409
    else:
        assert c.put(route, json={**ENGINE, "name": "", "revision": 1}, headers=H).status_code == 400
        assert c.delete(route, json={"revision": 1, "extra": True}, headers=H).status_code == 400
        assert c.get("/api/search-engines").json["engines"] == [engine]
        assert c.put("/api/search-engines/missing", json={**ENGINE, "revision": 1}, headers=H).status_code == 404


def test_engine_auth_csrf_and_owner_isolation(setup):
    clients, _, _ = setup
    c = clients()
    assert clients(None).get("/api/search-engines").status_code == 401
    assert c.post("/api/search-engines", json=ENGINE).status_code == 403
    engine = c.post("/api/search-engines", json=ENGINE, headers=H).json["engine"]
    other = clients("other@example.test")
    assert other.get("/api/search-engines").json == {"engines": []}
    route = f"/api/search-engines/{engine['id']}"
    assert other.put(route, json={**ENGINE, "revision": 1}, headers=H).status_code == 404
    assert other.delete(route, json={"revision": 1}, headers=H).status_code == 404
    assert c.head("/api/search-engines").status_code == 200


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_schema_v1_upgrade_retains_dashboards_and_backup(tmp_path, monkeypatch, case):
    path = tmp_path / "users.sqlite3"
    with database(path) as db:
        db.execute("CREATE TABLE dashboard_schema (version INTEGER NOT NULL)")
        db.execute("INSERT INTO dashboard_schema VALUES (1)")
        db.execute("CREATE TABLE dashboards (id TEXT PRIMARY KEY, owner TEXT NOT NULL, revision INTEGER NOT NULL, document TEXT NOT NULL)")
        db.execute("INSERT INTO dashboards VALUES ('existing','owner',7,'{}')")
        db.execute("CREATE TABLE dashboard_preferences (owner TEXT PRIMARY KEY, default_id TEXT)")
        db.execute("INSERT INTO dashboard_preferences VALUES ('owner','existing')")
    if case == "faal":
        original = type(path).touch
        def fail_backup(self, *args, **kwargs):
            if self.parent.name == "backups":
                raise PermissionError("simulated backup failure")
            return original(self, *args, **kwargs)
        monkeypatch.setattr(type(path), "touch", fail_backup)
        with pytest.raises(PermissionError):
            migrate_dashboards(path)
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT version FROM dashboard_schema").fetchone()[0] == 1
            assert db.execute("SELECT 1 FROM sqlite_master WHERE name='search_engines'").fetchone() is None
        return
    migrate_dashboards(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT revision FROM dashboards WHERE id='existing'").fetchone()[0] == 7
        assert db.execute("SELECT default_id FROM dashboard_preferences").fetchone()[0] == "existing"
        assert db.execute("SELECT version FROM dashboard_schema").fetchone()[0] == 3
    backups = list((tmp_path / "backups").glob("pre-dashboard-v2-*.sqlite3"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as snapshot:
        assert snapshot.execute("SELECT version FROM dashboard_schema").fetchone()[0] == 1
        assert snapshot.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    if case == "boundary":
        migrate_dashboards(path)
        assert len(list((tmp_path / "backups").glob("*.sqlite3"))) == 1
