# Arms the hardware watchdog early; the launcher (main.py) takes it from here.
try:
    import _wd
except Exception as e:
    print("watchdog not started:", e)
