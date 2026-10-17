# Files — ontwerp Nextcloud-bestandsbeheer in ControlDeck

Status: **eerste versie gebouwd** (2026-10-17); nog niet getest tegen de echte Nextcloud. Eis F-04 uit het [functioneel ontwerp](functioneel-ontwerp.md): bestanden bladeren, uploaden en downloaden binnen ControlDeck, met Nextcloud als opslag.

## Hoofddoel

**Vanaf de werkplek bij je eigen bestanden kunnen via ControlDeck** (`https://controldeck.vanburik.info`), zonder VPN, zonder extra software en zonder Nextcloud apart te openen. Op pc en telefoon draait de Nextcloud-client; op de werklaptop mag waarschijnlijk geen client worden geïnstalleerd. Daarom een webvariant die alleen een browser nodig heeft. Gevolgen voor het ontwerp:

- Alles loopt via het bestaande HTTPS-adres achter Cloudflare Access en de ControlDeck-login. Werkplekfirewalls zien alleen gewoon HTTPS-verkeer naar één domein.
- Begin in de **hele** eigen Nextcloud-map, niet in een submap.
- Downloaden is het belangrijkste; dat moet ook bij grote bestanden betrouwbaar zijn. De nginx-downloadroute (`X-Accel-Redirect`, zie onder) komt daarom in de eerste versie in plaats van fase 2.
- Alleen de bestanden in Nextcloud zelf. De NAS wordt bewust niet gekoppeld (keuze 2026-10-17). Mocht dat later toch gewenst zijn, dan kan het met de Nextcloud-app **External storage**; ControlDeck hoeft daarvoor niets extra's te kunnen.
- Op een werkplek-pc blijft niets achter: geen opgeslagen wachtwoorden in de browser, de sessie verloopt na 8 uur.

## Doel en afbakening

- Per gebruiker toegang tot de **eigen** Nextcloud-bestanden op `cloud.vanburik.info` (LXC 163, pve-nas), zonder Nextcloud apart te openen.
- Eerste versie: bladeren, downloaden, uploaden (ook groot), map maken, hernoemen, verplaatsen, verwijderen (naar de Nextcloud-prullenbak).
- Niet in de eerste versie: delen, versies, bewerken in de browser, zoeken, synchronisatie. Daarvoor blijft **Open in Nextcloud** beschikbaar.
- ControlDeck slaat **geen bestanden** op; Nextcloud blijft de enige bron.

## Architectuur

```
Browser ──(sessie + CSRF)──▶ ControlDeck /api/files/... ──(app-wachtwoord, Basic auth)──▶ Nextcloud WebDAV
                                                                     /remote.php/dav/files/<nc-gebruiker>/<pad>
```

- De browser praat alleen met ControlDeck. Het app-wachtwoord verlaat de server nooit.
- ControlDeck is een dunne, gecontroleerde WebDAV-proxy: alleen de handelingen hieronder, binnen de eigen map van de gebruiker.
- Geen extra container of Node-server; past in de bestaande Python-service (eis: lichte runtime).

### Koppelen per gebruiker

Voorkeur: **Nextcloud Login Flow v2**.

1. Gebruiker kiest **Files → Koppelen**. ControlDeck vraagt bij Nextcloud een login-flow aan (`POST /index.php/login/v2`) en opent de getoonde login-URL in een nieuw venster.
2. De gebruiker meldt zich daar aan zoals gewoonlijk (Google/OIDC) en keurt de toegang goed.
3. ControlDeck pollt server-side het `poll`-endpoint en ontvangt `loginName` + **app-wachtwoord**. De gebruiker hoeft niets te kopiëren.
4. Controle: `GET /ocs/v2.php/cloud/user` met dat wachtwoord; het e-mailadres van het Nextcloud-account moet gelijk zijn aan het ControlDeck-account (zelfde regel als Linkwarden). Anders wordt het wachtwoord direct weer ingetrokken en volgt een melding.

Alternatief (terugvaloptie): handmatig een app-wachtwoord maken in Nextcloud → Instellingen → Beveiliging en invullen bij **Files → Mijn koppeling**.

**Ontkoppelen** verwijdert het wachtwoord in ControlDeck en trekt het in bij Nextcloud (`DELETE /ocs/v2.php/core/apppassword`). Het app-wachtwoord is ook in Nextcloud zichtbaar als apparaat "ControlDeck" en daar in te trekken.

### Opslag van het geheim

- Per gebruiker een bestand onder `<data-dir>/nextcloud/users/<hash van subject + Nextcloud-origin>.json`, rechten `0600`, via dezelfde `save_private` als Linkwarden.
- Nooit in API-antwoorden, browseropslag, logs, configuratie-export of Git. Een andere Nextcloud-origin gebruikt nooit het wachtwoord van de vorige.

## API

Alle routes vereisen aanmelding en recht op module `files`; schrijfacties vereisen CSRF.

| Route | Nextcloud | Doel |
|---|---|---|
| `GET /api/files/list?path=` | `PROPFIND` (Depth 1) | Mapinhoud: naam, type, grootte, gewijzigd, ETag |
| `GET /api/files/download?path=` | `GET` (gestreamd) | Bestand downloaden |
| `PUT /api/files/upload?path=` | `PUT` of chunked upload v2 | Bestand uploaden |
| `POST /api/files/folder` | `MKCOL` | Map maken |
| `DELETE /api/files/item?path=` | `DELETE` | Naar de Nextcloud-prullenbak |
| `GET/PUT/DELETE /api/files/connection` | Login Flow v2 / OCS | Koppeling beheren |

