import bpy
s=bpy.context.scene; sh=s.display.shading
for mode in ('STUDIO','FLAT'):
    sh.light=mode
    for f in (1100,2350):
        s.frame_set(f); s.render.filepath=f'/home/claude/clair/test/L{mode}_{f}.png'; bpy.ops.render.render(write_still=True)
