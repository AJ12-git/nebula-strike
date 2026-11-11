"""Upbeat 120 BPM pop track for the dance video -> out/audio.wav (numpy only).

Sections follow the choreography in index.html:
  0-4s   intro: plucked chords, hats, finger snaps
  4-8s   + kick and bass (step-touch)
  8-12s  + lead melody (arm wave / disco point)
  12-14s breakdown: riser + pad for the spin
  14-18s drop: full band, hits on every jump landing
  18-22s full band + big claps (grapevine)
  22s    final stab, ring out
"""
import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 120
B = 60 / BPM
DUR = 25.5
N = int(SR * DUR)
OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(7)
mix = np.zeros((N, 2))

NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def nm(s):
    return 12 * (int(s[-1]) + 1) + NOTE[s[:-1]]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tt(d):
    return np.arange(int(d * SR)) / SR


def lp(x, fc):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X / (1 + (f / fc) ** 4), len(x))


def hp(x, fc):
    return x - lp(x, fc)


def add(sig, t0, g=1.0, pan=0.0):
    i = int(round(t0 * SR))
    if i >= N:
        return
    sig = sig[: N - i]
    mix[i:i + len(sig), 0] += sig * g * np.sqrt((1 - pan) / 2)
    mix[i:i + len(sig), 1] += sig * g * np.sqrt((1 + pan) / 2)


def saw(f, t):
    return 2 * ((f * t) % 1) - 1


# ---------------- instruments ----------------
def kick():
    t = tt(0.35)
    f = 45 + 90 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) + 0.3 * np.exp(-t * 200) * rng.standard_normal(len(t))


def hat(open_=False):
    d = 0.18 if open_ else 0.04
    return hp(rng.standard_normal(int(d * SR)), 7000) * np.exp(-tt(d) * (18 if open_ else 90))


def clap(big=False):
    d = 0.3
    t = tt(d)
    n = hp(lp(rng.standard_normal(len(t)), 3500), 900)
    env = np.exp(-t * 22)
    for k in (0.011, 0.022):
        env += 0.8 * np.exp(-np.clip(t - k, 0, None) * 120) * (t >= k)
    return n * env * (1.5 if big else 1)


def snap():
    d = 0.06
    t = tt(d)
    return (hp(rng.standard_normal(len(t)), 2500) * np.exp(-t * 120) + np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 160)) * 1.2


def bass(f, d):
    t = tt(d)
    s = lp(saw(f, t) + 0.5 * np.sign(np.sin(2 * np.pi * f * t)), 650)
    return s * np.minimum(1, t * 300) * np.exp(-t * 3) * np.minimum(1, (d - t) * 60)


def pluck_chord(fs, d=0.45):
    t = tt(d)
    s = sum(saw(f, t) + saw(f * 1.004, t) for f in fs) / (2 * len(fs))
    return lp(s, 2600) * np.minimum(1, t * 500) * np.exp(-t * 7)


def pad(fs, d):
    t = tt(d)
    s = sum(saw(f, t) + saw(f * 1.006, t) + saw(f * 0.994, t) for f in fs) / (3 * len(fs))
    return lp(s, 1500) * np.minimum(1, t / 0.6) * np.minimum(1, (d - t) / 0.3)


def lead(f, d):
    t = tt(d)
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1, t * 4)
    ph = 2 * np.pi * np.cumsum(f * vib) / SR
    s = np.tanh(np.sin(ph) * 2.2) + 0.3 * np.sin(2 * ph)
    return lp(s, 3500) * np.minimum(1, t * 200) * np.exp(-t * 2.2) * np.minimum(1, (d - t) * 80)


def crash(d=2.0):
    return hp(rng.standard_normal(int(d * SR)), 4500) * np.exp(-tt(d) * 2.5)


def riser(d):
    t = tt(d)
    n = rng.standard_normal(len(t))
    out = np.zeros_like(n)
    chunks = 16
    for c in range(chunks):
        a, b = c * len(n) // chunks, (c + 1) * len(n) // chunks
        out[a:b] = lp(n, 300 + 7000 * (c / chunks) ** 2)[a:b]
    return out * (t / d) ** 2


