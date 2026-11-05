# Ribbons: two or three line shapes (triangles and four-sided ones) whose
# corners bounce around the dark like billiard balls, each shape trailing a
# fan of fading echoes of where it just was, so they sweep out ribbons of
# light. Their colours drift slowly round the rainbow, and the echoes keep
# the colour they had, so each ribbon shades along its length.
# (Galactic Unicorn version: the corners bounce across the full 53 px.)
#   A = new shapes and colours
#
# Memory-friendly: corner positions are integers (1/256 of a pixel) in an
# array, the echo history is a fixed ring buffer made in setup(), and every
# pen (hues x brightness levels) is made once in setup().
import math
import random
from array import array
from galactic import GalacticUnicorn

SHAPES = (2, 3)      # how many shapes (min, max; A picks again)
CORNERS = (3, 4)     # corners per shape (min, max)
SPEED = (9.0, 20.0)  # corner speed across the strip, pixels a second (min, max)
TRAIL = 7            # echoes trailing behind each shape
GAP = 3              # frames between echoes (bigger = wider-spaced ribbons)
HUE_SPEED = 8.0      # colour drift, degrees of hue a second
FRAME = 0.04

MAX_SHAPES = 4
MAX_CORNERS = 4
HUES = 48
LEVELS = 8

def setup(su, g):
    global W, H, PEN, BLACK, pos, vel, ncorn, hue, hist, hhue, head, filled, nshapes, a_was, HLEN, TR
    W, H = su.WIDTH, su.HEIGHT
    TR = max(0, TRAIL)
    gap = max(1, GAP)
    HLEN = TR * gap + 1
    # pens: rich, slightly deep colours; dimmer levels drop off quickly so
    # the old echoes sink into the dark
    BLACK = g.create_pen(0, 0, 0)
    PEN = []
    for h in range(HUES):
        r, gg, b = hsv(h / HUES, 0.85)
        for lv in range(LEVELS):
            m = ((lv + 1) / LEVELS) ** 1.8
            PEN.append(g.create_pen(int(r * m), int(gg * m), int(b * m)))
    pos = array("i", [0] * (MAX_SHAPES * MAX_CORNERS * 2))
    vel = array("i", [0] * (MAX_SHAPES * MAX_CORNERS * 2))
    ncorn = bytearray(MAX_SHAPES)
    hue = [0.0] * MAX_SHAPES
    hist = array("h", [0] * (HLEN * MAX_SHAPES * MAX_CORNERS * 2))
    hhue = bytearray(HLEN * MAX_SHAPES)
    head = 0
    filled = 0
    nshapes = 0
    a_was = False
    new_scene()

def hsv(h, s):
    h = (h % 1.0) * 6
    i = int(h)
    f = h - i
    p = 1 - s
    q = 1 - s * f
    t = 1 - s * (1 - f)
    r, g, b = ((1, t, p), (q, 1, p), (p, 1, t), (p, q, 1), (t, p, 1), (1, p, q))[i % 6]
    return 255 * r, 255 * g, 255 * b

def rand_vel():
    v = random.uniform(SPEED[0], SPEED[1]) * 256 * FRAME
    return int(v) if random.getrandbits(1) else -int(v)

def new_scene():
    global nshapes, filled
    nshapes = min(MAX_SHAPES, random.randint(SHAPES[0], SHAPES[1]))
    h0 = random.random()
    for s in range(nshapes):
        ncorn[s] = random.randint(CORNERS[0], CORNERS[1])
        hue[s] = (h0 + s / nshapes + random.uniform(-0.05, 0.05)) % 1.0
        for c in range(MAX_CORNERS):
            i = (s * MAX_CORNERS + c) * 2
            pos[i] = random.randrange((W - 1) << 8)
            pos[i + 1] = random.randrange((H - 1) << 8)
            vel[i] = rand_vel()
            # across a short strip the corners move more gently up and down
            vel[i + 1] = rand_vel() * H // W + (1 if random.getrandbits(1) else -1) * random.randint(10, 30)
    filled = 0

def bounce(i, lim, k):
    # bounce off a wall, with a little fresh speed so patterns never settle
    p = pos[i]
    v = vel[i]
    p += v
    if p < 0 or p > lim:
        sp = abs(rand_vel())
        if k:
            sp = sp * H // W + random.randint(10, 30)
        if p < 0:
            p = -p
            v = sp
        else:
            p = 2 * lim - p
            v = -sp
        if p < 0:
            p = 0
        elif p > lim:
            p = lim
    pos[i] = p
    vel[i] = v

def frame(su, g, t):
    global head, filled, a_was
    a = su.is_pressed(GalacticUnicorn.SWITCH_A)
    if a and not a_was:
        new_scene()
    a_was = a

    limx = (W - 1) << 8
    limy = (H - 1) << 8
    dh = HUE_SPEED / 360 * FRAME
    # move every corner and record this frame in the ring
    head = (head + 1) % HLEN
    if filled < HLEN:
        filled += 1
    base = head * MAX_SHAPES
    for s in range(nshapes):
        hue[s] = (hue[s] + dh) % 1.0
        hhue[base + s] = int(hue[s] * HUES) % HUES
        for c in range(ncorn[s]):
            i = (s * MAX_CORNERS + c) * 2
            bounce(i, limx, 0)
            bounce(i + 1, limy, 1)
            j = (base + s) * MAX_CORNERS * 2 + c * 2
            hist[j] = pos[i]
            hist[j + 1] = pos[i + 1]

    g.set_pen(BLACK)
    g.clear()
    gap = max(1, GAP)
    # oldest echoes first, so newer and brighter lines land on top
    for k in range(TR, -1, -1):
        if k * gap >= filled:
            continue
        slot = (head - k * gap) % HLEN
        if k == 0:
            lv = LEVELS - 1
        else:
            lv = (LEVELS - 2) * (TR + 1 - k) // TR
        for s in range(nshapes):
            g.set_pen(PEN[hhue[slot * MAX_SHAPES + s] * LEVELS + lv])
            j = (slot * MAX_SHAPES + s) * MAX_CORNERS * 2
            n = ncorn[s]
            px = (hist[j + (n - 1) * 2] + 128) >> 8
            py = (hist[j + (n - 1) * 2 + 1] + 128) >> 8
            for c in range(n):
                x = (hist[j + c * 2] + 128) >> 8
                y = (hist[j + c * 2 + 1] + 128) >> 8
                g.line(px, py, x, y)
                px = x
                py = y
    return FRAME
