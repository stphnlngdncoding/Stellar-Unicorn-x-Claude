# World: a little meadow that follows the real sky over Marina del Rey.
# The sun and moon rise, cross and set where they really are right now
# (worked out on the board from the clock), the moon shows its real phase,
# the sky glows at dawn and dusk, and the weather comes from a live report
# (Open-Meteo, fetched over plain HTTP every 15 minutes): sun, clouds, fog,
# rain, snow or a thunderstorm. By day butterflies flutter, a bunny hops
# about and birds fly over; at night the stars come out and fireflies drift
# and glimmer in the grass.
#   A = fast-forward through a day (press again for real time)
#
# Memory-friendly: the sky is cached as one pen per pixel and refreshed every
# couple of seconds; critters and raindrops live in fixed pools.
import math
import random
import time
import json
from stellar import StellarUnicorn

LAT = 33.98          # where you are (degrees north)
LON = -118.46        # (degrees east; west is negative)
WEATHER = 0          # 0 = live report, 1 clear, 2 cloudy, 3 rain, 4 storm, 5 fog, 6 snow
FAST = 0             # 1 = a whole day in about 2 minutes (to watch the cycle)
FETCH_MIN = 15       # minutes between weather reports
BUTTERFLIES = 3
FIREFLIES = 10
CRITTERS = 1         # 1 = a bunny hops about by day, 0 = none
STARS = 22
CONTRAST = 1.5       # higher = deeper darks and punchier colours (1 = flat)
FRAME = 0.04

HZ = 11              # horizon: rows 0..10 are sky, the meadow starts at 11

# ---------------------------------------------------------------- sky maths
def rad(d):
    return d * 0.017453292519943295

def deg(r):
    return r * 57.29577951308232

def days_since_j2000(tm):
    """Days since 2000-01-01 12:00 UTC, split as (whole days, fraction)."""
    y, m, d, hh, mi, ss = tm[0], tm[1], tm[2], tm[3], tm[4], tm[5]
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd0 = (1461 * (y + 4716)) // 4 + (306001 * (m + 1)) // 10000 + d + b - 1525   # JD - 0.5 at 0h
    frac = (hh + mi / 60 + ss / 3600) / 24 + 0.5
    ni = jd0 - 2451545
    if frac >= 1:
        frac -= 1
        ni += 1
    return ni, frac

def to_alt_az(ra, dec, ni, nf):
    """Equatorial (degrees) to altitude and azimuth (degrees) for our spot."""
    gmst = (18.697374558 + 24 * nf + 0.06570982441908 * (ni + nf)) % 24
    h = rad((gmst * 15 + LON - ra) % 360)
    la = rad(LAT)
    de = rad(dec)
    alt = math.asin(math.sin(la) * math.sin(de) + math.cos(la) * math.cos(de) * math.cos(h))
    az = math.atan2(-math.sin(h), math.tan(de) * math.cos(la) - math.sin(la) * math.cos(h))
    return deg(alt), deg(az) % 360

def sky_now(tm):
    """Sun and moon altitude/azimuth, the moon's lit fraction and whether it's waxing."""
    ni, nf = days_since_j2000(tm)
    n = ni + nf
    eps = rad(23.439)
    # the sun
    L = (280.460 + 0.9856474 * n) % 360
    g = rad((357.528 + 0.9856003 * n) % 360)
    lam = rad(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    ra = deg(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam)))
    dec = deg(math.asin(math.sin(eps) * math.sin(lam)))
    s_alt, s_az = to_alt_az(ra, dec, ni, nf)
    # the moon (good to a degree or so)
    lp = (218.316 + 13.176396 * n) % 360
    mp = rad((134.963 + 13.064993 * n) % 360)
    f = rad((93.272 + 13.229350 * n) % 360)
    mlam = rad(lp + 6.289 * math.sin(mp))
    mbet = rad(5.128 * math.sin(f))
    mra = deg(math.atan2(math.sin(mlam) * math.cos(eps) - math.tan(mbet) * math.sin(eps), math.cos(mlam)))
    mdec = deg(math.asin(math.sin(mbet) * math.cos(eps) + math.cos(mbet) * math.sin(eps) * math.sin(mlam)))
    m_alt, m_az = to_alt_az(mra, mdec, ni, nf)
    elong = mlam - lam
    lit = (1 - math.cos(elong)) / 2
    waxing = math.sin(elong) > 0
    return s_alt, s_az, m_alt, m_az, lit, waxing

