import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("prune", Path(__file__).resolve().parent.parent / "scripts/prune.py")
prune = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prune)


def release(tag, day):
    return {"tagName": tag, "createdAt": f"2026-10-{day:02d}T12:00:00Z"}


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_releases_to_delete(case):
    if case == "normaal":
        releases = [release(f"v2026.10.{day:02d}.{day}", day) for day in range(1, 6)]
        assert prune.releases_to_delete(releases, 3) == ["v2026.10.02.2", "v2026.10.01.1"]
    elif case == "boundary":
        releases = [release(f"v2026.10.{day:02d}.{day}", day) for day in range(1, 4)]
        assert prune.releases_to_delete(releases, 3) == []
        assert prune.releases_to_delete(releases, 1) == ["v2026.10.02.2", "v2026.10.01.1"]
    else:
        # Historical semver releases and malformed entries are never selected.
        releases = [release("v0.4.0", 1), release("v0.1.0", 1), {"tagName": "v2026.10.05.9"}, None, release("v2026.10.05.0", 2), release("v2026.10.05.7", 3)]
        assert prune.releases_to_delete(releases, 1) == []
        for keep in (0, -1, True, "30"):
            with pytest.raises(ValueError):
                prune.releases_to_delete([], keep)


def image(identifier, day, *tags):
    return {"id": identifier, "created_at": f"2026-10-{day:02d}T12:00:00Z", "metadata": {"container": {"tags": list(tags)}}}


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_images_to_delete(case):
    if case == "normaal":
        versions = [image(day, day, f"sha-{day}") for day in range(1, 6)]
        assert prune.images_to_delete(versions, 2) == [3, 2, 1]
    elif case == "boundary":
        # "main" is protected even when it is old; untagged layers beyond the limit go.
        versions = [image(1, 1, "main"), image(2, 2), image(3, 3, "sha-3")]
        assert prune.images_to_delete(versions, 1) == [2]
        assert prune.images_to_delete(versions, 3) == []
    else:
        assert prune.images_to_delete([None, {"id": "x", "created_at": "2026"}, {"id": 5}], 1) == []
        with pytest.raises(ValueError):
            prune.images_to_delete([], 0)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_release_notes(case):
    if case == "normaal":
        notes = prune.release_notes(["Add Proxmox overview (abc1234)", "Fix CA check (def5678)"], "2026.10.05.31", "owner/repo")
        assert notes.startswith("ControlDeck 2026.10.05.31\n") and "- Add Proxmox overview (abc1234)" in notes and "- Fix CA check (def5678)" in notes
        assert "https://github.com/owner/repo/blob/main/docs/CHANGELOG.md" in notes
    elif case == "boundary":
        assert "Geen nieuwe commits" in prune.release_notes([], "2026.10.05.31", "owner/repo")
    else:
        notes = prune.release_notes(["", "   ", None, "Real change (1)"], "2026.10.05.31", "owner/repo")
        assert notes.count("\n- ") == 1
