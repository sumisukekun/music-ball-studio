import bpy, sys
s = bpy.context.scene
for spec in sys.argv[sys.argv.index('--')+1:]:
    f = int(spec); s.frame_set(f)
    s.render.filepath = '/home/claude/jazz/test/%s_%04d.png' % (TAG, f); bpy.ops.render.render(write_still=True)
