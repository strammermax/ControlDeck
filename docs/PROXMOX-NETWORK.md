# Proxmox Network

`#proxmox/network` gebruikt de ProxMenux-overzichtskaarten en interfacekaarten, afgeleid van `AppImage/components/network-metrics.tsx` (overzicht vanaf regel 650, fysieke kaarten vanaf regel 198) en `network-card.tsx`, commit `d4e98d16b11733e518b0162db1b528b2ecd4cc53`, GPL-3.0. Het bestaande `#network` blijft een compatibele weergave. Vier kaarten, kleuren, dubbele RX/TX-kop en interface-indeling zijn naar scoped CSS overgebracht. Gedeelde kaarten/iconen komen uit dezelfde bouwstenen als VMs en Storage. De historische grafiek gebruikt Recharts zoals upstream; deze wordt statisch meegebundeld en vereist geen extra runtime.

## Historische Network Traffic-grafiek

De grafiek boven Network Flow gebruikt `AppImage/components/network-traffic-chart.tsx` van dezelfde ProxMenux-commit als bron: Received groen, Sent blauw, gevulde monotone lijnen, raster, gedraaide tijdlabels, hoverdetails en afzonderlijk schakelbare reeksen. De periodekeuze biedt 1 uur, 24 uur (standaard), 7 dagen, 30 dagen en 1 jaar. Dezelfde grafiek reageert op Cluster of de gekozen node. Recharts is vastgezet op 3.10.1; de oorspronkelijke 2.x-branche is niet als nieuwe dependency ingevoerd. De API-/fetchlaag is vervangen door ControlDeck-sessies en begrensde gegevensprojectie.

`GET /api/proxmenux/network/history?timeframe=day` accepteert uitsluitend `hour`, `day`, `week`, `month`, `year`, één keer en zonder andere parameters. De bestaande Proxmox-modulerechten en monitor-CA/tokenverbinding blijven gelden. Serverzijdig wordt alleen het vaste pad `node/metrics?timeframe=<periode>` aangeroepen, hetzelfde RRD-bronpad als in ProxMenux. Iedere periode heeft een eigen achtergrondcache. Alleen tijd, ontvangen/verzonden bytes per seconde, interval en beschikbaarheidsstatus worden geprojecteerd; CPU-, geheugen-, account- en configuratievelden komen niet mee.

De Y-as toont GB per meetinterval, zoals upstream, geen GB/s. Byte/s wordt geïntegreerd over het interval. Het eerste punt gebruikt de werkelijke intervalduur, niet de upstream hardcoded 60 seconden. De gebruikelijke dagresolutie is vijf minuten. Kortere intervallen van oudere monitors worden binnen hetzelfde tijdvak samengevoegd voordat nodes worden opgeteld. De clustergrafiek gebruikt het gemeenschappelijke tijdvenster; onvolledige randintervallen worden afgeknipt. Bij een ontbrekende node of sample blijft het clustertotaal voor dat tijdvak onbekend; ontbrekende data wordt nooit nul. Een gat in timestamps vergroot de intervalduur niet. Periodewissels tonen geen achtergebleven curves uit de vorige selectie. De bovenste verkeerskaart blijft expliciet cumulatief sinds tellerstart; de historische grafiek toont de gekozen periode.

`tests/test_network_history.py` test veilige projectie, lege/null-metingen, ongeldige/duplicaatdata, gap-intervallen, periodecache, vaste upstream-paden, gedeeltelijke uitval en sessie-/modulerechten. `frontend/tests/proxmox-network-history.test.mjs` dekt tijduitlijning, gemengde resoluties, de regressie van het eerste interval, ontbrekende clusterwaarden, afwijzing en de echte legenda-/periode-/tooltipweergave. Browseracceptatie controleert de grafiek, periode- en nodekeuze, legenda en mobiele breedte.

## Gebruik

- Cluster en afzonderlijke nodes tonen dezelfde gegevensbron. De nodekeuze komt uit de bestaande Proxmox-clusterverbinding. Monitoren buiten deze inventaris worden genegeerd.
- Network Traffic telt uitsluitend fysieke interfaces per node. Bonds, bridges en virtuele interfaces tellen niet opnieuw mee. Een pakket tussen twee clusterhosts verschijnt op beide fysieke poorten; het getal is dus geen uniek internetverbruik.
- Bytes zijn cumulatieve tellers sinds de teller-/hoststart. RX/TX in bytes per seconde gebruikt de monitorsnelheid; oudere monitors zonder snelheden krijgen een afgeleide snelheid uit twee opeenvolgende tellermetingen (1–180 seconden). Een tellerreset, te lange pauze of eerste meting geeft geen afgeleide snelheid. Ontbrekende waarden zijn `—`, nul blijft nul. De kaart vermeldt expliciet dat het cumulatieve verkeer betreft.
- Active Interfaces onderscheidt fysieke poorten, bridges, bonds en VM/LXC-interfaces. Network Status toont fysieke fout- en droptellers; dit is geen berekende end-to-end packet-lossmeting. Historische drops maken een verbinding niet automatisch defect.
- Gateway Latency toont de meting en het laatste uur per node. De clusterkop is de hoogste beschikbare actuele nodewaarde, geen optelsom. Ontbrekende of verouderde nodes maken de kaart onvolledig.
- Network Flow gebruikt nu ook de originele `AppImage/components/network-flow.tsx`: de SVG-geometrie, iconen, desktop-/mobiele plaatsing en bewegende RX/TX-pulsen worden hergebruikt. Cluster toont alle node-diagrammen samen, met NIC → bond → host → bridge → VM/LXC. De host heet de echte nodenaam. Gelijknamige bridges op verschillende nodes blijven afzonderlijk. Ongebruikte bridges blijven zichtbaar. Bij onbekende rates staat `—`; verouderde data animeert niet. `prefers-reduced-motion` schakelt bewegende pulsen uit.
- Een gastinterface wordt gekoppeld via de gemelde kernelmaster of de ledenlijst van een bridge. Bij ontbrekend bewijs komt zij onder ‘Onbekende bridge’, nooit willekeurig onder de eerste bridge. De clustermap veronderstelt geen fysieke switch-/kabelverbindingen tussen hosts; die zijn niet in deze monitorgegevens aangetoond. Gestopte gastinterfaces worden volgens de upstreamweergave niet als actieve consumenten getekend.
- Fysieke poorten, bonds, bridges en virtuele interfaces krijgen ook aparte kaarten. Zoek op interface, node, IP, VM-naam of VMID; zoeken verandert de clustertotalen of het volledige diagram niet.

