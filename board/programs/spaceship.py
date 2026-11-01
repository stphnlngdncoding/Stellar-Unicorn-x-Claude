# Spaceship: a little ship cruises through space, engine flickering, while
# stars stream past in three layers. Huge things drift by slowly in the
# background: a blazing sun, banded gas giants, ringed planets, icy worlds and
# cratered rocks, each in its own colours and sometimes with moons of its own.
# Everything behind the ship is muted, and dimmed further in a thin halo
# right around it, so it stands out. The ship drifts forwards and backwards,
# and when an asteroid tumbles in it picks a clear lane and swerves into it
# (if one ever does clip it, its shield flashes). Every so often a flying
# saucer glides in, hovers with its rim lights chasing round, sometimes
# shines a tractor beam down, then zips off up and away; the ship gives it
# a wide berth.
#   A = send an asteroid   B = next planet   C = call the flying saucer
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
OUTLINE = 0.6        # how much the backdrop is dimmed right around the ship (0 = not at all, 1 = black)
UFO_S = (25, 70)     # seconds between flying saucer visits (min, max)
UFO_SPEED = 5.0      # how fast the saucer glides in, pixels a second
UFO_HOVER = (2.0, 5.0)  # seconds it hovers before zipping off (min, max)
BEAM = 0.6           # chance it shines its tractor beam while hovering
FRAME = 0.04

# star layers: (count, speed in px/s, brightness 0..255)
LAYERS = ((10, 0.7, 60), (8, 2.0, 120), (5, 5.0, 230))
PLANETS = ("gas", "ringed", "ice", "moon", "gas", "moon")   # one round between suns, shuffled

def setup(su, g):
    global BLACK, STARPEN, STARDIM, ROCKDIM, ROCK, HULL, WING, COCKPIT, COCKPIT2, NOSE, FLAME, SHIELD
    global stars, rocks, ship_x, ship_y, target_x, target_y, cruise_y, next_cruise, next_drift, dodge
    global last_threat, shield, a_was, b_was
    global body, body_x, next_body, order, next_rock, last_t
    global DOME, SAUCER, LIGHTS, BEAMPEN, ufo, next_ufo, c_was
    BLACK = g.create_pen(0, 0, 0)
    STARPEN = [g.create_pen(*muted((b, b, min(255, b + 30)))) for _, _, b in LAYERS]
    ROCK = (g.create_pen(60, 48, 40), g.create_pen(110, 92, 75), g.create_pen(170, 150, 125))
    STARDIM = [g.create_pen(*shade(muted((b, b, min(255, b + 30))), 1 - OUTLINE)) for _, _, b in LAYERS]
    ROCKDIM = g.create_pen(*shade((110, 92, 75), 1 - OUTLINE))
    HULL = (g.create_pen(175, 180, 200), g.create_pen(255, 255, 255))
    WING = g.create_pen(255, 25, 40)
    COCKPIT = g.create_pen(80, 245, 255)
    COCKPIT2 = g.create_pen(30, 150, 215)
    NOSE = g.create_pen(255, 255, 255)
    FLAME = (g.create_pen(255, 230, 120), g.create_pen(255, 130, 20), g.create_pen(150, 40, 0))
    SHIELD = g.create_pen(120, 200, 255)
    DOME = (g.create_pen(110, 255, 210), g.create_pen(220, 255, 245))         # glass, glint
    SAUCER = (g.create_pen(235, 238, 248), g.create_pen(165, 170, 190), g.create_pen(85, 88, 105))  # top, rim, belly
    LIGHTS = (g.create_pen(255, 50, 60), g.create_pen(255, 215, 40), g.create_pen(60, 255, 120), g.create_pen(70, 150, 255))
    BEAMPEN = (g.create_pen(90, 200, 120), g.create_pen(50, 125, 75), g.create_pen(25, 65, 40))
    ufo = None
    next_ufo = random.uniform(8, 20)      # the first visit comes fairly soon
    c_was = False
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
    global body, body_x, body_y, half, BPENS, BDIM
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
    dims = []                     # the same colours, dimmed for the halo round the ship
    cache = {}

    def pen(rgb):
        if rgb not in cache:
            cache[rgb] = len(pens)
            m = muted(rgb)
            pens.append(g.create_pen(*m))
            dims.append(g.create_pen(*shade(m, 1 - OUTLINE)))
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
    BDIM = dims
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

def halo(g, x, y):
    """Redraw the backdrop at (x, y) in its dimmed colour."""
    if not (0 <= x < 16 and 0 <= y < 16):
        return
    for r in rocks:
        if r[4]:
            rx = r[0] >> 8
            if rx <= x < rx + r[3] and r[1] <= y < r[1] + r[3]:
                g.set_pen(ROCKDIM)
                g.pixel(x, y)
                return
    if body is not None:
        mask, w = body
        i = x - ((body_x >> 8) - half)
        j = y - (body_y - half)
        if 0 <= i < w and 0 <= j < w:
            p = mask[j * w + i]
            if p != 255:
                g.set_pen(BDIM[p])
                g.pixel(x, y)
                return
    for s in stars:
        if s[1] == y and (s[0] >> 8) == x:
            g.set_pen(STARDIM[s[2]])
            g.pixel(x, y)
            return

