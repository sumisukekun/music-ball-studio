"""One command from config to finished vertical video.

    python studio/make.py configs/midnight_spiral.json                 # everything
    python studio/make.py configs/midnight_spiral.json --steps preview # a few test frames only
    python studio/make.py configs/x.json --steps render,post           # resume

Steps: song -> audio -> scene -> (preview) -> render -> post
Outputs go to build/<name>/ and out/<name>.mp4
Environment:
    MBS_BPY_PYTHON  python that can `import bpy` (default: current python)
    MBS_SAMPLES     folder with the Salamander piano wavs (default: ./samples)
    MBS_PARTS       number of render chunks (default 2; chunks finish one by one so a stopped run can resume)
"""
import json, os, sys, subprocess, argparse, shutil, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
BPY = os.environ.get('MBS_BPY_PYTHON', PY)
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

def run(cmd, **kw):
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)

RENDER_SNIPPET = r'''
import bpy, sys
blend, f0, f1, out = sys.argv[-4:]
bpy.ops.wm.open_mainfile(filepath=blend)
s = bpy.context.scene
s.frame_start, s.frame_end = int(f0), int(f1)
im = s.render.image_settings
try: im.media_type = 'VIDEO'
except Exception: pass
im.file_format = 'FFMPEG'
s.render.ffmpeg.format = 'MPEG4'; s.render.ffmpeg.codec = 'H264'
s.render.ffmpeg.constant_rate_factor = 'PERC_LOSSLESS'; s.render.ffmpeg.ffmpeg_preset = 'GOOD'
s.render.filepath = out
bpy.ops.render.render(animation=True)
'''
PREVIEW_SNIPPET = r'''
import bpy, sys
blend, outdir, frames = sys.argv[-3:]
bpy.ops.wm.open_mainfile(filepath=blend)
s = bpy.context.scene
for f in [int(x) for x in frames.split(',')]:
    s.frame_set(f); s.render.filepath = f'{outdir}/f{f:04d}.png'; bpy.ops.render.render(write_still=True)
'''

def t_expr(v, A):
    """caption times may be numbers or strings like 'end_music+1.5' / 'end'"""
    if isinstance(v, (int, float)): return float(v)
    env = dict(end_music=A['end_music'], end=A['END'])
    return float(eval(v, {}, env))

def post_filter(cfg, A, tmp):
    P = cfg.get('post', {})
    w, h = P.get('size', [1080, 1920])
    g = P.get('glow', {'threshold': 0.35, 'sigma': 9, 'opacity': 0.85})
    parts = [f'scale={w}:{h}:flags=lanczos', 'format=gbrp']
    if g:
        th = g['threshold']
        parts.append(f"split[a][b];[b]colorlevels=rimin={th}:gimin={th}:bimin={th},gblur=sigma={g['sigma']}[g];"
                     f"[a][g]blend=all_mode=screen:all_opacity={g['opacity']}")
    for i, c in enumerate(P.get('captions', [])):
        tf = os.path.join(tmp, f'cap{i}.txt'); open(tf, 'w').write(c['text'])
        a, b = t_expr(c.get('from', 0), A), t_expr(c.get('to', 'end'), A)
        parts.append(f"drawtext=fontfile={P.get('font', FONT)}:textfile={tf}:fontsize={c.get('size', 56)}:"
                     f"fontcolor={c.get('color', 'white')}:borderw={c.get('border', 6)}:bordercolor={c.get('border_color', '0x05080F')}:"
                     f"x=(w-text_w)/2:y={c.get('y', 300)}:enable='between(t,{a:.2f},{b:.2f})'")
    parts.append('format=yuv420p')
    return ','.join(parts)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('config'); ap.add_argument('--steps', default='song,audio,scene,render,post')
    args = ap.parse_args()
    cfg = json.load(open(args.config)); name = cfg['name']
    B = os.path.join(ROOT, 'build', name); os.makedirs(B, exist_ok=True); os.makedirs(os.path.join(ROOT, 'out'), exist_ok=True)
    arr, wav, blend = f'{B}/arr.json', f'{B}/music.wav', f'{B}/scene.blend'
    cfgp = os.path.abspath(args.config)
    steps = args.steps.split(',')
    if 'song' in steps: run([PY, os.path.join(ROOT, cfg['song']), arr])
    if 'audio' in steps: run([PY, os.path.join(ROOT, 'studio', 'audio.py'), cfgp, arr, wav])
    if 'scene' in steps: run([BPY, os.path.join(ROOT, 'studio', cfg.get('engine', 'spiral_scene.py')), cfgp, arr, blend])
    A = json.load(open(arr)); NF = int(A['END'] * 30) + 1
    if 'preview' in steps:
        pd = f'{B}/preview'; os.makedirs(pd, exist_ok=True)
        frames = cfg.get('preview_frames') or [int(NF * x) for x in (0.05, 0.3, 0.6, 0.9, 0.99)]
        snip = f'{B}/_preview.py'; open(snip, 'w').write(PREVIEW_SNIPPET)
        run([BPY, snip, blend, pd, ','.join(map(str, frames))])
        print('preview frames in', pd)
    if 'render' in steps:
        nparts = int(os.environ.get('MBS_PARTS', 2)); snip = f'{B}/_render.py'; open(snip, 'w').write(RENDER_SNIPPET)
        edges = [round(i * NF / nparts) for i in range(nparts + 1)]
        for i in range(nparts):
            done = f'{B}/part_{i}.mp4'
            if os.path.exists(done): print('skip', done); continue
            tmpf = f'{B}/tmp_part_{i}.mp4'
            run([BPY, snip, blend, str(edges[i]), str(edges[i + 1] - 1), tmpf])
            os.replace(tmpf, done)
    if 'post' in steps:
        lst = f'{B}/parts.txt'; nparts = int(os.environ.get('MBS_PARTS', 2))
        open(lst, 'w').write(''.join(f"file '{B}/part_{i}.mp4'\n" for i in range(nparts)))
        out = os.path.join(ROOT, 'out', f'{name}.mp4')
        with tempfile.TemporaryDirectory() as tmp:
            vf = post_filter(cfg, A, tmp)
            run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-i', wav,
                 '-filter_complex', f'[0:v]{vf}[v];[1:a]loudnorm=I=-14:TP=-1[a]', '-map', '[v]', '-map', '[a]',
                 '-c:v', 'libx264', '-preset', 'veryfast', '-crf', str(cfg.get('post', {}).get('crf', 21)),
                 '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-movflags', '+faststart', '-shortest', out + '.tmp.mp4'])
        os.replace(out + '.tmp.mp4', out)
        print('DONE ->', out)

if __name__ == '__main__':
    main()
