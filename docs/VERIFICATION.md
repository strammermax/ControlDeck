# Verificatie van de infrastructuur

Datum: 5 oktober 2026. Onderstaande controles zijn per versie vastgelegd; oudere secties beschrijven de toenmalige grenzen.

## 14 oktober 2026 — Publicatie dashboarduitbreiding

Op verzoek van de gebruiker gepubliceerd via de bestaande main-workflow. Vooraf opnieuw geslaagd: 489 Python-tests (8 overgeslagen), 160 frontendtests, TypeScript en productiebuild. De volledige geselecteerde MVP is nog in uitvoering.

De latere alleen-lezen Proxmox-inventarisatie is met het bestaande viewertoken op alle drie de hosts gelukt: drie nodes, 15 virtuele machines en 45 containers. Dit corrigeert de eerdere controle met het verkeerde subnet. Inventaris en toegangsgegevens blijven buiten Git.

## 14 oktober 2026 — Appverwijzingen en zoeken, vervolg

- Python: 489 geslaagd, 8 overgeslagen. Frontend: 160 geslaagd. TypeScript, statische productiebuild en whitespacecontrole geslaagd.
- Nieuwe bron- en zoektests controleren naam/adreswijzigingen, verwijderen, bronuitval, opgeslagen samenvattingen zonder credentials, directe bronrechten, eigen dashboards en de afwezigheid van zoekresultaten uit andere accounts of verborgen modules.
- Persoonlijke zoekmachines zijn getest op aanmaken/wijzigen/verwijderen, herstart, eigenaarisolatie inclusief admins, CSRF, revisieconflicten, grenzen, onveilige URL's en injectie via zoektermen. Schema-upgrades behouden bestaande dashboards en maken een echte herstelkopie.
- Regressie voor hergebruik van verwijderde app-ID's is eerst falend en daarna geslaagd uitgevoerd. De blijvende nummerregistratie houdt rekening met actuele bronnen, opgeslagen verwijzingen, integraties en de vorige linkversie. HEAD op Homepage is met een eerst falende en daarna geslaagde regressie als alleen-lezen vastgelegd.
- Browsercontrole met synthetische private fixtures: bestaande Jellyfin-app kiezen, opgeslagen cijfers tonen, naamwijziging via de echte Bookmarks-bediening terugzien op het dashboard, zoeken met Ctrl+K, persoonlijk dashboard openen uit een zoekresultaat, SearXNG-sjabloon aanmaken en de correct gecodeerde externe link controleren. Er is niet daadwerkelijk naar de externe voorbeeldzoekmachine genavigeerd.
- De drie door Camiel bevestigde Proxmox-hosts leverden vanuit deze omgeving geen SSH-inventaris op en waren niet bereikbaar op API-poort 8006. Er is geen live dienstinventaris geclaimd en er zijn geen hosts geherconfigureerd.
- Dienstenlijst en SSO-keuze zijn verwerkt zonder aangeleverde wachtwoorden/API-sleutels op te slaan. Geen live vaultwijzigingen, push, nieuwe release of deployment voor dit vervolg.

## 14 oktober 2026 — Lokale dashboarduitbreiding

