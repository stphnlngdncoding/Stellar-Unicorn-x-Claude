# Soft Plasma: a calm, dim plasma in a narrow band of colour, mirrored left to
# right and top to bottom so it breathes out from the middle of the board.
# Low contrast on purpose: no black and no bright peaks, just slow glowing
# folds of colour that drift around the rainbow over a few minutes.
#
# Memory-friendly: only one quarter of the board is worked out each frame
# (the rest is its mirror image), with integer lookup tables and pens made
# once in setup.
import math

SPEED = 0.25          # how fast the waves move (1 = as fast as Plasma)
STRETCH = 1.0         # how much wider the waves are side to side
BRIGHT = 0.4          # brightest it gets (0-1)
CONTRAST = 0.35       # how much darker the dim folds are (0 = flat, 1 = down to black)
SPREAD = 0.3          # how much of the rainbow shows at once (0-1)
SATURATION = 0.8      # colour strength (0 = grey, 1 = full colour)
COLOUR_SPEED = 0.004  # trips around the rainbow per second
FRAME = 0.03

HUES = 64
LEVELS = 8

def _hsv(h, s, v):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i]
    return int(r * 255), int(g * 255), int(b * 255)

def setup(su, g):
    global W, H, QW, QH, SIN, PENS, XA, XB, YA, YB, RAD, HO, LO, c0
    W, H = su.WIDTH, su.HEIGHT
    QW, QH = (W + 1) // 2, (H + 1) // 2
    SIN = [int(127 * math.sin(2 * math.pi * i / 256)) for i in range(256)]
    br = min(max(BRIGHT, 0.05), 1.0)
    ct = min(max(CONTRAST, 0.0), 1.0)
    sat = min(max(SATURATION, 0.0), 1.0)
    PENS = []
    for li in range(LEVELS):
        v = br * (1 - ct + ct * li / (LEVELS - 1))
        for hi in range(HUES):
            r, gg, b = _hsv(hi / HUES, sat, v)
            PENS.append(g.create_pen(r, gg, b))
    st = STRETCH if STRETCH > 0.2 else 0.2
    cx, cy = (W - 1) / 2, (H - 1) / 2
    k = 256 / (2 * math.pi)
    # distances from the middle, for the top-left quarter only
    DX = [abs(x - cx) / st for x in range(QW)]
    DY = [abs(y - cy) for y in range(QH)]
    XA = bytearray(int(d / 3 * k) & 255 for d in DX)
    XB = bytearray(int(d / 4 * k) & 255 for d in DX)
    YA = bytearray(int(d / 2.5 * k) & 255 for d in DY)
    YB = bytearray(int(d / 4 * k) & 255 for d in DY)
    RAD = bytearray(int(math.sqrt(dx * dx + dy * dy) / 2 * k) & 255 for dy in DY for dx in DX)
    # wave sum (0..1016) -> hue offset and brightness row, eased so the
    # middle values (the most common) spread out smoothly
    spread = min(max(SPREAD, 0.0), 1.0)
    HO = bytearray(1017)
    LO = []
    for u in range(1017):
        e = 0.5 - 0.5 * math.cos(math.pi * u / 1016)
        HO[u] = int(e * spread * (HUES - 1)) & 63
        LO.append(min(LEVELS - 1, int(e * LEVELS)) * HUES)
    c0 = int(math.sin(su.WIDTH * 7.3 + H) * 1000) % HUES   # where on the rainbow it starts

def frame(su, g, t):
    p = int(t * SPEED * 256 / (2 * math.pi))
    c = (c0 + int(t * COLOUR_SPEED * HUES)) % HUES
    p13 = p * 13 // 10
    p7 = p * 7 // 10
    p2 = 2 * p
    S = SIN
    i = 0
    xr = W - 1
    yr = H - 1
    for y in range(QH):
        wy = S[(YA[y] - p13) & 255]
        yb = YB[y] + p7
        y2 = yr - y
        for x in range(QW):
            u = (S[(XA[x] + p) & 255] + wy + S[(XB[x] + yb) & 255] + S[(RAD[i] - p2) & 255]) + 508
            g.set_pen(PENS[LO[u] + ((c + HO[u]) & 63)])
            x2 = xr - x
            g.pixel(x, y)
            g.pixel(x2, y)
            g.pixel(x, y2)
            g.pixel(x2, y2)
            i += 1
    return FRAME
