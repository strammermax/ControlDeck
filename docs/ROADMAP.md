# Roadmap

Eén lijst met alles wat nog open staat: ontbrekende functionaliteit, ideeën, geparkeerde punten en technische verbeteringen. Stand: 18 oktober 2026. Uitleg en onderbouwing staan in de [gap-analyse en het codeonderzoek](CODE-AUDIT-HERGEBRUIK.md) en het [functioneel ontwerp](functioneel-ontwerp.md).

**Prioriteit:** H = zichtbaar gat of eis uit een afgeronde fase · M = volgende verdieping · L = wens. **Omvang:** S = uren tot een dag · M = enkele dagen · L = meer.

Werkwijze: nieuwe functies bouwen op de gedeelde bouwstenen (B1–B8, F1–F6 in het codeonderzoek), met normaal-, rand-, faal- en autorisatietests; documentatie per stap bijwerken. Een afgevinkt punt verhuist naar de [changelog](CHANGELOG.md).

## 1. Eerst (prioriteit H)

- [ ] **502-bug** — 8 routes (Proxmox 4×, Linkwarden, Homepage-integraties, Cronjobs) geven 502; Cloudflare verbergt dan de melding. Oplossen met `UpstreamError` (B1) + regressietest per route. *S*
- [ ] **Auditlog (F-17)** — `audit(action, target, result)` in SQLite voor accounts, module-installaties, koppelingen, VM starten, Kasm stoppen, Files verwijderen/verplaatsen, Bookmarks-beheer; Admin-pagina "Activiteit" (alleen-lezen, filter, export). *M*
- [ ] **Monitoring-pagina (F-07)** — ProxMenux-gezondheid, Beszel, Uptime-status, Home Assistant; per regel bron en actualiteit (F-14). *M*
- [ ] **Meldingen** — e-mail/ntfy/Telegram/push bij offline node, mislukte cronjob, volle opslag, verlopen koppeling, verlopen licentie, Kasm-sessiegrens. *M*
- [ ] **Zoeken uitbreiden** — ook Linkwarden-bookmarks, Virtual Apps-workspaces, Proxmox-gasten en Files; één zoekbron per module. *M*
- [ ] **Menu opschonen** — `proxmox/containers` (dubbel met VM's & Containers), en placeholders (`monitoring`, `radarr`, `plex`, `admin`) verbergen tot ze bestaan. *S*
- [ ] **Geplande backup + hersteltest** — dagelijkse SQLite-backup (backup-API) + private bestanden naar PBS of Nextcloud; maandelijkse hersteltest. *M*

## 2. Functionaliteit per module (prioriteit M/L)

### Proxmox
- [ ] Acties op de inventaris: VM/container starten, stoppen, herstarten, met bevestiging, rechten (VM.PowerMgmt per pool) en auditlog (fase 3). *M*
- [ ] Back-up-/PBS-status per gast. *M*
- [ ] Meldingen bij offline nodes (via Meldingen). *S*

### Virtual Apps (Kasm) — deels geparkeerd
- [ ] Startrecht in Proxmox: pool `kasm` + rol `ControlDeckPower` (zie [VIRTUAL-APPS.md](VIRTUAL-APPS.md)). *S*
- [ ] DC01 als afhankelijkheid van WinServer (`before`). *S*
- [ ] Ongebruikte Kasm-VM's automatisch uitzetten na X uur, met energieverbruik in kWh/€. *M*
- [ ] Melding vóór de Kasm Community-grens (5 sessies). *S*
- [ ] Dashboardmodule "Mijn apps". *S*
- [ ] Domein opheffen en DC01 uitfaseren: lokaal account op WinServer, Kasm-RDP-account omzetten, WinServer uit het domein, DC01 eerst uitzetten en later verwijderen. Geen domeincontroller op de RDS-host. *M*

### Files
- [ ] Downloads via nginx (`X-Accel-Redirect`) voor grote bestanden. *S*
- [ ] Delen via link, zoeken, voorbeeld (afbeelding/PDF), versies, prullenbak terugzetten. *M*
- [ ] Dashboardwidget "Recente bestanden". *S*

### Media
- [ ] Submenu's Downloads, Requests, Movies, Series, Audio, Plex, Jellyfin (eis 2026-10-17). *M*
- [ ] Pagina-indeling `media` (verplaatsen/vergroten) aansluiten, of de pagina-ID verwijderen. *S*
- [ ] Jellyfin als servicewidget (nu alleen in het Homepage-integratiepad). *S*

### Bookmarks
- [ ] Favorieten (F-12): ster op links/apps + favorietenwidget. *S*
- [ ] Linkwarden-bookmarks ook in de persoonlijke indeling. *S*
- [ ] Automatische synchronisatie van OPNsense-Nginx-hosts en Dnsmasq-reserveringen naar een groep "Infra (automatisch)", met de regel *vanburik.info gaat voor*; dode links markeren. *M*

### Beheer
- [ ] Instellingenpagina (`admin`) voor site-instellingen via de UI. *S*
- [ ] Providers-pagina met echt beheer i.p.v. statische lijst. *M*
- [ ] Overzicht "Verbindingen": Proxmox, ProxMenux, Linkwarden, Kasm, Nextcloud, vault, met gezondheid. *M*
- [ ] Gezondheidspagina: vault, schijfruimte, versie, laatste deploy, certificaatgeldigheid (Kasm-pin, Proxmox-pin). *S*
- [ ] "Config-upgrade" in de installer: nginx, systemd-drop-in en private menu bijwerken met diff, backup en `nginx -t` (een release doet dat nu niet). *M*

### Gebruikers
- [ ] "Mijn koppelingen": Linkwarden-token, Files/Nextcloud, Kasm op één profielpagina met status en intrekken. *S*
- [ ] Gezins-/gastrol met alleen Media en enkele Bookmarks. *S*

### Algemeen
- [ ] Statusmodel consequent: gezondheid × actualiteit × verbinding (F-14, hoofdstuk 7 van het functioneel ontwerp). *M*
- [ ] Mobiel (F-19): Virtual Apps-stijl, touch-bediening van slepen/vergroten op echte apparaten testen. *S*
- [ ] Vertaling: vaste Nederlandse teksten naar `lib/i18n.ts` (nu 17 sleutels; taalvoorkeur *en* bestaat). *M*

## 3. Ideeën (uit de praktijk van oktober 2026)

- [ ] **Zelfherstel van diensten** — systemd-/Docker-status via de node-agent, melding en (instelbaar) automatisch herstarten; aanleiding: Linkwarden lag 1,5 dag plat na een OOM-kill. *M*
- [ ] **Updates-overzicht** — pakket-, Docker-image- en Proxmox-updates per LXC/VM, bijwerken via de agent met bevestiging en auditlog (open idee #1). *M*
- [ ] **DHCP-/DNS-overzicht** — OPNsense-reserveringen, Proxmox-MAC's en werkelijke ARP-adressen naast elkaar, afwijkingen gemarkeerd. *M*
- [ ] **Vervaldatums bewaken** — certificaten, API-sleutels, RDS-graceperiode, Kasm-licentiegrens. *S*
- [ ] **Mobiele app (PWA)** met pushmeldingen. *M*
- [ ] **Snelle acties in Ctrl K** — "start Windows Server", "open Word", "herstart Linkwarden", met dezelfde rechten en bevestiging. *S*
- [ ] **Wake-on-LAN** voor fysieke pc's (VeraPC, DevPC, rescuepc) via de agent. *S*
- [ ] **"Nieuw in deze versie"** na een deploy, plus waarschuwing als serverconfiguratie achterloopt. *S*

## 4. Technische verbeteringen (codeonderzoek)

Volgorde uit het [codeonderzoek](CODE-AUDIT-HERGEBRUIK.md#ontwerp-herbruikbare-bouwstenen-klassen-en-functies); elke ronde los terug te draaien.

- [ ] **Ronde 0** — B1 `UpstreamError` (zie 502-bug bovenaan).
- [ ] **Ronde 1** — T1 `conftest.py`-fixtures + `mockFetch`; F1 `requestJson`/`ApiError`.
- [ ] **Ronde 2** — F2 `usePolledResource` + F3 `useInventory` voor de drie Proxmox-inventarissen.
- [ ] **Ronde 3** — B5 `ProxmoxConnection`; B3 `PrivateFile`; B4 `PersonalSecretStore` met migratie van Linkwarden-tokens (e-mail → subject).
- [ ] **Ronde 4** — B2 `PermissionContext`/`require_module` en Blueprints.
- [ ] **Ronde 5** — F4 `StatusBadge`/`Meter`/`AsyncState`/`WidgetFrame` + kleurtokens; F5 `formatBytes`/URL-hulpfuncties; F6 `defineFeature`-register; dashboard op `EditableGrid`.
- [ ] **Ronde 6** — B6 `TtlCache`, B7 `HttpClient`, B8 `ConfigRepository`; connectorconsolidatie Homepage-integraties/servicewidgets.
- [ ] **Testdekking** — tests voor `backend/app_icons.py`; browser-/E2E-tests (slepen, uploaden, starten).

## 5. Infrastructuur (buiten ControlDeck, wel genoteerd)

- [ ] Linkwarden: `Restart=on-failure` in de systemd-unit (LXC 119) en schijfruimte (86 % vol op 17 oktober).
- [ ] OPNsense-DHCP: DNS-optie op DC01 (`192.168.20.136`) zolang het domein bestaat.
- [ ] Kasm-iconen na een Kasm-update terugzetten uit `/opt/kasm/custom-thumbnails/` (LXC 126).
- [ ] Hoofdmap `D:\Project\ControlDeck` gelijkzetten met `main` (oude ongecommitte kopie van het widgetwerk).
