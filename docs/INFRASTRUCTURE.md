# Infrastructuur ControlDeck

**Datum:** 5 oktober 2026. Dit document beschrijft de ingerichte omgeving en de huidige deploymentroute. Het vult de globale ontwerpen aan met operationele gegevens. Wachtwoorden, privésleutels en registratietokens zijn niet opgenomen.

## 1. Overzicht

```text
Lokale ontwikkeling: D:\Project\ControlDeck
              |
              v
GitHub: strammermax/ControlDeck
              |
              +--> GitHub-hosted CI: tests, frontendbuild en Docker-smoketest
              +--> GHCR: image per commit, main en versie
              +--> GitHub Releases: Linux-bundle en SHA-256
              |
              v
Productierunner in LXC 164
              |
              v
Root-owned deployhelper: checksum, commit, releasewisseling
              |
              v
controldeck.service → Flask/Gunicorn → statische frontend
```

## 2. LXC en netwerk

| Onderdeel | Waarde |
| --- | --- |
| Proxmox-node | `pve-amd`, volgens aangeleverde Proxmox-configuratie |
| Container-ID | `164` |
| Hostnaam | `ControlDeck` |
| Besturingssysteem | Debian GNU/Linux 13; container meldde 13.7 bij inrichting |
| Container | Onprivileged |
| CPU | 2 cores, volgens aangeleverde configuratie |
| Geheugen | 1512 MiB |
| Swap | 512 MiB |
| Rootdisk | 8 GiB op `Storage` |
| Bridge | `vmbr0`, volgens aangeleverde configuratie |
| Actueel IPv4-adres | `192.168.20.164/24`, gemeten binnen de draaiende container |
| Gateway | `192.168.1.1` |
| Webinterface | `http://controldeck.home:8080` |
| HTTPS-ingang | `https://controldeck.vanburik.info`, via bestaande Cloudflare Tunnel `remote` |
| Health/readiness | `/health` en `/ready` op dezelfde host en poort |

De vooraf aangeleverde wizardafbeelding vermeldde `/23`; de draaiende container rapporteerde bij verificatie `/24`. Er is tijdens deze inrichting geen subnetwijziging uitgevoerd. Het gemeten netwerk is in deze tabel leidend.

Docker is al op de container aanwezig, maar de huidige ControlDeck-productieservice draait rechtstreeks onder systemd. Voor de optionele Termix-integratie draait wel een afzonderlijke Docker-container in deze LXC; daarvoor is nesting ingeschakeld. Er is geen hardwaredoorgifte gebruikt.

## 3. Accounts en vertrouwensgrenzen

| Account | Gebruik |
| --- | --- |
| `llmuser` | SSH-beheeraccount met bestaande sudo-toegang |
| `controldeck` | Onbevoorrechte applicatiegebruiker; geen interactieve login |
| `controldeck-runner` | Afzonderlijke GitHub Actions-runnergebruiker |

De runner kan via sudo alleen `/usr/local/sbin/controldeck-deploy` aanroepen. De helper is root-owned. Vertrouwde repositorywijzigingen bepalen de geïnstalleerde code en dependencies; toegang tot main en workflowbestanden valt daarom binnen de productie-vertrouwensgrens.

SSH-gegevens blijven in de bestaande lokale credentialvoorziening. Zij worden niet in de repository, release of Actions-configuratie opgenomen. De runnerregistratietoken is kortlevend; de runner bewaart zijn eigen operationele credentials in zijn afgeschermde installatie.

## 4. Services en paden

| Service of pad | Functie |
| --- | --- |
| `controldeck.service` | Applicatie, start automatisch na boot |
| `actions.runner.strammermax-ControlDeck.controldeck-lxc-164.service` | Productierunner, start automatisch na boot |
| `/home/controldeck-runner/actions-runner` | Runnerinstallatie en werkmap |
| `/opt/controldeck/releases/<commit>` | Releasecode, statische frontend en eigen Python-venv |
| `/opt/controldeck/current` | Symlink naar de actieve release |
| `/var/lib/controldeck` | Persistente configuratie, accounts, sessiesleutel en SQLite-gebruikersvoorkeuren |
| `/usr/local/sbin/controldeck-deploy` | Geïnstalleerde deployhelper |
| `/etc/systemd/system/controldeck.service` | Productieserviceconfiguratie |
| `/etc/sudoers.d/controldeck-ci` | Begrensde runner-sudo-regel |
| `/run/lock/controldeck-deploy.lock` | Voorkomt gelijktijdige releasewisselingen |
| `/home/llmuser/controldeck-bootstrap` | Checkout voor beheer van unit en deployhelper |

