"""Read-only API adapters. Only normalized display fields leave the service."""
import math
from pathlib import PurePosixPath
from datetime import datetime, timezone
from urllib.parse import urlsplit
import re
from .transport import ProviderError
from .presentation import display_url, website


def text(value, limit=300):
    if value is None:
        return ""
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise ProviderError("Ongeldige brongegevens.")
    return str(value)[:limit]


def number(value):
    if isinstance(value, bool):
        raise ProviderError("Ongeldige brongegevens.")
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise ProviderError("Ongeldige brongegevens.") from None
    if not math.isfinite(result) or result < 0 or result > 2**53 - 1:
        raise ProviderError("Ongeldige brongegevens.")
    return result


def records(value, limit=1000):
    if not isinstance(value, list) or len(value) > limit or any(not isinstance(x, dict) for x in value):
        raise ProviderError("Ongeldige brongegevens.")
    return value


def item(identifier, title, subtitle="", status="", progress=None, date=None):
    result = {"id": text(identifier), "title": text(title) or "Naamloos", "subtitle": text(subtitle), "status": text(status, 80)}
    if progress is not None:
        value = number(progress)
        if value > 100:
            raise ProviderError("Ongeldige voortgang.")
        result["progress"] = value
    if date is not None:
        result["date"] = text(date, 80)
    return result


def result(items, stats=None):
    return {"items": items[:50], "stats": stats or [], "truncated": len(items) > 50}


def qbittorrent(t, s):
    headers = {"Authorization": "Bearer " + s["apiKey"]} if s.get("apiKey") else {}
    if not headers:
        login = t.call("/api/v2/auth/login", "POST", data={"username": s["username"], "password": s["password"]}, raw=True,
                       headers={"Referer": t.url + "/"})
        if login.strip() != "Ok.":
            raise ProviderError("qBittorrent weigert de aanmelding.")
    rows = records(t.call("/api/v2/torrents/info", params={"limit": 51, "sort": "priority"}, headers=headers), 51)
    values = [item(r["hash"], r["name"], f"{number(r.get('dlspeed', 0)) / 1024:.0f} KiB/s", r["state"], number(r["progress"]) * 100) for r in rows]
    return result(values)


def sabnzbd(t, s):
    queue = t.call("/api", "POST", data={"mode": "queue", "output": "json", "apikey": s["apiKey"], "limit": 51})["queue"]
    rows = records(queue["slots"], 51)
    return result([item(r["nzo_id"], r["filename"], r.get("timeleft", ""), r["status"], r["percentage"]) for r in rows],
                  [{"label": "Snelheid", "value": text(queue.get("speed"))}, {"label": "Resterend", "value": text(queue.get("sizeleft"))}])


def plex(t, s):
    payload = t.call("/status/sessions", headers={"X-Plex-Token": s["apiKey"], "Accept": "application/json"})["MediaContainer"]
    rows = records(payload.get("Metadata", []), 1000)
    machine = payload.get("machineIdentifier")
    if not machine and any(re.fullmatch(r"[0-9]{1,10}", str(r.get("ratingKey", ""))) for r in rows):
        try:
            machine = t.call("/", headers={"X-Plex-Token": s["apiKey"], "Accept": "application/json"})["MediaContainer"].get("machineIdentifier")
        except (ProviderError, KeyError, TypeError):
            pass
    values = []
    for r in rows:
        player = r.get("Player", {})
        progress = number(r.get("viewOffset", 0)) / number(r["duration"]) * 100 if r.get("duration") else None
        values.append(item(r.get("sessionKey", r.get("ratingKey")), r.get("title"), r.get("grandparentTitle", ""), player.get("state", ""), min(progress, 100) if progress is not None else None))
        if re.fullmatch(r"[0-9]{1,10}", str(r.get("ratingKey", ""))):
            values[-1]["imageId"] = str(r["ratingKey"])
            if isinstance(machine, str) and re.fullmatch(r"[A-Za-z0-9-]{1,128}", machine):
                base = website(s) or t.url + "/web"
                if base.endswith("/web"):
                    base += "/index.html"
                values[-1]["url"] = base.rstrip("/") + "#!/server/" + machine + "/details?key=%2Flibrary%2Fmetadata%2F" + str(r["ratingKey"])
    return result(values, [{"label": "Actieve streams", "value": str(len(values))}])


