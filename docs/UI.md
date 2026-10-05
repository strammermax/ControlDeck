# Basisinterface

De basisinterface volgt de door de gebruiker aangeleverde ProxMenux Monitor-mockup: een donkere bovenbalk, horizontaal hoofdmenu, blauwe selectie en een rustige werkruimte met centrale footer. Het eigen ControlDeck-logo uit `docs/logo.jpg` staat als ongewijzigde kopie in `frontend/public/controldeck-logo.jpg`; CSS begrenst de zichtbare uitsnede.

## Navigatie

`frontend/lib/navigation.ts` definieert het menu en de bestemmingen. Dashboard, Virtual Apps, Bookmarks, Media en Terminal openen rechtstreeks. Proxmox bevat Overzicht, Nodes, Virtual Machines, Containers, Storage, Files, Network en Monitoring. Admin bevat Instellingen, Modules, Providers en Gebruikers.

Elke bestemming heeft een hashlink, bijvoorbeeld `/#proxmox/nodes`. Links kunnen worden gedeeld en de terugknop werkt. Er zijn nog geen providerintegraties: de modulepagina's melden dat het onderdeel nog niet is ingericht. Het Dashboard blijft bewust leeg overeenkomstig de mockup.

Onder 800 pixels wordt het hoofdmenu inklapbaar met een hamburgerknop. Dit is de mobiele hoofdnav; het toekomstige boommenu naast de werkruimte is nog niet gebouwd. Native disclosure-elementen ondersteunen toetsenbordbediening. Escape sluit een dropdown en herstelt focus. Klikken buiten het menu sluit de dropdowns. Een skiplink gaat naar de inhoud.

## Bovenbalk

- `User: Guest`: er is nog geen authenticatie. Dit is geen ingelogde identiteit.
- Online/Offline/Checking: bereikbaarheid van de ControlDeck-service, niet de gezondheid van het hele homelab.
- Uptime: verstreken tijd sinds de start van het Flask-applicatieproces. Deze wordt opnieuw nul na een herstart.
- Refresh: vernieuwt `/health`; automatisch gebeurt dit elke 30 seconden. Een aanvraag heeft een timeout van acht seconden.
- Thema: licht/donker, opgeslagen in de browser indien lokale opslag beschikbaar is.
- Footer: de versie van de actieve backend, met de frontendversie als fallback, en een link naar het project op GitHub.

## Runtime en hergebruik

De interface blijft een statische Next.js-export. Er komen geen extra runtimeprocessen, UI-packages of externe lettertypen bij. De kleine SVG-menu-iconen zijn in het project getekend. De ProxMenux-referentie dient voor de visuele indeling; opgeslagen scripts uit de mockup worden niet uitgevoerd of meegeleverd.

## Verificatie

Bij deze wijziging worden TypeScript, productie-export en Python-tests uitgevoerd. Browsercontrole omvat desktop- en mobiele navigatie, dropdowns, directe links, terugnavigatie, thema en refresh. De bestaande CI controleert ook Docker en rolt de main-commit uit naar LXC 164. Integraties en login vallen buiten deze versie.
