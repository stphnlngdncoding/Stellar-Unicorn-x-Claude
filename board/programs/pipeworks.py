# Pipeworks: shiny pipes grow one segment at a time across a dark grid,
# turning at random corners and never crossing each other. Each pipe is one
# colour: lit from above, so its sideways runs are lighter than its upright
# ones, with darker elbows, couplings and end caps, and a glint that runs along
# them. When a pipe boxes itself in, a new one starts in a new colour
# somewhere free; when the board is mostly full it dissolves and starts again.
#   A = clear and restart
#
# Memory-friendly: the grid lives in bytearrays made once in setup(), and every
# pen (each colour's shades and fade steps) is made once in setup().
import random
from stellar import StellarUnicorn

PIPES = 1            # how many pipes grow at once
SPEED = 3.0          # segments grown per second, per pipe
TURN = 0.3           # chance of turning at each corner (0 = only when blocked)
FULL = 0.8           # dissolve once this much of the grid is filled
JOINT = 3            # a dark coupling every this many straight segments (0 = none)
GRID = 5             # brightness of the faint grid dots (0 = no grid)
DISSOLVE_S = 2.5     # seconds the dissolve takes
FRAME = 0.04

FADES = 6            # brightness steps used while dissolving

# rich pipe colours (r, g, b) at full strength
COLOURS = ((200, 30, 20), (220, 110, 0), (200, 170, 0), (40, 170, 30),
           (0, 160, 140), (20, 80, 220), (120, 40, 210), (200, 30, 140))


