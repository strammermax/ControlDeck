# Beveiliging

De applicatie vereist Google OIDC-login en een actief toegestaan account voor alle privé-API's. Accountbeheer is admin-only; configuratie wordt op serverrechten gefilterd en voorkeuren horen uitsluitend bij de aangemelde identiteit. Cookies zijn Secure/HttpOnly/SameSite en schrijfacties vereisen CSRF. Zie [AUTHENTICATION.md](AUTHENTICATION.md). Health/readiness blijven publiek voor runtimecontroles. Terminal en infrastructuuracties zijn nog niet geïmplementeerd.

De applicatiegebruiker is onbevoorrecht. De runner is een afzonderlijke gebruiker en kan alleen de geïnstalleerde deployhelper via sudo aanroepen. Omdat die helper vertrouwde applicatiecode en dependencies installeert, behoren repositoryschrijfrechten en workflowrechten tot de productie-vertrouwensgrens.

Voer geen fork- of pull-requestcode uit op de productierunner. Houd de runner en de container bijgewerkt. Publiceer de beheeromgeving alleen via bewust ingerichte netwerktoegang en HTTPS.

Gebruik voor een beveiligingsmelding GitHub private vulnerability reporting als dat voor de repository is ingeschakeld. Zet gevoelige details of secrets niet in een publieke issue. Een contactadres wordt pas opgenomen wanneer de maintainer er een opgeeft.
