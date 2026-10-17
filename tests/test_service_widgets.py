"""Provider behavior and authorization: no browser-selected targets or credential output."""
import copy
import json
from unittest.mock import Mock
import pytest
import requests
from backend.widgets.transport import Transport, ProviderError, provider_url
from backend.widget_sources import validate_sources, FAMILIES
from backend.dashboards import validate_dashboard
from test_dashboard_apps_search import setup, DOC, H
from test_dashboard_modules import MODULE

TOKEN = "synthetic-token-with-sufficient-entropy-123456"
CALENDAR = '<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:response><d:propstat><d:prop><c:calendar-data>BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:one\nDTSTART:20990101T100000Z\nDTEND:20990101T110000Z\nSUMMARY:Afspraak\nEND:VEVENT\nEND:VCALENDAR</c:calendar-data></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>'
KINDS = {kind: family for family, value in FAMILIES.items() for kind in value["kinds"]}


def source(kind):
    return {"family": KINDS[kind], "kind": kind, "title": "Testbron", "users": ["user@example.test"], "url": "https://provider.example.test", "apiKey": "" if kind == "qbittorrent" else TOKEN, "username": "synthetic-user", "password": TOKEN, "ingestToken": TOKEN}


@pytest.fixture
def widget_env(setup, monkeypatch):
    clients, data, accounts, _ = setup
    rows = json.loads(accounts.read_text())
    for row in rows:
        row["modules"] = ["dashboard", "media", "files", "monitoring"]
    accounts.write_text(json.dumps(rows))
    values = {kind: source(kind) for kind in KINDS}
    application = clients().application
    application.extensions["controldeck_vault"] = Mock(read=lambda: {"CONTROLDECK_WIDGET_SOURCES": json.dumps(values)})
    calls, replies = [], {}

    def call(self, path="", method="GET", **kwargs):
        calls.append((self.source["kind"], path, method, kwargs))
        value = replies[(self.source["kind"], path)]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)

    monkeypatch.setattr(Transport, "call", call)
    return clients, values, calls, replies, data


FIXTURES = {
    "qbittorrent": {"/api/v2/auth/login": "Ok.", "/api/v2/torrents/info": [{"hash": "hash", "name": "Download", "state": "downloading", "progress": .5, "dlspeed": 1024}]},
    "sabnzbd": {"/api": {"queue": {"slots": [{"nzo_id": "id", "filename": "Download", "status": "Downloading", "percentage": "50", "timeleft": "1:00"}], "speed": "1 MB/s"}}},
    "plex": {"/status/sessions": {"MediaContainer": {"Metadata": [{"sessionKey": "1", "title": "Film", "Player": {"state": "playing"}, "viewOffset": 50, "duration": 100}]}}},
    "seerr": {"/api/v1/request": {"results": [{"id": 1, "status": 1, "type": "movie", "media": {"tmdbId": 42}}]}, "/api/v1/movie/42": {"title": "Movie title"}},
    "tdarr": {"/api/v2/get-nodes": {"node": {"nodeName": "Node", "workers": {"worker": {"_id": "w", "file": "/private/path/movie.mkv", "status": "processing", "percentage": 50}}}}, "/api/v2/stats/get-pies": {"pieStats": {"totalFiles": 100, "totalTranscodeCount": 20}}},
    "prefect": {"/flow_runs/filter": [{"id": "1", "name": "Flowrun", "state": {"name": "Completed"}, "start_time": "2026-10-14T10:00:00Z"}]},
    "nextcloud-calendar": {"": CALENDAR},
}


@pytest.mark.parametrize("kind", list(FIXTURES))
@pytest.mark.parametrize("case", ["normal", "boundary", "failure"])
def test_provider_widgets_normal_boundary_and_failure(widget_env, kind, case):
    clients, _, calls, replies, _ = widget_env
    values = copy.deepcopy(FIXTURES[kind])
    if case == "boundary":
        if kind == "qbittorrent": values["/api/v2/torrents/info"] = []
        elif kind == "sabnzbd": values["/api"]["queue"]["slots"] = []
        elif kind == "plex": values["/status/sessions"]["MediaContainer"]["Metadata"] = []
        elif kind == "seerr": values["/api/v1/request"]["results"] = []
        elif kind == "tdarr": values["/api/v2/get-nodes"] = {}
        elif kind == "prefect": values["/flow_runs/filter"] = []
        else: values[""] = '<d:multistatus xmlns:d="DAV:"/>'
    if case == "failure":
        values[next(iter(values))] = ProviderError("synthetic secret must never be shown")
    replies.update({(kind, path): value for path, value in values.items()})
    response = clients().get(f"/api/widgets/{KINDS[kind]}/{kind}")
    assert response.status_code == (503 if case == "failure" else 200)
    assert TOKEN not in response.get_data(as_text=True)
    assert "synthetic secret" not in response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    if case == "boundary": assert response.json["items"] == []
    if case == "normal" and kind != "nextcloud-calendar": assert len(response.json["items"]) == 1
    if case == "normal" and kind == "tdarr": assert "/private/path/" not in response.get_data(as_text=True)
    if case == "normal" and kind == "nextcloud-calendar": assert calls[0][2] == "REPORT" and b"expand" in calls[0][3]["data"]


