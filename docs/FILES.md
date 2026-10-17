# Files — ontwerp Nextcloud-bestandsbeheer in ControlDeck

Status: **ontwerp, nog niet gebouwd** (2026-10-17). Eis F-04 uit het [functioneel ontwerp](functioneel-ontwerp.md): bestanden bladeren, uploaden en downloaden binnen ControlDeck, met Nextcloud als opslag.

## Doel en afbakening

- Per gebruiker toegang tot de **eigen** Nextcloud-bestanden op `cloud.vanburik.info` (LXC 163, pve-nas), zonder Nextcloud apart te openen.
- Eerste versie: bladeren, downloaden, uploaden (ook groot), map maken, verwijderen (naar de Nextcloud-prullenbak).
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
- **Cloudflare** begrenst een verzoek op 100 MB. Uploads gebruiken daarom Nextcloud **chunked upload v2**: de browser stuurt delen van 50 MB, ControlDeck zet ze door naar `/remote.php/dav/uploads/...` en laat Nextcloud ze samenvoegen. Voortgangsbalk en hervatten per deel.
- De globale aanvraaglimiet van ControlDeck (16 KiB) geldt niet voor de upload-route; daar geldt de deelgrootte als maximum. Nginx `client_max_body_size` wordt daarop afgestemd.
- **Capaciteit**: Gunicorn draait met 1 worker en 2 threads. Een lange download houdt een thread bezet. Fase 2: nginx laat de download zelf doen via `X-Accel-Redirect` naar een interne Nextcloud-locatie (Python controleert alleen rechten en pad), zodat ControlDeck vrij blijft.

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

## Tests (bij de bouw)

- **Normaal**: koppelen, lijst, download, upload (enkel en chunked), map maken, verwijderen.
- **Randgevallen**: lege map, spaties/Unicode in namen, precies 50 MB-deel, laatste kleine deel, diepe paden tot de limiet.
- **Afwijzing**: `..` en absolute paden, verkeerde e-mail bij koppelen, ingetrokken wachtwoord (401), Nextcloud onbereikbaar, overschrijven zonder bevestiging, te groot deel.
- **Authenticatie/autorisatie**: niet aangemeld (401), geen CSRF (403), geen `files`-recht (403), gebruiker A kan nooit het wachtwoord of de bestanden van gebruiker B gebruiken.
- **Download-veiligheid**: HTML/SVG komt altijd als bijlage met `nosniff`.

## Open vragen

1. Koppelen via **Login Flow v2** (aanbevolen) of alleen handmatig app-wachtwoord?
2. Maximale bestandsgrootte voor upload (voorstel: 10 GB via chunks)?
3. Hoort hernoemen/verplaatsen al in de eerste versie?
4. Hele Nextcloud-map tonen, of beginnen in een vaste map (bijvoorbeeld `/ControlDeck`)?

## Bronnen

- [Nextcloud WebDAV basis](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/WebDAV/basic.html)
- [Nextcloud chunked upload v2](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/WebDAV/chunking.html)
- [Nextcloud Login Flow v2](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/LoginFlow/index.html)
