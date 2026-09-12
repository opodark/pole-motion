"""Temporal live measurements; shared contact heuristics, experimental turn cue."""
from collections import deque
import math
import numpy as np
from . import pose


class LiveMetrics:
    def __init__(self):
        self.frames = deque(maxlen=80)
        self.sides = deque(maxlen=5)
        self.last_side = 0
        self.last_turn = -100
        self.still_anchor = None
        self.still_since = None

    def update(self, points, t, width, height, manual_pole=None):
        if self.frames and t-self.frames[-1].t > .7:
            self.still_anchor = None
            self.still_since = None
            self.frames.clear()
            self.sides.clear()
            self.last_side = 0
        lm = np.asarray(points) if points is not None else None
        self.frames.append(pose.PoseFrame(t=t, lm=lm))
        frames = list(self.frames)
        px = manual_pole if manual_pole is not None else pose.pole_x_from_pose(frames)
        angles = []
        if lm is not None:
            for label, a, b, c in [('Gomito S',11,13,15),('Gomito D',12,14,16),('Ginocchio S',23,25,27),('Ginocchio D',24,26,28)]:
                if min(lm[[a,b,c],2]) < .5:
                    continue
                u=(lm[a,:2]-lm[b,:2])*[width,height]
                v=(lm[c,:2]-lm[b,:2])*[width,height]
                norm=float(np.linalg.norm(u)*np.linalg.norm(v))
                if norm > 1e-8:
                    angles.append({'label':label,'joint':b,'a':a,'c':c,'degrees':round(math.degrees(math.acos(float(np.clip(np.dot(u,v)/norm,-1,1)))))})
        active = []
        if lm is not None:
            for contact in pose.contacts(frames, px):
                if abs(contact.t1-t)<1e-6:
                    xy=pose._part_xy(lm,pose.GRIP_PARTS[contact.part])
                    if xy is not None and abs(xy[0]-px)<.09:
                        active.append({'part':contact.part,'xy':xy,'duration':round(t-contact.t0,2)})
        turn = False
        # A left/right/left traversal is only a candidate: 2D cannot prove an orbit.
        if lm is not None and px is not None and min(lm[[23,24],2]) >= .5 and active:
            center=float(np.mean(lm[[23,24],0]))
            side=1 if center-px>.12 else -1 if center-px<-.12 else 0
            if side and side!=self.last_side:
                self.sides.append((side,t));self.last_side=side
            if len(self.sides)>=3:
                a,b,c=list(self.sides)[-3:]
                if a[0]==c[0] and a[0]!=b[0] and .8<c[1]-a[1]<8 and t-self.last_turn>3:
                    turn=True;self.last_turn=t;self.sides.clear()
        elif lm is None or not active:
            self.sides.clear();self.last_side=0
        # Sustained visibility and bounded displacement, not catalog recognition.
        key = [0,11,12,13,14,15,16,23,24,25,26,27,28,29,30,31,32]
        photo = {'ready': False, 'held': False, 'duration_s': 0.0, 'box': None,
                 'reason': 'Inquadra tutto il corpo'}
        visible = (lm is not None and np.isfinite(lm[key]).all()
                   and min(lm[key,2]) >= .6)
        if visible:
            xy = lm[key,:2]
            low, high = xy.min(axis=0), xy.max(axis=0)
            inside = bool(np.all(low >= .035) and np.all(high <= .965))
            # Reject degenerate detections, irrespective of upright/inverted orientation.
            substantial = float(np.linalg.norm((high-low)*[width,height])/math.hypot(width,height)) > .15
            if inside and substantial:
                scaled = xy * [width,height] / math.hypot(width,height)
                if self.still_anchor is None or np.max(np.linalg.norm(scaled-self.still_anchor,axis=1)) > .018:
                    self.still_anchor = scaled.copy()
                    self.still_since = t
                duration = max(0.0, t-self.still_since)
                photo.update(ready=duration >= 1.0, held=duration >= .6,
                             duration_s=round(duration,2),
                             box=[float(low[0]),float(low[1]),float(high[0]),float(high[1])],
                             reason='Pronta per lo scatto' if duration >= 1 else 'Mantieni la posa')
            else:
                self.still_anchor = None
                self.still_since = None
        else:
            self.still_anchor = None
            self.still_since = None
        return {'pole_x':px,'pole_method':'manual' if manual_pole is not None else 'keypoint estimate',
                'angles':angles,'contacts':active,'turn_candidate':turn,'photo':photo}
