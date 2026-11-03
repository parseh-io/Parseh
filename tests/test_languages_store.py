# SPDX-License-Identifier: GPL-3.0-or-later
"""THE LANGUAGES A PERSON ADDS LIVE IN config/, BESIDE PARSEH'S OWN.

    python3 -m unittest tests/test_languages_store.py

lib/languages.json ships with Parseh and an update replaces it, so a row
lib/newlang.py spliced into it was a language the next update took away.
The registry now has two halves: Parseh's own table, and
config/languages.json for the languages added on one machine, read after it
(lib/languages.py, read_rows).  What is held here:

- the second half is read, marked as the person's, and loses to Parseh's own
  row for a code both hold; a folder somebody already has leaves it out; a
  store or a row that cannot be read stops nothing else;
- `_shipped` in lib/languages.json names every row that is Parseh's, and a
  row it does not name is moved to config/ -- once, the shipped rows coming
  out byte for byte, never in a git checkout unless asked, never over a
  store that could not be read, and never when the two copies differ;
- newlang.py writes a new language to config/ (its .tex and .md still to
  lib/lang/ and docs/lang/), with Anki ids from the personal part of the
  grid; --shipped writes Parseh's own table and its `_shipped` instead;
- the book preamble's Lua reads both halves by the same rule, and both halves
  are in both of build.sh's keys.

NOTHING HERE WRITES config/, lib/ OR docs/ OF THE CHECKOUT.  Every test works
on a temporary tree -- lib/languages.json copied into it, config/ beside it --
and newlang.py's paths are pointed there for as long as a test runs.
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
LIB = os.path.join(ROOT, "lib")
sys.path.insert(0, LIB)
import languages                                               # noqa: E402
import newlang                                                 # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


SHIPPED_TEXT = read(os.path.join(LIB, "languages.json"))
SHIPPED = json.loads(SHIPPED_TEXT)
CODES = [c for c, d in SHIPPED.items() if not c.startswith("_") and isinstance(d, dict)]


def korean(code="ko", folder="korean", name="Korean", slot=1234):
    """A whole row for a language nobody ships, shaped as newlang writes one:
    Italian's row with its names, folder, script and ids changed."""
    row = json.loads(json.dumps(SHIPPED["it"]))
    row.update(name=name, native="한국어", folder=folder, tag=folder, iso3="kor",
               script="other", chars="\\uAC00-\\uD7AF")
    row["anki"] = {"field": name,
                   "vocab_model": newlang.ANKI_BASE + newlang.ANKI_STEP * slot + 1,
                   "opposites_model": newlang.ANKI_BASE + newlang.ANKI_STEP * slot + 2,
                   "vocab_name": "Frank " + name, "opposites_name": "Frank %s Opposites" % name}
    return row


