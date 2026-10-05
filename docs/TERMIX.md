# Termix Terminal-module

ControlDeck opent Termix binnen de bestaande Terminal-pagina. Termix draait als optionele, afzonderlijke Docker-container in dezelfde Debian LXC. Het hoofdproces van ControlDeck blijft de lichte Python-service met statische frontend.

## Installatie

Installeer eerst ControlDeck, Google SSO en minstens één actief Google-adminprofiel. Voer vanuit een checkout als root uit:

```sh
bash scripts/install-termix.sh
```

Het script installeert Docker Compose en Nginx, start de vastgepinde officiële Termix 2.9.1-image, maakt het eerste adminprofiel en activeert de runtime-provider. Het installeert geen extra Proxmox-container en wijzigt de Cloudflare Tunnel niet. Voor een losse LXC kan dezelfde Docker-container worden gebruikt, maar de huidige bridge verwacht Termix op loopback en moet dan eerst worden aangepast.

## Verkeer en opslag

```text
Browser HTTPS → Cloudflare Tunnel → LXC:8080 (Nginx)
  /               → 127.0.0.1:8081 ControlDeck
  /termix/        → sessiecontrole → 127.0.0.1:8090 Termix Docker
  WebSocket       → dezelfde controle bij de handshake
```

De Docker-poort is uitsluitend aan loopback gebonden. De container heeft maximaal 512 MiB geheugen en één CPU. Guacamole en telemetrie zijn uitgeschakeld; deze installatie is bedoeld voor SSH-terminals en bestandsbeheer. Remote desktop is niet ingericht. De volledige Termix-app draait afzonderlijk; de limiet is geen garantie voor grote aantallen gelijktijdige sessies.

Compose: `/opt/controldeck-integrations/termix/compose.yml`. De persistentie staat in het Compose-volume `controldeck-integrations_termix-data`, gemount op `/app/data`. Maak een consistente backup door Termix eerst te stoppen en het **volledige** volume te bewaren; database, encryptiesleutels en opnamen horen bij elkaar. Bewaar backups privé. Een ControlDeck-release vervangt dit volume niet.

Runtime-provider: `/var/lib/controldeck/config/providers/termix.json`. `enabled: false` sluit nieuwe toegang en laat installatie-informatie op de Terminal-pagina zien. Module: `terminal`, view: `terminal`. Dashboard-widgets worden later toegevoegd.

## Login en rechten

ControlDeck verifieert het Google-account, enabled-status en moduletoewijzing. De server maakt vervolgens een lokaal Termix-profiel met hetzelfde e-mailadres en een willekeurig wachtwoord. Dit wachtwoord wordt niet bewaard of aan de gebruiker getoond. Trusted proxy login koppelt de ControlDeck-rol aan de Termix-rol `admin` of `user`.

Termix staat interne registratie toe voor deze provisioning. Nginx blokkeert de externe registratie-, wachtwoordlogin- en interne auto-session-routes. Wachtwoordlogin/reset zijn ook in Termix uitgeschakeld. De vertrouwde adressen zijn uitsluitend loopback van de ingebouwde Termix-proxy. De gateway overschrijft identiteitsheaders; browserheaders leveren nooit rechten op.

De gateway controleert bij gegevensaanvragen en WebSocket-handshakes dat Termix-tokens bij hetzelfde ControlDeck-profiel en dezelfde rol horen. Een oude token van een ander account wordt afgewezen. Schrijfaanvragen vereisen de juiste HTTPS-Origin; het starten van de sessie vereist tevens de ControlDeck-CSRF-token. Termix-cookies zijn Secure/HttpOnly en beperkt tot `/termix/`. De officiële frontend gebruikt de runtime-meta `termix-base-path` voor API- en socketpaden. Alleen Termix mag binnen dezelfde origin worden geframed; ControlDeck zelf houdt `X-Frame-Options: DENY`.

Nieuwe aanvragen worden geweigerd na logout, uitschakeling of intrekking van Terminal-rechten. **Een reeds verbonden WebSocket wordt niet opnieuw bij elk bericht gecontroleerd.** Beëindig voor directe intrekking bestaande sessies in Termix en sluit geopende terminalvensters. De huidige integratie synchroniseert de rol bij het openen van de Terminal-module, niet via een achtergrondproces. Termix-opslag wordt niet verwijderd bij het uitschakelen van een ControlDeck-account.

SSH-doelhosts en hun toegangsgegevens worden door de gebruiker in Termix ingericht. De installatie importeert geen keyvault-gegevens of sudo-toegang automatisch. Termix gebruikers beheren hun eigen verbindingen; eventuele gedeelde verbindingen volgen Termix-RBAC.

## Beheer en uitrollen

ControlDeck CI blijft Python- en frontend-tests, types, build en Docker-smokechecks uitvoeren vóór uitrollen. De optionele Termix-image wordt bewust niet bij iedere applicatierelease bijgewerkt: versie én digest staan vast in `deploy/termix.compose.yml`. Werk deze gecontroleerd bij met backup en een echte SSH/WebSocket-controle.

Nginx-config: `/etc/nginx/conf.d/controldeck-termix.conf`. ControlDeck systemd drop-in: `/etc/systemd/system/controldeck.service.d/termix.conf`. Die zet Gunicorn op loopback:8081. Het bestaande release/deployment-script controleert nog steeds gateway:8080 en kan de app-release terugzetten.

De tests behandelen normale provisioning, reeds bestaande profielen, storingen, CSRF, verkeerde Origin, onbekende/verlopen/cross-account tokens, rolwijzigingen, rechten en configuratie. Authenticated browser- en containercontroles zijn aanvullend; unit-tests bewijzen geen echte SSH-verbinding of externe bereikbaarheid van iedere doelhost.

## Bronnen en licentie

Termix blijft een afzonderlijke upstream-app met Apache-2.0-licentie; ControlDeck distribueert de upstream-broncode niet. De Compose-installatie gebruikt het officiële image. Bronnen: [Docker-installatie](https://docs.termix.site/install/server/docker/), [Trusted Proxy Authentication](https://docs.termix.site/features/authentication/trusted-proxy/), [Reverse proxy](https://docs.termix.site/setup/reverse-proxy/) en [Termix 2.9.1-broncode](https://github.com/Termix-SSH/Termix/tree/release-2.9.1-tag).
