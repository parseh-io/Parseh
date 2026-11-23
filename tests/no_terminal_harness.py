#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Parseh's REAL handler on a temporary set of stores, for tests/no_terminal.mjs (TO-DO §5, a0.6.3
lane J1: no page tells anyone to type a command).

Every store a page here may write points into the temporary folder: prefs, network, the offline
digests, the reading downloads' folders, the word models' home (PKUSEG_HOME).  The library page is
the checkout's own books/index.html (git-ignored; built by make_index.py, as every build does).

Three things are FAKED, because doing them for real downloads to this computer:
  - the packages of the environment (runtime.status/find_env/complete_env): rapidfuzz and zstandard
    start missing, and adding them takes a second and writes two log lines;
  - Chinese's word models (words.fetch_models): written as the empty files segmenter.models looks for;
  - the analyzer being installed (segmenter.available) -- so the row offers Get it.
Everything else -- the routes, the jobs, the pages and their scripts -- is Parseh's own.

Prints READY {port}; reads nothing; ends on SIGTERM.
"""
import json
import os
import shutil
import signal
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
tmp = Path(tempfile.mkdtemp(prefix="parseh-no-terminal-test-"))
os.environ["PKUSEG_HOME"] = str(tmp / "pkuseg")
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", ".", "tests"):
    sys.path.insert(0, str(ROOT / p))
import corpus           # noqa: E402
import getmt            # noqa: E402
import lookup           # noqa: E402
import network          # noqa: E402
import offline          # noqa: E402
import prefs            # noqa: E402
import runtime          # noqa: E402
import segmenter        # noqa: E402
import serve            # noqa: E402
import words            # noqa: E402
import ytpages          # noqa: E402

network.STORE = str(tmp / "config" / "network.json")
prefs.STORE = str(tmp / "config" / "prefs.json")
offline.DIGESTS = str(tmp / "config" / "digests.json")
offline.WHERES = str(tmp / "config" / "wheres.json")
lookup.DICT_DIR = str(tmp / "dict")
corpus.CORPUS_DIR = str(tmp / "corpus")
getmt.MT_DIR = str(tmp / "mt")
getmt.ENGINE_DIR = str(tmp / "mt" / "engine")
os.makedirs(lookup.DICT_DIR, exist_ok=True)
ytpages.VIDEOS = str(ROOT / "tests" / "fixtures" / "videos")      # read, never written
serve.Handler.log_request = lambda self, *a, **k: None
serve.Handler.log_message = lambda self, *a: None

# ---- the environment's packages: two missing until "added"
HAVE = {"rapidfuzz": False, "zstandard": False}


def status():
    return {"packages": [{"module": m, "name": n, "what": w, "have": HAVE.get(n, True)}
                         for m, n, w in runtime.PACKAGES]}


def complete_env(prefix, python, report):
    report.step("packages", "the packages", "running", "adding rapidfuzz, zstandard")
    report.log("Collecting rapidfuzz")
    time.sleep(1.0)
    report.log("Successfully installed rapidfuzz zstandard")
    HAVE.update(rapidfuzz=True, zstandard=True)
    report.step("packages", "the packages", "done", "all present")
    return True


runtime.status = status
runtime.find_env = lambda: (str(tmp / "env"), str(tmp / "env" / "bin" / "python"))
runtime.complete_env = complete_env


# ---- Chinese's word models: the analyzer is here, its models are not
def fetch_models(code, say=print):
    time.sleep(1.0)
    for m in segmenter.MODELS[code]:
        d = os.path.join(segmenter.pkuseg_home(), m["name"])
        os.makedirs(d, exist_ok=True)
        open(d + ".zip", "wb").close()
        for f in m["files"]:
            open(os.path.join(d, f), "wb").close()
    say("fetched")
    return True


segmenter.available = lambda code: code in segmenter.BACKENDS
words.fetch_models = fetch_models


def main():
    srv = serve.Server(("127.0.0.1", 0), serve.Handler, None)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("READY " + json.dumps({"port": srv.server_address[1], "tmp": str(tmp)}), flush=True)

    def bye(*_a):
        shutil.rmtree(tmp, ignore_errors=True)
        os._exit(0)
    signal.signal(signal.SIGTERM, bye)
    signal.signal(signal.SIGINT, bye)
    for _line in sys.stdin:
        pass
    bye()


if __name__ == "__main__":
    main()
