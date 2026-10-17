"""Run on the Koopjesbot host. Read only one user's newest unread offers, then publish.

Bootstrap uses the existing infisical-secret-client. No credentials or offer content are logged.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl
from ipaddress import ip_address
import requests


def export_offers(database, email):
    if not isinstance(email, str) or "@" not in email or len(email) > 254:
        raise ValueError("Een expliciet Koopjesbot-account is vereist.")
    path = Path(database).resolve(strict=True)
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        has_image = "thumbnail_url" in {r[1] for r in db.execute("PRAGMA table_info(ads)")}
        image_column = "a.thumbnail_url" if has_image else "NULL"
        rows = db.execute(f"""SELECT a.id, a.title, a.url, a.price_cents, a.currency, a.first_seen_at, a.site, {image_column} AS thumbnail_url
            FROM ads a JOIN profiles p ON p.id=a.profile_id JOIN users u ON u.id=p.user_id
            WHERE lower(u.email)=? AND a.is_active=1 AND a.is_hidden=0
              AND p.is_results_hidden=0 AND a.viewed_at IS NULL
            ORDER BY a.first_seen_at DESC, a.id DESC LIMIT 10""", (email.casefold(),)).fetchall()
    values = []
    for row in rows:
        link = urlsplit(row["url"])
        if link.scheme not in ("http", "https") or not link.hostname or link.username or link.password or len(row["url"]) > 1024:
            continue
        stamp = datetime.fromisoformat(row["first_seen_at"].replace("Z", "+00:00"))
        # SQLite CURRENT_TIMESTAMP and Koopjesbot now_iso are UTC.
        stamp = stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp
        values.append({"id": str(row["id"]), "title": row["title"][:200], "url": row["url"], "priceCents": row["price_cents"],
                       "currency": row["currency"] or "EUR", "firstSeenAt": stamp.astimezone(timezone.utc).isoformat(), "site": row["site"][:80]})
        image = row["thumbnail_url"]
        if isinstance(image, str) and len(image) <= 2048 and not any(ord(c) < 33 for c in image) and "\\" not in image:
            parsed = urlsplit(image)
            if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password and not any(k.casefold() in {"token", "access_token", "apikey", "api_key", "password", "secret", "signature", "sig", "x-amz-signature", "x-amz-credential"} for k, _ in parse_qsl(parsed.query)):
                values[-1]["imageUrl"] = image
    return {"schemaVersion": 1, "offers": values, "generatedAt": datetime.now(timezone.utc).isoformat()}


def publish(config, payload, request=requests.post):
    url, token = config["url"], config["token"]
    target = urlsplit(url)
    internal_http = False
    if target.scheme == "http" and config.get("allowHttp") is True:
        try:
            internal_http = ip_address(target.hostname).is_private
        except ValueError:
            pass
    if (target.scheme != "https" and not internal_http) or not target.hostname or target.username or target.password or target.query or target.fragment or not target.path.startswith("/api/widget-ingest/"):
        raise ValueError("Gebruik een HTTPS-aanleveradres zonder geheimen in de URL.")
    if not isinstance(token, str) or not 32 <= len(token) <= 256:
        raise ValueError("Een aanlevercredential is vereist.")
    body = json.dumps(payload).encode()
    if len(body) > 16000:
        raise ValueError("De aanbiedingen passen niet binnen de aanleverlimiet.")
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    if config.get("accessClientId") and config.get("accessClientSecret"):
        headers.update({"CF-Access-Client-Id": config["accessClientId"], "CF-Access-Client-Secret": config["accessClientSecret"]})
    response = request(url, data=body, headers=headers, timeout=(4, 12), allow_redirects=False, verify=config.get("caBundle") or True)
    if response.status_code != 200:
        raise ValueError("ControlDeck heeft de aanbiedingen niet geaccepteerd.")


def main():
    from infisical_secret_client import InfisicalClient, InfisicalConfig
    try:
        config = json.loads(InfisicalClient(InfisicalConfig.from_env()).load_bundle()["CONTROLDECK_OFFERS_EXPORT"])
        publish(config, export_offers(config["database"], config["email"]))
        print("Koopjesbot-aanbiedingen bijgewerkt.")
    except Exception:
        raise SystemExit("Koopjesbot-widget kon niet worden bijgewerkt; controleer bron, toegang en Infisical.") from None


if __name__ == "__main__":
    main()
