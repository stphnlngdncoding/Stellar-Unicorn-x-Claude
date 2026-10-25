# Silk Tides: the whole board is a slow, liquid field of colour. Overlapping
# waves drift through each other while their shapes stretch and fold over
# minutes, and the colours roll through indigo, teal, sea green, gold, rose
# and plum. Every pixel is always lit.
#   A = reshuffle the waves
#
# Memory-friendly: integer maths and lookup tables only in the frame loop.
import math, random
from array import array
from stellar import StellarUnicorn

SPEED = 3            # how fast the waves flow (integer ticks per second x 2)
COLOUR_SPEED = 2     # how fast the palette rolls (steps per second)
FRAME = 0.03

# palette stops (r, g, b), looped; deep jewel tones, never fully black
STOPS = [(30, 20, 90), (10, 110, 140), (20, 150, 100), (210, 160, 40),
         (200, 60, 90), (110, 30, 120), (30, 20, 90)]

def setup(su, g):
    global W, H, SIN, PENS, RAD, seeds, a_was
    W, H = su.WIDTH, su.HEIGHT
    SIN = array("h", [int(127 * math.sin(2 * math.pi * i / 256)) for i in range(256)])
    # 256-step looping gradient, made into pens once
    PENS = []
    segs = len(STOPS) - 1
    for i in range(256):
        f = i / 256 * segs
        k = int(f)
        q = f - k
        a, b = STOPS[k], STOPS[k + 1]
        q = q * q * (3 - 2 * q)            # ease between stops
        PENS.append(g.create_pen(int(a[0] + (b[0] - a[0]) * q),
                                 int(a[1] + (b[1] - a[1]) * q),
                                 int(a[2] + (b[2] - a[2]) * q)))
    # distance from the centre, 0..255 scale, for a ring-shaped wave
    RAD = bytearray(min(255, int(math.sqrt((x - 7.5) ** 2 + (y - 7.5) ** 2) * 22))
                    for y in range(H) for x in range(W))
    seeds = [random.randrange(256) for _ in range(6)]
    a_was = False

def frame(su, g, t):
    global a_was
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was:
        for k in range(6):
            seeds[k] = random.randrange(256)
    a_was = a

    tt = int(t * SPEED * 2)
    slow = int(t * 2)                       # for the very slow shape changes
    s0, s1, s2, s3, s4, s5 = seeds
    # wave frequencies wander slowly, so the pattern keeps changing shape
    fx = 10 + (SIN[(slow // 3 + s0) & 255] >> 4)      # roughly 2..18
    fy = 10 + (SIN[(slow // 4 + s1) & 255] >> 4)
    fd = 9 + (SIN[(slow // 5 + s2) & 255] >> 4)
    fr = 3 + (SIN[(slow // 7 + s3) & 255] >> 5)       # roughly 0..6
    shift = int(t * COLOUR_SPEED) + s4
    t1, t2, t3, t4 = tt + s5, (tt * 3) >> 2, tt >> 1, (tt * 5) >> 2

    i = 0
    for y in range(H):
        yy = y * fy - t2
        for x in range(W):
            v = (SIN[(x * fx + t1) & 255]
                 + SIN[yy & 255]
                 + SIN[((x + y) * fd + t3) & 255]
                 + SIN[(RAD[i] * fr // 4 - t4) & 255])     # -508..508
            g.set_pen(PENS[((v + 512) >> 2) + shift & 255])
            g.pixel(x, y)
            i += 1
    return FRAME
