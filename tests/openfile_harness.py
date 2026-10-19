#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The server tests/openfile.mjs drives: the real routes (the studio alone, or Parseh's /studio) on a TEMPORARY
studio library, a TEMPORARY folder for the working copies of files opened from the computer, and a TEMPORARY
"person's own folder" seeded with the files such a person has.

    python3 tests/openfile_harness.py studio   markdown/app/server.py's handler: the studio at /
    python3 tests/openfile_harness.py studio remote
                                               the same, taking every client for ANOTHER device (what the page does when
                                               Parseh lets in a phone or a laptop: the files are still this computer's)
    python3 tests/openfile_harness.py parseh   serve.py's handler: the studio at /studio

Prints `READY {json}` once listening.  SIGTERM or SIGINT removes the temp tree.  Never touches markdown/library/,
markdown/open/, config/ or anything of the owner's."""
import json
import os
import shutil
import signal
import socket
import sys
import tempfile
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODE = sys.argv[1] if len(sys.argv) > 1 else "studio"

if MODE == "parseh":
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    import serve                                   # noqa: E402
    Handler, studio = serve.Handler, serve.studio
elif MODE == "studio":
    sys.path.insert(0, str(ROOT / "markdown" / "app"))
    import server                                  # noqa: E402
    Handler, studio = server.Handler, server
else:
    sys.exit("usage: openfile_harness.py studio|parseh")
import openfile  # noqa: E402
import store     # noqa: E402
import network   # noqa: E402  (the door that says who may reach Parseh: pointed at the temporary tree)
import prefs     # noqa: E402  (and the owner's preferences: a page driven here may save one)

REMOTE = "remote" in sys.argv[2:]
tmp = Path(tempfile.mkdtemp(prefix="parseh-openfile-test-"))
store.LIB = tmp / "library"
openfile.OPEN_DIR = tmp / "open"
network.STORE = str(tmp / "config" / "network.json")
if REMOTE:
    network.where = lambda ip, doc=None: network.LAN        # the studio alone has no gate of its own: every client is "another device"
prefs.STORE = str(tmp / "config" / "prefs.json")
import latexthemes, latexdraw, texpackages    # noqa: E402
latexthemes.STORE = str(tmp / "config" / "latex.json")
import prompts                                # noqa: E402
prompts.STORE = str(tmp / "config" / "prompts.json")
latexdraw.DRAWN = str(tmp / "latex-drawn")
texpackages.TREE = str(tmp / "texmf")
import texmf_fixture                          # noqa: E402
texmf_fixture.pretend_got(texpackages, latexthemes)
import offline                                # noqa: E402
offline.DIGESTS = str(tmp / "config" / "digests.json")
offline.WHERES = str(tmp / "config" / "wheres.json")
import languages, newlang, speechconfig       # noqa: E402,E401
languages.PERSONAL = newlang.PERSONAL = str(tmp / "config" / "languages.json")
speechconfig.CONFIG = tmp / "config" / "speech.json"
store.LIB.mkdir()
store.set_clips_dir(tmp / "clips")
if MODE == "parseh":
    import decks                              # noqa: E402
    decks.set_dir(tmp / "exercises")
    decks.set_clips_dir(tmp / "clips")


def cleanup(*_):
    shutil.rmtree(tmp, ignore_errors=True)
    os._exit(0)


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)
Handler.log_message = lambda self, *a: None
if MODE == "parseh":
    Handler.log_request = lambda self, *a, **k: None

# a real picture, so the page can show it
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cfc0f01f0005000201a5f645400000000049454e44ae426082")

LESSON = ("---\ntitle: A lesson\nlang: en\ntarget: fa\n---\n\nHello there.\n\n## Part one\n\nThe cat sat on the mat.\n")
PICTURES = ("---\ntitle: With a picture\nlang: en\ntarget: fa\n---\n\nLook:\n\n![A cat](images/cat.png)\n\nThe end.\n")
WINDOWS = ("---\ntitle: From Windows\nlang: en\ntarget: fa\n---\n\nTwo lines.\nOn purpose.\n").replace("\n", "\r\n")
PERSIAN = ("---\ntitle: درس\nlang: en\ntarget: fa\n---\n\nسلام دنیا\n")
COURSE_MD = ("---\ntitle: A course\nlang: en\ntarget: fa\n---\n\nIn a zip.\n\n![A cat](images/cat.png)\n")

mine = tmp / "mine"
mine.mkdir()
(mine / "lesson.md").write_text(LESSON, encoding="utf-8")
(mine / "pictures.md").write_text(PICTURES, encoding="utf-8")
(mine / "images").mkdir()
(mine / "images" / "cat.png").write_bytes(PNG)
(mine / "windows.md").write_bytes(b"\xef\xbb\xbf" + WINDOWS.encode("utf-8"))
(mine / "درس.md").write_text(PERSIAN, encoding="utf-8")
(mine / "readme.pdf").write_bytes(b"%PDF-1.4\n")                     # not something the studio opens
(mine / "notes").mkdir()
(mine / "notes" / "deep.md").write_text("---\ntitle: Deep\nlang: en\ntarget: fa\n---\n\nDown here.\n", encoding="utf-8")


def make_zip(path, entries):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in entries:
            zi = zipfile.ZipInfo(name, (2024, 3, 9, 12, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, data)


make_zip(mine / "course.zip", [("course.md", COURSE_MD), ("course.tags.json", json.dumps({"tags": ["a1", "verbs"]})),
                               ("images/cat.png", PNG), ("README.txt", "Kept as it is.\n")])
make_zip(mine / "two.zip", [("first.md", "---\ntitle: First one\nlang: en\ntarget: fa\n---\n\nFirst.\n"),
                            ("second.md", "---\ntitle: Second one\nlang: en\ntarget: fa\n---\n\nSecond.\n"),
                            ("data.csv", "1,2\n")])

try:
    studio.ensure_web_fonts()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    srv.daemon_threads = True
    studio.SERVER["instance"] = srv
    print("READY " + json.dumps({"port": srv.server_address[1], "studio": studio.BASE, "mode": MODE,
                                 "mine": str(mine), "open_dir": str(openfile.OPEN_DIR), "library": str(store.LIB),
                                 "tmp": str(tmp), "sep": os.sep, "host": socket.gethostname(), "remote": REMOTE},
                                ensure_ascii=False), flush=True)
    srv.serve_forever()
finally:
    shutil.rmtree(tmp, ignore_errors=True)
