# Adventure Dawn: an original, upbeat 8-bit "anime opening" theme with a
# matching title-card animation. A wide sunburst sweeps across the strip
# behind a glinting four-point star that flares out on every kick drum,
# sparkles pop on the hi-hats, and the colours change with each chord.
# (Galactic Unicorn version.)
#   A = mute / unmute   VOL +/- = volume
#
# The tune is an original composition in D major (D - G - A - D, Bm - G - A - D)
# at 150 BPM. Notes are short plucks that fade on their own, so the sound stops
# cleanly when you switch to another program.
import math, random
from galactic import GalacticUnicorn, Channel

STEPS_PER_SEC = 10          # sixteenth notes at 150 BPM
VOLUME = 0.6

# note frequencies (Hz)
A3, B3 = 220, 247
D4, E4, Fs4, G4, A4, B4, Cs5 = 294, 330, 370, 392, 440, 494, 554
D5, E5, Fs5, G5, A5, B5, D6 = 587, 659, 740, 784, 880, 988, 1175
_ = 0                       # no new note on this step

# lead melody: 8 bars x 16 sixteenth steps
LEAD = (
    A4, _, D5, _, Fs5, _, _, _, E5, _, D5, _, A4, _, _, _,      # D
    B4, _, D5, _, G5, _, _, _, Fs5, _, E5, _, D5, _, _, _,     # G
    Cs5, _, E5, _, A5, _, _, _, G5, _, Fs5, _, E5, _, Cs5, _,  # A
    D5, _, _, _, Fs5, _, A5, _, _, _, _, _, _, _, _, _,        # D
    Fs5, _, E5, _, D5, _, B4, _, D5, _, _, _, Fs5, _, _, _,    # Bm
    G5, _, Fs5, _, E5, _, D5, _, B4, _, D5, _, G5, _, _, _,    # G
    A5, _, _, _, G5, _, Fs5, _, E5, _, _, _, Cs5, _, E5, _,    # A
    D5, _, _, _, A4, _, D5, _, Fs5, _, A5, _, D6, _, _, _,     # D
)
# chord roots per bar (bass plays root / octave on eighth notes)
ROOTS = (73, 98, 110, 73, 62, 98, 110, 73)
# colour hue (0..255) per bar, following the chords
BAR_HUE = (20, 90, 150, 20, 200, 90, 150, 235)

def hsv(h, s, v):
    i = int(h * 6); f = h * 6 - i
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))[i % 6]
    return int(r * 255), int(g * 255), int(b * 255)

