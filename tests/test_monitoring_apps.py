"""Discovery from SABnzbd (Usenet servers), Seerr (Radarr/Sonarr/Plex settings) and Bazarr (Sonarr/Radarr settings)."""
import json
from unittest.mock import Mock

import pytest

from backend import monitoring
from backend.app import create_app

H = {"X-CSRF-Token": "csrf"}


class Fake:
    """Answers per path; records paths and headers to prove how the key is sent."""
    answers, calls = {}, []

    def __init__(self, source):
        pass

    def call(self, path, headers=None, **kwargs):
        Fake.calls.append((path, headers))
        value = Fake.answers.get(path.split("?")[0])
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        pass


def source(kind, **extra):
    return {"kind": kind, "title": kind.capitalize(), "url": "http://192.168.20.137:1", "allowHttp": True, "apiKey": "geheim0123456789abcdef", **extra}


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    Fake.answers, Fake.calls = {}, []
    monkeypatch.setattr(monitoring, "Transport", Fake)


def test_sabnzbd_usenet_servers_normal_and_disabled_skipped():
    Fake.answers = {"/api": {"config": {"servers": [
        {"name": "news.eweka.nl", "displayname": "Eweka", "host": "news.eweka.nl", "port": "563", "enable": 1},
        {"name": "oud", "host": "news.oud.example", "port": "119", "enable": 0}]}}}
    assert monitoring.discover_app(source("sabnzbd")) == [{"host": "news.eweka.nl", "port": 563, "label": "Usenet-server: Eweka"}]
    path, headers = Fake.calls[0]
    assert path.startswith("/api?mode=get_config&section=servers&output=json&apikey=") and headers is None


def test_seerr_radarr_sonarr_and_plex_boundary_ssl_without_port_and_missing_jellyfin():
    Fake.answers = {"/api/v1/settings/radarr": [{"name": "Radarr", "hostname": "arrsuite.home", "port": 7878}],
                    "/api/v1/settings/sonarr": [{"name": "Sonarr 4K", "hostname": "arrsuite.home", "port": 8989}],
                    "/api/v1/settings/plex": {"name": "Plex", "ip": "plex.home", "port": "", "useSsl": True},
                    "/api/v1/settings/jellyfin": monitoring.ProviderError("De bron geeft geen geldig antwoord.")}
    assert monitoring.discover_app(source("seerr")) == [
        {"host": "arrsuite.home", "port": 7878, "label": "Radarr: Radarr"},
        {"host": "arrsuite.home", "port": 8989, "label": "Sonarr: Sonarr 4K"},
        {"host": "plex.home", "port": 443, "label": "Plex: Plex"}]
    assert all(headers == {"X-Api-Key": "geheim0123456789abcdef"} for _, headers in Fake.calls)


def test_bazarr_settings_respects_use_flags():
    Fake.answers = {"/api/system/settings": {"general": {"use_sonarr": True, "use_radarr": False},
                                             "sonarr": {"ip": "sonarr", "port": 8989}, "radarr": {"ip": "radarr", "port": 7878}}}
    assert monitoring.discover_app(source("bazarr")) == [{"host": "sonarr", "port": 8989, "label": "Sonarr"}]
    assert Fake.calls[0][1] == {"X-API-KEY": "geheim0123456789abcdef"}


@pytest.mark.parametrize("kind,answers", [
    ("sabnzbd", {"/api": "geen json-object"}),
    ("sabnzbd", {"/api": {"config": {"servers": [{"host": "a b", "port": "563"}, {"host": "x.example", "port": "99999"}]}}}),
    ("bazarr", {"/api/system/settings": []}),
])
def test_failure_malformed_answers_find_nothing(kind, answers):
    Fake.answers = answers
    assert monitoring.discover_app(source(kind)) == []


def test_failure_refused_key_is_reported_per_source_and_key_never_leaks(tmp_path, monkeypatch):
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([{"email": "admin@example.test", "role": "admin"}]))
    monkeypatch.setattr(monitoring, "enrolled_nodes", lambda: set())
    monkeypatch.setattr(monitoring, "guests", lambda data_dir: {})
    monkeypatch.setattr(monitoring, "probe_central", lambda host, port: {"ok": True, "ip": "1.2.3.4", "ms": 1})
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True
    sources = {"sabnzbd": source("sabnzbd"), "seerr": source("seerr")}
    app.extensions["controldeck_vault"] = Mock(read=lambda: {"CONTROLDECK_MONITORING": json.dumps({"sources": sources})})
    Fake.answers = {"/api": {"config": {"servers": [{"host": "news.eweka.nl", "port": "563"}]}},
                    "/api/v1/settings/radarr": monitoring.ProviderError("De bron weigert de toegangsgegevens.")}
    client = app.test_client()
    with client.session_transaction() as session:
        session["identity"] = {"email": "admin@example.test", "sub": "admin@example.test"}
        session["csrf"] = "csrf"
    data = client.post("/api/monitoring/check", headers=H).get_json()
    assert [(row["source"], row["host"], row["port"]) for row in data["connections"]] == [("Sabnzbd", "news.eweka.nl", 563)]
    assert data["sourceErrors"] == [{"source": "seerr", "error": "De bron weigert de toegangsgegevens."}]
    assert "geheim0123456789abcdef" not in json.dumps(data)


def test_configuration_accepts_new_kinds_and_requires_api_key():
    assert set(monitoring.validate_sources({"sources": {"sab": source("sabnzbd"), "seerr": source("seerr"), "bazarr": source("bazarr")}})) == {"sab", "seerr", "bazarr"}
    with pytest.raises(monitoring.MonitorError):
        monitoring.validate_sources({"sources": {"sab": {**source("sabnzbd"), "apiKey": ""}}})


@pytest.mark.parametrize("key", ["…", "replace-in-vault", "kort", "sleutel met spaties erin!!", ""])
def test_placeholder_or_invalid_api_key_is_refused_with_source_name(key):
    """Regression: readarr had the example placeholder "…" as key; it failed later as "niet bereikbaar"
    (a non-latin-1 header), hiding the real cause. It is now refused up front, naming the source."""
    with pytest.raises(monitoring.MonitorError) as error:
        monitoring.validate_sources({"sources": {"readarr": {**source("radarr"), "apiKey": key}}})
    assert "readarr" in error.value.message
