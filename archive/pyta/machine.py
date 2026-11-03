import bpy, math, json, random, sys
import numpy as np
from mathutils import Vector, Matrix, Euler

# ================= timeline (120 BPM: beat = 0.5 s) =================
FPS = 30
END_T = 19.0
NF = int(END_T * FPS) + 1
ts = np.arange(NF) / FPS
random.seed(3); np.random.seed(3)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 0, NF - 1

# ================= helpers =================
def ensure_action(idb):
    if idb.animation_data is None:
        idb.animation_data_create()
    if idb.animation_data.action is None:
        idb.animation_data.action = bpy.data.actions.new(idb.name + "_act")

def set_curve(idb, path, index, vals, frames=None):
    vals = np.asarray(vals, np.float64)
    if frames is None:
        keep = np.zeros(len(vals), bool); keep[0] = keep[-1] = True
        d = np.abs(np.diff(vals)) > 1e-6
        keep[1:] |= d; keep[:-1] |= d
        frames = np.nonzero(keep)[0]; vals = vals[frames]
    ensure_action(idb)
    fc = idb.animation_data.action.fcurve_ensure_for_datablock(idb, path, index=index)
    n = len(frames)
    fc.keyframe_points.add(n)
    co = np.empty(2 * n, np.float32); co[0::2] = frames; co[1::2] = vals
    fc.keyframe_points.foreach_set('co', co)
    fc.keyframe_points.foreach_set('interpolation', np.full(n, 1, np.int32))
    fc.update()

def anim_loc(ob, P):
    for a in range(3): set_curve(ob, 'location', a, P[:, a])
def anim_rot(ob, R):
    for a in range(3): set_curve(ob, 'rotation_euler', a, R[:, a])

def srgb(h):
    h = h.lstrip('#'); c = np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])
    return tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4))
MATS = {}
def M(hexcol):
    if hexcol not in MATS:
        m = bpy.data.materials.new(hexcol); m.diffuse_color = (*srgb(hexcol), 1); m.roughness = 0.4
        MATS[hexcol] = m
    return MATS[hexcol]

def link(ob):
    scene.collection.objects.link(ob); return ob

def box(name, x0, x1, y0, y1, z0, z1, col, bevel=0.03):
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts:
        v.co.x = (v.co.x + .5) * (x1 - x0) + x0
        v.co.y = (v.co.y + .5) * (y1 - y0) + y0
        v.co.z = (v.co.z + .5) * (z1 - z0) + z0
    if bevel: bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1, affect='EDGES')
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(M(col))
    return link(bpy.data.objects.new(name, me))

def board(name, p_hi, p_lo, th, col, depth=1.8):
    """board whose TOP surface runs between two (x,z) points"""
    (xa, za), (xb, zb) = p_hi, p_lo
    L = math.hypot(xb - xa, zb - za)
    ob = box(name, -L / 2, L / 2, -depth / 2, depth / 2, -th, 0, col)
    ob.location = ((xa + xb) / 2, 0, (za + zb) / 2)
    ob.rotation_euler = (0, -math.atan2(zb - za, xb - xa), 0)
    return ob

def cyl(name, r, h, col, verts=32, axis='Y'):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, vertices=verts)
    ob = bpy.context.active_object; ob.name = name
    if axis == 'Y':
        ob.data.transform(Matrix.Rotation(math.pi / 2, 4, 'X'))
    ob.data.materials.append(M(col))
    return ob

def striped_ball(name, r, c1, c2):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=48, ring_count=24)
    ob = bpy.context.active_object; ob.name = name
    me = ob.data; me.materials.append(M(c1)); me.materials.append(M(c2))
    for p in me.polygons:
        c = p.center
        ang = math.atan2(c.z, c.x)
        p.material_index = int(((ang + math.pi) / (2 * math.pi)) * 6) % 2
        p.use_smooth = True
    return ob

def smooth01(u):
    u = np.clip(u, 0, 1); return u * u * (3 - 2 * u)

