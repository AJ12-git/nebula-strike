"""Living illustration: animates a still watercolor drawing with smooth mesh-free warps.

No cut-outs: every motion is a smooth, localized displacement field applied to the
original painting (backward mapping + bilinear sampling), so no holes ever open up
and the watercolor texture is preserved. All motions are periodic in LOOP seconds,
so the clip loops seamlessly.

Usage:
  python3 animate.py                      -> pipes frames to ffmpeg: out/video_silent.mp4
  python3 animate.py --stills 0,2.3,5     -> out/still_<t>.png
"""
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
SRC = np.asarray(Image.open(ROOT / "source.jpg").convert("RGB")).astype(np.float32)
SH, SW = SRC.shape[:2]                     # 2576 x 1288
# two layers: a static background plate and the figure (alpha = figure mask); see mask.py
MASK = np.asarray(Image.open(ROOT / "out" / "figure_mask.png")).astype(np.float32)[..., None] / 255.0
PLATE = np.asarray(Image.open(ROOT / "out" / "background.png").convert("RGB")).astype(np.float32)
OW, OH = 1080, 2160                        # output (same 1:2 aspect)
K = SW / OW                                # output px -> source px
FPS, LOOP = 24, 12.0
TAU = 2 * math.pi

# output pixel grid in source coordinates
gy, gx = np.mgrid[0:OH, 0:OW].astype(np.float32)
GX, GY = (gx + 0.5) * K - 0.5, (gy + 0.5) * K - 0.5


def smoothstep(e0, e1, x):
    u = np.clip((x - e0) / (e1 - e0), 0, 1)
    return u * u * (3 - 2 * u)


def ellipse_w(x, y, cx, cy, rx, ry, inner=0.85, outer=1.3):
    r = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
    return smoothstep(outer, inner, r)


def rotate_inv(x, y, px, py, ang, w):
    """Backward map of a weighted rotation by `ang` (radians) about (px, py)."""
    a = -ang * w
    c, s = np.cos(a), np.sin(a)
    dx, dy = x - px, y - py
    return px + dx * c - dy * s, py + dx * s + dy * c


