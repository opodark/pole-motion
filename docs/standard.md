# Contratto dati 0.1.0

`pole_motion/catalog.schema.json` descrive struttura e tipi in JSON Schema 2020-12.
`pole_motion.catalog.validate` verifica anche relazioni, duplicati e intervalli temporali.
Versioni sconosciute sono rifiutate: le modifiche al contratto richiederanno una migrazione esplicita.

Gli ID sono stringhe stabili, separate dai nomi visualizzati e dagli alias.
Una posa descrive una figura; una registrazione contiene osservazioni; un movimento
collega pose tramite una timeline relativa. I tempi delle registrazioni sono secondi
dall'inizio del video originale. `at_s` e `hold_s` sono secondi della sequenza.

## Coordinate e osservazioni

`image_xy_visibility`: x diviso larghezza, y diviso altezza, visibilità tra 0 e 1.
Origine in alto a sinistra; x cresce verso destra, y verso il basso.
Coordinate fuori dall'immagine sono ammesse. Gli indici seguono MediaPipe Pose 33;
sinistra/destra sono anatomiche, non quelle dello spettatore. Non si applica mirroring automatico.
Nessuna coordinata world/3D è disponibile in questa versione.

`pole.x` è una coordinata normalizzata o null se ignota. `method` conserva il metodo
del rilevatore. `sample_fps_requested` indica la frequenza richiesta, non garantisce
un campionamento esatto: usare sempre i timestamp effettivi dei frame.

Contatti e fermi sono intervalli in secondi. Gli eventi mantengono i tipi originali
del detector (`invert`, `arm_ext`, `leg_ext`, `straddle`, `line`); `value` conserva
la metrica del detector e non è un punteggio di qualità. Non confrontare valori di tipi diversi.

## Revisione

Le estrazioni nascono in `draft`. Una posa `validated` deve avere un riferimento,
un `reviewer` e una data `reviewed_at`. Un movimento validato può usare solo pose validate.
Il validatore controlla i metadati, non autentica chi li ha compilati:
la futura UI dovrà gestire identità e storico delle revisioni.

La registrazione può restare draft mentre l'istruttrice approva solo alcune pose:
la revisione di una posa non approva automaticamente l'intero video o tutti i keypoint.
Il catalogo non contiene ancora regole di scoring, livelli tecnici o biomeccanica normativa.
I futuri consumer dovranno filtrare i riferimenti validati e trattare il tracking mancante
come dato non valutabile.