def test_source_acl_authentication_and_no_credential_projection(widget_env):
    clients, values, _, _, _ = widget_env
    c = clients()
    listed = c.get("/api/widget-sources?family=downloads")
    assert listed.status_code == 200 and len(listed.json["sources"]) == 2
    assert set(listed.json["sources"][0]) == {"id", "title", "kind"}
    assert clients(None).get("/api/widget-sources?family=downloads").status_code == 401
    assert clients("other@example.test").get("/api/widget-sources?family=downloads").json == {"sources": []}
    assert clients("other@example.test").get("/api/widgets/downloads/qbittorrent").status_code == 404
    assert c.get("/api/widgets/calendar/qbittorrent").status_code == 404
    assert c.get("/api/widget-sources?family=unknown").status_code == 400
    values["qbittorrent"]["users"] = ["other@example.test"]
    assert c.get("/api/widgets/downloads/qbittorrent").status_code == 404


def test_qbittorrent_api_key_authentication_avoids_password_login(widget_env):
    clients, values, calls, replies, _ = widget_env
    values["qbittorrent"].update(apiKey=TOKEN)
    values["qbittorrent"].pop("password")
    values["qbittorrent"].pop("username")
    replies[("qbittorrent", "/api/v2/torrents/info")] = []
    assert clients().get("/api/widgets/downloads/qbittorrent").status_code == 200
    assert len(calls) == 1 and calls[0][1] == "/api/v2/torrents/info"
    assert calls[0][3]["headers"] == {"Authorization": "Bearer " + TOKEN}


def test_homeassistant_dashboard_uses_only_trusted_https_source(widget_env):
    clients, values, calls, _, _ = widget_env
    values["homeassistant-dashboard"]["url"] = "https://ha.example.test/dashboard-controldeck/0"
    reply = clients().get("/api/widgets/homeassistant-dashboard/homeassistant-dashboard")
    assert reply.status_code == 200 and reply.json["embedUrl"].endswith("/dashboard-controldeck/0")
    assert calls == [] and TOKEN not in reply.get_data(as_text=True)
    values["homeassistant-dashboard"]["url"] = "http://ha.example.test"
    values["homeassistant-dashboard"]["allowHttp"] = True
    assert clients().get("/api/widgets/homeassistant-dashboard/homeassistant-dashboard").status_code == 503


@pytest.mark.parametrize("kind", list(FIXTURES))
def test_provider_rejects_malformed_payload_instead_of_crashing_or_leaking(widget_env, kind):
    clients, _, _, replies, _ = widget_env
    replies.update({(kind, path): value for path, value in copy.deepcopy(FIXTURES[kind]).items()})
    path = list(FIXTURES[kind])[0] if kind == "seerr" else list(FIXTURES[kind])[-1]
    replies[(kind, path)] = {"secret": TOKEN} if kind != "nextcloud-calendar" else '<!DOCTYPE x><d:multistatus xmlns:d="DAV:"/>'
    response = clients().get(f"/api/widgets/{KINDS[kind]}/{kind}")
    assert response.status_code == 503 and TOKEN not in response.get_data(as_text=True)


def test_revoked_module_permission_blocks_source_without_network_call(widget_env):
    clients, _, calls, _, data = widget_env
    accounts = data.parent / "accounts.json"
    rows = json.loads(accounts.read_text())
    rows[0]["modules"] = ["dashboard"]
    accounts.write_text(json.dumps(rows))
    assert clients().get("/api/widget-sources?family=downloads").json == {"sources": []}
    assert clients().get("/api/widgets/downloads/qbittorrent").status_code == 404
    assert calls == []


