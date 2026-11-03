import bpy, math, json, random
import numpy as np
from mathutils import Vector, Matrix
import bmesh

S = json.load(open('/home/claude/ice/score.json'))
FPS = 30; END = S['END']; NF = int(END * FPS) + 1
ts = np.arange(NF) / FPS
random.seed(21); np.random.seed(21)
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
def M(h, rough=0.15):
    if h not in MATS:
        m = bpy.data.materials.new(h); m.diffuse_color = (*hexl(h), 1); m.roughness = rough; MATS[h] = m
    return MATS[h]
def link(o): scene.collection.objects.link(o); return o
def smooth01(u): u = np.clip(u, 0, 1); return u * u * (3 - 2 * u)

# ---------------- delicate snowflake meshes (dendrites) ----------------
def add_bar(bm, p0, p1, w, th=0.02):
    d = np.array(p1) - np.array(p0); L = np.linalg.norm(d)
    if L < 1e-6: return
    ux = d / L; uy = np.array([-ux[1], ux[0]])
    pts = [np.array(p0) - uy * w / 2, np.array(p1) - uy * w / 2, np.array(p1) + uy * w / 2, np.array(p0) + uy * w / 2]
    vb = [bm.verts.new((p[0], p[1], -th / 2)) for p in pts]; vt = [bm.verts.new((p[0], p[1], th / 2)) for p in pts]
    bm.faces.new(vt); bm.faces.new(list(reversed(vb)))
    for k in range(4): bm.faces.new((vb[k], vb[(k + 1) % 4], vt[(k + 1) % 4], vt[k]))
def rot2(v, a): return np.array([v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a)])
def snowflake_mesh(name, seed):
    rnd = random.Random(seed); bm = bmesh.new()
    w0 = rnd.uniform(0.035, 0.05)
    nb = rnd.randint(3, 5)
    br = sorted(rnd.uniform(0.18, 0.85) for _ in range(nb))
    bl = [rnd.uniform(0.18, 0.42) * (1 - 0.5 * b) for b in br]
    ring = rnd.random() < 0.6; rr = rnd.uniform(0.12, 0.22)
    for a in range(6):
        ang = a * math.pi / 3
        dirv = np.array([math.cos(ang), math.sin(ang)])
        add_bar(bm, (0, 0), dirv * 1.0, w0)
        for b, L in zip(br, bl):
            base = dirv * b
            for s in (-1, 1):
                d2 = rot2(dirv, s * math.pi / 3)
                add_bar(bm, base, base + d2 * L, w0 * 0.75)
                if L > 0.25:
                    m = base + d2 * L * 0.55
                    for s2 in (-1, 1):
                        add_bar(bm, m, m + rot2(d2, s2 * math.pi / 3) * L * 0.35, w0 * 0.55)
        if ring:
            p0 = np.array([math.cos(ang), math.sin(ang)]) * rr; p1 = np.array([math.cos(ang + math.pi / 3), math.sin(ang + math.pi / 3)]) * rr
            add_bar(bm, p0, p1, w0 * 0.8)
        tip = dirv * 1.0
        add_bar(bm, tip - rot2(dirv, 0.5) * 0.12, tip, w0 * 0.6); add_bar(bm, tip - rot2(dirv, -0.5) * 0.12, tip, w0 * 0.6)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(None); return me
FLAKES = [snowflake_mesh(f'flake{i}', 100 + i) for i in range(14)]
def needle_me(name, tipf=0.3):
    bm = bmesh.new()
    r0 = [bm.verts.new((math.cos(a), math.sin(a), 0)) for a in np.linspace(0, 2 * math.pi, 7)[:-1]]
    r1 = [bm.verts.new((math.cos(a), math.sin(a), 1 - tipf)) for a in np.linspace(0, 2 * math.pi, 7)[:-1]]
    tip = bm.verts.new((0, 0, 1))
    bm.faces.new(list(reversed(r0)))
    for k in range(6):
        bm.faces.new((r0[k], r0[(k + 1) % 6], r1[(k + 1) % 6], r1[k])); bm.faces.new((r1[k], r1[(k + 1) % 6], tip))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(None); return me
