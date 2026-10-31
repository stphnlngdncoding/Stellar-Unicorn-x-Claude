# Changelog

Each release has a branch `release/vMAJOR.MINOR.PATCH` pointing at the code that
shipped; `main` is always the latest release. The major number matches the
launcher's `VERSION` in `board/main.py`, which the board also reports in its status.
See "Versions and rolling back" in the README.

## v6.2.3 / v6.1.2: low storage warning (2026-10-31)

- Once a minute the launcher checks free storage. Below 200 KB (`LOW_FLASH_KB`), an orange border blinks four times every 45 seconds over whatever is playing, until programs are deleted. Programs are typically 5 to 15 KB and the board has about 1.6 MB free, so it's a safety net, not something to expect soon.
- `board/main.py` is v6.2.3; boards on v6.1.1 upgrade with `board/upgrades/install_v612.py`.

## Spaceship polish (2026-10-31)

- `spaceship.py`: the backdrop (stars, suns, planets) is muted and greyer, and dimmed a little more in a thin halo right round the ship, so the ship stands out. Planets come in many colour schemes and sizes, often with one or two moons, and a sun follows each round of six planets. The ship is brighter. New Settings: background brightness, colour drain and halo dimming.

## v6.2.2 / v6.1.1: smooth program starts (2026-10-31)

Starting a program from Claude or the Remote used to freeze it twice for about half a second, about 0.8 s and 1.7 s in (measured on the board). Each freeze was the board setting up a secure connection to the cloud: one to send back the result, one to wait for the next command.

- The result now rides along on the next long poll, so it's one connection instead of two. The relay already handled both in one request; no Worker change.
- A small spinner plays while that connection is made, then the program starts from t = 0, so the stutter happens on the spinner instead of the animation.
- `board/main.py` is v6.2.2. Boards on v6.1 can upgrade over the air with `board/upgrades/install_v611.py` (6.1 → 6.1.1).
- Still there: the long poll renews every 50 s, which costs one ~0.5 s pause each time.
- `spaceship.py`: the ship is two pixels tall, drifts forwards and backwards, and no longer jitters between dodges (it picks a clear lane and holds it).

## Starfall and spaceship (2026-10-31)

- **`starfall.py`**: twinkling stars over dark hills, shooting stars with fading tails, golden fireballs and meteor showers.
- **`spaceship.py`**: a little ship flies through parallax stars, swerving around asteroids, while a sun, gas giant, ringed planet, icy world and cratered moon drift by in the background.
- `fireflies.py`: lit fireflies stay lit, glimmer and zip about; new PACE, LIT_S and LIT_SPEED settings. Both new programs have Settings in the Remote.

## Program settings in the Remote (2026-10-31)

