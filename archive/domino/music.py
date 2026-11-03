import json, numpy as np
from scipy.signal import butter, sosfilt, fftconvolve
from scipy.io import wavfile

ev = json.load(open('/home/claude/domino/events.json'))
E = ev['E']; END = ev['end']
SR = 44100
N = int(SR * END) + SR
rng = np.random.default_rng(3)
dry = np.zeros((N, 2)); wet = np.zeros((N, 2)); side = np.zeros(N)  # side = kick envelope for ducking

def mtof(m): return 440 * 2 ** ((m - 69) / 12)
def tt(n): return np.arange(n) / SR
def lp(x, fc, order=2): return sosfilt(butter(order, fc, 'low', fs=SR, output='sos'), x)
def hp(x, fc, order=2): return sosfilt(butter(order, fc, 'high', fs=SR, output='sos'), x)
def bp(x, lo, hi): return sosfilt(butter(2, [lo, hi], 'band', fs=SR, output='sos'), x)

def put(sig, t, gain=1.0, pan=0.0, rev=0.0, bus=None):
    i = int(t * SR)
    if i >= N: return
    sig = sig[:N - i]
    l = np.cos((pan + 1) * np.pi / 4); r = np.sin((pan + 1) * np.pi / 4)
    st = np.stack([sig * l, sig * r], 1) * gain
    dry[i:i + len(sig)] += st
    if rev: wet[i:i + len(sig)] += st * rev

def saw(f, n, detune=0.0):
    t = tt(n); ph = (f * (1 + detune) * t) % 1.0
    return 2 * ph - 1

def mixa(a, b):
    n = max(len(a), len(b)); o = np.zeros(n); o[:len(a)] += a; o[:len(b)] += b; return o

# ---------- instruments ----------
def kick():
    n = int(0.45 * SR); t = tt(n)
    f = 45 + 110 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t * 7.5) + 0.25 * np.exp(-t * 300) * rng.standard_normal(n) * 0.3
    return np.tanh(s * 1.6)

def clap():
    n = int(0.35 * SR); t = tt(n)
    nz = bp(rng.standard_normal(n), 900, 5000)
    env = np.exp(-t * 18) + 0.6 * (np.exp(-np.maximum(t - 0.012, 0) * 60) * (t > 0.012)) + 0.5 * (np.exp(-np.maximum(t - 0.024, 0) * 50) * (t > 0.024))
    return nz * env * 0.9

def snare():
    n = int(0.25 * SR); t = tt(n)
    return (bp(rng.standard_normal(n), 1500, 8000) * np.exp(-t * 22) + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.5)

def hat(open_=False):
    n = int((0.25 if open_ else 0.06) * SR); t = tt(n)
    return hp(rng.standard_normal(n), 7000) * np.exp(-t * (12 if open_ else 70))

def pluck(m, dur=0.5, bright=1.0):
    n = int(dur * SR); t = tt(n); f = mtof(m)
    s = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 12) * bright
         + 0.25 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 20) * bright + 0.15 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t * 40))
    return s * np.exp(-t * 7) * np.minimum(t * 800, 1)

def marimba(m, dur=0.6):
    n = int(dur * SR); t = tt(n); f = mtof(m)
    s = np.sin(2 * np.pi * f * t) * np.exp(-t * 6) + 0.35 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t * 30) + 0.1 * np.sin(2 * np.pi * 10 * f * t) * np.exp(-t * 80)
    return s * np.minimum(t * 1500, 1)

def click(bright=1.0):
    n = int(0.03 * SR); t = tt(n)
    fc = 2500 + 2500 * bright
    s = bp(rng.standard_normal(n), fc * 0.6, min(fc * 1.6, 18000)) * np.exp(-t * 260)
    return s + np.sin(2 * np.pi * (1800 + 600 * bright) * t) * np.exp(-t * 300) * 0.4

def supersaw(ms, dur, cutoff=3500):
    n = int(dur * SR); s = np.zeros(n)
    for m in ms:
        for dt in (-0.012, -0.005, 0, 0.006, 0.013):
            s += saw(mtof(m), n, dt) * 0.2 * (1 + 0.3 * rng.random())
    s = lp(s, cutoff)
    t = tt(n)
    env = np.minimum(t * 200, 1) * np.minimum((dur - t) * 40, 1).clip(0, 1)
    return s * env / len(ms)

