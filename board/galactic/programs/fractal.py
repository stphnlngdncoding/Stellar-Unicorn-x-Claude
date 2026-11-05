# Evolving Julia set with strong contrast. The fractal's shape morphs as its
# parameter slowly travels around the edge of the Mandelbrot set, and the view
# turns gently. Space far from the set is near-black, the filaments near its
# edge glow bright, and the inside is pure black. The colours drift through
# steel blue, sage, sand, clay and plum.
# Galactic version: the strip is a wide, undistorted window that turns to
# follow the fractal's long axis (which rotates as the shape morphs), so the
# set always lies along the strip; the view sways gently either side of it.
import math
from array import array

MAX_ITER = 24
MORPH_SPEED = 0.045   # how fast the shape evolves
SPIN_SPEED = 0.03     # how fast the view sways either side of the fractal's long axis
ZOOM = 1.6            # half-width of the view in fractal units (along the strip)

# colour stops at full brightness (r, g, b), looped; brightness comes from
# how close each point is to the set
STOPS = [(90, 140, 230), (110, 210, 170), (240, 200, 110), (235, 110, 90),
         (180, 100, 220), (90, 140, 230)]
INSIDE = (0, 0, 0)
LEVELS = 8           # brightness steps
CONTRAST = 1.6       # bigger = darker background, brighter edges

def lerp(a, b, f):
    return int(a + (b - a) * f)

def setup(su, g):
    global W, H, PAL, NPAL, IN_PEN, CX, CY
    W, H = su.WIDTH, su.HEIGHT
    NPAL = 32
    PAL = []                                    # NPAL hues x LEVELS brightness
    segs = len(STOPS) - 1
    for i in range(NPAL):
        f = i / NPAL * segs
        k = int(f)
        r = f - k
        a, b = STOPS[k], STOPS[k + 1]
        col = (lerp(a[0], b[0], r), lerp(a[1], b[1], r), lerp(a[2], b[2], r))
        for lv in range(LEVELS):
            v = ((lv + 1) / LEVELS) ** CONTRAST
            w = max(0.0, (lv - LEVELS + 2.5) / 2.5) * 0.45      # brightest steps go towards white
            PAL.append(g.create_pen(*[min(255, int(c * v + (255 - c) * w)) for c in col]))
    IN_PEN = g.create_pen(*INSIDE)
    # pixel centres: -1..1 along the strip, same scale up and down (square pixels)
    # (two float arrays rather than a list of tuples: much less RAM on the Pico)
    CX = array("f", [(x + 0.5) / W * 2 - 1 for y in range(H) for x in range(W)])
    CY = array("f", [((y + 0.5) / H * 2 - 1) * H / W for y in range(H) for x in range(W)])

def frame(su, g, t):
    a = t * MORPH_SPEED
    # c wanders near the Mandelbrot boundary, where Julia sets are most intricate
    rad = 0.7885 + 0.03 * math.sin(a * 2.3)
    cr, ci = rad * math.cos(a), rad * math.sin(a)
    # the set's long axis lies at about a/2 + 90 degrees; follow it, swaying
    th = a * 0.5 + 1.5708 + 0.45 * math.sin(t * SPIN_SPEED * 3)
    s, c = math.sin(th) * ZOOM, math.cos(th) * ZOOM
    drift = t * 0.6
    i = 0
    for y in range(H):
        for x in range(W):
            px, py = CX[i], CY[i]
            i += 1
            zr = px * c - py * s
            zi = px * s + py * c
            n = 0
            while n < MAX_ITER:
                zr2, zi2 = zr * zr, zi * zi
                if zr2 + zi2 > 16.0:
                    break
                zi = 2 * zr * zi + ci
                zr = zr2 - zi2 + cr
                n += 1
            if n >= MAX_ITER:
                g.set_pen(IN_PEN)
            else:
                # smooth colouring so bands blend instead of stepping
                m = zr * zr + zi * zi
                nu = n + 1 - math.log(math.log(m) * 0.5) / 0.6931
                lv = int(nu * LEVELS / (MAX_ITER * 0.55))
                lv = 0 if lv < 0 else LEVELS - 1 if lv >= LEVELS else lv
                g.set_pen(PAL[(int(nu * 2.5 + drift) % NPAL) * LEVELS + lv])
            g.pixel(x, y)
    return 0.0
