# ControlDeck — Homelab Control Center

> Eén centrale ingang voor infrastructuur, applicaties en dagelijks beheer van het homelab.

**Documenttype:** Visiedocument  
**Versie:** 1.0  
**Datum:** 5 oktober 2026  
**Beoogde projectmap:** `D:\PROJECT\ControlDeck`  
**Status:** Richtinggevend ontwerp; technische keuzes en integraties worden tijdens de realisatie gevalideerd.

## 1. Visie

ControlDeck wordt het centrale webgebaseerde beheerportaal voor het volledige homelab. Het brengt infrastructuur, virtualisatie, opslag, netwerk, monitoring, media, bestanden, bookmarks en virtuele applicaties samen in één herkenbare omgeving.

Het homelab bestaat uit verschillende systemen met eigen adressen, interfaces en beheerprocessen. ControlDeck maakt dit landschap toegankelijk: de gebruiker ziet wat er draait, waar aandacht nodig is en hoe een dienst veilig kan worden geopend of beheerd. IP-adressen en poortnummers verdwijnen naar de achtergrond; systemen worden gepresenteerd op basis van hun naam, functie en status.

ControlDeck vormt een centrale laag boven bestaande toepassingen. Proxmox, Grafana, Uptime Kuma, Kasm, Linkwarden en andere diensten behouden hun eigen rol. Waar integratie waarde toevoegt, toont ControlDeck gegevens en biedt het gerichte acties. Voor gespecialiseerd beheer verwijst het naar de oorspronkelijke toepassing.

De ambitie is een rustig en overzichtelijk control center dat zowel dagelijks gebruik als technisch beheer ondersteunt, thuis en op afstand.

### Gewenst resultaat

- Eén startpunt voor alle belangrijke systemen en applicaties.
- Direct inzicht in beschikbaarheid, capaciteit en relevante waarschuwingen.
- Een korte route van overzicht naar detail en van detail naar een toegestane actie.
- Uitbreiding met nieuwe diensten zonder herbouw van het portaal.
- Veilige toegang vanuit een moderne browser op een daarvoor toegestaan apparaat.

## 2. Kernprincipes

| Principe | Betekenis voor ControlDeck |
| --- | --- |
| **Modulair** | Elke functie is een afzonderlijke module die kan worden ingeschakeld, aangepast of verwijderd. |
| **Configuratiegestuurd** | Servers, diensten, links, dashboards en providerkoppelingen worden zoveel mogelijk via gevalideerde configuratie beschreven. |
| **Eén overzicht** | Het Dashboard bundelt de belangrijkste informatie zonder alle details tegelijk te tonen. |
| **Van overzicht naar detail** | Widgets verwijzen naar detailpagina's en vervolgens naar de relevante beheeromgeving. |
| **Integreren in plaats van vervangen** | Bestaande API's en toepassingen blijven de basis voor specialistische functies. |
| **Browser first** | De interface is bruikbaar vanuit een moderne browser zonder verplichte lokale ControlDeck-client. |
| **Veilig als uitgangspunt** | Toegang, rechten, geheimen en beheeracties worden vanaf het begin bewust ingericht. |
| **Rust en consistentie** | Modules gebruiken dezelfde navigatie, statusbegrippen en interactiepatronen. |
| **Geleidelijke verdieping** | Een module kan beginnen met links en statusinformatie en later uitbreiden met beheerfuncties. |
| **Betrouwbare informatie** | Gegevens tonen hun bron en actualiteit; onbekende status wordt nooit als gezond weergegeven. |

Browser first beschrijft de bediening van ControlDeck. De gekozen route voor toegang op afstand kan aanvullende netwerkvoorzieningen vereisen. Toegang vanaf bijvoorbeeld een bedrijfscomputer blijft afhankelijk van het beleid en de mogelijkheden van dat apparaat.

## 3. Architectuur

### 3.1 Logische opbouw

```text
Gebruiker / browser
        |
        v
Beveiligde toegang en authenticatie
        |
        v
ControlDeck webinterface
  Dashboard | Modules | Zoeken | Instellingen
        |
        v
ControlDeck backend / API
  Autorisatie | Configuratie | Acties | Auditregistratie
        |
        +--> Cache en genormaliseerde statusgegevens
        |
        v
Providerlaag
  Proxmox | Monitoring | Files | Media | Network | Apps
        |
        v
Bestaande homelab-systemen en externe diensten
```

De webinterface presenteert gegevens en acties. De backend bewaakt rechten, verwerkt configuratie en communiceert via providers met onderliggende systemen. Geheimen blijven aan de serverzijde.

