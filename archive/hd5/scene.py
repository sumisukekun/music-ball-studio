import bpy, math, json, random
import numpy as np
from mathutils import Vector, Matrix
import bmesh

A = json.load(open('/home/claude/hd5/arr.json'))
FPS = 30; END = A['END']; NF = int(END * FPS) + 1
ts = np.arange(NF) / FPS
random.seed(8); np.random.seed(8)
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

EV = A['events']; EM = A['end_music']
G = 40.0; R = 0.28
# ---------------- path: arc length follows the beat (4 units per quarter) ----------------
bass_t = [e['t'] for e in EV if e['voice'] == 'bass']
bt = np.array(sorted(set(round(t, 4) for t in bass_t)))
bs = 4.0 * np.arange(len(bt))
def s_of(t):
    if t <= bt[-1]: return float(np.interp(t, bt, bs, left=bs[0] - (bt[0] - t) * 3.0))
    return float(bs[-1] + (t - bt[-1]) * 3.0)
r0 = 7.0; b = 4.6 / (2 * math.pi)
th_tab = np.linspace(0, 40 * math.pi, 40000)
r_tab = r0 + b * th_tab
s_tab = np.concatenate([[0], np.cumsum(np.hypot(np.diff(r_tab * np.cos(th_tab)), np.diff(r_tab * np.sin(th_tab))))])
def spiral(s, roff=0.0):
    th = np.interp(s, s_tab, th_tab); r = r0 + b * th + roff
    p = np.array([r * math.cos(th), r * math.sin(th)])
    tan = np.array([-math.sin(th), math.cos(th)]); rad = np.array([math.cos(th), math.sin(th)])
    return p, tan, rad

# ---------------- hit lists ----------------
def lanes():
    mel = [e for e in EV if e['voice'] in ('mel', 'coda')]
    acc = [e for e in EV if e['voice'] in ('bass', 'chord')]
    def group(es, zf):
        out = []
        for e in es:
            if out and e['t'] - out[-1]['t'] < 0.07:
                out[-1]['midis'].append(e['midi']); continue
            out.append(dict(t=e['t'], midis=[e['midi']], voice=e['voice']))
        for o in out: o['z'] = zf(o)
        return out
    m = group(mel, lambda o: 4.2 + (max(o['midis']) - 69) * 0.27 if o['voice'] != 'coda' else 7.5)
    a = group(acc, lambda o: -3.6 + (min(o['midis']) - 38) * 0.08 if o['voice'] == 'bass' else -1.2 + (min(o['midis']) - 57) * 0.06)
    return m, a
MEL, ACC = lanes()
LANES = [(MEL, 0.0, '#ffcf4a', '#fff1b8'), (ACC, -1.9, '#ff4d6d', '#ffc2cf')]

def build_ball(hits, roff):
    times = np.array([h['t'] for h in hits]); zs = np.array([h['z'] for h in hits]); ss = np.array([s_of(t) for t in times])
    # entrance: drop in from above before the first hit
    P = np.zeros((NF, 3)); vin = []; vout = []
    for k in range(len(hits) - 1):
        T = times[k + 1] - times[k]
        vs = (ss[k + 1] - ss[k]) / T; vz = ((zs[k + 1] - zs[k]) + 0.5 * G * T * T) / T
        vout.append((vs, vz)); vin.append((vs, vz - G * T))
    for f, t in enumerate(ts):
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

ball_P = []
glass_me = None
def slat_me():
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts: v.co.x *= 1.15; v.co.y *= 0.34; v.co.z *= 0.07
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.03, segments=2, affect='EDGES')
    me = bpy.data.meshes.new('slat'); bm.to_mesh(me); bm.free(); me.materials.append(None); return me
SLAT = slat_me()
spark_me = bpy.data.meshes.new('spark'); bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=0, radius=1); bm.to_mesh(spark_me); bm.free()
spark_me.materials.append(M('#fff6d8', 1.0))

