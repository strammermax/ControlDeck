# Basisinterface

De basisinterface volgt de door de gebruiker aangeleverde ProxMenux Monitor-mockup: een donkere bovenbalk, horizontaal hoofdmenu, blauwe selectie en een rustige werkruimte met centrale footer. Het eigen ControlDeck-logo uit `docs/logo.jpg` staat als ongewijzigde kopie in `frontend/public/controldeck-logo.jpg`; CSS begrenst de zichtbare uitsnede.

## Navigatie

`config/controldeck.json` en de bestanden onder `config/modules/` bepalen het menu en de bestemmingen. `frontend/lib/navigation.ts` verwerkt de gevalideerde configuratie. Dashboard, Bookmarks en Terminal openen rechtstreeks. Virtual Apps en Media hebben configureerbare dropdowns voor toepassingen. Proxmox bevat Overzicht, Nodes, Virtual Machines, Containers, Storage, Files, Network en Monitoring. Admin bevat Instellingen, Modules, Providers en Gebruikers.

Elke bestemming heeft een hashlink, bijvoorbeeld `/#proxmox/nodes`. Links kunnen worden gedeeld en de terugknop werkt. Providerdefinities kunnen een toepassing openen; echte API-adapters volgen later. De meegeleverde Kasm/Radarr/Plex-voorbeelden staan uit. Admin → Gebruikers bevat werkelijk profielbeheer voor admins. Het Dashboard blijft bewust leeg overeenkomstig de mockup.

Onder 800 pixels wordt het hoofdmenu inklapbaar met een hamburgerknop. Dit is de mobiele hoofdnav; het toekomstige boommenu naast de werkruimte is nog niet gebouwd. Native disclosure-elementen ondersteunen toetsenbordbediening. Escape sluit een dropdown en herstelt focus. Klikken buiten het menu sluit de dropdowns. Een skiplink gaat naar de inhoud.

## Bovenbalk

- De naam of het e-mailadres van de aangemelde gebruiker, met Uitloggen. Zonder login verschijnt uitsluitend de aanmeldpagina.
- Online/Offline/Checking: bereikbaarheid van de ControlDeck-service, niet de gezondheid van het hele homelab.
- Uptime: verstreken tijd sinds de start van het Flask-applicatieproces. Deze wordt opnieuw nul na een herstart.
- Refresh: vernieuwt sessie, configuratie en `/health`; het automatische interval komt uit JSON (standaard 30 seconden). Een aanvraag heeft een timeout van acht seconden.
- Thema: licht/donker, als persoonlijke voorkeur centraal opgeslagen. De laatst bezochte module wordt eveneens per gebruiker bewaard.
- Footer: de versie van de actieve backend, met de frontendversie als fallback, en een link naar het project op GitHub.

## Runtime en hergebruik

De interface blijft een statische Next.js-export. Er komen geen extra runtimeprocessen, UI-packages of externe lettertypen bij. De kleine SVG-menu-iconen zijn in het project getekend. De ProxMenux-referentie dient voor de visuele indeling; opgeslagen scripts uit de mockup worden niet uitgevoerd of meegeleverd.

## Verificatie

Bij deze wijziging worden TypeScript, productie-export en Python-tests uitgevoerd. Browsercontrole omvat desktop- en mobiele navigatie, dropdowns, directe links, terugnavigatie, thema en refresh. De bestaande CI controleert ook Docker en rolt de main-commit uit naar LXC 164. Google OIDC-login, serverzijdige rollen en accountbeheer worden apart getest. Windows-login en API-adapters volgen later; widgetdefinities worden nog niet als Dashboard gerenderd.

## Persoonlijke instellingen

Klik rechtsboven op je naam: de dropdown bevat Profiel (`#profile`, alleen-lezen: naam, e-mail, rol en aanmeldmethode), Instellingen (`#settings`) en Uitloggen. Escape of klikken buiten de dropdown sluit hem. Elke aangemelde gebruiker ziet deze pagina, los van de modulerechten. De instellingen gelden per gebruiker en worden via `/api/preferences` in SQLite opgeslagen, dus ook op andere apparaten gebruikt.

- **Interfacetaal:** Nederlands (standaard) of English. De keuze wordt direct opgeslagen. Voorlopig vertalen de Instellingen-pagina en de bediening rechtsboven; menulabels komen uit de configuratie.
- **Menuvolgorde:** sleep de hoofdtabbladen in de gewenste volgorde en kies Opslaan. Annuleren zet de laatst opgeslagen volgorde terug, Standaard herstellen de configuratievolgorde. Groepen zoals Proxmox en Admin verplaatsen als geheel. Op touchscherm eerst lang drukken; met het toetsenbord Alt+pijl omhoog/omlaag op de greep.

De server accepteert `language` (`nl`/`en`) en `navOrder` (maximaal 32 unieke menu-id's). Een opgeslagen id geeft nooit toegang: de volgorde wordt alleen toegepast op het menu dat de server voor die gebruiker filtert. Onbekende id's worden genegeerd en nieuwe menu-items komen achteraan.

## Site-iconen

De faviconset uit `docs/images/favicon_io.zip` staat in `frontend/public/`. De pagina verwijst naar ICO, PNG (16/32 pixels), Apple touch-icon en `site.webmanifest`. Het manifest gebruikt de ControlDeck-naam en Android-iconen van 192/512 pixels. Deze statische bestanden zijn ook op de aanmeldpagina beschikbaar.
