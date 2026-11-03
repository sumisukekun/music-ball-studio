import bpy, math, json, random, colorsys
import numpy as np
from mathutils import Vector, Matrix

Mj = json.load(open('/home/claude/nordic/machine.json'))
S = json.load(open('/home/claude/nordic/score.json'))
FPS = 30; END = Mj['END']; NF = int(END * FPS) + 1
ts = np.arange(NF) / FPS
G, R, DH, DD, DW, P = Mj['G'], Mj['R'], Mj['DH'], Mj['DD'], Mj['DW'], Mj['P']
random.seed(11); np.random.seed(11)
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
        m = bpy.data.materials.new(h); m.diffuse_color = (*hexl(h), 1); m.roughness = 0.45; MATS[h] = m
    return MATS[h]
def link(o): scene.collection.objects.link(o); return o
import bmesh
def box_me(name, x0, x1, y0, y1, z0, z1, bev=0.03):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts:
        v.co.x = (v.co.x + .5) * (x1 - x0) + x0; v.co.y = (v.co.y + .5) * (y1 - y0) + y0; v.co.z = (v.co.z + .5) * (z1 - z0) + z0
    if bev: bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bev, segments=2, affect='EDGES')
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); return me
def box(name, x0, x1, y0, y1, z0, z1, col, bev=0.03):
    me = box_me(name, x0, x1, y0, y1, z0, z1, bev); me.materials.append(M(col))
    return link(bpy.data.objects.new(name, me))
def gs(a, sg):
    r = int(3 * sg); k = np.exp(-0.5 * (np.arange(-r, r + 1) / sg) ** 2); k /= k.sum()
    if a.ndim == 1: return np.convolve(np.pad(a, r, mode='edge'), k, 'valid')
    return np.stack([gs(a[:, j], sg) for j in range(a.shape[1])], 1)
def smooth01(u): u = np.clip(u, 0, 1); return u * u * (3 - 2 * u)

WOOD = '#e2b57c'; WOOD2 = '#b9824a'; WALL = '#f4efe6'
NOR = ['#c8102e', '#ffffff', '#00205b']
KEYC = ['#d1495b', '#edae49', '#66a182', '#00798c', '#30638e', '#8e6c8a', '#e07a5f', '#81b29a']

secs = Mj['sections']
# ---------------- ball paths ----------------
class Path:
    def __init__(self): self.seg = []          # (t0, t1, p0, p1, mode) mode: 'fly' (gravity) | 'hold'
    def fly(self, t0, t1, p0, p1): self.seg.append((t0, t1, np.array(p0, float), np.array(p1, float), 'fly'))
    def hold(self, t0, t1, p): self.seg.append((t0, t1, np.array(p, float), np.array(p, float), 'hold'))
    def vel_out(self, k):
        t0, t1, p0, p1, m = self.seg[k]
        T = t1 - t0; return np.array([(p1[0] - p0[0]) / T, ((p1[1] - p0[1]) + 0.5 * G * T * T) / T])
    def vel_in(self, k):
        t0, t1, p0, p1, m = self.seg[k]
        v = self.vel_out(k); return np.array([v[0], v[1] - G * (t1 - t0)])
    def eval(self, t):
        for t0, t1, p0, p1, m in self.seg:
            if t0 <= t <= t1:
                if m == 'hold': return p0
                T = t1 - t0; tau = t - t0
                vz = ((p1[1] - p0[1]) + 0.5 * G * T * T) / T
                return np.array([p0[0] + (p1[0] - p0[0]) * tau / T, p0[1] + vz * tau - 0.5 * G * tau * tau])
        if t < self.seg[0][0]: return self.seg[0][2]
        return self.seg[-1][3]

def domino_angles(piv, times, Hs, ds, end_mode):
    n = len(piv); th = [None] * n
    for i in range(n - 1, -1, -1):
        t0 = times[i]
        if i == n - 1:
            if end_mode[0] == 'ball':
                tp, ang = end_mode[1], end_mode[2]
                u = np.clip((ts - t0) / (tp - t0), 0, 1)
                a = ang * u ** 1.5
                u2 = np.clip((ts - tp) / 0.35, 0, 1)
                th[i] = np.where(ts < tp, a, ang + (math.radians(84) - ang) * u2 * u2)
            else:   # bell strike
                tp, ang = end_mode[1], end_mode[2]
                u = np.clip((ts - t0) / (tp - t0), 0, 1)
                rb = np.where(ts > tp, np.sin(np.clip((ts - tp) / 0.4, 0, 1) * math.pi) * 0.08, 0)
                th[i] = np.where(ts < tp, ang * u ** 1.6, ang - rb)
            continue
        p = piv[i + 1] - piv[i]; H = Hs[i]; dn = ds[i + 1]
        thc = math.asin(min((p - dn) / H, 0.99))
        tc = times[i + 1]
        u = np.clip((ts - t0) / max(tc - t0, 1e-3), 0, 1)
        ph1 = thc * u ** 1.5
        al = th[i + 1]
        ph2 = al + np.arcsin(np.clip((p * np.cos(al) - dn) / H, -1, 1))
        th[i] = np.maximum.accumulate(np.where(ts < tc, ph1, np.maximum(ph2, thc)))
    return th

