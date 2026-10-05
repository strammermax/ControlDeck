# ControlDeck — Globaal functioneel ontwerp

**Versie:** 1.0  
**Datum:** 5 oktober 2026  
**Status:** Ontwerp voor verdere uitwerking  
**Basis:** `visie.md`  
**Bijbehorend document:** `technisch-ontwerp.md`

## 1. Doel en afbakening

ControlDeck biedt één browseromgeving voor het vinden, bekijken en gericht beheren van het homelab. Dit document beschrijft wat gebruikers kunnen doen, hoe de belangrijkste schermen werken en welke resultaten worden verwacht. Het technisch ontwerp beschrijft de inrichting die dit mogelijk maakt.

De volledige productrichting omvat negen modules. De eerste release richt zich op toegang, navigatie, favorieten en configuratiegestuurde links. Statusintegraties en beheeracties worden vervolgens stapsgewijs toegevoegd. Bestaande applicaties behouden hun specialistische functies.

ControlDeck is in deze opzet geen vervanging voor virtualisatiebeheer, monitoring, een mediaserver, bestandsopslag of een virtual-app-platform. Integraties zijn afhankelijk van de daadwerkelijk beschikbare systemen en hun interfaces.

## 2. Gebruikers en rechten

| Rol | Hoofdgebruik | Rechten |
| --- | --- | --- |
| Viewer | Diensten openen en toegestane informatie bekijken | Lezen en navigeren binnen toegewezen modules en resources |
| Operator | Dagelijks beheer uitvoeren | Viewer-rechten plus afzonderlijk toegekende acties |
| Administrator | ControlDeck inrichten | Modules, koppelingen, configuratie en rechten beheren |

Een rol geeft geen onbeperkte toegang tot alle onderliggende diensten. Toegang kan per resource worden beperkt. Terminaltoegang en bestandswijzigingen vragen afzonderlijke rechten. De oorspronkelijke applicatie kan daarnaast een eigen login vereisen; automatisch aanmelden is geen toezegging van de eerste release.

## 3. Navigatie en schermopbouw

Het hoofdmenu bevat Dashboard, Proxmox, Terminal, Files, Media, Network, Monitoring, Bookmarks en Virtual Apps. Instellingen staat apart onderaan. Alleen ingeschakelde, toegestane modules verschijnen in het menu.

Elke module gebruikt dezelfde basisopbouw: titel en korte toelichting, beschikbare filters, een overzicht en een detailweergave. De detailweergave vermeldt de bron, relevante status, laatste update, beschikbare acties en een link naar de oorspronkelijke toepassing.

Op desktop staat de navigatie naast de inhoud; op kleinere schermen is zij inklapbaar. De bediening ondersteunt toetsenbordgebruik, herkenbare focus, leesbare labels en statusinformatie die ook zonder kleur begrijpelijk is.

### Standaard schermtoestanden

| Toestand | Gedrag |
| --- | --- |
| Laden | Toon dat gegevens worden opgehaald; voorkom onbedoelde dubbele acties |
| Leeg | Leg uit dat nog geen resources of koppelingen aanwezig zijn |
| Niet geconfigureerd | Toon een bruikbare uitleg en voor beheerders een route naar instellingen |
| Geen toegang | Geef geen gevoelige details vrij; bied een duidelijke toegangsboodschap |
| Bron onbereikbaar | Toon de storing, laatste bekende gegevens en hun actualiteit |
| Actie in uitvoering | Toon voortgang of wachtstatus en blokkeer herhaalde uitvoering waar nodig |
| Actie mislukt | Toon een begrijpelijke fout en een referentie voor onderzoek |

## 4. Functionele eisen per module

