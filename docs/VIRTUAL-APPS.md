# Virtual Apps — Kasm-workspaces starten

**Virtual Apps → Overzicht** toont alle Kasm-workspaces die je kunt starten, elk met het icoon uit Kasm. Een klik start de workspace voor jouw eigen Kasm-account; ControlDeck wacht tot Kasm de sessie *running* meldt (maximaal 45 s) en opent hem dan in een nieuw tabblad. Elke statusvraag vernieuwt het sessietoken, dus de nieuwste link wordt gebruikt. Daarboven staan je **lopende sessies**: **Openen** heropent die sessie met een verse link (zonder een nieuwe te starten), **Stoppen** beëindigt hem. Zoeken filtert op naam, beschrijving en categorie. **Kasm openen** opent het gewone portaal.

## Inrichten (eenmalig, admin)

1. **API-sleutel in Kasm.** Kasm → Admin → Settings → Developers → **Add API Key**, daarna op de **sleutel** (niet op een groep) **Add Permissions**. Geef alleen deze vier rechten (getoetst op Kasm 1.19, [Developer API](https://www.kasmweb.com/docs/latest/developers/developer_api.html)):

   | Recht | Waarvoor |
   |---|---|
   | Images View | workspaces tonen (`get_images`) |
   | Sessions View | lopende sessies tonen (`get_kasms`) |
   | Users Auth Session | starten, status, stoppen en inloggen (`request_kasm`, `get_kasm_status`, `destroy_kasm`, `get_login`) |
   | User | starten, status en stoppen; zonder dit recht weigert Kasm met *403 Unauthorized*. **Global Admin telt hier niet voor mee.** |

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

## Werkplekken, VM-status en VM's wakker maken

De pagina toont twee secties: **Werkplekken (VM's)** (volledige bureaubladen op een server, zoals *Windows Server* of *zorinwerkplek*) en **Apps** (RemoteApps zoals Word, en containers zoals VS Code). Elke tegel waarvan de Kasm-server aan een VM is gekoppeld, toont **Online**, **Opstarten…**, **Offline** of **Status onbekend** (online = VM draait én RDP antwoordt).

Start je een app terwijl de VM uit staat, dan start ControlDeck eerst de VM (en de VM's in `before`, bijvoorbeeld de domeincontroller), wacht tot RDP antwoordt (maximaal 5 minuten) en vraagt dan pas de Kasm-sessie aan. ControlDeck start VM's alleen; het stopt ze nooit.

Koppeling in dezelfde vaultwaarde, onder `kasm.vms`, per **Kasm-server-ID** (Kasm → Admin → Servers):

```json
"vms": {
  "f230d0fed5104941abe3fba719fd67eb": {"node": "pve-amd", "vmid": 101, "host": "192.168.20.101",
                                        "before": [{"node": "pve-amd", "vmid": 136}]},
  "95cb9fd491914dd9a5514d19a3e910ee": {"node": "pve-amd", "vmid": 107, "host": "192.168.20.107"}
}
```

`host` (en optioneel `port`, standaard 3389) bepaalt de bereikbaarheidscontrole; zonder `host` geldt "VM draait" als online.

**Proxmox-recht.** De Proxmox-koppeling is verder alleen-lezen. Geef het token alleen voor deze VM's het recht om te starten (op een Proxmox-node):

```bash
pveum role add ControlDeckPower -privs "VM.PowerMgmt VM.Audit"
for vm in 101 107 136; do
  pveum acl modify /vms/$vm -user controldeck@pve -role ControlDeckPower
  pveum acl modify /vms/$vm -token 'controldeck@pve!controldeck' -role ControlDeckPower
done
```

Zonder dit recht toont de pagina: "ControlDeck mag VM … niet starten: het Proxmox-token mist het recht VM.PowerMgmt".

## Tests

`tests/test_virtual_apps.py`, `tests/test_vm_power.py` en `frontend/tests/virtual-apps.test.mjs`: normaal gebruik, randgevallen (lege lijsten, ID's met streepjes, VM al aan), afwijzingen (vreemde links, uitgeschakelde workspaces, Kasm-fouten, ontbrekend startrecht) en aanmelding/CSRF/modulerechten/koppeling per gebruiker. Starten en stoppen van Kasm-sessies is op 2026-10-18 tegen de echte Kasm-server getest; het wakker maken van VM's nog niet.
