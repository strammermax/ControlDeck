# Implementatie en repository

## Huidige runtime

De frontend wordt met Next.js, React en TypeScript gebouwd als statische export. Flask serveert de bestanden en `/health` en `/ready`. Gunicorn draait in productie met één worker en twee threads. Google OIDC en optioneel Cloudflare Access verzorgen de login. ControlDeck valideert configuratie en accounts serverzijdig en slaat identiteiten, voorkeuren, persoonlijke dashboards en versleutelde Homepage-koppelingen op in SQLite. Proxmox, ProxMenux, Linkwarden, Homepage-integraties, Terminal en Cronjobs hebben eigen backendmodules. Bestaande rol- en modulerechten blijven de basis voor toegang.

De dashboardeditor, appverwijzingen, lokale zoekfunctie en persoonlijke zoekmachines zijn beschreven in [DASHBOARD.md](DASHBOARD.md). Dashboards bewaren app-ID's; `dashboard_apps.py` projecteert toegestane brongegevens en opgeslagen integratiecijfers. `search.py` combineert lokale resultaten; externe zoeklinks worden pas in de browser geopend. De componenten gebruiken bestaande stylesheetvariabelen zodat een toekomstig gedeeld huisstijlproject kan aansluiten. Centrale instellingen en geheimen gebruiken waar al aangesloten de bestaande Infisical-client; [VAULT.md](VAULT.md) beschrijft de resterende migratie. Node.js blijft uitsluitend een builddependency.

```text
Browser → Flask/Gunicorn → vooraf gebouwde frontend
                      └→ /health en /ready
```

Node.js en TypeScript zijn builddependencies, geen verplichte productieprocessen. Een GitHub-hosted runner bouwt de export. De LXC ontvangt een Linux-bundle en installeert alleen Python-runtimepackages.

## Structuur

| Pad | Doel |
| --- | --- |
| `frontend/` | Next.js-app en vastgelegde npm-lockfile |
| `backend/` | Flask, OIDC, rollen, configuratievalidatie en voorkeuren |
| `config/` | Menu en gesplitste module/provider/widgetdefinities |
| `tests/` | Gedrag van readiness, health en statische bestandstoegang |
| `scripts/package.py` | Linux-bundle, buildmetadata en checksum |
| `scripts/install-lxc.sh` | Eenmalige service- en runnergebruikerinrichting |
| `scripts/deploy-lxc.sh` | Versie-installatie, healthcontrole en rollback |
| `deploy/controldeck.service` | systemd-productieservice |
| `.github/workflows/ci.yml` | Controles, builds, GHCR, releases en LXC-deployment |
| `docs/` | Alle uitgebreide projectdocumentatie |

`build-info.json` wordt tijdens de build gegenereerd. De versie komt uit `VERSION`; de commit uit de workflow. Deployment controleert dat `/health` exact de bedoelde commit meldt, zodat een oudere draaiende service geen nieuwe deployment als succesvol kan laten lijken.

## Richting

De visie en ontwerpen vormen het kader voor API-adapters, widgets en boomnavigatie. De huidige login, JSON-configuratie en submenu's vormen de basis hiervoor. Geen roottoegang, hostmounts of Docker-socket zijn nodig voor de huidige applicatie.
