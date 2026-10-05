# Implementatie en repository

## Huidige runtime

De frontend wordt met Next.js, React en TypeScript gebouwd als statische export. Flask serveert de bestanden en `/health` en `/ready`. Gunicorn draait in productie met één worker en twee threads. Er zijn nog geen database, login, providercollectors of beheeracties.

```text
Browser → Flask/Gunicorn → vooraf gebouwde frontend
                      └→ /health en /ready
```

Node.js en TypeScript zijn builddependencies, geen verplichte productieprocessen. Een GitHub-hosted runner bouwt de export. De LXC ontvangt een Linux-bundle en installeert alleen Python-runtimepackages.

## Structuur

| Pad | Doel |
| --- | --- |
| `frontend/` | Next.js-app en vastgelegde npm-lockfile |
| `backend/` | Flask-applicatie |
| `tests/` | Gedrag van readiness, health en statische bestandstoegang |
| `scripts/package.py` | Linux-bundle, buildmetadata en checksum |
| `scripts/install-lxc.sh` | Eenmalige service- en runnergebruikerinrichting |
| `scripts/deploy-lxc.sh` | Versie-installatie, healthcontrole en rollback |
| `deploy/controldeck.service` | systemd-productieservice |
| `.github/workflows/ci.yml` | Controles, builds, GHCR, releases en LXC-deployment |
| `docs/` | Alle uitgebreide projectdocumentatie |

`build-info.json` wordt tijdens de build gegenereerd. De versie komt uit `VERSION`; de commit uit de workflow. Deployment controleert dat `/health` exact de bedoelde commit meldt, zodat een oudere draaiende service geen nieuwe deployment als succesvol kan laten lijken.

## Richting

De visie en ontwerpen vormen het kader voor providers, login, submenu's en boomnavigatie. Die worden na de infrastructurele basis toegevoegd. Geen roottoegang, hostmounts of Docker-socket zijn nodig voor de huidige applicatie.
