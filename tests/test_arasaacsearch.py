# SPDX-License-Identifier: GPL-3.0-or-later
"""The search behind the pictogram picker (lib/arasaacsearch.py), a0.5.3.

    python3 -m unittest tests/test_arasaacsearch.py

A temporary arasaac/ is written by hand -- words in English, Spanish and Persian, flags, pictures -- and
getarasaac is pointed at it; nothing here reaches ARASAAC and nothing is written outside it.  What is held:

  * WHAT IS TYPED AND WHAT IS KEPT MEET: case, accents, the vowel marks, the Arabic yeh and kaf, the digits
    of every script and the zero-width non-joiner are all one thing to the search, and a mark that makes a
    letter of Hindi stays with it;
  * THE BEST COMES FIRST, in the order the module says: the keyword is what was typed, its plural is, a
    keyword starts with it, a word inside one does, the text is anywhere in one, only the meaning has it;
    two at the same step go by the shorter keyword and then the lower number; every word typed must be
    found, in any order;
  * A PICTURE THAT IS NOT HERE IS NOT LISTED, and a download that is not finished is searched as far as it
    got, and said to be;
  * THE FLAGGED ARE LEFT OUT, AND COUNTED: violence and sex unless asked for, and the answer says how many
    matching pictures were left out;
  * A PAGE is a page: the rest is `more`, and no words at all lists every picture by its word;
  * A REQUEST THAT IS NOT WELL MADE is refused, never trimmed into another: an unknown language, a limit
    that is not a small whole number;
  * WHAT CHANGES ON THE DISK IS SEEN by the next search, and an address's version moves with the picture.
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", ".", "tests"):
    sys.path.insert(0, str(ROOT / p))
import getarasaac as ga                                            # noqa: E402
import arasaacsearch as sr                                         # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 80 + b"IEND\xaeB`\x82"
SEX = 1 << ga.FLAGS.index("sex")
VIOLENCE = 1 << ga.FLAGS.index("violence")
SCHEMATIC = 1 << ga.FLAGS.index("schematic")


def entry(k, p="", m=""):
    return {key: v for key, v in (("k", k), ("p", p), ("m", m)) if v}


class Folder(unittest.TestCase):
    """A hand-written arasaac/ in a temporary tree, wired into getarasaac for one test."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.dir = Path(self._td.name) / "arasaac"
        (self.dir / "pictograms").mkdir(parents=True)
        self._patch = mock.patch.object(ga, "ARASAAC_DIR", str(self.dir))
        self._patch.start()
        ga._FACTS.clear()
        sr.forget()

    def tearDown(self):
        self._patch.stop()
        ga._FACTS.clear()
        sr.forget()
        self._td.cleanup()

    def words(self, locale, words):
        ga._write_json(ga.index_path(locale), {"format": 1, "words": {str(k): v for k, v in words.items()}})

    def facts(self, flags=None, ids=(), day="2023-01-04T10:00:00.000Z"):
        flags = flags or {}
        recs = {str(i): {"u": day, "f": flags.get(i, 0)} for i in ids}
        ga._write_json(ga.facts_path(), {"format": 1, "pictograms": recs})
        ga._FACTS.clear()

    def pictures(self, ids):
        for i in ids:
            (self.dir / "pictograms" / ("%d.png" % i)).write_bytes(PNG)

    def manifest(self, complete=True, resolution=300):
        ga._write_json(ga.manifest_path(), {"format": 1, "complete": complete, "resolution": resolution})

    def ids(self, answer):
        return [r["id"] for r in answer["results"]]


