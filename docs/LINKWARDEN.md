# Linkwarden — Bookmarks in ControlDeck

## Werking

Linkwarden is de centrale opslag voor bookmarks, collecties en tags. De eigen Bookmarks-pagina in ControlDeck haalt deze gegevens op via de Linkwarden-API; er wordt geen tweede bookmarkdatabase opgebouwd. De pagina ondersteunt zoeken, collectiefilters, paginering, verversen en een nieuwe bookmark opslaan. Persoonlijke en gedeelde collecties volgen de toegangsrechten van Linkwarden. Collecties beheren en uitgebreid bewerken blijven beschikbaar via **Open Linkwarden**.

De Linkwarden-browserextensie gebruikt dezelfde server. Een daarmee opgeslagen bookmark verschijnt in ControlDeck na verversen. Installeer de extensie via de officiële Linkwarden-downloadlinks en gebruik het HTTPS-adres van je eigen server. De extensie blijft met Linkwarden authenticeren; ControlDeck deelt geen sessiecookies met de extensie.

## Bestaande installatie koppelen

1. Open als admin **Admin → Modulebeheer → Linkwarden**.
2. Kies **Bestaande Linkwarden koppelen**, vul het HTTPS-basisadres of een intern IP-adres in en eventueel meteen jouw persoonlijke API-token. Alleen een intern IP krijgt standaard HTTP en poort 3000; een expliciete poort blijft behouden. Een `/dashboard`-adres wordt omgezet naar het basisadres. Alleen admins mogen de bestemming veranderen.
3. Open **Bookmarks → Mijn koppeling** en vul een persoonlijke Linkwarden-API-token in.
4. De server controleert `/api/v1/users/me`: de e-mail moet overeenkomen met het huidige ControlDeck-account. Daarna kunnen bookmarks worden opgehaald.

Iedere gebruiker heeft een eigen API-token. Een beheer-token wordt niet gebruikt als gezamenlijke toegang tot alle persoonlijke gegevens. Tokens worden uitsluitend op de ControlDeck-server bewaard in bestanden met beperkte rechten onder `/var/lib/controldeck/linkwarden/users`; zij komen niet terug in API-antwoorden, browseropslag, configuratie-export of Git. Een gewijzigde bestemming gebruikt andere tokenbestanden en ontvangt nooit automatisch een token van de vorige server. Iedere bookmarkaanvraag controleert opnieuw de upstream-identiteit.

**Mijn koppeling verwijderen** wist de persoonlijke token uit ControlDeck. **Verbinding verwijderen** in Modulebeheer ontkoppelt alleen de server; deze actie verwijdert geen Linkwarden-container, collecties of bookmarks. Bestaande persoonlijke tokenbestanden blijven bij ontkoppelen bewaard en worden opnieuw gebruikt als dezelfde server later terugkomt.

## Login en thema

De eigen Bookmarks-interface gebruikt de verplichte ControlDeck Google-login en de moduletoegangsrechten. Na eenmalig invoeren van de API-token is geen tweede Linkwarden-login nodig voor deze pagina. Zowel de lichte als donkere weergave gebruikt de bestaande ControlDeck-stijlen en opgeslagen gebruikersvoorkeur.

Dit maakt ControlDeck niet tot een OAuth-provider. Voor de zelfstandige Linkwarden-interface en browserextensie kan Google-SSO worden ingesteld volgens de officiële documentatie. Hiervoor zijn `NEXT_PUBLIC_GOOGLE_ENABLED=true`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` en een geldige `NEXTAUTH_URL` nodig. De Google-client moet het callbackadres `https://<linkwarden-host>/api/v1/auth/callback/google` toestaan. De bestaande ControlDeck-cookie of API-token wordt hiervoor niet hergebruikt. De instellingen van een bestaande Linkwarden-server worden niet automatisch gewijzigd.

## Nieuwe Docker-installatie

De wizard biedt een aparte Docker-route. De rootworker accepteert uitsluitend de gereviewde `install-linkwarden.sh`; de browser kan geen image, opdracht of shellargument doorgeven. Workerprotocol 3 is vereist. Werk de root-owned installatiebestanden bij met `scripts/install-wizard.sh` na review.

De installatie gebruikt Linkwarden `v2.16.3` en PostgreSQL 16 Alpine, met afzonderlijke blijvende volumes. Het lichte profiel schakelt browserarchivering uit (`DISABLE_BROWSER=true`) en gebruikt PostgreSQL-zoeken zonder MeiliSearch. Hierdoor blijven bookmarks, tags en collecties beschikbaar, maar ontbreken browsergegenereerde screenshots, PDF's en snapshots. De applicatie krijgt maximaal 768 MiB en 1,5 CPU, PostgreSQL 256 MiB en 0,5 CPU. Deze limieten zijn geen garantie voor voldoende capaciteit bij grote imports.

De installatiecontrole vereist minimaal 2 GiB totaal RAM, 3 GiB vrije Docker-opslag en een root-owned bestand `/etc/controldeck/linkwarden.env` met mode `0600`. Vul dat privé met ten minste:

```dotenv
POSTGRES_PASSWORD=<sterk uniek geheim zonder URL-gereserveerde tekens>
NEXTAUTH_SECRET=<sterk uniek geheim>
NEXTAUTH_URL=https://<linkwarden-host>/api/v1/auth
NEXT_PUBLIC_DISABLE_REGISTRATION=true
# Optioneel: specifiek LAN-adres voor de bestaande HTTPS-proxy.
LINKWARDEN_BIND_IP=127.0.0.1
```

