# Dashboardwidgets: scope en voortgang

De gebruiker heeft het dashboard en deze widgetvolgorde expliciet aangevraagd. Alle widgets zijn afzonderlijk toevoegbaar, instelbaar en verplaatsbaar via de bestaande dashboardeditor. Bestaande pagina’s blijven de uitgebreide beheerweergaven.

| Onderdeel | Implementatie | Live acceptatie |
| --- | --- | --- |
| Systeem | CPU, geheugen, temperatuur en CPU-vermogen; alle nodes of één node | Bestaande Proxmox/ProxMenux-bronnen, drie nodes bereikbaar |
| Downloads | qBittorrent en SABnzbd, wachtrij en voortgang | Beide API’s bereikbaar; qBittorrent gebruikt zijn API-key |
| Media | Plex-streams en Seerr-aanvragen | Seerr werkt; Plex-container staat uit en is niet gestart |
| Tdarr | Workers en verwerkingsaantallen | API bereikbaar; geen actieve workers tijdens acceptatie |
| Home Assistant | Eigen dashboard in HTTPS-iframe met apart-openen-optie | Adres ingesteld; browseraanmelding en framebeleid nog met gebruiker controleren |
| Agenda | Nextcloud CalDAV, komende zeven dagen | Twee agenda’s bereikbaar; geen afspraken in testvenster |
| Prefect | Laatste flowruns met status | API bereikbaar, echte runs aanwezig |
| Koopjesbot | Nieuwste tien persoonlijke, ongelezen aanbiedingen met prijs en link | Aanleverroute en exporter gebouwd; accountkoppeling wacht op expliciet Koopjesbot-account |

Home Assistant is op verzoek een iframe, geen nieuwe sensor- of bedieningslaag. Koopjesbot toont aanbiedingen in plaats van alleen aantallen. Nextcloud Google-browseraanmelding blijft afzonderlijk uitgesteld in GitHub-issue #10; CalDAV werkt onafhankelijk daarvan.

Verificatie: 648 Python-tests geslaagd, 8 overgeslagen; 190 frontendtests geslaagd; TypeScript en statische productiebuild geslaagd. Tests omvatten normaal gebruik, grensgevallen, afwijzing, sessie/CSRF, bronrechten, gebruikersisolatie, ongeldige upstreamgegevens en veilige links. Systeemkaarten zijn met fictieve waarden in licht/donker op een smalle viewport bekeken; dit vervangt geen ingelogde acceptatie van alle instellingen.

Zie [SERVICE-WIDGETS.md](SERVICE-WIDGETS.md) voor inrichting, rechten, API-contract en resterende live controles.
