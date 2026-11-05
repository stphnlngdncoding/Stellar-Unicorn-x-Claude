# Game of Life v2: still lifes and spaceships, taking turns
# (Galactic Unicorn version: the whole 53x11 strip).
#
# Still life round: a large still life (a pattern the Life rules leave
#   unchanged), mirror-symmetric about the middle column and filling the
#   whole strip, glows for 10 seconds. Then a single white dot drops in next
#   to it and the whole thing comes apart. The edges don't wrap.
# Spaceship round: a fleet of gliders and lightweight spaceships flies along
#   the strip, wrapping around the edges, until they crash into each other.
#
# A round ends when the world is empty, frozen, or flipping between two
# states (or stuck in a longer loop); it holds a moment, the board goes dark,
# and the other kind of round begins. Cells switch on and off instantly.
#   A = drop the dot now   B = next round   C = pause / resume
#
# The six still lifes were found with a SAT solver (every cell checked
# against the Life rules, the left half mirrored onto the right, and the
# cells just outside the strip kept dead too).
#
# Memory-friendly: the world is a 55x13 bytearray with a border, so
# neighbours are fixed offsets and no neighbour tables are needed; nothing is
# allocated per frame.
import random
from array import array
from galactic import GalacticUnicorn

STEP_SECONDS = 0.6   # time between generations (life.py uses 0.3)
CALM_SECONDS = 10    # how long the still life shows before the dot drops
HUE_SPEED = 5        # how fast the colours stream across the board (per frame, of 256)
AGE_SHIFT = 23       # each generation a cell survives shifts its colour this much
SHIPS = (5, 9)       # how many spaceships in a fleet
MAX_GENERATIONS = 600  # safety: start over if something keeps running forever
HISTORY = 12         # catches loops up to this long (e.g. a period-3 oscillator)
QUIET = 120          # end a round after this many generations of ships just flying past
                     # each other (nothing crashing, nothing changing)

# still lifes for the 53x11 strip, one number per row (top row first): the
# left 27 columns, leftmost cell = top bit; column 26 is the mirror line and
# columns 27..52 repeat 25..0
PATTERNS = (
    (0x0566361, 0x1da25a7, 0x2202828, 0x24ccb56, 0x6b45b44, 0x0a55064,
     0x6935695, 0x5609ab2, 0x140a28a, 0x526a289, 0x666c6d8),
    (0x2b36636, 0x5a14a14, 0x42532e4, 0x3bd0c85, 0x041533a, 0x39ad412,
     0x20a3445, 0x1f38dfc, 0x5146203, 0x6259a79, 0x032944c),
    (0x0600366, 0x4a0054a, 0x786653a, 0x044a305, 0x1a180e4, 0x23e4f17,
     0x5448930, 0x621a94f, 0x01030a9, 0x652c2b0, 0x6634300),
    (0x2310c8c, 0x54aa4e4, 0x37ab318, 0x0854041, 0x0991fff, 0x3ab3000,
     0x4294649, 0x7ee7bff, 0x0018000, 0x16c56db, 0x1b6db6d),
    (0x0362001, 0x014e182, 0x1231932, 0x29ce56a, 0x4d10a85, 0x716f4b5,
     0x06a8555, 0x1883d05, 0x274618d, 0x2928e52, 0x6c6d8d9),
    (0x6c358c0, 0x294d126, 0x4b61122, 0x6881b68, 0x168d12f, 0x64cca41,
     0x2901bb4, 0x4d0002f, 0x6567d80, 0x04a4b76, 0x031801a),
)
HALF = 27            # columns stored per pattern row

# spaceships as (x, y) cells; each launch flips and turns them at random
GLIDER = ((1, 0), (2, 1), (0, 2), (1, 2), (2, 2))
LWSS = ((1, 0), (4, 0), (0, 1), (0, 2), (4, 2), (0, 3), (1, 3), (2, 3), (3, 3))

HUES = 64
VALS = 8
WHITES = 2           # newborns flash white for one step, then go full colour

