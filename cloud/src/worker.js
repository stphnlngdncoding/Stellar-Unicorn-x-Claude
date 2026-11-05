// Unicorn cloud: a tiny relay between Claude and your Pimoroni Unicorn boards
// (a Stellar Unicorn, and optionally a Galactic Unicorn).
//
//   /mcp/<MCP_SECRET>   MCP server (streamable HTTP) that Claude connects to
//   /app/<MCP_SECRET>/  the Unicorn Remote as a phone web app (add it to your
//                       home screen); same secret, same tools as the connector
//   /board/sync         a board checks in here (Authorization: Bearer <BOARD_TOKEN>);
//                       ?board=galactic for the Galactic, otherwise it's the Stellar
//
// Each board has its own Durable Object holding its command queue; the board
// picks commands up on its next check-in, runs them, and reports results on
// the following one. Every tool takes an optional "board" (default stellar).
//
// A board's check-in stays open for up to 50 seconds, around the clock. That
// wait lives here in the Worker, not in the Durable Object: a Durable Object is
// billed for every second it's awake, so it sleeps on a hibernating WebSocket
// and only wakes when there's a command to pass on.

import APP_HTML from "./app/index.html";
import { ICON_180, ICON_512 } from "./app/icons.js";

const PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"];
const RESULT_WAIT_MS = 20000;
const ONLINE_WINDOW_MS = 20000;
const MAX_QUEUE = 20;
const POLL_SECONDS = 3;
const MAX_HOLD_MS = 50000;   // long-poll: hold an idle board check-in this long
const CLOSE_REPLACED = 4000; // WebSocket close code: a newer check-in took over

// The boards this Worker knows. "object" names each board's Durable Object
// (the Stellar keeps the name it always had, so its queue and status carry over).
const BOARDS = {
  stellar: { object: "board-v2", title: "Stellar Unicorn", size: "16x16" },
  galactic: { object: "galactic-v1", title: "Galactic Unicorn", size: "53 wide x 11 tall" },
};
const BOARD_NAMES = Object.keys(BOARDS);
const BOARD_ARG = {
  type: "string", enum: BOARD_NAMES,
  description: "Which board: stellar (16x16, the default) or galactic (53x11).",
};

const GUIDE = `# Programming the Stellar Unicorn (16x16 RGB LEDs)

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
- Keep state in module globals (declare them with \`global\` inside functions).
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
`;

// The Galactic's guide is the Stellar's with its own size, module and tips.
const GUIDE_GALACTIC = GUIDE
  .replace("# Programming the Stellar Unicorn (16x16 RGB LEDs)", "# Programming the Galactic Unicorn (53x11 RGB LEDs)")
  .replace("su is the StellarUnicorn", "su is the GalacticUnicorn")
  .replace(`- Display is 16 wide x 16 tall: x 0..15 left to right, y 0..15 top to bottom.
  su.WIDTH and su.HEIGHT are both 16.`, `- Display is 53 wide x 11 tall: x 0..52 left to right, y 0..10 top to bottom.
  Use su.WIDTH (53) and su.HEIGHT (11) rather than hard-coding numbers. It's a
  wide strip: scenes read best when things move sideways, text scrolls, and
  big objects are short and long rather than tall.`)
  .replace("Keep frames light: 256 pixels is small", "Keep frames light: 583 pixels is small")
  .replace("all 256 pixels with a", "all 583 pixels with a")
  .replace("bitmap8 is 8 px tall and readable", "bitmap8 is 8 px tall and readable (y=2 centres it on the 11-row strip)")
  .replace("    from stellar import StellarUnicorn\n    su.is_pressed(StellarUnicorn.SWITCH_A)", "    from galactic import GalacticUnicorn\n    su.is_pressed(GalacticUnicorn.SWITCH_A)")
  .replace("y=4 centres bitmap8", "y=2 centres bitmap8");

function guideFor(board) { return board === "galactic" ? GUIDE_GALACTIC : GUIDE; }

