# ControlDeck — Globaal technisch ontwerp

**Versie:** 1.0  
**Datum:** 5 oktober 2026  
**Status:** Voorgesteld ontwerp; geen bestaande implementatie  
**Basis:** `visie.md` en `functioneel-ontwerp.md`

## 1. Doel en uitgangspunten

Dit document beschrijft een technische basis voor een modulair browserportaal met veilige providerkoppelingen. Het ontwerp ondersteunt de gefaseerde functionele scope. Productversies, programmeertalen, frameworks en leveranciers zijn nog niet gekozen; die keuzes worden vastgelegd na inventarisatie en een klein werkend prototype.

De voorgestelde startarchitectuur is een modulaire monoliet: één backend met duidelijke interne grenzen, een webinterface en een achtergrondproces voor statusverzameling. Dit beperkt operationele complexiteit terwijl providers later afzonderlijk kunnen worden uitgevoerd indien daar aanleiding toe is.

## 2. Componenten en verantwoordelijkheden

```text
Browser
   | HTTPS, dezelfde origin voor interface en API
   v
Reverse proxy / toegangspunt
   |                 |
   v                 v
Webinterface     Backend / API
                     |
            +--------+---------+----------------+
            |                  |                |
       Autorisatie       Providerregister   Acties / audit
            |                  |                |
            +----------+-------+----------------+
                       |
             Database + statuscache
                       ^
                       |
              Achtergrondcollector
                       |
                 Provideradapters
                       |
                Homelab-systemen
```

| Component | Verantwoordelijkheid |
| --- | --- |
| Webinterface | Navigatie, kaarten, detailpagina's, formulieren en voortgang |
| Backend | Sessies, autorisatie, configuratie, API en gecontroleerde acties |
| Providerregister | Geïnstalleerde adapters en hun mogelijkheden registreren |
| Collector | Periodiek status ophalen met begrensde gelijktijdigheid |
| Actieverwerking | Opdrachten valideren, uitvoeren en hun uitkomst volgen |
| Database | Voorkeuren, rechten, actieadministratie en auditmetadata bewaren |
| Cache | Laatst bekende status en meettijdstippen beschikbaar stellen |
| Toegangspunt | HTTPS en routering; alleen bewust gekozen routes publiceren |

De browser communiceert voor geïntegreerde gegevens uitsluitend met ControlDeck. Providercredentials blijven serverzijdig. Links openen de oorspronkelijke dienst rechtstreeks en zijn geen generieke proxyfunctie.

## 3. Technische keuzes en besliscriteria

| Onderdeel | Voorgestelde richting | Nog te beslissen |
| --- | --- | --- |
| Frontend | Componentgebaseerde, responsieve interface met getypeerde API-contracten | Framework en buildtool |
| Backend | Getypeerde API met modules en dependency injection | Taal, framework en runtime |
| Persistente opslag | Relationele database; één instantie voor de eerste deployment | Databaseproduct en backupmethode |
| Cache | Begin met eenvoudige lokale cache; gegevens zijn opnieuw op te halen | Of een gedeelde cache later nodig is |
| Configuratie | Versiebeheerd YAML- of JSON-document met schemavalidatie | Definitief formaat |
| Identiteit | Centrale authenticatie via een ondersteund identityprotocol | Identityprovider en toegangsroute |
| Deployment | Containerdeployment op een dedicated Linux-VM of host | Host, capaciteit en beheeromgeving |

Dit zijn ontwerpvoorstellen. Voor de definitieve keuze worden onderhoudbaarheid, bestaande kennis, ondersteunde softwareversies, beveiligingsupdates en deploymentmogelijkheden getoetst. Een lokale database en cache impliceren één actieve backendinstantie; meerdere replicas vragen gedeelde opslag en gecoördineerde achtergrondtaken.

## 4. Module- en providercontract

