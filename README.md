# Stellar Unicorn × Claude

Prompt a [Pimoroni Stellar Unicorn](https://shop.pimoroni.com/products/space-unicorns) (16×16 RGB LED matrix) from Claude, from anywhere.

> "Put the Game of Life on the board."
> "Make it say *good morning* in rainbow letters."
> "Slow it down and add sparkles."

Claude writes a MicroPython program, sends it to the board through a custom connector, and the board starts it within a second. If the code crashes, the traceback comes straight back to Claude, which fixes the code and sends it again.

## How it works

```
Claude ──MCP──▶  Cloudflare Worker  ◀──HTTPS long-poll──  Stellar Unicorn
 (claude.ai        + Durable Object                        (launcher main.py
  connector)       (command queue)                          on your Wi-Fi)
```

- **The board can't be reached from the internet**, so it *pulls*: the launcher holds an HTTPS request open to the Worker (about 50 seconds at a time). When Claude sends a command, the Worker answers that request immediately, the board runs the command, and the result goes back on the next request.
- **The Worker** is both the MCP server Claude talks to and the relay the board checks in with. A single Durable Object holds the command queue and the board's last status.
- **The launcher** (`main.py` on the board) owns the main loop. It runs one program at a time, serves a small web UI on your LAN, and handles the cloud check-in, brightness and sleep buttons.

Holding one connection open (instead of polling) matters on this hardware. A TLS handshake keeps the Pico busy for a noticeable moment, so polling every few seconds makes animations hitch.

## What you need

- A Stellar Unicorn. Current boards have a Pico 2 W; the original Pico W boards should also work. Galactic and Cosmic Unicorns need small changes (see [Other Unicorns](#other-unicorns)).
- A USB-C cable that carries data, for the one-time setup
- [Thonny](https://thonny.org) (free) for copying files to the board
- A 2.4 GHz Wi-Fi network
- A free [Cloudflare](https://cloudflare.com) account
- [Node.js](https://nodejs.org) (LTS) on your computer, for deploying the Worker
- A Claude plan that supports custom connectors

## Repository layout

```
board/
  main.py            # launcher: runs programs, LAN web UI, cloud check-in
  secrets.example.py # copy to secrets.py and add your Wi-Fi details
  cloud.example.json # copy to _cloud.json and add your Worker URL + board token
  programs/          # example programs (life.py, rainbow.py, ...)
cloud/
  src/worker.js      # Cloudflare Worker + Durable Object + MCP server
  wrangler.toml
  package.json
```

**Never commit `secrets.py`, `_cloud.json`, or your tokens.** Add them to `.gitignore`:

```gitignore
board/secrets.py
board/_cloud.json
cloud/.dev.vars
cloud/connector-url.txt
node_modules/
```

## Setup

### 1. Generate two secrets

```bash
# board token: the board uses this to authenticate with the Worker
python3 -c "import secrets; print(secrets.token_urlsafe(24))"

# MCP secret: becomes part of the connector URL
python3 -c "import secrets; print(secrets.token_hex(16))"
```

Keep both somewhere safe (a password manager is ideal).

### 2. Deploy the Worker

```bash
cd cloud
npm install
npx wrangler login
npx wrangler deploy
printf '%s' '<board token>' | npx wrangler secret put BOARD_TOKEN
printf '%s' '<MCP secret>'  | npx wrangler secret put MCP_SECRET
```

`wrangler deploy` prints your Worker's address, something like `https://unicorn-cloud.<you>.workers.dev`. Opening it in a browser should show `Unicorn cloud is running.`

The free Workers plan covers this comfortably. With long-polling, the board makes roughly 1–2 requests a minute when idle.

### 3. Set up the board

1. Plug the Unicorn into your computer and open Thonny. In the bottom-right corner, choose **MicroPython (Raspberry Pi Pico)**, then turn on **View → Files**.
2. Click **Stop** so the board's files appear. **Back up the original `main.py`** (Pimoroni's demo) by right-clicking it and choosing **Download**.
3. Create `secrets.py` from `secrets.example.py`:
   ```python
   WIFI_SSID = "your network"
   WIFI_PASSWORD = "your password"
   ```
4. Create `_cloud.json` from `cloud.example.json`:
   ```json
   {"url": "https://unicorn-cloud.<you>.workers.dev", "token": "<board token>"}
   ```
5. Copy `main.py`, `secrets.py`, `_cloud.json` and any programs from `board/programs/` to the board. For each file, open it and choose **File → Save as… → Raspberry Pi Pico**, keeping the same name.
6. Unplug the board and plug it back in. It shows `WiFi...` in amber, scrolls its IP address in cyan, then plays the default program (if one is set).

From then on, the board only needs power. Any USB charger rated at 5 V and 1 A or more works.

### 4. Add the connector to Claude

In claude.ai, add a **custom connector** with this URL:

```
https://unicorn-cloud.<you>.workers.dev/mcp/<MCP secret>
```

To avoid approval prompts on every action, open the connector's settings and set its tools to **Always allow**.

**Treat the connector URL like a password.** Anyone who has it can run code on your board. To change it, set a new `MCP_SECRET` with `wrangler secret put` and update the connector.

### 5. Try it

In a chat with the connector enabled:

> What's on my Unicorn right now?
> Put a slow rainbow on the board.

## Connector tools

| Tool | What it does |
| --- | --- |
| `get_programming_guide` | The program contract and drawing API, for Claude to read before writing code |
| `get_board_status` | Online state, what's playing, the default program, the program list, the last error and brightness |
| `upload_program` | Save a program to the board, start it (by default) and optionally make it the default. Returns `Running <name>` or a traceback |
| `run_program` | Start a program that's already on the board |
| `stop_program` | Stop playback (the board shows its IP address) |
| `set_default_program` | Choose what plays at power-on |
| `get_program_source` | Read a program's code, for editing |
| `delete_program` | Remove a program |
| `set_brightness` | 0 (off) to 1 (full) |

## Writing programs

Programs don't loop forever. The launcher owns the main loop and calls your functions:

```python
def setup(su, g):          # optional, runs once
    global x, pen
    x = 0
    pen = g.create_pen(255, 120, 0)

def frame(su, g, t):       # draw one frame; t = seconds since start
    global x
    g.set_pen(g.create_pen(0, 0, 0))
    g.clear()
    g.set_pen(pen)
    g.pixel(x, 7)
    x = (x + 1) % 16
    return 0.05            # optional: seconds until the next frame
```

Rules:

- `su` is the `StellarUnicorn` and `g` is the `PicoGraphics` instance. Don't create your own, and don't call `su.update()`; the launcher does both.
- No `while True`, `time.sleep()` or network calls inside programs.
- Keep state in module globals, and create pens once in `setup()`.
- The display is 16×16: `x` and `y` both run from 0 to 15, starting at the top left.
- Buttons A–D are free for programs (`su.is_pressed(StellarUnicorn.SWITCH_A)`). The brightness and sleep buttons belong to the launcher.
- `local_time()` is available as a global. It returns the current US Pacific time (daylight saving included) as a `time.localtime`-style tuple. Change the offsets in `main.py` for other time zones.
- If `setup()` or the first `frame()` raises an error, the upload result contains the traceback.

**Old-style programs** with their own `while True` loop (such as Pimoroni's examples) still run. The launcher restarts the board into them, and the web UI and cloud connection stay off until you press the **sleep** button, which restarts back into the launcher. Converting them to `setup`/`frame` is usually a few lines of change.

## On your Wi-Fi

- **Web UI:** open `http://<board IP>/` on any device on the same network to upload, run, stop, delete or set the default program. It has no password, so keep it on a trusted network.
- **API:** `GET /api/status`, `POST /upload?name=x.py&run=1` (raw file as the body), `POST /run|/default|/delete?name=x.py`, `POST /stop`, `POST /brightness?value=0.4`.
  ```bash
  curl --data-binary @life.py "http://<board IP>/upload?name=life.py&run=1"
  ```

## Buttons

| Button | Action |
| --- | --- |
| Brightness + / − | Adjust brightness (works in every program) |
| Sleep | Turn the display off and on. For an old-style program, return to the launcher |
| A–D | Up to the running program |

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Red `WiFi failed` | Wrong SSID or password, or a 5 GHz-only network |
| Red `No secrets.py` | `secrets.py` isn't on the board |
| The connector says the board was never seen | Check that `_cloud.json` is on the board and the token matches `BOARD_TOKEN` |
| Animations hitch every few seconds | The board isn't long-polling. Check that the deployed Worker answers `/board/sync` with `"long_poll": true` (see below) |
| Thonny doesn't show the board's files | Click **Stop** first. A running program keeps the board busy |
| The board shows up as a drive called `RPI-RP2` / `RP2350` | It's in bootloader mode. Unplug and replug it without holding any buttons |

**Deploying Worker changes:** a Durable Object can keep running its old code after `wrangler deploy` while the board keeps it busy. If a change doesn't seem to take effect, rename the object in `worker.js` (for example, `idFromName("board")` → `idFromName("board-v2")`) and deploy again. Only transient state is lost.

## Updating the launcher

`main.py` and `secrets.py` are protected from the web UI and the connector, so a stray upload can't break the board. To update the launcher without USB, upload the new launcher under another name (such as `main_next.py`) plus a small old-style installer program that renames it to `main.py` and calls `machine.reset()`, then run the installer. Over USB, just replace `main.py` in Thonny.

## Other Unicorns

The same design works on the Galactic (53×11) and Cosmic (32×32) Unicorns. Swap the `stellar` / `StellarUnicorn` / `DISPLAY_STELLAR_UNICORN` imports for `galactic` / `GalacticUnicorn` / `DISPLAY_GALACTIC_UNICORN` (or the Cosmic equivalents), and update the sizes in the programming guide in `worker.js`.

## Security notes

- Two secrets protect the system: the **board token** (board ↔ Worker) and the **MCP secret** (Claude ↔ Worker). Rotate either one with `wrangler secret put`; for the board token, update `_cloud.json` on the board too.
- Programs are arbitrary MicroPython running on your board. The worst a leaked connector URL allows is someone else controlling your lights, but don't leak it.
- The board skips TLS certificate verification when it connects to the Worker, which keeps memory use low on the Pico. The board token still authenticates every request. For stricter setups, enable certificate verification in `cloud_post()`.

## Credits

Built on Pimoroni's MicroPython firmware and PicoGraphics. Assembled in an afternoon with Claude.
