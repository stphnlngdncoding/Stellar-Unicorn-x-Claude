# Supercomputer: every LED blinks on its own slightly different cycle, like
# the banks of status lights on a movie mainframe. Each light snaps on, holds,
# fades out and rests before its next blink.
# Galactic Unicorn version: the whole 53 x 11 strip is one long console.
#   colour = the (r, g, b) colour of the lights
import random
from array import array

colour = (230, 150, 0)

LEVELS = 16                 # fade steps between full and off


def setup(su, g):
    global W, H, lifetime, age, PENS, BLACK
    W, H = su.WIDTH, su.HEIGHT
    n = W * H
    lifetime = array("f", [0.0] * n)
    age = array("f", [0.0] * n)
    for i in range(n):
        lifetime[i] = 1.0 + random.uniform(0.0, 0.1)
        age[i] = random.uniform(0.0, 1.0) * lifetime[i]
    # PENS[k] = colour at brightness k / LEVELS (made once, not per pixel per frame)
    PENS = [g.create_pen(int(colour[0] * k / LEVELS), int(colour[1] * k / LEVELS),
                         int(colour[2] * k / LEVELS)) for k in range(LEVELS + 1)]
    BLACK = PENS[0]


def frame(su, g, t):
    i = 0
    for y in range(H):
        for x in range(W):
            a = age[i]
            life = lifetime[i]
            if a >= life:
                a = 0.0
                life = 1.0 + random.uniform(0.0, 0.1)
                lifetime[i] = life
            a += 0.025
            age[i] = a
            if a < life * 0.3:
                g.set_pen(PENS[LEVELS])
            elif a < life * 0.5:
                decay = (life * 0.5 - a) * 5.0          # 1 -> 0 as the light fades
                k = int(decay * LEVELS)
                g.set_pen(PENS[k if k < LEVELS else LEVELS] if k > 0 else BLACK)
            else:
                g.set_pen(BLACK)
            g.pixel(x, y)
            i += 1
    return 0.03
