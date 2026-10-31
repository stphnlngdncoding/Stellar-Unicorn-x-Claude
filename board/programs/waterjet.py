# Water jet: a jet of water spurts in from a random edge of the board, a
# random size each time, and its droplets scatter, bounce around inside the
# square and break up as they hit the edges. Every spurt is a different pale,
# spacey blue or green, so the colours mix where the water overlaps.
#   A = spurt now
#
# Memory-friendly: droplets live in preallocated integer arrays (fixed point,
# 1/256 px), the glow and colour of each pixel are bytearrays, and pens are
# made once.
import random
from array import array
from stellar import StellarUnicorn

MAX_DROPS = 90       # most droplets in the air at once (more = slower)
SPURT_S = (3.5, 6.5) # how long each spurt lasts (seconds)
PAUSE_S = (5.0, 10.0) # quiet time between spurts
GRAVITY = 7          # how hard the water falls (bigger = heavier)
# pale space colours the spurts take turns with (r, g, b)
PALETTE = ((150, 185, 255), (120, 215, 255), (110, 235, 225), (135, 240, 190),
           (175, 245, 165), (165, 170, 255), (190, 225, 255), (120, 200, 210))
BOUNCE = 185         # how bouncy the edges are (out of 256)
TRAIL = 110          # how long droplet trails linger (out of 256, bigger = longer)
FRAME = 0.03

ONE = 256            # fixed point: 1 pixel = 256
EDGE = 16 * ONE - 1

def setup(su, g):
    global X, Y, VX, VY, LIFE, HUE, n, GLOW, PIX, PENS, BLACK, spurt, next_spurt, a_was, colour
    X, Y = array("i", [0] * MAX_DROPS), array("i", [0] * MAX_DROPS)
    VX, VY = array("i", [0] * MAX_DROPS), array("i", [0] * MAX_DROPS)
    LIFE = bytearray(MAX_DROPS)
    HUE = bytearray(MAX_DROPS)                   # each droplet's colour
    n = 0
    GLOW = bytearray(256)                        # brightness of each pixel
    PIX = bytearray(256)                         # colour of each pixel
    BLACK = g.create_pen(0, 0, 0)
    # for each colour: deep -> rich -> bright -> white foam, 16 steps
    PENS = []
    for base in PALETTE:
        for k in range(16):
            f = (k + 1) / 16
            w = max(0.0, f - 0.75) / 0.25 * 0.7      # the brightest steps foam towards white
            PENS.append(g.create_pen(*[int(c * f + (255 - c * f) * w) for c in base]))
    colour = random.randrange(len(PALETTE))
    spurt = None
    next_spurt = 0.5
    a_was = False

def new_spurt(t):
    global colour
    # each spurt gets a different colour from the last one
    colour = (colour + random.randint(1, len(PALETTE) - 1)) % len(PALETTE)
    # the jet comes in from a random edge, pointing into the board
    side = random.randrange(4)
    p = random.randint(3, 12) * ONE + ONE // 2
    if side == 0:
        x, y, ax, ay = 0, p, 1, 0
    elif side == 1:
        x, y, ax, ay = EDGE, p, -1, 0
    elif side == 2:
        x, y, ax, ay = p, 0, 0, 1
    else:
        x, y, ax, ay = p, EDGE, 0, -1
    size = random.randint(1, 4)                  # 1 = a thin squirt, 4 = a fire hose
    return {"x": x, "y": y, "ax": ax, "ay": ay, "size": size,
            "speed": random.randint(128, 188) + size * 15,
            "aim": random.randint(-52, 52),      # tilt of the jet across its direction
            "until": t + random.uniform(*SPURT_S)}

def add_drop(x, y, vx, vy, life, hue):
    global n
    if n >= MAX_DROPS:
        return
    X[n] = x
    Y[n] = y
    VX[n] = vx
    VY[n] = vy
    LIFE[n] = life
    HUE[n] = hue
    n += 1

