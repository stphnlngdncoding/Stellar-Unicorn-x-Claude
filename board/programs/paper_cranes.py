# Paper Cranes: a loose flock of folded origami cranes drifts on a slow
# diagonal across a dark starry sky, in pale paper colours (cream, pink,
# blue, mint, lavender). Each one flaps at its own pace, glides between
# bursts, bobs on the air, and now and then peels away, loops and rejoins.
# Far cranes are smaller, dimmer and slower. (Stellar version: 3-5 px cranes
# climbing a steeper diagonal through the little square window.)
#   A = fold another crane (up to MAX_CRANES)
#
# Memory-friendly: every pen is made once in setup(); the hand-drawn crane
# sprites (3 sizes x 3 wing frames, facing both ways) are unpacked once into
# small bytes objects, and the cranes and stars are small lists reused forever.
import math
import random
from stellar import StellarUnicorn

CRANES = 7           # cranes in the flock at the start
MAX_CRANES = 12      # most cranes A can add up to
SPEED = 2.4          # drift speed of the nearest cranes, pixels a second
CLIMB = 0.45         # diagonal: pixels of rise per pixel across (0 = level)
FLAP_HZ = 2.2        # average wingbeats a second
GLIDE_S = (1.5, 4.0) # seconds a glide lasts between flapping bursts (min, max)
LOOP_S = (10, 30)    # seconds between loops for each crane (min, max)
STARS = 12           # faint twinkling stars

SIZES = (3, 4, 5)            # sprite width for far, middle and near cranes
DEPTH_BRIGHT = (0.6, 0.78, 0.95)
DEPTH_HAZE = (0.4, 0.18, 0.0)   # far cranes fade toward the night haze colour
HAZE = (110, 125, 190)
DEPTH_SPEED = (0.5, 0.72, 1.0)
DEPTH_BOB = (0.3, 0.4, 0.55)
LOOP_LEN = (4.8, 6.2)        # seconds a loop takes
LOOP_ROOM = 9                # only loop when this far down the sky
MARGIN = 3                   # cranes wrap this far off the left/right edges
VMARGIN = 3                  # and this far off the top/bottom
TINTS = ((248, 236, 205), (252, 196, 210), (192, 214, 252), (190, 244, 212), (218, 200, 252))
SHADE = (0.8, 1.0, 0.5)      # body/neck/tail, near wing, far wing
FRAME = 0.04
TAU = 6.283185307179586

SKY_TOP = (1, 2, 10)
SKY_LOW = (8, 7, 26)

# Hand-drawn cranes flying right: b = body, neck and tail, n = near wing,
# d = far wing (darker). Row 3 is the body row in every frame (drawn 1 px below the crane's y).
# Frames: wings up, wings level, wings down.
SHAPES = {
    3: (("...", "n.d", ".bb"),
        ("...", "...", "nbb"),
        ("...", "...", ".bb", "n.d")),
    4: (("n...", ".nd.", "b.nb", ".bb."),
        ("....", "...b", "bndb", ".bb."),
        ("....", "...b", "b..b", ".db.", ".n..")),
    5: (("nd...", ".nd.b", "b..nb", ".bbb."),
        (".....", "....b", "b.d.b", ".bnb."),
        (".....", "....b", "b...b", ".bdb.", "..n..", ".n...")),
}
SHADE_OF = {"b": 0, "n": 1, "d": 2}
FLAP_SEQ = (0, 1, 2, 1)      # up, level, down, level

