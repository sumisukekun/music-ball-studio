import bpy, math, json, random
import numpy as np
from mathutils import Vector, Matrix

B = json.load(open('/home/claude/vegas/board.json'))
T = json.load(open('/home/claude/vegas/timing.json'))
RS = np.load('/home/claude/vegas/simres.npz')
FPS = 30; END = T['END']; NF = int(END * FPS) + 1
ts = np.arange(NF) / FPS
random.seed(9); np.random.seed(9)
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
def srgb(h):
    h = h.lstrip('#'); c = np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])
    return tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4))
MATS = {}
def M(h):
    if h not in MATS:
        m = bpy.data.materials.new(h); m.diffuse_color = (*srgb(h), 1); MATS[h] = m
    return MATS[h]
def link(o): scene.collection.objects.link(o); return o
def box(name, x0, x1, y0, y1, z0, z1, col):
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts:
        v.co.x = (v.co.x + .5) * (x1 - x0) + x0; v.co.y = (v.co.y + .5) * (y1 - y0) + y0; v.co.z = (v.co.z + .5) * (z1 - z0) + z0
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(M(col) if isinstance(col, str) else col)
    return link(bpy.data.objects.new(name, me))
def cyl_y(name, r, depth, col, verts=32):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, vertices=verts)
    o = bpy.context.active_object; o.name = name
    o.data.transform(Matrix.Rotation(math.pi / 2, 4, 'X'))
    o.data.materials.append(M(col) if isinstance(col, str) else col)
    return o
def seg_box(name, x1, z1, x2, z2, th, col, y0=-0.6, y1=0.6):
    L = math.hypot(x2 - x1, z2 - z1)
    o = box(name, -L / 2, L / 2, y0, y1, -th / 2, th / 2, col)
    o.location = ((x1 + x2) / 2, 0, (z1 + z2) / 2)
    o.rotation_euler = (0, -math.atan2(z2 - z1, x2 - x1), 0)
    return o
def text(body, size, col, loc, align='CENTER', extrude=0.05):
    bpy.ops.object.text_add()
    t = bpy.context.active_object
    t.data.body = body; t.data.size = size; t.data.align_x = align; t.data.align_y = 'CENTER'
    t.data.extrude = extrude
    try:
        t.data.font = bpy.data.fonts.load('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', check_existing=True)
    except Exception:
        pass
    t.data.materials.append(M(col) if isinstance(col, str) else col)
    t.location = loc; t.rotation_euler = (math.pi / 2, 0, 0)
    return t

W = B['W']; TOP = 3.5; BOT = B['FLOOR'] - 1.2
NEON = ['#00f0ff', '#ff2bd6', '#ffe600', '#39ff88']
# ---------------- board ----------------
box('backplate', -W, W, 0.6, 0.9, BOT, TOP + 1, '#170b2e')
box('outer', -W - 3, W + 3, 0.95, 1.2, BOT - 3, TOP + 14, '#07030f')
for sx in (-1, 1):
    box(f'rail{sx}', sx * W - 0.35, sx * W + 0.35, -0.8, 0.9, BOT, TOP + 1, '#f5c542')
box('railtop', -W - 0.35, W + 0.35, -0.8, 0.9, TOP + 0.6, TOP + 1.3, '#f5c542')
box('railbot', -W - 0.35, W + 0.35, -0.8, 0.9, BOT - 0.4, BOT + 0.3, '#f5c542')
for k, (x, z, r, e, kind) in enumerate(B['pegs']):
    if kind == 0:
        o = cyl_y(f'peg{k}', r, 0.5, NEON[int(round(-z / 1.9)) % 3], 16)
        cap = cyl_y(f'pegc{k}', r * 0.45, 0.55, '#ffffff', 12); cap.parent = o
    else:
        o = cyl_y(f'bump{k}', r, 1.2, '#39ff88', 48)
        ring = cyl_y(f'bumpr{k}', r * 0.72, 1.26, '#0a3b22', 48); ring.parent = o
        cen = cyl_y(f'bumpc{k}', r * 0.4, 1.3, '#ffffff', 32); cen.parent = o
    o.location = (x, 0, z)
SEGCOL = {1: '#ff2bd6', 2: '#00f0ff', 3: '#f5c542', 4: '#f5c542'}
for k, (x1, z1, x2, z2, e, f, kind) in enumerate(B['segs']):
    if kind == 0: continue
    seg_box(f'seg{k}', x1, z1, x2, z2, 0.3, SEGCOL[int(kind)])