| ID | Module | Eerste invulling | Latere verdieping |
| --- | --- | --- | --- |
| F-01 | Dashboard | Startpagina met favoriete diensten en geconfigureerde kaarten | Statuswidgets, capaciteit, waarschuwingen en persoonlijke indeling |
| F-02 | Proxmox | Links naar toegestane beheeromgevingen | Nodes, VM's, containers en opslag bekijken; geselecteerde start- en afsluitacties |
| F-03 | Terminal | Links naar toegestane bestaande terminalvoorzieningen | Beveiligde sessies via een afzonderlijke gateway |
| F-04 | Files | Overzicht van opslaglocaties en bestandsapplicaties | Capaciteit, bladeren, uploaden, downloaden en begrensde wijzigingen |
| F-05 | Media | Catalogus van media-applicaties | Bibliotheekinformatie en relevante activiteit per provider |
| F-06 | Network | Netwerkdiensten en beheerlinks | DNS-, netwerk- en bereikbaarheidsinformatie; later gecontroleerde wijzigingen |
| F-07 | Monitoring | Links naar monitoringomgevingen | Beschikbaarheid, meldingen en meetgegevens met doorklik naar de bron |
| F-08 | Bookmarks | Gedeelde links, categorieën, tags en persoonlijke favorieten | Persoonlijke verzamelingen en een bookmark-provider |
| F-09 | Virtual Apps | Catalogus met links naar bestaande applicatieportalen | Sessies starten, actieve sessies tonen en beëindigen indien ondersteund |

De eerste release presenteert een link niet als gemeten beschikbaarheid. Een kaart zonder statuskoppeling vermeldt dat geen statusinformatie beschikbaar is.

### Dashboard

Het Dashboard geeft prioriteit aan aandachtspunten en veelgebruikte diensten. Een widget opent de betreffende module of bron. Ontbrekende informatie wordt expliciet vermeld; een niet aangesloten dienst krijgt geen groene status.

### Proxmox en Monitoring

Bij verdieping kan de gebruiker resources filteren en details bekijken. Capaciteitsgegevens bevatten eenheden en tijdstip. Monitoringmeldingen tonen ernst, bron en waarnemingstijd. Het bevestigen van een melding in de bron is pas mogelijk wanneer die integratie dit expliciet ondersteunt.

### Terminal, Files en Virtual Apps

Deze modules voeren uitsluitend handelingen uit op toegewezen doelen. Bij sessies ziet de gebruiker het doel en de verbindingstoestand. Bij bestanden worden locatie en gevolgen van overschrijven of verwijderen duidelijk weergegeven. Een virtual-app-sessie toont de betreffende applicatie en haar status; de provider bepaalt beschikbare sessiemogelijkheden.

### Media, Network en Bookmarks

Media presenteert relevante toepassingen zonder gevoelige gebruiksinformatie breed te delen. Network begint met inzicht; wijzigingen vragen een afzonderlijk ontwerp. Bookmarks biedt categorieën en tags zodat interne beheerlinks en externe documentatie herkenbaar zijn.

## 5. Belangrijkste gebruikersprocessen

### 5.1 Een dienst openen

1. De gebruiker meldt zich aan.
2. ControlDeck toont het Dashboard met toegestane kaarten.
3. De gebruiker kiest een dienst of navigeert naar een module.
4. De oorspronkelijke toepassing opent in een apart tabblad, tenzij een ondersteunde integratie een andere route biedt.

Een bookmark of applicatielink verleent op zichzelf geen rechten in de bestemming.

### 5.2 Een storing onderzoeken

1. Een statuswidget toont een afwijking en de actualiteit van de informatie.
2. De gebruiker opent de details.
3. ControlDeck toont bron, relevante metingen en eventuele foutmelding.
4. De gebruiker opent de monitoring- of beheeromgeving voor verder onderzoek.

Als de bron onbereikbaar is, blijven laatst bekende gegevens zichtbaar met het label verouderd of onbekend.

### 5.3 Een beheeractie uitvoeren

1. De gebruiker selecteert een resource en een toegestane actie.
2. ControlDeck toont doel en gevolgen en vraagt zo nodig bevestiging.
3. De actie wordt uitgevoerd na een nieuwe rechtencontrole.
4. De gebruiker ziet het resultaat of de voortgang.
5. De actie en haar uitkomst worden geregistreerd.

Een geaccepteerde aanvraag is nog geen geslaagde uitvoering. Bij onzekere uitkomst wordt dat expliciet getoond.

### 5.4 Een koppeling toevoegen

