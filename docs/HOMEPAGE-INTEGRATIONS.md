# Native Homepage-integraties

ControlDeck bevat eigen Homepage-code: geen installatie van Homepage of Homarr nodig. Via **Bookmarks → Homepage → Link toevoegen** kies je uit 88 apps uit de gepinde Homarr-catalogus of maak je een eigen link. Naam en icoon worden ingevuld; vul zelf het adres en de groep in. Zoeken filtert op naam/categorie. Alle catalogus-apps kunnen als link worden toegevoegd; alleen Seerr en Jellyfin hebben in deze versie een nieuwe native API-adapter. Voor deze apps kun je vanuit hetzelfde formulier **Link met API-koppeling instellen** kiezen. Andere apps vragen nog geen geheimen zolang hun adapter ontbreekt.

Onder **Bookmarks → Homepage → Integraties** kan een beheerder een koppeling toevoegen, aanpassen en verwijderen. Gebruikers met toegang tot Bookmarks zien de gedeelde tegels en kunnen aantallen vernieuwen.

## Eerste adapters

| Toepassing | Aanmelden voor API | Informatie op de tegel |
| --- | --- | --- |
| Seerr | API-sleutel | Aanvragen, in afwachting, beschikbaar |
| Jellyfin | API-sleutel of gebruikersnaam/wachtwoord | Films, series, afleveringen |

De knop **Verbinding testen en aanmaken** vraagt de echte, beschermde informatie op. Een bereikbare loginpagina is geen geslaagde test. Bij onjuiste ingevulde gegevens, ontbrekende rechten, certificaatproblemen of onbereikbaarheid wordt niets opgeslagen. Ontbreken accountgegevens of API-sleutel volledig of gedeeltelijk, dan vraagt het formulier of je gegevens wilt toevoegen. **Ja** blijft in het formulier; **Nee, alleen link opslaan** maakt uitsluitend een gewone Homepage-link aan, zonder API-test of integratierecord. Wijzigen van een bestaande API-koppeling vereist opnieuw volledige toegangsgegevens. Een mislukte wijziging behoudt de bestaande koppeling. Bij aanpassen moeten toegangsgegevens opnieuw worden ingevuld.

Naam, groep, API-adres, openingsadres en het tonen van een Homepage-tegel zijn instelbaar. Het openingsadres is optioneel; zonder eigen adres wordt het API-adres gebruikt. Onder **Gekoppelde app → Bestaand** kies je een bestaande Homepage-link. De aantallen worden op die tegel getoond zonder een tweede tegel aan te maken. De link zelf blijft behouden wanneer je de integratie verwijdert. Elke link kan aan één integratie gekoppeld worden. Automatische iconen gebruiken de reeds gebundelde lokale service-iconen en volgen het ControlDeck-thema.

Aantallen zijn van de laatste verbindingscontrole; **Aantallen vernieuwen** haalt actuele informatie op zonder de toepassing te wijzigen. Na opnieuw openen toont de pagina de opgeslagen aantallen van de laatste opslag. Er is geen achtergrondpolling of zwaar extra proces. Media en toekomstige widgets kunnen dezelfde adapter en geschoonde `summary` gebruiken. Het Dashboard blijft uitgesteld.

## Aanmelden en rechten

API-aanmelding is apart van browseraanmelding. De gebruikersnaam en het wachtwoord van Jellyfin worden op de server uitgewisseld voor een API-toegangstoken; de browser ontvangt dat token niet. Een geopende site gebruikt haar eigen bestaande sessie of ondersteunde SSO. ControlDeck doet geen automatische browserlogin met deze gegevens.

Deze koppelingen zijn **gedeeld**. Gebruik een account waarvan de zichtbare bibliotheekaantallen gedeeld mogen worden met gebruikers met Bookmarks-rechten. Dit zijn geen persoonlijke Jellyfin-accountkoppelingen. Details van gebruikers, films of aanvragen worden niet teruggestuurd. Seerr ondersteunt hier alleen de API-sleutel; andere providers worden pas aangeboden zodra hun adapter is geïmplementeerd.

## Opslag en herstel

Metadata en versleutelde toegangsgegevens staan in de bestaande private `users.sqlite3`, tabel `homepage_integrations`. De encryptiesleutel wordt met een afzonderlijk doel afgeleid van de bestaande private Flask-sessiesleutel. Maak daarom een consistente backup van de gehele ControlDeck-datamap, inclusief SQLite en de sessiesleutel. Bij verlies/vervanging van die sleutel moeten integraties opnieuw worden gekoppeld.

