# Starfall: a clear night over dark hills. Stars twinkle, and every few
# seconds a shooting star streaks across the sky, its tail fading behind it,
# burning out or slipping behind the hills. Now and then there's a fireball
# (slower, golden, with a long tail), and every minute or so a meteor shower
# sends a flurry of them from the same corner of the sky.
#   A = meteor shower now
#
# Memory-friendly: positions are integers (1/256 of a pixel), meteors are
# small lists reused from a fixed pool, and every pen is made once in setup().
import math
import random
from stellar import StellarUnicorn

STARS = 24           # background stars
SHOOT_S = (2.0, 7.0) # seconds between shooting stars (min, max)
SHOWER_S = (45, 90)  # seconds between meteor showers (min, max)
SHOWER_SIZE = (6, 10)  # meteors in a shower (min, max)
SPEED = (6.0, 15.0)  # shooting star speed, pixels a second (min, max)
TAIL = (3, 7)        # tail length in pixels (min, max)
FIREBALL = 0.12      # chance a shooting star is a big golden fireball
TWINKLE = 3          # how much the stars twinkle (0 = steady)
FRAME = 0.04
MAX_METEORS = 14
LEVELS = 16

# tail colours: blue-white, pale green, gold (fireballs), soft violet
TINTS = ((200, 225, 255), (190, 255, 215), (255, 205, 110), (220, 190, 255))
STAR_TINTS = ((255, 255, 255), (180, 205, 255), (255, 225, 180))

def setup(su, g):
    global BG, HILL, STARPEN, MPEN, HEAD, stars, meteors, TW, a_was, next_shoot, next_shower, shower
    # hills along the bottom, a smooth random profile 1..3 pixels tall
    h = random.uniform(1.2, 2.6)
    HILL = bytearray(16)
    for x in range(16):
        h += random.uniform(-0.6, 0.6)
        h = min(3.4, max(0.8, h))
        HILL[x] = 16 - int(h + 0.5)            # first hill row in this column
    BG = []
    for y in range(16):
        for x in range(16):
            if y >= HILL[x]:
                BG.append(g.create_pen(1, 3, 4))
            else:
                f = y * 16 // 15                  # darker at the top, a little purple low down
                BG.append(g.create_pen(1 + f // 2, 2 + f // 3, 10 + f))
    STARPEN = [[g.create_pen(r * v // 15, gg * v // 15, b * v // 15) for v in range(LEVELS)]
               for r, gg, b in STAR_TINTS]
    MPEN = [[g.create_pen(r * v // 15, gg * v // 15, b * v // 15) for v in range(LEVELS)]
            for r, gg, b in TINTS]
    HEAD = [g.create_pen(255 * v // 15, 255 * v // 15, 255 * v // 15) for v in range(LEVELS)]
    TW = bytes(int(8 + 7 * math.sin(i * 2 * math.pi / 64)) for i in range(64))
    stars = []
    for _ in range(STARS):
        x = random.randrange(16)
        y = random.randrange(HILL[x] - 1)
        stars.append((x, y, random.randint(2, 11), random.randrange(64),
                      random.randrange(len(STAR_TINTS)), random.randint(1, 3)))
    # meteor: [x, y, ux, uy, step, age, life, tint, tail, alive]
    meteors = [[0, 0, 0, 0, 0, 0, 0, 0, 0, False] for _ in range(MAX_METEORS)]
    a_was = False
    next_shoot = 1.0
    next_shower = random.uniform(*SHOWER_S)
    shower = None

def launch(angle=None, side=None, fire=None):
    for m in meteors:
        if not m[9]:
            break
    else:
        return
    if side is None:
        side = random.choice((-1, 1))          # +1 = heading right
    if angle is None:
        angle = random.uniform(0.3, 0.95)      # radians below horizontal
    if fire is None:
        fire = random.random() < FIREBALL
    ux = int(math.cos(angle) * 256) * side
    uy = int(math.sin(angle) * 256)
    speed = random.uniform(*SPEED) * (0.6 if fire else 1.0)
    # start near the top, on the side it's coming from, so it crosses the sky
    m[0] = int((random.uniform(-1, 9) if side > 0 else random.uniform(6, 16)) * 256)
    m[1] = int(random.uniform(-1, 4) * 256)
    m[2], m[3] = ux, uy
    m[4] = int(speed * FRAME * 256)
    m[5] = 0
    m[6] = int(random.uniform(0.8, 2.0) / FRAME) if not fire else int(random.uniform(2.0, 3.2) / FRAME)
    m[7] = 2 if fire else random.choice((0, 0, 1, 3))
    m[8] = random.randint(TAIL[0], TAIL[1]) + (4 if fire else 0)
    m[9] = True

def frame(su, g, t):
    global a_was, next_shoot, next_shower, shower
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if (a and not a_was) or t >= next_shower:
        # a shower: meteors from roughly the same direction over a few seconds
        shower = [t, random.choice((-1, 1)), random.uniform(0.35, 0.8),
                  random.randint(SHOWER_SIZE[0], SHOWER_SIZE[1])]
        next_shower = t + random.uniform(*SHOWER_S)
    a_was = a
    if shower:
        if shower[3] <= 0:
            shower = None
        elif random.random() < 0.12:
            launch(shower[2] + random.uniform(-0.08, 0.08), shower[1], False)
            shower[3] -= 1
    if t >= next_shoot:
        launch()
        next_shoot = t + random.uniform(*SHOOT_S)

    # ---- sky, hills, stars ----
    for i in range(256):
        g.set_pen(BG[i])
        g.pixel(i & 15, i >> 4)
    tick = int(t * 20)
    for x, y, lv, ph, tint, sp in stars:
        v = lv + ((TW[(tick * sp + ph) & 63] - 8) * TWINKLE >> 3)
        if v > 0:
            g.set_pen(STARPEN[tint][v if v < 16 else 15])
            g.pixel(x, y)

    # ---- shooting stars ----
    for m in meteors:
        if not m[9]:
            continue
        m[0] += m[2] * m[4] >> 8
        m[1] += m[3] * m[4] >> 8
        m[5] += 1
        age, life = m[5], m[6]
        if age >= life:
            m[9] = False
            continue
        # bright quickly, then burn out over the last third
        if age < 3:
            b = 5 * (age + 1)
        elif age > life * 2 // 3:
            b = 15 * (life - age) * 3 // life
        else:
            b = 15
        if b > 15:
            b = 15
        n = m[8]
        pens = MPEN[m[7]]
        for k in range(n, -1, -1):
            px = (m[0] - k * m[2]) >> 8
            py = (m[1] - k * m[3]) >> 8
            if 0 <= px < 16 and 0 <= py < 16 and py < HILL[px]:
                v = b * (n - k + 1) // (n + 1)
                if v > 0:
                    g.set_pen(HEAD[v] if k == 0 else pens[v])
                    g.pixel(px, py)
        # gone off the board?
        hx, hy = m[0] >> 8, m[1] >> 8
        if hy > 18 or hx < -n - 2 or hx > 17 + n:
            m[9] = False
    return FRAME
