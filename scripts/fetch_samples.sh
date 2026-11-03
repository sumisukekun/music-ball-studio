#!/usr/bin/env bash
# Salamander Grand Piano V3 samples (CC-BY 3.0 / public use) -> ./samples
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=${MBS_SAMPLES:-samples}; mkdir -p "$DEST"
if ls "$DEST"/*.wav >/dev/null 2>&1; then echo "samples already in $DEST"; exit 0; fi
TMP=$(mktemp -d)
git clone --depth 1 --filter=blob:none --sparse https://github.com/educandu/abcjs-soundfonts "$TMP/sf"
cd "$TMP/sf"
P=SalamanderGrandPianoV3_44.1khz16bit
pats=()
for n in C 'D#' 'F#' A; do for o in 1 2 3 4 5 6; do for v in 6 9 12; do pats+=("$P/**/${n}${o}v${v}.wav"); done; done; done
git sparse-checkout set --no-cone "${pats[@]}"
cd - >/dev/null
find "$TMP/sf" -name '*.wav' -exec cp {} "$DEST"/ \;
rm -rf "$TMP"; echo "$(ls "$DEST" | wc -l) samples -> $DEST"
