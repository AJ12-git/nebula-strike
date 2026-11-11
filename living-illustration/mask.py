"""Builds the figure mask (out/figure_mask.png) and a static background plate (out/background.png).

Mask: flood-fill from the image border through "background-like" pixels (paper white,
pale blue / pale yellow watercolor wash). Whatever the fill cannot reach is the figure.
Background plate: the figure area is filled from its surroundings with a pull-push
(pyramid) fill, so slivers revealed when the figure moves show plausible wash.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
src = Image.open(ROOT / "source.jpg").convert("RGB")
W, H = src.size
half = np.asarray(src.resize((W // 2, H // 2), Image.LANCZOS)).astype(np.float32)
r, g, b = half[..., 0], half[..., 1], half[..., 2]
mx, mn = half.max(-1), half.min(-1)
lum = half.mean(-1)
sat = (mx - mn) / np.maximum(mx, 1)
paper = (lum > 222) & (sat < 0.11)
blue = (lum > 185) & (b >= g - 2) & (b > r + 8)
yellow = (lum > 215) & (r >= g - 3) & (g >= b) & (sat < 0.17)
bglike = paper | blue | yellow

def dilate(m):
    o = m.copy()
    o[1:] |= m[:-1]; o[:-1] |= m[1:]; o[:, 1:] |= m[:, :-1]; o[:, :-1] |= m[:, 1:]
    return o

def erode(m):
    return ~dilate(~m)

reach = np.zeros_like(bglike)
reach[0, :] = bglike[0, :]; reach[-1, :] = bglike[-1, :]; reach[:, 0] = bglike[:, 0]; reach[:, -1] = bglike[:, -1]
for i in range(6000):
    nxt = dilate(reach) & bglike
    if (nxt == reach).all():
        break
    reach = nxt
print("flood iterations:", i)
fig = ~reach
# the lower skirt and the sneakers are almost paper-white, so the flood leaks into them:
# add their outline (traced from the drawing, full-res coords) explicitly
hull = Image.new("L", (W // 2, H // 2))
hd = ImageDraw.Draw(hull)
skirt = [(600, 1090), (830, 1090), (908, 1300), (928, 1500), (941, 1700), (955, 1875), (981, 2181), (940, 2245),
         (700, 2262), (530, 2262), (338, 2210), (328, 2100), (338, 1625), (394, 1500), (421, 1300)]
hd.polygon([(x / 2, y / 2) for x, y in skirt], fill=255)
hd.rectangle([535 / 2, 2225 / 2, 905 / 2, 2550 / 2], fill=255)
fig |= np.asarray(hull) > 0
# stray wash blots far from the figure are not part of her
fig[:, : 200 // 2] = False
fig[:, 1120 // 2:] = False
# close tiny gaps along the outline, drop specks, then grow slightly to keep the soft watercolor edge
for _ in range(3): fig = dilate(fig)
for _ in range(3): fig = erode(fig)
for _ in range(4): fig = erode(fig)
for _ in range(4): fig = dilate(fig)
for _ in range(3): fig = dilate(fig)
m = Image.fromarray((fig * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(2))
m.save(OUT / "figure_mask.png")

# background plate: pull-push fill of everything under a generously grown mask
grow = np.asarray(m.filter(ImageFilter.MaxFilter(31))).astype(np.float32) / 255
known = (grow < 0.02).astype(np.float32)
img = np.asarray(src).astype(np.float32)
levels = []
c, w = img * known[..., None], known
while min(w.shape) > 1:
    levels.append((c, w))
    h2, w2 = w.shape[0] // 2, w.shape[1] // 2
    c = c[:h2 * 2, :w2 * 2].reshape(h2, 2, w2, 2, 3).sum((1, 3))
    w = w[:h2 * 2, :w2 * 2].reshape(h2, 2, w2, 2).sum((1, 3))
fill = c / np.maximum(w, 1e-6)[..., None]
for c, w in reversed(levels):
    up = np.asarray(Image.fromarray(np.clip(fill, 0, 255).astype(np.uint8)).resize((w.shape[1], w.shape[0]), Image.BILINEAR)).astype(np.float32)
    cur = c / np.maximum(w, 1e-6)[..., None]
    a = np.clip(w, 0, 1)[..., None]
    fill = cur * a + up * (1 - a)
plate = img * known[..., None] + fill * (1 - known[..., None])
plate = np.asarray(Image.fromarray(np.clip(plate, 0, 255).astype(np.uint8)))
Image.fromarray(plate).save(OUT / "background.png")
print("ok")
