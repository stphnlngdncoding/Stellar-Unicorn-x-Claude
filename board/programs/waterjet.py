# Water jet: a jet of water spurts in from a random edge of the board, a
# random size each time, and its droplets scatter, bounce around inside the
# square and break up as they hit the edges. Gravity always pulls down, but
# its strength changes with every spurt: some spurts land like heavy rain,
# others float and drift around the board like the moon's pulling them.
#   A = spurt now
#
# Memory-friendly: droplets live in preallocated integer arrays (fixed point,
# 1/256 px), the glow is a bytearray, and pens are made once.
import random
from array import array
from stellar import StellarUnicorn

MAX_DROPS = 140      # most droplets in the air at once
SPURT_S = (1.2, 2.6) # how long each spurt lasts (seconds)
PAUSE_S = (1.5, 4.0) # quiet time between spurts
GRAVITY = (3, 40)    # gravity strength range, always downward (bigger = heavier)
BOUNCE = 185         # how bouncy the edges are (out of 256)
TRAIL = 200          # how long droplet trails linger (out of 256, bigger = longer)
FRAME = 0.03

ONE = 256            # fixed point: 1 pixel = 256
EDGE = 16 * ONE - 1

def setup(su, g):
    global X, Y, VX, VY, LIFE, n, GLOW, PENS, BLACK, gx, gy, spurt, next_spurt, a_was
    X, Y = array("i", [0] * MAX_DROPS), array("i", [0] * MAX_DROPS)
    VX, VY = array("i", [0] * MAX_DROPS), array("i", [0] * MAX_DROPS)
    LIFE = bytearray(MAX_DROPS)
    n = 0
    GLOW = bytearray(256)
    BLACK = g.create_pen(0, 0, 0)
    # deep water blue -> aqua -> white foam
    stops = ((0, 6, 22), (0, 40, 110), (0, 120, 200), (60, 200, 240), (220, 250, 255))
    PENS = []
    for k in range(32):
        f = k / 31 * (len(stops) - 1)
        i = min(int(f), len(stops) - 2); q = f - i
        a, b = stops[i], stops[i + 1]
        PENS.append(g.create_pen(*[int(a[c] + (b[c] - a[c]) * q) for c in range(3)]))
    gx, gy = 0, 20
    spurt = None
    next_spurt = 0.5
    a_was = False

def new_spurt(t):
    global gx, gy
    # gravity changes strength with every spurt, but always pulls down
    gx, gy = 0, random.randint(*GRAVITY)
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
            "speed": random.randint(90, 150) + size * 15,
            "aim": random.randint(-70, 70),      # tilt of the jet across its direction
            "until": t + random.uniform(*SPURT_S)}

def add_drop(x, y, vx, vy, life):
    global n
    if n >= MAX_DROPS:
        return
    X[n], Y[n], VX[n], VY[n], LIFE[n] = x, y, vx, vy, life
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
            sp = s["speed"] + random.randint(-20, 20)
            side = s["aim"] + random.randint(-20 - 10 * s["size"], 20 + 10 * s["size"])
            jx = s["x"] + s["ay"] * random.randint(-s["size"], s["size"]) * 64
            jy = s["y"] + s["ax"] * random.randint(-s["size"], s["size"]) * 64
            add_drop(jx, jy, s["ax"] * sp + s["ay"] * side, s["ay"] * sp + s["ax"] * side, 255)
        if t >= s["until"]:
            spurt = None
            next_spurt = t + random.uniform(*PAUSE_S)

    # ---- droplets: gravity, bounces, break-ups ----
    i = 0
    while i < n:
        vx, vy = VX[i] + gx, VY[i] + gy
        x, y = X[i] + vx, Y[i] + vy
        hit = 0
        if x < 0:
            x, vx, hit = -x, -vx * BOUNCE >> 8, abs(vx)
        elif x > EDGE:
            x, vx, hit = 2 * EDGE - x, -vx * BOUNCE >> 8, abs(vx)
        if y < 0:
            y, vy, hit = -y, -vy * BOUNCE >> 8, max(hit, abs(vy))
        elif y > EDGE:
            y, vy, hit = 2 * EDGE - y, -vy * BOUNCE >> 8, max(hit, abs(vy))
            if hit > 30:                          # splashes scatter sideways off the floor
                vx += random.randint(-hit, hit) >> 1
        x = 0 if x < 0 else EDGE if x > EDGE else x
        y = 0 if y < 0 else EDGE if y > EDGE else y
        life = LIFE[i]
        if hit > 60 and life > 90 and n < MAX_DROPS:   # a hard hit breaks it into two
            add_drop(x, y, vy * 3 >> 3 if vy else random.randint(-40, 40),
                     vx * 3 >> 3 if vx else random.randint(-40, 40), life - 40)
        # resting water drains away; flying water lasts longer
        speed = abs(vx) + abs(vy)
        life -= 1 if speed > 40 else 7
        if life <= 0:
            n -= 1                                # swap the last droplet into this slot
            X[i], Y[i], VX[i], VY[i], LIFE[i] = X[n], Y[n], VX[n], VY[n], LIFE[n]
            continue
        X[i], Y[i], VX[i], VY[i], LIFE[i] = x, y, vx, vy, life
        c = (y >> 8) * 16 + (x >> 8)
        b = GLOW[c] + 18 + (speed >> 2 if speed < 240 else 60) + (life >> 4)
        GLOW[c] = b if b < 255 else 255
        i += 1

    # ---- draw the glow, with fading trails ----
    g.set_pen(BLACK)
    g.clear()
    for c in range(256):
        v = GLOW[c]
        if v:
            if v > 6:
                g.set_pen(PENS[v >> 3])
                g.pixel(c & 15, c >> 4)
            GLOW[c] = v * TRAIL >> 8
    return FRAME
