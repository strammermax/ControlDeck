"""Read-only view of the homelab alert mailbox (docs/MONITORING.md → Mail).

The account and app password live in Infisical (`CONTROLDECK_MAILBOX`). ControlDeck opens the inbox read-only
and fetches with BODY.PEEK, so nothing is marked as read, moved or deleted. Managers only: mails can contain
sensitive details.
"""
import email
import email.policy
import html
import imaplib
import json
import re
import threading
import time
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

from flask import g, jsonify, request

from backend.auth import filter_configuration, is_manager
from backend.configuration import ConfigurationError, load_config
from backend.vault import VaultError

HOST = re.compile(r"(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9-]{0,62})(?:\.[A-Za-z0-9-]{1,63})+")
LIST_LIMIT = 50
CACHE_SECONDS = 60
MAX_TEXT = 100_000
# Which system sent a mail, from sender name or subject; first match wins.
SYSTEMS = [("NAS", r"\[NAS"), ("PBS", r"\bpbs\b|datastore|proxmox backup"), ("Proxmox", r"\bpve-|proxmox"), ("Sonarr", r"sonarr"),
           ("Radarr", r"radarr"), ("Lidarr", r"lidarr"), ("Prowlarr", r"prowlarr"), ("SABnzbd", r"sabnzbd"), ("Seerr", r"seerr"),
           ("Nextcloud", r"nextcloud"), ("ControlDeck", r"controldeck"), ("OPNsense", r"opnsense"), ("Google", r"google")]
ERROR = re.compile(r"fail|fout|error|problem|onderbroken|undelivered|returned to sender|critical|down\b|niet bereikbaar", re.I)
OK = re.compile(r"success|geslaagd|hersteld|klaar|is klaar|test", re.I)


class MailboxError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.message, self.status = message, status


def mailbox_config(app):
    vault = app.extensions.get("controldeck_vault")
    if vault is None:
        raise MailboxError("Geen keyvault ingericht.", 503)
    try:
        raw = vault.read().get("CONTROLDECK_MAILBOX")
        config = json.loads(raw) if raw else None
    except (ValueError, VaultError):
        raise MailboxError("De mailbox-instellingen zijn niet beschikbaar. Controleer Infisical.", 503) from None
    if config is None:
        raise MailboxError("Nog geen mailbox ingesteld (CONTROLDECK_MAILBOX in Infisical).", 404)
    if not isinstance(config, dict) or set(config) - {"host", "port", "username", "password"} or not isinstance(config.get("host"), str) \
            or not HOST.fullmatch(config["host"]) or type(config.get("port", 993)) is not int or not 1 <= config.get("port", 993) <= 65535 \
            or not isinstance(config.get("username"), str) or "@" not in config["username"] or not isinstance(config.get("password"), str) or not config["password"]:
        raise MailboxError("Ongeldige mailbox-instellingen in Infisical.", 503)
    return {"port": 993, **config}


def decoded(value):
    try:
        return str(make_header(decode_header(value or "")))[:300]
    except (ValueError, LookupError):
        return (value or "")[:300]


def classify(sender, subject):
    text = f"{sender} {subject}"
    system = next((name for name, pattern in SYSTEMS if re.search(pattern, text, re.I)), "Overig")
    level = "error" if ERROR.search(subject) else "ok" if OK.search(subject) else "info"
    return system, level


