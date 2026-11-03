"""Spiral bounce engine (Blender / bpy).

Two (or more) glowing balls bounce along a rising spiral track. Every bounce is one note:
the ball lands on a glass slat exactly at the note time, and the bounce height follows pitch.
The path leaves a light thread; at the end the camera rises to show the whole song as a spiral.

Run with the bpy-enabled Python:
    python studio/spiral_scene.py <config.json> <arr.json> <out.blend>
"""
import bpy, math, json, random, sys
import numpy as np
from mathutils import Vector, Matrix
import bmesh

CFG_PATH, ARR_PATH, OUT_BLEND = sys.argv[-3:]
CFG = json.load(open(CFG_PATH))
SC = CFG.get('scene', {})
A = json.load(open(ARR_PATH))
FPS = 30
END = A['END']; NF = int(END * FPS) + 1
ts = np.arange(NF) / FPS
random.seed(SC.get('seed', 8)); np.random.seed(SC.get('seed', 8))
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS; scene.frame_start, scene.frame_end = 0, NF - 1

# ---------------- helpers ----------------
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
def set_linear_0_1(idb, path):
    ensure_action(idb)
    fc = idb.animation_data.action.fcurve_ensure_for_datablock(idb, path, index=0)
    fc.keyframe_points.add(2); fc.keyframe_points.foreach_set('co', np.array([0, 0.0, NF - 1, 1.0], np.float32))
    fc.keyframe_points.foreach_set('interpolation', np.array([1, 1], np.int32)); fc.update()
def lin(c):
    c = np.asarray(c, float); return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def hexl(h): h = h.lstrip('#'); return lin([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])
MATS = {}
def M(h, rough=0.2):
    if (h, rough) not in MATS:
        m = bpy.data.materials.new(h); m.diffuse_color = (*hexl(h), 1); m.roughness = rough; MATS[(h, rough)] = m
    return MATS[(h, rough)]
def link(o): scene.collection.objects.link(o); return o
def smooth01(u): u = np.clip(u, 0, 1); return u * u * (3 - 2 * u)
def gs(a, sg):
    r = int(3 * sg); k = np.exp(-0.5 * (np.arange(-r, r + 1) / sg) ** 2); k /= k.sum()
    if a.ndim == 1: return np.convolve(np.pad(a, r, mode='edge'), k, 'valid')
    return np.stack([gs(a[:, j], sg) for j in range(a.shape[1])], 1)

EV = A['events']; EM = A['end_music']
G = SC.get('gravity', 34.0); R = SC.get('ball_radius', 0.24)

# ---------------- path: arc length follows the beat ----------------
beat_voice = SC.get('beat_voice', 'bass')
bt = np.array(sorted(set(round(e['t'], 4) for e in EV if e['voice'] == beat_voice)))
bs = SC.get('units_per_beat', 4.0) * np.arange(len(bt))
def s_of(t):
    if t <= bt[-1]: return float(np.interp(t, bt, bs, left=bs[0] - (bt[0] - t) * 3.0))
    return float(bs[-1] + (t - bt[-1]) * 3.0)
r0 = SC.get('spiral_r0', 7.0); b = SC.get('spiral_turn_gap', 4.6) / (2 * math.pi)
th_tab = np.linspace(0, 40 * math.pi, 40000)
r_tab = r0 + b * th_tab
s_tab = np.concatenate([[0], np.cumsum(np.hypot(np.diff(r_tab * np.cos(th_tab)), np.diff(r_tab * np.sin(th_tab))))])
def spiral(s, roff=0.0):
    th = np.interp(s, s_tab, th_tab); r = r0 + b * th + roff
    p = np.array([r * math.cos(th), r * math.sin(th)])
    tan = np.array([-math.sin(th), math.cos(th)]); rad = np.array([math.cos(th), math.sin(th)])
    return p, tan, rad

# ---------------- lanes (one ball each) ----------------
def z_of(o, zmap):
    m = zmap.get(o['voice'], zmap.get('*'))
    if 'fixed' in m: return m['fixed']
    key = max(o['midis']) if m.get('use', 'max') == 'max' else min(o['midis'])
    return m['base'] + (key - m['ref']) * m['scale']
