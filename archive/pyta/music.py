import json, numpy as np
from scipy.signal import butter, sosfilt, fftconvolve
from scipy.io import wavfile

SR = 44100; END = 19.0; N = int(SR * END)
B = 0.5  # beat (120 BPM)
rng = np.random.default_rng(11)
dry = np.zeros((N, 2)); wet = np.zeros((N, 2))
b2 = json.load(open('/home/claude/pyta/b2.json'))

def mtof(m): return 440 * 2 ** ((m - 69) / 12)
def tt(n): return np.arange(n) / SR
def lp(x, fc): return sosfilt(butter(2, fc, 'low', fs=SR, output='sos'), x)
def hp(x, fc): return sosfilt(butter(2, fc, 'high', fs=SR, output='sos'), x)
def bp(x, lo, hi): return sosfilt(butter(2, [lo, hi], 'band', fs=SR, output='sos'), x)
def put(sig, t, gain=1.0, pan=0.0, rev=0.0):
    i = int(t * SR)
    if i >= N: return
    sig = sig[:N - i]
    st = np.stack([sig * np.cos((pan + 1) * np.pi / 4), sig * np.sin((pan + 1) * np.pi / 4)], 1) * gain
    dry[i:i + len(sig)] += st
    if rev: wet[i:i + len(sig)] += st * rev

# ---- instruments ----
def kick():
    n = int(.35 * SR); t = tt(n); f = 50 + 100 * np.exp(-t * 30)
    return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) * 1.5)
def rim():
    n = int(.12 * SR); t = tt(n)
    return (bp(rng.standard_normal(n), 1800, 6000) * 0.6 + np.sin(2 * np.pi * 820 * t)) * np.exp(-t * 45)
def shaker():
    n = int(.08 * SR); t = tt(n)
    return hp(rng.standard_normal(n), 6000) * np.minimum(t * 300, 1) * np.exp(-t * 45)
def woodblock(f=1200):
    n = int(.15 * SR); t = tt(n)
    return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2.7 * t)) * np.exp(-t * 40)
def tom(m):
    n = int(.4 * SR); t = tt(n); f = mtof(m) * (1 + 0.5 * np.exp(-t * 25))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) + bp(rng.standard_normal(n), 300, 2000) * np.exp(-t * 60) * 0.3
def marimba(m, d=0.7):
    n = int(d * SR); t = tt(n); f = mtof(m)
    return (np.sin(2 * np.pi * f * t) * np.exp(-t * 5.5) + 0.35 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t * 28)
            + 0.12 * np.sin(2 * np.pi * 9.8 * f * t) * np.exp(-t * 70)) * np.minimum(t * 1500, 1)
def glock(m, d=1.2):
    n = int(d * SR); t = tt(n); f = mtof(m)
    return (np.sin(2 * np.pi * f * t) * np.exp(-t * 3) + 0.3 * np.sin(2 * np.pi * 2.76 * f * t) * np.exp(-t * 9)
            + 0.2 * np.sin(2 * np.pi * 5.4 * f * t) * np.exp(-t * 18)) * np.minimum(t * 3000, 1)
def pizz(m, d=0.35):
    n = int(d * SR); t = tt(n); f = mtof(m)
    s = sum(np.sin(2 * np.pi * f * h * t) * np.exp(-t * (8 + 6 * h)) / h for h in range(1, 6))
    return s * np.minimum(t * 800, 1)
def uke(ms, d=0.4):
    out = np.zeros(int((d + 0.08) * SR))
    for k, m in enumerate(ms):
        p = pizz(m, d) * 0.5; i = int(k * 0.012 * SR); out[i:i + len(p)] += p[:len(out) - i]
    return out
def click():
    n = int(.03 * SR); t = tt(n)
    return bp(rng.standard_normal(n), 2000, 7000) * np.exp(-t * 250)
