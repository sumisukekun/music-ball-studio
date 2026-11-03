import bpy, math, json, random
import numpy as np
from mathutils import Vector, Matrix

S = json.load(open('/home/claude/ice/score.json'))
FPS = 30; END = S['END']; NF = int(END * FPS) + 1
ts = np.arange(NF) / FPS
random.seed(3); np.random.seed(3)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS; scene.frame_start, scene.frame_end = 0, NF - 1

def ensure_action(idb):
    if idb.animation_data is None: idb.animation_data_create()
    if idb.animation_data.action is None: idb.animation_data.action = bpy.data.actions.new(idb.name + "_a")
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
def lin(c):
    c = np.asarray(c, float); return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def hexl(h): h = h.lstrip('#'); return lin([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])
MATS = {}
def M(h, rough=0.2):
    if h not in MATS:
        m = bpy.data.materials.new(h); m.diffuse_color = (*hexl(h), 1); m.roughness = rough; MATS[h] = m
    return MATS[h]
def link(o): scene.collection.objects.link(o); return o
def smooth01(u): u = np.clip(u, 0, 1); return u * u * (3 - 2 * u)
import bmesh

# ---------------- meshes ----------------
def crystal_me(name):
    bm = bmesh.new()
    ring0 = [bm.verts.new((math.cos(a), math.sin(a), 0)) for a in np.linspace(0, 2 * math.pi, 7)[:-1]]
    ring1 = [bm.verts.new((math.cos(a), math.sin(a), 0.78)) for a in np.linspace(0, 2 * math.pi, 7)[:-1]]
    tip = bm.verts.new((0, 0, 1.0))
    bm.faces.new(list(reversed(ring0)))
    for k in range(6):
        bm.faces.new((ring0[k], ring0[(k + 1) % 6], ring1[(k + 1) % 6], ring1[k]))
        bm.faces.new((ring1[k], ring1[(k + 1) % 6], tip))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(None); return me
def tile_me():
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.93, radius2=0.85, depth=0.16, matrix=Matrix.Translation((0, 0, 0.08)))
    me = bpy.data.meshes.new('tile'); bm.to_mesh(me); bm.free(); me.materials.append(None); return me
CRY = crystal_me('crystal'); TILE = tile_me()
ICE = ['#dff4ff', '#a9e0ff', '#7cc8ff', '#b3c2ff', '#d6c6ff', '#ffffff', '#8fe3ff']

# ---------------- build order (one slot per onset) ----------------
on = S['onsets']; N = len(on)
slots = []
# 1. hexagonal ice floor spiralling out
hexes = []
for q in range(-8, 9):
    for r in range(-8, 9):
        x = 1.73 * (q + r / 2); y = 1.5 * r
        hexes.append((math.hypot(x, y), math.atan2(y, x), x, y))
hexes.sort(key=lambda h: (round(h[0] / 1.6), (h[1] + math.pi / 2) % (2 * math.pi)))
for d, a, x, y in hexes[:92]:
    slots.append(dict(kind='tile', x=x, y=y, h=1.0, r=1.0))
def ring(n, rad, hmin, hmax, rmin, rmax, start=-math.pi / 2, kind='cry'):
    out = []
    for k in range(n):
        # alternate left/right of the front so the build looks symmetric
        j = (k + 1) // 2 * (1 if k % 2 else -1)
        a = start + j * 2 * math.pi / n
        out.append(dict(kind=kind, x=rad * math.cos(a), y=rad * math.sin(a), h=random.uniform(hmin, hmax), r=random.uniform(rmin, rmax)))
    return out
slots += ring(56, 10.2, 1.2, 2.4, 0.35, 0.55)                      # outer wall
lake = []
for k in range(26):
    a = random.uniform(0, 2 * math.pi); rr = random.uniform(12.5, 17)
    lake.append(dict(kind='cry', x=rr * math.cos(a), y=rr * math.sin(a), h=random.uniform(0.6, 1.6), r=random.uniform(0.25, 0.45)))
