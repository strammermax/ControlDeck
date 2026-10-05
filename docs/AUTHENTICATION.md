# Login, accounts en voorkeuren

Google verzorgt authenticatie via OpenID Connect. ControlDeck beheert zelf de toegestane gebruikers, rollen en voorkeuren. Er zijn geen lokale gebruikerswachtwoorden. Zonder geldige sessie zijn configuratie, accounts en voorkeuren niet toegankelijk, ook niet via het LAN. Het initiële HTML-document bevat alleen de shell/aanmeldinterface; het menu en de modules worden pas na authenticatie opgehaald.

## Accountprofiel en rechten

Een account heeft `firstName`, `lastName`, `email`, `role` (admin/user), `enabled` (standaard true), `ssoType` (google/windows) en een optionele `modules`-lijst (standaard `["*"]`). Voorbeeld:

```json
{
  "firstName": "Example",
  "lastName": "User",
  "email": "admin@example.com",
  "role": "admin",
  "enabled": true,
  "ssoType": "google",
  "modules": ["*"]
}
```

Accounts staan als array in `/var/lib/controldeck/accounts.json` op de LXC. De installatie levert een lege lijst; de beheerder moet minstens één toegestane Google-admin invullen. De productieaccounts zijn apart geïnstalleerd en staan niet in Git.

Een admin kan onder **Admin → Gebruikers** profielen aanmaken en wijzigen. Uitschakelen ontneemt toegang bij de volgende serveraanvraag. Rolwijzigingen worden bij iedere aanvraag opnieuw gelezen. De laatste actieve Google-admin mag niet worden uitgeschakeld, omgezet naar Windows of gedegradeerd. Er is geen publieke registratie. Users mogen eigen voorkeuren opslaan maar krijgen geen adminmenu, accountoverzicht of schrijfbevoegdheid op accounts. Een modules-lijst kan toegang verder beperken; deze projectie gebeurt op de server.

Windows is voorlopig uitsluitend een profielkeuze voor een latere koppeling met bijvoorbeeld Microsoft Entra ID. Een Windows-profiel kan niet met Google inloggen. Er is nog geen Windows-loginroute. Voornaam en achternaam worden door de admin ingevuld; Google-login vraagt uitsluitend `openid email`.

## Google OAuth instellen

Maak een Google OAuth-client van het type **Web application**. Voor de huidige productieomgeving:

- Authorized JavaScript origin (optioneel voor deze serverflow): `https://controldeck.vanburik.info`.
- Authorized redirect URI: `https://controldeck.vanburik.info/auth/google/callback`.
- Wanneer het Google consent project in Testing staat, moeten de toegestane gebruikers ook Google test users zijn.

De redirect moet exact overeenkomen. ControlDeck gebruikt een vast geconfigureerd HTTPS-basisadres en leidt dit niet af uit proxyheaders. Referenties: [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect) en [Authlib Flask-client](https://docs.authlib.org/en/latest/oauth2/client/web/flask.html).

LXC: zet in `/etc/controldeck/controldeck.env` (root-only, 0600):

```text
CONTROLDECK_BASE_URL=https://controldeck.vanburik.info
CONTROLDECK_GOOGLE_CLIENT_ID=<client-id>
CONTROLDECK_GOOGLE_CLIENT_SECRET=<client-secret>
```

`controldeck.service` leest dit optionele EnvironmentFile. Herstart na wijzigingen aan OAuth-variabelen. Configuratie- en accountbestanden worden zonder herstart opnieuw gelezen. Wanneer OAuth niet compleet is ingesteld, blijft de loginpoort gesloten; er is geen gastfallback.

Docker: gebruik `.env.example` als basis voor een niet-gecommit `.env` en een schrijfbare `/data`-volume. `CONTROLDECK_DATA_DIR=/data`; `CONTROLDECK_ACCOUNTS=/data/accounts.json`. Kopieer een accountlijst naar die volume voordat je inlogt; een ontbrekende of ongeldige lijst geeft niemand toegang. Het configuratievolume blijft alleen-lezen.

## Sessies en voorkeuren

Authlib controleert OAuth state, nonce en het ondertekende ID-token. Alleen een geverifieerd Google-e-mailadres dat actief in de lokale accountlijst staat krijgt een sessie. De stabiele Google `sub` wordt bij de eerste login aan het account gebonden; een ander Google-account kan niet via hetzelfde e-mailadres een bestaande identiteit overnemen. Het profiel is dus zonder wachtwoord, maar bevat technisch ook deze interne identiteitskoppeling.

De ondertekeningssleutel staat persistent in `CONTROLDECK_DATA_DIR/session.key` met rechten 0600. Google tokens worden niet in de sessie of database bewaard. Cookies zijn Secure, HttpOnly en SameSite=Lax; sessies duren maximaal acht uur zonder automatische verlenging. Uitloggen verwijdert de lokale sessie, niet de Google-sessie. Na uitschakelen of verwijderen wordt een bestaand account bij de volgende aanvraag afgewezen.

De SQLite-database `users.sqlite3` slaat het Google-subject, e-mailadres en voorkeuren op. Thema en laatst bezochte module worden automatisch opgeslagen en op een ander apparaat bij login opnieuw geladen. Een expliciete hashlink in de URL gaat vóór de laatst bezochte module. De API ondersteunt alleen deze voorkeurvelden; extra voorkeuren worden bij nieuwe bediening expliciet toegevoegd. Iedere gebruiker kan uitsluitend zijn eigen voorkeuren lezen en wijzigen. Schrijfacties en uitloggen vereisen een sessiegebonden CSRF-token.

Maak backups van accounts, configuratiemappen, session.key en users.sqlite3. Deze staan buiten de versie-releases en worden niet overschreven door CI/CD. Een backup van SQLite moet consistent zijn, bijvoorbeeld via de SQLite backup-API of tijdens een servicestop. Accounts en OAuth-geheimen mogen niet naar GitHub; `secrets/`, `.env`, data en lokale accountbestanden worden uitgesloten.

## Grenzen

Health en readiness blijven publiek voor deploymentcontroles; ze geven geen accountgegevens. De Google-loginroute en sessiestatus zijn toegankelijk om de login te starten. Externe toepassingen hebben hun eigen toegang en login. De toekomstige Terminal en provideracties moeten dezelfde rechtencontroles gebruiken; ze zijn nog niet gebouwd. Een volledig doorlopen Google-login vereist een echte toegestane gebruiker en wordt apart van unit-tests en lokale testaccounts gecontroleerd.
