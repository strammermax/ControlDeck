# Configuratie, modules en providers

ControlDeck leest de configuratie tijdens gebruik via een beveiligd `/api/config`-endpoint. Wijzigingen verschijnen met Refresh of na het ingestelde verversinterval; een frontendbuild of serviceherstart is hiervoor niet nodig. De server valideert JSON, verwijzingen, identifiers, URLs en limieten voordat de browser gegevens ontvangt.

## Bestanden

```text
config/
  controldeck.json          # Titel, logo, thema, interval, hoofdmenu en includes
  accounts.json            # Lege voorbeeldlijst; echte accounts staan buiten Git
  modules/
    core.json              # Huidige hoofdmodules en subpagina's
    kasm.json
    radarr.json
    plex.json
  providers/
    kasm.json               # Type, adres en inschakelen
    radarr.json
    plex.json
  widgets/
    kasm.json               # Definities voor het latere Dashboard
    radarr.json
    plex.json
```

Het hoofdbestand heeft `schemaVersion: 1`, `site`, `menu` en `includes`. Het kan modules/providers/widgets ook rechtstreeks als arrays bevatten. `includes` wijst naar submappen binnen dezelfde configuratiemap. Bestanden daarin worden alfabetisch gelezen; elk bestand bevat één object of een array. Dubbele identifiers, onbekende velden en verwijzingen naar onbekende modules worden afgewezen. Mappen buiten de configuratiemap en geneste dropdowns worden niet ondersteund in deze versie.

## Een toepassing instellen

Voorbeeld `providers/kasm.json`:

```json
{
  "id": "kasm",
  "type": "kasm",
  "label": "Kasm",
  "enabled": true,
  "url": "https://kasm.example.com",
  "tokenEnv": "CONTROLDECK_KASM_TOKEN"
}
```

De meegeleverde voorbeelden voor Kasm, Radarr en Plex staan uit en hebben geen adres. Zodra een provider is ingeschakeld, verschijnen de eraan gekoppelde module en menulink automatisch. `url` is een basisadres zonder gebruikersnaam, wachtwoord of queryparameters. `tokenEnv` is een verwijzing voor toekomstige serverzijdige API-adapters; de waarde en de verwijzing komen niet in het publieke configuratieantwoord. In deze versie leest geen adapter dit token en worden nog geen API-gegevens opgehaald.

Voorbeeld `modules/kasm.json`:

```json
{
  "id": "kasm",
  "enabled": true,
  "title": "Kasm",
  "view": "integration",
  "provider": "kasm",
  "description": "Open Kasm vanuit ControlDeck."
}
```

Een integration-module toont het ingestelde adres en een knop die de toepassing opent. Authenticatie bij die toepassing blijft van de toepassing zelf. `view` kan ook `empty` of `placeholder` zijn. Via `pages` kan een module subpagina's definiëren met `id`, `title` en optionele `description`; de route is dan `module-id/page-id`.

Menu-items hebben `id`, `label`, optionele `icon` en precies één van `route`, `url` of `children`. `enabled: false` verbergt het item. Modules en providers kunnen afzonderlijk worden uitgeschakeld; onbeschikbare routes verdwijnen uit het menu en lege dropdowns worden weggelaten. Pictogrammen: `dashboard`, `virtual-apps`, `bookmarks`, `proxmox`, `media`, `terminal`, `admin`.

Widgets hebben `id`, `enabled`, `title`, `provider` en `route`. Ze worden gevalideerd en alleen voor toegestane modules teruggegeven. **Het Dashboard blijft op verzoek leeg; de widgetweergave volgt later.**

`site` bevat `title`, `subtitle`, `logo` (lokaal absoluut assetpad), `defaultTheme` (dark/light), `refreshSeconds` (5..3600), `footerText`, `supportLabel` en `supportUrl`. Een persoonlijke themavoorkeur gaat vóór het standaardthema.

## Opslag en updates

- LXC: `/var/lib/controldeck/config/controldeck.json` en submappen. `CONTROLDECK_CONFIG` wijst naar het hoofdbestand. Installatie kopieert voorbeelden alleen wanneer nog geen configuratie aanwezig is. Release-deployment overschrijft deze bestanden niet.
- Docker Compose: de hele lokale `config/`-map is alleen-lezen gekoppeld aan `/config`. Voor accounts die admins in de UI wijzigen, gebruik een apart schrijfbaar accountbestand op de datavolume; zie AUTHENTICATION.md.
- Lokale ontwikkeling: de repositoryconfiguratie is de standaard. Een eigen locatie kan via `CONTROLDECK_CONFIG`.

Controleer wijzigingen vooraf:

```bash
python -m backend.configuration /var/lib/controldeck/config/controldeck.json
```

Schrijf bestanden bij voorkeur atomisch (tijdelijk bestand gevolgd door rename). Ongeldige JSON levert HTTP 503 op `/api/config` en `/ready`. Een reeds geopende interface behoudt de laatste geldige configuratie en toont een foutmelding. Dit is geen blijvende cache: na herladen moet een geldige configuratie beschikbaar zijn. `/health` blijft alleen de processtatus melden.

De totale configuratie mag maximaal 256 KiB zijn. Er worden geen dynamische scripts uitgevoerd. Een nieuw JSON-bestand kan een bestaand moduletype instellen; een nieuwe functionele API-adapter of renderer vraagt nog steeds broncode. Gevoelige koppelingen zijn pas toegankelijk na login en serverzijdige rechtencontrole.
