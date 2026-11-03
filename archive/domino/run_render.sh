set -e
cd /home/claude/domino
r(){ ../bvenv/bin/python -c "import bpy,sys; bpy.ops.wm.open_mainfile(filepath='domino.blend'); sys.argv=['x','--','$1','$2','$3','/home/claude/domino/tmp_$4.mp4']; exec(open('render.py').read())" > log_$4.txt 2>&1 && mv tmp_$4.mp4 scene_$4.mp4 && echo "OK $4"; }
r camC 422 505 C
r camA 0 421 AB
r camD 506 705 D
