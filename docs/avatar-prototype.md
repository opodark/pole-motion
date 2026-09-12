# Avatar 3D sperimentale

Riavviare lo Studio e ricaricare la pagina. Scegliere un video guida, quindi
premere **Ricostruisci avatar 3D**. In assenza di guida si usa il video
importato nel player principale. Per la webcam: registrare, scaricare il
video originale e caricarlo nel player. Non e ancora una ricostruzione live.

Il manichino articolato segue play, pausa, seek e velocita del video sorgente.
Trascinare per ruotare oppure scegliere fronte/lato/retro. Esportazione JSON
separata dal contratto catalogo 0.1.0, con hash del video e timestamp.

Si usano i veri output stimati pose_world_landmarks di MediaPipe, non la
visibilita dei landmark 2D come profondita. Riferimento:
https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/PoseLandmarkerResult

Coordinate xyz in metri stimati, origine al bacino, 33 punti e visibilita.
Il visualizzatore proietta in prospettiva segmenti volumetrici e testa;
non e ancora un personaggio con mesh e rig esportabile in glTF/BVH.
Interpolazione solo fra campioni validi distanti al massimo 0.25 secondi;
nessun riempimento delle rilevazioni mancanti. Punti sotto visibilita 0.5
nascosti. Non si ricostruiscono traslazione globale, geometria del palo,
contatti vincolati, rotazione assiale degli arti o proporzioni costanti.
Le inversioni e le occlusioni richiedono revisione umana.

Verifica locale: 12 campioni nei primi 3 secondi di Video Project 12.mp4,
12 con output 3D; questo prova l'estrazione, non la precisione anatomica.
Test automatici su profondita, origine, input immutati, timestamp, vuoti,
interpolazione e route HTTP. Controllo visivo interattivo da completare:
il browser di automazione non era disponibile nella sessione.