class Fold(unittest.TestCase):
    def test_case_accents_and_what_is_between_words_are_not_told_apart(self):
        for typed, kept in (("House", "house"), ("Árbol", "arbol"), ("árbol", "arbol"), ("  a  -  b  ", "a b"),
                            ("ice-cream", "ice cream"), ("Ça va", "ca va"), ("Straße", "strasse"),
                            ("STRASSE", "strasse"), ("ﬁsh", "fish"), ("İstanbul", "istanbul"), ("ısı", "isi"),
                            ("Ünïcode ñ", "unicode n"), ("fiancé(e)", "fiance e")):
            self.assertEqual(sr.fold(typed), kept, typed)

    def test_the_letters_a_persian_keyboard_and_an_arabic_one_write_differently_meet(self):
        self.assertEqual(sr.fold("كتاب"), sr.fold("کتاب"))                   # kaf
        self.assertEqual(sr.fold("بيت"), sr.fold("بیت"))                      # yeh
        self.assertEqual(sr.fold("مَدْرَسَة"), sr.fold("مدرسه"))               # the marks, and teh marbuta
        self.assertEqual(sr.fold("أحمد"), sr.fold("احمد"))                    # hamza on the alef
        self.assertEqual(sr.fold("٣ كتب"), "3 کتب")                           # Arabic-Indic digits
        self.assertEqual(sr.fold("۱۲"), "12")                                # Persian digits

    def test_a_zero_width_non_joiner_is_a_gap_and_a_joiner_nothing(self):
        self.assertEqual(sr.fold("می‌خواهم"), "می خواهم")
        self.assertEqual(sr.fold("a‍b"), "ab")
        self.assertEqual(sr.fold("‏سلام‎"), "سلام")

    def test_a_mark_that_makes_a_letter_stays_with_it(self):
        self.assertEqual(sr.fold("हाथ"), "हाथ")                                # Hindi: the vowel sign is part of the word
        self.assertEqual(sr.fold("שָׁלוֹם"), "שלום")                            # Hebrew points are not

    def test_nothing_folds_to_nothing(self):
        for x in (None, "", "   ", "---", 7, [], b"x"):
            self.assertEqual(sr.fold(x), "", repr(x))


class Rank(Folder):
    def setUp(self):
        super().setUp()
        self.words("en", {
            10: [entry("cream")],
            11: [entry("ice cream")],
            12: [entry("creamy")],
            13: [entry("scream")],
            14: [entry("dessert", m="cold, sweet cream")],
            15: [entry("lotion", p="cream")],
            16: [entry("creamier")],
        })
        ids = range(10, 17)
        self.facts(ids=ids)
        self.pictures(ids)
        self.manifest()

    def test_the_keyword_then_the_plural_then_a_start_then_a_word_then_anywhere_then_the_meaning(self):
        got = sr.search("cream")
        self.assertEqual(self.ids(got), [10, 15, 12, 16, 11, 13, 14])
        self.assertEqual(got["total"], 7)

    def test_two_at_one_step_go_by_the_shorter_keyword_and_then_the_number(self):
        a = sr.search("cream")
        self.assertLess(self.ids(a).index(12), self.ids(a).index(16))        # creamy before creamier
        self.words("en", {20: [entry("cat")], 19: [entry("cat")], 21: [entry("cats")]})
        self.facts(ids=(19, 20, 21))
        self.pictures((19, 20, 21))
        self.assertEqual(self.ids(sr.search("cat")), [19, 20, 21])

    def test_every_word_typed_must_be_found_in_any_order(self):
        self.assertEqual(self.ids(sr.search("ice cream")), [11])
        self.assertEqual(self.ids(sr.search("cream ice")), [11])
        self.assertEqual(self.ids(sr.search("ice dessert")), [])
        self.assertEqual(self.ids(sr.search("cold cream")), [14])            # both words are in a meaning, and nowhere else

    def test_case_accents_and_gaps_in_what_is_typed_do_not_matter(self):
        self.assertEqual(self.ids(sr.search("  ICE-Cream ")), [11])
        self.assertEqual(self.ids(sr.search("CREAM")), self.ids(sr.search("cream")))

    def test_the_text_that_was_typed_comes_back_trimmed_and_cut(self):
        self.assertEqual(sr.search("  cream  ")["q"], "cream")
        self.assertEqual(len(sr.search("x" * (sr.QUERY_MAX * 2))["q"]), sr.QUERY_MAX)

    def test_a_meaning_is_looked_in_by_its_words_and_not_by_the_letters_inside_them(self):
        self.words("en", {30: [entry("big", m="of great size")], 31: [entry("to eat", p="eats")], 32: [entry("cold", m="eaten when sweet")]})
        self.facts(ids=(30, 31, 32))
        self.pictures((30, 31, 32))
        got = self.ids(sr.search("eat"))
        self.assertIn(31, got)                    # a keyword
        self.assertIn(32, got)                    # "eaten" begins with it
        self.assertNotIn(30, got)                 # "great" only has it inside

    def test_a_query_that_finds_nothing_is_an_empty_answer_and_not_an_error(self):
        got = sr.search("zzzz")
        self.assertTrue(got["ok"] and got["ready"])
        self.assertEqual((got["total"], got["results"], got["more"], got["hidden"]), (0, [], False, 0))


