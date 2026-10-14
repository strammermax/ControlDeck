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

**Zoeken** in de bovenbalk of **Ctrl/Cmd+K** doorzoekt de toegestane onderdelen, eigen dashboards en bestaande Homepage-apps. Alle woorden moeten in naam/beschrijving/groep voorkomen. Maximaal 50 resultaten, met maximaal 200 tekens invoer. Dashboardresultaten openen de gekozen persoonlijke indeling. Appresultaten openen de bestaande app in een nieuw tabblad. Dit zoekt nog niet in live Linkwarden-inhoud of andere externe providerdata. Uitval van een bron laat andere resultaten bruikbaar. De resultatenlijst wordt bij veranderde modulerechten opnieuw opgebouwd.

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
