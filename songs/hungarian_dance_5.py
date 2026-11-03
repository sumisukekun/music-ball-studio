"""Own arrangement of Brahms, Hungarian Dance No.5 (public-domain melody) in A minor:
A | A' (octave up) | B (fast) | B (with ritardando) | A | coda chords.
Melody taken from a public-domain lead sheet line; accompaniment and tempo map are original."""
import json, re, sys, numpy as np

ABC_A = '''"Am"e6 a2 | "Am"c'6 a2 | "E7"^g6 a1b1 | "Am"a8 |
"Dm"f6 g1a1 | "Am"e8 | "E7"d1c1c1B1 B3e1 | "Am"A8 |
"Am"E3A1 c1e1a1c'1 | "Am"e'6 c'2 | "Bm7b5"b6 c'1d'1 | "Am"c'8 |
"Dm"f1g1a1f1 e1f1g1e1 | "Dm"d1e1f1d1 c1d1e1c1 | "E7"d1c1c1B1 B3e1 | "Am"A4 a2 z2 |'''
ABC_B = '''"A"a2e2 e2e2 | "A"e2d2 ^c2d2 | "A"e2e2 e2e2 | "A"a2e2 e2e2 |
"E7"e2d2 ^c2B2 | "A"A2A2 A2A2 | "A"^c4 d4 | "A"^c4 B4 |
"D"^c2c2 d2d2 | "A"e2a2 e4 |'''
BASE = {'C': 60, 'D': 62, 'E': 64, 'F': 65, 'G': 67, 'A': 69, 'B': 71}
CH = {'Am': (45, [57, 60, 64]), 'E7': (40, [56, 59, 62, 64]), 'Dm': (38, [57, 62, 65]), 'Bm7b5': (47, [57, 62, 65]),
      'A': (45, [57, 61, 64]), 'D': (38, [57, 62, 66])}

def parse(abc):
    bars = []
    for bar in abc.replace('\n', ' ').split('|'):
        bar = bar.strip()
        if not bar: continue
        chord = re.findall(r'"([^"]+)"', bar)[0]
        body = re.sub(r'"[^"]+"', '', bar)
        notes = []; pos = 0; acc = {}
        for m in re.finditer(r"(\^|_|=)?([A-Ga-gz])('*)(,*)(\d*)", body):
            a, l, up, dn, d = m.groups(); d = int(d) if d else 1
            if l == 'z': pos += d; continue
            mi = BASE[l.upper()] + (12 if l.islower() else 0) - 12 + 12 * len(up) - 12 * len(dn)
            key = (l.upper(), len(up), l.islower())
            if a == '^': acc[key] = 1
            elif a == '_': acc[key] = -1
            elif a == '=': acc[key] = 0
            mi += acc.get(key, 0)
            notes.append((pos, d, mi)); pos += d
        bars.append(dict(chord=chord, notes=notes))
    return bars
A = parse(ABC_A); B = parse(ABC_B)
sections = [('A', A, 0, 'rub'), ('A2', A, 12, 'rub2'), ('B', B, 0, 'fast'), ('B2', B, 0, 'fast_rit'), ('A3', A, 0, 'rub2')]

T0 = 1.2
events = []         # melody/accomp notes: t, midi, dur, voice
t = T0
for name, bars, octv, style in sections:
    nb = len(bars)
    for bi, bar in enumerate(bars):
        # gypsy rubato: each 4-bar phrase starts broad and rushes forward
        ph = bi % 4
        if style == 'rub':  q = [96, 116, 134, 108][ph]
        elif style == 'rub2': q = [108, 126, 142, 118][ph]
        elif style == 'fast': q = 150
        else: q = 150 if bi < nb - 2 else [92, 70][bi - (nb - 2)]
        if name == 'A3' and bi >= nb - 2: q = [118, 84][bi - (nb - 2)]
        six = 60 / q / 4
        for pos, d, mi in bar['notes']:
            events.append(dict(t=t + pos * six, midi=mi + octv, dur=d * six, voice='mel', octave=octv))
            if octv:
                events.append(dict(t=t + pos * six, midi=mi, dur=d * six, voice='mel2', octave=0))
        root, chord = CH[bar['chord']]
        # oom-pah: bass on 1 and 2, chord on the off-beats (8ths)
        for k in range(4):
            tt = t + k * 2 * six
            if k % 2 == 0:
                events.append(dict(t=tt, midi=root if k == 0 else root + 7 - (12 if root + 7 > 52 else 0), dur=2 * six * 0.9, voice='bass'))
            else:
                for c in chord:
                    events.append(dict(t=tt, midi=c, dur=2 * six * 0.6, voice='chord'))
        t += 8 * six
# coda: two hammered chords  E7 ... Am
for k, (root, ch) in enumerate([(40, [52, 56, 59, 62, 64, 68]), (33, [45, 57, 60, 64, 69, 72])]):
    tt = t + 0.25 + k * 0.55
    events.append(dict(t=tt, midi=root, dur=1.2 if k else 0.3, voice='bass'))
    for c in ch: events.append(dict(t=tt, midi=c, dur=1.6 if k else 0.3, voice='coda'))
END_MUSIC = t + 0.25 + 0.55
events.sort(key=lambda e: (e['t'], e['midi']))
json.dump(dict(events=events, end_music=END_MUSIC, END=END_MUSIC + 6.0), open(sys.argv[-1], 'w'))
mel = [e for e in events if e['voice'] == 'mel']
print(len(events), 'events,', len(mel), 'melody notes; music ends', round(END_MUSIC, 1))