def body_text(message):
    """Plain text of a message: the text/plain part, else HTML with tags removed. Bounded."""
    part = message.get_body(preferencelist=("plain", "html")) if hasattr(message, "get_body") else None
    if part is None:
        return ""
    try:
        content = part.get_content()
    except (LookupError, ValueError):
        content = (part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")
    if part.get_content_type() == "text/html":
        content = re.sub(r"(?is)<(script|style).*?</\1>", " ", content)
        content = html.unescape(re.sub(r"(?s)<br\s*/?>|</p>|</div>|</tr>", "\n", content))
        content = re.sub(r"<[^>]+>", "", content)
    return re.sub(r"\n{3,}", "\n\n", content).strip()[:MAX_TEXT]


def summary(uid, flags, raw_header):
    message = email.message_from_bytes(raw_header, policy=email.policy.default)
    name, address = parseaddr(message.get("From", ""))
    sender, subject = decoded(name) or address, decoded(message.get("Subject"))
    try:
        date = parsedate_to_datetime(message.get("Date")).timestamp()
    except (TypeError, ValueError, IndexError):
        date = None
    system, level = classify(sender, subject)
    return {"uid": uid, "from": sender[:200], "address": address[:200], "subject": subject, "date": date,
            "unread": b"\\Seen" not in flags, "system": system, "level": level}


class Mailbox:
    def __init__(self, app):
        self.app, self.lock, self.cache = app, threading.Lock(), (0.0, None)

    def connect(self):
        config = mailbox_config(self.app)
        try:
            connection = imaplib.IMAP4_SSL(config["host"], config["port"], timeout=15)
            connection.login(config["username"], config["password"])
            status, _ = connection.select("INBOX", readonly=True)
            if status != "OK":
                raise MailboxError("De inbox kan niet worden geopend.")
            return connection
        except imaplib.IMAP4.error:
            raise MailboxError("Aanmelden bij de mailbox mislukt. Controleer het app-wachtwoord in Infisical.") from None
        except OSError:
            raise MailboxError("De mailserver is niet bereikbaar.") from None

    def messages(self, force=False):
        with self.lock:
            stamp, cached = self.cache
            if cached is not None and not force and time.time() - stamp < CACHE_SECONDS:
                return {"messages": cached, "fetchedAt": stamp}
            connection = self.connect()
            try:
                status, data = connection.uid("SEARCH", None, "ALL")
                uids = data[0].split()[-LIST_LIMIT:] if status == "OK" and data and data[0] else []
                rows = []
                if uids:
                    status, data = connection.uid("FETCH", b",".join(uids), "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                    for item in data if status == "OK" else []:
                        if isinstance(item, tuple) and len(item) == 2:
                            meta = item[0]
                            uid = re.search(rb"UID (\d+)", meta)
                            flags = re.search(rb"FLAGS \(([^)]*)\)", meta)
                            if uid:
                                rows.append(summary(int(uid.group(1)), flags.group(1) if flags else b"", item[1]))
            except (imaplib.IMAP4.error, OSError):
                raise MailboxError("De mailbox gaf een fout bij het ophalen.") from None
            finally:
                try:
                    connection.logout()
                except (imaplib.IMAP4.error, OSError):
                    pass
            rows.sort(key=lambda row: (row["date"] or 0, row["uid"]), reverse=True)
            self.cache = (time.time(), rows)
            return {"messages": rows, "fetchedAt": self.cache[0]}

    def message(self, uid):
        connection = self.connect()
        try:
            status, data = connection.uid("FETCH", str(uid).encode(), "(FLAGS BODY.PEEK[])")
            raw = next((item for item in data if isinstance(item, tuple) and len(item) == 2), None) if status == "OK" else None
            if raw is None:
                raise MailboxError("Bericht niet gevonden.", 404)
        except (imaplib.IMAP4.error, OSError):
            raise MailboxError("De mailbox gaf een fout bij het ophalen.") from None
        finally:
            try:
                connection.logout()
            except (imaplib.IMAP4.error, OSError):
                pass
        flags = re.search(rb"FLAGS \(([^)]*)\)", raw[0])
        message = email.message_from_bytes(raw[1], policy=email.policy.default)
        return {**summary(uid, flags.group(1) if flags else b"", raw[1]), "to": decoded(message.get("To")), "text": body_text(message)}


def setup_mailbox(app, configuration_path):
    mailbox = Mailbox(app)
    app.extensions["controldeck_mailbox"] = mailbox

    @app.before_request
    def mailbox_access():
        if not request.path.startswith("/api/monitoring/mail") or g.account is None:
            return None
        try:
            allowed = any(module["id"] == "monitoring" for module in filter_configuration(load_config(configuration_path), g.account)["modules"])
        except ConfigurationError:
            allowed = False
        if not allowed or not is_manager(g.account):
            return jsonify(error="Alleen beheerders kunnen de mailbox lezen."), 403
        return None

    @app.get("/api/monitoring/mail")
    def mailbox_list():
        try:
            return jsonify(mailbox.messages(force=request.args.get("refresh") == "1"))
        except MailboxError as error:
            return jsonify(error=error.message), error.status

    @app.get("/api/monitoring/mail/<int:uid>")
    def mailbox_message(uid):
        if not 1 <= uid <= 2**32:
            return jsonify(error="Bericht niet gevonden."), 404
        try:
            return jsonify(mailbox.message(uid))
        except MailboxError as error:
            return jsonify(error=error.message), error.status