class Languages(Folder):
    def setUp(self):
        super().setUp()
        self.words("en", {1: [entry("house", "houses", "a place to live"), entry("home")], 6: [entry("tree")]})
        self.words("es", {1: [entry("casa", "casas")], 6: [entry("árbol")], 7: [entry("niño")]})
        self.words("fa", {1: [entry("خانه")], 6: [entry("درخت")]})
        self.facts(ids=(1, 6, 7))
        self.pictures((1, 6, 7))
        self.manifest()

    def test_every_language_that_is_here_is_looked_in_and_one_picture_is_listed_once(self):
        for typed in ("house", "casa", "خانه", "CASA", "Casas"):
            self.assertEqual(self.ids(sr.search(typed)), [1], typed)
        self.assertEqual(self.ids(sr.search("arbol")), [6])

    def test_the_caption_is_in_the_display_language_and_falls_back_to_the_one_that_was_found(self):
        r = sr.search("casa")["results"][0]
        self.assertEqual((r["word"], r["lang"]), ("house", "en"))             # English is the default display
        r = sr.search("casa", display="es")["results"][0]
        self.assertEqual((r["word"], r["lang"]), ("casa", "es"))
        r = sr.search("niño")["results"][0]                                   # English has no word for 7
        self.assertEqual((r["word"], r["lang"]), ("niño", "es"))
        r = sr.search("house", display="fa")["results"][0]
        self.assertEqual((r["word"], r["lang"]), ("خانه", "fa"))

    def test_what_the_preview_shows_comes_with_each_picture(self):
        r = sr.search("house", display="es")["results"][0]
        self.assertEqual(r["words"], {"es": ["casa"], "en": ["house", "home"], "fa": ["خانه"]})
        self.assertEqual(list(r["words"])[0], "es")                           # the display language first
        self.assertEqual(r["meaning"], "a place to live")                    # the display language has none: another's
        self.assertEqual(r["flags"], [])
        self.assertTrue(r["v"].endswith("-300"))

    def test_searching_one_language_looks_only_there_and_says_so(self):
        got = sr.search("house", locales=["es"])
        self.assertEqual((got["searched"], got["total"]), (["es"], 0))
        got = sr.search("casa", locales=["es"], display="es")
        self.assertEqual((got["searched"], self.ids(got)), (["es"], [1]))
        self.assertEqual(sr.search("house", locales=["fr"])["searched"], ["en", "es", "fa"])   # not here: all of them

    def test_the_languages_here_come_with_their_names_and_direction(self):
        rows = {r["code"]: r for r in sr.search("house")["locales"]}
        self.assertEqual(list(rows), ["en", "es", "fa"])
        self.assertEqual(rows["en"]["name"], "English")
        self.assertTrue(rows["fa"]["rtl"] and not rows["es"]["rtl"])

    def test_the_display_language_is_english_else_the_first_here(self):
        self.assertEqual(sr.search("house")["display"], "en")
        self.assertEqual(sr.search("house", display="es")["display"], "es")
        self.assertEqual(sr.search("house", display="de")["display"], "en")   # ARASAAC's, but not here
        os.unlink(ga.index_path("en"))
        self.assertEqual(sr.search("casa")["display"], "es")


