# Pagina-indelingen — tegels verplaatsen en vergroten

Naast het [Dashboard](DASHBOARD.md) kan iedere gebruiker de indeling van **Bookmarks** en **Proxmox** aanpassen: tegels verplaatsen en groter of kleiner maken. De indeling is **persoonlijk**: andere gebruikers zien hun eigen indeling, en de gedeelde inhoud (links, groepen, Proxmox-gegevens) verandert niet.

## Gebruikersmodus en bewerkmodus

ControlDeck start in **gebruikersmodus**: knoppen om te bewerken en te beheren zijn verborgen, zodat pagina's rustig blijven. Zet in het gebruikersmenu (rechtsboven, onder **Profiel**) de schakelaar **Bewerkmodus** aan om ze te tonen. De keuze is persoonlijk en wordt bewaard als voorkeur (`editMode`); alleen de waarde `true` zet de bewerkmodus aan.

In gebruikersmodus verborgen:

- **Indeling aanpassen** op Bookmarks en Proxmox.
- Op het Dashboard: **Nieuw dashboard**, **Bewerken**, **Dupliceren**, **Als standaard** en **Dashboard verwijderen**. Het kiezen van een dashboard blijft mogelijk.
- Op Bookmarks (admins/editors): **Link toevoegen**, **Aanpassen** per link en het beheer van koppelingen.

Wie de bewerkmodus uitzet terwijl een wijziging nog niet is opgeslagen, houdt **Opslaan** en **Annuleren** zichtbaar tot die wijziging is afgerond. De schakelaar is alleen weergave: rechten worden altijd door de server gecontroleerd.

## Gebruik

1. Zet de **Bewerkmodus** aan en kies **Indeling aanpassen** boven de pagina.
2. Sleep **⠿** (linksboven op een tegel) om de tegel te verplaatsen. Sleep **↘** (rechtsonder) om hem groter of kleiner te maken. Met het toetsenbord: focus op ⠿ of ↘ en gebruik de pijltjestoetsen.
3. **Opslaan** bewaart de indeling; **Annuleren** verwerpt de wijzigingen; **Standaard herstellen** verwijdert je eigen indeling van die pagina.

Tegels kunnen elkaar niet overlappen; een beweging naar een bezette plaats wordt genegeerd en de laatste geldige positie blijft staan. Op een smal scherm (≤ 600 px) worden tegels buiten de bewerkmodus onder elkaar getoond in leesvolgorde (rij voor rij).

| Pagina | Wat is verplaatsbaar | Raster |
|---|---|---|
| Bookmarks → Homepage | Links binnen hun groep en, net als op het Dashboard, **naar een andere groep** (slepen met ⠿ op een andere groep). Dat is persoonlijk: de gedeelde groep van de link verandert niet (die beheren admins via **Aanpassen**). Tijdens het bewerken blijven lege groepen zichtbaar als doel. | 2 kolommen per groep, tegel 1–4 rijen hoog |
| Proxmox | ProxMenux-gezondheid, gasten, nodes CPU/geheugen, taken per categorie/node, SDN-zones en de takenlijst | 12 kolommen, tegel 1–12 rijen hoog |

Tijdens zoeken in Homepage wordt geen raster getoond; de resultaten volgen wel je persoonlijke volgorde. Nieuwe links of widgets komen automatisch op de eerste vrije plaats; verwijderde links verdwijnen uit je indeling.

## Techniek

Eén gedeelde module, zodat een nieuwe pagina dezelfde bediening krijgt:

| Onderdeel | Rol |
|---|---|
| `frontend/lib/layout-grid.ts` | Rasterregels: plaatsen, botsingen, eerste vrije plaats, vergroten, aanwijzerpositie, samenvoegen van opgeslagen en huidige tegels. Ook het Dashboard gebruikt deze regels. |
| `frontend/components/editable-grid.tsx` | Raster-UI met verplaatsen/vergroten via muis, touch (pointer events) en pijltjestoetsen. |
| `frontend/components/page-layout.tsx` | `usePageLayout(pagina)` (laden, concept, opslaan, herstellen) en de knoppenbalk. |
| `frontend/lib/page-layouts.ts` | API-client en groepen per pagina (`group`, bijvoorbeeld de bookmarkgroep; pagina's met één raster gebruiken `main`). |
| `backend/page_layouts.py` | `GET/PUT/DELETE /api/layouts/<pagina>`; opslag in tabel `page_layouts` van de private `users.sqlite3`. |

Een nieuwe pagina aansluiten: voeg de pagina-ID toe aan `PAGES` in `backend/page_layouts.py` (met de module die toegang geeft) en aan `layoutPages` in `frontend/lib/page-layouts.ts`, bepaal standaardmaten en gebruik `usePageLayout`, `LayoutToolbar` en `EditableGrid`. De pagina-ID `media` is al voorbereid voor de Media-/servicekaarten.

### Beveiliging en grenzen

- Aanmelden is vereist; schrijven vereist CSRF. Toegang per pagina volgt de modulerechten (`bookmarks`, `proxmox`, `media`); onbekende pagina's geven 404.
- Alleen positie en grootte worden opgeslagen, nooit inhoud, adressen of credentials. Tegel-ID's zijn beperkt tot `[A-Za-z0-9:_.-]{1,100}`.
- Maximaal 500 tegels per pagina, 12 kolommen, 300 rijen, tegelhoogte 1–12 en een verzoek van maximaal 128 KiB. De server weigert overlap binnen een groep en dubbele ID's.
- Indelingen zijn per gebruiker (Google-subject) opgeslagen; een andere gebruiker kan ze niet lezen of herstellen.

### Tests

`frontend/tests/layout-grid.test.mjs` en `tests/test_page_layouts.py` dekken normaal gebruik, randgevallen, afwijzingen, aanmelding/CSRF en autorisatie (modulerechten en isolatie tussen gebruikers).
