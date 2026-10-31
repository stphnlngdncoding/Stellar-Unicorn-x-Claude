# Hedge Maze: a glowing firefly roams a hedge maze collecting dew drops while
# three spiders hunt it. It plays itself: the firefly heads for the nearest
# drop by a route that keeps its distance from the spiders, and grabs a pink
# berry for a burst of speed when one appears. Clear every drop and a new
# maze grows (with quicker spiders); get caught three times and it starts
# over. The bottom row shows the drops left and the lives.
#   A = new maze   B = speed up / slow down
#
# Memory-friendly: the maze, the drops and the route maps are bytearrays made
# once in setup(); routes are worked out with a small breadth-first search.
import random
from stellar import StellarUnicorn

PLAYER_SPEED = 5.5   # firefly moves per second
SPIDER_SPEED = 3.0   # spider moves per second on the first maze
SPEED_UP = 0.25      # spiders get this much quicker each maze cleared
SPIDERS = 3
CHASE = 0.6          # how often a spider takes the shortest way to the firefly
LOOPS = 0.5          # how many extra gaps are cut so the maze has loops
SAFE = 2             # extra squares of margin the firefly keeps over the spiders
BERRY_S = (12, 25)   # seconds between berries
BOOST_S = 4.0        # how long a berry's speed boost lasts
FRAME = 0.03

H = 15               # maze rows 0..14; row 15 is the status bar; column 15 is hedge

def setup(su, g):
    global WALL, WALL2, DROP, FLY, HALO, BERRY, SPIDERPEN, LIFE, BAR, BLACK, FLASH
    global wall, drop, dist_p, dist_s, dist_c, exits, queue, a_was, b_was, fast
    BLACK = g.create_pen(0, 0, 0)
    WALL = g.create_pen(22, 95, 38)
    WALL2 = g.create_pen(14, 70, 28)
    DROP = g.create_pen(22, 40, 70)
    FLY = (g.create_pen(210, 255, 90), g.create_pen(255, 255, 200))
    HALO = g.create_pen(40, 60, 15)
    BERRY = g.create_pen(255, 70, 160)
    SPIDERPEN = (g.create_pen(170, 60, 230), g.create_pen(190, 125, 40), g.create_pen(185, 185, 200))
    LIFE = g.create_pen(210, 255, 90)
    BAR = g.create_pen(40, 80, 130)
    FLASH = g.create_pen(255, 255, 255)
    wall = bytearray(256)
    drop = bytearray(256)
    dist_p = bytearray(256)
    dist_s = bytearray(256)
    dist_c = bytearray(256)       # steps to the firefly, for the spiders
    exits = bytearray(256)        # open neighbours of each square (1 = dead end)
    queue = bytearray(256)
    a_was = b_was = False
    fast = False
    new_game(0.0)

