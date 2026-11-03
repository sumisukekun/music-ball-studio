import bpy
s=bpy.context.scene; sh=s.display.shading
print('LIGHTS',[l.name for l in bpy.context.preferences.studio_lights if l.type=='STUDIO'])
sh.use_world_space_lighting=False
bpy.data.materials['floor'].diffuse_color=(1,1,1,1)
s.render.resolution_percentage=40
for name in [l.name for l in bpy.context.preferences.studio_lights if l.type=='STUDIO']:
    sh.studio_light=name
    for f,cam in [(120,'camA'),(440,'camC'),(640,'camD')]:
        s.camera=bpy.data.objects[cam]; s.frame_set(f)
        s.render.filepath=f'/home/claude/domino/test/L_{name}_{f}.png'; bpy.ops.render.render(write_still=True)
