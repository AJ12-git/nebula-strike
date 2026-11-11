"""Synthesizes the soundtrack for the cinematic from out/events.json -> out/audio.wav.

Everything is procedural (numpy only): ambient drone, flyby whoosh, laser zaps,
explosions, charge shot, and a title chord. Deterministic (fixed seed).
"""
import json
import wave
from pathlib import Path

import numpy as np

SR = 44100
DUR = 16.0
N = int(SR * DUR)
OUT = Path(__file__).parent / "out"
ev = json.loads((OUT / "events.json").read_text())
rng = np.random.default_rng(1111)
L = np.zeros(N)
Rch = np.zeros(N)
t_all = np.arange(N) / SR


def lp(x, fc, order=4):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X / (1 + (f / fc) ** order), len(x))


def bp(x, lo, hi):
    return lp(x, hi) - lp(x, lo)


def add(sig, start, gain=1.0, pan=0.0):
    i = int(start * SR)
    if i >= N:
        return
    sig = sig[: N - i]
    lg, rg = np.sqrt((1 - pan) / 2), np.sqrt((1 + pan) / 2)
    L[i:i + len(sig)] += sig * gain * lg
    Rch[i:i + len(sig)] += sig * gain * rg


def sweep(f0, f1, dur, shape=2.5, curve="exp"):
    t = np.arange(int(dur * SR)) / SR
    f = f0 * (f1 / f0) ** (t / dur) if curve == "exp" else f0 + (f1 - f0) * t / dur
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.tanh(np.sin(ph) * shape) / np.tanh(shape), t


def smoothstep(a, b, x):
    u = np.clip((x - a) / (b - a), 0, 1)
    return u * u * (3 - 2 * u)


# --- ambient drone + space wind (fades under the white-out, returns softly) ---
env = smoothstep(0, 2.5, t_all) * (0.7 + 0.5 * smoothstep(4, 10.5, t_all)) * (1 - 0.85 * smoothstep(11.1, 11.4, t_all))
drone = sum(a * np.sin(2 * np.pi * f * t_all + p) for f, a, p in [(41.2, 1, 0), (41.6, 0.7, 1), (55, 0.6, 2), (82.4, 0.35, 0.5), (110.3, 0.15, 3)])
drone *= 1 + 0.25 * np.sin(2 * np.pi * 0.23 * t_all)
wind = lp(rng.standard_normal(N), 380) * 3
add(drone * env * 0.11, 0)
L += wind * env * 0.05 * (1 + 0.3 * np.sin(t_all * 0.7))
Rch += wind[::-1] * env * 0.05 * (1 + 0.3 * np.cos(t_all * 0.6))

# --- war drums from the dogfight cut to the big hit ---
for k, tt in enumerate(np.arange(4.0, 11.1, 0.5)):
    s, t = sweep(70, 38, 0.6, shape=1.2)
    hit = s * np.exp(-t * 7) * (0.5 + 0.5 * (k % 2 == 0))
    add(hit, tt, 0.35 * (0.6 + 0.4 * (tt - 4) / 7))

# --- flyby whoosh with a left-to-right pan ---
fb = ev["flyby"]
n = int(1.6 * SR)
t = np.arange(n) / SR - 0.9
w = bp(rng.standard_normal(n), 250, 3200) * np.exp(-(t / 0.32) ** 2) * 2.2
pan = np.tanh(t * 4)
i0 = int((fb - 0.9) * SR)
L[i0:i0 + n] += w * np.sqrt((1 - pan) / 2) * 0.22
Rch[i0:i0 + n] += w * np.sqrt((1 + pan) / 2) * 0.22
eng, _ = sweep(180, 90, 1.6, shape=1.5)
L[i0:i0 + n] += eng * np.exp(-(t / 0.35) ** 2) * 0.06
Rch[i0:i0 + n] += eng * np.exp(-(t / 0.35) ** 2) * 0.06