def place(alt, az):
    """Where something at this altitude/azimuth sits on the board (east left, west right)."""
    a = az
    if a < 60:
        a = 60
    elif a > 300:
        a = 300
    x = (a - 60) / 240 * 15
    y = (HZ - 0.5) - alt / 75 * (HZ - 1)
    return x, y

# ---------------------------------------------------------------- weather
def fetch_weather():
    """Ask Open-Meteo for the weather here. Returns (kind, cloud 0..1, wind km/h) or None."""
    import socket
    s = None
    try:
        host = "api.open-meteo.com"
        path = "/v1/forecast?latitude=%.2f&longitude=%.2f&current=weather_code,cloud_cover,wind_speed_10m" % (LAT, LON)
        addr = socket.getaddrinfo(host, 80)[0][-1]
        s = socket.socket()
        s.settimeout(4)
        s.connect(addr)
        s.send(("GET %s HTTP/1.0\r\nHost: %s\r\nUser-Agent: unicorn\r\n\r\n" % (path, host)).encode())
        data = b""
        while len(data) < 4000:
            c = s.recv(512)
            if not c:
                break
            data += c
        body = data.split(b"\r\n\r\n", 1)[1]
        cur = json.loads(body.decode())["current"]
        code = cur["weather_code"]
        cloud = cur["cloud_cover"] / 100
        wind = cur["wind_speed_10m"]
        if code >= 95:
            kind = 4
        elif code in (71, 73, 75, 77, 85, 86):
            kind = 6
        elif code >= 51:
            kind = 3
        elif code in (45, 48):
            kind = 5
        elif code == 3 or cloud > 0.8:
            kind = 2
        else:
            kind = 1
        return kind, cloud, wind
    except Exception as e:
        print("world: weather fetch failed", repr(e))
        return None
    finally:
        if s:
            s.close()

# ---------------------------------------------------------------- colours
def pen(g, c):
    """A pen for an (r, g, b) colour, through the contrast curve."""
    return g.create_pen(CURVE[c[0]], CURVE[c[1]], CURVE[c[2]])

def mix(a, b, f):
    if f <= 0:
        return a
    if f >= 1:
        return b
    return (int(a[0] + (b[0] - a[0]) * f), int(a[1] + (b[1] - a[1]) * f), int(a[2] + (b[2] - a[2]) * f))

DAY_TOP, DAY_LOW = (25, 95, 240), (140, 205, 255)
NIGHT_TOP, NIGHT_LOW = (3, 4, 20), (28, 38, 90)
DUSK_GLOW = (255, 110, 40)
GREY_DAY, GREY_NIGHT = (125, 135, 150), (24, 26, 36)
GRASS_DAY, GRASS_NIGHT = (60, 190, 50), (20, 70, 35)
SOIL_DAY, SOIL_NIGHT = (20, 80, 25), (6, 24, 14)

