# Bouncing Clock: the time drifts slowly round the dark board like an old
# bouncing-logo screensaver, hours stacked over minutes in tiny hand-drawn
# 3x5 digits, with two dots between them that blink each second. Every time
# it touches an edge it changes colour, leaving a faint fading trail behind;
# land it exactly in a corner and it flashes through the rainbow.
#   A = switch between 12-hour and 24-hour time
#
# The time comes from the board's clock (the launcher keeps it set).
# Memory-friendly: the trail is two bytearrays and every pen is made in setup().
from stellar import StellarUnicorn

TWELVE_HOUR = 1      # 1 = 12-hour time, 0 = 24-hour
SPEED = (2.0, 1.4)   # drift speed across and down, pixels per second
TRAIL = 0.7          # seconds the trail takes to fade
TRAIL_GLOW = 80      # how bright the trail starts (0 = no trail, 255 = full)
BRIGHT = 220         # brightness of the digits
CORNER_S = 2.0       # seconds of rainbow after a perfect corner hit (0 = off)
FRAME = 0.04

HUES = 12            # colours it cycles through
LEVELS = 16          # trail brightness steps

# 3x5 digits, one row per byte: bit 2 = left column
DIGITS = ((7, 5, 5, 5, 7), (2, 6, 2, 2, 7), (7, 1, 7, 4, 7), (7, 1, 3, 1, 7),
          (5, 5, 7, 1, 1), (7, 4, 7, 1, 7), (7, 4, 7, 5, 7), (7, 1, 1, 2, 2),
          (7, 5, 7, 5, 7), (7, 5, 7, 1, 7))
BW, BH = 7, 11       # block size: two digits wide, two lines and a gap tall


def hsv(h, v):
    # fully saturated colour for hue 0..1 at value v (0..255)
    h = (h % 1.0) * 6
    i = int(h)
    f = h - i
    q = int(v * (1 - f))
    u = int(v * f)
    return ((v, u, 0), (q, v, 0), (0, v, u), (0, q, v), (u, 0, v), (v, 0, q))[i % 6]


def setup(su, g):
    global W, H, BLACK, PEN, TR, heat, hue, x, y, vx, vy, hue_i, twelve
    global a_was, party, sec_was, sec_t
    W, H = su.WIDTH, su.HEIGHT
    BLACK = g.create_pen(0, 0, 0)
    PEN = []
    TR = []
    for i in range(HUES):
        r, gg, b = hsv(i / HUES, BRIGHT)
        PEN.append(g.create_pen(r, gg, b))
        r, gg, b = hsv(i / HUES, TRAIL_GLOW)
        TR.append([g.create_pen(r * v // (LEVELS - 1), gg * v // (LEVELS - 1), b * v // (LEVELS - 1))
                   for v in range(LEVELS)])
    heat = bytearray(W * H)          # trail brightness, 0..255
    hue = bytearray(W * H)           # trail colour
    x = (W - BW) / 2
    y = (H - BH) / 2
    vx, vy = SPEED
    hue_i = 0
    twelve = TWELVE_HOUR
    a_was = False
    party = -99.0
    sec_was = -1
    sec_t = 0.0


def glyphs(now):
    # the digit list for the top line and the bottom line
    h = now[3]
    if twelve:
        h = h % 12 or 12
        top = (h // 10, h % 10) if h >= 10 else (-1, h)
    else:
        top = (h // 10, h % 10)
    return top, (now[4] // 10, now[4] % 10)


def draw(g, bx, by, top, bot, dots, pen, t, stamp):
    rows = (top, bot)
    for line in range(2):
        a, b = rows[line]
        if a < 0:                       # single-digit hour: centre it
            cols = ((b, 2),)
        else:
            cols = ((a, 0), (b, 4))
        for d, ox in cols:
            pat = DIGITS[d]
            for r in range(5):
                bits = pat[r]
                for c in range(3):
                    if bits & (4 >> c):
                        plot(g, bx + ox + c, by + line * 6 + r, pen, t, stamp)
    if dots:
        plot(g, bx + 2, by + 5, pen, t, stamp)
        plot(g, bx + 4, by + 5, pen, t, stamp)


def plot(g, px, py, pen, t, stamp):
    if 0 <= px < W and 0 <= py < H:
        if stamp:
            i = py * W + px
            heat[i] = 255
            hue[i] = hue_i
        else:
            if pen is None:             # rainbow party
                g.set_pen(PEN[int(t * 8 + px + py) % HUES])
            else:
                g.set_pen(pen)
            g.pixel(px, py)


def frame(su, g, t):
    global x, y, vx, vy, hue_i, twelve, a_was, party, sec_was, sec_t
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was:
        twelve = 0 if twelve else 1
    a_was = a

    now = local_time()
    if now[5] != sec_was:               # line the blink up with the real second
        sec_was = now[5]
        sec_t = t
    dots = (t - sec_t) < 0.5

    # drift and bounce
    x += vx * FRAME
    y += vy * FRAME
    hit = 0
    if x <= 0 or x >= W - BW:
        vx = -vx
        x = 0 if x <= 0 else W - BW
        hit += 1
    if y <= 0 or y >= H - BH:
        vy = -vy
        y = 0 if y <= 0 else H - BH
        hit += 1
    if hit:
        hue_i = (hue_i + 3 + hit * 2) % HUES
        if hit == 2 and CORNER_S > 0:
            party = t

    # fade the trail
    if TRAIL > 0:
        k = int(256 * (1 - FRAME * 3 / TRAIL))
        k = 0 if k < 0 else k
    else:
        k = 0
    for i in range(W * H):
        if heat[i]:
            heat[i] = heat[i] * k >> 8

    bx = int(x + 0.5)
    by = int(y + 0.5)
    top, bot = glyphs(now)

    g.set_pen(BLACK)
    g.clear()
    if TRAIL_GLOW > 0:
        i = 0
        for py in range(H):
            for px in range(W):
                v = heat[i]
                if v > 8:
                    g.set_pen(TR[hue[i]][v * (LEVELS - 1) >> 8])
                    g.pixel(px, py)
                i += 1
    pen = None if t - party < CORNER_S else PEN[hue_i]
    draw(g, bx, by, top, bot, dots, pen, t, False)
    draw(g, bx, by, top, bot, dots, pen, t, True)
    return FRAME
