# Valutazione Pole-Arina — 11 settembre 2026

**Esito: buona base per un esperimento di riconoscimento; non ancora un componente pronto per il prodotto.**
Usare prima i dati per un confronto controllato su poche figure. Non assimilare riconoscimento della figura,
accuratezza articolare e valutazione della tecnica: richiedono verifiche distinte.

## Evidenze acquisite

- Codice ufficiale esaminato al commit `f8ea347c9b58ab6b72f7b67f8fc63e2976cd5664`.
- Indice Drive pubblico accessibile: `annotations.csv`, `skeleton.tar`, `optical_flow.tar`.
- CSV scaricato e letto: 3.039 intervalli, 836 identificativi di clip.
- Archivio scheletri dichiarato nell'indice: 616.331.264 byte. Scaricati solo i primi 8 MiB.
- Letti 34 NPZ completi dal campione parziale, tutti della classe con prefisso `g`.
- In questi NPZ: coordinate finite, array `keypoints` con forma `(T, 75, 3)`.
- Campione iniziale: 298 frame; presenti anche metadati e connessioni dello scheletro.
- Nessun training, checkpoint eseguito o misura di accuratezza riprodotta in questa valutazione.

Le verifiche sono ripetibili con `data/research/audit_sample.py`; il risultato è in
`data/research/audit.json`. I file di ricerca rimangono locali e ignorati da Git.
I 34 file non costituiscono un campione rappresentativo di tutte le classi.

## Copertura e limiti del dataset

