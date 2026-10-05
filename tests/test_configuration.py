import copy
import json
import shutil
from pathlib import Path

import pytest

from backend.app import create_app
from backend.configuration import ConfigurationError, DEFAULT_PATH, load_config, validate


@pytest.fixture
def configuration(tmp_path):
    root = tmp_path / "config"
    shutil.copytree(DEFAULT_PATH.parent, root)
    return root / "controldeck.json"


def test_split_configuration_and_private_projection(configuration):
    result = load_config(configuration)
    assert len(result["menu"]) == 7
    assert result["widgets"] == []
    assert {provider["id"] for provider in result["providers"]} == {"kasm", "radarr", "plex", "termix"}
    assert "tokenEnv" not in json.dumps(result)
    assert all(module["id"] not in ("kasm", "radarr", "plex") for module in result["modules"])


def test_enable_provider_adds_module_menu_and_widget_without_build(configuration):
    path = configuration.parent / "providers/kasm.json"
    data = json.loads(path.read_text())
    data.update(enabled=True, url="https://kasm.example.test")
    path.write_text(json.dumps(data))
    result = load_config(configuration)
    assert any(module["id"] == "kasm" for module in result["modules"])
    assert any(child.get("route") == "kasm" for item in result["menu"] for child in item.get("children", []))
    assert result["widgets"][0]["provider"] == "kasm"
    assert "CONTROLDECK_KASM_TOKEN" not in json.dumps(result)


def test_api_reloads_files_and_reports_invalid_configuration(configuration, tmp_path):
    (tmp_path / "index.html").write_text("<h1>ControlDeck</h1>")
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([{"email":"admin@example.test", "role":"admin"}]))
    app = create_app(tmp_path, configuration, tmp_path / "data", accounts)
    client = app.test_client()
    with client.session_transaction() as session:
        session["identity"] = {"sub":"test-admin", "email":"admin@example.test"}
        session["csrf"] = "test-csrf"
    first = client.get("/api/config")
    assert first.status_code == 200
    assert first.headers["Cache-Control"] == "no-store"
    data = json.loads(configuration.read_text())
    data["site"]["title"] = "My homelab"
    configuration.write_text(json.dumps(data))
    assert client.get("/api/config").json["site"]["title"] == "My homelab"
    configuration.write_text('{"secret": "do-not-return-this"')
    response = client.get("/api/config")
    assert response.status_code == 503
    assert b"do-not-return-this" not in response.data
    assert client.get("/ready").status_code == 503
    assert client.get("/health").status_code == 200


def test_includes_cannot_escape_config_folder(configuration):
    data = json.loads(configuration.read_text())
    data["includes"]["modules"] = "../"
    configuration.write_text(json.dumps(data))
    with pytest.raises(ConfigurationError):
        load_config(configuration)


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://user:password@example.test", "https://example.test/?api_key=secret", "//example.test"])
def test_reject_unsafe_provider_urls(configuration, url):
    path = configuration.parent / "providers/kasm.json"
    data = json.loads(path.read_text())
    data.update(enabled=True, url=url)
    path.write_text(json.dumps(data))
    with pytest.raises(ConfigurationError):
        load_config(configuration)


def test_disable_module_hides_routes_and_widgets(configuration):
    data = load_config(configuration)
    data["modules"][0]["enabled"] = False
    result = validate(data)
    assert all(item.get("route") != "dashboard" for item in result["menu"])
    assert all(item["id"] != "dashboard" for item in result["modules"])


@pytest.mark.parametrize("mutation", [
    lambda c: c["menu"].append(copy.deepcopy(c["menu"][0])),
    lambda c: c["menu"][0].update(route="unknown"),
    lambda c: c["menu"][0].update(icon=[]),
    lambda c: c["site"].update(refreshSeconds=0),
    lambda c: c.update(password="secret"),
])
def test_reject_invalid_definitions(configuration, mutation):
    data = load_config(configuration)
    mutation(data)
    with pytest.raises(ConfigurationError):
        validate(data)
