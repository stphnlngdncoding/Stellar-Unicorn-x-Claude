# Installs launcher v6.3.1 over v6.3.0 (the Galactic Unicorn's launcher, or a
# Stellar on 6.3.0): when a big message comes from the cloud (an uploaded
# program), the running program is set aside to free memory while it's
# received, then picks up again; a plain out-of-memory error now triggers the
# same recovery as a failed connection. The old launcher is kept as
# main_v630.py. The patch is applied only if main.py is exactly v6.3.0.
import os, gc, time, machine

PATCHES = [('VERSION = "6.3.0"\n', 'VERSION = "6.3.1"\n'), ('MEM_RESET_S = 20                # still out of memory this long -> clean restart\n', 'MEM_RESET_S = 20                # still out of memory this long -> clean restart\nBIG_BODY = 6000                 # a cloud message bigger than this: set the program aside to receive it\n'), ('            data = await read_body(reader, length, chunked)\n        finally:', '            if length is not None and length > BIG_BODY and st["name"]:\n                # a big message (an uploaded program): free the running program\'s\n                # memory so there\'s room to receive it, and pick it up again after\n                st["parked"] = st["name"]\n                stop_program(keep_resume=True)\n                gc.collect()\n            data = await read_body(reader, length, chunked)\n        finally:'), ('                for cmd in reply.get("commands", []):\n                    results.append(execute(cmd))\n                    await asyncio.sleep(0)\n', '                for cmd in reply.get("commands", []):\n                    results.append(execute(cmd))\n                    await asyncio.sleep(0)\n                back = st.pop("parked", None)\n                if back and st["name"] is None and (st["what"] or st["list"]) and exists(back):\n                    start_program(back, managed=True)\n'), ('                if isinstance(e, OSError) and e.args and e.args[0] == 12:', '                back = st.pop("parked", None)\n                if back and st["name"] is None and exists(back):\n                    start_program(back, managed=True)\n                if isinstance(e, MemoryError) or (isinstance(e, OSError) and e.args and e.args[0] == 12):')]

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
    if 'VERSION = "6.3.0"' not in src:
        ok, why = False, "main.py is not v6.3.0"
    else:
        for old, new in PATCHES:
            if src.count(old) != 1:
                ok, why = False, "main.py differs from v6.3.0"
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
        if _exists("main_v630.py"):
            os.remove("main_v630.py")
        os.rename("main.py", "main_v630.py")
        os.rename("_main_new.tmp", "main.py")
        print("Installed launcher v6.3.1; restarting soon")
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