# ---------------- arrangement ----------------
CHORDS = [["C3", "E3", "G3", "C4"], ["A2", "C3", "E3", "A3"], ["F2", "A2", "C3", "F3"], ["G2", "B2", "D3", "G3"]]
ROOTS = ["C2", "A1", "F1", "G1"]
MEL = [
    ["E5", None, "G5", None, "A5", "G5", "E5", None],
    ["C5", None, "E5", None, "G5", "E5", "D5", None],
    ["A4", "C5", "F5", None, "E5", None, "C5", None],
    ["D5", None, "G5", None, "B4", "D5", "G5", None],
]
END_BEAT = 44                      # 22.0 s: final stab
for bar in range(END_BEAT // 4):
    t0 = bar * 4 * B
    ch, root = CHORDS[bar % 4], ROOTS[bar % 4]
    breakdown = 24 <= bar * 4 < 28
    # chords
    if breakdown:
        add(pad([hz(nm(n)) for n in ch], 4 * B), t0, 0.5)
    else:
        for k in [0, 1.5, 2.5, 3.5] if bar * 4 >= 8 else [0, 2]:
            add(pluck_chord([hz(nm(n) + 12) for n in ch]), t0 + k * B, 0.16 if bar * 4 >= 8 else 0.32, 0.2)
    # hats (8ths, open hat on the off-beat in the drop)
    if not breakdown:
        for e in range(8):
            drop = bar * 4 >= 28
            add(hat(open_=drop and e % 2 == 1), t0 + e * B / 2, 0.10 if e % 2 else 0.07, -0.3)
    # kick + bass from beat 8 (not in the breakdown)
    if bar * 4 >= 8 and not breakdown:
        for k in range(4):
            add(kick(), t0 + k * B, 0.8)
        for e in range(8):
            f = hz(nm(root) + (12 if e % 2 else 0))
            add(bass(f, B / 2 * 0.9), t0 + e * B / 2, 0.35)
    # snare-clap on 2 & 4 from beat 8
    if bar * 4 >= 8 and not breakdown:
        for k in (1, 3):
            add(clap(), t0 + k * B, 0.28, 0.1)
    # lead melody from beat 16, plus the drop and the grapevine
    if bar * 4 >= 16 and not breakdown:
        for e, n in enumerate(MEL[bar % 4]):
            if n:
                add(lead(hz(nm(n)), B / 2 * 0.95), t0 + e * B / 2, 0.15, -0.15)

# finger snaps on 2 & 4 of the intro (synced with the hand pops)
for tsn in [1, 3, 5, 7]:
    add(snap(), tsn * B, 0.6, 0.3 if tsn in (1, 5) else -0.3)
# breakdown riser into the spin, whoosh during the spin
add(riser(4 * B), 24 * B, 0.45)
t = tt(1.0)
add(lp(rng.standard_normal(len(t)), 2500) * np.sin(np.pi * t) ** 2, 24.5 * B, 0.18)
# drop: crash at 14s, landing hits
add(crash(), 28 * B, 0.25)
for lb in [29.15, 31.15, 33.15, 35.15]:
    add(kick(), lb * B, 0.5)
    add(hp(rng.standard_normal(int(0.08 * SR)), 1500) * np.exp(-tt(0.08) * 50), lb * B, 0.25)
# big overhead claps in the grapevine
for cb in [37, 39, 41, 43]:
    add(clap(big=True), cb * B, 0.45)
# final stab + ring out
fin = END_BEAT * B
add(kick(), fin, 0.9)
add(crash(3.0), fin, 0.3)
add(pad([hz(nm(n) + 12) for n in ["C3", "E3", "G3", "C4", "E4"]], 3.4) * np.exp(-tt(3.4) * 0.35), fin, 0.55)
for i, n in enumerate(["C6", "E6", "G6", "C7"]):
    t = tt(1.5)
    add(np.sin(2 * np.pi * hz(nm(n)) * t) * np.exp(-t * 3), fin + 0.06 * i, 0.08, 0.3 * (i % 2 * 2 - 1))

# ---------------- master ----------------
fade = np.clip((DUR - np.arange(N) / SR) / 0.9, 0, 1)
out = np.tanh(mix * 1.2) * fade[:, None]
out *= 0.89 / np.max(np.abs(out))
with wave.open(str(OUT / "audio.wav"), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((out * 32767).astype(np.int16).tobytes())
print("wrote", OUT / "audio.wav")
