# Codeonderzoek: dubbele functionaliteit en hergebruik

Datum: 18 oktober 2026. Onderzochte basis: commit `b74bd10`.

## Conclusie

ControlDeck heeft al een bruikbare modulaire basis. Verder bouwen op die basis is verstandiger dan opnieuw beginnen. De grootste winst zit in **één gegevenslaag per dienst, gedeelde widgetbouwstenen en pagina's die die widgets samenstellen**. De code hoeft daarvoor niet naar microservices, een Node-server of een zwaar pluginframework.

De belangrijkste overlap zit niet in letterlijk gekopieerde lange functies, maar in dezelfde verantwoordelijkheid die op meerdere plaatsen terugkomt: gegevens ophalen en verversen, verbindingen inrichten, rechten bepalen, instellingen registreren en tegels verplaatsen. De aanbeveling is een reeks kleine verbeteringen met behoud van bestaande gegevens en rechten.

Dit document is onderzoek en een uitvoeringsvoorstel. Er zijn bij dit onderzoek geen providers, accounts, dashboards of productie-instellingen veranderd.

## Herbeoordeling op commit `87bee12` (18 oktober 2026, middag)

Sinds `b74bd10` zijn Files, Virtual Apps (Kasm, VM-status/-wekken), de Proxmox-inventaris (gasten, netwerk, opslag) en de ProxMenux-overzichten toegevoegd. De bevindingen hieronder zijn opnieuw tegen de code gelegd.

| Bevinding | Stand nu | Toelichting |
| --- | --- | --- |
| **Nieuw — P0: upstreamfouten als HTTP 502** | **Bug, eerst oplossen** | Cloudflare vervangt elk origin-502-antwoord door een eigen pagina; de JSON-melding bereikt de gebruiker dan niet ("niet beschikbaar"). Files en Virtual Apps zijn hierop al gerepareerd (status 424, met regressietest). Nog 8 plaatsen: `backend/proxmox.py:312, 322, 339, 364`, `backend/linkwarden.py:153`, `backend/homepage_integrations.py:161`, `backend/cronjob_api.py:42`. Voorstel: één constante/foutklasse `UpstreamError` met status 424 en een regressietest per route. |
| 1. Dubbele ophaal-/ververslussen | **Gegroeid** | Drie nieuwe, vrijwel identieke lussen in `proxmox-guests.tsx`, `proxmox-network.tsx` en `proxmox-storage.tsx` (zelfde `AbortSignal`-, `busy`-, 401/403/409-, `stale`- en `pending ? 5 s`-logica; alleen endpoint en teksten verschillen), plus `virtual-apps-page.tsx`. In totaal 11 `setInterval`-lussen; `/api/proxmenux/summary` wordt door 3 componenten los opgehaald. Een generieke `usePolledResource(fetcher, {interval, fastWhile})` vervangt de drie inventarislussen direct. |
| 2. Vault vóór widgetcache | Ongewijzigd | Virtual Apps leest dezelfde vaultwaarde (`CONTROLDECK_APP_LAUNCHES`) per aanvraag; dezelfde configuratierepository zou beide dienen. |
| 3. Twee Kasm-implementaties | **Opgelost** | `backend/modules/kasm.py` levert `kasm_config`, `kasm_post` (intern `apiUrl` met certificaatpinning) en `linked_user`; aanmelden en Virtual Apps gebruiken beide. Aparte rechten `kasm` en `virtual-apps` zijn behouden. |
| 5. Verspreide HTTP-wrappers | Gegroeid | 25 frontendbestanden doen zelf `fetch`; 19 zetten zelf de CSRF-header. Nieuw sinds de audit: `files.ts`, `virtual-apps.ts`, `page-layouts.ts`. Die drie hebben al een gestructureerde fout (`status`, `relink`, `notLinked`) en zijn een goed model voor `ApiError`. |
| 6. Modulekennis in de hoofdpagina | Gegroeid | `page.tsx` kiest nu tussen 16 routes in één voorwaardelijke expressie. |
| 9. Infrastructuur bij productmodules | Ongewijzigd | `save_private` komt nog uit `linkwarden.py` (gebruikt door `homepage.py` en `files.py`). |
| 10. Autorisatie opnieuw opgebouwd | Gegroeid | 16 plaatsen doen `filter_configuration(load_config(...))` plus een eigen module-ID-zoekactie; nieuw: `files.py`, `page_layouts.py`, `virtual_apps.py`. |
| 11. Backendcaches | Gegroeid | Nieuwe eigen caches in `virtual_apps.py` (workspaces, 60 s) en `vm_power.py` (VM-status 10 s, VM-koppeling 60 s). Ze lossen elk hetzelfde op (TTL + lock), met verschillende vormen. |
| 13. URL-/HTTP-beleid | Gegroeid | Nieuwe validators `nextcloud_origin` (Files) en `workspace_icon`/`connect_url` (Virtual Apps), naast `secure_origin`, `provider_url`, `base_url`, `integration_url` en `display_url`. Terecht verschillende contracten, maar gedeelde fixtures ontbreken. Ook vier eigen HTTP-aanroepfuncties (`files.call`, `homepage_integrations.call`, `linkwarden.upstream`, `widgets.transport.call`) met elk eigen time-outs en foutvertaling. |

### Aanvullende bevindingen (nieuw in deze herbeoordeling)

**A1. P1 — Modules lezen de Proxmox-verbinding rechtstreeks van schijf.** `proxmox/connection.json` wordt buiten `proxmox.py` gelezen in `cronjobs.py:94`, `cronjob_api.py:76`, `linkwarden.py:158`, `proxmenux.py:258` en `vm_power.py:109`; elk bouwt zelf een `Client` en vangt eigen fouten af. Een wijziging aan het opslagformaat of aan certificaatpinning moet dus op zes plaatsen landen. *Voorstel:* een `ProxmoxConnection`-repository in `proxmox.py` (`load()`, `client()`, `require()`) die de anderen importeren. *Bewaken:* bestandsrechten (0600) en de alleen-lezen/startrecht-scheiding blijven gelijk.

**A2. P1 — Persoonlijke geheimen: twee opslagvarianten met een andere sleutel.** Linkwarden-tokens (`linkwarden.py:130`) zijn opgeslagen onder een hash van *server + e-mailadres*; Files-app-wachtwoorden (`files.py:139`) onder *server + login-subject*. Een gewijzigd e-mailadres laat de Linkwarden-koppeling dus stil vervallen, Files niet. *Voorstel:* één `PersonalSecretStore(module)` met `get/put/delete(account, server)` op basis van het stabiele subject, met `save_private` (bevinding 9) als opslag. *Bewaken:* bestaande Linkwarden-bestanden expliciet migreren (oude sleutel → nieuwe), niet weggooien; nooit een geheim van een andere server teruggeven.

**A3. P2 — Elf eigen `before_request`-hooks en drie eigen foutafhandelaars.** Zie `auth`, `cronjobs`, `cronjob_api`, `dashboards`, `files`, `homepage`, `installations`, `linkwarden`, `proxmenux`, `proxmox`, `virtual_apps` (hooks) en `FilesError`, `LinkwardenError`, `KasmError` (handlers, met statussen 424, 502 en 424). Iedere hook herhaalt "pad-prefix → module-ID → beheerder?". *Voorstel:* per module een Flask-**Blueprint** met één `require_module("files")`/`require_manager()`-decorator (bouwt op de `PermissionContext` van bevinding 10) en één gedeelde `UpstreamError`-basisklasse (lost de 502-bug in één keer structureel op). *Bewaken:* `/api/widget-ingest` houdt zijn machine-authenticatie; volgorde t.o.v. de sessie-/CSRF-hook in `auth.py` niet veranderen.

**A4. P2 — Tests bouwen 26× zelf een app en 21× zelf een sessie.** Er is geen `tests/conftest.py`; elke testmodule heeft een eigen accounts-bestand, `create_app`, `Vault.from_env`-patch en `session_transaction`. Zeven frontendtests vervangen elk zelf `globalThis.fetch`. *Voorstel:* gedeelde fixtures `app_factory(accounts)`, `login(email)` en `fake_vault(values)` in `conftest.py`, en een `mockFetch()`-helper voor de frontendtests. Bestaande tests ongewijzigd laten slagen; alleen nieuwe tests gebruiken ze eerst. *Winst:* nieuwe modules krijgen sneller de verplichte normaal/rand/faal/auth-tests.

