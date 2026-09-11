"""Score manually reviewed common joints. Missing predictions count as PCK failures."""
import argparse
import json
import math
from pathlib import Path

from pose_benchmark import COMMON, INDICES, OUT, dump


def score(manifest, reference, predictions, threshold=.3, tolerance=.02):
    if reference.get('source_sha256') != manifest['source_sha256']:
        raise ValueError('Reference belongs to a different source')
    if reference.get('common_joints') != COMMON:
        raise ValueError('Joint ordering differs')
    if reference.get('coordinate_system') != 'resized_image_pixels':
        raise ValueError('Reference must use resized image pixels')
    expected = {r['file']: r for r in manifest['frames']}
    ref_frames = {r['file']:r for r in reference.get('frames',[])}
    if set(ref_frames) != set(expected) or any(
        (ref_frames[k]['width'],ref_frames[k]['height'],ref_frames[k]['frame_index']) !=
        (v['width'],v['height'],v['frame_index']) for k,v in expected.items()):
        raise ValueError('Reference frame geometry differs')
    results={}
    for model, rows in predictions.items():
        by_file={r['file']:r for r in rows}
        total=detected=correct=0
        errors=[]
        for filename, annotation in reference['annotations'].items():
            if filename not in expected:
                raise ValueError('Unknown frame')
            points=annotation['points']
            if len(points)!=12:
                raise ValueError('Expected twelve common joints')
            frame=expected[filename]
            diagonal=math.hypot(frame['width'],frame['height'])
            prediction=by_file.get(filename,{}).get('points')
            for j,target in enumerate(points):
                if target is None or target == [None,None,0]:
                    continue
                if len(target)!=3 or target[2]!=1 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in target):
                    raise ValueError('Invalid reference point')
                total+=1
                if prediction is None:
                    continue
                point=prediction[INDICES[model][j]]
                if len(point)!=3 or not all(math.isfinite(v) for v in point) or point[2]<threshold:
                    continue
                detected+=1
                error=math.hypot(point[0]-target[0],point[1]-target[1])/diagonal
                errors.append(error)
                correct+=int(error<=tolerance)
        if total==0:
            raise ValueError('No visible reference points have been annotated')
        results[model]={'annotated_visible_joints':total,'predicted_joints':detected,
            'coverage':detected/total,'pck':correct/total,
            'mean_error_over_image_diagonal_detected_only':sum(errors)/len(errors) if errors else None}
    return {'reference_reviewer':reference.get('reviewer',''),
            'pck_tolerance_image_diagonal':tolerance,'prediction_confidence_threshold':threshold,
            'note':'PCK includes missing predictions as failures. Not an assessment of movement technique.',
            'models':results}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('reference',type=Path)
    a=p.parse_args()
    manifest=json.loads((OUT/'manifest.json').read_text())
    reference=json.loads(a.reference.read_text(encoding='utf-8'))
    predictions={m:json.loads((OUT/f'{m}.json').read_text()) for m in INDICES}
    result=score(manifest,reference,predictions)
    dump(OUT/'accuracy-reviewed.json',result)
    print(json.dumps(result,indent=2))
