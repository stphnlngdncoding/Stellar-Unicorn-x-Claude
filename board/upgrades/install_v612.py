# Installs launcher v6.1.2 over v6.1.1: blinks an orange border over the
# screen every 45 seconds when free storage drops below 200 KB. The old
# launcher is kept as main_v611.py. The patch is applied only if main.py is
# exactly the v6.1.1 it was made for.
import os, gc, time, machine

PATCHES = [('VERSION = "6.1.1"\n', 'VERSION = "6.1.2"\n'), ('MEM_RESET_S = 20                # still out of memory this long -> clean restart\n', 'MEM_RESET_S = 20                # still out of memory this long -> clean restart\nLOW_FLASH_KB = 200              # blink a warning border when free storage drops below this\n'), ('        "loading": 0,         # ticks_ms deadline: show the loader until the cloud connection is made\n', '        "loading": 0,         # ticks_ms deadline: show the loader until the cloud connection is made\n        "low_flash": False,   # storage is nearly full\n        "flash_check": time.ticks_ms(),  # when to check storage next\n'), ('            st["start"] = time.ticks_ms()     # the program starts fresh, without the stutter\n\n', '            st["start"] = time.ticks_ms()     # the program starts fresh, without the stutter\n\n    # ---------- low storage warning ----------\n    # Once a minute the launcher checks how much storage is free. If it\'s\n    # below LOW_FLASH_KB, an orange border blinks four times every 45 seconds\n    # over whatever is playing, until programs are deleted.\n    def flash_free_kb():\n        try:\n            s = os.statvfs("/")\n            return s[0] * s[3] // 1024\n        except Exception:\n            return 99999\n\n    def low_flash_overlay():\n        now = time.ticks_ms()\n        if time.ticks_diff(now, st["flash_check"]) >= 0:\n            st["flash_check"] = time.ticks_add(now, 60000)\n            st["low_flash"] = flash_free_kb() < LOW_FLASH_KB\n        if not st["low_flash"]:\n            return\n        phase = (now // 200) % 225\n        if phase < 8 and phase % 2 == 0:\n            g.set_pen(g.create_pen(255, 80, 0))\n            for i in range(16):\n                g.pixel(i, 0)\n                g.pixel(i, 15)\n                g.pixel(0, i)\n                g.pixel(15, i)\n\n'), ('                    d = env["frame"](su, g, t)\n                    su.update(g)\n', '                    d = env["frame"](su, g, t)\n                    low_flash_overlay()\n                    su.update(g)\n')]

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
    if 'VERSION = "6.1.1"' not in src:
        ok, why = False, "main.py is not v6.1.1"
    else:
        for old, new in PATCHES:
            if src.count(old) != 1:
                ok, why = False, "main.py differs from v6.1.1"
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
        if _exists("main_v611.py"):
            os.remove("main_v611.py")
        os.rename("main.py", "main_v611.py")
        os.rename("_main_new.tmp", "main.py")
        print("Installed launcher v6.1.2; restarting soon")
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