- **Settings** in the Unicorn Remote (artifact and `local/`): a Settings button on the now-playing card and a Settings mode for the program tiles. Each of 21 programs gets sliders (two for a range like "seconds between food") and, where it fits, buttons, for its adjustable constants. *Play with these settings* rewrites those lines in the program on the board and starts it; *Defaults* restores the shipped values. Every slider range was run at both ends in the simulator.
- `antfarm.py`: slower ants (0.3 s per step).
- `morph.py` in the repo was missing its `global` line in `setup()` (the board's copy had it).

## Fireflies and ant farm (2026-10-31)

- **`fireflies.py`**: fireflies with their own colours and three depths drift over a night meadow and blink in bursts of two to four, with an occasional flash wave across the board.
- **`antfarm.py`**: ants dig tunnels, carry sand up to a mound, fetch food for the queen, and her eggs hatch into new ants; a fresh farm starts when the sand is half dug out.
- `life2.py`: no fading; cells switch on and off instantly.

## Life v2 (2026-10-31)

- **`life2.py`**: rounds take turns. A mirror-symmetric still life (six found with a SAT solver) glows for 10 s, then a single dot drops in and breaks it apart; next, a fleet of gliders and lightweight spaceships flies around a wrapping board until they collide. A round ends when the world is empty, frozen or flipping between two states. Half the speed of `life.py`, with streaming rainbow colours. The Remote lists it under Games.

## v6.2.1 — Local mode (2026-10-31)

- **`local/`: run everything without the Cloudflare Worker.** `unicorn_mcp.py` is a stdio MCP server (Python standard library only) with the same nine tools as the cloud connector, talking to the board's LAN API. `serve.py` serves `remote.html`, the Unicorn Remote, on `localhost:8765` and relays its calls to the board. Works on the same Wi-Fi only; see `local/README.md`. No board changes: the launcher already runs without `_cloud.json`.
- New programs since the cleanup: `waterjet.py`, `sand.py`, `tetris.py`; `life.py` rewritten with integer buffers. The Remote lists sand and tetris.

## Repo cleanup (2026-10-29)

- Removed the Level Up habit-tracker integration (`board/levelup/`) and `board/programs/rotation.py`, which played its dragon. The app no longer talks to the board. Playlists and one-shot programs in the v6.2 launcher are unchanged; the examples now use regular programs. The removed files are still on the `release/v6.2.0` branch.

## v6.2.0 (2026-10-25)

Playlists, one-shot programs, and the Level Up habit tracker on the wall.

- **Playlists.** A `.py` file with `PLAYLIST`, `SECONDS` and an optional `NIGHT` time slot rotates programs on the clock and survives restarts (resume and power-on default both work with playlists). Broken items are skipped.
- **One-shot programs.** `DURATION = <seconds>` makes a program play once, then the board returns to what was playing before.
- **Saving without running** a program that's on screen now swaps in the new version instead of stopping it, and keeps the playlist going. Deleting a playlist item keeps the playlist going.
- Status reports `playlist` and `oneshot`; the board reports `"version": "6.2"`.
- **Level Up integration** (`board/levelup/`): avatar, X Effect card, check-off celebration and level-up fanfare templates, plus the page module that fills them in and uploads them.
- `board/programs/rotation.py`: the dragon, Life and plasma, one hour each, X Effect card from 10 to 11 PM.

## v6.1.0 (2026-10-25)

Fixes the board freezing (screen stuck, offline) while the Game of Life runs.

- **Clean restart when memory can't be recovered.** Each failed secure connection leaks memory that only a restart frees, so pausing and parking the program weren't enough. If the board is still out of memory 20 seconds after the first failure, it restarts and resumes the same program.
- Parking a program for memory no longer forgets it, so it's the one that resumes.
- **Memory-friendly Game of Life.** `life.py` allocates all buffers once and reuses them (double-buffered grid, precomputed neighbours, a precomputed pen table) instead of creating new lists, tuples and pens every frame, so it no longer fragments the heap.
- The board reports `"version": "6.1"`.

## v6.0.0 (2026-10-25)

Self-healing board.

- **Hardware watchdog.** `boot.py` arms the RP2 watchdog via `board/_wd.py`. While the launcher runs, the watchdog is only fed while the display loop keeps ticking, so a full freeze (for example, a network call blocking everything mid-handshake) resets the chip within about 8 seconds. After Ctrl-C in Thonny the watchdog is fed unconditionally, so the REPL stays usable.
- **Resume after recovery.** The launcher remembers the running program (`_resume`) and resumes it after a watchdog or self-heal restart, instead of falling back to the power-on default.
- **Wi-Fi reconnect.** When a check-in fails and Wi-Fi is down, the launcher reconnects.
- **Last-resort restart.** After 5 minutes without cloud contact, the board restarts cleanly and resumes its program.
- `boot.py` is protected from uploads, like `main.py` and `secrets.py`.

## v5.0.0 (2026-10-25)

- Low-memory recovery: `gc.collect()` before each check-in. On ENOMEM the launcher pauses the animation and retries; after three failures it stops the program, reconnects, then restarts the program.
- Cloud Worker with long-polling (one held connection instead of polling).
- `cloud/setup.sh`, example programs, README and `.gitignore`.
