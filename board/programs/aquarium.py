# Aquarium: a little tank seen through the glass, the water's surface
# glinting at the top. Fish of different colours and sizes swim back and forth, bobbing gently
# and turning round naturally (they slow, turn edge-on and swim off the other
# way). Bubbles rise from a bubbler on a rock, seaweed sways in front of and
# behind the fish, soft light ripples through the water over a sandy bottom,
# and every so often a slow jellyfish pulses up from below.
#   A = add a fish (up to MAX_FISH)
#
# Memory-friendly: sprites, sand and water pens are made once in setup();
# bubbles live in a fixed pool of bytearrays/lists; fish are small lists made
# only at start or when one is added; nothing is built per frame.
import math
import random
from stellar import StellarUnicorn

FISH = 3             # fish in the tank at the start
MAX_FISH = 6         # A adds fish up to this many
SPEED = 1.0          # how fast the fish swim
BUBBLES = 1.5        # bubbles a second from the bubbler (they come in little bursts)
SWAY = 1.0           # how far the seaweed sways (0 = still)
SHIMMER = 1.0        # light rippling through the water (0 = still water)
JELLY_S = (50, 140)  # seconds between jellyfish (min, max)

FRAME = 0.04
POOL = 24            # most bubbles at once
TURN_S = 0.8         # seconds a fish takes to turn round
SURF = 1             # the water's surface row (air above it)

# sprites facing right, tail first: B body, S stripe, T tail, F fin, E eye
KINDS = (
    (("TBB",), (3.0, 5.0)),                            # little darter
    (("TBSBB",), (2.2, 3.5)),                          # slim tetra
    (("TSBE", "TSBB"), (1.8, 3.0)),                    # chunky
    ((".FB.", "TBBE", ".FB."), (1.2, 2.2)),            # angel / disc
    (("T.FF..", ".BSBEB", "T.SBB."), (1.0, 1.8)),      # big one
)
KIND_PICK = (0, 1, 1, 2, 2, 3, 3, 4, 4)
# body, stripe, tail, fin
PALS = (
    ((220, 85, 10), (160, 150, 140), (150, 50, 5), (120, 40, 5)),      # orange and white
    ((215, 165, 20), (240, 205, 90), (150, 105, 10), (130, 85, 10)),   # gold
    ((20, 90, 200), (200, 20, 30), (10, 50, 120), (10, 40, 110)),      # neon
    ((200, 30, 30), (240, 120, 90), (120, 15, 15), (100, 10, 20)),     # red
    ((130, 40, 170), (220, 180, 40), (210, 170, 30), (90, 30, 120)),   # purple and yellow
    ((30, 170, 175), (190, 230, 220), (15, 100, 110), (10, 80, 95)),   # teal
    ((220, 90, 140), (250, 170, 190), (150, 50, 90), (120, 40, 80)),   # pink
    ((120, 150, 180), (60, 80, 120), (80, 100, 130), (60, 70, 100)),   # silver
)
# jellyfish (dx, dy, 0 rim / 1 bell / 2 tentacle): pulsing, then gliding with tentacles swaying
JELLY = (((0, 0, 1), (-1, 1, 0), (0, 1, 1), (1, 1, 0), (-1, 2, 2), (1, 2, 2), (-1, 3, 2), (1, 3, 2), (0, 4, 2)),
         ((-1, 0, 0), (0, 0, 1), (1, 0, 0), (-1, 1, 1), (0, 1, 1), (1, 1, 1), (-1, 2, 2), (1, 2, 2), (-1, 3, 2), (1, 3, 2)),
         ((-1, 0, 0), (0, 0, 1), (1, 0, 0), (-1, 1, 1), (0, 1, 1), (1, 1, 1), (-1, 2, 2), (1, 2, 2), (0, 3, 2), (0, 4, 2)))
WATER_TOP = (0, 30, 62)
WATER_LOW = (0, 9, 28)