## API, rechten en uitval

`GET /api/proxmox/network` projecteert alleen nodes uit `/cluster/resources`. `GET /api/proxmenux/network` leest uitsluitend de vaste monitorpaden `network` en `network/latency/history?target=gateway&timeframe=hour`. Beide gebruiken de bestaande sessie en het modulerecht `proxmox`; beheren van de verbinding blijft voor beheerders. De browser kan geen monitoradres of upstream-pad kiezen. Tokens blijven serverzijdig, de cluster-CA blijft verplicht en redirects worden geweigerd.

De monitorcache is gescheiden van gezondheid en opslag, met dezelfde begrensde parallelle achtergrondverversing en expliciete loading/stale/foutstatus. De projector begrenst lijsten en velden, valideert IP-adressen, laat niet-eindige/negatieve getallen weg en levert geen ruwe configuratie of credentials. Een ontbrekende latencybron blokkeert de interface-inventaris niet. Sessieweigering wist frontendgegevens; een mislukte monitorverversing kan geen gezonde volledige clusterstatus opleveren.

De oorspronkelijke SVG-stringinterpolatie wordt vóór rendering XML-geëscaped, inclusief labels, linkteksten en attributen. Alleen begrensde, gevalideerde flowvelden worden geaccepteerd. Zo kunnen gastnamen geen SVG/HTML invoegen. De geanimeerde paden blijven JSX met stabiele sleutels. Een diagram is begrensd op 64 poorten/bonds, 127 bridges plus een onbekende groep en 512 gastinterfaces per node; bij begrenzing verschijnt een melding en de gewone inventaris blijft beschikbaar.

## Bestaande installatie

Nieuwe configuraties bevatten `network` als pagina onder de Proxmox-module; het menu-item verwijst naar `proxmox/network`. Bestaande runtimeconfiguratie wordt buiten releases beheerd. Voeg daar dezelfde pagina toe en wijzig alleen de bestaande Network-menuroute. Maak vooraf een privébackup en valideer met `backend.configuration.load_config`; accountlijsten, providers en geheimen blijven buiten deze wijziging. `#network` blijft werken voor bestaande bookmarks.

## Verificatie

`tests/test_network_inventory.py` dekt normale inventarisatie, ontbrekende/nulmetingen, ongeldige invoer, veilige projectie, gescheiden cache, gedeeltelijke upstreamuitval en sessie-/modulerechten. `frontend/tests/proxmox-network.test.mjs` test fysiek-only totalen, nodefiltering, onbekende/stale-metingen, schema-afwijzing, echte JSX-kaarten, ontsnapte tekst en lege/foutweergaven. Volledige pytest, frontendtests, TypeScript en build moeten slagen vóór publicatie.

`frontend/tests/proxmox-network-flow.test.mjs` test de echte upstream desktop-/mobiele SVG-layout, NIC/bond/bridge/VM-koppelingen, RX/TX-pulsen, lege/onbekende data, clusternamen, begrenzing en de regressie voor onveilige SVG-interpolatie.

Lokale acceptatie op 18 oktober 2026: 764 Python-tests geslaagd, 8 overgeslagen; 244 frontendtests geslaagd; TypeScript en statische build geslaagd. Browsercontrole met fictieve data bevestigde de vier desktopkaarten, nodekeuze, lege zoekresultaten en een mobiele indeling op 390 pixels zonder horizontale overloop. Productieacceptatie gebeurt met de echte nodegegevens na publicatie.

Browseracceptatie met fictieve data: desktopindeling, nodekeuze en mobiele weergave op 390 pixels zonder horizontale overloop gecontroleerd. Het originele flowdiagram toonde drie aparte hosts, VM-/LXC-iconen en RX/TX-animatiepaden; Hardware volgde de systeem-/geheugen-/sensorindeling van de referentie. Deze voorbeeldmetingen zijn geen productiegegevens.

Acceptatie na samenvoegen met de recente Virtual Apps-wijzigingen op 18 oktober 2026: 785 Python-tests geslaagd, 8 overgeslagen; 256 frontendtests geslaagd; TypeScript-controle en statische productiebuild geslaagd.
