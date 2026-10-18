# Persoonlijke startpagina: werk en homelab

ControlDeck wordt Camiels dagelijkse startpagina voor werk en homelab, voortbouwend op de bestaande code. Eenvoudige bediening, aanpasbare dashboards, appkoppelingen en gegevensuitwisseling staan centraal.

## Gekozen prioriteiten

De selectie van 14 oktober 2026 is:

- **MVP:** A1–A7, B1–B8, D1–D10, E1–E4 en F1–F6 uit de Homarr-inventarisatie.
- **Nice to have:** C1–C25, de specialistische widgets.
- **Later:** overige functies. Een gewone Kasm-link past al in apptegels; native sessiestart blijft een latere uitbreiding.

De volledige betekenis van de IDs, vergelijking van beide codebases, technische aanpak, fasering, acceptatiecriteria en resterende keuzes staan in het [plan van aanpak](PVA-DASHBOARD.md). Dat document vervangt het eerdere voorlopige bouwvoorstel op deze pagina.

## Herstelpunt

De bestaande code is vastgelegd op GitHub met tag `checkpoint/pre-dashboard-2026-10-14`, commit `cc62ca4a6e82e7039f5b028e3587fa16e3f22016`. Nieuwe plandocumentatie en private runtimegegevens vallen niet onder dat codeherstelpunt.

## Eerste werkende uitbreiding

De huidige code bevat nu een eerste persoonlijke dashboardeditor, voortbouwend op de bestaande ControlDeck-shell:

- Werk en Homelab worden bij het eerste bezoek per gebruiker aangemaakt. Daarna kunnen dashboards worden toegevoegd, gedupliceerd, hernoemd en verwijderd, met een persoonlijk standaarddashboard.
- In Bewerken voeg je eigen app-links, bestaande Homepage-apps en groepen toe. Groepen kunnen in het midden, een vast linkerpaneel of een vast rechterpaneel staan. Eigen links hebben een naam, adres en optionele beschrijving. Bestaande apps worden als verwijzing toegevoegd: naam, adres, icoon en opgeslagen integratiecijfers blijven uit Bookmarks komen.
- Sleep een tegel met de handgreep. De hoekgreep verandert het formaat; pijltjestoetsen op die greep werken ook. Het formulier ondersteunt precieze posities en formaten. Overlap wordt afgewezen.
- Opslaan bewaart de volledige indeling atomair. Annuleren verwerpt lokale bewerkingen. Verlaten van een onopgeslagen dashboard vraagt bevestiging. Een wijziging vanuit een ander tabblad geeft een versieconflict en behoudt de lokale bewerking.
- Bekijken en bewerken zijn persoonlijk, ook voor admins. De bestaande Dashboard-modulerechten en sessie-/CSRF-controles blijven vereist. Groepenbeheer en gedeelde dashboards zijn hiermee niet toegevoegd.

Dit is een eerste onderdeel van A1–A7 en B met app-links, geen voltooide MVP. Een widgetcatalogus, bronadapters voor alle D-groepen, eigen API-widgets, machine-API en uitgebreid gebruikersbeheer volgen volgens het plan. De bestaande Homepage-links worden niet automatisch verplaatst: je kiest zelf welke apps op ieder dashboard komen.

## Appverwijzingen en centrale zoekfunctie

**Bestaande app toevoegen** opent een doorzoekbare appkiezer. De tegel bewaart alleen een bron-ID en de positie; bronadressen of integratiegeheimen worden niet in het dashboard gekopieerd. Dezelfde app kan op meerdere dashboards staan. Een naams- of adreswijziging in Bookmarks werkt door bij de volgende laadactie of **App-lijst vernieuwen**. Het icoon wordt uit de bestaande lokale iconenbibliotheek opgelost.

De opgeslagen Seerr/Jellyfin-cijfers van een aan een Homepage-link gekoppelde integratie kunnen op dezelfde tegel verschijnen. De tekst **Laatst opgeslagen cijfers** maakt duidelijk dat de app-lijst geen live providerverversing uitvoert. Gebruik de bestaande integratiebediening voor een upstream-verversing. Een kapotte samenvatting blokkeert gewone links niet.

De bestaande Bookmarks-rechten blijven vereist voor brongegevens, ook via het dashboard en zoeken. Een verwijderde of niet langer toegestane app geeft **App niet beschikbaar**, zonder oude gekopieerde naam, adres of cijfers terug te tonen. Je kunt die verwijzing nog verwijderen of verplaatsen zonder opnieuw brontoegang te krijgen. Nieuwe ontoegankelijke verwijzingen worden afgewezen. Het Dashboard-modulerecht alleen ontsluit geen gedeelde Bookmarks-data.

