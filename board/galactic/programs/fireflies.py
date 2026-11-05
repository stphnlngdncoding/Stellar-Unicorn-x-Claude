# Fireflies: a summer night over a long meadow. Fireflies drift slowly through
# the dark. Every so often one lights up and stays lit for a few seconds,
# glimmering as it flies and leaving a short glowing streak, then fades out. Every firefly has
# its own colour and a depth: near ones are bigger, brighter, warmer and
# quicker; far ones are small, dim, greener and drift slowly. Now and then
# they all flash together in a wave that rolls along the meadow. Stars
# twinkle above the grass, and the moon hangs in the sky showing tonight's
# real phase (worked out from the board's clock).
# (Galactic Unicorn version: a wide meadow panorama.)
#   A = set off a flash wave now
#
# PACE slows the dark drifting and how often they light up: at the very
# bottom the fireflies barely creep and each one lights up only every few
# minutes, so catching one is a little surprise. Lit ones always fly at
# LIT_SPEED.
#
# Memory-friendly: positions are integers (1/4096 of a pixel), the trail is a
# bytearray, and every pen is made once in setup().
import math
import random
import time
from galactic import GalacticUnicorn

COUNT = 36           # how many fireflies
PACE = 1.0           # overall speed: dark drifting and how often they light up (0.01 = almost never)
MAX_SPEED = 9        # top speed for the nearest fireflies at PACE 1, 1/256 px per frame
DARK = (70, 280)     # frames a firefly stays dark between lights at PACE 1 (min, max)
LIT_S = (3.0, 6.0)   # seconds a firefly stays lit (min, max)
LIT_SPEED = 380      # how fast lit fireflies zip about, 1/4096 px per frame (380 is about 2.3 px a second)
WAVE_S = (40, 90)    # seconds between flash waves (min, max)
MOON = 1             # 1 = show the moon in its real phase, 0 = no moon
FRAME = 0.04
LEVELS = 16

RISE = 8             # frames to light up
FALL = 20            # frames to fade out

# depth layers: brightness, speed and halo for far, middle and near
DEPTH_BRIGHT = (0.4, 0.7, 1.0)
DEPTH_SPEED = (0.45, 0.7, 1.0)
DEPTH_HALO = (16, 11, 6)     # halo shows above this brightness (16 = never)

MOON_X = 7           # where the moon's 4x4 disc sits (top-left corner)
MOON_Y = 1

