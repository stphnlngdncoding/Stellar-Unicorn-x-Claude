# Stellar Unicorn launcher v6.2 (playlists, one-shot programs, long-polling cloud, self-healing)
#
# Keeps a small web server running on your Wi-Fi *while* programs play, so a
# new program can be sent and started at any time, no button presses needed.
# If _cloud.json holds a cloud URL and token, the board also checks in with
# the Unicorn cloud service every few seconds, so Claude can send programs
# from anywhere.
#
#   http://<board IP>/   web page: upload, run, stop, set default, delete
#   Sleep button         turns the display off / on
#   Brightness +/-       work for every program
#
# Programs follow a simple contract (the launcher owns the main loop):
#
#     def setup(su, g):        # optional, runs once when the program starts
#         ...
#     def frame(su, g, t):     # draw one frame; t = seconds since start
#         ...
#         return 0.03          # optional: seconds to wait before next frame
#
# su is the StellarUnicorn, g the PicoGraphics. Don't create your own, don't
# call su.update() (the launcher does), and don't write a `while True` loop.
# Old-style programs with their own loop still run, but the board restarts
# into them and the web server is off until you press the sleep button.
#
# One-shot programs set DURATION = <seconds> at the top. They play that long,
# then the board goes back to whatever was playing before (great for
# celebrations and alerts).
#
# Playlists are .py files with no frame() that set:
#
#     PLAYLIST = ["avatar.py", "life.py", "plasma.py"]
#     SECONDS = 3600                       # how long each one plays
#     NIGHT = {"from": 22, "to": 23, "program": "today_card.py"}   # optional
#
# Items change on the clock (every SECONDS), so a restart picks up where it was.

import os, sys, time, gc, json, machine, micropython

VERSION = "6.2"
MEM_RESET_S = 20                # still out of memory this long -> clean restart
RESUME_FILE = "_resume"          # program to resume after a self-heal restart
SELF_RESET = "_self_reset"       # set just before a deliberate self-heal restart
CLOUD_SILENT_S = 300             # no cloud contact this long (Wi-Fi up) -> restart
HOLD_SECONDS = 50                # ask the cloud to keep each check-in open this long
CLOUD_FILE = "_cloud.json"       # {"url": "https://...", "token": "..."}
PORT = 80
HOSTNAME = "unicorn"
DEFAULT_FILE = "_default"          # program that runs at power-on
LEGACY_NEXT = "_legacy_next"       # old-style program to run after a restart
NO_AUTOSTART = "_no_autostart"     # skip a legacy default on the next boot
ERROR_FILE = "_last_error.txt"
PROTECTED = ("main.py", "secrets.py", "boot.py")
SAFE_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-."


# ---------- small helpers ----------

def exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def read(path, default=""):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default

def write(path, text):
    with open(path, "w") as f:
        f.write(text)

def remove(path):
    try:
        os.remove(path)
    except OSError:
        pass

def valid_name(name):
    return (name.endswith(".py") and name not in PROTECTED
            and not name.startswith("_") and 3 < len(name) <= 40
            and all(c in SAFE_CHARS for c in name))

def programs():
    return sorted(n for n in os.listdir() if valid_name(n))

def kind(name):
    """'contract', 'playlist' or 'legacy'."""
    with open(name) as f:
        src = f.read()
    if "def frame" in src:
        return "contract"
    if "PLAYLIST" in src:
        return "playlist"
    return "legacy"

def is_legacy(name):
    return kind(name) == "legacy"

def error_text(name, e):
    import io
    b = io.StringIO()
    sys.print_exception(e, b)
    return "Error in %s:\n%s" % (name, b.getvalue())


# ---------- time: US Pacific with daylight saving ----------

def _nth_sunday(year, month, n):
    wd = time.localtime(time.mktime((year, month, 1, 0, 0, 0, 0, 0)))[6]   # Monday = 0
    return 1 + (6 - wd) % 7 + 7 * (n - 1)

def local_time():
    now = time.time()
    y = time.localtime(now)[0]
    start = time.mktime((y, 3, _nth_sunday(y, 3, 2), 10, 0, 0, 0, 0))    # 2am PST
    end = time.mktime((y, 11, _nth_sunday(y, 11, 1), 9, 0, 0, 0, 0))    # 2am PDT
    offset = -7 if start <= now < end else -8
    return time.localtime(now + offset * 3600)


