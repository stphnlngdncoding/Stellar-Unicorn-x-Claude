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
import random
from stellar import StellarUnicorn

# --- settings to play with ---
STEP_SECONDS = 0.6   # time between generations (bigger = slower)
FADE = 0.12          # how fast cells fade in/out (smaller = softer, slower)
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

GLIDER = [(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)]

def hsv(g, h, s=1.0, v=1.0):
    i = int(h * 6)
    f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, gg, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i % 6]
    return g.create_pen(int(r * 255), int(gg * 255), int(b * 255))

def seed():
    global stale, generation
    centres = [(random.randrange(W), random.randrange(H), random.random())
               for _ in range(TRIBES)]
    for y in range(H):
        for x in range(W):
            i = y * W + x
            best = min(centres, key=lambda c: (c[0] - x) ** 2 + (c[1] - y) ** 2)
            gene[i] = best[2]
            alive[i] = 1 if random.random() < DENSITY else 0
            age[i] = 1 if alive[i] else 0
            sat[i] = 0.0
    del history[:]
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
    new = bytearray(N)
    new_gene = gene[:]
    for y in range(H):
        for x in range(W):
            parents = []
            for dy in (-1, 0, 1):
                row = ((y + dy) % H) * W
                for dx in (-1, 0, 1):
                    if dx or dy:
                        j = row + (x + dx) % W
                        if alive[j]:
                            parents.append(j)
            n = len(parents)
            i = y * W + x
            if alive[i]:
                new[i] = 1 if n == 2 or n == 3 else 0
            elif n == 3:
                new[i] = 1
                parent = random.choice(parents)
                new_gene[i] = (gene[parent] + random.uniform(-MUTATION, MUTATION)) % 1
    for i in range(N):
        if new[i]:
            if alive[i]:
                age[i] = min(age[i] + 1, 255)
            else:
                age[i] = 1
                sat[i] = 0.0
        else:
            age[i] = 0
    alive[:] = new
    gene[:] = new_gene

def is_repeating():
    state = bytes(alive)
    if state in history:
        return True
    history.append(state)
    if len(history) > 12:
        history.pop(0)
    return False

def pressed_once(su, switch):
    now = su.is_pressed(switch)
    was = prev.get(switch, False)
    prev[switch] = now
    return now and not was

def setup(su, g):
    global W, H, N, BLACK, alive, age, gene, glow, shown, sat, history, prev
    global style, drift, paused, stale, generation, next_step
    W, H = su.WIDTH, su.HEIGHT
    N = W * H
    BLACK = g.create_pen(0, 0, 0)
    alive = bytearray(N)
    age = bytearray(N)
    gene = [0.0] * N
    glow = [0.0] * N
    shown = [0.5] * N
    sat = [0.0] * N
    history = []
    prev = {}
    style = COLOR_STYLE
    drift = 0.0
    paused = False
    stale = 0
    generation = 0
    next_step = STEP_SECONDS
    seed()

def frame(su, g, t):
    global style, drift, paused, stale, generation, next_step

    if pressed_once(su, StellarUnicorn.SWITCH_A):
        seed()
    if pressed_once(su, StellarUnicorn.SWITCH_B):
        add_glider()
    if pressed_once(su, StellarUnicorn.SWITCH_C):
        paused = not paused
    if pressed_once(su, StellarUnicorn.SWITCH_D):
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
        x, y = i % W, i // W
        if alive[i]:
            if style == 0:
                h = gene[i]
            elif style == 1:
                h = (x + y) / (W + H) * RAINBOW_SPREAD
            else:
                h = min(age[i], 30) / 30 * AGE_SPREAD
            shown[i] = (h + drift) % 1
            target = 1.0
            target_sat = min(age[i], RIPEN) / RIPEN * MAX_SATURATION
            sat[i] += (target_sat - sat[i]) * FADE
        else:
            target = 0.0
        glow[i] += (target - glow[i]) * FADE
        if glow[i] > 0.01:
            g.set_pen(hsv(g, shown[i], sat[i], glow[i]))
            g.pixel(x, y)
    return 0.02
