import bpy, math, json, random, sys
import numpy as np
from mathutils import Vector, Matrix

S = json.load(open('/home/claude/bach/score.json'))
FPS = 30
END_T = S['end']
NF = int(END_T * FPS) + 1
ts = np.arange(NF) / FPS
random.seed(2); np.random.seed(2)
THEME = sys.argv[-1] if sys.argv[-1] in ('night', 'ivory') else 'night'

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 0, NF - 1

# ---------------- helpers ----------------
def ensure_action(idb):
    if idb.animation_data is None: idb.animation_data_create()
    if idb.animation_data.action is None:
        idb.animation_data.action = bpy.data.actions.new(idb.name + "_a")
def set_curve(idb, path, index, vals):
    vals = np.asarray(vals, np.float64)
    keep = np.zeros(len(vals), bool); keep[0] = keep[-1] = True
    d = np.abs(np.diff(vals)) > 1e-6; keep[1:] |= d; keep[:-1] |= d
    fr = np.nonzero(keep)[0]; v = vals[fr]
    ensure_action(idb)
    fc = idb.animation_data.action.fcurve_ensure_for_datablock(idb, path, index=index)
    fc.keyframe_points.add(len(fr))
    co = np.empty(2 * len(fr), np.float32); co[0::2] = fr; co[1::2] = v
    fc.keyframe_points.foreach_set('co', co)
    fc.keyframe_points.foreach_set('interpolation', np.full(len(fr), 1, np.int32))
    fc.update()
def srgb(h):
    h = h.lstrip('#'); c = np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])
    return tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4))
MATS = {}
def M(h):
    if h not in MATS:
        m = bpy.data.materials.new(h); m.diffuse_color = (*srgb(h), 1); m.roughness = 0.25
        MATS[h] = m
    return MATS[h]
def lerp_hex(a, b, u):
    ca = np.array([int(a[i:i + 2], 16) for i in (1, 3, 5)]); cb = np.array([int(b[i:i + 2], 16) for i in (1, 3, 5)])
    c = (ca + (cb - ca) * u).round().astype(int)
    return '#%02x%02x%02x' % tuple(c)
def smooth01(u):
    u = np.clip(u, 0, 1); return u * u * (3 - 2 * u)

def domino_mesh(name, w, d, H, bev):
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= w; v.co.y = v.co.y * d - d / 2; v.co.z = v.co.z * H + H / 2
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bev, segments=3, affect='EDGES')
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for _ in range(3): me.materials.append(None)
    for p in me.polygons:
        p.material_index = 1 if p.normal.y < -0.9 else (2 if p.normal.z > 0.9 else 0)
    return me

# ---------------- palette ----------------
if THEME == 'night':
    FLOOR, WORLD = '#1c2140', '#151a33'
    BODY, TOP = '#f6f1e7', '#e9c46a'
    PET_A, PET_B = '#f4a7bb', '#b8a4f2'
    PETAL_BODY, PETAL_BACK = '#fbf6ee', '#e9c46a'
else:
    FLOOR, WORLD = '#f6efe6', '#f3ebe1'
    BODY, TOP = '#ffffff', '#d8b45a'
    PET_A, PET_B = '#f2a0b6', '#a89be8'
    PETAL_BODY, PETAL_BACK = '#ffffff', '#d8b45a'

# ---------------- spiral path ----------------
notes = S['notes']; NN = len(notes)
P = 1.25
r0, b = 2.6, 1.95 / (2 * math.pi)
GAP = 3.2      # extra radius for the bridge out to the petal ring
def path_pts(th_end, n=20000):
    th = np.linspace(0, th_end, n)
    r = r0 + b * th
    blend = smooth01((th - (th_end - 1.3 * math.pi)) / (1.3 * math.pi))
    r = r + GAP * blend
    x, y = r * np.cos(th), r * np.sin(th)
    s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
    return th, x, y, s
lo, hi = 10.0, 200.0
for _ in range(60):
    mid = (lo + hi) / 2
    if path_pts(mid)[3][-1] < (NN - 1) * P: lo = mid
    else: hi = mid
TH_END = hi
th, xs, ys, ss = path_pts(TH_END)
R_PET = r0 + b * TH_END + GAP

D = []
for i, n in enumerate(notes):
    k = min(np.searchsorted(ss, i * P), len(ss) - 1)
    k1, k2 = max(k - 2, 0), min(k + 2, len(ss) - 1)
    dx, dy = xs[k2] - xs[k1], ys[k2] - ys[k1]
    yaw = math.atan2(-dx, dy)
    H = 1.35 + (n['midi'] - 43) / (81 - 43) * 1.45
    D.append(dict(x=xs[k], y=ys[k], yaw=yaw, H=H, d=0.22, w=0.9, hit=n['t'], th=th[k]))

