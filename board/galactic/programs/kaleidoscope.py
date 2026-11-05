# Kaleidoscope: coloured glass beads tumble in a slowly turning tube and
# mirrors fold them into a symmetric pattern. (Galactic version: like looking
# down a real kaleidoscope, the mirrors repeat the picture into a row of
# square tiles along the strip, each reflected into its neighbours. With
# eight mirrors every tile is 8-fold symmetric; with four, each tile has just
# a cross of mirrors and neighbouring tiles are mirror images of each other.) Each pixel
# takes the colour of the nearest bead, glowing brighter towards its middle,
# with thin dark lines where two pieces of glass meet, like stained glass.
# Now and then the tube is given a shake and everything tumbles into a new
# picture; the colours drift through the rainbow over time.
#   A = shake the tube   B = switch between 8 and 4 mirrors
#
# Only the few dozen pixels of one wedge are worked out each frame; every
# other pixel is a reflection of one of them. Pens are made once in setup().
import math
import random
from galactic import GalacticUnicorn

BEADS = 9            # pieces of glass in the tube
SPIN = 0.12          # how fast the tube turns, radians per second
TUMBLE = 1.2         # how fast the beads slide about (px per second)
SHAKE_S = (25, 50)   # seconds between shakes (min, max)
LINES = 0.6          # thickness of the dark lines between pieces (0 = none)
GLOW = 0.6           # how much brighter the middle of each piece is
COLOUR_SPEED = 2     # how fast the colours drift through the rainbow
COLOURS = 4          # how much of the rainbow one picture uses: 1 = a single family, 6 = all of it
FOUR_WAY = 0         # 0 = eight mirrors, 1 = four mirrors (per tile)
TILE = 15            # size of one mirrored tile in pixels (7 = lots of small tiles, 27 = two big ones)
FRAME = 0.04

HUES = 64
VALS = 12

def setup(su, g):
    global PENS, BLACK, beads, angle, last_t, next_shake, hue_drift, prev_btn, cellpen, shake_until
    global W, H, TUBE, SCALE
    W, H = su.WIDTH, su.HEIGHT
    SCALE = max(5, TILE) / 16          # this tile's size compared with the 16 x 16 original
    TUBE = 9.0 * SCALE                 # beads stay within this distance of the middle
    BLACK = g.create_pen(0, 0, 0)
    PENS = []
    for hi in range(HUES):
        for vi in range(VALS):
            h = hi / HUES
            v = ((vi + 1) / VALS) ** 1.6
            s = 1.0 if vi < VALS - 2 else 0.75     # the very brightest go a little milky
            i = int(h * 6)
            f = h * 6 - i
            p, q, tt = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
            r, gg, b = ((v, tt, p), (q, v, p), (p, v, tt), (p, q, v), (tt, p, v), (v, p, q))[i % 6]
            PENS.append(g.create_pen(int(r * 255), int(gg * 255), int(b * 255)))
    build_mirrors()
    beads = []
    fill_tube()
    angle = 0.0
    last_t = 0.0
    hue_drift = 0.0
    next_shake = random.uniform(*SHAKE_S)
    shake_until = 0.0
    prev_btn = [False, False]

def build_mirrors():
    """CELL[pixel] = which wedge cell it reflects; WEDGE = that cell's (a, b).
    The strip is a row of TILE x TILE tiles centred on the middle pixel; the
    tile edges are mirrors (so the pattern carries on, reflected, into the next
    tile) and inside each tile a cross of mirrors, plus the two diagonals when
    there are eight, folds everything into one small wedge."""
    global CELL, WEDGE, cellpen
    T = max(5, TILE)
    cx, cy = W // 2, H // 2
    CELL = bytearray(W * H)
    WEDGE = []
    seen = {}
    for y in range(H):
        ib = y - cy if y >= cy else cy - y          # rows from the middle
        for x in range(W):
            q = (x - cx) % (2 * T)                  # fold across the tile edges...
            if q > T:
                q = 2 * T - q
            if 2 * q > T:                           # ...and across the tile's middle
                q = T - q
            jb = ib % (2 * T)                       # rows fold the same way (only
            if jb > T:                              # matters for tiles shorter
                jb = 2 * T - jb                     # than the strip)
            if 2 * jb > T:
                jb = T - jb
            ia = q
            if not FOUR_WAY and jb > ia:
                ia, jb = jb, ia
            key = ia * 64 + jb
            if key not in seen:
                seen[key] = len(WEDGE)
                WEDGE.append((float(ia), float(jb)))
            CELL[y * W + x] = seen[key]
    cellpen = [0] * len(WEDGE)

