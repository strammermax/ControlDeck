# Ontwerp: module Cronjobs en ControlDeck-agent op Proxmox-nodes

**Status:** ontwerp goedgekeurd (zie §8). Bouw in vier stappen: **1. agent (`scripts/controldeck-agent.py`) — gebouwd**, **2. verbinding via de agent-proxy — gebouwd**, **3. module in Modulebeheer — gebouwd**, 4. pagina Proxmox → Nodes → Cronjobs. Gekozen route: eigen module met eigen agent (niet CronMaster koppelen, omdat de CronMaster-API geen aanmaken, pauzeren en run-geschiedenis biedt). Basis voor [#9 cronjob-manager](https://github.com/strammermax/ControlDeck/issues/9) en [#1 installeren en LXC-updates op nodes](https://github.com/strammermax/ControlDeck/issues/1).

## 1. Waarom

Een aantal functies heeft handelingen op de Proxmox-host zelf nodig, als root:

- cronjobs op de node bekijken, aanmaken, bewerken, verwijderen en monitoren;
- LXC-containers bijwerken (`pct exec … apt-get upgrade`);
- software op de node installeren (ProxMenux Monitor, Termix als LXC).

De Proxmox-API kan dat niet: het alleen-lezen token kan geen commando's uitvoeren en ook een schrijftoken geeft geen shell. ProxMenux biedt alleen een interactieve terminal. Er is dus één gecontroleerde route naar root op de nodes nodig, ontworpen vóór de eerste functie die hem gebruikt.

## 2. Ontwerp in het kort

```text
Browser ──HTTPS──> ControlDeck-webapp (gebruiker controldeck, geen root, geen sleutel)
                        │ lokaal Unix-socket /run/controldeck-agent/agent.sock (groep controldeck-ssh, 0660)
                        v
                   controldeck-agent-proxy (gebruiker controldeck-ssh, geen root; enige houder van de sleutel)
                        │ SSH met eigen sleutel, vastgepinde hostsleutel per node, time-out 60 s
                        v
   Proxmox-node:  authorized_keys  →  restrict,command="/usr/local/sbin/controldeck-agent"
                        │ alleen dit ene script, nooit een shell
                        v
                   controldeck-agent  →  vaste lijst acties, gevalideerde invoer, JSON terug
```

- **Geen shell:** de SSH-sleutel van ControlDeck staat in `authorized_keys` met `restrict` en een vast `command=`. Wat de verbinding ook vraagt, er start alleen `controldeck-agent`. Port forwarding, pty en X11 zijn uit.
- **Vaste acties:** de gevraagde actie komt binnen als naam (`SSH_ORIGINAL_COMMAND`), de gegevens als JSON op stdin (maximaal 64 KiB). Onbekende acties en extra velden worden geweigerd.
- **Sleutel alleen bij de agent-proxy:** de privésleutel staat in `/var/lib/controldeck-ssh/id_ed25519` (eigenaar `controldeck-ssh`, `0600`, map `0700`). De proxy is een kleine dienst (`controldeck-agent-proxy`) die als eigen systeemgebruiker **zonder rootrechten** draait; SSH heeft geen root nodig. Het webproces is lid van de groep `controldeck-ssh` en mag alleen het socket gebruiken, nooit de sleutel lezen. De proxy controleert per verzoek: bewerking, gekoppelde node, agent-actie uit de vaste lijst en grootte.
- **Waarom geen root-worker:** de bestaande root-worker draait via een timer (eens per 15 s). Dat is goed voor installaties, maar te traag voor een interactieve pagina, en SSH heeft geen root nodig. De proxy reageert direct en heeft minder rechten.
- **Hostsleutel vastgepind:** bij het koppelen wordt de SSH-hostsleutel van elke node vastgelegd na bevestiging van de vingerafdruk (zoals bij het Proxmox-certificaat). Een andere hostsleutel blokkeert de verbinding.
- **Alleen vanaf ControlDeck:** de sleutelregel krijgt `from="<IP van de ControlDeck-LXC>"`.

## 3. Acties (eerste versie)

| Actie | Doet | Invoer |
| --- | --- | --- |
| `info` | Versie van de agent, hostname, Proxmox-versie | — |
| `cron.list` | Alle cronregels: `/etc/crontab`, `/etc/cron.d/*`, crontab van root, systemd-timers. Eigen regels bewerkbaar, overige **alleen-lezen** | — |
| `cron.put` | ControlDeck-cronjob aanmaken of bijwerken | `id`, `schedule`, `user`, `command`, `enabled`, `description` |
| `cron.delete` | ControlDeck-cronjob verwijderen | `id` |
| `cron.status` | Laatste uitvoering per ControlDeck-cronjob | — |
| `cron.run` | ControlDeck-cronjob nu uitvoeren; geeft een `runId` terug | `id` |
| `cron.history` | Laatste runs van een job | `id`, `limit` |
| `cron.adopt` / `cron.release` | Bestaande cronregel overnemen of teruggeven (zie §8) | `source`, `line` / `id` |
| `cron.log` | Log van een run, vanaf een offset (voor live meekijken) | `id`, `runId`, `offset` |
| `cron.runs` | Alle runs sinds een tijdstip: ControlDeck-jobs (met resultaat) en gestarte overige cronjobs uit het cron-systeemlog | `since`, `limit` (maximaal 500) |

Later, met dezelfde route: `lxc.update` (één of meer CT-ID's) en `proxmenux.install`.

## 4. Module Cronjobs

Een gewone module in **Admin → Modulebeheer** (installeren, bewerken, verwijderen), zoals ProxMenux:

- **Installeren:** per node de agent plaatsen (zie §5), met dezelfde begeleiding en detectie per node als bij ProxMenux ("niet gevonden", "verouderd", "klaar").
- **Gebruiken:** **Proxmox → Nodes → Cronjobs**, met als eerste tabblad **Hele cluster** en daarnaast een tabblad per node. Gebruikers met de module `proxmox` zien jobs en resultaten; alleen admins maken, wijzigen, pauzeren, verwijderen en starten.
- **Hele cluster (jobgeschiedenis):** één tijdlijn van alle runs op alle nodes, nieuwste bovenaan: tijd, node, job, resultaat (✓ OK, ✗ fout met exitcode, ◌ bezig, △ gemist), duur en log. Filters op node, job, resultaat en periode; tellers bovenaan (bijv. "laatste 24 uur: 142 runs · 3 fout · 1 gemist"). Drie bronnen in dezelfde lijst:
  | Soort | Bron | Wat zichtbaar is |
  | --- | --- | --- |
  | ControlDeck-cronjobs | agent (log-wrapper) | start, einde, duur, exitcode, log |
  | Proxmox-jobs: backup (vzdump), replicatie | Proxmox-API (bestaande koppeling) | start, einde, resultaat, link naar het takenlog |
  | Overige cronjobs van de node | systeemlog van cron (`journalctl -u cron`) via de agent | alleen dat ze gestart zijn; geen resultaat of duur (niet via de log-wrapper). **Overnemen** geeft volledige monitoring |

  ControlDeck haalt de runs van alle nodes parallel op met een cache van 30 seconden; een node die niet antwoordt, blokkeert de rest niet en wordt apart gemeld (nooit als "OK").
- **Overzicht per node:**
  - **ControlDeck-jobs:** schema in gewone taal ("elke dag om 02:00"), volgende uitvoering, laatste uitvoering met resultaat (✓ OK, ✗ fout met exitcode, ◌ bezig, △ gemist), duur, gepauzeerd ja/nee.
  - **Overige cronjobs en systemd-timers** van de node: alleen-lezen, met bron (`/etc/crontab`, `/etc/cron.d/…`, crontab van root, timer).
- **Aanmaken en bewerken:** naam, omschrijving, commando, gebruiker, schema-kiezer (elke N minuten, elk uur, dagelijks, wekelijks, maandelijks, of geavanceerd), logs bewaren aan/uit. Bij het opslaan: samenvatting, uitleg van het schema en de volgende vijf uitvoeringen.
- **Acties per job:** nu uitvoeren (met live log), pauzeren/hervatten, dupliceren, verwijderen.
- **Geschiedenis:** per job de laatste runs (standaard 20) met tijd, duur, resultaat en log.

## 4a. Cronjobs op de node

- ControlDeck beheert alleen zijn **eigen** cronjobs, in `/etc/cron.d/controldeck`. Bestaande cronregels van het systeem, Proxmox of jezelf worden getoond maar nooit gewijzigd.
- Elke job heeft een definitie in `/etc/controldeck-agent/jobs/<id>.json` (root, `0600`). De cronregel roept niet het commando zelf aan, maar `controldeck-agent run <id>`.
- **Monitoren (log-wrapper):** `run` voert het commando uit en legt per run vast in `/var/lib/controldeck-agent/runs/<id>/<tijd>.json` en `.log`: start, einde, duur, exitcode en uitvoer (maximaal 256 KiB per run). **Rotatie:** per job de laatste 20 runs en maximaal 14 dagen; daarna verwijdert de agent ze zelf. Een run die nog bezig is, staat als "bezig" met een lock, zodat een volgende start niet dubbel loopt.
- **Pauzeren:** de job blijft bestaan, maar de regel in `/etc/cron.d/controldeck` wordt uitgecommentarieerd (`enabled: false`). ControlDeck toont daarmee laatste uitvoering, resultaat (OK/fout), duur en volgende uitvoering, en markeert een **gemiste run** als de laatste start ouder is dan het schema toelaat.
- **Validatie:**
  - `id`: kleine letters, cijfers en `-`, maximaal 40 tekens;
  - `schedule`: precies vijf cronvelden of `@hourly`/`@daily`/`@weekly`/`@monthly`, gecontroleerd op geldige waarden;
  - `user`: bestaande systeemgebruiker; standaard `root`;
  - `command`: één regel, maximaal 1000 tekens, geen NUL of regeleinde;
  - het bestand wordt atomisch geschreven en daarna door cron ingelezen.
- **Schema-kiezer in ControlDeck:** elke N minuten, elk uur, dagelijks om …, wekelijks op … om …, maandelijks op dag … om …, of geavanceerd met een vrije cronregel. Bij elk schema toont ControlDeck de uitleg in gewone taal en de volgende vijf uitvoeringen.

## 5. Koppelen per node

In Admin → Modulebeheer → **Node-agent**:

1. ControlDeck maakt (via de root-worker) eenmalig een SSH-sleutelpaar en toont per node één installatiecommando om in de shell van de node te plakken. Dat commando:
   - haalt `controldeck-agent` op uit de release die ControlDeck draait (vaste versie, SHA-256 gecontroleerd vóór installatie);
   - installeert het als `/usr/local/sbin/controldeck-agent` (root, `0755`);
   - voegt de sleutelregel met `restrict,from=…,command=…` toe aan `/root/.ssh/authorized_keys`.
2. ControlDeck leest de hostsleutel, jij bevestigt de vingerafdruk (`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` op de node).
3. ControlDeck test met `info`.

**Ontkoppelen:** Modulebeheer → Verwijderen toont het commando dat de sleutelregel verwijdert (en optioneel de agent en de eigen cronjobs). ControlDeck verwijdert zijn kopie van de hostsleutel.

**Bijwerken van de agent:** zoals de root-worker, bewust handmatig na controle: de wizard toont het commando voor de nieuwe versie. Een agent die ouder is dan ControlDeck nodig heeft, wordt gemeld en geblokkeerd, net als bij de root-worker.

## 6. Dreigingsmodel

| Scenario | Gevolg | Maatregel |
| --- | --- | --- |
| Iemand neemt een gewoon gebruikersaccount over | Geen acties | Alle schrijfacties zijn admin-only; de worker controleert de admin opnieuw |
| Iemand neemt de ControlDeck-webapp over (geen root) | Kan via het socket agent-acties laten uitvoeren, niet de sleutel lezen of meenemen | Proxy en agent accepteren alleen vaste acties; auditlog in de proxy (`/var/lib/controldeck-ssh/audit.log`) én op de node. Na herstel blijft de sleutel geldig: hij heeft het systeem nooit verlaten |
| Iemand neemt een **admin-sessie** over | Kan via `cron.put` een commando als root laten draaien | **Restrisico, inherent aan een cronjob-manager.** Beperkt door: alleen admins, samenvatting en expliciete bevestiging, auditlog bij ControlDeck én op de node, zichtbare wijzigingsgeschiedenis. Een verplichte hernieuwde login is bewust (nog) niet gekozen |
| Iemand neemt de ControlDeck-LXC als root over (of de gebruiker `controldeck-ssh`) | Heeft de sleutel: alle agent-acties op alle nodes | Sleutel werkt alleen vanaf het ControlDeck-IP, alleen voor de agent; intrekken = één regel verwijderen per node |
| Netwerk-aanvaller tussen ControlDeck en node | Geen | SSH met vastgepinde hostsleutel |
| Kwaadwillende of foute invoer | Geweigerd | Strikte validatie, geen shell-interpretatie van velden behalve het bewust ingevoerde `command` |

## 6a. Inspiratie en licenties

De functies zijn geïnspireerd op [CronMaster](https://github.com/fccview/cronmaster) (log-wrapper per run, pauzeren, live log, logrotatie, schema in gewone taal). CronMaster valt onder **AGPL-3.0**; ControlDeck neemt **geen code** over, alleen ideeën en werkwijzen. Voor het schema in gewone taal en het berekenen van volgende uitvoeringen worden de losse bibliotheken `cronstrue` (MIT, ondersteunt Nederlands) en `cron-parser` (MIT) overwogen, na de gebruikelijke controle in THIRD-PARTY.md; ze draaien alleen in de vooraf gebouwde frontend, niet op de nodes.

## 7. Overwogen alternatieven

| Alternatief | Waarom niet |
| --- | --- |
| Proxmox-API | Kan geen commando's op de host of in containers uitvoeren |
| Terminal van ProxMenux op afstand bedienen | Niet gedocumenteerd, interactief, en het token zou dan root geven |
| Gewone root-SSH zonder `command=` | Volledige shell voor ControlDeck: te veel macht bij één sleutel |
| Eigen HTTPS-dienst (agent) op elke node | Extra open poort en dienst die altijd draait; SSH staat al op elke node |
| Ansible | Zwaar voor de lichte runtime; vraagt toch volledige SSH-toegang |
| CronMaster koppelen | Extra root-webdienst (Node.js, http, poort 3000) op elke node; de REST-API kan geen jobs aanmaken of pauzeren en geeft geen run-geschiedenis |

## 7a. Stand van stap 1

`scripts/controldeck-agent.py` (Python 3, alleen standaardbibliotheek) bevat alle acties uit §3, de log-wrapper (`run <id>`), rotatie (20 runs / 14 dagen), lock tegen dubbel draaien, uitvoer tot 256 KiB per run, overnemen/teruggeven met back-up en het auditlog `/var/log/controldeck-agent.log`. De ControlDeck-cronregels bevatten alleen `controldeck-agent run <id>`; het commando zelf staat in de root-only jobdefinitie. Tests: `tests/test_agent.py` (op Windows draaien alleen de onderdelen zonder `/bin/sh`; CI draait alles op Linux). Nog niet verbonden met ControlDeck.

## 7b. Stand van stap 2

- `scripts/controldeck-agent-proxy.py` → `/usr/local/sbin/controldeck-agent-proxy`, systemd-dienst `deploy/controldeck-agent-proxy.service` (eigen gebruiker, `NoNewPrivileges`, `ProtectSystem=strict`, alleen `/var/lib/controldeck-ssh` schrijfbaar).
- Bewerkingen via het socket (één JSON-regel per verzoek): `status`, `keygen` (eenmalig ed25519-sleutelpaar), `scan` (hostsleutel en SHA-256-vingerafdruk van een node, nog niet vertrouwd), `trust` (opnieuw scannen; alleen als de vingerafdruk gelijk is aan wat de admin bevestigde, wordt de sleutel vastgelegd), `forget`, `call` (agent-actie uitvoeren).
- SSH-opties: `IdentitiesOnly`, eigen `known_hosts`, `StrictHostKeyChecking=yes`, `BatchMode=yes`, verbindings-time-out 5 s, totale time-out 60 s. Foutmeldingen voor de gebruiker noemen de oorzaak (hostsleutel veranderd, sleutel niet toegestaan, onbereikbaar) zonder technische details; die staan in het auditlog.
- `backend/agent_client.py`: de webapp-kant van het socket.
- `scripts/install-wizard.sh` installeert de proxy (inclusief `openssh-client`, gebruiker, rechten) en zet de agent klaar in `/opt/controldeck-integrations/agent/` voor verspreiding naar de nodes (stap 3).
- Tests: `tests/test_agent_proxy.py` (vingerafdruk vergeleken met `ssh-keygen`, gepinde hostsleutel, afgewezen vervalste hostsleutel, foutvertaling, socket-rechten `0660`).

## 7c. Stand van stap 3: module Cronjobs in Modulebeheer

**Admin → Modulebeheer → Installeren → Cronjobs** (bestand `config/catalog/cronjobs.json`, backend `backend/cronjobs.py`, frontend `frontend/components/cronjobs-connect.tsx`):

1. **Sleutel:** ControlDeck laat de agent-proxy eenmalig een ed25519-sleutelpaar maken en toont de publieke sleutel. Draait de proxy nog niet, dan toont de wizard het commando `bash scripts/install-wizard.sh`.
2. **Nodes:** de nodes en hun IP-adressen komen uit de Proxmox-koppeling. Per node:
   - **Hostsleutel lezen** → vergelijk de vingerafdruk met `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` op de node → **Node koppelen**. De proxy scant opnieuw en legt de sleutel alleen vast als de vingerafdruk gelijk is.
   - **Installatiecommando tonen** → plakken in de shell van de node. Het commando:
     - controleert dat `python3` aanwezig is;
     - downloadt `scripts/controldeck-agent.py` van GitHub **op de exacte commit die ControlDeck draait** en controleert de **SHA-256** vóór installatie (de checksum komt uit het bestand in de release-bundel);
     - installeert `/usr/local/sbin/controldeck-agent`;
     - voegt de sleutelregel `restrict,from="<IP van ControlDeck>",command="/usr/local/sbin/controldeck-agent" …` toe, maar alleen als die er nog niet staat. Op Proxmox is `/root/.ssh/authorized_keys` een symlink naar het clustergedeelde `/etc/pve/priv/authorized_keys`; het commando schrijft daar met `>>` doorheen, dus één keer toevoegen geldt voor het hele cluster.
     - Het IP-adres van ControlDeck bepaalt ControlDeck zelf per node (de route naar die node).
   - **Verbinding testen** → agent-actie `info`. Status per node: Klaar, Agent verouderd, Agent nog niet geïnstalleerd, Hostsleutel veranderd, Niet bereikbaar, Nog niet gekoppeld (onbekend is nooit "Klaar").
3. **Geïnstalleerd** zodra minstens één node "Klaar" is (`<datamap>/cronjobs/connection.json`).

**Verwijderen** vergeet de hostsleutels in de proxy en toont de commando's voor de node. Het commando om de sleutel uit `authorized_keys` te halen schrijft via `cat … >` door de symlink heen; `sed -i` zou de symlink naar het clusterbestand vervangen.

API (alleen admins, CSRF): `GET /api/cronjobs/agent`, `POST /api/cronjobs/agent/key`, `/scan`, `/trust`, `/install-command`, `/test`, `DELETE /api/cronjobs/connection`.

## 8. Besluiten (5 oktober 2026)

| Vraag | Besluit |
| --- | --- |
| Gebruiker van ControlDeck-cronjobs | Standaard **root**; per job een andere bestaande gebruiker te kiezen |
| Extra beveiliging bij aanmaken, wijzigen, nu uitvoeren | **Samenvatting + expliciete bevestiging + auditlog** (bij ControlDeck en op de node). Geen verplichte hernieuwde login |
| Meldingen bij mislukte of gemiste jobs | Voorlopig **alleen zichtbaar in ControlDeck**; e-mail/push later als aparte functie |
| Bestaande cronjobs | **Alleen-lezen**, met per job **Overnemen**: ControlDeck maakt een eigen job met hetzelfde schema en commando (met logging en monitoring) en zet het origineel uit door de regel uit te commentariëren met de markering `# disabled by ControlDeck <datum> (job <id>)`. Een kopie van het originele bestand gaat naar `/var/lib/controldeck-agent/backups/`. Terugzetten kan met **Teruggeven** |
