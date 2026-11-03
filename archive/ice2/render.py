import bpy, sys
a = sys.argv[sys.argv.index('--')+1:]
cam, f0, f1, out = a[0], int(a[1]), int(a[2]), a[3]
s = bpy.context.scene
s.camera = bpy.data.objects[cam]
s.frame_start, s.frame_end = f0, f1
im = s.render.image_settings
try: im.media_type = 'VIDEO'
except Exception as e: print('no media_type', e)
im.file_format = 'FFMPEG'
s.render.ffmpeg.format = 'MPEG4'
s.render.ffmpeg.codec = 'H264'
s.render.ffmpeg.constant_rate_factor = 'PERC_LOSSLESS'
s.render.ffmpeg.ffmpeg_preset = 'GOOD'
s.render.filepath = out
bpy.ops.render.render(animation=True)
print('DONE', out)
