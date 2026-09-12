import hashlib
import sys
from types import SimpleNamespace

import numpy as np

from pole_motion import extract, pose
from pole_motion.catalog import validate


def test_export_preserves_missing_frames_and_marks_draft(tmp_path, monkeypatch):
    video = tmp_path / "private-file.mp4"
    video.write_bytes(b"synthetic video stand-in")
    class Capture:
        def isOpened(self):
            return True
        def get(self, key):
            return {1: 30, 2: 60}[key]
        def release(self):
            pass
    monkeypatch.setitem(sys.modules, "cv2", SimpleNamespace(
        VideoCapture=lambda _: Capture(), CAP_PROP_FPS=1, CAP_PROP_FRAME_COUNT=2))
    frames = [pose.PoseFrame(0, np.array([[0.5, 0.5, 1.0]] * 33)), pose.PoseFrame(0.125)]
    monkeypatch.setattr(pose, "analyze_video", lambda *a, **kw: frames)
    monkeypatch.setattr(pose, "pole_x_auto", lambda *a: (0.5, "synthetic"))
    monkeypatch.setattr(pose, "contacts", lambda *a: [pose.Contact("left_hand", 0, 0.125)])
    monkeypatch.setattr(pose, "detect_holds", lambda *a: [])
    monkeypatch.setattr(pose, "detect_events", lambda *a: [pose.PoseEvent("invert", 0)])
    result = extract.extract(video, "example")
    validate(result)
    r = result["recordings"][0]
    assert r["frames"][1]["landmarks"] is None
    assert r["review"] == {"status": "draft"}
    assert r["duration_s"] == 2
    assert r["source"] == {"sha256": hashlib.sha256(video.read_bytes()).hexdigest()}
    assert "private-file" not in str(result)
    assert result["poses"] == []
    assert r["pole"]["track"] == [0.5, 0.5]                  # una x per frame, palo fermo qui
