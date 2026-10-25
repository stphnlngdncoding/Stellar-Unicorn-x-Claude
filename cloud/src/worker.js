// Unicorn cloud: a tiny relay between Claude and a Stellar Unicorn.
//
//   /mcp/<MCP_SECRET>   MCP server (streamable HTTP) that Claude connects to
//   /board/sync         the board checks in here every few seconds
//                       (Authorization: Bearer <BOARD_TOKEN>)
//
// Commands from Claude are queued in a Durable Object; the board picks them up
// on its next check-in, runs them, and reports results on the following one.

const PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"];
const RESULT_WAIT_MS = 20000;
const ONLINE_WINDOW_MS = 20000;
const MAX_QUEUE = 20;
const POLL_SECONDS = 3;
const MAX_HOLD_MS = 50000;   // long-poll: hold an idle board check-in this long

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

const TOOLS = [
  {
    name: "get_programming_guide",
    description: "How to write programs for the Stellar Unicorn LED board (program contract, drawing API, buttons, time). Read this before writing a new program.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    annotations: { readOnlyHint: true },
  },
  {
    name: "get_board_status",
    description: "Whether the board is online, what is playing, the power-on default, the list of programs, the last error and brightness.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
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
      properties: { name: { type: "string" } },
      required: ["name"],
      additionalProperties: false,
    },
  },
  {
    name: "stop_program",
    description: "Stop the current program (the board shows its IP address).",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
  },
  {
    name: "set_default_program",
    description: "Choose which program plays when the board powers on.",
    inputSchema: {
      type: "object",
      properties: { name: { type: "string" } },
      required: ["name"],
      additionalProperties: false,
    },
  },
  {
    name: "get_program_source",
    description: "Read the source code of a program on the board, e.g. to edit it.",
    inputSchema: {
      type: "object",
      properties: { name: { type: "string" } },
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
      properties: { name: { type: "string" } },
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
      properties: { value: { type: "number", minimum: 0, maximum: 1 } },
      required: ["value"],
      additionalProperties: false,
    },
  },
];

const INSTRUCTIONS =
  "These tools control a Pimoroni Stellar Unicorn, a 16x16 RGB LED matrix on the user's wall. " +
  "To show something new, call get_programming_guide (once per conversation), write a program that " +
  "follows its contract, and send it with upload_program. If the result is an error traceback, fix " +
  "the code and upload again under the same name. To change an existing program, read it with " +
  "get_program_source first.";

// ---------------------------------------------------------------------------
// Durable Object: holds the command queue and the board's last status
// ---------------------------------------------------------------------------

export class Board {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.waiters = new Map();
    this.wakeBoard = null;
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/sync") return this.sync(await request.json());
    if (url.pathname === "/command") return this.command(await request.json());
    if (url.pathname === "/status") return Response.json(await this.status());
    return new Response("not found", { status: 404 });
  }

  async status() {
    const s = await this.state.storage.get(["status", "lastSeen", "queue"]);
    const lastSeen = s.get("lastSeen") || 0;
    const age = lastSeen ? Date.now() - lastSeen : null;
    return {
      online: !!this.wakeBoard || (age !== null && age < ONLINE_WINDOW_MS),
      last_seen_seconds_ago: this.wakeBoard ? 0 : age === null ? null : Math.round(age / 1000),
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
    let queue = (await this.state.storage.get("queue")) || [];
    const hold = Math.min(Number(body.wait) || 0, MAX_HOLD_MS / 1000) * 1000;
    if (!queue.length && hold > 0) {
      // long-poll: keep the connection open until a command arrives or time runs out
      if (this.wakeBoard) this.wakeBoard();
      await new Promise((resolve) => {
        const timer = setTimeout(() => { this.wakeBoard = null; resolve(); }, hold);
        this.wakeBoard = () => { clearTimeout(timer); this.wakeBoard = null; resolve(); };
      });
      await this.state.storage.put("lastSeen", Date.now());
      queue = (await this.state.storage.get("queue")) || [];
    }
    if (queue.length) await this.state.storage.put("queue", []);
    return Response.json({ commands: queue, poll: POLL_SECONDS, long_poll: true });
  }

  async command(cmd) {
    cmd.id = crypto.randomUUID();
    const queue = (await this.state.storage.get("queue")) || [];
    queue.push(cmd);
    while (queue.length > MAX_QUEUE) queue.shift();
    await this.state.storage.put("queue", queue);
    if (this.wakeBoard) this.wakeBoard();

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

async function callTool(name, args, stub) {
  args = args || {};
  const needName = ["upload_program", "run_program", "set_default_program", "get_program_source", "delete_program"];
  if (needName.includes(name) && !NAME_RE.test(args.name || "")) {
    return text("Use a file name like my_program.py (letters, digits, _ - only).", true);
  }
  switch (name) {
    case "get_programming_guide":
      return text(GUIDE);
    case "get_board_status":
      return text(JSON.stringify(await boardCall(stub, "/status"), null, 2));
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

async function handleRpc(msg, stub) {
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
        serverInfo: { name: "stellar-unicorn", title: "Stellar Unicorn", version: "1.0.0" },
        instructions: INSTRUCTIONS,
      });
    }
    case "ping":
      return reply({});
    case "tools/list":
      return reply({ tools: TOOLS });
    case "tools/call": {
      try {
        const out = await callTool(params && params.name, params && params.arguments, stub);
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

async function handleMcp(request, stub) {
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
    const out = (await Promise.all(body.map((m) => handleRpc(m, stub)))).filter(Boolean);
    return out.length ? Response.json(out) : new Response(null, { status: 202 });
  }
  const out = await handleRpc(body, stub);
  return out ? Response.json(out) : new Response(null, { status: 202 });
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

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const stub = env.BOARD.get(env.BOARD.idFromName("board-v2"));

    if (url.pathname === "/board/sync") {
      const auth = request.headers.get("Authorization") || "";
      if (!env.BOARD_TOKEN || !safeEqual(auth, "Bearer " + env.BOARD_TOKEN)) {
        return new Response("unauthorized", { status: 401 });
      }
      if (request.method !== "POST") return new Response("Method Not Allowed", { status: 405 });
      return stub.fetch("https://board/sync", { method: "POST", body: await request.text() });
    }

    const parts = url.pathname.split("/");
    if (parts[1] === "mcp") {
      if (!env.MCP_SECRET || !safeEqual(parts[2] || "", env.MCP_SECRET) || parts.length > 3) {
        return new Response("not found", { status: 404 });
      }
      return handleMcp(request, stub);
    }

    if (url.pathname === "/") return new Response("Unicorn cloud is running.\n");
    return new Response("not found", { status: 404 });
  },
};
