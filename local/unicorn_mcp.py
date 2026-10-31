#!/usr/bin/env python3
"""Local MCP server for the Stellar Unicorn: no Cloudflare Worker needed.

Claude Desktop or Claude Code starts this script on your computer, and it talks
to the board directly over your Wi-Fi using the launcher's built-in web API.
Standard library only (Python 3.8+), nothing to install.

    UNICORN_HOST=192.168.0.154 python3 unicorn_mcp.py

See local/README.md for how to add it to Claude.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HOST = os.environ.get("UNICORN_HOST", "unicorn.local")
TIMEOUT = float(os.environ.get("UNICORN_TIMEOUT", "15"))
PROTOCOL = "2025-06-18"

GUIDE = """# Programming the Stellar Unicorn (16x16 RGB LEDs)

Programs are MicroPython files that follow this contract. The launcher owns the
main loop, the display and the network, so programs never loop forever.

    def setup(su, g):          # optional, runs once at start
        ...
    def frame(su, g, t):       # called repeatedly; draw ONE frame
        ...                    # t = seconds since the program started (float)
        return 0.03            # optional: seconds until the next frame

- su is the StellarUnicorn, g is PicoGraphics. Do NOT create your own, do NOT
  call su.update() (the launcher does after every frame), and do NOT write a
  while True loop, time.sleep() or anything blocking/network-y.
- Keep state in module globals (declare them with `global` inside functions).
- Create pens once in setup() (g.create_pen(r, g, b) with 0-255 values) and
  reuse them; creating pens every frame works but wastes time.
- Display is 16 wide x 16 tall: x 0..15 left to right, y 0..15 top to bottom.
  su.WIDTH and su.HEIGHT are both 16.
- The whole frame should normally be redrawn: g.set_pen(black); g.clear().
- Keep frames light: 256 pixels is small but this is a microcontroller.
  0.02-0.06 s per frame is typical. Nested loops over all 256 pixels with a
  little maths each are fine.

PicoGraphics drawing:
    g.set_pen(pen); g.clear(); g.pixel(x, y); g.line(x1, y1, x2, y2)
    g.rectangle(x, y, w, h); g.circle(cx, cy, r)
    g.triangle(x1, y1, x2, y2, x3, y3); g.polygon([(x, y), ...])
    g.set_font("bitmap6" | "bitmap8" | "bitmap14_outline")
    g.text(text, x, y, -1, scale)     # -1 = no word wrap; y=4 centres bitmap8
    g.measure_text(text, scale)       # width in pixels
Scrolling text: keep an x offset in a global, draw at x, decrease by 1 each
frame, wrap when x < -width. bitmap8 is 8 px tall and readable; bitmap6 is
smaller. Per-letter colours: draw each character separately, advancing by
g.measure_text(char, 1).

Buttons (read them inside frame):
    from stellar import StellarUnicorn
    su.is_pressed(StellarUnicorn.SWITCH_A)   # also SWITCH_B, SWITCH_C, SWITCH_D
Brightness and sleep buttons are handled by the launcher; don't use them.
Track the previous state yourself to react once per press.

Time: the board's clock is set over the internet. Use the helper
local_time() (already available as a global, no import) which returns a
time.localtime-style tuple (year, month, day, hour, minute, second, weekday,
yearday) in US Pacific time with daylight saving handled. weekday 0 = Monday.

Other modules: math, random, time (for time.ticks_ms etc.) are available.
Colour helper you can paste:
    def hsv(g, h, s=1.0, v=1.0):
        i = int(h * 6); f = h * 6 - i
        p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
        r, gg, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i % 6]
        return g.create_pen(int(r * 255), int(gg * 255), int(b * 255))

