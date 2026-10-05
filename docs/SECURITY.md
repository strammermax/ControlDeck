# Beveiliging

De foundation bevat uitsluitend een introductiepagina en publieke health/readiness-informatie. Er zijn nog geen login, providercredentials, terminal of infrastructuuracties. Voor verdere functies is serverzijdige authenticatie en autorisatie vereist zoals beschreven in het ontwerp.

De applicatiegebruiker is onbevoorrecht. De runner is een afzonderlijke gebruiker en kan alleen de geïnstalleerde deployhelper via sudo aanroepen. Omdat die helper vertrouwde applicatiecode en dependencies installeert, behoren repositoryschrijfrechten en workflowrechten tot de productie-vertrouwensgrens.

Voer geen fork- of pull-requestcode uit op de productierunner. Houd de runner en de container bijgewerkt. Publiceer de beheeromgeving alleen via bewust ingerichte netwerktoegang en HTTPS.

Gebruik voor een beveiligingsmelding GitHub private vulnerability reporting als dat voor de repository is ingeschakeld. Zet gevoelige details of secrets niet in een publieke issue. Een contactadres wordt pas opgenomen wanneer de maintainer er een opgeeft.