def setup(su, g):
    global W, H, ANG, DST, STAR, PENS, WHITE, BLACK, ch, last_step, glow, spark, muted, prev, NSPARK
    W, H = su.WIDTH, su.HEIGHT
    BLACK = g.create_pen(0, 0, 0)
    WHITE = g.create_pen(255, 250, 230)
    cx, cy = (W - 1) / 2, (H - 1) / 2
    ANG, DST, STAR = bytearray(W * H), bytearray(W * H), bytearray(W * H)
    for y in range(H):
        for x in range(W):
            dx, dy = x - cx, y - cy
            i = y * W + x
            # rays: angle in a squashed space so they fan out across the width
            ANG[i] = int((math.atan2(dy * 2.4, dx) / (2 * math.pi) + 0.5) * 256) & 255
            # distance for the colour bands, scaled so the bands span the strip
            DST[i] = min(255, int(math.sqrt(dx * dx + dy * dy * 4) * 9))
            # four-point star: distance shrunk along the horizontal/vertical spikes
            r = math.sqrt(dx * dx + dy * dy * 1.7)
            c = math.cos(2 * math.atan2(dy, dx))
            c = c * c
            STAR[i] = min(255, int(r / (0.42 + 0.58 * c * c) * 15))
    # pens: 32 hues x 4 brightness levels
    PENS = [g.create_pen(*hsv(h / 32, 0.9, (v + 1) / 4)) for h in range(32) for v in range(4)]
    NSPARK = max(3, W * H // 85)                     # same sparkle density as the 16x16

    ch = [su.synth_channel(i) for i in range(5)]
    ch[0].configure(waveforms=Channel.SQUARE + Channel.TRIANGLE, attack=0.005, decay=0.32,
                    sustain=0, release=0.05, volume=11000 / 65535)        # lead
    ch[1].configure(waveforms=Channel.TRIANGLE, attack=0.005, decay=0.18,
                    sustain=0, release=0.05, volume=16000 / 65535)        # bass
    ch[2].configure(waveforms=Channel.NOISE, attack=0.002, decay=0.06,
                    sustain=0, release=0.02, volume=16000 / 65535)        # kick
    ch[3].configure(waveforms=Channel.NOISE, attack=0.002, decay=0.10,
                    sustain=0, release=0.02, volume=10000 / 65535)        # snare
    ch[4].configure(waveforms=Channel.NOISE, attack=0.001, decay=0.025,
                    sustain=0, release=0.01, volume=5000 / 65535)         # hi-hat
    try:
        su.set_volume(VOLUME)
    except Exception:
        pass
    su.play_synth()
    last_step = -1
    glow = 0
    spark = bytearray(W * H)
    muted = False
    prev = [False, False, False]

def hit(i, freq):
    if not muted:
        ch[i].frequency(freq)
        ch[i].trigger_attack()

def play_step(s):
    global glow
    n = s % len(LEAD)
    bar, pos = n // 16, n % 16
    if LEAD[n]:
        hit(0, LEAD[n])
    if pos % 2 == 0:                                   # bass on eighth notes
        root = ROOTS[bar]
        hit(1, root * 2 if pos % 4 == 2 else root)
        hit(4, 9000)                                   # hi-hat
        for _i in range(NSPARK):                       # sparkles on the hats
            spark[random.randrange(W * H)] = 255
    if pos in (0, 8, 10):                              # kick
        hit(2, 180)
        glow = 255
    if pos in (4, 12):                                 # snare
        hit(3, 3500)

def frame(su, g, t):
    global last_step, glow, muted
    a = su.is_pressed(GalacticUnicorn.SWITCH_A)
    if a and not prev[0]:
        muted = not muted
    prev[0] = a
    if su.is_pressed(GalacticUnicorn.SWITCH_VOLUME_UP):
        su.adjust_volume(0.01)
    if su.is_pressed(GalacticUnicorn.SWITCH_VOLUME_DOWN):
        su.adjust_volume(-0.01)

    step = int(t * STEPS_PER_SEC)
    if step != last_step:
        for s in range(max(last_step + 1, step - 1), step + 1):   # catch up at most one step
            play_step(s)
        last_step = step

    n = step % len(LEAD)
    hue = BAR_HUE[n // 16]
    spin = int(t * 40)
    pulse = glow >> 6                                  # 0..3
    core = 20 + pulse * 10
    halo = 40 + pulse * 18
    halo_pen = PENS[(((hue + 128) >> 3) & 31) * 4 + 3]

    i = 0
    for y in range(H):
        for x in range(W):
            if spark[i] > 40:
                g.set_pen(WHITE)
                spark[i] = spark[i] * 3 >> 2
            else:
                s = STAR[i]
                if s < halo:                           # glinting star in the middle
                    g.set_pen(WHITE if s < core else halo_pen)
                else:
                    d = DST[i]
                    rays = ((ANG[i] + spin) >> 4) & 1  # 16 alternating rays
                    h = ((hue + (d >> 2) + (rays << 4)) >> 3) & 31
                    v = 3 if rays else 1
                    if d > 150:
                        v = v - 1 if v else 0
                    g.set_pen(PENS[h * 4 + v])
            g.pixel(x, y)
            i += 1
    glow = glow * 7 >> 3
    return 0.02
