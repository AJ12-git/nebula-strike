#!/usr/bin/env bash
# animate the illustration -> synthesize looping music -> 12s seamless loop + 24s (two loops) version
set -euo pipefail
cd "$(dirname "$0")"
python3 animate.py
python3 audio.py
ffmpeg -y -loglevel error -i out/video_silent.mp4 -i out/audio_loop.wav -c:v copy -c:a aac -b:a 192k -shortest out/living_loop_12s.mp4
ffmpeg -y -loglevel error -stream_loop 1 -i out/video_silent.mp4 -stream_loop 1 -i out/audio_loop.wav -c:v copy -c:a aac -b:a 192k -t 24 out/living_illustration.mp4
echo "done: out/living_loop_12s.mp4, out/living_illustration.mp4"