paths = []                 # one Path per ball
key_events = []            # (t, x, z, normal, colour, section)
cur = None
for si, s in enumerate(secs):
    if s['kind'] == 'B':
        keys = s['keys']
        pth = Path()
        if si == 0:
            k0 = keys[0]
            start = (k0['x'] - 1.6, k0['z'] + 3.2)
            pth.hold(0, k0['t'] - 0.55, start)
            pth.fly(k0['t'] - 0.55, k0['t'], start, (k0['x'], k0['z']))
            s['start'] = start; s['gate_t'] = k0['t'] - 0.55
        else:
            prev = secs[si - 1]
            rest = (prev['pivots'][-1] + 0.75 * DH + R, prev['z'] + R)
            tlast = prev['times'][-1]
            tpush = tlast + min(0.5 * (keys[0]['t'] - tlast), 0.2)
            prev['push'] = tpush; prev['rest'] = rest
            pth.hold(0, tpush, rest)
            pth.fly(tpush, keys[0]['t'], rest, (keys[0]['x'], keys[0]['z']))
        for k in range(len(keys) - 1):
            pth.fly(keys[k]['t'], keys[k + 1]['t'], (keys[k]['x'], keys[k]['z']), (keys[k + 1]['x'], keys[k + 1]['z']))
        nxt = secs[si + 1]
        contact = (nxt['pivots'][0] - DD - R, nxt['z'] + 0.72 * DH)
        pth.fly(keys[-1]['t'], nxt['times'][0], (keys[-1]['x'], keys[-1]['z']), contact)
        # after knocking the first domino the ball drops back onto the shelf
        land = (contact[0] - 0.7, nxt['z'] + R)
        pth.fly(nxt['times'][0], nxt['times'][0] + 0.32, contact, land)
        pth.hold(nxt['times'][0] + 0.32, END + 1, land)
        # key normals from in/out velocity at each bounce
        first_fly = 1
        for k in range(len(keys)):
            vin = pth.vel_in(1 + k); vout = pth.vel_out(2 + k)
            n_ = vout - vin; n_ /= np.linalg.norm(n_)
            keys[k]['n'] = n_.tolist()
        paths.append(pth)

# ---------------- build the scene ----------------
XMAX = secs[-1]['pivots'][-1] + 20
wall = box('wall', -30, XMAX + 30, 1.3, 1.6, -100, 50, WALL, 0)
# decals: painted snowflakes on the wall
for k in range(90):
    cx, cz = random.uniform(-20, XMAX), random.uniform(-90, 40); r = random.uniform(0.6, 1.4)
    col = random.choice(['#d7e3f0', '#e8d9d9'])
    for a in range(3):
        o = box(f'fl{k}{a}', -r, r, 1.22, 1.28, -0.06, 0.06, col, 0); o.location = (cx, 0, cz); o.rotation_euler = (0, math.radians(60 * a), 0)
