import bpy, math, json, random
import numpy as np
from mathutils import Vector, Matrix

S = json.load(open('/home/claude/clair/score.json'))
FPS = 30
END_T = S['end']
NF = int(END_T * FPS) + 1
ts = np.arange(NF) / FPS
random.seed(4); np.random.seed(4)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 0, NF - 1

def ensure_action(idb):
    if idb.animation_data is None: idb.animation_data_create()
    if idb.animation_data.action is None:
        idb.animation_data.action = bpy.data.actions.new(idb.name + "_a")
def set_curve(idb, path, index, vals, interp=1):
    vals = np.asarray(vals, np.float64)
    keep = np.zeros(len(vals), bool); keep[0] = keep[-1] = True
    d = np.abs(np.diff(vals)) > 1e-6; keep[1:] |= d; keep[:-1] |= d
    fr = np.nonzero(keep)[0]; v = vals[fr]
    ensure_action(idb)
    fc = idb.animation_data.action.fcurve_ensure_for_datablock(idb, path, index=index)
    fc.keyframe_points.add(len(fr))
    co = np.empty(2 * len(fr), np.float32); co[0::2] = fr; co[1::2] = v
    fc.keyframe_points.foreach_set('co', co)
    fc.keyframe_points.foreach_set('interpolation', np.full(len(fr), interp, np.int32))
    fc.update()
def srgb(h):
    h = h.lstrip('#'); c = np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])
    return tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4))
MATS = {}
def M(h, rough=0.3):
    k = (h, rough)
    if k not in MATS:
        m = bpy.data.materials.new(h); m.diffuse_color = (*srgb(h), 1); m.roughness = rough
        MATS[k] = m
    return MATS[k]
def smooth01(u):
    u = np.clip(u, 0, 1); return u * u * (3 - 2 * u)
def gs(a, s):
    r = int(3 * s); k = np.exp(-0.5 * (np.arange(-r, r + 1) / s) ** 2); k /= k.sum()
    if a.ndim == 1: return np.convolve(np.pad(a, r, mode='edge'), k, 'valid')
    return np.stack([gs(a[:, j], s) for j in range(a.shape[1])], 1)

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

BODY, TOPC = '#27305f', '#c9d3f2'
GLINT = ['#fff1c2', '#f7e3a1', '#eef3ff', '#dfe8ff', '#ffe9b0', '#fff8e0']
WATER, SKY = '#060b1f', '#0a1029'

# ---------------- rows of dominoes along the moon path ----------------
rows = S['rows']; NR = len(rows)
P = 1.45; Dd = 0.2; W = 0.7; GAPX = 0.12
def height(m): return max(1.55, 1.2 + (m - 36) / 48 * 1.7)
R = []
for k, r in enumerate(rows):
    ms = sorted(r['midis'])
    Hs = [height(m) for m in ms]
    final = r.get('final', False)
    y = k * P + (0.6 if final else 0)
    R.append(dict(t=r['t'], ms=ms, Hs=Hs, Hmax=max(Hs), y=y, final=final))

theta = [None] * NR
for k in range(NR - 1, -1, -1):
    o = R[k]; t0 = o['t']
    if k == NR - 1:
        u = np.clip((ts - t0) / 1.1, 0, 1)
        th = (math.pi / 2) * (0.15 * u + 0.85 * u * u)
        tb = ts - (t0 + 1.1)
        th = th - np.where((tb > 0) & (tb < 0.35), np.sin(np.clip(tb / 0.35, 0, 1) * math.pi) * 0.05, 0)
    else:
        n = R[k + 1]; p = n['y'] - o['y']; H = o['Hmax']
        thc = math.asin(np.clip((p - Dd) / H, -1, 1))
        tc = n['t']
        u = np.clip((ts - t0) / (tc - t0), 0, 1)
        ph1 = thc * u ** (2.0 if k == 0 else 1.6)
        al = theta[k + 1]
        ph2 = al + np.arcsin(np.clip((p * np.cos(al) - Dd) / H, -1, 1))
        th = np.where(ts < tc, ph1, np.maximum(ph2, thc))
    theta[k] = np.maximum.accumulate(th)

base = domino_mesh('dom', W, Dd, 1.0, 0.03)
for k, o in enumerate(R):
    n = len(o['ms'])
    xs = (np.arange(n) - (n - 1) / 2) * (W + GAPX)
    crossed = np.nonzero(theta[k] > math.radians(42))[0]
    fsw = int(crossed[0]) if len(crossed) else NF + 5
    for j, (x, H) in enumerate(zip(xs, o['Hs'])):
        ob = bpy.data.objects.new(f'r{k:02d}_{j}', base); scene.collection.objects.link(ob)
        ob.location = (x, o['y'], 0); ob.scale = (1, 1, H)
        for s in ob.material_slots: s.link = 'OBJECT'
        ob.material_slots[0].material = M(BODY)
        ob.material_slots[2].material = M(TOPC)
        # the face that turns up becomes moonlight on the water once the domino has tipped
        m = bpy.data.materials.new(f'back{k}_{j}'); m.roughness = 0.15
        ob.material_slots[1].material = m
        c1 = M(BODY).diffuse_color[:]; c2 = (*srgb(random.choice(GLINT)), 1)
        for ch in range(3):
            set_curve(m, 'diffuse_color', ch, np.where(np.arange(NF) < fsw, c1[ch], c2[ch]), interp=0)
        set_curve(ob, 'rotation_euler', 0, -theta[k])

