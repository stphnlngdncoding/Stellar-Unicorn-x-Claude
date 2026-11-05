# Hyperspace: stars rush out from the centre and streak past at warp speed,
# with the whole field slowly spinning. Fast!
# Galactic version: the star field is stretched into a wide oval so streaks
# fly out along the whole strip, and the vanishing point drifts a little.
import math, random

STARS = 48
ACCEL = 1.11        # how quickly stars speed up as they fly outward
FRAME = 0.016
WIDE = 2.6          # how much faster stars travel sideways than up/down (oval field)

def new_star():
    a = random.uniform(0, 6.283)
    return [a, random.uniform(0.2, 1.5), random.randrange(len(PENS))]

def setup(su, g):
    global W, H, CX, CY, BLACK, PENS, CORE, FAR, stars, spin
    W, H = su.WIDTH, su.HEIGHT
    CX, CY = (W - 1) / 2, (H - 1) / 2
    BLACK = g.create_pen(0, 0, 0)
    CORE = g.create_pen(40, 50, 90)
    FAR = g.create_pen(70, 80, 120)        # distant stars near the vanishing point
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
    # the vanishing point sways gently along the strip
    cx = CX + 6 * math.sin(t * 0.21)
    cy = CY + 1.2 * math.sin(t * 0.33)
    g.set_pen(CORE)
    g.pixel(int(cx + 0.5), int(cy + 0.5))
    wx = WIDE
    for s in stars:
        a = s[0] + spin
        d0 = s[1]
        s[1] = d0 * ACCEL + 0.12
        d1 = s[1]
        ca, sa = math.cos(a) * wx, math.sin(a)
        x0, y0 = int(cx + ca * d0), int(cy + sa * d0)
        x1, y1 = int(cx + ca * d1), int(cy + sa * d1)
        if d0 < 2.2:                       # still far away: a faint dot
            g.set_pen(FAR)
            g.pixel(x1, y1)
        else:
            g.set_pen(PENS[s[2]])
            g.line(x0, y0, x1, y1)
        if (x0 < -2 or x0 > W + 1 or y0 < -2 or y0 > H + 1) or d0 > 60:
            s[0], s[1], s[2] = new_star()
    return FRAME
