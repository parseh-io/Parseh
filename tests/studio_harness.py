#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The server tests/studio_audio.mjs drives: the real studio routes on a
TEMPORARY library, a TEMPORARY exercises/ store and a TEMPORARY clip tray,
with real recordings (ffmpeg) in it.

    python3 tests/studio_harness.py studio   markdown/app/server.py's handler:
                                             the studio at /, no clip tray routes
    python3 tests/studio_harness.py parseh   serve.py's handler: the studio at
                                             /studio, the tray at /clips

Seeds two clips in the tray (Persian, "سلام" and "خداحافظ") and a document
holding tests/fixtures/studio/audio/audio.md with its recording and picture.
Prints `READY {json}` once listening.  SIGTERM or SIGINT removes the temp
tree.  Never touches markdown/library/, exercises/ or clips/.

    --pictograms           an INSTALLED set of ARASAAC pictograms (tests/pictogram_world.py) in the temporary
    --pictograms=partial   arasaac/ -- or a download that was stopped; without the flag the folder is empty, and
                           either way it is the temporary one: the checkout's own is never read or written
                           (its path is in READY, so a suite may take the folder away and put it back)
    --latex-slow=SECONDS   every drawing the BATCH makes (lib/latexbatch.py: "Make drawings of N shown") waits this long
                           first, then is made for real: the work lasts long enough to be looked at, as
                           tests/activity.mjs makes its doors slow"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODE = sys.argv[1] if len(sys.argv) > 1 else "studio"
FORCE_LATEX_MISSING = "--latex-missing" in sys.argv[2:]
FORCE_LATEX_COMPILER_STATES = "--latex-compiler-states" in sys.argv[2:]
LATEX_SLOW = next((float(a.partition("=")[2]) for a in sys.argv[2:] if a.split("=")[0] == "--latex-slow"), 0.0)
PICTOGRAMS = next((a.partition("=")[2] or "complete" for a in sys.argv[2:] if a.split("=")[0] == "--pictograms"), "")

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
    sys.exit("usage: studio_harness.py studio|parseh")
import audiofile  # noqa: E402  (the modules the studio imported)
import clips      # noqa: E402
import decks      # noqa: E402
import store      # noqa: E402
# the door that says who may reach Parseh (lib/network.py): pointed at the
# temporary tree below, so a suite can neither read the owner's own settings
# nor shut his Wi-Fi door by running.  Imported in BOTH modes: the studio
# alone does not read it, but the assignment below runs either way.
import network    # noqa: E402
# and the owner's preferences (lib/prefs.py): a document, the editor and a deck
# load lib/prefs.js since a0.5.0 (the theme follows a person), and a suite that
# presses ◐ or the gear's Colours would write config/prefs.json -- the theme of
# the owner's own pages -- through serve.py's /__prefs
import prefs      # noqa: E402
# and the ARASAAC pictograms (lib/getarasaac.py): the picker reads them, and the checkout's own arasaac/ may be 160 MB of
# the owner's -- or none at all, which a suite must not depend on either
import getarasaac     # noqa: E402
import arasaacsearch  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="parseh-studio-audio-test-"))
store.LIB = tmp / "library"
getarasaac.ARASAAC_DIR = str(tmp / "arasaac")
getarasaac._FACTS.clear()
arasaacsearch.forget()
if PICTOGRAMS:
    sys.path.insert(0, str(ROOT / "tests"))
    import pictogram_world                         # noqa: E402
    pictogram_world.install(getarasaac.ARASAAC_DIR, complete=PICTOGRAMS != "partial",
                            pictures=None if PICTOGRAMS != "partial" else 12)
network.STORE = str(tmp / "config" / "network.json")
prefs.STORE = str(tmp / "config" / "prefs.json")
# and the LaTeX drawings' themes, their drawings and their packages
import latexthemes, latexdraw, texpackages
latexthemes.STORE = str(tmp / "config" / "latex.json")
# and the prompts a person wrote (lib/prompts.py)
import prompts
prompts.STORE = str(tmp / "config" / "prompts.json")
latexdraw.DRAWN = str(tmp / "latex-drawn")
if LATEX_SLOW:
    _made_for_real = latexdraw.draw

    def _slow_draw(*args, **kwargs):
        time.sleep(LATEX_SLOW)
        return _made_for_real(*args, **kwargs)
    latexdraw.draw = _slow_draw