def bassnote(m, dur):
    n = int(dur * SR); t = tt(n); f = mtof(m)
    s = lp(saw(f, n) * 0.7 + np.sin(2 * np.pi * f * t), 900)
    return np.tanh(s * 1.5) * np.minimum(t * 300, 1) * np.minimum((dur - t) * 60, 1).clip(0, 1)

def boom(m, size):
    n = int((0.8 + size * 0.5) * SR); t = tt(n)
    f = mtof(m) * (1 + 1.5 * np.exp(-t * 20))
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t * (6 / size)) + lp(rng.standard_normal(n), 400) * np.exp(-t * 8) * 0.8
    return np.tanh(s * 2)

def riser(dur, f0=200, f1=6000):
    n = int(dur * SR); t = tt(n)
    x = rng.standard_normal(n)
    out = np.zeros(n); blk = 2048
    for i in range(0, n, blk):
        fc = f0 * (f1 / f0) ** (i / n)
        out[i:i + blk] = bp(x[i:i + blk], fc * 0.7, min(fc * 1.4, 19000))
    return out * (t / dur) ** 2

def crash():
    n = int(2.5 * SR); t = tt(n)
    return hp(rng.standard_normal(n), 4000) * np.exp(-t * 2.2)

# ---------- harmony ----------
C, G, Am, F = [48, 52, 55], [43, 47, 50], [45, 48, 52], [41, 45, 48]
def chord_of_bar(b):
    if b <= 0: return C
    if b <= 8: return [C, G, Am, F][(b - 1) % 4]
    return [C, G, F][min(b - 9, 2)] if b < 12 else C
bar = 8 * E

# ---------- drums / bass / chords per section ----------
for b in range(12):
    t0 = b * bar
    ch = chord_of_bar(b)
    root = ch[0] - 12 if ch[0] > 44 else ch[0]
    section = 'intro' if b == 0 else 'A' if b <= 2 else 'B' if b <= 6 else 'build' if b <= 8 else 'drop'
    for q in range(4):            # quarters
        tq = t0 + q * 2 * E
        if section in ('A', 'B', 'drop') or (section == 'build' and not (b == 8 and q == 3)):
            if not (section == 'A' and q % 2 == 1 and b == 1):
                put(kick(), tq, 0.95 if section != 'A' else 0.75)
                i = int(tq * SR); side[i:i + int(0.22 * SR)] = 1
        if section in ('A', 'B', 'drop') and q in (1, 3):
            put(clap(), tq, 0.45, rev=0.25)
    for e8 in range(8):
        te = t0 + e8 * E
        if section in ('B', 'drop', 'build') or (section == 'A' and b == 2):
            put(hat(open_=(e8 % 2 == 1)), te, 0.16 if e8 % 2 else 0.1, pan=0.3)
        if section == 'intro':
            put(hat(), te, 0.05, pan=-0.2)
        # offbeat bass
        if section in ('A', 'B', 'drop') and e8 % 2 == 1:
            put(bassnote(root, E * 0.9), te, 0.5)
        if section == 'build' and b == 7:
            put(bassnote(root, E * 0.9), te, 0.45)
        if section in ('B', 'drop'):
            for s16 in (0, 1):
                put(hat(), te + s16 * E / 2, 0.05, pan=-0.3)
    # chords
    if section == 'intro':
        put(lp(supersaw([m + 12 for m in ch], bar), 900), t0, 0.35, rev=0.5)
    elif section in ('A', 'B'):
        for e8 in (1, 3, 4, 6):
            put(supersaw([m + 12 for m in ch], E * 0.7, 2600), t0 + e8 * E, 0.32, rev=0.35)
    elif section == 'build':
        put(supersaw([m + 12 for m in ch], bar, 1500 + 1500 * (b - 7)), t0, 0.3, rev=0.4)
    elif section == 'drop':
        put(supersaw([m + 12 for m in ch] + [ch[0] + 24], bar * 0.98, 5000), t0, 0.42, rev=0.4)
        put(bassnote(root - 12, bar * 0.98), t0, 0.35)

# build: snare roll accelerating through bars 7-8, riser, silence before drop
for k in range(32):
    t = 56 * E + k * (E / 2) * (1 if k < 16 else 1)
    put(snare(), t, 0.12 + 0.35 * k / 32, pan=0.1, rev=0.2)
for k in range(8):
    put(snare(), 68 * E + k * E / 4, 0.4 + 0.05 * k, rev=0.2)
put(riser(16 * E), 56 * E, 0.35, rev=0.3)

