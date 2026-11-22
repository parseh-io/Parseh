#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Arabic's varieties in the word tools (a0.6.3, TO-DO 12.29 and 12.31).

  1  cutting into phrases: lib/lang/ar.<v>.chunk.json read before ar.chunk.json for a text in a variety (the variety's
     function words join Arabic's, the rest is Arabic's); a new book's or video's cut is given the variety's key; a
     standard text is cut exactly as before
  2  romanisation: lib/lang/ar.<v>.ipa.json read before ar.ipa.json; the standard dictionary's hits in a text written
     in a variety said the variety's way (q > ʾ in Egyptian and Levantine, g in the Gulf; j > g in Egyptian; the
     interdentals > stops in Egyptian, Levantine and Moroccan), the dialect dictionary's own left as it writes them
     but for the glottal stop of a word written with ق; a standard text's romanisation byte-identical

    python3 -m unittest tests.test_arabic_variety_words
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))
import chunker        # noqa: E402
import draft          # noqa: E402
import languages      # noqa: E402
import lookup         # noqa: E402
import translit       # noqa: E402

VARIETIES = ("egy", "lev", "gulf", "mor")


def _dict(path, code, rows):
    c = lookup.create(path)
    for head, tr, pos, sense, forms in rows:
        cur = c.execute("INSERT INTO entry (headword, translit, pos, sense, sense_tags) VALUES (?,?,?,?,?)",
                        (head, tr, pos, sense, ""))
        for f in [head] + forms:
            c.execute("INSERT INTO form (form, entry_id, note) VALUES (?,?,?)", (f, cur.lastrowid, ""))
    c.executemany("INSERT INTO meta (key, value) VALUES (?,?)",
                  [("lang", code), ("source", "a fixture"), ("licence", "none")])
    c.commit()
    c.close()


def _forget():
    for conn, _stamp in (getattr(lookup._CONNS, "map", None) or {}).values():
        if conn is not None:
            conn.close()
    lookup._CONNS.map = {}


class NoDictionary(unittest.TestCase):
    """The lists alone, with no dictionary installed: what a person has before Settings -> Reading help."""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        was = lookup.DICT_DIR
        lookup.DICT_DIR = td.name
        _forget()
        self.addCleanup(lambda: (setattr(lookup, "DICT_DIR", was), _forget()))


class Phrases(NoDictionary):
    def test_every_variety_has_its_list_with_its_sources(self):
        for v in VARIETIES:
            R = chunker.rules("ar." + v)
            with self.subTest(v=v):
                self.assertTrue(chunker._read_rules("ar." + v).get("_sources"))
                self.assertIn("اللي", R["function_words"]["CONJ"])
                self.assertIn("NEG", R["function_words"])
                # Arabic's own settings still answer what the variety does not say
                self.assertEqual(R["np_head"], "initial")
                self.assertIn("هل", R["question_words"])

    def test_standard_arabic_has_no_function_words_of_a_dialect(self):
        self.assertNotIn("function_words", chunker.rules("ar"))
        self.assertEqual(chunker._lexicon("ar"), {})

    def test_a_dialect_sentence_is_cut_at_its_own_words(self):
        s = "أنا مش عارف الكتاب بتاعي فين عشان كنت حاطه على الترابيزة دي."
        self.assertEqual(chunker.chunk(s, "ar", "phrase"), [s])     # standard Arabic, no dictionary: no seam
        got = chunker.chunk(s, "ar.egy", "phrase")
        self.assertGreater(len(got), 1)
        self.assertTrue(chunker.exact(got, s))
        self.assertTrue(any(c.startswith("عشان") for c in got), got)  # the conjunction opens its clause
        self.assertTrue(any("مش عارف" in c for c in got), got)        # the negation stays with its word

    def test_a_levantine_relative_opens_its_clause(self):
        s = "هاد الشب اللي شفناه مبارح بيشتغل بمحل جنب البيت."
        got = chunker.chunk(s, "ar.lev", "phrase")
        self.assertTrue(any(c.startswith("اللي") for c in got), got)

    def test_a_new_book_in_a_variety_is_cut_with_its_lists(self):
        seen = []
        with mock.patch.object(chunker, "chunk_all", side_effect=lambda texts, lang, how, *a: seen.append(lang) or []):
            draft._cut_all(["x"], "ar", "phrase", "egy")
            draft._cut_all(["x"], "ar", "phrase", None)
            draft._cut_all(["x"], "ar", "phrase", "")
        self.assertEqual(seen, ["ar.egy", "ar", "ar"])

    def test_the_variety_does_not_change_how_a_word_it_does_not_list_is_read(self):
        # Arabic lists no function words, so the dictionary decides an unlisted word's class: a variety's list
        # must not switch Arabic into the mode where the list is the only authority on the closed classes
        with mock.patch.object(lookup, "pos_weights", return_value=[("prep", 3)]) as pw, \
                mock.patch.object(lookup, "pos_of", return_value=["prep"]):
            L = languages.get("ar.egy")
            got = chunker._candidates("على", False, L, chunker.rules(L.key), chunker._lexicon(L.key), True)
        self.assertEqual(got, ["ADP"])
        pw.assert_not_called()