# ================= path builder for balls =================
class Path:
    def __init__(self, r):
        self.r = r; self.segs = []
    def hold(self, t0, t1, p): self.segs.append(('hold', t0, t1, np.array(p), None, None))
    def roll(self, t0, t1, p0, p1, a=0.35):
        self.segs.append(('roll', t0, t1, np.array(p0), np.array(p1), a))
    def fly(self, t0, t1, p0, p1, g):
        self.segs.append(('fly', t0, t1, np.array(p0), np.array(p1), g))
    def eval(self, t):
        for kind, t0, t1, p0, p1, a in self.segs:
            if t0 <= t <= t1 or (kind == 'hold' and t < t0 and self.segs[0][1] == t0):
                u = (t - t0) / max(t1 - t0, 1e-9)
                if kind == 'hold': return p0
                if kind == 'roll':
                    s = a * u + (1 - a) * u * u
                    return p0 + (p1 - p0) * s
                T = t1 - t0; tau = t - t0
                vz = ((p1[1] - p0[1]) + 0.5 * a * T * T) / T
                return np.array([p0[0] + (p1[0] - p0[0]) * u, p0[1] + vz * tau - 0.5 * a * tau * tau])
        if t < self.segs[0][1]: return self.segs[0][3]
        last = self.segs[-1]
        return last[4] if last[4] is not None else last[3]
    def arrays(self):
        P = np.array([self.eval(t) for t in ts])
        dx = np.diff(P[:, 0], prepend=P[0, 0])
        spin = np.cumsum(dx) / self.r
        return P, spin

# ================= static world =================
WALL = '#fdf3e1'; WOOD = '#e2a464'; WOOD2 = '#c98a4b'; DARK = '#5a4636'
wall = box('wall', -30, 50, 1.4, 1.6, -5, 60, WALL, 0)
table = box('table', -30, 50, -6, 1.4, 2.4, 4.0, '#b97a44', 0.05)
floorp = box('floor', -60, 80, -60, 1.4, -0.1, 0.0, '#eadfcf', 0)
# pegboard dots on the wall (DIY workshop feel)
import bmesh
bm = bmesh.new()
for ix in range(-6, 32):
    for iz in range(2, 46):
        x, z = ix * 1.0 - 0.5, iz * 1.0 - 0.5
        bmesh.ops.create_circle(bm, cap_ends=True, radius=0.07, segments=8,
                                matrix=Matrix.Translation((x, 1.39, z)) @ Matrix.Rotation(math.pi / 2, 4, 'X'))
me = bpy.data.meshes.new('dots'); bm.to_mesh(me); bm.free(); me.materials.append(M('#e3d4bb'))
link(bpy.data.objects.new('dots', me))

R = 0.45
TH = 0.3
# zigzag ramps (top surface lines)
ramps = [((4.4, 33.0), (7.0, 32.7)),     # R1 (short, with gate)  -> right
         ((7.0, 30.0), (1.0, 29.4)),     # R2 -> left
         ((1.0, 27.0), (7.0, 26.4)),     # R3 -> right
         ((7.0, 24.0), (1.0, 23.4))]     # R4 -> left
cols_r = ['#ff6b6b', '#ffa94d', '#4dabf7', '#51cf66']
for k, (a, b) in enumerate(ramps):
    board(f'ramp{k}', a, b, TH, WOOD)
    # side rails in colour
    xa, za = a; xb, zb = b
    rl = board(f'rail{k}', (xa, za + 0.18), (xb, zb + 0.18), 0.18, cols_r[k], depth=0.15)
    rl.location.y = -0.95
    # end stop wall at the low end
    xw = max(xa, xb) if xb > xa else min(xa, xb)
    zl = min(za, zb)
    if xb > xa: box(f'stop{k}', xw, xw + 0.25, -0.9, 0.9, zl - TH, zl + 1.3, WOOD2)
    else:       box(f'stop{k}', xw - 0.25, xw, -0.9, 0.9, zl - TH, zl + 1.3, WOOD2)
    # wall bracket
    box(f'brk{k}', (xa + xb) / 2 - 0.15, (xa + xb) / 2 + 0.15, 0.9, 1.4, min(za, zb) - 1.2, min(za, zb) - TH, DARK)
def surf(k, x):
    (xa, za), (xb, zb) = ramps[k]
    return za + (x - xa) * (zb - za) / (xb - xa)

# floor A: domino shelf
ZA = 20.0
box('shelfA', -0.5, 18.8, -0.9, 0.9, ZA - 0.4, ZA, WOOD)
for x in (2, 10, 17): box(f'brkA{x}', x - 0.15, x + 0.15, 0.9, 1.4, ZA - 1.6, ZA - 0.4, DARK)

