# Liquid metal: the board is a tank of liquid metal that sloshes hard from
# side to side under heavy gravity, slamming into the edges and climbing
# them, with a moving chrome sheen. The metal slowly shifts colour like
# heated titanium: deep blue, violet, magenta, gold, green, teal, with the
# highlights a step ahead of the body. Every so often an invisible hand
# scoops up a blob, carries it somewhere, and drops it back in with a splash
# that sends waves racing across the tank.
#   A = scoop up a blob now
#
# Memory-friendly: the pool is two integer arrays (height and speed per
# column), and the 16 pens are refreshed about eight times a second.
import math, random
from array import array
from stellar import StellarUnicorn

LEVEL = 5.0          # how deep the pool is at rest (pixels)
SLOSH = 0.14         # how fast the tank rocks (lower = lazier)
TILT = 5.5           # how hard it rocks (pixels of height difference)
WAIT = (6, 15)       # seconds between scoops (random in this range)
GRAVITY = 60         # how hard blobs and droplets fall (pixels/s^2)
LIFT_S = 1.0         # seconds to scoop a blob up
CARRY_S = 1.4        # seconds to carry it somewhere
SPRAY = 150          # how hard a wave must hit a wall to throw spray
COLOUR_S = 30         # seconds for the colours to go all the way round
SPEED = 2            # overall speed (1 = calm, 2 = twice as fast)
FRAME = 0.03

L, R = 0, 15         # the tank is the whole board; its walls are just past the edges
N = R - L + 1
FLOOR = 16
SH = 16              # number of shades
ONE = 256            # fixed point: 1 pixel = 256

def setup(su, g):
    global H, V, PENS, SPEC, BLACK, SINT, hit, mode, mode_t, next_scoop, pal_at
    global bx, by, bvy, br, tx, ty, ox, drops, a_was, lost, taken
    H = array("i", [int(LEVEL * ONE)] * 16)
    V = array("i", [0] * 16)
    BLACK = g.create_pen(0, 0, 0)
    PENS = [BLACK] * SH
    SPEC = BLACK
    pal_at = -99.0
    SINT = array("h", [int(127 * math.sin(2 * math.pi * i / 256)) for i in range(256)])
    hit = [0, 0]                                 # how recently each wall got slammed (0..7)
    mode, mode_t = "pool", 0.0
    next_scoop = random.uniform(3, 6)
    bx = by = bvy = br = tx = ty = ox = 0.0
    lost = taken = 0                             # pool volume carried by the blob (fixed point)
    drops = []                                   # droplets: [x, y, vx, vy] in pixels
    a_was = False

def hsv(h, s, v):
    h %= 1.0
    i = int(h * 6); f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i % 6]
    return int(r * 255), int(g * 255), int(b * 255)

def palette(g, t):
    # heated-titanium colours: deep body -> rich mid -> bright highlight, each
    # stop a little further round the colour wheel so the shine looks iridescent
    global SPEC
    h = 0.62 + t / COLOUR_S                    # starts at cool blue
    stops = (hsv(h, 0.95, 0.09), hsv(h + 0.03, 0.9, 0.35), hsv(h + 0.07, 0.85, 0.68),
             hsv(h + 0.13, 0.6, 0.92), hsv(h + 0.22, 0.18, 1.0))
    for k in range(SH):
        f = k / (SH - 1) * (len(stops) - 1)
        i = min(int(f), len(stops) - 2); q = f - i
        a, b = stops[i], stops[i + 1]
        PENS[k] = g.create_pen(int(a[0] + (b[0] - a[0]) * q), int(a[1] + (b[1] - a[1]) * q), int(a[2] + (b[2] - a[2]) * q))
    w = hsv(h + 0.3, 0.1, 1.0)
    SPEC = g.create_pen(*w)

def col(x):
    return L if x < L else R if x > R else int(x)

def surface(x):
    return FLOOR - H[x] / ONE                    # y of the pool surface in column x

def spray(x, n, vx_lo, vx_hi, up_lo, up_hi):
    c = col(x)
    for _ in range(n):
        drops.append([x + random.uniform(-0.4, 0.4), surface(c) - 0.5,
                      random.uniform(vx_lo, vx_hi), -random.uniform(up_lo, up_hi)])

def splash(x, size):
    c = col(x)
    for k in range(-2, 3):
        if L <= c + k <= R:
            V[c + k] -= int(size * (300 - 80 * abs(k)))
    spray(x, int(3 + size * 3), -4.5, 4.5, 6, 12)

