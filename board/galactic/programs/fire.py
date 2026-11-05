# Fire: a classic rising-flame effect. Hot spots spawn along the bottom edge,
# each cell averages the heat below it and cools a little, and the heat is
# drawn in five fiery colours (white, yellow, orange, red, smoke).
# Galactic Unicorn version: a long row of flames along the 53 px strip.
#   fire_spawns    = hot spots added each frame (more = a fuller fire)
#   damping_factor = how slowly heat cools as it rises (higher = taller flames)
import random
from array import array

fire_spawns = 14
damping_factor = 0.94


def setup(su, g):
    global W, H, width, height, heat, palette
    W, H = su.WIDTH, su.HEIGHT
    # heat buffer is a little bigger than the screen: one spare column each
    # side and spare rows below where the fire is spawned
    width = W + 2
    height = H + 4
    heat = array("f", [0.0] * (width * height))     # heat[x * height + y]
    # a palette of five fiery colours (white, yellow, orange, red, smoke)
    palette = [
        g.create_pen(0, 0, 0),
        g.create_pen(20, 20, 20),
        g.create_pen(180, 30, 0),
        g.create_pen(220, 160, 0),
        g.create_pen(255, 255, 180)
    ]


# returns the palette entry for a given heat value
def pen_from_value(value):
    if value < 0.15:
        return palette[0]
    elif value < 0.25:
        return palette[1]
    elif value < 0.35:
        return palette[2]
    elif value < 0.45:
        return palette[3]
    return palette[4]


def frame(su, g, t):
    hb = heat
    ht = height
    # clear the rows off the bottom of the display
    for x in range(width):
        hb[x * ht + ht - 1] = 0.0
        hb[x * ht + ht - 2] = 0.0

    # add new fire spawns
    for c in range(fire_spawns):
        x = random.randint(0, width - 4) + 2
        for i in (x - 1, x, x + 1):
            hb[i * ht + ht - 1] = 1.0
            hb[i * ht + ht - 2] = 1.0

    # average and damp out each value to create rising flame effect
    damp = damping_factor / 5.0
    # (rows top to bottom, so every cell reads last frame's values below it)
    for y in range(0, ht - 2):
        for b in range(ht + y, (width - 1) * ht, ht):
            hb[b] = (hb[b] + hb[b + 1] + hb[b + 2] + hb[b - ht + 1] + hb[b + ht + 1]) * damp

    # render the heat values to the graphics buffer
    for x in range(W):
        b = (x + 1) * ht
        for y in range(H):
            g.set_pen(pen_from_value(hb[b + y]))
            g.pixel(x, y)
    return 0.03
