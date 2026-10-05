# Module-installatiewizard

De admin opent **Admin → Modules**. De wizard heeft vijf stappen: module kiezen, Docker of Proxmox LXC kiezen, bestemming en instellingen bekijken, het installatieplan controleren, en installeren met zichtbare voortgang. Gewone gebruikers gebruiken daarna de module; het aanpassen van infrastructuur blijft adminwerk.

Termix is het eerste catalogusvoorbeeld. De openbare beschrijving staat in `config/catalog/termix.json`. De catalogus bevat uitsluitend metadata; een browser kan geen willekeurig image, shellcommando of downloadadres laten uitvoeren. Nieuwe modules krijgen een expliciet beoordeelde installer, API-controles en normale, boundary- en faaltests.

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
