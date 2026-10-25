# Three light modes you can switch with the buttons
#   A = rainbow sweep   B = plasma   C = sparkles
import math, random
from stellar import StellarUnicorn

SPEED = 0.2   # 1.0 = full speed; lower = slower (try 0.1 for very calm)

def hsv(g, h, s=1.0, v=1.0):
    i = int(h * 6)
    f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, gg, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i % 6]
    return g.create_pen(int(r * 255), int(gg * 255), int(b * 255))

def setup(su, g):
    global W, H, mode, glow
    W, H = su.WIDTH, su.HEIGHT
    mode = 0
    glow = [[0.0] * W for _ in range(H)]

def frame(su, g, t_real):
    global mode
    if su.is_pressed(StellarUnicorn.SWITCH_A): mode = 0
    if su.is_pressed(StellarUnicorn.SWITCH_B): mode = 1
    if su.is_pressed(StellarUnicorn.SWITCH_C): mode = 2

    t = t_real * SPEED

    if mode == 0:   # diagonal rainbow that drifts
        for y in range(H):
            for x in range(W):
                g.set_pen(hsv(g, ((x + y) / 32 + t * 0.2) % 1))
                g.pixel(x, y)

    elif mode == 1:   # plasma: a few overlapping sine waves
        for y in range(H):
            for x in range(W):
                v = (math.sin(x / 3 + t)
                     + math.sin(y / 2.5 - t * 1.3)
                     + math.sin((x + y) / 4 + t * 0.7)
                     + math.sin(math.sqrt((x - 7.5) ** 2 + (y - 7.5) ** 2) / 2 - t * 2))
                g.set_pen(hsv(g, (v / 8 + t * 0.05) % 1))
                g.pixel(x, y)

    else:   # sparkles: random pixels flash and fade out
        if random.random() < 0.5 * SPEED:
            glow[random.randrange(H)][random.randrange(W)] = 1.0
        for y in range(H):
            for x in range(W):
                gl = glow[y][x]
                glow[y][x] = gl * (1 - 0.1 * SPEED)
                g.set_pen(hsv(g, 0.12, 0.6, gl))
                g.pixel(x, y)
    return 0.02