Providers vertalen leveranciersspecifieke gegevens naar een gemeenschappelijk model. Hierdoor hoeft een Dashboard-widget niet te weten hoe een bepaalde dienst zijn status aanlevert.

### 3.2 Integratievormen

ControlDeck ondersteunt drie niveaus van integratie:

1. **Openen:** een herkenbare applicatiekaart of link naar de oorspronkelijke dienst.
2. **Inzicht:** status, capaciteit of andere relevante gegevens via een ondersteunde koppeling.
3. **Beheer:** geselecteerde acties via de backend, met expliciete rechten en waar nodig bevestiging.

Een link is een volwaardige eerste integratie. Ingebedde interfaces worden alleen gebruikt wanneer de betreffende toepassing en de beveiligingsinstellingen dit ondersteunen. Openen in een apart tabblad blijft een bruikbare route.

### 3.3 Gegevens en beschikbaarheid

Configuratie, gebruikersvoorkeuren, geheimen en tijdelijke statusgegevens hebben ieder een eigen opslag- en beheerbeleid. Statusgegevens worden waar zinvol gecachet om systemen niet onnodig te belasten.

Een onbereikbare provider mag andere modules niet blokkeren. ControlDeck toont per bron of gegevens actueel, verouderd, onbekend of niet beschikbaar zijn. Time-outs, begrensde retries en duidelijke foutmeldingen voorkomen dat één storing het gehele portaal ontregelt.

Onderliggende diensten blijven zelfstandig bruikbaar wanneer ControlDeck tijdelijk uitvalt. Het portaal wordt geen noodzakelijke schakel in hun normale werking.

## 4. Hoofdmenu en gebruikerservaring

Het hoofdmenu volgt de functies van het homelab:

```text
Dashboard
Proxmox
Terminal
Files
Media
Network
Monitoring
Bookmarks
Virtual Apps
──────────────
Instellingen
```

Het Dashboard is de standaard startpagina. De navigatie blijft consistent op desktop, tablet en mobiel. Modules zijn alleen zichtbaar wanneer zij zijn ingeschakeld en de gebruiker er toegang toe heeft.

Een centrale zoekfunctie kan op termijn servers, applicaties, bookmarks en beschikbare acties ontsluiten. Favorieten geven veelgebruikte onderdelen een vaste plek. Status wordt aangegeven met tekst en herkenbare symbolen, zodat kleur niet de enige informatiedrager is.

Instellingen bevat onder meer modulebeheer, providerconfiguratie, gebruikers en rechten, dashboardindeling en algemene voorkeuren. Gevoelige instellingen zijn uitsluitend toegankelijk voor bevoegde beheerders.

## 5. Modules

### 5.1 Dashboard

**Doel:** binnen enkele seconden begrijpen hoe het homelab ervoor staat.

Het Dashboard toont een compacte selectie van systeemstatus, beschikbare capaciteit, waarschuwingen en favoriete applicaties. Denk aan bereikbaarheid van diensten, CPU- en geheugengebruik, opslagcapaciteit en samengevatte monitoringmeldingen.

Widgets zijn configureerbaar en verwijzen naar een detailpagina of de oorspronkelijke toepassing. Alleen informatie die helpt bij een beslissing krijgt een prominente plaats. De gebruiker kan later eigen indelingen maken voor bijvoorbeeld beheer, media of dagelijks gebruik.

### 5.2 Proxmox

**Doel:** virtualisatie-infrastructuur overzichtelijk maken en veelgebruikte beheerhandelingen toegankelijk aanbieden.

De module is gericht op nodes, virtuele machines, containers en opslag. Zij toont status en gebruik, biedt doorklikmogelijkheden en kan later geselecteerde acties ondersteunen, zoals starten, gecontroleerd afsluiten of herstarten.

Beheeracties vereisen passende rechten en tonen duidelijk het betrokken systeem. Risicovolle handelingen vragen bevestiging. Specialistische taken blijven bereikbaar in de Proxmox-interface. Integratie verloopt via een provider met zo beperkt mogelijke toegangsrechten.

### 5.3 Terminal

**Doel:** bevoegde beheerders browsergebaseerde toegang geven tot geselecteerde hosts.

De module biedt een overzicht van toegestane terminaldoelen en kan aansluiten op een bestaande browserterminal of een afzonderlijke terminalgateway. Hosts, gebruikersrechten en sessiebeleid worden centraal vastgelegd.

Terminaltoegang krijgt een afzonderlijke permissie, korte sessieduur en bescherming tegen onbevoegd openen van verbindingen. Wachtwoorden en privésleutels worden niet aan de browser geleverd. Auditregistratie legt sessiemetadata vast; opname van terminalinhoud vraagt een expliciet beleid voor privacy en geheimen.

