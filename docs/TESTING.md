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
