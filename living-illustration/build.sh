#!/usr/bin/env bash
# animate the illustration -> synthesize looping music -> 12s seamless loop + 24s (two loops) version
set -euo pipefail
cd "$(dirname "$0")"
python3 mask.py
python3 animate.py
python3 audio.py
ffmpeg -y -loglevel error -i out/video_silent.mp4 -i out/audio_loop.wav -vf scale=960:1920:flags=lanczos -c:v libx264 -profile:v high -level:v 4.1 -pix_fmt yuv420p -crf 18 -preset slow -c:a aac -b:a 192k -shortest -movflags +faststart out/living_loop_12s.mp4
ffmpeg -y -loglevel error -stream_loop 1 -i out/video_silent.mp4 -stream_loop 1 -i out/audio_loop.wav -vf scale=960:1920:flags=lanczos -c:v libx264 -profile:v high -level:v 4.1 -pix_fmt yuv420p -crf 18 -preset slow -c:a aac -b:a 192k -t 24 -movflags +faststart out/living_illustration.mp4
echo "done: out/living_loop_12s.mp4, out/living_illustration.mp4"
