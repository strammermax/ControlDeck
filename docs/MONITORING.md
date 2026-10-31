# Monitoring: verbindingen tussen apps

**Status:** eerste versie gebouwd: handmatige verbindingen, ontdekken via *arr-API's en de Cloudflare-tunnel, geleerde verbindingen (intern en internet) uit de open sockets van elke container, controle vanaf de bron via de node-agent. Meldingen per e-mail via de SMTP-gateway op OPNsense. Nog niet gebouwd: ontdekken via Home Assistant en DNS-/proxycontroles uit de Myscripts-inventaris (zie [ROADMAP.md](ROADMAP.md)).

Pagina: **Proxmox → Monitoring** (`#monitoring`). Zichtbaar voor iedereen met de module `monitoring`; toevoegen, verwijderen en "Nu controleren" alleen voor beheerders (admin/editor).

## Waarom

Apps vallen vaak om door een gewijzigd IP-adres, DNS-record of firewallregel, zonder dat de app zelf stuk is: Lidarr kan qBittorrent niet meer bereiken, Home Assistant de Zigbee-coördinator niet. Monitoring test daarom de **verbinding** van een app naar een host en poort, niet alleen of de app zelf draait.

## Wat een verbinding is

Een verbinding is `bron-app → host:poort`, met een omschrijving. Er zijn twee soorten:

| Soort | Bron | Opslag |
| --- | --- | --- |
| Ontdekt | *arr-apps: downloadclients en indexers (Sonarr/Radarr/Lidarr/Readarr), downloadclients en gekoppelde apps (Prowlarr), via hun eigen API. Cloudflare-tunnel: alle ingangen (`hostname → service`) uit de lokale cloudflared-config. | Elke 10 minuten opnieuw ontdekt; opgeslagen in SQLite |
| Gezien ("geleerd") | Elke 5 minuten leest de agent per draaiende LXC op een gekoppelde node de open, zelf gestarte TCP-verbindingen (`/proc/<pid>/net/tcp` en `tcp6` van de container; inkomende verbindingen op een luisterpoort en loopback tellen niet). Zo verschijnen ook alle internetverbindingen, bijv. removesky → `api.open-meteo.com`. | SQLite, per bestemming eerste en laatste keer gezien |
| Handmatig | Toegevoegd op de pagina, bijv. Home Assistant → `192.168.1.96:6638`, of een internetdienst op hostnaam | SQLite |

**Namen bij IP-adressen.** Een geleerde bestemming krijgt een leesbare naam, in deze volgorde:

1. **Docker-naam:** de agent vraagt per LXC aan Docker welk IP bij welke container hoort (`172.18.0.8` → `qbittorrent`). Dit is exact.
2. **Eigen opzoektabel IP → gast:** uit de Proxmox-config van elke LXC (`net*: ip=…`), een dag geldig (`192.168.20.137` → `arrsuite`). Nodig omdat de LAN-DNS wel naam → IP beantwoordt, maar vaak niet IP → naam.
3. **Reverse DNS** vanaf ControlDeck: voor het LAN levert OPNsense de `.home`-namen (`192.168.20.137` → `arrsuite.home`), voor internet de PTR-naam als die er is.
4. **CDN-label:** adressen in de gepubliceerde Cloudflare-reeksen heten "Cloudflare (CDN)". Reverse DNS zegt daar niets over de dienst erachter.

Opzoeken gebeurt parallel, met een tijdslimiet van 5 seconden per ronde. Een naam wordt een dag onthouden. Wat niet te vinden is, blijft leeg: er wordt nooit een naam bedacht. Een eenmaal gevonden naam blijft staan, ook als een latere ronde niets vindt. Op de pagina staat de naam bovenaan, met het IP-adres eronder. Meldingsmails tonen `naam (IP)`.

