import numpy as np
from pole_motion.live_metrics import LiveMetrics


def points():
    p=np.zeros((33,3))
    p[:,2]=1
    p[:,:2]=[.5,.5]
    return p


def test_angles_use_image_aspect_ratio():
    p=points();p[11,:2]=[.4,.4];p[13,:2]=[.5,.5];p[15,:2]=[.6,.4]
    result=LiveMetrics().update(p,0,200,100,.5)
    assert result['angles'][0]['degrees']==127


def test_contacts_need_time_and_disappear_when_missing():
    tracker=LiveMetrics();p=points()
    assert not tracker.update(p,0,640,360,.5)['contacts']
    assert not tracker.update(p,.1,640,360,.5)['contacts']
    assert tracker.update(p,.3,640,360,.5)['contacts']
    assert not tracker.update(None,.4,640,360,.5)['contacts']
    assert not tracker.update(p,2,640,360,.5)['contacts']


def test_occluded_angles_and_no_turn_without_contact():
    tracker=LiveMetrics();p=points();p[13,2]=0
    for i,x in enumerate([.2,.8,.2]):
        p[[23,24],0]=x
        result=tracker.update(p,i*.5,640,360,.95)
        assert not result['turn_candidate']
        assert not any(a['joint']==13 for a in result['angles'])


def test_manual_pole_overrides_estimate():
    result=LiveMetrics().update(points(),0,640,360,.75)
    assert result['pole_x']==.75
    assert result['pole_method']=='manual'


def full_body():
    p=points()
    p[0,:2]=[.5,.15]
    p[11,:2]=[.4,.3];p[12,:2]=[.6,.3]
    p[27:33,:2]=[.5,.85]
    return p


def test_photo_needs_sustained_hold_and_resets_on_missing_or_motion():
    tracker=LiveMetrics();p=full_body()
    assert not tracker.update(p,0,640,360,.5)['photo']['ready']
    tracker.update(p,.5,640,360,.5)
    assert tracker.update(p,1.01,640,360,.5)['photo']['ready']
    assert not tracker.update(None,1.1,640,360,.5)['photo']['ready']
    assert not tracker.update(p,1.2,640,360,.5)['photo']['held']
    tracker.update(p,1.7,640,360,.5)
    p[15,0]+=.1
    assert not tracker.update(p,2.21,640,360,.5)['photo']['ready']


def test_photo_rejects_cropped_occluded_and_stale_body():
    for case in ('cropped','occluded','degenerate'):
        tracker=LiveMetrics();p=full_body()
        if case=='cropped':p[31,1]=1.01
        elif case=='occluded':p[15,2]=.2
        else:p[:,:2]=.5
        for t in (0,.5,1.1):
            assert not tracker.update(p,t,640,360,.5)['photo']['ready']
    tracker=LiveMetrics();p=full_body()
    tracker.update(p,0,640,360,.5)
    assert not tracker.update(p,2,640,360,.5)['photo']['held']