# angles (reverse order chain)
theta = [None] * NN
for i in range(NN - 1, -1, -1):
    o = D[i]; t0 = o['hit']
    if i == NN - 1:
        dur = 0.55
        u = np.clip((ts - t0) / dur, 0, 1)
        thv = (math.pi / 2 - 0.12) * (0.3 * u + 0.7 * u * u)
    else:
        n = D[i + 1]
        fd = np.array([-math.sin(o['yaw']), math.cos(o['yaw'])])
        p = float(np.dot([n['x'] - o['x'], n['y'] - o['y']], fd))
        thc = math.asin(np.clip((p - n['d']) / o['H'], -1, 1))
        tc = n['hit']
        u = np.clip((ts - t0) / (tc - t0), 0, 1)
        ph1 = thc * u ** (2.0 if i == 0 else 1.5)
        al = theta[i + 1]
        ph2 = al + np.arcsin(np.clip((p * np.cos(al) - n['d']) / o['H'], -1, 1))
        thv = np.where(ts < tc, ph1, np.maximum(ph2, thc))
    theta[i] = np.maximum.accumulate(thv)

# ---------------- objects ----------------
base = domino_mesh('dom', 0.9, 0.22, 1.0, 0.035)
NPET = 12
pet_mats = [M(lerp_hex(PET_A, PET_B, j / (NPET - 1))) for j in range(NPET)]
for i, o in enumerate(D):
    ob = bpy.data.objects.new(f'd{i:03d}', base); scene.collection.objects.link(ob)
    ob.location = (o['x'], o['y'], 0)
    ob.scale = (1, 1, o['H'])
    ob.rotation_mode = 'XYZ'; ob.rotation_euler = (0, 0, o['yaw'])
    for s in ob.material_slots: s.link = 'OBJECT'
    ob.material_slots[0].material = M(BODY)
    phi = math.atan2(o['y'], o['x']); rr = math.hypot(o['x'], o['y'])
    v = 0.5 + 0.5 * math.cos(6 * phi - 0.55 * rr)
    ob.material_slots[1].material = pet_mats[int(round(v * (NPET - 1)))]
    ob.material_slots[2].material = M(TOP)
    set_curve(ob, 'rotation_euler', 0, -theta[i])

# petal ring: blooms outward with the final rolled chord
FT = S['final_t']
NP = 22
pmesh = domino_mesh('petal', 2.4, 0.4, 5.0, 0.08)
th_join = TH_END % (2 * math.pi)
for j in range(NP):
    a = th_join + math.radians(18) + j * math.radians(330 / (NP - 1))
    ob = bpy.data.objects.new(f'petal{j}', pmesh); scene.collection.objects.link(ob)
    # local +y = outward (fall direction)
    ob.location = (R_PET * math.cos(a), R_PET * math.sin(a), 0)
    ob.rotation_mode = 'XYZ'
    yaw = a - math.pi / 2
    for s in ob.material_slots: s.link = 'OBJECT'
    ob.material_slots[0].material = M(PETAL_BODY)
    ob.material_slots[1].material = M(PETAL_BACK)
    ob.material_slots[2].material = M(PETAL_BODY)
    t0 = FT + j * 0.06
    u = np.clip((ts - t0) / 0.95, 0, 1)
    ang = (math.pi / 2) * (0.1 * u + 0.9 * u * u)
    tb = ts - (t0 + 0.95)
    ang = ang - np.where((tb > 0) & (tb < 0.3), np.sin(np.clip(tb / 0.3, 0, 1) * math.pi) * 0.06, 0)
    ob.rotation_euler = (0, 0, yaw)
    set_curve(ob, 'rotation_euler', 0, -ang)
    set_curve(ob, 'rotation_euler', 2, np.full(NF, yaw))

