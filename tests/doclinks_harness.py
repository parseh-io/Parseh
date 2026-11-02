#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The server tests/doclinks.mjs drives: serve.py's handler (the studio at
/studio, a book's notes at /books/<folder>/<slug>/notes) on a TEMPORARY
studio library, a TEMPORARY exercises/ store and a TEMPORARY shelf holding
one book, seeded with documents that link to each other by name.

    python3 tests/doclinks_harness.py

Prints `READY {json}` once listening.  SIGTERM or SIGINT removes the temp
tree.  Never touches markdown/library/, exercises/ or books/."""
import json
import os
import shutil
import signal
import sys
import tempfile
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
import serve                                       # noqa: E402
Handler, studio = serve.Handler, serve.studio
# the door that says who may reach Parseh (lib/network.py): pointed at the
# temporary tree, so a suite can neither read the owner's own settings nor
# shut his Wi-Fi door by running
import network                                  # noqa: E402
import decks   # noqa: E402  (the modules the studio imported)
import notes   # noqa: E402
import store   # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="parseh-doclinks-test-"))
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
import prefs    # and the owner's preferences (lib/prefs.py): a document loads
prefs.STORE = str(tmp / "config" / "prefs.json")   # lib/prefs.js since a0.5.0
analysisconfig.STORE = str(tmp / "config" / "analysis.json")   # lib/prefs.js since a0.5.0
import languages, newlang, speechconfig    # the languages added on this machine (newlang keeps a copy of the
languages.PERSONAL = newlang.PERSONAL = str(tmp / "config" / "languages.json")   # path) and the speech settings
speechconfig.CONFIG = tmp / "config" / "speech.json"
store.LIB.mkdir()
decks.set_dir(tmp / "exercises")
decks.set_clips_dir(tmp / "clips")
store.set_clips_dir(tmp / "clips")
if "clips" in sys.modules:                         # the hub's own tray routes
    sys.modules["clips"].set_dir(tmp / "clips")
assert store.lib() == tmp / "library" and decks.DIR == tmp / "exercises"

# one book on a shelf of its own, for its notes
SHELF = tmp / "books"
BOOK = SHELF / "persian" / "reader"
BOOK.mkdir(parents=True)
(BOOK / "book.json").write_text(json.dumps({"title": "A Persian reader", "lang": "fa"}),
                                encoding="utf-8")


def parked_book(url_path):
    parts = url_path.strip("/").split("/")
    if len(parts) != 3 or parts[0] != "books" or not all(
            p and not p.startswith(".") for p in parts):
        return None
    d = SHELF.joinpath(*parts[1:])
    return str(d) if (d / "book.json").is_file() else None


serve.book_dir = parked_book


def cleanup(*_):
    shutil.rmtree(tmp, ignore_errors=True)
    os._exit(0)


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)
Handler.log_message = lambda self, *a: None
Handler.log_request = lambda self, *a, **k: None


NAMES = ["Plain", "Table 7-6 (percentages)", "a)b", "(a", "((a))", "(((a)))", "a\\b",
         "x (y (z (q) r) w) v", ")(", "شکل کلمهٔ فارسی", "日本語のノート", "two\nlines"]


def doc(title, body, target="en"):
    return ("---\ntitle: %s\nsubtitle:\nnote:\nlang: en\ntarget: %s\n---\n\n%s\n"
            % (title, target, body))


try:
    verbs = store.create(doc("Verbs of motion", "Going and coming. See also [myself](doc:Verbs of motion)."))
    taken = store.create(doc("Taken", "A document whose name is wanted."))
    grammar = store.create(doc("Grammar", "The first chapter is about [the verbs](doc:Verbs of motion), "
                                          "and then [](doc:verbs OF motion) again, with its title."))
    persian = store.create(doc("شکل کلمه", "کلمه‌ها در [فعل‌های حرکتی](doc:Verbs of motion) "
                                           "هم دیده می‌شوند.", target="fa"))
    legacy = store.create(doc("Old links", "Written before names: [the verbs](doc:%s)." % verbs["uid"]))
    lonely = store.create(doc("Lonely", "Nothing links here."))
    gone = store.create(doc("Gone soon", "Deleted before the test starts."))
    waiting = store.create(doc("Waiting", "Linked to [a deleted one](doc:Gone soon)."))
    store.delete(gone["id"])
    # a book's notes: the same store, another library
    with notes.library(BOOK):
        n1 = notes.create(BOOK, "after", "sub", "1.1-abc", "fa")
        n2 = notes.create(BOOK, "after", "sub", "1.2-def", "fa")
        _m, text = store.get(n2["id"])
        store.save_markdown(n2["id"], text.replace("Written by hand", "About [the first note](doc:A note), written by hand"))
    store.follow_renames(decks.rename_doc_links)       # as serve.py's start-up does

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    srv.daemon_threads = True
    studio.SERVER["instance"] = srv
    print("READY " + json.dumps({
        "port": srv.server_address[1], "studio": studio.BASE, "library": str(store.LIB),
        "notes": "/books/persian/reader/notes",
        "docs": {"verbs": verbs["id"], "taken": taken["id"], "grammar": grammar["id"],
                 "persian": persian["id"], "legacy": legacy["id"], "lonely": lonely["id"],
                 "waiting": waiting["id"]},
        "notes_docs": {"first": n1["id"], "second": n2["id"]},
        # the page's escapeDocName must write what texgen.escape_doc_name does
        "escapes": dict((n, studio.texgen.escape_doc_name(n)) for n in NAMES)},
        ensure_ascii=False), flush=True)
    srv.serve_forever()
finally:
    shutil.rmtree(tmp, ignore_errors=True)
