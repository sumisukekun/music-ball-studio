import json, glob, re, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

S = json.load(open('/home/claude/bach/score.json'))
SR = 44100
N = int(S['end'] * SR)
rng = np.random.default_rng(5)
mix = np.zeros((N, 2))

# ---------- Salamander Grand Piano sampler ----------
NAMES = {'C': 0, 'D#': 3, 'F#': 6, 'A': 9}
samples = {}   # (midi, layer) -> stereo float array
for f in glob.glob('/home/claude/bach/samples/*.wav'):
    m = re.match(r'.*/([A-G]#?)(\d)v(\d+)\.wav', f)
    note, octv, vel = m.group(1), int(m.group(2)), int(m.group(3))
    midi = 12 * (octv + 1) + NAMES[note]
    sr, x = wavfile.read(f)
    x = x.astype(np.float64) / 32768
    if x.ndim == 1: x = np.stack([x, x], 1)
    samples[(midi, vel)] = x
roots = sorted({k[0] for k in samples}); layers = sorted({k[1] for k in samples})

def piano(m, vel, dur):
    """vel 0..1 ; dur = time key is held before damper"""
    layer = layers[min(int(vel * len(layers)), len(layers) - 1)]
    root = min(roots, key=lambda r: abs(r - m))
    x = samples[(root, layer)]
    ratio = 2 ** ((m - root) / 12)
    n_out = int(min(dur + 0.6, len(x) / SR / ratio) * SR)
    src = np.arange(n_out) * ratio
    y = np.stack([np.interp(src, np.arange(len(x)), x[:, c]) for c in range(2)], 1)
    rel = int(dur * SR)
    if rel < n_out:
        tail = n_out - rel
        y[rel:] *= np.exp(-np.arange(tail) / SR * 9)[:, None]
    # within-layer volume shaping
    gain = 0.55 + 0.9 * vel
    return y * gain

def put(st, t, g=1.0):
    i = int(t * SR)
    if i >= N: return
    st = st[:N - i]
    mix[i:i + len(st)] += st * g

notes = S['notes']
for n in notes:
    b, k = n['bar'], n['k']
    phrase = 0.5 + 0.18 * np.sin(np.pi * min(b, 18) / 18) + 0.06 * np.sin(np.pi * (b % 4) / 4)
    acc = 0.12 if k % 8 == 0 else (0.05 if k % 8 == 1 else 0.0)
    vel = np.clip(phrase + acc + rng.normal(0, 0.03), 0.2, 0.95)
    if b == 18: vel *= 0.85
    put(piano(n['midi'], vel, n['end'] - n['t']), n['t'] + rng.normal(0, 0.004))

# final rolled chord, synced to the 24 petal dominoes
FT = S['final_t']
for j, m in enumerate(S['final_chord']):
    put(piano(m, 0.62 - 0.02 * j, 5.5 - j * 0.05), FT + j * 2 * 0.06)
for j in range(10, 22):
    put(piano([91, 88, 84, 91, 96, 88, 93][j % 7], 0.18, 2.5), FT + j * 0.06, 0.35)

# ---------- soft string pad (chord of each bar) ----------
def lp(x, fc): return sosfilt(butter(2, fc, 'low', fs=SR, output='sos'), x)
from score import BARS  # noqa
bar_t = {}
for n in notes:
    bar_t.setdefault(n['bar'], [n['t'], n['end']])
    bar_t[n['bar']][1] = n['end']
pad = np.zeros(N)
for b, (t0, t1) in bar_t.items():
    ch = BARS[b]
    n = int((t1 - t0 + 0.8) * SR); t = np.arange(n) / SR
    s = np.zeros(n)
    for m in (ch[0] - 12, ch[2], ch[3]):
        f = 440 * 2 ** ((m - 69) / 12)
        for dt in (-0.003, 0.0035):
            s += np.sin(2 * np.pi * f * (1 + dt) * t + 0.3 * np.sin(2 * np.pi * 5 * t))
    env = np.minimum(t / 0.7, 1) * np.clip((t1 - t0 + 0.8 - t) / 0.8, 0, 1)
    i = int(t0 * SR); pad[i:i + n] += (s * env)[:N - i]
pad = lp(pad, 1800) * 0.012
mix += np.stack([pad, pad], 1)

# ---------- delicate domino ticks ----------
tick_n = int(0.02 * SR)
for n in notes:
    tk = sosfilt(butter(2, [2500, 9000], 'band', fs=SR, output='sos'), rng.standard_normal(tick_n)) * np.exp(-np.arange(tick_n) / SR * 300)
    put(np.stack([tk, tk], 1), n['t'], 0.012)

# ---------- hall reverb ----------
ir_n = int(2.8 * SR); t = np.arange(ir_n) / SR
ir = rng.standard_normal((ir_n, 2)) * np.exp(-t * 2.4)[:, None]
ir = np.stack([lp(ir[:, 0], 5000), lp(ir[:, 1], 5000)], 1)
ir[:int(0.02 * SR)] = 0
ir /= np.sqrt((ir ** 2).sum(0))
wet = np.stack([fftconvolve(mix[:, c], ir[:, c])[:N] for c in range(2)], 1)
out = mix * 0.85 + wet * 0.45
fade = int(1.0 * SR); out[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
out = out / np.abs(out).max() * 0.89
wavfile.write('/home/claude/bach/music.wav', SR, (out * 32767).astype(np.int16))
print('ok', N / SR)
