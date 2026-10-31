"""Read-only alert mailbox: list and read mails, never mark them read, managers only."""
import imaplib
import json
from unittest.mock import Mock

import pytest

from backend import mailbox
from backend.app import create_app

CONFIG = {"host": "imap.gmail.com", "port": 993, "username": "homelab@example.test", "password": "abcdabcdabcdabcd"}


def raw(subject, sender="NAS <nas@example.test>", body="Hallo", html=False, date="Sat, 31 Oct 2026 19:06:48 +0100"):
    kind = "text/html" if html else "text/plain"
    return (f"From: {sender}\r\nTo: homelab@example.test\r\nSubject: {subject}\r\nDate: {date}\r\n"
            f"Content-Type: {kind}; charset=utf-8\r\n\r\n{body}\r\n").encode()


class FakeIMAP:
    """A small inbox. Records the commands, so the test can prove nothing is written."""
    messages, calls, login_fails, selected_readonly = {}, [], False, None

    def __init__(self, host, port, timeout):
        assert (host, port) == ("imap.gmail.com", 993)

    def login(self, user, password):
        FakeIMAP.calls.append("LOGIN")
        if FakeIMAP.login_fails:
            raise imaplib.IMAP4.error("[AUTHENTICATIONFAILED] Invalid credentials")

    def select(self, box, readonly=False):
        FakeIMAP.selected_readonly = readonly
        return "OK", [str(len(FakeIMAP.messages)).encode()]

    def uid(self, command, *args):
        FakeIMAP.calls.append(f"{command} {args[-1]}")
        if command == "SEARCH":
            return "OK", [b" ".join(str(u).encode() for u in sorted(FakeIMAP.messages))]
        wanted = [int(u) for u in args[0].split(b",")]
        out = []
        for u in wanted:
            if u not in FakeIMAP.messages:
                continue
            data, seen = FakeIMAP.messages[u]
            flags = b"\\Seen" if seen else b""
            out += [(f"{u} (UID {u} FLAGS ({flags.decode()}) BODY[] {{{len(data)}}}".encode(), data), b")"]
        return "OK", out

    def logout(self):
        pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([
        {"email": "admin@example.test", "role": "admin"},
        {"email": "viewer@example.test", "role": "user", "modules": ["monitoring"]},
    ]))
    FakeIMAP.messages = {
        11: (raw("[NAS] Problemen gedetecteerd", body="SnapRAID-content ouder dan 7 dagen"), False),
        12: (raw("Sonarr - Test Notification", sender="Sonarr <x@example.test>"), True),
        13: (raw("=?utf-8?q?Sync_local_datastore_=27pbs-store1=27_failed?=", sender="pbs <root@pbs.home>",
                 body="<p>Job &amp; <b>failed</b></p><script>alert(1)</script>", html=True), False),
    }
    FakeIMAP.calls, FakeIMAP.login_fails = [], False
    monkeypatch.setattr(mailbox.imaplib, "IMAP4_SSL", FakeIMAP)
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True
    holder = {"value": {"CONTROLDECK_MAILBOX": json.dumps(CONFIG)}}
    app.extensions["controldeck_vault"] = Mock(read=lambda: holder["value"])

    def client(email="admin@example.test"):
        test_client = app.test_client()
        with test_client.session_transaction() as session:
            session["identity"] = {"email": email, "sub": email}
            session["csrf"] = "csrf"
        return test_client
    return client, holder


def test_list_normal_newest_first_classified_and_read_only(env):
    client, _ = env
    data = client().get("/api/monitoring/mail").get_json()
    rows = {row["uid"]: row for row in data["messages"]}
    assert rows[11]["system"] == "NAS" and rows[11]["level"] == "error" and rows[11]["unread"] is True
    assert rows[12]["system"] == "Sonarr" and rows[12]["level"] == "ok" and rows[12]["unread"] is False
    assert rows[13]["subject"] == "Sync local datastore 'pbs-store1' failed" and rows[13]["system"] == "PBS" and rows[13]["level"] == "error"
    assert FakeIMAP.selected_readonly is True
    assert any("BODY.PEEK" in call for call in FakeIMAP.calls), "fetch with PEEK: never sets \\Seen"
    assert not any(c.startswith(("STORE", "COPY", "MOVE", "EXPUNGE")) for c in FakeIMAP.calls)
    assert "abcdabcd" not in json.dumps(data)


def test_message_detail_html_is_reduced_to_text(env):
    client, _ = env
    detail = client().get("/api/monitoring/mail/13").get_json()
    assert detail["text"] == "Job & failed" and "alert(1)" not in detail["text"]
    assert detail["to"] == "homelab@example.test"
    assert any("BODY.PEEK[]" in call for call in FakeIMAP.calls)


def test_boundary_empty_inbox_cache_and_long_body(env, monkeypatch):
    client, _ = env
    admin = client()
    FakeIMAP.messages = {}
    assert admin.get("/api/monitoring/mail").get_json()["messages"] == []
    FakeIMAP.messages = {5: (raw("Lang", body="x" * 300_000), False)}
    assert admin.get("/api/monitoring/mail").get_json()["messages"] == [], "cached for a minute"
    assert len(admin.get("/api/monitoring/mail?refresh=1").get_json()["messages"]) == 1
    assert len(admin.get("/api/monitoring/mail/5").get_json()["text"]) == mailbox.MAX_TEXT


def test_failure_wrong_password_missing_config_unknown_message(env):
    client, holder = env
    admin = client()
    FakeIMAP.login_fails = True
    answer = admin.get("/api/monitoring/mail?refresh=1")
    assert answer.status_code == 502 and "app-wachtwoord" in answer.get_json()["error"] and "Invalid credentials" not in answer.get_data(as_text=True)
    FakeIMAP.login_fails = False
    assert admin.get("/api/monitoring/mail/999").status_code == 404
    holder["value"] = {}
    assert admin.get("/api/monitoring/mail?refresh=1").status_code == 404
    holder["value"] = {"CONTROLDECK_MAILBOX": json.dumps({**CONFIG, "host": "imap gmail"})}
    assert admin.get("/api/monitoring/mail?refresh=1").status_code == 503
    holder["value"] = {"CONTROLDECK_MAILBOX": "geen json"}
    assert admin.get("/api/monitoring/mail?refresh=1").status_code == 503


def test_access_managers_only(env):
    client, _ = env
    from flask.testing import FlaskClient
    assert client("viewer@example.test").get("/api/monitoring/mail").status_code == 403
    assert client("viewer@example.test").get("/api/monitoring/mail/11").status_code == 403
    anonymous = client().application.test_client()
    assert isinstance(anonymous, FlaskClient) and anonymous.get("/api/monitoring/mail").status_code == 401
    assert FakeIMAP.calls == [], "no mailbox access for refused requests"
