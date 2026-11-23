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
  3  case endings (a0.6.3, R2): a standard hit in a dialect text loses its final case vowel and tanwīn (kataba > katab,
     kitāban > kitāb, madrasatun > madrasa), long vowels, the -a of ة and a stem's own -un kept; standard Arabic as was
  4  question words (a0.6.3, R2): youtube/lib/tidy.py asks with a variety's own (lib/lang/ar.<v>.chunk.json)

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
            f, roman, note = (f, "", "") if isinstance(f, str) else f        # a form of the table: its sound, its note
            c.execute("INSERT INTO form (form, entry_id, note, roman) VALUES (?,?,?,?)", (f, cur.lastrowid, note, roman))
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


class PhrasesWithTheDialectsDictionary(unittest.TestCase):
    """12.37: a text in a variety reads a word's class from the variety's own dictionary first (dict/ar.mor.db), the
    standard one after it as before, and a word only the variety's verb prefix explains (كي + يخدم) as a verb."""

    @classmethod
    def setUpClass(cls):
        td = tempfile.TemporaryDirectory()
        cls.addClassCleanup(td.cleanup)
        _dict(os.path.join(td.name, "ar.db"), "ar",
              [("كتب", "kataba", "verb", "to write", ["يكتب"]), ("بيت", "bayt", "noun", "house", ["البيت"]),
               # يخدم filed as a noun first, so that only the ka- prefix can say it is the verb here
               ("يخدم", "yaxdum", "noun", "a made-up noun", []), ("خدم", "xadama", "verb", "to serve", ["يخدم"]),
               ("ساكن", "sākin", "adj", "living", []), ("الدار", "ad-dār", "noun", "the house", [])])
        _dict(os.path.join(td.name, "ar.mor.db"), "ar",
              [("مشا", "mša", "verb", "to go", ["مشيت"]), ("دابا", "dāba", "adv", "now", []),
               ("حطيت", "ḥṭṭit", "verb", "I put", []), ("الساروت", "s-sārūt", "noun", "the key", [])])
        was = lookup.DICT_DIR
        lookup.DICT_DIR = td.name
        _forget()
        cls.addClassCleanup(lambda: (setattr(lookup, "DICT_DIR", was), _forget()))
        cls.dir = td.name

    def test_a_word_only_the_dialects_dictionary_has_takes_its_class(self):
        self.assertEqual(chunker._class("مشيت", "ar.mor"), "VERB")
        self.assertEqual(chunker._class("دابا", "ar.mor"), "ADV")
        # standard Arabic does not read the dialect's dictionary
        self.assertEqual(chunker._class("مشيت", "ar"), "OTHER")
        self.assertEqual(chunker.word_class("دابا", "ar"), "OTHER")

    def test_the_standard_dictionary_still_answers_what_the_dialects_has_not(self):
        self.assertEqual(chunker._class("يكتب", "ar.mor"), "VERB")
        self.assertEqual(chunker._class("البيت", "ar.mor"), "NOUN")

    def test_a_word_its_verb_prefix_explains_is_a_verb(self):
        L = languages.get("ar.mor")
        got = chunker._candidates("كيخدم", False, L, chunker.rules(L.key), chunker._lexicon(L.key), True)
        self.assertEqual(got, ["VERB"])
        # a prefix the rules do not mark as a verb's (فال-) says nothing of the kind
        self.assertFalse(chunker._marked_verb(L, "فالدار"))
        # and a word a dictionary has as written keeps its own classes
        self.assertFalse(chunker._marked_verb(L, "يكتب"))

    def test_the_cut_follows_the_dialects_classes(self):
        # حطيت is the Moroccan dictionary's verb: the question word opens its clause, where with no class for
        # حطيت the cut fell between the question word and its verb (الراجل ساكن فين | حطيت ...)
        s = "الراجل ساكن فين حطيت الساروت ديالي."
        self.assertEqual(chunker.chunk(s, "ar.mor", "phrase"), ["الراجل ساكن", "فين حطيت الساروت ديالي."])

    def test_standard_arabic_is_cut_as_it_was_without_the_dialects_dictionary(self):
        s = "ما عرفتش فين حطيت الساروت ديالي في البيت."
        with_it = chunker.chunk(s, "ar", "phrase")
        mor = os.path.join(self.dir, "ar.mor.db")
        os.rename(mor, mor + ".away")
        try:
            _forget()
            self.assertEqual(chunker.chunk(s, "ar", "phrase"), with_it)
            # and without its own dictionary a Moroccan text reads the standard one, as before 12.37
            self.assertEqual(chunker._class("حطيت", "ar.mor"), "OTHER")
            self.assertEqual(chunker._class("يكتب", "ar.mor"), "VERB")
        finally:
            os.rename(mor + ".away", mor)
            _forget()
        self.assertEqual(chunker._class("حطيت", "ar.mor"), "VERB")


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
               ("ثلاثة", "ṯalāṯa", "num", "three", []), ("كتب", "kataba", "verb", "to write", []),
               ("كتاب", "kitāb", "noun", "book", [("كتابا", "kitāban", "accusative indefinite singular")]),
               ("مدرسة", "madrasa", "noun", "school", [("والمدرسة", "wa-l-madrasati", "definite genitive singular")]),
               ("مدينة", "madīna", "noun", "city", [("مدن", "mudun", "plural")]),
               ("تعاون", "taʿāwun", "noun", "cooperation", [("التعاون", "at-taʿāwun", "definite informal singular")])])
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


