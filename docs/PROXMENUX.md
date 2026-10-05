# ProxMenux Monitor: installeren en koppelen

ProxMenux Monitor draait op elke Proxmox-node (poort 8008) en levert gegevens die de Proxmox-API niet heeft: een gezondheidsoordeel per node, CPU-temperatuur, stroomverbruik, SMART/slijtage van schijven, ZFS-pools en updates van Helper-Script-containers. ControlDeck haalt deze gegevens alleen-lezen op de server op en toont ze onder **Proxmox → Overzicht**. Gebruikers zien geen tweede login.

ProxMenux is een afzonderlijk open-sourceproject ([MacRimi/ProxMenux](https://github.com/MacRimi/ProxMenux), GPL-3.0). ControlDeck gebruikt alleen de HTTP-API en bevat geen ProxMenux-code.

## Overzicht van de route

```text
Admin → Modules → ProxMenux Monitor
  1. Module          kies ProxMenux Monitor
  2. Cluster-CA      plak /etc/pve/pve-root-ca.pem
  3. Nodes           ControlDeck zoekt per node de monitor en toont wat er nog moet gebeuren
  4. Controleren     certificaat, token en hostname per node
  5. Koppelen        tokens worden op de server opgeslagen
```

Voorwaarde: de [Proxmox-koppeling](PROXMOX.md) is aanwezig. De wizard vult de nodes en hun adressen daaruit in (`https://<node-ip>:8008`).

## Stap 2 — Cluster-CA

Alle Proxmox-nodes van een cluster hebben een certificaat dat is ondertekend door dezelfde clusterautoriteit. Toon die op een willekeurige node:

```sh
cat /etc/pve/pve-root-ca.pem
```

Plak de volledige inhoud, inclusief de `BEGIN`/`END`-regels. Dit is een openbaar certificaat. Gebruik nooit `pve-root-ca.key`. ControlDeck controleert met deze CA het certificaat én de hostname/het IP van elke monitor; vernieuwde node-certificaten blijven daardoor werken zonder opnieuw te koppelen.

## Stap 3 — Nodes en installatie

Kies **Monitors zoeken**. ControlDeck controleert per node, zonder token, in welke toestand de monitor is:

| Toestand | Betekenis | Wat te doen |
| --- | --- | --- |
| ✓ **Klaar om te koppelen** | HTTPS met clustercertificaat en login aan | API-token invullen |
| △ **Login staat uit** | Monitor bereikbaar, maar zonder login | Settings → Security: login aanzetten, daarna API-token maken |
| △ **Certificaat past niet bij de cluster-CA** | HTTPS met een ander certificaat, of verkeerd adres | Settings → SSL / HTTPS: Proxmox-hostcertificaat kiezen; adres controleren |
| △ **Alleen http** | Monitor draait, HTTPS staat uit | Settings → SSL / HTTPS aanzetten met het Proxmox-hostcertificaat |
| ✗ **Niet gevonden** | Geen monitor op dit adres | ProxMenux installeren (zie hieronder) |

Voer de stappen uit en kies **Opnieuw controleren**. **Nodes testen** is pas beschikbaar als alle nodes klaar zijn en een token hebben. ControlDeck stuurt nooit een token over http; de http-controle vraagt alleen de openbare status op.

### ProxMenux installeren op een node

In een shell op de node, als root (Proxmox-webinterface → node → Shell, of SSH):

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/MacRimi/ProxMenux/main/install_proxmenux.sh)"
```

De Monitor wordt automatisch meegeïnstalleerd als systemd-service `proxmenux-monitor.service` en is daarna bereikbaar op `http://<node-ip>:8008`. Controleer het script vooraf in de [officiële repository](https://github.com/MacRimi/ProxMenux); ControlDeck voert het niet zelf uit (zie [Waarom niet automatisch](#waarom-niet-automatisch)).

### De monitor inrichten

Open de monitor in je browser en:

1. **Settings → SSL / HTTPS** — HTTPS aanzetten met het **Proxmox-hostcertificaat** (`/etc/pve/local/pve-ssl.pem`). De pagina is kort onbereikbaar terwijl de service herstart; open daarna `https://<node-ip>:8008`.
2. **Settings → Security** — login aanzetten (eigen gebruikersnaam en wachtwoord; 2FA kan).
3. **Settings → Security → API tokens** — een token maken met de naam `controldeck`. Kopieer het direct; het wordt maar één keer getoond.

## Stap 4 en 5 — Controleren en koppelen

Per node controleert ControlDeck het certificaat, het token en of de hostname van de monitor gelijk is aan de nodenaam. Een verwisseld adres of token (bijvoorbeeld het token van pve-amd bij het adres van pve-intel) wordt geweigerd. Er wordt pas gekoppeld als alle nodes slagen.

## Opslag en beveiliging

| Gegeven | Waar | Toegang |
| --- | --- | --- |
| API-tokens per node | `<datamap>/proxmenux/connection.json` | Bestand `0600`, map `0700`; nooit naar de browser, logs of configuratie-API |
| Cluster-CA | `<datamap>/proxmenux/cluster-ca.pem` | Openbaar certificaat |

- Koppelen, testen en zoeken: alleen admins, met CSRF-token.
- Gegevens bekijken (`GET /api/proxmenux/summary`): gebruikers met toegang tot de module `proxmox`.
- Alleen een whitelist van velden gaat naar de browser: geen serienummers, IP-adressen, MAC-adressen of logs.
- Opnieuw opslaan met dezelfde node en hetzelfde adres: het tokenveld mag leeg blijven.
- Een token intrekken: in de monitor (Settings → Security → API tokens). Ontkoppelen in ControlDeck: `DELETE /api/proxmenux/connection`.

## Gedrag en storingen

- Per node worden vijf monitor-endpoints parallel opgehaald (time-out 15 s).
- Bekende gegevens worden direct getoond en elke 30 s op de achtergrond ververst; alleen de allereerste keer wordt gewacht.
- Een onbereikbare node blokkeert de andere niet. Hij toont **? Onbekend** of de laatst bekende gegevens met **verouderd**, nooit "gezond".
- Schijven met onbekende SMART-status zijn **Onbekend**, niet "OK".

## Volledige monitor openen

De webinterface van de monitor bewaart zijn eigen login in de browser. Inloggen met de ControlDeck-sessie (SSO) sluit daar niet betrouwbaar op aan; de monitor zelf houdt zijn eigen login. Alle relevante gegevens staan in ControlDeck.

## Waarom niet automatisch

Software op een Proxmox-host installeren vereist root-shelltoegang tot de node; het alleen-lezen API-token kan dat niet. Een ControlDeck met root-SSH naar alle nodes zou bij misbruik volledige toegang tot het cluster geven. Daarom begeleidt de wizard de installatie en voert de beheerder het commando zelf uit. Een eventuele automatische route wordt apart ontworpen (beperkt account, vaste lijst toegestane scripts, bevestiging en auditregistratie) en geldt dan ook voor de Termix-LXC-installatie. Zie [issue #1](https://github.com/strammermax/ControlDeck/issues/1).
