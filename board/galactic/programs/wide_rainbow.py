# Wide rainbow: a test program for the Galactic Unicorn (53x11).
def setup(su, g):
    global P
    P = []
    for i in range(53):
        h = i / 53
        k = int(h * 6); f = h * 6 - k
        r, gg, b = ((1, f, 0), (1 - f, 1, 0), (0, 1, f), (0, 1 - f, 1), (f, 0, 1), (1, 0, 1 - f))[k % 6]
        P.append(g.create_pen(int(r * 255), int(gg * 255), int(b * 255)))

def frame(su, g, t):
    s = int(t * 20)
    for x in range(su.WIDTH):
        g.set_pen(P[(x + s) % 53])
        for y in range(su.HEIGHT):
            g.pixel(x, y)
    return 0.03