for li, (hits, roff, col, light) in enumerate(LANES):
    times, zs, ss, P, nrm = build_ball(hits, roff)
    ball_P.append(P)
    for k, h in enumerate(hits):
        p, tan, rad = spiral(ss[k], roff)
        n3 = Vector((tan[0] * nrm[k][0], tan[1] * nrm[k][0], nrm[k][1])).normalized()
        u3 = Vector((rad[0], rad[1], 0)).normalized()
        w3 = n3.cross(u3).normalized(); u3 = w3.cross(n3).normalized()
        mat = Matrix((u3, w3, n3)).transposed().to_4x4()
        ob = link(bpy.data.objects.new(f'g{li}_{k}', SLAT))
        ob.matrix_world = Matrix.Translation(Vector((p[0], p[1], zs[k])) - n3 * (R + 0.04)) @ mat
        rot = ob.rotation_euler.copy()
        m = bpy.data.materials.new(f'gm{li}_{k}'); m.roughness = 0.05
        ob.material_slots[0].link = 'OBJECT'; ob.material_slots[0].material = m
        dt_ = ts - h['t']
        dim = hexl(light) * 0.35; lit = hexl(light)
        on = (dt_ >= 0).astype(float); fl = np.where(dt_ >= 0, np.exp(-dt_ * 8), 0)
        c = dim[None] * (1 - on[:, None]) + lit[None] * on[:, None]
        c = c * (1 - fl[:, None]) + np.ones(3)[None] * fl[:, None]
        for ch in range(3): set_curve(m, 'diffuse_color', ch, c[:, ch])
        wob = np.where((dt_ > 0) & (dt_ < 0.5), np.exp(-dt_ * 9) * np.sin(dt_ * 45) * 0.18, 0)
        base = ob.location.copy()
        for a in range(3): set_curve(ob, 'location', a, base[a] - n3[a] * wob)
        app = smooth01((dt_ + 1.3) / 0.35)
        for a in range(3): set_curve(ob, 'scale', a, np.maximum(app, 0.0001))
        # sparks
        if li == 0 or k % 3 == 0:
            for q in range(5 if li == 0 else 2):
                d = Vector((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-0.2, 1))).normalized() * random.uniform(2.5, 5)
                sp = link(bpy.data.objects.new(f'sp{li}_{k}_{q}', spark_me))
                tt_ = np.clip(dt_, 0, None); life = (dt_ >= 0) & (dt_ < 0.45)
                sc = np.where(life, 0.07 * (1 - dt_ / 0.45), 0.0001)
                for a in range(3):
                    set_curve(sp, 'location', a, p[0] * (a == 0) + p[1] * (a == 1) + zs[k] * (a == 2) + d[a] * tt_ * np.exp(-tt_ * 4) - (a == 2) * 3 * tt_ * tt_)
                    set_curve(sp, 'scale', a, np.maximum(sc, 0.0001))
    # the ball with squash & stretch and spin
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
    # ghost trail
    for j, (szf, lag) in enumerate([(0.8, 2), (0.62, 4), (0.46, 6), (0.32, 8), (0.2, 10)]):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=R * szf)
        gh = bpy.context.active_object; gh.data.materials.append(M(light, 1.0))
        Pl = np.vstack([np.repeat(P[:1], lag, 0), P[:-lag]])
        for a in range(3): set_curve(gh, 'location', a, Pl[:, a])
    # light thread (curve that grows with the ball)
    cu = bpy.data.curves.new(f'trail{li}', 'CURVE'); cu.dimensions = '3D'
    spl = cu.splines.new('POLY'); spl.points.add(NF - 1)
    for f in range(NF): spl.points[f].co = (P[f, 0], P[f, 1], P[f, 2], 1)
    cu.bevel_depth = 0.045; cu.bevel_resolution = 2
    cu.bevel_factor_mapping_end = 'SPLINE'
    tr = link(bpy.data.objects.new(f'trail{li}', cu)); cu.materials.append(M(light, 1.0))
    set_curve(cu, 'bevel_factor_end', 0, np.maximum(np.arange(NF) / (NF - 1), 0.0005), interp=1) if False else None
    fc_vals = np.maximum((np.arange(NF) - 1) / (NF - 1), 0.0)
    ensure_action(cu)
    fc = cu.animation_data.action.fcurve_ensure_for_datablock(cu, 'bevel_factor_end', index=0)
    fc.keyframe_points.add(2)
    fc.keyframe_points.foreach_set('co', np.array([0, 0.0, NF - 1, 1.0], np.float32))
    fc.keyframe_points.foreach_set('interpolation', np.array([1, 1], np.int32)); fc.update()
    cu.bevel_factor_mapping_start = 'SPLINE'
    cu.bevel_factor_start = max(times[0] * FPS - 2, 0) / (NF - 1)
    fc2 = cu.animation_data.action.fcurve_ensure_for_datablock(cu, 'bevel_depth', index=0)
    bd = 0.045 + 0.11 * smooth01((ts - EM) / 3)
    fc2.keyframe_points.add(NF)
    co = np.empty(2 * NF, np.float32); co[0::2] = np.arange(NF); co[1::2] = bd
    fc2.keyframe_points.foreach_set('co', co); fc2.update()