LANES = []
for L in SC['lanes']:
    es = [e for e in EV if e['voice'] in L['voices']]
    hits = []
    for e in es:
        if hits and e['t'] - hits[-1]['t'] < L.get('merge', 0.07):
            hits[-1]['midis'].append(e['midi']); continue
        hits.append(dict(t=e['t'], midis=[e['midi']], voice=e['voice']))
    for o in hits: o['z'] = z_of(o, L['z'])
    LANES.append((hits, L))

def build_ball(hits, roff, tsx=None):
    tsx = ts if tsx is None else tsx
    times = np.array([h['t'] for h in hits]); zs = np.array([h['z'] for h in hits]); ss = np.array([s_of(t) for t in times])
    P = np.zeros((len(tsx), 3)); vin = []; vout = []
    for k in range(len(hits) - 1):
        T = times[k + 1] - times[k]
        vs = (ss[k + 1] - ss[k]) / T; vz = ((zs[k + 1] - zs[k]) + 0.5 * G * T * T) / T
        vout.append((vs, vz)); vin.append((vs, vz - G * T))
    for f, t in enumerate(tsx):
        if t < times[0]:
            tau = times[0] - t; s = ss[0] - 1.5 * tau; z = zs[0] + 0.5 * G * min(tau, 0.6) ** 2 + 2.0 * min(tau, 0.6)
        elif t >= times[-1]:
            tau = t - times[-1]; s = ss[-1]; z = zs[-1] + max(0.0, 4.0 * tau - 0.5 * G * tau * tau) if tau < 0.2 else zs[-1]
        else:
            k = np.searchsorted(times, t, side='right') - 1
            tau = t - times[k]; vs, vz = vout[k]
            s = ss[k] + vs * tau; z = zs[k] + vz * tau - 0.5 * G * tau * tau
        p, _, _ = spiral(s, roff); P[f] = (p[0], p[1], z)
    nrm = []
    for k in range(len(hits)):
        vi = np.array(vin[k - 1]) if k > 0 else np.array([1.5, -9.0])
        vo = np.array(vout[k]) if k < len(vout) else np.array([0.0, 6.0])
        n_ = vo - vi; n_ /= np.linalg.norm(n_); nrm.append(n_)
    return times, zs, ss, P, nrm

# ---------------- meshes ----------------
SL = SC.get('slat', [0.95, 0.26, 0.05])
def cube_me(name, sx, sy, sz, zoff=0.0, bevel=0.0):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts: v.co.x *= sx; v.co.y *= sy; v.co.z = v.co.z * sz + zoff
    if bevel: bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=2, affect='EDGES')
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(None); return me
SLAT = cube_me('slat', SL[0], SL[1], SL[2], bevel=0.03)
INLAY = cube_me('inlay', SL[0] * 0.84, SL[1] * 0.2, 0.012, zoff=SL[2] * 0.6)
bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.012, major_segments=64, minor_segments=6)
_t = bpy.context.active_object; RING = _t.data; RING.materials.append(None); bpy.data.objects.remove(_t)
spark_me = bpy.data.meshes.new('spark'); bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=0, radius=1); bm.to_mesh(spark_me); bm.free()
spark_me.materials.append(M(SC.get('spark_color', '#fff6d8'), 1.0))