Het **zoekveld** in de bovenbalk (focus met **Ctrl/Cmd+K**) doorzoekt; resultaten verschijnen in een uitklappanel eronder, **Enter** opent het eerste resultaat en **Esc** sluit het panel. Het zoekveld doorzoekt de toegestane onderdelen, eigen dashboards en bestaande Homepage-apps. Alle woorden moeten in naam/beschrijving/groep voorkomen. Maximaal 50 resultaten, met maximaal 200 tekens invoer. Dashboardresultaten openen de gekozen persoonlijke indeling. Appresultaten openen de bestaande app in een nieuw tabblad. Dit zoekt nog niet in live Linkwarden-inhoud of andere externe providerdata. Uitval van een bron laat andere resultaten bruikbaar. De resultatenlijst wordt bij veranderde modulerechten opnieuw opgebouwd.

Onder **Zoekmachines beheren** voeg je persoonlijke zoekmachines toe, zoals SearXNG of een werkportaal. Gebruik één `%s` in een vast HTTP(S)-adres, bijvoorbeeld `https://zoeken.example.test/search?q=%s`. Alleen na het kiezen van de externe zoeklink wordt de term naar die website gestuurd. ControlDeck doet geen serververzoek naar die zoekmachine. De zoekterm wordt als één URL-gecodeerde waarde ingevoegd; een query kan geen extra parameters injecteren. Bestemmingen met ingebouwde login, secretparameters, variabele hostnaam of meerdere placeholders worden afgewezen.

Zoekmachines zijn persoonlijk, ook voor beheerders: maximaal 10, naam maximaal 80 tekens en sjabloon maximaal 2048. Aanmaken, aanpassen en verwijderen hebben dezelfde sessie-/CSRF-beveiliging als andere voorkeuren en gebruiken revisies tegen gelijktijdig overschrijven. Dit is gewone zoekconfiguratie zonder vaultcredentials; SearXNG gebruikt de eigen browsertoegang van de gebruiker.

Op mobiel staan panelen onder elkaar; buiten de bewerkmodus worden kaarten als lijst getoond. Afzonderlijke opgeslagen mobiele indelingen volgen later. Inklappen in de gewone weergave geldt voor het huidige bezoek; voor een opgeslagen ingeklapte starttoestand gebruik je Bewerken.

## Grenzen en opslag

Maximaal 20 dashboards per gebruiker, 20 groepen per dashboard en 100 tegels. Een groep gebruikt 12 logische kolommen en maximaal 100 rijen. Tegelhoogte is 1–6 rijen. De dashboardnaam en groepsnaam zijn maximaal 100 tekens, de tegelnaam 300, beschrijving 1000 en URL 2048. Alleen HTTP(S)-links zonder ingebouwde login of herkenbare secretparameters zijn toegestaan. De nieuwe API haalt zelf geen appstatus of externe gegevens op.

De private SQLite-tabellen `dashboard_schema`, `dashboards`, `dashboard_preferences` en `search_engines` bewaren schema, documenten, eigenaar, revisie en standaardkeuze. `homepage_link_sequence` bewaart de hoogste gebruikte app-ID zodat verwijderen geen nummer vrijmaakt voor een andere bron. Bij migratie worden ook bestaande verwijzingen en de vorige linkversie meegenomen. IDs blijven stabiel bij hernoemen. Elke schrijfactie gebruikt een transactie; een verouderde revisie levert HTTP 409. Een andere eigenaar krijgt HTTP 404 zonder gegevensprojectie. Bij het laatste dashboard verwijderen blijft de lijst leeg; de twee starters worden niet opnieuw aangemaakt.

API: `GET/POST /api/dashboards`, `GET/PUT/DELETE /api/dashboards/<id>` en `PUT /api/dashboards/default`. PUT verwacht `revision`, `title`, `sections` en `items`; DELETE verwacht alleen `revision`. Tegeltype `app` bewaart `appId` in plaats van `title`, `url` en `description`. De payloadgrens is 256 KiB. `GET /api/dashboards/apps` geeft de toegestane bronprojectie. `GET /api/search?q=...` zoekt lokaal. `GET/POST /api/search-engines` en `PUT/DELETE /api/search-engines/<id>` beheren persoonlijke zoekmachines. Dit zijn sessiebeveiligde browserendpoints, nog geen E4-machine-API.

## Migratie en herstel

