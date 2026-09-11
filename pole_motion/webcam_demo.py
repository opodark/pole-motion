"""Prototipo esplorativo: pose in tempo reale dalla webcam del Mac.

Su macOS `cv2.VideoCapture` usa il backend nativo **AVFoundation**: e' gia'
la "API webcam del Mac", non serve altro per iniziare. Questo script serve
solo a validare la fattibilita' del passo 5 della roadmap (gioco con webcam
in tempo reale) misurando FPS reali di MediaPipe Pose Landmarker in diretta.

Non fa parte del contratto dati 0.1.0 e non e' collegato a `pyproject.toml`
(nessun entry point). Va lanciato a mano.

Permesso Fotocamera (macOS)
----------------------------
La PRIMA esecuzione va fatta da un Terminale/iTerm normale (non da uno
strumento automatizzato): macOS mostra il dialog "vuole accedere alla
fotocamera" solo in una sessione interattiva con interfaccia. Una volta
concesso, resta valido per quel binario Python (visibile poi in
Preferenze di Sistema > Privacy e sicurezza > Fotocamera).

CLI:  python -m pole_motion.webcam_demo [--camera 0] [--width 1280] [--height 720]
"""
from __future__ import annotations

import time

from .pose import IDX, _SKELETON, ensure_model


def run(camera: int = 0, width: int = 1280, height: int = 720, mirror: bool = True) -> None:
    import cv2
    import mediapipe as mp
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

    t_start = time.time()
    n_frames = 0
    fps_ema = None

    print("Premi 'q' o ESC nella finestra per uscire.")
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

                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                ts_ms = int((time.time() - t_start) * 1000)
                result = lm.detect_for_video(img, ts_ms)

                h, w = bgr.shape[:2]
                if result.pose_landmarks:
                    lm0 = result.pose_landmarks[0]
                    pts = {name: (lm0[i].x * w, lm0[i].y * h, lm0[i].visibility)
                          for name, i in IDX.items()}
                    for a, b in _SKELETON:
                        xa, ya, va = pts[a]
                        xb, yb, vb = pts[b]
                        if va > 0.4 and vb > 0.4:
                            cv2.line(bgr, (int(xa), int(ya)), (int(xb), int(yb)),
                                    (60, 220, 60), 2, cv2.LINE_AA)
                    for x, y, v in pts.values():
                        if v > 0.4:
                            cv2.circle(bgr, (int(x), int(y)), 4, (40, 180, 255), -1, cv2.LINE_AA)

                dt = time.time() - loop_t0
                inst_fps = 1.0 / dt if dt > 0 else 0.0
                fps_ema = inst_fps if fps_ema is None else fps_ema * 0.9 + inst_fps * 0.1
                cv2.putText(bgr, f"{fps_ema:.1f} fps", (12, 28),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)

                cv2.imshow("pole-motion - webcam (q per uscire)", bgr)
                n_frames += 1
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        elapsed = time.time() - t_start
        avg = n_frames / elapsed if elapsed > 0 else 0.0
        print(f"{n_frames} fotogrammi in {elapsed:.1f}s -> media {avg:.1f} fps")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Prototipo pose in tempo reale dalla webcam.")
    ap.add_argument("--camera", type=int, default=0, help="indice del dispositivo (0 = default)")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--no-mirror", dest="mirror", action="store_false")
    run(**vars(ap.parse_args()))
