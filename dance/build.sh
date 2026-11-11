#!/usr/bin/env bash
# render frames -> synthesize music -> mux into out/dance.mp4
set -euo pipefail
cd "$(dirname "$0")"
[ -d node_modules ] || npm install
node render.js --fps 24
python3 audio.py
ffmpeg -y -loglevel error -i out/video_silent.mp4 -i out/audio.wav -c:v copy -c:a aac -b:a 192k -shortest out/dance.mp4
echo "done: out/dance.mp4"
