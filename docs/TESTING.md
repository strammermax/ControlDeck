# Testbeleid

Iedere pull request, main-push en versie-tag voert de Python-tests, frontend-unit-tests, TypeScript-controle en productiebuild uit. Vervolgens volgen shellcontrole, bundeling, Docker-start en readiness/commitverificatie. Publicatie en LXC-deployment hebben succesvolle verificatie als verplichte afhankelijkheid. Na uitrol moet de actieve commit overeenkomen met de bedoelde commit; de deployhelper herstelt de vorige release bij een mislukte start.

## Uitvoeren

```bash
python -m pytest -q
cd frontend
npm test
npm run typecheck
npm run build
```

Python-tests dekken runtime/readiness, configuratiebestanden en includes, provideractivering, uitschakelen, URL- en referentievalidatie, geheimenprojectie, loginblokkade, profielbeheer, rollen, CSRF, de laatste admin, accountrevocatie en voorkeurisolatie. OIDC-tests genereren RSA-ondertekende testtokens en gebruiken de werkelijke Authlib-tokenvalidator: handtekening, state, nonce, audience, issuer, expiry, geverifieerde e-mail en accounttoelating. Alleen netwerktransport en Google-discovery/JWKS zijn vervangen door lokale fixtures. Deze tests gebruiken geen echte accounts of clientgeheimen.

Frontend-unit-tests draaien met de ingebouwde Node-testfunctie en controleren configureerbare routes, dropdownselectie, modulepagina's en externe links. Iedere nieuwe module moet tests voor zijn echte gedrag en foutgevallen toevoegen. Autorisatie bij nieuwe endpoints wordt zowel voor admin, user als anonieme bezoekers getest. Voeg waar nodig tests toe voor gedeeltelijke uitval en ongeldige providerdata; test niet uitsluitend de succesroute.

Unit-tests bewijzen geen succesvolle Google Cloud-configuratie of beschikbaarheid van externe toepassingen. Daarom blijven echte Google-login en browsercontroles van formulieren, navigatie en voorkeurherstel aanvullende verificaties. Bij deze release zijn lokale admin/user-testaccounts gebruikt voor de browsercontrole; een echte Google-login wordt apart bevestigd. Een CI-build krijgt nooit een onbeveiligde loginbypass.

## Regressietests: elke bug krijgt een test

Iedere bug die we zien, in productie, in CI of tijdens het bouwen, krijgt bij de oplossing een **regressietest**:

1. **Eerst reproduceren:** schrijf de test zó dat hij **faalt zonder de oplossing**. Een test die ook zonder fix slaagt, bewijst niets.
2. **Dan oplossen:** de test slaagt met de oplossing.
3. **Benoemen:** zet in de docstring of het commentaar het symptoom en de oorzaak, zodat later duidelijk is waarom de test bestaat. Bijvoorbeeld: *"Python 3.13 (urllib3 VERIFY_X509_STRICT) weigerde de Proxmox-cluster-CA zonder keyUsage."*
4. **Echt gedrag:** test op het niveau waar de bug zat. Een TLS-fout test je met een echte TLS-verbinding, een time-out met een trage bron, een API-fout via de endpoint, niet alleen via een mock van de functie die je net hebt aangepast.
5. **Samen committen:** fix en test zitten in dezelfde commit. Vermeld de bug in de commitboodschap.

Een fout die CI vindt (tests, TypeScript-controle, build, shellcheck) is ook een bug: los hem op en draai daarna alle controles lokaal (`python -m pytest -q`, `npm test`, `npm run typecheck`, `npm run build`) vóór de volgende push. Typecontrolefouten worden gedekt door `npm run typecheck`; daarvoor is geen aparte unit-test nodig.

Voorbeelden uit dit project:

| Bug | Regressietest |
| --- | --- |
| ProxMenux: geldige node-certificaten geweigerd op Python 3.13 (strenge X.509-controle, cluster-CA zonder keyUsage) | `tests/test_proxmenux.py::test_cluster_ca_tls_against_real_server` (echte HTTPS-server) |
| ProxMenux: node "niet bereikbaar" doordat de gezondheidscontrole langer duurt dan de time-out | `test_slow_part_keeps_other_data` |
| ProxMenux: slapende schijf als "Onbekend · 0 °C" | `test_summary_details[boundary]`, `diskStatus` in `frontend/tests/proxmox.test.mjs` |
| ProxMenux: intern veld `latest` (`50:26:apparmor,…`) als versie getoond | `test_summary_details[normaal]` en `[faal]` |
| Detectie: niet-JSON-antwoord via https viel terug op http | `test_detect_states[faal]` |
| Installatie-API: ontbrekende worker gaf "verouderd" (409) in plaats van "niet beschikbaar" (503) | `test_queue_installation[faal]` |
| Proxmox-client: query-parameter `path=` botste met de argumentnaam | `test_connect_flow` (gebruikt `/access/permissions?path=/`) |
| Cron-bibliotheek: zoekgrens van één jaar gaf een schema op 29 februari geen volgende uitvoering | `frontend/tests/cron.test.mjs` (nextRuns boundary, verwacht 2028-02-29) |
| Cronjobs: verwijdercommando met `sed -i` zou de symlink `/root/.ssh/authorized_keys` → clusterbestand vervangen | `tests/test_cronjobs.py::test_removal_command_keeps_the_cluster_authorized_keys_symlink` |
| Agent-proxy: `serve()` zette de umask van het hele proces, waardoor in CI 217 andere tests faalden met "Permission denied" | `tests/test_agent_proxy.py::test_socket_server_and_client` |

