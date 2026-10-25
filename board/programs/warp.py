# Hyperspace: stars rush out from the centre and streak past at warp speed,
# with the whole field slowly spinning. Fast!
import math, random

STARS = 28
ACCEL = 1.13        # how quickly stars speed up as they fly outward
FRAME = 0.016

def new_star():
    a = random.uniform(0, 6.283)
    return [a, random.uniform(0.2, 1.5), random.randrange(len(PENS))]

def setup(su, g):
    global W, H, CX, CY, BLACK, PENS, stars, spin
    W, H = su.WIDTH, su.HEIGHT
    CX, CY = (W - 1) / 2, (H - 1) / 2
    BLACK = g.create_pen(0, 0, 0)
    # mostly blue-white, a few cyan and magenta streaks
    PENS = [g.create_pen(200, 220, 255), g.create_pen(255, 255, 255),
            g.create_pen(140, 180, 255), g.create_pen(80, 230, 255),
            g.create_pen(255, 90, 220), g.create_pen(170, 200, 255)]
    stars = [new_star() for _ in range(STARS)]
    for s in stars:
        s[1] = random.uniform(0.2, 10)     # spread them out at the start
    spin = 0.0

def frame(su, g, t):
    global spin
    spin += 0.012
    g.set_pen(BLACK)
    g.clear()
    for s in stars:
        a = s[0] + spin
        d0 = s[1]
        s[1] = d0 * ACCEL + 0.15
        d1 = s[1]
        ca, sa = math.cos(a), math.sin(a)
        x0, y0 = int(CX + ca * d0), int(CY + sa * d0)
        x1, y1 = int(CX + ca * d1), int(CY + sa * d1)
        g.set_pen(PENS[s[2]])
        g.line(x0, y0, x1, y1)
        if d0 > 13:
            s[0], s[1], s[2] = new_star()
    return FRAME
