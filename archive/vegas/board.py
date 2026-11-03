"""Board geometry for the Vegas plinko (x across, z up). Shared by sim and Blender."""
import json, math
import numpy as np

W = 10.0
pegs = []      # x, z, radius, restitution, kind(0 peg, 1 bumper)
segs = []      # x1, z1, x2, z2, restitution, friction, kind(0 wall,1 shelf,2 funnel,3 divider,4 floor)
spinners = []  # cx, cz, arm, n_arms, w, phase

def peg_rows(z0, rows, dz=1.9, dx=2.3, skip=()):
    for i in range(rows):
        z = z0 - i * dz
        n = 8 if i % 2 == 0 else 7
        for k in range(n):
            x = (k - (n - 1) / 2) * dx
            if not any(abs(x - sx) < 1.3 and abs(z - sz) < 1.3 for sx, sz in skip):
                pegs.append((x, z, 0.28, 0.5, 0))

# walls
segs.append((-W, 8, -W, -127, 0.4, 0.02, 0))
segs.append((W, 8, W, -127, 0.4, 0.02, 0))
# A: classic peg field
peg_rows(-2.0, 12)
# B: two spinners
spinners.append((-4.6, -27.0, 3.0, 4, 1.7, 0.0))
spinners.append((4.6, -27.0, 3.0, 4, -1.7, 0.4))
pegs += [(0.0, -25.5, 0.28, 0.5, 0), (0.0, -28.5, 0.28, 0.5, 0)]
# C: zig-zag shelves
segs.append((-W, -34.0, 6.5, -36.2, 0.2, 0.0006, 1))
segs.append((W, -39.0, -6.5, -41.2, 0.2, 0.0006, 1))
segs.append((-W, -44.0, 6.5, -46.2, 0.2, 0.0006, 1))
# D: pegs with bumpers
bump = [(-5.0, -55.0), (5.0, -55.0), (0.0, -61.0)]
peg_rows(-49.0, 9, skip=bump)
for x, z in bump:
    pegs.append((x, z, 1.0, 1.12, 1))
# E: funnel + roulette spinner
segs.append((-W, -70.0, -1.55, -76.0, 0.3, 0.01, 2))
segs.append((W, -70.0, 1.55, -76.0, 0.3, 0.01, 2))
spinners.append((0.0, -80.5, 3.4, 6, 2.2, 0.2))
# F: two more shelves
segs.append((-W, -86.0, 7.0, -88.2, 0.2, 0.0006, 1))
segs.append((W, -91.0, -7.0, -93.2, 0.2, 0.0006, 1))
# G: centre ramp + final peg field
segs.append((-W, -94.6, -1.8, -97.2, 0.2, 0.0006, 1))
peg_rows(-99.0, 11)
# slots
NS = 9
SLOT_TOP, FLOOR = -120.5, -126.0
for k in range(1, NS):
    x = -W + k * 2 * W / NS
    segs.append((x, SLOT_TOP, x, FLOOR, 0.3, 0.05, 3))
segs.append((-W, FLOOR, W, FLOOR, 0.15, 0.2, 4))
LABELS = ['$1', '$10', '$100', '$500', '$1M', '$500', '$100', '$10', '$1']
JACKPOT = 4

def save(path):
    json.dump(dict(W=W, pegs=pegs, segs=segs, spinners=spinners, NS=NS, SLOT_TOP=SLOT_TOP,
                   FLOOR=FLOOR, LABELS=LABELS, JACKPOT=JACKPOT), open(path, 'w'))
if __name__ == '__main__':
    save('/home/claude/vegas/board.json')
    print(len(pegs), 'pegs', len(segs), 'segs', len(spinners), 'spinners')
