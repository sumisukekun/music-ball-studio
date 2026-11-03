"""Lay out a Pythagora-style chain-reaction machine where every note is one event:
xylophone-key bounces (B sections) and domino hits (D sections)."""
import json, math, numpy as np

S = json.load(open('/home/claude/nordic/score.json'))
on = S['onsets']
SECT = [('B', [0]), ('D', [1]), ('B', [2]), ('D', [3]), ('B', [4]), ('D', [5, 6])]
G = 34.0; R = 0.42; C = 1.25
DH, DD, DW, P = 1.7, 0.24, 0.9, 1.05
KEY_L = 1.15

def merge(ts_, thr):
    groups = []
    for i, t in enumerate(ts_):
        if groups and t - ts_[groups[-1][-1]] < thr: groups[-1].append(i)
        else: groups.append([i])
    return groups

sections = []
x, z = 0.0, 0.0
ball_events = []        # (t, x, z) knots for the ball, with flight types
pending_ball = None     # ball resting at shelf end waiting to be pushed
for si, (kind, layers) in enumerate(SECT):
    idx = [i for i, o in enumerate(on) if o['layer'] in layers]
    tl = [on[i]['t'] for i in idx]
    if kind == 'B':
        groups = merge(tl, 0.09)
        gt = [tl[g[0]] for g in groups]
        dmin = min(np.diff(gt)) if len(gt) > 1 else 0.3
        vx = max(KEY_L * 1.25 / dmin, 5.0)
        if sections:
            x, z = x + 2.6, z - 2.4
        xs = x + vx * (np.array(gt) - gt[0]); zs = z - C * (np.array(gt) - gt[0])
        keys = []
        for k in range(len(gt)):
            keys.append(dict(t=gt[k], x=float(xs[k]), z=float(zs[k]), notes=[idx[j] for j in groups[k]]))
        sections.append(dict(kind='B', keys=keys, vx=vx))
        x, z = xs[-1], zs[-1]
    else:
        n = len(tl)
        # shelf starts a little after the ball's last key, lower down
        gap_t = tl[0] - sections[-1]['keys'][-1]['t']
        sx = x + sections[-1]['vx'] * gap_t * 0.9 + 0.6
        sz = z - 2.2
        piv = [sx + i * P for i in range(n)]
        sections.append(dict(kind='D', z=sz, pivots=piv, times=tl, notes=idx, x0=sx - 1.5,
                             x1=piv[-1] + (3.2 if si < len(SECT) - 1 else 1.0)))
        x = piv[-1] + 0.75 * DH + R
        z = sz + R
json.dump(dict(sections=sections, G=G, R=R, DH=DH, DD=DD, DW=DW, P=P, KEY_L=KEY_L, END=S['END'],
               end_music=S['end_music']), open('/home/claude/nordic/machine.json', 'w'))
for s in sections:
    if s['kind'] == 'B': print('B keys', len(s['keys']), 'vx', round(s['vx'], 1), 'x', round(s['keys'][0]['x'], 1), '->', round(s['keys'][-1]['x'], 1))
    else: print('D dominoes', len(s['pivots']), 'x', round(s['pivots'][0], 1), '->', round(s['pivots'][-1], 1), 'z', round(s['z'], 1))