class Romanisation(unittest.TestCase):
    STD = "qalb jamīl ṯalāṯa ḏahab ẓuhr"

    def test_each_variety_says_the_standard_letters_its_way(self):
        want = {"egy": "ʾalb gamīl talāta dahab ḍuhr",
                "lev": "ʾalb jamīl talāta dahab ḍuhr",
                "gulf": "galb jamīl ṯalāṯa ḏahab ẓuhr",
                "mor": "qalb jamīl talāta dahab ḍuhr"}
        for v, w in want.items():
            self.assertEqual(translit.in_variety("ar." + v, self.STD), w, v)

    def test_standard_arabic_and_other_languages_are_left_alone(self):
        for key in ("ar", "fa", "it", "ar.xyz", ""):
            self.assertEqual(translit.in_variety(key, self.STD), self.STD, key)

    def test_every_variety_file_cites_its_sources_and_keeps_arabics_rules(self):
        base = translit.ipa_rules("ar")["roman"]
        for v in VARIETIES:
            R = translit.ipa_rules("ar." + v)
            with self.subTest(v=v):
                self.assertTrue(translit._read_ipa("ar." + v).get("_sources"))
                self.assertEqual(R["roman"]["map"], base["map"])
                self.assertEqual(R["roman"]["drop_initial"], base["drop_initial"])

    def test_the_glottal_stop_of_a_qaf_is_kept_and_a_vowels_onset_dropped(self):
        self.assertEqual(translit.tidy_roman("ar.egy", "ʔalb", head="قلب"), "ʾalb")
        self.assertEqual(translit.tidy_roman("ar.egy", "ʔana", head="أنا"), "ana")
        self.assertEqual(translit.tidy_roman("ar.lev", "ʔalb", head="قلب"), "ʾalb")
        # standard Arabic, and a variety whose ق is not a glottal stop: as before
        self.assertEqual(translit.tidy_roman("ar", "ʔalb", head="قلب"), "alb")
        self.assertEqual(translit.tidy_roman("ar", "ʔalb"), "alb")
        self.assertEqual(translit.tidy_roman("ar.mor", "ʔalb", head="قلب"), "alb")


class RomanisationInTheLookup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        td = tempfile.TemporaryDirectory()
        cls.addClassCleanup(td.cleanup)
        _dict(os.path.join(td.name, "ar.db"), "ar",
              [("قلب", "qalb", "noun", "heart", []), ("جميل", "jamīl", "adj", "beautiful", []),
               ("ثلاثة", "ṯalāṯa", "num", "three", [])])
        _dict(os.path.join(td.name, "ar.egy.db"), "ar",
              [("قلب", "ʔalb", "noun", "heart", []), ("دلوقتي", "dilwaʔti", "adv", "now", [])])
        was = lookup.DICT_DIR
        lookup.DICT_DIR = td.name
        _forget()
        cls.addClassCleanup(lambda: (setattr(lookup, "DICT_DIR", was), _forget()))

    def said(self, text, variety=None):
        got = lookup.look_up("ar", text, variety=variety)
        return {w["word"]: [(h["translit"], h.get("head_sound"), h.get("standard_translit", ""), bool(h.get("variety")))
                            for h in w["hits"]] for w in got["words"]}

    def test_standard_arabic_is_as_it_was(self):
        got = self.said("قلب جميل ثلاثة")
        self.assertEqual(got["قلب"], [("qalb", "qalb", "", False)])
        self.assertEqual(got["جميل"], [("jamīl", "jamīl", "", False)])
        self.assertEqual(got["ثلاثة"], [("ṯalāṯa", "ṯalāṯa", "", False)])

    def test_in_egyptian_the_standard_hits_are_said_as_cairo_says_them(self):
        got = self.said("قلب جميل ثلاثة دلوقتي", "egy")
        self.assertEqual(got["قلب"], [("ʾalb", "ʾalb", "", True)])       # the Egyptian entry, its qaf kept
        self.assertEqual(got["جميل"], [("gamīl", "gamīl", "jamīl", False)])
        self.assertEqual(got["ثلاثة"], [("talāta", "talāta", "ṯalāṯa", False)])
        self.assertEqual(got["دلوقتي"][0][:2], ("dilwaʾti", "dilwaʾti"))

    def test_in_the_gulf_qaf_is_g_and_the_rest_standard(self):
        got = self.said("قلب جميل ثلاثة", "gulf")
        self.assertEqual(got["قلب"], [("galb", "galb", "qalb", False)])
        self.assertEqual(got["جميل"], [("jamīl", "jamīl", "", False)])
        self.assertEqual(got["ثلاثة"], [("ṯalāṯa", "ṯalāṯa", "", False)])


if __name__ == "__main__":
    unittest.main()