### 5.4 Files

**Doel:** bestanden en opslaglocaties via één ingang bereikbaar maken.

De module groepeert shares, opslagdiensten en bestandsapplicaties. De eerste versie kan bestaan uit links en capaciteitsinformatie. Latere uitbreiding kan bladeren, uploaden, downloaden en gericht bestandsbeheer omvatten via daarvoor geschikte providers.

Toegang wordt per locatie begrensd. Verwijderen en overschrijven krijgen passende bescherming. Het portaal geeft nooit automatisch toegang tot het volledige bestandssysteem van de host.

### 5.5 Media

**Doel:** mediatoepassingen en hun belangrijkste statusinformatie samenbrengen.

De module biedt toegang tot bijvoorbeeld Plex, Jellyfin, Sonarr en Radarr. Waar een geschikte koppeling beschikbaar is, kunnen bibliotheekstatus, activiteit of verwerkingstaken worden weergegeven.

Afspelen en specialistiek bibliotheekbeheer blijven bij de mediatoepassingen. ControlDeck richt zich op overzicht, navigatie en zorgvuldig gekozen acties. Persoonlijke kijkactiviteit wordt alleen getoond aan gebruikers die daarvoor bevoegd zijn.

### 5.6 Network

**Doel:** inzicht geven in netwerkdiensten en veilige bereikbaarheid.

De module kan netwerkcomponenten, DNS, domeinen en toegangsvoorzieningen groeperen. Technitium DNS, Cloudflare en Tailscale zijn mogelijke integratiepunten, afhankelijk van de uiteindelijke inrichting.

De eerste nadruk ligt op status en navigatie. Wijzigingen aan DNS, routering of toegangsregels worden pas toegevoegd wanneer rechten, validatie, auditregistratie en herstelmogelijkheden zijn uitgewerkt.

### 5.7 Monitoring

**Doel:** afwijkingen zichtbaar maken en onderzoek naar de oorzaak versnellen.

ControlDeck brengt beschikbaarheidsinformatie, waarschuwingen en relevante meetgegevens samen. Uptime Kuma en Grafana zijn mogelijke bronnen of bestemmingen voor verdere analyse.

Het Dashboard toont de samenvatting; Monitoring biedt verdieping met bron, tijdstip en een route naar de relevante dienst. Bestaande monitoring- en alarmeringssystemen behouden hun functie. ControlDeck voegt context en samenhang toe.

### 5.8 Bookmarks

**Doel:** diensten, documentatie en veelgebruikte bronnen vindbaar houden.

Bookmarks worden georganiseerd met namen, categorieën, tags en favorieten. Een koppeling met Linkwarden is een mogelijke route; een eenvoudige configuratiegestuurde linkverzameling kan als eerste versie dienen.

Persoonlijke en gedeelde bookmarks kunnen later naast elkaar bestaan. De gebruiker moet kunnen zien of een link een interne dienst, externe bron of beheeromgeving opent.

### 5.9 Virtual Apps

**Doel:** virtuele applicaties en werkomgevingen vanuit het portaal starten.

De module presenteert een catalogus van beschikbare applicaties en desktops. Kasm is een mogelijk integratiepunt. Een eerste uitvoering biedt toegang tot bestaande startpagina's; latere providers kunnen toegestane sessies starten en hun status tonen.

Beschikbaarheid, gebruikersrechten, sessieduur en resourcegrenzen blijven leidend. De oorspronkelijke applicatie- of sessieprovider beheert de uitvoering van de virtuele omgeving.

## 6. Inspiratiebronnen

De volgende projecten dienen als ontwerp- en productreferenties. De tabel beschrijft de gewenste inspiratie voor ControlDeck, geen vastgestelde technische afhankelijkheden of gegarandeerde functies van deze producten.

| Inspiratiebron | Ontwerprichting voor ControlDeck |
| --- | --- |
| **ProxMenux Monitor** | Een infrastructuurgericht overzicht als referentie voor de Proxmox-module en de presentatie van systeeminformatie. |
| **Homarr** | Een persoonlijke startomgeving met herkenbare applicatiekaarten en een aanpasbare indeling. |
| **Homepage** | Een overzichtelijke, configuratiegestuurde presentatie van diensten en statuswidgets. |
| **Linkwarden** | Het centraal organiseren en terugvinden van bookmarks en kennisbronnen. |
| **Glance** | Een rustig dashboard waarin compacte informatieblokken snel te lezen zijn. |

ControlDeck ontwikkelt een eigen samenhangende gebruikerservaring. Bij daadwerkelijk hergebruik van code of assets worden de toepasselijke licenties en voorwaarden gecontroleerd.