# ---------------- environment ----------------
world = bpy.data.worlds.new('w'); world.color = tuple(hexl('#0b0614')); scene.world = world
bm = bmesh.new()
for k in range(900):
    a = random.uniform(0, 2 * math.pi); rr = random.uniform(2, 45); z = random.uniform(-14, 22)
    bmesh.ops.create_icosphere(bm, subdivisions=0, radius=random.choice([0.03, 0.05, 0.08]), matrix=Matrix.Translation((rr * math.cos(a), rr * math.sin(a), z)))
me = bpy.data.meshes.new('dust'); bm.to_mesh(me); bm.free(); me.materials.append(M('#c9a24a', 1.0)); link(bpy.data.objects.new('dust', me))
# a faint folk-rosette under the stage


# ---------------- camera ----------------
cd = bpy.data.cameras.new('cam'); cd.lens = 30; cd.sensor_fit = 'VERTICAL'; cd.sensor_height = 36; cd.clip_end = 1500
cam = link(bpy.data.objects.new('cam', cd)); scene.camera = cam; cam.rotation_mode = 'XYZ'
mid = (ball_P[0] + ball_P[1]) / 2
def gs(a, sg):
    r = int(3 * sg); k = np.exp(-0.5 * (np.arange(-r, r + 1) / sg) ** 2); k /= k.sum()
    if a.ndim == 1: return np.convolve(np.pad(a, r, mode='edge'), k, 'valid')
    return np.stack([gs(a[:, j], sg) for j in range(a.shape[1])], 1)
mid = gs(mid, 6)
rad_dir = mid[:, :2] / np.linalg.norm(mid[:, :2], axis=1, keepdims=True)
tan_dir = np.stack([-rad_dir[:, 1], rad_dir[:, 0]], 1)
CPf = np.concatenate([mid[:, :2] + rad_dir * 12.5 - tan_dir * 5.0, (mid[:, 2] + 2.5)[:, None]], 1)
TGf = np.concatenate([mid[:, :2] + tan_dir * 1.5, (mid[:, 2] + 1.2)[:, None]], 1)
w = smooth01((ts - EM - 0.3) / 3.5)[:, None]
r_end = r0 + b * np.interp(s_of(EM), s_tab, th_tab)
top = np.array([0.0, -0.01, (2 * r_end + 6) / 0.5625 / 2 / math.tan(math.atan(18 / 30))])
CP = CPf * (1 - w) + top[None] * w
TG = TGf * (1 - w) + np.array([0.0, 0.0, 0.0])[None] * w
CP, TG = gs(CP, 4), gs(TG, 4)
rot = []
for n in range(NF):
    fwd = Vector(TG[n]) - Vector(CP[n]); rot.append(tuple(fwd.to_track_quat('-Z', 'Y').to_euler()))
rot = np.unwrap(np.array(rot), axis=0)
for a in range(3): set_curve(cam, 'location', a, CP[:, a]); set_curve(cam, 'rotation_euler', a, rot[:, a])

scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
scene.display.render_aa = 'FXAA'
sh = scene.display.shading
sh.light = 'STUDIO'; sh.studio_light = 'outdoor.sl'; sh.color_type = 'MATERIAL'
sh.show_shadows = False; sh.show_cavity = False; sh.show_specular_highlight = True
scene.view_settings.view_transform = 'Standard'; scene.view_settings.exposure = 0.3
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/hd5/hd5.blend')
print('BUILT', NF, 'mel hits', len(MEL), 'acc hits', len(ACC), 'r_end', round(r_end, 1))
