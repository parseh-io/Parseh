# SPDX-License-Identifier: GPL-3.0-or-later
"""A variety's translated sentences (a0.6.3, TO-DO 12.33): Arabic's dialects
have a corpus of their own, built from Tatoeba's exports under the dialect's
own codes (corpus/ar.egy-en.db), and read before the standard language's.

    python3 -m unittest tests.test_dialect_corpus

Fixtures of its own: a few sentences per corpus, made here; nothing is
downloaded (download.fetch is replaced by one that serves bytes made here,
and answers 404 for a code Tatoeba has not).
"""
import bz2
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
import corpus      # noqa: E402
import download    # noqa: E402
import getcorpus   # noqa: E402


def _bz2(text):
    return bz2.compress(text.encode("utf-8"))


# Levantine is two codes (ajp, apc); apc's second sentence is Arabizi and is not kept.
# Gulf's second code (acw) has no export at Tatoeba: it is skipped.
EXPORTS = {
    "arz-eng_links.tsv.bz2": _bz2("1\t11\n2\t12\n"),
    "arz_sentences.tsv.bz2": _bz2("1\tarz\tانا عايز اروح دلوقتي.\n2\tarz\tمش عايز.\n"),
    "ajp-eng_links.tsv.bz2": _bz2("3\t13\n"),
    "ajp_sentences.tsv.bz2": _bz2("3\tajp\tشو بدك هلق؟\n"),
    "apc-eng_links.tsv.bz2": _bz2("4\t14\n5\t15\n"),
    "apc_sentences.tsv.bz2": _bz2("4\tapc\tكتير منيح.\n5\tapc\tMa b7ebb 2Alis.\n"),
    "afb-eng_links.tsv.bz2": _bz2("6\t16\n"),
    "afb_sentences.tsv.bz2": _bz2("6\tafb\tشلونك اليوم؟\n"),
    "eng_sentences.tsv.bz2": _bz2("11\teng\tI want to go now.\n12\teng\tI don't want to.\n"
                                  "13\teng\tWhat do you want now?\n14\teng\tVery good.\n"
                                  "15\teng\tI don't like Alice.\n16\teng\tHow are you today?\n"),
}


def fake_fetch(url, dest, **kw):
    name = url.rsplit("/", 1)[-1]
    if name not in EXPORTS:
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
    with open(dest, "wb") as f:
        f.write(EXPORTS[name])


def pairs_db(path, rows, code="ar", variety=""):
    """A corpus made here: [(src, dst)], indexed as getcorpus indexes."""
    c = corpus.create(path)
    df = {}
    for s, d in rows:
        pid = c.execute("INSERT INTO pair (src, dst) VALUES (?,?)", (s, d)).lastrowid
        words = corpus.words_of(code, s)
        c.executemany("INSERT INTO tok (word, pair_id) VALUES (?,?)", [(w, pid) for w in words])
        for w in words:
            df[w] = df.get(w, 0) + 1
    c.executemany("INSERT INTO df (word, n) VALUES (?,?)", sorted(df.items()))
    c.executemany("INSERT INTO meta (key, value) VALUES (?,?)",
                  [("pairs", str(len(rows))), ("source", "a fixture"), ("variety", variety)])
    c.commit()
    c.close()


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="parseh-dialect-corpus-")
        self.dir = os.path.join(self.tmp.name, "corpus")
        self.patch = patch.object(corpus, "CORPUS_DIR", self.dir)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()


