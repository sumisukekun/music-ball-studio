"""Grieg - In the Hall of the Mountain King (piano version by the composer, public domain;
Mutopia edition). Excerpt: bars 0-16 then 49-87 with a continuous accelerando."""
import json, mido, numpy as np

m = mido.MidiFile('/home/claude/nordic/src/mk.midi'); tpb = m.ticks_per_beat; BAR = 4 * tpb
notes = []
for t in m.tracks:
    tick = 0; on = {}
    for e in t:
        tick += e.time
        if e.type == 'note_on' and e.velocity > 0: on.setdefault(e.note, []).append(tick)
        elif e.type in ('note_off', 'note_on') and on.get(e.note):
            s = on[e.note].pop(0); notes.append((s, tick, e.note))
SEGS = [(0, 17), (49, 88)]          # bar ranges [a, b)
T0 = 1.0
# tempo per bar of the excerpt
bars = [b for a, c in SEGS for b in range(a, c)]
nb = len(bars)
bpm = []
for i, b in enumerate(bars):
    if b < 17:
        bpm.append(118 + (150 - 118) * i / 16)
    else:
        j = b - 49
        bpm.append(160 * (255 / 160) ** (j / 37) if b < 87 else 230)
bar_start = [T0]
for q in bpm: bar_start.append(bar_start[-1] + 240 / q)
bar_index = {b: i for i, b in enumerate(bars)}
def t_of(tick):
    b = tick // BAR
    i = bar_index[b]
    return bar_start[i] + (tick - b * BAR) / BAR * (bar_start[i + 1] - bar_start[i])
LAYERS = [(0, 9), (9, 17), (49, 57), (57, 65), (65, 73), (73, 81), (81, 88)]
out = []
for s, e, n in notes:
    b = s // BAR
    if b not in bar_index: continue
    eb = min(e, (b + 1) * BAR - 1) if (e // BAR) not in bar_index else e
    ts_ = t_of(s); te_ = t_of(min(eb, (bars[-1] + 1) * BAR - 1))
    layer = next(i for i, (a, c) in enumerate(LAYERS) if a <= b < c)
    out.append(dict(t=ts_, end=max(te_, ts_ + 0.05), midi=n, bar=int(b), layer=layer))
out.sort(key=lambda x: (x['t'], x['midi']))
onsets = []
for n in out:
    if onsets and abs(onsets[-1]['t'] - n['t']) < 1e-4:
        onsets[-1]['midis'].append(n['midi'])
    else:
        onsets.append(dict(t=n['t'], midis=[n['midi']], layer=n['layer'], bar=n['bar']))
END_MUSIC = bar_start[-1]
json.dump(dict(notes=out, onsets=onsets, layers=len(LAYERS), end_music=END_MUSIC, END=END_MUSIC + 4.5,
               bar_start=bar_start), open('/home/claude/nordic/score.json', 'w'))
print(len(out), 'notes', len(onsets), 'onsets; music ends', round(END_MUSIC, 1),
      'per layer', [sum(1 for o in onsets if o['layer'] == l) for l in range(len(LAYERS))])
