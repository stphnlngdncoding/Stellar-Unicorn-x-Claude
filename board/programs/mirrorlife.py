# Mirror Life: the Game of Life plays out on the left half of the board and
# its reflection plays on the right, so every pattern grows into a mirrored
# twin. The left half wraps top to bottom, and at the middle line (and the
# outer edges) each cell sees its own reflection as a neighbour, which is
# exactly the Life of a mirror-symmetric world, so nothing ever breaks the
# symmetry.
#
# Each round starts either from a random soup or from a small seed by the
# middle line that blooms outwards. Newborns flash white; colours stream
# out from the middle and shift as cells age. The right half can be tinted
# differently (MIRROR_HUE) or run a few generations behind the left (ECHO),
# so the mirror visibly catches up. A round ends when the world is empty,
# frozen or looping, holds a moment, and a new one begins.
#   A = new round   B = pause / resume
#
# Memory-friendly: the half world is a 10x18 bytearray with a border, so
# neighbours are fixed offsets; nothing is allocated per frame.
import random
from array import array
from stellar import StellarUnicorn

STEP_SECONDS = 0.35  # time between generations
DENSITY = 0.35       # how full a random soup starts
SEED_CHANCE = 0.5    # how often a round starts from a small seed instead of a soup
HUE_SPEED = 4        # how fast colours stream out from the middle
AGE_SHIFT = 18       # each generation a cell survives shifts its colour this much
MIRROR_HUE = 0       # tint the right half: 0 = identical twin, 128 = opposite colours
ECHO = 0             # the right half shows the left as it was this many generations ago
MAX_GENERATIONS = 500
HISTORY = 12
FRAME = 0.03

HUES = 64
WHITES = 2
W = 10               # padded half width (8 + border)
CELLS = 128          # cells in one half

def setup(su, g):
    global BLACK, PENS, IDX, POS, alive, nxt, age, white, hist, hist_n, snap, prev1, prev2
    global ring_age, ring_white, ring_n, prev_btn, phase, phase_t, next_step, generation, drift, paused
    BLACK = g.create_pen(0, 0, 0)
    PENS = []
    for hi in range(HUES):
        for wi in range(WHITES):
            s = 1.0 - wi / WHITES
            h = hi / HUES
            i = int(h * 6)
            f = h * 6 - i
            p, q, tt = 1 - s, 1 - f * s, 1 - (1 - f) * s
            r, gg, b = ((1, tt, p), (q, 1, p), (p, 1, tt), (p, q, 1), (tt, p, 1), (1, p, q))[i % 6]
            PENS.append(g.create_pen(int(r * 255), int(gg * 255), int(b * 255)))
    # half cell k: x = k & 7 (0 = left edge, 7 = next to the middle), y = k >> 3
    IDX = array("H", [((k >> 3) + 1) * W + (k & 7) + 1 for k in range(CELLS)])
    POS = bytearray(CELLS)
    for k in range(CELLS):
        x = k & 7
        y = k >> 3
        POS[k] = int((7 - x) * 24 + abs(y - 7.5) * 6) & 255   # rings out from the middle
    alive = bytearray(W * 18)
    nxt = bytearray(W * 18)
    age = bytearray(CELLS)
    white = bytearray(CELLS)
    prev1 = bytearray(W * 18)
    prev2 = bytearray(W * 18)
    snap = bytearray(W * 18)
    hist = [bytearray(W * 18) for _ in range(HISTORY)]
    hist_n = 0
    ring_age = [bytearray(CELLS) for _ in range(ECHO + 1)]
    ring_white = [bytearray(CELLS) for _ in range(ECHO + 1)]
    ring_n = 0
    prev_btn = [False, False]
    drift = 0
    paused = False
    generation = 0
    start(0.0)

def fill_border():
    # left and right edges reflect (each edge cell is its own neighbour);
    # top and bottom wrap
    a = alive
    for y in range(1, 17):
        a[y * W] = a[y * W + 1]
        a[y * W + 9] = a[y * W + 8]
    a[0:W] = a[16 * W:17 * W]
    a[17 * W:18 * W] = a[W:2 * W]

def remember():
    global ring_n
    ring_n += 1
    j = ring_n % (ECHO + 1)
    ra = ring_age[j]
    rw = ring_white[j]
    for k in range(CELLS):
        if alive[IDX[k]]:
            ra[k] = age[k] or 1
            rw[k] = white[k]
        else:
            ra[k] = 0

