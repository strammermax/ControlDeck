import io
import json
from unittest.mock import Mock

import pytest

from backend import files
from backend.app import create_app
from backend.files import CHUNK_SIZE, clean_path, dav_items, nextcloud_origin

H = {"X-CSRF-Token": "csrf"}
SERVER = "https://cloud.example.test"
PASSWORD = "p" * 72
LISTING = f"""<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">
<d:response><d:href>/remote.php/dav/files/camiel/Docs/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
<d:response><d:href>/remote.php/dav/files/camiel/Docs/Fotos/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype><d:getlastmodified>Sat, 17 Oct 2026 07:00:00 GMT</d:getlastmodified></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
<d:response><d:href>/remote.php/dav/files/camiel/Docs/factuur%20oktober.pdf</d:href><d:propstat><d:prop><d:resourcetype/><d:getcontentlength>2048</d:getcontentlength></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
</d:multistatus>"""


def reply(status=200, body=None, content=b"", headers=None):
    response = Mock(status_code=status, content=content, headers=headers or {})
    response.json = Mock(return_value=body) if body is not None else Mock(side_effect=ValueError)
    response.iter_content = Mock(return_value=iter([content]))
    return response


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.auth.Vault.from_env", classmethod(lambda cls: None))
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([
        {"email": "admin@example.test", "role": "admin"},
        {"email": "user@example.test", "role": "user", "modules": ["files"]},
        {"email": "other@example.test", "role": "user", "modules": ["files"]},
        {"email": "denied@example.test", "role": "user", "modules": ["bookmarks"]},
    ]))
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True
    calls, routes = [], {}

    def fake(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if kwargs.get("data") is not None and hasattr(kwargs["data"], "read"):
            kwargs["data"].read()
        for (m, prefix), value in routes.items():
            if m == method and url.startswith(prefix):
                result = value(url, kwargs) if callable(value) and not isinstance(value, Mock) else value
                if isinstance(result, Exception):
                    raise result
                return result
        return reply(500)
    monkeypatch.setattr(files.requests, "request", fake)

    def client(email="user@example.test"):
        c = app.test_client()
        if email:
            with c.session_transaction() as session:
                session["identity"] = {"sub": "subject-" + email, "email": email}
                session["csrf"] = "csrf"
        return c

    assert client("admin@example.test").put("/api/files/server", json={"url": SERVER + "/"}, headers=H).status_code == 200
    return client, routes, calls


def link(client, routes, email="user@example.test", login="camiel"):
    routes[("POST", SERVER + "/index.php/login/v2")] = reply(200, {"login": SERVER + "/login/v2/flow/abc", "poll": {"token": "t" * 64, "endpoint": SERVER + "/login/v2/poll"}})
    routes[("POST", SERVER + "/login/v2/poll")] = reply(200, {"server": SERVER, "loginName": login, "appPassword": PASSWORD})
    routes[("GET", SERVER + "/ocs/v2.php/cloud/user")] = reply(200, {"ocs": {"data": {"email": email}}})
    c = client(email)
    started = c.post("/api/files/connection", headers=H).get_json()
    assert started.get("loginUrl", "").startswith(SERVER), started
    return c, c.post("/api/files/connection/poll", headers=H)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_paths_and_origin(case):
    if case == "normaal":
        assert clean_path("Docs/2026/factuur oktober.pdf") == ["Docs", "2026", "factuur oktober.pdf"]
        assert nextcloud_origin("https://cloud.vanburik.info/") == "https://cloud.vanburik.info"
    elif case == "boundary":
        assert clean_path("") == [] and clean_path(None) == [] and clean_path("//a//b/") == ["a", "b"]
        assert clean_path("é/日本/" + "x" * 255) == ["é", "日本", "x" * 255]
        assert nextcloud_origin("http://192.168.20.163") == "http://192.168.20.163"
        assert nextcloud_origin("https://cloud.example.test:8443") == "https://cloud.example.test:8443"
    else:
        for bad in ("..", "a/../b", "./a", "a\\b", "a\nb", "a\x00", "x" * 1025, "a/" + "y" * 256, 5):
            with pytest.raises(ValueError):
                clean_path(bad)
        with pytest.raises(ValueError):
            clean_path("", allow_root=False)
        for bad in ("http://cloud.example.test", "https://cloud.example.test/nextcloud", "https://u:p@cloud.example.test", "ftp://x", "https://x?y=1", "", None):
            with pytest.raises(ValueError):
                nextcloud_origin(bad)


def test_dav_listing_projection_normaal_boundary_faal():
    items = dav_items(LISTING.encode(), "/remote.php/dav/files/camiel/Docs/")
    assert items == [{"name": "Fotos", "type": "folder", "size": None, "modified": 1792220400},
                     {"name": "factuur oktober.pdf", "type": "file", "size": 2048, "modified": None}]
    assert dav_items(b'<d:multistatus xmlns:d="DAV:"/>', "/x/") == []
    with pytest.raises(files.FilesError):
        dav_items(b"<not xml", "/x/")


def test_login_flow_normaal_links_and_never_exposes_password(env):
    client, routes, calls = env
    c, result = link(client, routes)
    assert result.get_json() == {"state": "linked", "loginName": "camiel"}
    status = c.get("/api/files/connection").get_json()
    assert status == {"linked": True, "loginName": "camiel", "server": SERVER}
    assert PASSWORD not in json.dumps(status) and PASSWORD not in result.get_data(as_text=True)


def test_login_flow_boundary_pending_then_linked_and_unlink_revokes(env):
    client, routes, calls = env
    routes[("POST", SERVER + "/index.php/login/v2")] = reply(200, {"login": SERVER + "/login/v2/flow/abc", "poll": {"token": "t" * 64, "endpoint": SERVER + "/login/v2/poll"}})
    routes[("POST", SERVER + "/login/v2/poll")] = reply(404)
    c = client()
    c.post("/api/files/connection", headers=H)
    assert c.post("/api/files/connection/poll", headers=H).get_json() == {"state": "pending"}
    c, _ = link(client, routes)
    routes[("DELETE", SERVER + "/ocs/v2.php/core/apppassword")] = reply(200, {})
    assert c.delete("/api/files/connection", headers=H).get_json()["linked"] is False
    assert any(method == "DELETE" and url.endswith("/core/apppassword") for method, url, _ in calls)


def test_login_flow_faal_wrong_email_foreign_server_and_no_flow(env):
    client, routes, calls = env
    routes[("DELETE", SERVER + "/ocs/v2.php/core/apppassword")] = reply(200, {})
    c, result = link(client, routes, email="user@example.test")
    routes[("GET", SERVER + "/ocs/v2.php/cloud/user")] = reply(200, {"ocs": {"data": {"email": "someone@else.test"}}})
    c.post("/api/files/connection", headers=H)
    assert c.post("/api/files/connection/poll", headers=H).status_code == 502
    assert any(method == "DELETE" for method, url, _ in calls), "a mismatching app password is revoked immediately"
    other = client("other@example.test")
    assert other.post("/api/files/connection/poll", headers=H).status_code == 409, "no running flow"
    routes[("POST", SERVER + "/index.php/login/v2")] = reply(200, {"login": "https://evil.test/login", "poll": {"token": "t" * 64, "endpoint": SERVER + "/p"}})
    assert other.post("/api/files/connection", headers=H).status_code == 502


def test_browse_download_upload_normaal(env):
    client, routes, calls = env
    c, _ = link(client, routes)
    routes[("PROPFIND", SERVER + "/remote.php/dav/files/camiel/Docs")] = reply(207, content=LISTING.encode())
    listing = c.get("/api/files/list?path=Docs").get_json()
    assert [item["name"] for item in listing["items"]] == ["Fotos", "factuur oktober.pdf"]
    routes[("GET", SERVER + "/remote.php/dav/files/camiel/Docs/")] = reply(200, content=b"%PDF", headers={"Content-Length": "4"})
    download = c.get("/api/files/download?path=Docs/factuur oktober.pdf")
    assert download.data == b"%PDF" and download.headers["Content-Disposition"] == "attachment; filename*=UTF-8''factuur%20oktober.pdf"
    routes[("PUT", SERVER + "/remote.php/dav/files/camiel/")] = reply(201)
    assert c.put("/api/files/upload?path=Docs/nieuw.txt", data=b"hallo", headers=H).status_code == 201
    put = [kwargs for method, url, kwargs in calls if method == "PUT"][-1]
    assert put["headers"]["If-None-Match"] == "*" and put["auth"] == ("camiel", PASSWORD)
    for method in ("MKCOL", "MOVE", "DELETE"):
        routes[(method, SERVER + "/remote.php/dav/")] = reply(201 if method != "DELETE" else 204)
    assert c.post("/api/files/folder", json={"path": "Docs/Nieuw"}, headers=H).status_code == 201
    assert c.post("/api/files/move", json={"from": "Docs/nieuw.txt", "to": "Docs/Nieuw/hernoemd.txt"}, headers=H).status_code == 200
    move = [kwargs for method, url, kwargs in calls if method == "MOVE"][-1]
    assert move["headers"]["Destination"] == SERVER + "/remote.php/dav/files/camiel/Docs/Nieuw/hernoemd.txt" and move["headers"]["Overwrite"] == "F"
    assert c.delete("/api/files/item?path=Docs/Nieuw", headers=H).status_code == 200


def test_chunked_upload_boundary(env):
    client, routes, calls = env
    c, _ = link(client, routes)
    for method in ("MKCOL", "PUT", "MOVE", "DELETE"):
        routes[(method, SERVER + "/remote.php/dav/uploads/camiel/")] = reply(201 if method != "DELETE" else 204)
    started = c.post("/api/files/uploads", json={"path": "Video/film.mkv", "size": 10 * 1024 ** 3}, headers=H)
    assert started.status_code == 201 and started.get_json()["chunkSize"] == CHUNK_SIZE
    upload = started.get_json()["id"]
    assert c.put(f"/api/files/uploads/{upload}/1?path=Video/film.mkv", data=b"x" * (4 * 1024 * 1024), headers=H).status_code == 201, "chunks far above the 16 KiB API limit pass"
    chunk = [(url, kwargs) for method, url, kwargs in calls if method == "PUT"][-1]
    assert chunk[0].endswith(f"/uploads/camiel/{upload}/00001") and chunk[1]["headers"]["Destination"].endswith("/files/camiel/Video/film.mkv")
    assert c.post(f"/api/files/uploads/{upload}/finish", json={"path": "Video/film.mkv", "size": 1024}, headers=H).status_code == 201
    finish = [kwargs for method, url, kwargs in calls if method == "MOVE"][-1]
    assert finish["headers"]["OC-Total-Length"] == "1024" and finish["headers"]["Overwrite"] == "F"
    assert c.delete(f"/api/files/uploads/{upload}", headers=H).status_code == 200


def test_files_faal_refusals_and_upstream_errors(env):
    client, routes, calls = env
    c, _ = link(client, routes)
    assert c.get("/api/files/list?path=../etc").status_code == 400
    assert c.get("/api/files/download?path=").status_code == 400
    assert c.delete("/api/files/item?path=", headers=H).status_code == 400, "the root folder is never deleted"
    assert c.post("/api/files/move", json={"from": "Docs", "to": "Docs/sub"}, headers=H).status_code == 400
    assert c.post("/api/files/uploads", json={"path": "a.bin", "size": 10 * 1024 ** 3 + 1}, headers=H).status_code == 400
    assert c.put("/api/files/uploads/evil/1?path=a", data=b"x", headers=H).status_code == 400
    assert c.put("/api/files/upload?path=a.bin", data=io.BytesIO(b"x" * (CHUNK_SIZE + 1)), headers=H).status_code == 400
    routes[("PUT", SERVER + "/remote.php/dav/files/")] = reply(412)
    exists = c.put("/api/files/upload?path=bestaat.txt", data=b"x", headers=H)
    assert exists.status_code == 409 and "bestaat al" in exists.get_json()["error"]
    routes[("PROPFIND", SERVER + "/remote.php/dav/files/")] = reply(401)
    revoked = c.get("/api/files/list")
    assert revoked.status_code == 409 and revoked.get_json()["relink"] is True
    routes[("PROPFIND", SERVER + "/remote.php/dav/files/")] = lambda url, kwargs: files.requests.ConnectionError()
    assert c.get("/api/files/list").status_code == 502


def test_files_authentication_csrf_and_authorization(env):
    client, routes, calls = env
    assert client(None).get("/api/files/list").status_code == 401
    user = client()
    assert user.post("/api/files/folder", json={"path": "x"}).status_code == 403, "CSRF required"
    assert user.put("/api/files/server", json={"url": "https://evil.test"}, headers=H).status_code == 403, "admin only"
    assert client("denied@example.test").get("/api/files/list").status_code == 403, "no Files module"
    assert user.get("/api/files/list").get_json()["relink"] is True, "not linked yet"
    _, _ = link(client, routes)
    other = client("other@example.test")
    assert other.get("/api/files/connection").get_json()["linked"] is False, "app passwords are personal"
    assert other.get("/api/files/list").status_code == 409
    admin = client("admin@example.test")
    assert admin.put("/api/files/server", json={"url": "https://other-cloud.example.test"}, headers=H).status_code == 200
    assert client().get("/api/files/connection").get_json()["linked"] is False, "a new server never receives the old password"
