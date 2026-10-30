# Conway's Game of Life for the Stellar Unicorn (launcher setup/frame version)
#   A = new random world   B = drop in a glider   C = pause / resume
#   D = change colour style
#
# Colour styles (press D to cycle):
#   0  Families  - newborns inherit a parent's colour with a small mutation,
#                  so coloured tribes spread, collide and mix
#   1  Rainbow   - colour depends on position
#   2  Age       - newborns and old-timers get very different colours
# Every cell is born white and ripens into its colour as it ages. Cells fade
# in and out smoothly, the edges wrap, and a stuck or empty world reseeds.
#
# Memory-friendly: every per-cell value (colour, glow, ripeness) is a small
# integer in a bytearray allocated once in setup(), and colours come from a
# precomputed pen table. Nothing is allocated per frame, so the board's heap
# stays calm even at full speed (that leaves room for the secure cloud
# connection).
import random
from stellar import StellarUnicorn

# --- settings to play with ---
STEP_SECONDS = 0.3   # time between generations (bigger = slower)
FADE = 51            # how fast cells fade in/out, out of 256 per frame (smaller = softer)
DENSITY = 0.3        # fraction of cells alive in a new random world
MAX_GENERATIONS = 1000
HUE_STEP = 3         # how far the whole palette drifts each generation (out of 256)
COLOR_STYLE = 0      # starting style: 0 families, 1 rainbow, 2 age
TRIBES = 4           # number of colour families in a new world (style 0)
MUTATION = 8         # how much a newborn's colour can differ from its parent (out of 256)
RAINBOW_SPREAD = 1.0 # style 1: how much of the rainbow fits across the board
AGE_SPREAD = 150     # style 2: colour difference between young and old cells (out of 256)
RIPEN = 8            # generations a newborn takes to go from white to full colour
MAX_SATURATION = 0.85

HUES = 48            # pen table resolution
SATS = 6
VALS = 8
HISTORY = 12

GLIDER = ((1, 0), (2, 1), (0, 2), (1, 2), (2, 2))

def rgb(h, s, v):
    i = int(h * 6)
    f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, gg, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i % 6]
    return int(r * 255), int(gg * 255), int(b * 255)