**A5. P2 — Statuskleuren zijn hard gecodeerd en per onderdeel anders.** De CSS bevat o.a. `#22c55e`/`#63c691` (goed), `#e9b900`/`#9a6700` (waarschuwing) en `#ef4444`/`#cf222e`/`#c0392b`/`#f08080` (fout) naast 96 `var(--…)`-tokens. Meters, ProxMenux-gezondheid, Proxmox-inventaris en VM-status gebruiken elk een eigen set; donker/licht-contrast wordt per plek opnieuw gekozen. *Voorstel:* tokens `--ok`, `--warn`, `--error`, `--info` (met donkere varianten) in `style.css` en één `StatusBadge` (sluit aan op bevinding 14).

**A6. P2 — Eén laadpatroon voor de drie Proxmox-inventarissen.** Naast de ververslus (bevinding 1) delen `proxmox-guests`, `-network` en `-storage` ook het samenvoegen van Proxmox-inventaris en ProxMenux-monitor, de "eerst koppelen"-melding bij 409 en het `stale`-label. *Voorstel:* `useInventory(endpoint, monitorEndpoint, validate)` die `{data, monitor, error, pending}` teruggeeft; elk component houdt alleen zijn eigen weergave. Dit is de kleinste, veiligste eerste toepassing van `usePolledResource`.

**A7. P3 — Kleine dubbele hulpfuncties.** Twee bytesformatters met verschillende uitkomst (`lib/files.ts:formatSize` met komma, `lib/proxmox.ts:bytes`); twee lijsten met geheime URL-sleutels (`backend/widgets/presentation.py:PRIVATE_KEYS` en de regex in `lib/service-widgets.ts:offerLink`) die uit elkaar kunnen lopen; eigen `https()`-controle in `lib/virtual-apps.ts` naast `safeImage`/`offerLink`. *Voorstel:* één `formatBytes` (nl-NL) en een gedeelde fixtureset met toegestane/geweigerde URL's voor Python én TypeScript (sluit aan op bevinding 13); de dubbele validatie zelf behouden.

**A8. P3 — Persoonlijke pagina-indelingen: `media` is voorbereid maar ongebruikt.** `backend/page_layouts.py` en `lib/page-layouts.ts` accepteren `media`, terwijl de Media-pagina (`media-widgets.tsx`) nog geen `EditableGrid` gebruikt. Of aansluiten (één regel per tegel, zelfde patroon als Proxmox), of de pagina-ID verwijderen tot het zover is, zodat de API geen ongebruikte opslag aanbiedt.

**Aangepaste volgorde:**

| Ronde | Wijziging | Waarom eerst |
| --- | --- | --- |
| 0 | 502 → `UpstreamError` (424) op de 8 plaatsen, met regressietest per route | Gebruikerszichtbare bug, klein |
| 1 | `conftest.py`-fixtures (A4) en `requestJson`/`ApiError` (bevinding 5) | Maakt alle volgende rondes goedkoper en veiliger |
| 2 | `usePolledResource` + `useInventory` voor de drie Proxmox-inventarissen (bevinding 1, A6) | Grootste letterlijke dubbeling, laag risico |
| 3 | `ProxmoxConnection`-repository (A1) en `PersonalSecretStore` met migratie (A2) | Koppelingen op één plek; e-mailwijziging breekt niets meer |
| 4 | Blueprints met `require_module` en `PermissionContext` (A3, bevinding 10) | Raakt alle modules; pas na ronde 1 met goede fixtures |
| 5 | Statustokens/`StatusBadge` (A5), widgetinstellingen en register (bevindingen 6–7), dashboard op `EditableGrid` (8) | Grotere UI-stappen |
| 6 | Connectorconsolidatie en vaultoptimalisatie (bevindingen 2 en 4) | Vergt migratieplan |

Ronde 3 uit het oorspronkelijke plan (Kasm-client) is vervallen: al gedaan.

## Reikwijdte en bewijs

Repositorybrede inventarisatie van de eigen backend, frontend, scripts, installatie/deployment, configuratiestructuur en tests; verdiepende codelezing van de hieronder genoemde overlap. De inventaris omvat 42 backend-Pythonbestanden (4.980 regels), 77 TypeScript/TSX-bestanden onder `components`, `lib` en `modules` (3.571 regels), de applicatiepagina, 14 eigen scriptbestanden (1.658 regels), 37 Python-testbestanden en 26 frontendtestbestanden. Regelaantallen zijn fysieke regels, geen maat voor complexiteit.

Ook importafhankelijkheden en functie-inhoud van alle backend-Pythonbestanden zijn statisch onderzocht. Vergelijking van identieke AST-functiebodies met minimaal vier statements leverde geen exacte dubbels op. Dat sluit kleinere, bijna gelijke of functioneel overlappende implementaties niet uit.

Gegenereerde bestanden, dependencies, gedownloade mockupbundels, private runtimegegevens en andere werkmappen zijn geen eigen productcode en vallen buiten de inhoudelijke audit. Geen volledige veiligheidspentest, live belastingmeting of nieuwe acceptatietest van alle externe diensten. Prestatiebevindingen hieronder zijn afgeleid uit codepaden, niet uit gemeten productietijden.

## Wat al goed hergebruikt wordt

| Bouwsteen | Huidige toepassing | Advies |
| --- | --- | --- |
| `frontend/modules/service/index.tsx` en `cards.tsx` | Dezelfde serviceweergave op Media en persoonlijke dashboards | Behouden; ophalen losmaken van presenteren |
| `frontend/modules/linkwarden/view.tsx` | Linkwarden op Bookmarks en als dashboardmodule | Behouden; verder opsplitsen in gegevenshook, lijst en beheerformulier |
| `frontend/components/proxmox-summary.tsx` | Clusteroverzicht en dashboardmodule gebruiken dezelfde inhoud | Behouden; dezelfde bron ook aan systeemmeters leveren |
| `frontend/lib/layout-grid.ts` en `components/editable-grid.tsx` | Rasterberekening en bediening voor onder andere Bookmarks en Proxmox | Uitbreiden naar het dashboard |
| `frontend/components/app-icon.tsx` | Favicon, eigen PNG en terugval voor meerdere linkweergaven | Behouden; media-artwork krijgt wel een eigen formaat |
| `backend/dashboard_apps.py` | Gedeelde appverwijzingen voor dashboards en zoeken | Behouden; geen kopieën van appnamen en adressen opslaan in tegels |
| `backend/widgets/transport.py`, `adapters.py`, `presentation.py` | Transport, broninterpretatie en veilige presentatie zijn al gescheiden | Verder uitbouwen, geen tweede integratieplatform ernaast |
| `backend/agent_client.py` | Eén smalle route naar de afzonderlijke SSH-agentproxy | Proces- en rechtenbegrenzing behouden |

## Bevindingen op prioriteit

P1 betekent hier de eerste verbeteringsronde; het is geen classificatie van een beveiligingslek.

### 1. P1 — Dezelfde gegevens krijgen meerdere ophaal- en ververslussen

**Plaatsen:** `frontend/components/proxmox-summary.tsx:22`, `frontend/components/proxmenux-health.tsx:9`, `frontend/modules/system/index.tsx:9`, `frontend/modules/system/metrics.ts:8`, `frontend/modules/service/index.tsx:9`.

CPU- en geheugenmeters roepen allebei `/api/proxmox/summary` aan. Temperatuur en vermogen gebruiken allebei `/api/proxmenux/summary`. Iedere afzonderlijke widget maakt zijn eigen effect, timer en aanvraag. Het Proxmox-overzicht heeft daarnaast een eigen ververslus. De bestaande backendcache beperkt providerverkeer, maar voorkomt deze browseraanvragen, parsing en configuratiecontroles niet.

**Voorstel:** een kleine gedeelde bronlaag met `useResource`/specifieke hooks zoals `useClusterSummary`, `useNodeHealth` en `useServiceSource`. Meerdere widgets abonneren zich op dezelfde bron; selectors maken er afzonderlijke meters van. Deel lopende aanvragen en laat de laatste abonnee de timer opruimen. Gebruik bestaande React-middelen; voeg pas een library toe als de eenvoudige oplossing tekortschiet.

**Bewaken:** identiteit en bronconfiguratie maken onderdeel uit van de bronidentiteit. Bij afmelden of 401/403 moeten gedeelde gegevens verdwijnen. Een tijdelijke storing mag oude gegevens alleen zichtbaar laten met expliciete ouderdom/status. Een ingetrokken recht mag nooit als een tijdelijke storing behandeld worden.

