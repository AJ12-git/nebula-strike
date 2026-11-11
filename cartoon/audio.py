"""Cartoon score + sound effects for the cat-and-mouse short -> out/audio.wav.

Everything is synthesized with numpy and timed to the story in index.html:
sneaky pizzicato, snoring, slide whistles, a galop for the chase, BONK,
a music-box ending and a final flourish.
"""
import wave
from pathlib import Path

import numpy as np

SR = 44100
DUR = 30.0
N = int(SR * DUR)
OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(2026)
mix = np.zeros((N, 2))


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def nm(s):  # "C4", "D#3", "Bb2"
    s = s.replace("Bb", "A#").replace("Eb", "D#").replace("Ab", "G#")
    return 12 * (int(s[-1]) + 1) + NOTE[s[:-1]]


def add(sig, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= N or i + len(sig) <= 0:
        return
    if i < 0:
        sig, i = sig[-i:], 0
    sig = sig[: N - i]
    mix[i:i + len(sig), 0] += sig * gain * np.sqrt((1 - pan) / 2)
    mix[i:i + len(sig), 1] += sig * gain * np.sqrt((1 + pan) / 2)


def tt(d):
    return np.arange(int(d * SR)) / SR


def lp(x, fc):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X / (1 + (f / fc) ** 4), len(x))


def hp(x, fc):
    return x - lp(x, fc)


# ---------------- instruments ----------------
def pizz(f, d=0.35):
    t = tt(d)
    s = sum(np.sin(2 * np.pi * f * h * t) / h * np.exp(-t * (9 + 5 * h)) for h in range(1, 6))
    return s * np.minimum(1, t * 600)


def xylo(f, d=0.3):
    t = tt(d)
    return (np.sin(2 * np.pi * f * t) * np.exp(-t * 14) + 0.35 * np.sin(2 * np.pi * f * 3.93 * t) * np.exp(-t * 40)) * np.minimum(1, t * 900)


def glock(f, d=1.2):
    t = tt(d)
    return (np.sin(2 * np.pi * f * t) * np.exp(-t * 3.5) + 0.3 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 8) + 0.12 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 14)) * np.minimum(1, t * 900)


def tuba(f, d=0.22):
    t = tt(d)
    ph = (f * t) % 1
    s = lp(2 * ph - 1, 500)
    return s * np.minimum(1, t * 120) * np.exp(-t * 8)


def saw_chord(fs, d, attack=0.01, decay=3.0):
    t = tt(d)
    s = sum(lp(2 * ((f * t) % 1) - 1, 2500) for f in fs) / len(fs)
    return s * np.minimum(1, t / attack) * np.exp(-t * decay)


def glide(f0, f1, d, vib=0.0, shape="exp", wave="sine"):
    t = tt(d)
    f = f0 * (f1 / f0) ** (t / d) if shape == "exp" else f0 + (f1 - f0) * t / d
    f = f * (1 + vib * np.sin(2 * np.pi * 6.5 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) if wave == "sine" else np.tanh(np.sin(ph) * 2.5)
    return s * np.minimum(1, t * 60) * np.minimum(1, (d - t) * 30)


def noise(d, lo=None, hi=None):
    x = rng.standard_normal(int(d * SR))
    if hi:
        x = lp(x, hi)
    if lo:
        x = hp(x, lo)
    return x


def env_exp(d, k):
    return np.exp(-tt(d) * k)


def woodblock(f=900, d=0.12):
    t = tt(d)
    return (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.3 * t)) * np.exp(-t * 45)


def thud(d=0.5, f0=110, f1=40):
    return glide(f0, f1, d) * env_exp(d, 8) * 1.3 + lp(noise(d), 300) * env_exp(d, 14) * 2


# ---------------- music ----------------
# 0-3.5: sneaky intro, low pizzicato in C minor
for i, n in enumerate(["C3", "G2", "C3", "Eb3", "D3", "G2", "B2", "D3"]):
    add(pizz(mtof(nm(n))), 0.6 + i * 0.36, 0.35)

