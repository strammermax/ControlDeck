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

import pytest


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_readiness_three_cases(tmp_path, case):
    from backend.configuration import DEFAULT_PATH, load_config
    import json
    config = tmp_path / "controldeck.json"
    config.write_text(json.dumps(load_config(DEFAULT_PATH)))
    (tmp_path / "index.html").write_text("<h1>ControlDeck</h1>" if case != "boundary" else "")
    if case == "faal": config.write_text("invalid json")
    client = create_app(tmp_path, config, tmp_path / "data").test_client()
    assert client.get("/ready").status_code == (200 if case == "normaal" else 503)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_static_serving_three_cases(tmp_path, case):
    (tmp_path / "index.html").write_text("<h1>ControlDeck</h1>")
    (tmp_path / "asset with spaces.txt").write_text("known asset")
    client = create_app(tmp_path, data_dir=tmp_path / "data").test_client()
    if case == "normaal": assert b"ControlDeck" in client.get("/").data
    elif case == "boundary": assert client.get("/asset%20with%20spaces.txt").data == b"known asset"
    else: assert client.get("/%2e%2e/secret.txt").status_code == 404


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_health_three_cases(tmp_path, monkeypatch, case):
    if case == "boundary": monkeypatch.setattr("backend.app.time.monotonic",lambda:123.0)
    client = create_app(tmp_path, data_dir=tmp_path / "data").test_client()
    if case == "normaal": assert client.get("/health").json["status"] == "ok"
    elif case == "boundary": assert client.get("/health").json["uptime_seconds"] == 0
    else: assert client.post("/health").status_code == 405
