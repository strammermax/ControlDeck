"""Keeps the newest CI releases and container image versions; removes older ones.

Only CalVer releases (v<yyyy.mm.dd.build>) are pruned; historical semver releases stay. Image versions
tagged "main" are never removed. Git history is never touched; deleting a release also removes its tag.
"""
import argparse
import json
import re
import subprocess

CALVER_TAG = re.compile(r"v\d{4}\.\d{2}\.\d{2}\.[1-9]\d*")
PROTECTED_IMAGE_TAGS = {"main", "latest"}


def releases_to_delete(releases, keep):
    """releases: [{"tagName", "createdAt"}] from `gh release list --json`. Returns tags to delete, oldest last."""
    if not isinstance(keep, int) or isinstance(keep, bool) or keep < 1:
        raise ValueError("keep must be a positive integer")
    calver = [item for item in releases if isinstance(item, dict) and isinstance(item.get("tagName"), str) and CALVER_TAG.fullmatch(item["tagName"]) and isinstance(item.get("createdAt"), str)]
    calver.sort(key=lambda item: item["createdAt"], reverse=True)
    return [item["tagName"] for item in calver[keep:]]


def images_to_delete(versions, keep):
    """versions: GitHub package versions. Keeps the newest `keep` and every version tagged main/latest."""
    if not isinstance(keep, int) or isinstance(keep, bool) or keep < 1:
        raise ValueError("keep must be a positive integer")
    valid = [item for item in versions if isinstance(item, dict) and isinstance(item.get("id"), int) and isinstance(item.get("created_at"), str)]
    valid.sort(key=lambda item: item["created_at"], reverse=True)
    def tags(item):
        container = (item.get("metadata") or {}).get("container") or {}
        return set(container.get("tags") or [])
    return [item["id"] for item in valid[keep:] if not tags(item) & PROTECTED_IMAGE_TAGS]


def release_notes(subjects, version, repo):
    """Markdown notes from commit subjects since the previous release; empty history still yields a valid note."""
    lines = [f"ControlDeck {version}", ""]
    changes = [subject.strip() for subject in subjects if isinstance(subject, str) and subject.strip()]
    lines += ["## Wijzigingen", ""] + [f"- {subject}" for subject in changes] if changes else ["Geen nieuwe commits sinds de vorige release (herhaalde build)."]
    lines += ["", f"Volledige beschrijving per dag: [CHANGELOG](https://github.com/{repo}/blob/main/docs/CHANGELOG.md)"]
    return "\n".join(lines) + "\n"


def gh(*args):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("releases", "images", "notes"))
    parser.add_argument("--version", help="for notes: the release version")
    parser.add_argument("--since", help="for notes: previous release tag (omit for the last 20 commits)")
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--package", default="controldeck")
    parser.add_argument("--keep", type=int, default=30)
    args = parser.parse_args()
    if args.kind == "notes":
        revisions = f"{args.since}..HEAD" if args.since else "-20"
        subjects = subprocess.run(["git", "log", "--no-merges", "--pretty=%s (%h)", *revisions.split()], check=True, capture_output=True, text=True).stdout.splitlines()
        print(release_notes(subjects, args.version, args.repo), end="")
    elif args.kind == "releases":
        releases = json.loads(gh("release", "list", "--repo", args.repo, "--limit", "1000", "--json", "tagName,createdAt"))
        for tag in releases_to_delete(releases, args.keep):
            gh("release", "delete", tag, "--repo", args.repo, "--cleanup-tag", "--yes")
            print(f"Deleted release {tag}")
    else:
        owner = args.repo.split("/")[0]
        # --jq '.[]' prints one JSON object per line across all pages.
        lines = gh("api", "--paginate", "--jq", ".[]", f"/users/{owner}/packages/container/{args.package}/versions?per_page=100")
        versions = [json.loads(line) for line in lines.splitlines() if line.strip()]
        for version_id in images_to_delete(versions, args.keep):
            gh("api", "--method", "DELETE", f"/users/{owner}/packages/container/{args.package}/versions/{version_id}")
            print(f"Deleted image version {version_id}")


if __name__ == "__main__":
    main()