# ---------- legacy mode: old-style programs with their own loop ----------

_timer = None

def run_legacy(name):
    global _timer
    from stellar import StellarUnicorn
    button = machine.Pin(StellarUnicorn.SWITCH_SLEEP, machine.Pin.IN, machine.Pin.PULL_UP)
    armed = [False]

    def back(_):
        write(NO_AUTOSTART, "1")
        machine.reset()

    def check(_):
        if button.value():
            armed[0] = True
        elif armed[0]:
            armed[0] = False
            micropython.schedule(back, None)

    _timer = machine.Timer(period=100, mode=machine.Timer.PERIODIC, callback=check)
    remove(ERROR_FILE)
    try:
        with open(name) as f:
            code = f.read()
        exec(code, {"__name__": "__main__"})
    except Exception as e:
        write(ERROR_FILE, error_text(name, e))
    back(None)


# ---------- the launcher ----------

def launcher():
    import asyncio, network
    from stellar import StellarUnicorn
    from picographics import PicoGraphics, DISPLAY_STELLAR_UNICORN as DISPLAY

    su = StellarUnicorn()
    g = PicoGraphics(DISPLAY)
    su.set_brightness(0.5)
    W = StellarUnicorn.WIDTH

    st = {
        "env": None,          # the running program's globals
        "name": None,
        "start": 0,
        "msg": "WiFi...",     # scrolled when no program is running
        "colour": (255, 160, 0),
        "ip": None,
        "asleep": False,
        "hold": False,        # pause frames so the cloud connection can get memory
        "wlan": None,
        "last_ok": time.time(),
        "what": None,         # what the user chose: a program or a playlist
        "list": None,         # the active playlist
        "oneshot": None,      # {"name", "until", "back"} for a DURATION program
    }

    # ---------- watchdog ----------
    # boot.py arms the hardware watchdog (_wd.py) and feeds it from a timer. While
    # the launcher runs it switches to strict mode: the timer only feeds while the
    # display loop keeps ticking, so a full freeze resets the chip and the program
    # that was playing is resumed. When the launcher exits (Ctrl-C from Thonny)
    # strict mode is switched off again so the REPL stays usable.
    try:
        import _wd
    except ImportError:
        _wd = None

    def clear_display():
        g.set_pen(g.create_pen(0, 0, 0))
        g.clear()
        su.update(g)

    def fail(name, e):
        text = error_text(name, e)
        print(text)
        write(ERROR_FILE, text)
        st["env"] = None
        st["name"] = None
        st["msg"], st["colour"] = "Error :(", (255, 0, 0)
        return text

    def start_program(name, managed=False):
        """Load and start a contract program. Returns None or an error string.

        managed=True: started by the playlist or to resume; leaves the
        playlist, one-shot and resume state alone."""
        st["env"] = None
        st["name"] = None
        gc.collect()
        try:
            with open(name) as f:
                code = f.read()
            env = {"__name__": name[:-3], "local_time": local_time}
            exec(code, env)
            if "frame" not in env:
                raise ValueError("program has no frame(su, g, t) function")
            g.set_font("bitmap8")
            g.set_pen(g.create_pen(0, 0, 0))
            g.clear()
            if "setup" in env:
                env["setup"](su, g)
            env["frame"](su, g, 0.0)   # draw one test frame so errors show up right away
            su.update(g)
        except Exception as e:
            if not managed:
                st["list"], st["oneshot"], st["what"] = None, None, None
            return fail(name, e)
        remove(ERROR_FILE)
        st["env"] = env
        st["name"] = name
        st["start"] = time.ticks_ms()
        dur = env.get("DURATION")
        if managed:
            pass
        elif isinstance(dur, (int, float)) and dur > 0:
            back = st["oneshot"]["back"] if st["oneshot"] else st["what"]
            st["oneshot"] = {"name": name, "until": time.ticks_add(time.ticks_ms(), int(dur * 1000)), "back": back}
        else:
            st["oneshot"] = None
            st["list"] = None
            st["what"] = name
            if read(RESUME_FILE) != name:
                write(RESUME_FILE, name)
        print("Running", name)
        return None

    # ---------- playlists ----------

    def load_playlist(name):
        env = {}
        with open(name) as f:
            exec(f.read(), env)
        items = [n for n in env.get("PLAYLIST", ()) if valid_name(n)]
        if not items:
            raise ValueError("PLAYLIST needs at least one program name")
        night = env.get("NIGHT")
        if night and not valid_name(night.get("program", "")):
            night = None
        return {"name": name, "items": items, "secs": max(10, int(env.get("SECONDS", 3600))),
                "night": night, "bad": []}

    def usable(pl, n):
        if n in pl["bad"] or not exists(n):
            return False
        try:
            return kind(n) == "contract"
        except OSError:
            return False

    def playlist_pick(pl):
        night = pl["night"]
        if night:
            h = local_time()[3]
            a, b = night.get("from", 22), night.get("to", 23)
            if (a <= h < b) if a < b else (h >= a or h < b):
                if usable(pl, night["program"]):
                    return night["program"]
        items = pl["items"]
        i = int(time.time() // pl["secs"]) % len(items)
        for k in range(len(items)):
            n = items[(i + k) % len(items)]
            if usable(pl, n):
                return n
        return None

    def start_playlist(name):
        try:
            pl = load_playlist(name)
        except Exception as e:
            return fail(name, e)
        st["oneshot"] = None
        st["list"] = pl
        st["what"] = name
        if read(RESUME_FILE) != name:
            write(RESUME_FILE, name)
        print("Playlist", name)
        return playlist_step()

    def playlist_step():
        """Make sure the playlist's current pick is playing."""
        pl = st["list"]
        want = playlist_pick(pl)
        if want is None:
            st["env"], st["name"] = None, None
            st["msg"], st["colour"] = "Playlist is empty", (255, 160, 0)
            return None
        if want == st["name"]:
            return None
        err = start_program(want, managed=True)
        if err:
            pl["bad"].append(want)
        return err

    def resume_what(w):
        if w and exists(w):
            k = kind(w)
            if k == "playlist":
                start_playlist(w)
                return
            if k == "contract":
                start_program(w)
                return
        stop_program()

    async def scheduler():
        while True:
            await asyncio.sleep(1)
            if st["hold"]:
                continue
            try:
                o = st["oneshot"]
                if o:
                    done = time.ticks_diff(time.ticks_ms(), o["until"]) >= 0
                    if done or st["name"] != o["name"]:
                        st["oneshot"] = None
                        if st["name"] in (o["name"], None):
                            resume_what(o["back"])
                    continue
                if st["list"]:
                    playlist_step()
            except Exception as e:
                print("Scheduler:", repr(e))

    def stop_program(keep_resume=False):
        st["env"] = None
        st["name"] = None
        if not keep_resume:
            remove(RESUME_FILE)
            st["list"] = None
            st["oneshot"] = None
            st["what"] = None
        st["msg"], st["colour"] = (st["ip"] or "No WiFi"), (0, 220, 255)

    def replace_file(tmp, name):
        """Swap in an uploaded file. Returns True if it was playing."""
        was = st["name"] == name
        if was:
            st["env"], st["name"] = None, None
        remove(name)
        os.rename(tmp, name)
        if st["list"] and name in st["list"]["bad"]:
            st["list"]["bad"].remove(name)
        return was

    def forget(name):
        """A file is being deleted: stop it, but keep a playlist going."""
        if st["name"] == name:
            if st["list"] or st["oneshot"]:
                st["env"], st["name"] = None, None
            else:
                stop_program()
        if st["list"] and st["list"]["name"] == name:
            stop_program()

    def refresh(name, was):
        """After a save without run: restart it if it was playing, reload a playing playlist."""
        if st["list"] and st["list"]["name"] == name:
            start_playlist(name)
        elif was:
            if st["list"] or st["oneshot"]:
                start_program(name, managed=True)
            else:
                start_program(name)

    # ---------- display loop ----------

    async def render():
        sleep_was = False
        x = W
        while True:
            if _wd:
                _wd.tick()
            pressed = su.is_pressed(StellarUnicorn.SWITCH_SLEEP)
            if pressed and not sleep_was:
                st["asleep"] = not st["asleep"]
                if st["asleep"]:
                    clear_display()
            sleep_was = pressed
            if su.is_pressed(StellarUnicorn.SWITCH_BRIGHTNESS_UP):
                su.adjust_brightness(+0.01)
            if su.is_pressed(StellarUnicorn.SWITCH_BRIGHTNESS_DOWN):
                su.adjust_brightness(-0.01)

            if st["asleep"] or st["hold"]:
                await asyncio.sleep(0.05)
                continue

            env = st["env"]
            if env is not None:
                delay = 0.03
                try:
                    t = time.ticks_diff(time.ticks_ms(), st["start"]) / 1000
                    d = env["frame"](su, g, t)
                    su.update(g)
                    if isinstance(d, (int, float)) and d >= 0:
                        delay = d
                except Exception as e:
                    if st["list"] and st["name"]:
                        st["list"]["bad"].append(st["name"])
                    fail(st["name"], e)
                await asyncio.sleep(delay)
            else:
                g.set_font("bitmap8")
                msg = st["msg"]
                r, gr, b = st["colour"]
                g.set_pen(g.create_pen(0, 0, 0))
                g.clear()
                g.set_pen(g.create_pen(r, gr, b))
                g.text(msg, x, 4, -1, 1)
                su.update(g)
                x -= 1
                if x < -g.measure_text(msg, 1):
                    x = W
                await asyncio.sleep(0.07)

    # ---------- web server ----------

    REASONS = {200: "OK", 400: "Bad Request", 404: "Not Found",
               411: "Length Required", 500: "Server Error"}

    async def send(writer, status, body, ctype="text/plain"):
        if isinstance(body, str):
            body = body.encode()
        head = ("HTTP/1.0 %d %s\r\nContent-Type: %s; charset=utf-8\r\n"
                "Content-Length: %d\r\nAccess-Control-Allow-Origin: *\r\n"
                "Connection: close\r\n\r\n") % (status, REASONS.get(status, "OK"), ctype, len(body))
        writer.write(head.encode())
        writer.write(body)
        await writer.drain()

    def brightness():
        try:
            return round(su.get_brightness(), 2)
        except Exception:
            return None

    def status_dict():
        s = os.statvfs("/")
        return {
            "version": VERSION,
            "ip": st["ip"],
            "running": st["name"],
            "asleep": st["asleep"],
            "default": read(DEFAULT_FILE) or None,
            "programs": programs(),
            "error": read(ERROR_FILE) or None,
            "brightness": brightness(),
            "free_kb": s[0] * s[3] // 1024,
            "cloud": st.get("cloud"),
            "playlist": st["list"]["name"] if st["list"] else None,
            "oneshot": bool(st["oneshot"]),
        }

    def status_json():
        return json.dumps(status_dict())

    async def later_reset(delay=0.5):
        await asyncio.sleep(delay)
        machine.reset()

    def run_named(name, reset_delay=0.5):
        """Start a program now. Returns (status, message)."""
        k = kind(name)
        if k == "playlist":
            err = start_playlist(name)
            if err:
                return 500, err
            return 200, "Playing playlist %s (now: %s)" % (name, st["name"])
        if k == "legacy":
            write(LEGACY_NEXT, name)
            asyncio.create_task(later_reset(reset_delay))
            return 200, "Restarting into old-style program " + name + " (press sleep to come back)"
        err = start_program(name)
        if err:
            return 500, err
        return 200, "Running " + name

    async def handle(reader, writer):
        try:
            line = await reader.readline()
            if not line:
                return
            method, target, _ = line.decode().split(" ", 2)
            length = None
            expect_continue = False
            while True:
                h = await reader.readline()
                if h in (b"\r\n", b""):
                    break
                key, _, value = h.decode().partition(":")
                key = key.strip().lower()
                if key == "content-length":
                    length = int(value.strip())
                elif key == "expect" and "100" in value:
                    expect_continue = True

            path, _, query = target.partition("?")
            params = {}
            for part in query.split("&"):
                k, _, v = part.partition("=")
                params[k] = v
            name = params.get("name", "")

            if method == "GET" and path == "/":
                await send(writer, 200, build_page(), "text/html")
                return
            if method == "GET" and path == "/api/status":
                await send(writer, 200, status_json(), "application/json")
                return
            if method == "POST" and path == "/stop":
                stop_program()
                await send(writer, 200, "Stopped")
                return
            if method == "POST" and path == "/brightness":
                try:
                    su.set_brightness(max(0.0, min(1.0, float(params.get("value", "0.5")))))
                except ValueError:
                    await send(writer, 400, "value must be a number from 0 to 1")
                    return
                await send(writer, 200, "Brightness set")
                return

            known = {("GET", "/api/source"), ("POST", "/upload"), ("POST", "/run"),
                     ("POST", "/default"), ("POST", "/delete")}
            if (method, path) not in known:
                await send(writer, 404, "Not found")
                return
            if not valid_name(name):
                await send(writer, 400, "Use a name like my_program.py (letters, numbers, _ and - only).")
                return

            if path == "/upload":
                if length is None:
                    await send(writer, 411, "Missing Content-Length")
                    return
                if expect_continue:
                    writer.write(b"HTTP/1.1 100 Continue\r\n\r\n")
                    await writer.drain()
                tmp = "_upload.tmp"
                remaining = length
                with open(tmp, "wb") as f:
                    while remaining > 0:
                        chunk = await reader.read(min(1024, remaining))
                        if not chunk:
                            break
                        f.write(chunk)
                        remaining -= len(chunk)
                if remaining:
                    remove(tmp)
                    await send(writer, 400, "Upload was cut off, try again.")
                    return
                was = replace_file(tmp, name)
                print("Uploaded", name, length, "bytes")
                if params.get("run") == "1":
                    status, msg = run_named(name)
                    await send(writer, status, msg)
                else:
                    refresh(name, was)
                    await send(writer, 200, "Saved " + name)
                return

            if not exists(name):
                await send(writer, 404, name + " isn't on the board.")
                return

            if path == "/api/source":
                with open(name) as f:
                    await send(writer, 200, f.read())
            elif path == "/run":
                status, msg = run_named(name)
                await send(writer, status, msg)
            elif path == "/default":
                write(DEFAULT_FILE, name)
                await send(writer, 200, name + " will run at power-on")
            elif path == "/delete":
                forget(name)
                remove(name)
                if read(DEFAULT_FILE) == name:
                    remove(DEFAULT_FILE)
                await send(writer, 200, "Deleted " + name)
        except Exception as e:
            sys.print_exception(e)
            try:
                await send(writer, 500, "Error: " + str(e))
            except Exception:
                pass
        finally:
            writer.close()
            await writer.wait_closed()

    # ---------- cloud check-in ----------

    def save_program(name, code):
        tmp = "_upload.tmp"
        with open(tmp, "w") as f:
            f.write(code)
        return replace_file(tmp, name)

    def execute(cmd):
        """Run one command from the cloud. Returns a result dict."""
        ctype = cmd.get("type")
        name = cmd.get("name", "")
        res = {"id": cmd.get("id"), "ok": True, "message": "Done"}
        try:
            if ctype in ("upload", "run", "default", "delete", "source") and not valid_name(name):
                raise ValueError("Use a name like my_program.py")
            if ctype in ("run", "default", "delete", "source") and not exists(name):
                raise ValueError(name + " isn't on the board. Programs: " + ", ".join(programs()))
            if ctype == "upload":
                was = save_program(name, cmd.get("code", ""))
                print("Cloud uploaded", name)
                res["message"] = "Saved " + name
                if cmd.get("default"):
                    write(DEFAULT_FILE, name)
                    res["message"] += " (plays at power-on)"
                if not cmd.get("run"):
                    refresh(name, was)
                else:
                    status, msg = run_named(name, 4)
                    res["ok"] = status == 200
                    res["message"] = msg
            elif ctype == "run":
                status, msg = run_named(name, 4)
                res["ok"] = status == 200
                res["message"] = msg
            elif ctype == "stop":
                stop_program()
                res["message"] = "Stopped"
            elif ctype == "default":
                write(DEFAULT_FILE, name)
                res["message"] = name + " will play at power-on"
            elif ctype == "delete":
                forget(name)
                remove(name)
                if read(DEFAULT_FILE) == name:
                    remove(DEFAULT_FILE)
                res["message"] = "Deleted " + name
            elif ctype == "source":
                with open(name) as f:
                    res["message"] = f.read()
            elif ctype == "brightness":
                su.set_brightness(max(0.0, min(1.0, float(cmd.get("value", 0.5)))))
                res["message"] = "Brightness set"
            else:
                raise ValueError("unknown command " + str(ctype))
        except Exception as e:
            res["ok"] = False
            res["message"] = "Error: " + str(e)
        return res

    def parse_url(url):
        scheme, _, rest = url.partition("://")
        hostport = rest.split("/")[0]
        host, _, port = hostport.partition(":")
        secure = scheme == "https"
        return host, int(port) if port else (443 if secure else 80), secure

    async def read_body(reader, length, chunked):
        if chunked:
            data = b""
            while True:
                size = int((await reader.readline()).strip().split(b";")[0], 16)
                if size == 0:
                    break
                data += await reader.readexactly(size)
                await reader.readline()
            return data
        if length is not None:
            return await reader.readexactly(length)
        data = b""
        while True:
            chunk = await reader.read(1024)
            if not chunk:
                return data
            data += chunk

    async def cloud_post(cfg, payload):
        host, port, secure = parse_url(cfg["url"])
        ctx = None
        if secure:
            import ssl
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            try:
                ctx.check_hostname = False
            except AttributeError:
                pass
            ctx.verify_mode = ssl.CERT_NONE
        reader, writer = await asyncio.open_connection(host, port, ssl=ctx)
        try:
            body = json.dumps(payload).encode()
            head = ("POST /board/sync HTTP/1.1\r\nHost: %s\r\nAuthorization: Bearer %s\r\n"
                    "Content-Type: application/json\r\nContent-Length: %d\r\n"
                    "Connection: close\r\n\r\n") % (host, cfg["token"], len(body))
            writer.write(head.encode())
            writer.write(body)
            await writer.drain()
            code = int((await reader.readline()).split()[1])
            length, chunked = None, False
            while True:
                h = await reader.readline()
                if h in (b"\r\n", b""):
                    break
                k, _, v = h.decode().partition(":")
                k, v = k.strip().lower(), v.strip()
                if k == "content-length":
                    length = int(v)
                elif k == "transfer-encoding" and "chunked" in v.lower():
                    chunked = True
            data = await read_body(reader, length, chunked)
        finally:
            writer.close()
            await writer.wait_closed()
        if code != 200:
            raise OSError("cloud replied %d: %s" % (code, data[:80]))
        return json.loads(data)

    def cloud_post_blocking(cfg, payload):
        # fallback for firmware whose asyncio can't open TLS connections:
        # briefly pauses the animation while it talks to the cloud
        try:
            import requests
        except ImportError:
            import urequests as requests
        r = requests.post(cfg["url"].rstrip("/") + "/board/sync",
                          data=json.dumps(payload),
                          headers={"Authorization": "Bearer " + cfg["token"],
                                   "Content-Type": "application/json"})
        try:
            if r.status_code != 200:
                raise OSError("cloud replied %d" % r.status_code)
            return r.json()
        finally:
            r.close()

    async def cloud_loop():
        try:
            cfg = json.loads(read(CLOUD_FILE) or "{}")
        except ValueError:
            cfg = {}
        if not cfg.get("url") or not cfg.get("token"):
            st["cloud"] = "not set up"
            return
        results = []
        failures = 0
        mem_failures = 0
        mem_since = 0         # when the current run of out-of-memory failures started
        parked = None         # program stopped to free memory, restarted once connected
        use_blocking = False
        while True:
            gc.collect()
            try:
                payload = {"status": status_dict(), "results": results}
                if use_blocking:
                    reply = cloud_post_blocking(cfg, payload)
                else:
                    # results go back right away; otherwise wait for work
                    payload["wait"] = 0 if results else HOLD_SECONDS
                    try:
                        reply = await asyncio.wait_for(cloud_post(cfg, payload), HOLD_SECONDS + 20)
                    except (TypeError, NotImplementedError, AttributeError) as e:
                        print("Async TLS not available, using blocking requests:", repr(e))
                        use_blocking = True
                        payload.pop("wait", None)
                        reply = cloud_post_blocking(cfg, payload)
                results = []
                failures = 0
                mem_failures = 0
                st["hold"] = False
                st["last_ok"] = time.time()
                if parked and st["name"] is None and exists(parked):
                    start_program(parked, managed=True)
                parked = None
                st["cloud"] = "ok (blocking)" if use_blocking else "ok"
                for cmd in reply.get("commands", []):
                    results.append(execute(cmd))
                    await asyncio.sleep(0)
                if results:
                    delay = 0.1
                elif reply.get("long_poll") and not use_blocking:
                    delay = 0
                else:
                    delay = reply.get("poll", 3)
            except Exception as e:
                st["cloud"] = "error: " + repr(e)
                print("Cloud check-in failed:", repr(e))
                if isinstance(e, OSError) and e.args and e.args[0] == 12:
                    # out of memory for the secure connection: pause the animation,
                    # and if that isn't enough, stop the program until we're connected
                    if mem_failures == 0:
                        mem_since = time.ticks_ms()
                    mem_failures += 1
                    st["hold"] = True
                    if mem_failures >= 3 and st["name"]:
                        parked = st["name"]
                        stop_program(keep_resume=True)
                        print("Stopped", parked, "to free memory; will restart it")
                    if time.ticks_diff(time.ticks_ms(), mem_since) > MEM_RESET_S * 1000:
                        # failed connections leak memory that only a restart frees;
                        # restart cleanly and resume whatever was playing
                        print("Still out of memory; restarting")
                        write(SELF_RESET, "1")
                        await asyncio.sleep(0.1)
                        machine.reset()
                    delay = 0.3
                else:
                    failures += 1
                    st["hold"] = False
                    delay = min(60, 3 * failures)
                    await ensure_wifi()
            gc.collect()
            await asyncio.sleep(delay)

    async def ensure_wifi():
        wlan = st["wlan"]
        if wlan is None or wlan.isconnected():
            return
        print("Wi-Fi dropped, reconnecting")
        try:
            from secrets import WIFI_SSID, WIFI_PASSWORD
            wlan.disconnect()
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        except Exception as e:
            print("Wi-Fi reconnect failed:", repr(e))
            return
        for _ in range(30):
            if wlan.isconnected():
                st["ip"] = wlan.ifconfig()[0]
                print("Wi-Fi back at", st["ip"])
                return
            await asyncio.sleep(0.5)

    async def self_heal():
        # last resort: if the cloud has been unreachable for a long time even
        # though we keep trying, restart cleanly and resume the current program
        while True:
            await asyncio.sleep(30)
            if st.get("cloud") == "not set up":
                continue
            if time.time() - st["last_ok"] > CLOUD_SILENT_S:
                print("No cloud contact for", CLOUD_SILENT_S, "s; restarting")
                write(SELF_RESET, "1")
                await asyncio.sleep(0.2)
                machine.reset()

    def set_clock():
        try:
            import ntptime
            ntptime.settime()
            print("Clock set:", local_time())
        except Exception as e:
            print("Couldn't set the clock:", repr(e))

    # ---------- start-up ----------

    async def connect():
        try:
            from secrets import WIFI_SSID, WIFI_PASSWORD
        except ImportError:
            st["msg"], st["colour"] = "No secrets.py", (255, 0, 0)
            return False
        try:
            network.hostname(HOSTNAME)
        except Exception:
            pass
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        for _ in range(40):
            if wlan.isconnected():
                break
            await asyncio.sleep(0.5)
        if not wlan.isconnected():
            st["msg"], st["colour"] = "WiFi failed", (255, 0, 0)
            return False
        st["wlan"] = wlan
        st["ip"] = wlan.ifconfig()[0]
        st["msg"], st["colour"] = st["ip"], (0, 220, 255)
        print("Unicorn ready at http://%s/" % st["ip"])
        set_clock()
        st["last_ok"] = time.time()   # clock may have jumped; restart the cloud timer
        await asyncio.start_server(handle, "0.0.0.0", PORT)
        asyncio.create_task(cloud_loop())
        asyncio.create_task(self_heal())
        return True

    async def main_async():
        if _wd:
            _wd.strict(True)
        for n in os.listdir():
            if n.startswith("install_v") and n.endswith(".py"):
                remove(n)
        asyncio.create_task(render())
        asyncio.create_task(scheduler())
        online = await connect()
        if online:
            # show the IP address once before the default program starts
            await asyncio.sleep((W + g.measure_text(st["ip"], 1)) * 0.07)
        skip_legacy = exists(NO_AUTOSTART)
        remove(NO_AUTOSTART)
        default = read(DEFAULT_FILE)
        healed = exists(SELF_RESET) or machine.reset_cause() == getattr(machine, "WDT_RESET", -1)
        remove(SELF_RESET)
        resume = read(RESUME_FILE)
        if healed and resume and exists(resume) and not is_legacy(resume):
            print("Recovered from a freeze; resuming", resume)
            default = resume
        if default and exists(default):
            k = kind(default)
            if k == "playlist":
                start_playlist(default)
            elif k == "contract":
                start_program(default)
            elif not skip_legacy:
                write(LEGACY_NEXT, default)
                machine.reset()
        while True:
            await asyncio.sleep(3600)

    def build_page():
        default = read(DEFAULT_FILE)
        running = st["name"]
        rows = ""
        for n in programs():
            tags = ""
            if n == running:
                tags += " <i>playing</i>"
            if n == default:
                tags += " &#9733;"
            rows += ("<li><b>" + n + "</b>" + tags + "<span>"
                     "<button onclick=\"act('run','" + n + "')\">Run</button>"
                     "<button onclick=\"act('default','" + n + "')\">Default</button>"
                     "<button class=del onclick=\"if(confirm('Delete " + n + "?'))act('delete','" + n + "')\">Delete</button>"
                     "</span></li>")
        if not rows:
            rows = "<li>No programs yet. Upload one below.</li>"
        err = read(ERROR_FILE)
        err_html = ("<div class=err>" + err.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + "</div>") if err else ""
        s = os.statvfs("/")
        return (PAGE.replace("{{ROWS}}", rows)
                    .replace("{{ERROR}}", err_html)
                    .replace("{{FREE}}", str(s[0] * s[3] // 1024)))

    if exists(LEGACY_NEXT):
        name = read(LEGACY_NEXT)
        remove(LEGACY_NEXT)
        if exists(name):
            run_legacy(name)
            return
    try:
        asyncio.run(main_async())
    finally:
        if _wd:
            _wd.strict(False)


PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Unicorn</title>
<style>
body{font-family:system-ui,sans-serif;background:#111;color:#eee;max-width:560px;margin:auto;padding:16px}
h1{font-size:1.4em}ul{list-style:none;padding:0}
li{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;padding:10px;background:#1d1d1d;border-radius:8px;margin:6px 0}
i{color:#6cf;font-style:normal;font-size:.85em}
button{background:#2d6cdf;color:#fff;border:0;border-radius:6px;padding:7px 11px;margin-left:4px;font-size:.95em}
button.del{background:#a33}button.alt{background:#444}
.err{background:#3a1212;padding:10px;border-radius:8px;white-space:pre-wrap;font-family:monospace;font-size:.85em}
small{color:#999}
</style></head><body>
<h1>Stellar Unicorn</h1>
{{ERROR}}
<h3>Programs</h3><ul>{{ROWS}}</ul>
<button class=alt onclick="act('stop','')">Stop</button>
<h3>Upload</h3>
<input type=file id=f accept=".py" multiple> <button onclick="up()">Upload</button>
<p id=msg></p>
<p><small>{{FREE}} KB free &middot; &#9733; = runs at power-on &middot; sleep button turns the display off and on</small></p>
<script>
async function up(){
  const fs=document.getElementById('f').files, m=document.getElementById('msg');
  for(const x of fs){
    m.textContent='Uploading '+x.name+'...';
    const r=await fetch('/upload?name='+encodeURIComponent(x.name),{method:'POST',body:x});
    if(!r.ok){m.textContent=x.name+': '+await r.text();return}
  }
  location.reload();
}
async function act(a,n){
  const r=await fetch('/'+a+'?name='+encodeURIComponent(n),{method:'POST'});
  if(!r.ok){alert(await r.text())}
  location.reload();
}
</script></body></html>"""

launcher()