class CaseEndings(unittest.TestCase):
    """translit.pausal through in_variety: the rule in ar.ipa.json, turned on by each variety's file.  Moroccan, whose
    ق stays q, unless a test names another."""

    def said(self, s, pos, written, lemma=None, key="ar.mor"):
        return translit.in_variety(key, s, pos, written, lemma)

    def test_every_variety_turns_the_one_rule_on(self):
        self.assertTrue(translit._read_ipa("ar").get("pausal"))
        for v in VARIETIES:
            with self.subTest(v=v):
                self.assertIs(translit._read_ipa("ar." + v)["from_standard"].get("pausal"), True)
                self.assertNotIn("pausal", translit._read_ipa("ar." + v), "the rule is Arabic's, not a copy")

    def test_a_verb_loses_its_final_short_vowel(self):
        self.assertEqual(self.said("kataba", "verb", "كتب"), "katab")
        self.assertEqual(self.said("yaktubu", "verb", "يكتب", "kataba"), "yaktub")
        self.assertEqual(self.said("katabtu", "verb", "كتبت", "kataba"), "katabt")
        self.assertEqual(self.said("qawiya", "verb", "قوي"), "qawī")

    def test_a_verb_keeps_its_long_vowels_and_its_feminine_plural(self):
        self.assertEqual(self.said("katabū", "verb", "كتبوا", "kataba"), "katabū")
        self.assertEqual(self.said("katabna", "verb", "كتبن", "kataba"), "katabna")
        self.assertEqual(self.said("qālat", "verb", "قالت", "qāla"), "qālat")

    def test_a_noun_loses_its_case_vowel_and_tanwin(self):
        for form in ("kitābun", "kitāban", "kitābin"):
            self.assertEqual(self.said(form, "noun", "كتاب", "kitāb"), "kitāb", form)
        self.assertEqual(self.said("al-kitābi", "noun", "الكتاب", "kitāb"), "al-kitāb")
        self.assertEqual(self.said("kitābāni", "noun", "كتابان", "kitāb"), "kitābān")
        self.assertEqual(self.said("kātibātun", "noun", "كاتبات", "kātib"), "kātibāt")
        self.assertEqual(self.said("kātibūna", "noun", "كاتبون", "kātib"), "kātibūn")

    def test_the_feminine_a_stays(self):
        self.assertEqual(self.said("madrasa", "noun", "مدرسة"), "madrasa")
        self.assertEqual(self.said("madrasatun", "noun", "مدرسةٌ", "madrasa"), "madrasa")
        self.assertEqual(self.said("wa-l-madrasati", "noun", "والمدرسة", "madrasa"), "wa-l-madrasa")
        self.assertEqual(self.said("kabīratan", "adj", "كبيرةً", "kabīr"), "kabīra")

    def test_an_n_of_the_word_itself_stays(self):
        self.assertEqual(self.said("mudun", "noun", "مدن", "madīna"), "mudun")
        self.assertEqual(self.said("at-taʿāwun", "noun", "التعاون", "taʿāwun"), "at-taʿāwun")
        self.assertEqual(self.said("al-waṭan", "noun", "الوطن", "waṭan"), "al-waṭan")
        self.assertEqual(self.said("waṭanan", "noun", "وطنا", "waṭan"), "waṭan")
        self.assertEqual(self.said("taʿāwun", "noun", "تعاون"), "taʿāwun", "an entry's own romanisation is never cut")

    def test_other_words_and_phrases(self):
        self.assertEqual(self.said("huwa", "pron", "هو"), "huwa", "a pronoun is left as written")
        self.assertEqual(self.said("ṭalīqu l-lisāni", "adj", "طليق اللسان", "ṭalīq"), "ṭalīqu l-lisān",
                         "a phrase pauses once, at its end")

    def test_with_each_dialects_consonants(self):
        self.assertEqual(self.said("ḏahaba", "verb", "ذهب", key="ar.egy"), "dahab")
        self.assertEqual(self.said("qawiya", "verb", "قوي", key="ar.egy"), "ʾawī")
        self.assertEqual(self.said("qatala", "verb", "قتل", key="ar.gulf"), "gatal")
        self.assertEqual(self.said("jamīlatun", "adj", "جميلة", "jamīl", key="ar.egy"), "gamīla")

    def test_standard_arabic_keeps_its_endings(self):
        for key in ("ar", "fa", ""):
            self.assertEqual(translit.in_variety(key, "kataba", "verb", "كتب"), "kataba", key)
            self.assertEqual(translit.in_variety(key, "kitāban", "noun", "كتابا", "kitāb"), "kitāban", key)


