# Spaceship: a little ship cruises through space, engine flickering, while
# stars stream past in three layers. Huge things drift by slowly in the
# background: a blazing sun, a banded gas giant, a ringed planet, an icy
# world, a cratered moon. Every so often an asteroid tumbles in and the ship
# swerves around it (if one ever does clip it, its shield flashes).
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
FRAME = 0.04

SHIP_X = 3
# star layers: (count, speed in px/s, brightness 0..255)
LAYERS = ((10, 0.7, 60), (8, 2.0, 120), (5, 5.0, 230))
KINDS = ("sun", "gas", "ringed", "ice", "moon")

def setup(su, g):
    global BLACK, STARPEN, ROCK, HULL, WING, COCKPIT, NOSE, FLAME, SHIELD
    global stars, rocks, ship_y, target_y, cruise_y, next_cruise, shield, a_was, b_was
    global body, body_x, next_body, order, next_rock, last_t
    BLACK = g.create_pen(0, 0, 0)
    STARPEN = [g.create_pen(b, b, min(255, b + 30)) for _, _, b in LAYERS]
    ROCK = (g.create_pen(60, 48, 40), g.create_pen(110, 92, 75), g.create_pen(170, 150, 125))
    HULL = (g.create_pen(150, 155, 170), g.create_pen(230, 235, 245))
    WING = g.create_pen(220, 40, 50)
    COCKPIT = g.create_pen(60, 220, 255)
    NOSE = g.create_pen(255, 255, 255)
    FLAME = (g.create_pen(255, 230, 120), g.create_pen(255, 130, 20), g.create_pen(150, 40, 0))
    SHIELD = g.create_pen(120, 200, 255)
    stars = []
    for li, (n, sp, b) in enumerate(LAYERS):
        for _ in range(n):
            stars.append([random.randrange(16 << 8), random.randrange(16), li])
    rocks = [[0, 0, 0, 0, False] for _ in range(6)]   # x, y, speed, size, alive
    ship_y = target_y = cruise_y = 8 << 8
    next_cruise = 3.0
    shield = 0
    a_was = b_was = False
    order = list(KINDS[1:]) + ["sun"]            # the sun comes round again every fifth
    body = None
    body_x = 0
    next_body = 0.5
    next_rock = 3.0
    last_t = 0.0
    new_body("sun", g)

# ---------------------------------------------------------------- planets
def shade(c, f):
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f))

def new_body(kind, g):
    """Draw a planet into a mask: one pen index per pixel, 255 = empty."""
    global body, body_x, body_y, half, BPENS
    r = {"sun": 9, "gas": 6, "ringed": 4, "ice": 5, "moon": 3}[kind]
    half = r + (5 if kind == "ringed" else 2)
    w = 2 * half + 1
    mask = bytearray(b"\xff" * (w * w))
    pens = []
    cache = {}

    def pen(rgb):
        if rgb not in cache:
            cache[rgb] = len(pens)
            pens.append(g.create_pen(*rgb))
        return cache[rgb]

    bands = {"gas": ((215, 170, 110), (240, 215, 170), (200, 120, 70), (230, 190, 130), (170, 100, 60)),
             "ringed": ((70, 170, 190), (110, 200, 210), (60, 130, 170)),
             "ice": ((170, 215, 255), (200, 230, 255)),
             "moon": ((150, 145, 140),)}.get(kind)
    craters = [(random.uniform(-2, 2), random.uniform(-2, 2)) for _ in range(3)]
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
                            c = (100, 95, 92)
                mask[k] = pen(shade(c, light))
            if kind == "ringed":
                # a tilted ring; the half nearer to us is drawn over the planet
                rx = dx
                ry = dy - dx * tilt
                e = (rx / (r + 4.5)) ** 2 + (ry / 1.6) ** 2
                if 0.55 <= e <= 1.1 and (d > r or ry > 0):
                    mask[k] = pen(shade((230, 205, 150), 0.45 + 0.4 * (dx + half) / w))
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
        y = (ship_y >> 8) - size // 2 + random.randint(-1, 1)
    else:
        y = random.randint(0, 15 - size + 1)
    r[0] = 17 << 8
    r[1] = max(0, min(16 - size, y))
    r[2] = int(random.uniform(*ROCK_SPEED) * SPEED * FRAME * 256)
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

