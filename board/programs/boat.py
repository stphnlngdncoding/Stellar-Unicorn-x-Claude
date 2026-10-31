# Boat: a little sailboat rides the waves while the weather comes and goes.
# On sunny spells the sea is blue and gentle, the sun shines and white clouds
# drift by. Then the sky darkens, the rain slants in, the waves heap up with
# whitecaps and the boat gets tossed about (with the odd flash of lightning),
# until it clears again.
#   A = change the weather now
#
# Memory-friendly: every colour for every shade of weather is a pen made once
# in setup(); raindrops live in a fixed pool; nothing is allocated per frame.
import math
import random
from stellar import StellarUnicorn

SUNNY_S = (20, 45)   # how long sunny spells last (seconds)
RAINY_S = (15, 35)   # how long rainy spells last (seconds)
CHANGE_S = 6         # how long the weather takes to turn
CALM_WAVES = 0.7     # wave height on a sunny day (pixels)
STORM_WAVES = 2.6    # wave height in a storm (pixels)
TOSS = 1.0           # how hard the boat gets thrown about in storms
RAIN = 1.0           # how heavy the rain is
LIGHTNING = 1.0      # how often lightning strikes in a storm (0 = never)
SEA = 10.0           # where the sea is at rest (row)
FRAME = 0.04

STEPS = 12           # shades of weather from sunny (0) to stormy (STEPS - 1)
DROPS = 40

def mix(a, b, f):
    return (int(a[0] + (b[0] - a[0]) * f), int(a[1] + (b[1] - a[1]) * f), int(a[2] + (b[2] - a[2]) * f))

def setup(su, g):
    global SKY, WATER, FOAM, CLOUD, SUN, GLOW, RAINPEN, SPLASH, FLASH, BOLT
    global HULL, HULL2, SAIL, MAST, FLAG, drops, clouds
    global w, target, next_change, bx, by, vy, tilt, vt, last_t, flash, a_was, phase
    SKY, WATER, FOAM, CLOUD, SUN, GLOW = [], [], [], [], [], []
    for k in range(STEPS):
        f = k / (STEPS - 1)
        SKY.append([g.create_pen(*mix(mix((40, 110, 230), (150, 205, 255), y / 12),
                                      mix((22, 25, 38), (70, 76, 92), y / 12), f)) for y in range(16)])
        WATER.append([g.create_pen(*mix(mix((45, 175, 205), (8, 50, 130), d / 5),
                                        mix((62, 82, 98), (12, 20, 34), d / 5), f)) for d in range(6)])
        FOAM.append(g.create_pen(*mix((210, 245, 255), (185, 195, 205), f)))
        CLOUD.append(g.create_pen(*mix((235, 240, 250), (55, 58, 70), f)))
        SUN.append(g.create_pen(*mix((255, 225, 90), (40, 40, 50), f)))
        GLOW.append(g.create_pen(*mix((140, 160, 200), (30, 32, 45), f)))
    RAINPEN = (g.create_pen(150, 175, 220), g.create_pen(70, 85, 120))
    SPLASH = g.create_pen(170, 190, 215)
    FLASH = g.create_pen(200, 200, 230)
    BOLT = g.create_pen(255, 255, 220)
    HULL = g.create_pen(170, 75, 30)
    HULL2 = g.create_pen(110, 45, 18)
    SAIL = g.create_pen(250, 248, 235)
    MAST = g.create_pen(120, 80, 40)
    FLAG = g.create_pen(255, 40, 40)
    drops = [[0.0, 0.0, False] for _ in range(DROPS)]
    clouds = [[random.uniform(0, 16), random.uniform(1, 4), random.uniform(0.15, 0.5)] for _ in range(3)]
    w = 0.0
    target = 0.0
    next_change = random.uniform(*SUNNY_S)
    bx = 7.5
    by = SEA - 1
    vy = 0.0
    tilt = 0.0
    vt = 0.0
    last_t = 0.0
    flash = 0
    a_was = False
    phase = 0.0

def surface(x, t, amp):
    """Height of the sea at column x (row number, smaller = higher)."""
    return SEA - amp * (0.6 * math.sin(x * 0.55 + t * 1.3) + 0.4 * math.sin(x * 1.1 - t * 1.9 + 1.3)) \
        - w * 0.35 * math.sin(x * 2.3 + t * 3.7)

def put(g, dx, dy, pen):
    """Draw one pixel of the boat, rolled by the current tilt."""
    g.set_pen(pen)
    g.pixel(cx + dx + int(round(-tilt * dy * 0.5)), cy + dy + int(round(tilt * dx * 0.5)))

