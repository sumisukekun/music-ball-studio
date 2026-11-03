import json, glob, re, numpy as np, mido
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

T = json.load(open('/home/claude/vegas2/paths.json'))
SR = 44100; END = T['END']; N = int(END * SR)
rng = np.random.default_rng(21)
mix = np.zeros((N, 2))

def lp(x, fc): return sosfilt(butter(2, fc, 'low', fs=SR, output='sos'), x)
def hp(x, fc): return sosfilt(butter(2, fc, 'high', fs=SR, output='sos'), x)
def bp(x, a, b): return sosfilt(butter(2, [a, b], 'band', fs=SR, output='sos'), x)
def put(sig, t, g=1.0, pan=0.0):
    if sig.ndim == 1:
        sig = np.stack([sig * np.cos((pan + 1) * np.pi / 4), sig * np.sin((pan + 1) * np.pi / 4)], 1) * 1.414
    i = int(t * SR)
    if i >= N or i < 0: return
    sig = sig[:N - i]; mix[i:i + len(sig)] += sig * g

# ---------- piano sampler (Salamander, public domain) ----------
NAMES = {'C': 0, 'D#': 3, 'F#': 6, 'A': 9}
samples = {}
for f in glob.glob('/home/claude/bach/samples/*.wav'):
    m = re.match(r'.*/([A-G]#?)(\d)v(\d+)\.wav', f)
    sr, x = wavfile.read(f); x = x.astype(np.float64) / 32768
    if x.ndim == 1: x = np.stack([x, x], 1)
    samples[(12 * (int(m.group(2)) + 1) + NAMES[m.group(1)], int(m.group(3)))] = x
roots = sorted({k[0] for k in samples}); layers = sorted({k[1] for k in samples})
def piano(m, vel, dur):
    layer = layers[min(int(vel * len(layers)), len(layers) - 1)]
    root = min(roots, key=lambda r: abs(r - m)); x = samples[(root, layer)]
    ratio = 2 ** ((m - root) / 12)
    n = int(min(dur + 0.35, len(x) / SR / ratio) * SR)
    y = np.stack([np.interp(np.arange(n) * ratio, np.arange(len(x)), x[:, c]) for c in range(2)], 1)
    r = int(dur * SR)
    if r < n: y[r:] *= np.exp(-np.arange(n - r) / SR * 14)[:, None]
    return y * (0.5 + 0.8 * vel)

def tick_snd(f, dec=180, n=0.06):
    k = int(n * SR); t = np.arange(k) / SR
    return (np.sin(2 * np.pi * f * t) * 0.6 + bp(rng.standard_normal(k), 1500, 7000) * 0.5) * np.exp(-t * dec)
def boing():
    k = int(0.35 * SR); t = np.arange(k) / SR
    f = 600 * (1 + 0.6 * np.exp(-t * 18))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
def clack():
    k = int(0.08 * SR); t = np.arange(k) / SR
    return bp(rng.standard_normal(k), 600, 3500) * np.exp(-t * 90) + np.sin(2 * np.pi * 420 * t) * np.exp(-t * 70) * 0.5
def bell(f, d=1.2):
    k = int(d * SR); t = np.arange(k) / SR
    return (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 4) + 0.3 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 8)) * np.exp(-t * 3)
# ---------- every bounce plays its notes ----------
for b, p in enumerate(T['paths']):
    for k, (t, grp) in enumerate(zip(p['times'], p['notes'])):
        last = k == len(p['times']) - 1
        for m, dur in grp:
            vel = (0.62 if b == 0 else 0.5) + rng.normal(0, 0.03) + (0.15 if last else 0)
            put(piano(m, float(np.clip(vel, 0.2, 0.95)), 1.4 if last else max(dur, 0.12)), t, 0.55)
        put(tick_snd(2600 if b == 0 else 1700, 220, 0.03), t, 0.05, pan=0.0)
# JACKPOT: slot-machine bells, coin shower, applause
TL = T['T_END']
for k in range(36):
    put(bell([1319, 1568][k % 2], 0.25) * 0.8, TL + k * 0.07, 0.18, pan=0.3 if k % 2 else -0.3)
for k in range(220):
    tt_ = TL + 0.1 + rng.exponential(1.2)
    put(tick_snd(3500 + 2500 * rng.random(), 140, 0.05), tt_, 0.05 + 0.05 * rng.random(), pan=rng.uniform(-0.9, 0.9))
# applause (many random claps)
k = int(7 * SR); app = np.zeros(k)
for c in range(2600):
    st = int(rng.uniform(0, 6.8) * SR); ln = int(0.03 * SR)
    app[st:st + ln] += bp(rng.standard_normal(ln), 800, 5000) * np.exp(-np.arange(ln) / SR * 120) * rng.uniform(0.3, 1)
app *= np.minimum(np.arange(k) / SR / 0.6, 1) * np.clip((7 - np.arange(k) / SR) / 2.5, 0, 1)
put(np.stack([app, np.roll(app, 731)], 1) * 0.05, TL + 0.2)
# ta-da stinger: rolled C major in the piano
for j, m in enumerate([36, 48, 55, 60, 64, 67, 72, 76, 79, 84]):
    put(piano(m, 0.8, 3.5), TL + 0.25 + j * 0.03, 0.5)

# room reverb
ir_n = int(1.4 * SR); t = np.arange(ir_n) / SR
ir = rng.standard_normal((ir_n, 2)) * np.exp(-t * 4)[:, None]; ir[:int(0.015 * SR)] = 0
ir /= np.sqrt((ir ** 2).sum(0))
wet = np.stack([fftconvolve(mix[:, c], ir[:, c])[:N] for c in range(2)], 1)
out = mix + wet * 0.22
fade = int(1.2 * SR); out[-fade:] *= np.linspace(1, 0, fade)[:, None]
out = np.tanh(out / np.abs(out).max() * 1.2) * 0.89
wavfile.write('/home/claude/vegas2/music.wav', SR, (out * 32767).astype(np.int16))
print('ok', END)