**Docker binnen een LXC** (zoals de arrsuite): elke Docker-container heeft een eigen netwerk. De agent leert per netwerknamespace en noemt de bron naar de Docker-container, bijv. `arrsuite / sonarr`. Hij test ook vanuit die namespace, zodat `qbittorrent` of `localhost` in een *arr-instelling precies betekent wat die app ziet. Bestemmingen op internet met een poort vanaf 10000 worden niet geleerd: dat zijn peers van BitTorrent en Soulseek, die steeds wisselen.

Een geleerde verbinding wordt gecontroleerd zolang hij de afgelopen 24 uur open is gezien en na 7 dagen zonder waarneming vergeten. Internetdiensten achter een CDN wisselen van IP-adres. Een oud adres verdwijnt daardoor vanzelf; voeg een belangrijke internetdienst ook handmatig op hostnaam toe, dan lost de container de naam bij elke controle zelf op. Op de pagina filter je op **Intern** of **Internet**.

Mislukt het ontdekken bij één bron (sleutel ingetrokken, app uit), dan blijft de vorige lijst van die bron staan en toont de pagina de fout. Is Infisical onbereikbaar, dan blijft de hele lijst staan: een onbereikbare vault betekent niet dat alle verbindingen weg zijn.

## Hoe er gecontroleerd wordt

Elke minuut (achtergrondthread in de ene Gunicorn-worker; geen extra systemd-unit) en direct met **Nu controleren**:

- **Via bron:** is de bron een draaiende LXC op een node met de ControlDeck-agent, dan test de agent vanuit de container zelf. De agent stapt met `nsenter -n` in het netwerk van de container. Hij lost de naam op met de `/etc/hosts` en `resolv.conf` (inclusief zoekdomeinen) van die container en maakt een TCP-verbinding. Zo tellen routering, firewall en de DNS van de app zelf mee. De container heeft geen extra tools nodig: de agent gebruikt Python op de host.
- **Via ControlDeck:** voor VM's, apps buiten Proxmox, handmatige verbindingen zonder container-ID en als de agent niet beschikbaar is. Dit test het pad vanaf ControlDeck, niet dat van de app; de pagina zegt dat erbij.
- Een time-out (3 s), een geweigerde verbinding en een niet op te lossen naam krijgen elk een eigen melding.
- Mislukt de controle zelf (agent of node onbereikbaar), dan wordt de status **onbekend**: nooit online en nooit onderbroken.
- Per verbinding wordt bewaard: status, sinds wanneer, laatste controle, fout, reactietijd, IP-adres en via wie. Elke statuswissel komt in de lijst **Laatste wijzigingen** (maximaal 2000 bewaard).

De gast-ID van een bron wordt via de bestaande alleen-lezen Proxmox-koppeling (`/cluster/resources`) gekoppeld aan node, type en status.

## Meldingen per e-mail

Beheerders stellen dit in op de pagina onder **Meldingen per e-mail**: aan/uit, ontvangers (maximaal 10), afzender (standaard `homelab@vanburik.info`), de SMTP-gateway (standaard `192.168.20.1:25`, de mailrelay op OPNsense) en na hoeveel minuten onderbreking er gemeld wordt (standaard 5). Met **Testmail versturen** controleer je de route. De instellingen staan in de SQLite van Monitoring; ontvangers zijn alleen voor beheerders zichtbaar.

- Na elke controleronde gaat er hoogstens **één mail** uit, met alle verbindingen die langer dan de wachttijd onderbroken zijn en nog niet gemeld waren, plus alles wat gemeld was en weer online is ("hersteld"). Zolang iets onderbroken blijft, komt er geen herhaalmail.
- Een controle die zelf mislukt ("onbekend") meldt nooit iets. Geleerde verbindingen melden standaard niet: internetadressen achter een CDN wisselen. Dat is per instelling aan te zetten.
- De relay vraagt geen aanmelding. Biedt hij STARTTLS aan, dan wordt die gebruikt. Mislukt het versturen, dan staat de fout op de pagina en wordt het de volgende ronde opnieuw geprobeerd; er gaat niets verloren.
- Mail ophalen (IMAP/POP3) kan niet via de relay en is ook niet nodig: ControlDeck verstuurt alleen.

