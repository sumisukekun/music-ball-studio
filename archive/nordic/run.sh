cd /home/claude/nordic
r(){ ../bvenv/bin/python -c "import bpy,sys; bpy.ops.wm.open_mainfile(filepath='nordic.blend'); sys.argv=['x','--','cam','$1','$2','/home/claude/nordic/tmp_$3.mp4']; exec(open('render.py').read())" > log_$3.txt 2>&1 && mv tmp_$3.mp4 part_$3.mp4 && echo "OK $3"; }
r 0 1240 1
r 1241 2482 2
