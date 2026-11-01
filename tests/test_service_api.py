"""Server-to-server reads for ControlDeckv2 widgets: an API key, never a browser session."""
import json

from tests.test_virtual_apps import CHROME, ORIGIN, env  # noqa: F401 (pytest fixture)

KEY = "k" * 40
URL = "/api/service/virtual-apps/images"


def test_without_or_with_wrong_key_is_refused(env):
    client, calls, replies, vault = env
    vault["CONTROLDECK_SERVICE_API_KEY"] = KEY
    assert client(None).get(URL).status_code == 401
    assert client(None).get(URL, headers={"X-ControlDeck-Api-Key": "x" * 40}).status_code == 401
    assert client().get(URL).status_code == 401, "a browser session is not a service key"
    assert calls == []


def test_short_or_missing_vault_key_never_opens_the_endpoint(env):
    client, calls, replies, vault = env
    assert client(None).get(URL, headers={"X-ControlDeck-Api-Key": ""}).status_code == 401
    vault["CONTROLDECK_SERVICE_API_KEY"] = "short"
    assert client(None).get(URL, headers={"X-ControlDeck-Api-Key": "short"}).status_code == 401


def test_images_with_key_without_hosts_or_secrets(env):
    client, calls, replies, vault = env
    vault["CONTROLDECK_SERVICE_API_KEY"] = KEY
    response = client(None).get(URL, headers={"X-ControlDeck-Api-Key": KEY})
    body = response.get_json()
    assert response.status_code == 200 and body["portal"] == ORIGIN
    assert [a["name"] for a in body["apps"]] == ["Chrome", "Firefox"] and body["apps"][0]["id"] == CHROME
    text = json.dumps(body)
    assert "s" * 32 not in text and "serverHost" not in text and "get_kasms" not in [c[0] for c in calls]


def test_writes_are_refused(env):
    client, calls, replies, vault = env
    vault["CONTROLDECK_SERVICE_API_KEY"] = KEY
    assert client(None).post(URL, headers={"X-ControlDeck-Api-Key": KEY}).status_code == 405
