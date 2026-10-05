# CI/CD en releases

Repository: `strammermax/ControlDeck`. De workflow is `.github/workflows/ci.yml`.

## Pull request

GitHub-hosted Linux-runners voeren Python-tests, TypeScriptcontrole, frontendbuild, shellcontrole en een Docker-runtime-smoketest uit. De Linux-bundle en SHA-256-checksum worden als workflowartifact bewaard. Pull requests starten geen productiejob en publiceren geen image of release.

## Push naar main

Na de controles wordt een image gepubliceerd naar `ghcr.io/strammermax/controldeck` met de tags `main` en `sha-<volledige-commit>`. De LXC-deployment wordt alleen gestart wanneer de repositoryvariabele `LXC_DEPLOY_ENABLED` op `true` staat. De productierunner heeft label `controldeck-production`.

De runner downloadt het artifact van dezelfde workflowrun en roept de root-owned deployhelper aan. Deze valideert checksum en commit, installeert de release, wisselt de `current`-symlink en controleert readiness en commit. De vorige release wordt bij opstartfalen teruggezet.

Builds draaien op GitHub; de productierunner doet geen frontendbuild. Deploymentjobs worden achter elkaar uitgevoerd en niet halverwege afgebroken.

## Versies en releases

Versienummers zijn `jjjj.mm.dd.<build>`, bijvoorbeeld `2026.10.05.27`:

- **Datum:** de builddag in Europe/Amsterdam.
- **Build:** het doorlopende runnummer van deze workflow (`github.run_number`); het loopt altijd op, ook over dagen heen.

CI berekent het nummer bij elke build met `scripts/version.py`; er hoeft niets met de hand te worden aangepast. Elke gecontroleerde push naar `main`:

1. krijgt dit versienummer in de Linux-bundle (`build-info.json`), het Docker-image en `/health` (de footer toont het);
2. wordt gepubliceerd als image met de tags `sha-<commit>`, `<versie>` en `main`;
3. wordt een **GitHub-release** met tag `v<versie>` op de gebouwde commit, met bundle en checksum;
4. wordt uitgerold naar de LXC (als `LXC_DEPLOY_ENABLED` aan staat).

**Release notes** worden per release samengesteld uit de commitberichten sinds de vorige release (`scripts/prune.py notes`), met een link naar de [changelog](CHANGELOG.md). Schrijf commitberichten daarom als korte, leesbare zin. In ControlDeck linkt de footertekst met het versienummer naar de release notes van de draaiende versie (bij `development` naar het releaseoverzicht).

**Opruimen:** GitHub verwijdert releases, tags en images nooit zelf. CI bewaart de laatste **30** CalVer-releases (met hun tags) en de laatste **30** image-versies; versies met de tag `main` blijven altijd. De historische releases v0.1.0–v0.4.0 worden nooit verwijderd. Git-geschiedenis wordt nooit aangeraakt. Build-artifacts verlopen na 14 dagen, workflowlogs na 90 dagen. Opruimen mag mislukken zonder release of uitrol te blokkeren.

Pull requests krijgen ook een versienummer, maar worden niet gepubliceerd, uitgebracht of uitgerold. Een herhaalde run (zelfde runnummer) maakt geen tweede release. Lokaal en zonder build-nummer is de versie `development` (bestand `VERSION`). De Docker-build en `package.py` weigeren elk ander formaat.

Releases v0.1.0 t/m v0.4.0 gebruikten nog semver met handmatige tags; die blijven bestaan.

## GitHub-inrichting

- Environment: `production`.
- Variabele: `LXC_DEPLOY_ENABLED=true` zodra de runner en servicebootstrap klaar zijn.
- Runnerlabels: `self-hosted`, `linux`, `controldeck-production`.
- Het workflowtoken krijgt alleen per job benodigde rechten; geen extra PAT nodig voor builds en releases.
- Het ControlDeck-image is na publicatie zonder login opgehaald via de registry-manifestcontrole. Bij een eigen fork: controleer pakketvisibility; een nieuw package kan standaard privé zijn.

De self-hosted runner voert alleen jobs van vertrouwde main-pushes uit. Gebruik geen `pull_request_target`-job om code uit forks op de LXC uit te voeren. Het productieartifact bevat uitvoerbare code en dependencies: schrijf- en workflowrechten op de repository zijn daarom ook deploymentrechten. Configureer bij meerdere bijdragers branchbescherming en reviewbeleid.

## Referentie

RemoveSky gebruikt een lokale runner die een service herstart en git-updates toepast. ControlDeck gebruikt hetzelfde lokale-runnerprincipe, maar ontvangt een vooraf gebouwde bundle van de gecontroleerde commit en behoudt eerdere releases. Hiermee hoeven builds niet op de lichte LXC te draaien.

Bronnen: [GitHub self-hosted runners](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners), [Docker-images publiceren](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images).
