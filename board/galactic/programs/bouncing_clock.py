# Bouncing Clock: the time drifts slowly along the dark strip like an old
# bouncing-logo screensaver, in hand-drawn 5x7 digits with a colon that blinks
# each second. Every time it touches an edge it changes colour, leaving a faint
# fading trail behind; land it exactly in a corner and it flashes through the
# rainbow. Galactic Unicorn version: on the long strip it mostly glides sideways.
#   A = switch between 12-hour and 24-hour time
#
# The time comes from the board's clock (the launcher keeps it set).
# Memory-friendly: the trail is two bytearrays and every pen is made in setup().
from galactic import GalacticUnicorn

TWELVE_HOUR = 1      # 1 = 12-hour time, 0 = 24-hour
SPEED = (4.0, 0.9)   # drift speed across and down, pixels per second
TRAIL = 0.7          # seconds the trail takes to fade
TRAIL_GLOW = 80      # how bright the trail starts (0 = no trail, 255 = full)
BRIGHT = 220         # brightness of the digits
CORNER_S = 2.0       # seconds of rainbow after a perfect corner hit (0 = off)
FRAME = 0.04

HUES = 12            # colours it cycles through
LEVELS = 16          # trail brightness steps

# 5x7 digits, one row per byte: bit 4 = left column
DIGITS = ((14, 17, 17, 17, 17, 17, 14), (4, 12, 4, 4, 4, 4, 14),
          (14, 17, 1, 2, 4, 8, 31), (31, 2, 4, 2, 1, 17, 14),
          (2, 6, 10, 18, 31, 2, 2), (31, 16, 30, 1, 1, 17, 14),
          (6, 8, 16, 30, 17, 17, 14), (31, 1, 2, 4, 8, 8, 8),
          (14, 17, 17, 14, 17, 17, 14), (14, 17, 17, 15, 1, 2, 12))
DH = 7               # digit height
COLON = 10           # marks the colon in the glyph list


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
    global a_was, party, sec_was, sec_t, glist
    W, H = su.WIDTH, su.HEIGHT
    BLACK = g.create_pen(0, 0, 0)
    PEN = []
    TR = []
    for i in range(HUES):
        r, gg, b = hsv(i / HUES, BRIGHT)
        PEN.append(g.create_pen(r + (BRIGHT - r) // 6, gg + (BRIGHT - gg) // 6, b + (BRIGHT - b) // 6))
        r, gg, b = hsv(i / HUES, TRAIL_GLOW)
        TR.append([g.create_pen(r * v // (LEVELS - 1), gg * v // (LEVELS - 1), b * v // (LEVELS - 1))
                   for v in range(LEVELS)])
    heat = bytearray(W * H)          # trail brightness, 0..255
    hue = bytearray(W * H)           # trail colour
    glist = bytearray(5)             # glyphs to draw this frame (255 = unused)
    x = (W - 25) / 2
    y = (H - DH) / 2
    vx, vy = SPEED
    hue_i = 0
    twelve = TWELVE_HOUR
    a_was = False
    party = -99.0
    sec_was = -1
    sec_t = 0.0


def layout(now):
    # fill glist with the glyphs for HH:MM and return the total width
    h = now[3]
    if twelve:
        h = h % 12 or 12
    n = 0
    if h >= 10 or not twelve:
        glist[0] = h // 10
        n = 1
    glist[n] = h % 10
    glist[n + 1] = COLON
    glist[n + 2] = now[4] // 10
    glist[n + 3] = now[4] % 10
    if n == 0:
        glist[4] = 255
    return (n + 3) * 6 + 1              # 6 px per digit (5 + gap), colon 1 px + gap


def draw(g, bx, by, dots, pen, t, stamp):
    cx = bx
    for k in range(5):
        d = glist[k]
        if d == 255:
            break
        if d == COLON:
            if dots:
                plot(g, cx, by + 2, pen, t, stamp)
                plot(g, cx, by + 4, pen, t, stamp)
            cx += 2
            continue
        pat = DIGITS[d]
        for r in range(DH):
            bits = pat[r]
            for c in range(5):
                if bits & (16 >> c):
                    plot(g, cx + c, by + r, pen, t, stamp)
        cx += 6


def plot(g, px, py, pen, t, stamp):
    if 0 <= px < W and 0 <= py < H:
        if stamp:
            i = py * W + px
            heat[i] = 255
            hue[i] = hue_i
        else:
            if pen is None:             # rainbow party
                g.set_pen(PEN[int(t * 8 + px * 0.5) % HUES])
            else:
                g.set_pen(pen)
            g.pixel(px, py)


def frame(su, g, t):
    global x, y, vx, vy, hue_i, twelve, a_was, party, sec_was, sec_t
    a = su.is_pressed(GalacticUnicorn.SWITCH_A)
    if a and not a_was:
        twelve = 0 if twelve else 1
    a_was = a

    now = local_time()
    if now[5] != sec_was:               # line the blink up with the real second
        sec_was = now[5]
        sec_t = t
    dots = (t - sec_t) < 0.5
    bw = layout(now)

    # drift and bounce
    x += vx * FRAME
    y += vy * FRAME
    hit = 0
    if x <= 0 or x >= W - bw:
        vx = abs(vx) if x <= 0 else -abs(vx)
        x = 0 if x <= 0 else W - bw
        hit += 1
    if y <= 0 or y >= H - DH:
        vy = abs(vy) if y <= 0 else -abs(vy)
        y = 0 if y <= 0 else H - DH
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
    draw(g, bx, by, dots, pen, t, False)
    draw(g, bx, by, dots, pen, t, True)
    return FRAME
