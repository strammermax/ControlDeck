#!/usr/bin/env bash
# Root bootstrap for the optional admin installation wizard on native Debian LXC.
set -euo pipefail
[[ $(id -u) -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# Needs the service account and accounts file from install-lxc.sh; a deployed release is not required.
if [[ ! -f /var/lib/controldeck/accounts.json ]] || ! getent group controldeck >/dev/null; then
    echo 'Run scripts/install-lxc.sh first.' >&2
    exit 1
fi
install -d -o root -g controldeck -m 0750 /var/lib/controldeck/installations /var/lib/controldeck/installations/results
install -d -o controldeck -g controldeck -m 0750 /var/lib/controldeck/installations/queue
install -d -o root -g root -m 0755 /opt/controldeck-integrations/installer/{scripts,deploy}
for filename in install-termix.sh uninstall-termix.sh install-linkwarden.sh; do
    install -o root -g root -m 0755 "$source_root/scripts/$filename" "/opt/controldeck-integrations/installer/scripts/$filename"
done
for filename in termix.compose.yml termix-gateway.conf termix-app.conf linkwarden.compose.yml; do
    install -o root -g root -m 0644 "$source_root/deploy/$filename" "/opt/controldeck-integrations/installer/deploy/$filename"
done
install -o root -g root -m 0755 "$source_root/scripts/install-worker.py" /usr/local/sbin/controldeck-install-worker
install -o root -g root -m 0644 "$source_root/deploy/controldeck-install.service" /etc/systemd/system/controldeck-install.service
install -o root -g root -m 0644 "$source_root/deploy/controldeck-install.timer" /etc/systemd/system/controldeck-install.timer
# Agent proxy: the only holder of the SSH key to the Proxmox nodes (docs/NODE-AGENT.md). Own user, no root.
if ! command -v ssh >/dev/null || ! command -v ssh-keyscan >/dev/null; then
    apt-get update
    apt-get install -y openssh-client
fi
id controldeck-ssh >/dev/null 2>&1 || useradd --system --home /var/lib/controldeck-ssh --shell /usr/sbin/nologin controldeck-ssh
# The web app may use the proxy socket (group controldeck-ssh) but cannot read the key (0600, owner controldeck-ssh).
usermod -aG controldeck-ssh controldeck
install -d -o controldeck-ssh -g controldeck-ssh -m 0700 /var/lib/controldeck-ssh
install -o root -g root -m 0755 "$source_root/scripts/controldeck-agent-proxy.py" /usr/local/sbin/controldeck-agent-proxy
install -o root -g root -m 0644 "$source_root/deploy/controldeck-agent-proxy.service" /etc/systemd/system/controldeck-agent-proxy.service
# The node agent itself is distributed from here to the nodes (module Cronjobs, step 3).
install -d -o root -g root -m 0755 /opt/controldeck-integrations/agent
install -o root -g root -m 0644 "$source_root/scripts/controldeck-agent.py" /opt/controldeck-integrations/agent/controldeck-agent
systemctl daemon-reload
systemctl enable --now controldeck-install.timer
systemctl start controldeck-install.service
systemctl enable controldeck-agent-proxy.service
systemctl restart controldeck-agent-proxy.service
# Remember where this checkout is, so ControlDeck can show the exact update command (backend/root_components.py).
checkout_owner=$(stat -c %U "$source_root")
checkout_commit=$(git -C "$source_root" rev-parse HEAD 2>/dev/null || git -c safe.directory="$source_root" -C "$source_root" rev-parse HEAD 2>/dev/null || echo "")
python3 - "$source_root" "$checkout_owner" "$checkout_commit" <<'PY'
import json, sys, time
from pathlib import Path
target = Path("/var/lib/controldeck/bootstrap.json")
target.write_text(json.dumps({"checkout": sys.argv[1], "owner": sys.argv[2], "commit": sys.argv[3] or None, "installedAt": int(time.time())}) + "\n")
PY
chown root:controldeck /var/lib/controldeck/bootstrap.json
chmod 0640 /var/lib/controldeck/bootstrap.json
# New group membership only applies to new processes.
if systemctl is-active --quiet controldeck; then systemctl restart controldeck; fi
echo 'Administrative module installation wizard and agent proxy are ready.'
