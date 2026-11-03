import bpy
s=bpy.context.scene
for ex in (0.4, 0.7):
    s.view_settings.exposure=ex
    for f in (190,452):
        s.frame_set(f); s.render.filepath=f'/home/claude/pyta/test/e{ex}_{f}.png'; bpy.ops.render.render(write_still=True)