# --- lasers ---
for l in ev["lasers"]:
    if l["type"] == "blue":
        s, t = sweep(2400 * rng.uniform(0.9, 1.1), 450, 0.14, shape=3)
        add(s * np.exp(-t * 18), l["t"], 0.09, rng.uniform(-0.6, 0.6))
    else:
        s, t = sweep(950 * rng.uniform(0.9, 1.1), 220, 0.2, shape=4)
        add(s * np.exp(-t * 12), l["t"] + 0.08, 0.05, rng.uniform(-0.8, 0.8))

# --- explosions ---
noise_lo = lp(rng.standard_normal(SR * 6), 260) * 4
noise_hi = lp(rng.standard_normal(SR * 6), 2400) * 1.2
for e in ev["explosions"]:
    s = e["s"]
    dur = min(1.2 + 0.45 * s, 5.5)
    n = int(dur * SR)
    t = np.arange(n) / SR
    off = rng.integers(0, SR)
    body = noise_lo[off:off + n] * np.exp(-t * (3.5 / np.sqrt(s))) + noise_hi[off:off + n] * np.exp(-t * 9)
    thump, _ = sweep(90, 28, dur, shape=1.2)
    sig = body + thump * np.exp(-t * 4) * 1.4
    add(np.tanh(sig * 1.3) * np.minimum(1, t * 400), e["t"], 0.22 * np.sqrt(s), rng.uniform(-0.4, 0.4))

# --- charge + fire ---
cs, ct = sweep(180, 1600, ev["fire"] - ev["charge"], shape=1.5)
add(cs * (0.3 + 0.7 * ct / ct[-1]) * (0.8 + 0.2 * np.sin(ct * 2 * np.pi * 30)), ev["charge"], 0.12)
zs, zt = sweep(1400, 90, 0.7, shape=3)
add(zs * np.exp(-zt * 5), ev["fire"], 0.28)
add(bp(rng.standard_normal(int(0.7 * SR)), 400, 5000) * np.exp(-zt * 6), ev["fire"], 0.15)

# --- post-blast ring (tinnitus) during the white-out ---
n = int(1.4 * SR)
t = np.arange(n) / SR
add(np.sin(2 * np.pi * 3520 * t) * np.minimum(1, t * 8) * np.exp(-t * 2.2), 11.25, 0.03)

# --- title: impact + sustained chord + shimmer ---
tt = ev["title"]
s, t = sweep(60, 32, 3.0, shape=1.2)
add((s * 1.2 + lp(rng.standard_normal(len(t)), 200) * 3) * np.exp(-t * 1.6), tt, 0.32)
n = N - int(tt * SR)
t = np.arange(n) / SR
pad = np.zeros(n)
for f in [110, 164.81, 220, 246.94, 261.63, 329.63]:
    for h in range(1, 7):
        pad += np.sin(2 * np.pi * f * h * t * (1 + 0.0015 * np.sin(t * 0.8 + f))) / h ** 1.3
pad = lp(pad, 1400)
pad_env = smoothstep(0, 1.2, t) * (1 - smoothstep(DUR - tt - 1.0, DUR - tt, t))
add(pad * pad_env, tt, 0.045, -0.15)
add(pad[::-1][::-1] * pad_env, tt + 0.012, 0.045, 0.15)
shim = (np.sin(2 * np.pi * 880 * t) + 0.6 * np.sin(2 * np.pi * 1318.5 * t)) * (0.6 + 0.4 * np.sin(2 * np.pi * 5 * t))
add(shim * smoothstep(1.0, 2.5, t) * (1 - smoothstep(DUR - tt - 1.0, DUR - tt, t)), tt, 0.012)

# --- master: fade in/out, soft clip, normalize ---
master = smoothstep(0, 0.4, t_all) * (1 - smoothstep(15.3, 16.0, t_all))
st = np.stack([L, Rch], 1) * master[:, None]
st = np.tanh(st * 1.2)
st *= 0.89 / np.max(np.abs(st))
pcm = (st * 32767).astype(np.int16)
with wave.open(str(OUT / "audio.wav"), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("wrote", OUT / "audio.wav")
