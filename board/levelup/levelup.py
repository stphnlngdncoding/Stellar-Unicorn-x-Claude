
# ---------- level-up fanfare, then back to what was playing ----------
from stellar import StellarUnicorn, Channel

DURATION = 10 if EVOLVED else 7

# an original little fanfare: (seconds, lead Hz, bass Hz)
TUNE = ((0.00, 523, 131), (0.12, 659, 0), (0.24, 784, 0), (0.36, 1047, 196),
        (0.70, 988, 0), (0.82, 1047, 0), (0.94, 1175, 0), (1.10, 1319, 262),
        (1.60, 1568, 131), (1.72, 2093, 0))
COLS = 20

def setup(su, g):
    global SPR, BLINK_PEN, FLICK_PEN, BLACK, WHITE, GOLD, SPARK, HY, HS, tune, lead, bass, sound
    SPR = load_sprite(g)
    BLINK_PEN = g.create_pen(*COLORS[BODY])
    FLICK_PEN = g.create_pen(255, 230, 120)
    BLACK = g.create_pen(0, 0, 0)
    WHITE = g.create_pen(255, 252, 240)
    GOLD = g.create_pen(255, 190, 40)
    SPARK = [g.create_pen(255, 190, 40), g.create_pen(255, 120, 170), g.create_pen(120, 220, 255), g.create_pen(255, 255, 255)]
    HY = array("i", [random.randrange(16 * 256) for _ in range(COLS)])
    HS = array("i", [120 + random.randrange(200) for _ in range(COLS)])
    sound = not quiet_hours()
    tune = list(TUNE)
    lead, bass = su.synth_channel(0), su.synth_channel(1)
    lead.configure(waveforms=Channel.SQUARE, attack=0.005, decay=0.35, sustain=0, release=0.05, volume=10000 / 65535)
    bass.configure(waveforms=Channel.TRIANGLE, attack=0.005, decay=0.5, sustain=0, release=0.05, volume=16000 / 65535)
    if sound:
        su.play_synth()

def sparkles(g, n):
    for i in range(n):
        HY[i] -= HS[i]
        if HY[i] < 0:
            HY[i] = 16 * 256 + random.randrange(512)
        g.set_pen(SPARK[i & 3])
        g.pixel((i * 7) % 16, HY[i] >> 8)

def frame(su, g, t):
    while tune and tune[0][0] <= t:
        _, f, b = tune.pop(0)
        if sound:
            lead.frequency(f)
            lead.trigger_attack()
            if b:
                bass.frequency(b)
                bass.trigger_attack()
    g.set_pen(BLACK)
    g.clear()
    if t < 4.0:
        sparkles(g, COLS)
        flash = t > 1.7 and int(t * 8) % 2 == 0
        g.set_pen(WHITE if flash else GOLD)
        text3(g, "LV", (16 - text_w("LV")) // 2, 2)
        s = str(LEVEL)
        g.set_pen(GOLD if flash else WHITE)
        text3(g, s, (16 - text_w(s)) // 2, 9)
    elif EVOLVED and t < 4.6:
        g.set_pen(WHITE)                                # evolution flash
        g.clear()
    else:
        sparkles(g, 8)
        dy = -1 if (t % 0.8) < 0.2 else 0
        draw_sprite(g, SPR, t, dy, False, int(t * 8))
    return 0.03
