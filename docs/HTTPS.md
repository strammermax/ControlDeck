# HTTPS voor ControlDeck

**Domein:** `controldeck.vanburik.info`  
**Status:** actief en gecontroleerd op 5 oktober 2026.  
**Route:** bestaande Cloudflare Tunnel `remote` rechtstreeks naar LXC 164.

## Werkelijke route

```text
Browser → https://controldeck.vanburik.info:443
                    |
                    v
           Cloudflare HTTPS-ingang
                    |
             Versleutelde tunnel
                    |
                    v
      Bestaande cloudflared-connector
                    |
         HTTP op het lokale netwerk
                    |
                    v
           http://controldeck.home:8080
           Flask/Gunicorn in LXC 164
```

Cloudflare verzorgt het browsergerichte TLS-certificaat. De bestaande tunnelconnector gebruikt een versleutelde verbinding met Cloudflare. De laatste verbinding van die connector naar de ControlDeck-LXC gebruikt HTTP. Er is dus geen TLS-certificaat in de ControlDeck-applicatie zelf geïnstalleerd en niet ieder segment van deze route gebruikt TLS.

Er is geen extra proxy of tunnelproces in LXC 164 geplaatst. De gebruiker heeft de hostname aan de bestaande tunnel toegevoegd met zijn Proxmox-toolbox. Nginx Proxy Manager op `nginxproxy.home` maakt geen deel uit van deze actieve route.

## Ingestelde tunnelroute

| Instelling | Waarde |
| --- | --- |
| Tunnel | `remote` |
| Publieke hostname | `controldeck.vanburik.info` |
| Service | `http://controldeck.home:8080` |
| Publieke DNS | Cloudflare-record naar de bestaande tunnel |
| Applicatiepoort | `8080` |
| Browserpoort | `443` |

In de tunnelwizard is protocol `http` correct: het beschrijft de verbinding naar de origin, niet het protocol van de browser. Protocol `https` kiezen voor een origin die alleen HTTP aanbiedt, zou de verbinding laten mislukken.

## Verificatie

De HTTPS-aanvragen zijn met normale certificaatvalidatie uitgevoerd; certificate checks zijn niet uitgeschakeld.

- Startpagina: HTTP 200 en titel ControlDeck — Homelab Control Center.
- `/health`: HTTP 200, versie `0.1.1` en de bedoelde volledige deploymentcommit.
- `/ready`: HTTP 200.
- `/THIRD-PARTY-LICENSES.txt`: HTTP 200.
- `http://controldeck.vanburik.info/`: HTTP 301 naar de HTTPS-versie.

Na iedere deployment kan `/health` opnieuw worden gecontroleerd om versie en commit te vergelijken met GitHub. Applicatie-updates vervangen de tunnelroute of Cloudflare-certificaten niet.

## Interne DNS en alternatieve LAN-route

De huidige domeinnaam kan ook vanaf het LAN via Cloudflare worden gebruikt. Technitium DNS hoeft hiervoor geen record naar LXC 164 te krijgen: een rechtstreekse verwijzing naar de LXC biedt op die host geen HTTPS-listener op poort 443.

Als later een volledig lokale HTTPS-route gewenst is, kan Nginx Proxy Manager een host met passend certificaat aanbieden die naar `controldeck.home:8080` verwijst. Pas dan kan Technitium de hostname intern naar `nginxproxy.home` laten resolven. Dit is een aanvullende route en is voor ControlDeck nog niet ingesteld. Controleer daarbij bestaande zones, A/AAAA/CNAME-records en certificaatvernieuwing.

## Toegang en vervolg

HTTPS versleutelt de browserverbinding en bewijst serveridentiteit. Het vervangt geen login of autorisatie. De huidige foundation toont alleen een startpagina en healthinformatie. Vóór koppeling van gevoelige infrastructuurgegevens en beheeracties moet applicatieauthenticatie en eventueel Cloudflare Access worden ingericht.

Als ook de laatste LAN-verbinding versleuteld moet zijn, krijgt de origin een TLS-listener met een door de connector gevalideerd certificaat. Daarna wordt de service-URL bewust naar HTTPS gewijzigd; certificate validation wordt niet uitgeschakeld.

Bronnen: [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/), [published application protocols](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/protocols/), [Nginx Proxy Manager](https://nginxproxymanager.com/guide/).