# START gate on R1
gate = box('gate', -0.08, 0.08, -0.8, 0.8, -1.25, 0, '#ff3b5c', 0.02)
gate_pivot = (5.45, surf(0, 5.45) + 1.3)
gate.location = (gate_pivot[0], 0, gate_pivot[1])
box('gatepost', 5.3, 5.6, -1.0, -0.85, surf(0, 5.45), gate_pivot[1] + 0.25, DARK)
gth = np.radians(80) * smooth01((ts - 1.5) / 0.15)
anim_rot(gate, np.stack([np.zeros(NF), -gth, np.zeros(NF)], 1))

# ================= ball 1 =================
b1 = Path(R)
p_start = (4.95, surf(0, 4.95) + R)
b1.hold(0, 1.5, p_start)
x_end1 = 7.0 - R
b1.roll(1.5, 2.1, p_start, (x_end1, surf(0, x_end1) + R), 0.2)
b1.fly(2.1, 2.5, (x_end1, surf(0, x_end1) + R), (6.35, surf(1, 6.35) + R), 30)
b1.roll(2.5, 3.1, (6.35, surf(1, 6.35) + R), (1.0 + R, surf(1, 1.0 + R) + R), 0.45)
b1.fly(3.1, 3.5, (1.0 + R, surf(1, 1.45) + R), (1.65, surf(2, 1.65) + R), 30)
b1.roll(3.5, 4.1, (1.65, surf(2, 1.65) + R), (7.0 - R, surf(2, 6.55) + R), 0.45)
b1.fly(4.1, 4.5, (6.55, surf(2, 6.55) + R), (6.35, surf(3, 6.35) + R), 30)
b1.roll(4.5, 5.1, (6.35, surf(3, 6.35) + R), (1.45, surf(3, 1.45) + R), 0.45)
b1.fly(5.1, 5.5, (1.45, surf(3, 1.45) + R), (1.3, ZA + R), 30)
DOM0 = 5.0; DH, DD, DW = 1.6, 0.25, 0.8
b1.roll(5.5, 6.0, (1.3, ZA + R), (DOM0 - DD - R, ZA + R), 0.9)
b1.roll(6.0, 6.5, (DOM0 - DD - R, ZA + R), (DOM0 - DD - R - 0.5, ZA + R), 1.6)
P1, S1 = b1.arrays()
ball1 = striped_ball('ball1', R, '#ff3b5c', '#ffffff')
anim_loc(ball1, np.stack([P1[:, 0], np.zeros(NF), P1[:, 1]], 1))
anim_rot(ball1, np.stack([np.zeros(NF), S1, np.zeros(NF)], 1))

# ================= dominoes (eighth notes 6.0 .. 7.75) =================
dcols = ['#ff6b6b', '#ff922b', '#fcc419', '#94d82d', '#20c997', '#339af0', '#845ef7', '#f06595']
dhits = [6.0 + 0.25 * i for i in range(8)]
dx = [DOM0 + i * 1.0 for i in range(8)]
LEV_HIT = 8.0
thc = math.asin((1.0 - DD) / DH)
dth = [None] * 8
# lever geometry
LPX, LPZ = 15.0, ZA + 0.9
LL = 5.0
A0 = math.radians(11)
lev_ang = np.where(ts < LEV_HIT, A0, A0 - 2 * A0 * smooth01((ts - LEV_HIT) / 0.08))
# domino 7: rests on the lever's left end
left_end_z = LPZ + (LL / 2) * np.sin(lev_ang) + 0.08
x7 = dx[7]
ang_touch = np.arccos(np.clip((left_end_z - ZA) / DH, -1, 1))
u = np.clip((ts - dhits[7]) / (LEV_HIT - dhits[7]), 0, 1)
th7 = np.where(ts < LEV_HIT, ang_touch[0] * u ** 1.5, ang_touch)
dth[7] = np.maximum.accumulate(th7)
for i in range(6, -1, -1):
    al = dth[i + 1]
    uu = np.clip((ts - dhits[i]) / (dhits[i + 1] - dhits[i]), 0, 1)
    ph1 = thc * uu ** 1.5
    ph2 = al + np.arcsin(np.clip((1.0 * np.cos(al) - DD) / DH, -1, 1))
    dth[i] = np.maximum.accumulate(np.where(ts < dhits[i + 1], ph1, np.maximum(ph2, thc)))