Geheimen worden nooit in openbare JSON, URLs, afbeeldingen, API-antwoorden of Git opgeslagen. Alle wijzigingen vereisen beheerrechten en CSRF. De Bookmarks-toegangscontrole beschermt ook catalogus, lijst en status. API-verzoeken hebben een timeout van tien seconden, volgen geen redirects en controleren HTTPS-certificaten. Interne HTTP-adressen zijn toegestaan voor homelab-services; kies HTTPS wanneer de service dit ondersteunt.

Maximaal 50 koppelingen. SQLite-transacties voorkomen verloren updates bij meerdere webworkers. Toevoegen en wijzigen zijn atomair; verwijdering verwijdert alleen de eigen koppeling, geen upstream-data of andere Homepage-links.

## Uitbreiden en testen

Elke adapter declareert type, icoon, aanmeldmethoden en mogelijkheden in de catalogus. Voeg een vaste, alleen-lezen adapter toe en projecteer uitsluitend de noodzakelijke velden naar `summary`. Er is geen generieke proxy voor willekeurige endpoints. De frontend bevat geen providergeheimen en heeft geen apart runtimeproces nodig.

Unit- en API-tests dekken normaal gebruik, grenzen en afwijzingen voor invoer, de adapters, wachtwoordauthenticatie, versleutelde opslag, herstart, wijzigen/verwijderen, gelijktijdigheid, limieten, toegang, CSRF en upstream-fouten. Frontendtests dekken tegels en de API-helper. Tests gebruiken synthetische gegevens; live toegang vereist het eigen serviceadres en geldige toegangsgegevens.

