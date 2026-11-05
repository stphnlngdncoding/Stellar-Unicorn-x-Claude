# Today: a tear-off desk calendar page. A red tab shows the day of the week,
# and the white page beside it shows the date and month in red.
# Galactic Unicorn version: the tab and page sit side by side along the strip.
# The time comes from the board's clock (the launcher keeps it set), so this
# program never touches the network.

DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def setup(su, g):
    global W, H, RED, WHITE
    W, H = su.WIDTH, su.HEIGHT
    RED = g.create_pen(120, 0, 0)
    WHITE = g.create_pen(255, 255, 255)


def frame(su, g, t):
    now = local_time()                 # (year, month, mday, hour, min, sec, weekday, yday)
    day = DAYS[now[6]]
    date = str(now[2])
    month = MONTHS[now[1] - 1]

    # measure everything in the font it will be drawn in
    g.set_font("bitmap6")
    day_w = g.measure_text(day, 1)
    month_w = g.measure_text(month, 1)
    g.set_font("bitmap8")
    date_w = g.measure_text(date, 1)

    # red tab with a little padding each side; tighten the padding and the
    # date/month gap when a two-digit date needs the room
    pad, gap = 5, 3
    while pad > 2 and day_w + pad + date_w + gap + month_w > W - 1:
        if gap > 1:
            gap -= 1
        else:
            pad -= 1
    tab = day_w + pad
    page = W - tab
    block = date_w + gap + month_w

    # white page
    g.set_pen(WHITE)
    g.clear()

    # red tab with the weekday in white
    g.set_pen(RED)
    g.rectangle(0, 0, tab, H)
    g.set_pen(WHITE)
    g.set_font("bitmap6")
    g.text(day, (tab - day_w) // 2 + 1, 3, -1, 1)

    # date (big) and month (small, sharing its baseline) in red on the page
    x = tab + (page - block) // 2 + 1
    g.set_pen(RED)
    g.set_font("bitmap8")
    g.text(date, x, 2, -1, 1)
    g.set_font("bitmap6")
    g.text(month, x + date_w + gap, 4, -1, 1)

    g.set_font("bitmap8")
    return 1.0
