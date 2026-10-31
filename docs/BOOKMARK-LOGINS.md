# Persoonlijke aanmelding per bookmark

In bewerkmodus heeft iedere native Homepage-bookmark een knop **Mijn aanmelding**.
Deze instelling is persoonlijk, ook wanneer de bookmark zelf gedeeld is. Een gewone
gebruiker kan zijn eigen aanmelding instellen zonder gedeelde links te mogen wijzigen.
Linkwarden-bookmarks worden hiermee niet gewijzigd.

Ondersteunde methodes:

- **Bestaande Google/SSO-aanmeldroute**: een vaste HTTPS-route op hetzelfde adres
  als de bookmark. De app moet zelf al voor SSO zijn ingericht. Bijvoorbeeld de
  bestaande Nextcloud OIDC-route. Alleen de optionele queryvelden `provider` en
  `realm` zijn toegestaan; geen tijdelijke autorisatiecodes of sessietokens.
- **Kasm API-aanmelding**: API-sleutel, API-geheim en de eigen Kasm-gebruiker-ID.
  De backend vraagt via de ondersteunde `get_login`-API een aanmeldticket op.
  De browser krijgt uitsluitend het tijdelijke, gevalideerde ticketadres.

De gewone klik gebruikt een ingestelde route in hetzelfde tabblad. Zonder
aanmeldinstelling blijft de bookmark een gewone link naar een nieuw tabblad.
Ctrl/Cmd/Shift-klik en het contextmenu blijven gewone browserlinks; de speciale
aanmelding loopt alleen via de normale klik. Een API-aanmeldfout opent niet stil
de gewone app en verwijdert geen bookmark.

## Google-login en API-koppelingen

ControlDecks Google-sessie wordt nooit als Google-token naar een andere app
doorgestuurd. De app doorloopt haar eigen SSO-route; een bestaande Google-sessie
kan een wachtwoordprompt voorkomen, maar accountkeuze, toestemming en MFA kunnen
nog nodig zijn. Het opslaan van een route configureert Google SSO niet in de app.

Een losse Sonarr-, Proxmox- of andere API-sleutel maakt geen browsersessie aan.
API-integraties voor gegevens en acties blijven afzonderlijke koppelingen.
Er is geen universeel formulierinvullen, browserextensie of uitschakeling van
app-authenticatie toegevoegd. Gewone gebruikersnaam/wachtwoordvelden zijn daarom
geen ondersteunde algemene aanmeldmethode.

## Keyvault en rechten

Keyvault/Infisical moet al voor ControlDeck gekoppeld zijn. Per eigenaar en bookmark
wordt een eigen `CONTROLDECK_BOOKMARK_LOGIN_<digest>` geschreven in het bestaande
ControlDeck-secretpad. Account, bookmark-ID en doelselectie komen uit de geverifieerde
sessie en serverconfiguratie; de launch-aanvraag bevat alleen `{}`.

SQLite bewaart uitsluitend eigenaar, bookmark-ID, methode en het gebonden linkadres.
API-geheimen worden niet in SQLite, logs, frontendopslag of de bookmark-URL gezet.
De beheer-API toont geheimen niet terug: vervangen vereist opnieuw invullen.
Aanmelding verwijderen maakt de persoonlijke vaultwaarde leeg en verwijdert de
lokale verwijzing. Een gedeelde bookmark verwijderen verwijdert niet automatisch
de vaultgegevens van alle andere gebruikers; zulke verweesde waarden zijn niet
meer via een launch bruikbaar en kunnen in Keyvault worden opgeruimd.

Een gewijzigd bookmarkadres maakt de bestaande aanmelding ongeldig. De gebruiker
moet dan opnieuw instellen; oude API-gegevens gaan nooit automatisch naar het nieuwe
adres. Gebruikers zien en gebruiken uitsluitend hun eigen aanmeldinstellingen.
Alle mutaties en launches vereisen de actieve sessie, Bookmarks-rechten en CSRF.

Alleen een administrator kan via de API een afwijkend intern Kasm API-adres of een
certificaatvingerafdruk configureren. Het eenvoudige formulier gebruikt het adres
van de bookmark en normale certificaatvalidatie. Interne HTTP-bookmarks blijven
gewone links; deze aanmeldfunctie vereist HTTPS.

## Controle

`tests/test_bookmark_logins.py` controleert normaal gebruik, grenzen, uitval,
CSRF, account- en moduletoegang, persoonlijke isolatie, doelbinding, vaultuitval,
Kasm-fouten en afwijzing van onbeveiligde of niet-ondersteunde aanmeldinstellingen.
`frontend/tests/bookmark-logins.test.mjs` controleert verzoekinhoud en onafhankelijke
validatie van het teruggegeven doeladres. Bestaande Kasm-adaptertests blijven geldig.

Dit levert geen kant-en-klare SSO-inrichting voor alle apps. De eigenaar moet de
bestaande vaste SSO-route of passende Kasm API-gegevens per bookmark invullen.
