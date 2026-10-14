# Infisical en centrale instellingen

## Gewenste richting

Infisical is de centrale bron voor geheimen en applicatie-instellingen. ControlDeck gebruikt Camiels `infisical-secret-client`, lokaal ontwikkeld in `D:\Project\infisical-secret-client`. We bouwen geen tweede Infisical-HTTP-client in ControlDeck. Persoonlijke dashboardindelingen blijven applicatiedata in SQLite; ze zijn geen omgevingsconfiguratie.

De eerste bootstrap moet buiten de vault beschikbaar zijn om de vault te kunnen benaderen. De client vereist `INFISICAL_ADDR`, `INFISICAL_CLIENT_ID`, `INFISICAL_CLIENT_SECRET` en `INFISICAL_PROJECT_ID`. Bewaar deze uitsluitend op de runtimehost, in een afgeschermde serviceconfiguratie of via de bestaande secretinjectie. Zet ze niet in Git, publieke images of loguitvoer.

`INFISICAL_ENVIRONMENT` is optioneel (clientstandaard `prod`). `INFISICAL_SECRET_PATH` selecteert de ControlDeck-map; `INFISICAL_SHARED_PATH` selecteert gedeelde standaardwaarden. HTTPS met vertrouwde CA heeft de voorkeur; de client ondersteunt optioneel een eigen CA-bundle. Er zijn geen extra dashboard-omgevingsvariabelen nodig.

## Huidige koppeling

`backend/vault.py` gebruikt de geïnstalleerde `infisical-secrets` CLI. Installeer de client in de runtimeomgeving en zorg dat de service de CLI kan vinden. De lokale bronmap wordt niet als hardgecodeerde dependency gebruikt. Het projectpad op Camiels ontwikkelcomputer is geen productiepad.

De mapkeuze is, in volgorde:

1. Een reeds ingestelde `CONTROLDECK_INFISICAL_PATH`, voor compatibiliteit.
2. De standaardclientinstelling `INFISICAL_SECRET_PATH`.
3. De bestaande terugval `/apps/controldeck`.

De gedeelde map wordt doorgegeven uit `INFISICAL_SHARED_PATH`; zonder die instelling wordt uitsluitend de app-map gelezen. De client bepaalt de samenvoeging: appwaarden winnen van gedeelde waarden. Gebruik app-eigen schrijfrechten uitsluitend voor de ControlDeck-map. Geef de runtime geen identitybeheerrechten of algemene admincredentials.

ControlDeck haalt namen en waarden via het CLI-contract op. De waardeoverdracht wordt intern afgevangen en niet afgedrukt. Schrijven gebruikt stdin; geheimen komen niet als procesargument mee. De bestaande instelling `CONTROLDECK_INFISICAL_CLI` blijft beschikbaar voor installaties met een afwijkende CLI-locatie, maar is bij een normale installatie niet nodig.

Voor het uitlezen via `run` wordt de werkelijk actieve Python-interpreter gebruikt. Een naast de CLI geraden bestand met de naam `python` werkte niet betrouwbaar op Windows of bij gescheiden installaties; een regressietest controleert de echte extractiesubprocess.

## Wat al centraal staat en wat nog volgt

- De bestaande aanmeldinstellingen met `CONTROLDECK_`-namen kunnen uit de vault komen. De huidige implementatie projecteert ze bij startup intern naar de procesomgeving; er is geen afzonderlijke handmatig onderhouden app-`.env` nodig wanneer de vault ze levert.
- `CONTROLDECK_ACCOUNTS` is leidend voor accounts; bestaande compatibiliteit met `ACCESS_USERS` blijft behouden. Accountwijzigingen worden eerst naar de vault geschreven en pas daarna naar de private lokale kopie. Hiervoor is gerichte schrijfbevoegdheid nodig.
- De huidige versleutelde providercredentials, de persistente sessiesleutel en bepaalde private providerconfiguratie zijn nog niet allemaal naar vaultreferenties gemigreerd. Deze dashboardwijziging claimt dus geen volledige centralisatie.
- Bij het adapterfundament volgt migratie naar bronreferenties in de vault. Eerst per provider lezen, schrijven, sleutelrotatie, uitval en herstel testen; pas daarna oude lokale credentials opruimen. Bewaar bestaande werkende koppelingen tijdens die overgang.
- Een vaultstoring gebruikt voor bestaande accountconfiguratie de laatst bekende private kopie volgens het huidige gedrag. Nieuwe of gewijzigde secrets mogen niet stilzwijgend als succesvol opgeslagen worden gemeld wanneer de vault schrijfacties afwijst.

De lokale clientbron en het CLI-contract zijn onderzocht; er zijn tijdens dit werk geen echte vaultwaarden uitgelezen, gewijzigd of gepubliceerd. De tests gebruiken synthetische waarden en vervangen de vaulttransportgrens. Een live verbinding en de runtime-installatie van de client moeten op de doelhost afzonderlijk worden gecontroleerd.

## Aanmeldmodules

Kasm-API-geheimen en de private accountkoppeling voor automatisch aanmelden horen in de JSON-waarde `CONTROLDECK_APP_LAUNCHES` in dezelfde ControlDeck-vaultmap. De aanmeldroute leest deze waarde rechtstreeks via de bestaande vaultclient. Er is geen lokale bestand- of wachtwoordterugval voor deze nieuwe functies. Zie [APP-LAUNCHES.md](APP-LAUNCHES.md) voor het precieze contract en de nog ontbrekende live inrichting.