def sample(img, x, y):
    x = np.clip(x, 0, SW - 1.001)
    y = np.clip(y, 0, SH - 1.001)
    x0 = x.astype(np.int32)
    y0 = y.astype(np.int32)
    fx = (x - x0)[..., None]
    fy = (y - y0)[..., None]
    a = img[y0, x0]
    b = img[y0, x0 + 1]
    c = img[y0 + 1, x0]
    d = img[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


# ---------------- static weights (depend only on position) ----------------
HAND_AREA = ellipse_w(GX, GY, 890, 500, 95, 145)            # V-sign hand: keep it out of the head's rotation
W_HEAD = ellipse_w(GX, GY, 600, 385, 225, 240) * (1 - HAND_AREA)
W_TIPS_L = ellipse_w(GX, GY, 480, 560, 95, 70)
W_TIPS_R = ellipse_w(GX, GY, 770, 515, 55, 55) * (1 - HAND_AREA)
W_HAND = ellipse_w(GX, GY, 885, 480, 80, 130)
W_FOREARM = ellipse_w(GX, GY, 960, 690, 120, 240)
W_BREATH = smoothstep(1150, 620, GY)                         # everything above the waist rises
W_SKIRT = np.exp(-((GX - 650) / 330) ** 2) * smoothstep(1150, 1320, GY) * smoothstep(2275, 2215, GY) * np.clip((GY - 1150) / 1100, 0, 1) ** 1.3
W_SWAY = np.exp(-((GX - 680) / 420) ** 2) * smoothstep(2330, 2180, GY)  # sneakers stay planted

# ---------------- blink overlay (painted in source space, moves with the head) ----------------
EYES = [  # centre, half-width, half-height, tilt (deg)
    ((566, 432), 37, 27, -12),
    ((692, 381), 42, 23, -10),
]


def eye_skin(cx, cy, hu, hv, deg):
    """Median of bright skin pixels in a ring around the eye (skips lashes, iris and the glasses frame)."""
    a = math.radians(deg)
    ys, xs = np.mgrid[int(cy - hv * 2):int(cy + hv * 2), int(cx - hu * 2):int(cx + hu * 2)]
    u = (xs - cx) * math.cos(a) + (ys - cy) * math.sin(a)
    v = -(xs - cx) * math.sin(a) + (ys - cy) * math.cos(a)
    r = np.sqrt((u / hu) ** 2 + (v / hv) ** 2)
    px = SRC[ys, xs][(r > 1.15) & (r < 1.7)]
    lum = px.mean(axis=1)
    good = px[lum > np.percentile(lum, 55)]
    return tuple(int(c) for c in np.median(good, axis=0))


def closed_eye_overlay():
    S2 = 2
    ov = Image.new("RGBA", (SW * S2, SH * S2))
    d = ImageDraw.Draw(ov)
    frames = []
    for (cx, cy), hu, hv, deg in EYES:
        a = math.radians(deg)
        ux, uy = math.cos(a), math.sin(a)
        vx, vy = -uy, ux
        col = eye_skin(cx, cy, hu, hv, deg) + (255,)
        pts = []
        for k in range(48):
            th = k / 48 * TAU
            u, v = math.cos(th) * (hu + 1), math.sin(th) * (hv + 1)
            pts.append(((cx + u * ux + v * vx) * S2, (cy + u * uy + v * vy) * S2))
        d.polygon(pts, fill=col)
        frames.append((cx, cy, hu, hv, ux, uy, vx, vy))
    ov = ov.filter(ImageFilter.GaussianBlur(3 * S2))
    d = ImageDraw.Draw(ov)
    ink = (34, 26, 30, 255)
    for cx, cy, hu, hv, ux, uy, vx, vy in frames:
        P = lambda u, v: ((cx + u * ux + v * vx) * S2, (cy + u * uy + v * vy) * S2)
        line = [P(-hu * 0.95 + 1.9 * hu * k / 30, hv * 0.3 + 6 * (1 - ((-hu * 0.95 + 1.9 * hu * k / 30) / hu) ** 2)) for k in range(31)]
        for i in range(len(line) - 1):
            wdt = 2 + 5 * math.sin(math.pi * (i + 0.5) / (len(line) - 1)) ** 0.6
            d.line([line[i], line[i + 1]], fill=ink, width=int(wdt * S2))
        e = line[-1]
        d.line([e, P(hu * 0.95 + 10, hv * 0.3 - 7)], fill=ink, width=3 * S2)       # outer lash flick
        d.line([e, P(hu * 0.95 + 6, hv * 0.3 + 2)], fill=ink, width=2 * S2)
    ov = ov.filter(ImageFilter.GaussianBlur(1.0 * S2)).resize((SW, SH), Image.LANCZOS)
    return np.asarray(ov).astype(np.float32)


BLINK = closed_eye_overlay()
BG_OUT = sample(PLATE, GX, GY)                                # the background never moves
BLINK_A = BLINK[..., 3:4] / 255.0
BLINK_RGB = BLINK[..., :3]
BLINK_TIMES = [2.3, 6.9, 7.25, 10.6]                          # includes a double blink


def blink_amount(t):
    c = 0.0
    for b in BLINK_TIMES:
        d = abs(((t - b + LOOP / 2) % LOOP) - LOOP / 2)
        c = max(c, 1 - d / 0.09)
    return max(0.0, c)


# ---------------- leaves & light motes (output space) ----------------
rng = np.random.default_rng(11)


def leaf_sprite(color, size):
    s = 4
    w, h = int(size * 0.55) * s, size * s
    im = Image.new("RGBA", (w + 8 * s, h + 8 * s))
    d = ImageDraw.Draw(im)
    pts = []
    for k in range(40):
        th = k / 40 * TAU
        x = math.sin(th) * w / 2 * (0.75 + 0.25 * math.cos(th))
        y = -math.cos(th) * h / 2
        pts.append((x + w / 2 + 4 * s, y + h / 2 + 4 * s))
    d.polygon(pts, fill=color + (190,))
    dark = tuple(int(c * 0.7) for c in color) + (170,)
    d.line([(w / 2 + 4 * s, 4 * s + h * 0.05), (w / 2 + 4 * s, 4 * s + h)], fill=dark, width=s * 2)
    for k in range(3):
        yy = 4 * s + h * (0.3 + 0.2 * k)
        d.line([(w / 2 + 4 * s, yy + h * 0.08), (w / 2 + 4 * s + w * 0.3, yy)], fill=dark, width=s)
        d.line([(w / 2 + 4 * s, yy + h * 0.08), (w / 2 + 4 * s - w * 0.3, yy)], fill=dark, width=s)
    im = im.filter(ImageFilter.GaussianBlur(s * 0.8))
    return im.resize((im.width // s, im.height // s), Image.LANCZOS)


LEAF_COLORS = [(126, 176, 84), (156, 196, 98), (104, 156, 76), (214, 200, 110), (180, 206, 120)]
LEAVES = []
for i in range(11):
    LEAVES.append(dict(
        sprite=leaf_sprite(LEAF_COLORS[i % 5], int(rng.uniform(46, 78))),
        x0=rng.uniform(40, OW - 40), phase=i / 11 + rng.uniform(-0.03, 0.03),
        sway=rng.uniform(40, 110), spin=rng.choice([-1, 1]) * rng.uniform(1, 2), wph=rng.uniform(0, TAU),
        speed=rng.choice([1, 1, 2]),
    ))
MOTES = [(rng.uniform(0, OW), rng.uniform(0, 1), rng.uniform(2, 5), rng.uniform(0, TAU)) for _ in range(26)]


def overlay(frame, t):
    im = Image.fromarray(frame).convert("RGBA")
    glow = Image.new("RGBA", im.size)
    gd = ImageDraw.Draw(glow)
    for x0, ph, r, wp in MOTES:
        u = (t / LOOP + ph) % 1
        y = OH + 20 - u * (OH + 40)
        x = x0 + 30 * math.sin(TAU * (t / 6) + wp)
        a = int(120 * math.sin(math.pi * u))
        gd.ellipse([x - r * 2, y - r * 2, x + r * 2, y + r * 2], fill=(255, 252, 230, a // 3))
        gd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 245, a))
    glow = glow.filter(ImageFilter.GaussianBlur(2))
    im = Image.alpha_composite(im, glow)
    for L in LEAVES:
        u = (L["speed"] * t / LOOP + L["phase"]) % 1
        y = -90 + u * (OH + 180)
        x = L["x0"] + L["sway"] * math.sin(TAU * (t / 4) + L["wph"])
        ang = 25 * math.sin(TAU * (t / 3) + L["wph"]) + L["spin"] * 360 * (t / LOOP) * L["speed"]
        sp = L["sprite"].rotate(ang, resample=Image.BICUBIC, expand=True)
        flip = abs(math.cos(TAU * (t / 4) + L["wph"]))                     # tumbling foreshortening
        sp = sp.resize((max(4, int(sp.width * (0.45 + 0.55 * flip))), sp.height), Image.BICUBIC)
        im.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height / 2)))
    return np.asarray(im.convert("RGB"))


