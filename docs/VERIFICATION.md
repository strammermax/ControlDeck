# Verificatie van de infrastructuur

Datum: 5 oktober 2026. Onderstaande controles zijn per versie vastgelegd; oudere secties beschrijven de toenmalige grenzen.

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
