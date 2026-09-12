# Pole Motion

Una base dati condivisa per catalogare pose e movimenti di pole dance,
da usare in percorsi e-learning e giochi basati sul movimento.

Il progetto parte dall'analisi pose di [tiktok_editor](https://github.com/opodark/tiktok_editor).
Il formato **0.1.0 è una proposta di standard**, da sviluppare e validare insieme alle istruttrici.
Non contiene ancora un catalogo tecnico approvato, un sistema di punteggio o una UI.

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
