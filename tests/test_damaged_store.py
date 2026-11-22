# SPDX-License-Identifier: GPL-3.0-or-later
"""A personal store that does not parse is set aside, never written over (TO-DO §2.29).

    python3 -m unittest tests.test_damaged_store

Each of the person's JSON stores in config/ read a file that does not parse
as empty -- and its next save wrote over it, so every reading place, every
prompt, every device let in went with one click.  Here, for each store: broken
bytes are written where the store is, the store's own save is called, and the
broken bytes must be found again, byte for byte, under the dated name
`<store>.damaged-YYYYMMDD-HHMMSS` beside the fresh file.  On the old code each
of these fails: the broken file is simply gone.

Then the hub's sentence (serve.damaged_notice) and its "I have read this"
(storeguard.seen), and a deck whose deck.json does not parse, which the decks
page now draws as a damaged card instead of leaving out.

Nothing here writes the checkout's config/: every store points into a
temporary folder for as long as its test runs.
"""
import glob
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", "."):
    if str(ROOT / p) not in sys.path:
        sys.path.insert(0, str(ROOT / p))

import storeguard  # noqa: E402

BROKEN = b'{"settings": {"bk_rate": {"v": "1.2", "at": 1, "by": ""}}, "places": {"books/x/ma'


class _Case(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.config = os.path.join(self._td.name, "config")
        os.makedirs(self.config)

    def broken_at(self, name, data=BROKEN):
        path = os.path.join(self.config, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def assert_set_aside(self, path, data=BROKEN):
        aside = glob.glob(path + ".damaged-*")
        self.assertEqual(len(aside), 1, "the broken file was not set aside: %s"
                         % os.listdir(os.path.dirname(path)))
        self.assertRegex(os.path.basename(aside[0]),
                         r"\.json\.damaged-\d{8}-\d{6}$")
        with open(aside[0], "rb") as fh:
            self.assertEqual(fh.read(), data, "the broken bytes did not survive")
        with open(path, encoding="utf-8") as fh:
            json.load(fh)               # and the store itself was started fresh
        self.assertEqual([n for n in os.listdir(os.path.dirname(path)) if n.endswith(".tmp")], [])
        return aside[0]


class TheStores(_Case):
    def test_prefs(self):
        import prefs
        path = self.broken_at("prefs.json")
        with patch.object(prefs, "STORE", path):
            self.assertEqual(prefs.settings(), {})      # read as empty: a page must open
            prefs.set_settings({"bk_rate": {"v": "1.5"}})
        self.assert_set_aside(path)

    def test_prefs_not_an_object(self):
        import prefs
        path = self.broken_at("prefs.json", b"[1, 2, 3]\n")
        with patch.object(prefs, "STORE", path):
            prefs.set_place("books/a/main.tex", 3)
        self.assert_set_aside(path, b"[1, 2, 3]\n")

    def test_network(self):
        import network
        path = self.broken_at("network.json")
        with patch.object(network, "STORE", path):
            network.save({"vpn": True}, check_port=False)
        self.assert_set_aside(path)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_prompts(self):
        import prompts
        path = self.broken_at("prompts.json")
        with patch.object(prompts, "STORE", path):
            prompts.set_studio_text("my own studio prompt")
        self.assert_set_aside(path)

    def test_latex_themes(self):
        import latexthemes
        path = self.broken_at("latex.json")
        with patch.object(latexthemes, "STORE", path):
            latexthemes.set_timeout(30)
        self.assert_set_aside(path)

    def test_analysis(self):
        import analysisconfig
        path = self.broken_at("analysis.json")
        with patch.object(analysisconfig, "STORE", path):
            analysisconfig.save({})
        self.assert_set_aside(path)

    def test_speech(self):
        import speechconfig
        path = self.broken_at("speech.json")
        with patch.object(speechconfig, "CONFIG", Path(path)):
            speechconfig._write(speechconfig.load())
        self.assert_set_aside(path)

    def test_updates(self):
        import updater
        root = self._td.name
        path = self.broken_at("updates.json")
        updater.save_settings(root, daily=True)
        self.assert_set_aside(path)

    def test_a_good_file_is_simply_written(self):
        import prefs
        path = self.broken_at("prefs.json", b'{"settings": {}, "places": {}}\n')
        with patch.object(prefs, "STORE", path):
            prefs.set_settings({"bk_rate": {"v": "1.5"}})
            prefs.set_settings({"bk_gap": {"v": "1"}})
        self.assertEqual(glob.glob(path + ".damaged-*"), [])

    def test_two_in_one_second_keep_both(self):
        path = self.broken_at("prompts.json", b"one")
        storeguard.write_json(path, {"prompts": []})
        with open(path, "wb") as fh:
            fh.write(b"two")
        storeguard.write_json(path, {"prompts": []})
        kept = sorted(Path(p).read_bytes() for p in glob.glob(path + ".damaged-*"))
        self.assertEqual(kept, [b"one", b"two"])


class SayingSo(_Case):
    def test_found_and_seen(self):
        path = self.broken_at("prefs.json")
        storeguard.write_json(path, {"settings": {}, "places": {}})
        rows = storeguard.found([self.config])
        self.assertEqual([r["store"] for r in rows], ["prefs.json"])
        self.assertEqual(storeguard.seen([self.config], [rows[0]["name"]]), 1)
        self.assertEqual(storeguard.found([self.config]), [])
        # read, not deleted
        self.assertTrue(os.path.exists(rows[0]["path"]))
        self.assertEqual(len(storeguard.found([self.config], all_=True)), 1)

    def test_the_hub_says_so(self):
        import serve
        import prefs
        path = self.broken_at("prefs.json")
        with patch.object(prefs, "STORE", path), \
                patch.object(serve, "damaged_folders", lambda: [self.config]):
            self.assertEqual(serve.damaged_notice(), "")
            prefs.set_settings({"bk_rate": {"v": "1.5"}})
            said = serve.damaged_notice()
            self.assertIn("could not read", said)
            self.assertIn("prefs.json.damaged-", said)
            self.assertIn("your reading places", said)
            self.assertIn("I have read this", said)
            storeguard.seen([self.config], [r["name"] for r in storeguard.found([self.config])])
            self.assertEqual(serve.damaged_notice(), "")


class ADamagedDeck(_Case):
    def test_listed_as_damaged(self):
        import decks
        import languages
        base = Path(self._td.name) / "exercises"
        L = languages.get("fa")
        good = base / L.folder / "good"
        bad = base / L.folder / "bad"
        with patch.object(decks, "DIR", base):
            d = decks.create_deck("Good", "fa")
            self.assertTrue((base / d["path"]).is_dir())
            bad.mkdir(parents=True)
            (bad / "deck.json").write_bytes(b'{"name": "Broken", "id": ')
            damaged = []
            found = decks.list_decks(damaged=damaged)
            self.assertEqual([x["name"] for x in found], ["Good"])
            self.assertEqual([(x["slug"], x["lang"]) for x in damaged], [("bad", "fa")])
            self.assertIn("cannot be read", damaged[0]["why"])
            # nothing was changed
            self.assertEqual((bad / "deck.json").read_bytes(), b'{"name": "Broken", "id": ')
        del good


if __name__ == "__main__":
    unittest.main()
