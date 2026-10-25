# Neon Tunnel: drive forever through a twisting tunnel of coloured bands.
# Rings rush toward you, the walls slowly spin, the road curves left and right,
# and the colours shift as you go deeper.
#   A = boost   B = change the wall pattern
#
# Memory-friendly: angle/depth tables and pens are built once; the frame loop
# is integer lookups only.
import math
from array import array
from stellar import StellarUnicorn

SPEED = 34           # how fast you drive (depth units per second)
SPIN = 9             # how fast the walls rotate
CURVE = 5            # how far the road swings (pixels)
FRAME = 0.025

HUES = 32
SHADES = 8

def hsv(h, s, v):
    i = int(h * 6)
    f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i % 6]
    return int(r * 255), int(g * 255), int(b * 255)

def setup(su, g):
    global W, H, SIN, ANG, DEP, SHD, PENS, BLACK, pos, boost_was, pattern, b_was, last_t
    W, H = su.WIDTH, su.HEIGHT
    BLACK = g.create_pen(0, 0, 0)
    SIN = array("h", [int(127 * math.sin(2 * math.pi * i / 256)) for i in range(256)])
    # 32x32 lookup tables centred in the middle, so the view can slide around
    # inside them as the road curves
    ANG, DEP, SHD = bytearray(1024), bytearray(1024), bytearray(1024)
    for v in range(32):
        for u in range(32):
            dx, dy = u - 15.5, v - 15.5
            d = math.sqrt(dx * dx + dy * dy)
            i = v * 32 + u
            ANG[i] = int((math.atan2(dy, dx) / (2 * math.pi) + 0.5) * 256) & 255
            DEP[i] = int(320 / (d + 0.6)) & 255
            SHD[i] = min(SHADES - 1, int(d * 0.9))        # dark far away, bright near
    # pens: hue x shade x (band on / band off)
    PENS = []
    for h in range(HUES):
        for s in range(SHADES):
            lvl = (s + 1) / SHADES
            PENS.append(g.create_pen(*hsv(h / HUES, 0.85, lvl)))
            PENS.append(g.create_pen(*hsv(((h / HUES) + 0.5) % 1, 0.9, lvl * 0.45)))
    pos = 0
    boost_was = False
    pattern = 0
    b_was = False
    last_t = 0.0

def frame(su, g, t):
    global pos, pattern, b_was, last_t
    boost = su.is_pressed(StellarUnicorn.SWITCH_A)
    b = su.is_pressed(StellarUnicorn.SWITCH_B)
    if b and not b_was:
        pattern = (pattern + 1) % 3
    b_was = b

    dt = t - last_t
    last_t = t
    pos += int(dt * SPEED * (3 if boost else 1) * 16)   # 1/16 depth units
    fwd = pos >> 4
    tt = int(t * 4)
    rot = int(t * SPIN) + (SIN[(tt // 3) & 255] >> 2)    # spin, with a gentle wobble
    # the road curves: slide the view around inside the tables
    ox = (SIN[(tt // 2) & 255] * CURVE) >> 7
    oy = (SIN[(tt // 3 + 64) & 255] * (CURVE - 2)) >> 7
    hue_shift = fwd >> 5

    g.set_pen(BLACK)
    g.clear()
    for y in range(H):
        row = (y + 8 - oy) * 32 + 8 - ox
        for x in range(W):
            i = row + x
            d = DEP[i] + fwd
            a = ANG[i] + rot
            if pattern == 0:          # rings with spinning stripes
                on = ((d >> 4) ^ (a >> 5)) & 1
            elif pattern == 1:        # spiral
                on = ((d + a) >> 5) & 1
            else:                     # plain rings
                on = (d >> 4) & 1
            h = ((d >> 6) + hue_shift + (a >> 6)) % HUES
            s = SHD[i]
            g.set_pen(PENS[(h * SHADES + s) * 2 + (1 - on)])
            g.pixel(x, y)
    return FRAME
