# Garden: a tiny garden that grows itself. Sprouts push up out of the soil,
# grow leaves and open a flower, then drop seeds that drift off and sprout
# new plants nearby. Every plant has its own colour. Plants stand in three
# rows (back ones smaller and dimmer, front ones bigger and brighter) and
# overlap, so the garden has depth. Old plants wilt and make room.
#   A = scatter some seeds
#
# Memory-friendly: each plant's shape is built once when it sprouts; the
# frame loop just draws the part that has grown so far.
import math, random
from stellar import StellarUnicorn

MAX_PLANTS = 10      # how crowded the garden gets
GROW = (14, 30)      # seconds for a sprout to reach full size
BLOOM = (40, 90)     # seconds a grown plant lives before it wilts
WILT = 6             # seconds to wilt away
SEED_EVERY = (8, 20) # seconds between seeds from a blooming plant
FRAME = 0.05

ROWS = ((13, 45, 6), (14, 72, 9), (15, 100, 12))   # (base y, brightness %, max height) back -> front
GOLDEN = 0.618

def hsv(h, s, v):
    h %= 1.0
    i = int(h * 6); f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i % 6]
    return (int(r * 255), int(g * 255), int(b * 255))

def scale(c, pct):
    return (c[0] * pct // 100, c[1] * pct // 100, c[2] * pct // 100)

def shape(height):
    """Pixels of a plant in growth order: (dx, dy, part) with part 0 stem, 1 leaf, 2 flower."""
    px, x = [], 0
    side = random.choice((-1, 1))
    for y in range(height):
        if y > 1 and random.getrandbits(2) == 0:
            x += random.choice((-1, 1))          # the stem wanders a little
        px.append((x, -y, 0))
        if y >= 1 and y < height - 1 and (y + height) % 2 == 0:
            px.append((x + side, -y, 1))         # leaves on alternating sides
            if height > 6 and random.getrandbits(1):
                px.append((x + 2 * side, -y - 1, 1))
            side = -side
    top = -height
    kind = random.getrandbits(2)
    if kind == 0:                                # a single bud
        flower = [(x, top)]
    elif kind == 1:                              # a little cross
        flower = [(x, top), (x - 1, top), (x + 1, top), (x, top - 1)]
    elif kind == 2:                              # a tulip cup
        flower = [(x - 1, top), (x, top), (x + 1, top), (x - 1, top - 1), (x + 1, top - 1)]
    else:                                        # a tuft
        flower = [(x, top), (x - 1, top - 1), (x + 1, top - 1)]
    for fx, fy in flower:
        px.append((fx, fy, 2))
    return px, x, top

def new_plant(g, x, row, hue, born):
    by, bright, hmax = ROWS[row]
    height = random.randint(max(3, hmax - 4), hmax)
    px, tipx, tipy = shape(height)
    pens = (g.create_pen(*scale(hsv(hue, 0.85, 0.5), bright)),
            g.create_pen(*scale(hsv(hue, 0.8, 0.9), bright)),
            g.create_pen(*scale(hsv(hue + 0.06, 0.35, 1.0), bright)))
    grow = random.uniform(*GROW)
    return {"x": x, "row": row, "hue": hue, "born": born, "grow": grow,
            "die": born + grow + random.uniform(*BLOOM), "px": px, "tip": (tipx, tipy),
            "pens": pens, "seed_at": born + grow + random.uniform(*SEED_EVERY),
            "sway": random.uniform(0, 6.3)}

def setup(su, g):
    global plants, seeds, SOIL, BLACK, SEED, next_hue, a_was
    BLACK = g.create_pen(0, 0, 0)
    SOIL = (g.create_pen(40, 22, 10), g.create_pen(26, 14, 6))
    SEED = g.create_pen(255, 245, 210)
    next_hue = random.random()
    plants, seeds = [], []
    for i in range(4):                           # a few sprouts to start with, spread out
        sow(g, 2 + i * 3.6 + random.uniform(-0.8, 0.8), (i * 2 + 1) % 3, i * 2.5)
    a_was = False

def sow(g, x, row, now):
    global next_hue
    next_hue = (next_hue + GOLDEN) % 1.0         # each new plant gets a clearly different colour
    plants.append(new_plant(g, int(x), row, next_hue, now))
    plants.sort(key=lambda p: p["row"])          # draw back rows first

def frame(su, g, t):
    global a_was
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was:
        for _ in range(3):
            seeds.append([random.uniform(1, 14), 0.0, random.uniform(-1, 1), random.randrange(3)])
    a_was = a

    # ---- life cycle ----
    i = 0
    while i < len(plants):
        p = plants[i]
        if t > p["die"] + WILT:
            plants.pop(i)
            continue
        if t >= p["seed_at"] and t < p["die"]:
            p["seed_at"] = t + random.uniform(*SEED_EVERY)
            if len(plants) + len(seeds) < MAX_PLANTS:
                tx, ty = p["tip"]
                seeds.append([p["x"] + tx, ROWS[p["row"]][0] + ty, random.uniform(-2.5, 2.5), random.randrange(3)])
        i += 1
    if not plants and not seeds:                 # never leave the garden empty
        sow(g, random.uniform(2, 13), random.randrange(3), t)

    # ---- draw ----
    g.set_pen(BLACK)
    g.clear()
    g.set_pen(SOIL[0])
    for x in range(16):
        g.pixel(x, 14)
    g.set_pen(SOIL[1])
    for x in range(16):
        g.pixel(x, 15)
    for p in plants:
        age = t - p["born"]
        if age < 0:
            continue
        by = ROWS[p["row"]][0]
        n = len(p["px"])
        shown = n if age >= p["grow"] else int(n * age / p["grow"]) + 1
        if t > p["die"]:
            wilt = (t - p["die"]) / WILT        # 0..1
            shown = int(n * (1 - wilt))
            pen = g.create_pen(*scale(hsv(p["hue"] * (1 - wilt) + 0.08 * wilt, 0.7, 0.6 - 0.4 * wilt),
                                      ROWS[p["row"]][1]))
            pens = (pen, pen, pen)                # fades to one brown as it wilts
        else:
            pens = p["pens"]
        sway = math.sin(t * 0.9 + p["sway"])
        for k in range(shown):
            dx, dy, part = p["px"][k]
            lean = int(sway * (-dy) / 10)        # the top sways more than the base
            x, y = p["x"] + dx + lean, by + dy
            if 0 <= x < 16 and 0 <= y < 16:
                g.set_pen(pens[part])
                g.pixel(x, y)

    # ---- seeds drift down and sprout where they land ----
    i = 0
    while i < len(seeds):
        s = seeds[i]
        s[1] += 2.2 * FRAME
        s[0] += (s[2] + math.sin(t * 3 + i) * 1.5) * FRAME
        s[0] = min(14.5, max(0.5, s[0]))
        land = ROWS[s[3]][0]
        if s[1] >= land:
            seeds.pop(i)
            if len(plants) < MAX_PLANTS:
                sow(g, s[0], s[3], t)
            continue
        if s[1] >= 0:
            g.set_pen(SEED)
            g.pixel(int(s[0]), int(s[1]))
        i += 1
    return FRAME
