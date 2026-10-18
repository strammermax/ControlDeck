# Proxmox Storage: ProxMenux-weergave over het cluster

`#proxmox/storage` gebruikt de vier overzichtskaarten en opslaglijsten uit ProxMenux, met dezelfde kaartindeling, donut-/balkmeters en kleuren als `AppImage/components/storage-overview.tsx` op commit `d4e98d16b11733e518b0162db1b528b2ecd4cc53`. Tailwind/shadcn is vervangen door afgeschermde CSS; de bestaande Proxmox-kaartbouwstenen worden gedeeld met het VM-overzicht. De code blijft een statische frontend met één Python-service.

## Weergave

Bovenaan staan **Cluster | pve-amd | pve-intel | pve-nas**, gevuld vanuit de werkelijke nodelijst; Cluster is de standaard. De selectie geldt voor Storage Used, Local Used, Remote Used, Physical Disks, de Proxmox-opslaglijst, host-/LXC-remote mounts, fysieke schijven en ZFS-pools. Elke opslagkaart toont naam, type, node(s), beschikbaarheidsstatus, gebruiksbalk, totaal, gebruikt en beschikbaar. Gedeelde bronnen krijgen een herkenbaar label.

De schijfkaarten tonen model, capaciteit, temperatuur, slijtage en SMART-status. Serienummers worden niet naar de browser geprojecteerd. Standby en een ontbrekende temperatuur worden expliciet weergegeven; onbekende SMART-status geldt nooit als gezond. Dit is een alleen-lezen weergave: geen formatteer-, mount-, wijzigings- of SMART-testacties.

## Bronnen en berekening

- `/api/proxmox/storage` gebruikt de bestaande clusterverbinding en modulerechten. `/cluster/resources` levert de node-/opslagmetingen in bytes. `/storage` levert alleen serverzijdig de identiteit van het achterliggende doel. De browser krijgt hiervan een hash en toegestane presentatievelden, geen credentials of ruwe configuratie. Zonder aanvullende configuratierechten blijven resource-ID en shared-vlag bruikbaar; de UI meldt dat de identiteit onvolledig is.
- `/api/proxmenux/storage` leest via de bestaande monitorverbinding per node uitsluitend `/storage` en `/mounts`. Dit levert geschoonde fysieke schijven, ZFS-pools en mounts. Mountopties, credentials, serienummers, foutlogs en container-PID's worden niet geëxporteerd. Een mountbron met userinfo wordt geweigerd.
- De monitor deelt dezelfde achtergrondverversing en gedeeltelijke-uitvalafhandeling met het bestaande gezondheidsoverzicht. Beide weergaven hebben afzonderlijke cachenamespaces; het openen van Storage mag de gezondheid-/gasteninformatie niet vervangen. Verbindingswijzigingen wissen beide caches.
- In Cluster wordt dezelfde **gedeelde** opslag maar één keer geteld, ook wanneer drie nodes deze rapporteren. Exacte aliassen met hetzelfde server-/share-/datastore-/pooldoel worden waar aantoonbaar samengevoegd. Configuratiecredentials maken nooit deel uit van de publieke identiteit. Lokale opslag met dezelfde naam op verschillende nodes blijft afzonderlijke opslag.
- Per-nodekeuze toont de metingen die die node rapporteert. Een gedeelde bron die op één node uitvalt, blijft clusterbreed beschikbaar via een andere actieve node; de afwijking blijft zichtbaar. Er worden nooit drie nodecapaciteiten bij elkaar opgeteld voor dezelfde shared bron.
- Totalen beschrijven **actieve logische Proxmox-opslagdoelen**, zoals in ProxMenux. Dit is geen inventaris van uniek fysiek schijfoppervlak: verschillende shares, datasets of storage-types kunnen dezelfde fysieke hardware gebruiken. Mounts, schijven en ZFS-pools worden niet nogmaals boven op deze totalen opgeteld. Verschillende doelen worden niet alleen vanwege gelijke grootte samengevoegd.
- Bytewaarden worden vóór presentatie bij elkaar opgeteld. Onbekende of ongeldige capaciteit blijft `—`; nul betekent alleen een daadwerkelijk gemeten nul. Bij gedeeltelijke beschikbaarheid worden de bekende actieve totalen getoond met waarschuwing. Fysieke schijven mogen bij ontbrekende nodes niet het label “all healthy” krijgen.

## Testen en acceptatie

`tests/test_storage_inventory.py` dekt normaal gebruik, grenzen en afwijzing: shared-identiteit, lokale naamgenoten, aliassen, lege/onbekende capaciteit, private projectie, ontbreken van metadatarechten, cache, sessie/CSRF/modulerechten, gedeeltelijke monitoruitval en het gescheiden houden van de gezondheidscache. De bestaande ProxMenux-tests blijven gelden na het delen van de cache-/ververslogica.

`frontend/tests/proxmox-storage.test.mjs` bevat de regressie voor meervoudig tellen van shared capaciteit, nodekeuze, onbekende waarden, onbereikbare peers, SMART-onzekerheid en serverrendering van de daadwerkelijke afgeleide kaarten. Browseracceptatie moet desktop/mobiel, nodekeuze en onbekende/deellading controleren. Productieacceptatie vergelijkt de unieke opslagdoelen met de node-rapporten, niet met gefingeerde previewwaarden.

Bron en aanpassingen zijn opgenomen in `frontend/public/proxmenux/NOTICE.txt`; GPL-3.0 staat ernaast als `LICENSE.txt` en wordt meegebundeld. Er is geen extra runtime, bootstrapsecret of env-instelling nodig.

Lokale acceptatie op 18 oktober 2026 na samenvoegen met de recente Virtual Apps-wijzigingen: 752 Python-tests geslaagd, 8 overgeslagen; 239 frontendtests geslaagd; TypeScript-controle en statische build geslaagd. Browsercontrole met fictieve data bevestigde vier overzichtskaarten op desktop, correcte nodekeuze, deduplicatie van gedeelde capaciteit en een mobiele indeling zonder horizontale overloop. Fictieve previewwaarden zijn geen productie-totalen.
