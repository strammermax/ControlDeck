#!/usr/bin/env bash
# Root bootstrap for the optional admin installation wizard on native Debian LXC.
set -euo pipefail
[[ $(id -u) -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ -f /var/lib/controldeck/accounts.json && -d /opt/controldeck/current ]] || { echo 'Install ControlDeck first.' >&2; exit 1; }
install -d -o root -g controldeck -m 0750 /var/lib/controldeck/installations /var/lib/controldeck/installations/results
install -d -o controldeck -g controldeck -m 0750 /var/lib/controldeck/installations/queue
install -d -o root -g root -m 0755 /opt/controldeck-integrations/installer/{scripts,deploy}
install -o root -g root -m 0755 "$source_root/scripts/install-termix.sh" /opt/controldeck-integrations/installer/scripts/install-termix.sh
for filename in termix.compose.yml termix-gateway.conf termix-app.conf; do
    install -o root -g root -m 0644 "$source_root/deploy/$filename" "/opt/controldeck-integrations/installer/deploy/$filename"
done
install -o root -g root -m 0755 "$source_root/scripts/install-worker.py" /usr/local/sbin/controldeck-install-worker
install -o root -g root -m 0644 "$source_root/deploy/controldeck-install.service" /etc/systemd/system/controldeck-install.service
install -o root -g root -m 0644 "$source_root/deploy/controldeck-install.timer" /etc/systemd/system/controldeck-install.timer
systemctl daemon-reload
systemctl enable --now controldeck-install.timer
systemctl start controldeck-install.service
echo 'Administrative module installation wizard is ready.'
