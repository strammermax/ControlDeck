# Native Homepage-integraties

ControlDeck bevat eigen Homepage-code: geen installatie van Homepage of Homarr nodig. Via **Bookmarks → Homepage → Link toevoegen** kies je uit 88 apps uit de gepinde Homarr-catalogus of maak je een eigen link. Naam en icoon worden ingevuld; vul zelf het adres en de groep in. Zoeken filtert op naam/categorie. Alle catalogus-apps kunnen als link worden toegevoegd; alleen Seerr en Jellyfin hebben in deze versie een nieuwe native API-adapter. Voor deze apps kun je vanuit hetzelfde formulier **Link met API-koppeling instellen** kiezen. Andere apps vragen nog geen geheimen zolang hun adapter ontbreekt.

Onder **Bookmarks → Homepage → Integraties** kan een beheerder een koppeling toevoegen, aanpassen en verwijderen. Gebruikers met toegang tot Bookmarks zien de gedeelde tegels en kunnen aantallen vernieuwen.

## Eerste adapters

| Toepassing | Aanmelden voor API | Informatie op de tegel |
| --- | --- | --- |
| Seerr | API-sleutel | Aanvragen, in afwachting, beschikbaar |
| Jellyfin | API-sleutel of gebruikersnaam/wachtwoord | Films, series, afleveringen |

De knop **Verbinding testen en opslaan** vraagt de echte, beschermde informatie op. Een bereikbare loginpagina is geen geslaagde test. Bij onjuiste gegevens, ontbrekende rechten, certificaatproblemen of onbereikbaarheid wordt niets opgeslagen. Een mislukte wijziging behoudt de bestaande koppeling. Bij aanpassen moeten toegangsgegevens opnieuw worden ingevuld.

Naam, groep, API-adres, openingsadres en het tonen van een Homepage-tegel zijn instelbaar. Het openingsadres is optioneel; zonder eigen adres wordt het API-adres gebruikt. Bestaande gewone Homepage-links blijven apart beheerd; deze versie koppelt nog geen bestaande link aan een integratie. Automatische iconen gebruiken de reeds gebundelde lokale service-iconen en volgen het ControlDeck-thema.

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
