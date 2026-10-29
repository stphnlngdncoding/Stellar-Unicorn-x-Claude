# Liquid metal: a pool of cool blue liquid metal sloshes around the bottom
# of the board, rocking from side to side with a moving chrome sheen. Every
# so often an invisible hand scoops up a blob, carries it somewhere, and
# drops it back in with a splash that sends waves across the pool.
#   A = scoop up a blob now
#
# Memory-friendly: the pool is two integer arrays (height and speed per
# column), pens are made once, and nothing is allocated per frame.
import math, random
from array import array
from stellar import StellarUnicorn

LEVEL = 5.0          # how deep the pool is at rest (pixels)
SLOSH = 0.08         # how fast the pool rocks (lower = lazier)
TILT = 4.5           # how far it rocks (pixels of height difference)
WAIT = (10, 24)      # seconds between scoops (random in this range)
FRAME = 0.03

SH = 16              # number of shades
ONE = 256            # fixed point: 1 pixel = 256

def setup(su, g):
    global H, V, PENS, SPEC, BLACK, SINT, mode, mode_t, next_scoop, bx, by, bvy, br, tx, ty, ox, drops, a_was, lost, taken
    H = array("i", [int(LEVEL * ONE)] * 16)
    V = array("i", [0] * 16)
    BLACK = g.create_pen(0, 0, 0)
    # deep navy -> steel blue -> icy white
    stops = [(2, 6, 28), (8, 28, 90), (30, 80, 170), (90, 160, 230), (200, 235, 255)]
    PENS = []
    for k in range(SH):
        f = k / (SH - 1) * (len(stops) - 1)
        i = min(int(f), len(stops) - 2); q = f - i
        a, b = stops[i], stops[i + 1]
        PENS.append(g.create_pen(*[int(a[c] + (b[c] - a[c]) * q) for c in range(3)]))
    SPEC = g.create_pen(235, 248, 255)
    SINT = array("h", [int(127 * math.sin(2 * math.pi * i / 256)) for i in range(256)])
    mode, mode_t = "pool", 0.0
    next_scoop = random.uniform(4, 8)
    bx = by = bvy = br = tx = ty = ox = 0.0
    lost = taken = 0                             # pool volume carried by the blob (fixed point)
    drops = []                                   # splash droplets: [x, y, vx, vy] in pixels
    a_was = False

def surface(x):
    return 16 - H[x] / ONE                       # y of the pool surface in column x

def splash(x, size):
    xi = max(0, min(15, int(x)))
    for k in range(-2, 3):
        c = xi + k
        if 0 <= c < 16:
            V[c] -= int(size * (220 - 60 * abs(k)))
    for _ in range(int(3 + size * 3)):
        drops.append([x + random.uniform(-0.8, 0.8), surface(xi) - 0.5,
                      random.uniform(-3.5, 3.5), -random.uniform(4, 9)])

