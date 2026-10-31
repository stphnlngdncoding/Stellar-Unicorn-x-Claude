# Over-the-air launcher upgrades

An upgrade is an ordinary program named `install_v*.py`. Upload and run it
(from Claude or the Unicorn Remote) and it patches `main.py` on the board,
keeps the old launcher as a backup, shows a green tick and restarts the
board. The launcher deletes `install_v*.py` files when it starts, so it
can't run twice. If `main.py` isn't exactly the version the upgrade was made
for, it changes nothing and shows a red cross.

| File | From → to | What it does |
|---|---|---|
| `install_v611.py` | 6.1 → 6.1.1 | One cloud connection per command instead of two, and a loading spinner while it connects, so newly started programs don't stutter. Backup: `main_v61.py`. |
| `install_v612.py` | 6.1.1 → 6.1.2 | Blinks an orange border every 45 seconds when free storage drops below 200 KB. Backup: `main_v611.py`. |

To roll back, rename the backup to `main.py` in Thonny.