De containerpoort 8092 bindt standaard alleen loopback. Een proxy op een andere LAN-host vereist een expliciet LAN-bindadres en passende firewallregels. Stel de HTTPS-route in voordat je Linkwarden met een browser of extensie gebruikt. Koppel daarna het publieke basisadres in Modulebeheer en maak/toelaat de juiste Linkwarden-gebruikers. Geheimen zijn geen frontendinstellingen.

Deze Docker-route is voorbereid en geautomatiseerd getest met fixtures. Er is voor deze module geen extra Linkwarden-server op productie gestart: de bestaande installatie wordt gebruikt en de huidige ControlDeck-LXC heeft minder dan 2 GiB RAM. Een echte nieuwe Docker-uitrol en resourcewaarneming blijven een afzonderlijke verificatiestap op een geschikte host.

## Proxmox LXC

De wizard biedt **Nieuwe Proxmox LXC** met een begeleide installatie. Kies eerst een online node uit de gekoppelde Proxmox-cluster. Als de nodegegevens niet beschikbaar zijn, kun je de nodenaam handmatig invullen. Daarna toont de wizard het officiële Helper-Script en de stappen om het als root in de Shell van die Proxmox-host uit te voeren. Container-ID, opslag, netwerk en resources kies je in het Helper-Script. Offline nodes uit de opgehaalde lijst zijn niet selecteerbaar.

Nadat de gebruiker bevestigt dat de installatie gereed is, gaat de wizard verder naar het adres/IP-adres en de persoonlijke API-token. De bevestiging is een gebruikersverklaring, geen automatische healthcheck; de API-tokencontrole verifieert de toegang. De huidige Proxmox-koppeling blijft read-only. Automatisch starten en volgen op de host is nog niet aangesloten, en ControlDeck claimt geen voortgang van een handmatig gestart script. Er wordt geen SSH-toegang gevraagd om deze begeleide route te gebruiken.

## Verificatie en grenzen

Normaal-, boundary- en failure-tests controleren URL's, persoonlijke tokenverificatie, zoeken, collecties, toevoegen, secretopslag, moduletoegang, CSRF, upstreamfouten en installatieplanning. API-antwoorden worden geprojecteerd naar de benodigde velden; onveilige bookmark-URL's worden niet weergegeven. Upstreamredirects worden niet gevolgd. Zoekresultaten komen uit `/api/v1/search`; het oudere `/links`-zoekendpoint is deprecated.

De aangeleverde token wordt privé gecontroleerd via `/api/v1/users/me`. Voor een lokaal Linkwarden-account zonder e-mail kan de beheerder een expliciet bevestigde koppeling op upstream-gebruikers-ID installeren; iedere aanvraag controleert daarna dezelfde ID. De gewone tokenwizard vereist een overeenkomend e-mailadres. Deze uitzondering deelt geen token met andere ControlDeck-gebruikers. De module toont hiervoor een koppelformulier. Het opgeslagen adres bevestigt uitsluitend de bestemming; het bewijst geen werkende API-toegang. Maak voor herstel backups van de Linkwarden-volumes en de privéconfiguratie; alleen de ControlDeck-appcode terugrollen herstelt geen Linkwarden-database.

Linkwarden blijft een afzonderlijke upstreamtoepassing; er is geen Linkwarden-broncode gekopieerd in de ControlDeck-module. Linkwarden gebruikt AGPL-3.0; de upstreamlicentie en voorwaarden blijven gelden voor zijn distributie en eventuele wijzigingen.

## Herstel na een afgebroken LXC-update

Op 5 oktober 2026 ontbrak de productiebuild van de webinterface. Na opnieuw bouwen bleek ook de database achter te lopen: Prisma meldde een ontbrekende `User.uuid`-kolom. Een actieve service is onvoldoende als alleen de worker draait.

Het herstel bestond uit een gecontroleerde databaseback-up, opnieuw bouwen met `yarn web:build`, uitvoeren van de officiële migraties met `yarn prisma:deploy` en herstarten. De LXC kreeg tijdelijk 4 GiB RAM voor de build en is daarna teruggezet op 2 GiB. De aantallen gebruikers, bookmarks en collecties bleven gelijk. De oorspronkelijke oorzaak van het afbreken van de update is niet definitief vastgesteld.

Verificatie: publieke HTTPS-site en persoonlijke API geven HTTP 200; zonder token geeft de identiteits-API HTTP 401. De ControlDeck-koppeling, tokenisolatie en bestandsrechten zijn opnieuw gecontroleerd. Bestaande tokens en configuratie bleven behouden. Bij toekomstige updates moeten zowel de webbuild als de migraties succesvol eindigen voordat de service wordt gestart.

## Bronverwijzingen

- [API](https://docs.linkwarden.app/api/api-introduction)
- [Installatie](https://docs.linkwarden.app/self-hosting/setup)
- [Google en andere SSO-providers](https://docs.linkwarden.app/self-hosting/sso-oauth)
- [Licht installatieprofiel](https://docs.linkwarden.app/self-hosting/lighter-setup)
- [Proxmox VE Helper-Script](https://github.com/community-scripts/ProxmoxVE/blob/main/ct/linkwarden.sh)
