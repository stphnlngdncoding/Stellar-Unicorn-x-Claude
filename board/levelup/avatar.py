
# ---------- the avatar ----------
DRAGON_S = 24      # seconds of dragon between the info cards
CARD_S = 4         # seconds each info card shows

def setup(su, g):
    global SPR, BLINK_PEN, FLICK_PEN, BLACK, GOLD, WHITE, DIMBAR, ORANGE, YELLOW, ACC, DONE_PEN, TODO_PEN
    SPR = load_sprite(g)
    BLINK_PEN = g.create_pen(*COLORS[BODY])
    FLICK_PEN = g.create_pen(255, 230, 120)
    BLACK = g.create_pen(0, 0, 0)
    GOLD = g.create_pen(255, 190, 40)
    WHITE = g.create_pen(240, 236, 255)
    DIMBAR = g.create_pen(40, 30, 10)
    ORANGE = g.create_pen(255, 110, 30)
    YELLOW = g.create_pen(255, 220, 80)
    ACC = g.create_pen(*ACCENT)
    DONE_PEN = g.create_pen(255, 90, 110)
    TODO_PEN = g.create_pen(45, 20, 28)

def dragon(g, t):
    g.set_pen(BLACK)
    g.clear()
    period = 1.6 if MOOD == "party" else 3.2
    ph = t % period
    dy = -1 if ph < 0.22 else 0                      # little hop
    blink = MOOD != "sleepy" and (t % 4.7) < 0.14
    draw_sprite(g, SPR, t, dy, blink, int(t * 8))

def level_card(g, t):
    g.set_pen(BLACK)
    g.clear()
    g.set_pen(GOLD)
    text3(g, "LV", (16 - text_w("LV")) // 2, 1)
    s = str(LEVEL)
    g.set_pen(WHITE)
    text3(g, s, (16 - text_w(s)) // 2, 8)
    fill = 14 * XP_PCT // 100
    for x in range(14):
        g.set_pen(GOLD if x < fill else DIMBAR)
        g.pixel(1 + x, 14)

FLAME_ICON = ("...#...", "..##...", "..###..", ".#####.", ".##.##.", "##...##", ".#...#.", "..###..")

def streak_card(g, t):
    g.set_pen(BLACK)
    g.clear()
    f = int(t * 6)
    for y in range(8):
        row = FLAME_ICON[y]
        for x in range(7):
            if row[x] == "#":
                g.set_pen(YELLOW if (y > 3 and (x + f) % 3 == 0) else ORANGE)
                g.pixel(4 + x, y)
    s = str(STREAK)
    g.set_pen(WHITE)
    text3(g, s, (16 - text_w(s)) // 2, 9)
    n = min(TOTAL, 16)
    if n:
        pitch = 2 if n <= 8 else 1
        x0 = (16 - (n - 1) * pitch - 1) // 2
        for i in range(n):
            g.set_pen(DONE_PEN if i < DONE else TODO_PEN)
            g.pixel(x0 + i * pitch, 15)

def frame(su, g, t):
    c = t % (DRAGON_S + 2 * CARD_S)
    if c < DRAGON_S:
        dragon(g, t)
    elif c < DRAGON_S + CARD_S:
        level_card(g, t)
    else:
        streak_card(g, t)
    return 0.05
