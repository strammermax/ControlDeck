"""Create a minimal, versioned Linux deployment bundle from the built UI."""

import argparse
import hashlib
import json
from pathlib import Path
import tarfile
from python_licenses import collect
from version import validate

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version", help="yyyy.mm.dd.build from CI; defaults to the VERSION file")
    args = parser.parse_args()
    if not (ROOT / "frontend/out/index.html").is_file():
        raise SystemExit("Build the frontend before packaging")
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    version = validate(args.version or (ROOT / "VERSION").read_text().strip())
    (ROOT / "frontend/out/PYTHON-LICENSES.txt").write_text(collect(ROOT / "requirements.txt"), encoding="utf-8")
    metadata = {"version": version, "commit": args.commit}
    (ROOT / "build-info.json").write_text(json.dumps(metadata) + "\n")
    archive = dist / "controldeck-linux.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for relative in ("backend", "config", "frontend/out", "requirements.txt", "VERSION", "build-info.json", "LICENSE", "scripts/controldeck-agent.py"):
            bundle.add(ROOT / relative, arcname=relative, filter=clean_member)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (dist / "SHA256SUMS").write_text(f"{checksum}  {archive.name}\n")


def clean_member(member):
    if "__pycache__" in Path(member.name).parts or member.name.endswith(".pyc"):
        return None
    member.uid = member.gid = 0
    member.uname = member.gname = "root"
    return member


if __name__ == "__main__":
    main()
