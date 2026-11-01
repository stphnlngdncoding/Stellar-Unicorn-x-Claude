# Mirror Life: the Game of Life plays out on the left half of the board and
# its reflection plays on the right, so every pattern grows into a mirrored
# twin. The left half wraps top to bottom, and at the middle line (and the
# outer edges) each cell sees its own reflection as a neighbour, which is
# exactly the Life of a mirror-symmetric world, so nothing ever breaks the
# symmetry.
#
# Each round starts either from a random soup or from a small seed by the
# middle line that blooms outwards, and picks one of a few hand-made
# palettes: three colours that sit well together, bright against the black.
# New cells glow in (with a pale flash), dead ones fade away, and colours
# stream out from the middle and shift as cells age. The right half can be
# tinted differently (MIRROR_HUE) or run a few generations behind the left
# (ECHO), so the mirror visibly catches up. A round ends when the world is
# empty, frozen or looping, holds a moment, fades out, and a new one begins.
#   A = new round   B = pause / resume
#
# Memory-friendly: the half world is a 10x18 bytearray with a border, so
# neighbours are fixed offsets; nothing is allocated per frame. Pens are
# made once per round.
import random
from array import array
from stellar import StellarUnicorn

STEP_SECONDS = 0.5   # time between generations
FADE_IN = 0.25       # seconds for a new cell to glow in
FADE_OUT = 1.2       # seconds for a dead cell to fade away
PALETTE = 0          # 0 = a different palette each round, 1.. = always that one (see PALETTES)
DENSITY = 0.35       # how full a random soup starts
SEED_CHANCE = 0.5    # how often a round starts from a small seed instead of a soup
HUE_SPEED = 40       # how fast colours stream out from the middle (of 256 per second)
AGE_SHIFT = 14       # each generation a cell survives shifts its colour this much
FLASH = 0.5          # how pale newborns are for their first generation (0 = no flash)
MIRROR_HUE = 0       # tint the right half: 0 = identical twin, 128 = the far side of the palette
ECHO = 0             # the right half shows the left as it was this many generations ago
MAX_GENERATIONS = 500
HISTORY = 12
FRAME = 0.03

# three colours each, blended into a loop: bright, saturated, and related
PALETTES = (
    ((255, 45, 35), (255, 140, 0), (255, 215, 70)),     # 1 ember: red, orange, gold
    ((0, 220, 170), (0, 140, 255), (120, 70, 255)),     # 2 lagoon: jade, blue, violet
    ((255, 30, 150), (130, 50, 255), (0, 210, 255)),    # 3 neon: magenta, purple, cyan
    ((140, 255, 30), (255, 225, 0), (255, 110, 0)),     # 4 citrus: lime, lemon, tangerine
    ((40, 255, 120), (0, 190, 230), (255, 70, 200)),    # 5 aurora: green, teal, pink
    ((255, 80, 130), (255, 170, 90), (70, 240, 200)),   # 6 candy: rose, peach, mint
    ((190, 235, 255), (40, 110, 255), (110, 30, 230)),  # 7 ice: frost, blue, indigo
)
PAL = 32             # colours per palette loop
LEVELS = 12          # brightness steps for fading
W = 10               # padded half width (8 + border)
CELLS = 128          # cells in one half

def setup(su, g):
    global BLACK, PENS, IDX, POS, alive, nxt, age, white, hist, hist_n, snap, prev1, prev2
    global ring_age, ring_white, ring_n, prev_btn, phase, phase_t, next_step, generation
    global drift, paused, last_t, lvl, hue, wh, pal_i
    BLACK = g.create_pen(0, 0, 0)
    PENS = []
    pal_i = random.randrange(len(PALETTES)) if PALETTE == 0 else (PALETTE - 1) % len(PALETTES)
    make_pens(g)
    # half cell k: x = k & 7 (0 = left edge, 7 = next to the middle), y = k >> 3
    IDX = array("H", [((k >> 3) + 1) * W + (k & 7) + 1 for k in range(CELLS)])
    POS = bytearray(CELLS)
    for k in range(CELLS):
        x = k & 7
        y = k >> 3
        POS[k] = int((7 - x) * 20 + abs(y - 7.5) * 5) & 255   # rings out from the middle
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
    # what's on screen, per half: brightness 0..255, colour, paleness
    lvl = (bytearray(CELLS), bytearray(CELLS))
    hue = (bytearray(CELLS), bytearray(CELLS))
    wh = (bytearray(CELLS), bytearray(CELLS))
    prev_btn = [False, False]
    drift = 0.0
    last_t = 0.0
    paused = False
    generation = 0
    start(0.0)

