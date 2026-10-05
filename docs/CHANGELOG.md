# Changelog

## Unreleased — Personal settings

- Proxmox VE-koppeling via Admin → Modules (alleen-lezen API-token, certificaatpinning, verbindingstest). Zie PROXMOX.md.
- Proxmox → Overzicht toont clusterwidgets (CPU/geheugen van gasten en nodes, taken per categorie en node over 48 uur, SDN-zones) en de laatste taken van het hele cluster met filters en verouderd-melding.
- ProxMenux Monitor-koppeling via Admin → Modules (cluster-CA, API-token per node, hostnamecontrole); Overzicht toont gezondheid per node, schijven/ZFS en LXC-updates.
- ProxMenux-wizard zoekt per node de monitor (niet gevonden, alleen http, ander certificaat, login uit, klaar) en begeleidt installatie en inrichting.
- Admin → Modulebeheer met tabbladen Installeren (alleen niet-geïnstalleerd), Bewerken en Verwijderen (alleen geïnstalleerd), inclusief verwijderwizard en `uninstall-termix.sh` (gegevens bewaren of wissen). Vereist eenmalig opnieuw `install-wizard.sh` op de host.
- Modulecatalogus ondersteunt meerdere modules en koppelingen naast installaties.
- Gebruikersdropdown rechtsboven met Profiel, Instellingen en Uitloggen.
- Persoonlijke Instellingen-pagina per gebruiker: interfacetaal (Nederlands/English) en volgorde van de hoofdnavigatie met slepen, Annuleren, Opslaan en Standaard herstellen.

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
