# Paper Planes: a loose flock of folded paper planes glides across a long
# dusk sky, deep night blue overhead fading to a violet glow on the horizon,
# with a few stars and slow drifting clouds. The planes bob on the air, and
# now and then one pulls up into a loop or dips into a swoop. Near planes are
# bigger, brighter and quicker; far ones small and dim, and slip behind clouds.
# (Galactic Unicorn version: a wide panorama, planes 3-5 px long.)
#   A = launch another plane
#
# Memory-friendly: every pen is made once in setup(); plane sprites (each
# size at 32 headings) are drawn on demand into small bytes objects and
# cached, and planes and clouds are small lists reused for the whole run.
import math
import random
from galactic import GalacticUnicorn

PLANES = 7           # planes in the flock at the start
MAX_PLANES = 14      # most planes A can add up to
SPEED = 7.0          # flying speed of the nearest planes, pixels a second
GLIDE = 10           # glide angle in degrees (0 = level, higher = steeper descent)
STUNT_S = (8, 25)    # seconds between loops/swoops for each plane (min, max)
BOB = 0.25           # how much the planes bob on the air (0 = steady)
CLOUDS = 3           # drifting clouds
CLOUD_SPEED = 0.6    # cloud drift, pixels a second
FRAME = 0.04

HEADINGS = 32
SIZES = (3, 4, 5)            # sprite length for far, middle and near planes
DEPTH_BRIGHT = (0.55, 0.78, 1.0)
DEPTH_SPEED = (0.6, 0.8, 1.0)
MARGIN = 5                   # planes wrap this far off the left/right edges
VMARGIN = 3                  # and this far off the top/bottom
TINTS = ((235, 235, 245), (250, 212, 222), (205, 222, 255), (250, 238, 200), (212, 248, 228))
SHADE = (1.0, 0.72, 0.48)    # wing, keel, fold line
COVER = (0.55, 0.8, 1.0)    # partly covered edge pixels are dimmer
TAU = 6.283185307179586

# sky colour stops, top to bottom
SKY_TOP = (2, 3, 16)
SKY_MID = (14, 8, 36)
SKY_LOW = (46, 14, 40)

