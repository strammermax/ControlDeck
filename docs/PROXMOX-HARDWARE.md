# Proxmox Hardware

`#proxmox/hardware` gebruikt de indeling uit MacRimi/ProxMenux `AppImage/components/hardware.tsx`, commit `d4e98d16b11733e518b0162db1b528b2ecd4cc53`, GPL-3.0. Het System Information-, Memory Modules- en Thermal Monitoring-gedeelte vanaf regel 650 vormt de basis: CPU en moederbord naast elkaar, geheugenkaarten en sensoren gegroepeerd als CPU, GPU, NVMe, HDD, SSD, PCI en Other. Scoped CSS en gedeelde Proxmox-kaartbouwstenen vervangen Tailwind/shadcn. De bestaande sensorgegevens blijven per node herkenbaar.

## Cluster en nodes

De knoppen Cluster en de canonieke Proxmox-nodes gebruiken dezelfde inventaris. De clusterweergave toont System Information per node en combineert de lijsten met geheugenmodules, sensoren, GPU’s, PCI- en USB-apparaten, ventilatoren en vermogensmetingen. Nodes worden niet samengevoegd op een gelijknamige DIMM-bank of sensor. Geheugenmodule-identiteit is node plus index, omdat firmware meerdere modules als `DIMM 0` kan rapporteren.

Geheugengroottes uit ProxMenux zijn KiB en worden serverzijdig naar bytes omgerekend. Alleen een volledige bekende geheugeninventaris krijgt een totaal. Temperaturen worden nooit opgeteld. Ontbrekende temperaturen zijn `—`, ook nul en negatieve Celsiusmetingen blijven geldig. De echte high/critical-grenzen worden gebruikt; als die ontbreken gelden de ProxMenux-fallbacks 80/90°C. Een waarschuwing heeft naast kleur ook tekst. De balk gebruikt de critical-grens of een schaal van 100°C.

## Alleen-lezen gegevens

`GET /api/proxmox/hardware` deelt de canonieke nodeprojector met het netwerkoverzicht. `GET /api/proxmenux/hardware` leest uitsluitend het vaste monitorpad `hardware`, via de bestaande tokenverbinding en cluster-CA. Beide vereisen een aangemelde sessie met het modulerecht `proxmox`. De monitorcache deelt de bestaande achtergrondverversing maar houdt eigen gegevens gescheiden van gezondheid, netwerk en opslag. Een onbereikbare node blokkeert de andere nodes niet.

De projector begrenst lijsten en tekst, valideert eindige meetwaarden en projecteert alleen presentatievelden. Serialnummers, ruwe configuratie, tokens en accountgegevens worden niet doorgegeven. Installatie van drivers, GPU-moduswissels en andere hardwaremutaties uit ProxMenux zijn niet geïmporteerd. Schijfbeheer blijft bij Storage; er ontstaat geen tweede implementatie van de opslagpagina.

Nieuwe configuraties bevatten Hardware onder Proxmox. Voeg op een bestaande installatie de pagina `hardware` toe aan de Proxmox-module en het menu-item met route `proxmox/hardware`. Bewaar vooraf een privébackup en valideer de configuratie; runtimeconfiguratie en accountlijsten blijven buiten Git.

## Verificatie

`tests/test_hardware_inventory.py` dekt normale projectie, KiB/byte-eenheden, dubbele DIMM-labels, nul/negatieve temperaturen, ongeldige data, ontbrekende bronnen, veilige velden, API-cache en sessie-/modulerechten. `frontend/tests/proxmox-hardware.test.mjs` controleert de echte kaarten, nodefiltering, sensordrempels, lege/stale-metingen, HTML-escaping en het ontbreken van een schijnbaar volledig clustertotaal als een node ontbreekt. Draai volledige pytest, frontendtests, TypeScript en de build voor publicatie.

Browseracceptatie met fictieve data: desktopindeling, nodekeuze en mobiele weergave op 390 pixels zonder horizontale overloop gecontroleerd. Het originele flowdiagram toonde drie aparte hosts, VM-/LXC-iconen en RX/TX-animatiepaden; Hardware volgde de systeem-/geheugen-/sensorindeling van de referentie. Deze voorbeeldmetingen zijn geen productiegegevens.
