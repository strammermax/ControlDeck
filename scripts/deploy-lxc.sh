#!/usr/bin/env bash
# Root-owned helper: deploy a verified bundle and restore the previous release on failure.
set -euo pipefail
[[ $(id -u) -eq 0 && $# -eq 3 ]] || { echo 'Expected: sudo controldeck-deploy BUNDLE SHA256 COMMIT' >&2; exit 1; }
bundle=$(realpath -- "$1")
digest=$2
commit=$3
[[ $digest =~ ^[a-f0-9]{64}$ && $commit =~ ^[a-f0-9]{40}$ ]] || exit 2
[[ -f $bundle && $bundle == /home/controldeck-runner/*/controldeck-linux.tar.gz ]] || { echo 'Unexpected bundle location' >&2; exit 2; }
exec 9>/run/lock/controldeck-deploy.lock
flock -w 300 9
release="/opt/controldeck/releases/$commit"
previous=$(readlink -f /opt/controldeck/current || true)
stage=$(mktemp -d /opt/controldeck/releases/.stage-XXXXXX)
trap 'rm -rf -- "$stage"' EXIT
# Copy first: checksum and extraction operate on the same root-owned file.
install -m 0600 "$bundle" "$stage/bundle.tar.gz"
printf '%s  %s\n' "$digest" "$stage/bundle.tar.gz" | sha256sum -c -
python3 - "$stage" "$commit" <<'PY'
import json, pathlib, sys, tarfile
stage = pathlib.Path(sys.argv[1])
with tarfile.open(stage / 'bundle.tar.gz') as archive:
    for item in archive.getmembers():
        if not (item.isfile() or item.isdir()):
            raise SystemExit('Only regular files and directories are allowed')
        path = pathlib.PurePosixPath(item.name)
        if path.is_absolute() or '..' in path.parts:
            raise SystemExit('Unsafe archive path')
    archive.extractall(stage, filter='data')
metadata = json.loads((stage / 'build-info.json').read_text())
if metadata['commit'] != sys.argv[2]:
    raise SystemExit('Commit does not match bundle metadata')
if not (stage / 'frontend/out/index.html').is_file():
    raise SystemExit('Frontend is missing')
PY
rm -- "$stage/bundle.tar.gz"
# The application has no schema migrations yet. Reassess rollback when migrations are added.
if [[ -d $release ]]; then
    # Repeated deployment of a commit reuses its immutable runtime.
    rm -rf -- "$stage"
else
    mv -- "$stage" "$release"
    # Build at the final location: venv entry points contain absolute paths.
    if ! python3 -m venv "$release/venv" || ! "$release/venv/bin/pip" install --disable-pip-version-check -r "$release/requirements.txt"; then
        rm -rf -- "$release"
        echo 'Dependency installation failed; current release was not changed.' >&2
        exit 1
    fi
fi
chmod -R a+rX "$release"
ln -sfn "$release" /opt/controldeck/current.next
mv -Tf /opt/controldeck/current.next /opt/controldeck/current
healthy=false
if systemctl restart controldeck; then
    for attempt in $(seq 1 30); do
        if curl -fsS http://127.0.0.1:8080/ready >/dev/null && \
           curl -fsS http://127.0.0.1:8080/health | python3 -c 'import json,sys; sys.exit(json.load(sys.stdin).get("commit") != sys.argv[1])' "$commit"; then
            healthy=true
            break
        fi
        sleep 2
    done
fi
if [[ $healthy == true ]]; then
    echo "Deployed $commit"
    exit 0
fi
echo 'New release did not become healthy; restoring previous release.' >&2
if [[ -n $previous && -d $previous && $previous != "$release" ]]; then
    ln -sfn "$previous" /opt/controldeck/current.next
    mv -Tf /opt/controldeck/current.next /opt/controldeck/current
    systemctl restart controldeck
else
    systemctl stop controldeck
fi
exit 1
