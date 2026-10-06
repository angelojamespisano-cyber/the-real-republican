#!/usr/bin/env python3
"""Generate the app icons (navy tile, red stripes, white star) with Pillow."""
import math
from PIL import Image, ImageDraw

NAVY, RED, WHITE = (14, 31, 66), (200, 30, 45), (255, 255, 255)


def star(cx, cy, r_out, r_in, n=5):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = -math.pi / 2 + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def icon(size, maskable=False, rounded=False):
    S = size * 4  # supersample for smooth edges
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if rounded:
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=NAVY)
    else:
        d.rectangle([0, 0, S, S], fill=NAVY)
    # content scale: keep inside the maskable safe zone (80%)
    k = 0.72 if maskable else 0.9
    c = S / 2
    # red/white stripes across the lower part
    bw = S * k
    left = c - bw / 2
    sh = S * k * 0.075
    top = c + S * k * 0.14
    for i in range(3):
        y = top + i * sh * 2
        d.rounded_rectangle([left + bw * 0.12, y, left + bw * 0.88, y + sh], radius=int(sh / 2),
                            fill=RED if i % 2 == 0 else WHITE)
    d.polygon(star(c, c - S * k * 0.1, S * k * 0.3, S * k * 0.12), fill=WHITE)
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    icon(192).save("icons/icon-192.png")
    icon(512).save("icons/icon-512.png")
    icon(512, maskable=True).save("icons/icon-maskable-512.png")
    icon(180).convert("RGB").save("icons/apple-touch-icon.png")  # iOS wants opaque
    icon(64, rounded=True).save("icons/favicon-64.png")
    print("icons written")