dom_me = box_me('dom', -DD, 0, -DW / 2, DW / 2, 0, DH, 0.04)
dom_me.materials.append(None)
ball_objs = []
key_me = box_me('key', -KEY_L / 2 if (KEY_L := Mj['KEY_L']) else 0, KEY_L / 2, -0.8, 0.8, -0.2, 0, 0.04); key_me.materials.append(None)
kc = 0
for si, s in enumerate(secs):
    if s['kind'] == 'B':
        for k, key in enumerate(s['keys']):
            n_ = np.array(key['n'])
            ob = link(bpy.data.objects.new(f'k{si}_{k}', key_me))
            ob.location = (key['x'] - n_[0] * R, 0, key['z'] - n_[1] * R)
            ob.rotation_euler = (0, -(math.atan2(n_[1], n_[0]) - math.pi / 2), 0)
            m = bpy.data.materials.new(f'km{si}_{k}'); ob.material_slots[0].link = 'OBJECT'; ob.material_slots[0].material = m
            base = hexl(KEYC[kc % len(KEYC)]); kc += 1
            dt_ = ts - key['t']; fl = np.where(dt_ >= 0, np.exp(-dt_ * 9), 0)
            c = base[None] * (1 - fl[:, None]) + np.ones(3)[None] * fl[:, None]
            for ch in range(3): set_curve(m, 'diffuse_color', ch, c[:, ch])
            dip = np.where((dt_ > 0) & (dt_ < 0.14), np.sin(np.clip(dt_ / 0.14, 0, 1) * math.pi) * 0.12, 0)
            set_curve(ob, 'location', 0, key['x'] - n_[0] * (R + dip)); set_curve(ob, 'location', 2, key['z'] - n_[1] * (R + dip))
            # little post into the wall
            post = box(f'kp{si}_{k}', -0.07, 0.07, 0.6, 1.3, -0.07, 0.07, '#9a9a9a', 0)
            post.location = (key['x'] - n_[0] * R, 0, key['z'] - n_[1] * R - 0.1)
        if si == 0:
            sx, sz = s['start']
            box('startshelf', sx - 1.0, sx + 0.6, -0.8, 0.8, sz - R - 0.25, sz - R, WOOD)
            gate = box('gate', -0.06, 0.06, -0.8, 0.8, 0, 1.0, NOR[0], 0.02)
            gate.location = (sx + 0.55, 0, sz - R)
            set_curve(gate, 'rotation_euler', 1, -math.radians(95) * smooth01((ts - s['gate_t'] + 0.12) / 0.12))
            # flag on the start shelf
            box('pole0', sx - 0.85, sx - 0.75, -0.1, 0.1, sz - R, sz + 2.2, '#8a6a4a', 0)
            for i, (a, b, c_) in enumerate([(0, 1, NOR[0])]):
                pass
    else:
        z0 = s['z']; piv = s['pivots']; tms = s['times']
        last_sec = si == len(secs) - 1
        n = len(piv) - (1 if last_sec else 0)
        piv_d = piv[:n]; tms_d = tms[:n]
        Hs = [DH] * n; ds = [DD] * n
        if last_sec:
            Hs[-1] = 3.4; ds[-1] = 0.42
            bell_x = piv_d[-1] + 3.0; s['bell_x'] = bell_x
            ang = math.asin(1.6 / 3.4)
            th = domino_angles(piv_d, tms_d, Hs, ds, ('bell', tms[-1], ang))
        else:
            ang = math.asin(np.clip((0.75 * DH - 0.6 * R) / DH, 0, 0.99))
            th = domino_angles(piv_d, tms_d, Hs, ds, ('ball', s['push'], ang))
        box(f'shelf{si}', s['x0'], s['x1'] if not last_sec else piv_d[-1] + 6, -0.9, 0.9, z0 - 0.45, z0, WOOD)
        for bx in np.arange(s['x0'] + 2, (s['x1'] if not last_sec else piv_d[-1] + 6) - 1, 9):
            box(f'brk{si}_{bx:.0f}', bx - 0.15, bx + 0.15, 0.9, 1.3, z0 - 1.8, z0 - 0.45, WOOD2, 0)
        for i in range(n):
            if last_sec and i == n - 1:
                me = box_me('bigdom', -0.42, 0, -0.8, 0.8, 0, 3.4, 0.06); me.materials.append(M('#d4a017'))
                ob = link(bpy.data.objects.new('bigdom', me))
            else:
                ob = link(bpy.data.objects.new(f'd{si}_{i}', dom_me))
                ob.material_slots[0].link = 'OBJECT'; ob.material_slots[0].material = M(NOR[i % 3])
            ob.location = (piv_d[i], 0, z0)
            set_curve(ob, 'rotation_euler', 1, th[i])
        # Nordic decor on the shelf: a red cottage and pine trees
        cx = s['x0'] + 0.2
        house = box(f'house{si}', cx - 0.9, cx + 0.9, -0.3, 0.9, z0, z0 + 1.3, '#a4161a')
        roof = bpy.data.meshes.new(f'roof{si}'); bm = bmesh.new()
        v = [bm.verts.new(p) for p in [(cx - 1.1, -0.4, z0 + 1.3), (cx + 1.1, -0.4, z0 + 1.3), (cx, -0.4, z0 + 2.3),
                                       (cx - 1.1, 1.0, z0 + 1.3), (cx + 1.1, 1.0, z0 + 1.3), (cx, 1.0, z0 + 2.3)]]
        bm.faces.new((v[0], v[1], v[2])); bm.faces.new((v[3], v[5], v[4])); bm.faces.new((v[0], v[2], v[5], v[3])); bm.faces.new((v[1], v[4], v[5], v[2]))
        bm.to_mesh(roof); bm.free(); roof.materials.append(M('#2b2d42')); link(bpy.data.objects.new(f'roofo{si}', roof))
        box(f'door{si}', cx - 0.2, cx + 0.2, -0.33, -0.3, z0, z0 + 0.7, '#ffffff', 0)
