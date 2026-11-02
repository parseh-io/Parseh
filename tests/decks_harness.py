#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The server tests/decks.mjs drives: the real routes on a TEMPORARY studio
library and a TEMPORARY exercises/ store, seeded with a few decks.

    python3 tests/decks_harness.py studio   markdown/app/server.py's handler:
                                            the studio at /, the decks at /exercises
    python3 tests/decks_harness.py parseh   serve.py's handler: the studio at
                                            /studio, the decks at /exercises

Prints `READY {json}` once listening.  SIGTERM or SIGINT removes the temp
tree.  Never touches markdown/library/ or exercises/."""
import json
import os
import secrets
import shutil
import signal
import sys
import tempfile
from datetime import datetime, timedelta
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
    sys.exit("usage: decks_harness.py studio|parseh")
import decks   # noqa: E402  (the modules the studio imported)
import store   # noqa: E402

# the door that says who may reach Parseh (lib/network.py): pointed at the
# temporary tree below, so a suite can neither read the owner's own settings
# nor shut his Wi-Fi door by running.  Imported in BOTH modes: the studio
# alone does not read it, but the assignment below runs either way.
import network    # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="parseh-decks-test-"))
store.LIB = tmp / "library"
network.STORE = str(tmp / "config" / "network.json")
# and the LaTeX drawings' themes, their drawings and their packages
import latexthemes, latexdraw, texpackages
latexthemes.STORE = str(tmp / "config" / "latex.json")
# and the prompts a person wrote (lib/prompts.py)
import prompts
prompts.STORE = str(tmp / "config" / "prompts.json")
latexdraw.DRAWN = str(tmp / "latex-drawn")
texpackages.TREE = str(tmp / "texmf")
import texmf_fixture  # noqa: E402  what the themes add to the base, as if Parseh had got it
texmf_fixture.pretend_got(texpackages, latexthemes)
import offline  # the phone-keeping memories (lib/offline.py) too
offline.DIGESTS = str(tmp / "config" / "digests.json")
offline.WHERES = str(tmp / "config" / "wheres.json")
import analysisconfig                                          # noqa: E402
import prefs    # and the owner's preferences (lib/prefs.py): a page a suite
prefs.STORE = str(tmp / "config" / "prefs.json")   # drives may save one
analysisconfig.STORE = str(tmp / "config" / "analysis.json")   # drives may save one
import languages, newlang, speechconfig    # the languages added on this machine (newlang keeps a copy of the
languages.PERSONAL = newlang.PERSONAL = str(tmp / "config" / "languages.json")   # path) and the speech settings
speechconfig.CONFIG = tmp / "config" / "speech.json"
store.LIB.mkdir()
decks.set_dir(tmp / "exercises")
# the clip tray too: an exercise naming a clip looks there, never in clips/
decks.set_clips_dir(tmp / "clips")
store.set_clips_dir(tmp / "clips")
if "clips" in sys.modules:                         # the hub's own tray routes
    sys.modules["clips"].set_dir(tmp / "clips")
assert store.lib() == tmp / "library" and decks.DIR == tmp / "exercises"


def cleanup(*_):
    shutil.rmtree(tmp, ignore_errors=True)
    os._exit(0)


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)
Handler.log_message = lambda self, *a: None


def now():
    return datetime.now().astimezone()


def raw_item(folder, slug, markdown):
    """An exercise written straight to disk, past validation: the only way a
    deck holds one with errors (as an older or hand-edited store might)."""
    d = decks.deck_dir(folder, slug)
    item_id = secrets.token_hex(6)
    stamp = now().isoformat(timespec="microseconds")
    (d / "items").mkdir(exist_ok=True)
    (d / "items" / (item_id + ".json")).write_text(json.dumps(
        {"id": item_id, "created": stamp, "updated": stamp, "markdown": markdown,
         "footnotes": "", "origin": None}), encoding="utf-8")
    return item_id


FLASH = ":::exercise flashcard\ncard-type: vocab\ntarget: [سلام]{tl}\nmeaning: hello\n:::"
MYSTERY = ":::exercise mystery-type\nprompt: What is this?\n:::"
DOC = """---
title: Greetings doc
target: fa
---

Some text.

:::exercise true-false
prompt: Judge it
- [سلام]{tl} is a greeting => true
- [کتاب]{tl} is water => false
:::
"""
# notes beside a book: a library of their own, served under this mount
NOTES_SOURCE = "/books/arabic/grammar/notes"
NOTE_AR = """---
title: Arabic grammar notes
target: ar
---