def step_pool(t, dt):
    # wave physics: each column is pulled by its neighbours (so bumps travel
    # as waves) and gently toward a rocking target shape (the slosh)
    mean = sum(H) // 16
    tilt = math.sin(t * SLOSH * 2 * math.pi) + 0.35 * math.sin(t * SLOSH * 5.1 + 1.3)
    k = int(tilt * TILT * ONE / 15)
    for x in range(16):
        target = mean + k * (x - 7) + (k // 2 if x == 7 else 0)
        left = H[x - 1] if x > 0 else H[x]
        right = H[x + 1] if x < 15 else H[x]
        V[x] += ((left + right - 2 * H[x]) >> 2) + ((target - H[x]) >> 5)
        V[x] = V[x] * 61 >> 6                    # damping
    for x in range(16):
        H[x] = max(ONE // 2, H[x] + V[x] // 4)
    # keep the amount of metal exact (rounding would slowly drain the pool)
    fix = (int(LEVEL * ONE) * 16 - taken - sum(H)) // 16
    for x in range(16):
        H[x] += fix

def draw_pool(g, t):
    tt = int(t * 40)
    for x in range(16):
        s = surface(x)
        top = int(s)
        frac = s - top                           # partly filled top pixel
        slope = (H[min(15, x + 1)] - H[max(0, x - 1)]) >> 6
        for y in range(max(0, top), 16):
            d = y - top
            sheen = SINT[(x * 23 + d * 37 - tt) & 255] + SINT[(x * 11 - d * 19 + tt // 2) & 255]
            if d == 0:
                k = 13 + (slope > 1) - (slope < -1)
                k = int(k * (1 - frac)) + (2 if frac < 0.5 else 0)
            else:
                k = max(3, 10 - d) + (sheen >> 7)
            k = 0 if k < 0 else SH - 1 if k >= SH else k
            g.set_pen(PENS[k])
            g.pixel(x, y)

def draw_blob(g, cx, cy, r, stretch=1.0):
    # a shaded metal ball, lit from the upper left
    r2 = r * r
    for y in range(max(0, int(cy - r * stretch) - 1), min(16, int(cy + r * stretch) + 2)):
        dy = (y + 0.5 - cy) / stretch
        for x in range(max(0, int(cx - r) - 1), min(16, int(cx + r) + 2)):
            dx = x + 0.5 - cx
            d2 = dx * dx + dy * dy
            if d2 <= r2:
                lit = 1 - ((dx + r * 0.45) ** 2 + (dy + r * 0.45) ** 2) / (r2 * 2.2)
                k = int(4 + lit * 11)
                if d2 > r2 * 0.7:
                    k -= 3                       # darker rim
                g.set_pen(SPEC if k >= SH else PENS[max(0, k)])
                g.pixel(x, y)

def frame(su, g, t):
    global mode, mode_t, next_scoop, bx, by, bvy, br, tx, ty, ox, lost, taken, a_was
    dt = FRAME
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was and mode == "pool":
        next_scoop = t
    a_was = a

    # ---- the scoop / carry / drop cycle ----
    if mode == "pool" and t >= next_scoop:
        mode, mode_t = "lift", t
        ox = random.uniform(3, 12)
        bx, by = ox, surface(int(ox))
        br = random.uniform(1.7, 2.4)
        tx, ty = random.uniform(3, 12), random.uniform(2.5, 5.5)
        lost = int(math.pi * br * br * ONE)
        taken = 0
    p = t - mode_t
    if mode == "lift":                           # rises out of the pool, trailing a neck
        f = min(1.0, p / 1.6)
        e = f * f * (3 - 2 * f)
        want = int(lost * e)                     # pool volume taken so far
        per = (want - taken) // 16
        if per > 0:
            # most of it comes from under the blob, the rest from everywhere
            for x in range(16):
                H[x] -= per // 2
            c = int(ox)
            for k in (-1, 0, 1):
                if 0 <= c + k < 16:
                    H[c + k] -= per * 16 // 6
            taken += per * 16
        by = surface(int(ox)) + (ty - surface(int(ox))) * e
        bx = ox
        if f >= 1:
            mode, mode_t = "carry", t
    elif mode == "carry":                        # drifts over to a new spot, wobbling
        f = min(1.0, p / 2.2)
        e = f * f * (3 - 2 * f)
        bx = ox + (tx - ox) * e
        by = ty + 0.4 * math.sin(p * 5)
        if f >= 1:
            mode, mode_t, bvy = "fall", t, 0.0
    elif mode == "fall":                         # dropped: falls and splashes in
        bvy += 30 * dt
        by += bvy * dt
        if by + br * 0.6 >= surface(max(0, min(15, int(bx)))):
            c = max(0, min(15, int(bx)))
            for k in (-1, 0, 1):        # the metal lands in a heap that spreads out as waves
                if 0 <= c + k < 16:
                    H[c + k] += taken // 3
            taken = 0
            splash(bx, br / 2)
            mode = "pool"
            next_scoop = t + random.uniform(*WAIT)

    step_pool(t, dt)

    # ---- draw ----
    g.set_pen(BLACK)
    g.clear()
    draw_pool(g, t)
    if mode == "lift":
        f = min(1.0, (t - mode_t) / 1.6)
        s = surface(int(ox))
        if f < 0.75:                             # the neck of liquid still attached to the pool
            w = (1 - f / 0.75) * br * 0.9
            for y in range(max(0, int(by)), min(16, int(s) + 1)):
                for x in range(int(ox - w), int(ox + w) + 1):
                    if 0 <= x < 16:
                        g.set_pen(PENS[7 + (x == int(ox))])
                        g.pixel(x, y)
        draw_blob(g, bx, by, br * (0.5 + 0.5 * f))
    elif mode == "carry":
        draw_blob(g, bx, by, br, 1.0 + 0.12 * math.sin((t - mode_t) * 9))
    elif mode == "fall":
        draw_blob(g, bx, by, br, 1.0 + min(0.35, bvy * 0.02))

    # ---- splash droplets ----
    i = 0
    while i < len(drops):
        d = drops[i]
        d[3] += 30 * dt
        d[0] += d[2] * dt
        d[1] += d[3] * dt
        x, y = int(d[0]), int(d[1])
        if not (0 <= x < 16) or (d[3] > 0 and y >= surface(x)):
            drops.pop(i)
            continue
        if y >= 0:
            g.set_pen(PENS[12])
            g.pixel(x, y)
        i += 1
    return FRAME
