import bpy, math, json, sys, colorsys, random
import numpy as np
from mathutils import Vector, Euler, Matrix

# ---------------- timeline ----------------
FPS = 30
BPM = 128
E = 60 / BPM / 2            # eighth note seconds
END_T = 96 * E + 1.0
NF = int(round(END_T * FPS)) + 1
ts = np.arange(NF) / FPS
CUT_C = int(round(60 * E * FPS))   # cut to giant close-up
CUT_D = int(round(72 * E * FPS))   # drop: top-down reveal

random.seed(7)
np.random.seed(7)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start = 0
scene.frame_end = NF - 1

# ---------------- helpers ----------------
def get_fcurves(idblock):
    ad = idblock.animation_data
    act = ad.action
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
        if cb is not None:
            return cb.fcurves
    except Exception:
        pass
    return act.fcurves

def ensure_action(idblock):
    if idblock.animation_data is None:
        idblock.animation_data_create()
    if idblock.animation_data.action is None:
        idblock.animation_data.action = bpy.data.actions.new(idblock.name + "_act")
    return idblock.animation_data.action

def set_curve(idblock, path, index, frames, values, interp='LINEAR'):
    act = ensure_action(idblock)
    fc = act.fcurve_ensure_for_datablock(idblock, path, index=index)
    n = len(frames)
    fc.keyframe_points.add(n)
    co = np.empty(2 * n, dtype=np.float32)
    co[0::2] = frames
    co[1::2] = values
    fc.keyframe_points.foreach_set('co', co)
    ip = {'LINEAR': 1, 'CONSTANT': 0, 'BEZIER': 2}[interp]
    fc.keyframe_points.foreach_set('interpolation', np.full(n, ip, dtype=np.int32))
    fc.update()

def compress(vals, eps=1e-5):
    """keep only frames where value changes (plus neighbours) for linear keys"""
    keep = np.zeros(len(vals), bool)
    keep[0] = keep[-1] = True
    d = np.abs(np.diff(vals)) > eps
    keep[1:] |= d
    keep[:-1] |= d
    idx = np.nonzero(keep)[0]
    return idx.astype(np.float32), vals[idx]

def mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.roughness = 0.35
    m.metallic = 0.0
    return m

def srgb2lin(c):
    c = np.asarray(c, float)
    return tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4))

def hexc(h):
    h = h.lstrip('#')
    return srgb2lin([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])

# ---------------- domino meshes ----------------
def domino_mesh(name, w, d, H, bev):
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= w
        v.co.y = v.co.y * d - d / 2      # y in [-d, 0]
        v.co.z = v.co.z * H + H / 2      # z in [0, H]
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bev, segments=2, affect='EDGES')
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(None)
    me.materials.append(None)
    for p in me.polygons:
        p.material_index = 1 if p.normal.y < -0.9 else 0
        p.use_smooth = False
    return me

# ---------------- palette / picture ----------------
RAINBOW = ['#ff5e7e', '#ff9a3c', '#ffd23f', '#5ce1a0', '#3ec7ff', '#7b7bff', '#c86bff']
rainbow_lin = [hexc(h) for h in RAINBOW]
body_mats = [mat(f"body{i}", c) for i, c in enumerate(rainbow_lin)]

PIC = {
    'bg': hexc('#ff8fc7'),
    'face': hexc('#ffd83a'),
    'ink': hexc('#3a2340'),
    'cheek': hexc('#ff6f61'),
}
COLS, ROWS = 25, 32
SX, SY = 1.3, 1.4

def picture(c, r):
    px = (c - 12) * SX
    py = (r - 15.5) * SY
    rr = math.hypot(px, py)
    if rr > 15.3:
        return 'bg'
    # eyes
    for ex in (-5.0, 5.0):
        if ((px - ex) / 1.7) ** 2 + ((py - 4.6) / 2.9) ** 2 < 1:
            return 'ink'
    # smile
    md = math.hypot(px, py - 1.5)
    if 7.2 < md < 10.0 and py < -1.0:
        return 'ink'
    # cheeks
    for cx in (-9.6, 9.6):
        if math.hypot(px - cx, py + 1.6) < 1.9:
            return 'cheek'
    if rr > 14.0:
        return 'ink'   # outline
    return 'face'

# ---------------- build domino list ----------------
D = []   # dicts

def add(kind, x, y, yaw, H, d, w, hit, bodyi, pic=None):
    D.append(dict(kind=kind, x=x, y=y, yaw=yaw, H=H, d=d, w=w, hit=hit,
                  next=None, body=bodyi, pic=pic))
    return len(D) - 1

