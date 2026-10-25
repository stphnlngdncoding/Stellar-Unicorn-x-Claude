# Smiley face that blinks every few seconds
import random

SMILE = ((3, 9), (4, 10), (5, 11), (6, 11), (7, 11), (8, 11), (9, 11), (10, 10), (11, 9))

def setup(su, g):
    global BLACK, YELLOW, DARK, CHEEK, next_blink
    BLACK = g.create_pen(0, 0, 0)
    YELLOW = g.create_pen(255, 200, 0)
    DARK = g.create_pen(60, 30, 0)
    CHEEK = g.create_pen(255, 90, 60)
    next_blink = 3.0

def frame(su, g, t):
    global next_blink
    blinking = next_blink <= t < next_blink + 0.15
    if t >= next_blink + 0.15:
        next_blink = t + random.uniform(2, 5)
    g.set_pen(BLACK)
    g.clear()
    g.set_pen(YELLOW)
    g.circle(7, 7, 7)
    g.set_pen(DARK)
    if blinking:
        g.rectangle(4, 6, 2, 1)
        g.rectangle(10, 6, 2, 1)
    else:
        g.rectangle(4, 4, 2, 3)
        g.rectangle(10, 4, 2, 3)
    for px, py in SMILE:
        g.pixel(px, py)
    g.set_pen(CHEEK)
    g.pixel(3, 8)
    g.pixel(11, 8)
    return 0.03