for i in range(8):
    ob = box(f'dom{i}', -DD, 0, -DW / 2, DW / 2, 0, DH, dcols[i], 0.04)
    ob.location = (dx[i], 0, ZA)
    anim_rot(ob, np.stack([np.zeros(NF), dth[i], np.zeros(NF)], 1))

# lever (seesaw)
box('fulcrum', LPX - 0.45, LPX + 0.45, -0.7, 0.7, ZA, LPZ - 0.08, DARK)
lever = box('lever', -LL / 2, LL / 2, -0.75, 0.75, 0, 0.16, '#f59f00', 0.03)
lever.location = (LPX, 0, LPZ)
cupL = box('levercup', LL / 2 - 0.12, LL / 2, -0.75, 0.75, 0.16, 0.6, '#f59f00', 0.02)
cupL.parent = lever
anim_rot(lever, np.stack([np.zeros(NF), lev_ang, np.zeros(NF)], 1))

# ================= ball 2 + xylophone stairs =================
NK = 8
KX = [19.6 - 1.3 * k for k in range(NK)]
KZ = [17.0 - 0.85 * k for k in range(NK)]
KT = [9.0 + 0.25 * k for k in range(NK)]
key_cols = ['#e03131', '#f76707', '#f59f00', '#37b24d', '#1098ad', '#1c7ed6', '#7048e8', '#d6336c']
for k in range(NK):
    key = box(f'key{k}', -0.6, 0.6, -0.85, 0.85, -0.22, 0, key_cols[k], 0.05)
    tk = ts - KT[k]
    dip = np.where((tk > 0) & (tk < 0.18), np.sin(np.clip(tk / 0.18, 0, 1) * math.pi) * 0.14, 0)
    anim_loc(key, np.stack([np.full(NF, KX[k]), np.zeros(NF), KZ[k] - dip], 1))
    # small posts under each key
    for yy in (-0.6, 0.6):
        box(f'kp{k}{yy}', KX[k] - 0.07, KX[k] + 0.07, yy - 0.07, yy + 0.07, KZ[k] - 0.62, KZ[k] - 0.22, '#adb5bd', 0)
# stair rails
rail_a = (KX[0] + 0.8, KZ[0] - 0.6); rail_b = (KX[-1] - 0.8, KZ[-1] - 0.6)
for yy in (-0.6, 0.6):
    rr = board(f'xrail{yy}', rail_a, rail_b, 0.25, WOOD2, depth=0.3); rr.location.y = yy
box('xbrk', 14.8, 15.1, 0.9, 1.4, 12.0, 14.6, DARK)

# ramp 6 and cup / pulley
R6 = ((8.7, 10.1), (3.6, 9.35))
board('ramp6', R6[0], R6[1], TH, WOOD)
r6r = board('rail6', (8.7, 10.28), (3.6, 9.53), 0.18, '#be4bdb', depth=0.15); r6r.location.y = -0.95
box('brk6', 5.9, 6.2, 0.9, 1.4, 8.4, 9.4, DARK)
def s6(x):
    (xa, za), (xb, zb) = R6
    return za + (x - xa) * (zb - za) / (xb - xa)

CUPX = 2.75; CUP_BOT0 = 7.6; DROP = 1.5
T_CUP = 12.0; T_GATE = 12.5
cup_off = -DROP * smooth01((ts - T_CUP) / (T_GATE - T_CUP))
b2 = Path(R)
p2 = (LPX + LL / 2 - 0.12 - R - 0.05, LPZ - (LL / 2) * math.sin(A0) + 0.16 + R + 0.1)
b2.hold(0, LEV_HIT + 0.05, p2)
b2.fly(LEV_HIT + 0.05, KT[0], p2, (KX[0], KZ[0] + R), 60)
for k in range(NK - 1):
    b2.fly(KT[k], KT[k + 1], (KX[k], KZ[k] + R), (KX[k + 1], KZ[k + 1] + R), 75)
b2.fly(KT[-1], 11.0, (KX[-1], KZ[-1] + R), (8.4, s6(8.4) + R), 75)
b2.roll(11.0, 11.6, (8.4, s6(8.4) + R), (3.75, s6(3.75) + R), 0.5)
b2.fly(11.6, T_CUP, (3.75, s6(3.75) + R), (CUPX, CUP_BOT0 + 0.12 + R), 30)
P2, S2 = b2.arrays()
P2[:, 1] += np.where(ts >= T_CUP, cup_off, 0)
S2 = np.where(ts >= T_CUP, S2[int(T_CUP * FPS)], S2)
ball2 = striped_ball('ball2', R, '#228be6', '#ffffff')
anim_loc(ball2, np.stack([P2[:, 0], np.zeros(NF), P2[:, 1]], 1))
anim_rot(ball2, np.stack([np.zeros(NF), S2, np.zeros(NF)], 1))

