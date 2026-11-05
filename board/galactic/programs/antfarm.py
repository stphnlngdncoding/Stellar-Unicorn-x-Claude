# Ant farm: a side view through the glass of a long, shallow farm. Red ants
# dig narrow tunnels through the sand, carry each grain up to the surface and
# drop it on a growing mound. Now and then a crumb of food (green) lands on
# the surface; an ant fetches it and takes it down to the queen (pink) in her
# chamber, who lays an egg (white) that hatches into a new ant. Ants sometimes
# dig out side chambers or a second entrance. When the sand is half dug out,
# a fresh farm starts.
# (Galactic Unicorn version: a wide cross-section along the strip.)
#   A = drop some food   B = start a fresh farm
#
# Memory-friendly: the farm is a bytearray, the routes up to the surface and
# down to the queen are bytearray distance maps rebuilt only when the
# tunnels change, and every pen is made once in setup().
import random
from array import array
from galactic import GalacticUnicorn

START_ANTS = 6
MAX_ANTS = 24
TICK = 0.3           # seconds per ant step (smaller = busier ants)
DIG_CHANCE = 0.22    # chance an ant underground digs on a step (if it can)
FOOD_S = (6, 15)     # seconds between food drops (min, max)
HATCH_S = 25         # seconds for an egg to hatch
FULL = 190           # dug cells before a fresh farm starts
GROUND = 3           # first row of sand (rows above are air)
WALK = GROUND - 1    # the surface row the ants walk along

# ant states
WANDER, CARRY, DROP, FORAGE, FOOD, UP = 0, 1, 2, 3, 4, 5