# spinners
gate, s = T['gate'], T['s']
tsim = np.clip((ts - gate) / s, 0, None)
for k, (cx, cz, arm, na, w, ph) in enumerate(B['spinners']):
    hub = bpy.data.objects.new(f'spin{k}', None); link(hub); hub.location = (cx, 0, cz)
    for a in range(int(na)):
        o = box(f'arm{k}_{a}', 0, arm, -0.5, 0.5, -0.14, 0.14, '#f5c542'); o.parent = hub
        o.rotation_euler = (0, -(2 * math.pi * a / na), 0)
        tip = cyl_y(f'tip{k}_{a}', 0.2, 1.1, '#ff2bd6', 16); tip.parent = o; tip.location = (arm, 0, 0)
    h = cyl_y(f'hub{k}', 0.55, 1.3, '#ff3355', 32); h.parent = hub
    h2 = cyl_y(f'hubc{k}', 0.25, 1.35, '#ffffff', 16); h2.parent = hub
    set_curve(hub, 'rotation_euler', 1, -(ph + w * tsim))
# start gate bar
gbar = box('gate', -W, W, -0.6, 0.6, 0.3, 0.6, '#ff2bd6')
set_curve(gbar, 'location', 0, np.where(ts < gate, 0.0, -30.0), interp=0)

# slots: panels that flash when a chip lands, labels
NS = B['NS']; SW = 2 * W / NS
panels = []
for k in range(NS):
    x0 = -W + k * SW
    m = bpy.data.materials.new(f'slotpanel{k}')
    p = box(f'slotp{k}', x0 + 0.1, x0 + SW - 0.1, 0.5, 0.58, B['FLOOR'], B['SLOT_TOP'] + 0.4, m)
    panels.append(m)
    col = '#ff3355' if k == B['JACKPOT'] else '#f5c542'
    text(B['LABELS'][k], 0.62 if k != B['JACKPOT'] else 0.7, col, (x0 + SW / 2, -0.7, B['FLOOR'] - 0.7))
base_dark = np.array(srgb('#241045')); flash = np.array(srgb('#ffe066'))
for k in range(NS):
    lvl = np.zeros(NF)
    for i in range(8):
        if T['sl'][i] == k:
            tl = gate + T['lt'][i] * s
            dt_ = ts - tl
            lvl = np.maximum(lvl, np.where(dt_ >= 0, 0.35 + 0.65 * np.exp(-dt_ * 3), 0))
    if k == B['JACKPOT']:
        dt_ = ts - T['T_LAND']
        strobe = (np.floor(dt_ * 8) % 2 == 0).astype(float)
        lvl = np.where(dt_ >= 0, 0.4 + 0.6 * strobe, lvl)
        base_dark2 = np.array(srgb('#4a0b20'))
    c = base_dark[None] * (1 - lvl[:, None]) + flash[None] * lvl[:, None]
    for ch in range(3): set_curve(panels[k], 'diffuse_color', ch, c[:, ch])
    set_curve(panels[k], 'diffuse_color', 3, np.ones(NF))

# Vegas sign at the top
box('signbg', -W, W, 0.4, 0.6, TOP + 1.5, TOP + 11.5, '#2a0a3d')
text('LAS VEGAS', 3.0, '#ffe600', (0, -0.3, TOP + 8.6), extrude=0.12)
text('JACKPOT PLINKO', 1.7, '#ff2bd6', (0, -0.3, TOP + 4.4), extrude=0.1)
text('$1,000,000', 1.6, '#39ff88', (0, -0.3, B['FLOOR'] - 2.6), extrude=0.1)
# marquee bulbs blinking on the beat
bulbA = bpy.data.materials.new('bulbA'); bulbB = bpy.data.materials.new('bulbB')
beat = T['bar'] / 2
ph_ = (np.floor((ts - T['T0']) / beat) % 2 == 0)
on, off = np.array(srgb('#fff2a8')), np.array(srgb('#7a5a10'))
for mtl, inv in ((bulbA, False), (bulbB, True)):
    st = ph_ ^ inv
    c = np.where(st[:, None], on[None], off[None])
    for ch in range(3): set_curve(mtl, 'diffuse_color', ch, c[:, ch], interp=0)
import bmesh
for mtl, par in ((bulbA, 0), (bulbB, 1)):
    bm = bmesh.new(); k = 0
    zs = np.arange(BOT - 2, TOP + 13, 1.2)
    for z in zs:
        for sx in (-1, 1):
            if (k % 2) == par:
                bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.28,
                                          matrix=Matrix.Translation((sx * (W + 1.6), -0.2, z)))
            k += 1
    for x in np.arange(-W - 1.6, W + 1.7, 1.2):
        if (k % 2) == par:
            bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.28, matrix=Matrix.Translation((x, -0.2, TOP + 12.4)))
        k += 1
    me = bpy.data.meshes.new(f'bulbs{par}'); bm.to_mesh(me); bm.free(); me.materials.append(mtl)
    link(bpy.data.objects.new(f'bulbs{par}', me))