# ---------------------------------------------------------------- flying saucer
# Seven wide, four tall, top-left corner at (ux, uy):
#   . . d d d . .     glass dome
#   . t t t t t .     silver top
#   r r r r r r r     rim, with lights chasing round
#   . . b b b . .     belly
# ufo = [x, y, phase, phase start, direction, hover x, base y, speed, rise, hover time, beam on, beam off]
def call_ufo(t):
    global ufo
    d = random.choice((1, -1))
    beams = random.random() < BEAM
    # a saucer that will beam flies along the very top, so the ship has room below
    base = random.choice((0.4, 0.8)) if beams else random.choice((1.0, 2.0, 9.5, 10.5, 11.0))
    ufo = [-8.0 if d > 0 else 17.0, base, "in", t, d, float(random.randint(3, 6)), base,
           UFO_SPEED, random.choice((-1, 1)) * random.uniform(2, 5), random.uniform(*UFO_HOVER),
           -1.0 if beams else 0.0, 0.0]

def move_ufo(t, dt):
    global ufo, next_ufo
    u = ufo
    ph = u[2]
    if ph == "in":
        u[0] += u[4] * UFO_SPEED * SPEED * dt
        if (u[4] > 0 and u[0] >= u[5]) or (u[4] < 0 and u[0] <= u[5]):
            u[2] = "hover"
            u[3] = t
            if u[10] < 0:
                u[10] = t + 0.6
                u[11] = t + u[9] - 0.4
    elif ph == "hover":
        u[0] = u[5] + math.sin((t - u[3]) * 1.7) * 0.6
        if t - u[3] >= u[9]:
            u[2] = "out"
            u[3] = t
    else:                                      # zip off, faster and faster, up or down and away
        u[7] *= 1 + 3.5 * dt
        u[0] += u[4] * u[7] * dt
        u[6] += u[8] * (u[7] / UFO_SPEED) * dt * 0.4
        if u[0] < -9 or u[0] > 18 or u[6] < -6 or u[6] > 19:
            ufo = None
            next_ufo = t + random.uniform(*UFO_S)
            return
    u[1] = u[6] + math.sin(t * 2.3) * 0.7      # a lazy wobble

def ufo_rows(sx):
    """Rows the saucer (and its beam) take up ahead of the ship, as bits."""
    u = ufo
    x = int(u[0] + 0.5)
    if x + 7 < sx - 1 or x > sx + LOOKAHEAD:
        return 0
    y = int(u[1] + 0.5)
    m = 0
    # keep clear of where the beam will shine (five rows below) from the moment it arrives
    bottom = y + (8 if u[10] and u[2] != "out" and (u[10] < 0 or last_t < u[11]) else 4)
    for row in range(y - 1, bottom + 1):
        if 0 <= row < 16:
            m |= 1 << row
    return m

def beaming():
    u = ufo
    return u[2] == "hover" and 0 < u[10] <= last_t < u[11]

def draw_ufo(g, t):
    u = ufo
    x = int(u[0] + 0.5)
    y = int(u[1] + 0.5)
    if beaming():
        # a widening cone of pale green light, shimmering
        for j in range(1, 6):
            yy = y + 3 + j
            if yy > 15:
                break
            w = 1 + j // 3
            for i in range(-w, w + 1):
                xx = x + 3 + i
                if 0 <= xx < 16 and (random.getrandbits(3) or i == 0):
                    lv = (abs(i) + j // 3) // 2
                    g.set_pen(BEAMPEN[lv if lv < 3 else 2])
                    g.pixel(xx, yy)
    def px(i, j, p):
        xx = x + i
        yy = y + j
        if 0 <= xx < 16 and 0 <= yy < 16:
            g.set_pen(p)
            g.pixel(xx, yy)
    px(2, 0, DOME[0])
    px(3, 0, DOME[1])                          # a glint on the glass
    px(4, 0, DOME[0])
    for i in range(1, 6):
        px(i, 1, SAUCER[0])
    k = int(t * 8)
    for i in range(7):                         # rim lights chase round
        px(i, 2, LIGHTS[(i + k) % 4] if (i + k) % 2 == 0 else SAUCER[1])
    for i in range(2, 5):
        px(i, 3, SAUCER[2])

def blocked(sx):
    """Rows (as bits) that asteroids ahead of the ship will pass through, plus a margin."""
    m = ufo_rows(sx) if ufo is not None else 0
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
    global a_was, b_was, body, body_x, next_body, next_rock, last_t, order, next_ufo, c_was
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
    c = su.is_pressed(StellarUnicorn.SWITCH_C)
    if c and not c_was and ufo is None:
        next_ufo = t
    a_was, b_was, c_was = a, b, c

    # the flying saucer drops by now and then
    if ufo is None and t >= next_ufo:
        call_ufo(t)
    if ufo is not None:
        move_ufo(t, dt)

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
    # a thin halo round the ship: whatever is behind it is drawn dimmer there
    if OUTLINE:
        for x, y in RIM:
            halo(g, sx + x, sy + y)
    if ufo is not None:
        draw_ufo(g, t)
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
