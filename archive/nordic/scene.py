import bpy, math, json, random, colorsys
import numpy as np
from mathutils import Vector, Matrix

S = json.load(open('/home/claude/nordic/score.json'))
FPS = 30; END = S['END']; NF = int(END * FPS) + 1
ts = np.arange(NF) / FPS
random.seed(7); np.random.seed(7)
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
def M(h):
    if h not in MATS:
        m = bpy.data.materials.new(h); m.diffuse_color = (*hexl(h), 1); MATS[h] = m
    return MATS[h]

ARM = bpy.data.collections.new('arm')          # one wedge; instanced 6x
def link_arm(o): ARM.objects.link(o); return o
def link(o): scene.collection.objects.link(o); return o

# ---------------- geometry of the stitching ----------------
on = S['onsets']; NL = S['layers']
RJ = [4.0, 6.5, 10.0, 14.0, 18.5, 23.5, 29.0]
LAYER_COL = ['#bff6ff', '#7fe3ff', '#59ffb0', '#3dd6c4', '#9b8cff', '#d77bff', '#ffd27a']
A_DIR = np.array([math.sin(math.radians(30)), math.cos(math.radians(30))])
B_DIR = np.array([-A_DIR[0], A_DIR[1]])
pts = []; layer_of = []
for L in range(NL):
    idx = [i for i, o in enumerate(on) if o['layer'] == L]
    n = len(idx)
    for j, i in enumerate(idx):
        s = (j + 0.5) / n
        if j % 2 == 0: p = A_DIR * RJ[L] * s
        else: p = B_DIR * RJ[L] * (1 - s)
        pts.append(p); layer_of.append(L)
pts = np.array(pts); times = np.array([o['t'] for o in on])
NP = len(pts)

# unit meshes
import bmesh
def cyl_mesh(name, verts=6):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=1, radius2=1, depth=1,
                          matrix=Matrix.Translation((0, 0, 0.5)))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); return me
trail_me = cyl_mesh('trail', 6)
def crystal_mesh():
    bm = bmesh.new()
    top = bm.verts.new((0, 0, 1)); bot = bm.verts.new((0, 0, -1))
    ring = [bm.verts.new((0.28 * math.cos(a), 0.28 * math.sin(a), 0)) for a in np.linspace(0, 2 * math.pi, 7)[:-1]]
    for k in range(6):
        bm.faces.new((top, ring[k], ring[(k + 1) % 6])); bm.faces.new((bot, ring[(k + 1) % 6], ring[k]))
    me = bpy.data.meshes.new('crystal'); bm.to_mesh(me); bm.free(); return me
crys_me = crystal_mesh()
trail_me.materials.append(None); crys_me.materials.append(None)

def look_dir_euler(d2):
    """rotation taking local +Z to direction (dx, 0, dz) in the x-z plane"""
    v = Vector((d2[0], 0, d2[1])).normalized()
    return v.to_track_quat('Z', 'Y').to_euler()

