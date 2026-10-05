# Modulebeheer

De admin opent **Admin → Modulebeheer** en kiest een tabblad:

| Tabblad | Toont | Doet |
| --- | --- | --- |
| **Installeren** | Alleen modules die nog niet zijn geïnstalleerd of gekoppeld | Installatiewizard (Termix) of koppelwizard (Proxmox VE, ProxMenux Monitor) |
| **Bewerken** | Alleen geïnstalleerde modules | Koppelingen aanpassen (adres, certificaat, tokens; opgeslagen tokens mogen leeg blijven). Termix heeft geen eigen instellingen: Bewerken controleert de installatie en herstelt de koppeling |
| **Verwijderen** | Alleen geïnstalleerde modules | Verwijderwizard: gevolgen → bevestigen door de modulenaam te typen → uitvoeren → afrondingsstappen buiten ControlDeck |

"Geïnstalleerd" betekent: voor Termix een actieve provider, voor koppelingen een opgeslagen verbinding. Een onbekende status telt als niet geïnstalleerd, zodat er nooit iets wordt aangeboden om te verwijderen dat er niet is. Gewone gebruikers gebruiken de modules; het aanpassen van infrastructuur blijft adminwerk.

## Verwijderen

| Module | Wat ControlDeck doet | Zelf afronden |
| --- | --- | --- |
| Proxmox VE | Verbinding en token van de server verwijderen (`DELETE /api/proxmox/connection`) | `pveum user token remove controldeck@pve controldeck` (en optioneel de gebruiker) |
| ProxMenux Monitor | Tokens en cluster-CA van de server verwijderen | Tokens intrekken in elke monitor; ProxMenux blijft op de nodes |
| Termix | Root-worker voert `uninstall-termix.sh` uit: provider uit, Nginx-gateway en runtime-drop-in weg, ControlDeck terug op poort 8080, container verwijderd | — |

Bij Termix kiest de admin **Gegevens bewaren** (standaard; het Docker-volume blijft, opnieuw installeren brengt alles terug) of **Alles verwijderen** (`--delete-data`: verbindingen, sleutels en opnamen definitief weg). Docker en Nginx blijven geïnstalleerd. De verwijderopdracht bevat naast de vaste velden alleen `action: "uninstall"` en de boolean `keepData`; de worker zet dat om in een vaste argumentenlijst.

**Nieuwe installatie:** `scripts/install-lxc.sh` installeert de root-worker automatisch (het roept `install-wizard.sh` aan).

**Na een update:** de root-worker en de scripts onder `/opt/controldeck-integrations/installer` worden bewust niet door een CI-uitrol bijgewerkt; een overgenomen pipeline mag geen root-code kunnen plaatsen. Draai na deze versie eenmalig opnieuw `bash scripts/install-wizard.sh` (of `bash scripts/install-lxc.sh`) als root vanuit een bijgewerkte checkout, De worker meldt een protocolversie in zijn heartbeat (`worker.json`). Is die lager dan de app nodig heeft (`REQUIRED_WORKER` in `backend/installations.py`), dan toont Modulebeheer een melding en worden acties die een nieuwere worker vereisen vooraf geblokkeerd in plaats van halverwege te mislukken. Installatieopdrachten behouden hun oude vorm en blijven ook met een oudere worker werken.

## Installeren

Elk bestand in `config/catalog/` is één catalogusmodule. `kind` is `install` (standaard, bijvoorbeeld Termix) of `connect` (een bestaande toepassing koppelen, zoals Proxmox VE; zie [PROXMOX.md](PROXMOX.md)). Termix is het eerste installatievoorbeeld. De openbare beschrijving staat in `config/catalog/termix.json`. De catalogus bevat uitsluitend metadata; een browser kan geen willekeurig image, shellcommando of downloadadres laten uitvoeren. Nieuwe modules krijgen een expliciet beoordeelde installer, API-controles en normale, boundary- en faaltests.

## Docker

Op de native ControlDeck LXC werkt de Docker-route volledig. De wizard maakt een begrensde installatieopdracht aan. Een afzonderlijke root-worker controleert de opdracht en de actuele adminrechten en voert de vaste Termix-installer uit. De webserver krijgt geen Docker-socket en wordt geen root-proces.

Installatiebootstrap, als root vanuit de checkout:

```sh
bash scripts/install-wizard.sh
```

De worker draait alleen kort via `controldeck-install.timer`, iedere 15 seconden wanneer hij niet bezig is. Privé-opdrachten staan onder `/var/lib/controldeck/installations/queue`; root-beheerde voortgang en uitkomsten onder `results`. Root beheert de installer onder `/opt/controldeck-integrations/installer`. Een hoofdapp-release vervangt deze privileged installer niet automatisch. Installeer een beoordeelde update expliciet opnieuw met het bootstrap-script.

Maximaal één actieve opdracht wordt door de API toegelaten. De worker gebruikt een lock, accepteert alleen Termix/Docker/deze host, weigert extra velden en oude opdrachten, en controleert de admin opnieuw voor uitvoering. Uitkomsten worden atomisch geschreven via geopende directory-handles. Installatielogs staan root-only in `/var/log/controldeck-install.log`; de browser krijgt statusberichten zonder credentials of shelloutput.

Als Termix al draait, meldt het plan dat bestaande data behouden blijven. **Controleren en koppelen** controleert de container en activeert de Terminal-integratie. Een herhaalde installatie wist geen volume en herstart de hoofdapp alleen wanneer de serviceconfig gewijzigd is. Mislukt de gateway/configuratiefase, dan worden de vooraf bestaande instellingen hersteld; het Termix-volume blijft behouden.

## Proxmox LXC

De tweede keuze is **automatisch een nieuwe LXC aanmaken** via de [Proxmox VE Helper-Scripts-route uit de Termix-documentatie](https://docs.termix.site/install/server/proxmox/). Het actuele [Termix Helper-Script](https://github.com/community-scripts/ProxmoxVE/blob/main/ct/termix.sh) gebruikt standaard 4 CPU, 4096 MiB RAM en 10 GiB schijf. Dat is hoger dan het Docker-runtimeprofiel omdat deze route Termix en Guacamole uit broncode bouwt. De wizard toont deze waarden bij de controle.

Deze route is **nog niet uitvoerbaar**: de Proxmox-verbinding, hosttoegang en automatische Helper-Script-adapter zijn nog niet ingericht. De wizard toont dat als blocker en accepteert geen LXC-installatieopdracht. Hij voert geen niet-werkende opdracht uit en valt niet ongemerkt terug op Docker.

Voor het aansluiten zijn Proxmox-hostadres en bestaande toegangsgegevens uit een privébestand nodig. De Helper-Scripts worden op de Proxmox-host uitgevoerd, niet in de ControlDeck-webserver; een API-token alleen vervangt geen host-shelltoegang. De vervolginrichting omvat node, CT-ID, opslag, netwerk, taakcontrole en de beveiligde koppeling van de nieuwe Termix-LXC aan ControlDeck. SSH/consoletoegang en scriptversies worden vóór daadwerkelijke uitvoering gecontroleerd.

## Verificatie

Unit- en contracttests behandelen catalogusstatus, geldige/onbekende keuzes, blokkades, adminrechten, CSRF, queuing, gelijktijdige opdrachten, voortgang, padtraversal en de finite allowlist van de root-worker. Browsercontrole van de vijf stappen en een echte Docker-opdracht op LXC 164 vullen deze tests aan.
