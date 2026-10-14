# Plan van aanpak — ControlDeck Dashboard

Datum: 14 oktober 2026. Status: plan voor uitvoering; functies hieronder zijn niet als voltooid aangemerkt.

Uitvoeringsupdate: de eerste persoonlijke dashboardeditor en de aanpassing van de bestaande Infisical-clientkoppeling staan beschreven in [DASHBOARD.md](DASHBOARD.md) en [VAULT.md](VAULT.md). Dit is een eerste werkend deel, geen afronding van alle fasen. Het adapterregister, de uitgebreide rechten en volledige vaultmigratie moeten nog worden gebouwd. Nieuwe opmaak sluit later aan op Camiels afzonderlijke gedeelde huisstijlproject. Releases blijven `yyyy.mm.dd.buildnr` volgens de bestaande CI-versieopbouw.

## 1. Doel en uitgangspunt

ControlDeck wordt Camiels persoonlijke startpagina voor werk en homelab. We bouwen voort op de bestaande code, met de gekozen Homarr-functies als functionele referentie. De bestaande navigatie, Proxmox-functionaliteit, Bookmarks, Terminal en aanmelding moeten blijven werken.

De runtime blijft een statische frontend, één Python-service en lokale SQLite. Homarr draait niet als extra applicatie binnen ControlDeck. Alle substantive documentatie blijft onder `docs/`; privésleutels, accountlijsten en runtimegegevens blijven buiten Git en publieke images.

## 2. Herstelpunt en onderzoeksbasis

