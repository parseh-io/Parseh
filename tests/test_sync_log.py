# SPDX-License-Identifier: GPL-3.0-or-later
"""The change log (lib/synclog.py) and the hooks that feed it (docs/sync.md).

    python3 -m unittest tests/test_sync_log.py

  * THE SCAN finds every unit, records each once, records nothing the second
    time, catches a file changed outside Parseh, and leaves a tombstone for a
    unit that went;
  * THE HOOKS: a write through the real writers -- storeguard (prefs), the
    studio store, the decks, the clip tray, pathlock -- is recorded by flush()
    alone, with no scan; a deletion through them too;
  * VERSION VECTORS: one side, both sides, merge; adopt() records a partner's
    version without counting it as this install's; chosen() puts this side
    ahead of both; forget() drops only a tombstone;
  * a unit sync is writing is skipped and looked at again afterwards;
  * the log lives in config/sync/ beside prefs.STORE, never the checkout's.
"""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synctree import SyncTree   # noqa: E402
import pathlock                 # noqa: E402
import prefs                    # noqa: E402
import synclock                 # noqa: E402
import synclog                  # noqa: E402
import synctouch                # noqa: E402
import syncunits                # noqa: E402


class Log(SyncTree):
    def test_lives_beside_prefs_store(self):
        self.assertEqual(synclog.home(), os.path.join(self.t, "config", "sync"))
        synclog.scan()
        self.assertTrue(os.path.isfile(os.path.join(self.t, "config", "sync", "log.sqlite")))

    def test_scan_records_once_and_catches_outside_writes(self):
        self.w("books/persian/b/book.json", "{}")
        self.w("books/persian/b/ch.tex", "one")
        got = synclog.scan()
        self.assertEqual([(c["unit"], c["op"]) for c in got], [("book:persian/b", "put")])
        me = synclog._me()
        self.assertEqual(got[0]["vv"], {me: 1})
        self.assertEqual(synclog.scan(), [])                          # nothing moved
        synctouch.drain()
        self.w("books/persian/b/ch.tex", "two")                       # by hand: no hook
        got = synclog.scan()
        self.assertEqual([(c["unit"], c["op"], c["vv"]) for c in got], [("book:persian/b", "put", {me: 2})])
        row = synclog.get("book:persian/b")
        self.assertEqual(sorted(row["files"]), ["book.json", "ch.tex"])
        import shutil
        shutil.rmtree(self.p("books/persian/b"))
        got = synclog.scan()
        self.assertEqual([(c["unit"], c["op"]) for c in got], [("book:persian/b", "delete")])
        row = synclog.get("book:persian/b")
        self.assertTrue(row["deleted"])
        self.assertIsNone(row["hash"])
        self.assertEqual(row["vv"], {me: 3})
        self.assertEqual(synclog.rows(deleted=True)[0]["unit"], "book:persian/b")
        self.assertTrue(synclog.forget("book:persian/b"))
        self.assertIsNone(synclog.get("book:persian/b"))

    def test_hooks_feed_flush_without_a_scan(self):
        synclog.scan()
        # storeguard, through prefs' own writer
        prefs.set_settings({"parseh_theme": {"v": "dark", "at": time.time()}}, by="test")
        got = synclog.flush()
        self.assertEqual([(c["unit"], c["op"]) for c in got], [("setting:parseh_theme", "put")])
        # the clip tray's own writer, then its delete
        import clips
        was = clips.DIR
        clips.DIR = syncunits.SHELVES["clips"]
        try:
            with open(os.path.join(clips.DIR, "c.mp3"), "w") as fh:
                fh.write("s")
            clips._write_json(os.path.join(clips.DIR, "c.mp3.json"), {"lang": "fa"})
            got = synclog.flush()
            self.assertEqual([(c["unit"], c["op"]) for c in got], [("clip:c.mp3", "add")])
            self.assertEqual(sorted(got[0]["added"]["files"]), ["c.mp3", "c.mp3.json"])
            clips.delete("c.mp3")
            got = synclog.flush()
            self.assertEqual([(c["unit"], c["op"]) for c in got], [("clip:c.mp3", "delete")])
        finally:
            clips.DIR = was
        # pathlock: a book's write through its temporary name
        d = self.p("books/persian/b")
        os.makedirs(d)
        target = os.path.join(d, "ch.tex")
        with pathlock.held(d):
            tmp = pathlock.tmp(target)
            with open(tmp, "w") as fh:
                fh.write("x")
            os.replace(tmp, target)
        got = synclog.flush()
        self.assertEqual([(c["unit"], c["op"]) for c in got], [("book:persian/b", "put")])
        self.assertEqual(synclog.flush(), [])

    def test_studio_store_and_decks_hooks(self):
        app = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markdown", "app")
        if app not in sys.path:
            sys.path.insert(0, app)
        import store
        import decks
        from pathlib import Path
        was_lib, was_dir = store.LIB, decks.DIR
        store.LIB = Path(syncunits.SHELVES["library"])
        decks.DIR = Path(syncunits.SHELVES["exercises"])
        try:
            d = Path(syncunits.SHELVES["library"]) / "persian" / "doc-a"
            d.mkdir(parents=True)
            (d / "meta.json").write_text("{}")
            (d / "source.md").write_text("# a")
            synclog.scan()
            store._write_meta(store.doc_dir("doc-a"), {"title": "A"})
            got = synclog.flush()
            self.assertEqual([(c["unit"], c["op"]) for c in got], [("doc:persian/doc-a", "put")])
            store.delete("doc-a")
            got = synclog.flush()
            self.assertEqual([(c["unit"], c["op"]) for c in got], [("doc:persian/doc-a", "delete")])
            deck = decks.DIR / "persian" / "v"
            decks._write_json(deck / "deck.json", {"name": "v"})
            decks._write_json(deck / "items" / "e1.json", {"id": "e1", "markdown": "x"})
            got = synclog.flush()
            self.assertEqual(sorted((c["unit"], c["op"]) for c in got),
                             [("deck:persian/v", "put"), ("item:persian/v/e1", "put")])
            decks._remove(deck, {"id": "e1"})
            got = synclog.flush()
            self.assertEqual([(c["unit"], c["op"]) for c in got], [("item:persian/v/e1", "delete")])
        finally:
            store.LIB, decks.DIR = was_lib, was_dir

    def test_vectors(self):
        self.assertEqual(synclog.compare({"a": 2}, {"a": 1}), "ahead")
        self.assertEqual(synclog.compare({"a": 1}, {"a": 1, "b": 1}), "behind")
        self.assertEqual(synclog.compare({"a": 2, "b": 1}, {"a": 1, "b": 2}), "both")
        self.assertEqual(synclog.compare({}, {}), "same")
        self.assertEqual(synclog.merge({"a": 2, "b": 1}, {"a": 1, "c": 3}), {"a": 2, "b": 1, "c": 3})

    def test_adopt_is_not_a_local_change_and_chosen_is_ahead(self):
        self.w("clips/c.mp3", "s")
        synclog.scan()
        me = synclog._me()
        theirs = {"partner": 4}
        u = "clip:c.mp3"
        with synclock.sync_write(u):
            self.w("clips/c.mp3", "theirs")
            synctouch.touch(self.p("clips/c.mp3"))
            self.assertEqual(synclog.flush(), [])                        # skipped while sync writes
            snap = syncunits.snapshot(syncunits.locate(u))
            synclog.adopt(u, snap["hash"], theirs, snap["files"], by="partner")
        self.assertEqual(synclog.flush(), [])                            # looked at again: the same
        self.assertEqual(synclog.get(u)["vv"], {me: 1, "partner": 4})
        c = synclog.chosen(u, {"partner": 5})
        self.assertEqual(c["vv"], {me: 2, "partner": 5})
        self.assertEqual(synclog.compare(c["vv"], {me: 1, "partner": 5}), "ahead")
        self.assertFalse(synclog.forget(u))                              # a live unit is never forgotten
        ops = [ch["op"] for ch in synclog.changes_since(0)]
        self.assertEqual(ops, ["add", "adopt", "choose"])
        self.assertEqual(synclog.last_seq(), 3)

    def test_overflow_means_a_scan(self):
        self.w("clips/c.mp3", "s")
        was = synctouch.LIMIT
        synctouch.LIMIT = 2
        try:
            for i in range(5):
                synctouch.touch(self.p("nowhere/%d" % i))
            got = synclog.flush()
        finally:
            synctouch.LIMIT = was
        self.assertEqual([c["unit"] for c in got], ["clip:c.mp3"])

    def test_filehash_cache_reads_a_file_once(self):
        p = self.w("clips/c.mp3", "s" * 100)
        calls = []
        real = syncunits.sha256_file
        syncunits.sha256_file = lambda path: calls.append(path) or real(path)
        try:
            synclog.scan()
            synctouch.touch(p)
            synclog.flush()
        finally:
            syncunits.sha256_file = real
        self.assertEqual(calls.count(p), 1)


if __name__ == "__main__":
    unittest.main()
