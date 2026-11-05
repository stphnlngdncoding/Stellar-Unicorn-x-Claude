"""Build the iPhone web app version of the Unicorn Remote.

    python3 remote/build_app.py

Reads remote/unicorn-remote.html (the claude.ai artifact) and writes
cloud/src/app/index.html: the same page, but talking to your Cloudflare
Worker directly instead of through the claude.ai connector, with the tags
iOS needs to run it full screen from the home screen. Also writes the app
icons into cloud/src/app/icons.js. Run it after changing the Remote, then
deploy the Worker (cloud/deploy-app.sh).
"""
import base64
import io
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "remote", "unicorn-remote.html")
OUT_DIR = os.path.join(ROOT, "cloud", "src", "app")

HEAD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<title>Unicorn Remote</title>
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Unicorn">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="theme-color" content="#eef0f5" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0c0d12" media="(prefers-color-scheme: dark)">
<meta name="referrer" content="no-referrer">
<meta name="robots" content="noindex">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icon-180.png">
<link rel="icon" type="image/png" href="icon-180.png">
"""

# app-only styles: no tap flash, no zooming, notch-safe edges
APP_CSS = """
html{-webkit-text-size-adjust:100%;touch-action:pan-x pan-y}
input,select,textarea{font-size:16px!important}
body{margin:0;-webkit-tap-highlight-color:transparent;padding-top:max(20px,env(safe-area-inset-top,0px));padding-bottom:max(40px,calc(env(safe-area-inset-bottom,0px) + 72px))}
button,.tile,.chip,input[type=range]{touch-action:manipulation}
[hidden]{display:none!important}
"""

CALL_OLD = """  async function call(tool, input) {
    if (!mcp) throw { code: "capability_disabled" };
    return mcp.callTool(SERVER, tool, Object.assign({}, input || {}, { board: BOARD }), { cache: false });
  }"""
CALL_NEW = """  let reauthing = false;
  function reauth() { if (reauthing) return; reauthing = true; setTimeout(() => location.reload(), 900); }
  // App version: ask the Worker that serves this page (same secret address) to run the tool.
  async function call(tool, input) {
    let r;
    try {
      r = await fetch("api", { method: "POST", headers: { "Content-Type": "application/json" }, cache: "no-store",
        redirect: "manual", body: JSON.stringify({ tool, args: Object.assign({}, input || {}, { board: BOARD }) }) });
    } catch (e) { throw { code: "network" }; }
    // Cloudflare Access in front and the sign-in ran out: reload so it can ask again
    if (r.type === "opaqueredirect" || r.status === 401 || r.status === 403) { reauth(); throw { code: "signin" }; }
    if (r.status === 404) throw { code: "app_gone" };
    if (!r.ok) throw { code: "upstream_error" };
    const out = await r.json();
    const t = textOf(out);
    if (out.isError) throw { code: "tool_error", message: t };
    return out;
  }"""

FAIL_OLD = """    if (c === "server_not_connected") note("""
FAIL_NEW = """    if (c === "signin") { note("Your sign-in ran out. Opening the sign-in page…"); return; }
    if (c === "network") { note(navigator.onLine === false ? "You're offline." : "Couldn't reach the Unicorn cloud.", "bad", ["Try again", retry]); return; }
    if (c === "app_gone") { note("This app's address no longer works. Was the Worker redeployed with a new secret?", "bad"); return; }
    if (c === "server_not_connected") note("""

INIT_OLD = """    const Cl = window.claude;
    try { mcp = Cl && Cl.use ? await Cl.use("mcp") : null; } catch (e) { mcp = null; }
    if (!mcp) { $("connText").textContent = "Open this in Claude to control the board"; note("This remote works inside claude.ai with the stellar1 connector.", "bad"); return; }
    await refresh();"""
INIT_NEW = """    // a home-screen app shouldn't pinch-zoom
    for (const ev of ["gesturestart", "gesturechange"]) document.addEventListener(ev, e => e.preventDefault(), { passive: false });
    await refresh();"""

# a queued command on an offline board is reported by the Worker as an error; say it kindly
TOOLERR_OLD = """    else if (c === "tool_error") note("The board said: " + String(e.message || "error").slice(0, 200), "bad");"""
TOOLERR_NEW = """    else if (c === "tool_error" && /^Queued/.test(e.message || "")) note("The board is offline, so that's queued. It'll happen when the board checks in again.", "bad");
    else if (c === "tool_error") note("The board said: " + String(e.message || "error").slice(0, 200), "bad");"""


def build_page():
    s = open(SRC, encoding="utf-8").read()
    # the artifact starts with <title>; give the app a full document head
    assert s.startswith("<title>"), "unexpected start of remote/unicorn-remote.html"
    s = s.split("\n", 1)[1]
    s = s.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")
    s = HEAD + s
    s = s.replace("</style>\n", APP_CSS.lstrip("\n") + "</style>\n</head><body>\n", 1)
    for old, new in ((CALL_OLD, CALL_NEW), (FAIL_OLD, FAIL_NEW), (INIT_OLD, INIT_NEW), (TOOLERR_OLD, TOOLERR_NEW)):
        assert s.count(old) == 1, "couldn't find: " + old[:60]
        s = s.replace(old, new)
    s = s.rstrip() + "\n</body></html>\n"
    return s


def icon_png(size):
    """A 16x16 LED board glowing with rainbow ripples, on a near-black tile."""
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.new("RGB", (size, size), (10, 11, 16))
    glow = Image.new("RGB", (size, size), (0, 0, 0))
    d = ImageDraw.Draw(im)
    dg = ImageDraw.Draw(glow)
    pad = size * 0.14
    cell = (size - 2 * pad) / 16
    r = cell * 0.36
    for y in range(16):
        for x in range(16):
            dx, dy = x - 7.5, y - 7.5
            dist = math.hypot(dx, dy)
            v = 0.5 + 0.5 * math.sin(dist * 0.9 - 0.6) * math.cos((x - y) * 0.25)
            h = (dist / 11 + 0.62) % 1.0
            on = v > 0.42 and dist < 8.6
            i = int(h * 6)
            f = h * 6 - i
            q, t = 1 - f, f
            rr, gg, bb = ((1, t, 0), (q, 1, 0), (0, 1, t), (0, q, 1), (t, 0, 1), (1, 0, q))[i % 6]
            k = 0.35 + 0.65 * v if on else 0.0
            col = (int(255 * rr * k), int(255 * gg * k), int(255 * bb * k)) if on else (28, 30, 40)
            cx = pad + (x + 0.5) * cell
            cy = pad + (y + 0.5) * cell
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
            if on:
                dg.ellipse([cx - r * 1.6, cy - r * 1.6, cx + r * 1.6, cy + r * 1.6], fill=col)
    # soft glow under the lit LEDs, then the crisp dots on top
    glow = glow.filter(ImageFilter.GaussianBlur(size / 60)).point(lambda p: p * 0.55)
    base = Image.new("RGB", (size, size), (10, 11, 16))
    base = Image.composite(glow, base, glow.convert("L").point(lambda p: 255 if p > 10 else 0))
    dots = Image.new("L", (size, size), 0)
    dd = ImageDraw.Draw(dots)
    for y in range(16):
        for x in range(16):
            cx = pad + (x + 0.5) * cell
            cy = pad + (y + 0.5) * cell
            dd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    out = Image.composite(im, base, dots)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    page = build_page()
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    try:
        icons = {n: base64.b64encode(icon_png(n)).decode() for n in (180, 512)}
    except ImportError:
        print("Pillow isn't installed, so the icons were left as they are (pip install pillow to redraw them).")
        print("wrote cloud/src/app/index.html (%d KB)" % (len(page) // 1024))
        return
    with open(os.path.join(OUT_DIR, "icons.js"), "w") as f:
        f.write("// Generated by remote/build_app.py: the app's home-screen icons (PNG, base64).\n")
        for n, b in icons.items():
            f.write('export const ICON_%d = "%s";\n' % (n, b))
    print("wrote cloud/src/app/index.html (%d KB) and icons.js" % (len(page) // 1024))


if __name__ == "__main__":
    main()