NEEDLE = needle_me('needle', 0.22)
BAR = bpy.data.meshes.new('bar'); bm = bmesh.new(); add_bar(bm, (0, 0), (1, 0), 1.0, 1.0); bm.to_mesh(BAR); bm.free(); BAR.materials.append(None)

on = S['onsets']; N = len(on); times = np.array([o['t'] for o in on])
ICE = ['#ffffff', '#e6f6ff', '#c9ecff', '#b7dcff', '#dcd2ff', '#f0e9ff']

def anim_color(ob, base_hex, t0, name):
    m = bpy.data.materials.new(name); m.roughness = 0.1
    ob.material_slots[0].link = 'OBJECT'; ob.material_slots[0].material = m
    base = hexl(base_hex); dt_ = ts - t0
    fl = np.where(dt_ >= 0, np.exp(-dt_ * 5), 0)
    c = base[None] * (1 - fl[:, None]) + np.array([1.0, 1.0, 1.0])[None] * fl[:, None]
    for ch in range(3): set_curve(m, 'diffuse_color', ch, c[:, ch])
def bloom(ob, t0, scale, spin=True, dur=0.45):
    dt_ = ts - t0; g = np.clip(dt_ / dur, 0, 1)
    s = np.where(dt_ < 0, 0.0001, scale * (smooth01(g) * (1 + 0.12 * np.sin(g * math.pi))))
    s = np.maximum(s, 0.0001)
    for a in range(3): set_curve(ob, 'scale', a, s)
    if spin:
        base = ob.rotation_euler[2]
        set_curve(ob, 'rotation_euler', 2, base + np.where(dt_ < 0, -1.2, -1.2 * (1 - smooth01(g))))

# ---------------- build plan ----------------
# A) giant dendritic snowflake drawn on the frozen lake (6-fold, each note = one stroke in all six arms)
strokes = []          # (dist, segments list of (p0, p1, w)) in the arm frame (+x)
def arm_strokes():
    out = []
    spine = [(1.2, 3.0), (3.0, 5.0), (5.0, 7.0), (7.0, 9.0), (9.0, 11.2), (11.2, 12.4)]
    for a, b in spine: out.append((a, [((a, 0), (b, 0), 0.16)]))
    out.append((0.0, [((math.cos(0) * 1.2, math.sin(0) * 1.2), (math.cos(math.pi / 3) * 1.2, math.sin(math.pi / 3) * 1.2), 0.12)]))
    for b, L in [(2.4, 2.6), (4.2, 3.3), (6.2, 3.0), (8.2, 2.3), (10.0, 1.5)]:
        segs = []
        for s in (-1, 1):
            d = rot2(np.array([1.0, 0]), s * math.pi / 3)
            segs.append(((b, 0), tuple(np.array([b, 0]) + d * L), 0.11))
        out.append((b + 0.1, segs))
        for f in (0.35, 0.65, 0.9):
            segs = []
            for s in (-1, 1):
                d = rot2(np.array([1.0, 0]), s * math.pi / 3); m = np.array([b, 0]) + d * L * f
                for s2 in (-1, 1):
                    d2 = rot2(d, s2 * math.pi / 3)
                    segs.append((tuple(m), tuple(m + d2 * L * 0.32 * (1.1 - f)), 0.06))
            out.append((b + 0.2 + f, segs))
    for x in np.arange(1.6, 12.0, 0.55):          # fine needles along the spine
        segs = []
        for s in (-1, 1):
            d = rot2(np.array([1.0, 0]), s * math.pi / 3)
            segs.append(((x, 0), tuple(np.array([x, 0]) + d * 0.38), 0.045))
        out.append((x + 0.05, segs))
    out.sort(key=lambda o: o[0])
    return out
