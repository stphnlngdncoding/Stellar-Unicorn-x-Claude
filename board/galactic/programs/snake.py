# Snake: the classic game, playing itself (Galactic Unicorn version: the
# whole 53x11 strip is the field). The snake hunts the food, steering away
# from moves that would box it in or cut it off from its own tail, and grows
# a rainbow tail as it eats.
# When it finally crashes (or starves, stuck chasing its own tail with the
# food out of reach) it flashes, crumbles away and starts again.
#   A = turn left   B = turn right   (the autopilot takes over again after a few seconds)
#
# Memory-friendly: the board is a bytearray, the body is a ring buffer, the
# flood-fill stack is preallocated, and pens are made once.
import random
from array import array
from galactic import GalacticUnicorn

SPEED = 12           # moves per second
START = 4            # starting length
HAND_S = 4           # seconds the autopilot waits after you press a button
STARVE = 1500        # moves without food before a snake stuck chasing its own tail gives up
FRAME = 0.02

DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))   # right, down, left, up (turning = +-1)

def hsv(h, s, v):
    h %= 1.0
    i = int(h * 6); f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i % 6]
    return int(r * 255), int(g * 255), int(b * 255)

def setup(su, g):
    global W, H, N, BODYP, HEAD, FOOD, FOOD2, BLACK, WHITE, occ, seen, stack, ring, ab, mark
    W, H = su.WIDTH, su.HEIGHT
    N = W * H
    BLACK = g.create_pen(0, 0, 0)
    WHITE = g.create_pen(255, 255, 255)
    HEAD = g.create_pen(255, 255, 230)
    FOOD = g.create_pen(255, 40, 60)
    FOOD2 = g.create_pen(120, 10, 20)
    BODYP = [g.create_pen(*hsv(i / 48, 0.9, 0.95)) for i in range(48)]
    occ = bytearray(N)
    seen = bytearray(N)
    mark = 0
    stack = array("h", [0] * N)
    ring = array("h", [0] * N)       # the body: ring[head_i] is the head, going back to the tail
    ab = [False, False]
    reset(0.0)

def body_at(k):
    """The k-th body cell (0 = head)."""
    return ring[(head_i - k) % N]

def reset(t):
    global head_i, length, d, state, state_t, last_move, hand_until, hue0, hungry
    hungry = 0
    for i in range(N):
        occ[i] = 0
    length = START
    head_i = START - 1
    y = H // 2
    for k in range(START):           # tail at ring[0], head at ring[START - 1]
        c = y * W + 4 + k
        ring[k] = c
        occ[c] = 1
    d = 0
    place_food()
    state, state_t = "play", t
    last_move = t
    hand_until = -1.0
    hue0 = random.random() * 48

def place_food():
    global food
    free = N - length
    if free <= 0:
        food = -1
        return
    k = random.randrange(free)
    for c in range(N):
        if not occ[c]:
            if k == 0:
                food = c
                return
            k -= 1

def step_cell(c, di):
    x, y = c % W + DIRS[di][0], c // W + DIRS[di][1]
    if 0 <= x < W and 0 <= y < H:
        return y * W + x
    return -1

def room(start, tail):
    """Flood-fills the free cells reachable from start. Sets tail_ok when the
    tail can be reached (then the snake can always escape by following its
    own tail, so the fill stops right there); otherwise returns how many
    cells it could reach."""
    global tail_ok, mark
    mark += 1                        # seen[] holds the mark of the last fill
    if mark > 255:
        mark = 1
        for i in range(N):
            seen[i] = 0
    m = mark
    tail_ok = True
    if start == tail:
        return N
    n, top = 0, 1
    stack[0] = start
    seen[start] = m
    w1 = W - 1
    last = N - W
    while top:
        top -= 1
        c = stack[top]
        n += 1
        x = c % W
        if x > 0:
            nb = c - 1
            if nb == tail:
                return N
            if seen[nb] != m and not occ[nb]:
                seen[nb] = m
                stack[top] = nb
                top += 1
        if x < w1:
            nb = c + 1
            if nb == tail:
                return N
            if seen[nb] != m and not occ[nb]:
                seen[nb] = m
                stack[top] = nb
                top += 1
        if c >= W:
            nb = c - W
            if nb == tail:
                return N
            if seen[nb] != m and not occ[nb]:
                seen[nb] = m
                stack[top] = nb
                top += 1
        if c < last:
            nb = c + W
            if nb == tail:
                return N
            if seen[nb] != m and not occ[nb]:
                seen[nb] = m
                stack[top] = nb
                top += 1
    tail_ok = False
    return n

def autopilot():
    head, tail = body_at(0), body_at(length - 1)
    fx, fy = food % W, food // W
    need = length + 2
    best, best_score = d, -99999
    for turn in (0, -1, 1):
        di = (d + turn) % 4
        c = step_cell(head, di)
        if c < 0 or (occ[c] and c != tail):
            continue
        space = room(c, tail)
        dist = abs(c % W - fx) + abs(c // W - fy)
        score = -dist * 4 - (turn != 0)
        if not tail_ok:
            # cut off from its tail: only worth it with lots of room
            score -= 500 if space >= need else 1000 - space
        if score > best_score:
            best, best_score = di, score
    return best

def frame(su, g, t):
    global d, state, state_t, last_move, hand_until, head_i, length, hue0, hungry
    # buttons steer by hand for a while
    i = 0
    for sw in (GalacticUnicorn.SWITCH_A, GalacticUnicorn.SWITCH_B):
        p = su.is_pressed(sw)
        if p and not ab[i] and state == "play":
            d = (d + (-1 if i == 0 else 1)) % 4
            hand_until = t + HAND_S
        ab[i] = p
        i += 1

    if state == "play" and t - last_move >= 1 / SPEED:
        last_move = t
        if t >= hand_until:
            d = autopilot()
        c = step_cell(body_at(0), d)
        tail = body_at(length - 1)
        if c < 0 or (occ[c] and c != tail):
            state, state_t = "crash", t
        else:
            ate = c == food
            if not ate:
                occ[tail] = 0
                length -= 1
            head_i = (head_i + 1) % N
            ring[head_i] = c
            length += 1
            occ[c] = 1
            hungry += 1
            if ate:
                hungry = 0
                place_food()
                if food < 0:                     # filled the whole board!
                    state, state_t = "crash", t
            elif hungry >= STARVE:               # going round in circles: give up
                state, state_t = "crash", t

    g.set_pen(BLACK)
    g.clear()
    if state == "crash":
        p = t - state_t
        if p < 1.2:                              # flash
            if int(p * 8) % 2 == 0:
                g.set_pen(WHITE)
                for k in range(length):
                    c = body_at(k)
                    g.pixel(c % W, c // W)
                return FRAME
        elif length:                             # crumble away from the tail
            if int(p * 30) % 2 == 0:
                occ[body_at(length - 1)] = 0
                length -= 1
        else:
            reset(t)
            return FRAME
    # food blinks gently
    if food >= 0:
        g.set_pen(FOOD if int(t * 3) % 3 else FOOD2)
        g.pixel(food % W, food // W)
    # rainbow body, head brightest; the colours slide down the snake
    shift = int(hue0 + t * 6)
    for k in range(length - 1, 0, -1):
        c = body_at(k)
        g.set_pen(BODYP[(shift - k) % 48])
        g.pixel(c % W, c // W)
    if length:
        g.set_pen(HEAD)
        c = body_at(0)
        g.pixel(c % W, c // W)
    return FRAME