def setup(su, g):
    global W, H, SKY, CLOUDPEN, STARPEN, PEN, cache, planes, clouds, stars, a_was, frames
    W, H = su.WIDTH, su.HEIGHT
    SKY = []
    sky_rgb = []
    for y in range(H):
        f = y / (H - 1)
        if f < 0.6:
            k = f / 0.6
            c = [SKY_TOP[i] + (SKY_MID[i] - SKY_TOP[i]) * k for i in range(3)]
        else:
            k = (f - 0.6) / 0.4
            c = [SKY_MID[i] + (SKY_LOW[i] - SKY_MID[i]) * k * k for i in range(3)]
        sky_rgb.append(c)
        SKY.append(g.create_pen(int(c[0]), int(c[1]), int(c[2])))
    # clouds: a dusky lilac lit faintly from below, edge and body pens per row
    CLOUDPEN = []
    for y in range(H):
        c = sky_rgb[y]
        lift = 0.6 + 0.6 * y / (H - 1)
        CLOUDPEN.append((g.create_pen(int(c[0] + 11 * lift), int(c[1] + 9 * lift), int(c[2] + 14 * lift)),
                         g.create_pen(int(c[0] + 24 * lift), int(c[1] + 19 * lift), int(c[2] + 26 * lift))))
    STARPEN = [g.create_pen(10 * v, 11 * v, 14 * v) for v in range(16)]
    # plane pens: tint x depth x shade x coverage
    PEN = []
    for r, gg, b in TINTS:
        for d in range(3):
            for s in range(3):
                for c in range(3):
                    m = DEPTH_BRIGHT[d] * SHADE[s] * COVER[c]
                    PEN.append(g.create_pen(int(r * m), int(gg * m), int(b * m)))
    cache = {}
    planes = []
    for i in range(PLANES):
        planes.append(new_plane(random.uniform(-MARGIN, W + MARGIN), i % 3))
    planes.sort(key=lambda p: p[3])
    clouds = []
    for i in range(CLOUDS):
        clouds.append(new_cloud(random.uniform(0, W)))
    stars = []
    for i in range(12):
        y = random.randrange(0, H // 2 + 1)
        stars.append((random.randrange(W), y, random.randrange(64), 15 - y * 2))
    a_was = False
    frames = 0

def new_plane(x, depth=None):
    # [x, y, heading phase, depth, tint, bob phase, bob rate, stunt kind,
    #  stunt time, stunt length, next stunt countdown]
    if depth is None:
        depth = random.randrange(3)
    return [x, random.uniform(0, H), 0.0, depth, random.randrange(len(TINTS)),
            random.uniform(0, TAU), random.uniform(1.1, 1.9), 0, 0.0, 1.0,
            random.uniform(STUNT_S[0] * 0.3, STUNT_S[1])]

def new_cloud(x):
    w = random.randint(7, 13)
    top = random.randint(2, w - 3)
    off = random.randint(1, w - top - 1)
    spans = [(0, off, off + top)]                 # the puffy top
    spans.append((1, 0, w))                       # the long body
    if random.getrandbits(1):
        a = random.randint(1, w // 3)
        spans.append((2, a, w - random.randint(1, w // 3)))   # a flat base
    return [x, random.randint(1, H - 5), random.uniform(0.6, 1.3), w, spans]

# ---- plane sprites ----
# each size drawn by hand flying level to the right (W = wing, F = the
# darker fold line, K = keel); the other headings are rotated from these.
SHAPES = {
    3: ("WW ",
        "FFW"),
    4: ("WW  ",
        "FFFW",
        " K  "),
    5: ("W    ",
        "WWW  ",
        "FFFFW",
        " KK  "),
}
SHADE_OF = {"W": 0, "K": 1, "F": 2}

def sprite(size, h):
    """bytes of (dx + 8, dy + 8, shade * 3 + cover) for one size and heading."""
    key = size * HEADINGS + h
    s = cache.get(key)
    if s is not None:
        return s
    rows = SHAPES[size]
    bw = len(rows[0])
    bh = len(rows)
    cw = bw // 2 + 0.5
    ch = bh // 2 + 0.5
    a = h * TAU / HEADINGS
    ca = math.cos(a)
    sa = math.sin(a)
    R = size // 2 + 2
    out = bytearray()
    for py in range(-R, R + 1):
        for px in range(-R, R + 1):
            cnt = [0, 0, 0]
            for sy in (-0.3, 0.0, 0.3):
                Y = py + sy
                for sx in (-0.3, 0.0, 0.3):
                    X = px + sx
                    j = int(math.floor(X * ca + Y * sa + cw))
                    i = int(math.floor(-X * sa + Y * ca + ch))
                    if 0 <= i < bh and 0 <= j < bw:
                        c = rows[i][j]
                        if c != " ":
                            cnt[SHADE_OF[c]] += 1
            n = cnt[0] + cnt[1] + cnt[2]
            if n < 3:
                continue
            sh = 0
            if cnt[1] > cnt[sh]:
                sh = 1
            if cnt[2] >= cnt[sh]:
                sh = 2
            cov = 0 if n < 5 else (1 if n < 8 else 2)
            out.append(px + 8)
            out.append(py + 8)
            out.append(sh * 3 + cov)
    s = bytes(out)
    cache[key] = s
    return s

def draw_plane(g, p, glide, t):
    d = p[3]
    ang = glide + BOB * math.sin(p[5] + t * p[6]) + p[2]
    h = int(ang * HEADINGS / TAU + 0.5) % HEADINGS
    spr = sprite(SIZES[d], h)
    cx = int(p[0] + 0.5)
    cy = int(p[1] + 0.5)
    base = (p[4] * 3 + d) * 9
    for i in range(0, len(spr), 3):
        x = cx + spr[i] - 8
        y = cy + spr[i + 1] - 8
        if 0 <= x < W and 0 <= y < H:
            g.set_pen(PEN[base + spr[i + 2]])
            g.pixel(x, y)
    return ang

def fly(p, glide, t, dt):
    # stunts: a loop turns the heading a full circle upwards; a swoop dips
    # down and pulls back up
    if p[7]:
        p[8] += dt
        u = p[8] / p[9]
        if u >= 1:
            p[7] = 0
            p[2] = 0.0
            p[10] = random.uniform(STUNT_S[0], STUNT_S[1])
        elif p[7] == 1:
            e = u * u * (3 - 2 * u)
            p[2] = -TAU * e
        else:
            p[2] = 0.75 * math.sin(TAU * u)
    else:
        p[10] -= dt
        if p[10] <= 0:
            p[7] = 1 if random.random() < 0.55 else 2
            p[8] = 0.0
            p[9] = random.uniform(1.8, 2.6) if p[7] == 1 else random.uniform(1.6, 2.4)
    sp = SPEED * DEPTH_SPEED[p[3]]
    ang = glide + BOB * math.sin(p[5] + t * p[6]) + p[2]
    p[0] += sp * math.cos(ang) * dt
    p[1] += sp * math.sin(ang) * dt
    if p[0] > W + MARGIN:
        p[0] -= W + 2 * MARGIN
        p[1] = random.uniform(-1, H - 1)      # come back in somewhere new
    elif p[0] < -MARGIN:
        p[0] += W + 2 * MARGIN
    if p[1] > H + VMARGIN:
        p[1] -= H + 2 * VMARGIN
    elif p[1] < -VMARGIN:
        p[1] += H + 2 * VMARGIN

def frame(su, g, t):
    global a_was, frames
    frames += 1
    glide = GLIDE * 0.017453292519943295
    a = su.is_pressed(GalacticUnicorn.SWITCH_A)
    if a and not a_was:
        if len(planes) < MAX_PLANES:
            p = new_plane(-MARGIN)
            planes.append(p)
            planes.sort(key=lambda q: q[3])
        else:
            p = planes[random.randrange(len(planes))]
            p[0] = -MARGIN
            p[1] = random.uniform(0, H)
        p[1] = random.uniform(1, H - 2)
    a_was = a

    # sky and stars
    for y in range(H):
        g.set_pen(SKY[y])
        g.pixel_span(0, y, W)
    for x, y, ph, top in stars:
        v = (frames + ph) & 63
        v = v if v < 32 else 63 - v
        v = (v * top) >> 5
        if v > 2:
            g.set_pen(STARPEN[v])
            g.pixel(x, y)

    # far planes, then clouds, then the nearer planes
    for p in planes:
        fly(p, glide, t, FRAME)
    for p in planes:
        if p[3] == 0:
            draw_plane(g, p, glide, t)
    for c in clouds:
        c[0] += CLOUD_SPEED * c[2] * FRAME
        if c[0] > W + 1:
            c[:] = new_cloud(-c[3] - random.randint(2, 15))
        cx = int(c[0])
        cy = c[1]
        for dy, x0, x1 in c[4]:
            y = cy + dy
            pens = CLOUDPEN[y]
            for x in range(x0, x1):
                px = cx + x
                if 0 <= px < W:
                    g.set_pen(pens[0] if (x == x0 or x == x1 - 1) else pens[1])
                    g.pixel(px, y)
    for p in planes:
        if p[3]:
            draw_plane(g, p, glide, t)
    return FRAME
