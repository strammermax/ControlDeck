# Changelog

Vanaf oktober 2026 is elke build van `main` een release met versienummer `jjjj.mm.dd.<build>` (zie [CI-CD.md](CI-CD.md)). De changelog groepeert wijzigingen per dag.

## 2026.10.14 — In ontwikkeling: persoonlijke dashboards

- Bestaande Homepage-apps als bronverwijzing op dashboards, met lokale iconen en opgeslagen Seerr/Jellyfin-cijfers. Geen gekopieerde bronmetadata; Bookmarks-rechten blijven bepalend.
- Centrale zoekfunctie via bovenbalk en Ctrl/Cmd+K voor toegestane onderdelen, eigen dashboards en Homepage-apps. Persoonlijke zoekmachines, waaronder SearXNG, met externe zoeklinks na expliciete keuze.
- Schemas v2/v3: persoonlijke zoekmachines en blijvende Homepage-appnummers. Regressie opgelost waarbij verwijderen van de hoogste app-ID een oude dashboardverwijzing naar een nieuwe app kon laten wijzen. HEAD op Homepage-links is nu ook alleen-lezen.
- SSO-scope verduidelijkt: bestaande Google-SSO; geen nieuwe LDAP-/lokale wachtwoordlogin. Gekozen diensten en ARR-suite staan in [INTEGRATION-PLAN.md](INTEGRATION-PLAN.md), zonder aangeleverde geheimen.

- Eerste dashboardeditor: Werk/Homelab, meerdere persoonlijke indelingen, dupliceren, standaardkeuze, groepen, vaste zijpanelen, app-links, slepen en vergroten. Opslaan bewaart revisies en voorkomt het overschrijven van gelijktijdige wijzigingen. Dit is een eerste onderdeel van de gekozen MVP; zie [DASHBOARD.md](DASHBOARD.md).
- Private SQLite-backup vóór dashboardschema v1; tests voor opslag, herstel, eigenaarisolatie, modulerechten, CSRF, grenzen en afwijzingen.
- Infisical-koppeling gebruikt Camiels clientinstellingen voor app- en gedeelde mappen. Windows-regressie opgelost: de actieve Python-interpreter wordt gebruikt in plaats van een geraden executable naast de CLI. Zie [VAULT.md](VAULT.md).
- Regressies: nieuwe tegel negeerde handmatige positie door onterechte automatische plaatsing; HEAD op een dashboard werd behandeld als schrijfactie. Beide krijgen een benoemde test.
- Dashboardopmaak gebruikt bestaande ControlDeck-tokens als voorbereiding op een afzonderlijk gedeeld huisstijlproject. Releaseversies blijven `yyyy.mm.dd.buildnr` uit CI.

## 2026.10.05 — Instellingen, Proxmox, ProxMenux, Modulebeheer en Linkwarden

- Homepage: **Link toevoegen** en **Aanpassen** openen in een popup (`<dialog>`: focus, Escape en achtergrond afgeschermd).
- Module Cronjobs, stap 4: **Proxmox → Nodes** als cronjob-manager: clustertijdlijn (ControlDeck-jobs, systeem-cron, Proxmox-backups) met tellers en filters; per node aanmaken met schema-kiezer, bewerken, pauzeren, nu uitvoeren met live log, geschiedenis, verwijderen, overnemen/teruggeven. Zie CRONJOBS.md.
- Koppelwizard Cronjobs: stand "x van y nodes klaar" en knop terug naar de nodes.
- Modulebeheer meldt verouderde of ontbrekende root-onderdelen (installatieworker, agent-proxy) met het exacte updatecommando voor deze host; `install-wizard.sh` legt de checkout vast in `/var/lib/controldeck/bootstrap.json`.
- Module Cronjobs, stap 3: koppelwizard in Modulebeheer (sleutel, hostsleutel bevestigen, installatiecommando met SHA-256-controle en `from=`-beperking, verbindingstest per node, verwijderen).
- Module Cronjobs, stap 2: agent-proxy `controldeck-agent-proxy` (eigen gebruiker zonder root, enige houder van de SSH-sleutel, vastgepinde hostsleutels, auditlog); `install-wizard.sh` installeert hem.
- Module Cronjobs, stap 1: node-agent `controldeck-agent` (vaste acties via SSH, log-wrapper per run, rotatie, overnemen/teruggeven); nog niet verbonden.
- LXC-updates: knop **Bijwerken in ProxMenux ↗** per container en begeleide update per node met het PVE LXC Updater-script (kopieerknop).
- Release notes per release uit de commitberichten; de footer linkt naar de release notes van de draaiende versie. CI bewaart de laatste 30 releases en image-versies.
- Versienummering `jjjj.mm.dd.<build>`; elke build van `main` wordt automatisch een GitHub-release.