Een module bevat presentatielogica en use cases. Een provideradapter vertaalt een specifiek systeem naar het ControlDeck-model. Leveranciersdetails blijven binnen de adapter.

Een adapter declareert een type, contractversie en capabilities. Het voorgestelde contract bevat:

```text
describe()                  -> type, versie, capabilities
validateConfiguration()     -> validatieresultaat
testConnection()            -> verbindingsresultaat
listResources()             -> resources
getSnapshot(resourceId)     -> status en metingen
execute(actionRequest)      -> operationele referentie
getOperation(reference)     -> uitvoeringsstatus, indien ondersteund
```

Niet elke adapter ondersteunt alle methoden. Leesintegraties hoeven geen beheeracties te implementeren. Capabilities, resourcetoegang en actiebeleid bepalen samen welke functies beschikbaar zijn. De backend controleert dit bij iedere aanvraag.

De eerste versie bevat alleen adapters die met de applicatie worden geleverd. Willekeurige externe plugincode wordt niet dynamisch geladen.

## 5. Kerngegevensmodel

| Entiteit | Belangrijkste velden |
| --- | --- |
| User | Interne ID, externe identity-ID, weergavenaam, actief |
| PermissionGrant | Gebruiker of groep, module, resourcescope, toegestane actie |
| ModuleConfig | Module-ID, actief, indeling, gekoppelde provider-ID's |
| ProviderInstance | ID, type, naam, endpoint, secretReference, configVersion |
| Resource | ID, provider-ID, externe ID, type, naam, toegestane links |
| Snapshot | Resource-ID, gezondheid, metingen, observedAt, fetchedAt, lastSuccessAt, foutcode |
| Bookmark | ID, naam, URL, categorie, tags, eigenaar of gedeelde scope |
| Favorite | Gebruiker-ID en doel-ID |
| ActionOperation | ID, aanvrager, doel, actie, status, tijdstippen, externe referentie |
| AuditEvent | ID, actor, gebeurtenis, doel, resultaat, correlatie-ID, tijdstip |

Een resource-ID is stabiel en voorkomt botsingen tussen providers. Metingen hebben een expliciete eenheid. Tijdstippen worden intern in UTC opgeslagen en in de interface volgens de gebruikersinstelling weergegeven.

Gezondheid, actualiteit en providerbereikbaarheid blijven gescheiden. De actualiteit wordt berekend uit de laatste succesvolle meting en een per provider ingestelde grens. De cache bevat geen providergeheimen.

## 6. API-opzet

Onderstaande routes zijn een voorstel voor het interne API-contract, geen reeds beschikbare endpoints.

| Methode en route | Functie |
| --- | --- |
| `GET /api/v1/me` | Sessie en toegestane functies |
| `GET /api/v1/modules` | Toegestane modules |
| `GET /api/v1/dashboard` | Toegestane kaarten en snapshots |
| `GET /api/v1/resources` | Gefilterde resourcecatalogus |
| `GET /api/v1/resources/{id}` | Details en beschikbare acties |
| `POST /api/v1/resources/{id}/actions` | Geselecteerde actie aanvragen |
| `GET /api/v1/operations/{id}` | Uitvoeringsstatus lezen |
| `GET /api/v1/bookmarks` | Toegestane bookmarks |
| `PUT /api/v1/me/favorites/{id}` | Favoriet toevoegen |
| `DELETE /api/v1/me/favorites/{id}` | Favoriet verwijderen |
| `POST /api/v1/admin/providers/{id}/test` | Geconfigureerde verbinding testen |

Lijsten krijgen paginering en expliciete filters. Responses bevatten geen providercredentials. Fouten gebruiken stabiele foutcodes, een begrijpelijke boodschap en een correlatie-ID. Onbevoegde aanvragen geven geen informatie over verborgen resources prijs.

Een asynchrone actie retourneert een operation-ID en status `accepted`; voltooiing wordt afzonderlijk gevolgd. Alleen ondersteunde actietypen en gevalideerde parameters worden aan een provider doorgegeven.