## Normaal, boundary, faal

Elke functie krijgt minimaal drie herkenbare testcategorieën: `normaal` voor verwacht gebruik, `boundary` voor grenswaarden/randgevallen en `faal` voor afwijzing of uitval. Drie categorieën is het minimum, niet het maximum: login en rechten hebben extra beveiligingsgevallen. Nieuwe functies zijn pas klaar wanneer hun drietal in CI slaagt.

| Functie | Normaal | Boundary | Faal |
| --- | --- | --- | --- |
| Site-instellingen | Standaard interval | 5 en 3600 seconden | Waarde buiten grens/typefout |
| Provider | Geldig adres, ingeschakeld | Nog niet ingesteld, uit | Aan zonder adres |
| Module/subpagina | Geldige pagina | Module uit, routes verdwijnen | Dubbele pagina |
| Menu | Labelwijziging | Dropdown met alleen verborgen items | Onbekende route |
| Widgetdefinitie | Geldige koppeling | Uitgeschakelde widget | Onbekende bestemming |
| Configuratiebestand | Geldig JSON | Precies 256 KiB totaal | Eén byte te groot |
| Accountprofiel | Geldige velden/defaults | Namen 100 tekens, enabled=false | Naam 101 tekens |
| Gebruiker aanmaken | Admin maakt user | Maximale namen, e-mailnormalisatie | Ongeldige rol |
| Gebruiker wijzigen | Naam aanpassen | Enige admin blijft admin | Laatste admin degraderen |
| Sessie | Toegestaan actief account | Account wordt uitgeschakeld | Gemanipuleerde cookie |
| Voorkeuren | Thema opslaan/herladen | Paginaroute 130 tekens | Paginaroute 131 tekens |
| Modulerechten | Toegestane module | Geen modules toegewezen | User vraagt admingegevens |
| Google-login starten | Correct vast callbackadres | Client nog niet ingesteld | Provideruitval |
| Google-callback | Ondertekend toegestaan token | Exacte kloktolerantiegrens | Token buiten geldigheid |
| Uitloggen | Geldige sessie en CSRF | Tweede logout, al uitgelogd | Ongeldig CSRF-token |
| Readiness | Geldige frontend/config | Leeg indexbestand | Kapotte JSON |
| Statische bestanden | Startpagina | Gecodeerde spaties in assetnaam | Padtraversal |
| Health | Proces meldt ok | Uptime nul na start | Niet toegestane HTTP-methode |
| Frontendpagina's | Modules en subpagina's | Geen toegestane modules | Ongeldige module-invoer |
| Standaardroute | Eerste lokale route | Leeg menu | Item zonder bestemming |
| Dropdownselectie | Actieve subroute | Lege dropdown | Niet overeenkomende route |
| Menulink | Geldige route | Subpagina/externe URL | Ontbrekende bestemming |

Browserinteractie vult deze unit/contract-tests aan; hiervoor worden geen productielogin-bypasses toegevoegd.

## Termix

De optionele Terminal-integratie gebruikt een afzonderlijke Docker-container, de bestaande Google-login en een beveiligde Nginx-gateway. Zie [Termix-installatie en beheer](TERMIX.md).

De admin-installatiewizard biedt Docker en Proxmox LXC als keuzes, met voorafgaande controle en voortgang. Zie [module-installatiewizard](MODULE-WIZARD.md). Docker is aangesloten; de Proxmox-uitvoering vereist nog de hostverbinding en Helper-Script-adapter.

## Homepage-apps en integraties

De volledige gebruikersflow en technische afspraken staan in [HOMEPAGE-INTEGRATIONS.md](HOMEPAGE-INTEGRATIONS.md). Extra frontendtests controleren de exacte Jellyfin-instellingenlink, subpaden, onveilige adressen, complete/onvolledige credentials en het voorkomen van een dubbele tegel. Backendtests controleren bestaande link-IDs, dubbele koppelingen, behoud van de link na verwijderen en veilige deep links.

Browserregressie **gewone link direct zichtbaar na integratieformulier**: open Integratie toevoegen, kies Jellyfin, vul alleen naam en URL in, klik Verbinding testen en aanmaken en vervolgens Nee, alleen link opslaan. De nieuwe link moet zonder pagina-herladen zichtbaar zijn; er mag geen API-koppeling verschijnen. De oorzaak van de eerdere fout was dat het losse integratieformulier de Homepage-lijst niet opnieuw ophaalde. Controleer daarnaast Ja (formulier blijft ingevuld) en een volledige synthetische API-koppeling aan een bestaande link (aantallen verschijnen op dezelfde tegel).

`tests/test_homepage_integrations.py` toetst de Seerr/Jellyfin-adapters, normale/grens/foutgevallen, versleuteling, herstart, toegang, CSRF, gelijktijdige updates en de 50-koppelingenlimiet. `frontend/tests/homepage-apps.test.mjs` en `homepage-integrations.test.mjs` toetsen cataloguskeuze, tegelprojectie en API-aanroepen. Benoemde regressies bewaken Flask-endpointnamen, veilige icoonnamen en appnamen die niet door authenticatieheaders mogen worden vervangen. Browsercontrole: Link toevoegen → zoek Jellyfin → naam/icoon ingevuld → API-koppeling → gebruikersnaam/wachtwoord → geslaagde test → tegel met aantallen. Gebruik daarvoor synthetische API-antwoorden in een private lokale testomgeving; echte endpoints hebben eigen credentials nodig.