## Mail (tabblad, alleen beheerders)

Het tabblad **Mail** toont de laatste 50 berichten uit de inbox van de meldingenmailbox (`homelab@vanburik.info`). Daar komen de mails van NAS, PBS, de *arr-apps, Nextcloud en Monitoring zelf binnen. Per mail zie je status, tijd, systeem, onderwerp en afzender; een klik toont de volledige tekst.

- **Alleen lezen:** de inbox wordt `readonly` geopend en berichten worden met `BODY.PEEK` opgehaald. ControlDeck markeert dus niets als gelezen en verplaatst of verwijdert niets.
- **Systeem en status** worden afgeleid uit afzender en onderwerp. Een onderwerp met bijv. *failed*, *fout*, *Problemen* of *Undelivered* wordt een probleem; *Success*, *hersteld* of *klaar* wordt OK. Filter op systeem of op alleen problemen.
- **Toegang:** de lijst wordt een minuut bewaard; **Vernieuwen** haalt direct op. Alleen beheerders met de module `monitoring` zien het tabblad en de API; mails kunnen gevoelige details bevatten.
- **Inrichting:** `CONTROLDECK_MAILBOX` in Infisical (`/apps/controldeck/widgets`):

  ```json
  {"host": "imap.gmail.com", "port": 993, "username": "homelab@vanburik.info", "password": "<app-wachtwoord>"}
  ```

  Gebruik een eigen app-wachtwoord ("ControlDeck IMAP"), los van dat van de OPNsense-relay, zodat elk apart in te trekken is. De mailrelay zelf kan geen mail ophalen.

## Agent-acties

Drie nieuwe acties, alleen-lezen en daarom niet in het agent-auditlog (agentversie 2, proxyversie 2):

| Actie | Doet | Invoer |
| --- | --- | --- |
| `net.probe` | Per doel: naam oplossen en TCP verbinden vanuit de container, of vanuit een Docker-app daarin | `vmid`, optioneel `app`, `targets` (1-64 × `{host, port}`) |
| `net.connections` | Open uitgaande TCP-verbindingen per container en per Docker-app daarin (bestemming, poort, aantal), maximaal 200 per namespace; plus `names`: Docker-IP → containernaam per LXC (agent v3) | `vmids` (1-200) |
| `net.tunnel` | Ingangen van cloudflared (`/config` op `127.0.0.1:20241-20245`, alleen `hostname` en `service`) | `vmid` |

Hostnamen en poorten worden in de agent opnieuw gevalideerd; onbekende velden worden geweigerd. De interne modi `__probe` en `__tunnel` start de agent alleen zelf, via `nsenter`, zonder `SSH_ORIGINAL_COMMAND`. Over SSH zijn het geen geldige acties.

**Bijwerken na deze release:** de proxy (versie 2) via `bash scripts/install-wizard.sh` op de ControlDeck-host, en de agent per node via Modulebeheer → Cronjobs (de nodes staan op "Agent verouderd" tot dat is gebeurd).

## Bronnen in Infisical

`CONTROLDECK_MONITORING` in de ControlDeck-vaultmap, een JSON-object:

```json
{
  "sources": {
    "sonarr":   {"kind": "sonarr",   "title": "Sonarr",   "url": "http://192.168.20.137:8989", "allowHttp": true, "apiKey": "replace-in-vault", "vmid": 137, "app": "sonarr"},
    "radarr":   {"kind": "radarr",   "title": "Radarr",   "url": "http://192.168.20.137:7878", "allowHttp": true, "apiKey": "replace-in-vault", "vmid": 137},
    "lidarr":   {"kind": "lidarr",   "title": "Lidarr",   "url": "http://192.168.20.137:8686", "allowHttp": true, "apiKey": "replace-in-vault", "vmid": 137},
    "prowlarr": {"kind": "prowlarr", "title": "Prowlarr", "url": "http://192.168.20.137:9696", "allowHttp": true, "apiKey": "replace-in-vault", "vmid": 137},
    "tunnel":   {"kind": "cloudflared", "title": "Cloudflare-tunnel", "vmid": 127}
  }
}
```

