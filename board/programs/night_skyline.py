# Night Skyline: a little cluster of towers against a deep night sky full of
# twinkling stars. Office and flat windows switch on and off one by one in
# warm and cool tints (fewer late at night), red beacons blink on the masts,
# the moon hangs in tonight's real phase, aeroplanes cross with blinking
# lights, a car's headlights pass along the street now and then, and once in
# a while a shooting star streaks down. Hazy far-off towers stand behind.
#   A = a new skyline
#
# Memory-friendly: the skyline is a few bytearrays (one byte per column or
# per pixel), every pen is made once in setup() (the moon's few pens are
# remade every ten minutes as its phase creeps on), nothing is built per frame.
import math
import random
from stellar import StellarUnicorn

STARS = 22           # how many stars
TWINKLE = 1.0        # how fast the stars twinkle
LIT = 0.6            # share of windows lit in the evening (fewer after midnight)
WINDOW_RATE = 1.2    # windows switching on or off, per second
PLANE_S = (15, 45)   # seconds between aeroplanes (min, max)
SHOOT_S = (25, 75)   # seconds between shooting stars (min, max)
CAR_S = (6, 25)      # seconds between cars along the street (min, max)
MOON = 1             # 1 = moon in tonight's real phase, 0 = no moon

FRAME = 0.04
MOON_R = 2.7         # moon radius in pixels
MAX_ANT = 4

SKY_TOP = (2, 2, 14)
SKY_LOW = (52, 20, 62)                # city glow near the horizon
WALLS = ((3, 3, 8), (6, 4, 10), (2, 4, 9), (6, 5, 8), (1, 2, 5))
TINTS = ((150, 85, 20), (175, 130, 45), (95, 115, 150), (55, 120, 130))   # amber, yellow, cool white, teal
TV = ((30, 50, 120), (45, 70, 150), (25, 40, 100), (55, 85, 160))          # a flickering television
BIAS = ((0, 0, 1, 1, 4, 0), (2, 2, 3, 1, 2, 3), (0, 1, 2, 3, 4, 1))        # warm flats, cool offices, mixed


def setup(su, g):
    global W, H, LEN, top, wallc, bias, win, btop, bdot, wins, nwin, ant_x, ant_y, nant
    global SKY, WALLP, BACKP, BDOTP, TINTP, TVP, STARP, BEACON, TWT, PLANE, SHOOTP, STREET, CARP
    global sx, sy, sph, sbr, tick, toggle_acc, lit_now, lit_t, moonpix, moon_t, moon_x
    global plane_on, plane_x, plane_y, plane_d, plane_v, next_plane
    global shoot_on, shoot_x, shoot_y, shoot_vx, shoot_vy, shoot_life, next_shoot
    global car_on, car_x, car_d, car_v, next_car, a_was
    W, H = su.WIDTH, su.HEIGHT
    LEN = W
    top = bytearray(LEN)
    wallc = bytearray(LEN)
    bias = bytearray(LEN)
    win = bytearray(LEN * H)          # 0 wall, 1 dark window, 2.. lit (tint + 2)
    wins = list(range(LEN * H))       # indexes of the windows (first nwin used)
    nwin = 0
    btop = bytearray(LEN)             # the far-off towers
    bdot = bytearray(LEN * H)
    ant_x = bytearray(MAX_ANT)
    ant_y = bytearray(MAX_ANT)
    nant = 0

    SKY = [g.create_pen(*sky_rgb(y)) for y in range(H)]
    WALLP = [g.create_pen(*c) for c in WALLS]
    BACKP = g.create_pen(20, 10, 32)
    BDOTP = (g.create_pen(42, 30, 16), g.create_pen(26, 30, 44))
    TINTP = [g.create_pen(*c) for c in TINTS]
    TVP = [g.create_pen(*c) for c in TV]
    STARP = [g.create_pen(v * 10, v * 10, v * 13) for v in range(16)]
    BEACON = [g.create_pen(v * 14, v, v) for v in range(16)]
    PLANE = (g.create_pen(16, 16, 22), g.create_pen(200, 25, 25), g.create_pen(210, 210, 230))
    SHOOTP = [g.create_pen(v * 13, v * 14, v * 16) for v in range(16)]
    STREET = g.create_pen(7, 6, 10)
    CARP = (g.create_pen(60, 50, 25), g.create_pen(220, 200, 140), g.create_pen(18, 16, 24), g.create_pen(150, 15, 10))
    TWT = bytearray(64)               # twinkle wave, 0..15
    for i in range(64):
        TWT[i] = int(7.5 + 7.5 * math.sin(i * 6.283185 / 64))

    sx = bytearray(STARS)
    sy = bytearray(STARS)
    sph = bytearray(STARS)
    sbr = bytearray(STARS)
    for i in range(STARS):
        sx[i] = random.randrange(W)
        sy[i] = int(random.random() ** 1.5 * (H - 6))   # more stars high up, fewer in the glow
        sph[i] = random.randrange(64)
        sbr[i] = random.randint(5, 15)

    tick = 0
    toggle_acc = 0.0
    lit_t = -100.0
    lit_now = LIT
    moonpix = []
    moon_t = -1000.0
    moon_x = 12.5
    plane_on = False
    plane_x = plane_y = plane_d = plane_v = 0
    next_plane = random.uniform(3, 12)
    shoot_on = False
    shoot_x = shoot_y = shoot_vx = shoot_vy = 0.0
    shoot_life = 0
    next_shoot = random.uniform(*SHOOT_S)
    car_on = False
    car_x = car_d = car_v = 0
    next_car = random.uniform(2, 8)
    a_was = False
    new_skyline()


