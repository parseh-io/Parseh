# SPDX-License-Identifier: GPL-3.0-or-later
"""The units of sync (lib/syncunits.py, docs/sync.md).

    python3 -m unittest tests/test_sync_units.py

A tree holding one of every kind of unit: walk() finds each, under the id the
contract gives it; each unit's files are its own and never what is built,
cached or temporary; locate() turns every id back into the same place; a
touched path finds the units it covers; a hash moves with the content and only
with it; an id that climbs out of its shelf is refused.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synctree import SyncTree   # noqa: E402
import syncunits                # noqa: E402


def shelf(t):
    # a book: its source, a recording, and what a build leaves (never in the unit)
    t.w("books/persian/the-bell/book.json", "{}")
    t.w("books/persian/the-bell/main.tex", "\\begin{document}")
    t.w("books/persian/the-bell/ch1.tex", "one")
    t.w("books/persian/the-bell/audio/rec.mp3", "sound")
    t.w("books/persian/the-bell/main.pdf", "built")
    t.w("books/persian/the-bell/main.aux", "built")
    t.w("books/persian/the-bell/reader/index.html", "built")
    t.w("books/persian/the-bell/.reader-key", "k")
    t.w("books/persian/the-bell/ch1.tex.123.4.tmp", "half")
    t.w("books/persian/the-bell/original/scan.pdf", "the person's")
    # its note
    t.w("books/persian/the-bell/markdown/persian/n1/source.md", "a note")
    t.w("books/persian/the-bell/markdown/persian/n1/meta.json", "{}")
    t.w("books/persian/the-bell/markdown/persian/n1/build/n1.pdf", "built")
    t.w("books/.trash/old-20260101-000000/book.json", "{}")
    # a video
    t.w("youtube/videos/english/vid1/video.json", "{}")
    t.w("youtube/videos/english/vid1/annotations.json", "{}")
    t.w("youtube/videos/english/vid1/transcript.txt", "0.0 hi")
    t.w("youtube/videos/english/vid1/wordtimes.json", "{}")
    t.w("youtube/videos/english/vid1/waveform.json", "{}")
    t.w("youtube/videos/english/.pending-transcriptions/x.json", "{}")
    # a studio document
    t.w("markdown/library/persian/doc-1/source.md", "# hi")
    t.w("markdown/library/persian/doc-1/meta.json", "{}")
    t.w("markdown/library/persian/doc-1/images/a.png", "png")
    t.w("markdown/library/persian/doc-1/build/doc.pdf", "built")
    t.w("markdown/library/persian/doc-1/.seeded-1", "")
    # a deck, two exercises, one with a picture, a schedule, a stray picture
    t.w("exercises/persian/verbs/deck.json", "{}")
    t.w("exercises/persian/verbs/items/e1.json", '{"markdown": "![](cat.png)"}')
    t.w("exercises/persian/verbs/items/e2.json", '{"markdown": "no media"}')
    t.w("exercises/persian/verbs/schedule/e1.json", '{"history": []}')
    t.w("exercises/persian/verbs/images/cat.png", "cat")
    t.w("exercises/persian/verbs/images/stray.png", "stray")
    t.w("exercises/persian/verbs/checkout.json", "{}")
    t.w("exercises/.trash/persian--old--x/deck.json", "{}")
    # the tray
    t.w("clips/c1.mp3", "s")
    t.w("clips/c1.mp3.json", "{}")
    t.w("clips/README.md", "tracked")
    # the Anki store
    t.w("youtube/anki/notetypes.json", "{}")
    t.w("youtube/anki/seen.json", "{}")
    t.w("youtube/anki/persian/main/deck.json", "{}")
    t.w("youtube/anki/persian/main/cards/k1.json", "{}")
    t.w("youtube/anki/persian/main/media/m.mp3", "m")
    t.w("youtube/anki/persian/main/deleted/k0.json", "{}")
    t.w("youtube/anki/inbox/x.apkg", "a")
    # config: prefs with a personal key, a key nobody follows, a place, a flag and a tombstone
    t.wj("config/prefs.json", {
        "settings": {"parseh_theme": {"v": "dark", "at": 1, "by": "a"},
                     "bk_lvl:fa:vocal": {"v": "Sounds", "at": 1, "by": "a"},
                     "zoom": {"v": "120", "at": 1}},
        "places": {"/books/persian/the-bell/reader/": {"i": 3, "at": 2, "by": "a"}},
        "later": {"items": {"later:a": {"kind": "book", "at": 1, "by": "x"},
                            "later:b": {"gone": 5.0, "kind": "book"}}}})
    t.wj("config/prompts.json", {"prompts": [{"id": "p1", "name": "Mine"}], "moved": {}, "unread": []})
    t.wj("config/latex.json", {"format": 1, "themes": [{"name": "plain"}], "default": "plain", "timeout": 30})
    t.wj("config/analysis.json", {"lookup": "show"})
    t.wj("config/speech.json", {"format_version": 1, "second_pass": True, "models_by_language": {"fa": "m"}})
    t.wj("config/languages.json", {"_format": 1, "xx": {"name": "Ex"}})
    t.w("lib/lang/xx.tex", "tex")
    t.w("lib/lang/xx.chunk.json", "{}")
    t.w("lib/lang/fa.tex", "shipped, not personal")
    t.w("docs/lang/xx.md", "doc")
    t.w("markdown/exlex/starters/xx.md", "starter")
    t.wj("config/network.json", {"port": 1})


EXPECTED = [
    "ankideck:persian/main", "ankimedia:persian/main/m.mp3", "ankinotetypes:", "ankiseen:",
    "book:persian/the-bell", "card:persian/main/k1", "clip:c1.mp3", "deck:persian/verbs",
    "deckfile:persian/verbs/images/stray.png", "doc:persian/doc-1", "item:persian/verbs/e1",
    "item:persian/verbs/e2", "language:xx", "later:later:a", "latextheme:plain",
    "note:book/persian/the-bell/persian/n1", "place:/books/persian/the-bell/reader/",
    "progress:persian/verbs/e1", "prompt:p1", "setting:analysis.lookup", "setting:bk_lvl:fa:vocal",
    "setting:latex.default", "setting:latex.timeout", "setting:parseh_theme",
    "setting:speech.model.fa", "setting:speech.second_pass", "video:english/vid1"]


class Units(SyncTree):
    def setUp(self):
        super().setUp()
        shelf(self)

    def test_every_kind_found_by_its_id(self):
        self.assertEqual(self.ids(), EXPECTED)

    def test_files_are_the_units_own(self):
        by = {u.id: u for u in syncunits.walk()}
        self.assertEqual(sorted(syncunits.files_of(by["book:persian/the-bell"])),
                         ["audio/rec.mp3", "book.json", "ch1.tex", "main.tex", "original/scan.pdf"])
        self.assertEqual(sorted(syncunits.files_of(by["video:english/vid1"])),
                         ["annotations.json", "transcript.txt", "video.json", "wordtimes.json"])
        self.assertEqual(sorted(syncunits.files_of(by["doc:persian/doc-1"])),
                         ["images/a.png", "meta.json", "source.md"])
        self.assertEqual(sorted(syncunits.files_of(by["note:book/persian/the-bell/persian/n1"])),
                         ["meta.json", "source.md"])
        self.assertEqual(sorted(syncunits.files_of(by["item:persian/verbs/e1"])),
                         ["images/cat.png", "items/e1.json"])
        self.assertEqual(sorted(syncunits.files_of(by["item:persian/verbs/e2"])), ["items/e2.json"])
        self.assertEqual(sorted(syncunits.files_of(by["clip:c1.mp3"])), ["c1.mp3", "c1.mp3.json"])
        self.assertEqual(sorted(syncunits.files_of(by["language:xx"])),
                         ["docs/xx.md", "lang/xx.chunk.json", "lang/xx.tex", "starters/xx.md"])

    def test_rules(self):
        self.assertEqual(syncunits.rule_of("progress:a/b/c"), syncunits.PROGRESS)
        self.assertEqual(syncunits.rule_of("clip:x"), syncunits.ADDITIONS)
        self.assertEqual(syncunits.rule_of("place:/x"), syncunits.LATEST)
        self.assertEqual(syncunits.rule_of("deckfile:a/b/images/c"), syncunits.IMMUTABLE)
        self.assertEqual(syncunits.rule_of("doc:a/b"), syncunits.CHOICE)

    def test_locate_gives_back_every_unit(self):
        for u in syncunits.walk():
            got = syncunits.locate(u.id)
            self.assertEqual((got.where, got.key, got.rule), (u.where, u.key, u.rule), u.id)

    def test_locate_refuses_climbing_out_and_device_keys(self):
        for bad in ("book:../x", "book:persian/..", "video:a/.trash", "doc:a/b/c", "nope:x",
                    "setting:zoom", "setting:network.port", "clip:../../etc", "language:../x"):
            with self.assertRaises(KeyError, msg=bad):
                syncunits.locate(bad)

    def test_hash_moves_with_content_only(self):
        u = syncunits.locate("book:persian/the-bell")
        a = syncunits.snapshot(u)["hash"]
        self.w("books/persian/the-bell/main.pdf", "built again")            # derived: no change
        self.assertEqual(syncunits.snapshot(u)["hash"], a)
        self.w("books/persian/the-bell/ch1.tex", "two")
        self.assertNotEqual(syncunits.snapshot(u)["hash"], a)
        s = syncunits.locate("setting:parseh_theme")
        h = syncunits.snapshot(s)["hash"]
        self.wj("config/prefs.json", {"settings": {"parseh_theme": {"v": "dark", "at": 9, "by": "b"}}})
        self.assertEqual(syncunits.snapshot(s)["hash"], h)                  # when and by whom: no change
        self.assertIsNone(syncunits.snapshot(syncunits.locate("later:later:b")))   # a tombstone is deleted

    def test_units_for_a_touched_path(self):
        f = lambda p: sorted(u.id for u in syncunits.units_for(self.p(p)))   # noqa: E731
        self.assertEqual(f("books/persian/the-bell"), ["book:persian/the-bell",
                                                      "note:book/persian/the-bell/persian/n1"])
        self.assertEqual(f("books/persian/the-bell/ch1.tex"), ["book:persian/the-bell"])
        self.assertEqual(f("exercises/persian/verbs/images/cat.png"), ["item:persian/verbs/e1"])
        self.assertEqual(f("exercises/persian/verbs/schedule/e1.json"), ["progress:persian/verbs/e1"])
        self.assertEqual(f("clips/c1.mp3.json"), ["clip:c1.mp3"])
        self.assertEqual(f("youtube/anki/seen.json"), ["ankiseen:"])
        self.assertIn("setting:parseh_theme", f("config/prefs.json"))
        self.assertEqual(f("config/network.json"), [])


if __name__ == "__main__":
    unittest.main()
