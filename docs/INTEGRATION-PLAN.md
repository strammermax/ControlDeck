# Geselecteerde diensten en integratievolgorde

Datum: 14 oktober 2026. Bron: Camiels dienstenlijst en aangeleverde ARR-suitebeschrijving. Runtimeadressen, accountgegevens, API-sleutels en wachtwoorden zijn niet overgenomen. De hostinventaris moet nog via de bestaande beheerroute worden bevestigd.

## Vastgestelde keuzes

- Bestaande Google-SSO behouden. Geen nieuwe LDAP- of lokale wachtwoordlogin.
- Geheimen en centrale instellingen via Camiels Infisical-client. Nieuwe adapters krijgen vaultreferenties; zie [VAULT.md](VAULT.md).
- Alle gekozen diensten kunnen als gewone app-link worden ontsloten. Een app-link of catalogusicoon bewijst geen werkende API-koppeling.
- Dashboardtegels kunnen bestaande Homepage-apps als verwijzing gebruiken. De bron blijft in Bookmarks beheerd; naam, adres, icoon en opgeslagen integratiecijfers worden daaruit geprojecteerd.

## Diensten

| Dienst | Eerste doel voor ControlDeck | Nog vast te stellen of te bouwen |
| --- | --- | --- |
| Nextcloud | App openen; daarna agenda en meldingen. | Persoonlijke authenticatie, rechten en adapter. |
| Home Assistant | App openen; daarna geselecteerde entiteiten en acties. | Entiteitselectie en aparte lees-/actierechten. |
| Tdarr | App openen; later verwerking, wachtrij en workers. | Adapter en bronversie; specialistische weergaven horen bij C-widgets. |
| SearXNG | Zoekmachine in de centrale zoekbalk. | Werkelijk browseradres instellen; zoeklinks vragen geen nieuwe servercredentials. |
| Kasm | Virtual Apps openen; daarna workspacecatalogus en sessiestart. | Native koppeling, versie en toegangscontract. Kasm is expliciet geselecteerd; sessiestart is nog niet gebouwd. |
| Plex | App openen; later streams en recente media. | Adapter, Homapersoonlijke/gedeelde projectie en vaultreferentie. |
| Open WebUI | App openen met de eigen toegang van de toepassing. | Eventuele statusadapter. Een ingebouwde AI-assistent blijft buiten de MVP. |
| Koopjesbot | App openen; status of resultaten aanleveren. | Eigen API-contract via E1–E4. |
| Prefect | App openen; later flow-/deploymentstatus en acties. | Server/cloudvariant, API-versie en actierechten. |
| MeTube | App openen; later downloadstatus. | Ondersteund API-/sessiecontract en versie. |
| Your Spotify | App openen; later luisterstatistieken. | Adapter en persoonlijke gegevensafbakening. |
| Infisical | Client voor instellingen/geheimen; beheerinterface als link. | Volledige providermigratie; dashboard toont geen secretwaarden. |
| ARR-suite | Afzonderlijke apps en capabilities hieronder. | Leesgegevens, zoeken en acties per adapter. |

Nextcloud stond tweemaal in de lijst en is als één dienst opgenomen.

## ARR-suite

| Groep | Toepassingen | Aanpak |
| --- | --- | --- |
| Organiseren | Radarr, Sonarr, Lidarr, Bazarr, Prowlarr | Afzonderlijke adapters; verbindingen hergebruiken voor ondersteunde gegevens, zoeken en acties. |
| Downloads | qBittorrent, SABnzbd, Slskd | Links; daarna status en afzonderlijk toegestane beheeracties. |
| Aanvragen | Seerr | Bestaande aantallen behouden; B8 voegt zoeken/aanvragen met actierechten toe. |
| Boeken | Calibre, Calibre-Web, LazyLibrarian, Readarr, Booklore | Productidentiteit controleren; daarna concrete gegevens kiezen. |
| Hulpmiddelen | Spottarr, Umlautadaptarr, Notifiarr, Organizr, Droppedneedle | Link; adapter voor concrete ondersteunde capabilities. |
| Database | MariaDB | Onderliggende dienst; geen automatische databasebeheerinterface. |

In de aangeleverde beschrijving gebruikt de service `readarr` een Radarr-image. De naam bewijst daarom niet dat Readarr draait. Dit wordt tijdens inventarisatie gecontroleerd; deze compose wordt niet vanuit dit werk gewijzigd.

## Onderzochte Homarr-bronnen

Referentiecommit: `d7918f5ed3fb64e1e9b82372625f6160a7eb99a2`. Dit onderzoek bewijst geen al werkende ControlDeck-adapter.

- [Nextcloud](https://github.com/homarr-labs/homarr/blob/d7918f5ed3fb64e1e9b82372625f6160a7eb99a2/packages/integrations/src/nextcloud/nextcloud.integration.ts): agenda en meldingen.
- [Home Assistant](https://github.com/homarr-labs/homarr/blob/d7918f5ed3fb64e1e9b82372625f6160a7eb99a2/packages/integrations/src/homeassistant/homeassistant-integration.ts): entiteiten, agenda en expliciete automatiserings-/toggleacties.
- [Tdarr](https://github.com/homarr-labs/homarr/blob/d7918f5ed3fb64e1e9b82372625f6160a7eb99a2/packages/integrations/src/media-transcoding/tdarr-integration.ts): statistieken, workers en wachtrij.
- [Plex](https://github.com/homarr-labs/homarr/blob/d7918f5ed3fb64e1e9b82372625f6160a7eb99a2/packages/integrations/src/plex/plex-integration.ts): sessies en recente media.
- ARR-bronnen staan onder `packages/integrations/src/media-organizer/`, downloadclients onder `download-client/` en Your Spotify onder `stats/providers/your-spotify.ts`.

## Bouwbatches

1. Bestaande appverwijzingen, iconen en opgeslagen cijfers op dashboards; centrale zoekfunctie en eigen zoekmachines, waaronder SearXNG.
2. Adapterregister en vaultreferenties. Bestaande Seerr/Jellyfin- en Proxmox-koppelingen behouden; geselecteerde Nextcloud-, Home Assistant-, media- en ARR-adapters in kleine geteste pakketten toevoegen.
3. Kasm-workspaces en eigen werkdiensten op basis van vastgestelde versies en API-contracten. Gewone app-links kunnen eerder al worden gebruikt.
4. Specialistische C-widgets naar behoefte. Iedere adapter krijgt normaal-, grens- en fouttests plus rechtencontroles vóór een live claim.

Deze codewijzigingen installeren of herconfigureren geen diensten op de Proxmox-hosts. De bestaande toegang en echte dienstversies bepalen de live acceptatie.
