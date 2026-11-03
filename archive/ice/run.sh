cd /home/claude/ice
r(){ ../bvenv/bin/python -c "import bpy,sys; bpy.ops.wm.open_mainfile(filepath='ice.blend'); sys.argv=['x','--','cam','$1','$2','/home/claude/ice/tmp_$3.mp4']; exec(open('render.py').read())" > log_$3.txt 2>&1 && mv tmp_$3.mp4 part_$3.mp4 && echo "OK $3"; }
r 0 1326 1
r 1327 2652 2
