#!/usr/bin/env bash
# One-shot build: render frames -> synthesize audio -> mux into out/nebula_strike_cinematic.mp4
set -euo pipefail
cd "$(dirname "$0")"
[ -d node_modules ] || npm install
node render.js
python3 audio.py
ffmpeg -y -loglevel error -i out/video_silent.mp4 -i out/audio.wav -c:v copy -c:a aac -b:a 192k -shortest out/nebula_strike_cinematic.mp4
echo "done: out/nebula_strike_cinematic.mp4"
