from backend.app import create_app


def test_health_and_readiness(tmp_path):
    client = create_app(tmp_path).test_client()
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json["status"] == "ok"
    assert health.json["version"]
    assert isinstance(health.json["uptime_seconds"], int)
    assert health.json["uptime_seconds"] >= 0
    assert client.get("/ready").status_code == 503
    (tmp_path / "index.html").write_text("<h1>ControlDeck</h1>")
    assert client.get("/ready").status_code == 200
    assert b"ControlDeck" in client.get("/").data


def test_static_files_do_not_expose_parent_paths(tmp_path):
    root = tmp_path / "public"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("private")
    client = create_app(root).test_client()
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/backend/app.py"):
        assert client.get(path).status_code == 404
    assert client.get("/health").headers["Cache-Control"] == "no-store"
