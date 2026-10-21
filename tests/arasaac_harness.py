#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The server tests/arasaac_door.mjs drives: Parseh's real handler, its real Settings -> Pictograms
(ARASAAC) page and its real routes, on a TEMPORARY arasaac/ tree, with the two hosts the pictograms
come from stood in for (tests/arasaac_fake.py: two-pixel PNGs, a clock of its own).

    python3 tests/arasaac_harness.py               the computer's own browser asking
    python3 tests/arasaac_harness.py --as-phone    a device that has been let in over the Wi-Fi

WHAT IS REAL: the server, the page and every route it posts to, lib/getarasaac.py -- its download, its
resume, its update, its removal, its job and its activity entry -- and the files it leaves.  WHAT STANDS
IN: the two hosts, on 127.0.0.1.  Nothing here reaches a network, and nothing is written outside the
temporary tree (config/ included: the network store is pointed at it).

It reads one JSON command per line on stdin and answers `OK` (or `OK {json}`, or `ERR ...`) after each,
so that a browser test can change the world under an open page:

    {"cmd": "world", "n": 40, "locales": ["en", "fr", "es"], "delay": 0.0}   a new set of pictograms
    {"cmd": "clear"}                      the folder emptied, the job forgotten
    {"cmd": "build", "locales": ["en"], "resolution": 300, "stop_after": 12}   the real download, run here
    {"cmd": "slow", "seconds": 0.02}      how long the host takes over each answer
    {"cmd": "hold"} / {"cmd": "release"}  the pictures wait at the host until released (the lists do not)
    {"cmd": "fail", "pattern": "/2239/", "how": "500", "times": 99}    a misbehaving host (arasaac_fake.World.fail)
    {"cmd": "unfail"}                     it behaves again
    {"cmd": "change", "ids": [3], "picture": true, "add": [99999], "drop": [4]}   ARASAAC moved on
    {"cmd": "reset_stats"}                forget what the hosts were asked so far
    {"cmd": "stats"}                      answers OK {requests, pictures, lists, connections, conditional, files}
    {"cmd": "other_format"}               a manifest of a shape this Parseh does not know
    {"cmd": "retries", "waits": [0, 0, 0]}   how long a failed picture is waited on

