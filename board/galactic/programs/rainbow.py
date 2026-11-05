# Three light modes you can switch with the buttons
#   A = rainbow sweep   B = plasma   C = sparkles
# Galactic version: the sweep spans the strip, the plasma waves stretch along
# it, and there are more sparkles to fill the extra length.
import math, random
from array import array
from galactic import GalacticUnicorn

SPEED = 0.2   # 1.0 = full speed; lower = slower (try 0.1 for very calm)

HUES = 128
GLOWS = 32

def hsv(g, h, s=1.0, v=1.0):
    i = int(h * 6)
    f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, gg, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i % 6]
    return g.create_pen(int(r * 255), int(gg * 255), int(b * 255))

def setup(su, g):
    global W, H, mode, glow, RAINBOW, GOLD, RAD, CX, CY
    W, H = su.WIDTH, su.HEIGHT
    CX, CY = (W - 1) / 2, (H - 1) / 2
    mode = 0
    glow = array("H", [0] * (W * H))          # 0..65535 = dark..full
    RAINBOW = [hsv(g, i / HUES) for i in range(HUES)]
    GOLD = [hsv(g, 0.12, 0.6, i / (GLOWS - 1)) for i in range(GLOWS)]
    # oval distance from the middle, for the plasma's ring wave
    RAD = array("f", [math.sqrt(((x - CX) / 1.6) ** 2 + (y - CY) ** 2)
                      for y in range(H) for x in range(W)])

def frame(su, g, t_real):
    global mode
    if su.is_pressed(GalacticUnicorn.SWITCH_A): mode = 0
    if su.is_pressed(GalacticUnicorn.SWITCH_B): mode = 1
    if su.is_pressed(GalacticUnicorn.SWITCH_C): mode = 2

    t = t_real * SPEED

    if mode == 0:   # diagonal rainbow that drifts along the strip
        off = t * 0.2
        for y in range(H):
            for x in range(W):
                g.set_pen(RAINBOW[int(((x + y * 2) / 64 + off) * HUES) % HUES])
                g.pixel(x, y)

    elif mode == 1:   # plasma: a few overlapping sine waves
        i = 0
        for y in range(H):
            wy = math.sin(y / 2.5 - t * 1.3)
            for x in range(W):
                v = (math.sin(x / 4.8 + t)
                     + wy
                     + math.sin((x / 1.6 + y) / 4 + t * 0.7)
                     + math.sin(RAD[i] / 2 - t * 2))
                g.set_pen(RAINBOW[int((v / 8 + t * 0.05) * HUES) % HUES])
                g.pixel(x, y)
                i += 1

    else:   # sparkles: random pixels flash and fade out
        n = W * H
        if random.random() < 0.5 * SPEED * n / 256:      # same density as on the 16x16
            glow[random.randrange(n)] = 65535
        keep = int(65536 * (1 - 0.1 * SPEED))
        i = 0
        for y in range(H):
            for x in range(W):
                gl = glow[i]
                glow[i] = (gl * keep) >> 16
                g.set_pen(GOLD[(gl * GLOWS) >> 16])
                g.pixel(x, y)
                i += 1
    return 0.02