**Bewijs van verbetering:** vier systeemmeters op twee endpoints geven per verversronde twee gedeelde bronaanvragen; gelijke servicewidgets delen een aanvraag. Tests voor normale verversing, laat antwoord na bronwissel, afmelden, ingetrokken rechten, timeout en laatste abonnee weg.

### 2. P1 — Vault lezen gebeurt vóór de widgetcache

**Plaatsen:** `backend/widget_sources.py:58`, `backend/vault.py:46`, `backend/service_widgets.py:35`, `backend/service_widgets.py:68`.

Een widgetaanvraag leest eerst `sources(app)`. `Vault.read()` voert daarvoor een CLI-`list` en een CLI-`run` uit. Pas daarna wordt de 30-seconden-datacache geraadpleegd. Ook bronlijsten en beschermde afbeeldingen lezen deze inrichting. Een cachehit voor media is dus niet automatisch een goedkope aanvraag. Bovendien wordt de moduleconfiguratie opnieuw geladen bij bronautorisatie.

**Voorstel:** eerst één gevalideerde configuratie- en rechtenprojectie per request. Vervolgens een afzonderlijke, begrensde configuratierepository met expliciet ververs-/invalidatiegedrag. Houd geheimen uitsluitend serverzijdig en gebruik de bestaande Infisical-client. Meet CLI-aanroepen voordat een ruimere cache wordt ingevoerd.

**Bewaken:** geen blinde TTL-cache waardoor ingetrokken toegang nog minuten werkt. Rechtenwijzigingen, credentialrotatie en vaultuitval krijgen een expliciet contract. De broncache mag gegevens delen; een positieve gebruikersautorisatie wordt niet onbegrensd meegedeeld.

**Bewijs van verbetering:** tests tellen CLI-aanroepen en bewijzen dat gewijzigde bronrechten en credentials oude cachegegevens niet opnieuw toelaten. Ook lege inrichting, kapotte JSON en vaultuitval worden getest.

### 3. P1 — Kasm heeft twee implementaties van dezelfde basisverbinding

**Plaatsen:** `backend/modules/kasm.py:11`, `backend/virtual_apps.py:35`, `backend/virtual_apps.py:56`, `backend/app_launches.py:13`.

Zowel de aanmeldmodule als Virtual Apps valideren Kasm-origin, API-credentials en de koppeling van ControlDeck-gebruiker naar Kasm-gebruiker. Beide spreken dezelfde publieke Kasm-API aan, met verschillende foutafhandeling en timeouts.

**Voorstel:** één `KasmConnection`/`KasmClient` die configuratie en gebruikerskoppeling valideert. Aanmelden, workspaces tonen, starten en stoppen worden afzonderlijke methoden en afzonderlijk geautoriseerde acties op die client.

**Bewaken:** de loginlink en een workspacelink hebben verschillende toegestane routes; maak daarvoor geen algemene redirectfunctie. Houd ook de huidige rechten `kasm` en `virtual-apps` afzonderlijk totdat een bewuste rechtenmigratie is ontworpen.

**UX:** Kasm als portaal openen en een workspace starten zijn verschillende handelingen. Toon ze onder één herkenbare dienst, met duidelijk benoemde acties. Verwijder niet automatisch een van beide mogelijkheden.

### 4. P1 — Homepage-integraties en servicewidgets vormen twee integratiesystemen

**Plaatsen:** `backend/homepage_integrations.py:14`, `backend/homepage_integrations.py:63`, `backend/widgets/adapters.py:123`, `backend/widget_sources.py:10`, `backend/dashboard_apps.py:13`, `frontend/components/homepage-links.tsx:41`.

Seerr bestaat zowel als Homepage-koppeling met opgeslagen aantallen en versleutelde SQLite-credentials als in de centrale servicewidgetbronnen uit Infisical. De capabilities verschillen: aantallen tegenover aanvragen en artwork. De gedeelde dienstverbinding en authenticatie horen echter niet tweemaal ingericht te hoeven worden. Jellyfin bestaat in het oudere pad en mag bij samenvoegen niet verloren gaan.

Ook de actualiteit verschilt: apptegels gebruiken opgeslagen samenvattingen; servicewidgets halen actuele informatie op. De statusroute van een Homepage-integratie geeft nieuwe aantallen terug, maar schrijft die daar niet terug naar de opgeslagen metadata die de appcatalogus leest.

**Voorstel:** één connector per dienst, met capabilities zoals `summary`, `requests`, `sessions` en `artwork`. Laat een app-link desgewenst verwijzen naar een connector; elke widget kiest een capability en weergave. Migreer bestaande integraties expliciet en gecontroleerd naar vaultreferenties. Bewaar link-ID's, Jellyfin-ondersteuning en huidige rechten. Maak zichtbaar wanneer een getal actueel of oud is.

**Geen automatische migratie:** de oude gedeelde Bookmarks-toegang en de nieuwe expliciete bron-ACL zijn niet hetzelfde. Bepaal per bestaande bron wie toegang houdt; kopieer nooit stilzwijgend alle gebruikers naar een nieuwe bron.

### 5. P1 — HTTP-verzoeken en foutafhandeling zijn verspreid

**Plaatsen:** `frontend/lib/dashboards.ts:27`, `frontend/lib/linkwarden.ts:12`, `frontend/lib/page-layouts.ts:9`, `frontend/lib/service-widgets.ts:49`, `frontend/lib/files.ts:57`, `frontend/components/cronjobs-connect.tsx:7`, `frontend/components/cronjobs-page.tsx:16`.

Veel wrappers herhalen JSON-body, CSRF-header, `no-store`, JSON-parsing en foutmelding. Cronjobs heeft zelfs twee lokale `api`-helpers voor dezelfde API-prefix. Timeout, annulering en foutclassificatie verschillen tussen functies.

**Voorstel:** een kleine geteste `requestJson` met een gestructureerde `ApiError` (`status`, `code`, veilige melding), signaal en optionele validator. Elke module behoudt een dunne wrapper die uitsluitend eigen routes en methoden accepteert.

**Uitzonderingen:** Files-downloads, ruwe uploadchunks en herhaalpogingen krijgen een apart binair/streamingpad. Kasm-start en andere mutaties mogen niet generiek automatisch worden herhaald. De browser mag nooit een willekeurig upstreamadres aan een algemene proxy doorgeven.

### 6. P2 — Modulekennis staat in meerdere registers en in de hoofd-app

**Plaatsen:** `frontend/app/page.tsx:239`, `frontend/modules/registry.ts:8`, `frontend/lib/dashboard-modules.ts:3`, `frontend/lib/service-widgets.ts:1`, `backend/dashboard_modules.py:10`, `backend/widget_sources.py:10`.

Een nieuwe functie vraagt aanpassingen aan de paginakeuze, componentregistratie, dashboardcatalogus en backendvalidatie/rechten. Een deel hiervan is terecht servervalidatie, maar de frontend houdt meerdere catalogi met dezelfde module-ID's en labels bij. De lange voorwaardelijke paginarender maakt uitbreiden en testen onnodig lastig.

**Voorstel:** één frontenddefinitie per functie met pagina, widgets en instellingen. De applicatiepagina beheert alleen sessie, navigatie en de houder. Backendregistratie blijft expliciet en onafhankelijk afdwingbaar. Voeg een contracttest of buildgegenereerde publieke manifestprojectie toe voor overeenkomende ID's, capabilities en instellingenversies; geen dynamische code uit externe diensten laden.

### 7. P2 — Instellingenmodellen zijn aan het dashboard gekoppeld

**Plaatsen:** `frontend/modules/contracts.ts:1`, `frontend/lib/dashboards.ts:5`, `frontend/lib/service-widgets.ts:17`.

`ModuleSettings` wordt afgeleid van `DashboardItem`. Daardoor hangt een herbruikbare module af van het opslagmodel van één specifieke pagina. De dashboardinstellingen zijn bovendien één verzameling optionele velden: een type kan een combinatie van Linkwarden-, systeem- en servicevelden uitdrukken die functioneel nergens bij hoort.

**Voorstel:** onafhankelijke instellingen per widgettype en een getagde union die `widgetId` aan het juiste instellingstype koppelt. Het dashboard bewaart alleen een widgetinstantie met positie en instellingen; de module heeft geen kennis van het dashboard nodig.