DET = SC.get('detail', {})
ball_P = []
for li, (hits, L) in enumerate(LANES):
    roff = L.get('radius_offset', 0.0); col = L['color']; light = L['light']
    times, zs, ss, P, nrm = build_ball(hits, roff)
    ball_P.append(P)
    TSF = np.arange(NF * 4 - 3) / (FPS * 4)
    PF = build_ball(hits, roff, TSF)[3]
    for k, h in enumerate(hits):
        p, tan, rad = spiral(ss[k], roff)
        n3 = Vector((tan[0] * nrm[k][0], tan[1] * nrm[k][0], nrm[k][1])).normalized()
        u3 = Vector((rad[0], rad[1], 0)).normalized()
        w3 = n3.cross(u3).normalized(); u3 = w3.cross(n3).normalized()
        mat = Matrix((u3, w3, n3)).transposed().to_4x4()
        ob = link(bpy.data.objects.new(f'g{li}_{k}', SLAT))
        ob.matrix_world = Matrix.Translation(Vector((p[0], p[1], zs[k])) - n3 * (R + 0.04)) @ mat
        if DET.get('inlay', True):
            inl = link(bpy.data.objects.new(f'gi{li}_{k}', INLAY)); inl.parent = ob
            inl.material_slots[0].link = 'OBJECT'; inl.material_slots[0].material = M(L.get('inlay', '#ffffff'), 1.0)
        dt_ = ts - h['t']
        if DET.get('ripples', True):
            rg = link(bpy.data.objects.new(f'rg{li}_{k}', RING))
            rg.matrix_world = Matrix.Translation(Vector((p[0], p[1], zs[k])) - n3 * (R - 0.02)) @ mat
            rg.material_slots[0].link = 'OBJECT'; rg.material_slots[0].material = M(light, 1.0)
            life = (dt_ >= 0) & (dt_ < 0.6)
            rs = np.where(life, 0.25 + 1.4 * np.sqrt(np.clip(dt_, 0, None) / 0.6), 0.0001)
            thin = np.where(life, 1 - dt_ / 0.6, 0.0001)
            set_curve(rg, 'scale', 0, rs); set_curve(rg, 'scale', 1, rs); set_curve(rg, 'scale', 2, np.maximum(thin, 0.0001))
        m = bpy.data.materials.new(f'gm{li}_{k}'); m.roughness = 0.05
        ob.material_slots[0].link = 'OBJECT'; ob.material_slots[0].material = m
        dim = hexl(light) * 0.35; lit = hexl(light)
        on = (dt_ >= 0).astype(float); fl = np.where(dt_ >= 0, np.exp(-dt_ * 8), 0)
        c = dim[None] * (1 - on[:, None]) + lit[None] * on[:, None]
        c = c * (1 - fl[:, None]) + np.ones(3)[None] * fl[:, None]
        for ch in range(3): set_curve(m, 'diffuse_color', ch, c[:, ch])
        wob = np.where((dt_ > 0) & (dt_ < 0.5), np.exp(-dt_ * 9) * np.sin(dt_ * 45) * 0.18, 0)
        base = ob.location.copy()
        for a in range(3): set_curve(ob, 'location', a, base[a] - n3[a] * wob)
        app = smooth01((dt_ + 1.3) / 0.35)          # slats appear just before they are needed
        for a in range(3): set_curve(ob, 'scale', a, np.maximum(app, 0.0001))
        nsp = L.get('sparks', 3); every = L.get('spark_every', 1)
        if nsp and k % every == 0:
            for q in range(nsp):
                d = Vector((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-0.2, 1))).normalized() * random.uniform(1.8, 4.2)
                sp = link(bpy.data.objects.new(f'sp{li}_{k}_{q}', spark_me))
                tt_ = np.clip(dt_, 0, None); life = (dt_ >= 0) & (dt_ < 0.45)
                sc = np.where(life, SC.get('spark_size', 0.028) * (1 - dt_ / 0.45), 0.0001)
                for a in range(3):
                    set_curve(sp, 'location', a, p[0] * (a == 0) + p[1] * (a == 1) + zs[k] * (a == 2) + d[a] * tt_ * np.exp(-tt_ * 4) - (a == 2) * 3 * tt_ * tt_)
                    set_curve(sp, 'scale', a, np.maximum(sc, 0.0001))
    # ball: squash & stretch, spin, ghost trail
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R, segments=40, ring_count=20)
    ball = bpy.context.active_object; ball.name = f'ball{li}'
    ball.data.materials.append(M(col, 0.15)); ball.data.materials.append(M('#ffffff', 0.15))
    for pg in ball.data.polygons:
        pg.material_index = int(((math.atan2(pg.center.z, pg.center.x) + math.pi) / (2 * math.pi)) * 8) % 2; pg.use_smooth = True
    for a in range(3): set_curve(ball, 'location', a, P[:, a])
    near = np.min(np.abs(ts[:, None] - times[None, :]), axis=1)
    sq = 1 - 0.32 * np.exp(-(near / 0.035) ** 2)
    set_curve(ball, 'scale', 2, sq); set_curve(ball, 'scale', 0, 1 / np.sqrt(sq)); set_curve(ball, 'scale', 1, 1 / np.sqrt(sq))
    sp_ = np.cumsum(np.linalg.norm(np.diff(P, axis=0, prepend=P[:1]), axis=1)) / R
    set_curve(ball, 'rotation_euler', 0, sp_ * 0.7); set_curve(ball, 'rotation_euler', 2, np.arctan2(P[:, 1], P[:, 0]))
    for j, (szf, lag) in enumerate([(0.8, 2), (0.62, 4), (0.46, 6), (0.32, 8), (0.2, 10)]):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=R * szf)
        gh = bpy.context.active_object; gh.data.materials.append(M(light, 1.0))
        Pl = np.vstack([np.repeat(P[:1], lag, 0), P[:-lag]])
        for a in range(3): set_curve(gh, 'location', a, Pl[:, a])
    # light thread that grows with the ball (+ optional helix strands)
    def thread(name, pts, depth, colhex):
        cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
        spl = cu.splines.new('POLY'); spl.points.add(len(pts) - 1)
        for f in range(len(pts)): spl.points[f].co = (pts[f, 0], pts[f, 1], pts[f, 2], 1)
        cu.bevel_depth = depth; cu.bevel_resolution = 2
        cu.bevel_factor_mapping_end = 'SPLINE'; cu.bevel_factor_mapping_start = 'SPLINE'
        cu.bevel_factor_start = max(times[0] * FPS - 2, 0) / (NF - 1)
        cu.materials.append(M(colhex, 1.0)); link(bpy.data.objects.new(name, cu))
        set_linear_0_1(cu, 'bevel_factor_end')
        return cu
    td = SC.get('thread_depth', 0.03)
    cu = thread(f'trail{li}', PF, td, light)
    fc2 = cu.animation_data.action.fcurve_ensure_for_datablock(cu, 'bevel_depth', index=0)
    bd = td + SC.get('thread_final_extra', 0.09) * smooth01((ts - EM) / 3)
    fc2.keyframe_points.add(NF)
    co = np.empty(2 * NF, np.float32); co[0::2] = np.arange(NF); co[1::2] = bd
    fc2.keyframe_points.foreach_set('co', co); fc2.update()
    if DET.get('helix', True):
        tg_ = np.gradient(PF, axis=0); tg_ /= np.linalg.norm(tg_, axis=1, keepdims=True) + 1e-9
        n1 = np.cross(tg_, np.array([0, 0, 1.0])); n1 /= np.linalg.norm(n1, axis=1, keepdims=True) + 1e-9
        n2 = np.cross(tg_, n1)
        dist_ = np.cumsum(np.linalg.norm(np.diff(PF, axis=0, prepend=PF[:1]), axis=1))
        for hx in range(2):
            ph = 2 * math.pi * dist_ / 1.6 + hx * math.pi
            H = PF + 0.085 * (np.cos(ph)[:, None] * n1 + np.sin(ph)[:, None] * n2)
            thread(f'helix{li}{hx}', H, 0.011, '#ffffff')