# cup (open bucket)
cup = bpy.data.objects.new('cup', None); link(cup)
parts = [box('cupb', -0.75, 0.75, -0.75, 0.75, 0, 0.12, '#12b886'),
         box('cupl', -0.75, -0.63, -0.75, 0.75, 0, 1.1, '#12b886'),
         box('cupr', 0.63, 0.75, -0.75, 0.75, 0, 1.1, '#12b886'),
         box('cupf', -0.75, 0.75, -0.75, -0.63, 0, 1.1, '#12b886'),
         box('cupk', -0.75, 0.75, 0.63, 0.75, 0, 1.1, '#12b886')]
for p in parts: p.parent = cup
anim_loc(cup, np.stack([np.full(NF, CUPX), np.zeros(NF), CUP_BOT0 + cup_off], 1))

# pulley + strings
PR = 0.6; PCX, PCZ = 2.15, 12.6
pul = cyl('pulley', PR, 0.3, '#868e96'); pul.location = (PCX, -0.2, PCZ)
sp = box('spoke', -PR * 0.9, PR * 0.9, -0.2, 0.2, -0.08, 0.08, '#343a40', 0); sp.parent = pul
sp2 = box('spoke2', -0.08, 0.08, -0.2, 0.2, -PR * 0.9, PR * 0.9, '#343a40', 0); sp2.parent = pul
set_curve(pul, 'rotation_euler', 1, -cup_off / PR)
box('pulleyarm', PCX - 0.1, PCX + 0.1, -0.1, 1.4, PCZ - 0.1, PCZ + 1.2, DARK, 0)
GATEX = PCX - PR
GATE_BOT0 = 4.0
strL = cyl('stringCup', 0.04, 1, '#343a40', 8, axis='Z')
strR = cyl('stringGate', 0.04, 1, '#343a40', 8, axis='Z')
cup_top = CUP_BOT0 + 1.1 + cup_off
gate_top = GATE_BOT0 + 1.6 - cup_off          # gate rises when cup falls
for ob, xs, zlo in ((strL, PCX + PR, cup_top), (strR, GATEX, gate_top)):
    ob.data.transform(Matrix.Translation((0, 0, 0.5)))  # base at origin
    ob.location = (xs, -0.2, 0)
    anim_loc(ob, np.stack([np.full(NF, xs), np.full(NF, -0.2), zlo], 1))
    set_curve(ob, 'scale', 2, PCZ - zlo)
# cup bail
bail = box('bail', -0.75, 0.75, -0.05, 0.05, 1.1, 1.18, '#343a40', 0); bail.parent = cup
gateC = box('gateC', -0.15, 0.15, -0.9, 0.9, 0, 1.6, '#fab005', 0.03)
anim_loc(gateC, np.stack([np.full(NF, GATEX), np.zeros(NF), gate_top - 1.6], 1))
# gate guides
box('guide1', GATEX - 0.3, GATEX - 0.17, -1.0, -0.9, 4.0, 7.6, DARK, 0)

# ================= car on the table =================
ZT = 4.0
def track_z(x): return ZT + np.maximum(0, 3.6 - x) * 0.28
board('carslope', (-1.5, track_z(-1.5)), (3.6, ZT), 0.25, WOOD)
box('carfloor', 3.5, 20.6, -1.0, 1.0, ZT - 0.1, ZT, '#d0bfff', 0.02)
CAR_HIT = 14.0
car = bpy.data.objects.new('car', None); link(car)
WR = 0.32
cb = box('carbody', -0.95, 0.95, -0.6, 0.6, WR * 0.9, WR * 0.9 + 0.55, '#ff3b5c'); cb.parent = car
cc = box('carcab', -0.6, 0.35, -0.5, 0.5, WR * 0.9 + 0.55, WR * 0.9 + 1.0, '#ffe066'); cc.parent = car
wheels = []
for wx in (-0.6, 0.6):
    for wy in (-0.62, 0.62):
        w = cyl(f'wheel{wx}{wy}', WR, 0.2, '#212529', 24); w.location = (wx, wy, WR)
        hub = box('hub', -0.05, 0.05, -0.11, 0.11, -WR * 0.8, WR * 0.8, '#ced4da', 0); hub.parent = w
        w.parent = car; wheels.append(w)