`WidgetData` is nu een breed presentatiemodel met optionele velden voor iframe, agenda, download, aanbieding en statistiek. Splits dit stapsgewijs in een gedeelde statusomhulling en getagde resultaten zoals lijst, meting en embed. Alleen domeinvelden toevoegen waar een weergave ze werkelijk nodig heeft.

### 8. P2 — Dashboard en pagina-indelingen hebben twee bedieningen voor hetzelfde raster

**Plaatsen:** `frontend/components/dashboard.tsx:146`, `frontend/components/editable-grid.tsx:11`, `frontend/lib/layout-grid.ts:1`, `backend/dashboards.py`, `backend/page_layouts.py:23`.

Bookmarks en Proxmox gebruiken `EditableGrid`; het dashboard heeft eigen drag/drop-, pointerresize- en toetsenbordlogica. De berekeningen zijn al deels gedeeld via `layout-grid.ts`, maar fixes voor aanraken, slepen of vergroten moeten nog op meerdere plaatsen landen.

**Voorstel:** ook dashboardsecties laten renderen via `EditableGrid`, met aanpasbare rastergrenzen en een adapter voor dashboarditems. Deel backendgeometrievalidatie als kleine pure functie.

**Niet samenvoegen:** de opslagmodellen. Dashboards hebben inhoud, eigenaarschap, secties en revisies; pagina-indelingen beschrijven alleen positie van bestaande inhoud. Hun grenzen verschillen bewust (onder andere maximale hoogte en rijen).

### 9. P2 — Algemene infrastructuur hangt aan specifieke productmodules

**Plaatsen:** `backend/linkwarden.py:52`, `backend/homepage.py:10`, `backend/files.py:20`, `backend/auth.py:169`, `backend/dashboards.py:115`.

Homepage en Files importeren `save_private` uit Linkwarden. Een generieke atomaire bestandsbewerking heeft daarmee een dienstspecifieke eigenaar. De SQLite-contextmanager staat onder authenticatie terwijl veel andere functies hem gebruiken. Schema-initialisatie is verdeeld over auth, dashboards en andere setupfuncties; de dashboardmigratie maakt bijvoorbeeld ook de zoekmachinetabel aan.

**Voorstel:** kleine `storage`-bouwstenen voor private atomaire bestanden, SQLite-verbindingen en expliciete migraties. Dienstspecifieke repositories blijven verantwoordelijk voor hun eigen records. Eén gedocumenteerde migratievolgorde, met backup- en herstarttests.

**Bewaken:** rechten op bestanden/directories, atomaire vervanging, bestaande versleuteling en sleutelafleiding, ID-sequenties en transacties. Maak hier geen algemene ORM-migratie van zonder concrete noodzaak.

### 10. P2 — Autorisatie wordt vaak opnieuw opgebouwd

**Plaatsen:** `backend/proxmox.py:275`, `backend/proxmenux.py:246`, `backend/cronjob_api.py:96`, `backend/widget_sources.py:68`, `backend/app_launches.py:19`, `backend/virtual_apps.py:148`.

Meerdere endpoints laden de configuratie, filteren deze op de account en zoeken vervolgens naar dezelfde module-ID. Dit vergroot de kans op afwijkende foutcodes of rolinterpretatie en herhaalt werk binnen één aanvraag.

**Voorstel:** een requestgebonden `PermissionContext` met `has_module` en `require_manager`, gebaseerd op de bestaande serverprojectie. Bron-ACL en eigenaarschap blijven extra voorwaarden boven op modulerechten. Houd de machine-authenticatie van `/api/widget-ingest` apart van browsersessies.

### 11. P2 — Backendcaches hebben verschillende blokkering en verversing

**Plaatsen:** `backend/proxmox.py:340`, `backend/proxmenux.py:340`, `backend/service_widgets.py:35`, `backend/cronjob_api.py:235`.

De Proxmox-cache houdt één lock vast tijdens providerverkeer; een trage samenvatting kan daardoor ook het takenpad laten wachten. Servicewidgets geven de lock juist vrij vóór het ophalen, waardoor gelijktijdige misses hetzelfde providerverzoek kunnen starten. ProxMenux heeft een uitgebreider patroon met gedeeltelijke achtergrondverversing.

**Voorstel:** een kleine gedeelde cachevoorziening met één lopende fetch per sleutel, begrensde opslag, expliciete ouderdom en invalidatie. Sleutels verschillen per dienst/configuratie. Neem de achtergrond- en gedeeltelijke resultaten van ProxMenux niet weg om alle caches gelijk te maken.

**Bewijs van verbetering:** gelijktijdige aanvragen voor dezelfde bron veroorzaken één fetch; een trage bron blokkeert geen andere bron; credentialrotatie en autorisatieverlies geven nooit oude toegang terug. Gebruik een monotone klok voor interne looptijden.

### 12. P2 — Lokale-linkbeleid zit centraal, maar buiten de React-modellen

**Plaatsen:** `frontend/lib/local-links.ts:10`, `frontend/components/local-link-visibility.tsx:5`, `frontend/components/bookmark-groups.tsx:23`.

De recente globale regel gebruikt een DOM-observer en scant de links opnieuw bij wijzigingen. Dat dekt veel bestaande weergaven tegelijk. Het betekent ook dat groepsaantallen en rasterplaatsen eerst uit de onzichtbaar gemaakte inhoud berekend kunnen zijn. Bij druk verversende widgets wordt meer van de DOM onderzocht dan alleen de gewijzigde widget.

**Voorstel:** dezelfde zuivere URL-/netwerkpolicy gebruiken in een `VisibleLink`/linkprojectie en in de bronselectie van lijsten. Tel zichtbare resultaten en behandel lege groepen bewust. Houd een beperkte compatibiliteitsvangnetfunctie zolang oude modules nog niet zijn aangepast.

**Bewaken:** alleen de zichtbaarheid verandert; opgeslagen documenten en dashboardreferenties blijven bestaan. Deze voorkeur is geen autorisatiegrens. Dit is een uit code afgeleid UX-/onderhoudsrisico, geen gemeten prestatieprobleem.

### 13. P3 — URL- en foutbeleid lijken op elkaar, maar verschillen terecht deels

**Plaatsen:** `backend/modules/launch_urls.py:5`, `backend/files.py:59`, `backend/linkwarden.py:23`, `backend/homepage_integrations.py:21`, `backend/widgets/transport.py:11`.

Er zijn verschillende URL-validators en HTTP-clients. Deel de mechaniek voor parsing, veilige fouten, resourceopruiming en tests. Behoud benoemde beleidsvarianten: publiek HTTPS, intern HTTP met expliciete toestemming, Proxmox-certificaatpinning, ProxMenux-cluster-CA, downloadstream en browserlink zijn verschillende contracten.

Gebruik voor Python en TypeScript dezelfde fixtures met toegestane/geweigerde URL's waar de bedoeling gelijk is. Verwijder de servervalidatie nooit omdat de frontend ook valideert.

### 14. P3 — Vormgeving en statusweergave kunnen een kleine componentbibliotheek worden

**Plaatsen:** `frontend/modules/service/cards.tsx`, `frontend/modules/system/cards.tsx`, `frontend/components/proxmox-summary.tsx`, `frontend/components/proxmenux-health.tsx`, `frontend/components/modal.tsx`.

Meter, statuslabel, laad-/fout-/lege toestand, laatst bijgewerkt en kaartkop hebben verschillende uitvoeringen. Een kleine set `WidgetFrame`, `AsyncState`, `StatusBadge`, `Meter` en `ObjectLink` maakt widgets consistenter. De bestaande `AppIcon` en `Modal` zijn goede voorbeelden van die richting.

Hergebruik tokens/spacing en gedrag; maak niet één allesomvattende kaart met tientallen booleaanse opties. Een filmposter, appicoon en servermeting hebben bewust andere inhoud en afmetingen. Verplaats teksten geleidelijk naar de bestaande vertalingen; veel dienstweergaven bevatten nog vaste Nederlandse teksten.

## Functionele overlap: wat wel en niet samenvoegen