# snake (17 dominoes), last one at (0,-1.4) heading +y
ys = np.linspace(-1.4, -60, 6000)
def snake_x(y):
    taper = np.clip((-1.4 - y) / 7.0, 0, 1)
    taper = taper * taper * (3 - 2 * taper)
    return 5.0 * np.sin(2 * math.pi * (y + 1.4) / 17.0) * taper
xs = snake_x(ys)
seg = np.hypot(np.diff(xs), np.diff(ys))
arc = np.concatenate([[0], np.cumsum(seg)])
N_SNAKE = 17
snake_hits = [8, 10, 12, 14] + [16 + k for k in range(13)]
snake_idx = []
for i in range(N_SNAKE):
    j = N_SNAKE - 1 - i                # arc steps back from the end
    a = j * 1.4
    k = np.searchsorted(arc, a)
    x, y = xs[k], ys[k]
    # direction of travel (+y-ish): from point further back to this point
    k2 = max(k - 3, 0)
    k1 = min(k + 3, len(xs) - 1)
    dx, dy = xs[k2] - xs[k1], ys[k2] - ys[k1]
    yaw = math.atan2(-dx, dy)          # local +y -> (dx,dy)
    snake_idx.append(add('snake', float(x), float(y), yaw, 2.0, 0.3, 1.0,
                         snake_hits[i] * E, i % 7))
for a, b in zip(snake_idx[:-1], snake_idx[1:]):
    D[a]['next'] = b

# grid
grid = {}
for r in range(ROWS):
    for c in range(COLS):
        hit = (29 + r + 0.5 * abs(c - 12)) * E
        bi = int((r * 0.5 + abs(c - 12) * 0.25)) % 7
        grid[(r, c)] = add('grid', (c - 12) * SX, r * SY, 0.0, 2.0, 0.3, 1.0, hit,
                           bi, picture(c, r))
for r in range(ROWS - 1):
    for c in range(COLS):
        D[grid[(r, c)]]['next'] = grid[(r + 1, c)]
D[snake_idx[-1]]['next'] = grid[(0, 12)]

# giants
prev = grid[(ROWS - 1, 12)]
giant_hits = [61, 62.5, 64.5, 67]
giants = []
for k, gh in enumerate(giant_hits, start=1):
    H = 2 * 1.6 ** k
    d = 0.15 * H
    w = 0.5 * H if k < 4 else 0.78 * H
    py = D[prev]['y'] + 0.6 * D[prev]['H'] + d
    g = add('giant', 0.0, py, 0.0, H, d, w, gh * E, [0, 2, 4, 6][k - 1])
    D[prev]['next'] = g
    giants.append(g)
    prev = g
LAND_T = 72 * E
json.dump(dict(E=E), open('/home/claude/domino/meta.json', 'w'))

# ---------------- angles ----------------
order = sorted(range(len(D)), key=lambda i: -D[i]['hit'])
theta = {}
for i in order:
    o = D[i]
    t0 = o['hit']
    th = np.zeros(NF)
    if o['next'] is None:
        if o['kind'] == 'giant':
            dur = LAND_T - t0
            u = np.clip((ts - t0) / dur, 0, 1)
            th = (math.pi / 2) * (0.12 * u + 0.88 * u * u)
            # tiny rebound after the slam
            tb = ts - LAND_T
            reb = np.where((tb > 0) & (tb < 0.25), np.sin(np.clip(tb / 0.25, 0, 1) * math.pi) * 0.03, 0)
            th = th - reb
        else:
            dur = 1.5 * E
            u = np.clip((ts - t0) / dur, 0, 1)
            th = (math.pi / 2) * (0.25 * u + 0.75 * u * u)
            tb = ts - (t0 + dur)
            reb = np.where((tb > 0) & (tb < 0.2), np.sin(np.clip(tb / 0.2, 0, 1) * math.pi) * 0.07, 0)
            th = th - reb
    else:
        n = D[o['next']]
        fd = np.array([-math.sin(o['yaw']), math.cos(o['yaw'])])
        p = float(np.dot([n['x'] - o['x'], n['y'] - o['y']], fd))
        dn = n['d']
        H = o['H']
        thc = math.asin(np.clip((p - dn) / H, -1, 1))
        tc = n['hit']
        u = np.clip((ts - t0) / (tc - t0), 0, 1)
        expo = 2.0 if i == snake_idx[0] else 1.5
        ph1 = thc * u ** expo
        al = theta[o['next']]
        ph2 = al + np.arcsin(np.clip((p * np.cos(al) - dn) / H, -1, 1))
        th = np.where(ts < tc, ph1, np.maximum(ph2, thc))
        th = np.maximum.accumulate(th) if o['kind'] != 'giant' else th
    theta[i] = th