class Tree(unittest.TestCase):
    """A temporary install: lib/languages.json as the checkout has it, and a
    config/ beside it that starts empty."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix="parseh-langstore-")
        self.tmp = self._td.name
        self.shipped = os.path.join(self.tmp, "lib", "languages.json")
        self.personal = os.path.join(self.tmp, "config", "languages.json")
        write(self.shipped, SHIPPED_TEXT)

    def tearDown(self):
        self._td.cleanup()

    def load(self):
        return languages._load(self.shipped, self.personal)

    def with_extra(self, *rows):
        """lib/languages.json with rows added the way an older newlang.py
        added them: spliced before the closing brace."""
        text = SHIPPED_TEXT
        for code, row in rows:
            text = newlang.insert_entry(text, code, row)
        write(self.shipped, text)
        return text


class ShippedList(unittest.TestCase):
    def test_every_row_of_the_table_is_named(self):
        """`_shipped` is how a row of Parseh's is told from one somebody
        added: a row it forgets would be moved out of Parseh's own table at
        the next start of an install."""
        self.assertEqual(SHIPPED.get("_shipped"), CODES,
                         "lib/languages.json's _shipped must name every row it holds, in "
                         "order -- a language added to Parseh itself goes into both "
                         "(newlang.py --shipped does)")

    def test_the_store_is_found_beside_lib(self):
        self.assertEqual(os.path.realpath(languages.PERSONAL),
                         os.path.realpath(os.path.join(ROOT, "config", "languages.json")))
        self.assertEqual(newlang.PERSONAL, languages.PERSONAL)
        self.assertTrue(languages.STORE_FORMAT.startswith("parseh-languages/"))


class Reading(Tree):
    def test_a_person_row_is_read_after_and_marked(self):
        languages.write_store({"ko": korean()}, self.personal)
        langs, problems = self.load()
        self.assertEqual(problems, [])
        self.assertEqual(list(langs), CODES + ["ko"])
        self.assertTrue(langs["ko"].mine)
        self.assertFalse(any(langs[c].mine for c in CODES))
        self.assertTrue(langs["ko"].has_script("한국어"))
        doc = json.loads(read(self.personal))
        self.assertEqual(doc["_format"], languages.STORE_FORMAT)
        self.assertEqual(list(doc), ["_comment", "_format", "ko"])

    def test_parseh_own_row_wins_a_code_both_hold(self):
        languages.write_store({"it": korean("it", folder="notitalian", name="Not Italian")},
                              self.personal)
        langs, problems = self.load()
        self.assertEqual(langs["it"].name, "Italian")
        self.assertFalse(langs["it"].mine)
        self.assertEqual([c for c, _ in problems], ["it"])
        self.assertIn("Parseh itself now carries 'it' (Italian)", problems[0][1])

    def test_a_folder_already_taken_leaves_the_row_out(self):
        languages.write_store({"ko": korean(), "kq": korean("kq", folder="italian")},
                              self.personal)
        langs, problems = self.load()
        self.assertIn("ko", langs)
        self.assertNotIn("kq", langs)
        self.assertEqual(problems, [("kq", "its folder 'italian' is it's already, and one "
                                           "folder cannot hold two languages")])

    def test_a_store_that_is_not_json_stops_nothing(self):
        write(self.personal, "{not json")
        langs, problems = self.load()
        self.assertEqual(list(langs), CODES)
        self.assertEqual(problems[0][0], "")
        self.assertIn("config/languages.json cannot be read", problems[0][1])

    def test_a_row_that_cannot_be_read_stops_nothing(self):
        languages.write_store({"kx": {"folder": "broken"}, "ko": korean()}, self.personal)
        langs, problems = self.load()
        self.assertIn("ko", langs)
        self.assertNotIn("kx", langs)
        self.assertEqual([c for c, _ in problems], ["kx"])
        self.assertIn("cannot be read (KeyError", problems[0][1])

    def test_a_row_of_lib_that_parseh_does_not_ship_is_the_person_s(self):
        self.with_extra(("ko", korean()))
        langs, problems = self.load()
        self.assertTrue(langs["ko"].mine)
        self.assertEqual(problems, [])

    # --- the levels' names (a0.5.0): every pass has one, and the person's
    # rows obey the same rule as Parseh's own -- with one kindness
    def unnamed(self, row):
        for p in row["passes"]:
            del p["name"]
        return row

    def test_a_person_row_from_before_names_is_named_and_not_dropped(self):
        """An older newlang.py wrote rows without names, and an update must not
        take away a language somebody added: it is read with the default
        names, and the file -- theirs -- is not rewritten."""
        row = self.unnamed(korean())
        languages.write_store({"ko": row}, self.personal)
        langs, problems = self.load()
        self.assertEqual(problems, [])
        self.assertEqual([(p["key"], p["name"]) for p in langs["ko"].passes],
                         [("vocal", "Sentence"), ("chunks", "Chunks")])
        self.assertEqual(languages.read_store(self.personal)["ko"], row)

    def test_a_person_row_with_a_bad_name_is_left_out_and_says_why(self):
        for bad, why in (("x" * 13, "pass 'vocal' is named 'xxxxxxxxxxxxx', which is 13 characters"),
                         ("  ", "pass 'vocal' has no \"name\"")):
            with self.subTest(name=bad):
                row = korean()
                row["passes"][0]["name"] = bad
                languages.write_store({"ko": row}, self.personal)
                langs, problems = self.load()
                self.assertNotIn("ko", langs)
                self.assertEqual([c for c, _ in problems], ["ko"])
                self.assertIn("Korean (ko): " + why, problems[0][1])
                self.assertEqual(list(langs), CODES)          # nothing else is stopped

    def test_a_person_row_naming_some_passes_and_not_others_is_left_out(self):
        row = korean()
        del row["passes"][1]["name"]
        languages.write_store({"ko": row}, self.personal)
        langs, problems = self.load()
        self.assertNotIn("ko", langs)
        self.assertIn("pass 'chunks' has no \"name\"", problems[0][1])

    def test_a_row_of_parseh_s_own_without_a_name_is_refused_at_import(self):
        """A fault in lib/languages.json is a fault of the release: it raises,
        as it always has, and the message names the language and the pass."""
        raw = json.loads(SHIPPED_TEXT)
        del raw["it"]["passes"][0]["name"]
        write(self.shipped, json.dumps(raw, ensure_ascii=False, indent=2))
        with self.assertRaises(ValueError) as cm:
            self.load()
        self.assertIn("Italian (it): pass 'vocal' has no \"name\"", str(cm.exception))

    def test_a_table_from_before_shipped_is_all_parseh_s(self):
        """No _shipped: which rows are whose cannot be told, so none is
        called the person's and none is moved."""
        text = re.sub(r'\n  "_shipped": \[[^\]]*\],', "", SHIPPED_TEXT)
        self.assertNotIn('"_shipped":', text)
        text = newlang.insert_entry(text, "ko", korean())
        write(self.shipped, text)
        langs, _ = self.load()
        self.assertFalse(langs["ko"].mine)
        self.assertEqual(languages.migrate(self.shipped, self.personal), [])
        self.assertEqual(read(self.shipped), text)
        self.assertFalse(os.path.exists(self.personal))