const TOOLS = [
  {
    name: "get_programming_guide",
    description: "How to write programs for a board (program contract, drawing API, buttons, time). Pass board=galactic for the 53x11 Galactic Unicorn. Read it before writing a program for that board.",
    inputSchema: { type: "object", properties: { board: BOARD_ARG }, additionalProperties: false },
    annotations: { readOnlyHint: true },
  },
  {
    name: "get_board_status",
    description: "Whether the board is online, what is playing, the power-on default, the list of programs, the last error and brightness. Also lists the other boards briefly.",
    inputSchema: { type: "object", properties: { board: BOARD_ARG }, additionalProperties: false },
    annotations: { readOnlyHint: true },
  },
  {
    name: "upload_program",
    description: "Save a MicroPython program to the board and (by default) start it. The code must follow the contract in get_programming_guide (setup/frame, no loops). Returns 'Running <name>' or the error traceback.",
    inputSchema: {
      type: "object",
      properties: {
        name: { type: "string", description: "File name, e.g. clock.py" },
        code: { type: "string", description: "Full program source" },
        run: { type: "boolean", description: "Start it right away (default true)" },
        make_default: { type: "boolean", description: "Also make it play at power-on (default false)" },
        board: BOARD_ARG,
      },
      required: ["name", "code"],
      additionalProperties: false,
    },
  },
  {
    name: "run_program",
    description: "Start a program that is already on the board.",
    inputSchema: {
      type: "object",
      properties: { name: { type: "string" }, board: BOARD_ARG },
      required: ["name"],
      additionalProperties: false,
    },
  },
  {
    name: "stop_program",
    description: "Stop the current program (the board shows its IP address).",
    inputSchema: { type: "object", properties: { board: BOARD_ARG }, additionalProperties: false },
  },
  {
    name: "set_default_program",
    description: "Choose which program plays when the board powers on.",
    inputSchema: {
      type: "object",
      properties: { name: { type: "string" }, board: BOARD_ARG },
      required: ["name"],
      additionalProperties: false,
    },
  },
  {
    name: "get_program_source",
    description: "Read the source code of a program on the board, e.g. to edit it.",
    inputSchema: {
      type: "object",
      properties: { name: { type: "string" }, board: BOARD_ARG },
      required: ["name"],
      additionalProperties: false,
    },
    annotations: { readOnlyHint: true },
  },
  {
    name: "delete_program",
    description: "Delete a program from the board.",
    inputSchema: {
      type: "object",
      properties: { name: { type: "string" }, board: BOARD_ARG },
      required: ["name"],
      additionalProperties: false,
    },
    annotations: { destructiveHint: true },
  },
  {
    name: "set_brightness",
    description: "Set display brightness from 0 (off) to 1 (full).",
    inputSchema: {
      type: "object",
      properties: { value: { type: "number", minimum: 0, maximum: 1 }, board: BOARD_ARG },
      required: ["value"],
      additionalProperties: false,
    },
  },
];

const INSTRUCTIONS =
  "These tools control the user's Pimoroni Unicorn LED boards: a Stellar Unicorn (16x16, board=stellar, " +
  "the default when no board is given) and a Galactic Unicorn (53 wide x 11 tall, board=galactic). " +
  "Pass board on every call when working with the Galactic; programs must be written for that board's size. " +
  "To show something new, call get_programming_guide (once per conversation), write a program that " +
  "follows its contract, and send it with upload_program. If the result is an error traceback, fix " +
  "the code and upload again under the same name. To change an existing program, read it with " +
  "get_program_source first, from the same board.";

// ---------------------------------------------------------------------------
// Durable Object: holds the command queue and the board's last status
// ---------------------------------------------------------------------------