class WhatIsHere(Folder):
    def test_nothing_installed_is_not_ready_and_says_so(self):
        got = sr.search("house")
        self.assertTrue(got["ok"])
        self.assertEqual((got["ready"], got["state"], got["results"], got["locales"]), (False, "absent", [], []))
        self.assertEqual(got["credit"], ga.CREDIT_SHORT)

    def test_words_without_pictures_and_pictures_without_words_are_not_ready(self):
        self.words("en", {1: [entry("house")]})
        self.assertFalse(sr.search("house")["ready"])
        self.pictures((1,))
        os.unlink(ga.index_path("en"))
        self.assertFalse(sr.search("house")["ready"])

    def test_a_download_that_is_not_finished_is_searched_as_far_as_it_got(self):
        self.words("en", {1: [entry("house")], 2: [entry("horse")], 3: [entry("hose")]})
        self.facts(ids=(1, 2, 3))
        self.pictures((1, 3))
        self.manifest(complete=False)
        got = sr.search("ho")
        self.assertEqual(sorted(self.ids(got)), [1, 3])                       # 2 has no picture yet
        self.assertEqual((got["state"], got["pictures"], got["listed"]), ("partial", 2, 3))
        self.pictures((2,))
        self.assertEqual(sorted(self.ids(sr.search("ho"))), [1, 2, 3])        # the folder changed: seen at once

    def test_a_whole_install_says_installed(self):
        self.words("en", {1: [entry("house")]})
        self.facts(ids=(1,))
        self.pictures((1,))
        self.manifest()
        got = sr.search("house")
        self.assertEqual((got["ready"], got["state"], got["fetching"]), (True, "installed", False))

    def test_a_record_still_to_be_confirmed_keeps_it_partial(self):
        self.words("en", {1: [entry("house")]})
        ga._write_json(ga.facts_path(), {"format": 1, "pictograms": {"1": {"u": "x", "f": 0, "p": 1}}})
        ga._FACTS.clear()
        self.pictures((1,))
        self.manifest()
        self.assertEqual(sr.search("house")["state"], "partial")


class Flagged(Folder):
    def setUp(self):
        super().setUp()
        self.words("en", {1: [entry("kiss", m="to touch with the lips")], 2: [entry("kind")], 3: [entry("war")],
                          4: [entry("kitchen")], 5: [entry("kite")]})
        self.facts(flags={1: SEX, 3: VIOLENCE, 4: SCHEMATIC}, ids=(1, 2, 3, 4, 5))
        self.pictures((1, 2, 3, 4))                                           # 5 has no picture
        self.manifest()

    def test_violence_and_sex_are_left_out_and_counted(self):
        got = sr.search("ki")
        self.assertEqual(sorted(self.ids(got)), [2, 4])
        self.assertEqual((got["total"], got["hidden"]), (2, 1))               # kiss; kite has no picture: not counted
        got = sr.search("war")
        self.assertEqual((got["results"], got["hidden"]), ([], 1))

    def test_asked_for_they_are_listed_and_nothing_is_hidden(self):
        got = sr.search("ki", sensitive=True)
        self.assertEqual(sorted(self.ids(got)), [1, 2, 4])
        self.assertEqual(got["hidden"], 0)

    def test_a_word_found_only_in_a_meaning_is_left_out_all_the_same(self):
        self.assertEqual((sr.search("lips")["results"], sr.search("lips")["hidden"]), ([], 1))
        self.assertEqual(self.ids(sr.search("lips", sensitive=True)), [1])

    def test_the_flags_come_with_the_picture_in_ARASAACs_words(self):
        r = {x["id"]: x for x in sr.search("ki", sensitive=True)["results"]}
        self.assertEqual((r[1]["flags"], r[4]["flags"], r[2]["flags"]), (["sex"], ["schematic"], []))

    def test_a_flag_that_is_not_the_boolean_true_does_not_unlock_them(self):
        for v in (1, "yes", [1], None):
            self.assertEqual(sr.search("war", sensitive=v)["hidden"], 1, repr(v))


