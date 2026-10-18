import json

import pytest

from backend.app import create_app
from backend.page_layouts import MAX_CELLS, validate_layout

H = {"X-CSRF-Token": "csrf"}
CELL = {"id": "12", "group": "Media", "x": 0, "y": 0, "width": 2, "height": 1}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.auth.Vault.from_env", classmethod(lambda cls: None))
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([
        {"email": "admin@example.test", "role": "admin"},
        {"email": "user@example.test", "role": "user", "modules": ["bookmarks"]},
        {"email": "other@example.test", "role": "user", "modules": ["bookmarks"]},
    ]))
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True

    def make(email="user@example.test"):
        c = app.test_client()
        if email:
            with c.session_transaction() as session:
                session["identity"] = {"sub": "subject-" + email, "email": email}
                session["csrf"] = "csrf"
        return c
    return make


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_layout_validation(case):
    if case == "normaal":
        cells = [CELL, {**CELL, "id": "13", "x": 0, "y": 1}, {**CELL, "group": "Infra"}]
        assert validate_layout({"cells": cells})["cells"] == cells
    elif case == "boundary":
        assert validate_layout({"cells": []}) == {"cells": []}
        edge = {"id": "health", "group": "main", "x": 0, "y": 288, "width": 12, "height": 12}
        assert validate_layout({"cells": [edge]})["cells"] == [edge]
        touching = [{**CELL, "width": 1}, {**CELL, "id": "13", "x": 1, "width": 1}]
        assert len(validate_layout({"cells": touching})["cells"]) == 2
        many = [{**CELL, "id": f"c{i}", "x": i % 12, "y": i // 12, "width": 1} for i in range(MAX_CELLS)]
        assert len(validate_layout({"cells": many})["cells"]) == MAX_CELLS
    else:
        bad = [
            None, {}, {"cells": {}}, {"cells": [], "extra": 1},
            {"cells": [{**CELL, "x": 11}]}, {"cells": [{**CELL, "height": 13}]}, {"cells": [{**CELL, "width": 0}]},
            {"cells": [{**CELL, "x": -1}]}, {"cells": [{**CELL, "y": 300}]}, {"cells": [{**CELL, "x": 1.0}]}, {"cells": [{**CELL, "x": True}]},
            {"cells": [{**CELL, "id": "../x"}]}, {"cells": [{**CELL, "group": ""}]}, {"cells": [{**CELL, "group": "a\nb"}]},
            {"cells": [{**CELL, "url": "https://x"}]}, {"cells": [CELL, CELL]}, {"cells": [CELL, {**CELL, "id": "13", "x": 1}]},
            {"cells": [{**CELL, "id": f"c{i}", "y": i} for i in range(MAX_CELLS + 1)]},
        ]
        for value in bad:
            with pytest.raises(ValueError):
                validate_layout(value)


def test_layout_api_normaal_save_load_and_reset(client):
    c = client()
    assert c.get("/api/layouts/bookmarks").get_json() == {"cells": []}
    saved = c.put("/api/layouts/bookmarks", json={"cells": [CELL]}, headers=H)
    assert saved.status_code == 200 and saved.get_json()["cells"] == [CELL]
    moved = {**CELL, "y": 3, "width": 1, "height": 2}
    assert c.put("/api/layouts/bookmarks", json={"cells": [moved]}, headers=H).status_code == 200
    assert c.get("/api/layouts/bookmarks").get_json()["cells"] == [moved]
    assert c.delete("/api/layouts/bookmarks", headers=H).get_json() == {"cells": []}
    assert c.get("/api/layouts/bookmarks").get_json() == {"cells": []}
    # Deleting a layout that does not exist is harmless.
    assert c.delete("/api/layouts/bookmarks", headers=H).status_code == 200


def test_layout_api_boundary_admin_pages_are_separate(client):
    admin = client("admin@example.test")
    tile = {"id": "tasks", "group": "main", "x": 0, "y": 0, "width": 12, "height": 6}
    assert admin.put("/api/layouts/proxmox", json={"cells": [tile]}, headers=H).status_code == 200
    assert admin.put("/api/layouts/media", json={"cells": []}, headers=H).status_code == 200
    assert admin.get("/api/layouts/bookmarks").get_json() == {"cells": []}
    assert admin.get("/api/layouts/proxmox").get_json()["cells"] == [tile]


def test_layout_api_faal_invalid_body_and_unknown_page(client):
    c = client()
    assert c.put("/api/layouts/bookmarks", json={"cells": [CELL, CELL]}, headers=H).status_code == 400
    assert c.put("/api/layouts/bookmarks", data="geen json", headers={**H, "Content-Type": "application/json"}).status_code == 400
    assert c.put("/api/layouts/bookmarks", data="x" * (128 * 1024 + 1), headers={**H, "Content-Type": "application/json"}).status_code == 413
    assert c.get("/api/layouts/admin").status_code == 404
    assert c.get("/api/layouts/bookmarks").get_json() == {"cells": []}, "a refused save leaves the stored layout untouched"


def test_layout_api_authentication_and_csrf(client):
    assert client(None).get("/api/layouts/bookmarks").status_code == 401
    assert client(None).put("/api/layouts/bookmarks", json={"cells": []}).status_code == 401
    c = client()
    assert c.put("/api/layouts/bookmarks", json={"cells": [CELL]}).status_code == 403
    assert c.put("/api/layouts/bookmarks", json={"cells": [CELL]}, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert c.delete("/api/layouts/bookmarks").status_code == 403
    assert c.get("/api/layouts/bookmarks").get_json() == {"cells": []}


def test_layout_api_authorization_module_access_and_personal_isolation(client):
    user = client()
    assert user.get("/api/layouts/proxmox").status_code == 403, "no Proxmox module access"
    assert user.put("/api/layouts/proxmox", json={"cells": []}, headers=H).status_code == 403
    assert user.put("/api/layouts/bookmarks", json={"cells": [CELL]}, headers=H).status_code == 200
    other = client("other@example.test")
    assert other.get("/api/layouts/bookmarks").get_json() == {"cells": []}, "layouts are personal"
    assert other.delete("/api/layouts/bookmarks", headers=H).status_code == 200
    assert user.get("/api/layouts/bookmarks").get_json()["cells"] == [CELL], "another user's reset never touches mine"
