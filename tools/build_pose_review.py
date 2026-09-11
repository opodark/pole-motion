"""Build a local review UI and descriptive statistics; no accuracy without labels."""
import itertools
import json
from pathlib import Path

import cv2
import numpy as np

from pose_benchmark import COMMON, INDICES, OUT, dump

MODELS = ['mediapipe', 'rtmw', 'openpose']
EDGES = [(0,1),(0,2),(2,4),(1,3),(3,5),(0,6),(1,7),(6,7),(6,8),(8,10),(7,9),(9,11)]


def main():
    manifest = json.loads((OUT/'manifest.json').read_text())
    data = {m: json.loads((OUT/f'{m}.json').read_text()) for m in MODELS}
    for m, rows in data.items():
        if [r['file'] for r in rows] != [r['file'] for r in manifest['frames']]:
            raise ValueError(f'Frame alignment mismatch for {m}')
    summary = {'frames': len(manifest['frames']), 'accuracy_measured': False,
               'note': 'Confidence thresholds are not calibrated across models. Agreement is not accuracy.',
               'models': {}, 'disagreement': []}
    common = {}
    for m, rows in data.items():
        arrays = [np.asarray(r['points'])[INDICES[m]] if r['points'] is not None else np.zeros((12,3)) for r in rows]
        common[m] = [a.tolist() for a in arrays]
        confidence = np.stack(arrays)[:,:,2]
        summary['models'][m] = {
            'frames_with_person': sum(r['points'] is not None for r in rows),
            'frames_8_of_12_joints_above_0.3': int(((confidence>=.3).sum(axis=1)>=8).sum()),
            'missing_joint_count_at_0.3': int((confidence<.3).sum()),
            'candidate_count_max': max(r['people_count'] for r in rows)}
    for i, row in enumerate(manifest['frames']):
        distances = {}
        for a,b in itertools.combinations(MODELS,2):
            x,y = np.asarray(common[a][i]), np.asarray(common[b][i])
            valid = (x[:,2]>=.3)&(y[:,2]>=.3)
            if valid.sum()>=4:
                distances[f'{a}:{b}'] = float(np.linalg.norm(x[valid,:2]-y[valid,:2],axis=1).mean()/np.hypot(row['width'],row['height']))
        summary['disagreement'].append({'index':i,'t':row['t'],'mean_distance_over_image_diagonal':distances})
    dump(OUT/'summary.json',summary)
    payload = {'manifest':manifest,'common':common,'summary':summary}
    template = (Path(__file__).parent/'pose_review.html').read_text(encoding='utf-8')
    (OUT/'review.html').write_text(template.replace('__PAYLOAD__',json.dumps(payload).replace('</','<\\/')),encoding='utf-8')
    selected = sorted(summary['disagreement'],key=lambda r:max(r['mean_distance_over_image_diagonal'].values(),default=0),reverse=True)[:8]
    (OUT/'comparisons').mkdir(exist_ok=True)
    for i,row in enumerate(manifest['frames']):
        original = cv2.imread(str(OUT/'frames'/row['file']))
        panels=[]
        for m in MODELS:
            panel=original.copy()
            p=np.asarray(common[m][i])
            for a,b in EDGES:
                if min(p[a,2],p[b,2])>=.3:
                    cv2.line(panel,tuple(p[a,:2].astype(int)),tuple(p[b,:2].astype(int)),(40,240,240),3,cv2.LINE_AA)
            for j,q in enumerate(p):
                if q[2]>=.3:
                    cv2.circle(panel,tuple(q[:2].astype(int)),5,(100,255,70) if j%2==0 else (255,160,50),-1,cv2.LINE_AA)
            panel=cv2.resize(panel,(640,360))
            cv2.rectangle(panel,(0,0),(640,34),(15,15,15),-1)
            cv2.putText(panel,f'{m} | {row["t"]:.2f}s',(12,24),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),1,cv2.LINE_AA)
            panels.append(panel)
        cv2.imwrite(str(OUT/'comparisons'/f'compare_{i:03d}.jpg'),np.hstack(panels))
    # A compact contact sheet of greatest disagreements, for visual inspection.
    tiles=[cv2.resize(cv2.imread(str(OUT/'comparisons'/f'compare_{r["index"]:03d}.jpg')),(1440,270)) for r in selected]
    cv2.imwrite(str(OUT/'disagreements.jpg'),np.vstack(tiles))
    print(json.dumps(summary['models'],indent=2))
    print('Review:',OUT/'review.html')


if __name__=='__main__':
    main()