class Migrating(Tree):
    def test_a_hand_added_row_moves_once(self):
        self.with_extra(("ko", korean()))
        said = languages.migrate(self.shipped, self.personal)
        self.assertEqual(len(said), 1, said)
        self.assertTrue(said[0].startswith("languages: ko (Korean) moved from "
                                           "lib/languages.json to config/languages.json"),
                        said[0])
        # Parseh's own rows come out exactly as the release shipped them
        self.assertEqual(read(self.shipped), SHIPPED_TEXT)
        self.assertEqual(languages.read_store(self.personal), {"ko": korean()})
        langs, problems = self.load()
        self.assertTrue(langs["ko"].mine)
        self.assertEqual(problems, [])
        # and the next start finds nothing to do, and writes nothing
        before = (os.stat(self.shipped).st_mtime_ns, os.stat(self.personal).st_mtime_ns)
        self.assertEqual(languages.migrate(self.shipped, self.personal), [])
        self.assertEqual(before, (os.stat(self.shipped).st_mtime_ns,
                                  os.stat(self.personal).st_mtime_ns))

    def test_two_rows_and_one_in_the_middle(self):
        """A hand may put a row anywhere, not only where newlang did."""
        text = newlang.insert_entry(SHIPPED_TEXT, "kz", korean("kz", folder="kz"))
        ar_end = [end for key, _, end in languages._members(text) if key == "ar"][0]
        row = json.dumps(korean(), indent=2, ensure_ascii=False).replace("\n", "\n  ")
        text = text[:ar_end] + ',\n  "ko": ' + row + text[ar_end:]
        write(self.shipped, text)
        self.assertEqual(list(json.loads(text))[:6],
                         ["_comment", "_shipped", "fa", "ar", "ko", "it"])
        said = languages.migrate(self.shipped, self.personal)
        self.assertEqual(len(said), 2, said)
        self.assertEqual(read(self.shipped), SHIPPED_TEXT)
        self.assertEqual(list(languages.read_store(self.personal)), ["ko", "kz"])

    def test_a_row_config_already_holds_is_only_taken_out(self):
        languages.write_store({"ko": korean()}, self.personal)
        store = read(self.personal)
        self.with_extra(("ko", korean()))
        self.assertEqual(len(languages.migrate(self.shipped, self.personal)), 1)
        self.assertEqual(read(self.shipped), SHIPPED_TEXT)
        self.assertEqual(read(self.personal), store)

    def test_two_rows_that_differ_are_both_left(self):
        languages.write_store({"ko": korean(name="Korean (mine)")}, self.personal)
        store = read(self.personal)
        text = self.with_extra(("ko", korean()))
        said = languages.migrate(self.shipped, self.personal)
        self.assertEqual(len(said), 1)
        self.assertTrue(said[0].startswith("!! languages: ko (Korean) is in "
                                           "lib/languages.json and in config/languages.json"))
        self.assertEqual(read(self.shipped), text)
        self.assertEqual(read(self.personal), store)
        langs, problems = self.load()
        self.assertEqual(langs["ko"].name, "Korean")
        self.assertEqual([c for c, _ in problems], ["ko"])

    def test_not_in_a_git_checkout_unless_asked(self):
        os.makedirs(os.path.join(self.tmp, ".git"))
        text = self.with_extra(("ko", korean()))
        self.assertEqual(languages.migrate(self.shipped, self.personal), [])
        self.assertEqual(read(self.shipped), text)
        self.assertFalse(os.path.exists(self.personal))
        self.assertEqual(len(languages.migrate(self.shipped, self.personal, force=True)), 1)
        self.assertEqual(read(self.shipped), SHIPPED_TEXT)

    def test_a_store_that_cannot_be_read_is_never_written_over(self):
        write(self.personal, "{half a file")
        text = self.with_extra(("ko", korean()))
        said = languages.migrate(self.shipped, self.personal)
        self.assertEqual(len(said), 1)
        self.assertTrue(said[0].startswith("!! languages:"))
        self.assertIn("config/languages.json cannot be read", said[0])
        self.assertEqual(read(self.personal), "{half a file")
        self.assertEqual(read(self.shipped), text)

    def test_nothing_to_move_writes_nothing(self):
        self.assertEqual(languages.migrate(self.shipped, self.personal), [])
        self.assertFalse(os.path.exists(self.personal))
        self.assertEqual(read(self.shipped), SHIPPED_TEXT)


