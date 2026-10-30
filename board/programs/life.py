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
# Memory-friendly: all buffers are allocated once in setup() and reused, and
# colours come from a precomputed pen table, so the board's heap stays calm
# (that leaves room for the launcher's secure cloud connection).
import random
from stellar import StellarUnicorn

# --- settings to play with ---
STEP_SECONDS = 0.3   # time between generations (bigger = slower)
FADE = 0.2           # how fast cells fade in/out (smaller = softer, slower)
DENSITY = 0.3        # fraction of cells alive in a new random world
MAX_GENERATIONS = 1000
HUE_STEP = 0.01      # how far the whole palette drifts each generation
COLOR_STYLE = 0      # starting style: 0 families, 1 rainbow, 2 age
TRIBES = 4           # number of colour families in a new world (style 0)
MUTATION = 0.03      # how much a newborn's colour can differ from its parent
RAINBOW_SPREAD = 1.0 # style 1: how much of the rainbow fits across the board
AGE_SPREAD = 0.6     # style 2: colour difference between young and old cells
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
    global W, H, N, BLACK, PENS, alive, nxt, age, gene, new_gene, glow, shown, sat
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
    gene = [0.0] * N
    new_gene = [0.0] * N
    glow = [0.0] * N
    shown = [0.0] * N
    sat = [0.0] * N
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
    drift = 0.0
    paused = False
    stale = 0
    generation = 0
    next_step = STEP_SECONDS
    seed()

def seed():
    global stale, generation, hist_n
    centres = [(random.randrange(W), random.randrange(H), random.random()) for _ in range(TRIBES)]
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
            sat[i] = 0.0
    hist_n = 0
    stale = 0
    generation = 0

def add_glider():
    ox, oy = random.randrange(W), random.randrange(H)
    colour = random.random()
    for dx, dy in GLIDER:
        i = ((oy + dy) % H) * W + (ox + dx) % W
        alive[i] = 1
        age[i] = 1
        gene[i] = colour
        sat[i] = 0.0

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
                        new_gene[i] = (gene[j] + random.uniform(-MUTATION, MUTATION)) % 1
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
                sat[i] = 0.0
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
            drift = (drift + HUE_STEP) % 1
            if is_repeating():
                stale += 1
            if stale >= 10 or generation >= MAX_GENERATIONS:
                seed()

    g.set_pen(BLACK)
    g.clear()
    for i in range(N):
        if alive[i]:
            if style == 0:
                h = gene[i]
            elif style == 1:
                h = ((i % W) + (i // W)) / (W + H) * RAINBOW_SPREAD
            else:
                a = age[i] if age[i] < 30 else 30
                h = a / 30 * AGE_SPREAD
            shown[i] = (h + drift) % 1
            a = age[i] if age[i] < RIPEN else RIPEN
            sat[i] += (a / RIPEN - sat[i]) * FADE
            glow[i] += (1.0 - glow[i]) * FADE
        else:
            glow[i] -= glow[i] * FADE
        v = glow[i]
        if v > 0.06:
            pen = PENS[(int(shown[i] * HUES) % HUES) * SATS * VALS
                       + int(sat[i] * (SATS - 1) + 0.5) * VALS
                       + min(VALS - 1, int(v * VALS))]
            g.set_pen(pen)
            g.pixel(i % W, i // W)
    return 0.03
