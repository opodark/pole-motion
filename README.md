# Pole Motion

Una base dati condivisa per catalogare pose e movimenti di pole dance,
da usare in percorsi e-learning e giochi basati sul movimento.

Il progetto parte dall'analisi pose di [tiktok_editor](https://github.com/opodark/tiktok_editor).
Il formato **0.1.0 è una proposta di standard**, da sviluppare e validare insieme alle istruttrici.
Non contiene ancora un catalogo tecnico approvato o un sistema di punteggio tecnico.

## Studio locale

La UI per l'analisi video si avvia dalla cartella del progetto:

```powershell
.venv\Scripts\python.exe -m pole_motion.studio
```

Apri http://127.0.0.1:8765 nel browser. Importa un video (massimo 1 GB;
MP4 H.264 consigliato per la compatibilità del player), poi premi **Analizza il video**.
Il player permette di rallentare la riproduzione, visualizzare lo scheletro e
selezionare i fermi sulla timeline. L'analisi gira in locale con MediaPipe;
il primo utilizzo può scaricare il modello. Non sono necessarie API key.

Per la lezione dal vivo premi **Avvia webcam** e consenti la fotocamera nel
browser. **Specchio** ribalta insieme immagine e scheletro; **Schermo intero**
ingrandisce il player per le alunne. **Ferma webcam** spegne la fotocamera.
Il microfono resta spento. I frame live non vengono salvati automaticamente.
La UI invia un fotogramma alla volta al server locale, fino a 10 analisi/s,
e mostra il risultato sullo stesso fotogramma: la latenza effettiva e la
frequenza dipendono dal computer e sono indicate nella barra LIVE.
Gli interruttori **Effetti dal vivo** mostrano palo stimato, aloni sui contatti
confermati per almeno 0,25 secondi e angoli 2D di gomiti e ginocchia. Le prese
riusano `pose.contacts`, il palo `pose.pole_x_from_pose`. Puoi correggere il palo
con il cursore manuale, riferito all'immagine originale prima dello specchio.
Gli angoli sono proiezioni sul piano dell'immagine, non misure articolari 3D.
**Giravolta sperimentale**, disattivata inizialmente, segnala un possibile
attraversamento alternato intorno al palo con contatto: anche un'oscillazione
può attivarlo. Non certifica giri completi e richiede verifica su esempi reali.

**Registra** avvia la cattura; **Ferma registrazione** o **Ferma webcam** la
finalizzano. Scarica i file dai link che appaiono nel pannello: video originale,
video con effetti (opzionale) e misure JSON. Il limite per clip è 5 minuti;
la registrazione usa memoria del browser e i file vanno scaricati prima di
chiudere la pagina. La versione con effetti segue il player e lo specchio;
l'originale rimane privo di sovrapposizioni. Il JSON `pole-motion-live-0.1`
contiene hash dell'originale, timestamp di cattura relativi all'avvio della
registrazione e offset iniziale del video con effetti. La sincronizzazione
è approssimata dal clock del browser, non frame-accurate. Questo sidecar live
non è il catalogo 0.1.0 importabile dal player: per quello analizza il video
originale salvato. La versione con effetti può saltare frame quando la scheda
è in background; tieni lo studio in primo piano durante la registrazione.
Questa modalità non assegna voti e non identifica nomi tecnici dei movimenti.
Su macOS usa MediaPipe `>=0.10,<1.0`, come da correzione del branch macOS.

Puoi anche caricare un JSON prodotto da `cli analyze`: lo studio verifica
l'hash del video originale prima di associarlo. **Esporta analisi JSON**
salva i risultati dal browser. Video importati e risultati delle nuove analisi
sono conservati in `outputs/studio`, escluso da Git. Ricaricando la pagina,
seleziona di nuovo il video originale e carica il JSON per riprendere la revisione.

Questa prima UI gestisce una sessione video e i rilevamenti in bozza: la
correzione manuale dei punti e la validazione del catalogo
non sono ancora integrate nello studio. Il confronto dei tre modelli resta
disponibile separatamente in `outputs/pose-benchmark/review.html`.

## Il nucleo comune

- **Pose**: identità stabile, nome, alias e fotogrammi di riferimento.
- **Registrazioni**: punti articolari nel tempo, palo, contatti stimati, fermi ed eventi.
- **Movimenti**: sequenze temporali di pose con durata di mantenimento.
- **Revisione**: bozza, validato o rifiutato; la validazione registra autore e data.

L'AI produce misure e proposte. L'istruttrice decide quali riferimenti approvare.
E-learning e gioco consumano gli stessi identificatori e riferimenti: il primo aggiungerà
lezioni e progressione, il secondo confronto, ritmo e punteggio.

## Avvio

Python 3.10+; per l'analisi video serve una versione supportata da MediaPipe.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[pose,dev]"
.venv\Scripts\python -m pole_motion.cli validate examples/catalog.json
.venv\Scripts\python -m pole_motion.cli analyze video.mp4 --id lezione-001 --out outputs/lezione-001.json
.venv\Scripts\python -m pole_motion.pose --video video.mp4 --out outputs/debug.mp4
```

Il primo avvio dell'analisi scarica il modello MediaPipe. Il video debug richiede ffmpeg.
Le registrazioni e i modelli sono esclusi da Git; l'esempio incluso è sintetico.
L'export salva un hash del video, senza includere percorsi locali o il video stesso.

Il prototipo webcam (`python -m pole_motion.webcam_demo`) non è collegato a `pyproject.toml`
ed è a parte: apre una finestra live, quindi serve `pip install opencv-python` (non
`opencv-python-headless`, installato dall'extra `pose`, che non supporta la GUI).

```powershell
.venv\Scripts\python -m pytest
```

## Stato tecnico

Il rilevatore estratto produce 33 punti con **x, y e visibilità**, nel piano dell'immagine.
La terza componente non è profondità. I contatti sono ipotesi geometriche,
non misure del peso sostenuto. Il tracking attuale seleziona una persona.
I frame senza rilevamento restano espliciti con `landmarks: null`.

Il rilevatore e il renderer debug sono riutilizzati; l'export JSON e la validazione
del catalogo sono nuovi. La classificazione multimodale di `vision.py` resta un'integrazione
successiva: non viene chiamata durante l'export e non sono necessarie API key.

## Sviluppo

1. Catalogazione con l'istruttrice: nomi, varianti, riferimenti e criteri di revisione.
2. Interfaccia per selezionare pose e correggere annotazioni sul video originale.
3. Confronto fra esecuzioni: normalizzazione, orientamento, tempi e confidenza.
4. E-learning: lezioni, prerequisiti ed esercizi basati sul catalogo.
5. Gioco: sfide, feedback, combo e successivamente webcam in tempo reale.

Dettagli del contratto in [docs/standard.md](docs/standard.md).
Provenienza in [NOTICE.md](NOTICE.md). Licenza MIT per il codice;
eventuali video e cataloghi futuri dovranno dichiarare i propri diritti.