def frame(su, g, t):
    global w, target, next_change, bx, by, vy, tilt, vt, last_t, flash, a_was, phase, cx, cy
    dt = t - last_t
    if dt > 0.1:
        dt = 0.1
    last_t = t
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if (a and not a_was) or t >= next_change:
        target = 1.0 - target
        next_change = t + random.uniform(*(RAINY_S if target else SUNNY_S))
    a_was = a
    # the weather turns slowly
    step = dt / CHANGE_S
    if w < target:
        w = min(target, w + step)
    elif w > target:
        w = max(target, w - step)
    k = int(w * (STEPS - 1) + 0.5)
    amp = CALM_WAVES + (STORM_WAVES - CALM_WAVES) * w
    phase += dt * (0.8 + 0.6 * w)              # storms make the sea move faster
    tt = phase * 1.6

    # ---- the boat rides the swell, a little behind it, and rolls with the slope ----
    bx = 7.5 + 2.5 * math.sin(t * 0.09)           # it drifts slowly to and fro
    sea_here = surface(bx, tt, amp)
    slope = (surface(bx + 1.5, tt, amp) - surface(bx - 1.5, tt, amp)) / 3
    vy += ((sea_here - 1.0) - by) * 12 * dt - vy * 3 * dt
    if w > 0.5 and random.random() < 0.02 * TOSS * w:
        vy -= random.uniform(1.5, 4.0) * TOSS     # a big wave throws it up
    by += vy * dt
    if by < 4:
        by, vy = 4.0, 0.0
    elif by > 13:
        by, vy = 13.0, 0.0
    vt += (slope * 0.9 - tilt) * 10 * dt - vt * 3 * dt
    if w > 0.5 and random.random() < 0.03 * TOSS * w:
        vt += random.uniform(-1.0, 1.0) * TOSS
    tilt += vt * dt
    if tilt > 0.6:
        tilt, vt = 0.6, 0.0
    elif tilt < -0.6:
        tilt, vt = -0.6, 0.0

    # ---- sky ----
    sky = SKY[k]
    if flash:
        flash -= 1
    for y in range(16):
        g.set_pen(FLASH if flash > 1 else sky[y])
        g.rectangle(0, y, 16, 1)
    # the sun, fading behind the clouds as the weather turns
    if w < 0.8:
        g.set_pen(GLOW[k])
        for x, y in ((11, 2), (13, 2), (12, 1), (12, 3), (11, 1), (13, 1), (11, 3), (13, 3)):
            g.pixel(x, y)
        g.set_pen(SUN[k])
        g.pixel(12, 2)
        g.pixel(11, 2)
        g.pixel(13, 2)
        g.pixel(12, 1)
        g.pixel(12, 3)
    # clouds: small and white when it's fine, big and dark in a storm
    size = 1.2 + 2.3 * w
    g.set_pen(CLOUD[k])
    for c in clouds:
        c[0] += c[2] * dt * (1 + 2 * w)
        if c[0] > 16 + size * 2:
            c[0] = -size * 2
            c[1] = random.uniform(1, 4)
        ox, oy = c[0], c[1]
        for yy in range(int(oy - size * 0.6), int(oy + size * 0.6) + 1):
            for xx in range(int(ox - size * 1.6), int(ox + size * 1.6) + 1):
                if 0 <= xx < 16 and 0 <= yy < 8:
                    dx = (xx - ox) / (size * 1.6)
                    dy = (yy - oy) / (size * 0.6 + 0.3)
                    if dx * dx + dy * dy <= 1:
                        g.pixel(xx, yy)
    # lightning
    if w > 0.85 and flash == 0 and random.random() < 0.004 * LIGHTNING:
        flash = 4
    if flash > 1:
        g.set_pen(BOLT)
        x = random.randint(2, 13)
        for y in range(2, int(SEA)):
            g.pixel(x, y)
            x += random.choice((-1, 0, 1))

    # ---- the boat (drawn before the sea, so waves can wash over the hull) ----
    cx = int(bx + 0.5)
    cy = int(by + 0.5)
    for dx in (-2, -1, 0, 1, 2):
        put(g, dx, 0, HULL)
    for dx in (-1, 0, 1):
        put(g, dx, 1, HULL2)
    for dy in (-1, -2, -3):
        put(g, 0, dy, MAST)
    put(g, 1, -1, SAIL)
    put(g, 2, -1, SAIL)
    put(g, 1, -2, SAIL)
    put(g, 1, -3, SAIL)
    put(g, -1, -1, SAIL)
    put(g, 0, -4, FLAG)

    # ---- the sea ----
    water = WATER[k]
    foam = FOAM[k]
    for x in range(16):
        s = surface(x, tt, amp)
        top = int(s + 0.5)
        crest = s < SEA - amp * 0.55
        for y in range(top if top > 0 else 0, 16):
            d = y - top
            # leave the boat's hull showing above the water line
            if d == 0 and abs(x - cx) <= 2 and y <= cy:
                continue
            if d == 0 and (crest or (w > 0.6 and random.random() < 0.08)):
                g.set_pen(foam)
            else:
                g.set_pen(water[d if d < 6 else 5])
            g.pixel(x, y)

    # ---- rain ----
    if random.random() < w * RAIN * 1.6:
        for d in drops:
            if not d[2]:
                d[0] = random.uniform(-4, 16)
                d[1] = -1.0
                d[2] = True
                break
    slant = 4 + 6 * w
    for d in drops:
        if d[2]:
            d[1] += 18 * dt
            d[0] += slant * dt
            x, y = int(d[0]), int(d[1])
            if y >= surface(x, tt, amp) or x > 15:
                if 0 <= x < 16 and y < 16:
                    g.set_pen(SPLASH)
                    g.pixel(x, y - 1)
                d[2] = False
                continue
            g.set_pen(RAINPEN[0])
            g.pixel(x, y)
            g.set_pen(RAINPEN[1])
            g.pixel(x - 1, y - 1)
    return FRAME
