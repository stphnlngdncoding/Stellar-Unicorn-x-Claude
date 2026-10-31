# Game of Life v2: still lifes and spaceships, taking turns.
#
# Still life round: a large still life (a pattern the Life rules leave
#   unchanged), mirror-symmetric left to right and filling most of the board,
#   glows for 10 seconds. Then a single white dot drops in next to it and the
#   whole thing comes apart. The edges don't wrap.
# Spaceship round: a fleet of gliders and lightweight spaceships flies across
#   the board, wrapping around the edges, until they crash into each other.
#
# A round ends when the world is empty, frozen, or flipping between two
# states (or stuck in a longer loop); it holds a moment, fades out, and the
# other kind of round begins.
#   A = drop the dot now   B = next round   C = pause / resume
#
# The six still lifes were found with a SAT solver (every cell checked
# against the Life rules, the left half mirrored onto the right).
#
# Memory-friendly: the world is an 18x18 bytearray with a border, so
# neighbours are fixed offsets and no neighbour tables are needed; nothing is
# allocated per frame.
import random
from array import array
from stellar import StellarUnicorn

STEP_SECONDS = 0.6   # time between generations (life.py uses 0.3)
CALM_SECONDS = 10    # how long the still life shows before the dot drops
FADE = 40            # how fast cells fade in and out (out of 256 per frame)
HUE_SPEED = 5        # how fast the colours stream across the board (per frame, of 256)
AGE_SHIFT = 23       # each generation a cell survives shifts its colour this much
SHIPS = (3, 5)       # how many spaceships in a fleet
MAX_GENERATIONS = 600  # safety: start over if something keeps running forever
HISTORY = 12         # catches loops up to this long (e.g. a period-3 oscillator)

# still lifes, one 16-bit row each (top row first, leftmost cell = top bit)
PATTERNS = (
    (0xcff3, 0xc813, 0x0180, 0xc243, 0x9999, 0x566a, 0xd24b, 0x1818,
     0xc7e3, 0xd81b, 0x13c8, 0x1668, 0xd00b, 0xd7eb, 0x0810, 0x07e0),
    (0x6ff6, 0x2814, 0x27e4, 0x6006, 0x9e79, 0x9249, 0xd42b, 0x1818,
     0xc183, 0xd99b, 0x1008, 0xcff3, 0x8241, 0x8001, 0xb24d, 0x5ffa),
    (0xc3c3, 0xa425, 0x3dbc, 0x4182, 0x6c36, 0x2bd4, 0x2244, 0xd24b,
     0x518a, 0x9e79, 0xe187, 0x1248, 0xde7b, 0xa185, 0x0c30, 0x1bd8),
    (0xcff3, 0xc813, 0x03c0, 0xc663, 0x4812, 0x8bd1, 0xf42f, 0x1248,
     0xd66b, 0xd42b, 0x1248, 0xde7b, 0xc183, 0x1a58, 0xea57, 0x8421),
    (0x1a58, 0x2bd4, 0x2814, 0xdbdb, 0x4242, 0x9a59, 0x75ae, 0x0420,
     0x6c36, 0x6816, 0x0240, 0x7e7e, 0xa185, 0x8661, 0x9249, 0xfc3f),
    (0xce73, 0x9249, 0x5c3a, 0xc3c3, 0x9819, 0xb66d, 0x4242, 0x2c34,
     0x6816, 0x8421, 0xb99d, 0x4662, 0x324c, 0x0c30, 0xf3cf, 0x9249),
)

# spaceships as (x, y) cells; each launch flips and turns them at random
GLIDER = ((1, 0), (2, 1), (0, 2), (1, 2), (2, 2))
LWSS = ((1, 0), (4, 0), (0, 1), (0, 2), (4, 2), (0, 3), (1, 3), (2, 3), (3, 3))

HUES = 64
VALS = 8
WHITES = 2           # newborns flash white for one step, then go full colour
S = 18               # padded row length

def setup(su, g):
    global BLACK, PENS, IDX, OFFS, POS, alive, nxt, age, glow, col, white, prev1, prev2, hist
    global hist_n, snap, prev_btn, pattern, kind, phase, phase_t, next_step, generation, drift, paused, wrap
    BLACK = g.create_pen(0, 0, 0)
    PENS = []
    for hi in range(HUES):
        for wi in range(WHITES):
            s = 1.0 - wi / WHITES
            for vi in range(VALS):
                h = hi / HUES
                v = (vi + 1) / VALS
                i = int(h * 6)
                f = h * 6 - i
                p, q, tt = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
                r, gg, b = ((v, tt, p), (q, v, p), (p, v, tt), (p, q, v), (tt, p, v), (v, p, q))[i % 6]
                PENS.append(g.create_pen(int(r * 255), int(gg * 255), int(b * 255)))
    # board cell k (0..255) lives at IDX[k] in the padded 18x18 world
    IDX = array("H", [((k >> 4) + 1) * S + (k & 15) + 1 for k in range(256)])
    OFFS = (-S - 1, -S, -S + 1, -1, 1, S - 1, S, S + 1)
    # colour field: rings out from the centre line plus a vertical sweep,
    # mirrored left/right so the symmetry shows in the colours too
    POS = bytearray(256)
    for y in range(16):
        for x in range(16):
            dx = x - 7.5 if x > 7 else 7.5 - x
            POS[y * 16 + x] = int(dx * 22 + y * 9) & 255
    alive = bytearray(S * S)
    nxt = bytearray(S * S)
    age = bytearray(256)
    glow = bytearray(256)
    col = bytearray(256)       # hue last shown, kept while a cell fades out
    white = bytearray(256)     # newborn whiteness, counts down
    prev1 = bytearray(S * S)
    prev2 = bytearray(S * S)
    snap = bytearray(S * S)    # every 64 generations, to catch fleets that fly forever
    hist = [bytearray(S * S) for _ in range(HISTORY)]
    hist_n = 0
    prev_btn = [False, False, False]
    pattern = random.randrange(len(PATTERNS))
    drift = 0
    paused = False
    kind = "still"
    start(0.0)

