# Spaceship: a little ship cruises through space, engine flickering, while
# stars stream past in three layers. Huge things drift by slowly in the
# background: a blazing sun, banded gas giants, ringed planets, icy worlds and
# cratered rocks, each in its own colours and sometimes with moons of its own.
# Everything behind the ship is muted, and the ship has a thin dark outline,
# so it stands out. The ship drifts forwards and backwards, and when an
# asteroid tumbles in it picks a clear lane and swerves into it (if one ever
# does clip it, its shield flashes).
#   A = send an asteroid   B = next planet
#
# Memory-friendly: each planet is drawn into a small bytearray mask once when
# it appears; asteroids come from a fixed pool; positions are integers
# (1/256 of a pixel); nothing is allocated per frame.
import math
import random
from stellar import StellarUnicorn

SPEED = 1.0          # overall flying speed (stars, asteroids, planets)
ASTEROID_S = (2.5, 7.0)  # seconds between asteroids (min, max)
AIMED = 0.45         # chance an asteroid comes straight at the ship
ROCK_SPEED = (3.0, 7.0)  # asteroid speed, pixels a second (min, max)
PLANET_SPEED = 0.3   # how fast planets drift by, pixels a second
GAP_S = (4, 14)      # seconds of open space between planets (min, max)
DODGE_SPEED = 7.0    # how fast the ship swerves, pixels a second
DRIFT = (2, 8)       # how far back and forward the ship wanders (its left edge, px)
DRIFT_SPEED = 0.8    # how fast it drifts forwards and backwards, pixels a second
LOOKAHEAD = 12       # how far ahead the ship watches for asteroids (px)
BACKDROP = 0.3       # brightness of everything behind the ship: stars, suns, planets (0..1)
MUTE = 0.55          # how much colour is drained from the backdrop (0 = full colour, 1 = grey)
OUTLINE = 1          # 1 = a thin dark outline around the ship so it pops, 0 = none
FRAME = 0.04

# star layers: (count, speed in px/s, brightness 0..255)
LAYERS = ((10, 0.7, 60), (8, 2.0, 120), (5, 5.0, 230))
PLANETS = ("gas", "ringed", "ice", "moon", "gas", "moon")   # one round between suns, shuffled

def setup(su, g):
    global BLACK, STARPEN, ROCK, HULL, WING, COCKPIT, COCKPIT2, NOSE, FLAME, SHIELD
    global stars, rocks, ship_x, ship_y, target_x, target_y, cruise_y, next_cruise, next_drift, dodge
    global last_threat, shield, a_was, b_was
    global body, body_x, next_body, order, next_rock, last_t
    BLACK = g.create_pen(0, 0, 0)
    STARPEN = [g.create_pen(*muted((b, b, min(255, b + 30)))) for _, _, b in LAYERS]
    ROCK = (g.create_pen(60, 48, 40), g.create_pen(110, 92, 75), g.create_pen(170, 150, 125))
    HULL = (g.create_pen(175, 180, 200), g.create_pen(255, 255, 255))
    WING = g.create_pen(255, 25, 40)
    COCKPIT = g.create_pen(80, 245, 255)
    COCKPIT2 = g.create_pen(30, 150, 215)
    NOSE = g.create_pen(255, 255, 255)
    FLAME = (g.create_pen(255, 230, 120), g.create_pen(255, 130, 20), g.create_pen(150, 40, 0))
    SHIELD = g.create_pen(120, 200, 255)
    stars = []
    for li, (n, sp, b) in enumerate(LAYERS):
        for _ in range(n):
            stars.append([random.randrange(16 << 8), random.randrange(16), li])
    rocks = [[0, 0, 0, 0, False] for _ in range(6)]   # x, y, speed, size, alive
    ship_y = target_y = cruise_y = 7 << 8
    ship_x = target_x = 3 << 8
    next_drift = 2.0
    dodge = None
    last_threat = 0.0
    next_cruise = 3.0
    shield = 0
    a_was = b_was = False
    order = []
    body = None
    body_x = 0
    next_body = 0.5
    next_rock = 3.0
    last_t = 0.0
    new_body("sun", g)

# ---------------------------------------------------------------- planets
def muted(c):
    """Backdrop colours: a little greyer and dimmer, so the ship stands out."""
    grey = (c[0] + c[1] + c[2]) / 3
    return tuple(int((v + (grey - v) * MUTE) * BACKDROP) for v in c)

def shade(c, f):
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f))

