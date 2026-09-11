"""Reproducible image benchmark; agreement is NOT anatomical accuracy.

Run from the repository root using the isolated benchmark environment.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs' / 'pose-benchmark'
COMMON = ['left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
          'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
          'left_knee', 'right_knee', 'left_ankle', 'right_ankle']
INDICES = {'mediapipe': [11,12,13,14,15,16,23,24,25,26,27,28],
           'rtmw': [5,6,7,8,9,10,11,12,13,14,15,16],
           'openpose': [5,2,6,3,7,4,12,9,13,10,14,11]}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def prepare(video, count):
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError('Cannot open video')
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not fps or total < count or count < 1:
        raise ValueError('Invalid duration or sample count')
    # Equal bins, sampled at their center. No selection based on any model.
    selected = set(((np.arange(count) + .5) * total / count).astype(int).tolist())
    (OUT / 'frames').mkdir(parents=True, exist_ok=True)
    rows = []
    try:
        for i in range(total):
            ok, frame = cap.read()
            if not ok:
                break
            if i not in selected:
                continue
            h, w = frame.shape[:2]
            scale = min(1, 1280/w)
            frame = cv2.resize(frame, (round(w*scale), round(h*scale)))
            name = f'frame_{len(rows):03d}.jpg'
            if not cv2.imwrite(str(OUT / 'frames' / name), frame, [cv2.IMWRITE_JPEG_QUALITY, 95]):
                raise RuntimeError('Image write failed')
            rows.append({'file': name, 'frame_index': i, 't': i/fps,
                         'width': frame.shape[1], 'height': frame.shape[0]})
    finally:
        cap.release()
    if len(rows) != count:
        raise ValueError(f'Decoded only {len(rows)} of {count} requested frames')
    digest = hashlib.sha256()
    with Path(video).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            digest.update(chunk)
    dump(OUT / 'manifest.json', {'source_sha256': digest.hexdigest(), 'fps': fps,
        'selection': 'center of equal temporal bins; independent of pose predictions',
        'common_joints': COMMON, 'frames': rows})
    print(f'Prepared {len(rows)} frames', flush=True)


def run(model):
    rows = json.loads((OUT / 'manifest.json').read_text())['frames']
    result = []
    if model == 'mediapipe':
        import mediapipe as mp
        from mediapipe.tasks.python.core.base_options import BaseOptions
        from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions, RunningMode
        estimator = PoseLandmarker.create_from_options(PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(ROOT/'pole_motion/assets_data/models/pose_landmarker_full.task')),
            running_mode=RunningMode.IMAGE, num_poses=1, min_pose_detection_confidence=.4))
    else:
        from rtmlib import Wholebody
        tools = ROOT / 'data/benchmark/tools'
        det = next((tools/'yolox').rglob('*.onnx'))
        pose = next((tools/'rtmw').rglob('*.onnx'))
        estimator = Wholebody(det=str(det), det_input_size=(640,640), pose=str(pose),
            pose_input_size=(288,384), backend='onnxruntime', device='cpu', to_openpose=False)
    try:
        for i, row in enumerate(rows):
            image = cv2.imread(str(OUT/'frames'/row['file']))
            start = time.perf_counter()
            people = []
            if model == 'mediapipe':
                detection = estimator.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                    data=np.ascontiguousarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))))
                for points in detection.pose_landmarks:
                    people.append([[p.x*row['width'],p.y*row['height'],p.visibility] for p in points])
            else:
                keypoints, scores = estimator(image)
                people = [np.column_stack([k,s]).tolist() for k,s in zip(keypoints,scores)]
            elapsed = time.perf_counter() - start
            # One performer expected. Highest mean common-body confidence; retain count.
            selected = max(people, key=lambda p: np.mean(np.asarray(p)[INDICES[model],2])) if people else None
            result.append({'file': row['file'], 'people_count': len(people), 'points': selected, 'inference_s': elapsed})
            if (i+1)%10 == 0:
                dump(OUT/f'{model}.json', result)
                print(f'{model}: {i+1}/{len(rows)}', flush=True)
    finally:
        if model == 'mediapipe':
            estimator.close()
    dump(OUT/f'{model}.json', result)


def collect_openpose():
    rows = json.loads((OUT/'manifest.json').read_text())['frames']
    result = []
    for r in rows:
        file = OUT/'openpose-raw'/f"{Path(r['file']).stem}_keypoints.json"
        if not file.exists():
            raise ValueError(f'Missing OpenPose result: {file.name}')
        raw = json.loads(file.read_text())
        people = [np.asarray(p['pose_keypoints_2d']).reshape(-1,3) for p in raw['people']]
        selected = max(people,key=lambda p: p[INDICES['openpose'],2].mean()).tolist() if people else None
        result.append({'file':r['file'],'people_count':len(people),'points':selected})
    dump(OUT/'openpose.json',result)


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['prepare','mediapipe','rtmw','collect-openpose'])
    p.add_argument('--video',type=Path)
    p.add_argument('--count',type=int,default=120)
    a=p.parse_args()
    if a.action=='prepare': prepare(a.video,a.count)
    elif a.action=='collect-openpose': collect_openpose()
    else: run(a.action)