lake.sort(key=lambda s: math.atan2(s['y'], s['x']))
slots += lake
slots += ring(42, 7.3, 2.6, 3.6, 0.45, 0.65)                       # inner wall
towers = []
for ti in [0, 3, 1, 4, 2, 5]:
    a = -math.pi / 2 + math.pi / 6 + ti * math.pi / 3
    cx, cy = 8.6 * math.cos(a), 8.6 * math.sin(a)
    for k in range(11):
        aa = k * 2 * math.pi / 11
        towers.append(dict(kind='cry', x=cx + 0.95 * math.cos(aa), y=cy + 0.95 * math.sin(aa), h=random.uniform(4.0, 5.2), r=random.uniform(0.38, 0.5)))
    towers.append(dict(kind='cry', x=cx, y=cy, h=7.8, r=0.75))
slots += towers
slots += ring(30, 4.2, 5.5, 7.5, 0.55, 0.8)                       # keep
slots += ring(12, 2.1, 8.5, 10.5, 0.6, 0.85)                      # inner keep
rest = N - 1 - len(slots)
crown = ring(max(rest, 0), 3.2, 9.5, 12.0, 0.18, 0.3)              # slender crown spikes
for c in crown:
    c['z0'] = 0.0
slots += crown
slots = slots[:N - 1]
slots.append(dict(kind='spire', x=0.0, y=0.0, h=17.0, r=1.15))
assert len(slots) == N, (len(slots), N)

times = np.array([o['t'] for o in on])
# crystals
for k, s in enumerate(slots):
    if s['kind'] == 'tile':
        ob = link(bpy.data.objects.new(f's{k}', TILE)); sc = (1, 1, 1)
        base = hexl(random.choice(['#5aa8e6', '#6fb6ee', '#84c4f4']))
    else:
        ob = link(bpy.data.objects.new(f's{k}', CRY)); sc = (s['r'], s['r'], s['h'])
        base = hexl(random.choice(ICE))
    ob.location = (s['x'], s['y'], 0)
    ob.rotation_euler = (random.uniform(-0.05, 0.05), random.uniform(-0.05, 0.05), random.uniform(0, 1))
    m = bpy.data.materials.new(f'm{k}'); m.roughness = 0.15
    ob.material_slots[0].link = 'OBJECT'; ob.material_slots[0].material = m
    dt_ = ts - times[k]
    g = np.clip(dt_ / 0.28, 0, 1)
    grow = np.where(dt_ < 0, 0.0, np.where(g < 1, 1.18 * np.sin(g * math.pi / 2) ** 1.5, 1 + 0.18 * np.exp(-(dt_ - 0.28) * 9) * np.cos((dt_ - 0.28) * 20)))
    grow = np.maximum(grow, 0.0001)
    if s['kind'] == 'tile':
        for a in range(3): set_curve(ob, 'scale', a, np.clip(grow, 0.0001, 1.1))
    else:
        set_curve(ob, 'scale', 0, s['r'] * np.clip(0.5 + 0.5 * grow, 0.0001, 1.1) * (dt_ >= 0) + 0.0001)
        set_curve(ob, 'scale', 1, s['r'] * np.clip(0.5 + 0.5 * grow, 0.0001, 1.1) * (dt_ >= 0) + 0.0001)
        set_curve(ob, 'scale', 2, s['h'] * grow)
    fl = np.where(dt_ >= 0, np.exp(-dt_ * 6), 0)
    c = base[None] * (1 - fl[:, None]) + np.ones(3)[None] * fl[:, None]
    for ch in range(3): set_curve(m, 'diffuse_color', ch, c[:, ch])

