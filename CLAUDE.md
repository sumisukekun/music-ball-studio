# Project rules (music-ball-studio)

- Music: public domain (composer died 70+ years ago) or original only. Always render our own performance. Never copyrighted characters, songs or designs (e.g. Disney).
- Videos: 1080x1920, 30 fps, length >= 61 s (TikTok Creator Rewards / Shorts monetization).
- New video = new `songs/<name>.py` + `configs/<name>.json`, built with `studio/make.py`. Check `--steps ...,preview` frames before a full render.
- Engine changes go into `studio/` with backward-compatible config defaults so old configs still build.
- Posting/publishing or anything hard to undo: stop and ask the user first, even when running unattended.
- Keep a short progress note (done / next) at each milestone so work can resume after interruptions.
- Talk to the user in Japanese.
- Local: bpy Python is `MBS_BPY_PYTHON`, samples in `MBS_SAMPLES` (or ./samples via scripts/fetch_samples.sh).