# ---------------- scene objects ----------------
mesh_std = domino_mesh('dom_std', 1.0, 0.3, 2.0, 0.045)
coll = bpy.data.collections.new('dominoes')
scene.collection.children.link(coll)

pic_mats = {k: mat('pic_' + k, v) for k, v in PIC.items()}

for i, o in enumerate(D):
    if o['kind'] == 'giant':
        me = domino_mesh(f'giant{i}', o['w'], o['d'], o['H'], 0.06 * o['H'] / 2)
    else:
        me = mesh_std
    ob = bpy.data.objects.new(f"dom{i}", me)
    coll.objects.link(ob)
    ob.location = (o['x'], o['y'], 0)
    ob.rotation_mode = 'XYZ'
    ob.rotation_euler = (0, 0, o['yaw'])
    for s in ob.material_slots:
        s.link = 'OBJECT'
    ob.material_slots[0].material = body_mats[o['body']]
    if o['kind'] == 'grid':
        # back face shows its picture colour once the domino tips over
        m = bpy.data.materials.new(f"back{i}")
        m.roughness = 0.35
        ob.material_slots[1].material = m
        crossed = np.nonzero(theta[i] > math.radians(40))[0]
        fsw = int(crossed[0]) if len(crossed) else NF + 10
        before = body_mats[o['body']].diffuse_color[:]
        after = (*PIC[o['pic']], 1)
        for ch in range(3):
            set_curve(m, 'diffuse_color', ch, np.array([0, max(fsw, 1)], np.float32),
                      np.array([before[ch], after[ch]], np.float32), 'CONSTANT')
    elif o['kind'] == 'giant':
        ob.material_slots[1].material = body_mats[o['body']]
    else:
        ob.material_slots[1].material = body_mats[o['body']]
    f, v = compress(-theta[i])
    set_curve(ob, 'rotation_euler', 0, f, v.astype(np.float32))
    o['obj'] = ob

# "WOW!" on the back of the last giant, revealed when it lands
g4 = D[giants[-1]]
bpy.ops.object.text_add()
txt = bpy.context.active_object
txt.data.body = "WOW!"
txt.data.align_x = 'CENTER'
txt.data.align_y = 'CENTER'
txt.data.size = g4['w'] * 0.29
txt.data.extrude = 0.05
txt.data.bevel_depth = 0.02
txt.parent = g4['obj']
txt.location = (0, -g4['d'] - 0.08, g4['H'] * 0.5)
txt.rotation_euler = (math.pi / 2, 0, 0)
txt.data.materials.append(mat('wow', hexc('#ffffff')))
txt.hide_render = True
txt.keyframe_insert('hide_render', frame=0)
txt.hide_render = False
txt.keyframe_insert('hide_render', frame=CUT_D)
for fc in get_fcurves(txt):
    for kp in fc.keyframe_points:
        kp.interpolation = 'CONSTANT'
# white panel behind the text for contrast on giant back
g4['obj'].material_slots[1].material = mat('g4back', hexc('#ff4f8b'))

# ---------------- ball that starts it ----------------
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.55, segments=48, ring_count=24)
ball = bpy.context.active_object
ball.data.materials.append(mat('ball', hexc('#ff3b5c')))
for p in ball.data.polygons:
    p.use_smooth = True
d0 = D[snake_idx[0]]
fd0 = np.array([-math.sin(d0['yaw']), math.cos(d0['yaw'])])
contact = np.array([d0['x'], d0['y']]) - fd0 * (0.3 + 0.55)
t_hit = d0['hit']
bx, by, br = [], [], []
for t in ts:
    if t < t_hit:
        s = (t_hit - t) * 4.2           # rolls in at constant speed
    else:
        tt = t - t_hit
        s = -min(0.9, 2.2 * tt - 1.6 * tt * tt) if tt < 0.69 else -0.9 + 0.0 * tt
        s = -s * 0.0 + (0.9 * (1 - math.exp(-tt * 4)))   # bounces back a little and stops
    pos = contact - fd0 * s
    bx.append(pos[0]); by.append(pos[1]); br.append(-s / 0.55)
