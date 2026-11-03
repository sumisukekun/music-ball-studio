import json, glob, re, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve
A = json.load(open('/home/claude/hd5/arr.json'))
SR = 44100; END = A['END']; N = int(END * SR)
rng = np.random.default_rng(55); mix = np.zeros((N, 2))
def lp(x, fc): return sosfilt(butter(2, fc, 'low', fs=SR, output='sos'), x)
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
    n = int(min(dur + 0.35, len(x) / SR / ratio) * SR)
    y = np.stack([np.interp(np.arange(n) * ratio, np.arange(len(x)), x[:, c]) for c in range(2)], 1)
    r = int(dur * SR)
    if r < n: y[r:] *= np.exp(-np.arange(n - r) / SR * 13)[:, None]
    return y * (0.4 + 0.9 * vel)
EM = A['end_music']
for e in A['events']:
    v = e['voice']
    vel = {'mel': 0.68, 'mel2': 0.5, 'bass': 0.55, 'chord': 0.36, 'coda': 0.92}[v] + rng.normal(0, 0.03)
    g = {'mel': 0.6, 'mel2': 0.4, 'bass': 0.5, 'chord': 0.33, 'coda': 0.6}[v]
    pan = {'mel': 0.15, 'mel2': 0.1, 'bass': -0.25, 'chord': -0.1, 'coda': 0.0}[v]
    put(piano(e['midi'], float(np.clip(vel, 0.1, 0.97)), e['dur']), e['t'] + rng.normal(0, 0.003), g, pan)
# glassy tick on each ball impact
def tick(f):
    k = int(0.12 * SR); t = np.arange(k) / SR
    return (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.4 * t)) * np.exp(-t * 40)
for e in A['events']:
    if e['voice'] == 'mel': put(tick(2600 + 15 * (e['midi'] - 60)), e['t'], 0.03, 0.2)
    elif e['voice'] == 'bass': put(tick(1500), e['t'], 0.02, -0.3)
ir_n = int(1.8 * SR); t = np.arange(ir_n) / SR
ir = rng.standard_normal((ir_n, 2)) * np.exp(-t * 3.2)[:, None]; ir[:int(0.02 * SR)] = 0
ir = np.stack([lp(ir[:, 0], 6000), lp(ir[:, 1], 6000)], 1); ir /= np.sqrt((ir ** 2).sum(0))
wet = np.stack([fftconvolve(mix[:, c], ir[:, c])[:N] for c in range(2)], 1)
out = mix + wet * 0.3
fade = int(1.5 * SR); out[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
out = np.tanh(out / np.abs(out).max() * 1.15) * 0.89
wavfile.write('/home/claude/hd5/music.wav', SR, (out * 32767).astype(np.int16))
print('ok', END)