1. De beheerder kiest een ondersteund providertype.
2. De beheerder vult naam, doeladres en een verwijzing naar benodigde geheimen in.
3. ControlDeck valideert de configuratie en test de verbinding.
4. De beheerder koppelt de provider aan modules en kent toegang toe.
5. Na activering verschijnen de beschikbare functies.

In de eerste release kan dit proces via een gevalideerd configuratiebestand verlopen. Een instellingenformulier voor alle configuratie is een vervolgstap.

## 6. Algemene functionele eisen

| ID | Eis |
| --- | --- |
| F-10 | Toegang vereist authenticatie; uitloggen beëindigt de ControlDeck-sessie |
| F-11 | Menu, gegevens en acties volgen de toegewezen rechten |
| F-12 | Een gebruiker kan toegestane diensten als favoriet markeren |
| F-13 | Configuratiefouten geven gerichte meldingen; ongeldige wijzigingen worden niet actief |
| F-14 | Statusinformatie toont bron en laatste succesvolle update |
| F-15 | Storingen in een koppeling verhinderen het gebruik van andere modules niet |
| F-16 | Verstoring of gegevensverlies veroorzakende acties vragen passende bevestiging |
| F-17 | Beheeracties zijn herleidbaar naar gebruiker, doel, tijd en resultaat |
| F-18 | Geheimen worden niet in kaarten, foutmeldingen of configuratie-export weergegeven |
| F-19 | De interface blijft bruikbaar op desktop en mobiel |

## 7. Statusmodel

Gezondheid en actualiteit zijn afzonderlijke eigenschappen. Een dienst kan bijvoorbeeld laatst als gezond zijn gemeten terwijl die meting inmiddels verouderd is.

**Gezondheid:** gezond, waarschuwing, storing of onbekend.  
**Actualiteit:** actueel, verouderd of nog niet gemeten.  
**Verbinding met de bron:** bereikbaar, onbereikbaar of niet geconfigureerd.

ControlDeck maakt het verschil zichtbaar tussen een defecte dienst en een defecte meetkoppeling. Een verbindingsfout betekent niet automatisch dat het onderliggende systeem uitgevallen is.

## 8. Fasering en acceptatie

| Fase | Oplevering | Acceptatie |
| --- | --- | --- |
| 1 — Centrale ingang | Login, menu, configuratie, links en favorieten | Gebruiker vindt en opent toegestane diensten; ongeautoriseerde toegang wordt geweigerd |
| 2 — Inzicht | Proxmox- en monitoringgegevens via gevalideerde providers | Status en actualiteit kloppen; een bronstoring blokkeert andere modules niet |
| 3 — Bediening | Geselecteerde beheeracties en auditregistratie | Rechten, bevestiging, voortgang en foutafhandeling werken aantoonbaar |
| 4 — Uitbreiding | Persoonlijke dashboards, zoeken en extra providers | Nieuwe providers passen in bestaande navigatie en rechtenstructuur |

## 9. Openstaande beslissingen

Voor de technische realisatie moeten de aanwezige systemen, doelgroepen, toegang op afstand en identityprovider worden geïnventariseerd. Ook de eerste concrete widgets, resourcegroepen en beheeracties moeten worden gekozen.

Terminalbediening, bestandswijzigingen, netwerkwijzigingen en automatisering krijgen een aanvullende functionele uitwerking voordat zij worden gebouwd. Dit globale document vormt het kader voor die detailontwerpen.

## 10. Aanvulling: navigatie, open source en installatie

Deze aanvulling concretiseert de gebruikerswensen na versie 1.0 en geldt als uitgangspunt voor de verdere uitwerking.

### Hoofdmenu met inklapbare submenu's

De vormgeving van ProxMenux Monitor is de belangrijkste visuele referentie. ControlDeck krijgt een vaste zijbalk met herkenbare iconen, actieve selectie en inklapbare groepen. De onderstaande subitems zijn een voorstel; zij verschijnen alleen wanneer de bijbehorende functie is geïmplementeerd, geconfigureerd en toegestaan.

