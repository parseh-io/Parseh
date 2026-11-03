# SPDX-License-Identifier: GPL-3.0-or-later
"""THE LEVELS' NAMES: what each pass of a reading edition is called on a page.

    python3 -m unittest tests/test_level_names.py

A reading edition sets a passage in several passes; to the person reading, each
is a LEVEL, and its button wears a NAME -- "With vowels", "Chunks", "Plain" --
never a digit (a0.5.0, the owner's, 2026-10-06).  The registry holds the
default name of every pass and a one-line title that says what it shows
(lib/languages.json); a person renames a level on their own pages (the prefs
key bk_lvl:<language>:<pass key>, tests/test_prefs_levels.py).  What is held
here:

- every shipped language's passes carry the names and titles the owner settled,
  exactly; the digit labels, the keys and the marks to strip are what they were;
- a pass without a name, a name over 12 characters, a name that is not one
  line, two passes of one language with the same name: all refused, with a
  message that says which language and which pass;
- the limit is one number in the registry and in the preferences, so a rename
  the page accepts is a rename the toolbox keeps.

Nothing here writes anything: it reads lib/languages.json and builds Lang
objects in memory.
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
LIB = os.path.join(ROOT, "lib")
sys.path.insert(0, LIB)
import languages                                               # noqa: E402
import prefs                                                   # noqa: E402

CHUNKS = "the sentence cut into chunks, each with its gloss beside it"
VERTICAL = "the sentence in vertical columns (tategaki)"

# language -> [(key, name, label, title)], in the order the language has its passes
SHIPPED = {
    "fa": [("vocal", "With vowels", "1", "the sentence with its vowels, to read on its own"),
           ("chunks", "Chunks", "2", CHUNKS),
           ("bare", "Plain", "3", "the sentence as Persian is ordinarily printed, with no marks"),
           ("alt", "Nastaliq", "4", "the same sentence in nastaliq script")],
    "ar": [("vocal", "With vowels", "1", "the sentence with its vowels, to read on its own"),
           ("chunks", "Chunks", "2", CHUNKS),
           ("bare", "Plain", "3", "the sentence as Arabic is ordinarily printed, with no marks")],
    "ja": [("vocal", "Furigana", "1", "with furigana over each word"),
           ("aloud", "Kana only", "2", "the reading alone, in kana"),
           ("chunks", "Chunks", "3", CHUNKS),
           ("bare", "Plain", "4", "plain, as Japanese is written"),
           ("alt", "Vertical", "5", VERTICAL)],
    "zh": [("vocal", "Pinyin", "1", "with pinyin over each word"),
           ("aloud", "Pinyin only", "2", "the reading alone, in pinyin"),
           ("chunks", "Chunks", "3", CHUNKS),
           ("bare", "Plain", "4", "plain, as Chinese is written"),
           ("alt", "Vertical", "5", VERTICAL)],
}
for _code in ("it", "fr", "de", "tr", "en", "hi", "es", "ca"):
    SHIPPED[_code] = [("vocal", "Sentence", "1", "the sentence, to read on its own"),
                      ("chunks", "Chunks", "2", CHUNKS)]

# what the old wording was, which no page may read any more
OLD = ("the vowelled attempt", "bare naskh", "unvowelled, as Arabic is written",
       "chunks and glosses")


def shipped_langs():
    return [languages.get(c) for c in languages.CODES if not languages.get(c).mine]


class ShippedNames(unittest.TestCase):
    def test_the_table_covers_every_shipped_language(self):
        self.assertEqual(sorted(SHIPPED), sorted(c for c in languages.CODES
                                                 if not languages.get(c).mine))

    def test_every_pass_of_every_language_has_a_valid_name(self):
        for L in shipped_langs():
            with self.subTest(code=L.code):
                self.assertTrue(L.passes)
                self.assertEqual(languages.level_name_problems(L.passes), [])
                for p in L.passes:
                    self.assertIsInstance(p["name"], str)
                    self.assertEqual(p["name"], p["name"].strip())
                    self.assertTrue(1 <= len(p["name"]) <= 12, p["name"])
                names = [p["name"].casefold() for p in L.passes]
                self.assertEqual(len(names), len(set(names)), "a button shows nothing but its name")

    def test_the_names_the_owner_settled(self):
        for code, want in SHIPPED.items():
            with self.subTest(code=code):
                got = [(p["key"], p["name"]) for p in languages.get(code).passes]
                self.assertEqual(got, [(k, n) for k, n, _l, _t in want])

    def test_the_titles_the_owner_settled(self):
        for code, want in SHIPPED.items():
            with self.subTest(code=code):
                got = [(p["key"], p["title"]) for p in languages.get(code).passes]
                self.assertEqual(got, [(k, t) for k, _n, _l, t in want])

    def test_the_digits_stay_for_the_pdf(self):
        """A page stops printing the label; the PDF and the checkers still
        count by it, and it counts the passes this language has."""
        for code, want in SHIPPED.items():
            with self.subTest(code=code):
                self.assertEqual([(p["key"], p["label"]) for p in languages.get(code).passes],
                                 [(k, l) for k, _n, l, _t in want])

    def test_the_rest_of_the_pass_is_what_it_was(self):
        kinds = {("fa", "alt"): "font", ("ja", "alt"): "vertical", ("zh", "alt"): "vertical"}
        for L in shipped_langs():
            for p in L.passes:
                with self.subTest(code=L.code, key=p["key"]):
                    self.assertEqual(set(p) - {"kind"}, {"key", "name", "label", "title"})
                    self.assertEqual(p.get("kind"), kinds.get((L.code, p["key"])))
        # `strip`, `vocal_label` and `bare_label` are not touched by the names
        self.assertEqual(languages.get("fa").strip_range, "\\u064B-\\u0652")
        self.assertEqual(languages.get("ar").strip_range, "\\u064B-\\u0652\\u0670")
        self.assertEqual((languages.get("fa").vocal_label, languages.get("fa").bare_label),
                         ("vowelled", "bare"))
        self.assertEqual((languages.get("ar").vocal_label, languages.get("ar").bare_label),
                         ("vowelled", "unvowelled"))
        self.assertEqual((languages.get("ja").vocal_label, languages.get("ja").bare_label),
                         ("with furigana", "plain"))

    def test_the_old_wording_is_gone_from_the_registry(self):
        with open(os.path.join(LIB, "languages.json"), encoding="utf-8") as f:
            text = f.read()
        for old in OLD:
            self.assertNotIn(old, text)

    def test_the_page_receives_the_names(self):
        """The record a page embeds for its script (Lang.as_json) is the one
        the reader, the player and the gear read: the names are in it."""
        for L in shipped_langs():
            with self.subTest(code=L.code):
                passes = json.loads(json.dumps(L.as_json()))["passes"]
                self.assertEqual([p["name"] for p in passes], [p["name"] for p in L.passes])
                self.assertEqual([p["key"] for p in passes], L.pass_keys)

    def test_a_name_that_fits_a_button_fits_the_preferences(self):
        """One limit: a name the registry may hold is a name a person may
        keep, and the toolbox keeps nothing longer."""
        self.assertEqual(languages.LEVEL_NAME_MAX, 12)
        self.assertEqual(prefs.MAX_LEVEL_NAME, languages.LEVEL_NAME_MAX)


def row(passes, **more):
    """A language row with just enough to build a Lang."""
    d = {"name": "Testish", "native": "Testish", "folder": "testish", "script": "latin",
         "passes": passes}
    d.update(more)
    return d


class Refusals(unittest.TestCase):
    """languages.Lang refuses a pass that has no usable name, and says which
    language and which pass."""

    def refused(self, passes, *fragments):
        with self.assertRaises(ValueError) as cm:
            languages.Lang("xx", row(passes))
        text = str(cm.exception)
        self.assertIn("Testish (xx)", text)
        for f in fragments:
            self.assertIn(f, text)
        return text

    def test_no_name_at_all(self):
        self.refused([{"key": "vocal", "label": "1", "title": "t"}], "pass 'vocal' has no \"name\"")

    def test_an_empty_or_blank_name(self):
        for name in ("", "   ", None, 7):
            with self.subTest(name=name):
                self.refused([{"key": "chunks", "name": name, "label": "1", "title": "t"}],
                             "pass 'chunks' has no \"name\"")

    def test_a_name_over_twelve_characters(self):
        self.refused([{"key": "vocal", "name": "Thirteen char", "label": "1", "title": "t"}],
                     "pass 'vocal' is named 'Thirteen char', which is 13 characters")

    def test_twelve_characters_is_the_most(self):
        L = languages.Lang("xx", row([{"key": "vocal", "name": "Twelve chars", "label": "1",
                                       "title": "t"}]))
        self.assertEqual(L.passes[0]["name"], "Twelve chars")
        self.assertEqual(len(L.passes[0]["name"]), 12)

    def test_the_name_is_trimmed_before_it_is_counted(self):
        L = languages.Lang("xx", row([{"key": "vocal", "name": "  Twelve chars  ", "label": "1",
                                       "title": "t"}]))
        self.assertEqual(L.passes[0]["name"], "Twelve chars")

    def test_a_name_that_is_not_one_line(self):
        for name in ("two\nlines", "tab\there", "x y"):
            with self.subTest(name=name):
                self.refused([{"key": "vocal", "name": name, "label": "1", "title": "t"}],
                             "pass 'vocal' has a name that is not one plain line")

    def test_two_passes_with_one_name(self):
        self.refused([{"key": "vocal", "name": "Plain", "label": "1", "title": "t"},
                      {"key": "bare", "name": "plain", "label": "2", "title": "t"}],
                     "passes 'vocal' and 'bare' are both named 'plain'",
                     "a button shows nothing but its name")

    def test_every_fault_is_listed_not_only_the_first(self):
        text = self.refused([{"key": "vocal", "label": "1", "title": "t"},
                             {"key": "chunks", "name": "x" * 13, "label": "2", "title": "t"}],
                            "pass 'vocal' has no", "pass 'chunks' is named")
        self.assertIn("; ", text)

    def test_a_name_in_the_language_s_own_script(self):
        """A person may name a level in their own language -- Persian, with a
        zero-width non-joiner in it, is a name like any other."""
        L = languages.Lang("xx", row([{"key": "vocal", "name": "با‌اعراب", "label": "1",
                                       "title": "t"}]))
        self.assertEqual(L.passes[0]["name"], "با‌اعراب")
        self.assertEqual(languages.level_name_problems(L.passes), [])

    def test_a_row_with_no_passes_has_nothing_to_name(self):
        self.assertEqual(languages.Lang("xx", row([])).passes, [])
        self.assertEqual(languages.level_name_problems([]), [])
        self.assertEqual(languages.level_name_problems(None), [])


class DefaultNames(unittest.TestCase):
    """languages.default_level_name: the one rule a new language's names are
    written by (lib/newlang.py) and an older row is read by."""

    def test_by_key(self):
        self.assertEqual(languages.default_level_name({}, {"key": "chunks"}), "Chunks")
        self.assertEqual(languages.default_level_name({}, {"key": "bare"}), "Plain")
        self.assertEqual(languages.default_level_name({}, {"key": "vocal"}), "Sentence")

    def test_marks_that_come_off(self):
        arabic = {"strip": "\\u064B-\\u0652", "script": "arabic"}
        other = {"strip": "\\u05B0-\\u05C7", "script": "other"}
        self.assertEqual(languages.default_level_name(arabic, {"key": "vocal"}), "With vowels")
        self.assertEqual(languages.default_level_name(other, {"key": "vocal"}), "With marks")

    def test_the_reading_names_its_levels(self):
        zh = {"words": True, "translit_label": "pinyin"}
        ja = {"words": True, "reading": True, "reading_label": "kana"}
        self.assertEqual(languages.default_level_name(zh, {"key": "vocal"}), "Pinyin")
        self.assertEqual(languages.default_level_name(zh, {"key": "aloud"}), "Pinyin only")
        self.assertEqual(languages.default_level_name(ja, {"key": "vocal"}), "Kana")
        self.assertEqual(languages.default_level_name(ja, {"key": "aloud"}), "Kana only")

    def test_a_reading_too_long_for_a_button_is_just_the_reading(self):
        long = {"words": True, "translit_label": "transliteration"}
        self.assertEqual(languages.default_level_name(long, {"key": "vocal"}), "Reading")
        self.assertEqual(languages.default_level_name(long, {"key": "aloud"}), "Reading only")
        wide = {"words": True, "translit_label": "romanisation"}      # 12: fits alone, not with "only"
        self.assertEqual(languages.default_level_name(wide, {"key": "vocal"}), "Romanisation")
        self.assertEqual(languages.default_level_name(wide, {"key": "aloud"}), "Reading only")

    def test_the_last_pass(self):
        self.assertEqual(languages.default_level_name({}, {"key": "alt", "kind": "vertical"}),
                         "Vertical")
        self.assertEqual(languages.default_level_name({"fonts": {"alt_key": "nastaliq"}},
                                                      {"key": "alt", "kind": "font"}), "Nastaliq")
        self.assertEqual(languages.default_level_name({"fonts": {"alt_key": "alt"}},
                                                      {"key": "alt", "kind": "font"}), "Other font")
        self.assertEqual(languages.default_level_name({}, {"key": "alt", "kind": "font"}),
                         "Other font")

    def test_the_rule_gives_every_name_the_registry_ships(self):
        """ONE RULE names a new language's passes and an older row's, and it
        gives exactly the names the owner settled for the eleven -- Japanese's
        Furigana included, from its vocal_label ("with furigana") -- so a
        language added with the generator is named as Parseh's own are, and
        the rule is not a second opinion."""
        rows = languages.read_rows()[0]
        for L in shipped_langs():
            for p in L.passes:
                with self.subTest(code=L.code, key=p["key"]):
                    self.assertEqual(languages.default_level_name(rows[L.code], p), p["name"])

    def test_a_vocal_label_that_names_the_reading_names_the_level(self):
        ja = {"words": True, "reading": True, "reading_label": "kana", "vocal_label": "with furigana"}
        self.assertEqual(languages.default_level_name(ja, {"key": "vocal"}), "Furigana")
        self.assertEqual(languages.default_level_name(ja, {"key": "aloud"}), "Kana only")
        # one that does not say "with <reading>", or whose reading is too long, leaves it to the reading's own name
        for said in ("the sentence", "with", "with ", "with a reading far too long"):
            with self.subTest(said=said):
                self.assertEqual(languages.default_level_name(dict(ja, vocal_label=said),
                                                              {"key": "vocal"}), "Kana")

    def test_whatever_it_gives_is_a_valid_name(self):
        shapes = [{}, {"strip": "x", "script": "arabic"}, {"words": True},
                  {"words": True, "translit_label": "a very long name for a scheme"},
                  {"reading": True, "reading_label": "kana"},
                  {"fonts": {"alt_key": "an extremely long face name"}}]
        for d in shapes:
            for key in ("vocal", "aloud", "chunks", "bare", "alt", "odd_key", ""):
                with self.subTest(row=d, key=key):
                    name = languages.default_level_name(d, {"key": key, "kind": "font"})
                    self.assertTrue(1 <= len(name) <= languages.LEVEL_NAME_MAX, name)


if __name__ == "__main__":
    unittest.main()