export class Board {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.waiters = new Map();
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/sync") return this.sync(await request.json());
    if (url.pathname === "/hold") return this.hold();
    if (url.pathname === "/take") return Response.json({ commands: await this.take() });
    if (url.pathname === "/command") return this.command(await request.json());
    if (url.pathname === "/status") return Response.json(await this.status());
    return new Response("not found", { status: 404 });
  }

  async status() {
    const s = await this.state.storage.get(["status", "lastSeen", "queue"]);
    const lastSeen = s.get("lastSeen") || 0;
    const age = lastSeen ? Date.now() - lastSeen : null;
    const waiting = this.state.getWebSockets().length > 0;   // a check-in is being held open
    return {
      online: waiting || (age !== null && age < ONLINE_WINDOW_MS),
      last_seen_seconds_ago: waiting ? 0 : age === null ? null : Math.round(age / 1000),
      queued_commands: (s.get("queue") || []).length,
      board: s.get("status") || null,
    };
  }

  async sync(body) {
    await this.state.storage.put({ status: body.status || null, lastSeen: Date.now() });
    for (const r of body.results || []) {
      const resolve = this.waiters.get(r.id);
      if (resolve) {
        this.waiters.delete(r.id);
        resolve(r);
      }
    }
    const commands = await this.take(false);
    // nothing to do: tell the Worker how long to hold the check-in open
    const hold = commands.length ? 0 : Math.min(Number(body.wait) || 0, MAX_HOLD_MS / 1000) * 1000;
    return Response.json({ commands, poll: POLL_SECONDS, long_poll: true, hold });
  }

  // The Worker waits on the other end of this socket. The socket is hibernatable,
  // so this object can leave memory (and stop being billed) during the wait.
  async hold() {
    for (const old of this.state.getWebSockets()) {
      try { old.close(CLOSE_REPLACED, "replaced by a newer check-in"); } catch (e) {}
    }
    const pair = new WebSocketPair();
    this.state.acceptWebSocket(pair[1]);
    // a command that slipped in after /sync looked at the queue
    if (((await this.state.storage.get("queue")) || []).length) this.wake();
    return new Response(null, { status: 101, webSocket: pair[0] });
  }

  // Commands stay queued until the Worker takes them, so one sent just as a hold
  // ends isn't lost: the board's next check-in collects it.
  wake() {
    for (const ws of this.state.getWebSockets()) {
      try { ws.send("wake"); } catch (e) {}
    }
  }

  async take(touch = true) {
    const queue = (await this.state.storage.get("queue")) || [];
    if (queue.length) await this.state.storage.put("queue", []);
    if (touch) await this.state.storage.put("lastSeen", Date.now());
    return queue;
  }

  webSocketClose(ws, code, reason) {
    try { ws.close(code, reason); } catch (e) {}
  }

  async command(cmd) {
    cmd.id = crypto.randomUUID();
    const queue = (await this.state.storage.get("queue")) || [];
    queue.push(cmd);
    while (queue.length > MAX_QUEUE) queue.shift();
    await this.state.storage.put("queue", queue);
    this.wake();

    const result = await new Promise((resolve) => {
      this.waiters.set(cmd.id, resolve);
      setTimeout(() => {
        if (this.waiters.delete(cmd.id)) resolve(null);
      }, RESULT_WAIT_MS);
    });
    return Response.json({ result, status: await this.status() });
  }
}

// ---------------------------------------------------------------------------
// MCP
// ---------------------------------------------------------------------------

const NAME_RE = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,36}\.py$/;

