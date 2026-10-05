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
| Actueel IPv4-adres | `192.168.1.164/24`, gemeten binnen de draaiende container |
| Gateway | `192.168.1.1` |
| Webinterface | `http://192.168.1.164:8080` |
| Health/readiness | `/health` en `/ready` op dezelfde host en poort |

De vooraf aangeleverde wizardafbeelding vermeldde `/23`; de draaiende container rapporteerde bij verificatie `/24`. Er is tijdens deze inrichting geen subnetwijziging uitgevoerd. Het gemeten netwerk is in deze tabel leidend.

Docker is al op de container aanwezig, maar de huidige ControlDeck-productieservice draait rechtstreeks onder systemd. Docker-in-LXC en nesting zijn niet nodig voor deze route. Er is geen hardwaredoorgifte gebruikt.

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
| `/var/lib/controldeck` | Gereserveerd voor toekomstige persistente applicatiedata |
| `/usr/local/sbin/controldeck-deploy` | Geïnstalleerde deployhelper |
| `/etc/systemd/system/controldeck.service` | Productieserviceconfiguratie |
| `/etc/sudoers.d/controldeck-ci` | Begrensde runner-sudo-regel |
| `/run/lock/controldeck-deploy.lock` | Voorkomt gelijktijdige releasewisselingen |
| `/home/llmuser/controldeck-bootstrap` | Checkout voor beheer van unit en deployhelper |

Gunicorn gebruikt één worker, twee threads en poort 8080. Node.js draait niet als onderdeel van de applicatieruntime. Er is nog geen database of providercollector.

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

`/health` vermeldt de versie en volledige commit. Vergelijk deze commit met de geslaagde GitHub-deployment. `/ready` bevestigt dat de gebouwde startpagina aanwezig is.

De root-owned helper en unit worden bij bootstrap geïnstalleerd. Bij wijziging daarvan: werk de bootstrapcheckout bij en voer `scripts/install-lxc.sh` opnieuw uit. De runner voert die beheerwijziging niet zelf uit.

## 7. Huidige grenzen en vervolg

De inrichting is getest met een startpagina, zonder gekoppelde homelabsystemen. De applicatieservice gebruikte bij een eerste momentopname ongeveer 34 MiB en de runner ongeveer 99 MiB. Zie [VERIFICATION.md](VERIFICATION.md) voor testgrenzen.

Voor verdere functionaliteit volgen authenticatie, rechten en providers. HTTPS, domeinrouting en toegang op afstand moeten worden ingericht voordat een beheeromgeving breed wordt ontsloten. De huidige rechtstreekse HTTP-route is de interne verificatieroute.

Releasecleanup blijft voorlopig handmatig. Automatisch herstel is gericht op code en runtime; toekomstige databasemigraties krijgen een aanvullend backup- en herstelontwerp. Zie [OPERATIONS.md](OPERATIONS.md), [CI-CD.md](CI-CD.md) en [INSTALLATION.md](INSTALLATION.md).