# 3.5-9: tiptoe theme on the mouse's steps (one note per stride, freeze 6.0-6.8)
sneak = ["C3", "G3", "Eb3", "G3", "D3", "G3", "B2", "G3", "C3", "Ab3", "Eb3", "Ab3", "G2", "G3", "B2", "D3"]
k = 0
for st in np.arange(3.5, 9.0, 0.25):
    if 5.95 < st < 6.8:
        continue
    n = sneak[k % len(sneak)]
    add(pizz(mtof(nm(n)), 0.3), st, 0.4 if k % 2 == 0 else 0.28, -0.2 if k % 2 else 0.2)
    k += 1
# freeze: a held, nervous string tremolo
t = tt(0.8)
trem = np.sin(2 * np.pi * mtof(nm("F#4")) * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 14 * t)) * np.minimum(1, t * 20) * np.minimum(1, (0.8 - t) * 20)
add(trem, 6.0, 0.12)
# climb: rising pizz scale
for i, st in enumerate(np.arange(9.0, 10.55, 0.13)):
    add(pizz(mtof(nm("C3") + [0, 2, 3, 5, 7, 8, 10, 12, 14, 15, 17, 19, 20][i % 13])), st, 0.5)
# 11.9 found the cheese: glockenspiel ta-da
for i, n in enumerate(["C5", "E5", "G5", "C6"]):
    add(glock(mtof(nm(n))), 11.9 + i * 0.09, 0.32)
add(glide(500, 900, 0.18), 12.3, 0.12)  # little hop of joy
# 12.6 ear twitch, 13.0 alarm stab, 13.3 eek
add(woodblock(2200, 0.06), 12.62, 0.25)
add(woodblock(2400, 0.06), 12.72, 0.2)
add(saw_chord([mtof(nm(n)) for n in ["C4", "F#4", "A#4", "D#5"]], 0.7, decay=4), 13.0, 0.35)
add(glide(2000, 2700, 0.25, vib=0.04), 13.3, 0.13)
# 13.45 leap: slide whistle up and over
add(np.concatenate([glide(400, 1300, 0.38, vib=0.01), glide(1300, 700, 0.37, vib=0.01)]), 13.45, 0.16)
# 14.2 CRASH: plate shatters
add(thud(0.4, 140, 50), 14.2, 0.5)
add(hp(noise(0.5), 2500) * env_exp(0.5, 9), 14.2, 0.25)
for i in range(9):
    add(np.sin(2 * np.pi * rng.uniform(2500, 5200) * tt(0.25)) * env_exp(0.25, 18), 14.22 + rng.uniform(0, 0.4), 0.12, rng.uniform(-0.6, 0.6))

# 14.05-21.1: chase galop (beat = 0.3s); stops dead on the BONK
BEAT = 0.3
bars = [
    (["C2", "G2"], ["G4", "E4", "G4", "E4", "G4", "C5", "G4", "E4"]),
    (["F2", "C3"], ["A4", "F4", "A4", "F4", "A4", "C5", "A4", "F4"]),
    (["G2", "D3"], ["B4", "G4", "B4", "D5", "F5", "D5", "B4", "G4"]),
    (["C2", "G2"], ["C5", "E5", "G5", "E5", "C5", "G4", "C5", None]),
]
start, end = 14.05, 21.1
b = 0
while True:
    t0 = start + b * 4 * BEAT
    if t0 >= end:
        break
    bass, mel = bars[b % 4]
    for beat in range(4):
        tb = t0 + beat * BEAT
        if tb < end:
            add(tuba(mtof(nm(bass[beat % 2]))), tb, 0.45 if beat % 2 == 0 else 0.3)
            if beat % 2 == 1:
                add(hp(noise(0.08), 4000) * env_exp(0.08, 50), tb, 0.12)  # snare-ish offbeat
    for i, n in enumerate(mel):
        tn = t0 + i * BEAT / 2
        if n and tn < end:
            add(xylo(mtof(nm(n))), tn, 0.28, 0.25)
    b += 1

# chase sound effects
add(glide(1900, 1500, 0.25, vib=0.05), 15.5, 0.06)                         # mouse skid
add(glide(1700, 1300, 0.65, vib=0.06, wave="sq") * env_exp(0.65, 2), 15.95, 0.07)  # cat skid squeal
add(lp(noise(0.65), 1500) * env_exp(0.65, 3), 15.95, 0.12)
for i in range(3):
    add(woodblock(700 - i * 60), 16.56 + i * 0.13, 0.3 - i * 0.07)              # pot wobble
