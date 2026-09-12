"""Convert the inherited pose detector into portable, unreviewed data."""
from pathlib import Path
import hashlib
import math

from . import pose
from .catalog import validate


def build_record(recording_id, source, duration_s, frames, px, method, sample_fps):
    """Assembla il dict 'recording' (contratto 0.1.0) da frame gia' estratti.

    Condiviso fra `extract()` (file video) e i produttori "live" (es. la
    webcam): entrambi passano solo frame/palo gia' calcolati, cosi' la
    logica di contatti/fermi/eventi resta in un punto solo (`pose.py`).
    """
    contacts = pose.contacts(frames, px)
    holds = pose.detect_holds(frames, contacts)
    events = pose.detect_events(frames)
    # Traccia per fotogramma: la stessa che usa `contacts` internamente, cosi'
    # il player web puo' seguire il palo se la camera si sposta invece di
    # disegnare una linea ferma sulla sola stima globale.
    track = pose.pole_track(frames, px).tolist() if px is not None and frames else None
    return {
        "id": recording_id,
        "source": source,
        "duration_s": duration_s,
        "coordinate_system": "image_xy_visibility",
        "landmark_set": "mediapipe_pose_33",
        "producer": {"name": "pole-motion/mediapipe", "sample_fps_requested": sample_fps},
        "pole": {"x": px, "method": method, "track": track},
        "frames": [{"t": f.t, "landmarks": f.lm.tolist() if f.lm is not None else None} for f in frames],
        "contacts": [{"part": c.part, "t0": c.t0, "t1": c.t1} for c in contacts],
        "holds": [{"t0": h.t0, "t1": h.t1} for h in holds],
        "events": [{"kind": e.kind, "t": e.t, "part": e.part, "value": float(e.value)} for e in events],
        "review": {"status": "draft"},
    }


def extract(video, recording_id, fps=8.0):
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("fps must be a positive finite number")
    video = Path(video)
    import cv2
    cap = cv2.VideoCapture(str(video))
    try:
        src_fps = cap.get(cv2.CAP_PROP_FPS)
        count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not cap.isOpened() or src_fps <= 0 or count <= 0:
            raise ValueError("Cannot read video duration")
        duration = count / src_fps
    finally:
        cap.release()
    frames = pose.analyze_video(video, fps_sample=fps)
    px, method = pose.pole_x_auto(video, frames)
    digest = hashlib.sha256()
    with video.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    record = build_record(recording_id, {"sha256": digest.hexdigest()}, duration, frames, px, method, fps)
    document = {"schema_version": "0.1.0", "poses": [], "movements": [], "recordings": [record]}
    return validate(document)
