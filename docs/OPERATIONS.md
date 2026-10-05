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

De root-owned deployhelper en systemd-unit worden bewust bij bootstrap geïnstalleerd en niet door een artifact vervangen. Als deze bestanden wijzigen, werk dan de bootstrapcheckout bij en voer `scripts/install-lxc.sh` opnieuw als root uit vóór de volgende deployment. Een runner-update wordt via de GitHub-runner geregeld.

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

## Homepage: hostvalidatie herstellen

Op 5 oktober 2026 draaide de bestaande Homepage-Docker-container gezond, maar verzoeken via de interne DNS-naam met poort 3000 werden geweigerd. `HOMEPAGE_ALLOWED_HOSTS` bevatte de naam zonder poort. Homepage vergelijkt de exacte Host-header; neem daarom ook de gebruikte combinatie van naam en poort op.

De bestaande Compose-configuratie is privé geback-upt. Alleen de ontbrekende combinaties zijn toegevoegd, waarna de Homepage-container met het bestaande image opnieuw is aangemaakt. Configuratiebestanden, mounts en herstartbeleid bleven behouden. Gebruik geen wildcard om deze fout te omzeilen.

Verificatie: IP-adres, bestaande namen zonder poort en namen met poort geven HTTP 200. Een onbekende Host-header blijft HTTP 400 geven. De pagina, services-API en bookmarks-API geven HTTP 200 en de container is healthy.

Zie de officiële [Homepage-documentatie over toegestane hosts](https://gethomepage.dev/installation/#homepage_allowed_hosts).
