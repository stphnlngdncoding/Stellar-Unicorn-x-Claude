# Rotation: plays a list of programs one after another, switching every
# SECONDS. Set it up from the Unicorn Remote, or edit the two lines below.
# Programs change on the clock, so after a restart it picks up where it was.
# Old-style programs (ones with their own loop) are skipped.
PLAYLIST = ["plasma.py", "goo.py", "life.py"]
SECONDS = 600

# ---- the rest runs the playlist ----
import gc, time

def _load(name):
    global cur, cur_name, cur_t0
    cur, cur_name = None, None
    gc.collect()
    try:
        with open(name) as f:
            src = f.read()
        if "def frame" not in src:
            raise ValueError("old-style program")
        env = {"__name__": name[:-3]}
        if "local_time" in globals():
            env["local_time"] = local_time
        exec(src, env)
        del src
        G.set_font("bitmap8")
        G.set_pen(G.create_pen(0, 0, 0))
        G.clear()
        if "setup" in env:
            env["setup"](SU, G)
        cur, cur_name = env, name
    except Exception as e:
        print("rotation: skipping", name, repr(e))
        bad.append(name)
    cur_t0 = None

def _pick():
    items = [n for n in PLAYLIST if n not in bad]
    if not items:
        return None
    return items[int(time.time() // max(10, SECONDS)) % len(items)]

def setup(su, g):
    global SU, G, bad, cur, cur_name, cur_t0
    SU, G = su, g
    bad, cur, cur_name, cur_t0 = [], None, None, None

def frame(su, g, t):
    global cur_t0, cur
    want = _pick()
    if want is None:
        g.set_pen(g.create_pen(0, 0, 0))
        g.clear()
        return 0.5
    if want != cur_name:
        _load(want)
        if cur is None:
            return 0.05
    if cur_t0 is None:
        cur_t0 = t
    try:
        return cur["frame"](su, g, t - cur_t0)
    except Exception as e:
        print("rotation: error in", cur_name, repr(e))
        bad.append(cur_name)
        cur = None
        return 0.05
