# Verificatie van de infrastructuur

Datum: 5 oktober 2026. Deze controles betreffen de foundation, geen volledige functionele homelabapplicatie.

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

Automatische rollback bij een opstartfout is geïmplementeerd, maar een opzettelijke productie-opstartfout is nog niet gesimuleerd. Databaseherstel en schemamigraties zijn nog niet van toepassing. Authentication, providers en de navigatie-uitbreidingen behoren tot volgende implementatiestappen. De volledige release-uitkomst blijft zichtbaar in GitHub Actions en de releasepagina.