class Adding(Tree):
    """newlang.py, pointed at the temporary tree."""

    KO = ["ko", "--name", "Korean", "--native", "한국어", "--script", "other",
          "--chars", "\\uAC00-\\uD7AF", "--iso3", "kor"]

    def setUp(self):
        super().setUp()
        lang_tex = os.path.join(self.tmp, "lib", "lang")
        lang_docs = os.path.join(self.tmp, "docs", "lang")
        shutil.copytree(os.path.join(LIB, "lang"), lang_tex)
        shutil.copytree(os.path.join(ROOT, "docs", "lang"), lang_docs)
        self.patches = [mock.patch.object(newlang, name, value) for name, value in (
            ("REGISTRY", self.shipped), ("PERSONAL", self.personal),
            ("LANG_TEX", lang_tex), ("LANG_DOCS", lang_docs),
            ("ROOT", self.tmp), ("STUDIO", os.path.join(self.tmp, "markdown")))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        super().tearDown()

    def run_newlang(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = newlang.main(list(argv))
            except SystemExit as e:
                rc = e.code
        return rc, out.getvalue(), err.getvalue()

    def test_a_new_language_goes_to_config(self):
        rc, out, err = self.run_newlang(*self.KO)
        self.assertEqual(rc, 0, out + err)
        self.assertIn("config/languages.json entry added", out)
        self.assertEqual(read(self.shipped), SHIPPED_TEXT)      # Parseh's own untouched
        row = languages.read_store(self.personal)["ko"]
        self.assertEqual((row["name"], row["folder"], row["iso3"]), ("Korean", "korean", "kor"))
        slot = (row["anki"]["vocab_model"] - newlang.ANKI_BASE) // newlang.ANKI_STEP
        self.assertGreaterEqual(slot, newlang.PERSONAL_SLOT)
        self.assertEqual(row["anki"]["opposites_model"], row["anki"]["vocab_model"] + 1)
        # the two files and the three folders are where they always were
        for rel in ("lib/lang/ko.tex", "docs/lang/ko.md", "books/korean/.gitkeep",
                    "youtube/videos/korean/.gitkeep", "markdown/library/korean/.gitkeep"):
            self.assertTrue(os.path.isfile(os.path.join(self.tmp, rel)), rel)
        langs, problems = self.load()
        self.assertTrue(langs["ko"].mine)
        self.assertEqual(problems, [])
        # and it is refused a second time, saying whose it is
        rc, out, err = self.run_newlang(*self.KO)
        self.assertEqual(rc, 2)
        self.assertIn("'ko' is already Korean (added on this machine, in "
                      "config/languages.json)", err)

    def test_check_says_whose(self):
        self.assertEqual(self.run_newlang(*self.KO)[0], 0)
        rc, out, _ = self.run_newlang("--check")
        self.assertIn("  ko  Korean (korean)  -- added on this machine", out)
        self.assertIn("ok       lib/lang/ko.tex", out)
        self.assertEqual(rc, 0, out[-2000:])
        rc, out, _ = self.run_newlang()
        self.assertIn("added on this machine", out)

    # --- the levels' names, written by the generator and refused by its check
    def dry_row(self, *argv):
        """The row `newlang.py <argv> --dry-run` would add, as data."""
        rc, out, err = self.run_newlang(*(list(argv) + ["--dry-run"]))
        self.assertEqual(rc, 0, out + err)
        text = out[out.index("\n{") + 1:out.index("\n--dry-run")]
        return list(json.loads(text).values())[0]

    def test_a_new_language_carries_names(self):
        rc, out, err = self.run_newlang(*self.KO)
        self.assertEqual(rc, 0, out + err)
        row = languages.read_store(self.personal)["ko"]
        self.assertEqual([(p["key"], p["name"], p["label"], p["title"]) for p in row["passes"]],
                         [("vocal", "Sentence", "1", "the sentence, to read on its own"),
                          ("chunks", "Chunks", "2", newlang.CHUNKS_TITLE)])
        langs, problems = self.load()
        self.assertEqual(problems, [])
        self.assertEqual([p["name"] for p in langs["ko"].passes], ["Sentence", "Chunks"])
        # the summary says what each button will wear, and that it can be renamed
        self.assertIn("Sentence (the sentence, to read on its own); Chunks (", out)
        self.assertIn("a person renames a level on their own pages", out)

    def test_the_names_follow_what_the_language_has(self):
        shape = lambda row: [(p["key"], p["name"]) for p in row["passes"]]
        # marks that come off, in an Arabic script, and an alternate face
        urdu = self.dry_row("ur", "--name", "Urdish", "--native", "Urdish", "--script", "arabic",
                            "--alt-font", "Noto Nastaliq Urdu", "--alt-key", "nastaliq")
        self.assertEqual(shape(urdu), [("vocal", "With vowels"), ("chunks", "Chunks"),
                                       ("bare", "Plain"), ("alt", "Nastaliq")])
        self.assertEqual(urdu["passes"][2]["title"],
                         "the sentence as Urdish is ordinarily printed, with no marks")
        self.assertEqual(urdu["passes"][3]["kind"], "font")
        # the same, with no name for the face: a face has to be called something
        plain = self.dry_row("uq", "--name", "Urdq", "--native", "Urdq", "--script", "arabic",
                             "--alt-font", "Noto Nastaliq Urdu")
        self.assertEqual(shape(plain)[-1], ("alt", "Other font"))
        # marks in a script that is not Arabic's are not vowels
        marks = self.dry_row("hb", "--name", "Hebrewish", "--native", "Hebrewish", "--script",
                             "other", "--chars", "\\u05D0-\\u05EA", "--strip", "\\u05B0-\\u05C7")
        self.assertEqual(shape(marks), [("vocal", "With marks"), ("chunks", "Chunks"),
                                        ("bare", "Plain")])
        # words and a vertical setting: the reading names two levels, in all five passes
        zhish = self.dry_row("qx", "--name", "Testish", "--native", "Testish", "--script", "cjk",
                             "--words", "--vertical", "--translit-label", "pinyin")
        self.assertEqual(shape(zhish), [("vocal", "Pinyin"), ("aloud", "Pinyin only"),
                                        ("chunks", "Chunks"), ("bare", "Plain"),
                                        ("alt", "Vertical")])
        self.assertEqual([p["title"] for p in zhish["passes"]],
                         ["with pinyin over each word", "the reading alone, in pinyin",
                          newlang.CHUNKS_TITLE, "plain, as Testish is written",
                          newlang.VERTICAL_TITLE])
        # a reading with a long name: it would not fit a button, so the level is "Reading"
        long = self.dry_row("ql", "--name", "Longish", "--native", "Longish", "--script", "cjk",
                            "--words")
        self.assertEqual(shape(long)[:2], [("vocal", "Reading"), ("aloud", "Reading only")])
        # a reading beside the transliteration, over each chunk and not each word
        kana = self.dry_row("qk", "--name", "Kanaish", "--native", "Kanaish", "--script", "cjk",
                            "--reading", "--reading-label", "kana")
        self.assertEqual(shape(kana)[0], ("vocal", "Kana"))
        self.assertEqual(kana["passes"][0]["title"], "with kana over each chunk")
        # the labels still count the passes the language has
        self.assertEqual([p["label"] for p in zhish["passes"]], ["1", "2", "3", "4", "5"])
        self.assertEqual([p["label"] for p in urdu["passes"]], ["1", "2", "3", "4"])

    def test_every_row_it_writes_is_a_row_the_registry_accepts(self):
        for argv in (["qa", "--name", "Aaa", "--native", "Aaa"],
                     ["qb", "--name", "Bbb", "--native", "Bbb", "--script", "arabic"],
                     ["qc", "--name", "Ccc", "--native", "Ccc", "--script", "cjk", "--words",
                      "--vertical"],
                     ["qd", "--name", "Ddd", "--native", "Ddd", "--script", "devanagari"]):
            with self.subTest(code=argv[0]):
                row = self.dry_row(*argv)
                self.assertEqual(languages.level_name_problems(row["passes"]), [])
                languages.Lang(argv[0], row)

    def test_check_refuses_a_row_of_parseh_s_own_without_a_name(self):
        raw = json.loads(SHIPPED_TEXT)
        del raw["it"]["passes"][1]["name"]
        write(self.shipped, json.dumps(raw, ensure_ascii=False, indent=2))
        rc, out, _ = self.run_newlang("--check")
        self.assertEqual(rc, 1)
        self.assertIn("MISSING  lib/languages.json: Italian (it): pass 'chunks' has no \"name\"", out)
        self.assertIn("what is missing", out)

    def test_check_refuses_a_bad_name_and_notes_a_row_from_before_names(self):
        self.assertEqual(self.run_newlang(*self.KO)[0], 0)
        stored = languages.read_store(self.personal)
        # a row an older newlang.py wrote: read with the default names, and told so
        for p in stored["ko"]["passes"]:
            del p["name"]
        languages.write_store(stored, self.personal)
        rc, out, _ = self.run_newlang("--check")
        self.assertEqual(rc, 0, out[-1500:])
        self.assertRegex(out, r"note +its passes have no names \(the row was written before "
                              r"they had any\): Parseh reads them as 'Sentence', 'Chunks'")
        # a name that is wrong is a fault: the language is left out of every page
        stored["ko"]["passes"][0]["name"] = "y" * 20
        stored["ko"]["passes"][1]["name"] = "Chunks"
        languages.write_store(stored, self.personal)
        rc, out, _ = self.run_newlang("--check")
        self.assertEqual(rc, 1)
        self.assertRegex(out, r"MISSING +level names: pass 'vocal' is named 'y{20}', which is "
                              r"20 characters")
        self.assertRegex(out, r"MISSING +every page goes without this language: .*Korean \(ko\)")
        # and a row with its names mended says them
        stored["ko"]["passes"][0]["name"] = "Sentence"
        languages.write_store(stored, self.personal)
        rc, out, _ = self.run_newlang("--check")
        self.assertEqual(rc, 0, out[-1500:])
        self.assertIn("ok       level names Sentence / Chunks", out)

    def test_check_reports_what_was_left_out(self):
        languages.write_store({"it": korean("it", folder="notitalian"),
                               "kq": korean("kq", folder="italian", slot=1300),
                               "ky": korean("ky", folder="kyish", slot=12)}, self.personal)
        rc, out, _ = self.run_newlang("--check")
        self.assertEqual(rc, 1)                  # the folder clash is a fault
        self.assertRegex(out, r"note +it: Parseh itself now carries 'it' \(Italian\)")
        self.assertRegex(out, r"MISSING +kq: its folder 'italian' is it's already")
        # a row on Parseh's own walk of the Anki grid is told so
        self.assertRegex(out, r"note +its Anki ids are slot 12 of the part of the grid "
                              r"Parseh's own languages are given")

    def test_shipped_goes_into_parseh_own_table(self):
        rc, out, err = self.run_newlang(*(self.KO + ["--shipped"]))
        self.assertEqual(rc, 0, out + err)
        self.assertFalse(os.path.exists(self.personal))
        text = read(self.shipped)
        raw = json.loads(text)
        self.assertEqual(raw["_shipped"], CODES + ["ko"])
        self.assertEqual(list(raw)[-1], "ko")
        # every row that was there comes out byte for byte: only the
        # _shipped line changed, and the row went in before the closing brace
        self.assertEqual(text.replace(json.dumps(CODES + ["ko"], ensure_ascii=False),
                                      json.dumps(CODES, ensure_ascii=False))
                         [:len(SHIPPED_TEXT) - 3], SHIPPED_TEXT[:-3])
        slot = (raw["ko"]["anki"]["vocab_model"] - newlang.ANKI_BASE) // newlang.ANKI_STEP
        self.assertLess(slot, newlang.PERSONAL_SLOT)
        langs, _ = self.load()
        self.assertFalse(langs["ko"].mine)
        self.assertEqual(languages.migrate(self.shipped, self.personal), [])

    def test_migrate_on_request(self):
        self.with_extra(("ko", korean()))
        os.makedirs(os.path.join(self.tmp, ".git"))
        rc, out, _ = self.run_newlang("--migrate")
        self.assertEqual(rc, 0)
        self.assertIn("ko (Korean) moved", out)
        self.assertEqual(read(self.shipped), SHIPPED_TEXT)
        rc, out, _ = self.run_newlang("--migrate")
        self.assertIn("nothing to move", out)

    def test_a_personal_pair_is_drawn_free(self):
        reg = dict(SHIPPED)
        reg["ko"] = korean(slot=newlang.PERSONAL_SLOT + 5)
        draws = iter([5, 5, 7])
        with mock.patch.object(newlang, "_pick", lambda n: next(draws)):
            vocab, opp, slot = newlang.next_anki_pair(reg, personal=True)
        self.assertEqual(slot, newlang.PERSONAL_SLOT + 7)
        self.assertEqual((vocab, opp), (newlang.ANKI_BASE + newlang.ANKI_STEP * slot + 1,
                                        newlang.ANKI_BASE + newlang.ANKI_STEP * slot + 2))
        # and Parseh's own walk is the one it always was: the slot after the last shipped language's (Catalan's, 12)
        self.assertEqual(newlang.next_anki_pair(reg)[2], 13)


TEXLUA = shutil.which("texlua")


@unittest.skipUnless(TEXLUA, "texlua is not on this machine")
class Preamble(Tree):
    """The book preamble reads the registry itself, in Lua: it has to take in
    the second half by the rule the Python side follows."""

    def lua(self, lib, cwd):
        pre = read(os.path.join(LIB, "frank-preamble.tex"))
        m = re.search(r"\\directlua\{\n  frank_registry = nil\n(.*?)\n\}\n", pre, re.S)
        self.assertIsNotNone(m, "the registry's \\directlua block has moved")
        body = m.group(1).replace("\\FrankLib", lib)
        self.assertNotIn("\\", body)
        script = os.path.join(self.tmp, "reg.lua")
        write(script, "\n".join((
            'kpse.set_program_name("luatex")',
            'require("lualibs")',
            'tex = tex or {} ; tex.error = function(m) print("ERROR " .. m) end',
            'texio = texio or {} ; texio.write_nl = function(m) print("LOG " .. m) end',
            "frank_registry = nil", body,
            'print(frank_reg("ko", "tex", "babel"))',
            'print(frank_reg("ko", "name"))',
            'print(frank_reg("it", "name"))',
            'print(frank_reg("fa", "tex", "main_fallbacks"))')))
        r = subprocess.run([TEXLUA, script], cwd=cwd, capture_output=True, text=True,
                           timeout=120)
        return r.stdout.rstrip("\n").split("\n")

    def test_the_pdf_reads_both_halves(self):
        row = korean()
        row["tex"] = dict(row["tex"], babel="korean")
        languages.write_store({"ko": row, "it": korean("it", name="Not Italian")},
                              self.personal)
        book = os.path.join(self.tmp, "books", "korean", "mini-ko")
        os.makedirs(book)
        want = ["korean", "Korean", "Italian", "Noto Naskh Arabic"]
        # as a book has it -- \FrankLib is ../../../lib from the book's folder
        self.assertEqual(self.lua("../../../lib", book), want)
        # and as an absolute path
        self.assertEqual(self.lua(os.path.join(self.tmp, "lib"), self.tmp), want)

    def test_no_store_and_a_broken_one(self):
        book = os.path.join(self.tmp, "books", "x", "y")
        os.makedirs(book)
        self.assertEqual(self.lua("../../../lib", book), ["", "", "Italian", "Noto Naskh Arabic"])
        write(self.personal, "{not json")
        got = self.lua("../../../lib", book)
        self.assertTrue(got[0].startswith("LOG frank: ../../../config/languages.json is not "
                                          "JSON"), got)
        self.assertEqual(got[1:], ["", "", "Italian", "Noto Naskh Arabic"])


class Around(unittest.TestCase):
    def test_both_halves_are_in_both_build_keys(self):
        """A change to a language added on this machine must rebuild its
        books, as a change to Parseh's own table does."""
        sh = read(os.path.join(ROOT, "build.sh"))
        for fn in ("latex_key", "reader_key"):
            body = re.search(r"^%s\(\) \{\n(.*?)\n\}" % fn, sh, re.S | re.M).group(1)
            self.assertIn('"$ROOT/lib/languages.json"', body, fn)
            self.assertIn('"$ROOT/config/languages.json"', body, fn)

    def test_the_store_is_kept_out_of_git(self):
        lines = read(os.path.join(ROOT, ".gitignore")).splitlines()
        self.assertIn("config/languages.json", lines)
        self.assertIn("config/languages.json.tmp", lines)

    def test_the_server_moves_rows_as_it_starts(self):
        src = read(os.path.join(ROOT, "serve.py"))
        main = src[src.index("\ndef main("):]
        self.assertIn("languages.migrate()", main)
        self.assertLess(main.index("languages.migrate()"), main.index("languages.write_css()"))


if __name__ == "__main__":
    unittest.main()