## 7. Security

### 7.1 Toegang en identiteit

ControlDeck wordt primair ingericht als afgeschermd beheerportaal. Toegang op afstand verloopt via een bewust gekozen beveiligde route, bijvoorbeeld een privénetwerk of een beschermde toegangsgateway. Een publiek bereikbaar beheerportaal is geen standaarduitgangspunt.

Alle toegang gebruikt versleutelde verbindingen. Authenticatie ondersteunt waar mogelijk een centrale identityprovider en multifactorauthenticatie. Netwerktoegang vervangt de autorisatie binnen ControlDeck niet.

### 7.2 Rechten

Rechten worden per module, resource en actie gecontroleerd aan de serverzijde. Een mogelijke eerste rolverdeling is:

- **Viewer:** bekijkt toegestane statusinformatie en links.
- **Operator:** voert expliciet toegekende dagelijkse acties uit.
- **Administrator:** beheert configuratie, providers en toegangsrechten.

Verborgen knoppen vormen geen beveiligingsgrens. Terminaltoegang, bestandswijzigingen en infrastructuuracties krijgen afzonderlijke permissies.

### 7.3 Geheimen en verbindingen

API-tokens, wachtwoorden en sleutels worden buiten publieke configuratie, broncode en browseropslag gehouden. Configuratie verwijst naar geheimen die veilig aan de backend worden geleverd. Tokens krijgen minimale rechten en een beleid voor rotatie en intrekking.

Providerdoelen worden gecontroleerd en waar mogelijk begrensd tot toegestane hosts. Certificaatvalidatie staat standaard aan. Logs en foutmeldingen mogen geen geheimen prijsgeven.

### 7.4 Acties en auditregistratie

ControlDeck registreert wie een beheeractie uitvoert, op welk doel, wanneer en met welk resultaat. Destructieve of verstorende acties tonen vooraf de gevolgen en vragen bevestiging.

Sessies, webverzoeken en terminalverbindingen worden beschermd tegen ongeautoriseerd gebruik. De uitwerking omvat onder meer veilige cookies, bescherming tegen CSRF waar relevant, invoervalidatie en begrenzing van verzoeken.

### 7.5 Continuïteit

Configuratie en noodzakelijke persistente gegevens krijgen een backup- en herstelprocedure. Updates worden gecontroleerd uitgevoerd. Het ontwerp houdt rekening met het hoge privilege van een centraal beheerportaal: alleen benodigde koppelingen en acties worden ingeschakeld.

## 8. Modulair en provider-model

### 8.1 Scheiding van verantwoordelijkheden

Een **module** beschrijft de gebruikersfunctie, zoals Media of Monitoring. Een **provider** verbindt die functie met een specifieke dienst. Een **widget** presenteert een beperkte hoeveelheid informatie uit één of meer providers.

Zo kan Media meerdere providers gebruiken, terwijl een monitoringprovider zowel de Monitoring-module als het Dashboard voedt. Een module blijft bruikbaar wanneer een optionele provider ontbreekt.

### 8.2 Gemeenschappelijke contracten

Elke provider declareert zijn mogelijkheden, bijvoorbeeld status lezen, resources ophalen of een bepaalde actie uitvoeren. Modules tonen alleen functies die de gekoppelde provider daadwerkelijk ondersteunt en waarvoor de gebruiker rechten heeft.

Het gemeenschappelijke gegevensmodel omvat ten minste:

- Een stabiele resource-identiteit, naam en type.
- De provider en bron van de informatie.
- Een genormaliseerde status en tijdstip van de laatste succesvolle update.
- Beschikbare meetwaarden met eenheden.
- Ondersteunde acties en de daarvoor vereiste rechten.
- Foutinformatie die bruikbaar is zonder gevoelige gegevens te onthullen.

Providers handelen authenticatie, time-outs, foutvertaling en leveranciersspecifieke verschillen af. De backend verzorgt de uiteindelijke autorisatie en auditregistratie.

### 8.3 Configuratie en uitbreiding

Configuratie bepaalt welke modules actief zijn, welke providers eraan gekoppeld worden en welke resources zichtbaar zijn. Het exacte formaat wordt tijdens de technische uitwerking gekozen. Configuratie krijgt schemavalidatie, versiebeheer en een migratiepad.

Nieuwe providers volgen een gedocumenteerd contract en worden gecontroleerd voordat zij worden geactiveerd. Dynamisch laden van willekeurige externe code is geen vereiste voor de eerste versie. Een afgebakende providerlaag biedt al de gewenste uitbreidbaarheid.