white = np.ones(3)
for k in range(NP):
    L = layer_of[k]; col = hexl(LAYER_COL[L])
    # crystal at the bounce point (oriented along its wall)
    wall = A_DIR if np.dot(pts[k], A_DIR) >= np.dot(pts[k], B_DIR) - 1e-9 and (k == 0 or True) else B_DIR
    wall = A_DIR if (k - [i for i in range(NP) if layer_of[i] == L][0]) % 2 == 0 else B_DIR
    c = bpy.data.objects.new(f'c{k}', crys_me); link_arm(c)
    sz = 0.18 + 0.035 * RJ[L]
    c.scale = (sz, sz, sz * 1.6)
    c.location = (pts[k][0], -0.03 + 0.06 * L, pts[k][1])
    c.rotation_euler = look_dir_euler(wall)
    m = bpy.data.materials.new(f'cm{k}')
    c.material_slots[0].link = 'OBJECT'; c.material_slots[0].material = m
    dt_ = ts - times[k]
    lit = (dt_ >= 0).astype(float); fl = np.where(dt_ >= 0, np.exp(-dt_ * 7), 0)
    dim = col * 0.12
    cc = dim[None] * (1 - lit[:, None]) + col[None] * lit[:, None]
    cc = cc * (1 - fl[:, None]) + white[None] * fl[:, None]
    for ch in range(3): set_curve(m, 'diffuse_color', ch, cc[:, ch])
    pop = 1 + np.where((dt_ > 0) & (dt_ < 0.25), np.sin(np.clip(dt_ / 0.25, 0, 1) * math.pi) * 0.8, 0)
    lstart = times[[i for i in range(NP) if layer_of[i] == L][0]]
    for a, base in enumerate((sz, sz, sz * 1.6)): set_curve(c, 'scale', a, base * pop * np.where(ts > lstart - 0.3, 1, 0.0001))
    # trail to the next point, drawn while the orb flies
    if k < NP - 1:
        p0, p1 = pts[k], pts[k + 1]; seg = p1 - p0; Ls = np.linalg.norm(seg)
        if Ls < 1e-4: continue
        tr = bpy.data.objects.new(f't{k}', trail_me); link_arm(tr)
        rad = 0.018 + 0.0045 * RJ[layer_of[k + 1]]
        tr.location = (p0[0], 0.02 + 0.06 * layer_of[k + 1], p0[1]); tr.rotation_euler = look_dir_euler(seg)
        u = np.clip((ts - times[k]) / max(times[k + 1] - times[k], 1e-3), 0, 1)
        rr_ = np.where(ts >= times[k], rad, 0.0001)
        set_curve(tr, 'scale', 0, rr_); set_curve(tr, 'scale', 1, rr_)
        set_curve(tr, 'scale', 2, np.maximum(u * Ls, 1e-4))
        tm = bpy.data.materials.new(f'tm{k}')
        tr.material_slots[0].link = 'OBJECT'; tr.material_slots[0].material = tm
        lc = hexl(LAYER_COL[layer_of[k + 1]])
        drawn = np.where(ts < times[k + 1], 1.0, np.exp(-(ts - times[k + 1]) * 3))
        cc = lc[None] * 0.75 + (white * 0.25)[None] * 0 + (white - lc * 0.75)[None] * (drawn[:, None] * 0.6)
        for ch in range(3): set_curve(tm, 'diffuse_color', ch, cc[:, ch])

# the orb
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1)
orb = bpy.context.active_object
scene.collection.objects.unlink(orb); link_arm(orb)
orb.data.materials.append(M('#ffffff'))
ox = np.interp(ts, np.concatenate([[0.2], times]), np.concatenate([[0.0], pts[:, 0]]))
oz = np.interp(ts, np.concatenate([[0.2], times]), np.concatenate([[0.0], pts[:, 1]]))
set_curve(orb, 'location', 0, ox); set_curve(orb, 'location', 2, oz); set_curve(orb, 'location', 1, np.full(NF, -0.05))
Rcur = np.interp(ts, times, [RJ[l] for l in layer_of])
orad = 0.16 + 0.02 * Rcur
for a in range(3): set_curve(orb, 'scale', a, orad)
# faint spokes (walls)

# 6 instances of the wedge, slowly turning as a whole
root = bpy.data.objects.new('flake', None); link(root)
set_curve(root, 'rotation_euler', 1, np.radians(3.0) * ts)
for k in range(6):
    e = bpy.data.objects.new(f'inst{k}', None); link(e)
    e.instance_type = 'COLLECTION'; e.instance_collection = ARM
    e.rotation_euler = (0, math.radians(60 * k), 0); e.parent = root
# centre emblem
bpy.ops.mesh.primitive_circle_add(vertices=6, radius=0.9, fill_type='NGON')
hexo = bpy.context.active_object; hexo.rotation_euler = (math.pi / 2, 0, 0); hexo.location = (0, -0.1, 0)
hexo.data.materials.append(M('#ffffff')); hexo.parent = root

# ---------------- Nordic night backdrop ----------------
world = bpy.data.worlds.new('w'); world.color = tuple(hexl('#050a1d')); scene.world = world
YB = 420
def ribbon(name, z0, amp, ph, col, h, freq=0.012):
    bm = bmesh.new(); xs = np.linspace(-700, 700, 160); vt = []; vb = []
    for x in xs:
        z = z0 + amp * math.sin(x * freq + ph) + 0.35 * amp * math.sin(x * freq * 2.3 + ph * 1.7)
        vt.append(bm.verts.new((x, 0, z + h))); vb.append(bm.verts.new((x, 0, z)))
    for i in range(len(xs) - 1): bm.faces.new((vb[i], vb[i + 1], vt[i + 1], vt[i]))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(M(col))
    o = link(bpy.data.objects.new(name, me)); o.location = (0, YB, 0)
    set_curve(o, 'location', 0, 30 * np.sin(ts * 0.25 + ph))
    return o