def make_pens(g):
    """PENS[(colour * 2 + pale) * LEVELS + level] for the current palette."""
    del PENS[:]
    cols = PALETTES[pal_i]
    n = len(cols)
    for i in range(PAL):
        f = i * n / PAL
        j = int(f)
        f -= j
        f = f * f * (3 - 2 * f)                     # smooth blend between anchors
        a = cols[j]
        b = cols[(j + 1) % n]
        c = [a[m] + (b[m] - a[m]) * f for m in range(3)]
        for pale in (0, 1):
            p = FLASH * pale
            cc = [c[m] + (255 - c[m]) * p for m in range(3)]
            for lv in range(LEVELS):
                v = ((lv + 1) / LEVELS) ** 1.8
                PENS.append(g.create_pen(int(cc[0] * v), int(cc[1] * v), int(cc[2] * v)))

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

def clear_world():
    for i in range(W * 18):
        alive[i] = 0
    for j in range(ECHO + 1):
        remember()

def start(t, g=None):
    global phase, phase_t, generation, hist_n, next_step, ring_n, pal_i
    if g is not None:
        if PALETTE == 0:
            pal_i = (pal_i + random.randint(1, len(PALETTES) - 1)) % len(PALETTES)
        else:
            pal_i = (PALETTE - 1) % len(PALETTES)
        make_pens(g)
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
                    white[k] = 1
    else:
        for k in range(CELLS):
            if random.random() < DENSITY:
                alive[IDX[k]] = 1
                age[k] = 1
                white[k] = 1
    fill_border()
    for j in range(ECHO + 1):        # the mirror starts out showing the same thing
        ring_n = j
        remember()
    phase = "run"
    phase_t = t
    next_step = t + max(1.2, FADE_IN + 0.5)
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
                white[k] = 0
            else:
                age[k] = 1
                white[k] = 1
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
    global phase, phase_t, next_step, generation, drift, paused, last_t
    dt = t - last_t
    if dt < 0 or dt > 0.3:
        dt = FRAME
    last_t = t
    if pressed(su, 0, StellarUnicorn.SWITCH_A) and phase != "out":
        clear_world()
        phase, phase_t = "out", t
    if pressed(su, 1, StellarUnicorn.SWITCH_B):
        paused = not paused

    if paused:
        next_step += dt
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
            clear_world()
            phase, phase_t = "out", t
        else:
            remember()
    elif phase == "out" and t - phase_t > FADE_OUT + 0.6:
        start(t, g)

    # ---- draw: left half live, right half the (maybe delayed) reflection ----
    if not paused:
        drift = (drift + HUE_SPEED * dt) % 256
    up = 255 if FADE_IN <= 0 else int(255 * dt / FADE_IN) + 1
    down = 255 if FADE_OUT <= 0 else int(255 * dt / FADE_OUT) + 1
    d = int(drift)
    g.set_pen(BLACK)
    g.clear()
    j = (ring_n - ECHO) % (ECHO + 1)
    ra = ring_age[j]
    rw = ring_white[j]
    sh = AGE_SHIFT
    L0, L1 = lvl
    H0, H1 = hue
    W0, W1 = wh
    for k in range(CELLS):
        x = k & 7
        y = k >> 3
        # left
        v = L0[k]
        if alive[IDX[k]]:
            H0[k] = (POS[k] + d + age[k] * sh) & 255
            W0[k] = white[k]
            v = v + up if v + up < 255 else 255
        elif v:
            v = v - down if v > down else 0
        L0[k] = v
        if v:
            g.set_pen(PENS[(((H0[k] * PAL) >> 8) * 2 + W0[k]) * LEVELS + ((v * LEVELS) >> 8)])
            g.pixel(x, y)
        # right
        v = L1[k]
        a = ra[k]
        if a:
            H1[k] = (POS[k] + d + a * sh + MIRROR_HUE) & 255
            W1[k] = rw[k]
            v = v + up if v + up < 255 else 255
        elif v:
            v = v - down if v > down else 0
        L1[k] = v
        if v:
            g.set_pen(PENS[(((H1[k] * PAL) >> 8) * 2 + W1[k]) * LEVELS + ((v * LEVELS) >> 8)])
            g.pixel(15 - x, y)
    return FRAME