f = np.arange(NF, dtype=np.float32)
set_curve(ball, 'location', 0, f, np.array(bx, np.float32))
set_curve(ball, 'location', 1, f, np.array(by, np.float32))
set_curve(ball, 'location', 2, f, np.full(NF, 0.55, np.float32))
ball.rotation_mode = 'XYZ'
ball.rotation_euler = (0, 0, d0['yaw'])
set_curve(ball, 'rotation_euler', 0, f, np.array(br, np.float32))

# ---------------- floor & world ----------------
bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 20, 0))
floor = bpy.context.active_object
floor.data.materials.append(mat('floor', hexc('#fff6fd')))

world = bpy.data.worlds.new('w')
scene.world = world
world.color = hexc('#efe4ff')

# ---------------- confetti (after the drop) ----------------
conf_cols = [mat(f'conf{i}', c) for i, c in enumerate(rainbow_lin + [hexc('#ffffff')])]
bpy.ops.mesh.primitive_plane_add(size=1)
cp = bpy.context.active_object
cme = cp.data
cme.transform(Matrix.Diagonal((1.3, 0.75, 1, 1)))
bpy.data.objects.remove(cp)
cme.materials.append(None)
fD = np.arange(CUT_D - 1, NF, dtype=np.float32)
tD = (fD - CUT_D) / FPS
land_center = np.array([0.0, g4['y'] + g4['H'] * 0.5])
for k in range(380):
    ob = bpy.data.objects.new(f'conf{k}', cme)
    scene.collection.objects.link(ob)
    ob.material_slots[0].link = 'OBJECT'
    ob.material_slots[0].material = random.choice(conf_cols)
    # launch from cannons along the field sides + the giant's landing spot
    src = random.random()
    if src < 0.5:
        x0 = land_center + np.random.randn(2) * [3.0, 4.0]
    else:
        side = random.choice([-1, 1])
        x0 = np.array([side * 19.0, random.uniform(-2, 70)])
    ang = random.uniform(0, 2 * math.pi)
    hv = random.uniform(4, 14)
    v = np.array([math.cos(ang) * hv, math.sin(ang) * hv, random.uniform(22, 42)])
    if src >= 0.5:
        v[0] = -np.sign(x0[0]) * random.uniform(6, 16)
    delay = random.uniform(0, 0.12)
    pos = np.zeros((len(tD), 3))
    p = np.array([x0[0], x0[1], 0.2]); vel = v.copy()
    dt = 1 / FPS
    ph = random.uniform(0, 6.28)
    for n, t in enumerate(tD):
        if t > delay:
            g = np.array([0, 0, -32.0])
            drag = 1.6 if vel[2] < 0 else 0.5
            vel = vel + (g - drag * vel * np.array([1, 1, 1.2])) * dt
            vel[2] = max(vel[2], -6.0)
            sway = np.array([math.sin(t * 5 + ph), math.cos(t * 4 + ph), 0]) * 0.08
            p = p + vel * dt + sway
            if p[2] < 0.05:
                p[2] = 0.05; vel[:] = 0
        pos[n] = p
    pos[0] = [0, 0, -50]      # hidden before the drop
    for ax in range(3):
        set_curve(ob, 'location', ax, fD, pos[:, ax].astype(np.float32))
    ob.location = (0, 0, -50)
    ob.keyframe_insert('location', frame=0)
    spin = np.random.randn(3) * 9
    for ax in range(3):
        set_curve(ob, 'rotation_euler', ax, fD, (spin[ax] * np.clip(tD, 0, None) + random.uniform(0, 6)).astype(np.float32))

# ---------------- cameras ----------------
def look_rot(cam_pos, target, up=Vector((0, 0, 1))):
    fwd = (Vector(target) - Vector(cam_pos)).normalized()
    return fwd.to_track_quat('-Z', 'Y').to_euler()

def make_cam(name, lens):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_fit = 'VERTICAL'
    cd.sensor_height = 36
    cd.clip_end = 1000
    ob = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(ob)
    ob.rotation_mode = 'XYZ'
    return ob

def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)

def gauss_smooth(a, sigma):
    if sigma <= 0:
        return a
    r = int(sigma * 3)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2); k /= k.sum()
    pad = np.pad(a, ((r, r), (0, 0)), mode='edge')
    return np.stack([np.convolve(pad[:, j], k, mode='valid') for j in range(a.shape[1])], 1)

# wave front
sn = [D[i] for i in snake_idx]
hit_s = np.array([o['hit'] for o in sn] + [29 * E])
px_s = np.array([o['x'] for o in sn] + [0.0])
py_s = np.array([o['y'] for o in sn] + [0.0])
W = np.zeros((NF, 3))
for n, t in enumerate(ts):
    if t <= 29 * E:
        W[n] = [np.interp(t, hit_s, px_s), np.interp(t, hit_s, py_s), 0]
    else:
        W[n] = [0, min((t - 29 * E) / E, 31) * SY, 0]
