#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Adding a language, made easier (a0.6.1), and a language's varieties.

  1  every per-language fact is the row's: analysis, examples, compounds; the
     analyzer tables are built from it, and no shipped language lacks them
  2  lib/langfeatures.py answers for every language, and its states mean what
     they say (a template's TODO is MISSING, a file that is there is HAVE)
  3  lib/langprompts.py: a prompt for every piece, and an intake that takes a
     fenced, an unfenced and a nested-fence answer, and refuses what Parseh
     could not read or should not run (a \\directlua in a "How to read this")
  4  a variety: languages.get("ar.egy"), its files' key, draft's refusal of a
     variety the language has not, getdict's extracts and codes
  5  a word of a dialect text: the dialect's rules and dictionary first, the
     standard one after, the dialect's hits marked; a standard text unchanged
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))
import analyzer       # noqa: E402
import draft          # noqa: E402
import getdict        # noqa: E402
import langfeatures   # noqa: E402
import langprompts    # noqa: E402
import languages      # noqa: E402
import lookup         # noqa: E402

SHIPPED = json.load(open(os.path.join(ROOT, "lib", "languages.json"), encoding="utf-8"))["_shipped"]


class TheRow(unittest.TestCase):
    def test_every_shipped_language_says_its_analysis_and_its_examples(self):
        for code in SHIPPED:
            L = languages.get(code)
            with self.subTest(code=code):
                self.assertTrue(L.analysis["morphology"], "no analyzer named for %s" % code)
                for k in ("dict", "corpus", "model"):
                    self.assertTrue(L.examples.get(k), "%s has no %s example" % (code, k))

    def test_the_analyzer_tables_are_the_rows(self):
        for code in SHIPPED:
            L = languages.get(code)
            self.assertEqual(analyzer.MORPHOLOGY.get(code), L.analysis["morphology"], code)
            self.assertEqual(analyzer.SYNTAX.get(code), L.analysis["syntax"], code)

    def test_compounds_and_the_record_a_page_embeds(self):
        self.assertEqual(languages.get("de").compounds, "parts")
        self.assertEqual(languages.get("ca").compounds, "verb")
        rec = languages.get("ar").as_json()
        self.assertEqual([v["key"] for v in rec["varieties"]], ["egy", "lev", "gulf", "mor"])
        self.assertIn("examples", rec)

    def test_langs_css_names_every_language(self):
        css = languages.css()
        for L in languages.LANGS.values():
            self.assertIn("[data-lang=%s]{" % L.code, css)
            self.assertIn('--tl-name:"%s"' % L.name, css)


class Features(unittest.TestCase):
    def test_every_language_is_answered_and_the_states_are_known(self):
        for code in languages.LANGS:
            fs = langfeatures.features(code)
            self.assertGreaterEqual(len(fs), 15, code)
            for f in fs:
                self.assertIn(f.state, (langfeatures.HAVE, langfeatures.MISSING, langfeatures.OPTIONAL,
                                        langfeatures.ASKED), (code, f.key))

    def test_a_template_is_not_conventions(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "x.md")
            with open(p, "w", encoding="utf-8") as f:
                f.write("# X\n\nTODO: the scheme\n")
            self.assertTrue(langfeatures._todo_left(p))
            with open(p, "w", encoding="utf-8") as f:
                f.write("# X\n\nThe scheme, written.\n")
            self.assertFalse(langfeatures._todo_left(p))

    def test_the_shipped_languages_miss_nothing_core(self):
        for code in SHIPPED:
            _have, _of, missing = langfeatures.summary(code)
            self.assertEqual(missing, [], code)


class Prompts(unittest.TestCase):
    def test_a_prompt_for_every_piece_names_the_language_and_its_model(self):
        for piece in langprompts.PIECES:
            text = langprompts.prompt("ca", piece, like="es")
            self.assertIn("Catalan", text)
            # Spanish has no lookup rules: the nearest language that has them lends its own
            self.assertIn("Italian's, as the model" if piece == "lookup-rules" else "Spanish's, as the model", text)
            self.assertIn("````", text)

    def test_the_outermost_fence_is_the_answer(self):
        body = "# X\n## Example\n```json\n{}\n```\nend"
        for wrapped in ("Here:\n````markdown\n%s\n````\nthanks" % body, "```markdown\n%s\n```" % body, body):
            self.assertEqual(langprompts._unfence(wrapped), body + "\n", wrapped[:20])

    def test_the_intake_refuses_what_parseh_cannot_read_or_should_not_run(self):
        with self.assertRaises(langprompts.Refused):
            langprompts.intake("ca", "conventions", "````\n# Catalan\n\n## The text field\nonly one section\n````")
        with self.assertRaises(langprompts.Refused) as e:
            langprompts.intake("ca", "howto", "\\newcommand{\\FrankHowTo}{%\nRead it. \\input{/etc/passwd} more}")
        self.assertIn("\\input", str(e.exception))
        with self.assertRaises(langprompts.Refused):
            langprompts.intake("ca", "examples", "{\"dict\": [1, 2]}")
        with self.assertRaises(langprompts.Refused):
            langprompts.intake("ca", "chunk-rules", "{\"np_head\": \"sideways\", \"adposition\": \"before\"}")
        with self.assertRaises(langprompts.Refused):
            langprompts.intake("ca", "lookup-rules", "not json")

    def test_a_row_value_is_written_in_the_registrys_own_style(self):
        self.assertEqual(langprompts._compact({"a": [1, 2]}), '{\n      "a": [1, 2]\n    }')
        self.assertEqual(langprompts._compact("x"), '"x"')