### Grote bestanden

- **Streaming**: up- en downloads gaan in blokken door, nooit volledig in het geheugen (LXC 164 heeft weinig RAM).
- **Cloudflare** begrenst een verzoek op 100 MB. Uploads gebruiken daarom Nextcloud **chunked upload v2**: de browser stuurt delen van 32 MB, ControlDeck zet ze door naar `/remote.php/dav/uploads/...` en laat Nextcloud ze samenvoegen. Voortgangsbalk en hervatten per deel.
- De globale aanvraaglimiet van ControlDeck (16 KiB) geldt niet voor de upload-route; daar geldt de deelgrootte (32 MB) als maximum, onder nginx `client_max_body_size 50m`. Nginx buffert `/api/files/` niet (`proxy_request_buffering off`, `proxy_buffering off`, time-outs 900 s).
- **Capaciteit**: Een lange download houdt een Gunicorn-thread bezet; daarom draait Gunicorn nu met 6 in plaats van 2 threads. Downloads gaan in blokken van 1 MB door Python. Als dat in de praktijk te zwaar blijkt, laat nginx de download zelf doen via `X-Accel-Redirect` (Python controleert dan alleen rechten en pad).

## Beveiliging

- **Pad**: alleen relatieve paden binnen de eigen Nextcloud-map. Geen `..`, geen besturingstekens, maximaal 1024 tekens; elk deel wordt apart URL-gecodeerd. Antwoorden van Nextcloud worden geprojecteerd naar naam/type/grootte/datum.
- **Downloads** krijgen `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff` en een strikte CSP, zodat een geüpload HTML- of SVG-bestand nooit als pagina op het ControlDeck-domein draait.
- **Upstream**: TLS-verificatie aan, vaste time-outs, geen redirects volgen, foutmeldingen zonder antwoordbody of geheimen.
- **Overschrijven**: uploaden gebruikt standaard `If-None-Match: *`; bij een bestaand bestand vraagt de UI om bevestiging.
- **Verwijderen**: altijd bevestigen; het item gaat naar de Nextcloud-prullenbak en is daar te herstellen.
- **Bewerkmodus**: map maken en verwijderen alleen zichtbaar in de [bewerkmodus](LAYOUTS.md); bladeren, downloaden en uploaden altijd. De server controleert rechten onafhankelijk daarvan.

## Gebruikersinterface

- Kruimelpad, lijst met icoon, naam, grootte en datum; sorteren op naam/datum/grootte.
- Uploaden via knop en slepen naar de lijst, met voortgang per bestand en annuleren.
- Melding met **Koppelen** als er nog geen koppeling is; **Open in Nextcloud** voor alles wat hier niet kan.
- Later als dashboardmodule: "Recente bestanden" of een vaste map.

## Inrichting

1. Eenmalig als root de nieuwe nginx-locatie en de service met 6 threads plaatsen. De installatiewizard doet dit **niet** (die kopieert alleen naar de installatiemap): installeer `deploy/termix-gateway.conf` als `/etc/nginx/conf.d/controldeck-termix.conf` en `deploy/termix-app.conf` als `/etc/systemd/system/controldeck.service.d/termix.conf`, daarna `nginx -t`, `systemctl reload nginx`, `systemctl daemon-reload` en `systemctl restart controldeck`.
2. Als admin: **Files** openen en het Nextcloud-adres invullen (`https://cloud.vanburik.info`). Dit wordt opgeslagen in `<data-dir>/files/server.json`.
3. Iedere gebruiker: **Koppelen met Nextcloud**, aanmelden in het nieuwe venster en de toegang goedkeuren.

Hernoemen, verplaatsen, nieuwe map, verwijderen en ontkoppelen staan alleen in de bewerkmodus. Bladeren, downloaden en uploaden altijd.

## Tests

- **Normaal**: koppelen, lijst, download, upload (enkel en chunked), map maken, verwijderen.
- **Randgevallen**: lege map, spaties/Unicode in namen, precies 50 MB-deel, laatste kleine deel, diepe paden tot de limiet.
- **Afwijzing**: `..` en absolute paden, verkeerde e-mail bij koppelen, ingetrokken wachtwoord (401), Nextcloud onbereikbaar, overschrijven zonder bevestiging, te groot deel.
- **Authenticatie/autorisatie**: niet aangemeld (401), geen CSRF (403), geen `files`-recht (403), gebruiker A kan nooit het wachtwoord of de bestanden van gebruiker B gebruiken.
- **Download-veiligheid**: HTML/SVG komt altijd als bijlage met `nosniff`.

## Open vragen

1. ~~Login Flow v2 of handmatig~~ Besloten: Login Flow v2, handmatig app-wachtwoord als terugvaloptie.
2. ~~Maximale uploadgrootte~~ Besloten: 10 GB per bestand, in delen van 32 MB.
3. ~~Hernoemen/verplaatsen~~ Besloten: ja, in de eerste versie (alleen in de bewerkmodus).
4. ~~Hele map of vaste map~~ Besloten: hele eigen Nextcloud-map.
5. ~~Waar staan de bestanden~~ Besloten: alleen Nextcloud. De NAS wordt niet gekoppeld; zo blijven synchronisatie en de NAS-inrichting ongewijzigd.

## Bronnen

- [Nextcloud WebDAV basis](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/WebDAV/basic.html)
- [Nextcloud chunked upload v2](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/WebDAV/chunking.html)
- [Nextcloud Login Flow v2](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/LoginFlow/index.html)
