import json, glob, re, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

S = json.load(open('/home/claude/nordic/score.json'))
SR = 44100; END = S['END']; N = int(END * SR)
rng = np.random.default_rng(31)
mix = np.zeros((N, 2))
def lp(x, fc): return sosfilt(butter(2, fc, 'low', fs=SR, output='sos'), x)
def put(sig, t, g=1.0, pan=0.0):
    if sig.ndim == 1:
        sig = np.stack([sig * np.cos((pan + 1) * np.pi / 4), sig * np.sin((pan + 1) * np.pi / 4)], 1) * 1.414
    i = int(t * SR)
    if i >= N: return
    sig = sig[:N - i]; mix[i:i + len(sig)] += sig * g
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
    n = int(min(dur + 0.4, len(x) / SR / ratio) * SR)
    y = np.stack([np.interp(np.arange(n) * ratio, np.arange(len(x)), x[:, c]) for c in range(2)], 1)
    r = int(dur * SR)
    if r < n: y[r:] *= np.exp(-np.arange(n - r) / SR * 12)[:, None]
    return y * (0.4 + 0.9 * vel)

EM = S['end_music']
for n in S['notes']:
    prog = n['t'] / EM
    vel = 0.34 + 0.6 * prog ** 1.3 + rng.normal(0, 0.025)
    if n['midi'] < 48: vel += 0.05
    last = n['t'] > EM - 1.2
    dur = n['end'] - n['t']
    if last: dur = 3.0; vel = 0.95
    pan = float(np.clip((n['midi'] - 60) / 40, -0.6, 0.6))
    put(piano(n['midi'], float(np.clip(vel, 0.1, 0.97)), dur), n['t'] + rng.normal(0, 0.003), 0.5, pan)

# mechanism sounds: wooden key "tok" for bounces, domino clicks, the big bell
Mj = json.load(open('/home/claude/nordic/machine.json')); EX = json.load(open('/home/claude/nordic/machine_extra.json'))
def bp(x, a, b_): return sosfilt(butter(2, [a, b_], 'band', fs=SR, output='sos'), x)
def tok(f):
    k = int(0.09 * SR); t = np.arange(k) / SR
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 3.9 * t)) * np.exp(-t * 55) + bp(rng.standard_normal(k), 800, 4000) * np.exp(-t * 120) * 0.4
def click():
    k = int(0.03 * SR); t = np.arange(k) / SR
    return bp(rng.standard_normal(k), 1800, 7000) * np.exp(-t * 240)
for s_ in Mj['sections']:
    if s_['kind'] == 'B':
        for key in s_['keys']: put(tok(900 + 120 * (len(key['notes']) % 4)), key['t'], 0.10)
    else:
        for t_ in s_['times'][:-1]: put(click(), t_, 0.07)
TB = EX['bell_t']
k = int(5.5 * SR); t = np.arange(k) / SR
bell = sum(a_ * np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, a_, d in [(123.5, 1.0, 0.6), (247, 0.6, 0.9), (296, 0.4, 1.2), (370, 0.35, 1.4), (494, 0.25, 1.8), (741, 0.15, 2.5)])
put(bell * 0.5 * np.minimum(t * 400, 1), TB, 0.5)
ir_n = int(2.6 * SR); t = np.arange(ir_n) / SR
ir = rng.standard_normal((ir_n, 2)) * np.exp(-t * 2.6)[:, None]; ir[:int(0.02 * SR)] = 0
ir = np.stack([lp(ir[:, 0], 6000), lp(ir[:, 1], 6000)], 1); ir /= np.sqrt((ir ** 2).sum(0))
wet = np.stack([fftconvolve(mix[:, c], ir[:, c])[:N] for c in range(2)], 1)
out = mix + wet * 0.3
fade = int(1.5 * SR); out[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
out = np.tanh(out / np.abs(out).max() * 1.15) * 0.89
wavfile.write('/home/claude/nordic/music2.wav', SR, (out * 32767).astype(np.int16))
print('ok', END)
