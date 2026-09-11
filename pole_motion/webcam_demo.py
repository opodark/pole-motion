"""Prototipo esplorativo: pose in tempo reale dalla webcam del Mac.

Su macOS `cv2.VideoCapture` usa il backend nativo **AVFoundation**: e' gia'
la "API webcam del Mac", non serve altro per iniziare. Riusa la STESSA
logica di `pose.py` gia' validata sui video-tutorial (palo dai keypoint,
contatti mano/piede, fermi, eventi) invece di reinventarla per il live:

- ad ogni fotogramma campionato: presa "live" (leggera, solo per l'HUD) e
  un indicatore FERMO approssimato (media mobile del movimento);
- ogni ~2s: ricalcolo "ufficiale" con `pose.contacts` / `pose.detect_holds`
  / `pose.detect_events`, le stesse funzioni usate da `pole_motion.cli
  analyze` sui file video -- i nuovi fermi/eventi vengono stampati.

Con `--record` salva anche la sessione (video grezzo, senza overlay) e alla
chiusura scrive una "recording" nel formato del contratto 0.1.0 accanto al
video: e' cosi' che si comincia a popolare il dizionario di pose/movimenti,
con lo stesso identico formato prodotto dall'analisi di un video registrato.

Non fa parte del contratto dati 0.1.0 e non e' collegato a `pyproject.toml`
(nessun entry point). Va lanciato a mano.

Permesso Fotocamera (macOS)
----------------------------
La PRIMA esecuzione va fatta da un Terminale/iTerm normale (non da uno
strumento automatizzato): macOS mostra il dialog "vuole accedere alla
fotocamera" solo in una sessione interattiva con interfaccia. Una volta
concesso, resta valido per quel binario Python (visibile poi in
Preferenze di Sistema > Privacy e sicurezza > Fotocamera).

CLI:  python -m pole_motion.webcam_demo [--camera 0] [--record out.mp4] [--id nome]
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import pose
from .catalog import validate
from .extract import build_record
from .pose import GRIP_PARTS, IDX, PART_IT, _SKELETON, ensure_model

STILL = 0.012          # soglia movimento sotto la quale si considera "fermo" (vedi pose.detect_holds)
MIN_HOLD_S = 0.6        # quanto deve restare fermo prima di segnalarlo live


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(camera: int = 0, width: int = 1280, height: int = 720, mirror: bool = True,
        sample_fps: float = 10.0, pole_band: float = 0.09,
        record: Optional[Path] = None, recording_id: Optional[str] = None) -> None:
    import cv2
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks.python.core.base_options import BaseOptions
    from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions, RunningMode

    task = ensure_model()
    opts = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(task)),
        running_mode=RunningMode.VIDEO, num_poses=1,
        min_pose_detection_confidence=0.4, min_tracking_confidence=0.4,
    )

    cap = cv2.VideoCapture(camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    if not cap.isOpened():
        raise RuntimeError(
            "Camera non disponibile. Se e' la prima volta: lancia questo script "
            "da un Terminale normale e concedi il permesso Fotocamera quando "
            "richiesto (Preferenze di Sistema > Privacy e sicurezza > Fotocamera)."
        )
    disp_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or width
    disp_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or height

    record = Path(record) if record else None
    raw_path = writer = None
    record_fps = 20.0
    if record is not None:
        record.parent.mkdir(parents=True, exist_ok=True)
        raw_path = record.with_suffix(".raw.mp4")
        writer = cv2.VideoWriter(str(raw_path), cv2.VideoWriter_fourcc(*"mp4v"),
                                 record_fps, (disp_w, disp_h))
        if not writer.isOpened():
            cap.release()
            raise RuntimeError("cv2.VideoWriter non si apre (codec mp4v mancante?).")

    recording_id = recording_id or f"webcam-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"

    frames: list[pose.PoseFrame] = []
    last_lm = None
    motion_ema = None
    hold_since = None
    last_pose_t = -1.0
    last_batch_t = 0.0
    n_holds_seen = n_events_seen = 0
    pole_x_live = None

    t_start = time.time()
    n_display = 0
    fps_ema = None
    grip_now = None
    fermo = False

    print("Premi 'q' o ESC per uscire." + (f" Registro su {record}" if record else ""))
    try:
        with PoseLandmarker.create_from_options(opts) as lm:
            while True:
                loop_t0 = time.time()
                ok, bgr = cap.read()
                if not ok:
                    print("Nessun fotogramma dalla camera, esco.")
                    break
                if mirror:
                    bgr = cv2.flip(bgr, 1)
                if writer is not None:
                    writer.write(bgr)

                now = time.time() - t_start

                if now - last_pose_t >= 1.0 / max(1.0, sample_fps):
                    last_pose_t = now
                    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                    img = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
                    result = lm.detect_for_video(img, int(now * 1000))
                    pf = pose.PoseFrame(t=now, n_people=len(result.pose_landmarks))
                    if result.pose_landmarks:
                        p = result.pose_landmarks[0]
                        pf.lm = np.array([[k.x, k.y, getattr(k, "visibility", 1.0)] for k in p],
                                         dtype=np.float32)
                    frames.append(pf)

                    grip_now = None
                    if pf.lm is not None:
                        if pole_x_live is None and len(frames) >= 12:
                            pole_x_live = pose.pole_x_from_pose(frames)
                        if last_lm is not None:
                            mv = pose._motion(last_lm, pf.lm)
                            motion_ema = mv if motion_ema is None else motion_ema * 0.7 + mv * 0.3
                        last_lm = pf.lm
                        if pole_x_live is not None:
                            for part, names in GRIP_PARTS.items():
                                xy = pose._part_xy(pf.lm, names)
                                if xy is not None and abs(xy[0] - pole_x_live) < pole_band:
                                    grip_now = part
                                    break
                    else:
                        last_lm = None
                        motion_ema = None

                    if motion_ema is not None and motion_ema < STILL:
                        hold_since = now if hold_since is None else hold_since
                        fermo = (now - hold_since) >= MIN_HOLD_S
                    else:
                        hold_since = None
                        fermo = False

                # ricalcolo "ufficiale" periodico: le stesse funzioni usate su file
                if now - last_batch_t >= 2.0 and len(frames) >= 8:
                    last_batch_t = now
                    px_batch = pose.pole_x_from_pose(frames)
                    if px_batch is not None:
                        pole_x_live = px_batch
                        cts = pose.contacts(frames, px_batch)
                        holds = pose.detect_holds(frames, cts)
                        events = pose.detect_events(frames)
                        for h in holds[n_holds_seen:]:
                            part_it = PART_IT.get(h.focus_part, h.focus_part or "?")
                            print(f"  fermo   {h.t0:5.2f}-{h.t1:5.2f}s  focus={part_it}")
                        for e in events[n_events_seen:]:
                            print(f"  evento  {e.t:5.2f}s  {e.kind:9s} {e.part:12s} {e.value:6.1f}")
                        n_holds_seen, n_events_seen = len(holds), len(events)

                # --- HUD ---
                h, w = bgr.shape[:2]
                if frames and frames[-1].lm is not None:
                    lm0 = frames[-1].lm
                    pts = {name: (lm0[i, 0] * w, lm0[i, 1] * h, lm0[i, 2]) for name, i in IDX.items()}
                    for a, b in _SKELETON:
                        xa, ya, va = pts[a]
                        xb, yb, vb = pts[b]
                        if va > 0.4 and vb > 0.4:
                            cv2.line(bgr, (int(xa), int(ya)), (int(xb), int(yb)),
                                    (60, 220, 60), 2, cv2.LINE_AA)
                    for x, y, v in pts.values():
                        if v > 0.4:
                            cv2.circle(bgr, (int(x), int(y)), 4, (40, 180, 255), -1, cv2.LINE_AA)
                if pole_x_live is not None:
                    px_pix = int(pole_x_live * w)
                    cv2.line(bgr, (px_pix, 0), (px_pix, h), (255, 255, 255), 1, cv2.LINE_AA)

                hud = []
                if grip_now:
                    hud.append(f"PRESA: {PART_IT.get(grip_now, grip_now)}")
                if fermo:
                    hud.append("FERMO")
                y0 = 56
                for line_txt in hud:
                    cv2.putText(bgr, line_txt, (12, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                               (0, 0, 0), 4, cv2.LINE_AA)
                    cv2.putText(bgr, line_txt, (12, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                               (60, 220, 255), 2, cv2.LINE_AA)
                    y0 += 32

                dt = time.time() - loop_t0
                inst_fps = 1.0 / dt if dt > 0 else 0.0
                fps_ema = inst_fps if fps_ema is None else fps_ema * 0.9 + inst_fps * 0.1
                cv2.putText(bgr, f"{fps_ema:.1f} fps", (12, 28),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

                cv2.imshow("pole-motion - webcam (q per uscire)", bgr)
                n_display += 1
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
    finally:
        cap.release()
        if writer is not None:
            writer.release()
        cv2.destroyAllWindows()
        elapsed = time.time() - t_start
        avg = n_display / elapsed if elapsed > 0 else 0.0
        print(f"{n_display} fotogrammi mostrati in {elapsed:.1f}s -> media {avg:.1f} fps "
              f"({len(frames)} campionati per la posa)")

        if record is not None and raw_path is not None:
            import shutil
            import subprocess
            if shutil.which("ffmpeg") and avg > 0:
                # il raw e' stato scritto un frame per iterazione, dichiarato a
                # `record_fps` (valore comodo per il container, non quello vero):
                # qui si ri-etichetta al framerate REALMENTE misurato, altrimenti
                # la durata del video non combacia con quella della sessione
                # (e con i timestamp di frames/contatti/fermi/eventi nel JSON).
                result = subprocess.run(["ffmpeg", "-y", "-r", f"{avg:.3f}", "-i", str(raw_path),
                                         "-r", f"{avg:.3f}", "-c:v", "libx264",
                                         "-pix_fmt", "yuv420p", "-preset", "veryfast",
                                         str(record), "-loglevel", "error"], check=False)
                if result.returncode == 0:
                    raw_path.unlink(missing_ok=True)
                else:
                    print(f"ffmpeg ha fallito (exit {result.returncode}): "
                          f"tengo il video grezzo -> {raw_path}")
                    raw_path.replace(record)
            else:
                print(f"ffmpeg non trovato: video salvato ai {record_fps:.0f} fps nominali "
                      "del writer, mentre i timestamp nel JSON sono in tempo reale -- "
                      "possibile desincronizzazione se la webcam non ha girato esattamente "
                      "a quella frequenza.")
                raw_path.replace(record)

            if not frames:
                print("Nessun fotogramma campionato, registrazione non salvata.")
            else:
                px_final = pose.pole_x_from_pose(frames)
                rec = build_record(recording_id, {"sha256": _hash_file(record)}, elapsed, frames,
                                   px_final, "keypoint (live)", sample_fps)
                document = {"schema_version": "0.1.0", "poses": [], "movements": [], "recordings": [rec]}
                validate(document)
                out_json = record.with_suffix(".json")
                out_json.write_text(
                    json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False),
                    encoding="utf-8")
                print(f"video -> {record}")
                print(f"registrazione (bozza) -> {out_json}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Prototipo pose in tempo reale dalla webcam.")
    ap.add_argument("--camera", type=int, default=0, help="indice del dispositivo (0 = default)")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--no-mirror", dest="mirror", action="store_false")
    ap.add_argument("--sample-fps", type=float, default=10.0,
                    help="frequenza di campionamento pose (indipendente dagli fps mostrati)")
    ap.add_argument("--pole-band", type=float, default=0.09)
    ap.add_argument("--record", type=Path, default=None,
                    help="salva la sessione (video + bozza JSON) a questo percorso .mp4")
    ap.add_argument("--id", dest="recording_id", default=None, help="id della registrazione")
    a = ap.parse_args()
    run(camera=a.camera, width=a.width, height=a.height, mirror=a.mirror,
        sample_fps=a.sample_fps, pole_band=a.pole_band, record=a.record,
        recording_id=a.recording_id)