- Python: 449 geslaagd, 8 overgeslagen. Frontend: 142 geslaagd. TypeScript en statische productiebuild: geslaagd. De overgeslagen tests zijn geen live integratiebewijs.
- Nieuwe tests dekken dashboarddocumenten, rastergrenzen, transacties/revisieconflicten, persoonlijke toegang, modulerechten, CSRF, accountrevocatie, verwijderen tot een lege lijst en een echte leesherstelproef van de SQLite-migratiebackup.
- Benoemde regressietests zijn eerst falend en daarna geslaagd uitgevoerd voor de Windows-vaultinterpreter, het overschrijven van handmatig ingestelde nieuwe tegelposities en HEAD-verzoeken die onterecht als schrijfactie werden behandeld.
- Browsercontrole van de statische build via een tijdelijke loopbackservice met uitsluitend synthetische accounts/data: app-link toevoegen, handmatige kolomkeuze behouden, opslaan/herladen, rechterpaneel toevoegen, slepen, vergroten met toetsenbord én pointer, navigatie weigeren bij een onopgeslagen bewerking, dupliceren en standaarddashboard na herladen. Geen testloginroute toegevoegd aan de productieapplicatie.
- Camiels Infisical-clientbron en CLI-contract onderzocht; mapinstellingen en afgeschermde stdin-overdracht getest. Geen echte vaultgegevens uitgelezen of gewijzigd. Providergeheimen zijn nog niet volledig naar vaultreferenties gemigreerd.
- De herstelpunttag is naar GitHub gepusht en op commit geverifieerd. Deze nieuwe applicatiewijzigingen zijn lokaal; CI, Docker, LXC-deployment en echte Google/LDAP/externedienstverbindingen zijn voor deze uitbreiding niet uitgevoerd. Het volledige geselecteerde MVP is nog niet af.

## Uitgevoerde controles

- Lokale Python-tests voor health, readiness en verhinderen van padtraversal: geslaagd.
- TypeScriptcontrole en statische Next.js-export: geslaagd.
- GitHub Actions: Python-tests, frontendbuild, shellcheck en Docker-runtime-smoketest geslaagd.
- Imagepublicatie naar GHCR: geslaagd; anonieme manifestaanvraag retourneerde HTTP 200.
- Productierunner: online, afzonderlijke onbevoorrechte gebruiker.
- Eerste automatische deployment via main: geslaagd; `/health` meldde de bedoelde volledige commit.
- `/ready` en startpagina zijn via het netwerk bereikbaar.
- HTTPS op `controldeck.vanburik.info`: startpagina, health, readiness en licentieteksten retourneerden HTTP 200; HTTP verwijst met 301 naar HTTPS.
- Release `v0.1.1`: gedownloade bundle gecontroleerd op checksum, versie, commit en gebundelde licentieteksten; productie meldde dezelfde commit.
- Een bundle met een onjuiste checksum is door de deployhelper geweigerd; de actieve release en readiness bleven behouden.

## Eerste resourcewaarneming

In een Debian 13-LXC meldde systemd ongeveer 34 MiB voor de applicatieservice en ongeveer 99 MiB voor de Actions-runner na de eerste deployment. Dit betreft één moment zonder gebruikersbelasting. Het is geen duurtest, minimumvereiste of garantie voor toekomstige modules. Buildprocessen draaien op GitHub en zijn niet in deze runtimewaarden opgenomen.

## Grenzen

Automatische rollback bij een opstartfout is geïmplementeerd, maar een opzettelijke productie-opstartfout is nog niet gesimuleerd. De eerste foundation had nog geen gebruikersdatabase, authenticatie of providerintegraties. De latere secties beschrijven de inmiddels toegevoegde functionaliteit; een volledige herstelproef van de gebruikersdatabase is nog niet uitgevoerd. De volledige release-uitkomst blijft zichtbaar in GitHub Actions en de releasepagina.

## Basisinterface 0.2.0

De productie-export en TypeScript-controle slagen; beide Python-tests slagen, inclusief de nieuwe uptimecontrole. In de browser zijn Proxmox- en Admin-dropdowns, selectie van subpagina's, behoud van directe hashlinks na herladen, terugnavigatie, lichte/donkere themaopslag, refresh en de mobiele hamburgernavigatie gecontroleerd. Op het mobiele testformaat is geen horizontale overflow gemeten. Het eigen logo en de desktopindeling zijn visueel beoordeeld. De modulepagina's blijven placeholders en er is nog geen authenticatie.

## 0.3.0 — Configuratie, SSO en testcontracten

87 Python-tests en 12 frontend-unit-tests slagen. De nieuwe functies hebben expliciete normaal/boundary/faal-contracten; login heeft aanvullend tests voor echte RSA-tokenvalidatie, state, nonce, audience, issuer, expiry, geverifieerde e-mail en accounttoelating. TypeScript en productie-export slagen. Een lege startpagina voldoet niet meer aan readiness.

