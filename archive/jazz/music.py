import json, glob, re, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve, lfilter
A = json.load(open('/home/claude/jazz/arr.json'))
SR = 44100; END = A['END']; N = int(END * SR)
rng = np.random.default_rng(77); mix = np.zeros((N, 2))
def lp(x, fc): return sosfilt(butter(2, fc, 'low', fs=SR, output='sos'), x)
def hp(x, fc): return sosfilt(butter(2, fc, 'high', fs=SR, output='sos'), x)
def bp(x, a, b): return sosfilt(butter(2, [a, b], 'band', fs=SR, output='sos'), x)
def put(sig, t, g=1.0, pan=0.0):
    if sig.ndim == 1:
        sig = np.stack([sig * np.cos((pan + 1) * np.pi / 4), sig * np.sin((pan + 1) * np.pi / 4)], 1) * 1.414
    i = int(t * SR)
    if i >= N: return
    sig = sig[:N - i]; mix[i:i + len(sig)] += sig * g
NAMES = {'C': 0, 'D#': 3, 'F#': 6, 'A': 9}; samples = {}
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
    n = int(min(dur + 0.45, len(x) / SR / ratio) * SR)
    y = np.stack([np.interp(np.arange(n) * ratio, np.arange(len(x)), x[:, c]) for c in range(2)], 1)
    r = int(dur * SR)
    if r < n: y[r:] *= np.exp(-np.arange(n - r) / SR * 9)[:, None]
    return y * (0.4 + 0.9 * vel)
def upright(m, dur):
    f = 440 * 2 ** ((m - 69) / 12); n = int((dur + 0.3) * SR); P = int(SR / f)
    buf = lp(rng.standard_normal(P), 1200)
    out = np.zeros(n); y = np.concatenate([buf, np.zeros(n)])
    for i in range(P, n + P):
        y[i] = 0.5 * (y[i - P] + y[i - P + 1]) * 0.996
    out = y[P:n + P]
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * f * t) * np.exp(-t * 3)
    s = lp(out * 0.8 + body * 0.6, 900) * np.minimum(t * 300, 1)
    r = int(dur * SR); s[r:] *= np.exp(-np.arange(n - r) / SR * 12)
    return s / (np.abs(s).max() + 1e-9)
EM = A['end_music']
for e in A['events']:
    v = e['voice']
    if v == 'bass': put(upright(e['midi'], e['dur']), e['t'], 0.42, -0.15)
    elif v == 'mel': put(piano(e['midi'], float(np.clip(0.55 + rng.normal(0, 0.05), 0.2, 0.9)), e['dur']), e['t'] + rng.normal(0, 0.004), 0.62, 0.15)
    elif v == 'comp': put(piano(e['midi'], float(np.clip(0.3 + rng.normal(0, 0.03), 0.1, 0.6)), e['dur']), e['t'] + rng.normal(0, 0.006), 0.28, -0.05)
    else: put(piano(e['midi'], 0.6, e['dur']), e['t'], 0.55, 0.1)
# brushes + ride + hi-hat foot
BEAT = 60 / A['bpm']; T0 = A['T0']
def swish(d=0.45, accent=1.0):
    n = int(d * SR); t = np.arange(n) / SR
    return bp(rng.standard_normal(n), 2500, 9000) * np.sin(np.pi * t / d) ** 1.5 * accent
def ride():
    n = int(0.9 * SR); t = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) for f in (3150, 4270, 5490, 6630, 8100))
    return (s / 5 * 0.6 + hp(rng.standard_normal(n), 7000) * 0.4) * np.exp(-t * 5)
def chick():
    n = int(0.06 * SR); t = np.arange(n) / SR
    return hp(rng.standard_normal(n), 6000) * np.exp(-t * 70)
nb = A['bars'] * 4
for k in range(nb):
    tb = T0 + k * BEAT
    put(swish(BEAT * 0.95, 1.0 if k % 2 else 0.7), tb, 0.018, -0.4)
    put(ride(), tb, 0.014, 0.45)
    if k % 2 == 1:
        put(ride(), tb + 0.667 * BEAT, 0.01, 0.45); put(chick(), tb, 0.03, 0.3)
put(ride(), EM, 0.05, 0.45)
ir_n = int(2.0 * SR); t = np.arange(ir_n) / SR
ir = rng.standard_normal((ir_n, 2)) * np.exp(-t * 3.0)[:, None]; ir[:int(0.02 * SR)] = 0
ir = np.stack([lp(ir[:, 0], 5000), lp(ir[:, 1], 5000)], 1); ir /= np.sqrt((ir ** 2).sum(0))
wet = np.stack([fftconvolve(mix[:, c], ir[:, c])[:N] for c in range(2)], 1)
out = mix + wet * 0.28
fade = int(1.5 * SR); out[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
out = np.tanh(out / np.abs(out).max() * 1.1) * 0.89
wavfile.write('/home/claude/jazz/music.wav', SR, (out * 32767).astype(np.int16))
print('ok', END)