def setup(su, g):
    global W, H, N, SKY, SAND, TUNNEL, PILE, ANT, ANT_SAND, ANT_FOOD, QUEEN, QUEEN2, EGG, CRUMB, BLACK
    global open_, dist_s, dist_q, queue, prev_btn, next_tick
    W, H = su.WIDTH, su.HEIGHT
    N = W * H
    BLACK = g.create_pen(0, 0, 0)
    SKY = [g.create_pen(10 + 8 * y, 30 + 14 * y, 70 + 20 * y) for y in range(GROUND)]
    # sand gets darker and redder with depth, with a little grain to it
    SAND = []
    for k in range(N):
        y = k // W
        d = (y - GROUND) * 9
        n = random.randint(-14, 14)
        SAND.append(g.create_pen(max(0, 190 - d + n), max(0, 140 - d - d // 2 + n), max(0, 70 - d // 2 + n // 2)))
    TUNNEL = g.create_pen(14, 7, 3)
    PILE = (g.create_pen(205, 160, 85), g.create_pen(180, 135, 70))
    ANT = g.create_pen(255, 25, 10)
    ANT_SAND = g.create_pen(255, 120, 40)
    ANT_FOOD = g.create_pen(120, 255, 40)
    QUEEN = g.create_pen(255, 70, 170)
    QUEEN2 = g.create_pen(200, 40, 120)
    EGG = g.create_pen(240, 240, 220)
    CRUMB = g.create_pen(80, 220, 50)
    open_ = bytearray(N)
    dist_s = bytearray(N)
    dist_q = bytearray(N)
    queue = array("H", bytes(2 * N))       # cell indices go past 255 here
    prev_btn = [False, False]
    next_tick = 0.0
    new_farm(0.0)

def new_farm(t):
    global ants, eggs, food, pile, queen, next_food, dug, phase, phase_t
    for k in range(N):
        open_[k] = 1 if k // W < GROUND else 0
    # a starter shaft and a little chamber for the queen
    sx = random.randint(8, W - 9)
    depth = random.randint(GROUND + 2, H - 4)
    for y in range(GROUND, depth + 1):
        open_[y * W + sx] = 1
    for x in range(sx - 2, sx + 2):
        open_[(depth + 1) * W + x] = 1
        open_[(depth + 2) * W + x] = 1
    queen = (depth + 2) * W + sx - 1
    pile = bytearray(W)
    ants = []
    for _ in range(START_ANTS):
        ants.append([sx, WALK + random.randint(1, 2), WANDER, random.choice((-1, 1)), 0])
    eggs = []
    food = []
    next_food = t + 3
    dug = 0
    phase, phase_t = "run", t
    rebuild()

def passable(k):
    y = k // W
    return y == WALK or (y >= GROUND and open_[k])

def bfs(dist, starts):
    for k in range(N):
        dist[k] = 255
    head = tail = 0
    for k in starts:
        dist[k] = 0
        queue[tail] = k
        tail += 1
    while head < tail:
        k = queue[head]
        head += 1
        d = dist[k] + 1
        if d > 254:
            d = 254
        x = k % W
        for j in (k - W, k + W, k - 1 if x else -1, k + 1 if x < W - 1 else -1):
            if 0 <= j < N and dist[j] == 255 and passable(j):
                dist[j] = d
                queue[tail] = j
                tail += 1

def rebuild():
    bfs(dist_s, range(WALK * W, WALK * W + W))
    bfs(dist_q, (queen,))

def can_dig(x, y, wide):
    if x < 0 or x > W - 1 or y < GROUND or y > H - 1:
        return False
    k = y * W + x
    if open_[k]:
        return False
    n = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            xx, yy = x + dx, y + dy
            if (dx or dy) and 0 <= xx < W and GROUND <= yy < H and open_[yy * W + xx]:
                n += 1
    return n <= (5 if wide else 2)

def downhill(a, dist):
    """Move ant a one step along a distance map. True when it has arrived."""
    k = a[1] * W + a[0]
    best = dist[k]
    if best == 0:
        return True
    opts = []
    for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
        x, y = a[0] + dx, a[1] + dy
        if 0 <= x < W and 0 <= y < H and dist[y * W + x] < best:
            opts.append((x, y))
    if opts:
        a[0], a[1] = random.choice(opts)
    return dist[a[1] * W + a[0]] == 0

def lay_egg(t):
    qx, qy = queen % W, queen // W
    spots = []
    for dy in (-1, 0, 1):
        for dx in (-2, -1, 0, 1, 2):
            x, y = qx + dx, qy + dy
            k = y * W + x
            if 0 <= x < W and GROUND <= y < H and open_[k] and k != queen:
                taken = False
                for e in eggs:
                    if e[0] == k:
                        taken = True
                if not taken:
                    spots.append(k)
    if spots:
        eggs.append([random.choice(spots), t + HATCH_S])

def step_ant(a, t):
    global dug
    x, y, st = a[0], a[1], a[2]
    if st == CARRY or st == UP:
        if downhill(a, dist_s):
            if st == CARRY:
                a[2], a[4] = DROP, random.randint(1, 5)
                a[3] = random.choice((-1, 1))
            else:
                a[2] = WANDER
        return
    if st == DROP:
        if a[4] > 0:
            nx = x + a[3]
            if 0 <= nx < W:
                a[0] = nx
            else:
                a[3] = -a[3]
            a[4] -= 1
            return
        # drop the grain on the mound, rolling off if that spot is high
        px = a[0]
        for d in (0, -1, 1, -2, 2):
            if 0 <= px + d < W and pile[px + d] < 2:
                pile[px + d] += 1
                break
        a[2] = WANDER
        return
    if st == FOOD:
        if downhill(a, dist_q) or dist_q[a[1] * W + a[0]] <= 1:
            a[2] = WANDER
            lay_egg(t)
        return
    if st == FORAGE:
        if not food:
            a[2] = WANDER
            return
        # head for the nearest crumb
        fx = food[0]
        for f in food:
            if abs(f - x) < abs(fx - x):
                fx = f
        if x == fx and y == WALK:
            food.remove(fx)
            a[2] = FOOD
        elif y > WALK:
            downhill(a, dist_s)
        else:
            a[0] += 1 if fx > x else -1
        return
    # ---- wandering ----
    a[4] += 1
    if food and y == WALK and random.random() < 0.5:
        a[2] = FORAGE
        return
    if y == WALK:
        if random.random() < 0.15:
            a[3] = -a[3]
        below = (y + 1) * W + x
        if open_[below] and random.random() < 0.35:
            a[1] += 1
            return
        if random.random() < 0.006 and can_dig(x, y + 1, False):
            dig(a, x, y + 1)
            return
        nx = x + a[3]
        if 0 <= nx < W:
            a[0] = nx
        else:
            a[3] = -a[3]
        return
    if a[4] > 120:                          # nothing to do down here; head up
        a[2], a[4] = UP, 0
        return
    if random.random() < DIG_CHANCE:
        wide = a[4] < 0                     # negative timer = digging a chamber
        r = random.random()
        # the farm is shallow and long, so tunnels run sideways more than down
        if r < 0.4:
            tx, ty = x, y + 1
        elif r < 0.67:
            tx, ty = x - 1, y
        elif r < 0.94:
            tx, ty = x + 1, y
        else:
            tx, ty = x, y - 1
        if can_dig(tx, ty, wide):
            dig(a, tx, ty)
            return
    # walk along the tunnels, mostly keeping the same direction
    opts = []
    for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < W and WALK <= ny < H and passable(ny * W + nx):
            opts.append((nx, ny))
    if opts:
        ahead = (x + a[3], y)
        if ahead in opts and random.random() < 0.6:
            a[0], a[1] = ahead
        else:
            a[0], a[1] = random.choice(opts)
            if a[0] != x:
                a[3] = a[0] - x

def dig(a, x, y):
    global dug
    open_[y * W + x] = 1
    dug += 1
    a[0], a[1] = x, y
    a[2] = CARRY
    # now and then an ant decides to hollow out a chamber here
    a[4] = -4 if (y > GROUND + 2 and random.random() < 0.06) else (a[4] + 1 if a[4] < 0 else 0)
    rebuild()

def pressed(su, k, sw):
    now = su.is_pressed(sw)
    was = prev_btn[k]
    prev_btn[k] = now
    return now and not was

def frame(su, g, t):
    global next_tick, next_food, phase, phase_t
    if pressed(su, 0, GalacticUnicorn.SWITCH_A):
        for _ in range(3):
            if len(food) < 6:
                food.append(random.randrange(W))
    if pressed(su, 1, GalacticUnicorn.SWITCH_B):
        new_farm(t)

    if phase == "run" and t >= next_tick:
        next_tick = t + TICK
        if t >= next_food:
            if len(food) < 3:
                food.append(random.randrange(W))
            next_food = t + random.uniform(*FOOD_S)
        for a in ants:
            step_ant(a, t)
        for e in eggs:
            if t >= e[1]:
                eggs.remove(e)
                if len(ants) < MAX_ANTS:
                    ants.append([e[0] % W, e[0] // W, UP, random.choice((-1, 1)), 0])
                break
        if dug >= FULL:
            phase, phase_t = "full", t
    elif phase == "full" and t - phase_t > 6:
        new_farm(t)

    # ---- draw ----
    for y in range(GROUND):
        g.set_pen(SKY[y])
        g.rectangle(0, y, W, 1)
    k = GROUND * W
    for y in range(GROUND, H):
        for x in range(W):
            g.set_pen(TUNNEL if open_[k] else SAND[k])
            g.pixel(x, y)
            k += 1
    for x in range(W):                     # the mound of dug-out sand
        h = pile[x]
        for i in range(h):
            g.set_pen(PILE[i])
            g.pixel(x, WALK - i)
    g.set_pen(CRUMB)
    for fx in food:
        g.pixel(fx, WALK)
    g.set_pen(EGG)
    for e in eggs:
        g.pixel(e[0] % W, e[0] // W)
    g.set_pen(QUEEN if int(t * 2) % 2 else QUEEN2)
    g.pixel(queen % W, queen // W)
    for a in ants:
        st = a[2]
        g.set_pen(ANT_SAND if st == CARRY or st == DROP else ANT_FOOD if st == FOOD else ANT)
        g.pixel(a[0], a[1])
    return 0.04