## 7. Gegevensstromen en foutafhandeling

### Status ophalen

De collector haalt op vaste, configureerbare intervallen snapshots op. De backend levert de cache aan de interface, zodat een dashboardaanvraag niet op alle providers hoeft te wachten. Als beginwaarden kunnen 30 seconden voor verversing en 90 seconden voor veroudering worden gebruikt; ze worden per bron afgestemd.

Providerverzoeken hebben time-outs en begrensde gelijktijdigheid. Alleen veilige leesverzoeken krijgen beperkte retries met oplopende wachttijd. Herhaalde fouten veroorzaken een tijdelijke pauze voor die provider. Laatst bekende gegevens blijven zichtbaar met fout- en actualiteitsmetadata.

### Een actie uitvoeren

1. Controleer sessie, resourcescope, capability en parameters.
2. Controleer de vereiste bevestiging; bevestiging verleent geen extra rechten.
3. Maak een duurzame operation-record en auditregistratie aan vóór uitvoering.
4. Voer de actie uit met een sleutel om dubbele aanvragen te herkennen.
5. Volg de externe taak als de provider dat ondersteunt.
6. Registreer resultaat en werk de resourcegegevens bij.

Bij een time-out na verzending kan de uitkomst onbekend zijn. De actie wordt dan niet blind opnieuw uitgevoerd. Onderzoek via externe taakstatus of resource-inspectie bepaalt de volgende stap. Als duurzame registratie niet beschikbaar is, worden beheeracties geweigerd.

## 8. Configuratie en secrets

Configuratie beschrijft modules, providerinstances, doeladressen, intervallen en resourcegroepen. Een illustratieve configuratie:

```yaml
schemaVersion: 1
modules:
  proxmox:
    enabled: true
    providers: [lab-proxmox]
providers:
  lab-proxmox:
    type: proxmox
    endpoint: https://proxmox.example.internal
    secretReference: proxmox-readonly-token
    collectionIntervalSeconds: 30
```

Het voorbeeld bevat fictieve gegevens en is geen werkend configuratiecontract. Geheimen worden aangeleverd via een beveiligde secretvoorziening of afgeschermde runtimebestanden. Broncode en configuratie bevatten alleen verwijzingen.

De backend valideert structuur én betekenis voordat wijzigingen actief worden. Ongeldige wijzigingen vervangen de laatste geldige configuratie niet. Een configuratieversie maakt wijzigingen herleidbaar. UI-bewerking van configuratie wordt pas toegevoegd als eigenaarschap en versieconflicten zijn uitgewerkt.

## 9. Beveiligingsontwerp

Authenticatie wordt gekoppeld aan een gekozen identityprovider. De backend gebruikt een serverzijdige sessie met veilige cookies. Schrijvende verzoeken krijgen CSRF-bescherming waar de sessiemethode dat vereist. Tokens worden niet in browseropslag bewaard.

Autorisatie vindt plaats op de backend voor iedere resource en actie. Frontendfilters ondersteunen de gebruikerservaring maar vormen geen beveiligingsgrens. Leesproviders krijgen zo beperkt mogelijke credentials; credentials voor beheer worden waar mogelijk apart gehouden.

Providerdoelen worden beperkt tot goedgekeurde adressen en poorten. Redirects, naamresolutie en bestemmingen worden gecontroleerd om misbruik van serverzijdige verzoeken te voorkomen. Certificaatcontrole blijft ingeschakeld; interne certificaten worden via een beheerde truststore vertrouwd.

Terminalfunctionaliteit gebruikt een afzonderlijk uitgewerkt gatewayontwerp met doelbinding, korte sessies en controle op verbindingsherkomst. Een bestandsprovider begrenst toegestane roots en voorkomt padmanipulatie en ontsnappen via symlinks. Beide functies vallen buiten de eerste technische implementatie.

