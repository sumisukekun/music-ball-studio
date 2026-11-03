"""Debussy - Arabesque No.1 (1891, public domain; Mutopia edition), bars 1-38 (to the E-major cadence)."""
import json, mido, numpy as np
m = mido.MidiFile('/home/claude/ice/src/arab.midi'); tpb = m.ticks_per_beat; BAR = 4 * tpb
NB = 38
notes = []
for t in m.tracks:
    tick = 0; on = {}
    for e in t:
        tick += e.time
        if e.type == 'note_on' and e.velocity > 0: on.setdefault(e.note, []).append(tick)
        elif e.type in ('note_off', 'note_on') and on.get(e.note):
            s = on[e.note].pop(0)
            if s < NB * BAR: notes.append((s, tick, e.note))
T0 = 1.2
def bpm(b, beat):
    q = 112
    if b in (3, 7, 11, 15, 25) and beat >= 3: q *= 0.85
    if b in (8, 9, 10, 18, 19, 20, 21): q *= 1.05
    if b >= 35: q *= 0.92 - 0.12 * (b - 35 + beat / 4) / 3
    return q
edges = [T0]
for b in range(NB):
    for beat in range(4):
        edges.append(edges[-1] + 60 / bpm(b, beat))
edges = np.array(edges)
def t_of(tick):
    pos = tick / tpb; i = int(min(pos, len(edges) - 2)); return float(edges[i] + (edges[i + 1] - edges[i]) * (pos - i))
out = []
for s, e, n in notes:
    out.append(dict(t=t_of(s), end=t_of(min(e, NB * BAR - 1)), midi=n, bar=s // BAR))
out.sort(key=lambda x: (x['t'], x['midi']))
onsets = []
for n in out:
    if onsets and n['t'] - onsets[-1]['t'] < 0.03: onsets[-1]['midis'].append(n['midi'])
    else: onsets.append(dict(t=n['t'], midis=[n['midi']], bar=int(n['bar'])))
END_MUSIC = edges[-1]
json.dump(dict(notes=out, onsets=onsets, end_music=END_MUSIC, END=END_MUSIC + 5.0), open('/home/claude/ice/score.json', 'w'))
print(len(out), 'notes', len(onsets), 'onsets, music ends', round(END_MUSIC, 1))
