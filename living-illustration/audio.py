"""Gentle, seamlessly looping soundtrack (12 s) -> out/audio_loop.wav.

Everything is written into a circular buffer (indices wrap modulo the loop length),
so note tails at the end spill over into the beginning and the loop has no seam.
"""
import wave
from pathlib import Path

import numpy as np

SR = 44100
LOOP = 12.0
N = int(SR * LOOP)
BEAT = LOOP / 16            # 80 BPM, 16 beats
OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(5)
buf = np.zeros((N, 2))

NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def hz(name):
    return 440.0 * 2 ** ((12 * (int(name[-1]) + 1) + NOTE[name[:-1]] - 69) / 12)


def tt(d):
    return np.arange(int(d * SR)) / SR


def lp(x, fc):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X / (1 + (f / fc) ** 4), len(x))


def add(sig, t0, g=1.0, pan=0.0):
    i0 = int(round(t0 * SR)) % N
    idx = (i0 + np.arange(len(sig))) % N
    np.add.at(buf[:, 0], idx, sig * g * np.sqrt((1 - pan) / 2))
    np.add.at(buf[:, 1], idx, sig * g * np.sqrt((1 + pan) / 2))


def piano(f, d=3.0):
    t = tt(d)
    s = sum(np.sin(2 * np.pi * f * h * t * (1 + 0.0004 * h)) / h ** 1.6 * np.exp(-t * (1.2 + 0.9 * h)) for h in range(1, 7))
    return s * np.minimum(1, t * 120)


def musicbox(f, d=2.0):
    t = tt(d)
    return (np.sin(2 * np.pi * f * t) * np.exp(-t * 2.6) + 0.25 * np.sin(2 * np.pi * f * 3.0 * t) * np.exp(-t * 7)) * np.minimum(1, t * 800)


def pad(fs, d):
    t = tt(d)
    s = sum(np.sin(2 * np.pi * f * t + np.sin(2 * np.pi * 0.3 * t) * 0.4) + 0.4 * np.sin(2 * np.pi * f * 2.003 * t) for f in fs) / len(fs)
    return s * np.minimum(1, t / 1.0) * np.minimum(1, (d - t) / 1.0)


def chirp(f0, f1, d):
    t = tt(d)
    f = f0 + (f1 - f0) * (t / d) ** 0.7
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / d) ** 2


CHORDS = [  # each 4 beats = 3 s
    ["F3", "A3", "C4", "E4"],
    ["E3", "G3", "B3", "D4"],
    ["D3", "F3", "A3", "C4"],
    ["C3", "E3", "G3", "B3"],
]
BASS = ["F2", "E2", "D2", "C2"]
for i, ch in enumerate(CHORDS):
    t0 = i * 4 * BEAT
    add(piano(hz(BASS[i]), 3.5), t0, 0.35)
    for k, n in enumerate(ch):                       # gently rolled chord
        add(piano(hz(n), 3.2), t0 + 0.04 * k, 0.16, -0.3 + 0.2 * k)
    add(piano(hz(ch[2]), 2.0), t0 + 2 * BEAT, 0.09, 0.2)
    add(piano(hz(ch[3]), 2.0), t0 + 2.5 * BEAT, 0.07, 0.3)
    add(pad([hz(n) for n in ch], 3.4), t0 - 0.2, 0.05)

# sparse music-box melody
MEL = [(0, "C6"), (1.5, "A5"), (2, "G5"), (3, "E5"), (4, "D6"), (5.5, "B5"), (6, "G5"),
       (8, "C6"), (9, "A5"), (9.5, "F5"), (11, "E5"), (12, "G5"), (13, "E5"), (14, "D5"), (14.5, "E5")]
for b, n in MEL:
    add(musicbox(hz(n)), b * BEAT, 0.12, 0.35)

# breeze (filtered noise swelling with the leaves) and a few birds
t = np.arange(N) / SR
breeze = lp(rng.standard_normal(N), 700) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 6)) * 2.0
buf[:, 0] += breeze * 0.025
buf[:, 1] += np.roll(breeze, SR // 3) * 0.025
for t0, f0, f1, pan in [(1.1, 3200, 4200, 0.6), (1.25, 3600, 4400, 0.6), (5.7, 2800, 3900, -0.5), (5.82, 3100, 4100, -0.5), (5.95, 3300, 4300, -0.5), (9.4, 3500, 2700, 0.4)]:
    add(chirp(f0, f1, 0.09), t0, 0.04, pan)

out = np.tanh(buf * 1.4)
out *= 0.85 / np.max(np.abs(out))
with wave.open(str(OUT / "audio_loop.wav"), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((out * 32767).astype(np.int16).tobytes())
print("wrote", OUT / "audio_loop.wav")