FLOOR = arm_strokes()
NFLOOR = len(FLOOR)
# B) colonnades, spires, central tower, floating flakes
plan = []
for k in range(NFLOOR): plan.append(('floor', k))
def ring_slots(n, rad, start=-math.pi / 2):
    out = []
    for k in range(n):
        j = (k + 1) // 2 * (1 if k % 2 else -1)
        a = start + j * 2 * math.pi / n
        out.append(a)
    return out
for a in ring_slots(36, 9.0): plan.append(('pillar', a, 9.0, 3.4, 0.2, 0.5))
for a in ring_slots(36, 9.0): plan.append(('panel', a + math.pi / 36, 9.0, 2.5, 2 * 9.0 * math.sin(math.pi / 36) - 0.25, 0.5))
for a in ring_slots(24, 6.2): plan.append(('pillar', a, 6.2, 5.2, 0.26, 0.65))
for a in ring_slots(24, 6.2): plan.append(('panel', a + math.pi / 24, 6.2, 4.0, 2 * 6.2 * math.sin(math.pi / 24) - 0.3, 0.7))
spire_angles = [-math.pi / 2 + math.pi / 6 + i * math.pi / 3 for i in [0, 3, 1, 4, 2, 5]]
for a in spire_angles:
    cx, cy = 7.6 * math.cos(a), 7.6 * math.sin(a)
    plan.append(('needle', cx, cy, 4.2, 0.62)); plan.append(('needle', cx, cy, 7.0, 0.42)); plan.append(('needle', cx, cy, 10.2, 0.24))
    for k in range(6):
        aa = k * math.pi / 3
        plan.append(('needle', cx + 0.75 * math.cos(aa), cy + 0.75 * math.sin(aa), random.uniform(4.6, 5.8), 0.13))
    plan.append(('flake', cx, cy, 10.9, 1.1, a))
for a in ring_slots(12, 2.4): plan.append(('needle', 2.4 * math.cos(a), 2.4 * math.sin(a), random.uniform(9.0, 11.5), 0.32))
for a in ring_slots(6, 1.1): plan.append(('needle', 1.1 * math.cos(a), 1.1 * math.sin(a), 14.0, 0.42))
remaining = N - 1 - len(plan)
floaters = []
for k in range(max(remaining, 0)):
    a = random.uniform(0, 2 * math.pi); rr = random.uniform(3, 13); z = random.uniform(3, 15)
    floaters.append(('flake', rr * math.cos(a), rr * math.sin(a), z, random.uniform(0.35, 0.8), a))
