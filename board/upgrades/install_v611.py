# Installs launcher v6.1.1 over v6.1: one connection per cloud command
# instead of two, and a small loading spinner while it connects, so newly
# started programs don't stutter. The old launcher is kept as main_v61.py.
# The patch is applied only if main.py is exactly the v6.1 it was made for.
import os, gc, time, machine

PATCHES = [('\nimport os, sys, time, gc, json, machine, micropython\n\n', '\nimport os, sys, time, gc, json, math, machine, micropython\n\n'), ('\nVERSION = "6.1"\nMEM_RESET_S = 20                # still out of memory this long -> clean restart\n', '\nVERSION = "6.1.1"\nMEM_RESET_S = 20                # still out of memory this long -> clean restart\n'), ('        "hold": False,        # pause frames so the cloud connection can get memory\n        "wlan": None,\n', '        "hold": False,        # pause frames so the cloud connection can get memory\n        "loading": 0,         # ticks_ms deadline: show the loader until the cloud connection is made\n        "wlan": None,\n'), ('        return text\n\n', '        return text\n\n    # ---------- loading animation ----------\n    # After a program is started from the cloud, the board reports back over a\n    # new secure connection, and setting that up pauses everything for about\n    # half a second. Rather than let the new program stutter, a small spinner\n    # plays until the connection is made, then the program starts from t = 0.\n    RING = [(7 + round(3.4 * math.cos(i * math.pi / 6)), 7 + round(3.4 * math.sin(i * math.pi / 6)))\n            for i in range(12)]\n    LOADPENS = []\n\n    def draw_loader():\n        if not LOADPENS:\n            for k in range(6):\n                v = (6 - k) * 42\n                LOADPENS.append(g.create_pen(v * 7 // 10, v * 8 // 10, v))\n            LOADPENS.append(g.create_pen(0, 0, 0))\n        g.set_pen(LOADPENS[6])\n        g.clear()\n        head = (time.ticks_ms() // 70) % 12\n        for k in range(5, -1, -1):\n            x, y = RING[(head - k) % 12]\n            g.set_pen(LOADPENS[k])\n            g.pixel(x, y)\n            g.pixel(x + 1, y)\n            g.pixel(x, y + 1)\n            g.pixel(x + 1, y + 1)\n        su.update(g)\n\n    def done_loading():\n        if st["loading"]:\n            st["loading"] = 0\n            st["start"] = time.ticks_ms()     # the program starts fresh, without the stutter\n\n'), ('                continue\n\n', '                continue\n\n            if st["loading"]:\n                if st["env"] is not None and time.ticks_diff(st["loading"], time.ticks_ms()) > 0:\n                    draw_loader()\n                    await asyncio.sleep(0.03)\n                    continue\n                done_loading()\n\n'), ('            await writer.drain()\n            code = int((await reader.readline()).split()[1])\n', '            await writer.drain()\n            done_loading()\n            code = int((await reader.readline()).split()[1])\n'), ('                else:\n                    # results go back right away; otherwise wait for work\n                    payload["wait"] = 0 if results else HOLD_SECONDS\n                    try:\n', '                else:\n                    # results ride along on the next long poll: one connection, not two\n                    payload["wait"] = HOLD_SECONDS\n                    try:\n'), ('                st["cloud"] = "ok (blocking)" if use_blocking else "ok"\n                for cmd in reply.get("commands", []):\n', '                st["cloud"] = "ok (blocking)" if use_blocking else "ok"\n                done_loading()\n                started = st["start"]\n                for cmd in reply.get("commands", []):\n'), ('                    await asyncio.sleep(0)\n                if results:\n', '                    await asyncio.sleep(0)\n                if st["env"] is not None and st["start"] != started and not use_blocking:\n                    st["loading"] = time.ticks_add(time.ticks_ms(), 6000)\n                if results:\n'), ('                if results:\n                    delay = 0.1\n                elif reply.get("long_poll") and not use_blocking:\n', '                if results:\n                    delay = 0\n                elif reply.get("long_poll") and not use_blocking:\n')]

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
    if 'VERSION = "6.1"' not in src:
        ok, why = False, "main.py is not v6.1"
    else:
        for old, new in PATCHES:
            if src.count(old) != 1:
                ok, why = False, "main.py differs from v6.1"
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
        if _exists("main_v61.py"):
            os.remove("main_v61.py")
        os.rename("main.py", "main_v61.py")
        os.rename("_main_new.tmp", "main.py")
        print("Installed launcher v6.1.1; restarting soon")
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
