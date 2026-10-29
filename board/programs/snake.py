# Snake: the classic game, playing itself. The snake hunts the food, steering
# away from moves that would box it in, and grows a rainbow tail as it eats.
# When it finally crashes it flashes, crumbles away and starts again.
#   A = turn left   B = turn right   (the autopilot takes over again after a few seconds)
#
# Memory-friendly: the board is a bytearray, the flood-fill stack is
# preallocated, and pens are made once.
import random
from array import array
from stellar import StellarUnicorn

SPEED = 9            # moves per second
START = 3            # starting length
HAND_S = 4           # seconds the autopilot waits after you press a button
FRAME = 0.02

DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))   # right, down, left, up (turning = +-1)

def hsv(h, s, v):
    h %= 1.0
    i = int(h * 6); f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i % 6]
    return int(r * 255), int(g * 255), int(b * 255)

def setup(su, g):
    global BODYP, HEAD, FOOD, FOOD2, BLACK, WHITE, occ, seen, stack, ab
    BLACK = g.create_pen(0, 0, 0)
    WHITE = g.create_pen(255, 255, 255)
    HEAD = g.create_pen(255, 255, 230)
    FOOD = g.create_pen(255, 40, 60)
    FOOD2 = g.create_pen(120, 10, 20)
    BODYP = [g.create_pen(*hsv(i / 48, 0.9, 0.95)) for i in range(48)]
    occ = bytearray(256)
    seen = bytearray(256)
    stack = array("h", [0] * 256)
    ab = [False, False]
    reset(0.0)

def reset(t):
    global body, d, food, state, state_t, last_move, hand_until, hue0
    for i in range(256):
        occ[i] = 0
    body = []
    for k in range(START):                       # head is body[0]
        c = 7 * 16 + 4 - k
        body.append(c)
        occ[c] = 1
    d = 0
    place_food()
    state, state_t = "play", t
    last_move = t
    hand_until = -1.0
    hue0 = random.random() * 48

def place_food():
    global food
    free = 256 - len(body)
    if free <= 0:
        food = -1
        return
    k = random.randrange(free)
    for c in range(256):
        if not occ[c]:
            if k == 0:
                food = c
                return
            k -= 1

def step_cell(c, di):
    x, y = c % 16 + DIRS[di][0], c // 16 + DIRS[di][1]
    if 0 <= x < 16 and 0 <= y < 16:
        return y * 16 + x
    return -1

def room(start, tail):
    """How many free cells can be reached from start (the tail cell counts as free)."""
    for i in range(256):
        seen[i] = 0
    n, top = 0, 1
    stack[0] = start
    seen[start] = 1
    while top:
        top -= 1
        c = stack[top]
        n += 1
        x, y = c % 16, c // 16
        for nb in (c - 1 if x > 0 else -1, c + 1 if x < 15 else -1, c - 16 if y > 0 else -1, c + 16 if y < 15 else -1):
            if nb >= 0 and not seen[nb] and (not occ[nb] or nb == tail):
                seen[nb] = 1
                stack[top] = nb
                top += 1
    return n

def autopilot():
    head, tail = body[0], body[-1]
    fx, fy = food % 16, food // 16
    best, best_score = d, -99999
    for turn in (0, -1, 1):
        di = (d + turn) % 4
        c = step_cell(head, di)
        if c < 0 or (occ[c] and c != tail):
            continue
        space = room(c, tail)
        dist = abs(c % 16 - fx) + abs(c // 16 - fy)
        score = -dist * 4 - (turn != 0)
        if space < len(body) + 2:
            score -= 1000 - space                # avoid boxing itself in
        if score > best_score:
            best, best_score = di, score
    return best

def frame(su, g, t):
    global d, state, state_t, last_move, hand_until, body, hue0
    # buttons steer by hand for a while
    for i, sw in enumerate((StellarUnicorn.SWITCH_A, StellarUnicorn.SWITCH_B)):
        p = su.is_pressed(sw)
        if p and not ab[i] and state == "play":
            d = (d + (-1 if i == 0 else 1)) % 4
            hand_until = t + HAND_S
        ab[i] = p

    if state == "play" and t - last_move >= 1 / SPEED:
        last_move = t
        if t >= hand_until:
            d = autopilot()
        c = step_cell(body[0], d)
        tail = body[-1]
        if c < 0 or (occ[c] and c != tail):
            state, state_t = "crash", t
        else:
            ate = c == food
            if not ate:
                occ[body.pop()] = 0
            body.insert(0, c)
            occ[c] = 1
            if ate:
                place_food()
                if food < 0:                     # filled the whole board!
                    state, state_t = "crash", t

    g.set_pen(BLACK)
    g.clear()
    if state == "crash":
        p = t - state_t
        if p < 1.2:                              # flash
            if int(p * 8) % 2 == 0:
                g.set_pen(WHITE)
                for c in body:
                    g.pixel(c % 16, c // 16)
                return FRAME
        elif body:                               # crumble away from the tail
            if int(p * 30) % 2 == 0:
                occ[body.pop()] = 0
        else:
            reset(t)
            return FRAME
    # food blinks gently
    if food >= 0:
        g.set_pen(FOOD if int(t * 3) % 3 else FOOD2)
        g.pixel(food % 16, food // 16)
    # rainbow body, head brightest; the colours slide down the snake
    shift = int(hue0 + t * 6)
    n = len(body)
    for k in range(n - 1, 0, -1):
        c = body[k]
        g.set_pen(BODYP[(shift - k) % 48])
        g.pixel(c % 16, c // 16)
    if n:
        g.set_pen(HEAD)
        g.pixel(body[0] % 16, body[0] // 16)
    return FRAME
