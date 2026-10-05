# Cronjobs: geplande taken per node

**Proxmox → Nodes** is de cronjob-manager van ControlDeck. Je ziet in één oogopslag wat er in het hele cluster heeft gedraaid, en je beheert per node je eigen cronjobs: aanmaken, aanpassen, pauzeren, direct uitvoeren en verwijderen, met log en geschiedenis.

Voorwaarde: de module **Cronjobs** is ingericht in **Admin → Modulebeheer** (zie [NODE-AGENT.md](NODE-AGENT.md) §7c). ControlDeck werkt via de ControlDeck-agent op elke node; er draait geen extra webdienst op de nodes.

## Hele cluster

Het eerste tabblad toont één tijdlijn van alle runs op alle gekoppelde nodes, de nieuwste bovenaan.

| Bron | Wat je ziet |
| --- | --- |
| **ControlDeck** | Jobs die ControlDeck beheert: start, duur, resultaat met exitcode, log |
| **Systeem-cron** | Overige cronjobs van de node (uit het cron-systeemlog): alleen **dat** ze gestart zijn, niet het resultaat |
| **Proxmox-backup** | Backups (vzdump) uit de Proxmox-API, met resultaat |

- **Tellers** bovenaan: aantal runs, OK, fout, bezig, gestart.
- **Filters**: periode (24 uur tot 14 dagen), node, resultaat en bron.
- **Onbereikbare node**: wordt bovenaan gemeld; zijn runs ontbreken en tellen nergens als OK.

## Per node

### ControlDeck-cronjobs

| Kolom | Betekenis |
| --- | --- |
| **Job** | Naam, omschrijving; voor admins ook het commando |
| **Schema** | In gewone taal ("Elke werkdag om 07:00"), met de cronregel en de gebruiker |
| **Volgende** | Eerstvolgende uitvoering, of ⏸ Gepauzeerd |
| **Laatste run** | ✓ OK · ✗ Fout (exit N) · ◌ Bezig · △ Overgeslagen (vorige run nog bezig) · **△ Gemist**: het schema had al moeten draaien (5 minuten speling), maar er is geen run gestart |

**Acties** (alleen admins):
- **Nieuwe cronjob / Bewerken**: naam, omschrijving, schema, commando, gebruiker (standaard root), optionele time-out, uitvoer bewaren, actief. Eerst **Controleren** toont een samenvatting; pas na **Bevestigen en opslaan** wordt de job op de node gezet.
- **Schema-kiezer**: elke N minuten, elk uur, dagelijks om …, wekelijks op … om …, maandelijks op dag … om … (1 t/m 28), of **Geavanceerd** met een vrije cronregel. Je ziet direct de uitleg en de volgende vijf uitvoeringen.
- **Nu uitvoeren**: start de job direct (na bevestiging) en toont het **live log**.
- **Pauzeren / Hervatten**: de job blijft bestaan, maar draait niet.
- **Geschiedenis**: de laatste 20 runs, met log per run.
- **Verwijderen**: job en geschiedenis weg (na bevestiging).

### Overige cronjobs en timers

Cronregels uit `/etc/crontab` en `/etc/cron.d/*` (en de crontab van root) zijn **alleen-lezen**. Admins kunnen een regel **Overnemen**:

1. ControlDeck maakt een eigen job met hetzelfde schema, dezelfde gebruiker en hetzelfde commando, met logging en monitoring.
2. De oorspronkelijke regel wordt uitgecommentarieerd met de markering `# disabled by ControlDeck <datum> (job <naam>)`; een back-up van het bestand staat in `/var/lib/controldeck-agent/backups/` op de node.
3. **Teruggeven** zet de oorspronkelijke regel precies terug en verwijdert de ControlDeck-job.

Regels met `@reboot` kunnen niet worden overgenomen. Systemd-timers staan onder **Systemd-timers** (alleen-lezen).

## Rechten

| Wie | Mag |
| --- | --- |
| Gebruikers met de module `proxmox` | Tijdlijn, jobs, schema's en resultaten zien |
| Alleen admins | Commando's en logs zien (die kunnen wachtwoorden of tokens bevatten); aanmaken, bewerken, pauzeren, uitvoeren, verwijderen, overnemen, teruggeven |

Elke wijziging wordt vastgelegd in het auditlog van de agent-proxy (op de ControlDeck-host) én op de node (`/var/log/controldeck-agent.log`), met het account dat de actie deed.

## Goed om te weten

- **Root**: een cronjob als root kan alles op de node. ControlDeck toont dat in de samenvatting vóór opslaan.
- **Logs**: maximaal 256 KiB uitvoer per run; per job de laatste 20 runs en hooguit 14 dagen.
- **Tijdzone**: tijden staan in de tijdzone van je browser; cron op de node gebruikt de tijdzone van de node. In één tijdzone (zoals Europe/Amsterdam) is dat gelijk.
- **Dubbel draaien**: start een job terwijl de vorige run nog loopt, dan wordt de nieuwe overgeslagen en zo gemeld.

## Problemen

| Melding | Oplossing |
| --- | --- |
| "De agent-proxy draait niet" | Voer het commando uit dat Modulebeheer toont (`install-wizard.sh`) |
| "Onbekende of niet-gekoppelde node" | Koppel de node via Modulebeheer → Bewerken → Cronjobs |
| Node "niet bereikbaar" in de tijdlijn | Controleer of de node aan staat en SSH bereikbaar is; test via Modulebeheer |
| "Hostsleutel veranderd" | Controleer waarom (herinstallatie?). Ontkoppel en koppel opnieuw na controle van de vingerafdruk |
