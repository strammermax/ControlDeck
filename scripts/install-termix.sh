#!/usr/bin/env bash
# Optional integration; run as root in an existing ControlDeck Debian LXC.
set -euo pipefail
[[ $(id -u) -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ -f /var/lib/controldeck/accounts.json && -d /opt/controldeck/current ]] || { echo 'Install ControlDeck and its accounts first.' >&2; exit 1; }
apt-get update
apt-get install -y nginx curl
if ! command -v docker >/dev/null 2>&1; then apt-get install -y docker.io; fi
if ! docker compose version >/dev/null 2>&1; then apt-get install -y docker-compose; fi
systemctl enable --now docker
install -d -m 0700 /opt/controldeck-integrations/termix
install -m 0600 "$source_root/deploy/termix.compose.yml" /opt/controldeck-integrations/termix/compose.yml
docker compose -p controldeck-integrations -f /opt/controldeck-integrations/termix/compose.yml up -d
for _ in $(seq 1 60); do
    if curl -fsS http://127.0.0.1:8090/users/registration-allowed >/dev/null; then break; fi
    sleep 2
done
curl -fsS http://127.0.0.1:8090/users/registration-allowed >/dev/null
# Seed the first profile as an administrator before exposing any gateway routes.
# Subsequent approved profiles are provisioned lazily by the authenticated bridge.
python3 - <<'PY'
import json, secrets, urllib.request, urllib.error
from pathlib import Path
accounts = json.loads(Path('/var/lib/controldeck/accounts.json').read_text())
admin = next(a for a in accounts if a['role'] == 'admin' and a.get('enabled', True) and a.get('ssoType', 'google') == 'google')
data = json.dumps({'username': admin['email'], 'password': secrets.token_urlsafe(48)}).encode()
try:
    with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8090/users/create', data=data, headers={'Content-Type':'application/json'}), timeout=10) as response:
        if response.status not in (200, 201): raise SystemExit('Termix bootstrap rejected')
except urllib.error.HTTPError as error:
    if error.code != 409: raise SystemExit('Termix bootstrap rejected')
PY
install -d -m 0755 /etc/systemd/system/controldeck.service.d
install -m 0644 "$source_root/deploy/termix-app.conf" /etc/systemd/system/controldeck.service.d/termix.conf
install -m 0644 "$source_root/deploy/termix-gateway.conf" /etc/nginx/conf.d/controldeck-termix.conf
nginx -t
systemctl daemon-reload
systemctl restart controldeck
systemctl enable --now nginx
systemctl reload nginx
# Preserve all other private module/provider settings.
python3 - <<'PY'
import json, os
from pathlib import Path
root = Path('/var/lib/controldeck/config')
modules = root / 'modules/core.json'
data = json.loads(modules.read_text())
next(m for m in data if m['id'] == 'terminal')['view'] = 'terminal'
modules.write_text(json.dumps(data, indent=2) + '\n')
provider = root / 'providers/termix.json'
provider.write_text(json.dumps({'id':'termix','type':'termix','label':'Termix','enabled':True,'url':'https://controldeck.vanburik.info/termix/'}, indent=2) + '\n')
os.chmod(provider, 0o640)
import grp
os.chown(provider, 0, grp.getgrnam('controldeck').gr_gid)
PY
curl -fsS http://127.0.0.1:8080/ready
echo 'Termix installed behind the authenticated ControlDeck gateway.'
