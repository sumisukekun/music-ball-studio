import bpy, math, json, random, colorsys
import numpy as np
from mathutils import Vector, Matrix

D = json.load(open('/home/claude/vegas2/paths.json'))
FPS = 30; END = D['END']; NF = int(END * FPS) + 1
ts = np.arange(NF) / FPS
G = D['G']; R = D['R']
random.seed(5); np.random.seed(5)
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
def srgb(h):
    h = h.lstrip('#'); return tuple(lin([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]))
MATS = {}
def M(h):
    if h not in MATS:
        m = bpy.data.materials.new(h); m.diffuse_color = (*srgb(h), 1); MATS[h] = m
    return MATS[h]
def link(o): scene.collection.objects.link(o); return o
def box_mesh(name, x0, x1, y0, y1, z0, z1):
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts:
        v.co.x = (v.co.x + .5) * (x1 - x0) + x0; v.co.y = (v.co.y + .5) * (y1 - y0) + y0; v.co.z = (v.co.z + .5) * (z1 - z0) + z0
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.03, segments=1, affect='EDGES')
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); return me
def cyl_y(name, r, depth, col, verts=32):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, vertices=verts)
    o = bpy.context.active_object; o.name = name
    o.data.transform(Matrix.Rotation(math.pi / 2, 4, 'X'))
    o.data.materials.append(M(col) if isinstance(col, str) else col)
    return o
FONT = bpy.data.fonts.load('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
def text(body, size, col, loc, extrude=0.08):
    bpy.ops.object.text_add()
    t = bpy.context.active_object
    t.data.body = body; t.data.size = size; t.data.align_x = 'CENTER'; t.data.align_y = 'CENTER'
    t.data.extrude = extrude; t.data.font = FONT
    t.data.materials.append(M(col) if isinstance(col, str) else col)
    t.location = loc; t.rotation_euler = (math.pi / 2, 0, 0)
    return t

def pitch_rgb(m, v=1.0, sat=0.85):
    h = ((m % 12) / 12.0 + 0.55) % 1.0
    return np.array(colorsys.hsv_to_rgb(h, sat, v))

# ---------------- platforms ----------------
plat_me = box_mesh('plat', -0.55, 0.55, -0.45, 0.45, -0.09, 0.09)
gold_me = box_mesh('gold', -1.9, 1.9, -0.6, 0.6, -0.22, 0.22)
CHIP = [('#e8203a', '#ffffff'), ('#1e6bff', '#ffffff')]
ball_pos = []
for b, p in enumerate(D['paths']):
    times = np.array(p['times']); xs = np.array(p['xs']); zs = np.array(p['zs'])
    nrm = np.array(p['nrm']); vout = np.array(p['vout'])
    n = len(times)
    for k in range(n):
        last = k == n - 1
        me = gold_me if last else plat_me
        ob = bpy.data.objects.new(f'p{b}_{k}', me); link(ob)
        nx, nz = nrm[k] if not last else (0.0, 1.0)
        cx = xs[k] - nx * (R + (0.22 if last else 0.09)); cz = zs[k] - nz * (R + (0.22 if last else 0.09))
        ang = math.atan2(nz, nx) - math.pi / 2
        ob.rotation_euler = (0, -ang, 0)
        m = bpy.data.materials.new(f'pm{b}_{k}')
        ob.data.materials.clear() if False else None
        ob.material_slots and None
        ob.data = me
        slot_m = m
        ob.active_material = None
        ob.material_slots
        # object-linked material
        if len(ob.material_slots) == 0:
            me.materials.append(None) if len(me.materials) == 0 else None
        ob.material_slots[0].link = 'OBJECT'; ob.material_slots[0].material = m
        top = max(mm for mm, _ in p['notes'][k])
        if last:
            dim = lin([0.45, 0.33, 0.05]); lit = lin([1.0, 0.85, 0.2])
        else:
            dim = pitch_rgb(top, 0.28, 0.7); lit = pitch_rgb(top, 1.0)
        dt_ = ts - times[k]
        flash = np.where(dt_ >= 0, np.exp(-dt_ * 10), 0)
        on = (dt_ >= 0).astype(float)
        if last:
            on = np.where(dt_ >= 0, 0.6 + 0.4 * (np.floor(dt_ * 8) % 2), 0)
        c = dim[None] * (1 - on[:, None]) + lit[None] * on[:, None]
        c = c * (1 - flash[:, None]) + np.ones(3)[None] * flash[:, None]
        for ch in range(3): set_curve(m, 'diffuse_color', ch, c[:, ch])
        # small dip on impact
        dip = np.where((dt_ > 0) & (dt_ < 0.15), np.sin(np.clip(dt_ / 0.15, 0, 1) * math.pi) * 0.12, 0)
        set_curve(ob, 'location', 0, cx - nx * dip); set_curve(ob, 'location', 2, cz - nz * dip)
        set_curve(ob, 'location', 1, np.zeros(NF))
        if last:
            tx = text('JACKPOT', 0.55, '#ff2bd6', (xs[k], -0.65, cz - 0.02), extrude=0.03)
    # ball trajectory
    P = np.zeros((NF, 2)); t0 = times[0]
    tdrop = 0.55
    for f, t in enumerate(ts):
        if t < t0:
            tau = t0 - t
            P[f] = (xs[0], zs[0] + (0.5 * G * tau * tau + 6.0 * tau) if tau < tdrop else zs[0] + 0.5 * G * tdrop ** 2 + 6 * tdrop)
            continue
        k = min(np.searchsorted(times, t, side='right') - 1, n - 1)
        if k == n - 1:
            tau = t - times[k]
            hop = max(0.0, 3.0 * tau - 0.5 * G * tau * tau) if tau < 0.18 else 0.0
            P[f] = (xs[k], zs[k] + hop); continue
        tau = t - times[k]
        P[f] = (xs[k] + vout[k, 0] * tau, zs[k] + vout[k, 1] * tau - 0.5 * G * tau * tau)
    ball_pos.append(P)
    chip = cyl_y(f'chip{b}', R, 0.24, CHIP[b][0], 40)
    inner = cyl_y(f'ci{b}', R * 0.62, 0.26, '#ffffff', 32); inner.parent = chip
    inner2 = cyl_y(f'ci2{b}', R * 0.5, 0.28, CHIP[b][0], 32); inner2.parent = chip
    for a in range(6):
        st = bpy.data.objects.new(f'st{b}{a}', box_mesh('st', -0.06, 0.06, -0.13, 0.13, R * 0.72, R * 0.98)); link(st)
        st.data.materials.append(M('#ffffff')); st.parent = chip; st.rotation_euler = (0, a * math.pi / 3, 0)
    set_curve(chip, 'location', 0, P[:, 0]); set_curve(chip, 'location', 2, P[:, 1])
    spin = np.cumsum(np.diff(P[:, 0], prepend=P[0, 0])) / R
    set_curve(chip, 'rotation_euler', 1, spin)

# ---------------- Vegas backdrop (parallax) ----------------
XMAX = max(max(p['xs']) for p in D['paths']) + 30
signs = ['LAS VEGAS', 'CASINO', '777', 'JACKPOT', 'LUCKY', 'WIN BIG', 'ALL IN', '$$$']
neon = ['#ff2bd6', '#00f0ff', '#ffe600', '#39ff88', '#ff8a1c', '#b04bff']
x = -10; i = 0
while x < XMAX * 1.0:
    z = random.uniform(-150, 25)
    text(signs[i % len(signs)], random.uniform(3, 6), neon[i % len(neon)], (x * 0.85, 45, -0.0 * x + z), extrude=0.2)
    x += random.uniform(16, 26); i += 1
import bmesh
bm = bmesh.new()
for k in range(1400):
    xx = random.uniform(-40, XMAX * 0.9); zz = random.uniform(-170, 40); yy = random.uniform(20, 70)
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=random.choice([0.12, 0.2, 0.3]), matrix=Matrix.Translation((xx, yy, zz)))
me = bpy.data.meshes.new('lights'); bm.to_mesh(me); bm.free()
me.materials.append(M('#ffd36b'))
link(bpy.data.objects.new('lights', me))
back = bpy.data.objects.new('back', box_mesh('back', -200, XMAX + 200, 80, 81, -400, 200)); link(back)
back.data.materials.append(M('#0c0418'))
# intro sign