Gunicorn gebruikt één worker en twee threads op `127.0.0.1:8081`. Nginx luistert op poort 8080 en verzorgt de applicatie en de beveiligde `/termix/`-route. ControlDeck gebruikt een statische frontend en Python-runtime, met SQLite voor gebruikersvoorkeuren. De afzonderlijke Termix-container heeft zijn eigen Node.js-runtime en luistert uitsluitend op `127.0.0.1:8090`. Er zijn nog geen algemene providercollectors.

## 5. GitHub en distributie

- Repository: [strammermax/ControlDeck](https://github.com/strammermax/ControlDeck), publiek.
- Workflow: [Build, release and deploy](https://github.com/strammermax/ControlDeck/actions/workflows/ci.yml).
- Productiebranch: `main`.
- Environment: `production`; branchbeleid staat alleen `main` toe.
- Repositoryvariabele: `LXC_DEPLOY_ENABLED=true`.
- Runnernaam: `controldeck-lxc-164`.
- Extra runnerlabel: `controldeck-production`.
- Containerimage: `ghcr.io/strammermax/controldeck`.
- Versiebron: `VERSION`; een releasetag moet overeenkomen met deze versie.
- Releases: [releaseoverzicht](https://github.com/strammermax/ControlDeck/releases).

Main-pushes voeren CI, imagepublicatie en LXC-deployment uit. Versietags voeren CI, versie-imagepublicatie en releasepublicatie uit. Pull requests gebruiken GitHub-hosted runners en rollen niet uit naar productie.

## 6. Beheer en controle

```bash
systemctl status controldeck
journalctl -u controldeck -n 100
curl -f http://127.0.0.1:8080/health
curl -f http://127.0.0.1:8080/ready
systemctl show controldeck -p MemoryCurrent
```

`/health` vermeldt de versie en volledige commit. Vergelijk deze commit met de geslaagde GitHub-deployment. `/ready` controleert de gebouwde startpagina en de applicatieconfiguratie.

De root-owned helper en unit worden bij bootstrap geïnstalleerd. Bij wijziging daarvan: werk de bootstrapcheckout bij en voer `scripts/install-lxc.sh` opnieuw uit. De runner voert die beheerwijziging niet zelf uit.

## 7. Huidige grenzen en vervolg

De actuele inrichting omvat verplichte Google-login, gebruikersbeheer, opgeslagen voorkeuren en de Termix-integratie. Bij verificatie van 0.4.0 gebruikte ControlDeck circa 50 MiB en Termix circa 204 MiB; dit zijn momentopnamen zonder representatieve belasting. Zie [VERIFICATION.md](VERIFICATION.md) voor testgrenzen. De publieke HTTPS-route, HTTP-redirect en applicatiechecks via Cloudflare zijn eveneens geslaagd; zie [HTTPS.md](HTTPS.md).

Authenticatie en de rollen admin/user zijn ingericht. Alleen admins kunnen accounts beheren en module-installaties starten. De HTTPS-ingang is ingericht via een bestaande Cloudflare Tunnel; de laatste verbinding naar de LXC gebruikt HTTP op het LAN. De rechtstreekse HTTP-route blijft de interne verificatieroute. De Terminal-integratie en installatiewizard vereisen serverzijdige autorisatie; publieke probes geven uitsluitend gezondheid en versiegegevens weer.

Releasecleanup blijft voorlopig handmatig. Automatisch herstel is gericht op code en runtime; toekomstige databasemigraties krijgen een aanvullend backup- en herstelontwerp. Zie [OPERATIONS.md](OPERATIONS.md), [CI-CD.md](CI-CD.md) en [INSTALLATION.md](INSTALLATION.md).

## 0.3.0 — Persistente configuratie en toegang

De systemd-unit is bijgewerkt met `CONTROLDECK_CONFIG=/var/lib/controldeck/config/controldeck.json`, `CONTROLDECK_DATA_DIR=/var/lib/controldeck`, `CONTROLDECK_ACCOUNTS=/var/lib/controldeck/accounts.json` en het optionele root-only EnvironmentFile `/etc/controldeck/controldeck.env`. De server heeft een eigen ControlDeck Google OAuth-client. Accounts en clientgeheimen zijn uitsluitend privé op de server geïnstalleerd.

De accountlijst is niet onderdeel van de publieke repository. Configuratie, accounts, sessiesleutel en gebruikersdatabase blijven buiten de release-mappen bestaan. Een nieuwe installatie kopieert configuratievoorbeelden uitsluitend wanneer nog geen hoofdbestand aanwezig is. Google-login is verplicht voor de interfacegegevens, inclusief de interne LAN-route. De health/readiness-probes blijven zonder login bruikbaar. Meer details in AUTHENTICATION.md en CONFIGURATION.md.

## Termix

De optionele Terminal-integratie gebruikt een afzonderlijke Docker-container, de bestaande Google-login en een beveiligde Nginx-gateway. Zie [Termix-installatie en beheer](TERMIX.md).

De admin-installatiewizard biedt Docker en Proxmox LXC als keuzes, met voorafgaande controle en voortgang. Zie [module-installatiewizard](MODULE-WIZARD.md). Docker is aangesloten; de Proxmox-uitvoering vereist nog de hostverbinding en Helper-Script-adapter.

## 0.4.0 — Terminal en installatiebeheer

| Onderdeel | Productie-inrichting |
| --- | --- |
| Termix | Versie 2.9.1, Docker-image vastgezet op digest; limiet 1 CPU en 512 MiB |
| Applicatie | Gunicorn op loopback 8081, systemd-drop-in `termix.conf` |
| Gateway | Nginx op 8080; uitsluitend geautoriseerde aanvragen naar Termix |
| Termix-data | Docker-volume `controldeck-integrations_termix-data` |
| Installaties | `/var/lib/controldeck/installations`, afzonderlijke queue en root-owned resultaten |
| Installatieworker | `/usr/local/sbin/controldeck-install-worker`; `controldeck-install.timer` controleert iedere 15 seconden |
| Installatiebestanden | Root-owned allowlist onder `/opt/controldeck-integrations/installer` |
| Privé-installatielog | `/var/log/controldeck-install.log`, uitsluitend root |
| Agent-proxy | `/usr/local/sbin/controldeck-agent-proxy`, dienst `controldeck-agent-proxy` als gebruiker `controldeck-ssh` (geen root); socket `/run/controldeck-agent/agent.sock` (groep `controldeck-ssh`, `0660`) |
| SSH-sleutel naar de nodes | `/var/lib/controldeck-ssh/id_ed25519` (`0600`, map `0700`, eigenaar `controldeck-ssh`), met `known_hosts`, gekoppelde nodes en auditlog in dezelfde map |
| Node-agent (voor verspreiding) | `/opt/controldeck-integrations/agent/controldeck-agent` |
| Bootstrapgegevens | `/var/lib/controldeck/bootstrap.json` (root:controldeck, `0640`): checkout, eigenaar en commit van de laatste `install-wizard.sh`; ControlDeck toont hiermee het juiste updatecommando |

De webservice heeft geen Docker-socket of algemene rootrechten. De aparte installatieworker controleert opdrachten en de actuele adminrechten voordat hij de toegestane installer uitvoert. De bootstrap `scripts/install-wizard.sh` installeert deze worker en de agent-proxy (zie [NODE-AGENT.md](NODE-AGENT.md)) en wordt door `scripts/install-lxc.sh` automatisch uitgevoerd. De webservice is lid van de groep `controldeck-ssh` om het socket van de proxy te gebruiken, maar kan de SSH-sleutel niet lezen; wijzigingen aan de root-owned installatiebestanden vereisen opnieuw uitvoeren van die bootstrap na review. Een normale apprelease vervangt deze bestanden niet.

De Docker-installatie vanuit de wizard is op productie uitgevoerd en voltooid, met behoud van het bestaande Termix-volume. De keuze Proxmox LXC is zichtbaar, maar uitvoering is geblokkeerd totdat de Proxmox-hostverbinding en Helper-Script-adapter zijn aangesloten. Er is nog geen nieuwe LXC vanuit ControlDeck aangemaakt.
