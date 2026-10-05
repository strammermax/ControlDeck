#!/usr/bin/env bash
# Bootstrap inside an existing Debian LXC; does not create or modify the PVE guest.
set -euo pipefail
[[ $(id -u) -eq 0 ]] || { echo 'Run as root inside the ControlDeck LXC.' >&2; exit 1; }
source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
apt-get update
apt-get install -y python3 python3-venv curl ca-certificates sudo git jq unzip
id controldeck >/dev/null 2>&1 || useradd --system --home /var/lib/controldeck --shell /usr/sbin/nologin controldeck
id controldeck-runner >/dev/null 2>&1 || useradd --create-home --shell /bin/bash controldeck-runner
install -d -m 0755 /opt/controldeck/releases
install -d -o controldeck -g controldeck -m 0750 /var/lib/controldeck
# Preserve local settings on subsequent installs and deployments.
if [[ ! -e /var/lib/controldeck/config/controldeck.json ]]; then
    cp -R -- "$source_root/config" /var/lib/controldeck/config
    chown -R root:controldeck /var/lib/controldeck/config
    chmod -R u=rwX,g=rX,o= /var/lib/controldeck/config
fi
if [[ ! -e /var/lib/controldeck/accounts.json ]]; then
    install -o root -g controldeck -m 0640 "$source_root/config/accounts.json" /var/lib/controldeck/accounts.json
fi
install -d -o root -g root -m 0700 /etc/controldeck
install -m 0644 "$source_root/deploy/controldeck.service" /etc/systemd/system/controldeck.service
install -o root -g root -m 0755 "$source_root/scripts/deploy-lxc.sh" /usr/local/sbin/controldeck-deploy
rule=$(mktemp)
trap 'rm -f "$rule"' EXIT
printf 'controldeck-runner ALL=(root) NOPASSWD: /usr/local/sbin/controldeck-deploy *\n' > "$rule"
chmod 0440 "$rule"
visudo -cf "$rule"
install -m 0440 "$rule" /etc/sudoers.d/controldeck-ci
systemctl daemon-reload
systemctl enable controldeck
echo 'Bootstrap complete. Register the runner, then enable deployment in GitHub.'