for n, t in enumerate(ts):
    if t < t_hit:
        W[n] = [0.5 * (bx[n] + d0['x']), 0.5 * (by[n] + d0['y']), 0]
W = gauss_smooth(W, 9)

camA = make_cam('camA', 26)
CP = np.zeros((NF, 3)); TG = np.zeros((NF, 3))
for n, t in enumerate(ts):
    a = smoothstep(t / (29 * E))
    follow = W[n] + np.array([3.6 - 2.0 * a, -6.5 - 3.5 * a, 3.2 + 4.5 * a])
    ftg = W[n] + np.array([0, 2.0 + 2 * a, 0.6])
    b = smoothstep((t - 30 * E) / (26 * E))
    high = np.array([0.0, -10.0, 44.0]); htg = np.array([0.0, 27.0, 0.0])
    CP[n] = follow * (1 - b) + high * b
    TG[n] = ftg * (1 - b) + htg * b
CP = gauss_smooth(CP, 4); TG = gauss_smooth(TG, 4)
rots = np.array([tuple(look_rot(CP[n], TG[n])) for n in range(NF)])
f = np.arange(NF, dtype=np.float32)
for ax in range(3):
    set_curve(camA, 'location', ax, f, CP[:, ax].astype(np.float32))
    set_curve(camA, 'rotation_euler', ax, f, np.unwrap(rots[:, ax]).astype(np.float32))

# C: low, in the path of the giants
camC = make_cam('camC', 18)
gy = g4['y']
for n in range(CUT_C - 2, CUT_D + 2):
    t = ts[min(n, NF - 1)]
    a = smoothstep((t - 60 * E) / (12 * E))
    pos = Vector((17.0 - 4.0 * a, gy + 3.0 + 3.5 * a, 1.7 + 0.6 * a))
    tg = Vector((0.0, gy - 6.5 + 6.0 * a, 7.2 - 2.0 * a))
    camC.location = pos
    camC.rotation_euler = look_rot(pos, tg)
    camC.keyframe_insert('location', frame=n)
    camC.keyframe_insert('rotation_euler', frame=n)

# D: top-down reveal with shake
camD = make_cam('camD', 24)
for n in range(CUT_D - 2, NF):
    t = ts[n] - LAND_T
    z = 54 - 6 * smoothstep(t / 6.0)
    shake = 0
    if t > 0:
        shake = math.exp(-t * 5.5) * 1.3
    sx = shake * math.sin(t * 61) ; sy = shake * math.cos(t * 47)
    camD.location = (sx, 35.5 + sy, z)
    camD.rotation_euler = (0, 0, 0.0 + shake * 0.02 * math.sin(t * 33))
    camD.keyframe_insert('location', frame=n)
    camD.keyframe_insert('rotation_euler', frame=n)

# ---------------- render settings ----------------
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x = 1080
scene.render.resolution_y = 1920
scene.render.resolution_percentage = 100
scene.display.render_aa = sys.argv[-1] if sys.argv[-1] in ('FXAA','5','8','11') else 'FXAA'
sh = scene.display.shading
sh.light = 'STUDIO'
sh.color_type = 'MATERIAL'
sh.show_shadows = True
sh.studio_light = 'outdoor.sl'
sh.shadow_intensity = 0.35
sh.show_cavity = True
sh.cavity_type = 'BOTH'
sh.cavity_ridge_factor = 0.6
sh.cavity_valley_factor = 1.0
sh.show_specular_highlight = True
scene.display.light_direction = (0.45, -0.35, 0.82)
scene.display.shadow_shift = 0.05
scene.display.shadow_focus = 0.3
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
scene.camera = camA

bpy.ops.wm.save_as_mainfile(filepath='/home/claude/domino/domino.blend')

# events for the music
ev = []
for i, o in enumerate(D):
    ev.append(dict(t=o['hit'], kind=o['kind'], c=(None if o['kind'] != 'grid' else int(round(o['x'] / SX + 12))),
                   r=(None if o['kind'] != 'grid' else int(round(o['y'] / SY))), H=o['H']))
json.dump(dict(E=E, events=ev, land=LAND_T, end=END_T, cutC=CUT_C, cutD=CUT_D, nf=NF),
          open('/home/claude/domino/events.json', 'w'))
print("BUILT", len(D), "dominoes, frames", NF, "cuts", CUT_C, CUT_D)