Vóór installatie of upgrade maakt de service via de SQLite-backupfunctie een consistente kopie van de bestaande database in de private datamap: `backups/pre-dashboard-v<stap>-<id>.sqlite3`. Schema v1 introduceert dashboards, v2 persoonlijke zoekmachines en v3 blijvende app-ID's. Een nieuwe installatie gaat na één backup naar de huidige versie; een bestaande v1/v2-installatie krijgt vóór upgrade opnieuw één backup. Herhaald starten zonder nieuwe schemaversie maakt geen extra kopie. Een mislukte backup breekt de migratie af. Een onbekende schemaversie weigert startup. De brontransactie voorkomt gelijktijdige migraties.

Deze kopie bevat geen `session.key`, accountbestand of externe providerbestanden. Maak daarvoor de volledige private runtimebackup zoals beschreven in [AUTHENTICATION.md](AUTHENTICATION.md). Voor terugkeer naar de checkpointcode: stop de service, bewaar de huidige data, herstel de passende pre-dashboarddatabase en de bijbehorende private sleutel/configuratie, en start de vorige release. De hersteltest opent de werkelijk gemaakte databasekopie en controleert de integriteit en bestaande gebruikersvoorkeuren.

## Huisstijl en configuratie

De komende gedeelde huisstijl krijgt een eigen project. De dashboardcomponent gebruikt voorlopig de bestaande ControlDeck-variabelen `--bg`, `--card`, `--text`, `--muted`, `--border` en `--blue`. Het componentbestand `frontend/components/dashboard.css` bevat indeling en gebruikt die variabelen voor uiterlijk; er is geen tweede kleurenpalet of nieuwe huisstijlpackage toegevoegd. Een later package kan de gedeelde tokens leveren zonder dashboardgedrag te herschrijven.

Geheimen en centrale instellingen lopen via Camiels client volgens [VAULT.md](VAULT.md). Er zijn geen nieuwe dashboard-envvariabelen. De bestaande releaseversie blijft `yyyy.mm.dd.buildnr`, berekend in CI; het buildnummer wordt niet lokaal verzonnen. `VERSION` blijft `development` voor ontwikkeling. Een lokaal aanwezig genegeerd `build-info.json` kan nog metadata van een oudere build tonen.

## Runtime

De bestaande opzet blijft behouden: een statische frontend, één Python-service en lokale SQLite. Er komt geen Node.js-server bij in productie.

## Appiconen

Apptegels laden standaard `/favicon.ico` vanaf de website zelf, zonder referrer. Als dat ontbreekt volgt een beschikbaar lokaal diensticoon. Via App-link aanpassen kan de gebruiker een PNG kiezen (maximaal 2 MB en 4096 × 4096 pixels). De browser verkleint deze naar 64 × 64; de server accepteert alleen gecontroleerde PNG-data tot 32 KiB en 256 × 256 pixels. De afbeelding blijft onderdeel van het persoonlijke dashboard, met dezelfde toegangsrechten, revisiecontrole en back-up. Website-icoon gebruiken verwijdert de eigen afbeelding; Opslaan bewaart de wijziging. De totale dashboardlimiet van 256 KiB blijft gelden.

## Gedeelde apps en persoonlijke indeling

Bookmarks bevat twee bronnen: de gedeelde Homepage-appcatalogus met integraties en persoonlijke Linkwarden-bookmarks. Dashboard gebruikt bestaande catalogusapps via `appId`; er wordt geen tweede app of integratie aangemaakt. Naam, adres en icoon van zo'n app worden bij Bookmarks beheerd. Persoonlijke dashboardlinks blijven voor eigen links bestaan en zijn expliciet zo benoemd.

De faviconweergave, PNG-upload en servervalidatie worden nu door Bookmarks en Dashboard gedeeld. Een gewijzigd catalogusicoon volgt vanzelf mee bij het ophalen van de dashboardbronnen. Linkwarden blijft de bron voor persoonlijke verzamelingen en is via de hieronder beschreven module als dashboardbron beschikbaar. De andere overlap (groeperen en zoeken) is deels functioneel: Bookmarks ordent de bronnen, Dashboard bewaart de persoonlijke plaatsing; globaal zoeken vindt modules en dashboards. Verdere samenvoeging vraagt een afzonderlijke navigatiekeuze en migreert bestaande links niet stilzwijgend.

## Modules: Linkwarden

Een dashboard is een samenstelling van herbruikbare functies. De eerste volledige module is Linkwarden: dezelfde `LinkwardenModule` verzorgt de Bookmarks-pagina en de compacte dashboardweergave. Er is geen tweede providerkoppeling, tokenopslag of bookmarkdatabase. De bestaande `/api/linkwarden/*`-endpoints blijven identiteit en Bookmarks-toegang controleren.