def mix(a, b, f):
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f)


def sky_rgb(y):
    return mix(SKY_TOP, SKY_LOW, (min(y, H - 2) / (H - 2)) ** 1.8)


def now():
    try:
        return local_time()
    except NameError:
        import time
        return time.localtime()


def new_skyline():
    global nwin, nant, moon_x, moon_t
    moon_x = random.choice((3.5, 12.5))
    moon_t = -1000.0                          # redraw the moon in its new spot
    for i in range(LEN):
        top[i] = H - 1
        btop[i] = H - 1
    for i in range(LEN * H):
        win[i] = 0
        bdot[i] = 0
    nwin = 0
    nant = 0
    # far-off towers: hazy blocks with a few dim lights
    x = 0
    while x < LEN:
        w = random.randint(2, 4)
        h = random.randint(3, 8)
        for c in range(x, min(x + w, LEN)):
            btop[c] = H - 1 - h
            for y in range(H - h, H - 1):
                if random.random() < 0.07:
                    bdot[y * LEN + c] = random.randint(1, 2)
        x += w
    # the cluster in front: one tall tower, the rest lower
    x = random.randint(0, 1)
    last = -1
    tall = random.randint(0, 2)
    n = 0
    while x < LEN - 2:
        w = random.randint(3, 5)
        if x + w > LEN:
            w = LEN - x
        h = random.randint(11, 13) if n >= tall else random.randint(5, 10)
        # keep the moon clear (the tall tower waits for the next spot)
        if abs(x + w / 2 - moon_x) < w / 2 + MOON_R + 0.5:
            h = min(h, 7)
        elif n >= tall:
            tall = 99
        shade = random.randrange(len(WALLS))
        while shade == last:
            shade = random.randrange(len(WALLS))
        last = shade
        style = random.choice((0, 1, 2, 2))
        b = random.randrange(len(BIAS))
        stepped = w >= 4 and h >= 7 and random.random() < 0.45
        for c in range(x, x + w):
            hh = h + 1 if stepped and x < c < x + w - 1 else h
            top[c] = H - 1 - hh
            wallc[c] = shade
            bias[c] = b
        for c in range(x + 1, x + w - 1):
            k = c - x
            if style != 1 and k % 2 == 0 and w > 3:
                continue
            for y in range(top[c] + 1, H - 2):
                if style != 2 and (H - 3 - y) % 2:
                    continue
                i = y * LEN + c
                win[i] = light(c) if random.random() < LIT else 1
                wins[nwin] = i
                nwin += 1
        if h >= 8 and nant < MAX_ANT and random.random() < 0.6:
            c = x + w // 2
            ant_x[nant] = c
            ant_y[nant] = max(0, top[c] - random.randint(1, 3))
            nant += 1
        n += 1
        x += w + random.choice((0, 0, 1, 1, 2))


