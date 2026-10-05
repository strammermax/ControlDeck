# CI/CD en releases

Repository: `strammermax/ControlDeck`. De workflow is `.github/workflows/ci.yml`.

## Pull request

GitHub-hosted Linux-runners voeren Python-tests, TypeScriptcontrole, frontendbuild, shellcontrole en een Docker-runtime-smoketest uit. De Linux-bundle en SHA-256-checksum worden als workflowartifact bewaard. Pull requests starten geen productiejob en publiceren geen image of release.

## Push naar main

Na de controles wordt een image gepubliceerd naar `ghcr.io/strammermax/controldeck` met de tags `main` en `sha-<volledige-commit>`. De LXC-deployment wordt alleen gestart wanneer de repositoryvariabele `LXC_DEPLOY_ENABLED` op `true` staat. De productierunner heeft label `controldeck-production`.

De runner downloadt het artifact van dezelfde workflowrun en roept de root-owned deployhelper aan. Deze valideert checksum en commit, installeert de release, wisselt de `current`-symlink en controleert readiness en commit. De vorige release wordt bij opstartfalen teruggezet.

Builds draaien op GitHub; de productierunner doet geen frontendbuild. Deploymentjobs worden achter elkaar uitgevoerd en niet halverwege afgebroken.

## Een release maken

1. Werk `VERSION`, `frontend/package.json` en `docs/CHANGELOG.md` bij; vernieuw de npm-lockfile.
2. Commit en push naar main; wacht op een geslaagde workflow.
3. Maak een tag die overeenkomt met VERSION, bijvoorbeeld `v0.1.0`.
4. Push de tag. De tagworkflow valideert de versie, voert de controles uit, publiceert het versie-image en maakt een GitHub-release met bundle en checksum.

```bash
git tag -a v0.1.0 -m 'ControlDeck infrastructure foundation'
git push origin v0.1.0
```

Tags publiceren een release maar voeren geen tweede LXC-deployment uit. Productie volgt gecontroleerde pushes naar main. Een handmatige workflow op main kan dezelfde commit opnieuw uitrollen. Een andere ref start geen productiejob.

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
