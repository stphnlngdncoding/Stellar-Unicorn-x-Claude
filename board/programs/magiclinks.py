# "magiclinks" floats across a twinkling night sky, each letter bobbing on a
# wave and shimmering from magenta through violet to cyan, shedding sparkles.
# When the word has passed, a burst of magic fills the board.
import math, random

MESSAGE = "magiclinks"
SPEED = 0.05          # seconds per frame; the word moves 1 pixel per frame
SPARKLE_RATE = 0.10   # chance per visible letter per frame to shed a sparkle
MAX_PARTS = 45

def hsv_rgb(h, s, v):
    i = int(h * 6)
    f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i % 6]
    return int(r * 255), int(g * 255), int(b * 255)

def setup(su, g):
    global W, H, BLACK, PAL, SPARK, STAR, widths, total, x, stars, parts
    W, H = su.WIDTH, su.HEIGHT
    g.set_font("bitmap8")
    BLACK = g.create_pen(0, 0, 0)
    # shimmer palette: cyan -> violet -> magenta -> violet -> cyan
    PAL = []
    for i in range(32):
        k = 0.5 - 0.5 * math.cos(2 * math.pi * i / 32)
        PAL.append(g.create_pen(*hsv_rgb(0.5 + 0.42 * k, 0.85, 1.0)))
    # sparkles fade from white-gold to nothing, stars are dim violet
    SPARK = [g.create_pen(int(255 * v), int(225 * v), int(160 * v + 95 * v * v))
             for v in [n / 7 for n in range(8)]]
    STAR = [g.create_pen(int(60 * v), int(40 * v), int(110 * v))
            for v in [n / 7 for n in range(8)]]
    widths = [g.measure_text(c, 1) for c in MESSAGE]
    total = sum(widths)
    x = W
    stars = [[random.randrange(W), random.randrange(H),
              random.uniform(0, 6.28), random.uniform(1.0, 3.0)] for _ in range(18)]
    parts = []

def spawn(px, py, burst=False):
    if len(parts) >= MAX_PARTS:
        return
    if burst:
        a = random.uniform(0, 6.28)
        sp = random.uniform(0.2, 0.7)
        parts.append([px, py, math.cos(a) * sp, math.sin(a) * sp, 1.0])
    else:
        parts.append([px, py, random.uniform(-0.25, 0.25), random.uniform(-0.35, -0.05), 1.0])

def frame(su, g, t):
    global x
    g.set_pen(BLACK)
    g.clear()

    # twinkling background stars
    for s in stars:
        v = 0.5 + 0.5 * math.sin(t * s[3] + s[2])
        g.set_pen(STAR[int(v * 7)])
        g.pixel(s[0], s[1])

    # the word: each letter bobs on a wave and shimmers
    cx = x
    shift = int(t * 18)
    for i, c in enumerate(MESSAGE):
        w = widths[i]
        if -w < cx < W:
            bob = int(round(1.6 * math.sin(t * 3.5 + i * 0.8)))
            g.set_pen(PAL[(i * 3 + shift) % 32])
            g.text(c, cx, 4 + bob, -1, 1)
            if random.random() < SPARKLE_RATE:
                spawn(cx + random.randrange(max(1, w - 1)), 4 + bob + random.randrange(8))
        cx += w

    # sparkles drift and fade
    for p in parts[:]:
        p[0] += p[2]
        p[1] += p[3]
        p[4] -= 0.045
        if p[4] <= 0:
            parts.remove(p)
            continue
        px, py = int(round(p[0])), int(round(p[1]))
        if 0 <= px < W and 0 <= py < H:
            g.set_pen(SPARK[int(p[4] * 7)])
            g.pixel(px, py)

    x -= 1
    if x < -total:
        x = W
        for _ in range(30):
            spawn(7.5, 7.5, burst=True)
    return SPEED
