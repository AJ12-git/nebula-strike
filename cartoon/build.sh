#!/usr/bin/env bash
# render frames -> synthesize audio -> mux into out/cheese_heist.mp4
set -euo pipefail
cd "$(dirname "$0")"
[ -d node_modules ] || npm install
node render.js --fps 24
python3 audio.py
ffmpeg -y -loglevel error -i out/video_silent.mp4 -i out/audio.wav -c:v copy -c:a aac -b:a 192k -shortest out/cheese_heist.mp4
echo "done: out/cheese_heist.mp4"
