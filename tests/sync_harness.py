#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""One whole Parseh install in a temporary tree, over TLS, for the sync
transport's tests (tests/test_sync_pairing.py): the REAL serve.main, with
every store pointed into the tree by tests/cardkit_harness.py's serve_it,
and its .tls/ there too -- so config/sync/ and config/peers.json, which follow
prefs.STORE, are the tree's own, never the checkout's.

    python3 tests/sync_harness.py serve <tmp> <port>

SYNC_CODE_LIFE=<seconds> in the environment shortens the pairing code's
fifteen minutes, so that a test can watch one run out.

SYNC_JOBS_FAKE=<json> (lane D, tests/test_sync_jobs_end_to_end.py) sets this
install's capabilities ("caps", over what it really has), the jobs' deadline
and how long a partner's capabilities are trusted ("deadline", "caps_ttl"),
and FAKES THE BOOK BUILD: a runner that waits "run_seconds", then writes a PDF
and a reader into the book, as ./build.sh would; "no_numpy" makes estimating
by the sound impossible here, as a Python without NumPy does.  "stt"
({"runtime", "models", "segments"}, lane D2) makes this install's speech to
text tests/addstt_fakes.py's: the real job and worker, with the faster-whisper
stand-in of tests/fixtures/stt_runtime -- or no speech to text at all.

The books' shelf is the tree's own (root/books), as the server's pages see it.
"""
import json
import time
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for folder in ("markdown/exlex", "markdown/app", "youtube/lib", "lib", "tests", "."):
    sys.path.insert(0, str(REPO / folder))


def serve_tree(tmp, port):
    tmp = Path(tmp)
    for d in ("config", "tls", "root/youtube/videos", "library", "exercises", "anki", "tray"):
        (tmp / d).mkdir(parents=True, exist_ok=True)
    stt = (json.loads(os.environ.get("SYNC_JOBS_FAKE") or "null") or {}).get("stt")
    if stt is not None:
        # THIS INSTALL'S SPEECH TO TEXT is tests/addstt_fakes.py's (before serve imports getstt):
        # installed or not, and the real worker with the faster-whisper stand-in when it is
        import addstt_fakes
        root = str(tmp / "sttfake")
        sys.modules["getstt"] = addstt_fakes.make(root)
        addstt_fakes.configure(root, runtime=bool(stt.get("runtime")), models=stt.get("models") or [],
                               fake={"segments": stt.get("segments") or [[0.0, 2.0, " uno due tre"]]})
    import serve
    import syncpeer
    serve.TLS_DIR = str(tmp / "tls")
    if os.environ.get("SYNC_CODE_LIFE"):
        syncpeer.CODE_LIFE = float(os.environ["SYNC_CODE_LIFE"])
    real_main = serve.main

    import books
    books.BOOKS_DIR = str(tmp / "root" / "books")
    os.makedirs(books.BOOKS_DIR, exist_ok=True)
    fake = json.loads(os.environ.get("SYNC_JOBS_FAKE") or "null")
    if fake is not None:
        fake_jobs(serve, fake)

    def main():
        # serve_it asks for --http; this install speaks TLS, as one a partner calls does
        sys.argv = ["serve.py", "--local", str(port)]
        real_main()
    serve.main = main
    import cardkit_harness
    cardkit_harness.serve_it(tmp, port, True, "tray")


def fake_jobs(serve, fake):
    import syncjobs
    import syncunits
    syncjobs.CAPS_FORCE["*"] = fake.get("caps") or {}
    syncjobs.DEADLINE = float(fake.get("deadline", syncjobs.DEADLINE))
    syncjobs.CAPS_TTL = float(fake.get("caps_ttl", syncjobs.CAPS_TTL))
    syncjobs.TIMEOUT = float(fake.get("timeout", syncjobs.TIMEOUT))
    serve.lent_applied = lambda job: None          # never the checkout's library page
    if fake.get("no_numpy"):
        # this install's Python "lacks" NumPy: estimating by the sound cannot run here
        serve.load_wavealign = lambda: (None, "estimating by the sound needs numpy, which the Python "
                                              "running Parseh does not have")

    def build(rec, say):
        d = syncunits.locate(rec["unit"]).where
        say("building (a fake build)…")
        time.sleep(float(fake.get("run_seconds", 0)))
        os.makedirs(os.path.join(d, "reader"), exist_ok=True)
        with open(os.path.join(d, os.path.basename(d) + ".pdf"), "wb") as fh:
            fh.write(b"%PDF-1.5 built by " + syncjobs.syncid.install_id().encode() + b"\n")
        with open(os.path.join(d, "reader", "index.html"), "w") as fh:
            fh.write("<p>the reader, built by %s</p>" % syncjobs.syncid.install_id())
        return {"result": {"what": "pdf"}, "outputs": syncjobs._built_files(d, "pdf")}
    syncjobs.RUNNERS["book-build"] = build


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "serve":
        sys.exit(__doc__)
    serve_tree(sys.argv[2], int(sys.argv[3]))