Bronnen: [Homarr Jellyfin-adapter](https://github.com/homarr-labs/homarr/blob/dev/packages/integrations/src/jellyfin/jellyfin-integration.ts), [Jellyfin Library API](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Controllers/LibraryController.cs), [Seerr API](https://docs.seerr.dev/api/seerr-api/). De nieuwe implementatie is eigen Python/React-code; de volledige Homarr-stack wordt niet ingebouwd.

De app-catalogus staat in `frontend/lib/app-catalog.json`, met broncommit `4df4ee05998b1777b072770632a6427efbc09149`. De catalogus is geen claim dat alle Homarr-widgets al geporteerd zijn. Voor volledige functionaliteit per integratie moeten de adapter, rechten en tests afzonderlijk worden toegevoegd. Lokale PNG-iconen worden uit de eerder gepinde Dashboard Icons-bron gebruikt; Aria2 en llama.cpp tonen voorlopig initialen.

## Formulier zoals Homarr

De aanmeldmethoden worden met keuzeknoppen getoond. Jellyfin begint met gebruikersnaam/wachtwoord en kan naar API-sleutel worden omgeschakeld. De link **API-sleutel ophalen** wordt van het ingevulde integratieadres afgeleid: voor Jellyfin `/web/index.html#/dashboard/keys`, voor Seerr `/settings/general`. Hij opent in een nieuw tabblad zonder token of wachtwoord in het adres. Bij een ontbrekend of ongeldig basisadres wordt de link niet aangeboden. Het formulier behoudt de ingevulde gegevens na een mislukte verbindingscontrole. App-URL ondersteunt gewone veilige deep links met een fragment, terwijl het API-basisadres geen query/fragment accepteert.

## Stappen voor de beheerder

1. Open **Bookmarks → Homepage → Link toevoegen**, zoek de app en selecteer deze. Naam en lokaal icoon worden automatisch gekozen. Voor een gewone link vul je adres en groep in en kies je **Bewaren**.
2. Kies bij een ondersteunde app **Link met API-koppeling instellen**, of gebruik **Integratie toevoegen** in het integratieoverzicht.
3. Vul **Naam** en **URL** in. De URL is het basisadres dat de ControlDeck-server kan bereiken, inclusief een eventuele submap.
4. Kies de aanmeldmethode. Vul óf gebruikersnaam én wachtwoord in, óf een API-sleutel. **Geheim tonen/verbergen** verandert alleen de zichtbaarheid van het invoerveld. **API-sleutel ophalen** opent de instellingen van de betreffende app; maak daar zelf een sleutel en plak die in het formulier.
5. Laat **App aanmaken of koppelen** aan staan om de aantallen op Homepage te tonen. Bij **Nieuw** kies je een groep en eventueel een ander openingsadres. Bij **Bestaand** selecteer je een aanwezige Homepage-link; reeds gekoppelde links zijn niet beschikbaar. Zonder dit vinkje blijft de koppeling beschikbaar in het integratieoverzicht zonder nieuwe tegel.
6. Kies **Verbinding testen en aanmaken**. Pas na een geslaagde API-controle verschijnt de koppeling. Bij wijzigen heet de knop **Verbinding testen en opslaan**.

| Situatie bij opslaan | Resultaat |
| --- | --- |
| Volledige gegevens, API-controle slaagt | Koppeling en gecontroleerde aantallen worden opgeslagen |
| Volledige gegevens, API-controle faalt | Foutmelding; formulier en bestaande koppeling blijven behouden |
| Gegevens ontbreken; **Ja, gegevens invullen** | Vraag sluit; vul de gegevens in hetzelfde formulier in |
| Gegevens ontbreken; **Nee, alleen link opslaan** | Gewone link met naam, adres, groep en icoon; geen geheimen of API-koppeling |
| Bestaande link gekozen; **Nee, alleen link opslaan** | Bestaande link blijft behouden; geen dubbele link of koppeling |
| Bestaande API-koppeling wijzigen zonder gegevens | Wijziging wordt afgewezen; vul de gegevens opnieuw in |

Een gedeeltelijk ingevuld account telt als onvolledig. De keuze **Nee** bewaart ook dan geen ingevuld wachtwoord of API-sleutel. De gewone link moet nog steeds voldoen aan de normale adres- en veldvalidatie. **Terug naar overzicht** of de sluitknop annuleert het formulier.

## Technische afspraken

| Endpoint | Doel |
| --- | --- |
| `GET /api/homepage/integrations/catalog` | Ondersteunde API-adapters en aanmeldmethoden |
| `GET /api/homepage/integrations` | Metadata en geschoonde aantallen, zonder geheimen |
| `POST /api/homepage/integrations` | Controleren en nieuwe koppeling opslaan |
| `PUT /api/homepage/integrations/{id}` | Opnieuw controleren en koppeling wijzigen |
| `DELETE /api/homepage/integrations/{id}` | Alleen de ControlDeck-koppeling verwijderen |
| `GET /api/homepage/integrations/{id}/status` | Actuele aantallen opvragen |
| `POST /api/homepage/links` | Gewone Homepage-link bewaren bij de keuze zonder API |

De koppeling bevat `type`, `name`, `group`, `url`, `appUrl`, `authMode`, `showApp` en optioneel `linkId`. Geheimen worden alleen bij aanmaken/wijzigen aangeleverd en versleuteld opgeslagen. `linkId` is een positief geheel getal van een bestaande private Homepage-link; booleans, onbekende IDs en dubbele koppelingen worden afgewezen. Bij een bestaande link wordt haar openingsadres gebruikt. De frontend voegt aantallen alleen tijdens weergave toe aan de beschrijving; de oorspronkelijke linkbeschrijving wordt niet overschreven.

De keuze zonder API gebruikt uitsluitend de bestaande link-API en verstuurt naam, adres, groep, beschrijving en icoon. Er wordt geen gedeeltelijke integratie aangemaakt. De frontend bepaalt welke velden zichtbaar zijn; de backend blijft verantwoordelijk voor rechten, CSRF, invoervalidatie en de echte verbindingscontrole.

## Controle en probleemoplossing

Controleer bij een verbindingsfout of het adres vanuit de ControlDeck-container bereikbaar is, of de sleutel/accountrechten juist zijn en of het HTTPS-certificaat geldig is. Een intern DNS-adres dat alleen op je eigen computer werkt, is onvoldoende. De API-sleutelinstellingen openen in jouw browser; dat zegt nog niets over bereikbaarheid vanuit de container. Aantallen tonen de laatste controle en zijn geen continue monitoring.

De tests bevatten normale, grens- en faalgevallen voor aanmeldgegevens, veilige instellingenlinks, openingsadressen, bestaande links en dubbele koppelingen. Een benoemde regressietest bewaakt dat een deep link met fragment intact blijft terwijl een gewoon basisadres consequent wordt genormaliseerd. De browsercontrole gebruikt uitsluitend synthetische gegevens in een lokale omgeving en controleert ook **Ja/Nee** bij ontbrekende gegevens. Zie [TESTING.md](TESTING.md) voor de verplichte controles vóór uitrol.
