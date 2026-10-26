
# ---------- shared helpers (same in every Level Up program) ----------
import math, random
from array import array

# tiny 3x5 font for numbers and a few letters
FONT = {
    "0": (7, 5, 5, 5, 7), "1": (2, 6, 2, 2, 7), "2": (7, 1, 7, 4, 7), "3": (7, 1, 3, 1, 7),
    "4": (5, 5, 7, 1, 1), "5": (7, 4, 7, 1, 7), "6": (7, 4, 7, 5, 7), "7": (7, 1, 1, 2, 2),
    "8": (7, 5, 7, 5, 7), "9": (7, 5, 7, 1, 7), "L": (4, 4, 4, 4, 7), "V": (5, 5, 5, 5, 2),
    "/": (1, 1, 2, 4, 4), "+": (0, 2, 7, 2, 0), " ": (0, 0, 0, 0, 0),
}

def text_w(s):
    return len(s) * 4 - 1

def text3(g, s, x, y):
    for ch in s:
        rows = FONT.get(ch)
        if rows:
            for r in range(5):
                bits = rows[r]
                for c in range(3):
                    if bits & (4 >> c):
                        g.pixel(x + c, y + r)
        x += 4

def scaled(c, pct):
    return (c[0] * pct // 100, c[1] * pct // 100, c[2] * pct // 100)

def quiet_hours():
    try:
        h = local_time()[3]
        return h >= 23 or h < 7
    except Exception:
        return False

def load_sprite(g):
    """Turn SPRITE/GLOW strings into lists of (x, y, pen) ready to draw."""
    pens = [g.create_pen(*c) for c in COLORS]
    body, flame, eyes, glow = [], [], [], []
    for i in range(256):
        ch = SPRITE[i]
        if ch != ".":
            p = (i % 16, i // 16, pens[ord(ch) - 65])
            if FLAME[i] == "#":
                flame.append(p)
            elif i in EYES:
                eyes.append(p)
            else:
                body.append(p)
        ch = GLOW[i]
        if ch != ".":
            glow.append((i % 16, i // 16, g.create_pen(*scaled(COLORS[ord(ch) - 65], 30)), i))
    return body, flame, eyes, glow

def draw_sprite(g, spr, t, dy=0, blink=False, flicker=0):
    body, flame, eyes, glow = spr
    tw = int(t * 3)
    for x, y, p, i in glow:
        if (i * 7 + tw) % 5:
            g.set_pen(p)
            g.pixel(x, y)
    for x, y, p in body:
        g.set_pen(p)
        g.pixel(x, y + dy)
    for x, y, p in eyes:
        g.set_pen(BLINK_PEN if blink else p)
        g.pixel(x, y + dy)
    for x, y, p in flame:
        g.set_pen(FLICK_PEN if (x * 3 + y + flicker) % 3 == 0 else p)
        g.pixel(x, y + dy)
