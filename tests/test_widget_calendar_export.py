"""CalDAV recurrence boundaries and a strictly personal read-only offers exporter."""
import importlib.util
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock
import pytest
from backend.widgets.calendar import parse_calendar
from backend.widgets.adapters import statistics_payload
from backend.widgets.transport import ProviderError

spec = importlib.util.spec_from_file_location("offers_export", Path(__file__).resolve().parents[1] / "scripts/koopjesbot_widget_export.py")
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)
START, END = datetime(2026, 10, 14, tzinfo=timezone.utc), datetime(2026, 10, 16, tzinfo=timezone.utc)


def calendar(event):
    return '<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:response><d:propstat><d:status>HTTP/1.1 200 OK</d:status><d:prop><c:calendar-data>BEGIN:VCALENDAR\n' + event + '\nEND:VCALENDAR</c:calendar-data></d:prop></d:propstat></d:response></d:multistatus>'


def test_calendar_normal_folded_lines_all_day_and_cancelled_events():
    event = 'BEGIN:VEVENT\nDTSTART:20261014T100000Z\nDTEND:20261014T110000Z\nSUMMARY:Afspraak\\, met een\n lange naam\nBEGIN:VALARM\nSUMMARY:Alarm mag geen titel worden\nEND:VALARM\nEND:VEVENT'
    rows = parse_calendar(calendar(event), START, END)["items"]
    assert rows[0]["title"] == "Afspraak, met eenlange naam" and rows[0]["date"].startswith("2026-10-14T10")
    all_day = 'BEGIN:VEVENT\nDTSTART;VALUE=DATE:20261014\nSUMMARY:Vrij\nEND:VEVENT'
    assert parse_calendar(calendar(all_day), START, END)["items"][0]["allDay"] is True
    assert parse_calendar(calendar(all_day.replace('SUMMARY:Vrij', 'STATUS:CANCELLED')), START, END)["items"] == []


def test_calendar_boundary_overlap_empty_and_exclusive_window_end():
    assert parse_calendar('<d:multistatus xmlns:d="DAV:"/>', START, END)["items"] == []
    event = 'BEGIN:VEVENT\nDTSTART:20261013T220000Z\nDTEND:20261014T010000Z\nSUMMARY:Overnachting\nEND:VEVENT'
    assert len(parse_calendar(calendar(event), START, END)["items"]) == 1
    assert len(parse_calendar(calendar(event.replace('DTEND:20261014T010000Z', 'DURATION:PT3H')), START, END)["items"]) == 1
    assert parse_calendar(calendar(event.replace('20261013T220000Z', '20261016T000000Z').replace('20261014T010000Z', '20261016T010000Z')), START, END)["items"] == []


@pytest.mark.parametrize("event", [
    'BEGIN:VEVENT\nSUMMARY:Geen start\nEND:VEVENT',
    'BEGIN:VEVENT\nDTSTART:20261014T100000\nEND:VEVENT',
    'BEGIN:VEVENT\nDTSTART:20261014T100000Z\nRRULE:FREQ=DAILY\nEND:VEVENT',
    'BEGIN:VEVENT\nDTSTART:20261014T100000Z\nDTSTART:20261014T100000Z\nEND:VEVENT',
    'BEGIN:VEVENT\nDTSTART:20261014T100000Z',
])
def test_calendar_failure_never_silently_omits_unexpanded_or_invalid_events(event):
    with pytest.raises((ProviderError, KeyError)):parse_calendar(calendar(event), START, END)
    with pytest.raises(ProviderError):parse_calendar('<!DOCTYPE x><d:multistatus xmlns:d="DAV:"/>', START, END)


def test_offers_export_normal_owner_isolation_hidden_and_newest_first(tmp_path):
    path = tmp_path / "offers.db"
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE users(id,email); CREATE TABLE profiles(id,user_id,is_results_hidden); CREATE TABLE ads(id,profile_id,title,url,price_cents,currency,first_seen_at,site,is_active,is_hidden,viewed_at); INSERT INTO users VALUES(1,"one@example.test"),(2,"two@example.test"); INSERT INTO profiles VALUES(1,1,0),(2,2,0),(3,1,1);')
        for i,profile,hidden,viewed in [(1,1,0,None),(2,2,0,None),(3,3,0,None),(4,1,1,None),(5,1,0,'viewed'),(6,1,0,None)]:
            db.execute('INSERT INTO ads VALUES(?,?,?,?,?,?,?,?,?,?,?)',(i,profile,'Offer','https://offer.example.test/'+str(i),1000,'EUR',f'2026-10-14T10:0{i}:00+00:00','Site',1,hidden,viewed))
    with sqlite3.connect(path) as db:
        db.execute('ALTER TABLE ads ADD COLUMN thumbnail_url TEXT')
        db.execute('UPDATE ads SET thumbnail_url=? WHERE id=6',('https://images.example.test/offer.jpg',))
        db.execute('UPDATE ads SET thumbnail_url=? WHERE id=1',('javascript:alert(1)',))
    data = export.export_offers(path, "ONE@example.test")
    assert [o["id"] for o in data["offers"]] == ["6", "1"]
    assert data["offers"][0]["imageUrl"] == 'https://images.example.test/offer.jpg'
    assert 'imageUrl' not in data['offers'][1]
    assert statistics_payload(data)["offers"][0]["priceCents"] == 1000
    assert export.export_offers(path, "missing@example.test")["offers"] == []
    assert path.exists()
    with pytest.raises(ValueError):export.export_offers(path, "")
    with pytest.raises(FileNotFoundError):export.export_offers(tmp_path / 'missing.db', 'one@example.test')
    assert not (tmp_path / 'missing.db').exists()


def test_offers_publish_normal_tls_no_redirect_credentials_in_headers_only():
    request = Mock(return_value=Mock(status_code=200))
    config = {"url": "https://deck.example.test/api/widget-ingest/offers", "token": "synthetic-long-token-123456789012345678"}
    payload = {"schemaVersion": 1, "offers": [], "generatedAt": "2026-10-14T10:00:00Z"}
    export.publish(config, payload, request)
    kwargs = request.call_args.kwargs
    assert kwargs["verify"] is True and kwargs["allow_redirects"] is False
    assert kwargs["headers"]["Authorization"] == "Bearer " + config["token"]
    assert config["token"] not in request.call_args.args[0]
    for url in ['http://deck.example.test/api/widget-ingest/offers','https://user:pass@deck.example.test/api/widget-ingest/offers','https://deck.example.test/api/widget-ingest/offers?token=secret']:
        with pytest.raises(ValueError):export.publish({**config,'url':url},payload,request)
    request.return_value.status_code = 403
    with pytest.raises(ValueError):export.publish(config,payload,request)


def test_offers_publish_internal_http_requires_explicit_private_ip_and_scoped_token():
    """An internal producer may use LAN HTTP only by explicit configuration; public HTTP stays rejected."""
    request = Mock(return_value=Mock(status_code=200))
    config = {"url": "http://192.168.20.164:8080/api/widget-ingest/offers", "token": "synthetic-long-token-123456789012345678", "allowHttp": True}
    export.publish(config, {}, request)
    assert request.call_count == 1
    for change in [{"allowHttp": False}, {"url": "http://8.8.8.8/api/widget-ingest/offers"}, {"url": "http://public.example.test/api/widget-ingest/offers"}, {"token": "short"}]:
        with pytest.raises(ValueError):export.publish({**config, **change}, {}, request)
    assert request.call_count == 1
