# Cassette-animatie

Open `cassette-animatie.html` in een browser. Het bestand bevat de meegeleverde afbeelding en werkt offline, zonder installatie. Beide spoelen draaien linksom met iets verschillende snelheden; de kleine geleiderollen draaien mee. De tapewikkelingen gebruiken de textuur uit de foto. Een fijn bewegend oppervlaktepatroon geeft het doorlopende tapetransport onderaan weer, zonder stippellijn. De cassette staat vrij tegen zuiver zwart. De tapehoeveelheid blijft gelijk; het is een visuele lus. De knop pauzeert en hervat de animatie. Bij een voorkeur voor minder beweging begint de cassette gepauzeerd. Een ontbrekende afbeelding geeft een foutmelding en schakelt afspelen uit.

Dit is een losse visuele demonstratie, zonder koppeling aan het Dashboard of een muziekspeler.

Controle: `node --test frontend/tests/cassette-animation.test.mjs` dekt afspelen/pauzeren, minder beweging en laden dat mislukt.

## Bewerking van de aangeleverde video

De aangeleverde video is lokaal verwerkt naar `C:/Users/stram/Videos/Cassette-uitvoer/`. `cassette-transparant.webm` bevat VP9 met alpha; `cassette-zwart.mp4` is een breed afspeelbare versie op zwart. `cassette-video.html` speelt de zwarte versie herhalend af met bediening. Beide video's duren 20,44 seconden bij 25 beelden per seconde. De oorspronkelijke beweging en het watermerk blijven behouden. De vaste uitsnede met zachte rand verwijdert de omgeving buiten de cassette; de recorder die door de behuizing heen zichtbaar is blijft aanwezig. Er is geen gegarandeerd naadloze aansluiting tussen het laatste en eerste beeld.

De bronvideo en afgeleide bestanden blijven buiten de repository. Transparantie is op begin, midden en einde gecontroleerd: buitenste pixels alpha 0, cassettecentrum alpha 255 en tussenwaarden op de zachte rand. De zwarte compositie is als stilstaand beeld visueel gecontroleerd.