def setup(su, g):
    global W, H, AIRP, SURFP, SANDY, FLOOR, sandpix, WATERP, SANDP, ROCKP, BUBP, EYEP, FISHP, SPR, WEEDP, JELLYP
    global weeds, fish, bx, by, bph, bon, bub_acc, BUBX, BUBY, S1, S2, tick
    global jon, jx, jy, jph, next_jelly, a_was
    W, H = su.WIDTH, su.HEIGHT
    # ---- sand: one or two rows with gentle dunes, a few pebbles ----
    FLOOR = bytearray(W)              # first sand row in each column
    p = random.uniform(0, 6.28)
    for x in range(W):
        FLOOR[x] = H - 3 if math.sin(x * 0.5 + p) + 0.5 * math.sin(x * 1.1 + 2 * p) > 0.5 else H - 2
    SANDY = min(FLOOR)
    SANDP = [g.create_pen(*c) for c in ((95, 75, 42), (80, 62, 36), (112, 90, 54),
                                         (70, 70, 78), (110, 58, 38), (58, 82, 72))]
    sandpix = bytearray(W * H)
    for x in range(W):
        for y in range(FLOOR[x], H):
            r = random.random()
            sandpix[y * W + x] = 3 + random.randrange(3) if r < 0.06 else random.choice((0, 0, 0, 1, 2))
    # ---- the bubbler: a small rock with a stone on top ----
    BUBX = random.randint(3, W - 4)
    ROCKP = (g.create_pen(52, 56, 64), g.create_pen(34, 37, 46))
    BUBY = FLOOR[BUBX] - 2
    # ---- water pens: four light levels per row, the ripples fading with depth ----
    WATERP = []
    for y in range(H):
        f = max(0, y - SURF) / (H - 1 - SURF)
        base = [WATER_TOP[k] + (WATER_LOW[k] - WATER_TOP[k]) * f for k in range(3)]
        lift = (1 - f) * 0.8 + 0.2
        for lv in range(4):
            a = lv * lift
            WATERP.append(g.create_pen(int(base[0] + 6 * a), int(base[1] + 14 * a), int(base[2] + 16 * a)))
    S1 = bytearray(64)
    S2 = bytearray(64)
    for i in range(64):
        v = math.sin(i * 6.283185 / 64)
        S1[i] = 2 if v > 0.92 else (1 if v > 0.6 else 0)
        S2[i] = 1 if v > 0.75 else 0
    # ---- fish pens and sprites ----
    EYEP = g.create_pen(8, 8, 14)
    FISHP = [[g.create_pen(*c) for c in pal] for pal in PALS]
    SPR = []
    for rows, _ in KINDS:
        w = len(rows[0])
        pts = []
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                if ch != ".":
                    pts.append((dx - (w - 1) / 2, dy, "BSTFE".index(ch)))
        SPR.append((pts, w, len(rows)))
    # ---- seaweed: [x, height, phase, front?, leafy?, colour] ----
    WEEDP = ([g.create_pen(8 + k * 2, 40 + k * 6, 22 + k) for k in range(10)],        # behind: deep green
             [g.create_pen(6 + k, 34 + k * 5, 34 + k * 4) for k in range(10)],         # behind: sea green
             [g.create_pen(16 + k * 3, 80 + k * 9, 30 + k * 2) for k in range(10)],    # in front: green
             [g.create_pen(50 + k * 5, 70 + k * 7, 15 + k) for k in range(10)])        # in front: olive
    weeds = []
    x = random.randint(1, 4)
    while x < W - 1:
        if abs(x - BUBX) > 1:
            weeds.append([x, random.randint(4, H - 6), random.uniform(0, 6.28),
                          random.random() < 0.4, random.random() < 0.5, random.getrandbits(1)])
        x += random.randint(3, 6)
    BUBP = (g.create_pen(60, 120, 160), g.create_pen(110, 180, 220))
    AIRP = g.create_pen(3, 5, 10)
    SURFP = [g.create_pen(20 + 25 * v, 70 + 35 * v, 100 + 35 * v) for v in range(4)]
    JELLYP = (g.create_pen(70, 30, 95), g.create_pen(175, 75, 175), g.create_pen(55, 28, 85))
    bx = [0.0] * POOL
    by = [0.0] * POOL
    bph = [0.0] * POOL
    bon = bytearray(POOL)
    bub_acc = 0.0
    fish = []
    for _ in range(min(FISH, MAX_FISH)):
        add_fish(False)
    tick = 0
    jon = False
    jx = jy = jph = 0.0
    next_jelly = random.uniform(15, 40)
    a_was = False


def add_fish(enter):
    k = random.choice(KIND_PICK)
    w, h = SPR[k][1], SPR[k][2]
    lo, hi = KINDS[k][1]
    d = random.choice((-1, 1))
    if enter:                         # swims in from the side
        x = -w if d > 0 else W + w
    else:
        x = random.uniform(w, W - w)
    y = random.uniform(SURF + 1, SANDY - h)
    # [x, y, target y, facing, turn progress (-1 = not turning), speed, target speed,
    #  kind, pens, bob phase, speed range]
    fish.append([x, y, y, d, -1.0, random.uniform(lo, hi), random.uniform(lo, hi), k,
                 FISHP[random.randrange(len(PALS))], random.uniform(0, 6.28), lo, hi])


def rnd(v):
    return int(v + 100.5) - 100


