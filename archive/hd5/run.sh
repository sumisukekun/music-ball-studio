cd /home/claude/hd5
r(){ ../bvenv/bin/python -c "import bpy,sys; bpy.ops.wm.open_mainfile(filepath='hd5.blend'); sys.argv=['x','--','cam','$1','$2','/home/claude/hd5/tmp_$3.mp4']; exec(open('render.py').read())" > log_$3.txt 2>&1 && mv tmp_$3.mp4 part_$3.mp4 && echo "OK $3"; }
r 0 1118 1
r 1119 2237 2