texpackages.TREE = str(tmp / "texmf")
# what the themes add to the base, as if Parseh had got it: unless the suite is
# about the packages themselves (tests/texmf_fixture.py); a suite may empty the
# list at "texmf_list" for a while, and write it back
if "--latex-own-missing" not in sys.argv[2:]:
    import texmf_fixture
    texmf_fixture.pretend_got(texpackages, latexthemes)
# The LaTeX Settings browser pass needs a stable missing-package card even on
# a computer with a complete TeX installation. This changes only the test
# page's availability report; it never writes to or changes TeX.
if FORCE_LATEX_MISSING:
    texpackages.installed = lambda _file: False
    texpackages.installed_many = lambda files: {f: False for f in files}
# Settings' compiler list needs both available and unavailable facts without
# depending on the TeX tools installed on the computer that drives the browser.
if FORCE_LATEX_COMPILER_STATES:
    latexdraw.compilers = lambda fresh=False: {
        "xelatex": {"path": "/test/xelatex", "version": "XeTeX test 2026"},
        "pdflatex": None,
        "lualatex": {"path": "/test/lualatex",
                     "version": "LuaHBTeX, Version 1.19.0 (TeX Live test build)"},
    }
import offline  # the phone-keeping memories (lib/offline.py) too
offline.DIGESTS = str(tmp / "config" / "digests.json")
offline.WHERES = str(tmp / "config" / "wheres.json")
import languages, newlang, speechconfig    # the languages added on this machine (newlang keeps a copy of the
languages.PERSONAL = newlang.PERSONAL = str(tmp / "config" / "languages.json")   # path) and the speech settings
speechconfig.CONFIG = tmp / "config" / "speech.json"
store.LIB.mkdir()
decks.set_dir(tmp / "exercises")
tray = tmp / "clips"
tray.mkdir()
store.set_clips_dir(tray)
clips.set_dir(tray)
assert store.lib() == tmp / "library" and Path(clips.DIR) == tray


def cleanup(*_):
    shutil.rmtree(tmp, ignore_errors=True)
    os._exit(0)


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)
Handler.log_message = lambda self, *a: None
if MODE == "parseh":
    Handler.log_request = lambda self, *a, **k: None


def tone(name, seconds, hz):
    p = tmp / name
    subprocess.run([audiofile.ffmpeg() or "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "sine=frequency=%d:duration=%s" % (hz, seconds),
                    "-c:a", "libmp3lame", str(p)], check=True)
    return p.read_bytes()


try:
    hello = clips.save_audio(tone("hello.mp3", 3, 523), "hello",
                             {"lang": "fa", "label": "1.2", "text": "سلام",
                              "source": {"kind": "book", "title": "A Persian reader"}})
    bye = clips.save_audio(tone("bye.mp3", 3, 392), "goodbye",
                           {"lang": "fa", "label": "0:14", "text": "خداحافظ",
                            "source": {"kind": "film", "title": "Street market"}})
    fixture = ROOT / "tests" / "fixtures" / "studio" / "audio"
    rich = store.create((fixture / "audio.md").read_text(encoding="utf-8"))
    store.save_audio(rich["id"], "greeting.mp3", (fixture / "audio" / "greeting.mp3").read_bytes())
    store.save_image(rich["id"], "swatch.png", (fixture / "images" / "swatch.png").read_bytes())

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    srv.daemon_threads = True
    studio.SERVER["instance"] = srv
    print("READY " + json.dumps({"port": srv.server_address[1], "studio": studio.BASE, "mode": MODE,
                                 "library": str(store.LIB), "tray": str(tray), "arasaac": getarasaac.ARASAAC_DIR,
                                 "latex_drawn": str(latexdraw.DRAWN),
                                 "texmf_list": texpackages.manifest_path(),
                                 "rich_doc_id": rich["id"], "rich_doc_dir": str(store.doc_dir(rich["id"])),
                                 "clips": [hello, bye], "audio_accept": audiofile.ACCEPT,
                                 "audio_human": audiofile.HUMAN},
                                ensure_ascii=False), flush=True)
    srv.serve_forever()
finally:
    shutil.rmtree(tmp, ignore_errors=True)