# colour schemes: every planet that drifts by picks one at random
GAS = (((215, 170, 110), (240, 215, 170), (200, 120, 70), (230, 190, 130), (170, 100, 60)),   # tan
       ((60, 110, 220), (90, 150, 240), (50, 80, 180), (120, 170, 245)),                       # deep blue
       ((150, 90, 200), (190, 140, 230), (110, 60, 170), (210, 170, 240)),                      # violet
       ((60, 180, 160), (110, 215, 190), (40, 130, 120), (150, 230, 205)),                      # teal
       ((220, 120, 140), (240, 170, 180), (180, 80, 110), (250, 200, 205)),                     # rose
       ((230, 200, 80), (245, 225, 140), (200, 150, 50)))                                      # gold
RINGS = ((230, 205, 150), (200, 220, 240), (240, 180, 200), (180, 240, 220), (220, 220, 220))
ICE = (((170, 215, 255), (200, 230, 255)), ((170, 255, 220), (210, 255, 235)),
       ((210, 190, 255), (230, 215, 255)), ((200, 240, 255), (235, 250, 255)))
ROCKY = ((150, 145, 140), (200, 95, 60), (190, 160, 90), (120, 150, 110), (170, 120, 170), (110, 120, 150))
MOONS = ((170, 165, 160), (215, 195, 150), (160, 190, 220), (200, 120, 90), (190, 180, 210))

def new_body(kind, g):
    """Draw a planet (and maybe its moons) into a mask: one pen index per pixel, 255 = empty."""
    global body, body_x, body_y, half, BPENS
    r = {"sun": 9, "gas": random.randint(5, 7), "ringed": random.randint(3, 5),
         "ice": random.randint(4, 6), "moon": random.randint(2, 4)}[kind]
    reach = r + (5 if kind == "ringed" else 2)
    # moons: one or two small ones nearby, each its own colour
    moons = []
    if kind != "sun":
        for _ in range(random.choice((0, 1, 1, 2))):
            a = random.uniform(0, 6.283)
            dist = r + random.uniform(2.5, 4.5) + (3 if kind == "ringed" else 0)
            mr = random.choice((1, 1, 1.6, 2))
            moons.append((math.cos(a) * dist, math.sin(a) * dist * 0.7, mr, random.choice(MOONS)))
            reach = max(reach, int(dist + mr + 1))
    half = reach
    w = 2 * half + 1
    mask = bytearray(b"\xff" * (w * w))
    pens = []
    cache = {}

    def pen(rgb):
        if rgb not in cache:
            cache[rgb] = len(pens)
            pens.append(g.create_pen(*muted(rgb)))
        return cache[rgb]

    if kind in ("gas", "ringed"):
        bands = random.choice(GAS)
    elif kind == "ice":
        bands = random.choice(ICE)
    else:
        bands = (random.choice(ROCKY),)
    ring = random.choice(RINGS)
    craters = [(random.uniform(-r + 1, r - 1), random.uniform(-r + 1, r - 1)) for _ in range(r)]
    tilt = random.uniform(-0.35, 0.35)
    for j in range(w):
        for i in range(w):
            dx, dy = i - half, j - half
            d = math.sqrt(dx * dx + dy * dy)
            k = j * w + i
            if kind == "sun":
                if d <= r:
                    f = d / r
                    c = (255, int(250 - 140 * f), int(200 - 190 * f))
                    if random.random() < 0.15:                   # granules
                        c = shade(c, 0.85)
                    mask[k] = pen(c)
                elif d <= r + 2:
                    f = 0.35 if d <= r + 1 else 0.14             # corona
                    mask[k] = pen(shade((255, 110, 20), f))
                continue
            # lit from the upper right, with a soft shadow on the far side
            light = 0.5 + 0.5 * (dx * 0.75 - dy * 0.55) / r
            light = 0.18 if light < 0.18 else (1.0 if light > 1.0 else light)
            if d <= r:
                if kind == "gas" or kind == "ringed":
                    c = bands[int((dy + r) * len(bands) / (2 * r + 1)) % len(bands)]
                elif kind == "ice":
                    c = (245, 250, 255) if dy < -r * 0.6 else bands[(i + j) % 2]
                else:
                    c = bands[0]
                    for cx, cy in craters:
                        if (dx - cx) ** 2 + (dy - cy) ** 2 < 0.8:
                            c = shade(bands[0], 0.65)
                mask[k] = pen(shade(c, light))
            if kind == "ringed":
                # a tilted ring; the half nearer to us is drawn over the planet
                rx = dx
                ry = dy - dx * tilt
                e = (rx / (r + 4.5)) ** 2 + (ry / 1.6) ** 2
                if 0.55 <= e <= 1.1 and (d > r or ry > 0):
                    mask[k] = pen(shade(ring, 0.45 + 0.4 * (dx + half) / w))
            for mx, my, mr, mc in moons:
                ex, ey = dx - mx, dy - my
                if ex * ex + ey * ey <= mr * mr + 0.3 and mask[k] == 255:
                    ml = 0.55 + 0.45 * (ex * 0.75 - ey * 0.55) / (mr + 0.5)
                    mask[k] = pen(shade(mc, 0.25 if ml < 0.25 else (1.0 if ml > 1.0 else ml)))
    body = (mask, w)
    BPENS = pens
    body_x = (16 + half) << 8
    body_y = random.randint(3, 12) if kind != "sun" else random.choice((3, 4, 11, 12))