def test_scoped_statistics_ingestion_normal_boundary_and_failure(widget_env, monkeypatch):
    clients, values, _, _, _ = widget_env
    anonymous = clients(None)
    url = "/api/widget-ingest/statistics"
    payload = {"schemaVersion": 1, "offers": [], "generatedAt": "2026-10-14T12:00:00Z"}
    assert clients().get("/api/widgets/statistics/statistics").json["pending"] is True
    assert anonymous.post(url, json=payload).status_code == 401
    assert clients().post(url, json=payload, headers=H).status_code == 401
    auth = {"Authorization": "Bearer " + TOKEN}
    assert anonymous.post(url, json=payload, headers=auth).status_code == 200
    assert clients().get("/api/widgets/statistics/statistics").json["items"] == []
    assert anonymous.post("/api/widget-ingest/plex", json=payload, headers=auth).status_code == 401
    for patch in [{"offers": {}}, {"generatedAt": "2026-10-14"}, {"extra": "forbidden"}]:
        assert anonymous.post(url, json={**payload, **patch}, headers=auth).status_code == 400
    offer = {"id": "1", "title": "Aanbieding", "url": "https://offers.example.test/item/1", "priceCents": 1250, "currency": "EUR", "site": "Testsite", "firstSeenAt": "2026-10-14T10:00:00Z"}
    assert anonymous.post(url, json={**payload, "offers": [offer]}, headers=auth).status_code == 200
    assert clients().get("/api/widgets/statistics/statistics").json["items"][0]["priceCents"] == 1250
    for patch in [{"url": "javascript:alert(1)"}, {"priceCents": True}, {"currency": "euro"}, {"firstSeenAt": "invalid"}]:
        assert anonymous.post(url, json={**payload, "offers": [{**offer, **patch}]}, headers=auth).status_code == 400
    values["statistics"]["ingestToken"] = "rotated-long-synthetic-test-token-234567"
    assert anonymous.post(url, json=payload, headers=auth).status_code == 401
    assert anonymous.post("/api/widgets/statistics/statistics", json=payload, headers=auth).status_code == 401
    assert anonymous.get("/api/widgets/statistics/statistics", headers=auth).status_code == 401
    assert anonymous.post("/api/widget-ingest/statistics/unknown", json=payload, headers=auth).status_code == 401


@pytest.mark.parametrize("family", list(FAMILIES))
def test_widget_settings_accept_only_source_references(family):
    for identifier in ("", "source-1", "a" * 64):
        doc = validate_dashboard({**DOC, "items": [{**MODULE, "moduleId": family, "settings": {"sourceId": identifier}}]})
        assert doc["items"][0]["settings"] == {"sourceId": identifier}
    for settings in ({}, {"sourceId": []}, {"sourceId": "../other"}, {"sourceId": "a" * 65}, {"sourceId": "one", "token": TOKEN}):
        with pytest.raises(ValueError):validate_dashboard({**DOC, "items": [{**MODULE, "moduleId": family, "settings": settings}]})


@pytest.mark.parametrize("kind", list(KINDS))
def test_source_configuration_rejects_missing_access_and_unsafe_urls(kind):
    original = source(kind)
    assert validate_sources({"one": original})
    for patch in ({"users": []}, {"users": ["*"]}, {"kind": "unknown"}, {"title": ""}):
        with pytest.raises(ProviderError):validate_sources({"one": {**original, **patch}})
    if kind != "statistics":
        for url in ("javascript:alert(1)", "https://user:secret@host/", "https://host/?token=secret", "http://host/"):
            with pytest.raises(ProviderError):validate_sources({"one": {**original, "url": url}})


@pytest.mark.parametrize("mode", ["normal", "auth", "redirect", "timeout", "large", "invalid"])
def test_transport_fixed_tls_bounded_responses_and_safe_errors(monkeypatch, mode):
    session = Mock()
    response = Mock(status_code=401 if mode == "auth" else 302 if mode == "redirect" else 200)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.iter_content.return_value = [b"x" * (2 * 1024 * 1024 + 1)] if mode == "large" else [b"bad" if mode == "invalid" else b'{"ok":true}']
    session.request.return_value = response
    if mode == "timeout":session.request.side_effect = requests.Timeout("secret-url-password")
    monkeypatch.setattr("backend.widgets.transport.requests.Session", lambda: session)
    transport = Transport(source("plex"))
    if mode == "normal":assert transport.call("/status/sessions") == {"ok": True}
    else:
        with pytest.raises(ProviderError) as error:transport.call("/status/sessions")
        assert "secret-url" not in str(error.value)
    assert session.request.call_args.kwargs["allow_redirects"] is False
    assert session.request.call_args.kwargs["verify"] is True
    transport.close();session.close.assert_called_once()


def test_offer_image_is_optional_but_must_be_safe_https():
    from backend.widgets.adapters import statistics_payload
    offer={'id':'1','title':'Offer','url':'https://shop.example.test/item/1','priceCents':None,'currency':'EUR','site':'Shop','firstSeenAt':'2026-10-16T10:00:00Z'}
    payload={'schemaVersion':1,'generatedAt':'2026-10-16T10:00:00Z','offers':[offer]}
    assert 'imageUrl' not in statistics_payload(payload)['offers'][0]
    assert statistics_payload({**payload,'offers':[{**offer,'imageUrl':'https://images.example.test/one.jpg'}]})['offers'][0]['imageUrl'].endswith('/one.jpg')
    for image in ['http://images.example.test/one.jpg','javascript:alert(1)','https://host/a?token=secret']:
        with pytest.raises(ProviderError):statistics_payload({**payload,'offers':[{**offer,'imageUrl':image}]})