class Pages(Folder):
    def setUp(self):
        super().setUp()
        n = 130
        self.words("en", {i: [entry("word%03d" % i)] for i in range(1, n + 1)})
        self.facts(ids=range(1, n + 1))
        self.pictures(range(1, n + 1))
        self.manifest()

    def test_a_page_is_forty_eight_and_the_rest_is_more(self):
        got = sr.search("word")
        self.assertEqual((len(got["results"]), got["total"], got["more"], got["offset"]), (sr.PAGE_SIZE, 130, True, 0))
        self.assertEqual(self.ids(got), list(range(1, 49)))

    def test_the_pages_follow_one_another_and_end(self):
        seen = []
        offset = 0
        while True:
            got = sr.search("word", offset=offset, limit=50)
            seen += self.ids(got)
            if not got["more"]:
                break
            offset += 50
        self.assertEqual(seen, list(range(1, 131)))
        self.assertEqual(sr.search("word", offset=130)["results"], [])

    def test_no_words_at_all_lists_every_picture_by_its_word(self):
        self.words("en", {1: [entry("zebra")], 2: [entry("apple")], 3: [entry("Mango")], 4: [entry("árbol")]})
        got = sr.search("")
        self.assertEqual(self.ids(got), [2, 4, 3, 1])                         # apple, arbol, mango, zebra
        self.assertEqual(self.ids(sr.search(None)), self.ids(got))
        self.assertEqual(self.ids(sr.search("   ")), self.ids(got))

    def test_browsing_is_by_the_display_languages_words(self):
        self.words("en", {1: [entry("zebra")], 2: [entry("apple")]})
        self.words("es", {1: [entry("cebra")], 2: [entry("manzana")], 3: [entry("abeja")]})
        self.facts(ids=(1, 2, 3))
        self.pictures((1, 2, 3))
        self.assertEqual(self.ids(sr.search("", display="es")), [3, 1, 2])
        self.assertEqual(self.ids(sr.search("", display="en")), [2, 1])


class Refused(Folder):
    def setUp(self):
        super().setUp()
        self.words("en", {1: [entry("house")]})
        self.facts(ids=(1,))
        self.pictures((1,))
        self.manifest()

    def refused(self, **kw):
        with self.assertRaises(ga.ArasaacError) as cm:
            sr.search("house", **kw)
        return cm.exception.code

    def test_a_language_to_look_in_that_is_not_ARASAACs_is_refused(self):
        self.assertEqual(self.refused(locales=["en", "klingon"]), "bad-language")
        self.assertEqual(self.refused(locales=["../en"]), "bad-language")
        self.assertEqual(self.refused(locales="en"), "bad-language")

    def test_the_language_the_words_are_shown_in_is_a_hint_and_a_name(self):
        for hint in ("ja", "xx", "../en", ""):                     # not here, not ARASAAC's: English, and no error
            self.assertEqual(sr.search("house", display=hint)["display"], "en", repr(hint))
        for hint in (7, ["en"], {"en": 1}):
            self.assertEqual(self.refused(display=hint), "bad-request", repr(hint))

    def test_a_number_that_is_not_a_small_whole_one_is_refused(self):
        for kw in ({"limit": 0}, {"limit": sr.PAGE_MAX + 1}, {"limit": "7"}, {"limit": 1.5}, {"limit": True},
                   {"offset": -1}, {"offset": "0"}, {"offset": 10 ** 7}):
            self.assertEqual(self.refused(**kw), "bad-request", repr(kw))

    def test_what_is_typed_must_be_text_and_not_a_book(self):
        for q in (7, ["house"], {"q": "house"}):
            with self.assertRaises(ga.ArasaacError):
                sr.search(q)
        with self.assertRaises(ga.ArasaacError):
            sr.search("x" * (sr.QUERY_MAX * 4 + 1))


