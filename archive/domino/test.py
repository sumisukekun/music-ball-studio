import bpy, sys, time
s = bpy.context.scene
for spec in sys.argv[sys.argv.index('--')+1:]:
    f = int(spec)
    cam = 'camA' if f < 422 else ('camC' if f < 506 else 'camD')
    s.camera = bpy.data.objects[cam]
    s.frame_set(f)
    s.render.filepath = f'/home/claude/domino/test/f{f:03d}.png'
    t=time.time(); bpy.ops.render.render(write_still=True); print('FRAME', f, round(time.time()-t,1), flush=True)
