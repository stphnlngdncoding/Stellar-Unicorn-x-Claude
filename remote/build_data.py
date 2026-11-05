"""Fill in the Remote's per-board data from the programs themselves.

    python3 remote/build_data.py

- Settings sliders: remote/tune_spec.json (Stellar) and
  remote/tune_spec_galactic.json (Galactic) list each program's adjustable
  constants as [NAME, label, min, max, step] or [NAME, label, "choice", [labels]].
  The default ("d") is read from the program file, so it always matches.
- The Marquee card's template: board/programs/marquee.py and
  board/galactic/programs/marquee.py.

Writes into remote/unicorn-remote.html (both boards) and local/remote.html
(Stellar only), then rebuilds the phone app (remote/build_app.py).
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = {"stellar": os.path.join(ROOT, "board", "programs"),
        "galactic": os.path.join(ROOT, "board", "galactic", "programs")}
SPECS = {"stellar": os.path.join(ROOT, "remote", "tune_spec.json"),
         "galactic": os.path.join(ROOT, "remote", "tune_spec_galactic.json")}


def tune_table(board):
    if not os.path.exists(SPECS[board]):
        return {}
    spec = json.load(open(SPECS[board]))
    out = {}
    for prog, ctrls in spec.items():
        path = os.path.join(DIRS[board], prog)
        if not os.path.exists(path):
            print("  (no %s for %s yet; skipped)" % (prog, board))
            continue
        src = open(path).read()
        rows = []
        for c in ctrls:
            m = re.search(r"^%s\s*=\s*(\([^)\n]*\)|-?[0-9.]+)" % c[0], src, re.M)
            if not m:
                sys.exit("%s/%s has no %s" % (board, prog, c[0]))
            raw = m.group(1)
            d = [json.loads(x.strip()) for x in raw[1:-1].split(",")] if raw[0] == "(" else json.loads(raw)
            if isinstance(d, float) and d.is_integer():
                d = int(d)
            if isinstance(d, list):
                d = [int(x) if float(x).is_integer() else x for x in d]
            if c[2] == "choice":
                rows.append({"k": c[0], "l": c[1], "opts": c[3], "d": d})
            else:
                rows.append({"k": c[0], "l": c[1], "min": c[2], "max": c[3], "step": c[4], "d": d})
        out[prog] = rows
    return out


def js(v):
    return json.dumps(v, separators=(",", ":")).replace("</", "<\\/")


def marquee(board):
    p = os.path.join(DIRS[board], "marquee.py")
    return open(p).read() if os.path.exists(p) else None


def main():
    tunes = {b: tune_table(b) for b in DIRS}
    mq = {b: marquee(b) for b in DIRS}
    mq["galactic"] = mq["galactic"] or mq["stellar"]

    f = os.path.join(ROOT, "remote", "unicorn-remote.html")
    s = open(f).read()
    s, n1 = re.subn(r"  const TUNES = \{ stellar: .*?, galactic: .*? \};\n",
                    lambda m: "  const TUNES = { stellar: %s, galactic: %s };\n" % (js(tunes["stellar"]), js(tunes["galactic"])), s, count=1)
    s, n2 = re.subn(r"  const MQ_SRCS = \{ stellar: .*?, galactic: .*? \};\n",
                    lambda m: "  const MQ_SRCS = { stellar: %s, galactic: %s };\n" % (js(mq["stellar"]), js(mq["galactic"])), s, count=1)
    assert n1 == 1 and n2 == 1, "couldn't find TUNES / MQ_SRCS in the Remote"
    open(f, "w").write(s)

    f = os.path.join(ROOT, "local", "remote.html")
    s = open(f).read()
    s, n1 = re.subn(r"  const TUNE = .*?;\n", lambda m: "  const TUNE = %s;\n" % js(tunes["stellar"]), s, count=1)
    s, n2 = re.subn(r"  const MQ_SRC = .*?;\n", lambda m: "  const MQ_SRC = %s;\n" % js(mq["stellar"]), s, count=1)
    assert n1 == 1 and n2 == 1, "couldn't find TUNE / MQ_SRC in local/remote.html"
    open(f, "w").write(s)

    print("Settings: %d Stellar programs, %d Galactic programs" % (len(tunes["stellar"]), len(tunes["galactic"])))
    subprocess.check_call([sys.executable, os.path.join(ROOT, "remote", "build_app.py")])


if __name__ == "__main__":
    main()