| Hoofdmenu | Voorgestelde subitems |
| --- | --- |
| Dashboard | Overzicht, Favorieten |
| Proxmox | Overzicht, Nodes, Virtuele machines, Containers, Storage |
| Terminal | Hosts, Actieve sessies |
| Files | Opslaglocaties, Bestandsapps |
| Media | Overzicht, Mediaservers, Bibliotheekbeheer |
| Network | Overzicht, DNS, Domeinen, Toegang op afstand |
| Monitoring | Status, Meldingen, Dashboards |
| Bookmarks | Alle links, Categorieën, Favorieten |
| Virtual Apps | Catalogus, Actieve sessies |
| Instellingen | Modules, Providers, Gebruikers en rechten, Vormgeving, Over ControlDeck |

Het hoofditem opent het moduleoverzicht; een afzonderlijke knop klapt subitems in of uit. De actieve groep blijft open. Directe links naar subpagina's werken ook na verversen. Op mobiel sluit de navigatie na een keuze. Uitklappen werkt met toetsenbord en geeft de open/dicht-status door aan ondersteunende technologie.

### Publiek herbruikbaar project

ControlDeck wordt ontworpen voor toekomstige open-sourcepublicatie op GitHub. Andere gebruikers moeten hun eigen homelab kunnen aansluiten zonder code aan te passen. De distributie bevat fictieve voorbeeldconfiguratie, installatie-instructies, upgrade- en backupinstructies en een overzicht van ondersteunde providers.

Persoonlijke adressen, credentials en gegevens blijven buiten de publieke distributie. Een pagina Over ControlDeck vermeldt versie, bronrepository, licentie en erkenning van hergebruikte onderdelen. Publicatie op GitHub is een vervolgstap; met deze documentatie wordt nog geen repository gepubliceerd.

### Installatie en licht gebruik

Ondersteunde doelvormen zijn een Docker-installatie en installatie als service in een onprivileged LXC. De eenvoudige basisinstallatie vereist geen volledige monitoringstack, externe cache of afzonderlijke databaseserver. Media, virtuele desktops en terminaldoelen draaien buiten ControlDeck; hun resourcegebruik hoort niet bij het portaal.

Acceptatie omvat beide installatievormen, behoud van configuratie na herstart en bruikbaarheid met beperkte resources. Het technisch ontwerp bevat voorlopige meetdoelen; daadwerkelijke minimale systeemeisen volgen na het prototype.


### Vastgelegde basis voor de interface

De ProxMenux Monitor-indeling is gekozen als basis voor de leesbare ControlDeck-interface: een herkenbare zijbalk, hoofdmenu-items met inklapbare submenu's en consistente kaarten. De gekozen techniek en het plan voor een lichte runtime zijn vastgelegd in sectie 15 van het technisch ontwerp.


### Latere uitbreiding: boommenu met hamburgerknop

Een goedgekeurde vervolgstap is een boommenu aan de linkerkant, met de hiërarchie module → onderdeel → resource. Bijvoorbeeld: Proxmox → Nodes → servernaam. Een hamburgerknop opent en sluit de gehele zijbalk; afzonderlijke uitklapknoppen bedienen de groepen.

Op desktop kan het menu open blijven. Op mobiel verschijnt het als tijdelijk paneel over de inhoud en sluit het na navigatie. De actieve pagina en haar bovenliggende groepen blijven herkenbaar. Alleen toegestane modules en resources worden getoond. Dit is een latere uitbreiding van de eerder beschreven navigatie, geen extra eis voor de eerste release.

### Bestemmingen in het boommenu

Items in het boommenu kunnen verwijzen naar een afzonderlijke subpagina of naar een sectie binnen de huidige pagina via een ankerlink. Een module kan beide vormen combineren. Een subpagina is geschikt voor een zelfstandig overzicht of resource-detail; een ankerlink is geschikt voor onderdelen van dezelfde overzichtspagina.

Bij een ankerlink blijft de gebruiker op de pagina en wordt de betreffende sectie zichtbaar. De actieve bestemming blijft herkenbaar in het menu. Directe links en de terugknop van de browser blijven bruikbaar. Uitklappen van een menugroep en navigeren naar een bestemming blijven afzonderlijke handelingen.
