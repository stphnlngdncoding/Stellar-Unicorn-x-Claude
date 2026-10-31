# Stellar Unicorn × Claude guide

The details behind the [README](README.md): how the system works, manual setup, writing programs, recovery features, versions and security.

- [How it works](#how-it-works)
- [Repository layout](#repository-layout)
- [Manual setup](#manual-setup)
- [Connector tools](#connector-tools)
- [Writing programs](#writing-programs)
- [On your Wi-Fi](#on-your-wi-fi)
- [Buttons](#buttons)
- [Troubleshooting](#troubleshooting)
- [Low-memory recovery](#low-memory-recovery)
- [Self-healing](#self-healing)
- [Versions and rolling back](#versions-and-rolling-back)
- [Updating the launcher](#updating-the-launcher)
- [Other Unicorns](#other-unicorns)
- [Security notes](#security-notes)

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

## Repository layout

```
board/
  main.py            # launcher: runs programs, LAN web UI, cloud check-in
  boot.py            # arms the hardware watchdog at power-on
  _wd.py             # watchdog helper used by boot.py and main.py
  secrets.example.py # copy to secrets.py and add your Wi-Fi details
  cloud.example.json # copy to _cloud.json and add your Worker URL + board token
  programs/          # example programs (life, lava lamp, fractal, warp, spaceship, ...)
  upgrades/          # over-the-air launcher upgrades (install_v*.py)
remote/
  unicorn-remote.html # the Unicorn Remote artifact app (see below)
local/               # no-Cloudflare alternative, Python only (see local/README.md)
  unicorn_mcp.py     # local MCP server for Claude Desktop / Claude Code
  serve.py           # serves remote.html on localhost and relays to the board
  remote.html        # the Unicorn Remote, talking to the board over Wi-Fi
cloud/
  src/worker.js      # Cloudflare Worker + Durable Object + MCP server
  setup.sh           # one-command deploy: generates secrets, writes board/_cloud.json
  wrangler.toml
  package.json
```

**Never commit `secrets.py`, `_cloud.json`, or your tokens.** Add them to `.gitignore`:

```gitignore
board/secrets.py
board/_cloud.json
cloud/.dev.vars
cloud/connector-url.txt
cloud/deploy.log
node_modules/
.wrangler/
```

(The included `.gitignore` already does this.)

## Manual setup

`cloud/setup.sh` does steps 1, 2 and the `_cloud.json` part of step 3 for you. These are the same steps by hand.

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
5. Copy `main.py`, `boot.py`, `_wd.py`, `secrets.py`, `_cloud.json` and any programs from `board/programs/` to the board. For each file, open it and choose **File → Save as… → Raspberry Pi Pico**, keeping the same name.
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

### Playlists and one-shot programs (v6.2+)

**Playlists** are `.py` files with no `frame()` that list other programs:

```python
PLAYLIST = ["plasma.py", "goo.py", "life.py"]
SECONDS = 3600                                          # each one plays this long
NIGHT = {"from": 22, "to": 23, "program": "lava_lamp.py"}   # optional time slot
```

Run one like any program, or make it the power-on default. Items change on the clock (every `SECONDS`, aligned to the hour for 3600), so a restart picks up where it was. During the `NIGHT` hours (local time) the night program plays instead. A program that errors is skipped. Saving a new version of a playlist item (upload with `run: false`) swaps it in without stopping the playlist.

**One-shot programs** set `DURATION = <seconds>` at the top. They play that long, then the board goes back to whatever was playing before, playlist included. Good for celebrations and alerts.

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

## Low-memory recovery

The Pico has a few hundred KB of RAM, and opening a secure connection to the cloud needs a sizable block of it. A program that allocates a lot while it runs (the Game of Life, for example) can fragment memory until the TLS handshake fails with `OSError(12)` (ENOMEM). If nothing handled that, the board would drop offline until it was power-cycled.

The launcher (v5 and later) recovers on its own:

1. It runs `gc.collect()` before every check-in.
2. If a check-in fails with ENOMEM, it **pauses the animation** (the last frame stays on screen) and retries a moment later, so the program isn't allocating while the connection is being set up.
3. After three ENOMEM failures in a row, it **stops the program** to free its memory, reconnects, then **restarts the same program** automatically.
4. If it's still out of memory 20 seconds after the first failure (failed connections leak memory that only a restart frees), it **restarts the board** and resumes the same program (v6.1+).

When writing your own programs, you can help by creating pens and lists in `setup()` and reusing them rather than allocating new ones every frame.

## Unicorn Remote app

`remote/unicorn-remote.html` is a claude.ai artifact page that controls the board through the same `stellar1` connector: it shows what's playing and whether the board is online, and lets you play or stop any program, choose the power-on program, set the brightness, and build a rotation: pick programs, drag them into order, choose how often to switch, and start it. Programs are grouped (Calm, Lively, Games, Music, Classics); anything it doesn't know yet shows up under Other.

The rotation is saved on the board as `board/programs/rotation.py`. It's a normal program that runs the others itself, so it works with any launcher version. Programs change on the clock, so it carries on where it was after a restart. Old-style programs are skipped.

**Settings.** The Settings button on the now-playing card (or the Settings mode above the tiles) opens sliders and buttons for that program's adjustable constants: speeds, counts, timings, colours. A setting with a range, like "seconds between food", gets two sliders. *Play with these settings* rewrites those constant lines in the program's source on the board and starts it, *Save without playing* just saves, and *Defaults* puts back the values it ships with. The sliders for each program, and their safe ranges, are in `TUNE` in the script; to make a new program adjustable, add an entry there for each `NAME = value` line near the top of the program.

To publish your own copy, ask Claude to publish the file as an artifact that declares the `mcp` capability for `stellar1` with the tools `get_board_status`, `run_program`, `stop_program`, `set_default_program`, `set_brightness`, `upload_program` and `get_program_source`. The first time you open it, claude.ai asks you to allow the connector for the page. To add a new program's name, colours and group, add a line to `CAT` at the top of the script.

## Self-healing

Since v6, the board recovers from freezes and network trouble without anyone touching it:

- **Watchdog.** `boot.py` arms the chip's hardware watchdog (`_wd.py`). While the launcher runs, the watchdog is only fed while the display loop keeps ticking. If the whole board locks up, it resets itself within about 8 seconds.
- **Resume.** After a watchdog or self-heal restart, the board resumes the program that was playing instead of the power-on default.
- **Wi-Fi reconnect.** If a check-in fails because Wi-Fi dropped, the launcher reconnects.
- **Last resort.** After 5 minutes without reaching the cloud, the board restarts cleanly.

**Thonny note.** Pressing Stop (Ctrl-C) switches the watchdog to always-fed mode, so the REPL keeps working. A soft reboot re-runs `boot.py`, which also feeds the watchdog unconditionally. If you ever need to work on the board with no watchdog at all, delete `boot.py` and power-cycle the board.

## Versions and rolling back

Every release gets a branch named `release/vX.Y.Z` (`release/v5.0.0`, `release/v6.0.0`, …) pointing at the exact code that shipped, and [CHANGELOG.md](CHANGELOG.md) lists what changed in each. `main` is always the latest release. The major version number matches `VERSION` in `board/main.py`, which the board reports in `get_board_status`.

To roll the board back to an earlier release:

```bash
git fetch origin
git checkout origin/release/v5.0.0 -- board/     # restores that release's board files
```

Then copy them to the board, either over USB with Thonny, or by asking Claude to install that version through the connector (see below). When rolling back from v6 to v5, also delete `boot.py` and `_wd.py` from the board.

The board also keeps the previous launcher as `main_v<N>.py` after each over-the-air update, so a one-step rollback only needs renaming it back to `main.py`.

## Updating the launcher

`main.py` and `secrets.py` are protected from the web UI and the connector, so a stray upload can't break the board. To update the launcher without USB, upload the new launcher under another name (such as `main_next.py`) plus a small old-style installer program that renames it to `main.py` and calls `machine.reset()`, then run the installer. Over USB, just replace `main.py` in Thonny.

## Other Unicorns

The same design works on the Galactic (53×11) and Cosmic (32×32) Unicorns. Swap the `stellar` / `StellarUnicorn` / `DISPLAY_STELLAR_UNICORN` imports for `galactic` / `GalacticUnicorn` / `DISPLAY_GALACTIC_UNICORN` (or the Cosmic equivalents), and update the sizes in the programming guide in `worker.js`.

## Security notes

- Two secrets protect the system: the **board token** (board ↔ Worker) and the **MCP secret** (Claude ↔ Worker). Rotate either one with `wrangler secret put`; for the board token, update `_cloud.json` on the board too.
- Programs are arbitrary MicroPython running on your board. The worst a leaked connector URL allows is someone else controlling your lights, but don't leak it.
- The board skips TLS certificate verification when it connects to the Worker, which keeps memory use low on the Pico. The board token still authenticates every request. For stricter setups, enable certificate verification in `cloud_post()`.
