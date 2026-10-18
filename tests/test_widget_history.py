import pytest

from backend.widgets.adapters import sabnzbd, tdarr
from backend.widgets.presentation import present
from backend.widgets.transport import ProviderError

SAB = {"kind": "sabnzbd", "apiKey": "k" * 32, "url": "https://sab.example.test", "title": "SABnzbd"}
TDARR = {"kind": "tdarr", "url": "https://tdarr.example.test", "title": "Tdarr"}
QUEUE = {"queue": {"slots": [{"nzo_id": "q1", "filename": "Bezig.mkv", "status": "Downloading", "percentage": "40", "timeleft": "0:10"}], "speed": "5 MB/s", "sizeleft": "1 GB"}}
HISTORY = {"history": {"slots": [
    {"nzo_id": "h1", "name": "Carrie S01E07", "status": "Completed", "completed": 1792220400, "size": "2.1 GB", "category": "tv"},
    {"nzo_id": "h2", "name": "Kapot", "status": "Failed", "completed": 1792220000, "size": "1 GB", "category": "*"},
]}}
NODES = {"n": {"nodeName": "Node", "workers": {"w": {"_id": "w", "file": "/m/bezig.mkv", "status": "processing", "percentage": 10}}}}
PIES = {"pieStats": {"totalFiles": 10, "totalTranscodeCount": 3}}


def row(name, decision, when, old=2.0, new=1.0):
    return {"_id": f"/mnt/private/{name}", "file": f"/mnt/private/{name}", "TranscodeDecisionMaker": decision, "lastTranscodeDate": when, "oldSize": old, "newSize": new}


class Fake:
    def __init__(self, replies):
        self.replies, self.calls = replies, []

    def call(self, path="", method="GET", **kwargs):
        key = (kwargs.get("data") or {}).get("mode") or (((kwargs.get("json") or {}).get("data") or {}).get("opts") or {}).get("table") or path
        self.calls.append((path, key, kwargs))
        value = self.replies[key]
        if isinstance(value, Exception):
            raise value
        return value


def test_sabnzbd_history_normaal_queue_then_last_completed():
    body = sabnzbd(Fake({"queue": QUEUE, "history": HISTORY}), SAB)
    assert [(i["title"], i["section"], i["status"]) for i in body["items"]] == [
        ("Bezig.mkv", "Bezig", "Downloading"), ("Carrie S01E07", "Laatst voltooid", "Voltooid"), ("Kapot", "Laatst voltooid", "Mislukt")]
    done = body["items"][1]
    assert done["subtitle"] == "2.1 GB · tv" and done["date"].startswith("2026-10-17")
    assert body["items"][2]["subtitle"] == "1 GB", "the '*' category is not shown"


def test_sabnzbd_history_boundary_empty_queue_and_history_limit():
    fake = Fake({"queue": {"queue": {"slots": [], "speed": "0", "sizeleft": "0"}}, "history": {"history": {"slots": []}}})
    assert sabnzbd(fake, SAB)["items"] == []
    assert [k for _, k, kw in fake.calls if k == "history"] and next(kw for _, k, kw in fake.calls if k == "history")["data"]["limit"] == 10


def test_sabnzbd_history_faal_keeps_the_queue():
    for broken in (ProviderError("weg"), {"history": {}}, {"history": {"slots": "x"}}):
        body = sabnzbd(Fake({"queue": QUEUE, "history": broken}), SAB)
        assert [i["title"] for i in body["items"]] == ["Bezig.mkv"]


def test_tdarr_history_normaal_only_real_conversions_newest_first():
    table = {"array": [row("oud.mkv", "Transcode success", 1780000000000), row("skip.mkv", "Not required", 1790000000000),
                       row("nieuw.mkv", "Transcode success", 1781000000000, 4.0, 1.5)]}
    fake = Fake({"/api/v2/get-nodes": NODES, "table2": table, "/api/v2/stats/get-pies": PIES})
    items = tdarr(fake, TDARR)["items"]
    assert [(i["title"], i["section"]) for i in items] == [("bezig.mkv", "Bezig"), ("nieuw.mkv", "Laatst voltooid"), ("oud.mkv", "Laatst voltooid")]
    assert items[1]["subtitle"] == "4.00 GB → 1.50 GB" and items[1]["status"] == "Voltooid"
    request = next(kw for _, k, kw in fake.calls if k == "table2")["json"]["data"]
    assert request["sorts"] == [{"id": "lastTranscodeDate", "desc": True}]


def test_tdarr_history_boundary_limit_and_private_paths():
    table = {"array": [row(f"f{i}.mkv", "Transcode success", 1780000000000 + i) for i in range(50)]}
    items = tdarr(Fake({"/api/v2/get-nodes": {}, "table2": table, "/api/v2/stats/get-pies": PIES}), TDARR)["items"]
    assert len(items) == 10 and items[0]["title"] == "f49.mkv"
    assert all("/mnt/private" not in str(i) for i in items), "server paths never leave the adapter"


def test_tdarr_history_faal_keeps_workers_and_stats():
    for broken in (ProviderError("weg"), {"geen": []}, {"array": "x"}):
        body = tdarr(Fake({"/api/v2/get-nodes": NODES, "table2": broken, "/api/v2/stats/get-pies": PIES}), TDARR)
        assert [i["title"] for i in body["items"]] == ["bezig.mkv"] and body["stats"][0]["value"] == "10"


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_widget_heading_link(case):
    if case == "normaal":
        assert present({"items": []}, {"kind": "seerr", "url": "https://seerr.example.test/", "title": "Seerr"}, "s")["sourceUrl"] == "https://seerr.example.test/requests"
        assert present({"items": []}, SAB, "s")["sourceUrl"] == "https://sab.example.test"
    elif case == "boundary":
        source = {"kind": "seerr", "url": "http://10.0.0.5:5055", "webUrl": "https://requests.example.test", "title": "Seerr"}
        assert present({"items": []}, source, "s")["sourceUrl"] == "https://requests.example.test/requests", "the public web address wins"
    else:
        for url in ("https://user:pw@sab.example.test", "https://sab.example.test?apikey=secret", "javascript:alert(1)"):
            assert "sourceUrl" not in present({"items": []}, {**SAB, "url": url}, "s"), url