| Huidige functies | Beoordeling | Gewenste uitkomst |
| --- | --- | --- |
| Media-pagina en mediawidgets op Dashboard | Gewenst hergebruik, al aanwezig | Eén weergave en één bronlaag, meerdere plekken |
| Proxmox-overzicht, Proxmox-dashboardmodule en systeemmeters | Gewenste verschillende weergaven, dubbel ophalen | Eén clusterbron met verschillende selectors/widgets |
| Homepage-links en Linkwarden-bookmarks | Twee bewuste bronnen met andere eigenaar/beheer | Dezelfde linkpresentatie; bron duidelijk aangeven; niet stilzwijgend records samenvoegen |
| Homepage-Seerr en Seerr-servicewidget | Gedeeltelijk dubbele koppeling | Eén connector, meerdere capabilities |
| Kasm-portaal en Virtual Apps | Zelfde dienst, andere handeling | Eén client en herkenbare dienst, behoud aparte acties en rechten |
| Nextcloud-openknop, Files en Agenda | Geen functionele dubbeling | Dienstorigin/connectorconcept delen; OIDC, persoonlijke WebDAV-toegang en agenda-ACL onderscheiden |
| Dashboardindeling en vaste pagina-indeling | Zelfde rasterinteractie, andere inhoudsopslag | Raster delen, documenten en revisies apart houden |
| Cronvalidatie in browser, API, proxy en nodeagent | Verdediging op verschillende vertrouwensgrenzen | Alle validators behouden; gedeelde contractfixtures/protocoltests |
| Webservice, agentproxy en root-worker | Bewuste privilegescheiding | Niet samenvoegen om code te besparen |

## Voorgesteld model voor modules en widgets

Gebruik vijf kleine begrippen:

1. **Connector:** één dienstverbinding, server-side credentials/vaultreferentie, capabilities en herkomst van gegevens.
2. **Domeinmodel:** bijvoorbeeld `ClusterSummary`, `DownloadQueue`, `MediaRequest`, `Offer`, `CalendarEvent` of `WorkspaceSession`. Geen dashboardcoördinaten of credentials.
3. **Widgetdefinitie:** type, titel, vereiste rechten, instellingenvalidator, standaardformaat en weergave.
4. **Widgetinstantie:** een verwijzing naar widgettype en bron, plus persoonlijke instellingen. De pagina bezit de plaatsing.
5. **Pagina:** stelt widgets samen en voegt waar nodig beheerhandelingen toe. Een dashboard is één van die pagina's.

```mermaid
flowchart LR
    V[Infisical en persoonlijke koppelingen] --> C[Connector per dienst]
    C --> M[Gevalideerd domeinmodel]
    M --> A[Geautoriseerde API]
    A --> R[Gedeelde browserbron]
    R --> W[Widgetweergaven en selectors]
    W --> D[Persoonlijk dashboard]
    W --> P[Dienstpagina]
```

De backend blijft op elke aanvraag modulerechten, bron-ACL en waar nodig eigenaarschap controleren. De frontendbronlaag is alleen voor hergebruik en responsiviteit. Pagina's mogen naast widgets ook gespecialiseerde functies bevatten, zoals Files-upload, een terminal of cronbeheer.

De bestaande `frontend/modules/` is een goed vertrekpunt. Voeg daar geleidelijk domeinspecifieke hooks/modellen aan toe en verplaats gedeelde infrastructuur naar kleine `lib`-/`core`-bouwstenen. Verplaats geen bestanden alleen om een ideaal mappenplan te bereiken; verplaats ze wanneer verantwoordelijkheden daadwerkelijk worden losgemaakt.

## Ontbrekende functionaliteit (gap-analyse, 18 oktober 2026)

Vergeleken met het [functioneel ontwerp](functioneel-ontwerp.md) (F-01 t/m F-19, statusmodel, fasering), het menu in `config/controldeck.json` en de afspraken in deze periode. Prioriteit: **H** = zichtbaar gat of eis uit een afgeronde fase, **M** = volgende verdieping, **L** = wens.

### Menu-items zonder pagina

Deze routes staan in het menu maar vallen in `page.tsx` terug op "Dit onderdeel is nog niet ingericht":

| Route | Prio | Wat ontbreekt | Voorstel |
| --- | --- | --- | --- |
| `proxmox/containers` | H | Dubbel: `proxmox/vms` toont al VM's én containers | Menu-item laten wijzen naar `proxmox/vms` met filter *containers*, of verwijderen |
| `monitoring` | H | Hele module (F-07) | Overzicht met ProxMenux-gezondheid, Beszel, Uptime-status en Home Assistant-meldingen; bron + actualiteit per regel (F-14) |
| `radarr`, `plex` | M | Media-submenu's (eis 2026-10-17: Downloads, Requests, Movies, Series, Audio, Plex, Jellyfin) | Per submenu een pagina die dezelfde servicewidgets toont, gefilterd per familie |
| `admin` (Instellingen) | M | Eigen instellingenpagina; nu placeholder | Site-instellingen (titel, verversing, ondertitel) via de UI i.p.v. config-bestand |

### Eisen uit het functioneel ontwerp

| Eis | Stand | Prio | Wat ontbreekt |
| --- | --- | --- | --- |
| F-12 Favorieten | Niet gebouwd | M | Geen "favoriet"-markering; dashboards dekken het deels. Ster op Bookmarks/apps + favorietenwidget |
| F-14 Bron + laatste update | Deels | M | Servicewidgets, Proxmox en ProxMenux tonen tijd; Bookmarks-integraties, Files en Virtual Apps niet. Statusmodel (gezondheid × actualiteit × verbinding) nergens consequent; zie F4 `WidgetFrame`/`StatusBadge` |
| F-16 Bevestiging bij destructieve acties | Grotendeels | L | Aanwezig (Files verwijderen, Kasm stoppen, dashboards); VM-wekken vraagt geen bevestiging (bewust: alleen starten) |
| **F-17 Herleidbare beheeracties** | **Ontbreekt** | **H** | Alleen Cronjobs geeft `actor` door aan de agent. Geen centraal auditlog voor: accounts, module-installaties, Proxmox-koppeling, VM starten, Kasm-sessies stoppen, Files verwijderen/verplaatsen, Bookmarks-beheer, pagina-indelingen. Voorstel: `backend/core/audit.py` met `audit(action, target, result)` → SQLite-tabel + Admin-pagina "Activiteit" (alleen-lezen, filter, export) |
| F-19 Mobiel | Deels | M | 16 mediaqueries in `style.css`, maar `virtual-apps.css` heeft er geen; dashboard-bewerken en `EditableGrid` op touch niet op echte apparaten getest |
| Fase 3 — Bediening | Deels | M | Cronjobs ja; Proxmox-acties (VM/container starten, stoppen, herstarten) alleen "wekken" voor Kasm-VM's. Algemene start/stop op de inventarispagina met bevestiging, rechten (VM.PowerMgmt per pool) en auditlog |

### Functionele gaten per module

| Module | Prio | Ontbreekt |
| --- | --- | --- |
| **Zoeken** | H | Zoekt in modules, dashboards en Homepage-apps (`backend/search.py`), niet in Linkwarden-bookmarks, Virtual Apps-workspaces, Proxmox-gasten of Files. Eén `search_provider` per module (sluit aan op F6 `defineFeature`) |
| **Virtual Apps** | M | Startrecht in Proxmox (pool `kasm`) en DC01-afhankelijkheid nog niet ingericht; geen automatisch uitzetten van ongebruikte VM's; geen limietmelding vóór de Kasm-grens (5 sessies, Community); geen dashboardmodule "Mijn apps" |
| **Files** | M | Delen (links), zoeken, voorbeeld (afbeelding/PDF), versies, prullenbak terugzetten, downloads via nginx (`X-Accel-Redirect`) voor grote bestanden; geen dashboardwidget "Recente bestanden" |
| **Media** | M | Submenu's (zie boven); pagina-indeling `media` voorbereid maar niet gebruikt (A8); geen Jellyfin-servicewidget (bestaat alleen in het oude Homepage-integratiepad) |
| **Proxmox** | M | Containers-route (boven); acties (fase 3); backups/PBS-status; meldingen bij offline nodes |
| **Monitoring / meldingen** | H | Geen meldingen buiten de UI (e-mail, ntfy, Telegram, push) bij storingen: offline node, mislukte cronjob, volle opslag, verlopen koppeling, verlopen RDS-licentie of Kasm-grens |
| **Bookmarks** | L | Verplaatsen van Linkwarden-bookmarks in de persoonlijke indeling (alleen Homepage-links); favorieten (F-12) |
| **Beheer** | M | Providers-pagina is een statische lijst (geen beheer); geen UI voor site-instellingen; geen overzicht van gekoppelde integraties met hun gezondheid ("Verbindingen": Proxmox, ProxMenux, Linkwarden, Kasm, Nextcloud, vault) |
| **Gebruikers/accounts** | L | Geen zelfservice-overzicht "Mijn koppelingen" (Linkwarden-token, Files/Nextcloud, Kasm) op één plek |
| **Taal (i18n)** | L | `lib/i18n.ts` heeft 17 sleutels; de meeste pagina's hebben vaste Nederlandse teksten, terwijl de taalvoorkeur *en* bestaat |