def seerr(t, s):
    headers = {"X-Api-Key": s["apiKey"]}
    payload = t.call("/api/v1/request", params={"take": 50, "skip": 0, "sort": "added"}, headers=headers)
    rows = records(payload["results"], 50)
    statuses = {1: "In afwachting", 2: "Goedgekeurd", 3: "Afgewezen", 4: "Mislukt", 5: "Afgerond"}
    values = []
    for index, r in enumerate(rows):
        media = r.get("media") or {}
        title = media.get("title")
        poster = media.get("posterPath")
        kind, identifier = r.get("type"), media.get("tmdbId")
        # Enrich only a few missing titles, with a short timeout and an honest ID fallback.
        if (not title or not poster) and index < 10 and kind in ("movie", "tv") and type(identifier) is int and identifier > 0:
            try:
                details = t.call(f"/api/v1/{kind}/{identifier}", headers=headers, timeout=1.5)
                title = title or details.get("title") or details.get("name")
                poster = poster or details.get("posterPath")
            except ProviderError:
                pass
        values.append(item(r["id"], title or f"{text(kind)} #{text(identifier)}", "", statuses.get(r["status"], "Onbekend"), date=r.get("createdAt")))
        if kind in ("movie", "tv") and type(identifier) is int and identifier > 0:
            values[-1]["url"] = (website(s) or t.url) + f"/{kind}/{identifier}"
        if isinstance(poster, str) and re.fullmatch(r"/[A-Za-z0-9_.-]+", poster):
            values[-1]["imageUrl"] = "https://image.tmdb.org/t/p/w185" + poster
    return result(values)


def tdarr(t, s):
    headers = {"X-Api-Key": s["apiKey"]} if s.get("apiKey") else {}
    nodes = t.call("/api/v2/get-nodes", headers=headers)
    if not isinstance(nodes, dict) or len(nodes) > 100:
        raise ProviderError("Ongeldige Tdarr-nodes.")
    values = []
    for node in nodes.values():
        workers = node["workers"]
        if not isinstance(workers, dict) or len(workers) > 100:
            raise ProviderError("Ongeldige Tdarr-workers.")
        for worker in workers.values():
            values.append(item(worker["_id"], PurePosixPath(text(worker["file"])).name or "Worker", node["nodeName"], worker["status"], worker.get("percentage")))
    stats = t.call("/api/v2/stats/get-pies", "POST", json={"data": {"libraryId": ""}}, headers=headers)["pieStats"]
    return result(values, [{"label": "Bestanden", "value": str(int(number(stats["totalFiles"])))},
                           {"label": "Verwerkt", "value": str(int(number(stats["totalTranscodeCount"])))},
                           {"label": "Workers", "value": str(len(values))}])


def prefect(t, s):
    headers = {"Authorization": "Bearer " + s["apiKey"]} if s.get("apiKey") else {}
    kwargs = {"auth": (s["username"], s["password"])} if s.get("username") else {}
    rows = records(t.call("/flow_runs/filter", "POST", json={"limit": 50, "offset": 0, "sort": "START_TIME_DESC"}, headers=headers, **kwargs), 50)
    return result([item(r["id"], r["name"], "", (r.get("state") or {}).get("name", r.get("state_type", "Onbekend")), date=r.get("start_time") or r.get("expected_start_time")) for r in rows])


def statistics_payload(payload):
    """Versioned, bounded interchange for the user's newest Koopjesbot offers."""
    if not isinstance(payload, dict) or set(payload) != {"schemaVersion", "offers", "generatedAt"} or type(payload["schemaVersion"]) is not int or payload["schemaVersion"] != 1:
        raise ProviderError("Ongeldige statistieken.")
    values = []
    for offer in records(payload["offers"], 10):
        if set(offer) - {"imageUrl"} != {"id", "title", "url", "priceCents", "currency", "firstSeenAt", "site"}:
            raise ProviderError("Ongeldige aanbieding.")
        url = offer["url"]
        if not isinstance(url, str) or len(url) > 1024 or any(ord(c) < 33 for c in url) or "\\" in url:
            raise ProviderError("Ongeldige advertentielink.")
        parsed = urlsplit(url)
        _ = parsed.port
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise ProviderError("Ongeldige advertentielink.")
        price = offer["priceCents"]
        if price is not None and (type(price) is not int or not 0 <= price <= 10**12):
            raise ProviderError("Ongeldige prijs.")
        if not isinstance(offer["currency"], str) or not re.fullmatch(r"[A-Z]{3}", offer["currency"]):
            raise ProviderError("Ongeldige valuta.")
        for field, limit in [("id", 64), ("title", 200), ("site", 80)]:
            if not isinstance(offer[field], str) or not 1 <= len(offer[field]) <= limit:
                raise ProviderError("Ongeldige aanbieding.")
        value = dict(offer)
        if "imageUrl" in offer:
            image = display_url(offer["imageUrl"], image=True)
            if image is None:
                raise ProviderError("Ongeldige productafbeelding.")
            value["imageUrl"] = image
        value["firstSeenAt"] = timestamp(offer["firstSeenAt"])
        values.append(value)
    if len({o["id"] for o in values}) != len(values):
        raise ProviderError("Dubbele aanbiedingen.")
    return {"schemaVersion": 1, "offers": sorted(values, key=lambda o: o["firstSeenAt"], reverse=True), "generatedAt": timestamp(payload["generatedAt"])}


def timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ProviderError("Ongeldig tijdstip.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ProviderError("Tijdzone ontbreekt.")
    return parsed.astimezone(timezone.utc).isoformat()


ADAPTERS = {"qbittorrent": qbittorrent, "sabnzbd": sabnzbd, "plex": plex, "seerr": seerr, "tdarr": tdarr, "prefect": prefect}