De lokale browsercontrole gebruikt uitsluitend een apart loopback-testharnas buiten de repository met testaccounts: profiel aanmaken (user en enabled=true als defaults), dynamische wijziging van het menu zonder rebuild, activeren van een Kasm-testmodule en de adres/open-knop zijn gecontroleerd. Dit is geen echte provider-API-integratie. Verplichte login toont bij niet-ingestelde OAuth uitsluitend de gesloten aanmeldpagina. Er is geen testloginroute in de applicatiebroncode of releasebundle.

De productieomgeving gebruikt een eigen Google OAuth-client die privé uit het door de gebruiker verstrekte JSON-bestand is geïnstalleerd. De callback in dat bestand komt exact overeen met de productiecallback. Een complete Google-login vereist nog browserverificatie door een echte toegestane gebruiker; de unit-tests vervangen Google-netwerktransport door fixtures.

### Productieverificatie na uitrol 0.3.0

De main-workflow en LXC-deployment zijn geslaagd. Via het publieke HTTPS-adres geven `/api/config`, `/api/preferences` en `/api/accounts` voor anonieme bezoekers HTTP 401. De eigen Google OAuth-client leidt naar de accountkeuze zonder redirectfout. Een echte Google-login met een toegestaan useraccount is succesvol doorlopen; het Admin-menu ontbreekt voor die rol. Thema en laatst bezochte module zijn op productie na herladen teruggezet.

De adminpagina is met een lokaal testaccount gecontroleerd: overzicht, alle gevraagde profielvelden, aanmaken en defaults user/enabled=true. De serverzijdige admin/user-grens, wijzigen en laatste-adminbescherming zijn geautomatiseerd getest. Een echte Google-login van de admin is nog niet door de agent doorlopen; de betreffende gebruiker kan dit zelf doen.

Na Google-login gebruikte de appservice in een momentopname 52.948.992 bytes (ongeveer 50,5 MiB), met een piek van 53.977.088 bytes. Dit is één observatie, geen gegarandeerd maximum. De lichte architectuur blijft één Python-service en een statische frontend.

## 0.4.0 — Termix en module-installatiewizard

- CI: 144 Python-tests en 18 frontendtests geslaagd, naast TypeScript, productiebuild, shellcheck en Docker-runtimecontrole. Normal-, boundary- en failure-contracten zijn aangevuld voor autorisatie, Termix-sessies, installatieplanning, opdrachten en de rootworker.
- Productie: Termix 2.9.1 is gezond en de hoofdapplicatie meldt versie 0.4.0.
- Een echt ingelogd Google-useraccount opent de ingebedde Termix-interface zonder tweede login.
- Anonieme Termix-aanvragen worden geweigerd. Publieke accountregistratie is geblokkeerd en het interne gateway-autorisatiepad is extern onbereikbaar.
- Een Termix-adminsessie gecombineerd met een ander ControlDeck-useraccount wordt geweigerd. Identiteit en rol worden serverzijdig gecontroleerd.
- Een daadwerkelijke WebSocket via het publieke HTTPS-adres, Cloudflare, Nginx en Termix heeft een sessielijst ontvangen. Een SSH-verbinding naar een homelabhost is nog niet getest; er zijn nog geen hosts in Termix ingericht.
- De productie-installatie-API heeft met een tijdelijk ondertekende testsessie van een bestaande admin een Docker-opdracht ingediend. De rootworker heeft de installer uitgevoerd en de opdracht als geslaagd afgesloten; de applicatie bleef bereikbaar. Deze verificatie voegt geen testlogin aan het product toe.
- De vijf wizardstappen, Docker/LXC-keuze en LXC-blokkade zijn in de browser met een afzonderlijk lokaal admin-testprofiel gecontroleerd. Een echte Google-adminlogin is nog niet door de agent doorlopen.

