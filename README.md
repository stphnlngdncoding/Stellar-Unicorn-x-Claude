# Stellar Unicorn × Claude

Prompt a [Pimoroni Stellar Unicorn](https://shop.pimoroni.com/products/space-unicorns) (16×16 RGB LED matrix) from Claude, from anywhere.

> "Put the Game of Life on the board."
> "Make it say *good morning* in rainbow letters."
> "Slow it down and add sparkles."

Claude writes a MicroPython program, sends it to the board through a custom connector, and the board starts it within a second. If the code crashes, the traceback comes straight back to Claude, which fixes the code and sends it again.

```
Claude ──MCP──▶  Cloudflare Worker  ◀──HTTPS──  Stellar Unicorn
                 (command relay)                (on your Wi-Fi)
```

The board can't be reached from the internet, so it keeps a connection open to a small Cloudflare Worker, which is also the MCP server Claude talks to. More in [GUIDE.md](GUIDE.md#how-it-works).

## What you need

- A Stellar Unicorn (Pico 2 W or Pico W)
- A USB-C data cable and [Thonny](https://thonny.org), for the one-time setup
- 2.4 GHz Wi-Fi
- A free [Cloudflare](https://cloudflare.com) account and [Node.js](https://nodejs.org)
- A Claude plan with custom connectors

## Setup

1. **Deploy the cloud service.**
   ```bash
   cd cloud
   bash setup.sh
   ```
   It deploys the Worker, generates your secrets, writes `board/_cloud.json` and prints your connector URL.

2. **Set up the board.** Copy `board/secrets.example.py` to `board/secrets.py` and add your Wi-Fi details. In Thonny (interpreter: *MicroPython (Raspberry Pi Pico)*), back up the board's original `main.py`, then save `main.py`, `boot.py`, `_wd.py`, `secrets.py`, `_cloud.json` and any programs from `board/programs/` to the board. Unplug and replug it.

3. **Add the connector.** In claude.ai, add a custom connector with the URL from step 1 and set its tools to *Always allow*. Keep that URL private: anyone with it can control your board.

4. **Try it.** "What's on my Unicorn right now?" or "Put a slow rainbow on the board."

After setup the board only needs USB power. Prefer to do it by hand? See [manual setup](GUIDE.md#manual-setup).

## Example programs

`board/programs/` has ready-made programs: Game of Life, plasma, lava lamp, silk tides, neon tunnel, driftfield, fractal, warp and more. Programs use a simple `setup()` / `frame()` contract; see [writing programs](GUIDE.md#writing-programs).

## More

[GUIDE.md](GUIDE.md) covers the connector tools, the board's local web page, buttons, troubleshooting, self-healing, versions and rollback, and security. [CHANGELOG.md](CHANGELOG.md) lists every release.

Built on Pimoroni's MicroPython firmware and PicoGraphics.