def setup(su, g):
    global W, H, PENS, BLACK, DOT, cells, col, kind, order, rnd, pipes
    global a_was, acc, state, state_t, last_col, NX, NY, OX, OY
    W, H = su.WIDTH, su.HEIGHT
    BLACK = g.create_pen(0, 0, 0)
    DOT = g.create_pen(GRID, GRID, GRID * 2)
    # PENS[c][k][f]: colour c, kind k (0 dark, 1 base, 2 light, 3 glint), fade f
    PENS = []
    for r, gg, b in COLOURS:
        kinds = []
        for k in range(4):
            if k == 0:
                rr, g2, b2 = r * 0.4, gg * 0.4, b * 0.4
            elif k == 1:
                rr, g2, b2 = r * 0.75, gg * 0.75, b * 0.75
            elif k == 2:
                rr, g2, b2 = r + (255 - r) * 0.2, gg + (255 - gg) * 0.2, b + (255 - b) * 0.2
            else:
                rr, g2, b2 = r + (255 - r) * 0.55, gg + (255 - gg) * 0.55, b + (255 - b) * 0.55
            kinds.append([g.create_pen(int(rr * f / FADES), int(g2 * f / FADES), int(b2 * f / FADES))
                          for f in range(FADES + 1)])
        PENS.append(kinds)
    col = bytearray(W * H)          # 0 = empty, else colour + 1
    kind = bytearray(W * H)
    order = bytearray(W * H)        # position along its pipe (for the glint), wraps at 256
    rnd = bytearray(W * H)          # dissolve order
    cells = bytearray(((W + 1) // 2) * ((H + 1) // 2))
    pipes = [[0, 0, 0, 0, 0, 0, 0, 0] for _ in range(max(1, PIPES))]
    a_was = False
    last_col = -1
    reset(0.0)


def reset(t):
    global state, state_t, acc, NX, NY, OX, OY
    for i in range(W * H):
        col[i] = 0
    # nodes sit every 2 px, leaving a 1 px gap between neighbouring pipes;
    # on an even-sized board, pick which edge gets the spare pixel
    OX = random.randrange(2) if W % 2 == 0 else 0
    OY = random.randrange(2) if H % 2 == 0 else 0
    NX = (W - OX + 1) // 2
    NY = (H - OY + 1) // 2
    for i in range(NX * NY):
        cells[i] = 0
    for p in pipes:
        p[7] = 0
    state = 0
    state_t = t
    acc = 0.0
    for p in pipes:
        start(p)


DX = (1, 0, -1, 0)
DY = (0, 1, 0, -1)


def free(nx, ny):
    return 0 <= nx < NX and 0 <= ny < NY and not cells[ny * NX + nx]


def exits(nx, ny):
    n = 0
    for d in range(4):
        if free(nx + DX[d], ny + DY[d]):
            n += 1
    return n


def put(nx, ny, sx, sy, c, k, o):
    # sx, sy: 0 = on the node, else half a step towards that direction
    x = OX + nx * 2 + sx
    y = OY + ny * 2 + sy
    i = y * W + x
    col[i] = c + 1
    kind[i] = k
    order[i] = o & 255
    rnd[i] = random.randrange(1, 256)


def start(p):
    # p = [nx, ny, dir, colour, order, half-step, straight count, alive]
    global last_col
    # count the free nodes that still have somewhere to go, then pick one
    n = 0
    for ny in range(NY):
        for nx in range(NX):
            if not cells[ny * NX + nx] and exits(nx, ny):
                n += 1
    if n == 0:
        p[7] = 0
        return False
    k = random.randrange(n)
    for ny in range(NY):
        for nx in range(NX):
            if not cells[ny * NX + nx] and exits(nx, ny):
                if k == 0:
                    c = random.randrange(len(COLOURS))
                    while c == last_col:
                        c = random.randrange(len(COLOURS))
                    last_col = c
                    cells[ny * NX + nx] = 1
                    put(nx, ny, 0, 0, c, 0, 0)      # a dark end cap
                    p[0], p[1], p[3], p[4], p[5], p[6], p[7] = nx, ny, c, 1, 0, 0, 1
                    p[2] = random.randrange(4)
                    return True
                k -= 1
    return False


def grow(p):
    nx, ny, d, c = p[0], p[1], p[2], p[3]
    if p[5] == 0:
        # at a node: choose where to go next
        sd = free(nx + DX[d], ny + DY[d])
        a = (d + 1) & 3
        b = (d + 3) & 3
        fa = free(nx + DX[a], ny + DY[a])
        fb = free(nx + DX[b], ny + DY[b])
        nd = d
        if (not sd) or (random.random() < TURN and (fa or fb)):
            if fa and fb:
                nd = a if random.random() < 0.5 else b
            elif fa:
                nd = a
            elif fb:
                nd = b
            elif not sd:
                # boxed in: cap it off and start a fresh pipe
                put(nx, ny, 0, 0, c, 0, p[4])
                p[7] = 0
                return
        if nd != d and p[4] > 1:
            put(nx, ny, 0, 0, c, 0, p[4] - 1)        # darker elbow
            p[6] = 0
        p[2] = nd
        cells[(ny + DY[nd]) * NX + nx + DX[nd]] = 1  # claim the next node
        put(nx, ny, DX[nd], DY[nd], c, 2 if DX[nd] else 1, p[4])
        p[4] += 1
        p[5] = 1
    else:
        nx += DX[d]
        ny += DY[d]
        p[0], p[1] = nx, ny
        p[6] += 1
        k = 2 if DX[d] else 1
        if JOINT and p[6] % (JOINT + 1) == 0:
            k = 0
        put(nx, ny, 0, 0, c, k, p[4])
        p[4] += 1
        p[5] = 0


def filled():
    n = 0
    for i in range(NX * NY):
        n += cells[i]
    return n


def frame(su, g, t):
    global a_was, acc, state, state_t
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was:
        reset(t)
    a_was = a

    if state == 0:
        acc += SPEED * 2 * FRAME
        steps = int(acc)
        acc -= steps
        for _ in range(min(steps, 8)):
            for p in pipes:
                if p[7]:
                    grow(p)
                if not p[7] and state == 0:
                    if filled() >= FULL * NX * NY or not start(p):
                        state = 1
                        state_t = t
    elif state == 1 and t - state_t > DISSOLVE_S:
        state = 2
        state_t = t
    elif state == 2 and t - state_t > 0.8:
        reset(t)

    # the glint: a short bright band sweeping along every pipe from its start
    gl = int(t * 14) & 63
    if state == 1:
        cut = int(255 * (t - state_t) / DISSOLVE_S)
        fade = FADES - int(FADES * 0.6 * (t - state_t) / DISSOLVE_S)
    else:
        cut = 0
        fade = FADES
    g.set_pen(BLACK)
    g.clear()
    for y in range(H):
        i = y * W
        on_row = GRID and state == 0 and (y - OY) % 2 == 0 and y >= OY
        for x in range(W):
            c = col[i]
            if c:
                if state == 2 or rnd[i] <= cut:
                    pass
                else:
                    k = kind[i]
                    if k and (gl - order[i]) & 63 < 3:
                        k = 3
                    g.set_pen(PENS[c - 1][k][fade])
                    g.pixel(x, y)
            elif on_row and x >= OX and (x - OX) % 2 == 0:
                g.set_pen(DOT)
                g.pixel(x, y)
            i += 1
    return FRAME
