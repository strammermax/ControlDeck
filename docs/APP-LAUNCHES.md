# Automatisch aanmelden vanuit modules

## Ondersteunde routes

Kasm en Nextcloud zijn afzonderlijke modules, met één gedeelde aanmeldknop en een centrale serverroute. Ze kunnen op de eigen modulepagina of op een dashboard worden gebruikt. Modulecode bevat geen persoonlijke hostnamen, accounts of wachtwoorden.

- Kasm: de server gebruikt de officiële `POST /api/public/get_login`-API om een aanmeldlink voor het vooraf gekoppelde bestaande Kasm-account te verkrijgen. De API-sleutel vraagt de permissie Users Auth Session; er worden geen gebruikers gemaakt en geen groepen/rechten gewijzigd. Deze eerste stap opent het Kasm-portaal; direct starten en monitoren van een specifiek workspace-image is nog niet gebouwd.
- Nextcloud: de server opent de vooraf ingerichte Google/OIDC-route van de `user_oidc`-app. De Google-sessie van de browser kan hergebruikt worden; eerste toestemming, accountkeuze of door de provider vereiste verificatie blijven mogelijk. Een API-appwachtwoord is geen vervanging voor deze browseraanmelding. De route configureert de Google-client of user_oidc-provider niet automatisch.

De adapterstructuur kan later andere officiële aanmeldmethoden ondersteunen. Willekeurig invullen van websiteformulieren met wachtwoorden is niet geïmplementeerd. Een nieuw systeem krijgt een eigen expliciete adapter, met dezelfde rechten- en vaultgrenzen.

## Private inrichting

Plaats één JSON-waarde `CONTROLDECK_APP_LAUNCHES` in de bestaande ControlDeck-vaultmap van Infisical. De service leest die rechtstreeks via Camiels `infisical-secret-client`; er worden geen extra omgevingsvariabelen of publieke configuratiegeheimen toegevoegd. Ontbrekende of onbereikbare vaultinstellingen blokkeren alleen deze aanmeldactie.

De JSON heeft optionele sleutels `kasm` en `nextcloud`:

- `kasm`: exact `url` (HTTPS-origin), `apiKey`, `apiSecret` en `users`. `users` koppelt het door ControlDeck geverifieerde e-mailadres aan de bestaande Kasm-user-UUID. Neem alleen de bedoelde accounts op. De gebruiker kan zelf geen doelaccount meegeven.
- `nextcloud`: exact `url` (HTTPS-origin) en `loginPath`. Ondersteunde paden zijn `/apps/user_oidc/login/<provider-id>` en `/index.php/apps/user_oidc/login/<provider-id>`. Kies het ID van de bestaande Google-provider. Installaties onder een URL-subpad of een andere authenticatie-app vragen een afzonderlijke adapteruitbreiding.

Schakel de overeenkomstige provider in de private runtimeconfiguratie in en stel daar het publieke basisadres in. Kasm is al een bestaand configuratietype. De distributie bevat een uitgeschakelde Nextcloud-provider met de moduledefinitie; bestaande private configuratiemappen worden bij release niet overschreven en moeten deze definitie zo nodig overnemen. Voeg de module toe aan de gewenste gebruikersrechten. Een menu-item is optioneel: het dashboard kan de ingeschakelde module rechtstreeks gebruiken.

De service moet het publieke HTTPS-adres kunnen bereiken met geldige certificaatcontrole. Er worden geen certificaatcontroles uitgezet of bestaande Google/Cloudflare-beveiligingen veranderd. De live inrichting is nog niet geactiveerd: publieke adressen, vaultverwijzingen, accountkoppeling en de bestaande Google-providerinstelling moeten eerst worden vastgesteld. Lokale tests met synthetische gegevens bewijzen geen echte aanmelding.

## Nextcloud met Social Login

Een Nextcloud-installatie kan ook de Social Login-app gebruiken voor Google. Bewaar de OAuth-client in Infisical onder `/Nextcloud` met `NEXTCLOUD_GOOGLE_CLIENT_ID`, `NEXTCLOUD_GOOGLE_CLIENT_SECRET` en `NEXTCLOUD_GOOGLE_REDIRECT_URI`. Configureer de provider via Nextclouds appconfig-API als gevoelige array; geef secrets niet mee in procesargumenten. Maak vooraf een gecontroleerde database- en configuratieback-up.

Gebruik `disable_registration=true`, `allow_login_connect=true`, `hide_default_login=false` en `update_profile_on_login=false`. Bestaande gebruikers melden zich eerst met hun gewone account aan, openen persoonlijke instellingen → Social Login en koppelen daar Google. Niet-gekoppelde Google-accounts mogen geen nieuwe Nextcloud-gebruiker aanmaken. De gewone login blijft als toegang beschikbaar.

Controleer de loginpagina, de redirect naar Google, het exacte geregistreerde terugkeeradres en een aanwezige OAuth-state. Deze controles bewijzen nog geen afgeronde Google-aanmelding: de gebruiker moet de eerste accountkoppeling uitvoeren en daarna opnieuw aanmelden. De bestaande ControlDeck-adapter ondersteunt momenteel alleen `user_oidc`; Social Login in Nextcloud activeren maakt de ControlDeck-startknop nog niet geschikt voor deze route.

## Grenzen en controles (ControlDeck)

`POST /api/app-launches/<module-id>` verwacht uitsluitend `{}` en een geldige sessie met CSRF-token. De server controleert telkens de bestaande modulerechten en leest het doel uit de vault. POST-bodyvelden voor gebruikers, wachtwoorden of doeladressen worden afgewezen. API-sleutels blijven aan de serverkant; alleen de voor de browser bedoelde Kasm-aanmeldlink gaat terug. Deze link wordt niet in dashboards, lokale opslag of logs bewaard. Het antwoord heeft no-store en no-referrer; open de dienst in hetzelfde tabblad om geblokkeerde pop-ups te vermijden.

Kasm-netwerkverzoeken hebben een vaste timeout en volgen geen redirects. Antwoordlinks moeten dezelfde HTTPS-origin en de bekende Kasm-aanmeldroute gebruiken. Providerfouten worden generiek afgehandeld en bevatten geen antwoordbody of geheime waarden. TLS blijft actief. Een ontbrekend Kasm-profiel wordt geweigerd; er is geen gedeeld beheeraccount als terugval. Nextcloud blijft zijn eigen toegang en Google-identiteit controleren.

## Officiële bronnen

- [Kasm Developer API: Get Login](https://www.kasmweb.com/docs/latest/developers/developer_api.html#get-login)
- [Kasm Google OpenID](https://www.kasmweb.com/docs/latest/guide/oidc/google.html)
- [Nextcloud: authenticatie met OpenID Connect](https://docs.nextcloud.com/server/stable/admin_manual/configuration_user/user_auth_oidc.html)
- [Nextcloud user_oidc-routes](https://github.com/nextcloud/user_oidc/blob/main/appinfo/routes.php)
