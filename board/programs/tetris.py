# Tetris that plays itself. A 10-wide well sits in the middle of the board;
# the autopilot looks at every rotation and position for each piece, picks
# the one that keeps the stack low, flat and free of holes, then rotates,
# slides and drops it there. Full rows flash and vanish. The next piece shows
# in the top-right corner, and the lines cleared fill up the left edge.
# When the stack finally reaches the top it greys out and a new game starts.
#   A = drop the current piece right now   B = speed up / slow down
#
# Memory-friendly: the well is a bytearray; pieces and pens are made once.
import random
from stellar import StellarUnicorn

TICK = 0.07          # seconds per move (rotate / slide / fall a row)
FAST_TICK = 0.03
WELL_X = 3           # left edge of the well on the board
WW, WH = 10, 16      # well size

# piece shapes as (x, y) cells in their box, and their box size
SHAPES = (
    (((0, 1), (1, 1), (2, 1), (3, 1)), 4),   # I
    (((0, 0), (1, 0), (0, 1), (1, 1)), 2),   # O
    (((1, 0), (0, 1), (1, 1), (2, 1)), 3),   # T
    (((1, 0), (2, 0), (0, 1), (1, 1)), 3),   # S
    (((0, 0), (1, 0), (1, 1), (2, 1)), 3),   # Z
    (((0, 0), (0, 1), (1, 1), (2, 1)), 3),   # J
    (((2, 0), (0, 1), (1, 1), (2, 1)), 3),   # L
)
COLOURS = ((60, 220, 255), (255, 220, 40), (190, 80, 255), (60, 230, 90),
           (255, 60, 70), (60, 110, 255), (255, 150, 30))

def rotations(cells, n):
    out = [cells]
    for _ in range(3):
        cells = tuple((n - 1 - y, x) for x, y in cells)
        if sorted(cells) in [sorted(c) for c in out]:
            break
        out.append(cells)
    # shift each rotation so its top-left cell sits at y = 0
    res = []
    for c in out:
        mx, my = min(x for x, _ in c), min(y for _, y in c)
        res.append(tuple((x - mx, y - my) for x, y in c))
    return res