Logs bevatten geen wachtwoorden, tokens of ongefilterde externe responses. Auditgegevens zijn alleen voor bevoegde gebruikers toegankelijk. Retentie en eventuele sessieopname worden expliciet vastgesteld voordat productiegebruik begint.

## 10. Deployment en beheer

De voorgestelde productieomgeving draait op een dedicated host of VM met beperkte netwerktoegang tot benodigde providers. Interface en API worden via één HTTPS-origin aangeboden. Database, secrets en interne beheerpoorten worden niet rechtstreeks gepubliceerd.

De deployment gebruikt vastgelegde releaseversies, een gecontroleerde migratiestap en persistente opslag buiten het vervangbare applicatie-image. Ontwikkeling, test en productie gebruiken afzonderlijke configuratie en credentials.

De applicatie heeft afzonderlijke controles voor procesgezondheid en gereedheid. Een externe providerstoring maakt de hele applicatie niet automatisch ongereed. Interne meetgegevens omvatten API-responstijd, providerfouten, actualiteit van snapshots en mislukte acties.

## 11. Backup, herstel en updates

Backups omvatten configuratie, database, noodzakelijke encryptiesleutels en een afzonderlijk beschermde backup van secrets. Statuscache hoeft niet te worden hersteld. Een backup wordt getest door een geïsoleerde herstelprocedure uit te voeren.

Vóór een update worden migratiegevolgen en herstelbaarheid gecontroleerd. Rollback van applicatiecode is alleen veilig als het databaseschema compatibel blijft. Anders is herstel van een passende backup nodig. Hersteltijd en maximaal acceptabel gegevensverlies worden vastgesteld op basis van het gebruik.

## 12. Validatie en traceerbaarheid

| Functionele eisen | Technische invulling | Belangrijkste verificatie |
| --- | --- | --- |
| F-01 t/m F-09 | Modulecatalogus en provider-capabilities | Navigatie, lege toestanden en toegestane functies |
| F-10, F-11 | Sessies en serverzijdige rechten | Login, logout en directe ongeautoriseerde API-aanvragen |
| F-12 | Gebruikersgebonden favorieten | Bewaren en afscherming tussen gebruikers |
| F-13 | Configuratieschema en gecontroleerde activering | Ongeldige configuratie behoudt laatste geldige toestand |
| F-14, F-15 | Snapshots, collector en providerisolatie | Bronuitval, time-outs en verouderde gegevens |
| F-16, F-17 | Actiebeleid, operations en audit | Dubbele aanvraag, ontbrekende rechten en onzekere uitkomst |
| F-18 | Secretscheiding en logfiltering | Geen geheimen in responses, exports en fouten |
| F-19 | Responsieve interface | Desktop, mobiel en toetsenbordbediening |

Providercontracten worden met gecontroleerde fixtures getest; echte koppelingen worden eerst met leesrechten gevalideerd. Beheeracties worden op een afzonderlijke testresource beproefd. De eerste release krijgt een beperkte pilot voordat verdere modules worden verdiept.

## 13. Open beslissingen en volgende stap

De volgende inventarisatie is nodig: aanwezige hosts en diensten, netwerktoegang, certificaten, identityprovider, gewenste eerste gebruikers, deploymenthost en toegestane beheeracties. Voor iedere integratie worden de werkelijk beschikbare API's en rechten gecontroleerd.

Daarna worden stackkeuzes vastgelegd in korte architectuurbesluiten. Het eerste prototype omvat login, een geconfigureerde dienstencatalogus en favorieten. Een afzonderlijke leesprovider bewijst vervolgens het contract, de statusweergave en de foutisolatie voordat beheeracties worden toegevoegd.

## 14. Aanvulling: lichte distributie en open-sourcebasis

Deze aanvulling specificeert de eerdere globale keuzes. Niet genoemde stackkeuzes blijven open. De lichte basisinstallatie krijgt voorrang boven verplichte extra services.