Gebruik: Bewerken → Module toevoegen → Linkwarden → kies alle toegankelijke collecties of één collectie → Toepassen → Opslaan. Het dashboarddocument bewaart alleen `type: module`, `moduleId: linkwarden`, `settings: {collectionId: null|positief geheel getal}` en de plaatsing. Meerdere exemplaren mogen verschillende collecties tonen. Collectienummers zijn geen toegangsrechten: de bestaande persoonlijke Linkwarden-koppeling bepaalt wat de gebruiker mag zien.

De compacte module toont zoeken, vernieuwen, paginering, lege/foutstatus en een verwijzing naar Beheren. Toevoegen van bookmarks en beheren van de koppeling blijven op de volledige modulepagina. Een filterselectie tijdens gebruik is tijdelijk; de gekozen standaardcollectie wordt via Module instellen opgeslagen. Bij een vast ingestelde collectie blijft dat filter vast. Moduleplaatsen en -formaten staan achter Plaats en grootte, zodat de eerste instelling zich op de inhoud richt.

De modulecatalogus heeft één expliciete registratie per ondersteunde functie, met bestaande modulerechten en beginformaat. Onbekende modules of instellingen, credentials in instellingen, negatieve/ongeldige collectienummers en nieuwe modules zonder bronrechten worden geweigerd. Na intrekken van Bookmarks-toegang wordt geen Linkwarden-component geladen. Verplaatsen/verwijderen van een eerder opgeslagen module blijft mogelijk, maar een andere collectie instellen vraagt opnieuw bronrechten. Bestaande dashboards en persoonlijke links blijven behouden; de module gebruikt het bestaande JSON-schema zonder nieuwe databasetabel.

UX-richting: het dashboard is de persoonlijke werkplek; volledige modulepagina's zijn voor uitgebreid beheer. Nieuwe functies worden eerst herbruikbare modules en daarna via de catalogus beschikbaar, zonder gekopieerde formulieren. Apps en persoonlijke links blijven bestaande tegelopties in dezelfde kiezer.

## Proxmox en ProxMenux

Bewerken → Module toevoegen → Proxmox biedt vijf weergaven: nodes (CPU/geheugen), gasten (hoogste CPU-gebruik), taakresultaten, volledig clusteroverzicht en ProxMenux-gezondheid (problemen, temperatuur, CPU-vermogen, load en hostupdates). Meerdere exemplaren bewaren hun eigen weergave. De module bewaart uitsluitend `settings: {view: nodes|guests|tasks|all|health}` en de plaatsing; verbindingsgegevens blijven centraal.

De Proxmox-pagina en dashboardmodules gebruiken dezelfde presentatiecomponenten, bestaande `/api/proxmox/summary`- en `/api/proxmenux/summary`-routes en servercaches. De compacte ProxMenux-weergave toont nodekaarten; uitgebreide schijf-/updatebediening blijft op de bestaande pagina. Ontbrekende verbindingen, laadstatus, onbekende sensoren en verouderde gegevens worden herkenbaar getoond. De module vernieuwt iedere minuut zolang deze gemount is; ProxMenux controleert tijdens het laden van nodes tijdelijk iedere vijf seconden. Ingeklapte groepen worden niet gemount.

De kiezer en presentatie vereisen het bestaande `proxmox`-modulerecht. De API controleert dit opnieuw; een opgeslagen dashboardtegel verleent geen bronrechten. Na intrekken van toegang kan de tegel worden verwijderd, maar kunnen de broninstellingen niet worden gewijzigd. Er zijn geen nieuwe start-, stop- of updateacties toegevoegd.

ProxMenux-brononderzoek: commit `1a8efb96a59676cc652a8d766b2738507af3bb44`. `web/` bevat de documentatiesite; de monitorinterface staat onder `AppImage/components/`, onder meer `system-overview.tsx`, `disk-temperature-card.tsx` en `hardware-monitor.tsx`. Deze zijn onderzocht als referentie voor losse kaarten en beschikbare gegevens. Voor deze batch is geen upstream-code gekopieerd en zijn geen nieuwe grafiek-/UI-pakketten toegevoegd. Historische grafieken en GPU-monitoring zijn nog geen dashboardfunctionaliteit. Het genoemde interne monitoradres kon vanuit de ontwikkelomgeving niet via DNS worden bereikt; deze wijziging claimt geen nieuwe live monitorkoppeling.

Controle via de Proxmox-node: de genoemde monitornaam wordt daar wel gevonden. De HTTPS-controle met zowel de standaard truststore als de interne home-root-CA faalde op certificaatvalidatie. Certificaatcontrole is niet uitgezet en de bestaande monitorconfiguratie is niet gewijzigd. Controleer bij live acceptatie de bestaande koppeling, het certificaat en het ingestelde API-adres afzonderlijk.