def draw_body(g):
    mask, w = body
    bx = (body_x >> 8) - half
    by = body_y - half
    for j in range(w):
        y = by + j
        if y < 0 or y > 15:
            continue
        row = j * w
        for i in range(w):
            x = bx + i
            if 0 <= x < 16:
                p = mask[row + i]
                if p != 255:
                    g.set_pen(BPENS[p])
                    g.pixel(x, y)

# ---------------------------------------------------------------- asteroids
def send_rock(aimed):
    for r in rocks:
        if not r[4]:
            break
    else:
        return
    size = random.choice((1, 2, 2, 3))
    if aimed:
        y = (ship_y >> 8) + 1 - size // 2 + random.randint(-1, 1)
    else:
        y = random.randint(0, 15 - size + 1)
    r[0] = 17 << 8
    r[1] = max(0, min(16 - size, y))
    r[2] = int(random.uniform(*ROCK_SPEED) * SPEED * 256 / 25)   # per 1/25 s
    r[3] = size
    r[4] = True

def draw_rock(g, r):
    x = r[0] >> 8
    y = r[1]
    s = r[3]
    for j in range(s):
        for i in range(s):
            if s == 3 and (i + j == 0 or i + j == 4):     # round off the corners
                continue
            px = x + i
            if 0 <= px < 16:
                g.set_pen(ROCK[2] if i + j == 0 or (s == 3 and i + j == 1 and j == 0) else ROCK[1] if i + j < s else ROCK[0])
                g.pixel(px, y + j)

