# Plasma: overlapping sine waves ripple across the whole board in slowly
# shifting rainbow colours (the "B" mode from rainbow.py on its own).
#
# Memory-friendly: integer lookup tables and precomputed pens only.
import math
from array import array

SPEED = 0.2          # 1.0 = original speed; lower = calmer
FRAME = 0.02

def setup(su, g):
    global W, H, SIN, PENS, RAD
    W, H = su.WIDTH, su.HEIGHT
    SIN = array("h", [int(127 * math.sin(2 * math.pi * i / 256)) for i in range(256)])
    PENS = []
    for i in range(256):
        h = i / 256
        k = int(h * 6); f = h * 6 - k
        q, t = 1 - f, f
        r, gg, b = ((1, t, 0), (q, 1, 0), (0, 1, t), (0, q, 1), (t, 0, 1), (1, 0, q))[k % 6]
        PENS.append(g.create_pen(int(r * 255), int(gg * 255), int(b * 255)))
    # distance from the centre, in table units (one full wave every ~12.6 px)
    RAD = bytearray(int(math.sqrt((x - 7.5) ** 2 + (y - 7.5) ** 2) / 2 * 256 / (2 * math.pi)) & 255
                    for y in range(H) for x in range(W))

def frame(su, g, t_real):
    # phase in table units: one unit = 2*pi/256 radians
    p = int(t_real * SPEED * 256 / (2 * math.pi))
    c = int(t_real * SPEED * 0.05 * 256)          # slow colour drift
    i = 0
    for y in range(H):
        wy = SIN[(y * 256 // 16 - (p * 13 // 10)) & 255]          # sin(y/2.5 - 1.3t)
        for x in range(W):
            v = (SIN[(x * 256 // 19 + p) & 255]                    # sin(x/3 + t)
                 + wy
                 + SIN[((x + y) * 256 // 25 + (p * 7 // 10)) & 255]  # sin((x+y)/4 + 0.7t)
                 + SIN[(RAD[i] - 2 * p) & 255])                    # sin(r/2 - 2t)
            # v is -508..508 (sum of four waves); hue = v/8 of the rainbow, like the original
            g.set_pen(PENS[((v * 128) // 508 + c) & 255])
            g.pixel(x, y)
            i += 1
    return FRAME