- Proxmox VE-koppeling via Admin → Modules (alleen-lezen API-token, certificaatpinning, verbindingstest). Zie PROXMOX.md.
- Proxmox → Overzicht toont clusterwidgets (CPU/geheugen van gasten en nodes, taken per categorie en node over 48 uur, SDN-zones) en de laatste taken van het hele cluster met filters en verouderd-melding.
- ProxMenux Monitor-koppeling via Admin → Modules (cluster-CA, API-token per node, hostnamecontrole); Overzicht toont gezondheid per node, schijven/ZFS en LXC-updates.
- ProxMenux-wizard zoekt per node de monitor (niet gevonden, alleen http, ander certificaat, login uit, klaar) en begeleidt installatie en inrichting.
- Admin → Modulebeheer met tabbladen Installeren (alleen niet-geïnstalleerd), Bewerken en Verwijderen (alleen geïnstalleerd), inclusief verwijderwizard en `uninstall-termix.sh` (gegevens bewaren of wissen). Vereist eenmalig opnieuw `install-wizard.sh` op de host.
- `install-lxc.sh` installeert de root-worker voor Modulebeheer voortaan automatisch.
- ProxMenux-overzicht: CPU-vermogen (RAPL) met bron, load ten opzichte van threads, slaapstand voor schijven, LXC-updates over alle nodes gesorteerd met totalen en pakketnamen, laden op de achtergrond en 30 s time-out voor de gezondheidscontrole.
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

## Gedeelde appiconen

- Bookmarks en Dashboard gebruiken dezelfde faviconweergave en PNG-upload, met een lokaal diensticoon als terugval.
- Bestaande appverwijzingen volgen het icoon uit de centrale Bookmarks-bron. Persoonlijke dashboardlinks behouden eigen iconen en zijn duidelijk als persoonlijk benoemd.
- Kleine PNG-afbeeldingen worden gecontroleerd en zonder extra runtimeservice opgeslagen.

## Herbruikbare dashboardmodules

- Linkwarden gebruikt één implementatie op de modulepagina en op persoonlijke dashboards, met de bestaande persoonlijke koppeling en rechten.
- Eén modulekiezer vervangt afzonderlijke toevoegknoppen. Linkwarden kan per dashboardexemplaar een eigen collectie tonen, met zoeken, vernieuwen en meer laden.
- De compacte module verwijst voor uitgebreid beheer naar Bookmarks. Plaats en grootte zijn optioneel uitklapbaar; verwijderen wordt pas aangeboden voor bestaande tegels.

## Modulaire aanmeldadapters

- Modules hebben eigen frontendmappen met weergave en instellingen; het dashboard gebruikt een generiek contract en expliciete registraties. Backendinstellingen worden per module gevalideerd.
- Kasm kan via een centraal geconfigureerde API-sleutel een aanmeldlink voor het eigen gekoppelde account verkrijgen. Nextcloud gebruikt een geconfigureerde Google/user_oidc-route.
- Aanmeldconfiguratie komt uitsluitend uit Infisical. Browserselectie van een doelaccount of doeladres is niet toegestaan. Live activering wacht op de private inrichting.
- Regressie: de globale responsehook behield een strengere no-referrer-header van aanmeldroutes niet. De hook bewaart nu expliciet ingestelde policies; de gedragstest is eerst falend en daarna geslaagd uitgevoerd.