def setup(su, g):
    global W, H, N, BLACK, PENS, alive, nxt, age, gene, new_gene, glow, sat, col, POS
    global hist, hist_n, nbrs, prev, style, drift, paused, stale, generation, next_step
    W, H = su.WIDTH, su.HEIGHT
    N = W * H
    BLACK = g.create_pen(0, 0, 0)
    # pens for every (hue, saturation, brightness) step, made once
    PENS = []
    for hi in range(HUES):
        for si in range(SATS):
            for vi in range(VALS):
                PENS.append(g.create_pen(*rgb(hi / HUES, si / (SATS - 1) * MAX_SATURATION, (vi + 1) / VALS)))
    alive = bytearray(N)
    nxt = bytearray(N)
    age = bytearray(N)
    gene = bytearray(N)          # each cell's hue, 0..255
    new_gene = bytearray(N)
    glow = bytearray(N)          # brightness, fades in and out
    sat = bytearray(N)           # ripeness: 0 = white newborn, 255 = full colour
    col = bytearray(N)           # the colour on screen (kept while a cell fades out)
    POS = bytearray(int(((i % W) + (i // W)) * 256 * RAINBOW_SPREAD / (W + H)) & 255 for i in range(N))
    hist = [bytearray(N) for _ in range(HISTORY)]
    hist_n = 0
    # the 8 neighbour indices of every cell (edges wrap), computed once
    nbrs = []
    for y in range(H):
        for x in range(W):
            nbrs.append(tuple(((y + dy) % H) * W + (x + dx) % W
                              for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy))
    prev = [False, False, False, False]
    style = COLOR_STYLE
    drift = 0
    paused = False
    stale = 0
    generation = 0
    next_step = STEP_SECONDS
    seed()

def seed():
    global stale, generation, hist_n
    centres = [(random.randrange(W), random.randrange(H), random.getrandbits(8)) for _ in range(TRIBES)]
    for y in range(H):
        for x in range(W):
            i = y * W + x
            best = 0
            bd = 999
            for c in centres:
                d = (c[0] - x) ** 2 + (c[1] - y) ** 2
                if d < bd:
                    bd, best = d, c[2]
            gene[i] = best
            a = 1 if random.random() < DENSITY else 0
            alive[i] = a
            age[i] = a
            sat[i] = 0
    hist_n = 0
    stale = 0
    generation = 0

def add_glider():
    ox, oy = random.randrange(W), random.randrange(H)
    colour = random.getrandbits(8)
    for dx, dy in GLIDER:
        i = ((oy + dy) % H) * W + (ox + dx) % W
        alive[i] = 1
        age[i] = 1
        gene[i] = colour
        sat[i] = 0

def step():
    global alive, nxt, gene, new_gene
    for i in range(N):
        n = 0
        for j in nbrs[i]:
            n += alive[j]
        if alive[i]:
            nxt[i] = 1 if n == 2 or n == 3 else 0
            new_gene[i] = gene[i]
        elif n == 3:
            nxt[i] = 1
            # inherit from a random live neighbour
            k = random.randrange(3)
            for j in nbrs[i]:
                if alive[j]:
                    if k == 0:
                        new_gene[i] = (gene[j] + random.randrange(2 * MUTATION + 1) - MUTATION) & 255
                        break
                    k -= 1
        else:
            nxt[i] = 0
            new_gene[i] = gene[i]
    for i in range(N):
        if nxt[i]:
            if alive[i]:
                if age[i] < 255:
                    age[i] += 1
            else:
                age[i] = 1
                sat[i] = 0
        else:
            age[i] = 0
    alive, nxt = nxt, alive          # swap buffers, no new allocation
    gene, new_gene = new_gene, gene

def is_repeating():
    global hist_n
    for k in range(min(hist_n, HISTORY)):
        if hist[k] == alive:
            return True
    hist[hist_n % HISTORY][:] = alive
    hist_n += 1
    return False

def pressed_once(su, k, switch):
    now = su.is_pressed(switch)
    was = prev[k]
    prev[k] = now
    return now and not was

def frame(su, g, t):
    global style, drift, paused, stale, generation, next_step

    if pressed_once(su, 0, StellarUnicorn.SWITCH_A):
        seed()
    if pressed_once(su, 1, StellarUnicorn.SWITCH_B):
        add_glider()
    if pressed_once(su, 2, StellarUnicorn.SWITCH_C):
        paused = not paused
    if pressed_once(su, 3, StellarUnicorn.SWITCH_D):
        style = (style + 1) % 3

    if t >= next_step:
        next_step = t + STEP_SECONDS
        if not paused:
            step()
            generation += 1
            drift = (drift + HUE_STEP) & 255
            if is_repeating():
                stale += 1
            if stale >= 10 or generation >= MAX_GENERATIONS:
                seed()

    g.set_pen(BLACK)
    g.clear()
    sv = SATS * VALS
    for i in range(N):
        v = glow[i]
        if alive[i]:
            a = age[i]
            if style == 0:
                h = gene[i]
            elif style == 1:
                h = POS[i]
            else:
                h = (a if a < 30 else 30) * AGE_SPREAD // 30
            r = a * 255 // RIPEN if a < RIPEN else 255
            sat[i] += (r - sat[i]) * FADE >> 8
            v += ((255 - v) * FADE >> 8) + 1
            glow[i] = v if v < 255 else 255
            col[i] = h
        else:
            v -= (v * FADE >> 8) + 1
            glow[i] = v if v > 0 else 0
        v = glow[i]
        if v > 15:
            g.set_pen(PENS[((col[i] + drift & 255) * HUES >> 8) * sv
                           + (sat[i] * (SATS - 1) + 127) // 255 * VALS
                           + (v * VALS >> 8)])
            g.pixel(i % W, i // W)
    return 0.03
