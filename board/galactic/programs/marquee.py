# Marquee: your message scrolls along the board, jazzy and lively. The
# letters bob along in a wave, colours dance through them, each letter has a
# soft shadow, and sparkles pop and twinkle around the words. Set it from the
# Unicorn Remote's Marquee card, or edit the lines below. (Galactic version:
# a long 53 x 11 strip, so the message has room to breathe.)
#   A = pause / resume
#
# Memory-friendly: letter positions and pens are worked out once in setup(),
# sparkles live in a fixed pool, and each frame only draws what's on screen.
import math
import random
from galactic import GalacticUnicorn

MESSAGE = "Hello from the Unicorn!"
STYLE = 0            # colours: 0 rainbow, 1 white, 2 warm, 3 cool, 4 neon
SPEED = 16           # pixels a second
WAVE = 1             # how far the letters bob up and down (0 = straight, 2 = big, clips a little)
BOUNCE = 6.0         # how fast they bob
SPARKLE = 0.5        # how many sparkles (0 = none, 1 = lots)
COLOUR_SPEED = 0.6   # how fast the colours dance along the message
GAP = 16             # blank pixels before the message comes round again

HUES = 32
SPARKS = 48

def hsv(h, s, v):
    i = int(h * 6)
    f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i % 6]
    return int(r * 255), int(g * 255), int(b * 255)

def setup(su, g):
    global W, H, BASE_Y, CHARS, TOTAL, PENS, SHADOW, SPARKPEN, BLACK, BOB, RATE
    global sparks, scroll, last_t, paused, a_was, spark_acc
    W, H = su.WIDTH, su.HEIGHT
    g.set_font("bitmap8")
    BASE_Y = (H - 9) // 2                         # 8 px letters + 1 px shadow, centred
    BLACK = g.create_pen(0, 0, 0)
    CHARS = []
    x = 0
    for ch in MESSAGE or " ":
        w = 4 if ch == " " else g.measure_text(ch, 1)
        CHARS.append((ch, x, w))
        x += w + 1
    TOTAL = x
    cols = []
    for i in range(HUES):
        k = abs(i - HUES // 2) / (HUES // 2)          # 1 -> 0 -> 1 round the table
        if STYLE == 1:
            c = hsv(0.6, 0.08 * k, 1.0)
        elif STYLE == 2:
            c = hsv(0.13 * k, 0.85, 1.0)
        elif STYLE == 3:
            c = hsv(0.47 + 0.25 * k, 0.75, 1.0)
        elif STYLE == 4:
            c = (255, 40, 200) if i % 8 < 4 else (40, 240, 255)
        else:
            c = hsv(i / HUES, 0.9, 1.0)
        cols.append(c)
    PENS = [g.create_pen(*c) for c in cols]
    SHADOW = [g.create_pen(c[0] // 7, c[1] // 7, c[2] // 7) for c in cols]
    SPARKPEN = [g.create_pen(v, v, min(255, v + 40)) for v in (40, 90, 150, 215, 255)]
    BOB = [int(WAVE * math.sin(k * 2 * math.pi / 64) + 0.5 * (1 if k < 32 else -1)) for k in range(64)]
    RATE = SPARKLE * 0.6 * W / 16                 # same sparkle density as on the 16 x 16
    sparks = [[0, 0, 0] for _ in range(SPARKS)]   # x, y, life (0 = free)
    spark_acc = 0.0
    scroll = 0.0
    last_t = 0.0
    paused = False
    a_was = False

def frame(su, g, t):
    global scroll, last_t, paused, a_was, spark_acc
    a = su.is_pressed(GalacticUnicorn.SWITCH_A)
    if a and not a_was:
        paused = not paused
    a_was = a
    dt = t - last_t
    if dt > 0.1:
        dt = 0.1
    last_t = t
    if not paused:
        scroll += SPEED * dt

    g.set_pen(BLACK)
    g.clear()

    # sparkles twinkle and fade behind the words
    if not paused:
        spark_acc += RATE * random.random() * 2
        while spark_acc >= 1:
            spark_acc -= 1
            for s in sparks:
                if not s[2]:
                    s[0] = random.randrange(W)
                    s[1] = random.choice((0, 1, H - 2, H - 1, random.randrange(H)))
                    s[2] = 9
                    break
    for s in sparks:
        if s[2]:
            v = s[2] if s[2] < 5 else 9 - s[2]
            g.set_pen(SPARKPEN[v if v < 5 else 4])
            g.pixel(s[0], s[1])
            if not paused:
                s[2] -= 1

    period = TOTAL + GAP + W
    x0 = W - int(scroll) % period
    shift = int(t * COLOUR_SPEED * HUES)
    phase = int(t * BOUNCE * 64 / 6.283)
    for i in range(len(CHARS)):
        ch, off, w = CHARS[i]
        x = x0 + off
        if x >= W:
            break
        if x + w < 0 or ch == " ":
            continue
        y = BASE_Y + BOB[(phase + i * 9) & 63]
        c = (i * 3 + shift) % HUES
        g.set_pen(SHADOW[c])
        g.text(ch, x + 1, y + 1, -1, 1)
        g.set_pen(PENS[c])
        g.text(ch, x, y, -1, 1)
    return 0.03
