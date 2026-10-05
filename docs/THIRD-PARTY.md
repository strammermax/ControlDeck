# Third-party-overzicht

## Referentie

[ProxMenux Monitor](https://github.com/MacRimi/ProxMenux) is de visuele en technische referentie. Deze eerste foundation bevat geen geïmporteerde ProxMenux-applicatiecode of assets. De GPL-3.0-licentietekst is opgenomen als projectlicentie. Registreer bij later broncodehergebruik de exacte broncommit, bestanden, oorspronkelijke notices en wijzigingen.

## Directe afhankelijkheden

De frontendbuild verzamelt licentieteksten uit de geïnstalleerde dependencyboom, inclusief gebundelde Next.js-dependencies. De export, bundle en Docker-runtime bevatten `THIRD-PARTY-LICENSES.txt`. Een snapshot staat in [THIRD-PARTY-LICENSES.txt](THIRD-PARTY-LICENSES.txt) in deze map en wordt bij dependencywijzigingen bijgewerkt.

React, Next.js, TypeScript, Flask, Gunicorn en pytest worden als externe packages gebruikt. De exacte versies staan in package.json, package-lock.json en requirementsbestanden. npm bevat de volledige frontenddependencyboom. Ook transitieve Python-runtimepackages worden in requirements.txt vastgelegd. Ontwikkeldependencies zijn nog niet volledig gelockt.

Docker-baselagen en GitHub Actions zijn eveneens externe dependencies. GitHub Actions worden op gecontroleerde commits vastgezet. Docker-baselagen gebruiken nog versie-tags; digestpinning en geautomatiseerde updates zijn een verdere verbetering. Een releaseclaim over volledig reproduceerbare dependencies is daarom nog niet van toepassing.