def setup(su, g):
    global sky, rowcol, ground_pen, hills, flowers, stars, butterflies, flies, drops, clouds, bird, bunny
    global weather, cloud, cloud_t, rain, rain_t, wind, next_fetch, light, sun, moon, astro_next
    global last_t, a_was, fast, sky_next, flash, BLACK, WHITE, CURVE
    CURVE = bytes(int(255 * (i / 255) ** CONTRAST + 0.5) for i in range(256))
    BLACK = g.create_pen(0, 0, 0)
    WHITE = g.create_pen(255, 255, 255)
    sky = [0] * 256
    rowcol = [(0, 0, 0)] * (HZ + 1)
    ground_pen = [0] * 256
    hills = bytearray(16)
    h = random.uniform(0.4, 1.2)
    for x in range(16):
        h += random.uniform(-0.45, 0.45)
        h = min(1.6, max(0.0, h))
        hills[x] = HZ - int(h + 0.5)         # first grass row in this column
    flowers = [(random.randrange(16), random.randint(13, 15), random.choice(((255, 90, 140), (255, 220, 60), (180, 120, 255), (255, 255, 255))))
               for _ in range(7)]
    stars = [(random.randrange(16), random.randrange(HZ - 2), random.randrange(64), random.randint(120, 255)) for _ in range(STARS)]
    butterflies = [[random.uniform(1, 14), random.uniform(5, 11), 0.0, 0.0,
                    random.choice(((255, 150, 30), (255, 230, 60), (90, 170, 255), (255, 110, 200), (255, 255, 255)))]
                   for _ in range(BUTTERFLIES)]
    flies = [[random.uniform(0, 15), random.uniform(7, 14), 0.0, 0.0, random.randint(20, 160), -1, 0]
             for _ in range(FIREFLIES)]
    drops = [[0.0, 0.0, False] for _ in range(40)]
    clouds = [[random.uniform(-4, 18), random.uniform(1, 6), random.uniform(0.2, 0.6), random.uniform(1.2, 2.6)] for _ in range(4)]
    bird = [0.0, 0.0, 0.0, False]            # x, y, speed, flying
    bunny = [random.uniform(2, 13), 1, 0.0, 0.0, 0]   # x, direction, hop phase, timer, state
    weather, cloud_t, rain_t, wind = 1, 0.2, 0.0, 8.0
    cloud, rain = cloud_t, rain_t
    next_fetch = 0.0
    light = 1.0
    sun = moon = None
    astro_next = 0.0
    sky_next = 0.0
    last_t = 0.0
    a_was = False
    fast = FAST
    flash = 0

def now_utc(t):
    if fast:
        return time.gmtime(int(time.time() + t * 720))
    return time.gmtime()

def rebuild_sky(g):
    """Work out one colour per sky pixel for the current light, clouds and glow."""
    s_alt = sun[0]
    sx = sun[2]
    dusk = 0.0
    if -10 < s_alt < 10:
        dusk = 1 - abs(s_alt) / 10                       # glow round sunrise and sunset
    dusk *= 1 - cloud * 0.7
    grey = mix(GREY_NIGHT, GREY_DAY, light * (1 - cloud * 0.3))
    fog = 0.7 if weather == 5 else 0.0
    for y in range(HZ + 1):
        top = mix(NIGHT_TOP, DAY_TOP, light)
        low = mix(NIGHT_LOW, DAY_LOW, light)
        base = mix(top, low, y / HZ)
        base = mix(base, grey, cloud * 0.6)
        rowcol[y] = base
        for x in range(16):
            c = base
            if dusk > 0 and y > 3:
                d = abs(x - sx)
                k = dusk * (y - 3) / (HZ - 3) * (1 - d / 22)
                c = mix(c, DUSK_GLOW, k * 0.8)
            if fog:
                c = mix(c, grey, fog * (0.4 + 0.6 * y / HZ))
            sky[y * 16 + x] = pen(g, c)
    for i in range(256):
        x, y = i & 15, i >> 4
        if y >= hills[x]:
            depth = y - hills[x]
            gc = mix(GRASS_NIGHT, GRASS_DAY, light)
            sc = mix(SOIL_NIGHT, SOIL_DAY, light)
            col = gc if depth == 0 else mix(gc, sc, depth / 4)
            if fog:
                col = mix(col, grey, fog * 0.4)
            ground_pen[i] = pen(g, col)

