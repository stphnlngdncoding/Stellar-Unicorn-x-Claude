
# ---------- tonight's X Effect card ----------
# One bar per habit. Done = lit, crushed = gold with sparkles, not yet = slow
# dim pulse. Everything done = a rainbow sweep now and then.
import math, random
from array import array

LEVELS = 12

def setup(su, g):
    global BARS, BLACK, SIN, GOLDP, WHITE, RAINBOW, ALL
    BLACK = g.create_pen(0, 0, 0)
    WHITE = g.create_pen(255, 250, 235)
    SIN = array("b", [int(100 * math.sin(2 * math.pi * i / 64)) for i in range(64)])
    today = ""
    try:
        lt = local_time()
        today = "%04d-%02d-%02d" % (lt[0], lt[1], lt[2])
    except Exception:
        pass
    fresh = today and today != DATE          # a new day: nothing marked yet
    n = min(len(HABITS), 16)
    h = 16 // max(1, n)
    gap = 1 if h >= 3 else 0
    top = (16 - h * n + gap) // 2
    BARS = []
    for i in range(n):
        name, state, col = HABITS[i]
        if fresh:
            state = 0
        dim = [g.create_pen(*[c * (8 + 4 * k) // 100 for c in col]) for k in range(LEVELS)]
        BARS.append((top + i * h, h - gap, state, g.create_pen(*col), dim))
    GOLDP = g.create_pen(255, 190, 40)
    ALL = n > 0 and all(b[2] for b in BARS)
    RAINBOW = []
    for k in range(16):
        hh = k / 16
        j = int(hh * 6); f = hh * 6 - j
        q, tt = int(255 * (1 - f)), int(255 * f)
        r, gg, b = ((255, tt, 0), (q, 255, 0), (0, 255, tt), (0, q, 255), (tt, 0, 255), (255, 0, q))[j % 6]
        RAINBOW.append(g.create_pen(r, gg, b))

def frame(su, g, t):
    g.set_pen(BLACK)
    g.clear()
    tt = int(t * 20)
    sweep = ALL and (t % 8) < 2.2
    for i, (y0, bh, state, pen, dim) in enumerate(BARS):
        if state == 0:
            lvl = (SIN[(tt // 2 + i * 6) & 63] + 100) * (LEVELS - 1) // 200
            g.set_pen(dim[lvl])
            for y in range(y0, y0 + bh):
                for x in range(1, 15):
                    g.pixel(x, y)
            continue
        shine = (tt + i * 5) % 30
        for y in range(y0, y0 + bh):
            for x in range(16):
                if sweep:
                    g.set_pen(RAINBOW[(x + y - int(t * 18)) & 15])
                elif x == shine or x == shine - 1:
                    g.set_pen(WHITE)
                elif state == 2:
                    g.set_pen(WHITE if random.getrandbits(5) == 0 else GOLDP)
                else:
                    g.set_pen(pen)
                g.pixel(x, y)
    return 0.05
