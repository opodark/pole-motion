# Archivio locale e ottimizzazioni

L'archivio legge automaticamente le analisi gia presenti in outputs/studio.
Raggruppa per hash SHA-256 del video, mostrando analisi 2D e avatar 3D insieme.
I duplicati storici vengono raggruppati, non cancellati. Il nome originale
viene conservato per i nuovi caricamenti; i vecchi file senza nome sono
mostrati come Video salvato con data e dimensione.

Riprendi apre direttamente il video locale via HTTP Range e carica i risultati,
senza selezionare JSON o caricare l'intero filmato nella memoria del browser.
Importando un file locale della stessa dimensione di un video archiviato,
il browser ne verifica l'hash e ripristina i risultati corrispondenti.
Il calcolo hash richiede una lettura del file in memoria (limite 1 GB).

Le analisi completate sopravvivono al riavvio. Le richieste duplicate in corso
condividono il medesimo job. Un nuovo tipo di analisi sul video archiviato riusa
il file server senza nuovo upload. Non si riprendono automaticamente job
interrotti da arresto forzato. Formato e motore sono attualmente fissi; un
futuro cambio di modello/configurazione richiede versionamento della cache.

Il rilevatore converte in immagini soltanto i fotogrammi campionati tramite
OpenCV grab/retrieve. Modello, risoluzione e timestamp restano invariati.
La prima analisi continua a usare MediaPipe CPU. ONNX Runtime nell'ambiente
benchmark espone solo CPU/Azure, non CUDA. nvidia-smi ha negato l'accesso
anche nella sessione elevata; nessuna accelerazione GPU viene dichiarata.

I risultati sono scritti atomicamente. Metadati nome/tempo sono sidecar locali.
Log in outputs/studio/studio.log. Video e analisi restano esclusi da Git.