# snowflake emblem on top of the spire at the final chord
TF = times[-1]
emb = bpy.data.objects.new('emblem', None); link(emb); emb.location = (0, 0, 17.6)
for a in range(3):
    bmx = bmesh.new(); bmesh.ops.create_cube(bmx, size=1)
    for v in bmx.verts: v.co.x *= 3.2; v.co.y *= 0.12; v.co.z *= 0.22
    me = bpy.data.meshes.new(f'arm{a}'); bmx.to_mesh(me); bmx.free(); me.materials.append(M('#ffffff'))
    o = link(bpy.data.objects.new(f'arm{a}', me)); o.parent = emb; o.rotation_euler = (math.pi / 2, math.radians(60 * a), 0)
    for side in (-1, 1):
        for bb in (-1, 1):
            bmx = bmesh.new(); bmesh.ops.create_cube(bmx, size=1)
            for v in bmx.verts: v.co.x *= 0.9; v.co.y *= 0.1; v.co.z *= 0.16
            me = bpy.data.meshes.new('tw'); bmx.to_mesh(me); bmx.free(); me.materials.append(M('#ffffff'))
            tw = link(bpy.data.objects.new('tw', me)); tw.parent = o
            tw.location = (side * 2.1, 0, 0); tw.rotation_euler = (0, bb * side * math.radians(55), 0)
de = ts - TF
es = 1.6 * np.where(de < 0, 0.0001, np.clip(1.15 * smooth01(de / 0.5) - 0.15 * smooth01((de - 0.5) / 0.4), 0.0001, 2))
for a in range(3): set_curve(emb, 'scale', a, es)
set_curve(emb, 'rotation_euler', 2, np.where(de > 0, de * 0.6, 0))
set_curve(emb, 'location', 2, np.full(NF, 19.6))
set_curve(emb, 'rotation_euler', 0, np.full(NF, 0.0))

# the magic orb visiting every slot
pts = []
for s in slots:
    zt = 0.3 if s['kind'] == 'tile' else min(s['h'] * 0.6, 6.0)
    pts.append((s['x'], s['y'], zt))
pts = np.array(pts)
kt = np.concatenate([[0.0], times]); kp = np.vstack([[[0, -14, 6]], pts])
from scipy.interpolate import CubicSpline
cs = CubicSpline(kt, kp, bc_type='natural')
OP = cs(np.clip(ts, 0, times[-1]))
OP[:, 2] = np.maximum(OP[:, 2], 0.3)
for j, (sz, lag) in enumerate([(0.38, 0.0), (0.26, 0.05), (0.19, 0.1), (0.14, 0.15), (0.1, 0.2)]):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=sz)
    o = bpy.context.active_object; o.data.materials.append(M('#ffffff' if j == 0 else '#bfe7ff'))
    P = cs(np.clip(ts - lag, 0, times[-1])); P[:, 2] = np.maximum(P[:, 2], 0.3)
    vis = ts < TF + 0.3
    for a in range(3): set_curve(o, 'location', a, np.where(vis, P[:, a], P[-1, a] if a < 2 else -50))

# ---------------- world: frozen lake, mountains, aurora, stars, snow ----------------
world = bpy.data.worlds.new('w'); world.color = tuple(hexl('#060c24')); scene.world = world
bpy.ops.mesh.primitive_circle_add(vertices=96, radius=400, fill_type='NGON'); lake_o = bpy.context.active_object
lake_o.data.materials.append(M('#20385f', 0.1))
for k in range(28):
    a = k * 2 * math.pi / 28 + random.uniform(-0.05, 0.05); rr = random.uniform(170, 230); h = random.uniform(22, 48); w = random.uniform(40, 70)
    bpy.ops.mesh.primitive_cone_add(radius1=w, radius2=0, depth=h, vertices=7, location=(rr * math.cos(a), rr * math.sin(a), h / 2 - 2))
    c = bpy.context.active_object; c.data.materials.append(M('#111a38', 0.8))
    bpy.ops.mesh.primitive_cone_add(radius1=w * 0.28, radius2=0, depth=h * 0.28, vertices=7, location=(rr * math.cos(a), rr * math.sin(a), h - h * 0.14 - 2))
    c2 = bpy.context.active_object; c2.data.materials.append(M('#dbe8ff', 0.8)); c2.location = (rr * 0.995 * math.cos(a), rr * 0.995 * math.sin(a), h - h * 0.14 - 2)