def fill_tube():
    # spread in hue around a base colour
    base = random.randrange(HUES)
    spread = max(3, COLOURS * HUES // 6)
    del beads[:]
    for _ in range(BEADS):
        r = TUBE * math.sqrt(random.random())
        a = random.uniform(0, 6.283)
        sp = random.uniform(0.4, 1.0) * TUMBLE
        d = random.uniform(0, 6.283)
        beads.append([r * math.cos(a), r * math.sin(a), sp * math.cos(d), sp * math.sin(d),
                      (base + random.randrange(spread)) % HUES])

def shake(t):
    global shake_until
    shake_until = t + 1.5
    for b in beads:
        d = random.uniform(0, 6.283)
        sp = random.uniform(3, 6) * max(TUMBLE, 0.5)
        b[2] = sp * math.cos(d)
        b[3] = sp * math.sin(d)
    # a few pieces change colour too
    for _ in range(max(1, BEADS // 3)):
        b = random.choice(beads)
        b[4] = (random.choice(beads)[4] + random.randint(-4, 4)) % HUES

def move(dt, t):
    calm = t > shake_until
    for b in beads:
        x = b[0] + b[2] * dt
        y = b[1] + b[3] * dt
        r2 = x * x + y * y
        if r2 > TUBE * TUBE:                 # bounce off the wall of the tube
            r = math.sqrt(r2)
            nx, ny = x / r, y / r
            dot = b[2] * nx + b[3] * ny
            b[2] -= 2 * dot * nx
            b[3] -= 2 * dot * ny
            x, y = nx * TUBE, ny * TUBE
        b[0], b[1] = x, y
        if calm:                             # after a shake, settle back to a gentle slide
            sp = math.sqrt(b[2] * b[2] + b[3] * b[3])
            want = TUMBLE
            if sp > want * 1.05 and sp > 0:
                k = 1 - min(0.9, 2.0 * dt)
                b[2] *= k
                b[3] *= k
            elif sp < want * 0.3:
                d = random.uniform(0, 6.283)
                b[2] += 0.3 * want * math.cos(d)
                b[3] += 0.3 * want * math.sin(d)

def pressed(su, k, sw):
    now = su.is_pressed(sw)
    was = prev_btn[k]
    prev_btn[k] = now
    return now and not was

def frame(su, g, t):
    global angle, last_t, next_shake, hue_drift, FOUR_WAY
    dt = t - last_t
    if dt < 0 or dt > 0.3:
        dt = FRAME
    last_t = t
    if pressed(su, 0, GalacticUnicorn.SWITCH_A) or t >= next_shake:
        shake(t)
        next_shake = t + random.uniform(*SHAKE_S)
    if pressed(su, 1, GalacticUnicorn.SWITCH_B):
        FOUR_WAY = 1 - FOUR_WAY
        build_mirrors()

    angle += SPIN * dt
    hue_drift = (hue_drift + COLOUR_SPEED * dt) % HUES
    move(dt, t)

    c = math.cos(angle)
    s = math.sin(angle)
    drift = int(hue_drift)
    line = LINES * 1.4
    top = VALS - 1
    n = len(WEDGE)
    for k in range(n):
        a, b = WEDGE[k]
        sx = a * c - b * s
        sy = a * s + b * c
        d1 = 1e9
        d2 = 1e9
        h = 0
        for bd in beads:
            dx = sx - bd[0]
            dy = sy - bd[1]
            d = dx * dx + dy * dy
            if d < d1:
                d2 = d1
                d1 = d
                h = bd[4]
            elif d < d2:
                d2 = d
        r1 = math.sqrt(d1)
        edge = math.sqrt(d2) - r1             # 0 right on a seam between two pieces
        if line > 0 and edge < line:
            cellpen[k] = BLACK if edge < line * 0.45 else PENS[((h + drift) % HUES) * VALS + 1]
            continue
        v = 1.0 - GLOW * min(1.0, r1 / (4.0 * SCALE))  # brighter towards the middle of a piece
        vi = int(v * top)
        if vi < 2:
            vi = 2
        cellpen[k] = PENS[((h + drift) % HUES) * VALS + vi]

    i = 0
    for y in range(H):
        for x in range(W):
            g.set_pen(cellpen[CELL[i]])
            g.pixel(x, y)
            i += 1
    return FRAME
