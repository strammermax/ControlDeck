"""Public display URLs never contain provider credentials."""
import re
from urllib.parse import urlsplit, parse_qsl, quote

PRIVATE_KEYS = {"token", "access_token", "apikey", "api_key", "x-plex-token", "password", "secret", "authorization", "key", "sig", "signature", "x-amz-signature", "x-amz-credential", "x-goog-signature", "x-goog-credential"}


def display_url(value, image=False):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value) or "\\" in value:
        return None
    try:
        u = urlsplit(value)
        _ = u.port
        if u.scheme not in (("https",) if image else ("https", "http")) or not u.hostname or u.username or u.password:
            return None
        if any(k.casefold() in PRIVATE_KEYS for k, _ in parse_qsl(u.query)):
            return None
        return value
    except ValueError:
        return None


def website(source):
    value = source.get("webUrl") or source.get("url")
    if not display_url(value):
        return None
    value = value.rstrip("/")
    if source["kind"] == "plex" and not source.get("webUrl"):
        value += "/web"
    if source["kind"] == "prefect" and not source.get("webUrl") and value.endswith("/api"):
        value = value[:-4]
    if source["kind"] == "nextcloud-calendar" and not source.get("webUrl"):
        value = value.split("/remote.php/")[0] + "/index.php/apps/calendar"
    return value


def present(body, source, source_id):
    base = website(source)
    rows = []
    for original in body.get("items", []):
        row = dict(original)
        link = display_url(row.get("url"))
        if not link and base:
            if source["kind"] == "prefect" and re.fullmatch(r"[A-Za-z0-9-]{1,64}", row["id"]):
                link = base + "/runs/flow-run/" + quote(row["id"], safe="")
            else:
                link = base
            row["linkIsApplication"] = source["kind"] != "prefect"
        if link:
            row["url"] = link
        else:
            row.pop("url", None)
        image = display_url(row.get("imageUrl"), image=True)
        if source["kind"] == "plex" and re.fullmatch(r"[0-9]{1,10}", str(row.get("imageId", ""))):
            image = "/api/widget-images/" + source_id + "/" + str(row["imageId"])
        row.pop("imageId", None)
        if image:
            row["imageUrl"] = image
        else:
            row.pop("imageUrl", None)
        rows.append(row)
    return {**body, "items": rows, "sourceTitle": source["title"], "providerKind": source["kind"]}


def match_artwork(rows, media):
    """Only a unique, sufficiently long literal title prefix may supply download artwork."""
    def normalized(value):
        return re.sub(r"[^a-z0-9]", "", value.casefold())
    for row in rows:
        if row.get("imageUrl"):
            continue
        matches = [m for m in media if m.get("imageUrl") and len(normalized(m["title"])) >= 5 and normalized(row["title"]).startswith(normalized(m["title"]))]
        identities = {(m.get("url"), m["imageUrl"]) for m in matches}
        if len(identities) == 1:
            row["imageUrl"] = matches[0]["imageUrl"]
    return rows
