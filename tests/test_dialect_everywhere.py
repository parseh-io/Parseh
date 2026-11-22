# SPDX-License-Identifier: GPL-3.0-or-later
"""The variety a text is written in (Arabic's dialects), beyond books and videos (a0.6.3, TO-DO 12.28, 12.34, 12.32).

    python3 -m unittest tests/test_dialect_everywhere.py

Held here, on real files in temporary trees:

  * a studio document says its variety in its front matter (`variety:`): written there and taken out again by
    the document's info (store.update_meta), read into meta.json, refused for a key its language has not,
    dropped by the parser for a language without varieties, and absent in a document written before it existed;
    the library's list names it; its prompts (the exercise prompt, the prompt page's) say it, and the skill's
    request carries it;
  * an exercise deck stores it in deck.json: made with one, changed, refused, carried by an export into another
    Parseh, and a deck made before there were any is the standard language;
  * a book made in place records the request's variety in book.json; its instructions name the dialect and
    offer no analyzer for it; its skill request carries it;
  * Settings -> Languages: Arabic has four sub-rows, each feature found by the presence of its file (a per-variety
    chunk list or romanisation file appearing turns its row to "have");
  * a book's card on the library and a video's card on the index say the dialect, on the computer and the phone.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for p in ("markdown/exlex", "markdown/app", "lib", "youtube/lib", "."):
    sys.path.insert(0, str(ROOT / p))
import languages                                               # noqa: E402
import mdparser                                                # noqa: E402
import store                                                   # noqa: E402
import decks                                                   # noqa: E402
import making                                                  # noqa: E402
import skills                                                  # noqa: E402
import langfeatures                                            # noqa: E402
import languagespage                                           # noqa: E402

DOC = "---\ntitle: Fi el-maktab\nlang: en\ntarget: ar\n---\n\n## Words\n\n[دلوقتي]{tl} now.\n"


def _tmp(test):
    d = tempfile.mkdtemp(prefix="test-dialect-", dir=os.environ.get("TMPDIR") or None)
    test.addCleanup(shutil.rmtree, d, ignore_errors=True)
    return Path(d)


class Documents(unittest.TestCase):
    def setUp(self):
        self.root = _tmp(self)
        self.old_lib = store.use_library(self.root / "library")
        self.addCleanup(store.use_library, self.old_lib)

    def test_the_front_matter_line_round_trips(self):
        a = store.set_variety(DOC, "egy")
        self.assertIn("target: ar\nvariety: egy\n---", a)
        self.assertEqual("egy", mdparser.parse(a)[0]["variety"])
        b = store.set_variety(a, "lev")
        self.assertEqual(1, b.count("variety:"))
        self.assertEqual(DOC, store.set_variety(b, "standard"))
        self.assertEqual(DOC, store.set_variety(b, ""))
        with self.assertRaises(store.StoreError):
            store.set_variety(DOC, "xyz")
        with self.assertRaises(store.StoreError):
            store.set_variety(DOC.replace("target: ar", "target: fa"), "egy")

    def test_the_parser_keeps_only_a_variety_the_language_has(self):
        self.assertNotIn("variety", mdparser.parse(DOC.replace("target: ar", "target: ar\nvariety: xyz"))[0])
        self.assertNotIn("variety", mdparser.parse(DOC.replace("target: ar", "target: it\nvariety: egy"))[0])
        self.assertEqual("gulf", mdparser.parse(DOC.replace("target: ar", "target: ar\nvariety: Gulf"))[0]["variety"])

    def test_the_document_info_writes_it_and_the_record_follows(self):
        meta = store.create(DOC)
        self.assertNotIn("variety", meta)                     # written before there were any: the standard language
        doc = meta["id"]
        meta = store.update_meta(doc, {"variety": "egy"})
        self.assertEqual("egy", meta["variety"])
        got, md = store.get(doc)
        self.assertEqual("egy", got["variety"])
        self.assertIn("variety: egy", md)
        listed = [d for d in store.list_docs() if d["id"] == doc][0]
        self.assertEqual(("egy", "Egyptian Arabic"), (listed["variety"], listed["variety_name"]))
        meta = store.update_meta(doc, {"variety": ""})
        self.assertNotIn("variety", meta)
        self.assertNotIn("variety", store.get(doc)[1])
        with self.assertRaises(store.StoreError):
            store.update_meta(doc, {"variety": "mor-x"})
        # a `variety:` typed into the editor is read the same way
        store.save_markdown(doc, store.set_variety(store.get(doc)[1], "mor"))
        self.assertEqual("mor", store.get(doc)[0]["variety"])

    def test_its_prompts_name_it(self):
        import server
        md = store.set_variety(DOC, "egy")
        a, _rows = server.exercise_prompt(md)
        self.assertEqual("egy", a.target.variety)
        self.assertIn("This text is in Egyptian Arabic", a.text)
        self.assertNotIn("This text is in", server.exercise_prompt(DOC)[0].text)
        L = languages.get("ar").with_variety("lev")
        p = server.studio_prompt(L)
        self.assertIn("written in Levantine Arabic: write `target: ar` and `variety: lev`", p.text)
        self.assertIn("This text is in Levantine Arabic", p.text)
        self.assertNotIn("variety", server.studio_prompt(languages.get("ar")).text.split("\n")[1])
        req = skills.for_studio(L, p, [])
        self.assertTrue(req["available"], req)
        self.assertEqual("Levantine Arabic (lev)", skills.parse_header(req["text"])["variety"])


class Decks(unittest.TestCase):
    def setUp(self):
        self.root = _tmp(self)
        self.old = decks.set_dir(self.root / "exercises")
        self.addCleanup(decks.set_dir, self.old)

    def test_a_deck_stores_changes_and_carries_it(self):
        d = decks.create_deck("Masri", "ar", "egy")
        self.assertEqual(("egy", "Egyptian Arabic"), (d["variety"], d["variety_name"]))
        self.assertEqual(["egy", "lev", "gulf", "mor"], [v["key"] for v in d["varieties"]])
        on_disk = json.loads((decks.deck_dir(d["folder"], d["slug"]) / "deck.json").read_text("utf-8"))
        self.assertEqual("egy", on_disk["variety"])
        d = decks.update_deck(d["folder"], d["slug"], variety="mor")
        self.assertEqual("mor", d["variety"])
        with self.assertRaises(decks.DeckError):
            decks.update_deck(d["folder"], d["slug"], variety="xx")
        data, _name = decks.export_zip(d["folder"], d["slug"], False)
        decks.set_dir(self.root / "other")
        got = decks.import_zip(data)["deck"]
        self.assertEqual("mor", got["variety"])
        d = decks.update_deck(got["folder"], got["slug"], variety="standard")
        self.assertEqual(("", ""), (d["variety"], d["variety_name"]))
        self.assertNotIn("variety", json.loads((decks.deck_dir(d["folder"], d["slug"]) / "deck.json")
                                               .read_text("utf-8")))

    def test_an_old_deck_and_a_language_without_varieties(self):
        d = decks.create_deck("Old", "ar")
        self.assertEqual("", d["variety"])
        it = decks.create_deck("Italiano", "it")
        self.assertEqual([], it["varieties"])
        with self.assertRaises(decks.DeckError):
            decks.create_deck("No", "it", "egy")


PDF_TEXT = "دلوقتي بكتب.\n".encode("utf-8")


class MadeInPlace(unittest.TestCase):
    def make(self, variety):
        into = _tmp(self) / "books"
        into.mkdir()
        fields = {"lang": "ar", "gloss": "en", "title": "كتاب", "title_latin": "Ketab", "author": "x",
                  "author_latin": "x", "variety": variety}
        return making.make(fields, {"name": "a.txt", "data": PDF_TEXT}, {}, into=str(into))

    def test_the_request_s_variety_is_the_book_s(self):
        r = self.make("egy")
        meta = json.loads(Path(r["path"], "book.json").read_text("utf-8"))
        self.assertEqual("egy", meta["variety"])
        agents = Path(r["path"], "AGENTS.md").read_text("utf-8")
        self.assertIn("This text is in Egyptian Arabic", agents)
        self.assertNotIn("variety", json.loads(Path(self.make("")["path"], "book.json").read_text("utf-8")))

    def test_no_analysis_and_the_skill_says_it(self):
        with mock.patch("analysisconfig.choice", return_value="on"), \
                mock.patch("analyzer.available", return_value=True):
            L = languages.get("ar")
            self.assertTrue(making.evidence_helper({"python": "py", "lib": "lib"}, L))
            self.assertEqual("", making.evidence_helper({"python": "py", "lib": "lib"}, L.with_variety("gulf")))
        facts = making.form_facts({"lang": "ar", "gloss": "en", "title": "كتاب", "title_latin": "Ketab",
                                   "variety": "gulf"}, {})
        self.assertEqual("gulf", facts["book"]["variety"])
        self.assertIn("This text is in Gulf Arabic", making.instructions_text(facts, {}))
        req = making.skill_request_for(facts, {}, 1000)
        self.assertTrue(req["available"], req)
        self.assertEqual("Gulf Arabic (gulf)", skills.parse_header(req["text"])["variety"])
        self.assertIn(skills.VARIETY_RULE, skills.build("parseh-book").files["SKILL.md"])
        with self.assertRaises(ValueError):
            making.form_facts({"lang": "ar", "gloss": "en", "title": "x", "variety": "xx"}, {})


class LanguagesPage(unittest.TestCase):
    def test_arabic_has_four_sub_rows(self):
        rows = {r["code"]: r for r in languagespage.view()["languages"]}
        self.assertEqual(["egy", "lev", "gulf", "mor"], [v["key"] for v in rows["ar"]["varieties"]])
        self.assertEqual([], rows["it"]["varieties"])
        egy = {f["key"]: f for f in rows["ar"]["varieties"][0]["features"]}
        for key in ("dictionary", "lookup-rules", "ipa", "chunk-rules", "verbs", "analysis", "prompts", "captions"):
            self.assertIn(key, egy)
        self.assertEqual("have", egy["lookup-rules"]["state"])       # lib/lang/ar.egy.lookup.json ships
        self.assertIn("arz", egy["captions"]["says"])

    def test_a_per_variety_file_is_found_by_its_presence(self):
        lang = _tmp(self) / "lang"
        shutil.copytree(str(ROOT / "lib" / "lang"), str(lang))
        for name in ("ar.lev.chunk.json", "ar.lev.ipa.json"):
            (lang / name).unlink(missing_ok=True)
        with mock.patch.object(langfeatures, "LANG_FILES", str(lang)):
            f = {x.key: x for x in langfeatures.variety_features("ar", "lev")}
            self.assertEqual(("optional", "optional"), (f["chunk-rules"].state, f["ipa"].state))
            (lang / "ar.lev.chunk.json").write_text("{}", encoding="utf-8")
            (lang / "ar.lev.ipa.json").write_text("{}", encoding="utf-8")
            f = {x.key: x for x in langfeatures.variety_features("ar", "lev")}
            self.assertEqual(("have", "have"), (f["chunk-rules"].state, f["ipa"].state))

    def test_the_dictionary_row_says_whether_it_is_fetched(self):
        with mock.patch.object(langfeatures, "_dictionary_of", side_effect=lambda k: {"entries": "12"} if k == "ar.egy" else None):
            self.assertEqual("have", langfeatures.variety_features("ar", "egy")[0].state)
            self.assertIn("12 entries", langfeatures.variety_features("ar", "egy")[0].says)
            self.assertEqual("optional", langfeatures.variety_features("ar", "mor")[0].state)


class Cards(unittest.TestCase):
    def test_a_video_card_says_its_dialect(self):
        import ytpages
        m = {"_dir": "arabic/abc", "_lang": "ar", "_segments": 1, "_glossed": 1, "variety": "lev", "title": "t"}
        self.assertIn('data-variety="lev">Levantine Arabic<', ytpages.video_card(dict(m)))
        self.assertNotIn("data-variety", ytpages.video_card(dict(m, variety="")))
        import mobile
        self.assertIn('data-variety="lev">Levantine Arabic<', mobile._video_card(dict(m)))

    def test_a_book_card_says_its_dialect(self):
        import books as booklib
        import make_index
        import mobile
        b = _tmp(self) / "arabic" / "mini-ar"
        shutil.copytree(str(ROOT / "tests/fixtures/books/arabic/mini-ar"), str(b),
                        ignore=shutil.ignore_patterns("reader", ".reader-key"))
        meta = json.loads((b / "book.json").read_text("utf-8"))
        meta["variety"] = "mor"
        (b / "book.json").write_text(json.dumps(meta), encoding="utf-8")
        self.assertIn('data-variety="mor">Moroccan Arabic<', make_index.card(booklib.Book(str(b))))
        self.assertIn('data-variety="mor">Moroccan Arabic<', mobile.book_card(booklib.Book(str(b))))
        meta.pop("variety")
        (b / "book.json").write_text(json.dumps(meta), encoding="utf-8")
        self.assertNotIn("data-variety", make_index.card(booklib.Book(str(b))))


if __name__ == "__main__":
    unittest.main()