def frame(su, g, t):
    global n, spurt, next_spurt, a_was
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was and spurt is None:
        next_spurt = t
    a_was = a

    # ---- the jet ----
    if spurt is None and t >= next_spurt:
        spurt = new_spurt(t)
    if spurt:
        s = spurt
        for _ in range(s["size"]):
            sp = s["speed"] + random.randint(-15, 15)
            side = s["aim"] + random.randint(-15 - 8 * s["size"], 15 + 8 * s["size"])
            jx = s["x"] + s["ay"] * random.randint(-s["size"], s["size"]) * 64
            jy = s["y"] + s["ax"] * random.randint(-s["size"], s["size"]) * 64
            add_drop(jx, jy, s["ax"] * sp + s["ay"] * side, s["ay"] * sp + s["ax"] * side, 255, colour)
        if t >= s["until"]:
            spurt = None
            next_spurt = t + random.uniform(*PAUSE_S)

    # ---- droplets: gravity, bounces, break-ups ----
    # (local names and plain assignments keep this loop fast on the board)
    Xa, Ya, VXa, VYa, La, Ha, Ga, Pa = X, Y, VX, VY, LIFE, HUE, GLOW, PIX
    i = 0
    while i < n:
        vx = VXa[i]
        vy = VYa[i] + GRAVITY
        x = Xa[i] + vx
        y = Ya[i] + vy
        hit = 0
        if x < 0:
            x = -x
            hit = vx if vx > 0 else -vx
            vx = -vx * BOUNCE >> 8
        elif x > EDGE:
            x = 2 * EDGE - x
            hit = vx if vx > 0 else -vx
            vx = -vx * BOUNCE >> 8
        if y < 0:
            y = -y
            h2 = vy if vy > 0 else -vy
            if h2 > hit:
                hit = h2
            vy = -vy * BOUNCE >> 8
        elif y > EDGE:
            y = 2 * EDGE - y
            h2 = vy if vy > 0 else -vy
            if h2 > hit:
                hit = h2
            vy = -vy * BOUNCE >> 8
            if h2 > 22:                           # splashes scatter sideways off the floor
                vx += random.randint(-h2, h2) >> 1
        if x < 0:
            x = 0
        elif x > EDGE:
            x = EDGE
        if y < 0:
            y = 0
        elif y > EDGE:
            y = EDGE
        life = La[i]
        if hit > 45 and life > 90 and n < MAX_DROPS:   # a hard hit breaks it into two
            add_drop(x, y, vy * 3 >> 3 if vy else random.randint(-30, 30),
                     vx * 3 >> 3 if vx else random.randint(-30, 30), life - 40, Ha[i])
        # resting water drains away; flying water lasts longer
        speed = (vx if vx > 0 else -vx) + (vy if vy > 0 else -vy)
        life -= 2 if speed > 30 else 7
        if life <= 0:
            n -= 1                                # move the last droplet into this slot
            Xa[i] = Xa[n]
            Ya[i] = Ya[n]
            VXa[i] = VXa[n]
            VYa[i] = VYa[n]
            La[i] = La[n]
            Ha[i] = Ha[n]
            continue
        Xa[i] = x
        Ya[i] = y
        VXa[i] = vx
        VYa[i] = vy
        La[i] = life
        c = (y >> 8) * 16 + (x >> 8)
        b = Ga[c] + 18 + (speed // 3 if speed < 180 else 60) + (life >> 4)
        Ga[c] = b if b < 255 else 255
        Pa[c] = Ha[i]
        i += 1

    # ---- draw the glow, with fading trails ----
    g.set_pen(BLACK)
    g.clear()
    for c in range(256):
        v = GLOW[c]
        if v:
            if v > 6:
                g.set_pen(PENS[PIX[c] * 16 + (v >> 4)])
                g.pixel(c & 15, c >> 4)
            GLOW[c] = v * TRAIL >> 8
    return FRAME
