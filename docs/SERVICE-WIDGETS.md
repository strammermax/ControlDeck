# Dienstwidgets

## Gebruik

Dashboard → Bewerken → Module toevoegen. Kies Downloads, Media, Tdarr, Home Assistant, Agenda of Flows en aanbiedingen. Kies daarna de bron bij Aanpassen en sla het dashboard op. Voeg dezelfde module meermaals toe voor verschillende bronnen, bijvoorbeeld beide downloaders of meerdere agenda’s. Elke tegel heeft eigen instellingen en plaatsing. Alle formaten passen binnen het bestaande raster van twaalf kolommen en maximaal zes rijen per tegel.

De systeembibliotheek bevat daarnaast losse CPU-, geheugen-, temperatuur- en CPU-vermogenswidgets. De huisstijl volgt de bestaande tokens voor licht en donker. Er is geen Homarr-code of nieuwe runtime-grafiekbibliotheek gekopieerd.

## Centrale inrichting en rechten

`CONTROLDECK_WIDGET_SOURCES` is een JSON-object in Infisical. De bestaande infisical-secret-client verzorgt alle vaulttoegang. Alleen de noodzakelijke bootstrap staat in een beschermd serverbestand. Voor de huidige installatie is een afzonderlijke appmap `/apps/controldeck/widgets` gebruikt om de bestaande lokale accountlijst niet door oudere vaultinstellingen te vervangen. De runtime-identiteit heeft uitsluitend toegang tot deze map. Het clientprogramma staat buiten de releases in een eigen venv; stel `CONTROLDECK_INFISICAL_CLI` expliciet in wanneer de service-PATH het programma niet vindt. De interne CA staat op een voor de service leesbare, publieke certificaatlocatie. Secrets blijven root-only.

Voorbeeld met uitsluitend fictieve gegevens:

```json
{
  "downloads": {
    "family": "downloads", "kind": "qbittorrent", "title": "Downloads",
    "users": ["owner@example.test"], "url": "https://downloads.example.test",
    "apiKey": "replace-in-vault"
  }
}
```

Iedere bron heeft expliciete `users`. Zowel het bestaande modulerecht als de bronlijst moet toegang geven; ook een beheerder krijgt geen automatische toegang tot andermans persoonlijke bron. Dashboardinstellingen bewaren uitsluitend `sourceId`. De browser krijgt nooit credentials, providerconfiguratie of een aanlevercredential. Intrekken van rechten wordt vóór iedere cachelezing gecontroleerd; bij een geweigerde vernieuwingsaanvraag verdwijnen oude widgetgegevens. Voor tijdelijke verbindingsfouten blijven eerder getoonde gegevens herkenbaar verouderd.

| family | kind | Bestaand recht | Verbinding |
| --- | --- | --- | --- |
| downloads | qbittorrent | media | apiKey (v5.2+) of username/password |
| downloads | sabnzbd | media | apiKey |
| media-widget | plex / seerr | media | apiKey |
| tdarr | tdarr | media | optionele apiKey |
| homeassistant-dashboard | homeassistant-dashboard | monitoring | HTTPS-dashboard-URL |
| calendar | nextcloud-calendar | files | volledige CalDAV-agenda-URL, username/password (appwachtwoord) |
| statistics | prefect | monitoring | URL inclusief `/api`, optioneel apiKey of basic auth |
| statistics | statistics | monitoring | eigen ingestToken van 32–256 URL-veilige tekens |

HTTP voor server-naar-server-verkeer moet per bron expliciet met `allowHttp: true` worden toegestaan. Standaard is HTTPS vereist; TLS-validatie blijft aan, eventueel met `caBundle`. Credentials, query’s en fragments zijn niet toegestaan in bron-URL’s. Geen redirects; antwoorden maximaal 2 MiB en een begrensde wachttijd. De widget vernieuwt elke minuut en gebruikt een servercache van dertig seconden. Persoonlijke advertenties hebben een aparte SQLite-opslag, één laatste payload per bron.

## Home Assistant en agenda

Het Home Assistant-dashboard wordt als iframe geladen en gebruikt zijn eigen sessie. Er worden geen gebruikersnaam, wachtwoord of tokens in het iframe gezet. Een zichtbare link opent het dashboard apart als browser-, frame- of toegangsbeleid embedding verhindert. De gewenste dashboardroute is ingesteld via de vault; de daadwerkelijke ingelogde iframewerking moet nog met de gebruiker worden bevestigd. De browser bereikt het losse Home Assistant-inlogscherm. Een iframe wordt door het bestaande `X-Frame-Options: SAMEORIGIN` geweigerd; een controle vanuit de ControlDeck-container bevestigt HTTP 200 met deze header en zonder CSP. Er is geen beveiligingsinstelling versoepeld. Voor embedding is nog een gerichte inrichting van het externe framebeleid nodig.

CalDAV gebruikt REPORT voor de komende zeven dagen met server-side recurrence-expansie. Hele dagen, tijdzones, overlap, annuleringen en gevouwen regels worden verwerkt. Onuitgebreide herhaling of ongeldige kalenderinhoud geeft een fout in plaats van een misleidend leeg resultaat. Google-browser-SSO is hiervoor niet nodig.

## Persoonlijke Koopjesbot-aanbiedingen