class Varieties(unittest.TestCase):
    def test_a_variety_is_the_language_under_another_key(self):
        V = languages.get("ar.egy")
        self.assertEqual((V.code, V.key, V.variety, V.variety_name), ("ar", "ar.egy", "egy", "Egyptian Arabic"))
        self.assertIs(languages.get("ar").with_variety("nope"), languages.get("ar"))
        with self.assertRaises(KeyError):
            languages.get("ar.nope")

    def test_draft_writes_a_variety_the_language_has_and_refuses_another(self):
        ar = languages.get("ar")
        self.assertEqual(draft._variety(ar, "lev"), {"variety": "lev"})
        self.assertEqual(draft._variety(ar, ""), {})
        self.assertEqual(draft._variety(ar, "standard"), {})
        with self.assertRaises(ValueError):
            draft._variety(ar, "iraqi")
        with self.assertRaises(ValueError):
            draft._variety(languages.get("it"), "egy")

    def test_a_variety_of_two_extracts_is_fetched_from_both(self):
        V = languages.get("ar.lev")
        urls = getdict.urls_for(V)
        self.assertEqual(len(urls), 2)
        self.assertTrue(urls[0].endswith("/South%20Levantine%20Arabic/kaikki.org-dictionary-SouthLevantineArabic.jsonl"))
        self.assertEqual(getdict.accepted_codes(V), {"ajp", "apc"})
        self.assertEqual(getdict.accepted_codes(languages.get("ar")), {"ar"})
        self.assertEqual(getdict.url_for(languages.get("ar")),
                         "https://kaikki.org/dictionary/Arabic/kaikki.org-dictionary-Arabic.jsonl")


def _dict(path, code, rows):
    c = lookup.create(path)
    for head, pos, sense, forms in rows:
        cur = c.execute("INSERT INTO entry (headword, pos, sense, sense_tags) VALUES (?,?,?,?)",
                        (head, pos, sense, ""))
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


class DialectLookup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        td = tempfile.TemporaryDirectory()
        cls.addClassCleanup(td.cleanup)
        _dict(os.path.join(td.name, "ar.db"), "ar",
              [("كتب", "verb", "to write", ["يكتب"]), ("وقت", "noun", "time", [])])
        _dict(os.path.join(td.name, "ar.egy.db"), "ar",
              [("دلوقتي", "adv", "now", [])])
        was = lookup.DICT_DIR
        lookup.DICT_DIR = td.name
        _forget()
        cls.addClassCleanup(lambda: (setattr(lookup, "DICT_DIR", was), _forget()))

    def hits(self, text, variety=None):
        got = lookup.look_up("ar", text, variety=variety)
        return {w["word"]: [(h["headword"], h.get("variety", "")) for h in w["hits"]] for w in got["words"]}

    def test_a_dialect_text_reads_the_dialects_words_and_forms(self):
        got = self.hits("هيكتب دلوقتي", "egy")
        self.assertEqual(got["هيكتب"][0], ("كتب", ""))            # the future's ha- taken off, the standard verb
        self.assertEqual(got["دلوقتي"][0], ("دلوقتي", "Egyptian Arabic"))

    def test_read_as_standard_the_same_text_finds_neither(self):
        got = self.hits("هيكتب دلوقتي")
        self.assertEqual(got["دلوقتي"], [])
        self.assertEqual(got["هيكتب"], [])

    def test_a_dialect_hit_says_where_it_is_from_in_its_note(self):
        got = lookup.look_up("ar", "دلوقتي", variety="egy")
        self.assertTrue(got["words"][0]["hits"][0]["note"].startswith("Egyptian Arabic"))


if __name__ == "__main__":
    unittest.main()