# ---------------------------------------------------------------- the maze
def grow_maze():
    """A random maze on the even squares, with some extra gaps cut for loops."""
    for i in range(256):
        wall[i] = 1
    stack = [(0, 0)]
    wall[0] = 0
    while stack:
        x, y = stack[-1]
        opts = []
        for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < 15 and 0 <= ny < H and wall[ny * 16 + nx]:
                opts.append((nx, ny, dx, dy))
        if not opts:
            stack.pop()
            continue
        nx, ny, dx, dy = random.choice(opts)
        wall[(y + dy // 2) * 16 + x + dx // 2] = 0
        wall[ny * 16 + nx] = 0
        stack.append((nx, ny))
    # cut extra gaps so there are loops to escape around
    for y in range(H):
        for x in range(15):
            if wall[y * 16 + x] and (x + y) % 2 == 1 and random.random() < LOOPS:
                if x % 2 == 1 and 0 < x < 14:
                    wall[y * 16 + x] = 0
                elif y % 2 == 1 and 0 < y < H - 1:
                    wall[y * 16 + x] = 0

def new_maze(t):
    global px, py, spiders, berry, next_berry, boost_until, total, start_total, state, state_t, aim
    grow_maze()
    total = 0
    for i in range(256):
        drop[i] = 0
        if (i & 15) < 15 and (i >> 4) < H and not wall[i]:
            drop[i] = 1
            total += 1
    # the firefly starts in a corner, the spiders in the far ones
    corners = [(0, 0), (14, 0), (0, 14), (14, 14)]
    for i in range(3, 0, -1):                     # shuffle (MicroPython has no random.shuffle)
        j = random.randrange(i + 1)
        corners[i], corners[j] = corners[j], corners[i]
    px, py = corners[0]
    drop[py * 16 + px] = 0
    total -= 1
    start_total = total
    for i in range(256):
        x, y = i & 15, i >> 4
        exits[i] = (open_cell(x + 1, y) + open_cell(x - 1, y) + open_cell(x, y + 1) + open_cell(x, y - 1)) if open_cell(x, y) else 0
    bfs(dist_c, px, py)
    spiders = []
    for k in range(SPIDERS):
        sx, sy = corners[1 + k % 3]
        spiders.append([sx, sy, 0.0, -1])          # x, y, move timer, last cell
    berry = -1
    aim = -1
    next_berry = t + random.uniform(*BERRY_S)
    boost_until = 0.0
    state, state_t = "ready", t

def new_game(t):
    global lives, level, next_move, last_t
    lives = 3
    level = 0
    next_move = 0.0
    last_t = t
    new_maze(t)

# ---------------------------------------------------------------- routes
def open_cell(x, y):
    return 0 <= x < 15 and 0 <= y < H and not wall[y * 16 + x]

def bfs(dist, sx, sy):
    for i in range(256):
        dist[i] = 255
    dist[sy * 16 + sx] = 0
    queue[0] = sy * 16 + sx
    head, tail = 0, 1
    while head < tail:
        c = queue[head]
        head += 1
        d = dist[c] + 1
        x, y = c & 15, c >> 4
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if open_cell(nx, ny):
                n = ny * 16 + nx
                if dist[n] == 255:
                    dist[n] = d
                    queue[tail] = n
                    tail += 1

def danger_map():
    """dist_s = steps from the nearest spider to every square."""
    for i in range(256):
        dist_s[i] = 255
    head, tail = 0, 0
    for s in spiders:
        c = s[1] * 16 + s[0]
        if dist_s[c]:
            dist_s[c] = 0
            queue[tail] = c
            tail += 1
    while head < tail:
        c = queue[head]
        head += 1
        d = dist_s[c] + 1
        x, y = c & 15, c >> 4
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if open_cell(nx, ny):
                n = ny * 16 + nx
                if dist_s[n] > d:
                    dist_s[n] = d
                    queue[tail] = n
                    tail += 1

def player_step(ratio):
    """Pick the firefly's next square: the nearest drop (or berry) by a safe route."""
    global RATIO, aim
    RATIO = int(ratio * 16)          # spider speed / firefly speed, in sixteenths
    danger_map()
    here = dist_s[py * 16 + px]
    # search outwards from the firefly, only through squares that are safe enough
    for i in range(256):
        dist_p[i] = 255
    start = py * 16 + px
    dist_p[start] = 0
    queue[0] = start
    head, tail = 0, 1
    goal = -1
    while head < tail:
        c = queue[head]
        head += 1
        if goal < 0 and c != start and (drop[c] or c == berry):
            goal = c
        x, y = c & 15, c >> 4
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if open_cell(nx, ny):
                n = ny * 16 + nx
                # only squares the firefly can reach well before any spider,
                # and no dead ends unless the spiders are far away
                d = dist_p[c] + 1
                if dist_p[n] == 255 and dist_s[n] * 16 >= d * RATIO + SAFE * 16 \
                        and (exits[n] > 1 or dist_s[n] > 7):
                    dist_p[n] = d
                    queue[tail] = n
                    tail += 1
    # stick with the drop it was already heading for while that's still safe,
    # so it doesn't dither between two targets
    if aim >= 0 and aim != start and dist_p[aim] != 255 and (drop[aim] or aim == berry):
        goal = aim
    aim = goal
    if goal >= 0:
        # walk back from the goal to find the first step
        c = goal
        while dist_p[c] > 1:
            x, y = c & 15, c >> 4
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if open_cell(nx, ny) and dist_p[ny * 16 + nx] == dist_p[c] - 1:
                    c = ny * 16 + nx
                    break
        return c & 15, c >> 4
    # nothing safe to go for: run to the reachable square furthest from the spiders
    for i in range(256):
        dist_p[i] = 255
    dist_p[start] = 0
    queue[0] = start
    head, tail = 0, 1
    best, score = start, -1
    while head < tail:
        c = queue[head]
        head += 1
        sc = dist_s[c] * 4 + (exits[c] > 2) * 3 - dist_p[c]
        if c != start and sc > score:
            best, score = c, sc
        x, y = c & 15, c >> 4
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if open_cell(nx, ny):
                n = ny * 16 + nx
                d = dist_p[c] + 1
                if dist_p[n] == 255 and dist_s[n] * 16 > d * RATIO:
                    dist_p[n] = d
                    queue[tail] = n
                    tail += 1
    if best == start:
        return px, py
    c = best
    while dist_p[c] > 1:
        x, y = c & 15, c >> 4
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if open_cell(nx, ny) and dist_p[ny * 16 + nx] == dist_p[c] - 1:
                c = ny * 16 + nx
                break
    return c & 15, c >> 4

def spider_step(s):
    x, y = s[0], s[1]
    opts = []
    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
        if open_cell(nx, ny) and ny * 16 + nx != s[3]:
            opts.append((nx, ny))
    if not opts:                                   # dead end: turn round
        c = s[3]
        opts = [(c & 15, c >> 4)]
    if random.random() < CHASE:
        nx, ny = opts[0]
        for ox, oy in opts:
            if dist_c[oy * 16 + ox] < dist_c[ny * 16 + nx]:
                nx, ny = ox, oy
    else:
        nx, ny = random.choice(opts)
    s[3] = y * 16 + x
    s[0], s[1] = nx, ny

def caught():
    for s in spiders:
        if s[0] == px and s[1] == py:
            return True
    return False

# ---------------------------------------------------------------- frame
def frame(su, g, t):
    global px, py, state, state_t, next_move, lives, level, last_t, total, berry, next_berry
    global boost_until, a_was, b_was, fast
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    b = su.is_pressed(StellarUnicorn.SWITCH_B)
    if a and not a_was:
        new_maze(t)
    if b and not b_was:
        fast = not fast
    a_was, b_was = a, b
    dt = t - last_t
    if dt > 0.1:
        dt = 0.1
    last_t = t
    pace = 1.8 if fast else 1.0

    if state == "ready" and t - state_t > 1.2:
        state = "play"
        next_move = t
    elif state == "play":
        # berries come and go
        if berry < 0 and t >= next_berry:
            cells = [i for i in range(256) if (i & 15) < 15 and (i >> 4) < H and not wall[i] and not drop[i]
                     and i != py * 16 + px]
            if cells:
                berry = random.choice(cells)
            next_berry = t + random.uniform(*BERRY_S)
        # the firefly
        speed = PLAYER_SPEED * pace * (1.6 if t < boost_until else 1.0)
        if t >= next_move:
            next_move = t + 1.0 / speed
            px, py = player_step((SPIDER_SPEED + SPEED_UP * level) / (speed / pace))
            bfs(dist_c, px, py)
            c = py * 16 + px
            if drop[c]:
                drop[c] = 0
                total -= 1
            if c == berry:
                berry = -1
                boost_until = t + BOOST_S
        # the spiders
        sp = (SPIDER_SPEED + SPEED_UP * level) * pace
        for s in spiders:
            s[2] += dt * sp
            if s[2] >= 1:
                s[2] -= 1
                spider_step(s)
        if caught():
            lives -= 1
            state, state_t = "caught", t
        elif total <= 0:
            level += 1
            state, state_t = "clear", t
    elif state == "caught" and t - state_t > 1.6:
        if lives <= 0:
            new_game(t)
        else:
            # back to a corner, the maze and drops stay as they are
            corners = [(0, 0), (14, 0), (0, 14), (14, 14)]
            corners.sort(key=lambda p: -min(abs(p[0] - s[0]) + abs(p[1] - s[1]) for s in spiders))
            px, py = corners[0]
            bfs(dist_c, px, py)
            state, state_t = "ready", t
    elif state == "clear" and t - state_t > 1.8:
        new_maze(t)

    # ---- draw ----
    g.set_pen(BLACK)
    g.clear()
    flash_walls = state == "clear" and int((t - state_t) * 8) % 2 == 0
    for i in range(256):
        x, y = i & 15, i >> 4
        if y >= H:
            continue
        if x == 15 or wall[i]:
            g.set_pen(FLASH if flash_walls else (WALL if (x + y) % 3 else WALL2))
            g.pixel(x, y)
        elif drop[i]:
            g.set_pen(DROP)
            g.pixel(x, y)
    if berry >= 0 and int(t * 4) % 4:
        g.set_pen(BERRY)
        g.pixel(berry & 15, berry >> 4)
    # soft glow round the firefly on the open squares next to it
    g.set_pen(HALO)
    for nx, ny in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
        if open_cell(nx, ny) and not drop[ny * 16 + nx]:
            g.pixel(nx, ny)
    for k in range(len(spiders)):
        s = spiders[k]
        g.set_pen(SPIDERPEN[k % 3])
        g.pixel(s[0], s[1])
    if state == "caught":
        g.set_pen(FLASH if int((t - state_t) * 10) % 2 else FLY[0])
    else:
        g.set_pen(FLY[1] if t < boost_until and int(t * 12) % 2 else FLY[0])
    g.pixel(px, py)
    # status bar: drops left on the left, lives on the right
    left = (total * 11 + start_total - 1) // max(1, start_total)
    g.set_pen(BAR)
    for x in range(left):
        g.pixel(x, 15)
    g.set_pen(LIFE)
    for k in range(lives):
        g.pixel(15 - k * 2, 15)
    return FRAME