def setup(su, g):
    global ROTS, PENS, DIM, WALL, GREY, WHITE, BLACK, well, a_was, b_was, fast
    ROTS = [rotations(c, n) for c, n in SHAPES]
    PENS = [None] + [g.create_pen(*c) for c in COLOURS]
    DIM = [None] + [g.create_pen(c[0] // 5, c[1] // 5, c[2] // 5) for c in COLOURS]
    WALL = g.create_pen(30, 34, 48)
    GREY = g.create_pen(70, 70, 80)
    WHITE = g.create_pen(255, 255, 255)
    BLACK = g.create_pen(0, 0, 0)
    well = bytearray(WW * WH)
    a_was = b_was = False
    fast = False
    new_game(0.0)

def new_game(t):
    global lines, nxt, state, state_t, bag
    for i in range(WW * WH):
        well[i] = 0
    lines = 0
    bag = []
    nxt = draw_piece()
    state, state_t = "spawn", t

def draw_piece():
    global bag
    if not bag:
        bag = list(range(7))
        for i in range(6, 0, -1):                 # shuffle a bag of all seven pieces
            j = random.randrange(i + 1)
            bag[i], bag[j] = bag[j], bag[i]
    return bag.pop()

def fits(b, cells, px, py):
    for x, y in cells:
        x += px
        y += py
        if x < 0 or x >= WW or y >= WH:
            return False
        if y >= 0 and b[y * WW + x]:
            return False
    return True

def drop_y(b, cells, px):
    y = -2
    while fits(b, cells, px, y + 1):
        y += 1
    return y

def score_placement(cells, px, py):
    """How good it is to lock this piece here (bigger = better)."""
    b = bytearray(well)
    for x, y in cells:
        if y + py < 0:
            return -99999
        b[(y + py) * WW + x + px] = 1
    cleared = 0
    for y in range(WH):
        full = True
        for x in range(WW):
            if not b[y * WW + x]:
                full = False
                break
        if full:
            cleared += 1
            for yy in range(y, 0, -1):
                b[yy * WW:yy * WW + WW] = b[(yy - 1) * WW:yy * WW]
            for x in range(WW):
                b[x] = 0
    heights, holes = [], 0
    for x in range(WW):
        h, seen = 0, False
        for y in range(WH):
            if b[y * WW + x]:
                if not seen:
                    h, seen = WH - y, True
            elif seen:
                holes += 1
        heights.append(h)
    bump = 0
    for x in range(WW - 1):
        bump += abs(heights[x] - heights[x + 1])
    return -51 * sum(heights) + 76 * cleared * cleared * 10 - 356 * holes - 18 * bump - 30 * max(heights)

def plan(piece):
    best, best_s = (0, 3), -999999
    for r, cells in enumerate(ROTS[piece]):
        w = max(x for x, _ in cells) + 1
        for px in range(WW - w + 1):
            py = drop_y(well, cells, px)
            if py < -1:
                continue
            s = score_placement(cells, px, py)
            if s > best_s:
                best, best_s = (r, px), s
    return best

def lock():
    global lines, full_rows
    cells = ROTS[cur][rot]
    for x, y in cells:
        if 0 <= y + py:
            well[(y + py) * WW + x + px] = cur + 1
    full_rows = []
    for y in range(WH):
        if all(well[y * WW + x] for x in range(WW)):
            full_rows.append(y)
    lines += len(full_rows)

def clear_rows():
    for y in full_rows:
        for yy in range(y, 0, -1):
            well[yy * WW:yy * WW + WW] = well[(yy - 1) * WW:yy * WW]
        for x in range(WW):
            well[x] = 0

def frame(su, g, t):
    global state, state_t, cur, nxt, rot, px, py, target, next_tick, a_was, b_was, fast, over_row
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    b = su.is_pressed(StellarUnicorn.SWITCH_B)
    drop_now = a and not a_was
    if b and not b_was:
        fast = not fast
    a_was, b_was = a, b
    tick = FAST_TICK if fast else TICK

    if state == "spawn":
        cur, nxt = nxt, draw_piece()
        rot, px, py = 0, 3 if cur != 1 else 4, -1
        if not fits(well, ROTS[cur][0], px, 0):
            state, state_t, over_row = "over", t, WH - 1
        else:
            target = plan(cur)
            state, next_tick = "move", t
    elif state == "move" and t >= next_tick:
        next_tick = t + tick
        tr, tx = target
        cells = ROTS[cur][rot]
        if drop_now:
            py = drop_y(well, cells, px)
            lock()
            state, state_t = ("clear" if full_rows else "spawn"), t
        elif rot != tr and fits(well, ROTS[cur][tr], px, py):
            rot = tr
        elif px != tx and fits(well, cells, px + (1 if tx > px else -1), py):
            px += 1 if tx > px else -1
        elif fits(well, cells, px, py + 1):
            py += 1
        else:
            lock()
            state, state_t = ("clear" if full_rows else "spawn"), t
    elif state == "clear" and t - state_t > 0.3:
        clear_rows()
        state = "spawn"
    elif state == "over" and t - state_t > 0.04 * (WH - over_row):
        over_row -= 1
        if over_row < -12:
            new_game(t)

    # ---- draw ----
    g.set_pen(BLACK)
    g.clear()
    g.set_pen(WALL)
    for y in range(16):
        g.pixel(WELL_X - 1, y)
        g.pixel(WELL_X + WW, y)
    flash = state == "clear" and int((t - state_t) * 20) % 2 == 0
    for y in range(WH):
        for x in range(WW):
            c = well[y * WW + x]
            if c:
                if state == "over" and y > over_row:
                    g.set_pen(GREY)
                elif state == "clear" and y in full_rows:
                    g.set_pen(WHITE if flash else PENS[c])
                else:
                    g.set_pen(PENS[c])
                g.pixel(WELL_X + x, y)
    if state == "move":
        cells = ROTS[cur][rot]
        gy = drop_y(well, cells, px)               # faint ghost where it will land
        g.set_pen(DIM[cur + 1])
        for x, y in cells:
            if y + gy >= 0:
                g.pixel(WELL_X + px + x, y + gy)
        g.set_pen(PENS[cur + 1])
        for x, y in cells:
            if y + py >= 0:
                g.pixel(WELL_X + px + x, y + py)
    # next piece, squeezed into the top-right corner
    g.set_pen(PENS[nxt + 1])
    for x, y in ROTS[nxt][0]:
        if x < 2 and y < 2:
            g.pixel(14 + x, 1 + y)
    # lines cleared fill the left edge, one dot per line, wrapping every 32
    k = lines % 32
    for i in range(k):
        g.set_pen(PENS[(i // 2) % 7 + 1])
        g.pixel(i % 2, 15 - i // 2)
    return 0.02