def frame(su, g, t):
    global bub_acc, tick, jon, jx, jy, jph, next_jelly, a_was
    tick += 1
    dt = FRAME
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was and len(fish) < MAX_FISH:
        add_fish(True)
    a_was = a

    # ---- water with rippling light ----
    k1 = int(tick * SHIMMER)
    k2 = int(tick * SHIMMER * 0.7)
    for y in range(H):
        row = y * 4
        for x in range(W):
            if y >= FLOOR[x]:
                g.set_pen(SANDP[sandpix[y * W + x]])
            elif y < SURF:
                g.set_pen(AIRP)
            elif y == SURF:
                g.set_pen(SURFP[S1[(x * 5 + k1) & 63] + S2[(x * 3 - k2) & 63]])
            else:
                lv = S1[(x * 3 + y * 2 - k1) & 63] + S2[(x * 2 - y * 3 + k2) & 63] if SHIMMER else 0
                g.set_pen(WATERP[row + (lv if lv < 4 else 3)])
            g.pixel(x, y)
    # the bubbler rock
    g.set_pen(ROCKP[1])
    g.rectangle(BUBX - 2, FLOOR[BUBX] - 1, 5, 1)
    g.set_pen(ROCKP[0])
    g.rectangle(BUBX - 1, FLOOR[BUBX] - 1, 3, 1)
    g.pixel(BUBX, FLOOR[BUBX] - 2)

    # ---- seaweed behind ----
    draw_weeds(g, t, False)

    # ---- jellyfish ----
    if not jon and t >= next_jelly:
        jon = True
        jx = random.uniform(3, W - 4)
        jy = H + 1.0
        jph = random.random()
    if jon:
        jph += dt * 0.55
        p = jph % 1.0
        squeeze = p < 0.25
        jy -= (1.6 if squeeze else 0.35) * dt * (2 if p < 0.12 else 1)
        jx += 0.25 * math.sin(jph * 1.3) * dt
        cx = rnd(jx)
        cy = rnd(jy)
        draw_jelly(g, cx, cy, squeeze, tick)
        if jy < -6:
            jon = False
            next_jelly = t + random.uniform(*JELLY_S)

    # ---- fish ----
    for f in fish:
        spr = SPR[f[7]]
        w = spr[1]
        h = spr[2]
        # cruise speed wanders now and then
        if random.random() < dt / 4:
            f[6] = random.uniform(f[10], f[11])
        f[5] += (f[6] - f[5]) * dt
        sp = f[5] * SPEED
        tp = f[4]
        if tp >= 0:
            tp += dt / TURN_S
            if tp >= 1:
                tp = -1.0
                f[3] = -f[3]
        if tp >= 0:
            c = math.cos(3.141593 * tp)
            vel = f[3] * sp * c
            m = f[3] * c
        else:
            vel = f[3] * sp
            m = f[3]
            half = w / 2 + 0.6
            x = f[0]
            if (f[3] > 0 and W - half < x < W + 1) or (f[3] < 0 and -1 < x < half) \
                    or (half < x < W - half and random.random() < dt / 18) \
                    or (f[3] > 0 and x > W + w + 1) or (f[3] < 0 and x < -w - 1):
                tp = 0.0
        f[4] = tp
        f[0] += vel * dt
        # up and down: drift towards a chosen depth, with a gentle bob
        if abs(f[2] - f[1]) < 0.2 or random.random() < dt / 7:
            f[2] = random.uniform(SURF + 1, SANDY - h)
        f[1] += (f[2] - f[1]) * 0.5 * dt
        yy = f[1] + 0.35 * math.sin(t * 2.2 + f[9])
        pens = f[8]
        for dx, dy, role in spr[0]:
            px = rnd(f[0] + dx * m)
            py = rnd(yy) + dy
            if 0 <= px < W and 0 <= py < H:
                g.set_pen(EYEP if role == 4 else pens[role])
                g.pixel(px, py)

    # ---- bubbles ----
    bub_acc += BUBBLES * dt * (1.9 if math.sin(t * 1.3) > 0.2 else 0.1)
    while bub_acc >= 1:
        bub_acc -= 1
        for i in range(POOL):
            if not bon[i]:
                bon[i] = 1
                bx[i] = BUBX + random.uniform(-0.3, 0.3)
                by[i] = BUBY
                bph[i] = random.uniform(0, 6.28)
                break
    for i in range(POOL):
        if bon[i]:
            by[i] -= (3.2 + (BUBY - by[i]) * 0.3) * dt
            if by[i] < SURF + 0.5:
                bon[i] = 0
                continue
            g.set_pen(BUBP[i & 1])
            g.pixel(rnd(bx[i] + 0.6 * math.sin(t * 5 + bph[i])), rnd(by[i]))

    # ---- seaweed in front ----
    draw_weeds(g, t, True)
    return FRAME


def draw_weeds(g, t, front):
    for wd in weeds:
        if wd[3] != front:
            continue
        pens = WEEDP[(2 if front else 0) + wd[5]]
        x0 = wd[0]
        h = wd[1]
        base = FLOOR[x0] - 1
        for k in range(h):
            f = (k + 1) / h
            off = rnd(SWAY * 1.3 * f * math.sin(t * 0.9 + wd[2] - k * 0.35))
            px = x0 + off
            py = base - k
            if py < 0:
                break
            g.set_pen(pens[k * 9 // h])
            g.pixel(px, py)
            if wd[4] and k % 3 == 1 and k < h - 1:
                g.pixel(px + (1 if k % 6 == 1 else -1), py)


def draw_jelly(g, cx, cy, squeeze, tick):
    wig = (tick >> 3) & 1
    for dx, dy, r in JELLY[0 if squeeze else 1 + wig]:
        px = cx + dx
        py = cy + dy
        if 0 <= px < W and SURF < py < H:     # it slips away under the surface
            g.set_pen(JELLYP[r])
            g.pixel(px, py)
