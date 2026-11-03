"""Debussy - Clair de lune (Suite bergamasque, 1905; public domain), bars 1-14.
Notes come from the Mutopia Project edition (public domain typesetting).
Adds an expressive tempo map and a final D-flat major chord as a short coda."""
import json, numpy as np

d = json.load(open('/home/claude/clair/raw.json'))
tpb = d['tpb']; E8 = tpb // 2; BAR = 9 * E8
NBARS = 14
T0 = 1.5
E0 = 0.56            # base eighth-note length (s)

def factor(b, k):
    f = 1.0
    if b in (3, 7, 11) and k >= 6: f *= 1.0 + 0.12 * (k - 5)          # breathe at phrase ends
    if b in (9, 10): f *= 0.96
    if b == 13: f *= 1.0 + 0.6 * (k / 8) ** 1.6                       # final ritardando
    if b == 0 and k == 0: f *= 1.3
    return f
edges = [T0]
for b in range(NBARS):
    for k in range(9):
        edges.append(edges[-1] + E0 * factor(b, k))
edges = np.array(edges)
def t_of(tick):
    pos = tick / E8
    i = int(np.clip(np.floor(pos), 0, len(edges) - 2))
    return float(edges[i] + (edges[i + 1] - edges[i]) * (pos - i))

notes = [n for n in d['notes'] if n['s'] < NBARS * BAR]
out = []
for n in notes:
    s = t_of(n['s'])
    bar_end = t_of(((n['s'] // BAR) + 1) * BAR)
    e = max(t_of(min(n['e'], NBARS * BAR)), bar_end + 0.15)        # pedal: ring through the bar
    out.append(dict(t=s, end=e, midi=n['m'], upper=n['tr'] == 1, bar=n['s'] // BAR))
out.sort(key=lambda n: (n['t'], n['midi']))
final_t = edges[-1] + 0.35
coda = [37, 44, 49, 53, 56, 61, 65, 68, 73, 77]
rows = []
for n in out:
    if rows and abs(rows[-1]['t'] - n['t']) < 1e-6:
        rows[-1]['midis'].append(n['midi'])
    else:
        rows.append(dict(t=n['t'], midis=[n['midi']]))
rows.append(dict(t=final_t, midis=coda, final=True))
json.dump(dict(notes=out, rows=rows, final_t=final_t, coda=coda, end=final_t + 6.0),
          open('/home/claude/clair/score.json', 'w'))
print(len(out), 'notes', len(rows), 'rows; final', round(final_t, 2), 'end', round(final_t + 6, 2))
