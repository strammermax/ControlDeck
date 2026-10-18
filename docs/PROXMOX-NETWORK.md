# Proxmox Network

`#proxmox/network` gebruikt de ProxMenux-overzichtskaarten en interfacekaarten, afgeleid van `AppImage/components/network-metrics.tsx` (overzicht vanaf regel 650, fysieke kaarten vanaf regel 198) en `network-card.tsx`, commit `d4e98d16b11733e518b0162db1b528b2ecd4cc53`, GPL-3.0. Het bestaande `#network` blijft een compatibele weergave. Vier kaarten, kleuren, dubbele RX/TX-kop en interface-indeling zijn naar scoped CSS overgebracht. Gedeelde kaarten/iconen komen uit dezelfde bouwstenen als VMs en Storage. Er is geen extra runtime of grafiekbibliotheek nodig.

## Gebruik

- Cluster en afzonderlijke nodes tonen dezelfde gegevensbron. De nodekeuze komt uit de bestaande Proxmox-clusterverbinding. Monitoren buiten deze inventaris worden genegeerd.
- Network Traffic telt uitsluitend fysieke interfaces per node. Bonds, bridges en virtuele interfaces tellen niet opnieuw mee. Een pakket tussen twee clusterhosts verschijnt op beide fysieke poorten; het getal is dus geen uniek internetverbruik.
- Bytes zijn cumulatieve tellers sinds de teller-/hoststart. RX/TX in bytes per seconde gebruikt de monitorsnelheid; oudere monitors zonder snelheden krijgen een afgeleide snelheid uit twee opeenvolgende tellermetingen (1–180 seconden). Een tellerreset, te lange pauze of eerste meting geeft geen afgeleide snelheid. Ontbrekende waarden zijn `—`, nul blijft nul. De kaart vermeldt expliciet dat het cumulatieve verkeer betreft.
- Active Interfaces onderscheidt fysieke poorten, bridges, bonds en VM/LXC-interfaces. Network Status toont fysieke fout- en droptellers; dit is geen berekende end-to-end packet-lossmeting. Historische drops maken een verbinding niet automatisch defect.
- Gateway Latency toont de meting en het laatste uur per node. De clusterkop is de hoogste beschikbare actuele nodewaarde, geen optelsom. Ontbrekende of verouderde nodes maken de kaart onvolledig.
- Network Flow toont de door de monitor gemelde fysieke poort → bond → bridge-relaties. Fysieke poorten, bonds, bridges en virtuele interfaces krijgen aparte kaarten. Zoek op interface, node, IP, VM-naam of VMID; zoeken verandert de clustertotalen niet.

## API, rechten en uitval

`GET /api/proxmox/network` projecteert alleen nodes uit `/cluster/resources`. `GET /api/proxmenux/network` leest uitsluitend de vaste monitorpaden `network` en `network/latency/history?target=gateway&timeframe=hour`. Beide gebruiken de bestaande sessie en het modulerecht `proxmox`; beheren van de verbinding blijft voor beheerders. De browser kan geen monitoradres of upstream-pad kiezen. Tokens blijven serverzijdig, de cluster-CA blijft verplicht en redirects worden geweigerd.

De monitorcache is gescheiden van gezondheid en opslag, met dezelfde begrensde parallelle achtergrondverversing en expliciete loading/stale/foutstatus. De projector begrenst lijsten en velden, valideert IP-adressen, laat niet-eindige/negatieve getallen weg en levert geen ruwe configuratie of credentials. Een ontbrekende latencybron blokkeert de interface-inventaris niet. Sessieweigering wist frontendgegevens; een mislukte monitorverversing kan geen gezonde volledige clusterstatus opleveren.

## Bestaande installatie

Nieuwe configuraties bevatten `network` als pagina onder de Proxmox-module; het menu-item verwijst naar `proxmox/network`. Bestaande runtimeconfiguratie wordt buiten releases beheerd. Voeg daar dezelfde pagina toe en wijzig alleen de bestaande Network-menuroute. Maak vooraf een privébackup en valideer met `backend.configuration.load_config`; accountlijsten, providers en geheimen blijven buiten deze wijziging. `#network` blijft werken voor bestaande bookmarks.

## Verificatie

`tests/test_network_inventory.py` dekt normale inventarisatie, ontbrekende/nulmetingen, ongeldige invoer, veilige projectie, gescheiden cache, gedeeltelijke upstreamuitval en sessie-/modulerechten. `frontend/tests/proxmox-network.test.mjs` test fysiek-only totalen, nodefiltering, onbekende/stale-metingen, schema-afwijzing, echte JSX-kaarten, ontsnapte tekst en lege/foutweergaven. Volledige pytest, frontendtests, TypeScript en build moeten slagen vóór publicatie.

Lokale acceptatie op 18 oktober 2026: 764 Python-tests geslaagd, 8 overgeslagen; 244 frontendtests geslaagd; TypeScript en statische build geslaagd. Browsercontrole met fictieve data bevestigde de vier desktopkaarten, nodekeuze, lege zoekresultaten en een mobiele indeling op 390 pixels zonder horizontale overloop. Productieacceptatie gebeurt met de echte nodegegevens na publicatie.