CX0 = GATEX - 0.15 - 0.96
uc = np.clip((ts - T_GATE) / (CAR_HIT - T_GATE), 0, 1)
cxs = CX0 + (18.0 - 0.95 - CX0) * (0.15 * uc + 0.85 * uc ** 1.7)
cxs = np.where(ts > CAR_HIT, (18.0 - 0.95) - 0.25 * smooth01((ts - CAR_HIT) / 0.2), cxs)
czs = track_z(cxs)
pitch = np.where(cxs < 3.6, math.atan(0.28), 0.0)
anim_loc(car, np.stack([cxs, np.zeros(NF), czs], 1))
anim_rot(car, np.stack([np.zeros(NF), pitch, np.zeros(NF)], 1))
spin = (cxs - cxs[0]) / WR
for w in wheels: set_curve(w, 'rotation_euler', 1, spin)

# ================= GOAL box & pop-up sign =================
box('goalbox', 18.0, 20.6, -1.0, 1.0, ZT, ZT + 1.6, '#4c6ef5')
box('goalboxlid', 17.9, 20.7, -1.05, 1.05, ZT + 1.6, ZT + 1.75, '#364fc7')
sign = bpy.data.objects.new('sign', None); link(sign)
pole = box('pole', -0.1, 0.1, -0.1, 0.1, -3.2, 0, '#adb5bd', 0); pole.parent = sign
spr = box('board', -3.0, 3.0, -0.2, 0.2, 0, 2.4, '#ffd43b', 0.08); spr.parent = sign
bpy.ops.object.text_add()
txt = bpy.context.active_object
try:
    txt.data.font = bpy.data.fonts.load('/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc')
    txt.data.body = 'ゴール！'
except Exception:
    txt.data.body = 'GOAL!'
txt.data.align_x = 'CENTER'; txt.data.align_y = 'CENTER'
txt.data.size = 1.7; txt.data.extrude = 0.05
txt.data.materials.append(M('#e03131'))
txt.parent = sign; txt.location = (0, -0.26, 1.2); txt.rotation_euler = (math.pi / 2, 0, 0)
tg = ts - CAR_HIT
spring = np.where(tg <= 0, 0.0, 1 - np.exp(-tg * 6) * np.cos(tg * 19))
sign_z = (ZT + 1.75 - 3.2 + 0.1) + spring * 5.4
sign_z = np.where(tg <= 0, -30.0, sign_z)
anim_loc(sign, np.stack([np.full(NF, 19.3), np.zeros(NF), sign_z], 1))
sign_tilt = np.where(tg > 0, np.exp(-tg * 4) * np.sin(tg * 14) * 0.18, 0)
set_curve(sign, 'rotation_euler', 1, sign_tilt)
# push plate the car hits
plate = box('plate', -0.12, 0, -0.7, 0.7, 0.1, 1.2, '#ff922b', 0.02)
anim_loc(plate, np.stack([18.0 - 0.0 * np.ones(NF) + np.where(tg > 0, 0.12 * smooth01(tg / 0.05), 0), np.zeros(NF), np.full(NF, ZT)], 1))

# confetti
conf_cols = ['#ff6b6b', '#ffd43b', '#51cf66', '#339af0', '#cc5de8', '#ff922b', '#ffffff']
bpy.ops.mesh.primitive_plane_add(size=1); cp = bpy.context.active_object
cme = cp.data; cme.transform(Matrix.Diagonal((0.32, 0.18, 1, 1))); bpy.data.objects.remove(cp)
cme.materials.append(None)
fC = int(CAR_HIT * FPS)
for k in range(220):
    ob = bpy.data.objects.new(f'conf{k}', cme); link(ob)
    ob.material_slots[0].link = 'OBJECT'; ob.material_slots[0].material = M(random.choice(conf_cols))
    side = random.choice([-1, 1])
    p = np.array([19.3 + side * 1.2, random.uniform(-0.8, 0.3), ZT + 1.8])
    v = np.array([side * random.uniform(1, 9), random.uniform(-5, 0.5), random.uniform(14, 26)])
    ph = random.uniform(0, 6.3); delay = random.uniform(0, 0.25)
    P = np.zeros((NF, 3)); P[:] = (0, 0, -20)
    for n in range(fC, NF):
        t = ts[n] - CAR_HIT
        if t > delay:
            vv = v + (np.array([0, 0, -26]) - 1.4 * v) / FPS
            v = vv; v[2] = max(v[2], -3.0)
            p = p + v / FPS + np.array([math.sin(t * 6 + ph), 0, 0]) * 0.03
            if p[2] < ZT + 0.02: p[2] = ZT + 0.02; v[:] = 0
        P[n] = p
    anim_loc(ob, P)
    spinv = np.random.randn(3) * 8
    anim_rot(ob, np.stack([spinv[a] * np.clip(ts - CAR_HIT, 0, None) + random.uniform(0, 6) for a in range(3)], 1))