Lokale verificatie van deze batch: 562 Python-tests geslaagd, 8 overgeslagen; 178 frontendtests geslaagd; TypeScript en statische productiebuild geslaagd. De nieuwe tests omvatten weergavekeuze, compacte sensorkaarten, lege bronnen, verouderde gegevens, foutmeldingen, ongeldige instellingen, sessie/CSRF, eigenaarschap en ingetrokken bronrechten. De bestaande parser-/API-tests blijven onderdeel van de volledige suite. Er is nog geen release van deze batch gepubliceerd.

### Live acceptatie ProxMenux, 14 oktober 2026

De deployment van commit `48c1c82` is geslaagd. Na de netwerkregelwijziging en een herstart van uitsluitend de vastgelopen monitorservice op de NAS-node zijn alle drie de monitoren vanuit de ControlDeck-container gecontroleerd met de bestaande API-tokens en cluster-CA. Gezondheid, systeem, hardware, opslag en gasten zijn per node succesvol opgevraagd. De uitgebreide gezondheidscontrole op de Intel-node liep eenmaal tegen de bestaande timeout aan; een herhaalde controle slaagde binnen 13,6 seconden. Dit blijft een aandachtspunt bij live belasting. Wachtwoordbeveiliging en certificaatcontrole zijn behouden; VM's en containers zijn niet herstart.

## Losse systeemwidgets

Via Bewerken → Module toevoegen → Systeemwidget kan iedere tegel CPU-gebruik, geheugen, temperatuur of CPU-vermogen tonen. Kies alle nodes of één node uit de bestaande Proxmox-koppeling. Met meerdere tegels kunnen verschillende metingen en hosts naast elkaar staan; plaatsing, formaat en instellingen worden per tegel bewaard.

CPU/geheugen gebruiken `/api/proxmox/summary`; temperatuur/vermogen gebruiken `/api/proxmenux/summary`. De server controleert het bestaande Proxmox-modulerecht. Het dashboard bewaart alleen `moduleId: system`, `settings: {metric: cpu|memory|temperature|power, node: ""|nodenaam}` en de plaatsing. Er is geen extra geheim of provider nodig. Bron-URL's, tokens en willekeurige velden worden als widgetinstelling afgewezen.

CPU/geheugen krijgen een cirkelmeter met zichtbare waarde en tekst bij hoog gebruik. Temperatuur en CPU-vermogen tonen meetwaarden zonder verzonnen maximum of geschiedenis. CPU-vermogen is expliciet geen totaalverbruik. Onbekende metingen worden geen nul; offline nodes krijgen geen actuele waarde. Verouderde bronnen en fouten blijven zichtbaar; bij ingetrokken bronrechten verdwijnen eerder getoonde meetwaarden na de eerstvolgende controle. Het tijdstip onder de kaarten is het ophaaltijdstip, niet een beloofde nieuwe bronmeting.

De widget vernieuwt iedere minuut met maximaal één lopende aanvraag per exemplaar, een timeout en annulering bij sluiten of een gewijzigde selectie. Meerdere widgets hergebruiken de bestaande servercache. Kleur, kaarten, tekst en randen volgen de bestaande huisstijltokens voor licht en donker. Deze eerste uitvoering gebruikt eigen React/SVG-code; er is geen Homarr-widgetcode of extra grafiekpakket geïmporteerd.

## Aanmeldmodules Kasm en Nextcloud

De modulecatalogus bevat ook Kasm en Nextcloud als afzonderlijke modules voor het openen van een aangemelde dienst. Zij verschijnen alleen bij de bestaande ingeschakelde provider en bijbehorende modulerechten. De modules hebben lege dashboardinstellingen; doelen, geheimen en accountkoppelingen worden centraal uit Infisical gelezen. Dit zijn aanmeldmodules, nog geen ingebedde werkplekken of Nextcloud-bestandenoverzicht. Zie [APP-LAUNCHES.md](APP-LAUNCHES.md).

## Downloads, media en andere dienstwidgets

De catalogus bevat afzonderlijke modules voor Downloads, Media, Tdarr, een Home Assistant-dashboard, Agenda en Flows en aanbiedingen. Voeg meerdere exemplaren toe om meerdere diensten tegelijk te tonen; kies de bron per tegel. Bronnen en persoonlijke toegang worden centraal in Infisical beheerd. Er is geen dubbel beheerformulier op het dashboard. Zie [SERVICE-WIDGETS.md](SERVICE-WIDGETS.md) voor inrichting, gebruikersisolatie, lege/fouttoestanden en de resterende live controles.