# interleave floaters through the palace part so the air fills with flakes as it rises
palace = plan[NFLOOR:]
mixed = []; fi = 0
step = max(1, len(palace) // max(len(floaters), 1))
for i, p in enumerate(palace):
    mixed.append(p)
    if fi < len(floaters) and i % step == step - 1:
        mixed.append(floaters[fi]); fi += 1
mixed += floaters[fi:]
plan = (plan[:NFLOOR] + mixed)[:N - 1]
plan.append(('crown',))
assert len(plan) == N, (len(plan), N)
print('floor strokes', NFLOOR, 'palace pieces', len(palace), 'floaters', len(floaters))

# ---------------- create ----------------
ARM = bpy.data.collections.new('floorarm')
orb_pts = []
for i, p in enumerate(plan):
    t0 = times[i]
    if p[0] == 'floor':
        dist, segs = FLOOR[p[1]]
        for j, (a, b, w) in enumerate(segs):
            d = np.array(b) - np.array(a); L = np.linalg.norm(d)
            ob = bpy.data.objects.new(f'f{i}_{j}', BAR); ARM.objects.link(ob)
            ob.location = (a[0], a[1], 0.02); ob.rotation_euler = (0, 0, math.atan2(d[1], d[0]))
            g = np.clip((ts - t0) / 0.35, 0, 1)
            set_curve(ob, 'scale', 0, np.maximum(L * smooth01(g), 0.0001))
            set_curve(ob, 'scale', 1, np.where(ts >= t0, w, 0.0001)); set_curve(ob, 'scale', 2, np.full(NF, 0.05))
            anim_color(ob, '#dff3ff' if w > 0.1 else '#b9e2ff', t0, f'fm{i}_{j}')
        orb_pts.append((segs[0][1][0], segs[0][1][1], 0.4))
    elif p[0] == 'pillar':
        _, a, rad, h, r, fs = p
        x, y = rad * math.cos(a), rad * math.sin(a)
        ob = link(bpy.data.objects.new(f'p{i}', NEEDLE)); ob.location = (x, y, 0)
        g = np.clip((ts - t0) / 0.35, 0, 1)
        set_curve(ob, 'scale', 0, np.where(ts >= t0, r, 0.0001)); set_curve(ob, 'scale', 1, np.where(ts >= t0, r, 0.0001))
        set_curve(ob, 'scale', 2, np.maximum(h * smooth01(g) * (1 + 0.06 * np.sin(g * math.pi)), 0.0001))
        anim_color(ob, random.choice(ICE), t0, f'pm{i}')
        fl = link(bpy.data.objects.new(f'pf{i}', random.choice(FLAKES))); fl.location = (x, y, h + fs * 0.9)
        fl.rotation_euler = (math.pi / 2, 0, a + math.pi / 2); bloom(fl, t0 + 0.12, fs)
        anim_color(fl, '#ffffff', t0 + 0.12, f'pfm{i}')
        orb_pts.append((x, y, h * 0.7))
    elif p[0] == 'panel':
        _, a, rad, h, wdt, fs = p
        x, y = rad * math.cos(a), rad * math.sin(a)
        ob = link(bpy.data.objects.new(f'w{i}', BAR)); ob.location = (x, y, 0)
        ob.rotation_euler = (math.pi / 2, 0, a + math.pi / 2)
        ob.location = (x - math.cos(a + math.pi / 2) * wdt / 2, y - math.sin(a + math.pi / 2) * wdt / 2, 0)
        g = np.clip((ts - t0) / 0.35, 0, 1)
        set_curve(ob, 'scale', 0, np.where(ts >= t0, wdt, 0.0001)); set_curve(ob, 'scale', 2, np.full(NF, 0.08))
        set_curve(ob, 'scale', 1, np.maximum(h * smooth01(g), 0.0001))
        set_curve(ob, 'location', 2, 0.5 * h * smooth01(g))
        anim_color(ob, random.choice(['#9fd3f7', '#a9c8ff', '#b9dcff']), t0, f'wm{i}')
        fl = link(bpy.data.objects.new(f'wf{i}', random.choice(FLAKES)))
        fl.location = (x + math.cos(a) * 0.08, y + math.sin(a) * 0.08, h * 0.55)
        fl.rotation_euler = (math.pi / 2, 0, a + math.pi / 2); bloom(fl, t0 + 0.15, fs)
        anim_color(fl, '#ffffff', t0 + 0.15, f'wfm{i}')
        orb_pts.append((x, y, h * 0.6))
    elif p[0] == 'needle':
        _, x, y, h, r = p
        ob = link(bpy.data.objects.new(f'n{i}', NEEDLE)); ob.location = (x, y, 0)
        g = np.clip((ts - t0) / 0.35, 0, 1)
        set_curve(ob, 'scale', 0, np.where(ts >= t0, r, 0.0001)); set_curve(ob, 'scale', 1, np.where(ts >= t0, r, 0.0001))
        set_curve(ob, 'scale', 2, np.maximum(h * smooth01(g) * (1 + 0.06 * np.sin(g * math.pi)), 0.0001))
        anim_color(ob, random.choice(ICE), t0, f'nm{i}')
        orb_pts.append((x, y, h * 0.7))
    elif p[0] == 'flake':
        _, x, y, z, s, a = p
        fl = link(bpy.data.objects.new(f'fl{i}', random.choice(FLAKES))); fl.location = (x, y, z)
        fl.rotation_euler = (math.pi / 2 + random.uniform(-0.3, 0.3), 0, a + math.pi / 2 + random.uniform(-0.4, 0.4))
        bloom(fl, t0, s); anim_color(fl, random.choice(['#ffffff', '#e6f6ff', '#dcd2ff']), t0, f'flm{i}')
        if s < 0.9:
            sp = random.uniform(0.15, 0.4)
            set_curve(fl, 'location', 2, z + 0.25 * np.sin((ts - t0) * sp * 3 + i))
        orb_pts.append((x, y, z))
    else:  # crown: main spire + giant snowflake crown
        ob = link(bpy.data.objects.new('mainspire', NEEDLE)); ob.location = (0, 0, 0)
        g = np.clip((ts - t0) / 0.6, 0, 1)
        set_curve(ob, 'scale', 0, np.where(ts >= t0 - 0.0, 0.75, 0.0001)); set_curve(ob, 'scale', 1, np.where(ts >= t0, 0.75, 0.0001))
        set_curve(ob, 'scale', 2, np.maximum(19.0 * smooth01(g), 0.0001))
        anim_color(ob, '#ffffff', t0, 'msm')
        for j, (s, zz, rotz) in enumerate([(3.6, 21.0, 0.0), (2.2, 21.05, math.pi / 6)]):
            cr = link(bpy.data.objects.new(f'crown{j}', FLAKES[3 + j * 5])); cr.location = (0, 0, zz)
            cr.rotation_euler = (math.pi / 2, 0, rotz)
            bloom(cr, t0 + 0.35, s, dur=0.9); anim_color(cr, '#ffffff', t0 + 0.35, f'crm{j}')
            de = ts - t0
            set_curve(cr, 'rotation_euler', 1, np.where(de > 0, de * (0.35 if j == 0 else -0.5), 0))
        orb_pts.append((0, 0, 20))
# instance floor arm 6x
for k in range(6):
    e = link(bpy.data.objects.new(f'farm{k}', None)); e.instance_type = 'COLLECTION'; e.instance_collection = ARM
    e.rotation_euler = (0, 0, math.radians(60 * k) - math.pi / 2)
# the guiding light (orb + sparkle trail)
orb_pts = np.array(orb_pts)
from scipy.interpolate import PchipInterpolator
kt = np.concatenate([[0.0], times]); kp = np.vstack([[[0, -10, 5]], orb_pts])
# floor strokes were made in the arm frame; rotate their orb targets into the first arm's world frame
rotm = np.array([[math.cos(-math.pi / 2), -math.sin(-math.pi / 2)], [math.sin(-math.pi / 2), math.cos(-math.pi / 2)]])
for k in range(NFLOOR):
    kp[k + 1, :2] = rotm @ kp[k + 1, :2]
interp = PchipInterpolator(kt, kp, axis=0)
for j, (sz, lag) in enumerate([(0.22, 0.0), (0.16, 0.04), (0.12, 0.08), (0.09, 0.12), (0.07, 0.16), (0.05, 0.2)]):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=sz)
    o = bpy.context.active_object; o.data.materials.append(M('#ffffff'))
    P = interp(np.clip(ts - lag, 0, times[-1]))
    vis = ts < times[-1] + 0.2
    for a in range(3): set_curve(o, 'location', a, np.where(vis, P[:, a], -80))

