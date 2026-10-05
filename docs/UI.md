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
