"""Monitoring e-mail notifications through the SMTP relay: when to mail, what, and who may configure it."""
import json
import smtplib
import time
from unittest.mock import Mock

import pytest

from backend import monitoring
from backend.app import create_app

H = {"X-CSRF-Token": "csrf"}
SETTINGS = {"enabled": True, "recipients": ["beheer@example.test"], "sender": "controldeck@example.test",
            "smtpHost": "192.168.20.1", "smtpPort": 25, "delayMinutes": 5, "learned": False}


class FakeSMTP:
    """Records sent messages; `fail` makes the next connection raise like an unreachable relay."""
    sent, fail, starttls_offered = [], False, False

    def __init__(self, host, port, timeout):
        if FakeSMTP.fail:
            raise ConnectionRefusedError
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def ehlo(self, name):
        pass

    def has_extn(self, name):
        return FakeSMTP.starttls_offered

    def starttls(self):
        FakeSMTP.sent.append("STARTTLS")

    def send_message(self, message):
        FakeSMTP.sent.append(message)


@pytest.fixture
def env(tmp_path, monkeypatch):
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([
        {"email": "admin@example.test", "role": "admin"},
        {"email": "viewer@example.test", "role": "user", "modules": ["monitoring"]},
    ]))
    FakeSMTP.sent, FakeSMTP.fail, FakeSMTP.starttls_offered = [], False, False
    monkeypatch.setattr(monitoring.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(monitoring, "enrolled_nodes", lambda: set())
    monkeypatch.setattr(monitoring, "guests", lambda data_dir: {})
    monkeypatch.setenv("CONTROLDECK_BASE_URL", "https://controldeck.example.test")
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True
    app.extensions["controldeck_vault"] = Mock(read=lambda: {})
    state = {"ok": {}}
    monkeypatch.setattr(monitoring, "probe_central", lambda host, port: {"ok": state["ok"].get(host, True), "ip": "10.0.0.1", "error": None if state["ok"].get(host, True) else "Time-out (geen antwoord, mogelijk firewall)."})

    def client(email="admin@example.test"):
        test_client = app.test_client()
        with test_client.session_transaction() as session:
            session["identity"] = {"email": email, "sub": email}
            session["csrf"] = "csrf"
        return test_client
    return client, app.extensions["controldeck_monitor"], state


def at(monkeypatch, seconds):
    monkeypatch.setattr(monitoring.time, "time", lambda: seconds)


def test_down_mail_after_delay_once_then_recovery_mail(env, monkeypatch):
    client, monitor, state = env
    admin = client()
    assert admin.put("/api/monitoring/notifications", json=SETTINGS, headers=H).status_code == 200
    admin.post("/api/monitoring/connections", json={"source": "Prefect", "host": "remvebg.home", "port": 12345, "label": "removesky"}, headers=H)
    state["ok"]["remvebg.home"] = False
    at(monkeypatch, 1_000_000)
    monitor.check()
    assert FakeSMTP.sent == [], "not yet down for 5 minutes"
    at(monkeypatch, 1_000_000 + 301)
    monitor.check()
    assert len(FakeSMTP.sent) == 1
    mail = FakeSMTP.sent[0]
    assert mail["Subject"] == "ControlDeck monitoring: 1 onderbroken" and mail["To"] == "beheer@example.test"
    body = mail.get_content()
    assert "Prefect → remvebg.home:12345 (removesky), via ControlDeck" in body and "Time-out" in body
    assert "https://controldeck.example.test/#monitoring" in body
    at(monkeypatch, 1_000_000 + 900)
    monitor.check()
    assert len(FakeSMTP.sent) == 1, "no repeat mail while it stays down"
    state["ok"]["remvebg.home"] = True
    at(monkeypatch, 1_000_000 + 960)
    monitor.check()
    assert len(FakeSMTP.sent) == 2 and FakeSMTP.sent[1]["Subject"] == "ControlDeck monitoring: 1 hersteld"


def test_boundary_one_mail_for_several_and_learned_or_unknown_never_alert(env, monkeypatch):
    client, monitor, state = env
    admin = client()
    admin.put("/api/monitoring/notifications", json={**SETTINGS, "delayMinutes": 1}, headers=H)
    for host in ("a.home", "b.home"):
        admin.post("/api/monitoring/connections", json={"source": "App", "host": host, "port": 80}, headers=H)
        state["ok"][host] = False
    with monitoring.database(monitor.path) as db:
        db.execute("INSERT INTO learned VALUES ('aaaaaaaaaaaaaaaa', 137, 'arrsuite', '1.1.1.1', 443, ?, ?, '', '')", (time.time(), time.time()))
    state["ok"]["1.1.1.1"] = False
    at(monkeypatch, time.time())
    monitor.check()
    at(monkeypatch, time.time() + 120)
    monitor.check()
    assert len(FakeSMTP.sent) == 1 and FakeSMTP.sent[0]["Subject"] == "ControlDeck monitoring: 2 onderbroken"
    assert "1.1.1.1" not in FakeSMTP.sent[0].get_content(), "learned connections are excluded by default"
    with monitoring.database(monitor.path) as db:
        db.execute("UPDATE status SET ok=NULL, since=0")
    FakeSMTP.sent.clear()
    monitor.notify(time.time() + 99999)
    assert FakeSMTP.sent == [], "unknown (check failed) never mails as down or recovered"


def test_failure_relay_down_is_reported_and_retried(env, monkeypatch):
    client, monitor, state = env
    admin = client()
    admin.put("/api/monitoring/notifications", json={**SETTINGS, "delayMinutes": 1}, headers=H)
    admin.post("/api/monitoring/connections", json={"source": "App", "host": "a.home", "port": 80}, headers=H)
    state["ok"]["a.home"] = False
    at(monkeypatch, 2_000_000)
    monitor.check()
    FakeSMTP.fail = True
    at(monkeypatch, 2_000_000 + 120)
    monitor.check()
    assert monitor.notify_error == "Mail versturen mislukt: ConnectionRefusedError." and FakeSMTP.sent == []
    monkeypatch.undo()
    monkeypatch.setattr(monitoring.smtplib, "SMTP", FakeSMTP)
    assert admin.get("/api/monitoring/notifications").get_json()["lastError"] == "Mail versturen mislukt: ConnectionRefusedError."
    FakeSMTP.fail = False
    monkeypatch.setattr(monitoring, "probe_central", lambda host, port: {"ok": False, "ip": "10.0.0.1", "error": "Time-out"})
    monkeypatch.setattr(monitoring, "enrolled_nodes", lambda: set())
    monkeypatch.setattr(monitoring, "guests", lambda data_dir: {})
    monitor.check()
    assert len(FakeSMTP.sent) == 1, "the alert is sent on the next round once the relay is back"
    assert admin.get("/api/monitoring/notifications").get_json()["lastError"] is None


def test_starttls_used_when_relay_offers_it(env):
    client, _, _ = env
    admin = client()
    admin.put("/api/monitoring/notifications", json=SETTINGS, headers=H)
    FakeSMTP.starttls_offered = True
    assert admin.post("/api/monitoring/notifications/test", headers=H).get_json() == {"sent": True, "recipients": ["beheer@example.test"]}
    assert FakeSMTP.sent[0] == "STARTTLS" and FakeSMTP.sent[1]["Subject"] == "ControlDeck monitoring: testmail"


@pytest.mark.parametrize("body", [
    {**SETTINGS, "recipients": ["geen-adres"]},
    {**SETTINGS, "recipients": ["a@example.test"] * 11},
    {**SETTINGS, "recipients": []},
    {**SETTINGS, "sender": "x"},
    {**SETTINGS, "smtpHost": "a b"},
    {**SETTINGS, "smtpPort": 0},
    {**SETTINGS, "delayMinutes": 0},
    {**SETTINGS, "delayMinutes": "5"},
    {**SETTINGS, "enabled": "ja"},
    {**SETTINGS, "password": "x"},
    "niet-een-object",
])
def test_settings_failure_rejected(env, body):
    client, _, _ = env
    assert client().put("/api/monitoring/notifications", json=body, headers=H).status_code == 400


def test_settings_boundary_disabled_without_recipients_and_test_requires_one(env):
    client, _, _ = env
    admin = client()
    assert admin.put("/api/monitoring/notifications", json={**SETTINGS, "enabled": False, "recipients": []}, headers=H).status_code == 200
    assert admin.post("/api/monitoring/notifications/test", headers=H).status_code == 400
    assert FakeSMTP.sent == []


def test_access_settings_are_manager_only_and_need_csrf(env):
    client, _, _ = env
    viewer = client("viewer@example.test")
    assert viewer.get("/api/monitoring/notifications").status_code == 403, "recipients are personal data"
    assert viewer.put("/api/monitoring/notifications", json=SETTINGS, headers=H).status_code == 403
    assert viewer.post("/api/monitoring/notifications/test", headers=H).status_code == 403
    assert client().put("/api/monitoring/notifications", json=SETTINGS).status_code == 403
    assert client().get("/api/monitoring/notifications").get_json()["enabled"] is False, "nothing saved"


def test_relay_refusal_reason_is_shown(env, monkeypatch):
    """Regression: a refused recipient showed only 'SMTPRecipientsRefused', hiding that the relay said
    'Relay access denied' (ControlDeck's VLAN not in the relay's trusted networks)."""
    client, _, _ = env
    admin = client()
    admin.put("/api/monitoring/notifications", json=SETTINGS, headers=H)

    def refuse(self, message):
        raise smtplib.SMTPRecipientsRefused({"beheer@example.test": (554, b"5.7.1 <beheer@example.test>: Relay access denied")})
    monkeypatch.setattr(FakeSMTP, "send_message", refuse)
    answer = admin.post("/api/monitoring/notifications/test", headers=H)
    assert answer.status_code == 502
    assert answer.get_json()["error"] == "Mail versturen mislukt: de gateway weigert de ontvanger (554 5.7.1 <beheer@example.test>: Relay access denied)."
