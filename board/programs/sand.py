# Sand: sand sprinkles down from the top of the board in pours of different
# colours, tumbles off the slopes and piles up in layers like a sand-art
# bottle. When the board is nearly full, the floor opens and it all drains
# away, then the sprinkling starts again.
#   A = drain now
#
# Memory-friendly: the whole board is one bytearray (0 = empty, otherwise a
# colour and shade), pens are made once, and nothing is allocated per frame.
import random
from stellar import StellarUnicorn

POUR_S = (4, 9)      # how long each pour lasts (seconds)
PAUSE_S = (1.0, 3.0) # quiet time between pours
RATE = (70, 200)     # chance of a grain each frame while pouring (out of 256)
FULL = 170           # grains on the board before it drains (of 256)
FRAME = 0.04

# sand colours the pours take turns with (r, g, b)
SANDS = ((236, 214, 170), (222, 170, 110), (196, 120, 80), (240, 190, 170),
         (170, 200, 220), (150, 185, 160), (214, 196, 230), (245, 235, 205))
SHADES = 4

def setup(su, g):
    global GRID, PENS, BLACK, pour, next_pour, colour, draining, count, flip, a_was
    GRID = bytearray(256)
    BLACK = g.create_pen(0, 0, 0)
    PENS = [BLACK]                               # index 0 = empty
    for base in SANDS:
        for k in range(SHADES):
            f = 0.62 + 0.38 * k / (SHADES - 1)   # each grain a slightly different shade
            PENS.append(g.create_pen(int(base[0] * f), int(base[1] * f), int(base[2] * f)))
    pour = None
    next_pour = 0.3
    colour = random.randrange(len(SANDS))
    draining = False
    count = 0
    flip = 0
    a_was = False

def new_pour(t):
    global colour
    colour = (colour + random.randint(1, len(SANDS) - 1)) % len(SANDS)
    return {"x": random.uniform(2, 13), "drift": random.uniform(-1.6, 1.6),
            "width": random.randint(0, 2), "rate": random.randint(*RATE),
            "until": t + random.uniform(*POUR_S)}

def frame(su, g, t):
    global pour, next_pour, draining, count, flip, a_was
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was:
        draining = True
    a_was = a

    # ---- pouring from the top ----
    if not draining:
        if pour is None and t >= next_pour:
            pour = new_pour(t)
        if pour:
            p = pour
            p["x"] += p["drift"] * FRAME          # the stream wanders across the top
            if p["x"] < 0.5 or p["x"] > 14.5:
                p["drift"] = -p["drift"]
            if random.getrandbits(8) < p["rate"]:
                x = int(p["x"]) + random.randint(-p["width"], p["width"])
                if 0 <= x < 16 and not GRID[x]:
                    GRID[x] = 1 + colour * SHADES + random.randrange(SHADES)
            if t >= p["until"]:
                pour = None
                next_pour = t + random.uniform(*PAUSE_S)

    # ---- falling: each grain drops, or slides off a slope ----
    flip ^= 1
    for y in range(14, -1, -1):
        row, below = y * 16, y * 16 + 16
        for k in range(16):
            x = k if flip else 15 - k
            c = GRID[row + x]
            if not c:
                continue
            if not GRID[below + x]:
                GRID[below + x] = c
                GRID[row + x] = 0
                continue
            l = x > 0 and not GRID[below + x - 1]
            r = x < 15 and not GRID[below + x + 1]
            if l and r:
                if random.getrandbits(1):
                    l = False
                else:
                    r = False
            if l:
                GRID[below + x - 1] = c
                GRID[row + x] = 0
            elif r:
                GRID[below + x + 1] = c
                GRID[row + x] = 0

    # ---- draining: the floor opens and the sand pours out ----
    if draining:
        for x in range(16):
            if GRID[240 + x] and random.getrandbits(1):
                GRID[240 + x] = 0
    count = 0
    for c in GRID:
        if c:
            count += 1
    if not draining and count >= FULL:
        draining = True
        pour = None
    elif draining and count == 0:
        draining = False
        next_pour = t + 0.8

    # ---- draw ----
    for i in range(256):
        g.set_pen(PENS[GRID[i]])
        g.pixel(i & 15, i >> 4)
    return FRAME