Prints `READY {json}` once listening.  SIGTERM or SIGINT removes the temp tree."""
import json
import os
import shutil
import signal
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", ".", "tests"):
    sys.path.insert(0, str(ROOT / p))
import network                                                 # noqa: E402
import download                                                # noqa: E402
import getarasaac                                              # noqa: E402
import languages                                               # noqa: E402
import latexthemes                                             # noqa: E402
import newlang                                                 # noqa: E402
import offline                                                 # noqa: E402
import prefs                                                   # noqa: E402
import prompts                                                 # noqa: E402
import serve                                                   # noqa: E402
import speechconfig                                            # noqa: E402
import arasaac_fake                                            # noqa: E402

AS_PHONE = "--as-phone" in sys.argv[1:]
tmp = Path(tempfile.mkdtemp(prefix="parseh-arasaac-door-test-"))
network.STORE = str(tmp / "config" / "network.json")
# and every other store of config/ (tests/test_harness_stores.py asks), though this page saves none of them today:
# the owner's preferences, the two memories of the phone-keeping door, the prompts he wrote, the LaTeX themes, the
# languages added on this machine (lib/newlang.py keeps a copy of the path) and the speech settings
prefs.STORE = str(tmp / "config" / "prefs.json")
offline.DIGESTS = str(tmp / "config" / "digests.json")
offline.WHERES = str(tmp / "config" / "wheres.json")
prompts.STORE = str(tmp / "config" / "prompts.json")
latexthemes.STORE = str(tmp / "config" / "latex.json")
languages.PERSONAL = newlang.PERSONAL = str(tmp / "config" / "languages.json")
speechconfig.CONFIG = tmp / "config" / "speech.json"
getarasaac.ARASAAC_DIR = str(tmp / "arasaac")
getarasaac.MIN_RECORDS = 5
getarasaac.PAUSE = 0.0
getarasaac.RETRIES = (0, 0, 0)
serve.Handler.log_request = lambda self, *a, **k: None
serve.Handler.log_message = lambda self, *a: None
if AS_PHONE:
    for patched in (mock.patch.object(network, "where", lambda ip, doc=None: network.LAN),
                    mock.patch.object(network, "may_connect", lambda ip, doc=None: True),
                    mock.patch.object(network, "let_in", lambda *a, **k: True)):
        patched.start()

FAKE = {"server": None}


def new_world(n=40, locales=("en", "fr", "es"), delay=0.0):
    if FAKE["server"] is not None:
        FAKE["server"].stop()
    server = arasaac_fake.Fake(arasaac_fake.World(n, tuple(locales)))
    server.world.delay = delay
    FAKE["server"] = server
    getarasaac.API = server.api
    getarasaac.STATIC = server.static
    # (the table says what the real host measured; a test world is smaller, which the page shows once it is here)


def wipe():
    getarasaac.stop_all(3)
    getarasaac.remove() if not getarasaac.running() else None
    getarasaac.JOB.clear()
    getarasaac._FACTS.clear()


def command(line):
    c = json.loads(line)
    what = c.get("cmd")
    srv = FAKE["server"]
    if what == "world":
        wipe()
        new_world(int(c.get("n", 40)), c.get("locales") or ("en", "fr", "es"), float(c.get("delay", 0.0)))
    elif what == "clear":
        wipe()
        srv.requests.clear()
        srv.world.failures.clear()
        srv.after.clear()
    elif what == "build":
        cancel = threading.Event()
        stop_after = c.get("stop_after")
        if stop_after:
            srv.after[r"/pictograms/\d+/"] = (int(stop_after), cancel.set)
        srv.requests.clear()
        try:
            getarasaac.build(c.get("locales") or ["en"], int(c.get("resolution", 300)), say=lambda t: None,
                             update=bool(c.get("update")), cancel=cancel)
        except download.Cancelled:
            pass
        finally:
            srv.after.clear()
    elif what == "slow":
        srv.world.delay = float(c["seconds"])
    elif what == "hold":                    # the pictures wait at the host (not the lists) until `release`
        srv.world.gate.clear()
    elif what == "release":
        srv.world.gate.set()
    elif what == "fail":
        srv.world.fail(c["pattern"], c.get("how", "500"), int(c.get("times", 1)))
    elif what == "unfail":
        srv.world.failures.clear()
    elif what == "change":
        for pid in c.get("ids") or []:
            srv.world.touch(sorted(srv.world.dates)[int(pid)], picture=bool(c.get("picture")))
        for pid in c.get("add") or []:
            srv.world.add(int(pid))
        for i in c.get("drop") or []:
            srv.world.drop(sorted(srv.world.dates)[int(i)])
    elif what == "reset_stats":
        srv.requests.clear()
        srv.connections = 0
    elif what == "stats":
        pics = srv.count(r"/pictograms/\d+/")
        return {"requests": len(srv.requests), "pictures": pics, "lists": srv.count(r"/v1/pictograms/all/"),
                "connections": srv.connections, "conditional": sum(1 for _m, p, h in srv.requests
                                                                  if "If-Modified-Since" in h and "/pictograms/" in p),
                "files": len(list((Path(getarasaac.ARASAAC_DIR) / "pictograms").glob("*.png")))}
    elif what == "other_format":
        os.makedirs(getarasaac.ARASAAC_DIR, exist_ok=True)
        Path(getarasaac.manifest_path()).write_text(json.dumps({"format": 99, "resolution": 300}), encoding="utf-8")
    elif what == "retries":
        getarasaac.RETRIES = tuple(c["waits"])
    else:
        raise ValueError("no such command: %r" % what)
    return None


def cleanup(*_):
    getarasaac.stop_all(1)
    if FAKE["server"] is not None:
        try:
            FAKE["server"].stop()
        except Exception:                                       # noqa: BLE001
            pass
    shutil.rmtree(tmp, ignore_errors=True)
    os._exit(0)


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)
new_world()
try:
    srv = serve.Server(("127.0.0.1", 0), serve.Handler, None)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("READY " + json.dumps({"port": srv.server_address[1], "arasaac": getarasaac.ARASAAC_DIR, "phone": AS_PHONE}), flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            got = command(line)
            print("OK" + (" " + json.dumps(got) if got is not None else ""), flush=True)
        except Exception as e:                                  # noqa: BLE001
            print("ERR %s: %s" % (type(e).__name__, e), flush=True)
finally:
    cleanup()