# ---------------- coins at the jackpot ----------------
TE = D['T_END']
for b, p in enumerate(D['paths']):
    jx, jz = p['xs'][-1], p['zs'][-1]
    for k in range(110):
        c = cyl_y(f'coin{b}_{k}', 0.26, 0.07, '#ffcf3a', 18)
        vx = random.uniform(-6, 6); vz = random.uniform(8, 17); vy = random.uniform(-2.5, 0)
        t = ts - TE - random.uniform(0, 4.0); tt_ = np.clip(t, 0, None)
        vis = t > 0
        set_curve(c, 'location', 0, np.where(vis, jx + vx * tt_, 0))
        set_curve(c, 'location', 1, np.where(vis, -0.6 + vy * tt_, 5))
        set_curve(c, 'location', 2, np.where(vis, np.maximum(jz + vz * tt_ - 10 * tt_ ** 2, jz - 40), -900))
        sp = np.random.randn(3) * 10
        for a in range(3): set_curve(c, 'rotation_euler', a, sp[a] * tt_)

# ---------------- camera ----------------
cd = bpy.data.cameras.new('cam'); cd.lens = 32; cd.sensor_fit = 'VERTICAL'; cd.sensor_height = 36; cd.clip_end = 900
cam = link(bpy.data.objects.new('cam', cd)); scene.camera = cam; cam.rotation_mode = 'XYZ'
mid = (ball_pos[0] + ball_pos[1]) / 2
def gs(a, sg):
    r = int(3 * sg); k = np.exp(-0.5 * (np.arange(-r, r + 1) / sg) ** 2); k /= k.sum()
    return np.convolve(np.pad(a, r, mode='edge'), k, 'valid')
cx = gs(mid[:, 0], 12); cz = gs(mid[:, 1], 12)
VH = 19.0
dist = VH / 2 / (18 / 32)
pull = np.clip((ts - TE - 0.3) / 2.5, 0, 1); pull = pull * pull * (3 - 2 * pull)
shake = np.where(ts > TE, np.exp(-(ts - TE) * 4) * 0.4, 0)
set_curve(cam, 'location', 0, cx + shake * np.sin(ts * 61))
set_curve(cam, 'location', 1, -dist * (1 + 0.15 * pull))
set_curve(cam, 'location', 2, cz + shake * np.cos(ts * 47))
set_curve(cam, 'rotation_euler', 0, np.full(NF, math.pi / 2))

scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
scene.display.render_aa = 'FXAA'
sh = scene.display.shading
sh.light = 'FLAT'; sh.color_type = 'MATERIAL'
sh.show_shadows = False; sh.show_cavity = True; sh.cavity_type = 'BOTH'
scene.view_settings.view_transform = 'Standard'
world = bpy.data.worlds.new('w'); world.color = srgb('#05020b'); scene.world = world
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/vegas2/bounce.blend')
print('BUILT', NF)