def light(c):
    return 2 + random.choice(BIAS[bias[c]])


def moon_age():
    """Days since the last new moon, from the board's clock."""
    try:
        y, m, d, hh = now()[:4]
    except Exception:
        return 7.4
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    days = (1461 * (y + 4716)) // 4 + (306001 * (m + 1)) // 10000 + d + 2 - a + a // 4 - 1525 - 2451550
    return (days + 0.5 - 0.26 + (hh + 8) / 24) % 29.530588


def make_moon(g, cx, cy, R):
    """The moon as a list of (x, y, pen): anti-aliased disc, shadow side, faint glow."""
    ang = moon_age() / 29.530588 * 6.283185
    c = math.cos(ang)
    waxing = ang < 3.141593
    lit_rgb = (230, 225, 185)
    dark_rgb = (15, 15, 30)
    out = []
    for py in range(int(cy - R - 2), int(cy + R + 3)):
        if py < 0 or py >= H:
            continue
        sky = sky_rgb(py)
        for px in range(int(cx - R - 2), int(cx + R + 3)):
            if px < 0 or px >= W:
                continue
            inside = lit = 0
            for sy_ in range(4):
                for sx_ in range(4):
                    dx = px + (sx_ + 0.5) / 4 - cx
                    dy = py + (sy_ + 0.5) / 4 - cy
                    if dx * dx + dy * dy <= R * R:
                        inside += 1
                        hw = math.sqrt(max(0.0, R * R - dy * dy))
                        if (dx > hw * c) if waxing else (dx < -hw * c):
                            lit += 1
            dx = px + 0.5 - cx
            dy = py + 0.5 - cy
            dist = math.sqrt(dx * dx + dy * dy)
            glow = max(0.0, 1 - (dist - R) / 2.5) * 0.10 * (0.3 + 0.7 * (1 - c) / 2)
            if inside == 0 and glow <= 0.01:
                continue
            fi = inside / 16
            fl = lit / 16
            col = [sky[k] * (1 - fi) + lit_rgb[k] * fl + dark_rgb[k] * (fi - fl) + lit_rgb[k] * glow * (1 - fi) for k in range(3)]
            out.append((px, py, g.create_pen(int(min(255, col[0])), int(min(255, col[1])), int(min(255, col[2])))))
    return out