class Build(Case):
    def build(self, key):
        with patch.object(download, "fetch", fake_fetch), patch.object(download, "probe", return_value=None):
            return getcorpus.build(key, "en", say=lambda m: None)

    def test_a_variety_is_its_own_file(self):
        self.assertEqual(self.build("ar.egy"), 2)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "ar.egy-en.db")))
        self.assertFalse(corpus.available("ar", "en"), "the standard language's corpus is not touched")
        self.assertIn(("ar.egy", "en"), corpus.installed())
        m = corpus.about("ar.egy", "en")
        self.assertEqual((m["lang"], m["variety"], m["pairs"]), ("ar", "egy", "2"))

    def test_levantine_is_two_codes_and_arabizi_is_left_out(self):
        self.assertEqual(self.build("ar.lev"), 2, "ajp's one and apc's Arabic-script one; the Arabizi one dropped")
        r = corpus.look_up("ar.lev", "en", "كتير")
        self.assertEqual([p["dst"] for p in r["pairs"]], ["Very good."])

    def test_a_code_tatoeba_has_not_is_skipped(self):
        self.assertEqual(self.build("ar.gulf"), 1, "afb's sentence; acw has no export")

    def test_the_standard_language_is_read_as_before(self):
        self.assertEqual(getcorpus._isos(getcorpus._known("ar", "language")), ["ara"])
        with self.assertRaises(SystemExit):
            getcorpus._known("ar.egy", "gloss language")     # a variety is never a gloss
        with self.assertRaises(SystemExit):
            getcorpus._known("ar.xyz", "language")

    def test_offered_by_the_floor(self):
        self.assertEqual(getcorpus.offered("ar.egy"), (True, getcorpus.VARIETY_PAIRS[("ar.egy", "en")]))
        self.assertFalse(getcorpus.offered("ar.gulf")[0])
        self.assertFalse(getcorpus.offered("ar.mor")[0])
        self.assertEqual(getcorpus.offered("ar.egy", "it"), (False, None))


class Read(Case):
    def setUp(self):
        super().setUp()
        os.makedirs(self.dir)
        pairs_db(os.path.join(self.dir, "ar.egy-en.db"),
                 [("انا عايز اروح دلوقتي", "I want to go now."), ("مش عايز اروح", "I don't want to go."),
                  ("ماما مش هنا", "Mom isn't here."), ("الكتاب هنا", "The book is here.")], variety="egy")
        pairs_db(os.path.join(self.dir, "ar-en.db"),
                 [("أريد أن أروح الآن", "I want to go now."), ("أروح إلى البيت", "I go home."),
                  ("البيت كبير", "The house is big."), ("القطة نائمة", "The cat sleeps."),
                  ("أروح غدا", "I go tomorrow.")])

    def test_the_variety_first_then_the_standard_language(self):
        r = corpus.look_up_variety("ar", "egy", "en", "عايز اروح أروح", limit=10)
        kinds = [p["variety"] for p in r["pairs"]]
        self.assertTrue(kinds and kinds[0] == "egy", kinds)
        self.assertIn("", kinds, "the standard language's come after")
        self.assertEqual(kinds, sorted(kinds, reverse=True), "never a standard one before a dialect one: %s" % kinds)
        self.assertFalse(r["more"])

    def test_pages_join_into_the_whole(self):
        whole = corpus.look_up_variety("ar", "egy", "en", "عايز اروح أروح", limit=10)["pairs"]
        got, at = [], 0
        while True:
            r = corpus.look_up_variety("ar", "egy", "en", "عايز اروح أروح", limit=1, offset=at)
            got += r["pairs"]
            at += len(r["pairs"])
            if not r["more"]:
                break
        self.assertEqual([p["src"] for p in got], [p["src"] for p in whole])

    def test_no_variety_corpus_gives_the_standard_ones_marked_so(self):
        os.unlink(os.path.join(self.dir, "ar.egy-en.db"))
        r = corpus.look_up_variety("ar", "egy", "en", "أروح", limit=10)
        self.assertTrue(r["pairs"])
        self.assertEqual({p["variety"] for p in r["pairs"]}, {""})

    def test_no_variety_is_look_up(self):
        a = corpus.look_up_variety("ar", "", "en", "أروح", limit=10)
        b = corpus.look_up("ar", "en", "أروح", limit=10)
        self.assertEqual([p["src"] for p in a["pairs"]], [p["src"] for p in b["pairs"]])
        self.assertEqual({p["variety"] for p in a["pairs"]}, {""})

    def test_another_variety_does_not_read_egyptian(self):
        r = corpus.look_up_variety("ar", "lev", "en", "عايز", limit=10)
        self.assertEqual([p for p in r["pairs"] if p["variety"]], [])


if __name__ == "__main__":
    unittest.main()