La pubblicazione descrive sei figure: Layout, Pin-Up, Wrist Seat, Straddle Invert,
Gemini e Inverted Crucifix, registrate da 58 partecipanti. Fornisce etichette per
clip e fasi temporali. Non distribuisce il video RGB originale; lo scoring tecnico
è trattato separatamente tramite regole geometriche. Non è un catalogo completo di pole.
[Progetto](https://di-marin.github.io/pole-arina/) e
[articolo](https://di-marin.github.io/pole-arina/static/pdfs/pole-arina-paper.pdf).

Il conteggio locale dei prefissi nel CSV è L=191, P=170, W=135, S=150, I=101, G=89.
Questi sono conteggi di clip, non di esecuzioni riuscite né di persone.
Gli stati sono `floor`, `on_pole` e sei etichette `*_pose`.
Il campo `experience_level` è presente; il CSV non contiene un identificativo partecipante.

## Qualità delle annotazioni

L'audit usa estremi inclusivi, coerentemente con il loader del codice ufficiale.

- Due intervalli con fine precedente all'inizio: `l114.MOV` 99–98 e `l80.MOV` 202–201.
  Il loader ufficiale scarta questi intervalli.
- Quattro sovrapposizioni e dodici discontinuità fra gli intervalli, includendo eventuali
  frame iniziali non coperti. Le discontinuità non sono automaticamente errori.
- Somma grezza delle lunghezze: 212.601 frame; non è un conteggio deduplicato.
  Non equipararlo ai 212.574 frame dichiarati nell'articolo senza riconciliare le annotazioni.
- Nel campione `g10`, lo scheletro ha 298 frame mentre l'ultima etichetta termina al frame 290:
  i frame residui devono restare non etichettati, senza assegnare automaticamente una posa.

Conservare gli originali; produrre un rapporto delle righe escluse o corrette.
Non colmare i vuoti delle etichette propagando la figura vicina.

## Compatibilità con pole-motion

| Aspetto | Evidenza | Intervento |
|---|---|---|
| Punti | Il loader richiede 75 punti. Le connessioni corporee nel campione corrispondono ai primi 33 MediaPipe. | Verificare formalmente ordine e semantica dei punti extra; partire da un modello nuovo sui 33 punti comuni. |
| Coordinate | Nel primo campione x arriva a circa 1.033 e y a 1.386; non sono le nostre coordinate 0–1. Sono ammessi anche punti fuori immagine. | Recuperare risoluzioni/calibrazione o adottare normalizzazione relativa al corpo per entrambe le sorgenti. Non dividere per il massimo osservato. |
| Tempo | Gli NPZ campionati non espongono timestamp/FPS nei campi letti. Il nostro export usa timestamp effettivi. | Verificare il tempo della variante scheletro; non trasferire automaticamente la frequenza descritta per l'optical flow. |
| Confidenza | Terzo canale 0–1; il loader a quattro canali seleziona x, y e quarto canale. | Preservare confidenza e dati mancanti; non interpretare il terzo canale del campione come profondità. |
| Riferimento al palo | Nessun campo palo nel NPZ campionato. | Mantenere il nostro rilevatore separato e annotare manualmente i riferimenti quando necessari. |
| Generalizzazione | Lo split nel codice è stratificato per clip/prefisso, non per persona. | Richiedere una mappa anonima dei partecipanti; in sua assenza testare su nostre persone/sessioni mai viste. |
| Esecuzione | Gli script skeleton impongono CUDA; ambiente proposto Python 3.11. | Ambiente separato dal nostro Python 3.14, o adattamento CPU prima di eseguire. |
| Tempo reale | Backbone bidirezionale. | Prima analisi di clip registrate; per webcam servono finestre con latenza dichiarata o un modello causale. |

Il formato e gli script sono documentati nel
[repository ufficiale](https://github.com/di-marin/pole-arina-code).
L'adattamento a 33 punti non rende utilizzabili senza modifiche i pesi di un modello a 75 punti.

## Disponibilità, codice e licenza

Il repository contiene quattro script di training/evaluation e supporta il caricamento di checkpoint,
ma nel checkout non sono presenti pesi né il motore di feedback geometrico descritto nell'articolo.
Nel livello principale del Drive visitato non compaiono checkpoint o split, sebbene il README menzioni
uno split condiviso. Non è stata verificata la presenza di altri file nell'intero archivio.

Non ho trovato un file LICENSE nel repository né una licenza esplicita nell'indice del dataset o nella
pagina del progetto. La disponibilità pubblica non documenta da sola i permessi di redistribuzione,
modifica e uso commerciale. Chiarire con gli autori prima di incorporare codice, dati o pesi nel prodotto
o redistribuirli. Non è stato inviato alcun messaggio agli autori.

## Esperimento proposto

1. Confermare licenze, ordine dei punti, FPS, risoluzioni, identità anonime e disponibilità dei pesi.
2. Scaricare la variante MediaPipe completa; controllare la corrispondenza clip/annotazioni e le maschere.
3. Preparare un'interfaccia comune a 33 punti con normalizzazione e timestamp espliciti.
4. Confrontare un classificatore semplice con un modello temporale. Trattare `floor`, `on_pole`,
   figura sconosciuta e dato non valutabile come casi distinti.
5. Annotare un piccolo test nostro con l'istruttrice, includendo entrata, figura e uscita.
   Il video già analizzato può diventare materiale di test solo dopo etichettatura umana e controllo
   della presenza delle classi; i fermi automatici non sono etichette vere.
6. Misurare F1 per figura, confusione fra figure, falsi riconoscimenti nelle transizioni e copertura.
   Per i keypoint usare annotazioni corrette; per il feedback confrontare i giudizi dell'istruttrice.

I sensori possono fornire una sorgente di riferimento più precisa per il nostro dataset futuro.
Questo materiale pubblico è particolarmente utile per studiare il riconoscimento temporale; non offre
di per sé traiettorie 3D misurate o una verità di riferimento per valutare la tecnica.

## Fonti e artefatti locali

- [Pagina degli autori](https://di-marin.github.io/pole-arina/)
- [Dataset ufficiale Drive](https://drive.google.com/drive/folders/19Vhthsz0lhAQE3a4GubbJbb32AXvaoZk)
- [Codice](https://github.com/di-marin/pole-arina-code)
- `data/research/annotations.csv`: copia esaminata.
- `data/research/sample.npz`: primo file completo letto dal campione.
- `data/research/audit.json`: risultati quantitativi locali.
- `data/research/pole-arina-paper.pdf`: articolo consultato.
