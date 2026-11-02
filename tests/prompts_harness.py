#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The server tests/your_prompts.mjs drives: Parseh's real handler, its real
Settings -> Your prompts page and its real routes, on a TEMPORARY tree -- the
store of the prompts, the network settings and the studio's library are all in
it, so nothing here is written outside it (config/ included).

    python3 tests/prompts_harness.py

TWO DEVICES, ONE SERVER.  A request that carries `X-Test-Device: phone` is a
device that has been let in over the Wi-Fi (lib/network.py's LAN: the page and
the routes ask serve.py's Handler._where, which is answered from that header);
every other request is the computer's own.  The browser test opens one context
for each, at another address of this computer (127.0.0.1 and localhost are two
origins to a browser), so the second device has storage and cookies of its own.

It reads one JSON command per line on stdin and answers `OK` (with a JSON
document after it where there is one) or `ERR ...`, so that a browser test can
change the world under an open page:

    {"cmd": "save", "prompt": {surface, name, kind, text, languages}}   made through lib/prompts.py
    {"cmd": "clear"}                       the store emptied
    {"cmd": "parseh", "changed": true}     Parseh's own prompt for a stretch of a video changed (or put back);
                                           "surface": "studio-doc" does it for the studio's page instead
    {"cmd": "stored"}                      OK <the store's file, as JSON>

Prints `READY {json}` once listening.  SIGTERM or SIGINT removes the temp tree."""
import json
import os
import shutil
import signal
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", "."):
    sys.path.insert(0, str(ROOT / p))
import languages                                               # noqa: E402
import latexthemes                                             # noqa: E402
import network                                                 # noqa: E402
import newlang                                                 # noqa: E402
import offline                                                 # noqa: E402
import analysisconfig                                          # noqa: E402
import prefs                                                   # noqa: E402
import promptkit                                               # noqa: E402
import prompts                                                 # noqa: E402
import serve                                                   # noqa: E402
import speechconfig                                            # noqa: E402
import store                                                   # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="parseh-prompts-test-"))
network.STORE = str(tmp / "config" / "network.json")
prompts.STORE = str(tmp / "config" / "prompts.json")
# and every other store of config/ (tests/test_harness_stores.py asks): the owner's preferences (a page of the
# studio saves its theme through lib/prefs.py since a0.5.0), the two memories of the phone-keeping door, the LaTeX
# themes, the languages added on this machine (lib/newlang.py keeps a copy of the path) and the speech settings
prefs.STORE = str(tmp / "config" / "prefs.json")
analysisconfig.STORE = str(tmp / "config" / "analysis.json")
offline.DIGESTS = str(tmp / "config" / "digests.json")
offline.WHERES = str(tmp / "config" / "wheres.json")
latexthemes.STORE = str(tmp / "config" / "latex.json")
languages.PERSONAL = newlang.PERSONAL = str(tmp / "config" / "languages.json")
speechconfig.CONFIG = tmp / "config" / "speech.json"
store.LIB = tmp / "library"
serve.Handler.log_request = lambda self, *a, **k: None
serve.Handler.log_message = lambda self, *a: None

_where = serve.Handler._where


def where(self):
    return network.LAN if self.headers.get("X-Test-Device") == "phone" else _where(self)


serve.Handler._where = where

REGION = promptkit.TEMPLATES["video-region"]
CHANGED = tmp / "region-prompt.md"
STUDIO = promptkit.TEMPLATES["studio-doc"]
STUDIO_CHANGED = tmp / "studio-prompt.md"


def command(line):
    c = json.loads(line)
    what = c.get("cmd")
    if what == "save":
        return prompts.save(c["prompt"])["id"]
    if what == "clear":
        if os.path.exists(prompts.STORE):
            os.remove(prompts.STORE)
        return None
    if what == "parseh" and c.get("surface") == "studio-doc":
        if c.get("changed"):
            text = Path(STUDIO).read_text(encoding="utf-8")
            STUDIO_CHANGED.write_text(text.replace("You are writing a document for", "You are writing a document, for", 1),
                                      encoding="utf-8")
            promptkit.TEMPLATES["studio-doc"] = str(STUDIO_CHANGED)
        else:
            promptkit.TEMPLATES["studio-doc"] = STUDIO
        return None
    if what == "parseh":
        if c.get("changed"):
            text = Path(REGION).read_text(encoding="utf-8")
            CHANGED.write_text(text.replace("# Gloss part", "# Gloss part (edited)", 1), encoding="utf-8")
            promptkit.TEMPLATES["video-region"] = str(CHANGED)
        else:
            promptkit.TEMPLATES["video-region"] = REGION
        return None
    if what == "stored":
        return json.loads(Path(prompts.STORE).read_text(encoding="utf-8")) if os.path.exists(prompts.STORE) else None
    raise ValueError("no such command: %r" % what)


def cleanup(*_):
    shutil.rmtree(tmp, ignore_errors=True)
    os._exit(0)


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)
try:
    srv = serve.Server(("127.0.0.1", 0), serve.Handler, None)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("READY " + json.dumps({"port": srv.server_address[1], "store": prompts.STORE}), flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            got = command(line)
            print("OK" + ("" if got is None else " " + json.dumps(got, ensure_ascii=False)), flush=True)
        except Exception as e:                                  # noqa: BLE001
            print("ERR %s: %s" % (type(e).__name__, e), flush=True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