`scripts/koopjesbot_widget_export.py` draait op de Koopjesbot-host en leest de bestaande SQLite-database alleen-lezen. De query selecteert uitsluitend het expliciet ingestelde account, zichtbare profielen, actieve en niet verborgen advertenties die nog niet bekeken zijn. Maximaal tien nieuwste resultaten worden geleverd; lezen markeert niets als bekeken. Bij meerdere accounts wordt geen identiteit geraden of de lijst van een beheerder gedeeld.

De exporter leest `CONTROLDECK_OFFERS_EXPORT` via een eigen beperkte Infisical-identiteit. Die JSON bevat `database`, `email`, `url` en `token`; eventueel `caBundle`. Standaard is het aanleveradres HTTPS. Een expliciet ingestelde `allowHttp: true` is alleen toegestaan voor een letterlijk privé-IP-adres op het interne netwerk. Publiceer niet met secrets in argumenten of URL’s. De exporter en een tweeminutentimer zijn op de Koopjesbot-host geïnstalleerd, met een eigen venv en root-only bootstrap. Unitvalidatie, beperkte vaultlezing, databasebereikbaarheid en bereikbaarheid van ControlDeck zijn gecontroleerd. Na herstel van de Koopjesbot-login met het oorspronkelijke NOT NULL-schema en een geslaagde gebruikersaanmelding is precies één account met hetzelfde e-mailadres gevonden. De persoonlijke producerconfiguratie is daarop ingesteld. De eerste service-uitvoering is geslaagd, de ontvangen payload is in ControlDeck gecontroleerd en de tweeminutentimer is ingeschakeld. Dit account heeft bij acceptatie nul zoekprofielen en nul nieuwe aanbiedingen; daarom is de eerste geldige feed leeg. Er zijn geen accounts of profielen samengevoegd. Nieuwe aanbiedingen verschijnen zodra dit account eigen profielresultaten heeft.

POST `/api/widget-ingest/<sourceId>` accepteert uitsluitend het bearercredential van die bron, geen browsersessie als vervanging. De vrijstelling van sessie/CSRF geldt uitsluitend voor deze POST-endpoint; de machinecredential blijft verplicht. Het aanlevercontract is strikt:

```json
{
  "schemaVersion": 1,
  "generatedAt": "2026-10-15T12:00:00+00:00",
  "offers": [{
    "id": "123", "title": "Voorbeeldaanbieding", "site": "Voorbeeld",
    "url": "https://offers.example.test/item/123", "priceCents": 1250,
    "currency": "EUR", "firstSeenAt": "2026-10-15T11:59:00+00:00"
  }]
}
```

`priceCents` mag null zijn. Onbekende velden, dubbele IDs, onveilige links, ontbrekende tijdzones en meer dan tien aanbiedingen worden geweigerd. Na vijf minuten zonder nieuwe aanlevering meldt de widget verouderde gegevens. Tokenrotatie gebeurt in beide beperkte vaultmappen.

## Operationele acceptatie

De runtime-servicegebruiker heeft de negen geconfigureerde bronnen via de eigen vaultidentiteit succesvol gelezen. De bestaande accounts en Google-configuratie zijn behouden. qBittorrent, SABnzbd, Seerr, Tdarr, Prefect en twee CalDAV-agenda’s gaven geldige API-antwoorden. Dit zijn momentopnamen, geen garantie dat diensten later beschikbaar blijven.

Seerr had nog twee oude interne hostadressen voor Sonarr en Radarr. Beide nieuwe API-adressen zijn met de bestaande keys gecontroleerd, het configuratiebestand is geback-upt en uitsluitend die twee adressen zijn gewijzigd. Alleen Seerr is herstart; aanvragen konden daarna worden gelezen. Plex staat uit; er is geen Plex-bron geactiveerd en de container is niet gestart.

Open live controles: Home Assistant met echte browsersessie/framebeleid; Plex na beschikbaar maken van de dienst; eventueel terugvinden van eerdere Koopjesbot-profielen na expliciete gebruikersbevestiging. Nextcloud Google-aanmelding blijft issue #10.


De widgetrelease is via de volledige GitHub-verificatie en deploystraat gepubliceerd. Productiecontroles bevestigen verplichte aanmelding op leesroutes (401), weigering van ontbrekende/verkeerde aanlevercredentials en verkeerde bron (401), en payloadvalidatie met geldige machineauthenticatie (400 voor de opzettelijk ongeldige lege payload, zonder gegevens te schrijven). Alle negen bronnen zijn voor het bedoelde account toegestaan. De zeven actieve leesadapters zijn vanuit de productie-servicegebruiker met echte vaultconfiguratie gecontroleerd; alle gaven geldige genormaliseerde gegevens.

Een afzonderlijk persoonlijk dashboard **Homelab widgets** is toegevoegd met vier systeemwidgets en negen brontegels. De twee bestaande dashboards en de standaardkeuze zijn behouden. Vooraf zijn accounts, sessiesleutel en SQLite opgeslagen in een afgeschermde serverback-up; checksums bevestigden behoud van accounts en sessies. Dit is een eenmalige persoonlijke inrichting, geen automatische databasewijziging voor andere gebruikers of nieuwe installaties. De resterende live controles staan in GitHub-issue #11.