add(hp(noise(0.3), 800) * np.sin(np.linspace(0, np.pi, int(0.3 * SR))), 16.6, 0.15)  # spin whoosh
add(glide(1300, 280, 0.6, vib=0.012), 18.45, 0.16)                          # slip!
add(thud(0.5), 19.05, 0.55)
add(glide(250, 900, 0.22, vib=0.08, shape="lin"), 19.45, 0.15)             # boing back up
add(glide(900, 180, 0.09), 21.0, 0.25)                                       # pop into the hole
# 21.1 BONK
t = tt(0.9)
bonk = (np.sin(2 * np.pi * 185 * t) + 0.7 * np.sin(2 * np.pi * 277 * t) + 0.3 * np.sin(2 * np.pi * 412 * t)) * np.exp(-t * 6)
add(bonk + lp(noise(0.9), 400) * np.exp(-t * 25) * 3, 21.1, 0.85)
# dizzy tweets / twinkles while the stars circle
for i, tt0 in enumerate(np.arange(21.5, 27.0, 0.55)):
    add(glide(2600, 3400, 0.08) * 0.9, tt0, 0.05, 0.4 if i % 2 else -0.4)
    add(glide(3000, 3800, 0.06), tt0 + 0.1, 0.04, 0.4 if i % 2 else -0.4)
# frame wobble creak, frame crash on the head
for i in range(4):
    add(glide(320 + i * 20, 260, 0.12, vib=0.1, wave="sq") * 0.6, 21.25 + i * 0.2, 0.05)
add(thud(0.35, 200, 80), 22.35, 0.35)
add(lp(hp(noise(0.25), 1200), 5000) * env_exp(0.25, 12), 22.35, 0.25)  # canvas rip
# slow fall, then THUD
add(glide(1000, 220, 1.0, vib=0.015), 22.6, 0.14)
add(thud(0.7, 90, 35), 23.6, 0.7)

# 23.8-27: music-box ending waltz
box = ["E5", "G5", "C6", "B5", "G5", "E5", "F5", "A5", "D6"]
for i, n in enumerate(box):
    add(glock(mtof(nm(n) + 12), 1.0), 23.9 + i * 0.4, 0.18, 0.15)
    if i % 3 == 0:
        add(pizz(mtof(nm(n) - 24), 0.5), 23.9 + i * 0.4, 0.35)
# chewing and giggling
for st in np.arange(24.45, 25.3, 0.14):
    add(lp(noise(0.06), 900) * env_exp(0.06, 30), st, 0.25)
for st in np.arange(25.35, 26.1, 0.13):
    add(glide(1500, 1900, 0.07, vib=0.08), st, 0.07)
add(glock(mtof(nm("A6")), 0.6), 26.82, 0.2)                                   # wink ding
# iris-out glissando + final flourish
for i in range(10):
    add(xylo(mtof(nm("C6") - i * 2)), 27.0 + i * 0.09, 0.18)
for n in ["C4", "E4", "G4", "C5"]:
    add(glock(mtof(nm(n)), 1.8), 28.1, 0.11)
    add(pizz(mtof(nm(n) - 12), 0.8), 28.1, 0.13)
add(saw_chord([mtof(nm(n)) for n in ["C4", "E4", "G4", "C5"]], 1.6, attack=0.02, decay=1.4), 28.1, 0.07)

# ---------------- ambient: snoring while the cat sleeps ----------------
for st in np.arange(0.3, 12.5, 2.85):
    t = tt(1.0)
    inhale = lp(noise(1.0), 220) * np.sin(np.pi * t) ** 2 * 3
    add(inhale * (1 + 0.6 * np.sin(2 * np.pi * 28 * t)), st, 0.12)
    add(glide(900, 600, 0.7, vib=0.02) * np.sin(np.linspace(0, np.pi, int(0.7 * SR))), st + 1.1, 0.025)

# ---------------- master ----------------
fade = np.minimum(1, np.arange(N) / (0.3 * SR)) * np.clip((DUR - np.arange(N) / SR) / 0.6, 0, 1)
out = np.tanh(mix * 1.1) * fade[:, None]
out *= 0.89 / np.max(np.abs(out))
with wave.open(str(OUT / "audio.wav"), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((out * 32767).astype(np.int16).tobytes())
print("wrote", OUT / "audio.wav")