### Beheer en betrouwbaarheid

| Onderwerp | Prio | Ontbreekt |
| --- | --- | --- |
| Backup van ControlDeck-data | H | `OPERATIONS.md` beschrijft een handmatige backup van `users.sqlite3`, `session.key` en private bestanden; geen geplande backup en geen hersteltest. Voorstel: dagelijkse SQLite-backup-API-kopie + private bestanden naar PBS of Nextcloud, met een maandelijkse hersteltest |
| Configuratie buiten de release | M | Nginx, systemd-drop-in en private menu worden niet door een release bijgewerkt (zie de releasebeperkingen in `OPERATIONS.md`); een migratiestap "config-upgrade" in de installer met diff, backup en `nginx -t` |
| Gezondheidspagina | M | `/health` en `/ready` bestaan; geen Admin-overzicht van vault, koppelingen, schijfruimte, versie, laatste deploy en certificaatgeldigheid (Kasm-pin, Proxmox-pin) |
| Testdekking | L | Geen tests voor `backend/app_icons.py` buiten de frontendtest; geen browser-/E2E-test (Playwright) voor slepen, uploaden en starten, die nu alleen handmatig zijn gecontroleerd |

### Aanbevolen volgorde voor nieuwe functionaliteit

1. **F-17 auditlog** (H) — wettelijke/beheerbasis voor alle bediening; klein te beginnen.
2. **Meldingen + Monitoring-pagina** (H) — maakt het statusmodel bruikbaar buiten de browser.
3. **Zoeken uitbreiden** (H) — veel winst voor dagelijks gebruik.
4. **Menu opschonen** (H) — containers-route, lege placeholders verbergen tot ze bestaan.
5. **Backup + hersteltest** (H).
6. Daarna fase 3 (Proxmox-acties), Media-submenu's, Files-verdieping en favorieten.

Nieuwe functies bouwen op de bouwstenen hieronder (B1–B8, F1–F6), zodat ze de bestaande dubbelingen niet vergroten.

### Eigen ideeën (voortgekomen uit het werk van oktober 2026)

Niet uit de eisen, maar uit wat er in de praktijk misging of met de hand moest:

| Idee | Waarom | Omvang |
| --- | --- | --- |
| **Zelfherstel van diensten** | Linkwarden lag op 15 oktober anderhalve dag plat na een OOM-kill, omdat de service geen `Restart=` had. Een "Diensten"-overzicht dat systemd-/Docker-status leest (via de bestaande node-agent), gestopte diensten meldt en met één klik (of automatisch, per dienst instelbaar) herstart. | M |
| **Updates-overzicht** | Open idee #1 (LXC-updates). Per LXC/VM: beschikbare pakketupdates, Docker-images met nieuwere versie (Kasm, Linkwarden, Termix), Proxmox-updates; bijwerken via de agent met bevestiging en auditlog. | M |
| **Bookmarks automatisch uit OPNsense** | De 66 Nginx-links zijn op 17 oktober met de hand overgezet. Een periodieke synchronisatie van OPNsense-Nginx-hosts en Dnsmasq-reserveringen naar een Bookmarks-groep "Infra (automatisch)", met de regel *vanburik.info gaat voor*. Ook dode links markeren (HTTP-check). | M |
| **DHCP-/DNS-overzicht** | Vandaag bleken IP-adressen, reserveringen en Kasm-serveradressen uit elkaar te lopen. Een alleen-lezen netwerkpagina: OPNsense-reserveringen naast Proxmox-VM-MAC's naast werkelijke ARP-adressen, met afwijkingen gemarkeerd (zoals WinServer op `192.168.1.101`). | M |
| **Energiebesparing** | VM's die alleen voor Kasm draaien automatisch uitzetten na X uur zonder sessie (het omgekeerde van wekken), met verbruik uit ProxMenux omgerekend naar kWh/€ per maand. | M |
| **Vervaldatums bewaken** | Certificaten (Kasm-pin, Proxmox-pin, Cloudflare), API-sleutels, de RDS-licentie-graceperiode en de Kasm-licentiegrens op één plek met waarschuwing vooraf. | S |
| **Mobiele app (PWA)** | ControlDeck installeerbaar op de telefoon, met pushmeldingen voor de meldingen uit de gap-analyse. Past bij de lichte architectuur (statische frontend + service worker). | M |
| **Snelle acties in de zoekbalk** | Ctrl K niet alleen om te zoeken maar ook om te doen: "start Windows Server", "open Word", "stop sessie", "herstart Linkwarden" — met dezelfde rechten en bevestiging als de knoppen. | S |
| **Wake-on-LAN voor fysieke pc's** | In de Bookmarks staan VeraPC, DevPC en rescuepc; een "wek"-knop (WoL via de agent) naast "open via Kasm/RDP" maakt ze bruikbaar vanaf de werkplek. | S |
| **"Mijn koppelingen"** | Linkwarden-token, Files/Nextcloud, Kasm en (later) andere persoonlijke koppelingen op één profielpagina, met status, laatste gebruik en intrekken. | S |
| **Gezins-/gastweergave** | Een rol met alleen Media en een paar Bookmarks, zonder Proxmox/Admin; de bestaande modulerechten en de bewerkmodus maken dit bijna gratis. | S |
| **Wijzigingsoverzicht na deploy** | Na een release een korte melding "nieuw in deze versie" uit `CHANGELOG.md`, en een waarschuwing als serverconfiguratie (nginx, drop-in, menu) achterloopt op de release. | S |

Omvang: **S** = enkele uren tot een dag, **M** = enkele dagen.

## Ontwerp: herbruikbare bouwstenen (klassen en functies)

Elke bevinding wordt één kleine, geteste bouwsteen. Modules stappen er één voor één op over; gedrag, foutteksten, rechten en opgeslagen gegevens blijven gelijk, tenzij hieronder anders staat. Gedeelde backendcode komt in `backend/core/`, gedeelde frontendcode in `frontend/lib/core/` (logica) en `frontend/components/core/` (weergave). Geen nieuwe dependencies; geen dynamisch laden van code.

### Overzicht

| # | Bouwsteen | Plaats | Lost op |
| --- | --- | --- | --- |
| B1 | `UpstreamError` | `backend/core/errors.py` | 502-bug, A3 (foutklassen) |
| B2 | `PermissionContext`, `require_module`, `require_manager` | `backend/core/access.py` | 10, A3 |
| B3 | `PrivateFile` | `backend/core/storage.py` | 9 |
| B4 | `PersonalSecretStore` | `backend/core/secrets.py` | A2 |
| B5 | `ProxmoxConnection` | `backend/proxmox.py` | A1 |
| B6 | `TtlCache` | `backend/core/cache.py` | 11, 2 |
| B7 | `HttpClient` | `backend/core/http.py` | 13 |
| B8 | `ConfigRepository` | `backend/core/config_repo.py` | 2 |
| F1 | `requestJson`, `ApiError` | `frontend/lib/core/request.ts` | 5 |
| F2 | `usePolledResource` | `frontend/lib/core/polling.ts` | 1 |
| F3 | `useInventory` | `frontend/lib/core/inventory.ts` | A6 |
| F4 | `StatusBadge`, `Meter`, `AsyncState`, `WidgetFrame` | `frontend/components/core/` | 14, A5 |
| F5 | `formatBytes`, `safeUrl`-familie | `frontend/lib/core/format.ts`, `urls.ts` | A7, 13 |
| F6 | `defineFeature` (frontendregister) | `frontend/modules/registry.ts` | 6, 7 |
| T1 | `conftest.py`-fixtures, `mockFetch` | `tests/conftest.py`, `frontend/tests/helpers.mjs` | A4 |

### Backend

**B1 — `UpstreamError`** (`backend/core/errors.py`)

```python
class UpstreamError(Exception):
    status = 424          # nooit 502: Cloudflare vervangt dat door een eigen pagina
    def __init__(self, message: str, *, code: str = "upstream", relink: bool = False): ...
    def payload(self) -> dict: ...   # {"error": message, "code": code, "relink": relink}

class NotConfigured(UpstreamError): status = 503
class NotLinked(UpstreamError): status = 403

def register_error_handlers(app): ...   # één @app.errorhandler(UpstreamError) voor alle modules
```

