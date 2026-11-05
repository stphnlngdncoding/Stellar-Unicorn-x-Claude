# Changelog

Each release has a branch `release/vMAJOR.MINOR.PATCH` pointing at the code that
shipped; `main` is always the latest release. The major number matches the
launcher's `VERSION` in `board/main.py`, which the board also reports in its status.
See "Versions and rolling back" in the README.

## Galactic programs and the board switcher (2026-11-05)

- **All 34 programs reworked for the Galactic's 53×11 strip** in `board/galactic/programs/` (the repo's 30 plus Adventure, Fire, Supercomputer and Today from the board, which are now `setup`/`frame` programs, plus a playlist `rotation.py` and a `wide_rainbow.py` test). Scenes became panoramas (World's sun and moon cross the whole strip, the boat sails along a long sea, a long ant farm), ambient fields are stretched to the wide shape (with new `STRETCH`/`OVAL`/`WIDE` settings), Tetris falls sideways, Snake's autopilot now plans around its own tail, Life v2 has six new mirror-symmetric still lifes found for 53×11, and Mirror Life reflects about the middle column. Each was soak-tested in the simulator with every setting at both ends.
- **Board switcher in the Unicorn Remote** (artifact and phone app): Stellar / Galactic at the top, with a dot for whether each is online. Everything on the page (programs, now playing, settings, rotation, marquee) follows the chosen board, and it remembers your choice. On the Galactic, Now playing shows a wide strip.
- Settings for both boards are built from `remote/tune_spec.json` and `remote/tune_spec_galactic.json` by `remote/build_data.py`, which also refreshes the Marquee template and rebuilds the phone app. The local (`local/`) Remote stays Stellar-only.

## v6.3.0: Galactic Unicorn support (2026-11-05)

- **One launcher for both boards.** `board/main.py` checks whether it's on Stellar (16×16) or Galactic (53×11) firmware and sizes its spinner, messages and warnings to fit. On the Galactic it uses the hostname `galactic` and checks in at `/board/sync?board=galactic`. Status reports `model` and `size`.
- **The Worker handles two boards** (connector v1.1): each has its own Durable Object, so its own queue and status; the Stellar keeps its existing one. Every tool takes an optional `board` (default `stellar`, so nothing changes for existing chats and the Remote); `get_programming_guide` has a Galactic version; `get_board_status` mentions the other board. Same token and secret, no new setup in Cloudflare or claude.ai.
- The Stellar stays on v6.1.3 for now; v6.3.0 runs on it too.

## v6.2.4 / v6.1.3: full brightness at start-up (2026-11-03)

- The board starts at full brightness instead of 50%. The brightness buttons, the Remote and Claude can still dim it until the next restart.
- `board/main.py` is v6.2.4; boards on v6.1.2 upgrade over the air with `board/upgrades/install_v613.py`.

## Unicorn Remote on your iPhone (2026-11-03)

- **The Worker serves the Remote as a phone web app** at `/app/<MCP_SECRET>/`: your connector URL with `/mcp/` changed to `/app/`. Add it to the iPhone home screen from Safari and it opens full screen with its own icon, and works from anywhere because it goes through the same command queue as Claude. No new secret; the page sends no referrer and isn't indexed.
- The app uses the same tools as the connector minus `delete_program`. A command sent while the board is offline says it's queued and will run when the board checks back in.
- `remote/build_app.py` builds the app page and icons from the artifact Remote; `cloud/deploy-app.sh` redeploys the Worker (secrets untouched) and prints the app's address. `setup.sh` prints it too.
- Needs a Worker redeploy (`bash cloud/deploy-app.sh`); no board changes.
- The phone app doesn't zoom (no pinch or double-tap zoom, and no zooming in when you tap a text box).
- The Worker can deploy itself from GitHub: connect it under Settings → Build with root directory `cloud`, and every push to `main` redeploys it.

## Remote UX pass (2026-11-01)

- **Programs first on a phone**: the Rotation and Marquee cards fold to a one-line summary ("3 programs · every 10 min", the current message) and remember whether you left them open, so the library starts on the first screen.
- **Sticky library bar** with the Play / Power-on / Rotation / Settings switch and shortcuts to each group. Outside Play mode the hint turns accent-coloured with a *Done* button, and choosing Rotation opens the rotation card.
- Tiles follow the curated order within each group instead of alphabetical.
- Messages are a toast at the bottom of the screen, so they're seen wherever you've scrolled; confirmations fade after a few seconds, errors stay until dismissed.
- Stop and Settings are disabled when they can't do anything; Refresh is now a small icon next to the connection status.
- Settings choices (like World's seven weather options) wrap instead of running off the screen; bigger touch targets for buttons; the rotation number badge no longer covers tile names.

## Remote categories (2026-11-01)

- The Unicorn Remote groups programs by theme instead of Calm / Lively / Games: Outdoors, Space, Ambient, Neon, Physics, Life, Games, Music and Classics (artifact and `local/`).

## Flying saucer (2026-11-01)

- `spaceship.py`: a classic flying saucer (glass dome, silver hull, rim lights chasing round) visits every 25 to 70 seconds. It glides in from either side, hovers with a wobble, often shines a shimmering tractor beam down, then zips off up or down and away. The ship steers clear of it and its beam. C = call the saucer now. New Settings: how often, speed, hover time, beam chance.

## Mirror Life fades and palettes, and Slow Life (2026-11-01)

- `mirrorlife.py`: new cells glow in and dead ones fade away (timed in seconds, so it stays smooth at any speed), and colours come from seven hand-made three-colour palettes (ember, lagoon, neon, citrus, aurora, candy, ice), a different one each round unless you pick one. New Settings for palette, fade in/out and newborn flash.
- **`slowlife.py`**: Mirror Life at a crawl: a generation every 4 seconds, 2.5 s to glow in, 6 s to fade out. In the Remote under Calm.

## Kaleidoscope and Mirror Life (2026-11-01)

- **`kaleidoscope.py`**: pieces of coloured glass tumble in a slowly turning tube, folded by eight mirrors (or four) into a symmetric picture, stained-glass style with dark seams and pieces that glow towards their middles. Every so often the tube is shaken into a new picture. A = shake, B = eight or four mirrors.
- **`mirrorlife.py`**: the Game of Life runs on the left half and is reflected onto the right, from random soups or small seeds by the middle that bloom outwards. Settings can tint the right half differently or have it lag a few generations behind, so the mirror visibly catches up. A = new round, B = pause.
- Both are in the Unicorn Remote with Settings.
- Unicorn Remote: spinners while anything loads (program tiles, Stop, brightness, Settings, Marquee, the connection and rotation status), and buttons are disabled until their command finishes.

## World, and a moon for Fireflies (2026-11-01)

- **`world.py`**: a meadow under the real sky over Marina del Rey (set `LAT`/`LON` for elsewhere). The sun and moon are placed from the board's clock with standard low-precision formulas (about a degree), so they rise, cross and set on time; the moon shows its real phase; the sky glows at dawn and dusk. Weather comes from Open-Meteo over plain HTTP every 15 minutes (each fetch pauses the animation for about a third of a second): clear, cloudy, fog, rain, snow or thunderstorm, eased in gradually. By day butterflies, a hopping bunny and passing birds; at night stars and fireflies. A = fast-forward through a day. Settings: weather (live or fixed), fast time, critter counts, report interval.
- `fireflies.py`: a moon in tonight's real phase, top left (`MOON` setting).

## Boat (2026-10-31)

- **`boat.py`**: a sailboat rides the waves while the weather turns between sunny spells (blue sea, sun, white clouds) and storms (dark sky, slanting rain, whitecaps, the odd lightning flash), with the boat tossed and rolled harder as the sea builds. A = change the weather. Settings in the Remote.

## Hedge Maze (2026-10-31)

- **`maze.py`**: a self-playing maze chase. A firefly collects dew drops in a freshly grown hedge maze while three spiders hunt it; it plans routes it can reach well ahead of the spiders, avoids dead ends, and runs for open ground when cornered. Pink berries give a speed boost. Clearing a maze grows a new one with quicker spiders; three catches and it starts over. In testing it clears a maze roughly every minute and a half and reaches level 3 or 4. A = new maze, B = faster. Settings in the Remote.

## Marquee (2026-10-31)

- **`marquee.py`**: scrolls a message with bobbing letters, soft shadows, dancing colours (rainbow, neon, warm, cool or white) and twinkling sparkles. A = pause.
- **Marquee card in the Unicorn Remote** (artifact and `local/`): type a message, pick colours and speed, press *Show on board* (or Enter). Curly quotes and dashes become plain ones, and characters the board's font can't draw (like emoji) are dropped. The card fills in the message that's on the board. Marquee also has Settings for bounce, sparkles and more.

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