# ---------------- chips ----------------
CHIP = ['#e8203a', '#ff8a1c', '#ffd21a', '#21c45a', '#1e6bff', '#9b3dff', '#ff4fb8', '#f4f4f4']
STRIPE = ['#ffffff'] * 7 + ['#222222']
P = RS['P']; Vv = RS['V']; p0 = RS['p0']
simt = np.arange(len(P)) / 60.0
R = 0.55
for i in range(8):
    chip = cyl_y(f'chip{i}', R, 0.32, CHIP[i], 48)
    inner = cyl_y(f'chipin{i}', R * 0.62, 0.34, STRIPE[i] if i == 7 else '#ffffff', 40); inner.parent = chip
    inner2 = cyl_y(f'chipin2{i}', R * 0.52, 0.36, CHIP[i], 40); inner2.parent = chip
    for a in range(6):
        ang = a * math.pi / 3
        st = box(f'stripe{i}_{a}', -0.09, 0.09, -0.175, 0.175, R * 0.72, R * 0.98, STRIPE[i])
        st.parent = chip; st.rotation_euler = (0, ang, 0)
    x = np.where(ts < gate, p0[i, 0], np.interp(tsim, simt, P[:, i, 0]))
    z = np.where(ts < gate, p0[i, 1], np.interp(tsim, simt, P[:, i, 1]))
    vx = np.interp(tsim, simt, Vv[:, i, 0])
    spin = np.cumsum(np.where(ts < gate, 0, -vx * (1 / FPS) / s / R))
    set_curve(chip, 'location', 0, x); set_curve(chip, 'location', 2, z)
    set_curve(chip, 'location', 1, np.full(NF, -0.05))
    set_curve(chip, 'rotation_euler', 1, -spin)

# ---------------- jackpot coins ----------------
TL = T['T_LAND']; jx = -W + (B['JACKPOT'] + 0.5) * SW
coin_me = None
for k in range(260):
    c = cyl_y(f'coin{k}', 0.32, 0.08, '#ffcf3a', 20)
    vx = random.uniform(-6, 6); vz = random.uniform(9, 19); vy = random.uniform(-2.5, -0.3)
    t = ts - TL - random.uniform(0, 4.5)
    tt_ = np.clip(t, 0, None)
    x = jx + vx * tt_; y = -0.6 + vy * tt_; z = np.maximum(B['SLOT_TOP'] + vz * tt_ - 0.5 * 20 * tt_ ** 2, B['FLOOR'] - 30)
    vis = t > 0
    set_curve(c, 'location', 0, np.where(vis, x, 0)); set_curve(c, 'location', 1, np.where(vis, y, 5))
    set_curve(c, 'location', 2, np.where(vis, z, -400))
    sp = np.random.randn(3) * 10
    for a in range(3): set_curve(c, 'rotation_euler', a, sp[a] * tt_)

# ---------------- camera ----------------
cd = bpy.data.cameras.new('cam'); cd.lens = 35; cd.sensor_fit = 'VERTICAL'; cd.sensor_height = 36; cd.clip_end = 800
cam = link(bpy.data.objects.new('cam', cd)); scene.camera = cam; cam.rotation_mode = 'XYZ'
VH = 41.0; dist = VH / 2 / math.tan(math.atan(18 / 35))
zs = np.zeros(NF)
lt_v = np.array([gate + l * s for l in T['lt']])
for n in range(NF):
    zz = []
    for i in range(8):
        if ts[n] < lt_v[i] + 0.4:
            zz.append(np.interp(max(ts[n] - gate, 0) / s, simt, P[:, i, 1]))
    zs[n] = np.mean(zz) if zz else B['FLOOR']
zt = np.clip(zs + 6.0, B['FLOOR'] + VH / 2 - 2.8, TOP + 11.5 - VH / 2 + 2.5)
zt[ts < gate + 1.0] = TOP + 11.5 - VH / 2 + 2.5
def gs(a, sg):
    r = int(3 * sg); k = np.exp(-0.5 * (np.arange(-r, r + 1) / sg) ** 2); k /= k.sum()
    return np.convolve(np.pad(a, r, mode='edge'), k, 'valid')
zt = gs(zt, 22)
# celebration: push in on the jackpot with a shake
b = np.clip((ts - TL) / 1.2, 0, 1); b = b * b * (3 - 2 * b)
shake = np.where(ts > TL, np.exp(-(ts - TL) * 4) * 0.5, 0)
cz = zt * (1 - b) + (B['FLOOR'] + 8.0) * b + shake * np.sin(ts * 57)
cx = 0 * b + jx * 0.4 * b + shake * np.cos(ts * 43)
cy = -dist * (1 - 0.3 * b)
set_curve(cam, 'location', 0, cx); set_curve(cam, 'location', 1, cy); set_curve(cam, 'location', 2, cz)
set_curve(cam, 'rotation_euler', 0, np.full(NF, math.pi / 2))

scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
scene.display.render_aa = 'FXAA'
sh = scene.display.shading
sh.light = 'FLAT'; sh.color_type = 'MATERIAL'
sh.show_shadows = True; sh.shadow_intensity = 0.5
scene.display.light_direction = (-0.3, -0.5, 0.8)
sh.show_cavity = True; sh.cavity_type = 'BOTH'
scene.view_settings.view_transform = 'Standard'
world = bpy.data.worlds.new('w'); world.color = srgb('#05020b'); scene.world = world
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/vegas/vegas.blend')
print('BUILT', NF)