# pine trees scattered along the bottom edge of each section
def pine(x, z, h):
    for j, (r, zz) in enumerate([(0.9, 0.0), (0.7, 0.45), (0.5, 0.85)]):
        bpy.ops.mesh.primitive_cone_add(radius1=r * h, radius2=0, depth=0.9 * h, vertices=12, location=(x, 0.6, z + zz * h + 0.45 * h))
        c = bpy.context.active_object; c.data.materials.append(M('#2d6a4f'))
        bpy.ops.mesh.primitive_cone_add(radius1=r * h * 0.45, radius2=0, depth=0.35 * h, vertices=12, location=(x, 0.55, z + zz * h + 0.72 * h))
        sn = bpy.context.active_object; sn.data.materials.append(M('#ffffff'))
for s in secs:
    if s['kind'] == 'B':
        for k in range(0, len(s['keys']), 9):
            kk = s['keys'][k]; pine(kk['x'] + random.uniform(-1, 1), kk['z'] - 3.6, random.uniform(1.0, 1.4))

# balls
for b, pth in enumerate(paths):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R, segments=40, ring_count=20)
    ob = bpy.context.active_object; ob.name = f'ball{b}'
    me = ob.data; me.materials.append(M('#c8102e')); me.materials.append(M('#ffffff'))
    for p in me.polygons:
        p.material_index = int(((math.atan2(p.center.z, p.center.x) + math.pi) / (2 * math.pi)) * 6) % 2; p.use_smooth = True
    PB = np.array([pth.eval(t) for t in ts])
    set_curve(ob, 'location', 0, PB[:, 0]); set_curve(ob, 'location', 2, PB[:, 1])
    set_curve(ob, 'rotation_euler', 1, np.cumsum(np.diff(PB[:, 0], prepend=PB[0, 0])) / R)
    ball_objs.append(PB)

# ---------------- bell finale ----------------
last = secs[-1]; z0 = last['z']; bx = last['bell_x']; TB = last['times'][-1]
box('bellpostL', bx - 2.2, bx - 1.95, -0.2, 0.2, z0, z0 + 6.0, WOOD2)
box('bellpostR', bx + 1.95, bx + 2.2, -0.2, 0.2, z0, z0 + 6.0, WOOD2)
box('bellbeam', bx - 2.4, bx + 2.4, -0.25, 0.25, z0 + 6.0, z0 + 6.4, WOOD2)
bell = bpy.data.objects.new('bell', None); link(bell); bell.location = (bx, 0, z0 + 6.0)
bpy.ops.mesh.primitive_cone_add(radius1=1.45, radius2=0.7, depth=2.6, vertices=48, location=(0, 0, -2.0))
bc = bpy.context.active_object; bc.data.materials.append(M('#d4a017')); bc.parent = bell
bpy.ops.mesh.primitive_torus_add(major_radius=1.4, minor_radius=0.14, location=(0, 0, -3.25))
br = bpy.context.active_object; br.data.materials.append(M('#b8860b')); br.parent = bell
tb = ts - TB
set_curve(bell, 'rotation_euler', 1, np.where(tb > 0, -0.32 * np.exp(-tb * 1.2) * np.sin(tb * 7), 0))
# flag pops up
flag = bpy.data.objects.new('flag', None); link(flag)
pole = box('pole', -0.08, 0.08, -0.08, 0.08, 0, 5.2, '#d9d9d9', 0); pole.parent = flag
fx0 = 0.08
for (x0, x1, z0_, z1, col) in [(0, 3.2, 2.3, 4.7, '#ba0c2f'), (0.85, 1.35, 2.3, 4.7, '#ffffff'), (0, 3.2, 3.25, 3.75, '#ffffff'),
                               (0.97, 1.23, 2.3, 4.7, '#00205b'), (0, 3.2, 3.37, 3.63, '#00205b')]:
    f = box(f'flag{col}{x0}', fx0 + x0, fx0 + x1, -0.06 - 0.01 * (col != '#ba0c2f') - 0.01 * (col == '#00205b'), 0.0, z0_ + 0.5, z1 + 0.5, col, 0)
    f.parent = flag
