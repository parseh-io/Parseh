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
"""
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
    import serve
    import syncpeer
    serve.TLS_DIR = str(tmp / "tls")
    if os.environ.get("SYNC_CODE_LIFE"):
        syncpeer.CODE_LIFE = float(os.environ["SYNC_CODE_LIFE"])
    real_main = serve.main

    def main():
        # serve_it asks for --http; this install speaks TLS, as one a partner calls does
        sys.argv = ["serve.py", "--local", str(port)]
        real_main()
    serve.main = main
    import cardkit_harness
    cardkit_harness.serve_it(tmp, port, True, "tray")


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "serve":
        sys.exit(__doc__)
    serve_tree(sys.argv[2], int(sys.argv[3]))