Het model maakt latere ondersteuning van andere virtualisatie-, opslag-, monitoring- of applicatieplatformen mogelijk zonder de gehele interface opnieuw te ontwerpen.

## 9. Realisatierichting

### Fase 1 — Centrale ingang

Een werkend portaal met authenticatie, het hoofdmenu, configureerbare applicatielinks, favorieten en een eenvoudig Dashboard. Alle negen modules krijgen een duidelijke bestemming; alleen beschikbare integraties worden geactiveerd.

**Resultaat:** de gebruiker vindt de belangrijkste diensten vanuit één omgeving.

### Fase 2 — Betrouwbaar inzicht

De providerlaag wordt ingevuld met een eerste Proxmox-koppeling en monitoringinformatie. Statuswidgets tonen actualiteit en storingen. Configuratievalidatie en veilige opslag van geheimen worden onderdeel van het beheer.

**Resultaat:** het portaal geeft een bruikbaar en betrouwbaar beeld van het homelab.

### Fase 3 — Gerichte bediening

Geselecteerde beheeracties worden toegevoegd, met rechten, bevestiging en auditregistratie. Terminal, Files en Virtual Apps krijgen verdieping waar dit aantoonbaar waarde toevoegt.

**Resultaat:** veelgebruikte handelingen kunnen veilig vanuit ControlDeck worden uitgevoerd.

### Fase 4 — Persoonlijke werkomgeving

Verdere uitbreiding met persoonlijke dashboards, zoeken, aanvullende providers en eventueel meldingen of gecontroleerde automatisering.

**Resultaat:** ControlDeck groeit mee met het homelab zonder zijn eenvoud te verliezen.

De fasering is een richting, geen vastgelegde planning. De eerstvolgende stap is een klein werkend fundament; de technische stack en definitieve integratiekeuzes volgen uit de eisen en beschikbare systemen.

## 10. Toekomstbeeld

ControlDeck groeit uit tot de dagelijkse startpagina voor het homelab. De beheerder ziet direct welke systemen aandacht vragen, opent relevante details en voert toegestane acties uit. Andere gebruikers krijgen een eenvoudiger omgeving met de applicaties, bestanden en media waarvoor zij rechten hebben.

Mogelijke uitbreidingen zijn meerdere locaties of clusters, persoonlijke dashboards, centrale zoekfuncties, relevante notificaties, capaciteitsontwikkeling en gecontroleerde workflows. Automatisering wordt pas toegevoegd wanneer handelingen betrouwbaar, herleidbaar en voldoende begrensd zijn.

De kern blijft hetzelfde: één duidelijke ingang, betrouwbare informatie en een korte route naar de juiste toepassing.

## 11. Succescriteria

ControlDeck voldoet aan zijn visie wanneer:

- De belangrijkste homelab-diensten zonder kennis van hun IP-adres of poortnummer te vinden zijn.
- Het Dashboard onderscheid maakt tussen gezond, afwijkend, onbekend en verouderd.
- Een storing in één provider de overige modules bruikbaar laat.
- Een nieuwe dienst kan worden toegevoegd via configuratie of een afgebakende provider.
- Beheeracties uitsluitend door bevoegde gebruikers uitgevoerd kunnen worden en herleidbaar zijn.
- De interface prettig werkt op desktop en mobiel en geen overbodige informatie toont.
- De oorspronkelijke toepassingen zelfstandig bereikbaar en bruikbaar blijven.

---

**ControlDeck — Homelab Control Center**  
Een modulair, veilig en overzichtelijk portaal dat het homelab als één samenhangende omgeving presenteert.

## 12. Aanvulling: open source, navigatie en lichte hosting

ControlDeck wordt ontwikkeld met het doel het later als open-sourceproject via GitHub beschikbaar te stellen. Andere homelabgebruikers moeten het met eigen configuratie kunnen installeren. Bestaande open-sourceonderdelen kunnen worden hergebruikt nadat hun technische geschiktheid en toepasselijke licenties zijn gecontroleerd.

ProxMenux Monitor is de belangrijkste visuele referentie voor de zijbalk, kaarten en overzichtelijke indeling. ControlDeck voegt daar hoofdmenu-items met inklapbare submenu's aan toe, zodat de negen modules binnen één consistente interface kunnen groeien.

Docker en een onprivileged LXC zijn beide doelplatformen. Laag resourcegebruik is een ontwerpeis: een lichte basisinstallatie, vooraf gebouwde frontend, beperkte achtergrondtaken en geen verplichte extra monitoring- of cachestack. De functionele en technische documenten werken deze richting uit. Resourcebudgetten zijn voorlopig en worden tijdens het prototype gemeten.