async function boardCall(stub, path, body) {
  const res = await stub.fetch("https://board" + path, {
    method: body ? "POST" : "GET",
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

function text(t, isError = false) {
  return { content: [{ type: "text", text: t }], isError };
}

async function sendCommand(stub, cmd) {
  const { result, status } = await boardCall(stub, "/command", cmd);
  if (result) return text(result.message || (result.ok ? "Done" : "Failed"), !result.ok);
  const seen = status.last_seen_seconds_ago;
  const where = seen === null
    ? "The board has never checked in yet. Is the launcher installed and on Wi-Fi?"
    : status.online
      ? "The board is online but didn't confirm in time; check get_board_status in a moment."
      : `The board looks offline (last seen ${seen}s ago). It will run this when it next checks in.`;
  return text("Queued, not confirmed yet. " + where, !status.online);
}

async function callTool(name, args, stubFor) {
  args = args || {};
  const board = args.board === undefined || args.board === null || args.board === "" ? "stellar" : args.board;
  if (!BOARDS[board]) return text("board must be one of: " + BOARD_NAMES.join(", "), true);
  const stub = stubFor(board);
  const needName = ["upload_program", "run_program", "set_default_program", "get_program_source", "delete_program"];
  if (needName.includes(name) && !NAME_RE.test(args.name || "")) {
    return text("Use a file name like my_program.py (letters, digits, _ - only).", true);
  }
  switch (name) {
    case "get_programming_guide":
      return text(guideFor(board));
    case "get_board_status": {
      const st = await boardCall(stub, "/status");
      st.which = board;
      st.title = BOARDS[board].title + " (" + BOARDS[board].size + ")";
      // a one-line glance at the other boards, so Claude knows they're there
      st.other_boards = {};
      for (const other of BOARD_NAMES) {
        if (other === board) continue;
        const o = await boardCall(stubFor(other), "/status");
        st.other_boards[other] = o.last_seen_seconds_ago === null
          ? "never connected"
          : (o.online ? "online" : "offline") + (o.board && o.board.running ? ", playing " + o.board.running : "");
      }
      return text(JSON.stringify(st, null, 2));
    }
    case "upload_program":
      if (typeof args.code !== "string" || !args.code.trim()) return text("code is empty", true);
      if (args.code.length > 60000) return text("Program is too large (60 KB max).", true);
      return sendCommand(stub, {
        type: "upload", name: args.name, code: args.code,
        run: args.run !== false, default: args.make_default === true,
      });
    case "run_program":
      return sendCommand(stub, { type: "run", name: args.name });
    case "stop_program":
      return sendCommand(stub, { type: "stop" });
    case "set_default_program":
      return sendCommand(stub, { type: "default", name: args.name });
    case "get_program_source":
      return sendCommand(stub, { type: "source", name: args.name });
    case "delete_program":
      return sendCommand(stub, { type: "delete", name: args.name });
    case "set_brightness": {
      const v = Number(args.value);
      if (!(v >= 0 && v <= 1)) return text("value must be between 0 and 1", true);
      return sendCommand(stub, { type: "brightness", value: v });
    }
    default:
      return null;
  }
}

async function handleRpc(msg, stubFor) {
  const { id, method, params } = msg;
  const reply = (result) => ({ jsonrpc: "2.0", id, result });
  const fail = (code, message) => ({ jsonrpc: "2.0", id, error: { code, message } });

  if (id === undefined || id === null) return null; // notification
  switch (method) {
    case "initialize": {
      const asked = params && params.protocolVersion;
      return reply({
        protocolVersion: PROTOCOL_VERSIONS.includes(asked) ? asked : PROTOCOL_VERSIONS[0],
        capabilities: { tools: { listChanged: false } },
        serverInfo: { name: "stellar-unicorn", title: "Unicorn boards", version: "1.1.0" },
        instructions: INSTRUCTIONS,
      });
    }
    case "ping":
      return reply({});
    case "tools/list":
      return reply({ tools: TOOLS });
    case "tools/call": {
      try {
        const out = await callTool(params && params.name, params && params.arguments, stubFor);
        if (!out) return fail(-32602, "Unknown tool: " + (params && params.name));
        return reply(out);
      } catch (e) {
        return reply(text("Server error: " + (e && e.message), true));
      }
    }
    default:
      return fail(-32601, "Method not found: " + method);
  }
}

async function handleMcp(request, stubFor) {
  if (request.method === "GET") return new Response("Method Not Allowed", { status: 405, headers: { Allow: "POST" } });
  if (request.method === "DELETE") return new Response(null, { status: 204 });
  if (request.method !== "POST") return new Response("Method Not Allowed", { status: 405 });

  let body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error" } }, { status: 400 });
  }
  if (Array.isArray(body)) {
    const out = (await Promise.all(body.map((m) => handleRpc(m, stubFor)))).filter(Boolean);
    return out.length ? Response.json(out) : new Response(null, { status: 202 });
  }
  const out = await handleRpc(body, stubFor);
  return out ? Response.json(out) : new Response(null, { status: 202 });
}

// ---------------------------------------------------------------------------
// Phone web app: the Unicorn Remote, served at /app/<MCP_SECRET>/
// ---------------------------------------------------------------------------

// Tools the app may use (no deleting from a phone tap).
const APP_TOOLS = ["get_board_status", "run_program", "stop_program", "set_default_program",
  "set_brightness", "upload_program", "get_program_source"];

const PRIVATE = {
  "Cache-Control": "no-store",
  "Referrer-Policy": "no-referrer",
  "X-Robots-Tag": "noindex, nofollow",
  "X-Content-Type-Options": "nosniff",
};

function pngResponse(b64) {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  return new Response(bytes, { headers: { ...PRIVATE, "Content-Type": "image/png", "Cache-Control": "public, max-age=86400" } });
}

async function handleApp(request, stubFor, rest, base) {
  if (rest === "" || rest === "index.html") {
    return new Response(APP_HTML, {
      headers: { ...PRIVATE, "Content-Type": "text/html; charset=utf-8",
        "Content-Security-Policy": "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'" },
    });
  }
  if (rest === "manifest.webmanifest") {
    return new Response(JSON.stringify({
      name: "Unicorn Remote", short_name: "Unicorn", start_url: base, scope: base, display: "standalone",
      background_color: "#0c0d12", theme_color: "#0c0d12",
      icons: [{ src: "icon-180.png", sizes: "180x180", type: "image/png" },
              { src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "any maskable" }],
    }), { headers: { ...PRIVATE, "Content-Type": "application/manifest+json" } });
  }
  if (rest === "icon-180.png") return pngResponse(ICON_180);
  if (rest === "icon-512.png") return pngResponse(ICON_512);
  if (rest === "api") {
    if (request.method !== "POST") return new Response("Method Not Allowed", { status: 405, headers: PRIVATE });
    let body;
    try { body = await request.json(); } catch { return new Response("bad request", { status: 400, headers: PRIVATE }); }
    if (!APP_TOOLS.includes(body && body.tool)) return new Response("unknown tool", { status: 400, headers: PRIVATE });
    let out;
    try { out = await callTool(body.tool, body.args, stubFor); }
    catch (e) { out = text("Server error: " + (e && e.message), true); }
    return Response.json(out, { headers: PRIVATE });
  }
  return new Response("not found", { status: 404, headers: PRIVATE });
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

function safeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// A board's check-in, in the Worker: hand it to the Durable Object, and if
// there's nothing to do, wait here until the object says a command has arrived.
async function boardSync(stub, body) {
  const res = await stub.fetch("https://board/sync", { method: "POST", body });
  if (!res.ok) return res;
  const { hold, ...reply } = await res.json();
  if (hold > 0) reply.commands = await waitForCommands(stub, hold);
  return Response.json(reply);
}

async function waitForCommands(stub, ms) {
  const res = await stub.fetch("https://board/hold", { headers: { Upgrade: "websocket" } });
  const ws = res.webSocket;
  if (!ws) return [];
  ws.accept();
  const woken = await new Promise((resolve) => {
    const timer = setTimeout(() => resolve(false), ms);
    const finish = (v) => { clearTimeout(timer); resolve(v); };
    ws.addEventListener("message", () => finish(true));
    ws.addEventListener("close", () => finish(false));
    ws.addEventListener("error", () => finish(false));
  });
  try { ws.close(1000, "done"); } catch (e) {}
  if (!woken) return [];
  const took = await stub.fetch("https://board/take", { method: "POST" });
  return (await took.json()).commands;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const stubFor = (board) => env.BOARD.get(env.BOARD.idFromName(BOARDS[board].object));

    if (url.pathname === "/board/sync") {
      const which = url.searchParams.get("board") || "stellar";
      if (!BOARDS[which]) return new Response("unknown board", { status: 404 });
      const auth = request.headers.get("Authorization") || "";
      if (!env.BOARD_TOKEN || !safeEqual(auth, "Bearer " + env.BOARD_TOKEN)) {
        return new Response("unauthorized", { status: 401 });
      }
      if (request.method !== "POST") return new Response("Method Not Allowed", { status: 405 });
      return boardSync(stubFor(which), await request.text());
    }

    const parts = url.pathname.split("/");
    if (parts[1] === "mcp") {
      if (!env.MCP_SECRET || !safeEqual(parts[2] || "", env.MCP_SECRET) || parts.length > 3) {
        return new Response("not found", { status: 404 });
      }
      return handleMcp(request, stubFor);
    }

    if (parts[1] === "app") {
      if (!env.MCP_SECRET || !safeEqual(parts[2] || "", env.MCP_SECRET) || parts.length > 4) {
        return new Response("not found", { status: 404 });
      }
      const base = "/app/" + parts[2] + "/";
      if (parts.length === 3) return Response.redirect(url.origin + base, 301);  // relative links need the slash
      return handleApp(request, stubFor, parts[3], base);
    }

    if (url.pathname === "/") return new Response("Unicorn cloud is running.\n");
    return new Response("not found", { status: 404 });
  },
};