up = np.where(tb > 0.15, 1 - np.exp(-(tb - 0.15) * 6) * np.cos((tb - 0.15) * 16), 0)
set_curve(flag, 'location', 0, np.full(NF, bx + 2.7)); set_curve(flag, 'location', 1, np.full(NF, 0.3))
set_curve(flag, 'location', 2, z0 - 5.4 + 5.4 * np.clip(up, 0, 1.3))
# snow confetti
for k in range(160):
    c = box(f'snow{k}', -0.12, 0.12, -0.02, 0.02, -0.12, 0.12, random.choice(['#ffffff', '#ffffff', '#c8102e', '#00205b']), 0)
    vx = random.uniform(-6, 6); vz = random.uniform(8, 16); dl = random.uniform(0, 0.4)
    t = np.clip(ts - TB - dl, 0, None)
    x = bx + vx * t * np.exp(-t * 0.4); z = z0 + 3 + vz * t - 6 * t * t
    z = np.maximum(z, z0 + 3 + vz * 1.0 - 6 - 1.2 * (t - 1.0)) if False else z
    zf = np.where(t < vz / 12, z, (z0 + 3 + vz * vz / 24) - 1.6 * (t - vz / 12))
    vis = ts > TB + dl
    set_curve(c, 'location', 0, np.where(vis, x, bx)); set_curve(c, 'location', 1, np.full(NF, -0.8))
    set_curve(c, 'location', 2, np.where(vis, zf, z0 - 30))
    sp = np.random.randn(3) * 8
    for a in range(3): set_curve(c, 'rotation_euler', a, sp[a] * t)

# ---------------- camera ----------------
focus = np.zeros((NF, 2))
for f, t in enumerate(ts):
    for s in secs:
        if s['kind'] == 'D' and s['times'][0] <= t <= s['times'][-1] + 0.6:
            xx = np.interp(t, s['times'], s['pivots'])
            focus[f] = (xx + 1.0, s['z'] + 1.6); break
    else:
        # active ball
        best = None
        for b, s in enumerate([q for q in secs if q['kind'] == 'B']):
            t0 = (s['gate_t'] - 1.5) if 'gate_t' in s else secs[secs.index(s) - 1]['times'][-1]
            nxt = secs[secs.index(s) + 1]
            if t0 - 0.01 <= t <= nxt['times'][0] + 0.01:
                best = ball_objs[b][f]
        focus[f] = best if best is not None else focus[f - 1]
    if t > TB - 0.6:
        focus[f] = (last['bell_x'] + 1.2, last['z'] + 3.4)
focus = gs(focus, 7)
cd = bpy.data.cameras.new('cam'); cd.lens = 40; cd.sensor_fit = 'VERTICAL'; cd.sensor_height = 36; cd.clip_end = 500
cam = link(bpy.data.objects.new('cam', cd)); scene.camera = cam; cam.rotation_mode = 'XYZ'
VH = 13.5 * (1 + 0.35 * smooth01((ts - TB - 0.5) / 2.5))
dist = VH / 2 / (18 / 40)
set_curve(cam, 'location', 0, focus[:, 0]); set_curve(cam, 'location', 1, -dist); set_curve(cam, 'location', 2, focus[:, 1] + 0.8)
set_curve(cam, 'rotation_euler', 0, np.full(NF, math.pi / 2 - math.atan(0.8 / 25)))

scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
scene.display.render_aa = 'FXAA'
sh = scene.display.shading
sh.light = 'STUDIO'; sh.studio_light = 'outdoor.sl'; sh.color_type = 'MATERIAL'
sh.show_shadows = True; sh.shadow_intensity = 0.3
sh.show_cavity = True; sh.cavity_type = 'BOTH'; sh.show_specular_highlight = True
scene.display.light_direction = (-0.35, -0.55, 0.75)
scene.view_settings.view_transform = 'Standard'; scene.view_settings.exposure = 0.6
world = bpy.data.worlds.new('w'); world.color = tuple(hexl(WALL)); scene.world = world
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/nordic/pyta_nordic.blend')
json.dump(dict(bell_t=TB, push=[s.get('push') for s in secs]), open('/home/claude/nordic/machine_extra.json', 'w'))
print('BUILT', NF)