for i, (z0, amp, ph, col, h) in enumerate([(40, 35, 0.0, '#0f5a4a', 70), (55, 35, 0.0, '#1d9c6c', 22), (60, 30, 1.2, '#3a2f7a', 60),
                                           (75, 28, 1.2, '#5f3fa8', 14), (20, 30, 2.4, '#0c3d4f', 40), (28, 30, 2.4, '#21b38a', 10)]):
    ribbon(f'aurora{i}', z0, amp, ph, col, h)
# stars
bm = bmesh.new()
for k in range(700):
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=random.choice([0.5, 0.8, 1.1]),
                               matrix=Matrix.Translation((random.uniform(-500, 500), YB + 60, random.uniform(-80, 320))))
me = bpy.data.meshes.new('stars'); bm.to_mesh(me); bm.free(); me.materials.append(M('#dfe8ff'))
link(bpy.data.objects.new('stars', me))
# mountains (fjord silhouettes) with snow caps
bm = bmesh.new(); bm2 = bmesh.new()
x = -650
while x < 650:
    w = random.uniform(60, 130); h = random.uniform(50, 120); base = -150
    a = bm.verts.new((x, -2, base)); b = bm.verts.new((x + w, -2, base)); c = bm.verts.new((x + w / 2, -2, base + h))
    bm.faces.new((a, b, c))
    f = 0.22
    a2 = bm2.verts.new((x + w / 2 - w / 2 * f, -3, base + h * (1 - f))); b2 = bm2.verts.new((x + w / 2 + w / 2 * f, -3, base + h * (1 - f)))
    c2 = bm2.verts.new((x + w / 2, -3, base + h)); bm2.faces.new((a2, b2, c2))
    x += w * random.uniform(0.45, 0.75)
for nm, bmx, col in (('mount', bm, '#0b1330'), ('snowcap', bm2, '#cfe0ff')):
    me = bpy.data.meshes.new(nm); bmx.to_mesh(me); bmx.free(); me.materials.append(M(col))
    o = link(bpy.data.objects.new(nm, me)); o.location = (0, YB - 80, 0)
# falling snow
bm = bmesh.new()
flakes = []
for k in range(350):
    flakes.append((random.uniform(-260, 260), random.uniform(40, 260), random.uniform(-150, 250), random.uniform(0.25, 0.7)))
for i, (x, y, z, r) in enumerate(flakes):
    pass
snow_me = bpy.data.meshes.new('flake')
bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1); bm.to_mesh(snow_me); bm.free()
snow_me.materials.append(M('#f2f6ff'))
for i, (x, y, z, r) in enumerate(flakes):
    o = link(bpy.data.objects.new(f'sn{i}', snow_me)); o.scale = (r, r, r)
    sp_ = random.uniform(4, 9)
    zz = ((z - sp_ * ts + 150) % 400) - 150
    set_curve(o, 'location', 0, x + 3 * np.sin(ts * 0.7 + i)); set_curve(o, 'location', 1, np.full(NF, y)); set_curve(o, 'location', 2, zz)

# ---------------- camera ----------------
cd = bpy.data.cameras.new('cam'); cd.lens = 35; cd.sensor_fit = 'VERTICAL'; cd.sensor_height = 36; cd.clip_end = 3000
cam = link(bpy.data.objects.new('cam', cd)); scene.camera = cam; cam.rotation_mode = 'XYZ'
need = np.maximum(3.9 * np.maximum.accumulate(np.interp(ts + 0.6, times, [RJ[l] for l in layer_of])), 15)
def gs(a, sg):
    r = int(3 * sg); k = np.exp(-0.5 * (np.arange(-r, r + 1) / sg) ** 2); k /= k.sum()
    return np.convolve(np.pad(a, r, mode='edge'), k, 'valid')
H = gs(need, 25)
EM = S['end_music']
H = H * (1 + 0.12 * np.clip((ts - EM) / 3, 0, 1))
dist = H / 2 / (18 / 35)
set_curve(cam, 'location', 1, -dist); set_curve(cam, 'location', 2, np.full(NF, 0.0))
set_curve(cam, 'rotation_euler', 0, np.full(NF, math.pi / 2))

scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
scene.display.render_aa = 'FXAA'
sh = scene.display.shading
sh.light = 'FLAT'; sh.color_type = 'MATERIAL'; sh.show_shadows = False; sh.show_cavity = False
scene.view_settings.view_transform = 'Standard'
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/nordic/nordic.blend')
print('BUILT', NF, 'points', NP)