File names: letters, digits, _ and - only, ending in .py, e.g. clock.py.
When a program errors, the upload result contains the traceback: fix and
re-upload under the same name.
"""

TOOLS = [
    {"name": "get_programming_guide",
     "description": "How to write programs for the Stellar Unicorn LED board (program contract, drawing API, buttons, time). Read this before writing a new program.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_board_status",
     "description": "Whether the board is reachable, what is playing, the power-on default, the list of programs, the last error and brightness.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "upload_program",
     "description": "Save a MicroPython program to the board and (by default) start it. The code must follow the contract in get_programming_guide (setup/frame, no loops). Returns 'Running <name>' or the error traceback.",
     "inputSchema": {"type": "object", "properties": {
         "name": {"type": "string", "description": "File name, e.g. clock.py"},
         "code": {"type": "string", "description": "Full program source"},
         "run": {"type": "boolean", "description": "Start it right away (default true)"},
         "make_default": {"type": "boolean", "description": "Also make it play at power-on (default false)"}},
         "required": ["name", "code"]}},
    {"name": "run_program", "description": "Start a program that is already on the board.",
     "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "stop_program", "description": "Stop the current program (the board shows its IP address).",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "set_default_program", "description": "Choose which program plays when the board powers on.",
     "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "get_program_source", "description": "Read the source code of a program on the board, e.g. to edit it.",
     "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "delete_program", "description": "Delete a program from the board.",
     "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "set_brightness", "description": "Set display brightness from 0 (off) to 1 (full).",
     "inputSchema": {"type": "object", "properties": {"value": {"type": "number", "minimum": 0, "maximum": 1}}, "required": ["value"]}},
]

INSTRUCTIONS = ("These tools control a Pimoroni Stellar Unicorn, a 16x16 RGB LED matrix on the user's wall, "
                "directly over the local network. To show something new, call get_programming_guide (once per "
                "conversation), write a program that follows its contract, and send it with upload_program. If the "
                "result is an error traceback, fix the code and upload again under the same name. To change an "
                "existing program, read it with get_program_source first.")


class BoardError(Exception):
    pass


def board(method, path, params=None, body=None):
    url = "http://%s%s" % (HOST, path)
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = body.encode("utf-8") if isinstance(body, str) else body
    if method == "POST" and data is None:
        data = b""
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise BoardError(e.read().decode("utf-8", "replace") or "HTTP %d" % e.code)
    except (urllib.error.URLError, OSError) as e:
        raise BoardError("Can't reach the board at %s (%s). Is it on and on the same Wi-Fi? "
                         "Set UNICORN_HOST to the IP address it scrolls at startup." % (HOST, getattr(e, "reason", e)))


def call_tool(name, args):
    n = args.get("name", "")
    if name == "get_programming_guide":
        return GUIDE
    if name == "get_board_status":
        try:
            status = json.loads(board("GET", "/api/status"))
        except BoardError as e:
            return json.dumps({"online": False, "host": HOST, "error": str(e)}, indent=2)
        return json.dumps({"online": True, "host": HOST, "board": status}, indent=2)
    if name == "upload_program":
        params = {"name": n}
        if args.get("run", True):
            params["run"] = "1"
        msg = board("POST", "/upload", params, args.get("code", ""))
        if args.get("make_default"):
            board("POST", "/default", {"name": n})
            msg += " (plays at power-on)"
        return msg
    if name == "run_program":
        return board("POST", "/run", {"name": n})
    if name == "stop_program":
        return board("POST", "/stop")
    if name == "set_default_program":
        return board("POST", "/default", {"name": n})
    if name == "get_program_source":
        return board("GET", "/api/source", {"name": n})
    if name == "delete_program":
        return board("POST", "/delete", {"name": n})
    if name == "set_brightness":
        return board("POST", "/brightness", {"value": max(0.0, min(1.0, float(args.get("value", 0.5))))})
    raise BoardError("Unknown tool " + name)


def reply(msg_id, result=None, error=None):
    out = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()


def handle(msg):
    method, msg_id = msg.get("method"), msg.get("id")
    if msg_id is None:                       # a notification: nothing to answer
        return
    if method == "initialize":
        version = (msg.get("params") or {}).get("protocolVersion") or PROTOCOL
        reply(msg_id, {"protocolVersion": version,
                       "capabilities": {"tools": {}},
                       "serverInfo": {"name": "stellar-unicorn-local", "version": "1.0"},
                       "instructions": INSTRUCTIONS})
    elif method == "ping":
        reply(msg_id, {})
    elif method == "tools/list":
        reply(msg_id, {"tools": TOOLS})
    elif method == "tools/call":
        p = msg.get("params") or {}
        try:
            text = call_tool(p.get("name", ""), p.get("arguments") or {})
            reply(msg_id, {"content": [{"type": "text", "text": text}],
                           "isError": text.startswith("Error")})
        except BoardError as e:
            reply(msg_id, {"content": [{"type": "text", "text": str(e)}], "isError": True})
        except Exception as e:                 # never crash the server on a bad call
            reply(msg_id, {"content": [{"type": "text", "text": "Error: %r" % e}], "isError": True})
    else:
        reply(msg_id, error={"code": -32601, "message": "Method not found: %s" % method})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        for m in (msg if isinstance(msg, list) else [msg]):
            handle(m)


if __name__ == "__main__":
    main()