# ---------------- moon, water, stars ----------------
YEND = R[-1]['y']
MOON_Y, MOON_R = YEND + 60, 24
bpy.ops.mesh.primitive_cylinder_add(radius=MOON_R, depth=0.5, vertices=128)
moon = bpy.context.active_object; moon.name = 'moon'
moon.data.transform(Matrix.Rotation(math.pi / 2, 4, 'X'))
moon.data.materials.append(M('#fff6d8', 1.0))
mz0 = MOON_R * 0.55
rise = 2.5 * smooth01((ts - (S['final_t'] - 0.5)) / 5.0)
set_curve(moon, 'location', 0, np.zeros(NF)); set_curve(moon, 'location', 1, np.full(NF, MOON_Y))
set_curve(moon, 'location', 2, mz0 + rise)
# soft halo rings behind the moon
for i, (rr, col) in enumerate([(1.12, '#3a4677'), (1.25, '#26305e'), (1.42, '#1a2247')]):
    bpy.ops.mesh.primitive_cylinder_add(radius=MOON_R * rr, depth=0.2, vertices=128)
    h = bpy.context.active_object
    h.data.transform(Matrix.Rotation(math.pi / 2, 4, 'X'))
    h.data.materials.append(M(col, 1.0))
    h.parent = moon; h.location = (0, 1.0 + i * 0.6, 0)
# water
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 60, 0))
water = bpy.context.active_object; water.scale = (600, 600, 1)
water.data.materials.append(M(WATER, 1.0))
# a few far islands / hills on the horizon for depth
for i, (x, w, h) in enumerate([(-70, 60, 7), (75, 70, 9), (-20, 40, 4)]):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=48, ring_count=24, location=(x, MOON_Y + 25, 0))
    hill = bpy.context.active_object; hill.scale = (w, 6, h)
    hill.data.materials.append(M('#151d40', 1.0))
# stars
import bmesh
bm = bmesh.new()
for i in range(420):
    x = random.uniform(-160, 160); z = random.uniform(8, 170) ** 1.0
    s = random.choice([0.18, 0.25, 0.35, 0.5])
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=s, matrix=Matrix.Translation((x, MOON_Y + 70 + random.uniform(0, 30), z)))
me = bpy.data.meshes.new('stars'); bm.to_mesh(me); bm.free(); me.materials.append(M('#fdf8e8', 1.0))
scene.collection.objects.link(bpy.data.objects.new('stars', me))

world = bpy.data.worlds.new('w'); world.color = srgb(SKY); scene.world = world

# ---------------- camera ----------------
cd = bpy.data.cameras.new('cam'); cd.lens = 28; cd.sensor_fit = 'VERTICAL'; cd.sensor_height = 36; cd.clip_end = 1000
cam = bpy.data.objects.new('cam', cd); scene.collection.objects.link(cam); scene.camera = cam
cam.rotation_mode = 'XYZ'
rt = np.array([o['t'] for o in R]); ry = np.array([o['y'] for o in R])
front = gs(np.interp(ts, rt, ry), 45)
FT = S['final_t']
a = smooth01(ts / FT)
back = 6.5 + 5.0 * a; up = 1.3 + 3.2 * a; side = 2.6 - 1.4 * a
CP = np.stack([side, front - back, up], 1)
TG = np.stack([side * 0.2, front + 6 + 2 * a, 0.9 + 0.8 * a], 1)
# finale: rise and pull back to show the whole moonlit path
b = smooth01((ts - (FT - 2.0)) / 6.5)
endP = np.array([0.0, -7.0, 8.0]); endT = np.array([0.0, YEND * 0.5, 4.0])
CP = CP * (1 - b)[:, None] + endP * b[:, None]
TG = TG * (1 - b)[:, None] + endT * b[:, None]
CP, TG = gs(CP, 6), gs(TG, 6)
rot = []
for n in range(NF):
    fwd = Vector(TG[n]) - Vector(CP[n])
    rot.append(tuple(fwd.to_track_quat('-Z', 'Y').to_euler()))
rot = np.unwrap(np.array(rot), axis=0)
for i in range(3):
    set_curve(cam, 'location', i, CP[:, i]); set_curve(cam, 'rotation_euler', i, rot[:, i])

scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
scene.display.render_aa = 'FXAA'
sh = scene.display.shading
sh.light = 'FLAT'; sh.color_type = 'MATERIAL'
sh.show_shadows = True; sh.shadow_intensity = 0.5
sh.show_cavity = True; sh.cavity_type = 'BOTH'
sh.show_specular_highlight = True
scene.display.light_direction = (0.0, 0.6, 0.8)
scene.display.shadow_shift = 0.03; scene.display.shadow_focus = 0.2
scene.view_settings.view_transform = 'Standard'
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/clair/clair.blend')
print('BUILT', NF, 'rows', NR, 'yend', round(YEND, 1))