def setup(su, g):
    global W, H, SKY, STARPEN, PEN, SPR, cranes, stars, a_was, last_t
    W, H = su.WIDTH, su.HEIGHT
    SKY = []
    for y in range(H):
        f = (y / (H - 1)) ** 1.5
        SKY.append(g.create_pen(int(SKY_TOP[0] + (SKY_LOW[0] - SKY_TOP[0]) * f),
                                int(SKY_TOP[1] + (SKY_LOW[1] - SKY_TOP[1]) * f),
                                int(SKY_TOP[2] + (SKY_LOW[2] - SKY_TOP[2]) * f)))
    STARPEN = [g.create_pen(5 + 6 * v, 5 + 6 * v, 9 + 7 * v) for v in range(12)]
    PEN = []
    for r, gg, b in TINTS:
        for d in range(3):
            for s in range(3):
                m = DEPTH_BRIGHT[d] * SHADE[s]
                k = DEPTH_HAZE[d]
                PEN.append(g.create_pen(int((r + (HAZE[0] - r) * k) * m),
                                        int((gg + (HAZE[1] - gg) * k) * m),
                                        int((b + (HAZE[2] - b) * k) * m)))
    # SPR[depth][frame * 2 + flipped] = bytes of (dx + 8, dy + 8, shade)
    SPR = []
    for d in range(3):
        w = SIZES[d]
        lst = []
        for rows in SHAPES[w]:
            for flip in (0, 1):
                out = bytearray()
                for i in range(len(rows)):
                    row = rows[i]
                    for j in range(len(row)):
                        c = row[j]
                        if c != ".":
                            x = (w - 1 - j) if flip else j
                            out.append(x - w // 2 + 8)
                            out.append(i - 2 + 8)
                            out.append(SHADE_OF[c])
                lst.append(bytes(out))
        SPR.append(lst)
    global tint_next
    tint_next = random.randrange(len(TINTS))
    cranes = []
    for i in range(CRANES):
        # spread the starting flock along the diagonal so it begins loose
        k = (i + random.uniform(0.1, 0.9)) / CRANES
        c = new_crane(-MARGIN + k * (W + 2 * MARGIN), i % 3)
        c[1] = (k * 2.7 + random.uniform(0, 0.25)) % 1.0 * (H + 2 * VMARGIN) - VMARGIN
        cranes.append(c)
    cranes.sort(key=lambda c: c[2])
    stars = []
    for i in range(STARS):
        stars.append((random.randrange(W), random.randrange(H - 1),
                      random.uniform(0, TAU), random.uniform(0.4, 1.6), random.randint(4, 11)))
    a_was = False
    last_t = 0.0

def new_crane(x, depth=None):
    # [0 x, 1 y, 2 depth, 3 tint, 4 flap phase, 5 flap rate, 6 flapping?,
    #  7 state timer, 8 bob phase, 9 bob rate, 10 loop time (-1 = none),
    #  11 loop length, 12 next loop countdown, 13 lag behind the flock,
    #  14 own speed factor, 15 facing left?]
    if depth is None:
        depth = random.randrange(3)
    global tint_next
    tint_next = (tint_next + 1 + random.getrandbits(1)) % len(TINTS)
    return [x, random.uniform(-1, H), depth, tint_next,
            random.random(), random.uniform(0.75, 1.3), random.getrandbits(1),
            random.uniform(0.5, 3.0), random.uniform(0, TAU), random.uniform(0.7, 1.4),
            -1.0, 3.0, random.uniform(LOOP_S[0] * 0.3, LOOP_S[1]), 0.0,
            random.uniform(0.88, 1.12), 0]

def fly(c, dt, dirx, diry):
    v = SPEED * DEPTH_SPEED[c[2]] * c[14]
    # flapping and gliding spells
    c[7] -= dt
    if c[7] <= 0:
        if c[6]:
            c[6] = 0
            c[7] = random.uniform(GLIDE_S[0], GLIDE_S[1])
        else:
            c[6] = 1
            c[7] = random.uniform(1.0, 3.5)
            c[4] = 0.0
    if c[6] or c[10] >= 0:
        c[4] += FLAP_HZ * c[5] * dt * (1.6 if c[10] >= 0 else 1.0)
    if c[10] >= 0:
        # a loop: heading turns a full circle, climbing first, then rejoins
        c[10] += dt
        u = c[10] / c[11]
        if u >= 1:
            c[10] = -1.0
            c[15] = 0
            c[12] = random.uniform(LOOP_S[0], LOOP_S[1])
            ang = 0.0
        else:
            ang = TAU * u * u * (3 - 2 * u)
        ca = math.cos(ang)
        sa = math.sin(ang)
        # rotate the drift direction upwards (screen y points down)
        hx = dirx * ca + diry * sa
        hy = diry * ca - dirx * sa
        c[15] = 1 if hx < -0.15 else 0
        c[0] += hx * v * dt
        c[1] += hy * v * dt
        c[13] += v * dt * (1 - (hx * dirx + hy * diry))
    else:
        step = v * dt
        if c[13] > 0:                       # catch up with the flock after a loop
            extra = min(c[13], 0.4 * step)
            c[13] -= extra
            step += extra
        c[0] += dirx * step
        c[1] += diry * step + (-0.25 if c[6] else 0.25) * DEPTH_SPEED[c[2]] * dt
        c[12] -= dt
        if c[12] <= 0:
            if c[1] > LOOP_ROOM:            # a loop climbs; wait for headroom
                c[10] = 0.0
                c[11] = random.uniform(LOOP_LEN[0], LOOP_LEN[1])
            else:
                c[12] = random.uniform(1.0, 3.0)
    # wrap around the edges
    if c[0] > W + MARGIN:
        c[0] -= W + 2 * MARGIN
        c[1] += random.uniform(-3, 3)
    elif c[0] < -MARGIN:
        c[0] += W + 2 * MARGIN
    if c[1] < -VMARGIN:
        c[1] += H + 2 * VMARGIN
    elif c[1] > H + VMARGIN:
        c[1] -= H + 2 * VMARGIN

def spread(dt):
    # keep the flock loose: cranes that overlap drift apart vertically
    # (gently if they're at different depths, so near ones can still pass)
    n = len(cranes)
    for i in range(n):
        a = cranes[i]
        for j in range(i + 1, n):
            b = cranes[j]
            gap = (SIZES[a[2]] + SIZES[b[2]]) * 0.5 + 1
            dx = b[0] - a[0]
            dy = b[1] - a[1]
            if -gap < dx < gap and -5 < dy < 5:
                push = (1.2 if a[2] == b[2] else 0.6) * dt
                if dy < 0:
                    push = -push
                a[1] -= push
                b[1] += push

def draw_crane(g, c, t):
    d = c[2]
    if c[6] or c[10] >= 0:
        f = FLAP_SEQ[int(c[4] * 4) & 3]
    else:
        f = 0                               # glide with wings raised
    spr = SPR[d][f * 2 + c[15]]
    cx = int(math.floor(c[0] + 0.5))
    cy = int(math.floor(c[1] + DEPTH_BOB[d] * math.sin(c[8] + t * c[9]) + 0.5))
    base = (c[3] * 3 + d) * 3
    for i in range(0, len(spr), 3):
        x = cx + spr[i] - 8
        y = cy + spr[i + 1] - 8
        if 0 <= x < W and 0 <= y < H:
            g.set_pen(PEN[base + spr[i + 2]])
            g.pixel(x, y)

def frame(su, g, t):
    global a_was, last_t
    dt = t - last_t
    last_t = t
    if dt < 0 or dt > 0.2:
        dt = FRAME
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was and len(cranes) < MAX_CRANES:
        c = new_crane(-MARGIN + 1)
        c[1] = random.uniform(2, H + 2)
        cranes.append(c)
        cranes.sort(key=lambda q: q[2])
    a_was = a

    n = 1.0 / math.sqrt(1 + CLIMB * CLIMB)
    dirx = n
    diry = -CLIMB * n

    for y in range(H):
        g.set_pen(SKY[y])
        g.pixel_span(0, y, W)
    for x, y, ph, rate, top in stars:
        v = 0.5 + 0.5 * math.sin(ph + t * rate)
        v = int(top * v * v)
        if v > 1:
            g.set_pen(STARPEN[v])
            g.pixel(x, y)

    for c in cranes:
        fly(c, dt, dirx, diry)
    spread(dt)
    for c in cranes:                        # sorted far to near
        draw_crane(g, c, t)
    return FRAME