# ---------------------------------------------------------------- the ship
# A two-pixel-tall fighter seen from the side, top-left corner at (sx, sy):
#   fin  hull  cockpit cockpit
#   fin  hull  hull    hull    nose
SHAPE = ((0, 0), (1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (2, 1), (3, 1), (4, 1))
RIM = tuple((x + dx, y + dy) for x, y in SHAPE for dx in (-1, 0, 1) for dy in (-1, 0, 1)
            if (x + dx, y + dy) not in SHAPE)
RIM = tuple(sorted(set(RIM)))

def blocked(sx):
    """Rows (as bits) that asteroids ahead of the ship will pass through, plus a margin."""
    m = 0
    for r in rocks:
        if r[4]:
            rx = r[0] >> 8
            if rx + r[3] >= sx - 1 and rx <= sx + LOOKAHEAD:
                for row in range(r[1] - 1, r[1] + r[3] + 1):
                    if 0 <= row < 16:
                        m |= 1 << row
    return m

def free(m, y):
    return 0 <= y <= 14 and not (m >> y) & 3

def frame(su, g, t):
    global ship_x, ship_y, target_x, target_y, cruise_y, next_cruise, next_drift, dodge, last_threat, shield
    global a_was, b_was, body, body_x, next_body, next_rock, last_t, order
    dt = t - last_t
    if dt > 0.1:
        dt = 0.1          # after a pause, carry on instead of jumping ahead
    last_t = t
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    b = su.is_pressed(StellarUnicorn.SWITCH_B)
    if a and not a_was:
        send_rock(True)
    if b and not b_was:
        body = None
        next_body = t
    a_was, b_was = a, b

    # planets come and go
    if body is None and t >= next_body:
        if not order:
            order = list(PLANETS)
            for i in range(len(order) - 1, 0, -1):
                j = random.randrange(i + 1)
                order[i], order[j] = order[j], order[i]
            order.append("sun")                   # a sun after every round of planets
        new_body(order.pop(0), g)
    if body is not None:
        body_x -= int(PLANET_SPEED * SPEED * dt * 256) or 1
        if (body_x >> 8) < -half - 1:
            body = None
            next_body = t + random.uniform(*GAP_S)

    # asteroids
    if t >= next_rock:
        send_rock(random.random() < AIMED)
        next_rock = t + random.uniform(*ASTEROID_S)
    for r in rocks:
        if r[4]:
            r[0] -= int(r[2] * dt * 25)
            if r[0] < -(4 << 8):
                r[4] = False

    # drift forwards and backwards
    if t >= next_drift:
        target_x = random.randint(DRIFT[0], DRIFT[1]) << 8
        next_drift = t + random.uniform(3, 9)
    stepx = int(DRIFT_SPEED * dt * 256) or 1
    if ship_x < target_x:
        ship_x = min(target_x, ship_x + stepx)
    elif ship_x > target_x:
        ship_x = max(target_x, ship_x - stepx)
    sx = (ship_x + 128) >> 8

    # dodging: pick the nearest clear lane and stick with it until it's safe
    m = blocked(sx)
    sy = (ship_y + 128) >> 8
    if m:
        if dodge is None or not free(m, dodge):
            best = None
            for d in range(15):
                for y in (sy - d, sy + d):
                    if free(m, y) and 1 <= y <= 13:
                        best = y
                        break
                if best is not None:
                    break
            dodge = best if best is not None else sy
        target_y = dodge << 8
        last_threat = t
    elif dodge is not None and t - last_threat < 0.8:
        target_y = dodge << 8              # hold the lane a moment after it's clear
    else:
        dodge = None
        if t >= next_cruise:
            cruise_y = random.randint(3, 11) << 8
            next_cruise = t + random.uniform(3, 8)
        target_y = cruise_y + int(math.sin(t * 1.3) * 120)
    step = int(DODGE_SPEED * dt * 256) or 1
    if ship_y < target_y:
        ship_y = min(target_y, ship_y + step)
    elif ship_y > target_y:
        ship_y = max(target_y, ship_y - step)
    sy = (ship_y + 128) >> 8

    # did anything hit? (the shield takes it)
    for r in rocks:
        if r[4]:
            rx = r[0] >> 8
            if rx <= sx + 4 and rx + r[3] > sx and r[1] <= sy + 1 and r[1] + r[3] > sy:
                shield = 12
                r[4] = False

    # ---- draw ----
    g.set_pen(BLACK)
    g.clear()
    for s in stars:
        sp = LAYERS[s[2]][1]
        s[0] -= int(sp * SPEED * dt * 256) or 1
        if s[0] < 0:
            s[0] += 16 << 8
            s[1] = random.randrange(16)
        g.set_pen(STARPEN[s[2]])
        g.pixel(s[0] >> 8, s[1])
    if body is not None:
        draw_body(g)
    for r in rocks:
        if r[4]:
            draw_rock(g, r)
    # a dark outline keeps the backdrop off the ship
    if OUTLINE:
        g.set_pen(BLACK)
        for x, y in RIM:
            g.pixel(sx + x, sy + y)
    # engine flame flickers
    fl = random.getrandbits(2)
    g.set_pen(FLAME[0])
    g.pixel(sx - 1, sy + 1)
    if fl:
        g.set_pen(FLAME[1])
        g.pixel(sx - 2, sy + 1)
    if fl & 1:
        g.set_pen(FLAME[2])
        g.pixel(sx - 1, sy)
    if fl == 3:
        g.set_pen(FLAME[2])
        g.pixel(sx - 3, sy + 1)
    g.set_pen(WING)
    g.pixel(sx, sy)
    g.pixel(sx, sy + 1)
    g.set_pen(HULL[1])
    g.pixel(sx + 1, sy)
    g.pixel(sx + 2, sy + 1)
    g.pixel(sx + 3, sy + 1)
    g.set_pen(HULL[0])
    g.pixel(sx + 1, sy + 1)
    g.set_pen(COCKPIT)
    g.pixel(sx + 2, sy)
    g.set_pen(COCKPIT2)
    g.pixel(sx + 3, sy)
    g.set_pen(NOSE)
    g.pixel(sx + 4, sy + 1)
    if shield:
        shield -= 1
        if shield & 2:
            g.set_pen(SHIELD)
            for x, y in ((sx + 5, sy + 1), (sx + 4, sy), (sx + 2, sy - 1), (sx + 2, sy + 2),
                         (sx, sy - 1), (sx, sy + 2), (sx - 1, sy), (sx - 1, sy + 1)):
                g.pixel(x, y)
    return FRAME