Automatisch aanmaken van een Proxmox LXC is nog niet uitgevoerd of getest: hosttoegang en de uitvoerende Helper-Script-adapter ontbreken. De wizard voorkomt starten van die route. Bestaande WebSocket-verbindingen worden niet voortdurend opnieuw geautoriseerd; nieuwe aanvragen controleren de actuele toegang.

## Gedeelde appiconen — lokale controle

500 Python-tests geslaagd, 8 overgeslagen; 165 frontendtests geslaagd; TypeScript en productiebuild geslaagd. PNG-tests controleren normale afbeeldingen, formaatgrenzen, beschadigde inhoud, verkeerde bestandstypen, opslaan, centrale bronprojectie, CSRF en toegang per gebruiker. Favicon- en uploadtests controleren oorsprongadressen, verkeerde protocollen, verwerking en foutafhandeling. Deze wijziging is nog niet gepubliceerd en is niet ingelogd op productie gecontroleerd.

## 14 oktober 2026 — Herbruikbare Linkwarden-module

- Direct voor publicatie: 517 Python-tests geslaagd, 8 overgeslagen; 169 frontendtests geslaagd; TypeScript, statische productiebuild en whitespacecontrole geslaagd.
- Modulecontracten controleren opslag, herstart, dupliceren, revisieconflicten, onbekende functies, collectiegrenzen, ontbrekende rechten, eigenaarisolatie, CSRF en het na intrekken van rechten kunnen verplaatsen/verwijderen van bestaande modules. De bestaande persoonlijke Linkwarden-API is aanvullend gecontroleerd met normale, lege en afgewezen providerantwoorden.
- Browsercontrole op een tijdelijk loopback-testharnas met synthetische gegevens: module kiezen, collectie instellen, opslaan/herladen, zoeken zonder resultaten, Beheren openen, twee modules met verschillende collecties en naast elkaar plaatsen. Op telefoonformaat is geen horizontale pagina-overflow gemeten. Deze controle is geen live Linkwarden-providerproef.
- De bestaande volledige Bookmarks-pagina gebruikt dezelfde Linkwarden-component. De dashboardweergave biedt compacte bediening en bewaart uitsluitend selectie/plaatsing. Faviconweergave en PNG-upload zijn eveneens gedeeld.
- Publicatie verloopt via de bestaande workflow, met controles vóór publiceren en deployen. Ingelogde productiecontrole achter Cloudflare vereist een bestaande gebruikerssessie.

## 14 oktober 2026 — Modulaire structuur en aanmeldadapters

- Finale lokale controles: 550 Python-tests geslaagd, 8 overgeslagen; 173 frontendtests geslaagd; TypeScript, statische productiebuild en whitespacecontrole geslaagd.
- Linkwarden-weergave en instellingen staan in een eigen frontendmodulemap. Het dashboard monteert generieke modulecontracten en rechten uit de catalogus. Servervalidatie staat per module in backend/modules.
- Kasm- en Nextcloud-aanmeldadapters zijn met synthetische fixtures getest op normale aanmelding, configuratiegrenzen, onbekende modules, accountbinding, CSRF, modulerechten, uitgeschakelde provider, bronuitval, TLS-fouten, onveilige redirects en ontbrekende vault. API-geheimen komen niet in de antwoordprojectie. De no-referrer-regressietest is eerst falend en na correctie geslaagd uitgevoerd.
- De opgegeven Nextcloud-installatie is alleen-lezen bereikbaar gecontroleerd: versie 33.0.9, geen onderhoudsmodus, gewone loginpagina zonder zichtbare Google-knop. Dit bewijst geen ingerichte Google/user_oidc-aanmelding. Geen remote aanmeld- of accountinstellingen aangepast.
- Het Kasm-adres, de vaultverwijzingen en de bestaande Nextcloud-Google-provider moeten nog worden vastgesteld. Live automatisch aanmelden is daarom niet geactiveerd en niet als werkend geclaimd. Een echte browseraanmelding achter Cloudflare is niet uitgevoerd.
- De laatste Linkwarden-module is opnieuw in het lokale synthetische browserharnas gecontroleerd na de modulair opgebouwde registratiewijziging.