def setup(su, g):
    global W, H, N, S, BLACK, PENS, IDX, OFFS, POS, alive, nxt, age, white, prev1, prev2, hist
    global hist_n, snap, pops, quiet, prev_btn, pattern, kind, phase, phase_t, next_step, generation, drift, paused, wrap
    W, H = su.WIDTH, su.HEIGHT
    N = W * H
    S = W + 2            # padded row length
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
    # board cell k lives at IDX[k] in the padded world
    IDX = array("H", [(k // W + 1) * S + k % W + 1 for k in range(N)])
    OFFS = (-S - 1, -S, -S + 1, -1, 1, S - 1, S, S + 1)
    # colour field: bands out from the middle column plus a vertical sweep,
    # mirrored left/right so the symmetry shows in the colours too
    POS = bytearray(N)
    mid = (W - 1) / 2
    for y in range(H):
        for x in range(W):
            dx = x - mid if x > mid else mid - x
            POS[y * W + x] = int(dx * 8 + y * 10) & 255
    alive = bytearray(S * (H + 2))
    nxt = bytearray(S * (H + 2))
    age = bytearray(N)
    white = bytearray(N)       # newborn whiteness, counts down
    prev1 = bytearray(S * (H + 2))
    prev2 = bytearray(S * (H + 2))
    snap = bytearray(S * (H + 2))  # taken at generations 1, 2, 4, 8, ... to catch long loops
    hist = [bytearray(S * (H + 2)) for _ in range(HISTORY)]
    hist_n = 0
    pops = array("H", [0] * 60)       # population of the last 60 generations
    quiet = 0
    prev_btn = [False, False, False]
    pattern = random.randrange(len(PATTERNS))
    drift = 0
    paused = False
    kind = "still"
    start(0.0)

def clear_world():
    for i in range(S * (H + 2)):
        alive[i] = 0

def start(t):
    global phase, phase_t, generation, hist_n, wrap, next_step, quiet
    clear_world()
    quiet = 0
    for k in range(N):
        age[k] = 0
        white[k] = 0
    if kind == "still":
        wrap = False
        rows = PATTERNS[pattern]
        for k in range(N):
            x = k % W
            if x >= HALF:
                x = W - 1 - x          # mirror the right side
            if (rows[k // W] >> (HALF - 1 - x)) & 1:
                alive[IDX[k]] = 1
                age[k] = 40
        phase = "calm"
    else:
        wrap = True
        launch_fleet()
        phase = "run"
        next_step = t + 2.0          # show the fleet for a moment first
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
    while placed < n and tries < 300:
        tries += 1
        lw = random.getrandbits(2) < 2
        shape = LWSS if lw else GLIDER
        fx, fy = random.getrandbits(1), random.getrandbits(1)
        # spaceships mostly fly along the strip; gliders go any diagonal
        tr = (random.getrandbits(3) == 0) if lw else random.getrandbits(1)
        ox, oy = random.randrange(W), random.randrange(H)
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
                    if alive[((oy + y + dy) % H + 1) * S + (ox + x + dx) % W + 1]:
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
            k = ((oy + y) % H) * W + (ox + x) % W
            alive[IDX[k]] = 1
            age[k] = 1
            white[k] = WHITES - 1
        placed += 1

def drop_dot():
    # a dead cell next to the pattern, so the dot always sets something off
    while True:
        k = random.randrange(N)
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

def fill_border():
    # copy the opposite edges into the border so the world wraps
    a = alive
    for y in range(1, H + 1):
        a[y * S] = a[y * S + W]
        a[y * S + W + 1] = a[y * S + 1]
    a[0:S] = a[H * S:(H + 1) * S]
    a[(H + 1) * S:(H + 2) * S] = a[S:2 * S]

def step():
    global alive, nxt
    if wrap:
        fill_border()
    a = alive
    s1 = S - 1
    s2 = S + 1
    for k in range(N):
        i = IDX[k]
        n = (a[i - s2] + a[i - S] + a[i - s1] + a[i - 1] + a[i + 1]
             + a[i + s1] + a[i + S] + a[i + s2])
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
        a = alive
        for y in range(H + 2):
            a[y * S] = 0
            a[y * S + W + 1] = 0
        for x in range(S):
            a[x] = 0
            a[(H + 1) * S + x] = 0

def finished():
    """True when the world is empty, frozen, flipping, or looping."""
    global hist_n, quiet
    if max(alive) == 0 or alive == prev1 or alive == prev2:
        return True
    for k in range(min(hist_n, HISTORY)):
        if hist[k] == alive:
            return True
    hist[hist_n % HISTORY][:] = alive
    hist_n += 1
    prev2[:] = prev1
    prev1[:] = alive
    # any longer loop: compare with a snapshot taken at each power of two
    if generation > 2 and snap == alive:
        return True
    if generation & (generation - 1) == 0:
        snap[:] = alive
    # gliders and spaceships repeat every 4 generations (and most oscillators
    # divide 60); if the population keeps repeating for a long while,
    # everything is just flying past or blinking
    n = sum(alive)
    j = generation % 60
    quiet = quiet + 1 if n == pops[j] else 0
    pops[j] = n
    return quiet >= QUIET or generation >= MAX_GENERATIONS

def pressed(su, k, sw):
    now = su.is_pressed(sw)
    was = prev_btn[k]
    prev_btn[k] = now
    return now and not was

def frame(su, g, t):
    global phase, phase_t, next_step, generation, drift, paused, pattern, kind
    if pressed(su, 0, GalacticUnicorn.SWITCH_A) and phase == "calm":
        phase_t = t - CALM_SECONDS
    if pressed(su, 1, GalacticUnicorn.SWITCH_B) and phase != "out":
        clear_world()
        phase, phase_t = "out", t
    if pressed(su, 2, GalacticUnicorn.SWITCH_C):
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
    elif phase == "out" and t - phase_t > 1.0:
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
    top = VALS - 1
    for k in range(N):
        if alive[IDX[k]]:
            # colours stream through the field and jump as cells age
            h = (POS[k] + drift + age[k] * AGE_SHIFT) & 255
            g.set_pen(PENS[((h * HUES >> 8) * WHITES + white[k]) * VALS + top])
            g.pixel(k % W, k // W)
    return 0.03
