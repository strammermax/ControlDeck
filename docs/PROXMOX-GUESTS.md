# Proxmox → Virtual Machines: clusterbreed ProxMenux-overzicht

Het overzicht staat op `#proxmox/vms`. De overzichtskaarten en VM-/LXC-kaarten zijn afgeleid van de echte ProxMenux-component `AppImage/components/virtual-machines.tsx`, vastgezet op commit `d4e98d16b11733e518b0162db1b528b2ecd4cc53`. De vier kaarten, donutgeometrie, kleuren, badges en vijf metrickolommen zijn behouden. Tailwind/shadcn is vervangen door afgeschermde CSS, zodat ControlDeck statisch blijft zonder extra runtime. De upstream component bevat ook beheer, terminals en backupfuncties; die zijn niet nodig voor dit alleen-lezen overzicht en zijn niet geïmporteerd.

## Gebruik

- Bovenaan staan **Cluster**, gevolgd door de werkelijk bekende nodes in alfabetische volgorde, in de huidige inrichting pve-amd, pve-intel en pve-nas. Cluster is de standaard.
- De vier overzichtskaarten en statusaantallen volgen de gekozen node. All, Running en Stopped filteren de lijst; zoeken werkt op naam, ID, node, IP en tags. De overzichtstotalen blijven de volledige gekozen scope beschrijven, ook tijdens zoeken.
- Elke kaart toont status, type, naam, ID, node, gekleurde Proxmox-tags, uptime, CPU, geheugen, schijf en I/O-tellers. Beschikbare pakketupdates uit ProxMenux krijgen een paarse badge.
- Op kleinere schermen verschuiven de kaarten en metingen naar meerdere rijen. Filters blijven gewone toetsenbordbedienbare knoppen met een geselecteerde status.

## Gegevens en betrouwbaarheid

`GET /api/proxmox/guests` gebruikt de bestaande alleen-lezen Proxmox-koppeling en de cluster-resource-API als inventaris. Er is geen aparte token of nieuwe env nodig. Alle gasten uit de bron blijven behouden, ook gestopte gasten; er is geen top-tienfilter. De server projecteert uitsluitend toegestane presentatievelden. In de bestaande cache geldt dezelfde configuratie-/rechtenafscherming als voor andere Proxmox-gegevens.

Expliciete LXC-adressen worden uit de leesbare netwerkconfiguratie gehaald, met maximaal vier parallelle lezers. DHCP en niet-beschikbare adressen worden niet uit het CT-ID afgeleid. Voor een VM zonder aangeleverd IP wordt geen adres verzonnen. Een fout of ontbrekend leesrecht bij deze optionele netwerkconfiguratie houdt de inventaris beschikbaar.

De bestaande ProxMenux-summary voegt een begrensde, geschoonde gastenprojectie toe aan zijn bestaande cache. De frontend gebruikt die alleen als aanvullende bron voor dezelfde VM-ID op dezelfde node, met hetzelfde type en dezelfde status. Oude, onbereikbare of nog ladende monitors mogen geen actuele inventaris overschrijven. Migratie naar een andere node kan zo niet twee kaarten voor dezelfde VM opleveren.

CPU-gebruik in de clusterkaart wordt gewogen op de fysieke threads van de nodes. Configured is de som van alle toegewezen vCPU's; In use is de toegewezen vCPU-capaciteit van draaiende gasten. Dit laatste is geen gemeten CPU-belasting. Geheugengebruik en fysiek totaal komen van de hosts; Alloc is toegewezen gastgeheugen. Schijfwaarden zijn de gebruikte/toegewezen gastenwaarden zoals de providers die rapporteren, geen optelling van gedeelde fysieke clusteropslag. Toegewezen geheugen en CPU kunnen hoger zijn dan de fysieke capaciteit.

I/O toont bytecounters, geen bytes per seconde. Onbekende metingen zijn `—`. Bij een onbereikbare node, verouderde inventaris of niet volledig beschikbare monitorgegevens volgt een zichtbare waarschuwing. Een tijdelijke netwerkfout kan de laatste inventaris verouderd tonen; 401/403 wist de geladen inventaris. Er worden geen start-, stop-, wijzigings- of SSH-acties aangeboden.

## Hergebruik en licentie

`frontend/modules/proxmox/guest-cards.tsx` bevat de herbruikbare presentatie; `frontend/lib/proxmox-guests.ts` bevat selectie, totalen, validatie en veilige verrijking; `backend/guest_inventory.py` de serverprojectie. De Proxmox-pagina bezit de scopekeuze en het verversen. Dit scheidt bronlogica van vormgeving zonder een tweede dashboard-/providersysteem in te voeren.

De ProxMenux-tagkleuren komen uit dezelfde gepinde bron, `AppImage/lib/pve-tag-color.ts`. Bron, wijzigingen en GPL-3.0 staan in `frontend/public/proxmenux/NOTICE.txt` en `LICENSE.txt`, die in de statische export worden meegeleverd. Zie ook [THIRD-PARTY.md](THIRD-PARTY.md).

## Verificatie

`tests/test_guest_inventory.py` controleert clusterprojectie, volledige lijst, cache, optioneel IP, foutieve/te grote brondata, ontbrekende koppeling, sessie en modulerechten. `frontend/tests/proxmox-guests.test.mjs` controleert scope-/status-/zoekselectie, gewogen totalen, onbekende metingen, migratie-/stale-afscherming en serverrendering van de werkelijke overgenomen kaarten. De bestaande ProxMenux-tests blijven verplicht voor gedeeltelijke node-uitval en certificaatcontrole. Voeg browseracceptatie op desktop en mobiel en een live alleen-lezen controle toe voordat de release als afgerond wordt gemeld.

Lokale verificatie op 18 oktober 2026, na samenvoegen met de recente Kasm-wijzigingen: 736 Python-tests geslaagd, 8 overgeslagen; 234 frontendtests geslaagd; TypeScript-controle en statische build geslaagd. De ProxMenux-tests controleren de extra gastenprojectie voor normale, lege en foutieve brondatasets. Browseracceptatie met fictieve gegevens: vier kaarten naast elkaar op desktop, cluster-/nodekeuze, statusfilter, zoeken zonder resultaten en mobiel zonder horizontale pagina-overloop. De lokale preview bevat uitsluitend synthetische accounts en gasten en wordt niet gepubliceerd.