class CaseEndingsInTheLookup(RomanisationInTheLookup):
    """The same through lib/lookup.py: the standard dictionary's own rows, said in Egyptian."""

    def test_standard_arabic_is_as_it_was(self):
        got = self.said("كتب كتابا والمدرسة مدن التعاون")
        self.assertEqual(got["كتب"], [("kataba", "kataba", "", False)])
        self.assertEqual(got["كتابا"], [("kitāban", "kitāb", "", False)])
        self.assertEqual(got["والمدرسة"], [("wa-l-madrasati", "madrasa", "", False)])

    def test_in_egyptian_the_case_endings_go(self):
        got = self.said("كتب كتابا والمدرسة مدن التعاون", "egy")
        self.assertEqual(got["كتب"], [("katab", "katab", "kataba", False)])
        self.assertEqual(got["كتابا"], [("kitāb", "kitāb", "kitāban", False)])
        self.assertEqual(got["والمدرسة"], [("wa-l-madrasa", "madrasa", "wa-l-madrasati", False)])
        self.assertEqual(got["مدن"], [("mudun", "madīna", "", False)])
        self.assertEqual(got["التعاون"], [("at-taʿāwun", "taʿāwun", "", False)])

    def test_the_dialect_dictionarys_own_entry_is_untouched(self):
        got = self.said("دلوقتي", "egy")
        self.assertEqual(got["دلوقتي"][0][1:], ("dilwaʾti", "", True))


class QuestionWords(unittest.TestCase):
    """youtube/lib/tidy.py: a bare transcript in a dialect gets its question mark from the dialect's own words."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "youtube", "lib"))
        import tidy
        cls.tidy = tidy
        td = tempfile.TemporaryDirectory()
        cls.addClassCleanup(td.cleanup)
        _dict(os.path.join(td.name, "ar.db"), "ar", [("كتاب", "kitāb", "noun", "book", [])])
        was = lookup.DICT_DIR
        lookup.DICT_DIR = td.name
        _forget()
        cls.addClassCleanup(lambda: (setattr(lookup, "DICT_DIR", was), _forget()))

    def asked(self, lang, *lines):
        # captions far apart, so that each is a sentence of its own (the silence after it)
        caps = [{"start": 10.0 * k, "text": t} for k, t in enumerate(lines)]
        out, _notes = self.tidy.tidy(caps, lang, dur=10.0 * len(lines))
        return [c["text"] for c in out]

    def test_an_egyptian_question_ends_with_a_question_mark(self):
        got = self.asked("ar.egy", "انت رايح فين", "انا رايح البيت")
        self.assertEqual(got, ["انت رايح فين\u061f", "انا رايح البيت."])

    def test_each_dialect_asks_with_its_own(self):
        for v, line in (("lev", "شو بدك انت"), ("gulf", "وين رايح انت"), ("mor", "فين ساكن انت")):
            with self.subTest(v=v):
                self.assertEqual(self.asked("ar." + v, line, "الكتاب هنا يا ولد")[0], line + "\u061f")

    def test_standard_arabic_reads_only_its_own(self):
        self.assertEqual(self.asked("ar", "انت رايح فين", "انا رايح البيت"),
                         ["انت رايح فين.", "انا رايح البيت."])
        self.assertEqual(self.asked("ar.egy", "أين الكتاب يا ولد", "الكتاب هنا يا ولد")[0], "أين الكتاب يا ولد\u061f",
                         "and a dialect keeps Arabic's question words")


if __name__ == "__main__":
    unittest.main()