def clear_world():
    for i in range(S * S):
        alive[i] = 0

def start(t):
    global phase, phase_t, generation, hist_n, wrap, next_step
    clear_world()
    for k in range(256):
        age[k] = 0
        white[k] = 0
    if kind == "still":
        wrap = False
        rows = PATTERNS[pattern]
        for k in range(256):
            if (rows[k >> 4] >> (15 - (k & 15))) & 1:
                alive[IDX[k]] = 1
                age[k] = 40
        phase = "calm"
    else:
        wrap = True
        launch_fleet()
        phase = "run"
        next_step = t + 2.0          # let the fleet fade in first
    phase_t = t
    generation = 0
    hist_n = 0
    prev1[:] = alive
    prev2[:] = alive
    prev2[0] = 1                     # the border is never 1, so the first check can't match

def launch_fleet():
    n = random.randint(SHIPS[0], SHIPS[1])
    placed = 0
    tries = 0
    while placed < n and tries < 200:
        tries += 1
        shape = LWSS if random.getrandbits(2) == 0 else GLIDER
        fx, fy, tr = random.getrandbits(1), random.getrandbits(1), random.getrandbits(1)
        ox, oy = random.randrange(16), random.randrange(16)
        ok = True
        for x, y in shape:
            if fx:
                x = 4 - x
            if fy:
                y = 4 - y
            if tr:
                x, y = y, x
            # keep a gap of one cell from ships already placed
            for dy in (-2, -1, 0, 1, 2):
                for dx in (-2, -1, 0, 1, 2):
                    if alive[((oy + y + dy) % 16 + 1) * S + (ox + x + dx) % 16 + 1]:
                        ok = False
        if not ok:
            continue
        for x, y in shape:
            if fx:
                x = 4 - x
            if fy:
                y = 4 - y
            if tr:
                x, y = y, x
            k = ((oy + y) % 16) * 16 + (ox + x) % 16
            alive[IDX[k]] = 1
            age[k] = 1
            white[k] = WHITES - 1
        placed += 1

def drop_dot():
    # a dead cell next to the pattern, so the dot always sets something off
    while True:
        k = random.randrange(256)
        i = IDX[k]
        if alive[i]:
            continue
        n = 0
        for o in OFFS:
            n += alive[i + o]
        if n:
            break
    alive[i] = 1
    age[k] = 1
    white[k] = WHITES - 1
    glow[k] = 255

def fill_border():
    # copy the opposite edges into the border so the world wraps
    for y in range(1, 17):
        alive[y * S] = alive[y * S + 16]
        alive[y * S + 17] = alive[y * S + 1]
    alive[0:S] = alive[16 * S:17 * S]
    alive[17 * S:18 * S] = alive[S:2 * S]

def step():
    global alive, nxt
    if wrap:
        fill_border()
    a = alive
    for k in range(256):
        i = IDX[k]
        n = (a[i - 19] + a[i - 18] + a[i - 17] + a[i - 1] + a[i + 1]
             + a[i + 17] + a[i + 18] + a[i + 19])
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
    if wrap:                       # leave the border empty for comparisons
        for y in range(S):
            alive[y * S] = 0
            alive[y * S + 17] = 0
        for x in range(S):
            alive[x] = 0
            alive[17 * S + x] = 0

def finished():
    """True when the world is empty, frozen, flipping, or looping."""
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
    global phase, phase_t, next_step, generation, drift, paused, pattern, kind
    if pressed(su, 0, StellarUnicorn.SWITCH_A) and phase == "calm":
        phase_t = t - CALM_SECONDS
    if pressed(su, 1, StellarUnicorn.SWITCH_B) and phase != "out":
        clear_world()
        phase, phase_t = "out", t
    if pressed(su, 2, StellarUnicorn.SWITCH_C):
        paused = not paused

    if paused:
        pass
    elif phase == "calm" and t - phase_t >= CALM_SECONDS:
        drop_dot()
        phase, next_step = "run", t + STEP_SECONDS
    elif phase == "run" and t >= next_step:
        next_step = t + STEP_SECONDS
        step()
        generation += 1
        if finished():
            phase, phase_t = "hold", t
    elif phase == "hold" and t - phase_t > 2.5:
        clear_world()
        phase, phase_t = "out", t
    elif phase == "out" and t - phase_t > 1.5:
        if kind == "still":
            kind = "ships"
        else:
            kind = "still"
            pattern = (pattern + 1) % len(PATTERNS)
        start(t)

    # ---- draw ----
    drift = (drift + HUE_SPEED) & 255
    g.set_pen(BLACK)
    g.clear()
    for k in range(256):
        v = glow[k]
        if alive[IDX[k]]:
            v += ((255 - v) * FADE >> 8) + 1
            glow[k] = v if v < 255 else 255
            # colours stream through the field and jump as cells age
            col[k] = (POS[k] + drift + age[k] * AGE_SHIFT) & 255
        elif v:
            v -= (v * FADE >> 8) + 1
            glow[k] = v if v > 0 else 0
            col[k] = (col[k] + 3) & 255     # dying cells keep shifting as they fade
        v = glow[k]
        if v > 12:
            g.set_pen(PENS[((col[k] * HUES >> 8) * WHITES + white[k]) * VALS + (v * VALS >> 8)])
            g.pixel(k & 15, k >> 4)
    return 0.03
