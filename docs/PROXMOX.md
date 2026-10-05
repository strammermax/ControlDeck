# Proxmox-koppeling

ControlDeck leest gegevens uit een Proxmox VE-cluster via de officiële API (`/api2/json`). De koppeling is **alleen-lezen**: ControlDeck start, stopt of wijzigt niets in Proxmox.

## Koppelen (admin)

**Admin → Modules → Proxmox VE** opent de koppelwizard:

1. **Module** — kies Proxmox VE.
2. **Verbinding** — vul een node-adres (`https://192.168.1.98:8006`) of eigen domein (`https://pm.vanburik.info`) in. Een geplakt adres met `/#` wordt opgeschoond. ControlDeck haalt het certificaat op:
   - Geldig (publiek vertrouwd) certificaat: normale certificaat- en hostnaamcontrole, geen vingerafdruk.
   - Zelfondertekend certificaat: de wizard toont de SHA-256-vingerafdruk. Vergelijk die met Proxmox → node → Systeem → Certificaten (`pve-ssl.pem`) en bevestig. ControlDeck accepteert daarna uitsluitend dat certificaat; een ander certificaat wordt geweigerd vóórdat het token wordt verzonden. Na vernieuwing van het Proxmox-certificaat moet je opnieuw koppelen.
3. **Toegang** — maak een alleen-lezen token:
   ```sh
   pveum user add controldeck@pve --comment "ControlDeck read-only"
   pveum acl modify / --users controldeck@pve --roles PVEAuditor
   pveum user token add controldeck@pve controldeck --privsep 0
   ```
   Vul token-ID (`controldeck@pve!controldeck`) en geheim in.
4. **Controleren** — ControlDeck toont versie, clusternaam, nodes en aantallen VM's/containers. Ontbreekt `Sys.Audit` of `VM.Audit`, dan kan niet worden gekoppeld. Heeft het token méér dan `*.Audit`-rechten, dan verschijnt een waarschuwing.
5. **Koppelen** — de verbinding wordt opgeslagen.

Bij een cluster volstaat één adres: de API levert gegevens van alle nodes.

## Geheimen

De verbinding staat in `<datamap>/proxmox/connection.json` (map `0700`, bestand `0600`, atomisch geschreven), buiten git, images en de configuratie-API. Het tokengeheim wordt één keer via HTTPS naar de server gestuurd en nooit teruggegeven, gelogd of in foutmeldingen opgenomen. Bij opnieuw koppelen met dezelfde token-ID mag het geheim leeg blijven. `DELETE /api/proxmox/connection` verwijdert de koppeling.

## Overzicht

ControlDeck bouwt een eigen clusteroverzicht rechtstreeks op de Proxmox VE-API; er is geen Proxmox Datacenter Manager nodig. Bovenaan staan widgets (`GET /api/proxmox/summary`, zelfde 30-secondencache en verouderd-melding):

- **Gasten met het hoogste CPU-gebruik** — top 10 van draaiende VM's en containers.
- **Nodes · CPU** en **Nodes · geheugen** — balk per node, percentage als tekst, exacte waarden in de tooltip. Vanaf 75 % geel, vanaf 90 % rood met △.
- **Taken per categorie** en **Taken per node** over de laatste 48 uur (fout/waarschuwing/OK), via `/nodes/{node}/tasks` van elke online node. Lopende taken tellen niet mee.
- **SDN-zones** — beschikbaar, fout en in behandeling.
- Offline nodes worden apart gemeld en nooit als gezond getoond.

Daaronder staat de takenlijst:

**Proxmox → Overzicht** toont de laatste 50 taken van het hele cluster (`/cluster/tasks`), met CT/VM-namen uit `/cluster/resources`: status (Bezig, OK, Waarschuwing, Fout — met tekst en symbool), starttijd, duur, node, gebruiker en beschrijving. Filters op node en status. Bij een fout of waarschuwing toont "details" de melding van Proxmox.

De backend haalt de gegevens hooguit eens per 30 seconden op (time-out 5 s). Is Proxmox onbereikbaar, dan blijven de laatst bekende taken zichtbaar met de melding **Verouderd**. Zonder koppeling verwijst de pagina admins naar de wizard.

## API en rechten

| Endpoint | Wie |
| --- | --- |
| `GET/PUT/DELETE /api/proxmox/connection`, `POST …/certificate`, `POST …/test` | Alleen admins, met CSRF-token |
| `GET /api/proxmox/tasks` | Gebruikers met toegang tot de module `proxmox` |

## ProxMenux Monitor

ProxMenux Monitor (poort 8008 op elke node) levert gegevens die de Proxmox-API niet heeft. ControlDeck haalt ze op de server op; de browser praat nooit met de monitor en gebruikers zien geen tweede login.

**Koppelen:** Admin → Modules → ProxMenux Monitor.

1. **Cluster-CA** — plak de inhoud van `/etc/pve/pve-root-ca.pem` (openbaar certificaat). Zet in elke monitor HTTPS aan met het Proxmox-hostcertificaat (`/etc/pve/local/pve-ssl.pem`). ControlDeck controleert certificaat én hostnaam tegen deze CA; vernieuwde node-certificaten blijven werken. Http wordt niet geaccepteerd.
2. **Nodes** — vooraf ingevuld vanuit de Proxmox-koppeling (`https://<node-ip>:8008`). Maak per monitor een API-token (Settings → Security → API tokens) en vul het in.
3. **Controleren** — per node: certificaat, token en of de hostname van de monitor gelijk is aan de nodenaam. Een verwisseld adres of token wordt zo geweigerd. Er wordt pas gekoppeld als alle nodes slagen.

De tokens staan in `<datamap>/proxmenux/connection.json` (`0600`), de CA in `cluster-ca.pem`. Tokens worden nooit teruggegeven; bij opnieuw opslaan met dezelfde node en hetzelfde adres mag het token leeg blijven.

**Overzicht:** bovenaan per node een gezondheidskaart (totaalstatus, temperatuur, stroomverbruik, load, host-updates en alleen de afwijkende controles met reden), daaronder **Schijven** (SMART, temperatuur, slijtage; onbekende SMART is nooit "gezond") met ZFS-pools, en **LXC-updates** (beveiligingsupdates eerst).

`GET /api/proxmenux/summary` (module `proxmox`) haalt per node vijf monitor-endpoints parallel op (time-out 15 s). Bekende gegevens worden direct teruggegeven en op de achtergrond ververst (30 s); een onbereikbare node blokkeert de andere niet en toont "Onbekend" of "verouderd". Alleen een whitelist van velden wordt doorgegeven: geen serienummers, IP-adressen of logs.

**Volledige monitor openen:** de webinterface van de monitor bewaart zijn login in de browser. Inloggen met de ControlDeck-sessie (SSO) kan daar niet betrouwbaar op aansluiten; de monitor zelf houdt zijn eigen login.

## Volgende stappen

Nodes, Virtual Machines, Containers en Storage gebruiken dezelfde koppeling. Daarna: netwerkverkeer per node en historie van temperatuur/verbruik uit de monitor.
