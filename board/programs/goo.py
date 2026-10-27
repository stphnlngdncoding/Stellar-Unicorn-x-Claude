# Goo: a few soft blobs of glowing goo drift, swell and melt into each other
# on a black background. Where they meet they bulge and merge, then pull
# apart again. The colours are one matching family (a deep rim, a bright
# core a little further round the colour wheel) that slowly travels round
# the rainbow over a few minutes.
#   A = stir the goo
#
# Memory-friendly: positions are worked out once per frame; the pixel loop
# is integer maths only and pens come from a small table refreshed every
# couple of seconds.
import math, random
from array import array
from stellar import StellarUnicorn

BLOBS = 5
DRIFT = 0.045        # how fast the blobs wander (lower = slower)
SWELL = 0.11         # how fast they swell and shrink
COLOUR_MINUTES = 4   # minutes for the colours to travel all the way round
EDGE = 260           # field strength where goo starts (higher = more black space)
FRAME = 0.04
SHADES = 16

def hsv(h, s, v):
    h %= 1.0
    i = int(h * 6); f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i % 6]
    return int(r * 255), int(g * 255), int(b * 255)

def new_paths():
    return [(random.uniform(0.6, 1.4), random.uniform(0.6, 1.4),
             random.uniform(0, 6.3), random.uniform(0, 6.3),
             random.uniform(0.8, 1.3), random.uniform(0, 6.3)) for _ in range(BLOBS)]

def setup(su, g):
    global PATHS, BX, BY, BR, PENS, BLACK, pal_at, a_was
    PATHS = new_paths()
    BX, BY, BR = array("i", [0] * BLOBS), array("i", [0] * BLOBS), array("i", [0] * BLOBS)
    BLACK = g.create_pen(0, 0, 0)
    PENS = [BLACK] * SHADES
    pal_at = -99.0
    a_was = False

def palette(g, t):
    # one hue family: deep rim -> bright, slightly shifted core
    base = t / (COLOUR_MINUTES * 60.0)
    for k in range(SHADES):
        f = k / (SHADES - 1)
        rim = 0.18 + 0.82 * (1 - (1 - f) ** 2)          # brightness rises fast, then eases
        PENS[k] = g.create_pen(*hsv(base + 0.13 * f, 0.95 - 0.45 * f * f, rim))

def frame(su, g, t):
    global pal_at, a_was, PATHS
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was:
        PATHS = new_paths()
    a_was = a
    if t - pal_at > 2.0:
        palette(g, t)
        pal_at = t
    # blob positions (1/16 px) and sizes for this frame
    for n in range(BLOBS):
        fx, fy, px, py, size, ps = PATHS[n]
        u = t * DRIFT
        BX[n] = int((7.5 + 7.5 * math.sin(u * fx + px)) * 16)
        BY[n] = int((7.5 + 7.5 * math.sin(u * fy + py)) * 16)
        r = size * (1.0 + 0.35 * math.sin(t * SWELL * (1 + n * 0.2) + ps)) * 2.4 * 16
        BR[n] = int(r * r)
    g.set_pen(BLACK)
    g.clear()
    for y in range(16):
        yy = y * 16 + 8
        for x in range(16):
            xx = x * 16 + 8
            f = 0
            for n in range(BLOBS):
                dx = xx - BX[n]
                dy = yy - BY[n]
                f += (BR[n] << 8) // (dx * dx + dy * dy + 256)
            if f > EDGE:
                k = (f - EDGE) >> 6
                g.set_pen(PENS[k if k < SHADES else SHADES - 1])
                g.pixel(x, y)
    return FRAME
