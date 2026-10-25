# Hardware watchdog for the Stellar Unicorn launcher. Imported by boot.py.
# Normally the timer feeds the watchdog unconditionally (safe for Thonny/REPL).
# In strict mode (switched on by the launcher) it only feeds while tick() keeps
# being called, so a frozen board resets itself within ~8 seconds.
import machine, time

TIMEOUT_MS = 8000     # RP2 maximum is about 8.3 s
STALL_MS = 6000       # no tick() for this long in strict mode = frozen

wdt = machine.WDT(timeout=TIMEOUT_MS)
_state = [time.ticks_ms(), False]     # last tick, strict mode

def _feed(_):
    if not _state[1] or time.ticks_diff(time.ticks_ms(), _state[0]) < STALL_MS:
        wdt.feed()

timer = machine.Timer(period=1000, mode=machine.Timer.PERIODIC, callback=_feed)

def tick():
    _state[0] = time.ticks_ms()

def strict(on):
    _state[0] = time.ticks_ms()
    _state[1] = bool(on)