# ---------------------------------------------------------------- frame
def frame(su, g, t):
    global ship_y, target_y, cruise_y, next_cruise, shield, a_was, b_was
    global body, body_x, next_body, next_rock, last_t
    dt = t - last_t
    if dt > 0.2:
        dt = 0.2
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
        kind = order.pop(0)
        order.append(kind)
        new_body(kind, g)
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
            r[0] -= r[2]
            if r[0] < -(4 << 8):
                r[4] = False

    # the ship looks ahead and swerves around anything in its lane
    sy = (ship_y + 128) >> 8
    danger = None
    for r in rocks:
        if r[4]:
            rx = r[0] >> 8
            if SHIP_X - 1 <= rx <= SHIP_X + 12 and r[1] - 2 <= sy <= r[1] + r[3] + 1:
                if danger is None or rx < danger[0]:
                    danger = (rx, r[1], r[3])
    if danger:
        up = danger[1] - 3
        down = danger[1] + danger[2] + 2
        ok_up, ok_down = up >= 1, down <= 14
        if ok_up and (not ok_down or abs(up - sy) <= abs(down - sy)):
            target_y = up << 8
        elif ok_down:
            target_y = down << 8
    else:
        if t >= next_cruise:
            cruise_y = random.randint(4, 11) << 8
            next_cruise = t + random.uniform(3, 8)
        target_y = cruise_y + int(math.sin(t * 1.3) * 140)
    step = int(DODGE_SPEED * dt * 256)
    if ship_y < target_y:
        ship_y = min(target_y, ship_y + step)
    elif ship_y > target_y:
        ship_y = max(target_y, ship_y - step)
    sy = (ship_y + 128) >> 8

    # did anything hit? (the shield takes it)
    for r in rocks:
        if r[4]:
            rx = r[0] >> 8
            if rx <= SHIP_X + 4 and rx + r[3] > SHIP_X and r[1] <= sy + 1 and r[1] + r[3] > sy - 1:
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
    # engine flame flickers
    fl = random.getrandbits(2)
    g.set_pen(FLAME[0])
    g.pixel(SHIP_X - 1, sy)
    if fl:
        g.set_pen(FLAME[1])
        g.pixel(SHIP_X - 2, sy)
    if fl == 3:
        g.set_pen(FLAME[2])
        g.pixel(SHIP_X - 3, sy)
    # the ship: red wings, grey and white hull, a cyan cockpit
    g.set_pen(WING)
    g.pixel(SHIP_X, sy - 1)
    g.pixel(SHIP_X + 1, sy - 1)
    g.pixel(SHIP_X, sy + 1)
    g.pixel(SHIP_X + 1, sy + 1)
    g.set_pen(HULL[0])
    g.pixel(SHIP_X, sy)
    g.set_pen(HULL[1])
    g.pixel(SHIP_X + 1, sy)
    g.pixel(SHIP_X + 2, sy)
    g.set_pen(COCKPIT)
    g.pixel(SHIP_X + 3, sy)
    g.set_pen(NOSE)
    g.pixel(SHIP_X + 4, sy)
    if shield:
        shield -= 1
        if shield & 2:
            g.set_pen(SHIELD)
            for x, y in ((SHIP_X + 5, sy), (SHIP_X + 3, sy - 1), (SHIP_X + 3, sy + 1),
                         (SHIP_X + 1, sy - 2), (SHIP_X + 1, sy + 2), (SHIP_X - 1, sy - 1), (SHIP_X - 1, sy + 1)):
                g.pixel(x, y)
    return FRAME
