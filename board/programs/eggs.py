# Scrolls "Let's make eggs!" in warm yolky colours, followed by a fried egg
MESSAGE = "Let's make eggs!"
SPEED = 0.06        # seconds per pixel of scrolling (bigger = slower)

EGG = ["..WWWW..",
       ".WWWWWW.",
       "WWWYYWWW",
       "WWYYYYWW",
       "WWWYYWWW",
       ".WWWWWW.",
       "..WWW..."]

def setup(su, g):
    global widths, text_width, total, x, W, BLACK, PENS, EGG_PENS
    W = su.WIDTH
    g.set_font("bitmap8")
    widths = [g.measure_text(c, 1) for c in MESSAGE]
    text_width = sum(widths)
    total = text_width + 4 + 8
    x = W
    BLACK = g.create_pen(0, 0, 0)
    # a little palette from yolk yellow to toasty orange
    PENS = [g.create_pen(255, 220, 40), g.create_pen(255, 190, 30),
            g.create_pen(255, 160, 20), g.create_pen(255, 190, 30)]
    EGG_PENS = {"W": g.create_pen(255, 255, 240), "Y": g.create_pen(255, 170, 0)}

def frame(su, g, t):
    global x
    g.set_pen(BLACK)
    g.clear()
    shift = int(t * 4)
    cx = x
    for i, c in enumerate(MESSAGE):
        if -8 < cx < W:
            g.set_pen(PENS[(i + shift) % len(PENS)])
            g.text(c, cx, 4, -1, 1)
        cx += widths[i]
    ex = x + text_width + 4
    for row, line in enumerate(EGG):
        for col, ch in enumerate(line):
            if ch != "." and 0 <= ex + col < W:
                g.set_pen(EGG_PENS[ch])
                g.pixel(ex + col, 4 + row)
    x -= 1
    if x < -total:
        x = W
    return SPEED