def frame(su, g, t):
    global tick, toggle_acc, lit_now, lit_t, moonpix, moon_t, a_was
    global plane_on, plane_x, plane_y, plane_d, plane_v, next_plane
    global shoot_on, shoot_x, shoot_y, shoot_vx, shoot_vy, shoot_life, next_shoot
    global car_on, car_x, car_d, car_v, next_car
    tick += 1
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was:
        new_skyline()
    a_was = a

    # fewer lights on after midnight, checked once a minute
    if t - lit_t > 60:
        lit_t = t
        try:
            hr = now()[3]
        except Exception:
            hr = 20
        lit_now = LIT * (0.65 if hr < 5 else (1.0 if hr >= 17 else 0.8))
    # windows switching one by one; settles at lit_now of them on
    toggle_acc += WINDOW_RATE * FRAME
    while toggle_acc >= 1 and nwin:
        toggle_acc -= 1
        i = wins[random.randrange(nwin)]
        if win[i] == 1:
            if random.random() < lit_now:
                win[i] = light(i % LEN)
        elif random.random() > lit_now:
            win[i] = 1

    # ---- sky and stars ----
    for y in range(H):
        g.set_pen(SKY[y])
        g.rectangle(0, y, W, 1)
    tw = int(tick * TWINKLE)
    for i in range(STARS):
        v = TWT[(sph[i] + tw * (1 + (i & 1))) & 63] * sbr[i] // 15
        if v > 1:
            g.set_pen(STARP[v])
            g.pixel(sx[i], sy[i])
    if MOON:
        if t - moon_t > 600:
            moon_t = t
            moonpix = make_moon(g, moon_x, 3.5, MOON_R)
        for px, py, pen in moonpix:
            g.set_pen(pen)
            g.pixel(px, py)

    # ---- the far-off towers ----
    for x in range(W):
        y0 = btop[x]
        g.set_pen(BACKP)
        g.rectangle(x, y0, 1, H - 1 - y0)
        for y in range(y0 + 1, H - 1):
            d = bdot[y * LEN + x]
            if d:
                g.set_pen(BDOTP[d - 1])
                g.pixel(x, y)

    # ---- aeroplane ----
    if not plane_on and t >= next_plane:
        plane_on = True
        plane_d = random.choice((-1, 1))
        plane_x = -2.0 if plane_d > 0 else W + 1.0
        plane_y = random.randint(0, 3)
        plane_v = random.uniform(1.2, 2.2)
    if plane_on:
        plane_x += plane_d * plane_v * FRAME
        px = int(plane_x)
        k = tick % 30
        g.set_pen(PLANE[0])
        g.pixel(px - plane_d, plane_y)
        g.set_pen(PLANE[1] if k < 14 else PLANE[0])
        g.pixel(px, plane_y)
        if k in (20, 21):
            g.set_pen(PLANE[2])
            g.pixel(px - plane_d, plane_y)
        if px < -3 or px > W + 3:
            plane_on = False
            next_plane = t + random.uniform(*PLANE_S)

    # ---- shooting star ----
    if not shoot_on and t >= next_shoot:
        shoot_on = True
        shoot_x = random.uniform(3, W - 3)
        shoot_y = random.uniform(-1, 2)
        shoot_vx = random.choice((-1, 1)) * random.uniform(10, 16)
        shoot_vy = random.uniform(6, 10)
        shoot_life = random.randint(10, 15)
    if shoot_on:
        shoot_x += shoot_vx * FRAME
        shoot_y += shoot_vy * FRAME
        shoot_life -= 1
        fade = min(15, shoot_life * 2)
        for k in range(6):
            x = int(shoot_x - shoot_vx * FRAME * k)
            y = int(shoot_y - shoot_vy * FRAME * k)
            v = fade * (6 - k) // 6
            if v > 0 and 0 <= x < W and 0 <= y < H:
                g.set_pen(SHOOTP[v])
                g.pixel(x, y)
        if shoot_life <= 0:
            shoot_on = False
            next_shoot = t + random.uniform(*SHOOT_S)

    # ---- the towers ----
    for x in range(W):
        y0 = top[x]
        if y0 >= H - 1:
            continue
        g.set_pen(WALLP[wallc[x]])
        g.rectangle(x, y0, 1, H - 1 - y0)
        for y in range(y0 + 1, H - 2):
            v = win[y * LEN + x]
            if v > 1:
                if v == 6:
                    g.set_pen(TVP[((tick >> 2) * 7 + x * 3 + y) % 4])
                else:
                    g.set_pen(TINTP[v - 2])
                g.pixel(x, y)
    # masts with slow red beacons
    b = (tick % 60)
    b = 15 - abs(b - 30) if 20 <= b <= 40 else 0
    b = b * 3 // 2 if b < 10 else 15
    for n in range(nant):
        x = ant_x[n]
        g.set_pen(WALLP[wallc[x]])
        g.rectangle(x, ant_y[n], 1, top[x] - ant_y[n])
        g.set_pen(BEACON[b if b else 2])
        g.pixel(x, ant_y[n])

    # ---- the street and the odd car ----
    g.set_pen(STREET)
    g.rectangle(0, H - 1, W, 1)
    if not car_on and t >= next_car:
        car_on = True
        car_d = random.choice((-1, 1))
        car_x = -3.0 if car_d > 0 else W + 2.0
        car_v = random.uniform(3.0, 5.0)
    if car_on:
        car_x += car_d * car_v * FRAME
        cx = int(car_x)
        for k in range(4):                    # glow ahead, headlight, body, tail light
            px = cx + car_d * (1 - k)
            if 0 <= px < W:
                g.set_pen(CARP[k])
                g.pixel(px, H - 1)
        if cx < -4 or cx > W + 4:
            car_on = False
            next_car = t + random.uniform(*CAR_S)
    return FRAME
