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
# Galactic version: a long runway for the ship to wander along, and the big
# bodies are scaled to the strip (suns rise over the top or bottom edge).
#   A = send an asteroid   B = next planet   C = call the flying saucer
# When a saucer comes in, the ship shoots little bullets at it; a few hits
# and it bursts into sparks.
#
# Memory-friendly: each planet is drawn into a small bytearray mask once when
# it appears; asteroids come from a fixed pool; positions are integers
# (1/256 of a pixel); nothing is allocated per frame.
import math
import random
from galactic import GalacticUnicorn

SPEED = 1.0          # overall flying speed (stars, asteroids, planets)
ASTEROID_S = (2.0, 5.0)  # seconds between asteroids (min, max)
AIMED = 0.45         # chance an asteroid comes straight at the ship
ROCK_SPEED = (3.0, 7.0)  # asteroid speed, pixels a second (min, max)
PLANET_SPEED = 0.5   # how fast planets drift by, pixels a second
GAP_S = (4, 12)      # seconds of open space between planets (min, max)
DODGE_SPEED = 7.0    # how fast the ship swerves, pixels a second
DRIFT = (2, 44)      # how far back and forward the ship roams (its left edge, px)
DRIFT_SPEED = 4.0    # top speed when it flies forwards or back, pixels a second
ROAM_S = (1.0, 4.0)  # seconds it lingers at a spot before flying somewhere new (min, max)
LOOKAHEAD = 18       # how far ahead the ship watches for asteroids (px)
BACKDROP = 0.3       # brightness of everything behind the ship: stars, suns, planets (0..1)
MUTE = 0.55          # how much colour is drained from the backdrop (0 = full colour, 1 = grey)
OUTLINE = 0.6        # how much the backdrop is dimmed right around the ship (0 = not at all, 1 = black)
UFO_S = (25, 60)     # seconds between flying saucer visits (min, max)
UFO_SPEED = 5.0      # how fast the saucer glides in, pixels a second
UFO_HOVER = (2.0, 5.0)  # seconds it hovers before zipping off (min, max)
BEAM = 0.6           # chance it shines its tractor beam while hovering
BEAM_LEN = 3         # how far the tractor beam reaches below the saucer (px)
SHOOT = 1            # 1 = the ship shoots at saucers, 0 = leaves them be
FIRE_S = 0.6         # seconds between shots
HITS = 6             # hits to knock a saucer out
AIM = 1.2            # how much the aim wobbles (px); some shots miss
BULLET_SPEED = 24.0    # how fast bullets fly, pixels a second
FRAME = 0.04

# star layers: (count, speed in px/s, brightness 0..255)
LAYERS = ((22, 0.7, 60), (16, 2.0, 120), (10, 5.0, 230))
PLANETS = ("gas", "ringed", "ice", "moon", "gas", "moon")   # one round between suns, shuffled

