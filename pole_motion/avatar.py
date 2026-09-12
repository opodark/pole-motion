"""Experimental monocular 3D motion; separate from the catalog contract."""
import hashlib
import json
from pathlib import Path
import numpy as np
from . import pose


def motion_from_frames(frames, source_hash):
    result = []
    previous = -1.0
    has_root = False
    for frame in frames:
        if not np.isfinite(frame.t) or frame.t <= previous:
            raise ValueError("Non-monotonic motion timestamps")
        previous = frame.t
        points = None
        root = None
        if frame.world is not None:
            a = np.array(frame.world, dtype=float, copy=True)
            if a.shape != (33, 4) or not np.isfinite(a).all():
                raise ValueError("Invalid world landmarks")
            a[:, :3] -= (a[23, :3] + a[24, :3]) / 2
            a[:, 3] = np.clip(a[:, 3], 0, 1)
            points = a.tolist()
        if frame.lm is not None:
            image = np.asarray(frame.lm, dtype=float)
            if image.shape == (33, 3) and np.isfinite(image).all():
                hips = image[[23, 24]]
                root = [float(hips[:, 0].mean()), float(hips[:, 1].mean()),
                        float(np.clip(hips[:, 2].min(), 0, 1))]
                has_root = True
        result.append({"t": float(frame.t), "points": points, "root": root})
    return {"schema_version": "pole-motion-avatar-0.1", "source_sha256": source_hash,
            "coordinate_system": "mediapipe_world_xyz_visibility_hip_centered",
            "units": "estimated_meters", "landmark_set": "mediapipe_pose_33",
            "review": "draft", "root_translation": has_root, "frames": result}


def reconstruct(path):
    path = Path(path)
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return motion_from_frames(pose.analyze_video(path, fps_sample=12), digest)
