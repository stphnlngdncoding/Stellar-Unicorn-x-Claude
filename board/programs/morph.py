# Morph: a trippy 8-way kaleidoscope. Glowing bands pour through rings,
# spirals, diamonds, flowers and plaid, melting smoothly from one shape into
# the next, while a rainbow drifts across them at its own pace.
#   A = jump to the next shape
#
# Memory-friendly: every shape is a precomputed integer table; the frame loop
# only blends two of them and looks up a pen.
import math
from array import array
from stellar import StellarUnicorn

HOLD = 6.0           # seconds each shape holds
MELT = 4.0           # seconds to melt into the next one
FLOW = 40            # how fast the bands pour (table units per second)
HUE_DRIFT = 5        # how fast the rainbow drifts (hues per second, out of 32)
FRAME = 0.02

HUES = 32
LEVELS = 8

def hsv(h, s, v):
    i = int(h * 6); f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i % 6]
    return int(r * 255), int(g * 255), int(b * 255)

def setup(su, g):
    SIN = [int(127 * math.sin(2 * math.pi * i / 256)) for i in range(256)]
    rings, spiral, diamond, flower, plaid = (array("h", [0] * 256) for _ in range(5))
    for y in range(16):
        for x in range(16):
            dx, dy = x - 7.5, y - 7.5
            r = math.sqrt(dx * dx + dy * dy) * 16                       # 0..~170
            a = int((math.atan2(dy, dx) / (2 * math.pi) + 0.5) * 256) % 32
            a8 = (a if a <= 16 else 32 - a) * 8                          # 8-way mirror, 0..128
            i = y * 16 + x
            rings[i] = int(r * 0.45)
            spiral[i] = int(r * 0.4) + a8 // 4
            diamond[i] = int((abs(dx) + abs(dy)) * 6)
            flower[i] = int(r * 0.45) + SIN[(a8 * 2) & 255] // 6
            plaid[i] = (SIN[int(abs(dx) * 20) & 255] + SIN[int(abs(dy) * 20) & 255]) // 5 + int(r * 0.2)
    SHAPES = [rings, spiral, diamond, flower, plaid]
    DIR = [1, -1, 1, -1, 1]                                              # bands pour out or in
    PENS = []
    for h in range(HUES):
        for lv in range(LEVELS):
            v = 0.06 + 0.94 * (lv / (LEVELS - 1)) ** 1.6
            PENS.append(g.create_pen(*hsv(h / HUES, 0.95, v)))
    # band profile: dark -> bright -> dark over 32 steps
    TRI = bytearray(min(LEVELS - 1, (16 - abs(k - 16)) * LEVELS // 16) for k in range(32))
    shape = 0
    last_switch = 0.0
    a_was = False

def frame(su, g, t):
    global shape, last_switch, a_was
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was:
        shape = (shape + 1) % len(SHAPES)
        last_switch = t
    a_was = a
    since = t - last_switch
    if since >= HOLD + MELT:
        shape = (shape + 1) % len(SHAPES)
        last_switch = t
        since = 0
    cur, nxt = SHAPES[shape], SHAPES[(shape + 1) % len(SHAPES)]
    w = 0 if since < HOLD else int((since - HOLD) / MELT * 64)
    w = w * w // 64                                    # ease into the melt
    flow = int(t * FLOW)
    fa = flow * DIR[shape]
    fb = flow * DIR[(shape + 1) % len(SHAPES)]
    hue = int(t * HUE_DRIFT)
    for i in range(256):
        v = ((cur[i] - fa) * (64 - w) + (nxt[i] - fb) * w) >> 6
        h = ((v >> 3) + hue) % HUES
        g.set_pen(PENS[h * LEVELS + TRI[v & 31]])
        g.pixel(i & 15, i >> 4)
    return FRAME