# ---------------- one frame ----------------
def frame(t):
    w = lambda period, ph=0.0: math.sin(TAU * t / period + ph)
    # motion curves (all periods divide LOOP)
    sway = math.radians(0.35) * w(6, 0.5)
    skirt = 7.0 * 1.0
    breath = 3.2 * (0.5 - 0.5 * math.cos(TAU * t / 4))
    head = math.radians(2.0) * w(6) + math.radians(0.7) * w(3, 1.0)
    tips = 5.0 * w(3, -0.7) + 2.0 * w(2, 0.3)
    hand = math.radians(6.0) * w(2) ** 3                          # snappier wiggle
    forearm = math.radians(1.6) * w(2, -0.4)

    x, y = GX, GY
    x, y = rotate_inv(x, y, 680, 2420, sway, W_SWAY)
    phase = TAU * t / 3 - (y - 1150) / 380
    x = x - skirt * np.sin(phase) * W_SKIRT
    y = y + breath * W_BREATH
    x = x - tips * W_TIPS_L - tips * 0.8 * W_TIPS_R
    x, y = rotate_inv(x, y, 680, 600, head, W_HEAD)
    x, y = rotate_inv(x, y, 1040, 860, forearm, W_FOREARM)
    x, y = rotate_inv(x, y, 905, 600, hand, W_HAND)

    src = SRC
    c = blink_amount(t)
    if c > 0:
        a = BLINK_A * min(1.0, c * 1.6)
        src = SRC * (1 - a) + BLINK_RGB * a
    fg = sample(src, x, y)
    a = sample(MASK, x, y)
    out = fg * a + BG_OUT * (1 - a)
    return overlay(np.clip(out, 0, 255).astype(np.uint8), t)


if __name__ == "__main__":
    if "--stills" in sys.argv:
        for t in map(float, sys.argv[sys.argv.index("--stills") + 1].split(",")):
            Image.fromarray(frame(t)).save(OUT / f"still_{t}.png")
            print("still", t)
        sys.exit()
    n = int(LOOP * FPS)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "slow", str(OUT / "video_silent.mp4")], stdin=subprocess.PIPE)
    for i in range(n):
        ff.stdin.write(frame(i / FPS).tobytes())
        if i % 48 == 0:
            print("frame", i, "/", n, flush=True)
    ff.stdin.close()
    ff.wait()
    print("wrote", OUT / "video_silent.mp4")