def start(t):
    global phase, phase_t, generation, hist_n, next_step, ring_n
    for i in range(W * 18):
        alive[i] = 0
    for k in range(CELLS):
        age[k] = 0
        white[k] = 0
    if random.random() < SEED_CHANCE:
        # a small random seed hugging the middle line
        top = random.randint(4, 9)
        for y in range(top, top + random.randint(3, 5)):
            for x in range(4, 8):
                if random.random() < 0.5:
                    k = y * 8 + x
                    alive[IDX[k]] = 1
                    age[k] = 1
                    white[k] = WHITES - 1
    else:
        for k in range(CELLS):
            if random.random() < DENSITY:
                alive[IDX[k]] = 1
                age[k] = 1
                white[k] = WHITES - 1
    fill_border()
    for j in range(ECHO + 1):        # the mirror starts out showing the same thing
        ring_n = j
        remember()
    phase = "run"
    phase_t = t
    next_step = t + 1.2
    generation = 0
    hist_n = 0
    prev1[:] = alive
    prev2[:] = alive
    prev2[0] = 2                     # never matches on the first check

def step():
    global alive, nxt
    a = alive
    for k in range(CELLS):
        i = IDX[k]
        n = (a[i - 11] + a[i - 10] + a[i - 9] + a[i - 1] + a[i + 1]
             + a[i + 9] + a[i + 10] + a[i + 11])
        if n == 3 or (n == 2 and a[i]):
            nxt[i] = 1
            if a[i]:
                if age[k] < 255:
                    age[k] += 1
                if white[k]:
                    white[k] -= 1
            else:
                age[k] = 1
                white[k] = WHITES - 1
        else:
            nxt[i] = 0
            age[k] = 0
    alive, nxt = nxt, alive
    fill_border()
    remember()

def finished():
    global hist_n
    if max(alive) == 0 or alive == prev1 or alive == prev2:
        return True
    for k in range(min(hist_n, HISTORY)):
        if hist[k] == alive:
            return True
    hist[hist_n % HISTORY][:] = alive
    hist_n += 1
    prev2[:] = prev1
    prev1[:] = alive
    if generation % 64 == 0:
        if generation and snap == alive:
            return True
        snap[:] = alive
    return generation >= MAX_GENERATIONS

def pressed(su, k, sw):
    now = su.is_pressed(sw)
    was = prev_btn[k]
    prev_btn[k] = now
    return now and not was

def frame(su, g, t):
    global phase, phase_t, next_step, generation, drift, paused
    if pressed(su, 0, StellarUnicorn.SWITCH_A):
        phase, phase_t = "out", t - 0.5
        for i in range(W * 18):
            alive[i] = 0
        for j in range(ECHO + 1):
            remember()
    if pressed(su, 1, StellarUnicorn.SWITCH_B):
        paused = not paused

    if paused:
        pass
    elif phase == "run" and t >= next_step:
        next_step = t + STEP_SECONDS
        step()
        generation += 1
        if finished():
            phase, phase_t = "hold", t
    elif phase == "hold" and t >= next_step:
        # let the echo catch up with the left half, then rest a moment
        next_step = t + STEP_SECONDS
        if t - phase_t > 2.5 + ECHO * STEP_SECONDS:
            for i in range(W * 18):
                alive[i] = 0
            for j in range(ECHO + 1):
                remember()
            phase, phase_t = "out", t
        else:
            remember()
    elif phase == "out" and t - phase_t > 1.0:
        start(t)

    # ---- draw: left half live, right half the (maybe delayed) reflection ----
    drift = (drift + HUE_SPEED) & 255
    g.set_pen(BLACK)
    g.clear()
    j = (ring_n - ECHO) % (ECHO + 1)
    ra = ring_age[j]
    rw = ring_white[j]
    sh = AGE_SHIFT
    for k in range(CELLS):
        x = k & 7
        y = k >> 3
        if alive[IDX[k]]:
            h = (POS[k] + drift + age[k] * sh) & 255
            g.set_pen(PENS[(h * HUES >> 8) * WHITES + white[k]])
            g.pixel(x, y)
        a = ra[k]
        if a:
            h = (POS[k] + drift + a * sh + MIRROR_HUE) & 255
            g.set_pen(PENS[(h * HUES >> 8) * WHITES + rw[k]])
            g.pixel(15 - x, y)
    return FRAME