# ---------------- environment ----------------
world = bpy.data.worlds.new('w'); world.color = tuple(hexl(SC.get('world', '#05080f'))); scene.world = world
bm = bmesh.new()
for k in range(900):
    a = random.uniform(0, 2 * math.pi); rr = random.uniform(2, 45); z = random.uniform(-14, 22)
    bmesh.ops.create_icosphere(bm, subdivisions=0, radius=random.choice([0.03, 0.05, 0.08]), matrix=Matrix.Translation((rr * math.cos(a), rr * math.sin(a), z)))
me = bpy.data.meshes.new('dust'); bm.to_mesh(me); bm.free(); me.materials.append(M(SC.get('dust', '#8a6a3a'), 1.0)); link(bpy.data.objects.new('dust', me))
sv = SC.get('sparkle_voice')            # e.g. piano comping chords twinkle as tiny lights
if sv:
    spk = bpy.data.meshes.new('cspk'); bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1); bm.to_mesh(spk); bm.free()
    spk.materials.append(None)
    for k, e in enumerate([e for e in EV if e['voice'] == sv]):
        p, tan, rad = spiral(s_of(e['t']) + random.uniform(-0.5, 0.5), -0.95 + random.uniform(-0.3, 0.3))
        z = 0.6 + (e['midi'] - 60) * 0.18 + random.uniform(-0.2, 0.2)
        o = link(bpy.data.objects.new(f'cs{k}', spk)); o.location = (p[0], p[1], z)
        o.material_slots[0].link = 'OBJECT'; o.material_slots[0].material = M(random.choice(SC.get('sparkle_colors', ['#ffffff'])), 1.0)
        dt_ = ts - e['t']
        sc = np.where(dt_ < 0, 0.0001, 0.02 + 0.07 * np.exp(-np.clip(dt_, 0, None) * 5))
        for a in range(3): set_curve(o, 'scale', a, sc)
