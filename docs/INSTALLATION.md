# Installatie

## Docker

```bash
git clone https://github.com/strammermax/ControlDeck.git
cd ControlDeck
docker compose up --build -d
curl -f http://127.0.0.1:8080/ready
```

Compose bindt standaard alleen op localhost. Gebruik een reverse proxy voor toegang vanaf andere apparaten. De applicatie draait zonder root, met een alleen-lezen filesystem en een tijdelijke `/tmp`. De build vraagt meer resources dan de uiteindelijke runtime.

Voor een gepubliceerd image gebruik je een bestaande releasetag, bijvoorbeeld `ghcr.io/strammermax/controldeck:v0.1.0`. Het ControlDeck-package is zonder login beschikbaar. Bij een eigen fork moet je packagevisibility controleren; bij een privépackage is registry-login nodig. Docker-in-LXC is niet vereist voor de volgende route.

## Debian LXC

Gebruik een bestaande onprivileged Debian-container. De eerste applicatie heeft geen nesting of hardwaredoorgifte nodig. Installeer als root binnen de container:

```bash
apt-get update
apt-get install -y git
git clone https://github.com/strammermax/ControlDeck.git /root/controldeck-bootstrap
cd /root/controldeck-bootstrap
bash scripts/install-lxc.sh
```

Dit maakt de gebruikers `controldeck` en `controldeck-runner`, de systemd-service, de root-owned deployhelper en de root-worker voor Modulebeheer (`install-wizard.sh`). De service wordt pas bruikbaar na de eerste deployment; er is nog geen `current`-release bij alleen bootstrap.

## GitHub Actions-runner

Open in de repository Settings → Actions → Runners → New self-hosted runner. Kies de Linux-architectuur van de container. Voer de download- en registratieopdrachten uit als `controldeck-runner`, in `/home/controldeck-runner/actions-runner`. Gebruik de actuele, door GitHub getoonde download en checksum. Voeg label `controldeck-production` toe en gebruik de kortlevende registratietoken; leg die niet vast in bestanden of documentatie.

```bash
su - controldeck-runner
mkdir -p ~/actions-runner
cd ~/actions-runner
# Download en pak de runner uit volgens GitHub Settings.
./config.sh --url https://github.com/strammermax/ControlDeck \
  --token '<KORTLEVENDE-REGISTRATIETOKEN>' \
  --labels controldeck-production --unattended
exit
cd /home/controldeck-runner/actions-runner
./svc.sh install controldeck-runner
./svc.sh start
```

Activeer daarna `LXC_DEPLOY_ENABLED=true` in GitHub en start de workflow op main. De runner heeft uitgaande HTTPS-toegang naar GitHub en de Python-packagebron nodig; inkomende GitHub-webhooks zijn niet nodig.

## Controle

```bash
systemctl status controldeck
curl -f http://127.0.0.1:8080/health
curl -f http://127.0.0.1:8080/ready
```

Gunicorn bindt in de LXC op poort 8080. Gebruik firewallregels en een beveiligde reverse proxy voor toegestane bereikbaarheid. De huidige release toont alleen een introductiepagina; voeg geen gevoelige integraties toe voordat authenticatie is gerealiseerd.
