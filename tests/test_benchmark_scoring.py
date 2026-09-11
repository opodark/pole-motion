import importlib.util
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from score_pose_review import score
from pose_benchmark import COMMON


def fixture():
    m={'source_sha256':'test','frames':[{'file':'a.jpg','width':100,'height':100,'frame_index':0}]}
    r={'source_sha256':'test','common_joints':COMMON,'coordinate_system':'resized_image_pixels',
       'frames':m['frames'],'annotations':{'a.jpg':{'points':[[50,50,1]]+[None]*11}}}
    return m,r


def test_missing_prediction_is_not_perfect_score():
    m,r=fixture()
    result=score(m,r,{'mediapipe':[{'file':'a.jpg','points':None}]})['models']['mediapipe']
    assert result['pck']==0 and result['coverage']==0
    assert result['mean_error_over_image_diagonal_detected_only'] is None


def test_common_joint_mapping_and_geometry():
    m,r=fixture()
    points=[[0,0,0] for _ in range(33)]
    points[11]=[50,50,1]
    result=score(m,r,{'mediapipe':[{'file':'a.jpg','points':points}]})['models']['mediapipe']
    assert result['pck']==1
    r['frames']=[{'file':'a.jpg','width':200,'height':100,'frame_index':0}]
    with pytest.raises(ValueError,match='geometry'):
        score(m,r,{'mediapipe':[]})


def test_empty_reference_cannot_produce_accuracy():
    m,r=fixture()
    r['annotations']['a.jpg']['points']=[None]*12
    with pytest.raises(ValueError,match='No visible'):
        score(m,r,{'mediapipe':[]})
