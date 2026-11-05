# Installs launcher v6.3.2 over v6.3.1 (the Galactic Unicorn): reading a big
# program's source (for Settings, the Marquee card or Claude) sets the playing
# program aside while the file is read and sent, then resumes it, and the file
# isn't kept in memory twice while it's sent. Reading big programs used to run
# the Galactic out of memory. The old launcher is kept as main_v631.py. The
# patch is applied only if main.py is exactly v6.3.1.
import os, gc, time, machine

PATCHES = [('VERSION = "6.3.1"\n', 'VERSION = "6.3.2"\n'), ('            elif ctype == "source":\n                with open(name) as f:\n                    res["message"] = f.read()', '            elif ctype == "source":\n                if st["name"] and os.stat(name)[6] > BIG_BODY:\n                    # a big file: set the program aside to make room for reading\n                    # and sending it; it picks up again once it\'s been sent\n                    st["sent_park"] = st["name"]\n                    stop_program(keep_resume=True)\n                    gc.collect()\n                with open(name) as f:\n                    res["message"] = f.read()'), ('            body = json.dumps(payload).encode()\n            head = ("POST %s', '            body = json.dumps(payload)\n            for r in payload.get("results") or ():\n                # a big result (a program\'s source) is now in the body; let go of\n                # the original so there\'s room to encode it. If this send fails,\n                # the caller gets a note to ask again instead of a second copy.\n                m = r.get("message")\n                if m and len(m) > BIG_BODY:\n                    r["message"] = "That file was too big to send twice; please read it again."\n                    r["ok"] = False\n            m = None\n            gc.collect()\n            body = body.encode()\n            gc.collect()\n            head = ("POST %s'), ('                if parked and st["name"] is None and exists(parked):\n                    start_program(parked, managed=True)\n                parked = None', '                if parked and st["name"] is None and exists(parked):\n                    start_program(parked, managed=True)\n                parked = None\n                back = st.pop("sent_park", None)          # a big file\'s been sent: carry on\n                if back and st["name"] is None and (st["what"] or st["list"]) and exists(back):\n                    start_program(back, managed=True)'), ('                back = st.pop("parked", None)\n                if back and st["name"] is None and exists(back):\n                    start_program(back, managed=True)\n                if isinstance(e, MemoryError)', '                back = st.pop("parked", None) or st.pop("sent_park", None)\n                if back and st["name"] is None and exists(back):\n                    start_program(back, managed=True)\n                if isinstance(e, MemoryError)'), ('            writer.write(head.encode())\n            writer.write(body)\n            await writer.drain()\n            done_loading()', '            writer.write(head.encode())\n            writer.write(body)\n            await writer.drain()\n            body = None\n            back = st.pop("sent_park", None)              # a big file\'s gone: carry on now\n            if back and st["name"] is None and (st["what"] or st["list"]) and exists(back):\n                gc.collect()\n                start_program(back, managed=True)\n            done_loading()'), ('            "running": st["name"],\n', '            "running": st["name"] or st.get("sent_park"),   # paused only while a big file goes out\n')]

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
    if 'VERSION = "6.3.1"' not in src:
        ok, why = False, "main.py is not v6.3.1"
    else:
        for old, new in PATCHES:
            if src.count(old) != 1:
                ok, why = False, "main.py differs from v6.3.1"
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
        if _exists("main_v631.py"):
            os.remove("main_v631.py")
        os.rename("main.py", "main_v631.py")
        os.rename("_main_new.tmp", "main.py")
        print("Installed launcher v6.3.2; restarting soon")
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
