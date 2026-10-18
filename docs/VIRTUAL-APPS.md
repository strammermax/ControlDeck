# Virtual Apps — Kasm-workspaces starten

**Virtual Apps → Overzicht** toont alle Kasm-workspaces die je kunt starten, elk met het icoon uit Kasm. Een klik start de workspace voor jouw eigen Kasm-account en opent hem in een nieuw tabblad. Daarboven staan je **lopende sessies**, met **Openen** en **Stoppen**. Zoeken filtert op naam, beschrijving en categorie. **Kasm openen** opent het gewone portaal.

## Inrichten (eenmalig, admin)

1. **API-sleutel in Kasm.** Kasm → Admin → Settings → Developers → **Add API Key**. Geef de sleutel alleen deze rechten:

   | Recht | Waarvoor |
   |---|---|
   | Images View | workspaces tonen (`get_images`) |
   | Sessions View | lopende sessies tonen (`get_kasms`) |
   | Sessions Create | een workspace starten (`request_kasm`) |
   | Sessions Delete | een sessie stoppen (`destroy_kasm`) |
   | Users Auth Session | inloggen via de Kasm-module (`get_login`) |

2. **Kasm-gebruiker per ControlDeck-account.** Kasm → Admin → Users → open de gebruiker en kopieer het **User ID** (een UUID). ControlDeck maakt geen Kasm-gebruikers aan.
3. **In Infisical**, omgeving **Production**, map **`/apps/controldeck/widgets`** (waar ook `CONTROLDECK_WIDGET_SOURCES` staat), de JSON-waarde `CONTROLDECK_APP_LAUNCHES` (dezelfde als voor [automatisch aanmelden](APP-LAUNCHES.md)):

   ```json
   {"kasm": {"url": "https://kasm.example.org", "apiKey": "…", "apiSecret": "…",
             "users": {"jij@example.org": "11111111-2222-3333-4444-555555555555"},
             "apiUrl": "https://kasm.home",
             "apiFingerprint": "06:A5:…:C7:88"}}
   ```

   - `url`: het publieke HTTPS-adres zonder pad; dit opent de browser.
   - `apiUrl` (optioneel): het adres waarmee de **server** de API aanroept. Nodig als het publieke adres achter een aanmeldproxy staat, zoals Cloudflare Access: dan stuurt elk API-verzoek door naar een aanmeldpagina ("het adres stuurt door naar een aanmeldpagina").
   - `apiFingerprint` (optioneel): SHA-256-vingerafdruk van het certificaat op `apiUrl`, voor Kasm's standaard zelfondertekende certificaat (naam `kasm`, past niet bij de hostnaam). Alleen precies dat certificaat wordt geaccepteerd, zoals bij [Proxmox](PROXMOX.md). Opvragen op de ControlDeck-server: `echo | openssl s_client -connect kasm.home:443 2>/dev/null | openssl x509 -noout -fingerprint -sha256`.

   ControlDeck leest de waarde bij elk verzoek; een herstart is niet nodig.

Zonder inrichting toont de pagina "Kasm is nog niet ingericht"; zonder gekoppelde gebruiker "Er is geen Kasm-account aan jouw profiel gekoppeld".

## Beveiliging

- API-sleutel en -geheim blijven op de server; de browser krijgt alleen namen, iconen en de startlink.
- De Kasm-gebruiker komt uit de vault op basis van je ControlDeck-e-mail, nooit uit de browser. Starten accepteert alleen een lege body; alleen ingeschakelde workspaces kunnen worden gestart.
- Je ziet en stopt alleen je **eigen** sessies; de server controleert dat voor het stoppen.
- De startlink moet Kasm's eigen route `#/connect/kasm/…` op hetzelfde adres zijn.
- Iconen: een Kasm-thumbnailpad op het Kasm-adres (zonder `..`), of een in Kasm ingebedde PNG/JPEG/WebP (max. 256 KB, inhoud gecontroleerd). Externe icoonadressen en SVG worden niet geladen; dan toont de tegel de eerste letter. Stel een icoon in via Kasm → Admin → Workspaces → *Thumbnail URL* (bijvoorbeeld `img/thumbnails/<naam>.png`).
- Toegang volgt de module `virtual-apps`; schrijfacties vereisen CSRF. Kasm-fouten krijgen status 424 (niet 502, dat Cloudflare zou vervangen), met de melding van Kasm.

## Tests

`tests/test_virtual_apps.py` en `frontend/tests/virtual-apps.test.mjs`: normaal gebruik, randgevallen (lege lijsten, ID's met streepjes), afwijzingen (vreemde links, uitgeschakelde workspaces, Kasm-fouten) en aanmelding/CSRF/modulerechten/koppeling per gebruiker. De echte Kasm-API is nog niet getest; daarvoor is eerst de inrichting hierboven nodig.