if SC.get('bokeh'):
    bm = bmesh.new()
    for k in range(160):
        a = random.uniform(0, 2 * math.pi); rr = random.uniform(120, 220); z = random.uniform(-20, 40)
        bmesh.ops.create_circle(bm, cap_ends=True, segments=24, radius=random.uniform(1.0, 3.0),
                                matrix=Matrix.Translation((rr * math.cos(a), rr * math.sin(a), z)) @ Matrix.Rotation(math.pi / 2, 4, 'X') @ Matrix.Rotation(-a, 4, 'Y'))
    me = bpy.data.meshes.new('bokeh'); bm.to_mesh(me); bm.free(); me.materials.append(M(SC['bokeh'], 1.0))
    link(bpy.data.objects.new('bokeh', me))

# ---------------- camera: chase, then rise to show the whole spiral ----------------
LENS = SC.get('lens', 30)
cd = bpy.data.cameras.new('cam'); cd.lens = LENS; cd.sensor_fit = 'VERTICAL'; cd.sensor_height = 36; cd.clip_end = 1500
cam = link(bpy.data.objects.new('cam', cd)); scene.camera = cam; cam.rotation_mode = 'XYZ'
mid = gs(np.mean(ball_P, axis=0), 6)
rad_dir = mid[:, :2] / np.linalg.norm(mid[:, :2], axis=1, keepdims=True)
tan_dir = np.stack([-rad_dir[:, 1], rad_dir[:, 0]], 1)
CPf = np.concatenate([mid[:, :2] + rad_dir * SC.get('cam_out', 12.5) - tan_dir * 5.0, (mid[:, 2] + 2.5)[:, None]], 1)
TGf = np.concatenate([mid[:, :2] + tan_dir * 1.5, (mid[:, 2] + 1.2)[:, None]], 1)
w = smooth01((ts - EM - 0.3) / 3.5)[:, None]
r_end = r0 + b * np.interp(s_of(EM), s_tab, th_tab)
top = np.array([0.0, -0.01, (2 * r_end + 6) / 0.5625 / 2 / math.tan(math.atan(18 / LENS))])
CP = gs(CPf * (1 - w) + top[None] * w, 4); TG = gs(TGf * (1 - w), 4)
rot = []
for n in range(NF):
    fwd = Vector(TG[n]) - Vector(CP[n]); rot.append(tuple(fwd.to_track_quat('-Z', 'Y').to_euler()))
rot = np.unwrap(np.array(rot), axis=0)
for a in range(3): set_curve(cam, 'location', a, CP[:, a]); set_curve(cam, 'rotation_euler', a, rot[:, a])

res = SC.get('render_resolution', [1440, 2560])
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x, scene.render.resolution_y = res
scene.display.render_aa = 'FXAA'
sh = scene.display.shading
sh.light = 'STUDIO'; sh.studio_light = 'outdoor.sl'; sh.color_type = 'MATERIAL'
sh.show_shadows = False; sh.show_cavity = False; sh.show_specular_highlight = True
scene.view_settings.view_transform = 'Standard'; scene.view_settings.exposure = SC.get('exposure', 0.3)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print('BUILT', NF, 'frames;', ', '.join(f'lane{i}: {len(h)} hits' for i, (h, _) in enumerate(LANES)))
