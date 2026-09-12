#!/bin/bash
cd "$(dirname "$0")"
if [ ! -x ".venv/bin/python" ]; then
  echo "Ambiente Python non trovato. Segui le istruzioni di installazione nel README."
  read -p "Premi invio per uscire..."
  exit 1
fi
echo "Apri http://127.0.0.1:8765 nel browser."
echo "Per fermare lo studio premi Ctrl+C in questa finestra."
.venv/bin/python -m pole_motion.studio
