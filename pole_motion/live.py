"""Stateless image inference for the local webcam; no frames are persisted."""
import threading
import time


class LivePose:
    def __init__(self):
        self.lock = threading.Lock()
        self.model = None
        self.sessions = {}

    def detect(self, encoded, session=None, manual_pole=None):
        import cv2
        import mediapipe as mp
        import numpy as np
        from mediapipe.tasks.python.core.base_options import BaseOptions
        from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions, RunningMode
        from .pose import ensure_model

        bgr = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError('Fotogramma non leggibile')
        if max(bgr.shape[:2]) > 1280:
            raise ValueError('Fotogramma troppo grande (massimo 1280 px)')
        # Reject concurrent clients instead of building a stale inference queue.
        if not self.lock.acquire(blocking=False):
            raise BlockingIOError('Motore webcam occupato')
        try:
            if self.model is None:
                self.model = PoseLandmarker.create_from_options(PoseLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=str(ensure_model())),
                    running_mode=RunningMode.IMAGE, num_poses=1,
                    min_pose_detection_confidence=.4))
            started = time.perf_counter()
            rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
            result = self.model.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
            points = [[p.x, p.y, p.visibility] for p in result.pose_landmarks[0]] if result.pose_landmarks else None
            response = {'landmarks': points, 'inference_ms': round((time.perf_counter()-started)*1000, 1)}
            if session:
                from .live_metrics import LiveMetrics
                if session not in self.sessions:
                    if len(self.sessions) >= 8:
                        self.sessions.pop(next(iter(self.sessions)))
                    self.sessions[session] = LiveMetrics()
                response['metrics'] = self.sessions[session].update(points, time.monotonic(), bgr.shape[1], bgr.shape[0], manual_pole)
            return response
        finally:
            self.lock.release()

    def close(self):
        with self.lock:
            if self.model is not None:
                self.model.close()
                self.model = None
