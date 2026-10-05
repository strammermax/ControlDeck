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
systemctl daemon-reload
systemctl enable --now controldeck-install.timer
systemctl start controldeck-install.service
echo 'Administrative module installation wizard is ready.'