def boing(f0=180):
    n = int(.6 * SR); t = tt(n)
    f = f0 * (1 + 1.6 * (1 - np.exp(-t * 9))) * (1 + 0.08 * np.sin(2 * np.pi * 22 * t) * np.exp(-t * 4))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6)
def roll(d):
    n = int(d * SR); t = tt(n)
    return lp(rng.standard_normal(n), 250) * (0.6 + 0.4 * np.sin(2 * np.pi * 9 * t)) * np.minimum(t * 20, 1) * np.minimum((d - t) * 20, 1).clip(0, 1)
def plop():
    n = int(.35 * SR); t = tt(n); f = 300 * np.exp(-t * 9) + 140
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 12)
def ding(m=88):
    return glock(m, 1.5)
def creak(d):
    n = int(d * SR); t = tt(n); f = 420 + 160 * np.sin(2 * np.pi * 3 * t)
    s = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * (1 + 0.5 * rng.standard_normal(n))
    return bp(s, 400, 2500) * 0.2 * np.minimum((d - t) * 10, 1).clip(0, 1)
def snare():
    n = int(.2 * SR); t = tt(n)
    return bp(rng.standard_normal(n), 1500, 8000) * np.exp(-t * 25) + np.sin(2 * np.pi * 200 * t) * np.exp(-t * 35) * 0.4
def crash():
    n = int(2.4 * SR); t = tt(n)
    return hp(rng.standard_normal(n), 4500) * np.exp(-t * 2.4)
def brass(ms, d):
    n = int(d * SR); t = tt(n); s = np.zeros(n)
    for m in ms:
        for dt in (-0.004, 0.004):
            ph = (mtof(m) * (1 + dt) * t) % 1
            s += (2 * ph - 1)
    cut = 600 + 3000 * np.minimum(t * 12, 1)
    s = lp(s, 3000) * np.minimum(t * 40, 1) * np.minimum((d - t) * 15, 1).clip(0, 1)
    return s / len(ms)

# ---- harmony: bars of 2 s ----
CH = {0: [60, 64, 67], 1: [60, 64, 67], 2: [57, 60, 64], 3: [53, 57, 60], 4: [55, 59, 62],
      5: [60, 64, 67], 6: [53, 57, 60], 7: [60, 64, 67], 8: [53, 57, 60]}
for bar in range(9):
    t0 = bar * 2.0; ch = CH[bar]
    if bar == 0:
        for q in range(3): put(woodblock(1500 if q < 2 else 1500), t0 + q * B, 0.5)
        put(woodblock(2000), t0 + 1.5, 0.6)
        continue
    full = bar >= 7
    for q in range(4):
        tq = t0 + q * B
        if q in (0, 2) or full: put(kick(), tq, 0.75)
        if q in (1, 3): put(rim() if not full else snare(), tq, 0.35 if not full else 0.4, rev=0.2)
        for e in (0, 1): put(shaker(), tq + e * B / 2, 0.12 if e else 0.07, pan=0.35)
    # bouncy bass (root, fifth)
    root = ch[0] - 24
    for k, (dt, m) in enumerate([(0, root), (0.75, root + 7), (1.0, root + 12), (1.5, root + 7)]):
        if bar < 6 or full or k == 0:
            put(pizz(m, 0.3) * 1.2, t0 + dt, 0.55)
    # ukulele chord strums on offbeats
    if bar != 6:
        for dt in (0.25, 0.75, 1.25, 1.75):
            put(uke([m + 12 for m in ch], 0.3), t0 + dt, 0.18, pan=-0.3, rev=0.15)

# ---- machine events (all on the beat grid) ----
put(woodblock(900), 1.5, 0.4); put(click(), 1.5, 0.5)                 # gate opens
put(roll(0.6), 1.5, 0.18)
for k, t in enumerate([2.5, 3.5, 4.5, 5.5]):                            # ramp landings
    put(tom([55, 52, 48, 45][k]), t, 0.6, pan=[0.3, -0.3, 0.3, -0.3][k])
    put(roll(0.55), t + 0.03, 0.15)