# ---------------- environment ----------------
world = bpy.data.worlds.new('w'); world.color = tuple(hexl('#050a20')); scene.world = world
bpy.ops.mesh.primitive_circle_add(vertices=128, radius=500, fill_type='NGON'); lake = bpy.context.active_object
lake.data.materials.append(M('#0b1532', 1.0))
for k in range(30):
    a = k * 2 * math.pi / 30 + random.uniform(-0.05, 0.05); rr = random.uniform(190, 240); h = random.uniform(20, 42); w = random.uniform(40, 70)
    bpy.ops.mesh.primitive_cone_add(radius1=w, radius2=0, depth=h, vertices=9, location=(rr * math.cos(a), rr * math.sin(a), h / 2 - 2))
    c = bpy.context.active_object; c.data.materials.append(M('#0d1531', 0.9))
bm = bmesh.new()
for k in range(1100):
    th = random.uniform(0, 2 * math.pi); ph = random.uniform(0.1, 1.4); rr = 420
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=random.choice([0.4, 0.7, 1.0]),
                               matrix=Matrix.Translation((rr * math.cos(ph) * math.cos(th), rr * math.cos(ph) * math.sin(th), rr * math.sin(ph))))
me = bpy.data.meshes.new('stars'); bm.to_mesh(me); bm.free(); me.materials.append(M('#eef3ff', 1.0)); link(bpy.data.objects.new('stars', me))
for i, (col, z0, hh, ph0) in enumerate([('#29d39a', 60, 26, 0.0), ('#1b9d84', 82, 20, 1.0), ('#6d5cff', 98, 18, 2.0), ('#3fd6d0', 50, 12, 3.1)]):
    bm = bmesh.new(); vt = []; vb = []
    angs = np.linspace(math.radians(20), math.radians(170), 140)
    for a in angs:
        rr = 330 + 25 * math.sin(a * 5 + ph0); z = z0 + 10 * math.sin(a * 7 + ph0)
        vb.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z))); vt.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z + hh)))
    for k in range(len(angs) - 1): bm.faces.new((vb[k], vb[k + 1], vt[k + 1], vt[k]))
    me = bpy.data.meshes.new(f'aur{i}'); bm.to_mesh(me); bm.free(); me.materials.append(M(col, 1.0))
    o = link(bpy.data.objects.new(f'aur{i}', me)); set_curve(o, 'rotation_euler', 2, 0.03 * np.sin(ts * 0.3 + i))
