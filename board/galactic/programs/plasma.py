# Plasma: overlapping sine waves ripple along the whole strip in slowly
# shifting rainbow colours (the "B" mode from rainbow.py on its own).
# Galactic version: the waves are stretched along the strip and the ring
# wave spreads from the middle as wide ovals.
#
# Memory-friendly: integer lookup tables and precomputed pens only.
import math
from array import array

SPEED = 0.3          # 1.0 = original speed; lower = calmer
FRAME = 0.02
STRETCH = 1.6        # how much wider the waves are along the strip (1 = as on the 16x16)

def setup(su, g):
    global W, H, SIN, PENS, RAD, XA, XB
    W, H = su.WIDTH, su.HEIGHT
    SIN = array("h", [int(127 * math.sin(2 * math.pi * i / 256)) for i in range(256)])
    PENS = []
    for i in range(256):
        h = i / 256
        k = int(h * 6); f = h * 6 - k
        q, t = 1 - f, f
        r, gg, b = ((1, t, 0), (q, 1, 0), (0, 1, t), (0, q, 1), (t, 0, 1), (1, 0, q))[k % 6]
        PENS.append(g.create_pen(int(r * 255), int(gg * 255), int(b * 255)))
    cx, cy = (W - 1) / 2, (H - 1) / 2
    st = STRETCH if STRETCH > 0.2 else 0.2
    # distance from the centre (x squashed so the rings are wide ovals), in table units
    RAD = bytearray(int(math.sqrt(((x - cx) / st) ** 2 + (y - cy) ** 2) / 2 * 256 / (2 * math.pi)) & 255
                    for y in range(H) for x in range(W))
    # per-column phases for the two x waves (stretched along the strip)
    XA = bytearray(int(x * 256 / (19 * st)) & 255 for x in range(W))
    XB = bytearray(int(x * 256 / (25 * st)) & 255 for x in range(W))

def frame(su, g, t_real):
    # phase in table units: one unit = 2*pi/256 radians
    p = int(t_real * SPEED * 256 / (2 * math.pi))
    c = int(t_real * SPEED * 0.05 * 256)          # slow colour drift
    p7 = p * 7 // 10
    i = 0
    for y in range(H):
        wy = SIN[(y * 256 // 16 - (p * 13 // 10)) & 255]          # sin(y/2.5 - 1.3t)
        yb = y * 256 // 25 + p7
        for x in range(W):
            v = (SIN[(XA[x] + p) & 255]                            # sin(x/3 + t)
                 + wy
                 + SIN[(XB[x] + yb) & 255]                         # sin((x+y)/4 + 0.7t)
                 + SIN[(RAD[i] - 2 * p) & 255])                    # sin(r/2 - 2t)
            # v is -508..508 (sum of four waves); hue = v/8 of the rainbow, like the original
            g.set_pen(PENS[((v * 128) // 508 + c) & 255])
            g.pixel(x, y)
            i += 1
    return FRAME
