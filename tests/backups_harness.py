#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Parseh's REAL handler for Settings -> Backups (lib/backupspage.py, TO-DO §13.19) on a temporary tree, for
tests/backups_door.mjs.

EVERY STORE AND EVERY SHELF POINTS AT THE TEMPORARY FOLDER, never at the checkout: config/ (each store by its own
constant, tests/test_harness_stores.py holds this list to the product's), the language files a backup carries
(lib/lang, docs/lang, the studio's starters), the books, the videos, the studio library, the exercise decks, the
Anki card store and the clip tray; a bundle installs into the tree, and the library page is not written.

Prints READY {port}; reads one JSON command a line and answers OK <json>:
    {"what": "seed"}                     a computer with one of everything
    {"what": "change"}                   after a backup: a newer place, a prompt rewritten, a flag removed
    {"what": "wipe"}                     a new computer: every shelf and every store empty
    {"what": "look"}                     what is there now
    {"what": "damage", "from", "to", "member"}   a copy of a zip with one member's bytes changed
"""
import json
import os
import shutil
import signal
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", ".", "tests"):
    sys.path.insert(0, str(ROOT / p))
import analysisconfig   # noqa: E402
import books            # noqa: E402
import bundle           # noqa: E402
import clips            # noqa: E402
import langprompts      # noqa: E402
import languages        # noqa: E402
import later            # noqa: E402
import latexthemes      # noqa: E402
import network          # noqa: E402
import newlang          # noqa: E402
import offline          # noqa: E402
import prefs            # noqa: E402
import prompts          # noqa: E402
import shelf            # noqa: E402
import speechconfig     # noqa: E402
import serve            # noqa: E402
import ytpages          # noqa: E402

AS_PHONE = "--as-phone" in sys.argv[1:]
tmp = Path(tempfile.mkdtemp(prefix="parseh-backups-door-test-"))
CFG = tmp / "config"
network.STORE = str(CFG / "network.json")
prefs.STORE = str(CFG / "prefs.json")
offline.DIGESTS = str(CFG / "digests.json")
offline.WHERES = str(CFG / "wheres.json")
prompts.STORE = str(CFG / "prompts.json")
latexthemes.STORE = str(CFG / "latex.json")
languages.PERSONAL = newlang.PERSONAL = str(CFG / "languages.json")
speechconfig.CONFIG = CFG / "speech.json"
analysisconfig.STORE = str(CFG / "analysis.json")
LANG, DOCS, STARTERS = tmp / "lib-lang", tmp / "docs-lang", tmp / "starters"
langprompts.LANG_FILES, langprompts.LANG_DOCS, langprompts.STARTERS = str(LANG), str(DOCS), str(STARTERS)
languages.write_css = lambda path=None: str(tmp / "langs.css")
SHELF = tmp / "root"
serve.ROOT = str(SHELF)
serve._AtRoot.directory = str(SHELF)
books.BOOKS_DIR = str(SHELF / "books")
ytpages.VIDEOS = str(SHELF / "youtube" / "videos")
serve.ANKI = ytpages.ANKI = str(tmp / "anki")
ytpages.INBOX = str(tmp / "anki" / "inbox")
clips.set_dir(tmp / "clips")
for st in {serve.studio.store}:
    st.LIB = tmp / "library"
serve.studio.decks.set_dir(tmp / "exercises")
_install, _inspect = bundle.install, bundle.inspect
bundle.install = lambda data, replace=False, root=str(SHELF): _install(data, replace, root)
bundle.inspect = lambda data, root=str(SHELF): _inspect(data, root)
serve.Handler._write_library = lambda self: {"ok": True}
serve.Handler.log_request = lambda self, *a, **k: None
serve.Handler.log_message = lambda self, *a: None
if AS_PHONE:
    for patched in (mock.patch.object(network, "where", lambda ip, doc=None: network.LAN),
                    mock.patch.object(network, "may_connect", lambda ip, doc=None: True),
                    mock.patch.object(network, "let_in", lambda *a, **k: True)):
        patched.start()

BOOK = ROOT / "tests" / "fixtures" / "books" / "english" / "mini-en"
VIDEO = ROOT / "tests" / "fixtures" / "videos" / "persian" / "fA6bK2mQ8sT"
READER = "/books/english/mini-en/reader/"
FLAG = "later:book:%s:1.1-abc123:2:x9" % READER
GONE = "later:book:%s:1.2-def456:1:y7" % READER


def empty():
    # the tree's own lib/ is the checkout's, linked: the pages' scripts and styles are served from serve.ROOT.
    # Only the shelves are emptied, never through the link.
    if not (SHELF / "lib").exists():
        SHELF.mkdir(parents=True, exist_ok=True)
        os.symlink(ROOT / "lib", SHELF / "lib")
    for d in (SHELF / "books", SHELF / "youtube", tmp / "library", tmp / "exercises", tmp / "anki", tmp / "clips", CFG, LANG, DOCS, STARTERS):
        shutil.rmtree(d, ignore_errors=True)
    for d in (SHELF / "books", SHELF / "youtube" / "videos", tmp / "library", tmp / "exercises", tmp / "anki",
              tmp / "clips", CFG, LANG, DOCS, STARTERS):
        d.mkdir(parents=True, exist_ok=True)
    languages.reload()


def seed():
    empty()
    shutil.copytree(BOOK, SHELF / "books" / "english" / "mini-en")
    shutil.copytree(VIDEO, SHELF / "youtube" / "videos" / "persian" / VIDEO.name)
    serve.studio.store.create("# A page of mine\n\nWritten on the old computer.\n")
    deck = serve.studio.decks.create_deck("Old deck", "en")
    anki = tmp / "anki" / "english" / "market"
    (anki / "cards").mkdir(parents=True)
    (anki / "deck.json").write_text(json.dumps({"name": "Market", "lang": "en"}), encoding="utf-8")
    (anki / "cards" / "c1.json").write_text(json.dumps({"front": "hello", "back": "salaam"}), encoding="utf-8")
    (tmp / "anki" / "notetypes.json").write_text("{}", encoding="utf-8")
    (tmp / "anki" / "build").mkdir()
    (tmp / "anki" / "build" / "old.apkg").write_bytes(b"made again")
    (tmp / "clips" / "hello-abc123.png").write_bytes(b"\x89PNG\r\n\x1a\nnot really")
    (tmp / "clips" / "hello-abc123.png.json").write_text(json.dumps({"lang": "en", "text": "hello"}),
                                                         encoding="utf-8")
    now = time.time()
    prefs.set_settings({"bk_rate": {"v": "1.25", "at": now - 500}, "bk_lvl:fa:vocal": {"v": "Mine", "at": now - 500}})
    prefs.set_place(READER, 4, "1.4", at=now - 500)
    later.apply_ops([{"op": "add", "record": {"id": FLAG, "kind": "book", "ref": READER, "text": "the clock",
                                              "title": "Mini", "at": now - 500}},
                     {"op": "add", "record": {"id": GONE, "kind": "book", "ref": READER, "text": "the bell",
                                              "title": "Mini", "at": now - 400}}])
    prompts.save({"surface": "ask", "name": "brief", "text": "Answer in one line."})
    row = dict(json.loads((ROOT / "lib" / "languages.json").read_text(encoding="utf-8"))["it"],
               name="Basque", native="Euskara", folder="basque", tag="eu")
    languages.write_store({"eu": row})
    (LANG / "eu.tex").write_text("% the LaTeX of Basque, written here\n", encoding="utf-8")
    (DOCS / "eu.md").write_text("# Basque\n", encoding="utf-8")
    languages.reload()
    analysisconfig.save({"lookup": "show"})
    return {"deck": deck.get("name"), "flag": FLAG}


def change():
    now = time.time()
    prefs.set_place(READER, 9, "3.1", at=now)
    later.apply_ops([{"op": "remove", "id": GONE, "at": now}])
    p = next(x for x in prompts.all_of() if x["name"] == "brief")
    prompts.save({"id": p["id"], "text": "Answer at length."})
    analysisconfig.save({"lookup": "assist"})
    return {"prompt": p["id"]}


def look():
    st = serve.studio.store
    anki = []
    for here, _dirs, files in os.walk(tmp / "anki"):
        anki += [os.path.relpath(os.path.join(here, f), tmp / "anki").replace(os.sep, "/") for f in files]
    return {"books": [os.path.basename(d) for d in shelf.items("book")],
            "videos": [os.path.basename(d) for d in shelf.items("video")],
            "docs": [d.get("name") or d.get("title") for d in st.list_docs()],
            "decks": [m.get("name") for _f, _s2, _p, m in serve.studio.decks._shelf_decks()],
            "anki": sorted(anki),
            "clips": sorted(os.listdir(tmp / "clips")) if (tmp / "clips").is_dir() else [],
            "places": prefs.places(),
            "settings": {k: v["v"] for k, v in prefs.settings().items()},
            "flags": sorted(e["id"] for e in later.all_of()),
            "prompts": {p["name"]: p["text"] for p in prompts.all_of()},
            "languages": sorted(languages.read_store()),
            "eu_tex": (LANG / "eu.tex").is_file(),
            "eu_known": languages.by_folder("basque") is not None,
            "analysis": analysisconfig.load(),
            "config": sorted(os.listdir(CFG)) if CFG.is_dir() else []}


def damage(c):
    src, dst, member = c["from"], c["to"], c["member"]
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w") as zo:
        for info in zi.infolist():
            data = zi.read(info)
            if info.filename == member:
                data = data[:-1] + bytes([data[-1] ^ 0x55]) if data else b"x"
            zo.writestr(info, data)
    return {"ok": True}


def command(line):
    c = json.loads(line)
    what = c.get("what")
    if what == "seed":
        return seed()
    if what == "change":
        return change()
    if what == "wipe":
        empty()
        return {"ok": True}
    if what == "look":
        return look()
    if what == "damage":
        return damage(c)
    raise ValueError("no such command: %r" % what)


def main():
    empty()
    srv = serve.Server(("127.0.0.1", 0), serve.Handler, None)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("READY " + json.dumps({"port": srv.server_address[1], "tmp": str(tmp)}), flush=True)

    def bye(*_a):
        shutil.rmtree(tmp, ignore_errors=True)
        os._exit(0)
    signal.signal(signal.SIGTERM, bye)
    signal.signal(signal.SIGINT, bye)
    for line in sys.stdin:
        try:
            out = command(line)
            print("OK" + ((" " + json.dumps(out)) if out is not None else ""), flush=True)
        except Exception as e:      # noqa: BLE001
            import traceback
            traceback.print_exc()
            print("ERR %s" % e, flush=True)
    bye()


if __name__ == "__main__":
    main()
