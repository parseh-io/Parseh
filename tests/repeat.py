#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run one browser suite again and again, to see how often it fails -- and to make it fail on purpose.

A suite that fails now and then and passes when it is run again has a cause nobody has found: a wait for a time
instead of a state, a count taken at one instant, a request that can be answered before it is looked for.  This
finds out how often (a rate, not a feeling), and `--stress` makes the machine slow enough for the fault to show:
the suite and everything it starts (the hub, the browser, ffmpeg) are pinned to a few cores that busy loops also
use, so that every wait in it is a fraction of what it expects.

    python3 tests/repeat.py studio_audio -n 20                  # twenty runs, one after the other, as they are
    python3 tests/repeat.py studio_audio -n 20 --stress 2       # the same on two cores shared with two busy loops
    python3 tests/repeat.py reach -n 6 --env REACH_PARTS=slow   # a suite's own selectors are environment variables
    python3 tests/repeat.py arasaac_door -n 30 --env SECTIONS=g --env ARASAAC_DOOR_WHO=phone

Each run's log is kept in the folder printed first.  Needs `deno` on the path and CHROME_BIN (docs/releasing.md,
"Before you start"); the stress needs `taskset` (Linux).  Exit status 0 when every run was green.
"""
import argparse
import collections
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAD = re.compile(r"FAIL|Error|error:|not ok|timed out", re.I)


def chrome():
    if os.environ.get("CHROME_BIN"):
        return os.environ["CHROME_BIN"]
    found = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome")))
    return found[-1] if found else ""


def cores(want):
    """The last `want` cores of this computer: the ones a person is least likely to be using."""
    total = os.cpu_count() or 1
    want = max(1, min(want, total))
    return ",".join(str(c) for c in range(total - want, total))


def reason(log):
    """The line of a red run that says why: the first FAIL, else the first line that looks like an error."""
    lines = log.splitlines()
    for pattern in (re.compile(r"FAIL"), BAD):
        for line in lines:
            if pattern.search(line):
                return re.sub(r"\s+", " ", line.strip())[:240]
    return "(no line says why; the log's end: %s)" % re.sub(r"\s+", " ", " | ".join(lines[-2:]))[:200]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("suite", help="a suite of tests/, without .mjs (arasaac_door, reach, mobile_pages ...)")
    ap.add_argument("-n", "--runs", type=int, default=10)
    ap.add_argument("--stress", type=int, default=0, metavar="K",
                    help="pin the suite to K cores that K busy loops share (a slow computer); 0 = none")
    ap.add_argument("--cores", default="", help="which cores, like 22,23 (default: the last K)")
    ap.add_argument("--env", action="append", default=[], metavar="NAME=VALUE", help="set for the suite; repeatable")
    ap.add_argument("--timeout", type=int, default=1500, help="seconds a run may take (default 1500)")
    ap.add_argument("--logs", default="", help="where the logs go (default: a new folder in TMPDIR)")
    args = ap.parse_args(argv)

    suite = os.path.join(ROOT, "tests", args.suite + ".mjs")
    if not os.path.isfile(suite):
        sys.exit("no such suite: %s" % suite)
    deno = shutil.which("deno")
    if not deno:
        sys.exit("deno is not on the path (docs/releasing.md, 'Before you start')")
    env = dict(os.environ, NO_COLOR="1")
    if not env.get("CHROME_BIN") and chrome():
        env["CHROME_BIN"] = chrome()
    for item in args.env:
        name, _, value = item.partition("=")
        env[name] = value
    logs = args.logs or tempfile.mkdtemp(prefix="parseh-repeat-%s-" % args.suite)
    os.makedirs(logs, exist_ok=True)

    pin = []
    hogs = []
    if args.stress:
        where = args.cores or cores(args.stress)
        if shutil.which("taskset"):
            pin = ["taskset", "-c", where]
            print("stress: the suite and %d busy loops share cores %s" % (args.stress, where))
        else:
            print("stress: no taskset here, so the %d busy loops are not pinned to the suite's cores" % args.stress)
        for _ in range(args.stress):
            hogs.append(subprocess.Popen(pin + [sys.executable, "-c", "while True: pass"]))
    print("logs: %s" % logs)

    green, why = 0, collections.Counter()
    try:
        for i in range(1, args.runs + 1):
            began = time.time()
            path = os.path.join(logs, "%s-%d.log" % (args.suite, i))
            try:
                with open(path, "w") as out:
                    done = subprocess.run(pin + [deno, "run", "--allow-all", suite], cwd=ROOT, env=env, stdout=out,
                                          stderr=subprocess.STDOUT, timeout=args.timeout)
                code = done.returncode
            except subprocess.TimeoutExpired:
                code = "timeout"
            took = int(time.time() - began)
            if code == 0:
                green += 1
                print("run %d: green (%d s)" % (i, took))
            else:
                text = open(path, errors="replace").read()
                line = reason(text)
                why[line] += 1
                print("run %d: RED, exit %s (%d s): %s" % (i, code, took, line))
            sys.stdout.flush()
    finally:
        for h in hogs:
            h.kill()
    print("\n%s: %d green, %d red of %d" % (args.suite, green, args.runs - green, args.runs))
    for line, n in why.most_common():
        print("  %d x %s" % (n, line))
    return 0 if green == args.runs else 1


if __name__ == "__main__":
    sys.exit(main())
