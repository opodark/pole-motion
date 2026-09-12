@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente Python non trovato. Segui le istruzioni di installazione nel README.
  pause
  exit /b 1
)
echo Apri http://127.0.0.1:8765 nel browser.
echo Per fermare lo studio premi Ctrl+C in questa finestra.
".venv\Scripts\python.exe" -m pole_motion.studio
pause