# drop lead hook
hook = {9: [64, 67, 72, 67, 64, 67, 69, 67], 10: [62, 67, 71, 67, 62, 67, 69, 71], 11: [65, 69, 72, 69, 72, 74, 76, 79]}
for b, notes in hook.items():
    for k, m in enumerate(notes):
        put(mixa(pluck(m + 12, 0.4), 0.4 * supersaw([m], E * 0.85, 4000)), b * bar + k * E, 0.33, pan=(-0.25 if k % 2 else 0.25), rev=0.35)
# final chord
put(supersaw([60, 64, 67, 72, 76], 1.6, 4000) * np.exp(-tt(int(1.6 * SR)) * 1.5), 96 * E, 0.55, rev=0.6)
put(kick(), 96 * E, 1.0); put(crash(), 96 * E, 0.35, rev=0.3)
put(boom(36, 1.5), 96 * E, 0.5)

# ---------- domino sounds ----------
pent = [60, 62, 64, 67, 69, 72, 74, 76, 79, 81, 84]
snake = sorted([e for e in ev['events'] if e['kind'] == 'snake'], key=lambda e: e['t'])
# ball rolling in + tap
nroll = int(8 * E * SR)
roll = lp(rng.standard_normal(nroll), 180) * np.linspace(0.2, 1, nroll)
put(roll, 0, 0.25)
for k, e in enumerate(snake):
    m = pent[min(k, len(pent) - 1)] if k < 9 else [72, 76, 79, 76, 74, 79, 81, 84][k - 9]
    put(marimba(m), e['t'], 0.5, pan=0.0, rev=0.3)
    put(click(0.6), e['t'], 0.35)

grid = [e for e in ev['events'] if e['kind'] == 'grid']
for e in grid:
    pan = (e['c'] - 12) / 12 * 0.8
    put(click(rng.random()), e['t'] + rng.normal(0, 0.003), 0.06, pan=pan)
# row melody: arpeggio of current chord on each centre hit
for r in range(32):
    t = (29 + r) * E
    b = int(t // bar)
    ch = chord_of_bar(b)
    tones = [m + 24 for m in ch] + [ch[0] + 36]
    seq = [0, 1, 2, 3, 2, 1, 2, 3]
    m = tones[seq[r % 8]]
    put(marimba(m, 0.4), t, 0.32, pan=0, rev=0.3)

# giants
gi = sorted([e for e in ev['events'] if e['kind'] == 'giant'], key=lambda e: e['t'])
for k, e in enumerate(gi):
    put(boom([43, 45, 47, 48][k], 1 + 0.4 * k), e['t'], 0.45 + 0.1 * k, rev=0.3)
    put(click(0.2), e['t'], 0.5)
# whoosh as the last giant falls, then THE impact on the drop
put(riser(ev['land'] - gi[-1]['t'], 150, 2500) * 1.0, gi[-1]['t'], 0.4)
L = ev['land']
put(boom(31, 2.5), L, 1.0)
put(crash(), L, 0.45, rev=0.4)
put(kick(), L, 1.0)
# confetti sparkles
for k in range(60):
    t = L + 0.05 + rng.random() * 1.8
    put(pluck(int(rng.choice([84, 88, 91, 96, 100])), 0.25), t, 0.05 * (1 - (t - L) / 2), pan=rng.uniform(-0.9, 0.9), rev=0.5)

# ---------- mix ----------
ir_n = int(1.6 * SR)
ir = rng.standard_normal((ir_n, 2)) * np.exp(-tt(ir_n) * 4.0)[:, None]
ir = np.stack([lp(ir[:, 0], 6000), lp(ir[:, 1], 6000)], 1) * 0.08
rv = np.stack([fftconvolve(wet[:, i], ir[:, i])[:N] for i in range(2)], 1)
duck = 1 - 0.55 * lp(side, 30)
mix = dry * duck[:, None] ** 0.0 + rv
# apply ducking only to non-kick content would need separate buses; gentle global pump:
mix = mix * (1 - 0.18 * lp(side, 25))[:, None]
mix = np.tanh(mix * 1.3) / np.tanh(1.3)
mix = mix[:int(END * SR)]
fade = int(0.4 * SR); mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
mix = mix / np.max(np.abs(mix)) * 0.89
wavfile.write('/home/claude/domino/music.wav', SR, (mix * 32767).astype(np.int16))
print('music', len(mix) / SR)