:::exercise true-false
prompt: صح أم خطأ
- [نعم]{tl} means yes => true
- [لا]{tl} means yes => false
:::

:::exercise single-choice
prompt: أي كلمة تعني نعم؟
- [ ] [لا]{tl}
- [x] [نعم]{tl}
:::
"""

if MODE == "parseh":
    # The book those notes are beside, parked in the temp tree.  serve.py's
    # /books/<folder>/<slug>/notes route and the resolver it registers for
    # "+ Deck" both find a book through serve.book_dir; pointed here, they
    # look at this shelf alone and never at the real books/.
    SHELF = tmp / "books"
    (SHELF / "arabic" / "grammar").mkdir(parents=True)
    (SHELF / "arabic" / "grammar" / "book.json").write_text(
        json.dumps({"title": "Arabic grammar", "lang": "ar"}), encoding="utf-8")

    def parked_book(url_path):
        parts = url_path.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "books" or not all(
                p and not p.startswith(".") for p in parts):
            return None
        d = SHELF.joinpath(*parts[1:])
        return str(d) if (d / "book.json").is_file() else None

    serve.book_dir = parked_book

try:
    # Persian practice: browse + manage
    p = decks.create_deck("Persian practice", "fa")
    F, S = p["folder"], p["slug"]
    decks.add_item(F, S, ":::exercise single-choice\nprompt: Pick the right one\n"
                         "- [ ] wrong\n- [x] right\n:::")
    decks.add_item(F, S, FLASH)
    mt = decks.add_item(F, S, ":::exercise match-translations\nprompt: Match them\n"
                              "- [سلام]{tl} => hello\n- [کتاب]{tl} => book\n:::")
    meta = store.create(DOC)
    decks.copy_from_doc(F, S, meta["id"], 1, "true-false", meta["updated"])
    raw_item(F, S, MYSTERY)
    # one exercise answered Again five minutes ago: learning, and due now
    decks.review(F, S, mt["id"], "again", now=now() - timedelta(minutes=5))

    # Persian study: new single-choice, flashcard, a broken one, true-false
    s = decks.create_deck("Persian study", "fa")
    decks.add_item(s["folder"], s["slug"], ":::exercise single-choice\nprompt: Choose the greeting\n"
                                           "- [ ] [کتاب]{tl}\n- [x] [سلام]{tl}\n:::")
    decks.add_item(s["folder"], s["slug"], FLASH)
    raw_item(s["folder"], s["slug"], MYSTERY)
    decks.add_item(s["folder"], s["slug"], ":::exercise true-false\nprompt: True or not?\n"
                                           "- The sky is green => false\n- Water is wet => true\n:::")

    a = decks.create_deck("Arabic basics", "ar")
    decks.add_item(a["folder"], a["slug"], ":::exercise single-choice\nprompt: اختر\n"
                                           "- [x] نعم\n- [ ] لا\n:::")
    # and one copied from those notes: its origin names their mount.  In
    # Parseh they are the parked book's own notes, which its notes page
    # serves; the studio alone has no notes pages, only the library
    notes = (Path(studio.notes.dir_for(SHELF / "arabic" / "grammar")) if MODE == "parseh"
             else tmp / "notes")
    notes.mkdir(parents=True, exist_ok=True)
    was = store.use_library(notes)
    try:
        note = store.create(NOTE_AR)
    finally:
        store.use_library(was)
    decks.copy_from_doc(a["folder"], a["slug"], note["id"], 1, "true-false", note["updated"],
                        library=notes, source=NOTES_SOURCE)
    decks.create_deck("Empty deck", "fa")

    # the web fonts, as both servers provision them when they start
    # (server.py main, serve.py): without them every face a page names falls
    # back to one of the browser's own, and a test cannot tell a page that
    # draws Vazirmatn from one that only asks for it.  They are copied into
    # the studio's static/fonts/ (gitignored) from lib/fonts and TeX, once.
    studio.ensure_web_fonts()

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    srv.daemon_threads = True
    studio.SERVER["instance"] = srv
    print("READY " + json.dumps({"port": srv.server_address[1], "doc_id": meta["id"],
                                 "notes_doc_id": note["id"], "notes_source": NOTES_SOURCE,
                                 "studio": studio.BASE, "mode": MODE, "tmp": str(tmp)}), flush=True)
    srv.serve_forever()
finally:
    shutil.rmtree(tmp, ignore_errors=True)