class Changes(Folder):
    def test_a_word_list_that_was_rewritten_is_read_again(self):
        self.words("en", {1: [entry("house")]})
        self.facts(ids=(1, 2))
        self.pictures((1, 2))
        self.manifest()
        self.assertEqual(self.ids(sr.search("house")), [1])
        self.assertEqual(self.ids(sr.search("horse")), [])
        self.words("en", {1: [entry("house")], 2: [entry("horse")]})
        self.assertEqual(self.ids(sr.search("horse")), [2])
        os.unlink(ga.index_path("en"))
        got = sr.search("house")
        self.assertEqual((got["ready"], got["results"]), (False, []))

    def test_the_address_of_a_picture_carries_the_day_it_changed_and_the_size_it_is_at(self):
        self.words("en", {1: [entry("house")]})
        self.facts(ids=(1,), day="2023-01-04T10:00:00.000Z")
        self.pictures((1,))
        self.manifest(resolution=300)
        a = sr.search("house")["results"][0]["v"]
        self.assertEqual(a, "20230104100000000-300")
        self.facts(ids=(1,), day="2024-02-05T11:00:00.000Z")
        b = sr.search("house")["results"][0]["v"]
        self.manifest(resolution=500)
        c = sr.search("house")["results"][0]["v"]
        self.assertEqual(len({a, b, c}), 3)
        self.assertTrue(c.endswith("-500"))

    def test_a_picture_with_no_record_still_has_an_address_version(self):
        self.assertEqual(sr.version(5, {}), "0-0")


class Damaged(Folder):
    """A word list is a file on a disk that anybody may have edited or a half download may have left: what is not an
    entry is passed over, and the entries that are still find their pictures."""

    def test_entries_that_are_not_entries_are_passed_over(self):
        self.words("en", {1: ["junk", None, {"k": 5}, {"k": ""}, {"p": "only a plural"}, entry("house")],
                          2: [], 3: entry("not a list"), 4: [entry("home", m=7), {"k": "hut", "m": ["x"]}]})
        self.facts(ids=(1, 2, 3, 4))
        self.pictures((1, 2, 3, 4))
        self.manifest()
        got = sr.search("house")
        self.assertEqual(self.ids(got), [1])
        self.assertEqual(got["results"][0]["words"], {"en": ["house"]})
        self.assertEqual(self.ids(sr.search("hut")), [4])
        self.assertEqual(self.ids(sr.search("")), [4, 1])                     # home, house; 2 and 3 have no word to be listed by

    def test_a_word_list_that_is_not_a_list_of_words_is_no_language_here(self):
        ga._write_json(ga.index_path("en"), {"format": 1, "words": ["not", "an", "object"]})
        self.facts(ids=(1,))
        self.pictures((1,))
        self.manifest()
        got = sr.search("house")
        self.assertFalse(got["ready"])
        self.assertEqual(got["locales"], [])
        with open(ga.index_path("en"), "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertFalse(sr.search("house")["ready"])

    def test_records_of_another_shape_do_not_break_the_flags(self):
        self.words("en", {1: [entry("kiss")]})
        ga._write_json(ga.facts_path(), {"format": 1, "pictograms": {"1": "not a record", "2": {"f": "many"}}})
        ga._FACTS.clear()
        self.pictures((1,))
        self.manifest()
        got = sr.search("kiss")
        self.assertEqual(self.ids(got), [1])
        self.assertEqual(got["results"][0]["flags"], [])


class Pictures(Folder):
    def test_a_picture_is_found_by_its_number_alone(self):
        self.pictures((12, 3456))
        self.assertEqual(sr.picture(12), ga.picture_path(12))
        self.assertEqual(sr.picture("3456"), ga.picture_path(3456))
        self.assertTrue(os.path.isfile(sr.picture("12")))

    def test_what_is_not_a_number_or_not_here_is_none(self):
        self.pictures((12,))
        for x in (13, "13", "", "../12", "12.png", "1 2", "٣", "0", 0, -1, "12345678", 10 ** 8, None, 1.5, [12]):
            self.assertIsNone(sr.picture(x), repr(x))


if __name__ == "__main__":
    unittest.main()