# gold ball that starts it all
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.42, segments=48, ring_count=24)
ball = bpy.context.active_object
ball.data.materials.append(M(TOP))
for p in ball.data.polygons: p.use_smooth = True
d0 = D[0]; fd0 = np.array([-math.sin(d0['yaw']), math.cos(d0['yaw'])])
hitp = np.array([d0['x'], d0['y']]) - fd0 * (0.22 + 0.42)
zhit = d0['H'] - 0.25
g = 22.0; T0 = d0['hit']; ztop = 14.0
tf = math.sqrt(2 * (ztop - zhit) / g)
BX, BY, BZ = [], [], []
for t in ts:
    if t < T0:
        tau = max(t - (T0 - tf), 0)
        z = ztop - 0.5 * g * tau * tau if t > T0 - tf else ztop + 30
        pos = hitp
    else:
        tau = t - T0
        # small bounce back toward the centre, then settles
        k = 1 - math.exp(-tau * 2.2)
        pos = hitp + (np.array([0.0, 0.0]) - hitp) * 0.75 * k
        vz0 = 4.0
        z = max(0.42, zhit + vz0 * tau - 0.5 * g * tau * tau)
        if tau > 0.3: z = 0.42 + 0.5 * abs(math.sin(tau * 8)) * math.exp(-tau * 4)
    BX.append(pos[0]); BY.append(pos[1]); BZ.append(z)
for a, arr in enumerate((BX, BY, BZ)): set_curve(ball, 'location', a, arr)

# floor
bpy.ops.mesh.primitive_plane_add(size=400); floor = bpy.context.active_object
fm = bpy.data.materials.new('floor'); fm.diffuse_color = (*srgb(FLOOR), 1); fm.roughness = 1.0
floor.data.materials.append(fm)
world = bpy.data.worlds.new('w'); world.color = srgb(WORLD); scene.world = world

# ---------------- camera ----------------
cd = bpy.data.cameras.new('cam'); cd.lens = 26; cd.sensor_fit = 'VERTICAL'; cd.sensor_height = 36; cd.clip_end = 600
cam = bpy.data.objects.new('cam', cd); scene.collection.objects.link(cam); scene.camera = cam
cam.rotation_mode = 'XYZ'
hit_t = np.array([o['hit'] for o in D])
W = np.stack([np.interp(ts, hit_t, [o['x'] for o in D]), np.interp(ts, hit_t, [o['y'] for o in D])], 1)
def gs(a, s):
    r = int(3 * s); k = np.exp(-0.5 * (np.arange(-r, r + 1) / s) ** 2); k /= k.sum()
    if a.ndim == 1: return np.convolve(np.pad(a, r, mode='edge'), k, 'valid')
    return np.stack([gs(a[:, j], s) for j in range(a.shape[1])], 1)
W = gs(W, 30)
kt = np.array([0, 3, 12, 25, 40, 55, 63, 67.5, END_T])
kdist = np.array([10, 10.5, 14, 19, 26, 33, 44, 52, 54])
kelev = np.radians([40, 41, 43, 46, 50, 57, 68, 80, 82])
kw = np.array([0.2, 0.55, 0.7, 0.7, 0.65, 0.55, 0.2, 0.0, 0.0])
dist = np.interp(ts, kt, kdist); elev = np.interp(ts, kt, kelev); wf = np.interp(ts, kt, kw)
dist, elev, wf = gs(dist, 20), gs(elev, 20), gs(wf, 20)
az = math.radians(-100) + np.radians(5.5) * ts
TG = np.stack([W[:, 0] * wf, W[:, 1] * wf, np.zeros(NF)], 1)
CP = np.stack([TG[:, 0] + dist * np.cos(elev) * np.cos(az), TG[:, 1] + dist * np.cos(elev) * np.sin(az),
               0.6 + dist * np.sin(elev)], 1)
rot = []
for n in range(NF):
    fwd = Vector(TG[n]) - Vector(CP[n])
    rot.append(tuple(fwd.to_track_quat('-Z', 'Y').to_euler()))
rot = np.unwrap(np.array(rot), axis=0)
for a in range(3):
    set_curve(cam, 'location', a, CP[:, a]); set_curve(cam, 'rotation_euler', a, rot[:, a])

# ---------------- render ----------------
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
scene.display.render_aa = 'FXAA'
sh = scene.display.shading
sh.light = 'STUDIO'; sh.studio_light = 'outdoor.sl'; sh.color_type = 'MATERIAL'
sh.show_shadows = True; sh.shadow_intensity = 0.45
sh.show_cavity = True; sh.cavity_type = 'BOTH'; sh.cavity_ridge_factor = 0.8
sh.show_specular_highlight = True
scene.display.light_direction = (0.35, -0.45, 0.8)
scene.display.shadow_shift = 0.03; scene.display.shadow_focus = 0.25
scene.view_settings.view_transform = 'Standard'
bpy.ops.wm.save_as_mainfile(filepath=f'/home/claude/bach/bach_{THEME}.blend')
print('BUILT', THEME, NF, 'R_PET', round(R_PET, 1))