def frame(su, g, t):
    global weather, cloud, cloud_t, rain, rain_t, wind, next_fetch, light, sun, moon, astro_next
    global last_t, a_was, fast, sky_next, flash
    dt = t - last_t
    if dt > 0.1:
        dt = 0.1
    last_t = t
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was:
        fast = 0 if fast else 1
        astro_next = sky_next = 0.0
    a_was = a

    # ---- weather: a live report every so often, eased in gently ----
    if WEATHER:
        weather = WEATHER
        cloud_t = (0.1, 0.1, 0.9, 0.95, 1.0, 0.8, 0.9)[WEATHER]
        rain_t = (0, 0, 0, 0.7, 1.0, 0, 0.7)[WEATHER]
    elif t >= next_fetch:
        rep = fetch_weather()
        next_fetch = t + (FETCH_MIN * 60 if rep else 300)
        if rep:
            weather, c, wind = rep
            cloud_t = max(c, (0, 0, 0.85, 0.9, 1.0, 0.7, 0.9)[weather])
            rain_t = (0, 0, 0, 0.6, 1.0, 0, 0.6)[weather]
    cloud += (cloud_t - cloud) * min(1, dt * 0.3)
    rain += (rain_t - rain) * min(1, dt * 0.3)

    # ---- sun and moon from the clock ----
    if t >= astro_next:
        astro_next = t + (0.5 if fast else 20)
        s_alt, s_az, m_alt, m_az, lit, waxing = sky_now(now_utc(t))
        sx, sy = place(s_alt, s_az)
        mx, my = place(m_alt, m_az)
        sun = (s_alt, s_az, sx, sy)
        moon = (m_alt, m_az, mx, my, lit, waxing)
        light = min(1.0, max(0.0, (s_alt + 6) / 14))     # civil twilight to full day
    if t >= sky_next:
        sky_next = t + (0.5 if fast else 2.0)
        rebuild_sky(g)

    stormy = weather == 4
    wet = rain > 0.15
    snowy = weather == 6

    # ---- sky ----
    if flash:
        flash -= 1
    for i in range(HZ * 16 + 16):
        x, y = i & 15, i >> 4
        if y >= hills[x]:
            continue
        g.set_pen(WHITE if flash > 1 else sky[i])
        g.pixel(x, y)
    # stars, behind the clouds
    if light < 0.4:
        sv = (0.4 - light) / 0.4 * (1 - cloud)
        tick = int(t * 6)
        for x, y, ph, b in stars:
            v = int(b * sv * (0.6 + 0.4 * math.sin((tick + ph) * 0.4)))
            if v > 12 and y < hills[x]:
                g.set_pen(pen(g, (v, v, min(255, v + 25))))
                g.pixel(x, y)
    # the moon, with its real phase (pale by day)
    m_alt, m_az, mx, my, lit, waxing = moon
    if m_alt > -2:
        draw_moon(g, int(mx + 0.5), int(my + 0.5), lit, waxing, 0.35 + 0.65 * (1 - light), cloud)
    # the sun, reddening near the horizon
    s_alt, s_az, sx, sy = sun
    if s_alt > -1.5:
        draw_sun(g, int(sx + 0.5), int(sy + 0.5), s_alt, cloud)
    # clouds drift with the wind
    cg = mix(mix((70, 74, 95), (250, 252, 255), light), mix((50, 52, 64), (150, 155, 168), light), max(0, cloud - 0.6) * 1.5)
    if sun[0] > -8 and sun[0] < 8:
        cg = mix(cg, (255, 150, 110), (1 - abs(sun[0]) / 8) * 0.4)
    cpen = pen(g, cg)
    size = 0.8 + 2.4 * cloud
    g.set_pen(cpen)
    shown = 1 + int(cloud * 3.99)
    for k in range(4):
        c = clouds[k]
        c[0] += c[2] * dt * (0.3 + wind / 20)
        if c[0] > 18 + size * 2:
            c[0] = -size * 2.5
            c[1] = random.uniform(1, 6)
        if k >= shown or cloud < 0.08:
            continue
        ox, oy, sz = c[0], c[1], size * c[3] / 2
        for yy in range(int(oy - sz * 0.6), int(oy + sz * 0.6) + 1):
            for xx in range(int(ox - sz * 1.7), int(ox + sz * 1.7) + 1):
                if 0 <= xx < 16 and 0 <= yy < hills[xx]:
                    dx = (xx - ox) / (sz * 1.7)
                    dy = (yy - oy) / (sz * 0.6 + 0.3)
                    if dx * dx + dy * dy <= 1:
                        g.pixel(xx, yy)
    # lightning
    if stormy and flash == 0 and random.random() < 0.005:
        flash = 4
    if flash > 1:
        x = random.randint(2, 13)
        for y in range(1, HZ):
            g.pixel(x, y)
            x += random.choice((-1, 0, 1))

    # ---- meadow ----
    for i in range(256):
        x, y = i & 15, i >> 4
        if y >= hills[x]:
            g.set_pen(ground_pen[i])
            g.pixel(x, y)
    # flowers open by day
    if light > 0.3:
        for x, y, c in flowers:
            if y > hills[x]:
                g.set_pen(pen(g, mix((10, 20, 10), c, light)))
                g.pixel(x, y)
    # a little tree on the left
    tr = mix((20, 12, 6), (90, 55, 25), light)
    lf = mix((3, 14, 8), (30, 110, 40), light)
    g.set_pen(pen(g, tr))
    g.pixel(2, hills[2] - 1)
    g.pixel(2, hills[2] - 2)
    g.set_pen(pen(g, lf))
    for dx, dy in ((-1, -3), (0, -3), (1, -3), (-1, -4), (0, -4), (1, -4), (0, -5), (-2, -3), (2, -3)):
        g.pixel(2 + dx, hills[2] + dy)

    # ---- daytime critters ----
    day = light > 0.55 and not wet and not snowy
    if day:
        for b in butterflies:
            b[2] += random.uniform(-0.6, 0.6) * dt * 10
            b[3] += random.uniform(-0.6, 0.6) * dt * 10
            b[2] = max(-2.0, min(2.0, b[2]))
            b[3] = max(-1.5, min(1.5, b[3]))
            b[0] += b[2] * dt
            b[1] += b[3] * dt
            if b[0] < 0.5 or b[0] > 14.5:
                b[2] = -b[2]
                b[0] = min(14.5, max(0.5, b[0]))
            if b[1] < 4 or b[1] > HZ + 2:
                b[3] = -b[3]
                b[1] = min(HZ + 2.0, max(4.0, b[1]))
            x, y = int(b[0]), int(b[1])
            g.set_pen(pen(g, b[4]))
            g.pixel(x, y)
            if int(t * 8 + b[0]) % 2:              # wings open
                g.pixel(x + 1, y)
        # a bunny hops about
        if CRITTERS:
            draw_bunny(g, t, dt)
        # now and then a bird flies over
        if not bird[3] and random.random() < dt * 0.06:
            bird[0], bird[1], bird[2], bird[3] = -2.0, random.uniform(1.5, 5), random.uniform(3, 5), True
        if bird[3]:
            bird[0] += bird[2] * dt
            bird[1] += math.sin(t * 2) * dt * 0.5
            if bird[0] > 17:
                bird[3] = False
            x, y = int(bird[0]), int(bird[1])
            g.set_pen(pen(g, mix((30, 30, 40), (40, 40, 50), light)))
            g.pixel(x, y)
            if int(t * 6) % 2:
                g.pixel(x - 1, y - 1)
                g.pixel(x + 1, y - 1)
            else:
                g.pixel(x - 1, y)
                g.pixel(x + 1, y)

    # ---- night: fireflies glimmer over the grass ----
    if light < 0.35 and rain < 0.5 and not snowy:
        for f in flies:
            f[2] += random.uniform(-0.3, 0.3) * dt * 6
            f[3] += random.uniform(-0.3, 0.3) * dt * 6
            f[2] = max(-0.8, min(0.8, f[2]))
            f[3] = max(-0.5, min(0.5, f[3]))
            f[0] += f[2] * dt
            f[1] += f[3] * dt
            if f[0] < 0 or f[0] > 15:
                f[2] = -f[2]
                f[0] = min(15.0, max(0.0, f[0]))
            if f[1] < 6 or f[1] > 14:
                f[3] = -f[3]
                f[1] = min(14.0, max(6.0, f[1]))
            if f[5] < 0:
                f[4] -= 1
                if f[4] <= 0:
                    f[5] = 0
                    f[6] = random.randint(50, 130)
                continue
            k = f[5]
            v = random.randint(150, 255)
            if k < 8:
                v = v * (k + 1) // 8
            elif k > f[6] - 15:
                v = v * (f[6] - k) // 15
            f[5] += 1
            if f[5] >= f[6]:
                f[5] = -1
                f[4] = random.randint(60, 260)
            if v > 10:
                g.set_pen(pen(g, (v * 3 // 4, v, v // 5)))
                g.pixel(int(f[0] + 0.5), int(f[1] + 0.5))

    # ---- rain and snow ----
    if rain > 0.05 and random.random() < rain * (1.8 if not snowy else 0.9):
        for d in drops:
            if not d[2]:
                d[0] = random.uniform(-4, 16)
                d[1] = -1.0
                d[2] = True
                break
    slant = 1 + wind / 6
    rp = pen(g, mix((50, 60, 90), (150, 175, 220), max(light, 0.3)))
    sp = pen(g, mix((120, 120, 130), (245, 245, 255), max(light, 0.4)))
    for d in drops:
        if d[2]:
            if snowy:
                d[1] += 3.5 * dt
                d[0] += (slant * 0.3 + math.sin(t * 2 + d[1]) * 0.8) * dt
            else:
                d[1] += 16 * dt
                d[0] += slant * dt
            x, y = int(d[0]), int(d[1])
            if y > 15 or x > 15 or (0 <= x < 16 and y >= hills[x] + (1 if snowy else 0)):
                d[2] = False
                continue
            if 0 <= x < 16 and y >= 0:
                g.set_pen(sp if snowy else rp)
                g.pixel(x, y)
                if not snowy and y > 0:
                    g.pixel(x - 1, y - 1)
    return FRAME

def draw_sun(g, x, y, alt, cloud):
    """A 2x2 sun with a soft halo, redder near the horizon, veiled by cloud."""
    warm = 1 - min(1, max(0, alt / 12))
    core = mix((255, 248, 190), (255, 125, 45), warm)
    veil = mix(DAY_LOW, GREY_DAY, cloud)
    core = mix(core, veil, cloud * 0.75)
    halo = mix(core, mix(DAY_LOW, DUSK_GLOW, warm), 0.55)
    if cloud < 0.85:
        g.set_pen(pen(g, halo))
        for dx, dy in ((0, -1), (1, -1), (0, 2), (1, 2), (-1, 0), (-1, 1), (2, 0), (2, 1)):
            px, py = x + dx, y + dy
            if 0 <= px < 16 and 0 <= py < hills[px]:
                g.pixel(px, py)
    g.set_pen(pen(g, core))
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        px, py = x + dx, y + dy
        if 0 <= px < 16 and 0 <= py < hills[px]:
            g.pixel(px, py)

def draw_moon(g, x, y, lit, waxing, bright, cloud):
    """A small moon (3x3, corners rounded off), lit on the right while waxing and the
    left while waning. The dark part only shows faintly at night."""
    b = bright * (1 - cloud * 0.8)            # how strongly it shows through the sky
    base = rowcol[min(HZ, max(0, y))]
    on = pen(g, mix(base, (240, 238, 215), b))
    off = pen(g, mix(base, (30, 32, 46), b)) if light < 0.25 else None
    edge = 1.5 * (1 - 2 * lit)                 # terminator position across the disc
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx and dy:
                continue
            px, py = x + dx, y + dy
            if not (0 <= px < 16 and 0 <= py < hills[px]):
                continue
            side = dx if waxing else -dx
            if side + 0.5 > edge:
                g.set_pen(on)
            elif off is not None:
                g.set_pen(off)
            else:
                continue
            g.pixel(px, py)

def draw_bunny(g, t, dt):
    b = bunny
    b[3] -= dt
    if b[3] <= 0:
        b[4] = random.choice((0, 1, 1, 2))      # 0 sit, 1 hop, 2 turn round
        b[3] = random.uniform(1.0, 3.5)
        if b[4] == 2:
            b[1] = -b[1]
            b[4] = 1
    hop = 0
    if b[4] == 1:
        b[2] += dt * 3
        b[0] += b[1] * dt * 2.2
        hop = 1 if (b[2] % 1) < 0.5 else 0
        if b[0] < 4 or b[0] > 14:
            b[1] = -b[1]
            b[0] = min(14.0, max(4.0, b[0]))
    x = int(b[0])
    y = hills[min(15, max(0, x))] - 1 - hop
    g.set_pen(pen(g, (215, 185, 155)))
    g.pixel(x, y)
    g.pixel(x + b[1], y)
    g.pixel(x + b[1], y - 1)                     # ear
    g.set_pen(WHITE)
    g.pixel(x - b[1], y)                         # tail
