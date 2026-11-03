import json, glob, re, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

S = json.load(open('/home/claude/clair/score.json'))
SR = 44100
N = int(S['end'] * SR)
rng = np.random.default_rng(8)
mix = np.zeros((N, 2))

NAMES = {'C': 0, 'D#': 3, 'F#': 6, 'A': 9}
samples = {}
for f in glob.glob('/home/claude/clair/samples/*.wav'):
    m = re.match(r'.*/([A-G]#?)(\d)v(\d+)\.wav', f)
    midi = 12 * (int(m.group(2)) + 1) + NAMES[m.group(1)]
    sr, x = wavfile.read(f)
    x = x.astype(np.float64) / 32768
    if x.ndim == 1: x = np.stack([x, x], 1)
    samples[(midi, int(m.group(3)))] = x
roots = sorted({k[0] for k in samples}); layers = sorted({k[1] for k in samples})

def piano(m, vel, dur):
    layer = layers[min(int(vel * len(layers)), len(layers) - 1)]
    root = min(roots, key=lambda r: abs(r - m))
    x = samples[(root, layer)]
    ratio = 2 ** ((m - root) / 12)
    n_out = int(min(dur + 0.9, len(x) / SR / ratio) * SR)
    src = np.arange(n_out) * ratio
    y = np.stack([np.interp(src, np.arange(len(x)), x[:, c]) for c in range(2)], 1)
    rel = int(dur * SR)
    if rel < n_out:
        y[rel:] *= np.exp(-np.arange(n_out - rel) / SR * 6)[:, None]
    return y * (0.45 + 0.9 * vel)

def put(st, t, g=1.0):
    i = int(t * SR)
    if i >= N: return
    st = st[:N - i]
    mix[i:i + len(st)] += st * g

notes = S['notes']
# melody = highest note of the upper staff at each onset
top = {}
for n in notes:
    if n['upper']: top[n['t']] = max(top.get(n['t'], 0), n['midi'])
for n in notes:
    b = n['bar']
    phrase = 0.30 + 0.10 * np.sin(np.pi * ((b % 4) + 0.5) / 4) + (0.06 if 8 <= b <= 12 else 0)
    if n['upper'] and n['midi'] == top.get(n['t']): phrase += 0.12
    if not n['upper']: phrase -= 0.06
    vel = float(np.clip(phrase + rng.normal(0, 0.025), 0.12, 0.8))
    put(piano(n['midi'], vel, n['end'] - n['t']), n['t'] + rng.normal(0, 0.006))

# coda: soft rolled D-flat major chord
FT = S['final_t']
for j, m in enumerate(S['coda']):
    put(piano(m, 0.34 + (0.08 if j == len(S['coda']) - 1 else 0), 5.2 - 0.1 * j), FT + j * 0.07)

# hall reverb (long, soft)
def lp(x, fc): return sosfilt(butter(2, fc, 'low', fs=SR, output='sos'), x)
ir_n = int(3.4 * SR); t = np.arange(ir_n) / SR
ir = rng.standard_normal((ir_n, 2)) * np.exp(-t * 1.9)[:, None]
ir = np.stack([lp(ir[:, 0], 4500), lp(ir[:, 1], 4500)], 1)
ir[:int(0.025 * SR)] = 0
ir /= np.sqrt((ir ** 2).sum(0))
wet = np.stack([fftconvolve(mix[:, c], ir[:, c])[:N] for c in range(2)], 1)
out = mix * 0.8 + wet * 0.55
fade = int(1.5 * SR); out[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
out = out / np.abs(out).max() * 0.89
wavfile.write('/home/claude/clair/music.wav', SR, (out * 32767).astype(np.int16))
print('ok', N / SR)
