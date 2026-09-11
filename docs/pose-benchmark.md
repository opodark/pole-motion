# Confronto pose sul video dell'istruttrice

Eseguito il 11 settembre 2026 su 120 immagini campionate uniformemente da
`Video Project 12.mp4`. Manifest, hash del video, tempi e coordinate sono in
`outputs/pose-benchmark/`, escluso da Git insieme alle immagini e ai modelli.

| Modello | Immagini con persona | Almeno 8/12 articolazioni con confidenza >= 0.3 |
| --- | ---: | ---: |
| MediaPipe Pose Full | 117/120 | 114/120 |
| RTMW WholeBody | 120/120 | 120/120 |
| OpenPose BODY_25 | 119/120 | 94/120 |

Queste sono misure di copertura, non di accuratezza. Le confidenze dei tre
modelli non sono calibrate fra loro. Si confrontano 12 articolazioni corporee
comuni, in pixel sull'immagine ridimensionata a 1280x720. MediaPipe opera in
modalita IMAGE; il campionamento sparso non misura stabilita temporale.
L'ispezione della tavola dei maggiori disaccordi mostra discrepanze anche
nelle inversioni e negli arti sovrapposti. Nessun vincitore di precisione e
stato stabilito e nessun addestramento e stato ancora eseguito.

## Modelli e ambiente

- Python 3.14.6; ambiente separato `.venv-benchmark`.
- MediaPipe 1.0.1, RTMLib 0.0.16, ONNX Runtime 1.30.
- RTMW: modello MMPose `rtmw-dw-x-l_simcc-cocktail14_270e-384x288_20231122`,
  eseguito tramite RTMLib/ONNX con detector YOLOX HumanArt. Non e una
  installazione completa di MMPose e non e un modello addestrato sulla pole.
- [Modelli ufficiali MMPose](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose).
- [RTMLib](https://github.com/Tau-J/rtmlib).
- [OpenPose 1.7.0 ufficiale](https://github.com/CMU-Perceptual-Computing-Lab/openpose/releases/tag/v1.7.0),
  distribuzione Windows CPU, BODY_25, risoluzione rete -1x368.
  Il binario GPU ha fallito sulla RTX 5060 con errore CUDA 209; il confronto
  usa soltanto risultati CPU. Tre processi disgiunti da 40 immagini,
  OPENBLAS_CORETYPE=Haswell, OPENBLAS_NUM_THREADS=4, OMP_NUM_THREADS=4.
- Il server originale dei pesi BODY_25 non era raggiungibile. Pesi ottenuti
  dal [mirror con revisione fissata](https://huggingface.co/gaijingeek/openpose-models/blob/7b606a341a4dcf057c98ebcb5c17b53b1d7c7cc9/pose/body_25/pose_iter_584000.caffemodel).
  Non e stata verificata l'identita binaria rispetto al server originale.
  OpenPose richiede una verifica della licenza prima dell'uso nel prodotto.

## Revisione e misura successiva

Aprire `outputs/pose-benchmark/review.html` con la cartella `frames` accanto.
La pagina affianca originale e tre modelli, permette annotazioni manuali
delle 12 articolazioni e l'esportazione del riferimento JSON. Le annotazioni
partono vuote, senza assumere corretta la previsione di un modello.

`comparisons/` contiene 120 confronti; `disagreements.jpg` raccoglie gli otto
con maggiore divergenza fra previsioni. Questa selezione serve alla diagnosi,
non e un campione imparziale per stimare la precisione.

Dopo la revisione da parte dell'istruttrice:

```powershell
.venv-benchmark/Scripts/python.exe tools/score_pose_review.py riferimento.json
```

Lo score usa PCK con tolleranza del 2% della diagonale dell'immagine,
conta le previsioni mancanti come errori ed esclude punti non annotati o
non visibili. Non valuta correttezza tecnica o sicurezza del movimento.
Prima del fine-tuning servono riferimenti corretti, piu persone e sessioni,
e una suddivisione train/test per persona. Eventuali sensori vanno
sincronizzati e calibrati con le telecamere.

## Riproduzione degli artefatti

```powershell
.venv-benchmark/Scripts/python.exe tools/pose_benchmark.py collect-openpose
.venv-benchmark/Scripts/python.exe tools/build_pose_review.py
```

Prerequisiti: manifest, immagini e risultati dei tre motori gia presenti.
La suite comprende controlli su corrispondenza delle articolazioni,
geometria del riferimento e penalizzazione delle previsioni mancanti.
