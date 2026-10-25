# Changelog

Each release has a branch `release/vMAJOR.MINOR.PATCH` pointing at the code that
shipped; `main` is always the latest release. The major number matches the
launcher's `VERSION` in `board/main.py`, which the board also reports in its status.
See "Versions and rolling back" in the README.

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
