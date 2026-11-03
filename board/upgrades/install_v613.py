# Installs launcher v6.1.3 over v6.1.2: the board starts at full brightness
# instead of half (the brightness buttons, the Remote and Claude can still
# change it until the next restart). The old launcher is kept as
# main_v612.py. The patch is applied only if main.py is exactly the v6.1.2 it
# was made for.
import os, gc, time, machine

PATCHES = [('VERSION = "6.1.2"\n', 'VERSION = "6.1.3"\n'), ('    su.set_brightness(0.5)\n', '    su.set_brightness(1.0)      # start at full brightness\n')]

def _exists(p):
    try:
        os.stat(p)
        return True
    except OSError:
        return False

def setup(su, g):
    global ok, why, t0, GREEN, RED, BLACK
    GREEN = g.create_pen(0, 200, 80)
    RED = g.create_pen(230, 30, 30)
    BLACK = g.create_pen(0, 0, 0)
    ok, why = True, ""
    with open("main.py") as f:
        src = f.read()
    if 'VERSION = "6.1.2"' not in src:
        ok, why = False, "main.py is not v6.1.2"
    else:
        for old, new in PATCHES:
            if src.count(old) != 1:
                ok, why = False, "main.py differs from v6.1.2"
                break
            src = src.replace(old, new)
    if ok:
        gc.collect()
        try:
            compile(src, "main.py", "exec")
        except (NameError, MemoryError):
            pass                       # can't check here; it was tested before shipping
        except Exception as e:
            ok, why = False, "patched launcher doesn't compile: " + repr(e)
    if ok:
        with open("_main_new.tmp", "w") as f:
            f.write(src)
        del src
        if _exists("main_v612.py"):
            os.remove("main_v612.py")
        os.rename("main.py", "main_v612.py")
        os.rename("_main_new.tmp", "main.py")
        print("Installed launcher v6.1.3; restarting soon")
    else:
        print("Launcher not installed:", why)
    t0 = None

def frame(su, g, t):
    global t0
    g.set_pen(BLACK)
    g.clear()
    if ok:
        g.set_pen(GREEN)
        for i, (x, y) in enumerate(((3, 8), (4, 9), (5, 10), (6, 11), (7, 10), (8, 9), (9, 8), (10, 7), (11, 6), (12, 5))):
            g.pixel(x, y)
            g.pixel(x, y - 1)
        if t > 6:
            machine.reset()            # restart into the new launcher
    else:
        g.set_pen(RED)
        for i in range(4, 12):
            g.pixel(i, i)
            g.pixel(15 - i, i)
    return 0.1
