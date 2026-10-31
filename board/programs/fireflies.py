# Fireflies: a summer night over a meadow. Fireflies drift slowly through
# the dark. Every so often one lights up and stays lit for a few seconds,
# glimmering as it flies and leaving a short glowing streak, then fades out. Every firefly has
# its own colour and a depth: near ones are bigger, brighter, warmer and
# quicker; far ones are small, dim, greener and drift slowly. Now and then
# they all flash together in a wave that rolls across the board. A few stars
# twinkle above the grass.
#   A = set off a flash wave now
#
# PACE slows the dark drifting and how often they light up: at the very
# bottom the fireflies barely creep and each one lights up only every few
# minutes, so catching one is a little surprise. Lit ones always fly at
# LIT_SPEED.
#
# Memory-friendly: positions are integers (1/4096 of a pixel), the trail is a
# bytearray, and every pen is made once in setup().
import random
from stellar import StellarUnicorn

COUNT = 16           # how many fireflies
PACE = 1.0           # overall speed: dark drifting and how often they light up (0.01 = almost never)
MAX_SPEED = 9        # top speed for the nearest fireflies at PACE 1, 1/256 px per frame
DARK = (70, 280)     # frames a firefly stays dark between lights at PACE 1 (min, max)
LIT_S = (3.0, 6.0)   # seconds a firefly stays lit (min, max)
LIT_SPEED = 150      # how fast lit fireflies fly, 1/4096 px per frame (150 is about 1 px a second)
WAVE_S = (40, 90)    # seconds between flash waves (min, max)
FRAME = 0.04
LEVELS = 16

RISE = 8             # frames to light up
FALL = 20            # frames to fade out

# depth layers: brightness, speed and halo for far, middle and near
DEPTH_BRIGHT = (0.4, 0.7, 1.0)
DEPTH_SPEED = (0.45, 0.7, 1.0)
DEPTH_HALO = (16, 11, 6)     # halo shows above this brightness (16 = never)

def setup(su, g):
    global BG, STAR, NUDGE, flies, trail, trail_fly, next_wave, a_was, frames
    NUDGE = max(1, int(32 * PACE))
    # the night: a deep blue sky that darkens towards the ground, and grass
    grass = [random.choice((1, 1, 2, 2, 2, 3)) for _ in range(16)]
    for x in range(1, 15, 4):
        grass[x + random.randrange(2)] = 4          # a few taller stems
    BG = []
    for y in range(16):
        for x in range(16):
            if 15 - y < grass[x]:
                k = 15 - y
                BG.append(g.create_pen(3, 10 + 3 * k, 5))
            else:
                f = 12 - y if y < 12 else 0
                BG.append(g.create_pen(f // 3, f // 2 + 1, 4 + f * 2))
    STAR = [g.create_pen(v * 9, v * 10, v * 14) for v in range(LEVELS)]
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
        flies.append([random.randrange(16 << 12), random.randrange(1 << 12, 12 << 12),
                      0, 0, dark_frames(), -1, 100, d, glow, halo, 12])
    flies.sort(key=lambda f: f[7])                   # far ones drawn first
    random.choice(flies)[4] = random.randint(25, 75) # one says hello early on
    trail = bytearray(256)
    trail_fly = bytearray(256)                       # which firefly left it
    next_wave = random.uniform(*WAVE_S) / PACE
    a_was = False
    frames = 0

def dark_frames():
    return int(random.randint(DARK[0], DARK[1]) / PACE)

def wave():
    # flash in a sweep from one side to the other
    left = random.getrandbits(1)
    for f in flies:
        px = f[0] >> 12
        if f[5] < 0:
            f[4] = (px if left else 15 - px) * 4 + random.randrange(4)

def frame(su, g, t):
    global next_wave, a_was, frames
    frames += 1
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if (a and not a_was) or t >= next_wave:
        wave()
        next_wave = t + random.uniform(*WAVE_S) / PACE
    a_was = a

    # ---- background and stars ----
    for i in range(256):
        g.set_pen(BG[i])
        g.pixel(i & 15, i >> 4)
    for i in range(6):
        v = (frames // 2 + i * 23) & 63
        v = v if v < 32 else 63 - v              # slow twinkle
        if v > 12:
            g.set_pen(STAR[v >> 2])
            g.pixel((i * 7 + 3) % 16, (i * 5) % 6)

    # ---- trails fade (half speed: every other frame) ----
    fade = frames & 1
    for i in range(256):
        v = trail[i]
        if v:
            if fade:
                trail[i] = v - 1
            g.set_pen(flies[trail_fly[i]][9][v])
            g.pixel(i & 15, i >> 4)

    # ---- fireflies ----
    for n in range(COUNT):
        f = flies[n]
        lit = f[5] >= 0
        if lit:
            top = int(LIT_SPEED * DEPTH_SPEED[f[7]]) or 1
            nudge = 32
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
        if vy > top:
            vy = top
        elif vy < -top:
            vy = -top
        x = f[0] + vx
        y = f[1] + vy
        if x < 0 or x > (15 << 12):
            vx = -vx
            x = f[0]
        if y < (1 << 12) or y > (13 << 12):
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
        if px > 15:
            px = 15
        if py > 15:
            py = 15
        i = py * 16 + px
        if (v >> 1) > trail[i]:
            trail[i] = v >> 1
            trail_fly[i] = n
        # soft halo around the brightest part of a blink (near ones only)
        if v > DEPTH_HALO[f[7]]:
            g.set_pen(f[9][v])
            if px > 0:
                g.pixel(px - 1, py)
            if px < 15:
                g.pixel(px + 1, py)
            if py > 0:
                g.pixel(px, py - 1)
            if py < 15:
                g.pixel(px, py + 1)
        g.set_pen(f[8][v])
        g.pixel(px, py)
    return FRAME