bm = bmesh.new()
for k in range(900):
    th = random.uniform(0, 2 * math.pi); ph = random.uniform(0.12, 1.3); rr = 380
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=random.choice([0.6, 0.9, 1.3]),
                               matrix=Matrix.Translation((rr * math.cos(ph) * math.cos(th), rr * math.cos(ph) * math.sin(th), rr * math.sin(ph))))
me = bpy.data.meshes.new('stars'); bm.to_mesh(me); bm.free(); me.materials.append(M('#e8efff', 1.0)); link(bpy.data.objects.new('stars', me))
# aurora curtains (arcs high in the sky)
for i, (col, z0, hh, ph0) in enumerate([('#2fe0a0', 70, 30, 0.0), ('#18a27c', 95, 25, 1.0), ('#7a5cff', 110, 22, 2.0), ('#33d9c9', 60, 18, 3.1)]):
    bm = bmesh.new(); vt = []; vb = []
    angs = np.linspace(math.radians(30), math.radians(150), 120)
    for a in angs:
        rr = 300 + 25 * math.sin(a * 5 + ph0)
        z = z0 + 12 * math.sin(a * 7 + ph0)
        vb.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z))); vt.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z + hh)))
    for k in range(len(angs) - 1): bm.faces.new((vb[k], vb[k + 1], vt[k + 1], vt[k]))
    me = bpy.data.meshes.new(f'aur{i}'); bm.to_mesh(me); bm.free(); me.materials.append(M(col, 1.0))
    o = link(bpy.data.objects.new(f'aur{i}', me))
    set_curve(o, 'rotation_euler', 2, 0.03 * np.sin(ts * 0.3 + i))
snow_me = bpy.data.meshes.new('flk'); bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1); bm.to_mesh(snow_me); bm.free()
snow_me.materials.append(M('#ffffff', 1.0))
for i in range(260):
    o = link(bpy.data.objects.new(f'sn{i}', snow_me)); r = random.uniform(0.05, 0.12); o.scale = (r, r, r)
    x0, y0, z0 = random.uniform(-26, 26), random.uniform(-26, 26), random.uniform(0, 30); sp = random.uniform(0.8, 1.6)
    set_curve(o, 'location', 0, x0 + 0.6 * np.sin(ts * 0.8 + i)); set_curve(o, 'location', 1, np.full(NF, y0))
    set_curve(o, 'location', 2, (z0 - sp * ts) % 30)

# ---------------- camera: slow orbit, rising ----------------
cd = bpy.data.cameras.new('cam'); cd.lens = 26; cd.sensor_fit = 'VERTICAL'; cd.sensor_height = 36; cd.clip_end = 1500
cam = link(bpy.data.objects.new('cam', cd)); scene.camera = cam; cam.rotation_mode = 'XYZ'
u = ts / END
ang = math.radians(-118) + math.radians(85) * smooth01(u)
rad = 15.5 + 9.5 * smooth01(u * 1.15) + 3 * smooth01((ts - TF) / 4)
hgt = 4.5 + 9.5 * smooth01(u)
look = np.stack([np.zeros(NF), np.zeros(NF), 1.0 + 7.0 * smooth01(u)], 1)
CP = np.stack([rad * np.cos(ang), rad * np.sin(ang), hgt], 1)
rot = []
for n in range(NF):
    fwd = Vector(look[n]) - Vector(CP[n]); rot.append(tuple(fwd.to_track_quat('-Z', 'Y').to_euler()))
rot = np.unwrap(np.array(rot), axis=0)
for a in range(3): set_curve(cam, 'location', a, CP[:, a]); set_curve(cam, 'rotation_euler', a, rot[:, a])

scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
scene.display.render_aa = 'FXAA'
sh = scene.display.shading
sh.light = 'STUDIO'; sh.studio_light = 'outdoor.sl'; sh.color_type = 'MATERIAL'
sh.show_shadows = True; sh.shadow_intensity = 0.35; sh.show_cavity = True; sh.cavity_type = 'BOTH'
sh.show_specular_highlight = True
scene.display.light_direction = (0.3, -0.5, 0.8)
scene.view_settings.view_transform = 'Standard'
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/ice/ice.blend')
print('BUILT', NF, 'slots', len(slots), 'crown', rest)
