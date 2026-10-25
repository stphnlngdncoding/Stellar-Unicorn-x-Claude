# Pimoroni's "70s-tastic, procedural rainbow lava lamp", converted to the
# launcher's setup/frame style. Soft blobs drift, swell and merge while the
# colour slowly cycles through the rainbow.
#   A = shake up the lamp (new blobs)
import random, math
from stellar import StellarUnicorn

BLOB_COUNT = 5
HUE_STEP = 0.001    # how fast the colour cycles

class Blob():
    def __init__(self):
        self.x = float(random.randint(0, width - 1))
        self.y = float(random.randint(0, height - 1))
        self.r = (float(random.randint(0, 40)) / 10.0) + 5.0
        self.dx = (float(random.randint(0, 2)) / 10.0) - 0.1
        self.dy = (float(random.randint(0, 2)) / 10.0) - 0.05  # positive bias

def from_hsv(g, h, s, v):
    i = math.floor(h * 6.0)
    f = h * 6.0 - i
    v *= 255.0
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    i = int(i) % 6
    if i == 0:
        return g.create_pen(int(v), int(t), int(p))
    if i == 1:
        return g.create_pen(int(q), int(v), int(p))
    if i == 2:
        return g.create_pen(int(p), int(v), int(t))
    if i == 3:
        return g.create_pen(int(p), int(q), int(v))
    if i == 4:
        return g.create_pen(int(t), int(p), int(v))
    return g.create_pen(int(v), int(p), int(q))

def setup_portrait():
    global width, height, liquid, blobs
    width = StellarUnicorn.HEIGHT
    height = StellarUnicorn.WIDTH
    liquid = [[0.0 for y in range(height)] for x in range(width)]
    blobs = [Blob() for i in range(BLOB_COUNT)]

def update_liquid():
    for y in range(height):
        for x in range(width):
            liquid[x][y] = 0.0
    for blob in blobs:
        r_sq = blob.r * blob.r
        for y in range(max(math.floor(blob.y - blob.r), 0), min(math.ceil(blob.y + blob.r), height)):
            for x in range(max(math.floor(blob.x - blob.r), 0), min(math.ceil(blob.x + blob.r), width)):
                x_diff = x - blob.x
                y_diff = y - blob.y
                d_sq = x_diff * x_diff + y_diff * y_diff
                if d_sq <= r_sq:
                    liquid[x][y] += 1.0 - (d_sq / r_sq)

def move_blobs():
    for blob in blobs:
        blob.x += blob.dx
        blob.y += blob.dy
        if blob.x < 0.0 or blob.x >= float(width):
            blob.dx = 0.0 - blob.dx
        if blob.y < 0.0 or blob.y >= float(height):
            blob.dy = 0.0 - blob.dy

def setup(su, g):
    global hue, BLACK, a_was
    hue = 0.0
    BLACK = g.create_pen(0, 0, 0)
    a_was = False
    setup_portrait()

def frame(su, g, t):
    global hue, a_was
    a = su.is_pressed(StellarUnicorn.SWITCH_A)
    if a and not a_was:
        setup_portrait()
    a_was = a

    update_liquid()
    move_blobs()

    hue += HUE_STEP
    dark = from_hsv(g, hue, 1.0, 0.3)
    mid = from_hsv(g, hue, 1.0, 0.6)
    bright = from_hsv(g, hue, 1.0, 1.0)
    for y in range(height):
        for x in range(width):
            v = liquid[x][y]
            # pick a colour by how much "blobfluence" there is here
            if v >= 1.5:
                g.set_pen(bright)
            elif v >= 1.25:
                g.set_pen(mid)
            elif v >= 1.0:
                g.set_pen(dark)
            else:
                g.set_pen(BLACK)
            g.pixel(y, x)
    return 0.01
