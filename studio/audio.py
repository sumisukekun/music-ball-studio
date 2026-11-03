"""Render the soundtrack from arr.json.

Instruments: Salamander Grand Piano samples (public domain), a Karplus-Strong upright bass,
synthesised brushes/ride, glassy ticks for bounces, and a convolution hall reverb.
    python studio/audio.py <config.json> <arr.json> <out.wav>
"""
import json, glob, re, sys, os, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

CFG_PATH, ARR_PATH, OUT = sys.argv[-3:]
CFG = json.load(open(CFG_PATH)); AU = CFG.get('audio', {})
A = json.load(open(ARR_PATH))
SR = 44100; END = A['END']; N = int(END * SR)
rng = np.random.default_rng(AU.get('seed', 77)); mix = np.zeros((N, 2))
SAMPLES = os.environ.get('MBS_SAMPLES', os.path.join(os.path.dirname(__file__), '..', 'samples'))

def lp(x, fc): return sosfilt(butter(2, fc, 'low', fs=SR, output='sos'), x)
def hp(x, fc): return sosfilt(butter(2, fc, 'high', fs=SR, output='sos'), x)
def bp(x, a, b): return sosfilt(butter(2, [a, b], 'band', fs=SR, output='sos'), x)
def put(sig, t, g=1.0, pan=0.0):
    if sig.ndim == 1:
        sig = np.stack([sig * np.cos((pan + 1) * np.pi / 4), sig * np.sin((pan + 1) * np.pi / 4)], 1) * 1.414
    i = int(t * SR)
    if i >= N or i < 0: return
    sig = sig[:N - i]; mix[i:i + len(sig)] += sig * g

# --- piano sampler ---
NAMES = {'C': 0, 'D#': 3, 'F#': 6, 'A': 9}; samples = {}
for f in glob.glob(os.path.join(SAMPLES, '*.wav')):
    m = re.match(r'.*/([A-G]#?)(\d)v(\d+)\.wav', f)
    if not m: continue
    sr, x = wavfile.read(f); x = x.astype(np.float64) / 32768
    if x.ndim == 1: x = np.stack([x, x], 1)
    samples[(12 * (int(m.group(2)) + 1) + NAMES[m.group(1)], int(m.group(3)))] = x
assert samples, f'no piano samples in {SAMPLES} - run scripts/fetch_samples.sh'
roots = sorted({k[0] for k in samples}); layers = sorted({k[1] for k in samples})
def piano(m, vel, dur, release=9):
    layer = layers[min(int(vel * len(layers)), len(layers) - 1)]
    root = min(roots, key=lambda r: abs(r - m)); x = samples[(root, layer)]
    ratio = 2 ** ((m - root) / 12)
    n = int(min(dur + 0.45, len(x) / SR / ratio) * SR)
    y = np.stack([np.interp(np.arange(n) * ratio, np.arange(len(x)), x[:, c]) for c in range(2)], 1)
    r = int(dur * SR)
    if r < n: y[r:] *= np.exp(-np.arange(n - r) / SR * release)[:, None]
    return y * (0.4 + 0.9 * vel)
# --- upright bass (Karplus-Strong) ---
def upright(m, dur):
    f = 440 * 2 ** ((m - 69) / 12); n = int((dur + 0.3) * SR); P = int(SR / f)
    y = np.concatenate([lp(rng.standard_normal(P), 1200), np.zeros(n)])
    for i in range(P, n + P): y[i] = 0.5 * (y[i - P] + y[i - P + 1]) * 0.996
    t = np.arange(n) / SR
    s = lp(y[P:n + P] * 0.8 + np.sin(2 * np.pi * f * t) * np.exp(-t * 3) * 0.6, 900) * np.minimum(t * 300, 1)
    r = int(dur * SR); s[r:] *= np.exp(-np.arange(n - r) / SR * 12)
    return s / (np.abs(s).max() + 1e-9)
def tick(f):
    k = int(0.12 * SR); t = np.arange(k) / SR
    return (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.4 * t)) * np.exp(-t * 40)

VO = AU['voices']
for e in A['events']:
    v = VO.get(e['voice'])
    if not v: continue
    vel = float(np.clip(v.get('vel', 0.5) + rng.normal(0, v.get('vel_jitter', 0.04)), 0.08, 0.97))
    t = e['t'] + rng.normal(0, v.get('time_jitter', 0.004))
    if v['inst'] == 'piano': put(piano(e['midi'], vel, e['dur'], v.get('release', 9)), t, v.get('gain', 0.5), v.get('pan', 0))
    elif v['inst'] == 'upright': put(upright(e['midi'], e['dur']), e['t'], v.get('gain', 0.42), v.get('pan', -0.15))
    if 'tick' in v: put(tick(v['tick'][1] + 15 * (e['midi'] - 60)), e['t'], v['tick'][0], v.get('pan', 0))

DR = AU.get('drums')
if DR:
    BEAT = 60 / A['bpm']; T0 = A['T0']
    def swish(d, acc):
        n = int(d * SR); t = np.arange(n) / SR
        return bp(rng.standard_normal(n), 2500, 9000) * np.sin(np.pi * t / d) ** 1.5 * acc
    def ride():
        n = int(0.9 * SR); t = np.arange(n) / SR
        s = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) for f in (3150, 4270, 5490, 6630, 8100))
        return (s / 5 * 0.6 + hp(rng.standard_normal(n), 7000) * 0.4) * np.exp(-t * 5)
    def chick():
        n = int(0.06 * SR); t = np.arange(n) / SR
        return hp(rng.standard_normal(n), 6000) * np.exp(-t * 70)
    g = DR.get('gain', 1.0)
    for k in range(A['bars'] * 4):
        tb = T0 + k * BEAT
        put(swish(BEAT * 0.95, 1.0 if k % 2 else 0.7), tb, 0.018 * g, -0.4)
        put(ride(), tb, 0.014 * g, 0.45)
        if k % 2 == 1:
            put(ride(), tb + 0.667 * BEAT, 0.01 * g, 0.45); put(chick(), tb, 0.03 * g, 0.3)
    put(ride(), A['end_music'], 0.05 * g, 0.45)

RV = AU.get('reverb', {'length': 2.0, 'decay': 3.0, 'wet': 0.28})
ir_n = int(RV['length'] * SR); t = np.arange(ir_n) / SR
ir = rng.standard_normal((ir_n, 2)) * np.exp(-t * RV['decay'])[:, None]; ir[:int(0.02 * SR)] = 0
ir = np.stack([lp(ir[:, 0], 5500), lp(ir[:, 1], 5500)], 1); ir /= np.sqrt((ir ** 2).sum(0))
wet = np.stack([fftconvolve(mix[:, c], ir[:, c])[:N] for c in range(2)], 1)
out = mix + wet * RV['wet']
fade = int(1.5 * SR); out[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
out = np.tanh(out / np.abs(out).max() * 1.1) * 0.89
wavfile.write(OUT, SR, (out * 32767).astype(np.int16))
print('audio', round(END, 1), 's ->', OUT)