De geannoteerde GitHub-tag [checkpoint/pre-dashboard-2026-10-14](https://github.com/strammermax/ControlDeck/tree/checkpoint/pre-dashboard-2026-10-14) verwijst naar commit `cc62ca4a6e82e7039f5b028e3587fa16e3f22016`. De remote tag en de onderliggende commit zijn na push gecontroleerd. Het herstelpunt bevat de bestaande code; de nieuwe dashboardplannen waren nog niet gecommit en vallen erbuiten.

Verificatie van deze uitgangssituatie:

| Controle | Resultaat |
| --- | --- |
| Python-tests via projectomgeving | 419 geslaagd, 8 overgeslagen |
| Frontendtests | 123 geslaagd |
| TypeScript-controle | Geslaagd |
| Statische productiebuild en licentiebundeling | Geslaagd |

Dit bewijst geen live werking van externe diensten. De overgeslagen tests en hun omgevingsvoorwaarden moeten bij de uiteindelijke release worden beoordeeld.

Homarr is als afzonderlijke referentiecheckout onderzocht op commit [`d7918f5ed3fb64e1e9b82372625f6160a7eb99a2`](https://github.com/homarr-labs/homarr/tree/d7918f5ed3fb64e1e9b82372625f6160a7eb99a2), met `package.json`-versie 2.5.2. Dit is een vastgezette ontwikkelbranch, geen claim over de laatste stabiele release. Het onderzoek is gericht op architectuur en de geselecteerde functies; niet iedere adapter is afzonderlijk geaudit of live getest. Homarr is niet geïnstalleerd of uitgevoerd.

### Onderzochte onderdelen en betekenis

| Onderdeel | ControlDeck-bron | Homarr-bron in genoemde commit | Bevinding voor het plan |
| --- | --- | --- | --- |
| Dashboard en navigatie | `frontend/app/page.tsx`, `frontend/lib/navigation.ts`, `config/modules/core.json` | `packages/api/src/router/board.ts`, `packages/validation/src/board.ts` | ControlDeck heeft een lege dashboardweergave; Homarr valideert en bewaart aparte boards, secties en items. Voeg eigen dashboardonderdelen toe aan de bestaande shell. |
| Editor | `frontend/lib/bookmark-layout.ts`, bestaande kaartcomponenten | `apps/nextjs/src/components/board/sections/grid/grid-editor.tsx`, `packages/boards/src/edit-mode.tsx` | Bookmarkgroepering is geen dashboardeditor. Homarr heeft een omvangrijke editor met veel interne afhankelijkheden; een directe kopie is geen kleine uitbreiding. |
| Opslag | `backend/auth.py`, `backend/homepage.py`, `backend/homepage_integrations.py` | `packages/db/schema/sqlite.ts` | ControlDeck combineert private JSON en SQLite; Homarr modelleert onder meer boards, items, groepen, integraties en rechten apart. Maak een migratiepad in plaats van links opnieuw aan te maken. |
| Autorisatie | `backend/auth.py`, `backend/homepage.py` | `packages/auth/permissions/board-permissions.ts`, `integration-query-permissions.ts` | ControlDeck controleert rollen en modules; Homarr heeft daarnaast rechten per resource. Dashboards mogen bestaande modulegrenzen niet omzeilen. |
| Integraties | `backend/proxmox.py`, `backend/proxmenux.py`, `backend/homepage_integrations.py` | `packages/integrations/src/base/integration.ts`, `proxmox/proxmox-integration.ts`, `seerr/seerr-integration.ts` | ControlDeck heeft bruikbare eigen adapters, maar nog geen algemene capabilitylaag. Homarr scheidt verbinding, authenticatie, gegevens en bediening. |
| Zoeken | `frontend/components/homepage-links.tsx`, Bookmarks/Linkwarden | `packages/integrations/src/base/searchable-integration.ts`, `packages/api/src/router/search-engine/search-engine-router.ts` | Een lokale tegelfilter is geen centrale zoekfunctie. Zoekresultaten moeten per bron en gebruiker worden gefilterd. |
| Machine-API | Globale sessie- en CSRF-controle in `backend/auth.py` | `packages/auth/api-key/get-api-key-session.ts` | ControlDeck vereist nu een browsersessie voor API-routes. Machineauthenticatie vraagt een expliciete nieuwe route door die controle. |
| Backup | `docs/OPERATIONS.md`, private opslag en deployhelper | `apps/nextjs/src/app/api/backup/export/route.ts` | Code terugzetten herstelt geen gegevens. Backup moet ook private JSON en benodigd sleutelmateriaal omvatten. |

Aanvullende documentatiebronnen: [boards](https://homarr.dev/docs/management/boards/), [apps](https://homarr.dev/docs/management/apps/), [integraties](https://homarr.dev/docs/integrations/), [Custom API](https://homarr.dev/docs/widgets/custom-api/), [API](https://homarr.dev/docs/management/api/), [gebruikers](https://homarr.dev/docs/management/users/) en [backup](https://homarr.dev/docs/management/backup/). Deze online pagina's kunnen na de onderzoeksdatum veranderen; de broncommit hierboven is het vaste technische referentiepunt.

## 3. Vastgelegde scope

De selectie van Camiel is leidend: **MVP A1–A7, B1–B8, D1–D10, E1–E4, F1–F6; nice to have C1–C25; overige later.**

| IDs | MVP-resultaat |
| --- | --- |
| A1–A3 | Meerdere dashboards; aanmaken, dupliceren, hernoemen, verwijderen en persoonlijk standaarddashboard. Werk en Homelab zijn de eerste indelingen. |
| A4–A5 | Visuele bewerkmodus; items toevoegen, configureren, verwijderen, slepen en vergroten. |
| A6–A7 | Benoemde inklapbare groepen en vaste linker- en rechterpanelen. |
| B1–B2 | Apptegels met naam, adres, beschrijving en iconen uit bibliotheek of eigen upload. |
| B3–B5 | Bereikbaarheidscontrole, bookmarkgroepen en een herbruikbare koppeling tussen app en integratie. |
| B6–B7 | Centrale zoekfunctie en instelbare externe zoekmachines. |
| B8 | Media zoeken en aanvragen via een ondersteunde Seerr-achtige koppeling, met aparte actierechten. |
| D1–D10 | Integratiedekking voor de tien gekozen families; concrete diensten en capabilities komen in een controleerbare adapterlijst. |
| E1–E3 | Eigen API-gegevens weergeven, expliciete actieknoppen en herbruikbare widgetdefinities. |
| E4 | Gedocumenteerde externe beheer-API met intrekbare credentials en begrensde rechten. |
| F1–F2 | Gebruikers, groepen en onderscheid tussen bekijken, wijzigen en acties uitvoeren. |
| F3 | Bestaande Google-SSO gebruiken, zoals door Camiel bevestigd. Geen extra LDAP-, generieke OIDC- of lokale wachtwoordlogin bouwen. Bestaande Cloudflare-functionaliteit blijft behouden waar geconfigureerd. |
| F4–F6 | Persoonlijke voorkeuren, uitnodigen/toelaten voor bestaande Google-accounts en volledige backup/herstelbediening. F5 krijgt geen lokale wachtwoordaccounts. |

**Nice to have:** de specialistische widgets C1–C25, van systeemgrafieken en uptime tot agenda, notities, media en domotica. Ze blokkeren de MVP niet. De editor, apptegels en eigen API-widget vallen wel onder A, B en E en zijn dus geen optionele C-widgets.

**Later:** A8–A12 (aparte schermindelingen, uitgebreide vormgeving, eigen CSS, dashboarddeling en uitgebreide toetsenbordeditor) en E5–E6 (MCP en AI-assistent). De basis blijft leesbaar op mobiel en standaardformulieren blijven toegankelijk; aparte mobiele indelingen zijn later.

Kasm is inmiddels expliciet door Camiel als doelintegratie gekozen. Een gewone Kasm-link past in B1; de native workspacecatalogus en sessiestart vormen een vervolgbatch van de geselecteerde integraties. Versie, API-contract en rechten moeten nog worden vastgesteld. De sessiekoppeling is nog niet gebouwd.

### Afbakening D1–D10

De gekozen IDs zijn families, geen lijst met afzonderlijk geaccepteerde adapters. Een catalogusicoon of app-link telt niet als werkende API-integratie. De eerste concrete diensten zijn inmiddels benoemd in [INTEGRATION-PLAN.md](INTEGRATION-PLAN.md). Deze families blijven in scope; versies en capabilities worden per dienst vastgesteld.

| ID | Familie | Kandidaatdiensten uit de inventarisatie |
| --- | --- | --- |
| D1 | Virtualisatie | Proxmox |
| D2 | Containers en hosting | Docker, Kubernetes, Coolify |
| D3 | Monitoring | Beszel, Glances, Netdata, Prometheus, Uptime Kuma, Healthchecks |
| D4 | Netwerk en beveiliging | UniFi, OPNsense, Pi-hole, AdGuard Home, Technitium DNS |
| D5 | Opslag en bestanden | TrueNAS, Unraid, Synology, OpenMediaVault, Nextcloud |
| D6 | Media | Jellyfin, Plex, Emby, Sonarr, Radarr, Seerr |
| D7 | Downloads | qBittorrent, Transmission, SABnzbd, NZBGet |
| D8 | Persoonlijke informatie | Linkwarden, Karakeep, Paperless-ngx, iCal en notitiediensten |
| D9 | Huisautomatisering | Home Assistant |
| D10 | Overige diensten | Onder meer Immich, Frigate, Gotify en ntfy |

Per gekozen dienst leggen we versie, aanmeldmethode, verbindingscontrole, leesgegevens, zoekmogelijkheden en toegestane acties vast. Als alle genoemde diensten bedoeld zijn, blijven die allemaal releasewerk; dat wordt niet stilzwijgend teruggebracht tot één adapter per familie.

## 4. Technische aanpak

### Dashboards en opslag

Voeg afzonderlijke dashboardcomponenten en een kleine widgetregistratie toe. De bestaande `page.tsx` selecteert de weergave; editorlogica komt niet in de al omvangrijke routevoorwaarde terecht. Gebruik stabiele IDs voor dashboards, secties, panelen en items; namen mogen wijzigen zonder verwijzingen te breken.

Voorgestelde nieuwe SQLite-entiteiten: dashboards, secties/panelen, dashboarditems, groepen, groepsleden, capabilities/rechtentoekenningen, API-credentials, zoekmachines, uitnodigingen, widgetdefinities en laatste aangeleverde waarden. Leg in migraties een schemaversie vast. Bestaande gebruikers, voorkeuren en koppelingen behouden hun identiteit. Het definitieve schema volgt in fase 1.

Sla wijzigingen atomair op, met een revisienummer om gelijktijdige bewerkingen herkenbaar af te wijzen. Valideer grenzen, posities, afmetingen, panelen, verwijzingen en toegestane itemtypes op de server. De editor laadt alleen wanneer hij nodig is. Selecteer een onafhankelijke drag/resize-oplossing op basis van een kleine proef met groepen, panelen en statische export voordat we die vastleggen.

### Integratielaag

Maak een adapterregister met gedeclareerde capabilities zoals `test`, `summary`, `search` en benoemde acties. Niet iedere adapter ondersteunt alles. Dashboards, bestaande modules en zoeken gebruiken dezelfde adapter in de Python-service. De bestaande Proxmox-certificaatvalidatie en Homepage-versleuteling blijven behouden tijdens de migratie.

Toon per koppeling de laatste succesvolle meting, verversmoment en foutstatus. Gebruik begrensde verzoeken, verversing alleen waar nodig en een beperkte cache. Meet de belasting van de bestaande productieconfiguratie voordat achtergrondwerk wordt toegevoegd. Geen verplichte Redis, aparte Node-runtime of extra database.

### Rechten en machine-API

Hergebruik de bestaande identiteit en sessies. Breid de huidige rollen uit met groepen en capabilities; migreer huidige roltoegang expliciet. Persoonlijke dashboards blijven in de MVP van hun eigenaar. Een groep geeft toegang tot apps, bronnen en acties; dashboarddeling hoort bij A11 en volgt later.

Een zichtbaar item geeft geen impliciete nieuwe bronrechten. Hetzelfde geldt voor zoeken, API-aanroepen, cachetoegang en backup. Servercontrole blijft bepalend, ook wanneer een knop verborgen is. B8 en E2 vereisen actierechten naast leesrechten.

Voeg machineauthenticatie doelgericht toe aan de huidige globale API-controle: geldige machinecredentials leveren een begrensde principal; browserverzoeken behouden sessie en CSRF. Ongeldige machineheaders mogen niet ongemerkt terugvallen op ruimere sessierechten. Credentials zijn intrekbaar, alleen bij aanmaak zichtbaar, gehasht opgeslagen en gekoppeld aan toegestane resources en acties. Accountuitschakeling en rechtenintrekking werken direct door.

### Eigen API-widgets en gegevensuitwisseling

Begin met declaratieve widgetdefinities: benoemde bronnen, velden, weergavetypes, opties en acties. Laat geen willekeurige Python, JavaScript of JSX op de server uitvoeren. Homarr's Custom JSX-systeem is een referentie voor mogelijkheden, geen vereiste om dezelfde taal te ondersteunen.

Maak onderscheid tussen drie stromen: externe gegevens ophalen voor E1, expliciete upstream-acties voor E2 en ControlDeck beheren via E4. De oorspronkelijke wens om gegevens naar ControlDeck te sturen krijgt daarnaast een gevalideerd ingest-endpoint met de laatste waarde per gegevensstroom. Documenteer deze uitbreiding apart van Homarr-pariteit; tijdreeksen, webhooks en tweerichtingssynchronisatie volgen later.

Serververzoeken krijgen een beheerde bestemmingsscope. Interne homelabadressen zijn mogelijk, maar redirects, DNS-resolutie, metadata-adressen, padontsnapping, antwoordgrootte en credentialdoorsturen krijgen expliciete regels. Acties hebben een benoemde methode en bestemming, passende bevestiging en veilige auditmetadata. Het systeem mag geen onbeperkte proxy worden.

### Backup en migratie

Een codetag is geen backup van databases, geheime sleutels of runtimeconfiguratie. Maak vóór schemawijzigingen een consistente private backup met de SQLite-backupfunctie, relevante private JSON en benodigd sleutelmateriaal of een gedocumenteerde vault-herstelroute. Exports blijven buiten Git en images.

F6 bevat export, inhoudscontrole, herstel naar een testomgeving en gecontroleerd productieherstel. Controleer versies, bestandspaden en archiefgrenzen vóór uitpakken. Maak vóór vervangen een herstelkopie; ongeldige of onvolledige backups mogen de huidige installatie niet wijzigen. Een eerder werkende release mag niet zonder passend databaseherstel tegen een incompatibel nieuw schema worden gestart.

## 5. Bouwfasen en acceptatie

Iedere fase is een afzonderlijk reviewbaar pakket. Een vroeg werkend dashboard is een tussenresultaat; de volledige gekozen MVP is pas af na alle verplichte pakketten.

| Fase | Werkpakket | Gereed wanneer |
| --- | --- | --- |
| 0 — Uitgangssituatie | Codeherstelpunt, bestaande controles en inventarisatie. | Remote tag geverifieerd en uitgangsresultaten vastgelegd. Codeherstelpunt en controles zijn uitgevoerd; runtimebackup is nog uit te voeren vóór migraties. |
| 1 — Fundament | Schema, migraties, autorisatiecontract, adapterregister, migratie van bestaande appverwijzingen en private herstelprocedure. | Migratie met synthetische bestaande data behoudt IDs, voorkeuren, koppelingen en rechten; herstelproef slaagt. |
| 2 — Dashboardeditor | A1–A7, met B1/B4/B5 als eerste inhoud. | Werk/Homelab, dupliceren, standaardkeuze, secties, vaste panelen, slepen en vergroten blijven na herladen behouden; een andere gebruiker kan ze niet wijzigen. |
| 3 — Apps en zoeken | B1–B8, inclusief iconen, bereikbaarheid, externe zoekmachines en media-aanvragen. | Eén zoeking vindt alleen toegestane resultaten; een media-aanvraag wordt werkelijk door de adapter uitgevoerd en fouten worden zichtbaar afgehandeld. |
| 4 — Integraties | D1–D10 in batches volgens de vastgelegde dienstenlijst; bestaande adapters eerst. | Iedere afgesproken adapter heeft echte capabilities en tests; verbindingsfouten blokkeren andere bronnen niet. |
| 5 — Eigen gegevens en API | E1–E4 plus expliciete ingest-uitbreiding. | Een testapp kan gegevens aanleveren en uitlezen, een eigen widget toont ze en een toegestane actie werkt; ingetrokken credentials en ongeoorloofde bronnen worden afgewezen. |
| 6 — Gebruikers en herstel | F1–F6 afronden: groepenbeheer, bestaande Google-SSO, Google-accounttoelating, voorkeuren, backup- en herstelinterface. | Google-login en rechtentoekenningen zijn getest; een volledige backup is op een schone testinstallatie hersteld. |
| 7 — MVP-release | Browsercontrole, belastingmeting, documentatie en releasecontrole. | Alle verplichte IDs en afgesproken adapters zijn aantoonbaar af; CI blokkeert publicatie/deployment bij een fout. |
| 8 — Uitbreidingen | C1–C25 naar behoefte; vervolgens de overige functies buiten de gekozen MVP. Native Kasm is inmiddels een gekozen integratiebatch. | Afzonderlijk geselecteerd en getest. |

De autorisatiebasis van F1/F2 wordt in fase 1 aangelegd; fase 6 maakt het beheer compleet. Hetzelfde geldt voor het onderscheid tussen herstelbaarheid vóór migraties en de uiteindelijke F6-interface.

## 6. Test- en releasebeleid

Iedere nieuwe of gewijzigde functie krijgt de categorieën normaal, boundary/randgevallen en faal/afwijzing volgens [TESTING.md](TESTING.md). Iedere bugfix krijgt een benoemde regressietest die zonder fix faalt. Test op gedrag, niet uitsluitend op snapshots of de eigen implementatie.

| Gebied | Normaal | Boundary | Afwijzing en beveiliging |
| --- | --- | --- | --- |
| Dashboard/editor | Opslaan, dupliceren en verplaatsen. | Leeg dashboard, volle sectie, paneelgrenzen en gelijktijdige wijzigingen. | Onbekend type, ongeldige positie, andere eigenaar en ontbrekende CSRF. |
| Apps en zoeken | App openen en toegestane zoekresultaten tonen. | Unicode, geen resultaten, bron deels uitgevallen en zoeklimieten. | Onveilige links, verborgen bron in resultaten, malafide upload en te grote invoer. |
| Iedere adapter | Werkelijk parser-/transportpad met synthetische bron. | Lege of gedeeltelijke respons en ondersteunde versiegrenzen. | Timeout, TLS-fout, 401/403, ongeldige brondata en ontbrekende rechten. |
| API en acties | Waarde aanleveren, uitlezen en toegestane actie. | Nulwaarde, payloadlimiet, verlopen informatie en herhaalde aanvraag. | Ingetrokken credential, te ruime scope, verkeerde methode, SSRF en secretlekkage. |
| Identiteit en groepen | Toegestane Google-login en geërfde capabilities. | Meerdere groepen, laatste admin en verlopen toelating. | Verkeerde issuer, handtekening of nonce, ongeoorloofd Google-account en uitgeschakeld account. |
| Backup en migratie | Export en volledige herstelproef. | Lege installatie, schema-upgrade en gelijktijdige schrijfactiviteit. | Verkeerde sleutel, kapot archief, padtraversal, versieconflict en onvoldoende rechten. |

Frontendtests blijven snel; voeg browsergedragstests toe voor slepen, vergroten, panelen, opslaan, zoekbediening en login-/rechtenovergangen. Onderzoek in fase 1 de kleinste passende browsertestinrichting. Live adapters worden aanvullend getest met private testconfiguratie; unit-tests vervangen dat niet.

Vóór iedere push draaien `python -m pytest -q`, `npm test`, `npm run typecheck` en `npm run build` in de daarvoor bedoelde omgeving. Voor releases blijven ook bestaande shell-, package-, Docker- en readinesschecks vereist. De huidige CI heeft `verify` als afhankelijkheid van publiceren; behoud en controleer die blokkade bij workflowwijzigingen.

Meet op het doelplatform laden, zoeken, geheugengebruik en adaptertimeouts met een representatieve hoeveelheid tegels en koppelingen. Leg de gemeten baseline en numerieke acceptatiegrenzen in fase 1 vast; er is nu nog geen onderbouwde prestatieclaim.

## 7. Risico's, keuzes en resterende vragen

- **Omvang:** de gekozen MVP omvat meer dan een dashboardeditor. Alle integratiefamilies, zoekacties, eigen API's en accountbeheer maken dit een meerfasig producttraject. Geef pas een betrouwbare doorlooptijd na de adapterlijst en editorproef.
- **Nog te kiezen diensten:** welke concrete producten uit D1–D10 worden daadwerkelijk gebruikt, met welke versies? Dit bepaalt adapterwerk en live verificatie. Fase 1 en de dashboardbasis kunnen al zonder credentials beginnen.
- **SSO-inrichting vastgesteld:** Camiel gebruikt de bestaande Google-SSO. Extra loginproviders en lokale wachtwoordaccounts vervallen uit de MVP. Toelating en eventuele uitnodigingen sluiten aan op Google; deel geen echte accountlijsten in Git.
- **Custom widgets:** declaratieve velden, kaarten en knoppen dekken de eerste E1–E3-aanpak. Volledige programmeerbare Homarr-JSX-pariteit is een aanvullende technische keuze met meer beheer- en testwerk.
- **Rechtenmigratie:** huidige Homepage-data is gedeeld en gekoppeld aan Bookmarks-rechten. Geef nieuwe dashboards niet automatisch toegang tot alle bestaande bronnen.
- **Documentatieachterstand:** `docs/ARCHITECTURE.md` noemt collectors nog toekomstig, terwijl adapters bestaan. `docs/OPERATIONS.md` noemt nog een foundation zonder gebruikersdatabase/secrets. Werk deze passages bij in fase 1 op basis van de actuele opslag en herstelproef.
- **Herbruikbare broncode:** Homarr gebruikt Apache-2.0; ControlDeck heeft GPL-3.0 als projectlicentie. Registreer bij daadwerkelijke overname de exacte bestanden, broncommit, notices en aanpassingen in `docs/THIRD-PARTY.md`. Dit onderzoek heeft geen Homarr-applicatiecode in ControlDeck geïmporteerd.

## 8. Eerstvolgende uitvoerstap

Begin met fase 1: contracten en migraties voor dashboards en rechten, een editorproef met een groep en vast paneel, en een adaptermatrix met de daadwerkelijk gebruikte diensten. Lever daarna fase 2 als eerste bruikbare dashboardversie binnen de bestaande ControlDeck-shell op. Leg resultaten en resterende acceptatiepunten per fase vast; publiceer geen fase als volledige MVP zolang geselecteerde functies ontbreken.
