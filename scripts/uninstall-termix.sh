#!/usr/bin/env bash
# Removes the optional Termix integration; run as root by the install worker or manually.
# Keeps Docker, Nginx and all other ControlDeck settings. --delete-data also removes the Termix volume.
set -euo pipefail
[[ $(id -u) -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
delete_data=false
case "${1:-}" in
    '') ;;
    --delete-data) delete_data=true ;;
    *) echo 'Usage: uninstall-termix.sh [--delete-data]' >&2; exit 2 ;;
esac
compose=/opt/controldeck-integrations/termix/compose.yml
provider=/var/lib/controldeck/config/providers/termix.json
# 1. Close access first: disable the provider so no new sessions start.
if [[ -f $provider ]]; then
    python3 - "$provider" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
data = json.loads(path.read_text())
data.update(enabled=False, url=None)
path.write_text(json.dumps(data, indent=2) + '\n')
PY
fi
# 2. Remove the gateway and the runtime drop-in.
rm -f /etc/nginx/conf.d/controldeck-termix.conf /etc/systemd/system/controldeck.service.d/termix.conf
if systemctl is-active --quiet nginx; then nginx -t && systemctl reload nginx; fi
systemctl daemon-reload
systemctl restart controldeck
# 3. Stop and remove the container; the named volume is only removed on request.
if [[ -f $compose ]] && command -v docker >/dev/null 2>&1; then
    docker compose -p controldeck-integrations -f "$compose" down --remove-orphans
fi
if [[ $delete_data == true ]] && command -v docker >/dev/null 2>&1; then
    docker volume rm -f controldeck-integrations_termix-data >/dev/null
fi
rm -f -- "$compose"
for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8080/ready >/dev/null; then break; fi
    sleep 1
done
curl -fsS http://127.0.0.1:8080/ready >/dev/null
if [[ $delete_data == true ]]; then echo 'Termix removed; data deleted.'; else echo 'Termix removed; data kept.'; fi