scale_up = [60, 62, 64, 65, 67, 69, 71, 72]
for i in range(8):                                                       # dominoes
    t = 6.0 + 0.25 * i
    put(marimba(scale_up[i] + 12), t, 0.5, pan=-0.4 + 0.11 * i, rev=0.25)
    put(click(), t, 0.4)
put(kick(), 8.0, 0.9); put(boing(160), 8.0, 0.5)                         # seesaw launch
# slide whistle follows ball 2's height while it flies
z = np.array(b2['P2z']); fps = b2['fps']
i0, i1 = int(8.05 * SR), int(9.0 * SR)
tz = np.arange(i0, i1) / SR
zz = np.interp(tz, np.arange(len(z)) / fps, z)
f = 700 + (zz - zz.min()) * 160
ph = 2 * np.pi * np.cumsum(f) / SR
wh = (np.sin(ph) + 0.1 * rng.standard_normal(len(ph)) * 0.3) * np.minimum((tz - tz[0]) * 20, 1) * np.minimum((tz[-1] - tz) * 30, 1)
put(wh, 8.05, 0.22, rev=0.3)
xylo = [84, 83, 81, 79, 77, 76, 74, 72]                                   # stairs: descending scale
for k, m in enumerate(xylo):
    put(glock(m), 9.0 + 0.25 * k, 0.45, pan=0.4 - 0.1 * k, rev=0.35)
put(tom(50), 11.0, 0.35); put(roll(0.6), 11.0, 0.18)
put(plop(), 12.0, 0.7); put(kick(), 12.0, 0.6)                          # into the cup
put(creak(0.5), 12.0, 0.5)
put(ding(91), 12.5, 0.35, rev=0.4)                                        # gate up
put(roll(1.5) * 1.5, 12.5, 0.2)
for k in range(12):                                                       # build-up to the goal
    put(snare(), 12.5 + k * 0.125, 0.08 + 0.025 * k, rev=0.15)
# GOAL!
put(kick(), 14.0, 1.0); put(crash(), 14.0, 0.4, rev=0.3); put(boing(260), 14.0, 0.4)
put(brass([72, 76, 79], 0.35), 14.0, 0.35, rev=0.3)
put(brass([72, 76, 79, 84], 0.9), 14.5, 0.35, rev=0.3)
for k in range(30):
    put(glock(int(rng.choice([96, 98, 100, 103, 105])), 0.4), 14.0 + rng.random() * 1.5, 0.06, pan=rng.uniform(-.8, .8), rev=0.5)
# victory melody bars 7-8
mel = [(15.0, 76), (15.25, 79), (15.5, 84), (16.0, 81), (16.25, 79), (16.5, 77), (16.75, 74), (17.0, 77), (17.25, 76), (17.5, 74), (17.75, 71)]
for t, m in mel: put(marimba(m, 0.5), t, 0.45, pan=0.15, rev=0.3)
# ending chord
put(brass([60, 64, 67, 72], 0.8), 18.0, 0.45, rev=0.5)
put(glock(84, 1.0), 18.0, 0.4, rev=0.5); put(kick(), 18.0, 0.9); put(crash(), 18.0, 0.25)

ir_n = int(1.3 * SR)
ir = rng.standard_normal((ir_n, 2)) * np.exp(-tt(ir_n) * 4.5)[:, None] * 0.07
ir = np.stack([lp(ir[:, 0], 7000), lp(ir[:, 1], 7000)], 1)
mix = dry + np.stack([fftconvolve(wet[:, i], ir[:, i])[:N] for i in range(2)], 1)
mix = np.tanh(mix * 1.1) / np.tanh(1.1)
fade = int(0.4 * SR); mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
mix = mix / np.abs(mix).max() * 0.89
wavfile.write('/home/claude/pyta/music.wav', SR, (mix * 32767).astype(np.int16))
print('ok')