- `kind`: `sonarr`, `radarr`, `lidarr`, `readarr`, `prowlarr` of `cloudflared`.
- `vmid` (optioneel bij *arr, verplicht bij `cloudflared`): de container waarin de app draait. Daarvandaan wordt getest.
- `app` (optioneel, alleen met `vmid`): de Docker-container binnen de LXC van waaruit getest wordt.
- `url` en `apiKey` voor *arr: de app zelf, zoals bij de servicewidgets. Een API-sleutel is alleen-lezen nodig; hij komt nooit in de browser of in de API-antwoorden.
- Maximaal 32 bronnen, 500 verbindingen.

## API

| Methode en pad | Rechten | Doet |
| --- | --- | --- |
| `GET /api/monitoring` | module `monitoring` | Verbindingen met status, laatste 50 wijzigingen, fouten per bron |
| `POST /api/monitoring/check` | beheerder + CSRF | Nu ontdekken en controleren |
| `POST /api/monitoring/connections` | beheerder + CSRF | Handmatige verbinding: `source`, `host`, `port`, optioneel `label`, `vmid` |
| `DELETE /api/monitoring/connections/<id>` | beheerder + CSRF | Handmatige verbinding verwijderen (ontdekte niet) |
| `GET /api/monitoring/notifications` | beheerder | Meldinginstellingen en laatste verzendfout |
| `PUT /api/monitoring/notifications` | beheerder + CSRF | Meldinginstellingen opslaan |
| `POST /api/monitoring/notifications/test` | beheerder + CSRF | Testmail versturen |
| `GET /api/monitoring/mail` (`?refresh=1`) | beheerder | Laatste 50 mails uit de inbox (zonder wachtwoord of inhoud) |
| `GET /api/monitoring/mail/<uid>` | beheerder | Eén mail met tekst (HTML omgezet naar platte tekst, maximaal 100.000 tekens) |

## Testen

`tests/test_monitoring.py`, `tests/test_monitoring_notify.py`, `tests/test_mailbox.py` (alleen lezen: geen STORE/MOVE/EXPUNGE, PEEK; HTML naar tekst; lege inbox; verkeerd wachtwoord; ontbrekende of ongeldige config; alleen beheerders) en `frontend/tests/monitoring.test.mjs`. Meldingen: mail pas na de wachttijd en maar één keer; herstelmail; meerdere storingen in één mail; geleerde en onbekende verbindingen melden niet; relay onbereikbaar → fout zichtbaar en later alsnog verstuurd; STARTTLS; ongeldige instellingen geweigerd; ontvangers alleen voor beheerders. Verder:

- **Normaal:** geleerde verbindingen uit de socketlijst (intern en internet) en controle via de agent in de container, naam via de hosts van de container, ontdekking via de *arr-API en de tunnel, statuswissels met behoud van "sinds".
- **Grens:** IPv4-in-IPv6-adressen, inkomende en loopbackverbindingen uitgesloten, vervallen na 24 uur, 64 doelen, korte namen met zoekdomein, dubbele verbinding, tunnelregels zonder host (`http_status:404`), hoofdletters en een punt op het eind.
- **Afwijzing:** ongeldige hosts, poorten, container-ID's en extra velden, gestopte container, niet op te lossen naam, ongeldige vaultconfiguratie, mislukte ontdekking bij één bron, onbereikbare vault, agent onbereikbaar ("onbekend").
- **Toegang:** zonder aanmelding (401), zonder module (403), kijker zonder beheerrechten (403 bij wijzigen), ontbrekend CSRF-token (403), geen API-sleutels in antwoorden.
