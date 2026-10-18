# Lokale links buiten het thuisnetwerk

Instellingen → Lokale links bevat de persoonlijke optie **Lokale .home-links buiten mijn netwerk verbergen**. Deze staat standaard aan, ook voor bestaande gebruikers zonder opgeslagen waarde. De voorkeur wordt per gebruiker opgeslagen in dezelfde SQLite-voorkeuren als taal en menuvolgorde; wijzigen vereist een aangemelde sessie en CSRF-token. Uitschakelen toont de links weer, ook buiten het lokale netwerk.

De weergaveregel geldt voor de hele ControlDeck-interface: navigatie, Bookmarks, persoonlijke dashboards, zoekresultaten en objectlinks in widgets. Een link naar exact `home` of een subdomein van `.home` wordt verborgen, inclusief een eventuele poort, hoofdletters of afsluitende DNS-punt. Een publiek adres met `.home` alleen in het pad, een queryparameter of vóór een ander domein blijft zichtbaar. Interne navigatie zoals `#settings` blijft beschikbaar. Zelfstandige lokale tegels en lijstregels worden als geheel verborgen; iframe-links naar zulke hosts worden ook verborgen. Nieuwe links uit asynchrone modules worden opnieuw beoordeeld. De onderliggende URL en persoonlijke documenten worden niet gewijzigd; daardoor blijven verborgen links bewaard bij opslaan van een dashboard en keren ze lokaal of na uitschakelen terug.

## Netwerkherkenning

`/api/session` geeft alleen `network: {isLocal, scope}` terug, geen IP-adres. Standaard gelden RFC1918, IPv6 ULA en IPv6 link-local als lokaal. Een niet vast te stellen verbinding geldt voor deze zichtbaarheid als buiten het netwerk. Dit is een weergavevoorkeur, geen toegangscontrole: de gebruikelijke API- en bronrechten blijven verplicht en oorspronkelijke URLs kunnen nog via toegestane APIs worden gelezen.

Een rechtstreeks bezoek wordt op het werkelijke peeradres beoordeeld. Achter de lokale Nginx-gateway overschrijft Nginx altijd `X-ControlDeck-Peer-IP` met zijn eigen peeradres. De app accepteert dit alleen van loopback. Alleen expliciet ingerichte edge-proxies mogen vervolgens `CF-Connecting-IP` leveren. Een willekeurige `X-Forwarded-For` of bezoekersheader mag dus geen externe bezoeker als lokaal laten gelden.

De centrale Infisical-instellingen `CONTROLDECK_TRUSTED_EDGE_PROXIES` en `CONTROLDECK_LOCAL_NETWORKS` bevatten kommagescheiden CIDRs. Er komen geen extra providergeheimen of handmatige bootstrap-envs bij. Vul bij de lokale netwerken ook het publieke uitgaande thuisadres in, zodat een thuisbezoek via de publieke Cloudflare-tunnel herkenbaar blijft. Bij wijziging van dat publieke adres moet deze centrale instelling worden bijgewerkt. Netwerkadressen en accountgegevens horen niet in Git. Ongeldige/brede nul-prefixconfiguratie wordt niet als vertrouwde netwerkregel gebruikt.

## Testen

Normaal: publieke bezoeker ziet geen `.home`-links, lokale bezoeker wel; instelling uit toont alles. Grenzen: IPv4/IPv6, expliciet thuis-WAN-adres via een vertrouwde edge, ontbrekende voorkeur, onbekende netwerkherkomst, poorten, hoofdletters, afsluitende punt, dynamisch toegevoegde links en herstel zonder URL-wijziging. Afwijzing: vervalste proxyheaders, ongeldige IP/CIDR, niet-booleaanse voorkeur, ontbrekende sessie/CSRF en toegang tot andermans voorkeur. Controleer in de browser ook het omzetten van de checkbox en het bewaren na herladen.

Productie-inrichting: de gateway is met een back-up aangepast om de peerheader te overschrijven; Nginx-configuratiecontrole en reload zijn geslaagd. De bestaande tunnelpeer en het publieke uitgaande thuisadres zijn uitsluitend in de beperkte Infisical-appmap vastgelegd. Het huidige thuisadres is vanaf de thuis-host bepaald, niet van de bezoeker overgenomen.