def setup(su, g):
    global BLACK, STARPEN, STARDIM, ROCKDIM, ROCK, HULL, WING, COCKPIT, COCKPIT2, NOSE, FLAME, SHIELD
    global stars, rocks, ship_x, ship_y, target_x, target_y, cruise_y, next_cruise, next_drift, dodge
    global last_threat, shield, a_was, b_was
    global body, body_x, next_body, order, next_rock, last_t
    global DOME, SAUCER, LIGHTS, BEAMPEN, ufo, next_ufo, c_was, W, H, TT, TS
    W, H = su.WIDTH, su.HEIGHT
    TT = bytearray(H)
    TS = bytearray(H)
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
    shoot_setup(su, g)
    c_was = False
    stars = []
    for li, (n, sp, b) in enumerate(LAYERS):
        for _ in range(n):
            stars.append([random.randrange(W << 8), random.randrange(H), li])
    rocks = [[0, 0, 0, 0, False] for _ in range(6)]   # x, y, speed, size, alive
    ship_y = target_y = cruise_y = (H // 2 - 1) << 8
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
W, H = 53, 11        # the Galactic Unicorn (set again from the board in setup)

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
    r = {"sun": random.randint(8, 10), "gas": random.randint(4, 7), "ringed": random.randint(3, 4),
         "ice": random.randint(3, 5), "moon": random.randint(2, 3)}[kind]
    reach = r + (5 if kind == "ringed" else 2)
    # moons: one or two small ones nearby, each its own colour
    moons = []
    if kind != "sun":
        for _ in range(random.choice((0, 1, 1, 2))):
            a = random.uniform(0, 6.283)
            dist = r + random.uniform(2.5, 4.5) + (3 if kind == "ringed" else 0)
            mr = random.choice((1, 1, 1.6, 2))
            moons.append((math.cos(a) * dist, math.sin(a) * dist * 0.4, mr, random.choice(MOONS)))
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
    body_x = (W + half) << 8
    if kind == "sun":            # a sun rises over the top or bottom edge, 4 or 5 rows of it showing
        dip = random.randint(4, 5)
        body_y = dip - 1 - r if random.getrandbits(1) else H - dip + r
    elif r <= 3:                 # small worlds sit wholly on the strip
        body_y = random.randint(r - 1, H - r)
    else:                        # big ones may hang off the top or bottom
        body_y = random.randint(H // 2 - r // 2 - 1, H // 2 + r // 2 + 1)

def draw_body(g):
    mask, w = body
    bx = (body_x >> 8) - half
    by = body_y - half
    for j in range(w):
        y = by + j
        if y < 0 or y >= H:
            continue
        row = j * w
        for i in range(w):
            x = bx + i
            if 0 <= x < W:
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
        y = random.randint(0, H - size)
    r[0] = (W + 1) << 8
    r[1] = max(0, min(H - size, y))
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
            if 0 <= px < W:
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
    if not (0 <= x < W and 0 <= y < H):
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
    base = 0.4 if beams else random.choice((0.5, 1.5, H - 5.5, H - 4.5))
    ufo = [-8.0 if d > 0 else W + 1.0, base, "in", t, d, float(random.randint(W // 2, W - 9)), base,
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
        if u[0] < -9 or u[0] > W + 2 or u[6] < -6 or u[6] > H + 3:
            ufo = None
            next_ufo = t + random.uniform(*UFO_S)
            return
    u[1] = u[6] + math.sin(t * 2.3) * (0.5 if u[10] else 0.7)   # a lazy wobble

def ufo_rows(sx):
    """Rows the saucer (and its beam) take up ahead of the ship, as bits."""
    u = ufo
    x = int(u[0] + 0.5)
    behind = LOOKAHEAD if u[4] > 0 and u[2] == "in" else 1    # it may be catching up from behind
    if x + 7 < sx - behind or x > sx + LOOKAHEAD:
        return 0
    y = int(u[1] + 0.5)
    m = 0
    # keep clear of where the beam will shine from the moment it arrives
    bottom = y + (4 + BEAM_LEN if u[10] and u[2] != "out" and (u[10] < 0 or last_t < u[11]) else 4)
    for row in range(y - 1, bottom + 1):
        if 0 <= row < H:
            m |= 1 << row
    return m

def beaming():
    u = ufo
    return u[2] == "hover" and 0 < u[10] <= last_t < u[11]

# ---------------------------------------------------------------- shooting
# When a saucer comes in ahead, the ship fires little bullets at it, aimed at
# where it is. Each hit makes it flash and throws a few sparks; after HITS
# hits it bursts into a shower of sparks and is gone until its next visit.
def shoot_setup(su, g):
    global BULLETS, SPARKS, BULLETPEN, SPARKPEN, FLASHPEN, next_shot, ufo_hits, ufo_flash, SW, SH
    SW, SH = su.WIDTH, su.HEIGHT
    BULLETS = [[0.0, 0.0, 0.0, 0.0, False] for _ in range(8)]      # x, y, vx, vy, flying
    SPARKS = [[0.0, 0.0, 0.0, 0.0, 0, 0] for _ in range(24)]       # x, y, vx, vy, frames left, colour
    BULLETPEN = (g.create_pen(255, 250, 170), g.create_pen(255, 120, 20))
    SPARKPEN = [[g.create_pen(r * v // 4, gg * v // 4, b * v // 4) for v in range(1, 5)]
                for r, gg, b in ((255, 240, 120), (255, 120, 30), (120, 255, 200), (255, 80, 200), (255, 255, 255))]
    FLASHPEN = g.create_pen(255, 255, 255)
    next_shot = 0.0
    ufo_hits = 0
    ufo_flash = 0

def spark(x, y, n, colours, speed):
    for s in SPARKS:
        if n <= 0:
            break
        if s[4] <= 0:
            a = random.uniform(0, 6.283)
            v = random.uniform(0.3, 1.0) * speed
            s[0] = x
            s[1] = y
            s[2] = math.cos(a) * v
            s[3] = math.sin(a) * v * 0.7
            s[4] = random.randint(8, 20)
            s[5] = random.choice(colours)
            n -= 1

def shooting(t, dt, sx, sy):
    global next_shot, ufo_hits, ufo_flash, ufo, next_ufo
    u = ufo
    if u is None:
        ufo_hits = 0
    elif SHOOT and u[2] == "hover" and t >= next_shot:
        nx = sx + 5                            # from the nose
        ny = sy + 1
        dx = u[0] + 3.5 - nx
        dy = u[1] + 1.5 - ny + random.uniform(-AIM, AIM)
        if 0 < dx < SW * 0.85 and abs(dy) < 2 * dx + 4:   # ahead of the ship, or up ahead
            for b in BULLETS:
                if not b[4]:
                    d = math.sqrt(dx * dx + dy * dy)
                    b[0] = nx
                    b[1] = ny
                    b[2] = dx / d * BULLET_SPEED
                    b[3] = dy / d * BULLET_SPEED
                    b[4] = True
                    break
            next_shot = t + FIRE_S * random.uniform(0.8, 1.25)
    for b in BULLETS:
        if not b[4]:
            continue
        b[0] += b[2] * dt
        b[1] += b[3] * dt
        if b[0] < -1 or b[0] > SW or b[1] < -1 or b[1] > SH:
            b[4] = False
            continue
        u = ufo
        if u is not None:
            ux = int(u[0] + 0.5)
            uy = int(u[1] + 0.5)
            bx = int(b[0] + 0.5)
            by = int(b[1] + 0.5)
            if ux <= bx <= ux + 6 and uy <= by <= uy + 3:
                b[4] = False
                ufo_hits += 1
                ufo_flash = 4
                spark(b[0], b[1], 3, (0, 1), 6)
                if ufo_hits >= HITS:
                    spark(u[0] + 3.5, u[1] + 1.5, 20, (0, 1, 2, 3, 4), 9)
                    ufo = None
                    ufo_hits = 0
                    next_ufo = t + random.uniform(*UFO_S)
    for s in SPARKS:
        if s[4] > 0:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += 3 * dt                     # sparks sag a little as they fade
            s[2] *= 0.97
            s[4] -= 1

def draw_shots(g):
    global ufo_flash
    if ufo_flash and ufo is not None:          # a hit: the saucer flashes white
        ufo_flash -= 1
        x = int(ufo[0] + 0.5)
        y = int(ufo[1] + 0.5)
        g.set_pen(FLASHPEN)
        for i, j in ((2, 0), (3, 0), (4, 0), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (0, 2), (6, 2), (3, 2)):
            if 0 <= x + i < SW and 0 <= y + j < SH:
                g.pixel(x + i, y + j)
    for b in BULLETS:
        if b[4]:
            x = int(b[0] + 0.5)
            y = int(b[1] + 0.5)
            tx = int(b[0] - b[2] / BULLET_SPEED + 0.5)     # a short glowing tail
            ty = int(b[1] - b[3] / BULLET_SPEED + 0.5)
            if 0 <= tx < SW and 0 <= ty < SH:
                g.set_pen(BULLETPEN[1])
                g.pixel(tx, ty)
            if 0 <= x < SW and 0 <= y < SH:
                g.set_pen(BULLETPEN[0])
                g.pixel(x, y)
    for s in SPARKS:
        if s[4] > 0:
            x = int(s[0] + 0.5)
            y = int(s[1] + 0.5)
            if 0 <= x < SW and 0 <= y < SH:
                g.set_pen(SPARKPEN[s[5]][3 if s[4] > 12 else s[4] // 4])
                g.pixel(x, y)

def draw_ufo(g, t):
    u = ufo
    x = int(u[0] + 0.5)
    y = int(u[1] + 0.5)
    if beaming():
        # a widening cone of pale green light, shimmering
        for j in range(1, BEAM_LEN + 1):
            yy = y + 3 + j
            if yy >= H:
                break
            w = 1 + (j * 2) // (BEAM_LEN + 1)
            for i in range(-w, w + 1):
                xx = x + 3 + i
                if 0 <= xx < W and (random.getrandbits(3) or i == 0):
                    lv = (abs(i) + j // 3) // 2
                    g.set_pen(BEAMPEN[lv if lv < 3 else 2])
                    g.pixel(xx, yy)
    def px(i, j, p):
        xx = x + i
        yy = y + j
        if 0 <= xx < W and 0 <= yy < H:
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

def threats(sx):
    """For every row: frames (1/25 s) until something ahead of the ship reaches it
    (TT), and the same counting a row of margin round each asteroid (TS); 255 =
    nothing coming. Returns True if anything is coming at all."""
    m = ufo_rows(sx) if ufo is not None else 0
    any_ = m != 0
    for row in range(H):
        # the saucer's rows are to be kept clear of, but the ship may cross them to get away
        TT[row] = 100 if (m >> row) & 1 else 255
        TS[row] = 0 if (m >> row) & 1 else 255
    for r in rocks:
        if r[4]:
            rx = r[0] >> 8
            if rx + r[3] >= sx - 1 and rx <= sx + LOOKAHEAD:
                any_ = True
                d = rx - sx - 5
                tt = 0 if d <= 0 else min(254, d * 256 // (r[2] or 1))
                for row in range(r[1] - 1, r[1] + r[3] + 1):
                    if 0 <= row < H:
                        if tt < TS[row]:
                            TS[row] = tt
                        if r[1] <= row < r[1] + r[3] and tt < TT[row]:
                            TT[row] = tt
    return any_

def lane(y):
    """How long the lane with the ship's top at row y stays clear (255 = clear);
    brushing past an asteroid's margin counts for less than meeting it."""
    a = TT[y] if TT[y] < TT[y + 1] else TT[y + 1]
    b = (TS[y] if TS[y] < TS[y + 1] else TS[y + 1]) + 12
    return a if a < b else b

def reachable(sy, y, rowf):
    """Can the ship swerve from row sy to row y without being in a row (other than
    where it ends up) when something gets there? rowf = frames per row of swerve."""
    if y < sy:                       # going up: rows y+2 .. sy+1 are left behind
        for k in range(y + 2, sy + 2):
            if k < H and TT[k] * 2 <= (2 * (sy + 1 - k) + 1) * rowf:
                return False
    else:                            # going down: rows sy .. y-1 are left behind
        for k in range(sy, y):
            if TT[k] * 2 <= (2 * (k - sy) + 1) * rowf:
                return False
    return True

def pick_lane(sy, rowf):
    """The best lane: wholly clear if possible (the nearest such), otherwise the one
    that stays clear longest; only lanes the ship can reach in time."""
    best, bv, bd = sy, lane(sy), 0
    for d in range(1, H):
        for y in (sy - d, sy + d):
            if 0 <= y <= H - 2:
                v = lane(y)
                if v > bv and reachable(sy, y, rowf):
                    best, bv, bd = y, v, d
        if bv == 255:
            break
    return best, bv

def frame(su, g, t):
    global ship_x, ship_y, target_x, target_y, cruise_y, next_cruise, next_drift, dodge, last_threat, shield
    global a_was, b_was, body, body_x, next_body, next_rock, last_t, order, next_ufo, c_was
    dt = t - last_t
    if dt > 0.1:
        dt = 0.1          # after a pause, carry on instead of jumping ahead
    last_t = t
    a = su.is_pressed(GalacticUnicorn.SWITCH_A)
    b = su.is_pressed(GalacticUnicorn.SWITCH_B)
    if a and not a_was:
        send_rock(True)
    if b and not b_was:
        body = None
        next_body = t
    c = su.is_pressed(GalacticUnicorn.SWITCH_C)
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
        # somewhere new, and usually a good way off, so it really moves about
        cur = ship_x >> 8
        for _ in range(4):
            nx = random.randint(DRIFT[0], DRIFT[1])
            if abs(nx - cur) >= (DRIFT[1] - DRIFT[0]) // 3:
                break
        target_x = nx << 8
        next_drift = t + 1e9                      # fly all the way there first
        next_cruise = min(next_cruise, t + 0.5)     # and often a new height to go with it
    if ufo is not None and ufo[2] != "out":
        # hang back behind a saucer that's arriving or hovering
        target_x = min(target_x, max(DRIFT[0], int(ufo[5]) - 10) << 8)
    # ease in and out: full speed in the middle of a trip, slowing to arrive
    gap = target_x - ship_x
    sp = min(DRIFT_SPEED, 0.25 + abs(gap) / 256 * 0.9)
    if dodge is not None and gap > 0:
        sp *= 0.5                              # mid-dodge: don't charge forwards into rocks
    stepx = int(sp * dt * 256) or 1
    if gap > 0:
        ship_x = min(target_x, ship_x + stepx)
    elif gap < 0:
        ship_x = max(target_x, ship_x - stepx)
    if ship_x == target_x and next_drift > t + 1e8:
        next_drift = t + random.uniform(*ROAM_S)   # arrived: linger a moment
    sx = (ship_x + 128) >> 8

    # dodging: pick the nearest clear lane and stick with it until it's safe;
    # if no lane is wholly clear, go for the one that stays clear longest
    # (with only a moment left and nowhere to go, it swerves twice as hard)
    sy = (ship_y + 128) >> 8
    hard = False
    if threats(sx):
        rowf = int(25 / DODGE_SPEED) + 1
        cur = lane(dodge) if dodge is not None else -1
        if cur < 255 or not reachable(sy, dodge, rowf):
            best, bv = pick_lane(sy, rowf)
            if dodge is None or bv > cur + 6 or not reachable(sy, dodge, rowf):
                dodge = best
            if bv < 3 * rowf:
                best2, bv2 = pick_lane(sy, rowf // 2)
                if bv2 > bv + 6:
                    dodge = best2
                    hard = True
        target_y = dodge << 8
        last_threat = t
    elif dodge is not None and t - last_threat < 0.8:
        target_y = dodge << 8              # hold the lane a moment after it's clear
    else:
        dodge = None
        if t >= next_cruise:
            cruise_y = random.randint(1, H - 3) << 8
            next_cruise = t + random.uniform(2, 5)
        target_y = cruise_y + int(math.sin(t * 1.3) * 120)
    step = int(DODGE_SPEED * (2 if hard else 1) * dt * 256) or 1
    if ship_y < target_y:
        ship_y = min(target_y, ship_y + step)
    elif ship_y > target_y:
        ship_y = max(target_y, ship_y - step)
    sy = (ship_y + 128) >> 8

    shooting(t, dt, sx, sy)

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
            s[0] += W << 8
            s[1] = random.randrange(H)
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
    draw_shots(g)
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
