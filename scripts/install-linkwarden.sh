#!/usr/bin/env bash
# Reviewed installer for the optional low-resource bookmarks profile.
set -euo pipefail
[[ $(id -u) -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if ! command -v docker >/dev/null || ! docker compose version >/dev/null; then
    echo 'Install Docker and Compose first.' >&2
    exit 1
fi
# The existing 1512 MiB ControlDeck LXC is too small for another database/application stack.
memory_kb=$(awk '/^MemTotal:/{print $2}' /proc/meminfo)
[[ $memory_kb -ge 2097152 ]] || { echo 'Linkwarden needs a host with at least 2 GiB RAM; use a separate host or enlarge this LXC.' >&2; exit 1; }
free_kb=$(df -Pk /var/lib/docker | awk 'NR==2 {print $4}')
[[ $free_kb -ge 3145728 ]] || { echo 'Provide at least 3 GiB free Docker storage.' >&2; exit 1; }
[[ -f /etc/controldeck/linkwarden.env ]] || { echo 'Configure a root-only /etc/controldeck/linkwarden.env with POSTGRES_PASSWORD, NEXTAUTH_SECRET and NEXTAUTH_URL first.' >&2; exit 1; }
[[ $(stat -c %u /etc/controldeck/linkwarden.env) -eq 0 && $(stat -c %a /etc/controldeck/linkwarden.env) == 600 ]] || { echo 'Unsafe Linkwarden environment file.' >&2; exit 1; }
python3 - <<'PY'
from pathlib import Path
import re
from urllib.parse import urlsplit
values = {}
for line in Path('/etc/controldeck/linkwarden.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('\"').strip("'")
assert len(values.get('NEXTAUTH_SECRET', '')) >= 32, 'Provide a strong NEXTAUTH_SECRET'
assert re.fullmatch(r'[A-Za-z0-9_-]{32,}', values.get('POSTGRES_PASSWORD', '')), 'Use a strong URL-safe POSTGRES_PASSWORD'
parts = urlsplit(values.get('NEXTAUTH_URL', ''))
assert parts.scheme == 'https' and parts.hostname and parts.path == '/api/v1/auth' and not parts.username and not parts.password and not parts.query and not parts.fragment, 'Provide the public HTTPS NEXTAUTH_URL'
PY
install -d -m 0755 /opt/controldeck-integrations/linkwarden
install -m 0644 "$source_root/deploy/linkwarden.compose.yml" /opt/controldeck-integrations/linkwarden/compose.yml
docker compose --env-file /etc/controldeck/linkwarden.env -p controldeck-linkwarden -f /opt/controldeck-integrations/linkwarden/compose.yml up -d
for _attempt in $(seq 1 90); do
    if docker compose --env-file /etc/controldeck/linkwarden.env -p controldeck-linkwarden -f /opt/controldeck-integrations/linkwarden/compose.yml exec -T linkwarden node -e 'fetch("http://127.0.0.1:3000/api/v1/logins").then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))' >/dev/null; then
        python3 - <<'PY'
import json
import os
import pwd
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
values = dict(line.split('=', 1) for line in Path('/etc/controldeck/linkwarden.env').read_text().splitlines() if line and not line.startswith('#') and '=' in line)
parts = urlsplit(values['NEXTAUTH_URL'].strip().strip('\"').strip("'"))
root = Path('/var/lib/controldeck/linkwarden')
root.mkdir(mode=0o700, exist_ok=True)
owner = pwd.getpwnam('controldeck')
os.chown(root, owner.pw_uid, owner.pw_gid)
fd, temporary = tempfile.mkstemp(dir=root)
with os.fdopen(fd, 'w') as output:
    json.dump({'url': f'{parts.scheme}://{parts.netloc}'}, output)
os.chown(temporary, owner.pw_uid, owner.pw_gid)
os.replace(temporary, root/'connection.json')
PY
        echo 'Linkwarden is ready and connected. Verify the public HTTPS route before use.' 
        exit 0
    fi
    sleep 3
done
echo 'Linkwarden did not become ready; inspect the Docker logs.' >&2
exit 1
