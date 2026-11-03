"""Build bounce paths so every bounce lands exactly on a note of The Entertainer.
Ball 0 = right hand (melody), ball 1 = left hand (bass/chords)."""
import json, mido, math, numpy as np

T0 = 1.2
BAR = 1.56                     # seconds per 2/4 bar (q ~ 77)
mf = mido.MidiFile('/home/claude/vegas/src/ent.midi'); tpb = mf.ticks_per_beat
BAR_T = 2 * tpb
CUT = 35 * BAR_T + tpb // 4
spt = BAR / BAR_T

onsets = []
for ti, tr in enumerate(mf.tracks[1:]):
    tick = 0; on = {}; notes = []
    for e in tr:
        tick += e.time
        if e.type == 'note_on' and e.velocity > 0: on.setdefault(e.note, []).append(tick)
        elif e.type in ('note_off', 'note_on') and on.get(e.note):
            s = on[e.note].pop(0)
            if s < CUT: notes.append((s, tick, e.note))
    groups = {}
    for s, e, m in notes: groups.setdefault(s, []).append((m, (e - s) * spt))
    onsets.append([(T0 + s * spt, sorted(groups[s])) for s in sorted(groups)])
T_END = T0 + 35 * BAR
print('onsets', [len(o) for o in onsets], 'jackpot at', T_END)

G = 34.0
R = 0.38
C = 2.3                          # average descent speed (units/s) shared by both balls
ZOFF = [4.6, -4.6]
VX = 6.6
PLAT_L = 1.0

def build(times, zoff, vx0):
    n = len(times)
    extra = np.zeros(n)
    for attempt in range(400):
        xs = vx0 * times
        zs = -C * times + zoff - np.cumsum(extra)
        # platform normals from in/out velocities
        vin = np.zeros((n, 2)); vout = np.zeros((n, 2))
        for k in range(n - 1):
            dt = times[k + 1] - times[k]
            vxk = (xs[k + 1] - xs[k]) / dt
            vz = ((zs[k + 1] - zs[k]) + 0.5 * G * dt * dt) / dt
            vout[k] = (vxk, vz); vin[k + 1] = (vxk, vz - G * dt)
        vin[0] = (0, -6.0); vout[-1] = (0, 6.0)
        nrm = vout - vin
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
        # check arcs against other platforms
        bad = None
        px = xs - nrm[:, 0] * R; pz = zs - nrm[:, 1] * R          # platform centres
        tang = np.stack([nrm[:, 1], -nrm[:, 0]], 1)
        for k in range(n - 1):
            dt = times[k + 1] - times[k]
            for u in np.linspace(0.08, 0.92, 12):
                tau = u * dt
                bx = xs[k] + vout[k, 0] * tau; bz = zs[k] + vout[k, 1] * tau - 0.5 * G * tau * tau
                lo, hi = max(0, k - 40), min(n, k + 40)
                for j in range(lo, hi):
                    if j in (k, k + 1): continue
                    dx, dz = bx - px[j], bz - pz[j]
                    along = dx * tang[j, 0] + dz * tang[j, 1]
                    perp = dx * nrm[j, 0] + dz * nrm[j, 1]
                    if abs(along) < PLAT_L / 2 + R * 0.6 and abs(perp) < R + 0.25:
                        bad = (k, j); break
                if bad: break
            if bad: break
        if bad is None:
            return xs, zs, nrm, vout, extra
        extra[bad[0] + 1] += 0.35
        if attempt % 50 == 0: print('bad', bad, round(times[bad[0]],2), round(times[bad[1]],2))
    raise RuntimeError('could not resolve collisions')

paths = []
for b in range(2):
    times = np.array([t for t, _ in onsets[b]])
    xs, zs, nrm, vout, extra = build(times, ZOFF[b], VX)
    paths.append(dict(times=times.tolist(), xs=xs.tolist(), zs=zs.tolist(), nrm=nrm.tolist(),
                      vout=vout.tolist(), notes=[g for _, g in onsets[b]]))
    print('ball', b, 'extra drops', int((extra > 0).sum()), 'zmin', round(zs.min(), 1))
zf = 0
json.dump(dict(T0=T0, BAR=BAR, T_END=T_END, G=G, R=R, paths=paths, END=T_END + 6.5),
          open('/home/claude/vegas2/paths.json', 'w'))
print('final z', round(zf, 1))
