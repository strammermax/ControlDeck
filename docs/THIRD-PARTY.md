# Third-party-overzicht

## Referentie

[ProxMenux Monitor](https://github.com/MacRimi/ProxMenux) is de visuele en technische referentie. Deze eerste foundation bevat geen geïmporteerde ProxMenux-applicatiecode of assets. De GPL-3.0-licentietekst is opgenomen als projectlicentie. Registreer bij later broncodehergebruik de exacte broncommit, bestanden, oorspronkelijke notices en wijzigingen.

## Directe afhankelijkheden

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
