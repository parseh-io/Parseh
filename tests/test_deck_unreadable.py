# SPDX-License-Identifier: GPL-3.0-or-later
"""An exercise file that cannot be read is named, not dropped (TO-DO a0.6.3 G1).

    python3 -m unittest tests.test_deck_unreadable

A deck whose items/ holds one file that does not parse still opens with its
good exercises, and its summary -- the decks page's card and the deck's own
page both draw from it -- carries "unreadable": the files passed over, as
paths inside the deck.  A deck with none carries no such key, so every other
answer is byte for byte as it was.  A folder with no deck.json is not a deck
(create_deck writes deck.json with the folder; an import is staged under a
dot name): list_decks names it in `stray`, and leaves it alone.

On the old code the broken file vanished without a word: no "unreadable" key,
no `stray` argument.  Everything works in a temporary exercises/ folder.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib"):
    if str(ROOT / p) not in sys.path:
        sys.path.insert(0, str(ROOT / p))

import decks      # noqa: E402
import languages  # noqa: E402

FLASH = ":::exercise flashcard\nfront: [گربه]{tl}\nback: cat\n:::"
BROKEN = b'{"markdown": ":::exercise flashcard\\nfront: x'


class Unreadable(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.base = Path(td.name) / "exercises"
        p = patch.object(decks, "DIR", self.base)
        p.start()
        self.addCleanup(p.stop)
        self.deck = decks.create_deck("Words", "fa")
        decks.add_item(self.deck["folder"], self.deck["slug"], FLASH)
        self.dir = self.base / self.deck["path"]

    def test_a_clean_deck_has_no_key(self):
        self.assertNotIn("unreadable", decks.get_deck(self.deck["folder"], self.deck["slug"]))
        found = decks.list_decks()
        self.assertNotIn("unreadable", found[0])

    def test_the_broken_file_is_named_and_the_rest_opens(self):
        (self.dir / "items" / "0123456789ab.json").write_bytes(BROKEN)
        (self.dir / "items" / "abcdefabcdef.json").write_text('{"no": "markdown"}')
        (self.dir / "items" / "not-an-id.json").write_text("[]")
        got = decks.get_deck(self.deck["folder"], self.deck["slug"])
        self.assertEqual(got["counts"]["total"], 1)
        self.assertEqual(got["unreadable"], ["items/0123456789ab.json",
                                             "items/abcdefabcdef.json",
                                             "items/not-an-id.json"])
        self.assertEqual(len(decks.list_items(self.deck["folder"], self.deck["slug"])), 1)
        listed = decks.list_decks()
        self.assertEqual(listed[0]["unreadable"], got["unreadable"])
        # nothing was changed
        self.assertEqual((self.dir / "items" / "0123456789ab.json").read_bytes(), BROKEN)

    def test_a_folder_without_deck_json_is_stray(self):
        L = languages.get("fa")
        lost = self.base / L.folder / "half-made"
        (lost / "items").mkdir(parents=True)
        (lost / "items" / "0123456789ab.json").write_text("{}")
        damaged, stray = [], []
        found = decks.list_decks(damaged=damaged, stray=stray)
        self.assertEqual([d["slug"] for d in found], [self.deck["slug"]])
        self.assertEqual(damaged, [])
        self.assertEqual(stray, [{"folder": L.folder, "slug": "half-made",
                                  "path": "%s/half-made" % L.folder, "lang": "fa",
                                  "language": L.name, "files": 1}])
        self.assertTrue((lost / "items" / "0123456789ab.json").is_file())
        # a deck.json that is there but broken stays a damaged card, not a stray
        (lost / "deck.json").write_text("{")
        damaged, stray = [], []
        decks.list_decks(damaged=damaged, stray=stray)
        self.assertEqual([d["slug"] for d in damaged], ["half-made"])
        self.assertEqual(stray, [])


if __name__ == "__main__":
    unittest.main()