def setup(su, g):
    global W, H, N, BG, STAR, STARS, NUDGE, flies, trail, trail_fly, next_wave, a_was, frames
    global MOONPEN, MOONPX, GLOWPX, phase, phase_t
    W, H = su.WIDTH, su.HEIGHT
    N = W * H
    NUDGE = max(1, int(32 * PACE))
    # the night: a deep blue sky that darkens towards the ground, and a long
    # strip of grass with taller stems poking up here and there
    grass = bytearray(random.choice((1, 1, 2, 2, 2, 3)) for _ in range(W))
    for x in range(1, W - 2, 4):
        grass[x + random.randrange(3)] = random.choice((3, 4, 4))
    BG = []
    top = H - 2
    for y in range(H):
        for x in range(W):
            k = H - 1 - y
            if k < grass[x]:
                BG.append(g.create_pen(3, 10 + 3 * k, 5))
            else:
                f = 12 * (top - y) // top if y < top else 0
                BG.append(g.create_pen(f // 3, f // 2 + 1, 4 + f * 2))
    STAR = [g.create_pen(v * 9, v * 10, v * 14) for v in range(LEVELS)]
    # a scatter of twinkling stars across the top rows, kept clear of the moon
    STARS = []
    while len(STARS) < 16:
        x = random.randrange(W)
        y = random.randrange(5)
        if MOON and MOON_X - 2 <= x <= MOON_X + 5 and y <= MOON_Y + 4:
            continue
        STARS.append((x, y, random.randrange(64)))
    # lit, half-lit (the edge of the shadow), earthshine-dark, glow
    MOONPEN = (g.create_pen(225, 225, 200), g.create_pen(110, 112, 104),
               g.create_pen(22, 24, 38), g.create_pen(14, 18, 38))
    MOONPX = bytearray(16)                         # pen index per disc pixel (255 = not in the disc)
    GLOWPX = []
    for j in range(-1, 5):                         # a soft ring just outside the disc
        for i in range(-1, 5):
            u, v = i - 1.5, j - 1.5
            d = u * u + v * v
            if 3.0 < d < 7.0 and not (0 <= i < 4 and 0 <= j < 4 and d <= 2.6):
                GLOWPX.append((i, j))
    phase = moon_phase()
    shade_moon()
    phase_t = 0.0
    # each firefly: [x, y, vx, vy, countdown, lit frame (-1 = dark),
    #                frames lit, depth, glow pens, halo pens, glimmer]
    flies = []
    for _ in range(COUNT):
        d = random.choice((0, 0, 1, 1, 1, 2, 2))
        # its own colour: far ones greener and cooler, near ones warmer
        r = random.randint(110, 180) + d * 35
        gg = random.randint(220, 255)
        b = random.randint(20, 70) + (2 - d) * 25
        m = DEPTH_BRIGHT[d]
        glow = [g.create_pen(int(r * m * v / 15), int(gg * m * v / 15), int(b * m * v / 15)) for v in range(LEVELS)]
        halo = [g.create_pen(int(r * m * v / 60), int(gg * m * v / 45), int(b * m * v / 60)) for v in range(LEVELS)]
        flies.append([random.randrange(W << 12), random.randrange(1 << 12, (H - 3) << 12),
                      0, 0, dark_frames(), -1, 100, d, glow, halo, 12])
    flies.sort(key=lambda f: f[7])                   # far ones drawn first
    for f in flies[:3]:
        f[4] = random.randint(25, 75)                # a few say hello early on
    trail = bytearray(N)
    trail_fly = bytearray(N)                         # which firefly left it
    next_wave = random.uniform(*WAVE_S) / PACE
    a_was = False
    frames = 0

def rad(d):
    return d * 0.017453292519943295

def deg(r):
    return r * 57.29577951308232

def moon_phase():
    """(lit fraction 0..1, waxing?) for right now, from the board's clock."""
    try:
        y, m, d, hh, mi = time.gmtime()[:5]
    except Exception:
        return 0.5, True
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    days = (1461 * (y + 4716)) // 4 + (306001 * (m + 1)) // 10000 + d + 2 - a + a // 4 - 1525 - 2451545
    n = days + (hh + mi / 60) / 24 + 0.5
    sun = rad(280.460 + 0.9856474 * n + 1.915 * math.sin(rad(357.528 + 0.9856003 * n)))
    moon = rad(218.316 + 13.176396 * n + 6.289 * math.sin(rad(134.963 + 13.064993 * n)))
    e = moon - sun
    return (1 - math.cos(e)) / 2, math.sin(e) > 0

def shade_moon():
    """Work out which of the 4x4 disc's pixels are lit for the current phase."""
    lit, waxing = phase
    for j in range(4):
        for i in range(4):
            u, v = i - 1.5, j - 1.5
            if u * u + v * v > 2.6:
                MOONPX[j * 4 + i] = 255
                continue
            hw = math.sqrt(4.0 - v * v)
            edge = hw * (1 - 2 * lit)               # where the shadow edge falls on this row
            uu = u if waxing else -u                # waxing: lit on the right
            c = uu + 0.5 - edge                     # how much of this pixel is on the lit side
            MOONPX[j * 4 + i] = 0 if c >= 0.75 else (1 if c > 0.25 else 2)

def draw_moon(g, mx, my):
    g.set_pen(MOONPEN[3])                      # a faint glow round it
    for i, j in GLOWPX:
        g.pixel(mx + i, my + j)
    for k in range(16):
        p = MOONPX[k]
        if p != 255:
            g.set_pen(MOONPEN[p])
            g.pixel(mx + (k & 3), my + (k >> 2))

def dark_frames():
    return int(random.randint(DARK[0], DARK[1]) / PACE)

def wave():
    # flash in a sweep from one end of the meadow to the other
    left = random.getrandbits(1)
    for f in flies:
        px = f[0] >> 12
        if f[5] < 0:
            f[4] = (px if left else W - 1 - px) * 2 + random.randrange(4)

def frame(su, g, t):
    global next_wave, a_was, frames, phase, phase_t
    frames += 1
    a = su.is_pressed(GalacticUnicorn.SWITCH_A)
    if (a and not a_was) or t >= next_wave:
        wave()
        next_wave = t + random.uniform(*WAVE_S) / PACE
    a_was = a

    # ---- background and stars ----
    i = 0
    for y in range(H):
        for x in range(W):
            g.set_pen(BG[i])
            g.pixel(x, y)
            i += 1
    for x, y, ph in STARS:
        v = (frames // 2 + ph) & 63
        v = v if v < 32 else 63 - v              # slow twinkle
        if v > 12:
            g.set_pen(STAR[v >> 2])
            g.pixel(x, y)
    if MOON:
        if t - phase_t > 600:                  # the phase barely changes; check every 10 minutes
            phase = moon_phase()
            shade_moon()
            phase_t = t
        draw_moon(g, MOON_X, MOON_Y)

    # ---- trails fade (half speed: every other frame) ----
    fade = frames & 1
    for i in range(N):
        v = trail[i]
        if v:
            if fade:
                trail[i] = v - 1
            g.set_pen(flies[trail_fly[i]][9][v])
            g.pixel(i % W, i // W)

    # ---- fireflies ----
    xmax = (W - 1) << 12
    ylo = 1 << 12
    yhi = (H - 3) << 12
    for n in range(COUNT):
        f = flies[n]
        lit = f[5] >= 0
        if lit:
            top = int(LIT_SPEED * DEPTH_SPEED[f[7]]) or 1
            nudge = LIT_SPEED // 5 + 1          # lit ones swerve more
        else:
            top = int(MAX_SPEED * 16 * DEPTH_SPEED[f[7]] * PACE) or 1
            nudge = NUDGE
        # wander: nudge the velocity now and then, keep it gentle
        vx = f[2]
        vy = f[3]
        if fade:
            vx += random.randint(-nudge, nudge)
            vy += random.randint(-nudge, nudge)
        if vx > top:
            vx = top
        elif vx < -top:
            vx = -top
        # vertical room is short, so keep climbing and diving gentler than drifting
        vtop = top * 2 // 3 or 1
        if vy > vtop:
            vy = vtop
        elif vy < -vtop:
            vy = -vtop
        x = f[0] + vx
        y = f[1] + vy
        if x < 0 or x > xmax:
            vx = -vx
            x = f[0]
        if y < ylo or y > yhi:
            vy = -vy
            y = f[1]
        f[0] = x
        f[1] = y
        f[2] = vx
        f[3] = vy
        # dark: count down to lighting up
        if not lit:
            f[4] -= 1
            if f[4] <= 0:
                f[5] = 0
                f[6] = int(random.uniform(LIT_S[0], LIT_S[1]) / FRAME)
            continue
        # lit: glimmer (a brightness that wanders, with the odd sparkle)
        gl = f[10] + random.randint(-2, 2)
        if gl < 8:
            gl = 8
        elif gl > 15:
            gl = 15
        f[10] = gl
        v = 15 if random.getrandbits(5) == 0 else gl
        k = f[5]
        if k < RISE:
            v = v * (k + 1) // RISE
        elif k > f[6] - FALL:
            v = v * (f[6] - k) // FALL
        f[5] = k + 1
        if f[5] >= f[6]:
            f[5] = -1
            f[4] = dark_frames()
        if v <= 0:
            continue
        px = (x + 2048) >> 12
        py = (y + 2048) >> 12
        if px > W - 1:
            px = W - 1
        if py > H - 1:
            py = H - 1
        i = py * W + px
        if (v >> 1) > trail[i]:
            trail[i] = v >> 1
            trail_fly[i] = n
        # soft halo around the brightest part of a blink (near ones only)
        if v > DEPTH_HALO[f[7]]:
            g.set_pen(f[9][v])
            if px > 0:
                g.pixel(px - 1, py)
            if px < W - 1:
                g.pixel(px + 1, py)
            if py > 0:
                g.pixel(px, py - 1)
            if py < H - 1:
                g.pixel(px, py + 1)
        g.set_pen(f[8][v])
        g.pixel(px, py)
    return FRAME
