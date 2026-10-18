# Third-party-overzicht

## Referentie

[ProxMenux Monitor](https://github.com/MacRimi/ProxMenux) is de visuele en technische referentie. De oorspronkelijke foundation bevatte geen geïmporteerde ProxMenux-applicatiecode of assets. Het VM-/LXC-overzicht gebruikt inmiddels afgeleide broncode zoals hieronder beschreven. De projectlicentie blijft GPL-3.0.

## ProxMenux VM-/LXC-overzicht

De vier overzichtskaarten en inventarislijst in `frontend/modules/proxmox/guest-cards.tsx` zijn aangepast uit `AppImage/components/virtual-machines.tsx` van MacRimi/ProxMenux, commit `d4e98d16b11733e518b0162db1b528b2ecd4cc53` (overzicht/lijst rond regels 2799–3240). `frontend/modules/proxmox/pve-tag-color.ts` neemt de tagkleuren uit `AppImage/lib/pve-tag-color.ts` over. Beide vallen onder de upstream GPL-3.0-licentie; de upstreamnotities over de Proxmox-kleuralgoritmen zijn behouden. Aanpassingen: cluster-/nodekeuze, alleen-lezen gegevensprojectie, scoped CSS in plaats van Tailwind/shadcn, expliciete onbekende/stale-status en ControlDeck-sessierechten. Er worden geen upstreamterminal-, backup- of mutatieacties geladen. Bronvermelding en licentie worden meegeleverd als `frontend/public/proxmenux/NOTICE.txt` en `LICENSE.txt`. Zie [PROXMOX-GUESTS.md](PROXMOX-GUESTS.md).

Het Storage-overzicht in `frontend/modules/proxmox/storage-cards.tsx` is aangepast uit `AppImage/components/storage-overview.tsx` op dezelfde commit, GPL-3.0. De vier kaarten (vanaf regel 1120), capaciteits-/statusindeling en lijsten zijn overgenomen naar scoped CSS en gedeelde Proxmox-componenten. ControlDeck voegt cluster-/nodekeuze, gedeelde-opslagidentiteit, veilige projectie, gedeeltelijke-uitvalmeldingen en aparte read-only mount-/schijfkaarten toe. Upstream SMART-test-, bestands-/mountbeheer- en terminalacties zijn niet geïmporteerd. Zie [PROXMOX-STORAGE.md](PROXMOX-STORAGE.md).

## Directe afhankelijkheden

Het Network-overzicht in `frontend/modules/proxmox/network-cards.tsx` is aangepast uit `AppImage/components/network-metrics.tsx` (overzicht vanaf regel 650 en fysieke interfacekaart vanaf regel 198) en `network-card.tsx`, dezelfde ProxMenux-commit en GPL-3.0. De dubbele verkeerskop, statuschips en kaartindeling worden hergebruikt met scoped CSS en gedeelde Proxmox-kaartcomponenten. ControlDeck voegt clusterselectie, fysieke-only totalen, begrensde veilige projecties en expliciete ontbrekende metingen toe. De compacte Network Flow is een eigen presentatie van de gemelde relaties; upstreammutaties en terminalacties zijn niet overgenomen. Zie [PROXMOX-NETWORK.md](PROXMOX-NETWORK.md).

De frontendbuild verzamelt licentieteksten uit de geïnstalleerde dependencyboom, inclusief gebundelde Next.js-dependencies. De export, bundle en Docker-runtime bevatten `THIRD-PARTY-LICENSES.txt`. Een snapshot staat in [THIRD-PARTY-LICENSES.txt](THIRD-PARTY-LICENSES.txt) in deze map en wordt bij dependencywijzigingen bijgewerkt.

React, Next.js, TypeScript, Flask, Gunicorn en pytest worden als externe packages gebruikt. De exacte versies staan in package.json, package-lock.json en requirementsbestanden. npm bevat de volledige frontenddependencyboom. Ook transitieve Python-runtimepackages worden in requirements.txt vastgelegd. Ontwikkeldependencies zijn nog niet volledig gelockt.

Docker-baselagen en GitHub Actions zijn eveneens externe dependencies. GitHub Actions worden op gecontroleerde commits vastgezet. Docker-baselagen gebruiken nog versie-tags; digestpinning en geautomatiseerde updates zijn een verdere verbetering. Een releaseclaim over volledig reproduceerbare dependencies is daarom nog niet van toepassing.

## Basisinterface 0.2.0

De door de gebruiker aangeleverde mockup vormt de visuele referentie voor de nieuwe shell. Kleuren, indeling en navigatie zijn opnieuw opgebouwd in de eigen React-broncode. De opgeslagen ProxMenux-bundles en het ProxMenux-logo zijn niet opgenomen in de runtime. Het eigen ControlDeck-logo wordt gebruikt. De projectlicentie blijft GPL-3.0.

## Python OAuth-dependencies

Authlib en joserfc gebruiken BSD-3-Clause. Cryptography gebruikt Apache-2.0 of BSD-3-Clause; overige notices staan in [PYTHON-LICENSES.txt](PYTHON-LICENSES.txt). De snapshot is uit de lokale ontwikkelomgeving verzameld. Linux-bundles en Docker-images genereren het bestand opnieuw uit de daadwerkelijk geïnstalleerde Python-distributies, inclusief Gunicorn. Het runtimebestand is `PYTHON-LICENSES.txt` naast de frontend-notices.

## Dashboard Icons

De eigen Homepage- en Linkwarden-kaarten gebruiken 36 ongewijzigde PNG-iconen uit [Homarr Labs Dashboard Icons](https://github.com/homarr-labs/dashboard-icons), vastgezet op commit `adca944175c9a3eb0471f78a4da87f237476d585`. De Apache-2.0-licentie en bronvermelding worden meegeleverd in `frontend/public/service-icons/LICENSE.txt` en `NOTICE.txt`, en zijn daardoor ook aanwezig in de statische export. Productnamen en logo's blijven eigendom van hun respectieve rechthebbenden. De kaartcomponenten zijn eigen ControlDeck-code; Homepage- en Homarr-appcode zijn niet gekopieerd.

## Homepage app-catalogus

De namen, standaardpoorten, categorieën en icoonnamen van 88 apps zijn afgeleid van [Homarr integration definitions](https://github.com/homarr-labs/homarr/blob/4df4ee05998b1777b072770632a6427efbc09149/packages/definitions/src/integration.ts), Apache-2.0. De catalogus verwijst naar die bron in `frontend/lib/app-catalog.json`. Aanvullende iconen komen uit dezelfde eerder gedocumenteerde gepinde Dashboard Icons-bron en vallen onder de bestaande meegeleverde LICENSE/NOTICE. De native Python-adapters en React-formulieren zijn eigen code.

De Apache-2.0-licentietekst van Homarr is opgenomen in `docs/licenses/HOMARR-LICENSE.txt`. De test-only Mock-integratie is uitgesloten van de gebruikerscatalogus.
