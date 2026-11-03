import json, sys, math, numpy as np
from numba import njit
import board

PEG = np.array(board.pegs, np.float64)
SEG = np.array(board.segs, np.float64)
SPN = np.array(board.spinners, np.float64)
R = 0.55
NC = 8
DT = 1 / 600.0
SUB = 10            # store every 10 substeps -> 60 Hz
TMAX = 75.0
G = 30.0

@njit(cache=True)
def run(p0, v0, PEG, SEG, SPN, g, tmax):
    nsteps = int(tmax / DT)
    nst = nsteps // SUB + 1
    P = np.zeros((nst, NC, 2)); V = np.zeros((nst, NC, 2))
    p = p0.copy(); v = v0.copy()
    land_t = np.full(NC, -1.0); slot = np.full(NC, -1)
    ev = np.zeros((60000, 6)); ne = 0      # t, kind, x, z, mag, id
    W = 10.0; NS = 9
    for s in range(nsteps):
        t = s * DT
        for i in range(NC):
            v[i, 1] -= g * DT
            v[i, 0] *= 0.9997; v[i, 1] *= 0.9997
            p[i, 0] += v[i, 0] * DT; p[i, 1] += v[i, 1] * DT
            # pegs / bumpers
            for k in range(PEG.shape[0]):
                dx = p[i, 0] - PEG[k, 0]; dz = p[i, 1] - PEG[k, 1]
                rr = R + PEG[k, 2]
                d2 = dx * dx + dz * dz
                if d2 < rr * rr:
                    d = math.sqrt(d2) + 1e-9
                    nx = dx / d; nz = dz / d
                    p[i, 0] += nx * (rr - d); p[i, 1] += nz * (rr - d)
                    vn = v[i, 0] * nx + v[i, 1] * nz
                    if vn < 0:
                        e = PEG[k, 3]
                        v[i, 0] -= (1 + e) * vn * nx; v[i, 1] -= (1 + e) * vn * nz
                        if PEG[k, 4] == 1:
                            v[i, 0] += nx * 3.0; v[i, 1] += nz * 3.0
                        tx = -nz; tz = nx; vt = v[i, 0] * tx + v[i, 1] * tz
                        v[i, 0] -= 0.05 * vt * tx; v[i, 1] -= 0.05 * vt * tz
                        if -vn > 1.2 and ne < 60000:
                            ev[ne, 0] = t; ev[ne, 1] = 1 + PEG[k, 4]; ev[ne, 2] = PEG[k, 0]; ev[ne, 3] = PEG[k, 1]; ev[ne, 4] = -vn; ev[ne, 5] = k; ne += 1
            # segments
            for k in range(SEG.shape[0]):
                ax = SEG[k, 0]; az = SEG[k, 1]; bx = SEG[k, 2]; bz = SEG[k, 3]
                ex = bx - ax; ez = bz - az
                L2 = ex * ex + ez * ez
                u = ((p[i, 0] - ax) * ex + (p[i, 1] - az) * ez) / L2
                if u < 0: u = 0.0
                if u > 1: u = 1.0
                qx = ax + u * ex; qz = az + u * ez
                dx = p[i, 0] - qx; dz = p[i, 1] - qz
                d2 = dx * dx + dz * dz
                if d2 < R * R:
                    d = math.sqrt(d2) + 1e-9
                    nx = dx / d; nz = dz / d
                    p[i, 0] += nx * (R - d); p[i, 1] += nz * (R - d)
                    vn = v[i, 0] * nx + v[i, 1] * nz
                    if vn < 0:
                        e = SEG[k, 4]
                        v[i, 0] -= (1 + e) * vn * nx; v[i, 1] -= (1 + e) * vn * nz
                        tx = -nz; tz = nx; vt = v[i, 0] * tx + v[i, 1] * tz
                        f = SEG[k, 5]
                        v[i, 0] -= f * vt * tx; v[i, 1] -= f * vt * tz
                        if -vn > 1.5 and ne < 60000:
                            ev[ne, 0] = t; ev[ne, 1] = 10 + SEG[k, 6]; ev[ne, 2] = qx; ev[ne, 3] = qz; ev[ne, 4] = -vn; ev[ne, 5] = k; ne += 1
            # spinners (rotating arms)
            for k in range(SPN.shape[0]):
                cx = SPN[k, 0]; cz = SPN[k, 1]; arm = SPN[k, 2]; na = int(SPN[k, 3]); w = SPN[k, 4]
                for a in range(na):
                    ang = SPN[k, 5] + w * t + 2 * math.pi * a / na
                    ex = math.cos(ang) * arm; ez = math.sin(ang) * arm
                    L2 = ex * ex + ez * ez
                    u = ((p[i, 0] - cx) * ex + (p[i, 1] - cz) * ez) / L2
                    if u < 0: u = 0.0
                    if u > 1: u = 1.0
                    qx = cx + u * ex; qz = cz + u * ez
                    dx = p[i, 0] - qx; dz = p[i, 1] - qz
                    rr = R + 0.15
                    d2 = dx * dx + dz * dz
                    if d2 < rr * rr:
                        d = math.sqrt(d2) + 1e-9
                        nx = dx / d; nz = dz / d
                        p[i, 0] += nx * (rr - d); p[i, 1] += nz * (rr - d)
                        svx = -w * (qz - cz); svz = w * (qx - cx)
                        rvx = v[i, 0] - svx; rvz = v[i, 1] - svz
                        vn = rvx * nx + rvz * nz
                        if vn < 0:
                            rvx -= 1.4 * vn * nx; rvz -= 1.4 * vn * nz
                            v[i, 0] = rvx + svx; v[i, 1] = rvz + svz
                            if -vn > 1.5 and ne < 60000:
                                ev[ne, 0] = t; ev[ne, 1] = 20; ev[ne, 2] = qx; ev[ne, 3] = qz; ev[ne, 4] = -vn; ev[ne, 5] = k; ne += 1
            # landing
            if land_t[i] < 0 and p[i, 1] < -121.3:
                land_t[i] = t
                sl = int((p[i, 0] + W) / (2 * W / NS))
                if sl < 0: sl = 0
                if sl > NS - 1: sl = NS - 1
                slot[i] = sl
        # chip-chip
        for i in range(NC):
            for j in range(i + 1, NC):
                dx = p[j, 0] - p[i, 0]; dz = p[j, 1] - p[i, 1]
                d2 = dx * dx + dz * dz
                if d2 < 4 * R * R:
                    d = math.sqrt(d2) + 1e-9
                    nx = dx / d; nz = dz / d
                    pen = 2 * R - d
                    p[i, 0] -= nx * pen / 2; p[i, 1] -= nz * pen / 2
                    p[j, 0] += nx * pen / 2; p[j, 1] += nz * pen / 2
                    rv = (v[j, 0] - v[i, 0]) * nx + (v[j, 1] - v[i, 1]) * nz
                    if rv < 0:
                        imp = -(1 + 0.5) * rv / 2
                        v[i, 0] -= imp * nx; v[i, 1] -= imp * nz
                        v[j, 0] += imp * nx; v[j, 1] += imp * nz
                        if -rv > 1.5 and ne < 60000:
                            ev[ne, 0] = t; ev[ne, 1] = 30; ev[ne, 2] = p[i, 0]; ev[ne, 3] = p[i, 1]; ev[ne, 4] = -rv; ev[ne, 5] = i; ne += 1
        if s % SUB == 0:
            P[s // SUB] = p; V[s // SUB] = v
        done = True
        for i in range(NC):
            if land_t[i] < 0: done = False
        if done and t > land_t.max() + 8.0:
            return P[:s // SUB + 1], V[:s // SUB + 1], land_t, slot, ev[:ne]
    return P[:nsteps // SUB], V[:nsteps // SUB], land_t, slot, ev[:ne]

def init(seed):
    rng = np.random.default_rng(seed)
    xs = np.linspace(-7, 7, NC) + rng.uniform(-0.35, 0.35, NC)
    p0 = np.stack([xs, np.full(NC, 1.5) + rng.uniform(-0.1, 0.1, NC)], 1)
    v0 = np.stack([rng.uniform(-0.6, 0.6, NC), np.zeros(NC)], 1)
    return p0, v0

if __name__ == '__main__':
    results = []
    for seed in range(int(sys.argv[1]), int(sys.argv[2])):
        p0, v0 = init(seed)
        P, V, lt, sl, ev = run(p0, v0, PEG, SEG, SPN, G, TMAX)
        ok = (lt >= 0).all()
        jp = [i for i in range(NC) if sl[i] == board.JACKPOT]
        last = int(np.argmax(lt)) if ok else -1
        gap = (np.sort(lt)[-1] - np.sort(lt)[-2]) if ok else 0
        results.append((seed, ok, jp, last, round(float(lt.max()), 2), round(float(gap), 2), list(sl)))
        if ok and len(jp) == 1 and jp[0] == last:
            print('GOOD', len(set(sl.tolist())), seed, 'winner', last, 'land', round(float(lt.max()), 2), 'gap', round(float(gap), 2), 'slots', list(sl), flush=True)
    bad = sum(1 for r in results if not r[1])
    print('done; stuck runs', bad, 'example', results[:3])
