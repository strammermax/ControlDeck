# Workfarm in de huisstijl

Workfarm draait in een frame: de CSS van ControlDeck kan niet automatisch de
inhoud ervan opmaken. De werkelijke dashboardbron staat in de Prefect-repository,
onder `dashboard/`. Die laadt een ongewijzigde kopie van `huisstijl/css/tokens.css`
uit huisstijlversie 2026.10.14.1. Lokale layoutregels gebruiken uitsluitend tokens;
er wordt geen alternatieve kleurenpalet gedefinieerd.

ControlDeck geeft `theme=dark|light` en `embedded=1` mee aan `/workfarm/`.
Bij wisselen van thema wordt het frame opnieuw geladen; filters, paginaselectie en
opengeklapte logs in het frame worden daardoor opnieuw ingesteld. In het frame is
de dubbele dashboardheader verborgen. Het losse venster behoudt de header en heeft
een eigen themaknop. Ongeldige themawaarden vallen in Workfarm terug op donker;
ControlDeck zelf weigert zulke waarden.

Knoppen, kaarten, statuskleuren, tabellen, focusranden en logvlakken gebruiken de
gedeelde huisstijl. Op smalle schermen worden kaarten één kolom en scrollt alleen
de brede workitemtabel horizontaal. De server serveert uitsluitend de drie expliciet
toegestane stijl-/scriptbestanden, met dezelfde netwerktoegangscontrole als de pagina.

Controles: ControlDeck `frontend/tests/workfarm.test.mjs`, Prefect
`tests/test_dashboard.py` en `node tests/test_dashboard_theme.cjs`. De deployment
van Prefect moet ook de nieuwe CSS- en themabestanden meenemen.
