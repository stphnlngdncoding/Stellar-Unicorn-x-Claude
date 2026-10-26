
# ---------- a quick celebration, then back to what was playing ----------
import math, random
from array import array
from stellar import StellarUnicorn, Channel

DURATION = 6 if KIND in ("perfect", "legend") else 3.5

NOTES = {
    "done": ((0.00, 1319), (0.10, 1760)),
    "crush": ((0.00, 1047), (0.08, 1319), (0.16, 1568), (0.24, 2093)),
    "perfect": ((0.00, 523), (0.10, 659), (0.20, 784), (0.30, 1047), (0.45, 784), (0.55, 1047), (0.65, 1319), (0.80, 1568), (1.00, 2093)),
}
NOTES["legend"] = NOTES["perfect"]
N = 28

def setup(su, g):
    global XPEN, DST, ANG, PX, PY, VX, VY, PC, PENS, RING, BLACK, WHITE, notes, ch, word, sound
    BLACK = g.create_pen(0, 0, 0)
    WHITE = g.create_pen(255, 250, 235)
    DST, ANG = bytearray(256), bytearray(256)
    for i in range(256):
        dx, dy = i % 16 - 7.5, i // 16 - 7.5
        DST[i] = min(255, int(math.sqrt(dx * dx + dy * dy) * 16))
        ANG[i] = int((math.atan2(dy, dx) / (2 * math.pi) + 0.5) * 16) & 15
    gold = KIND in ("crush", "legend")
    base = (255, 190, 40) if gold else COLOR
    PENS = []
    for k in range(16):
        if KIND in ("perfect", "legend"):
            hh = k / 16
            j = int(hh * 6); f = hh * 6 - j
            q, tt = int(255 * (1 - f)), int(255 * f)
            c = ((255, tt, 0), (q, 255, 0), (0, 255, tt), (0, q, 255), (tt, 0, 255), (255, 0, q))[j % 6]
        else:
            c = base
        PENS.append(g.create_pen(*c))
    XPEN = g.create_pen(*base)
    RING = [g.create_pen(*[v * p // 100 for v in base]) for p in (100, 55, 25)]
    PX, PY, VX, VY = array("i", [0] * N), array("i", [0] * N), array("i", [0] * N), array("i", [0] * N)
    PC = bytearray(N)
    for i in range(N):
        a = random.random() * 2 * math.pi
        s = 600 + random.randrange(800)
        PX[i], PY[i] = 7 * 256 + 128, 7 * 256 + 128
        VX[i], VY[i] = int(math.cos(a) * s), int(math.sin(a) * s)
        PC[i] = random.randrange(16)
    sound = not quiet_hours()
    notes = list(NOTES.get(KIND, NOTES["done"]))
    ch = su.synth_channel(0)
    ch.configure(waveforms=Channel.SQUARE + Channel.TRIANGLE, attack=0.005, decay=0.25,
                 sustain=0, release=0.05, volume=12000 / 65535)
    if sound:
        su.play_synth()
    word = WORD

def frame(su, g, t):
    while notes and notes[0][0] <= t:
        f = notes.pop(0)[1]
        if sound:
            ch.frequency(f)
            ch.trigger_attack()
    g.set_pen(BLACK)
    g.clear()
    burst = t % 2.0 if KIND in ("perfect", "legend") else t
    r = int(burst * 200)                               # ring radius, 1/16 px
    if r < 300:
        for i in range(256):
            d = r - DST[i]
            if 0 <= d < 48:
                g.set_pen(PENS[(ANG[i] + int(t * 10)) & 15] if KIND in ("perfect", "legend") else RING[d // 16])
                g.pixel(i % 16, i // 16)
    for i in range(N):
        PX[i] += VX[i] // 8
        PY[i] += VY[i] // 8
        VY[i] += 14                                    # a little gravity
        x, y = PX[i] >> 8, PY[i] >> 8
        if 0 <= x < 16 and 0 <= y < 16:
            g.set_pen(WHITE if random.getrandbits(3) == 0 else PENS[PC[i]])
            g.pixel(x, y)
        elif KIND in ("perfect", "legend") and t < DURATION - 1:
            PX[i], PY[i] = (6 + random.randrange(4)) * 256, (6 + random.randrange(4)) * 256
            VX[i], VY[i] = random.randrange(1200) - 600, -(500 + random.randrange(700))
    if not word and t > 0.6:                          # the X goes on the card
        k = min(5, int((t - 0.6) * 14))
        g.set_pen(WHITE if t < 0.75 or (KIND == "crush" and int(t * 6) % 2) else XPEN)
        for i in range(-k, k + 1):
            for w in (0, 1):
                g.pixel(7 + i + w, 7 + i)
                g.pixel(7 + i + w, 8 - i)
    if word and t > 1.2:
        g.set_font("bitmap8")
        x = 16 - int((t - 1.2) * 18)
        g.set_pen(WHITE)
        g.text(word, x, 4, -1, 1)
    return 0.03