# falling tiny snowflakes
for i in range(220):
    o = link(bpy.data.objects.new(f'sn{i}', FLAKES[i % len(FLAKES)])); r = random.uniform(0.08, 0.18); o.scale = (r, r, r)
    o.material_slots[0].link = 'OBJECT'; o.material_slots[0].material = M('#ffffff', 1.0)
    x0, y0, z0 = random.uniform(-22, 22), random.uniform(-22, 22), random.uniform(0, 26); sp = random.uniform(0.6, 1.2)
    set_curve(o, 'location', 0, x0 + 0.5 * np.sin(ts * 0.7 + i)); set_curve(o, 'location', 1, np.full(NF, y0))
    set_curve(o, 'location', 2, (z0 - sp * ts) % 26)
    set_curve(o, 'rotation_euler', 0, ts * random.uniform(0.5, 1.5)); set_curve(o, 'rotation_euler', 1, ts * random.uniform(0.3, 1.0))

# ---------------- camera ----------------
cd = bpy.data.cameras.new('cam'); cd.lens = 26; cd.sensor_fit = 'VERTICAL'; cd.sensor_height = 36; cd.clip_end = 2000
cam = link(bpy.data.objects.new('cam', cd)); scene.camera = cam; cam.rotation_mode = 'XYZ'
TF = times[-1]; T_FLOOR = times[NFLOOR - 1]
u = ts / END
ang = math.radians(-100) + math.radians(80) * smooth01(u)
fl = 1 - smooth01((ts - T_FLOOR + 3) / 6)              # high overhead while the floor is drawn
rad = (14 * fl + 24 * (1 - fl)) + 4 * smooth01((ts - TF) / 4)
hgt = (24 * fl + 9 * (1 - fl)) + 5 * smooth01((ts - T_FLOOR) / 40) + 3 * smooth01((ts - TF) / 4)
lz = (0.0 * fl + 6.0 * (1 - fl)) + 3.5 * smooth01((ts - T_FLOOR) / 40)
CP = np.stack([rad * np.cos(ang), rad * np.sin(ang), hgt], 1)
look = np.stack([np.zeros(NF), np.zeros(NF), lz], 1)
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
sh.show_shadows = False; sh.show_cavity = False; sh.show_specular_highlight = True
scene.view_settings.view_transform = 'Standard'; scene.view_settings.exposure = 0.4
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/ice2/ice2.blend')
print('BUILT', NF, 'T_FLOOR', round(T_FLOOR, 1))
