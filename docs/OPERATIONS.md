# Beheer en herstel

## Controles

- `/health`: proces antwoordt, inclusief versie en commit.
- `/ready`: de gebouwde startpagina is aanwezig.
- `journalctl -u controldeck -n 100`: servicelog.
- `systemctl status controldeck`: service-status.
- GitHub Actions: build- en deployresultaat.

## Releasepaden

```text
/opt/controldeck/releases/<commit>/  code, frontend, metadata en eigen venv
/opt/controldeck/current            symlink naar actieve release
/var/lib/controldeck/               gereserveerd voor toekomstige persistente data
/usr/local/sbin/controldeck-deploy   root-owned helper
```

Runtimecode is niet schrijfbaar door de servicegebruiker. Bewerk productiecode niet rechtstreeks: wijzigingen lopen via GitHub en een gecontroleerde deployment.

## Automatisch herstel

Na het wisselen van de release controleert de deployhelper maximaal ongeveer één minuut op readiness en de juiste commit. Bij falen wordt de vorige release teruggezet en de workflow als mislukt gemarkeerd. Bij een eerste installatie zonder vorige release wordt de mislukte service gestopt.

Dit herstelmodel geldt voor de huidige release zonder databasewijzigingen. Zodra schemamigraties worden toegevoegd, moet compatibiliteit expliciet worden geregeld voordat code-rollback voldoende is.

## Handmatig herstel

Kies een bestaande commitdirectory en wijzig als root de symlink onder dezelfde deploymentlock, zodat dit niet tegelijk met CI gebeurt:

```bash
flock /run/lock/controldeck-deploy.lock bash
ls /opt/controldeck/releases
ln -sfn /opt/controldeck/releases/<BESTAANDE-COMMIT> /opt/controldeck/current.next
mv -Tf /opt/controldeck/current.next /opt/controldeck/current
systemctl restart controldeck
curl -f http://127.0.0.1:8080/health
exit
```

## Backup en ruimte

Backup toekomstige persistente data en configuratie volgens het technische ontwerp. De huidige foundation heeft geen gebruikersdatabase of secrets. Releasebundles kunnen opnieuw uit GitHub worden opgehaald zolang zij beschikbaar blijven; workflowartifacts hebben beperkte retentie, officiële releases zijn het blijvende distributiepunt.

Releasecleanup is voorlopig handmatig. Bewaar altijd de actieve en minstens één vorige werkende release. Controleer schijfruimte voordat oude releases worden verwijderd; wijzig niets buiten `/opt/controldeck/releases`.
