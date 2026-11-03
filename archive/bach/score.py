"""Bach, Prelude in C major BWV 846, bars 1-19 (public domain composition).
Produces note times shared by the music renderer and the Blender scene."""
import json

BARS = [
    (60, 64, 67, 72, 76), (60, 62, 69, 74, 77), (59, 62, 67, 74, 77), (60, 64, 67, 72, 76),
    (60, 64, 69, 76, 81), (60, 62, 66, 69, 74), (59, 62, 67, 74, 79), (59, 60, 64, 67, 72),
    (57, 60, 64, 67, 72), (50, 57, 62, 66, 72), (55, 59, 62, 67, 71), (55, 58, 64, 67, 73),
    (53, 57, 62, 69, 74), (53, 56, 62, 65, 71), (52, 55, 60, 67, 72), (52, 53, 57, 60, 65),
    (50, 53, 57, 60, 65), (43, 50, 55, 59, 65), (48, 52, 55, 60, 64),
]
T0 = 1.2
DT = 60 / 72 / 4          # sixteenth at quarter = 72
notes = []                # dicts: t, midi, bar, idx_in_half, end (sustain end)
t = T0
for b, ch in enumerate(BARS):
    for half in range(2):
        pattern = [0, 1, 2, 3, 4, 2, 3, 4]
        half_start = t
        times = []
        for k, pi in enumerate(pattern):
            # gentle ritardando through the final bar
            stretch = 1.0
            if b == len(BARS) - 1:
                stretch = 1.0 + 0.45 * ((half * 8 + k) / 15) ** 2
            times.append(t)
            t += DT * stretch
        for k, pi in enumerate(pattern):
            notes.append(dict(t=times[k], midi=ch[pi], bar=b, k=half * 8 + k, end=t + 0.05))
final_t = t + 0.25
final_chord = [36, 48, 55, 60, 64, 67, 72, 76, 79, 84]
json.dump(dict(notes=notes, final_t=final_t, final_chord=final_chord, end=final_t + 6.0),
          open('/home/claude/bach/score.json', 'w'))
print(len(notes), 'notes; last', round(notes[-1]['t'], 2), 'final', round(final_t, 2), 'end', round(final_t + 6, 2))