Vervangt `FilesError`/`RelinkError`/`ConflictError` (`files.py`), `KasmError`/`NotLinked`/`NotConfigured` (`virtual_apps.py`), `LinkwardenError`, en de vrije `jsonify(...), 502` in `proxmox.py`, `homepage_integrations.py` en `cronjob_api.py`. Bestaande subklassen blijven bestaan als dunne afleidingen, zodat imports en meldingen gelijk blijven. *Tests:* per voormalige 502-route een regressietest dat status < 500 is en de melding behouden blijft; `relink`/`code` in de JSON; handler geregistreerd vóór module-handlers.

**B2 — Toegang** (`backend/core/access.py`)

```python
class PermissionContext:
    """Eén keer per request opgebouwd uit filter_configuration(load_config(...), g.account)."""
    modules: frozenset[str]
    def has(self, module_id: str) -> bool: ...
    def is_manager(self) -> bool: ...

def permissions() -> PermissionContext: ...            # lui gecachet in flask.g
def require_module(module_id: str, *, manager_for_writes=False): ...   # decorator voor route of Blueprint
def require_manager(): ...
```

Modules worden Flask-**Blueprints** (`Blueprint("files", __name__, url_prefix="/api/files")` met `@bp.before_request` → `require_module("files")`). Vervangt de 11 eigen `before_request`-hooks en 16 losse `filter_configuration`-zoekacties. *Bewaken:* de sessie-/CSRF-hook in `auth.py` blijft als eerste draaien; `/api/widget-ingest` blijft machine-auth; bron-ACL (widgets) en eigenaarschap (dashboards) blijven extra controles. *Tests:* zonder sessie 401, zonder module 403, gebruiker vs. beheerder bij schrijfacties, en dat `load_config` maar één keer per request wordt gelezen.

**B3 — `PrivateFile`** (`backend/core/storage.py`)

```python
class PrivateFile:
    def __init__(self, path: Path): ...
    def read_json(self, default=None): ...
    def write_json(self, value) -> None: ...   # tijdelijk bestand + fsync + os.replace, map 0700, bestand 0600
    def delete(self) -> None: ...
```

Vervangt `save_private` (nu in `linkwarden.py`, gebruikt door `homepage.py` en `files.py`) en de losse `json.loads(path.read_text())`-blokken. `save_private` blijft als alias bestaan tot alle aanroepers zijn omgezet. *Tests:* atomair (geen half bestand bij fout), rechten 0600/0700, kapotte JSON → `default`.

**B4 — `PersonalSecretStore`** (`backend/core/secrets.py`)

```python
class PersonalSecretStore:
    def __init__(self, data_dir: Path, module: str): ...      # <data-dir>/<module>/users/<hash>.json
    def get(self, subject: str, server: str) -> dict | None: ...
    def put(self, subject: str, server: str, value: dict) -> None: ...
    def delete(self, subject: str, server: str) -> None: ...
    def migrate_from_email(self, email: str, subject: str, server: str) -> bool: ...
```

Sleutel = SHA-256 van *server + stabiel login-subject* (zoals Files nu). Vervangt de eigen opslag in `files.py` en `linkwarden.py`. **Migratie Linkwarden:** bij eerste gebruik na de omschakeling wordt het oude bestand (sleutel op e-mail) eenmalig verplaatst naar de nieuwe sleutel; het oude bestand blijft bewaard tot een volgende release. *Tests:* andere server krijgt nooit het oude geheim; gebruiker A ziet nooit B; migratie eenmalig en idempotent; e-mailwijziging breekt de koppeling niet meer.

**B5 — `ProxmoxConnection`** (in `backend/proxmox.py`)

```python
class ProxmoxConnection:
    def __init__(self, data_dir: Path): ...
    def load(self) -> dict | None: ...
    def client(self) -> Client: ...          # gooit UpstreamError/NotConfigured als niet gekoppeld
    def public(self) -> dict: ...            # zonder secret, zoals nu de GET-route
```

Vervangt het rechtstreeks lezen van `proxmox/connection.json` in `cronjobs.py`, `cronjob_api.py`, `linkwarden.py`, `proxmenux.py` en `vm_power.py`. Opslag, pinning en de scheiding alleen-lezen/startrecht blijven gelijk. *Tests:* niet gekoppeld, kapot bestand, pinning-mismatch, en dat geen enkele module het secret in een antwoord zet.

**B6 — `TtlCache`** (`backend/core/cache.py`)

```python
class TtlCache:
    def __init__(self, ttl: float, *, max_entries: int = 64, clock=time.monotonic): ...
    def get_or_fetch(self, key, fetch: Callable[[], T]) -> tuple[T, float]: ...  # (waarde, ouderdom)
    def invalidate(self, key=None) -> None: ...
```

Eén lopende fetch per sleutel (andere aanvragers wachten op hetzelfde resultaat), lock alleen rond de administratie (een trage bron blokkeert geen andere sleutel), begrensde opslag. Vervangt de caches in `service_widgets.py`, `virtual_apps.py` (workspaces), `vm_power.py` (status, koppeling) en de eenvoudige delen van `proxmox.py`. De achtergrond- en deelresultaten van ProxMenux blijven eigen code. *Tests:* gelijktijdige misses = één fetch; trage sleutel blokkeert andere niet; credentialrotatie zit in de sleutel; monotone klok.

**B7 — `HttpClient`** (`backend/core/http.py`)

```python
class HttpClient:
    def __init__(self, base_url: str, *, verify=True, pin: str | None = None, timeout=(5, 30), max_bytes=2 * 1024 * 1024): ...
    def json(self, method: str, path: str, **kwargs) -> dict | list: ...
    def raw(self, method: str, path: str, *, stream=False, **kwargs) -> requests.Response: ...
```

Nooit redirects volgen, begrensde body, één foutvertaling naar `UpstreamError` zonder upstream-body of geheimen. Gebruik door `linkwarden.upstream`, `homepage_integrations.call`, `files.call`, `modules/kasm.kasm_post` en `widgets/transport.Transport` (die laatste houdt zijn afbeeldingscontrole). De URL-validators blijven per contract bestaan (publiek HTTPS, intern HTTP, pinning, cluster-CA). *Tests:* redirect geweigerd, te grote body, time-out, pinning, geen secret in foutmelding.

**B8 — `ConfigRepository`** (`backend/core/config_repo.py`)

```python
class ConfigRepository:
    def __init__(self, vault, *, ttl: float = 30): ...
    def get(self, name: str, validate: Callable[[Any], T]) -> T: ...   # gevalideerd, gecachet per naam+inhoudshash
    def invalidate(self) -> None: ...
```

Eén vaultlezing per korte periode voor `CONTROLDECK_WIDGET_SOURCES` en `CONTROLDECK_APP_LAUNCHES` (nu bij vrijwel elke aanvraag twee CLI-aanroepen). *Bewaken:* korte TTL en invalidatie bij een fout; rechten worden nooit gecachet, alleen de inrichting. *Tests:* tellen van CLI-aanroepen, kapotte JSON, vault onbereikbaar, wijziging zichtbaar na TTL.

### Frontend

**F1 — `requestJson` en `ApiError`** (`frontend/lib/core/request.ts`)

```ts
export class ApiError extends Error { status: number; code?: string; relink?: boolean; notLinked?: boolean; notConfigured?: boolean }
export async function requestJson<T>(url: string, options?: {
  method?: "GET" | "POST" | "PUT" | "DELETE"; csrf?: string; body?: unknown | Blob;
  signal?: AbortSignal; timeoutMs?: number; validate?: (value: unknown) => T;
}): Promise<T>;
```

CSRF bij elke niet-GET, `cache: "no-store"`, JSON of Blob, time-out, statuscode in de melding als de server geen JSON gaf (zoals nu in Files). Elke module houdt een dunne wrapper die alleen haar eigen routes accepteert (`filesRequest`, `virtualAppsRequest`, `dashboardRequest`, …). *Uitzonderingen:* Files-downloads (gewone link) en chunk-uploads met herhaalpogingen. *Tests:* JSON-fout, HTML-foutpagina (status in melding), netwerkfout, time-out, CSRF-header, geen body bij GET.

