import bpy, sys
s = bpy.context.scene
for spec in sys.argv[sys.argv.index('--')+1:]:
    f = int(spec); s.frame_set(f)
    s.render.filepath = f'/home/claude/pyta/test/f{f:03d}.png'; bpy.ops.render.render(write_still=True)