# ================= camera =================
cam_d = bpy.data.cameras.new('cam'); cam_d.lens = 50; cam_d.sensor_fit = 'VERTICAL'; cam_d.sensor_height = 36
cam_d.clip_end = 500
cam = link(bpy.data.objects.new('cam', cam_d)); cam.rotation_mode = 'XYZ'
scene.camera = cam
key = [(0.0, 4.0, 29.2, 13.5), (1.3, 4.3, 29.0, 13.0), (2.6, 4.3, 27.5, 13.5), (4.6, 4.2, 25.0, 14.0),
       (5.5, 3.6, 22.5, 12.5), (6.3, 6.8, 21.5, 11.5), (7.6, 11.0, 21.6, 12.0), (8.15, 14.3, 21.8, 13.0),
       (8.6, 16.3, 21.2, 14.5), (9.1, 16.6, 17.8, 14.0), (10.8, 11.6, 14.6, 13.5), (11.5, 7.0, 11.8, 12.0),
       (12.15, 3.6, 9.6, 12.0), (12.6, 3.8, 7.8, 11.5), (13.3, 9.5, 7.2, 11.0), (14.0, 15.6, 7.6, 11.5),
       (14.6, 17.5, 8.4, 12.5), (15.6, 17.3, 8.6, 13.0), (17.4, 10.0, 19.6, 40.0), (19.0, 10.0, 19.6, 40.5)]
kt = np.array([k[0] for k in key])
from scipy.interpolate import PchipInterpolator
cx = PchipInterpolator(kt, [k[1] for k in key])(ts)
cz = PchipInterpolator(kt, [k[2] for k in key])(ts)
ch = PchipInterpolator(kt, np.log([k[3] for k in key]))(ts)
def gs(a, s):
    r = int(3 * s); k = np.exp(-0.5 * (np.arange(-r, r + 1) / s) ** 2); k /= k.sum()
    return np.convolve(np.pad(a, r, mode='edge'), k, 'valid')
cx, cz, ch = gs(cx, 4), gs(cz, 4), np.exp(gs(ch, 4))
tanv = 18 / 50
dist = ch / 2 / tanv
CP = np.stack([cx + dist * 0.06, -dist, cz + dist * 0.12], 1)
rot = []
for n in range(NF):
    fwd = Vector((cx[n], 0, cz[n])) - Vector(CP[n])
    rot.append(tuple(fwd.to_track_quat('-Z', 'Y').to_euler()))
anim_loc(cam, CP); anim_rot(cam, np.unwrap(np.array(rot), axis=0))

# ================= render settings =================
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
scene.display.render_aa = 'FXAA'
sh = scene.display.shading
sh.light = 'STUDIO'; sh.studio_light = 'outdoor.sl'; sh.color_type = 'MATERIAL'
sh.show_shadows = True; sh.shadow_intensity = 0.3
sh.show_cavity = True; sh.cavity_type = 'BOTH'
sh.show_specular_highlight = True
scene.display.light_direction = (-0.35, -0.55, 0.75)
scene.display.shadow_shift = 0.02; scene.display.shadow_focus = 0.2
scene.view_settings.view_transform = 'Standard'
scene.view_settings.exposure = 0.7
world = bpy.data.worlds.new('w'); world.color = srgb('#fdf3e1'); scene.world = world

bpy.ops.wm.save_as_mainfile(filepath='/home/claude/pyta/machine.blend')
json.dump(dict(P2z=P2[:, 1].tolist(), fps=FPS, end=END_T), open('/home/claude/pyta/b2.json', 'w'))
print('BUILT', NF)
