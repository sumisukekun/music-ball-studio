"""'Midnight Spiral' - an original medium-swing jazz tune (AABA, F major), composed for this video."""
import json, re
NOTE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
def mi(s):
    m = re.match(r'([A-G])(#|b)?(\d)', s); n = NOTE[m.group(1)] + {'#': 1, 'b': -1, None: 0}[m.group(2)]
    return 12 * (int(m.group(3)) + 1) + n
CH = {'F': ('F', [9, 4, 7]), 'D7': ('D', [6, 0, 4]), 'Gm7': ('G', [10, 5, 9]), 'C7': ('C', [4, 10, 2]),
      'Am7': ('A', [0, 7, 11]), 'Cm7': ('C', [3, 10, 2]), 'F7': ('F', [9, 3, 7]), 'Bb': ('Bb', [2, 9, 0]),
      'Dm7': ('D', [5, 0, 4]), 'G7': ('G', [11, 5, 9])}
# bars: (chords, melody "pitch:beats ...", r = rest)
A_HEAD = [
    (['F'], 'A4:1 C5:.5 E5:.5 G5:1.5 E5:.5'),
    (['D7'], 'F#5:1 E5:.5 D5:.5 C5:1 A4:1'),
    (['Gm7'], 'Bb4:.5 D5:.5 F5:.5 A5:1.5 G5:1'),
    (['C7'], 'E5:1 D5:.5 C5:.5 Bb4:1 G4:1'),
    (['Am7', 'D7'], 'A4:.5 C5:.5 E5:1 D5:.5 C5:.5 A4:1'),
    (['Gm7', 'C7'], 'Bb4:.5 D5:.5 F5:1 E5:.5 G5:.5 C5:1')]
A1 = A_HEAD + [(['F', 'D7'], 'A5:1.5 G5:.5 F#5:1 E5:.5 D5:.5'), (['Gm7', 'C7'], 'F5:1 D5:.5 Bb4:.5 G4:1 r:1')]
A2 = A_HEAD + [(['F'], 'A4:.5 C5:.5 F5:1 E5:.5 F5:.5 A5:1'), (['F'], 'F5:3 r:1')]
B = [(['Cm7'], 'G5:1 Eb5:.5 C5:.5 Bb4:1 C5:1'), (['F7'], 'Eb5:1.5 D5:.5 C5:1 A4:1'),
     (['Bb'], 'D5:.5 F5:.5 A5:1.5 F5:.5 D5:1'), (['Bb'], 'C5:3 r:1'),
     (['Dm7'], 'F5:1 A5:.5 C6:.5 A5:1 F5:1'), (['G7'], 'B5:1.5 A5:.5 G5:1 F5:1'),
     (['Gm7'], 'Bb5:1 A5:.5 G5:.5 F5:1 D5:1'), (['C7'], 'E5:1 G5:.5 Bb5:.5 A5:1 G5:1')]
A3 = A_HEAD + [(['F', 'D7'], 'A5:1.5 G5:.5 F5:1 D5:1'), (['Gm7', 'C7'], 'F5:.5 E5:.5 D5:.5 C5:.5 A4:1 F4:1')]
SONG = A1 + A2 + B + A3
BPM = 132; BEAT = 60 / BPM; T0 = 1.2
def swing(b):   # beat position -> swung time (in beats)
    w = int(b); f = b - w
    return w + (f / 0.5 * 0.667 if f <= 0.5 else 0.667 + (f - 0.5) / 0.5 * 0.333)
ev = []
for bi, (chords, mel) in enumerate(SONG):
    t_bar = T0 + bi * 4 * BEAT
    pos = 0.0
    for tok in mel.split():
        p, d = tok.split(':'); d = float(d)
        if p != 'r':
            st = swing(pos); en = swing(pos + d)
            ev.append(dict(t=t_bar + st * BEAT, midi=mi(p), dur=(en - st) * BEAT * 0.95, voice='mel'))
        pos += d
    # walking bass: one note per beat
    roots = [CH[c] for c in chords]
    nxt = SONG[(bi + 1) % len(SONG)][0][0] if bi + 1 < len(SONG) else 'F'
    nroot = mi(CH[nxt][0] + '2') % 12
    line = []
    if len(roots) == 1:
        r, tones = roots[0]; rm = mi(r + '2')
        if rm > 45: rm -= 12
        third = rm + (tones[0] - mi(r + '2') % 12) % 12
        fifth = rm + 7
        appr = rm + ((nroot - rm % 12) % 12) - 1
        if appr - rm > 9: appr -= 12
        line = [rm, third, fifth, appr]
    else:
        for r, tones in roots:
            rm = mi(r + '2')
            if rm > 45: rm -= 12
            line += [rm, rm + 7]
        line[-1] = line[-2] + ((nroot - line[-2] % 12) % 12) - 1
    for k, m in enumerate(line):
        ev.append(dict(t=t_bar + k * BEAT, midi=int(m), dur=BEAT * 0.92, voice='bass'))
    # piano comping (Charleston: beat 1 and the & of 2), rootless voicings
    for ci, (r, tones) in enumerate(roots):
        span = 4 / len(roots)
        base = 4 * 12 + 4 + 0 * ci
        hits = [0.0, 1.5] if len(roots) == 1 else [0.0]
        for h in hits:
            hb = ci * span + h
            for tn in tones:
                m = 60 + ((tn - 60) % 12) - (12 if (60 + ((tn - 60) % 12)) > 67 else 0)
                ev.append(dict(t=t_bar + swing(hb) * BEAT, midi=m, dur=BEAT * (0.8 if h == 0 else 0.5), voice='comp'))
END_BAR = len(SONG)
tf = T0 + END_BAR * 4 * BEAT
for m in [41, 53, 57, 60, 64, 67, 69, 77]:
    ev.append(dict(t=tf, midi=m, dur=3.5, voice='coda' if m in (77,) else ('bass' if m == 41 else 'comp')))
ev.sort(key=lambda e: (e['t'], e['midi']))
json.dump(dict(events=ev, end_music=tf, END=tf + 6.5, bpm=BPM, T0=T0, bars=END_BAR), open('/home/claude/jazz/arr.json', 'w'))
print(len(ev), 'events; melody', sum(e['voice'] == 'mel' for e in ev), 'end', round(tf, 1))