**F2 — `usePolledResource`** (`frontend/lib/core/polling.ts`)

```ts
export function usePolledResource<T>(key: string | null, fetcher: (signal: AbortSignal) => Promise<T>, options?: {
  intervalSeconds?: number; fastWhile?: (data: T) => boolean; fastSeconds?: number;
}): {data: T | null; error: ApiError | null; stale: boolean; loading: boolean; refresh: () => void};
```

Eén lopende aanvraag per `key` gedeeld tussen componenten (zelfde `key` = zelfde data), annulering bij unmount, laatste abonnee ruimt de timer op, 401/403 wist gedeelde data, een tijdelijke fout houdt oude data met `stale: true`. Vervangt de 11 `setInterval`-lussen. *Tests:* twee abonnees één fetch, bronwissel met laat antwoord, afmelden/403 wist, time-out, laatste abonnee weg.

**F3 — `useInventory`** (`frontend/lib/core/inventory.ts`)

```ts
export function useInventory<I, M>(endpoint: string, monitorEndpoint: string | null,
  validate: (value: unknown) => I, validateMonitor?: (value: unknown) => M[], refreshSeconds?: number
): {data: I | null; monitor: M[]; error: string; pending: boolean};
```

Gebouwd op F2; vat het gedeelde patroon van `proxmox-guests`, `-network` en `-storage` samen (Proxmox-inventaris + ProxMenux-monitor, 409 → "eerst koppelen", sneller verversen zolang de monitor laadt). De drie componenten houden alleen hun weergave.

**F4 — Weergavebouwstenen** (`frontend/components/core/`)

```tsx
<StatusBadge state="online" | "booting" | "offline" | "unknown" | "ok" | "warning" | "error" label?/>
<Meter value={73.4} label="CPU" detail="8 cores"/>        // drempels uit één plek
<AsyncState loading error empty onRetry>{children}</AsyncState>
<WidgetFrame title href? updatedAt? stale?>{children}</WidgetFrame>
```

Met CSS-tokens in `style.css`: `--ok`, `--warn`, `--error`, `--info` (+ donkere varianten), in plaats van de hard gecodeerde kleuren (A5). Vervangt de eigen badges in Virtual Apps, ProxMenux-gezondheid, Proxmox-inventaris, servicewidgets en de meters in `proxmox-summary.tsx`/`system/cards.tsx`. Geen allesomvattende kaart: poster, appicoon en meting blijven eigen componenten.

**F5 — Kleine hulpfuncties** (`frontend/lib/core/format.ts`, `urls.ts`)

```ts
export function formatBytes(bytes: number | null, locale = "nl-NL"): string;
export function safeHttpsUrl(value: unknown, {sameOrigin?}?): string;      // basis voor safeImage, connectLink
export function stripsSecrets(url: URL): boolean;                           // één lijst geheime query-sleutels
```

Vervangt `formatSize` (`files.ts`) en `bytes` (`proxmox.ts`); de URL-controles in `service-widgets.ts` en `virtual-apps.ts` gebruiken één basis. De lijst geheime sleutels komt uit één JSON-fixture die ook de Python-test (`presentation.PRIVATE_KEYS`) leest.

**F6 — `defineFeature`** (`frontend/modules/registry.ts`)

```ts
export function defineFeature<S>(feature: {
  id: string; route?: string; title: string; permission: string;
  Page?: React.ComponentType<PageProps>;
  widgets?: WidgetDefinition<S>[];          // met eigen instellingstype en validator (getagde union)
}): Feature;
```

`page.tsx` kiest de pagina via het register in plaats van 16 voorwaardelijke takken; dashboardcatalogus en modulekeuze lezen hetzelfde register. Een contracttest vergelijkt de ID's met `backend/dashboard_modules.py` en `config/modules`.

### Tests

**T1 — gedeelde fixtures**

```python
# tests/conftest.py
@pytest.fixture
def app_factory(tmp_path, monkeypatch): ...          # create_app met tijdelijke data-dir en accounts
@pytest.fixture
def login(): ...                                     # login(client, email) → sessie + CSRF "csrf"
@pytest.fixture
def fake_vault(): ...                                # fake_vault(app, {"CONTROLDECK_…": json})
```

```js
// frontend/tests/helpers.mjs
export function mockFetch(routes) { … }               // {url: response|fn}, herstelt globalThis.fetch na de test
```

Bestaande tests blijven ongewijzigd slagen; nieuwe tests gebruiken eerst de fixtures, oude worden alleen omgezet als ze toch worden aangeraakt.

### Werkwijze per bouwsteen

1. Bouwsteen maken met eigen tests (normaal, rand, faal, plus auth waar relevant).
2. Eén module omzetten; alle bestaande tests moeten ongewijzigd slagen.
3. Overige modules één voor één omzetten; oude code verwijderen zodra niets er meer naar verwijst.
4. Per stap de documentatie bijwerken en pushen, zodat elke stap los terug te draaien is.

## Uitvoering in zes reviewbare wijzigingen

| Ronde | Afgebakende wijziging | Gereed wanneer |
| --- | --- | --- |
| 1 | `requestJson`, `ApiError` en één gedeelde Cronjobs-wrapper | Bestaande meldingen/CSRF/routes behouden; JSON-, netwerk- en afwijzingstests slagen |
| 2 | Gedeelde Proxmox-/ProxMenux-bron en selectors voor systeemmeters | Geen dubbele fetch per endpoint/ronde; annulering, bronwissel, afmelden en 403 wissen correct |
| 3 | Gedeelde Kasm-client en configuratievalidator | Portaal, lijst, start en stop blijven werken; vreemde sessies en ongeldige redirects worden geweigerd |
| 4 | Onafhankelijke widgetinstellingstypes en frontendregister; paginahouder vereenvoudigen | Nieuwe widget krijgt één frontenddefinitie; cataloguscontract en bestaande dashboarddocumenten blijven geldig |
| 5 | Dashboard op `EditableGrid`; kleine opslag-/rechtenbouwstenen | Touch/toetsenbord, groepsverplaatsing, grenzen, revisieconflicten, persoonlijke layouts en herstel getest |
| 6 | Connectorconsolidatie van Homepage-integraties/servicewidgets en vaultoptimalisatie | Expliciet migratieplan met backup, stabiele link-ID's, Jellyfin-behoud, bronrechten en credentialrotatie bewezen |

Gemeenschappelijke UI-elementen en lokale-linkprojectie kunnen per aangeraakte functie meelopen; geen grote cosmetische verbouwing vooraf. Iedere ronde moet zelfstandig terug te draaien zijn. Metingen van aanvraag-/CLI-aantallen bepalen of verdere cacheoptimalisatie zinvol is.

## Test- en migratieregels

- Iedere gewijzigde functie krijgt normaal-, grens- en afwijzingsgevallen; daarnaast expliciete sessie-, CSRF-, bron- en eigenaarschapstests.
- Gedeelde transporttests dekken JSON-fouten, veilige foutmeldingen, timeouts en annulering. Files-streams en mutaties houden eigen tests voor grootte, lengte en herhaalbaarheid.
- Gedeelde bron- en cachetests moeten gelijktijdigheid, verouderde antwoorden, laatste abonnee weg, credentialrotatie, logout en ingetrokken toegang aantonen.
- Wijzig bestaande dashboard-/link-/account-ID's niet bij een technische opsplitsing. Een schemawijziging krijgt backup-, bestaande-data-, herstart- en hersteltests.
- Houd de agent en proxy zelfstandig deploybaar en versieer hun protocol. Een gedeelde frontendhelper vervangt nooit de validatie op een node.
- Voer Python-tests, frontendtests, TypeScript-controle en frontendbuild uit vóór iedere push. CI blijft publicatie/deployment blokkeren bij fouten.

## Verificatie van de onderzochte basis

De bestaande controles zijn opnieuw uitgevoerd tijdens dit onderzoek:

| Controle | Resultaat |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q` | 718 geslaagd, 8 overgeslagen |
| `npm test` in `frontend/` | 227 geslaagd |
| `npm run typecheck` | Geslaagd |
| `npm run build` | Geslaagd; statische export |
| `git diff --check` | Geen whitespacefouten in de bestaande getrackte diff |

Dit bewijst de huidige regressiebasis, niet dat de voorgestelde refactors al zijn gebouwd of dat alle externe diensten opnieuw live zijn getest. Er zijn alleen dit onderzoeksdocument en de verwijzing in de documentatie-index toegevoegd.
