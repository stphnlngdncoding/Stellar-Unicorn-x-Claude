# Driftfield: a handful of glowing motes drift along a slowly changing current,
# leaving soft fading trails. The palette travels on its own through kelp and
# moonlight, dusk harbour, glacier melt, ember tide and plankton bloom.
#   A = nudge the current somewhere new
#
# Memory-friendly: integer maths only in the frame loop (no float churn), and
# every buffer is allocated once in setup().
import math, random
from array import array
from stellar import StellarUnicorn

MOTES = 14
STEP = 26            # mote speed (1/256 px per frame units); bigger = faster
DEPOSIT = 46         # how much light a mote leaves per frame
FADE = 60            # trail fade per frame, out of 64 (bigger = longer trails)
PALETTE_SECONDS = 90 # time spent on each palette before drifting to the next
FRAME = 0.04

TIDES = [
    [(178, 55, 52), (205, 60, 58), (262, 40, 66)],   # kelp & moonlight
    [(18, 70, 62), (338, 45, 60), (265, 35, 58)],    # dusk harbour
    [(190, 60, 64), (168, 45, 55), (215, 55, 70)],   # glacier melt
    [(28, 80, 58), (8, 65, 55), (45, 70, 64)],       # ember tide
    [(140, 55, 55), (176, 65, 58), (96, 45, 60)],    # plankton bloom
]
SEG = 64             # gradient steps per palette

def hsl(h, s, l):
    s /= 100; l /= 100
    c = (1 - abs(2 * l - 1)) * s
    hp = (h % 360) / 60
    x = c * (1 - abs(hp % 2 - 1))
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(hp) % 6]
    m = l - c / 2
    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)

def setup(su, g):
    global W, H, SIN, PR, PG, PB, NPAL, R, G, B, mx, my, mk, mage, seed, a_was, BLACK
    W, H = su.WIDTH, su.HEIGHT
    BLACK = g.create_pen(0, 0, 0)
    SIN = array("h", [int(1024 * math.sin(2 * math.pi * i / 256)) for i in range(256)])
    # one long looping gradient through every palette, blending between them
    PR, PG, PB = bytearray(), bytearray(), bytearray()
    for p in range(len(TIDES)):
        a, b = TIDES[p], TIDES[(p + 1) % len(TIDES)]
        for i in range(SEG):
            f = i / SEG
            # within a palette walk its three stops; near the end blend into the next palette
            pos = f * 3
            j = int(pos) % 3
            q = pos - int(pos)
            s0, s1 = a[j], a[(j + 1) % 3]
            h = s0[0] + (((s1[0] - s0[0] + 540) % 360) - 180) * q
            col = hsl(h, s0[1] + (s1[1] - s0[1]) * q, s0[2] + (s1[2] - s0[2]) * q)
            if f > 0.75:
                w = (f - 0.75) / 0.25
                nb = hsl(*b[0])
                col = tuple(int(col[k] + (nb[k] - col[k]) * w) for k in range(3))
            PR.append(col[0]); PG.append(col[1]); PB.append(col[2])
    NPAL = len(PR)
    R, G, B = bytearray(W * H), bytearray(W * H), bytearray(W * H)
    mx = array("i", [random.randrange(W * 256) for _ in range(MOTES)])
    my = array("i", [random.randrange(H * 256) for _ in range(MOTES)])
    mk = bytearray(random.randrange(SEG) for _ in range(MOTES))
    mage = array("i", [random.randrange(400) for _ in range(MOTES)])
    seed = random.randrange(256)
    a_was = False

def frame(su, g, t):
    global seed, a_was
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was:
        seed = (seed + 64 + random.randrange(64)) & 255
    a_was = a

    tt = int(t * 6)                                   # slow time in integer ticks
    base = int(t * NPAL / (PALETTE_SECONDS * len(TIDES))) % NPAL

    # fade the trails
    for i in range(W * H):
        R[i] = R[i] * FADE >> 6
        G[i] = G[i] * FADE >> 6
        B[i] = B[i] * FADE >> 6

    for n in range(MOTES):
        x, y = mx[n], my[n]
        u, v = x >> 4, y >> 4                         # 0..255 across the board
        ang = (SIN[(u + tt + seed) & 255] + SIN[((v * 3 >> 1) - (tt >> 1)) & 255]
               + SIN[((u + v) // 2 + (tt >> 2) + seed) & 255]) >> 4
        ang = (ang + seed) & 255
        x += SIN[(ang + 64) & 255] * STEP >> 10
        y += SIN[ang] * STEP >> 10
        mage[n] += 1
        if x < 0 or y < 0 or x >= W * 256 or y >= H * 256 or mage[n] > 700:
            x, y = random.randrange(W * 256), random.randrange(H * 256)
            mage[n] = 0
        mx[n], my[n] = x, y
        c = (base + mk[n]) % NPAL
        i = (y >> 8) * W + (x >> 8)
        r = R[i] + (PR[c] * DEPOSIT >> 6)
        gg = G[i] + (PG[c] * DEPOSIT >> 6)
        b = B[i] + (PB[c] * DEPOSIT >> 6)
        R[i] = r if r < 255 else 255
        G[i] = gg if gg < 255 else 255
        B[i] = b if b < 255 else 255

    g.set_pen(BLACK)
    g.clear()
    for i in range(W * H):
        r, gg, b = R[i], G[i], B[i]
        if r | gg | b:
            g.set_pen(g.create_pen(r, gg, b))
            g.pixel(i % W, i // W)
    return FRAME
