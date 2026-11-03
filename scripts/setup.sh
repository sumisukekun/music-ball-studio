#!/usr/bin/env bash
# Local / CI setup: ffmpeg, lilypond, python venv with bpy
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v apt-get >/dev/null; then sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg lilypond fonts-dejavu-core libxi6 libxkbcommon0 libsm6 libgl1 libegl1 libgl1-mesa-dri >/dev/null; fi
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q bpy numpy scipy mido
echo "ok: use  MBS_BPY_PYTHON=.venv/bin/python .venv/bin/python studio/make.py configs/<name>.json"