### 14.1 Onderzoek ProxMenux Monitor

De onderzochte Monitor-broncode bevindt zich onder AppImage in de ProxMenux-repository. De frontend gebruikt Next.js, React en TypeScript, met Tailwind CSS, Radix UI, Lucide-iconen en Recharts. De documentatie noemt een Python/Flask-backend. Er is een afzonderlijke sidebarcomponent. De map web bevat daarnaast de website; die moet niet worden verward met de Monitor-applicatie.

Bronnen, geraadpleegd op 5 oktober 2026:

- [Monitor package.json](https://github.com/MacRimi/ProxMenux/blob/main/AppImage/package.json)
- [Monitor README en techniek](https://github.com/MacRimi/ProxMenux/blob/main/AppImage/README.md)
- [Sidebarcomponent](https://github.com/MacRimi/ProxMenux/blob/main/AppImage/components/sidebar.tsx)
- [Buildconfiguratie](https://github.com/MacRimi/ProxMenux/blob/main/AppImage/next.config.mjs)
- [Repositorylicentie](https://github.com/MacRimi/ProxMenux/blob/main/LICENSE)

De menu-indeling is een passende visuele referentie. Inklapbare subgroepen zijn een expliciete ControlDeck-eis; deze beperkte broncontrole bewijst niet dat de onderzochte sidebar dat al volledig implementeert. Exacte versies en gekozen broncommit worden bij daadwerkelijk hergebruik opnieuw vastgesteld.

### 14.2 Strategie voor codehergebruik

Per onderdeel kiezen we tussen inspiratie, broncodehergebruik en integratie via een API. Eerst beoordelen we menucomponenten, kaarten en grafieken. Hostgebonden scripts worden niet automatisch overgenomen: ControlDeck draait in een eigen container en verzamelt infrastructuurgegevens bij voorkeur via providers.

ProxMenux heeft op repositoryniveau GPL-3.0. Bij overname van gedekte code gelden de toepasselijke licentievoorwaarden, waaronder behoud van notices en de voorwaarden voor verspreiding van gewijzigde werken en bijbehorende broncode. De exacte licentie en eventuele uitzonderingen worden per bestand gecontroleerd. De definitieve ControlDeck-licentie wordt gekozen op basis van alle werkelijk hergebruikte onderdelen; een permissieve licentie wordt niet vooraf aangenomen.

Voor ieder overgenomen onderdeel registreren we bron, commit, oorspronkelijke licentie, auteursvermelding, eigen wijzigingen en updatebeleid in een third-party-overzicht. Ook afhankelijkheden, iconen en andere assets worden geïnventariseerd. Alleen een API-koppeling is een andere vorm van integratie dan broncode overnemen; beide worden afzonderlijk beoordeeld.

De bronlicentie is leidend: [GPL-3.0, met name secties 4–6](https://github.com/MacRimi/ProxMenux/blob/main/LICENSE).

### 14.3 Runtime voor weinig resources

Het eerste prototype onderzoekt een vooraf gebouwde frontend die als statische bestanden door de backend wordt aangeboden. Daarmee is geen aparte frontendserver nodig tijdens normaal gebruik. Interactieve kaarten en submenu's kunnen in de browser werken; serverfuncties worden via de ControlDeck-API geleverd. Statische export wordt pas gekozen nadat de benodigde routes en hergebruikte componenten ermee zijn gevalideerd.

De backend bevat aanvankelijk de collector als interne achtergrondtaak. Een afzonderlijke worker is alleen nodig bij aantoonbare belasting of isolatie-eisen. De basisopslag is een ingebedde relationele database, bij voorkeur SQLite na validatie van het schrijfpatroon. Een externe database of cache is optioneel voor latere schaalvergroting.

De basisinstallatie gebruikt één actieve applicatie-instantie met lokale persistente opslag. Zij bewaart actuele snapshots en beperkte auditgegevens; langlopende meetreeksen blijven bij de monitoringprovider. Uitgeschakelde modules starten geen collectors. Verversingsintervallen, gelijktijdigheid en retentie zijn begrensd en configureerbaar.

### 14.4 Docker en LXC

**Docker:** één applicatie-image met vooraf gebouwde frontend, backend en benodigde runtime. Een meerfasige build houdt buildtools buiten het runtime-image. De applicatie draait met een onbevoorrechte gebruiker en persistente volumes voor data en configuratie. Secrets worden apart aangeleverd. Geen Docker-socket, privileged modus of Proxmox-hostfilesystem is nodig voor de basisfuncties.

**LXC:** dezelfde applicatierelease draait rechtstreeks als service in een onprivileged Linux-container. Installatie-instructies beschrijven dependencies, serviceaccount, servicebeheer en datarechten. Docker-in-LXC is geen voorwaarde. Er zijn geen standaard device-mounts of ruime hostrechten nodig.

Beide vormen gebruiken hetzelfde configuratieschema en dezelfde database-inhoud. HTTPS kan door een bestaande reverse proxy worden aangeboden. Een identiteitservice kan extern zijn; installatie-instructies moeten die afhankelijkheid expliciet maken. Voor zelfstandig communitygebruik wordt ook een beveiligde lokale login onderzocht, zodat een zware externe identity-stack geen verplichte basisdependency wordt. Centrale login blijft een gewenste optie.

### 14.5 Voorlopig resourcebudget

Dit zijn meetdoelen, geen gemeten eigenschappen of gegarandeerde systeemeisen.

| Onderdeel | Voorlopig doel |
| --- | --- |
| Testomgeving | 1 vCPU, 512 MiB RAM voor de lichte runtime; 1 GiB als ruimere eerste pilot |
| Applicatiegeheugen | Maximaal 300 MiB stabiel werkgeheugen voor backend en collectors bij basisbelasting |
| CPU in rust | Gemiddeld minder dan 5% van één toegewezen vCPU gedurende 15 minuten |
| Basisbelasting | 1 gebruiker, 5 providers, maximaal 100 resources, polling per 30–60 seconden |
| Installatieopslag | Richtbudget 2 GiB voor runtime en basisdata; backups en groei apart begroten |

Geheugenmetingen omvatten alle ControlDeck-runtimeprocessen. Browsergeheugen, buildtaken, een externe reverse proxy en achterliggende diensten worden apart gerapporteerd. De build vindt buiten de lichte productiecontainer plaats. Docker- en LXC-overhead worden naast applicatiegebruik gemeten.

Acceptatie meet koude start, stabiele belasting, provideruitval en geheugengroei tijdens een duurtest. Als het prototype het budget overschrijdt, worden runtime, polling en afhankelijkheden aangepast voordat minimale eisen worden gepubliceerd.

### 14.6 Voorbereiding voor GitHub

De toekomstige repository bevat broncode, documentatie, een expliciete licentie, third-party-notices, fictieve voorbeeldconfiguratie, Dockerfile, Compose-voorbeeld en LXC-installatie-instructies. Releases koppelen versie, broncommit, migratie-informatie en images aan elkaar.

Automatische controles omvatten build, relevante tests, dependencycontrole en controle op onbedoelde secrets. Communitybijdragen krijgen richtlijnen, issue-templates en een beveiligingsmeldprocedure. Persoonlijke configuratie, databases, logs en credentials worden uitgesloten. Imagepublicatie en repositorypublicatie zijn nog niet uitgevoerd.

## 15. Gekozen technische basis

De gebruiker heeft de onderzochte ProxMenux Monitor-techniek als basis voor ControlDeck gekozen. Daarmee worden de eerdere open stackkeuzes als volgt ingevuld:

| Laag | Keuze |
| --- | --- |
| Interface | React, Next.js en TypeScript |
| Vormgeving | Tailwind CSS met herbruikbare UI-componenten op basis van Radix UI |
| Iconen en grafieken | Lucide en Recharts, uitsluitend waar nodig |
| Backend | Python met Flask, productiegeschikt aangeboden via een WSGI-server |
| Basisopslag | SQLite als uitgangspunt voor één actieve instantie; schrijfbelasting valideren |
| Navigatie | Zijbalk met hoofdmodules, iconen en inklapbare submenu's |
| Productiedistributie | Docker-image en rechtstreekse service-installatie in onprivileged LXC |

Next.js wordt gebruikt voor ontwikkeling en build. Het voorkeursontwerp levert de frontend als statische bestanden via de backend. De geschiktheid daarvan wordt met het eerste prototype gecontroleerd; server rendering en Next.js-serverfuncties zijn geen basisvereiste. Een blijvend draaiende Next.js-runtime wordt alleen toegevoegd als een aantoonbare functionele noodzaak dat rechtvaardigt en het resourcebudget opnieuw is beoordeeld.

De keuze voor deze techniek betekent geen automatische overname van alle ProxMenux-code of dependencies. Alleen benodigde en beoordeelde componenten worden opgenomen. Python-provideradapters gebruiken de ControlDeck-contracten; hostgebonden verzamelscripts worden waar nodig vervangen door API-koppelingen. Licentievoorwaarden en bronvermelding blijven van toepassing bij daadwerkelijk codehergebruik.

Concrete ondersteunde versies worden bij de bouw gecontroleerd en vastgezet. De versiegetallen uit de onderzochte referentie worden niet blind overgenomen. De ontwikkelserver van Flask wordt niet als productieserver gebruikt.

## 16. Latere uitbreiding: boomnavigatie

De goedgekeurde boomnavigatie gebruikt dezelfde modulecatalogus en geautoriseerde resourcegegevens als de overige interface. De hiërarchie is module → onderdeel → resource. Routes en stabiele resource-ID's bepalen de actieve selectie; er komt geen afzonderlijke, hardcoded resourcecatalogus voor het menu.

De hamburgerknop bedient de zichtbaarheid van de zijbalk. Groepsknoppen bedienen de takken en communiceren hun open/dicht-status aan ondersteunende technologie. De bediening krijgt passende toetsenbord- en focusafhandeling. Het mobiele paneel kan met Escape worden gesloten en geeft de focus terug aan de hamburgerknop.

Resourcegroepen worden zo nodig pas geladen bij uitklappen, met begrensde of gepagineerde resultaten om grote inventarissen en onnodige netwerkverzoeken te voorkomen. De backend past de bestaande resourcerechten toe. Dit onderdeel wordt na de basisnavigatie gerealiseerd.

### 16.1 Subpagina's en ankerlinks

Het navigatiemodel ondersteunt bestemmingen met een pad en een optionele fragment-ID. Een item kan bijvoorbeeld verwijzen naar `/proxmox/nodes` of naar `/proxmox#storage`. Fragmenten gebruiken stabiele, unieke sectie-ID's. Een item zonder bestemming kan uitsluitend als uitklapbare groep dienen.

De router bepaalt de actieve subpagina; bij sectienavigatie bepalen het fragment en eventueel de zichtbare sectie het actieve ankeritem. Laden van een directe URL met fragment wacht tot de doelinhoud beschikbaar is. Scrollpositionering houdt rekening met een vaste paginakop. Ankernavigatie ondersteunt toegankelijke focusafhandeling en respecteert de voorkeur voor beperkte animatie.

Navigatie bewaart bruikbare browserhistorie zonder bij iedere scrollbeweging een nieuw historie-item toe te voegen. Beide bestemmingstypen volgen hetzelfde autorisatiebeleid; een ankerlink omzeilt geen toegangscontrole.