def step_pool(t):
    # wave physics: each column is pulled by its neighbours (so bumps travel
    # as waves and bounce off the walls) and toward a rocking target shape
    total = 0
    for x in range(L, R + 1):
        total += H[x]
    mean = total // N
    tilt = math.sin(t * SLOSH * 2 * math.pi) + 0.35 * math.sin(t * SLOSH * 5.1 + 1.3)
    k = int(tilt * TILT * ONE / (N - 1))
    for x in range(L, R + 1):
        target = mean + k * (2 * x - L - R) // 2
        left = H[x - 1] if x > L else H[x]
        right = H[x + 1] if x < R else H[x]
        V[x] += ((left + right - 2 * H[x]) >> 1) + ((target - H[x]) >> 4)
        V[x] = V[x] * 62 >> 6                    # damping
    for x in range(L, R + 1):
        H[x] = max(ONE // 2, min(15 * ONE, H[x] + V[x] // 4))
    # keep the amount of metal exact (rounding would slowly drain the pool)
    total = 0
    for x in range(L, R + 1):
        total += H[x]
    fix = (int(LEVEL * ONE) * N - taken - total) // N
    for x in range(L, R + 1):
        H[x] += fix
    # a wave slamming into an edge climbs it and throws spray back off it
    for side, x, away in ((0, L, 1), (1, R, -1)):
        if V[x] > SPRAY and H[x] > H[x + away]:
            hit[side] = 7
            if random.getrandbits(2) == 0:
                spray(x + 0.5 - 0.4 * away, 1 + random.getrandbits(1), 0.5 * away, 3.5 * away, 5, 10)
        elif hit[side]:
            hit[side] -= 1

def draw_pool(g, t):
    tt = int(t * 40)
    for x in range(L, R + 1):
        s = surface(x)
        top = int(s)
        frac = s - top                           # partly filled top pixel
        slope = (H[min(R, x + 1)] - H[max(L, x - 1)]) >> 6
        for y in range(max(0, top), FLOOR):
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
    for y in range(max(0, int(cy - r * stretch) - 1), min(FLOOR, int(cy + r * stretch) + 2)):
        dy = (y + 0.5 - cy) / stretch
        for x in range(max(L, int(cx - r) - 1), min(R + 1, int(cx + r) + 2)):
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
    global mode, mode_t, next_scoop, bx, by, bvy, br, tx, ty, ox, lost, taken, a_was, pal_at
    if t - pal_at > 0.12:
        palette(g, t)                            # colours keep their own pace
        pal_at = t
    t *= SPEED                                   # everything else runs SPEED times faster
    dt = FRAME * SPEED
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was and mode == "pool":
        next_scoop = t
    a_was = a

    # ---- the scoop / carry / drop cycle ----
    if mode == "pool" and t >= next_scoop:
        mode, mode_t = "lift", t
        ox = random.uniform(3.5, 11.5)
        bx, by = ox, surface(int(ox))
        br = random.uniform(1.7, 2.4)
        tx, ty = random.uniform(3.5, 11.5), random.uniform(2.5, 5.5)
        lost = int(math.pi * br * br * ONE)
        taken = 0
    p = t - mode_t
    if mode == "lift":                           # rises out of the pool, trailing a neck
        f = min(1.0, p / LIFT_S)
        e = f * f * (3 - 2 * f)
        want = int(lost * e)                     # pool volume taken so far
        per = (want - taken) // 16
        if per > 0:
            # most of it comes from under the blob, the rest from everywhere
            for x in range(L, R + 1):
                H[x] -= per // 2
            c = int(ox)
            for k in (-1, 0, 1):
                if L <= c + k <= R:
                    H[c + k] -= per * 16 // 6
            taken += per * 16
        by = surface(int(ox)) + (ty - surface(int(ox))) * e
        bx = ox
        if f >= 1:
            mode, mode_t = "carry", t
    elif mode == "carry":                        # drifts over to a new spot, wobbling
        f = min(1.0, p / CARRY_S)
        e = f * f * (3 - 2 * f)
        bx = ox + (tx - ox) * e
        by = ty + 0.4 * math.sin(p * 7)
        if f >= 1:
            mode, mode_t, bvy = "fall", t, 0.0
    elif mode == "fall":                         # dropped: falls and splashes in
        bvy += GRAVITY * dt
        by += bvy * dt
        if by + br * 0.6 >= surface(col(bx)):
            c = col(bx)
            for k in (-1, 0, 1):                 # lands in a heap that spreads out as waves
                if L <= c + k <= R:
                    H[c + k] += taken // 3
            taken = 0
            splash(bx, br / 2)
            mode = "pool"
            next_scoop = t + random.uniform(*WAIT)

    for _ in range(SPEED):
        step_pool(t)

    # ---- draw ----
    g.set_pen(BLACK)
    g.clear()
    draw_pool(g, t)
    if mode == "lift":
        f = min(1.0, (t - mode_t) / LIFT_S)
        s = surface(int(ox))
        if f < 0.75:                             # the neck of liquid still attached to the pool
            w = (1 - f / 0.75) * br * 0.9
            for y in range(max(0, int(by)), min(FLOOR, int(s) + 1)):
                for x in range(int(ox - w), int(ox + w) + 1):
                    if L <= x <= R:
                        g.set_pen(PENS[7 + (x == int(ox))])
                        g.pixel(x, y)
        draw_blob(g, bx, by, br * (0.5 + 0.5 * f))
    elif mode == "carry":
        draw_blob(g, bx, by, br, 1.0 + 0.12 * math.sin((t - mode_t) * 12))
    elif mode == "fall":
        draw_blob(g, bx, by, br, 1.0 + min(0.35, bvy * 0.02))

    # ---- droplets: fly, bounce off the walls, fall back in ----
    i = 0
    while i < len(drops):
        d = drops[i]
        d[3] += GRAVITY * dt
        d[0] += d[2] * dt
        d[1] += d[3] * dt
        if d[0] < L:                         # bounce off the edges of the board
            d[0], d[2] = L + 0.01, -d[2] * 0.5
        elif d[0] >= R + 1:
            d[0], d[2] = R + 0.99, -d[2] * 0.5
        x, y = int(d[0]), int(d[1])
        if d[3] > 0 and y >= surface(x):
            drops.pop(i)
            continue
        if y >= 0:
            g.set_pen(PENS[12])
            g.pixel(x, y)
        i += 1
    return FRAME
