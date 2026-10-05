# Changelog

## 0.3.0 — Configuration, SSO and users

- Runtime-configuratie in gesplitste JSON-bestanden voor site, menu, modules, providers en toekomstige widgets.
- Voorbereide, uitgeschakelde voorbeelden voor Kasm, Radarr en Plex.
- Verplichte Google OIDC-login, actieve accountlijst en serverzijdige admin/user-rechten.
- Adminpagina voor gebruikersprofielen, SSO-type en inschakelen/uitschakelen.
- Persoonlijke voorkeuren persistent in SQLite, buiten versie-releases.
- Uitgebreide configuratie-, autorisatie-, ondertekende OIDC- en navigatietests vóór uitrol.
- Geheimen uitgesloten van Git, Dockercontext en configuratie-API.
- Het Dashboard blijft leeg; Windows-login en provider-API-adapters volgen later.

## 0.2.0 — Dashboard shell

- Basisinterface volgens de aangeleverde mockup, met eigen ControlDeck-logo.
- Horizontaal menu, Proxmox/Admin-dropdowns en mobiele hamburgernavigatie.
- Deelbare modulelinks, licht/donker thema, refresh en werkelijke procesuptime.
- Documentatie van huidige bediening en grenzen in UI.md.

## 0.1.1 — Distribution notices

- Automatisch verzamelde frontendlicentieteksten in de statische export, Linux-bundle en het Docker-image.
- Snapshot van de frontendlicentieteksten bij de projectdocumentatie.

## 0.1.0 — Infrastructure foundation

- Next.js/React/TypeScript-startpagina als statische export.
- Flask/Gunicorn-runtime met health, readiness en commitmetadata.
- Python-tests en geautomatiseerde frontend- en Dockerbuild.
- GHCR-images, versie-tags en GitHub-releasebundles met SHA-256.
- LXC-bootstrap, productierunnerroute en deployment met healthcontrole en rollback.
- Centrale documentatie in docs, inclusief visie en ontwerpen.

Authenticatie, providerintegraties en functionele modules volgen in latere releases.
