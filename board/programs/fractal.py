# Evolving Julia set in muted colours. The fractal's shape morphs as its
# parameter slowly travels around the edge of the Mandelbrot set, the view
# turns gently, and the colours drift through slate, sage, sand and clay.
import math

MAX_ITER = 24
MORPH_SPEED = 0.045   # how fast the shape evolves
SPIN_SPEED = 0.03     # how fast the view rotates
ZOOM = 1.2            # half-width of the view in fractal units

# muted palette stops (r, g, b), looped
STOPS = [(28, 34, 48), (58, 78, 100), (88, 112, 98), (150, 138, 104),
         (132, 88, 90), (78, 64, 92), (28, 34, 48)]
INSIDE = (8, 10, 16)

def lerp(a, b, f):
    return int(a + (b - a) * f)

def setup(su, g):
    global W, H, PAL, NPAL, IN_PEN, coords
    W, H = su.WIDTH, su.HEIGHT
    NPAL = 64
    PAL = []
    segs = len(STOPS) - 1
    for i in range(NPAL):
        f = i / NPAL * segs
        k = int(f)
        r = f - k
        a, b = STOPS[k], STOPS[k + 1]
        PAL.append(g.create_pen(lerp(a[0], b[0], r), lerp(a[1], b[1], r), lerp(a[2], b[2], r)))
    IN_PEN = g.create_pen(*INSIDE)
    # pixel centres in -1..1
    coords = [((x + 0.5) / W * 2 - 1, (y + 0.5) / H * 2 - 1) for y in range(H) for x in range(W)]

def frame(su, g, t):
    a = t * MORPH_SPEED
    # c wanders near the Mandelbrot boundary, where Julia sets are most intricate
    rad = 0.7885 + 0.03 * math.sin(a * 2.3)
    cr, ci = rad * math.cos(a), rad * math.sin(a)
    s, c = math.sin(t * SPIN_SPEED) * ZOOM, math.cos(t * SPIN_SPEED) * ZOOM
    drift = t * 0.6
    i = 0
    for y in range(H):
        for x in range(W):
            px, py = coords[i]
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
                g.set_pen(PAL[int(nu * 5 + drift) % NPAL])
            g.pixel(x, y)
    return 0.0
