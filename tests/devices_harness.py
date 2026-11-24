#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Parseh's REAL server for Settings -> Devices (lib/devicespage.py, a0.7.0 lane E)
on a temporary tree, for tests/devices_page.mjs:

    python3 tests/devices_harness.py serve <tmp> <port>

Every store points into <tmp> (tests/cardkit_harness.py serve_it), so config/,
config/sync/ and config/peers.json are the tree's, never the checkout's.  The
tree holds one studio document, one deck with one exercise, one book page and
one partner ("laptop", never reachable).  Lane C's syncrules and lane D's
syncjobs are the FAKES tests/syncrules_fake.py and tests/syncjobs_fake.py,
seeded with a choice on the document, a deletion of the book, a grouped
deletion of three clips and a deletion-edited -- unless DEVICES_REAL=1, which
leaves the real modules (once merged) in place.

Prints "SEEDED <json>" (the ids the browser test needs) before the server starts.
"""
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
os.chdir(REPO)
for folder in ("markdown/exlex", "markdown/app", "youtube/lib", "lib", "tests", "."):
    sys.path.insert(0, str(REPO / folder))


def serve_tree(tmp, port):
    tmp = Path(tmp)
    for d in ("config", "root/youtube/videos", "root/books/persian/demo", "library", "exercises", "anki", "tray"):
        (tmp / d).mkdir(parents=True, exist_ok=True)
    if os.environ.get("DEVICES_REAL") != "1":
        import syncrules_fake
        import syncjobs_fake
        sys.modules["syncrules"] = syncrules_fake
        sys.modules["syncjobs"] = syncjobs_fake
    import prefs
    prefs.STORE = str(tmp / "config" / "prefs.json")
    import store
    import decks
    store.LIB = tmp / "library"
    decks.set_dir(tmp / "exercises")
    doc = store.create("---\ntitle: The bell\nsubtitle:\nnote:\nlang: en\ntarget: fa\n---\n\nHello.\n\n"
                       "The bell rang twice.\n")
    deck = decks.create_deck("Words", "fa")
    folder, slug = deck["path"].split("/") if "path" in deck else (deck["folder"], deck["slug"])
    item = decks.add_item(folder, slug, ":::exercise true-false\nprompt: Read -> decide.\n- up -> down => true\n:::")
    (tmp / "root/books/persian/demo/index.html").write_text(
        '<!doctype html><html><head><meta charset="utf-8"><title>Demo book</title>'
        '<script src="/lib/parseh.js"></script></head><body><h1>Demo book</h1><p>A page of a book.</p></body></html>',
        encoding="utf-8")
    peers = {"format": 1, "partners": {"p-laptop": {
        "id": "p-laptop", "name": "laptop", "cert": "", "fingerprint": "ab" * 32, "protocol": 1,
        "addresses": ["127.0.0.1:9"], "last_ok": None, "paired": time.time() - 86400, "last_seen": None,
        "device": {"send_only": False, "holds_little": True}},
        # a partner that removed this computer (lane H): its row says so and offers to remove it here too
        "p-desk": {
        "id": "p-desk", "name": "desk", "cert": "", "fingerprint": "cd" * 32, "protocol": 1,
        "addresses": ["127.0.0.1:9"], "last_ok": None, "paired": time.time() - 86400, "last_seen": None,
        "removed_you": {"at": time.time() - 3600, "by": "desk"}}}}
    # THIS INSTALL'S IDENTITY WAS MADE ON ANOTHER MACHINE ("oldbox"), as a copied folder's is: the page says so
    (tmp / "config" / "sync").mkdir(parents=True, exist_ok=True)
    (tmp / "config" / "sync" / "identity.json").write_text(json.dumps({
        "format": 1, "install": "0123456789abcdef" * 2, "name": "testbox", "created": time.time() - 86400,
        "key": None, "machine": {"id": "0" * 64, "host": "oldbox"}}), encoding="utf-8")
    # the shared scripts (/lib/parseh.js, /lib/syncpage.js) are served from the root, as in a checkout
    if not (tmp / "root" / "lib").exists():
        (tmp / "root" / "lib").symlink_to(REPO / "lib")
    (tmp / "config" / "peers.json").write_text(json.dumps(peers), encoding="utf-8")
    doc_uid = "doc:persian/%s" % doc["id"]
    item_id = (item.get("items") or [{}])[0].get("id")
    if os.environ.get("DEVICES_REAL") != "1":
        syncrules_fake.seed(str(tmp / "fake-diffs"), doc=doc_uid, book="book:persian/demo")
        syncjobs_fake.seed()
    print("SEEDED " + json.dumps({"doc": doc["id"], "doc_uid": doc_uid, "deck": "%s/%s" % (folder, slug),
                                  "item": item_id}), flush=True)
    # A SYNC WRITING THE DOCUMENT, on the test's word: while <tmp>/hold-write exists, synclock.sync_write holds the
    # document as the exchange does while it writes a partner's version, and an editor asking to open it is Busy
    import threading
    import synclock

    def hold():
        flag = tmp / "hold-write"
        while True:
            if flag.exists():
                try:
                    with synclock.sync_write(doc_uid):
                        while flag.exists():
                            time.sleep(0.05)
                except synclock.Busy:
                    pass
            time.sleep(0.05)
    threading.Thread(target=hold, daemon=True).start()
    import cardkit_harness
    cardkit_harness.serve_it(tmp, port, True, "tray")


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "serve":
        sys.exit(__doc__)
    serve_tree(sys.argv[2], int(sys.argv[3]))
