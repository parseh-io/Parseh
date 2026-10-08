#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Your own prompts (lib/prompts.py, brief §8 of a0.4.2): the store, the export and
the import, what a route is asked for by id, keeping up with Parseh's own, the
studio's old prompt moved once, and the routes that hand it all out.

    python3 -m unittest tests/test_prompts_store.py

WHAT IS HELD, and where:

  * THE STORE: a prompt is added after Parseh's instructions unless it says it
    is in place of them; a name is one per place; an unknown placeholder, a
    block the kit does not know and the marks of the locked parts are refused on
    save in words that name them; Parseh's own prompt is not in the store and no
    route can touch it; export then import gives the same prompt, and an import
    that meets a name is renamed, never written over one;
  * EVERY PROMPT PARSEH READS BACK (the studio's two, a video from scratch, a
    stretch of a video or of a book, the tidy): what a person's text is handed to
    is the kit, and the answer contract and the data after it are Parseh's, word
    for word, so that an answer lands as one to Parseh's own -- driven through the
    real assemblers and the real doors that read an answer back;
  * KEEPING UP WITH PARSEH: a prompt in place of Parseh's says when Parseh's own
    changed since it began from it, and shows what changed;
  * THE STUDIO'S OLD PROMPT (library/_prompt.md) moves into the store once and
    only once, and the studio's old routes go on working on it;
  * THE ROUTES, on a real server: Settings' and the studio's own, a device let in
    over the Wi-Fi, a request from another site, and `prompt=<id>` on the doors
    that hand a prompt out.

NOTHING HERE WRITES config/: the store is pointed at a temporary tree in every
class (tests/configguard.py watches the whole run for the day one is not).
"""
import http.client
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for _p in ("tests", "markdown/exlex", "markdown/app", "lib", "youtube/lib", "."):
    if str(ROOT / _p) not in sys.path:
        sys.path.insert(0, str(ROOT / _p))
import check_annotations as CA                                  # noqa: E402
import glossregion as GR                                        # noqa: E402
import languages                                                # noqa: E402
import network                                                  # noqa: E402
import promptkit as K                                           # noqa: E402
import prompts as P                                             # noqa: E402
import server as studio_server                                  # noqa: E402
import store                                                    # noqa: E402
import tidy as tidier                                           # noqa: E402
import version                                                  # noqa: E402
import ytpages                                                  # noqa: E402
import test_glossregion as TG                                   # noqa: E402

FIX = ROOT / "tests" / "fixtures"
PERSIAN_VIDEO = FIX / "videos" / "persian" / "fA6bK2mQ8sT"
# what a person writes, for every place: a sentence the answer must carry on
# with whatever else is said, and a name of its own
MINE = "Never gloss the names of people."
NAMES = ("British spellings", "my rules", "الفبا", "日本語の規則")


def mine(surface, name="my rules", kind="added", text=MINE, **more):
    return dict(surface=surface, name=name, kind=kind, text=text, **more)


class Stored(unittest.TestCase):
    """A store in a temporary tree, for as long as a test runs."""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name)
        patcher = mock.patch.object(P, "STORE", str(self.tmp / "config" / "prompts.json"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def refused(self, fields, *words):
        with self.assertRaises(P.PromptsError) as cm:
            P.save(fields)
        for w in words:
            self.assertIn(w, str(cm.exception))
        return str(cm.exception)


class ThePlacesOfTheStore(unittest.TestCase):
    """The places a person may replace are the kit's places this file has words for: the kit can gain
    a place (the browser review of a transcript, a0.4.3) before a menu on it exists, and the store
    must neither offer it nor break on it."""

    def test_a_place_is_offered_when_the_kit_hands_it_out_and_this_file_names_it(self):
        offered = tuple(s for s in K.SURFACES if s in P.LABELS and s in P.DATA)
        self.assertEqual(P.SURFACES, offered)
        self.assertTrue(P.SURFACES, "the store offers no place at all")

    def test_no_label_or_data_line_is_left_for_a_place_the_kit_no_longer_has(self):
        self.assertEqual(sorted(set(P.LABELS) - set(K.SURFACES)), [])
        self.assertEqual(sorted(set(P.DATA) - set(K.SURFACES)), [])

    def test_a_place_with_a_label_has_its_data_line_too(self):
        self.assertEqual(sorted(set(P.LABELS) ^ set(P.DATA)), [])


class TheStore(Stored):
    def test_a_new_prompt_is_added_after_parsehs_unless_it_says_otherwise(self):
        p = P.save({"surface": "video-region", "name": "British spellings", "text": MINE})
        self.assertEqual((p["kind"], p["languages"], p["based_on"]), ("added", [], None))
        self.assertRegex(p["id"], r"^p[0-9a-f]{8}$")
        self.assertEqual(p["created"], p["updated"])
        self.assertEqual(P.find(p["id"]), p)
        self.assertEqual([x["id"] for x in P.all_of()], [p["id"]])

    def test_a_prompt_in_place_of_parsehs_records_the_prompt_and_the_version_it_began_from(self):
        for surface in P.SURFACES:
            with self.subTest(surface):
                begins = P.parseh(surface)
                p = P.save(mine(surface, kind="replace", text=begins["text"]))
                self.assertEqual(p["based_on"], {"surface": surface, "version": begins["version"],
                                                 "text": begins["text"]})
                self.assertRegex(begins["version"], r"^[0-9a-f]{8}$")
                P.delete(p["id"])

    def test_the_version_is_a_hash_of_the_words_and_not_of_the_release(self):
        with mock.patch.object(version, "VERSION", "a9.9.9"):
            self.assertEqual(P.parseh("video-region")["version"],
                             P.version_of(K.instructions("video-region")))
        self.assertNotEqual(P.version_of("a"), P.version_of("b"))
        self.assertEqual(P.parseh("video-region")["version"], P.parseh("book-region")["version"],
                         "the two regions have one template")

    def test_names_are_told_apart_per_place_ignoring_case_and_the_way_a_letter_is_spelt(self):
        P.save(mine("video-region", name="Café"))
        self.refused(mine("video-region", name="CAFÉ"), "you have a prompt called Café for this already")
        self.refused(mine("video-region", name="  café  "), "already")
        P.save(mine("book-region", name="Café"))               # another place: another list
        p = P.save(mine("video-region", name="Café 2"))
        self.assertEqual(P.save(dict(mine("video-region"), id=p["id"], name="Café 2", text="x"))["text"], "x",
                         "a prompt may keep its own name")
        self.refused(dict(mine("video-region"), id=p["id"], name="café"), "already")

    def test_a_name_is_a_few_words_on_one_line(self):
        for bad in ("", "   ", None, "x" * 61):
            with self.subTest(bad):
                self.refused(mine("ask", name=bad), "name is a few words on one line, at most 60")
        self.assertEqual(P.save(mine("ask", name="a\nb\tc"))["name"], "a b c")
        self.assertEqual(P.save(mine("ask", name="x" * 60))["name"], "x" * 60)

    def test_a_prompt_is_for_every_language_or_for_one_and_is_offered_only_there(self):
        everywhere = P.save(mine("video-region", name="all"))
        fa = P.save(mine("video-region", name="fa only", languages=["fa"]))
        it = P.save(mine("video-region", name="it only", languages="it"))
        self.assertEqual((fa["languages"], it["languages"]), (["fa"], ["it"]))
        names = lambda lang: [p["name"] for p in P.offered("video-region", lang)]
        self.assertEqual(names("fa"), ["all", "fa only"])
        self.assertEqual(names("it"), ["all", "it only"])
        self.assertEqual(names("ja"), ["all"])
        self.assertEqual(names(None), ["all", "fa only", "it only"], "no language asked: all of them")
        self.assertEqual(P.offered("book-region", "fa"), [], "and only for the place it is for")
        self.refused(mine("ask", languages=["fa", "it"]), "every language, or for one")
        self.refused(mine("ask", languages=["Persian!"]), "is not a language's code")
        self.assertEqual(everywhere["languages"], [])

    def test_a_prompt_stays_with_the_place_it_was_made_for(self):
        p = P.save(mine("video-region"))
        self.refused(dict(mine("book-region"), id=p["id"]), "stays with the one it was made for")
        self.assertEqual(P.find(p["id"])["surface"], "video-region")

    def test_what_a_prompt_may_be_is_said_in_words(self):
        self.refused(mine("the-moon"), "'the-moon' is not a place Parseh hands a prompt out from",
                     "a stretch of a video, glossed by an LLM", "Ask LLM, one sentence in the sources")
        self.refused(mine("ask", kind="both"), "added to Parseh's instructions or in place of them")
        self.refused(mine("ask", text=""), "no words in it")
        self.refused(mine("ask", text="  \n "), "no words in it")
        self.refused(mine("ask", text=5), "text is text")
        self.refused(mine("ask", text="x" * (P.TEXT_MAX + 1)), "at most")
        self.refused(mine("ask", text="a\x00b"), "control characters")
        self.refused("nothing", "a set of named fields")
        self.assertEqual(P.all_of(), [], "and none of it was kept")

    def test_a_placeholder_parseh_does_not_fill_is_refused_on_save_in_words_that_name_it(self):
        for surface in P.SURFACES:
            with self.subTest(surface):
                said = self.refused(mine(surface, text="Be brief. {{NOT_A_THING}} and {{ALSO_NOT}}"),
                                    "{{NOT_A_THING}}, {{ALSO_NOT}} are not something Parseh fills in",
                                    "It fills in: {{LANGUAGE}}")
                self.assertNotIn("bug", said)
                self.refused(mine(surface, text="{{language}}"), "{{language}} is not something Parseh fills in")
        self.assertEqual(P.all_of(), [])

    def test_a_name_another_place_fills_is_not_this_places(self):
        # ADDRESS is a stretch's, and the studio's prompt has no stretch
        P.save(mine("video-region", text="Say {{ADDRESS}} for each."))
        self.refused(mine("studio-doc", text="Say {{ADDRESS}} for each."), "{{ADDRESS}} is not something")
        self.refused(mine("ask", text="into {{TITLE}}"), "{{TITLE}} is not something")

    def test_every_name_the_kit_lists_for_a_place_is_taken_there(self):
        for surface in P.SURFACES:
            with self.subTest(surface):
                names = [n for n, _m in P.known_names(surface)]
                p = P.save(mine(surface, text=" ".join("{{%s}}" % n for n in names)))
                self.assertEqual(p["text"].count("{{"), len(names))
                P.delete(p["id"])

    def test_the_blocks_and_marks_the_kit_refuses_are_refused_on_save(self):
        for text, said in (("{{?nope}}x{{/nope}}", "{{?nope}} is a block this prompt does not know"),
                           ("{{?book}}never closed", "{{?book}} is opened and never closed"),
                           ("closed {{/book}}", "{{/book}} closes a block that was never opened"),
                           ("{{?contract}}mine{{/contract}}", "cannot carry the answer contract or the data"),
                           ("{{?data}}mine{{/data}}", "cannot carry the answer contract or the data"),
                           ("a {{ b }} c", "double brace"), ("{{", "double brace")):
            with self.subTest(text):
                self.refused(mine("video-region", text=text), said)
        # ...and a block the place's own template uses, and the kit's own kinds, are taken
        for text in ("{{?keep}}kept{{/keep}}", "{{?book}}b{{/book}} {{?video}}v{{/video}}",
                     "{{?regloss}}again{{/regloss}}"):
            with self.subTest(text):
                P.delete(P.save(mine("video-region", text=text))["id"])

    def test_a_language_a_prompt_is_for_is_the_language_it_is_checked_in(self):
        p = P.save(mine("video-region", languages=["ja"], text="Read {{LANGUAGE_NATIVE}} as it is."))
        self.assertEqual(p["languages"], ["ja"])

    def test_parsehs_own_prompt_is_not_in_the_store_and_nothing_here_can_touch_it(self):
        files = [K.TEMPLATES[s] for s in K.TEMPLATES] + [str(ROOT / "youtube" / "lib" / "tidy.py")]
        before = {f: Path(f).read_bytes() for f in files}
        text = {s: P.parseh(s)["text"] for s in P.SURFACES}
        p = P.save(mine("video-region", kind="replace", text=P.parseh("video-region")["text"] + "\nMine."))
        P.save(dict(mine("video-region", kind="added"), id=p["id"], text="Changed."))
        P.uptodate(P.save(mine("book-region", kind="replace", text="Mine."))["id"])
        P.delete(p["id"])
        for name in ("parseh", "video-region", "ask", "", "studio-doc", "p00000000"):
            with self.assertRaises(P.NotFound, msg=name):
                P.delete(name)
        with self.assertRaises(P.PromptsError):
            P.save(dict(mine("video-region"), id="parseh"))
        self.assertEqual({f: Path(f).read_bytes() for f in files}, before, "not a template moved")
        self.assertEqual({s: P.parseh(s)["text"] for s in P.SURFACES}, text)
        self.assertNotIn("parseh", json.loads(Path(P.STORE).read_text(encoding="utf-8")).get("prompts", [{}])[0].get("id", ""))

    def test_delete_takes_one_away_and_says_so_of_one_that_is_gone(self):
        a, b = P.save(mine("ask", name="a")), P.save(mine("ask", name="b"))
        P.delete(a["id"])
        self.assertEqual([p["name"] for p in P.all_of()], ["b"])
        with self.assertRaises(P.NotFound) as cm:
            P.delete(a["id"])
        self.assertIn("there is no prompt of yours with that id", str(cm.exception))
        self.assertEqual(b, P.find(b["id"]))

    def test_the_store_is_written_whole_and_leaves_no_scratch_file(self):
        P.save(mine("ask"))
        self.assertEqual(sorted(os.listdir(self.tmp / "config")), ["prompts.json"])
        doc = json.loads(Path(P.STORE).read_text(encoding="utf-8"))
        self.assertEqual(doc["format"], P.STORE_FORMAT)
        self.assertEqual(set(doc), {"format", "prompts", "moved"})

    def test_what_the_store_cannot_read_is_kept_as_it_came(self):
        # a hand-edited entry, one from a newer Parseh: never dropped because a rule changed
        odd = {"id": "pfuture01", "name": "from later", "surface": "video-region", "kind": "quoted",
               "text": "a kind this Parseh does not know"}
        P.save(mine("ask"))
        doc = json.loads(Path(P.STORE).read_text(encoding="utf-8"))
        doc["prompts"].append(odd)
        Path(P.STORE).write_text(json.dumps(doc), encoding="utf-8")
        self.assertEqual([p["name"] for p in P.all_of()], ["my rules"], "not offered")
        P.save(mine("ask", name="second"))
        after = json.loads(Path(P.STORE).read_text(encoding="utf-8"))["prompts"]
        self.assertIn(odd, after, "and still in the file after this Parseh wrote it")
        self.assertEqual(len(after), 3)

    def test_a_store_that_is_not_one_is_an_empty_store_and_the_next_save_makes_it_whole(self):
        for text in ("", "not json", "[1, 2]", '{"prompts": 5}'):
            with self.subTest(text):
                Path(P.STORE).parent.mkdir(parents=True, exist_ok=True)
                Path(P.STORE).write_text(text, encoding="utf-8")
                self.assertEqual(P.all_of(), [])
        P.save(mine("ask"))
        self.assertEqual(len(P.all_of()), 1)

    def test_two_entries_with_one_id_are_not_both_offered(self):
        p = P.save(mine("ask"))
        doc = json.loads(Path(P.STORE).read_text(encoding="utf-8"))
        doc["prompts"].append(dict(doc["prompts"][0], name="twin"))
        Path(P.STORE).write_text(json.dumps(doc), encoding="utf-8")
        self.assertEqual([x["name"] for x in P.all_of()], ["my rules"])
        self.assertEqual(P.find(p["id"])["name"], "my rules")

    def test_a_failing_disk_is_said_in_words_by_the_routes(self):
        with mock.patch.object(P, "_write", side_effect=PermissionError(13, "Permission denied")):
            code, out = P.api("save", mine("ask"))
        self.assertEqual(code, 500)
        self.assertIn("your prompts could not be kept", out["error"])
        self.assertIn("config/prompts.json", out["error"])


class ExportAndImport(Stored):
    def test_export_then_import_gives_the_same_prompt_for_every_place_and_kind(self):
        for surface in P.SURFACES:
            for kind in P.KINDS:
                with self.subTest((surface, kind)):
                    text = P.parseh(surface)["text"] + "\nMine." if kind == "replace" else MINE
                    was = P.save(mine(surface, kind=kind, text=text, languages=["fa"]))
                    data = P.export_bytes(was["id"])
                    self.assertEqual(json.loads(data)["format"], P.EXPORT_FORMAT)
                    P.delete(was["id"])
                    got, renamed = P.import_prompt(P.read_export(data))
                    self.assertIsNone(renamed)
                    keys = ("name", "surface", "kind", "text", "languages", "based_on")
                    self.assertEqual({k: got[k] for k in keys}, {k: was[k] for k in keys})
                    self.assertNotEqual(got["id"], was["id"], "an import is a prompt of its own")
                    P.delete(got["id"])

    def test_every_name_survives_the_file_and_the_file_is_utf_8(self):
        for name in NAMES:
            with self.subTest(name):
                was = P.save(mine("ask", name=name, text="السلام ✓ 日本語"))
                data = P.export_bytes(was["id"])
                self.assertIn("السلام ✓ 日本語".encode("utf-8"), data, "written as itself, not escaped")
                P.delete(was["id"])
                self.assertEqual(P.import_prompt(P.read_export(data))[0]["name"], name)

    def test_an_import_that_meets_a_name_is_renamed_and_never_written_over_one(self):
        was = P.save(mine("video-region", name="British spellings", text="Mine, first."))
        data = P.export_bytes(was["id"])
        second, asked = P.import_prompt(P.read_export(data))
        third, _ = P.import_prompt(P.read_export(data))
        self.assertEqual((second["name"], asked), ("British spellings (2)", "British spellings"))
        self.assertEqual(third["name"], "British spellings (3)")
        self.assertEqual(P.find(was["id"])["text"], "Mine, first.", "the one that was there is as it was")
        self.assertEqual(len(P.all_of()), 3)
        # another place has a list of its own: the same name is free there
        other = json.loads(data)
        other["prompt"]["surface"] = "book-region"
        got, asked = P.import_prompt(P.read_export(json.dumps(other)))
        self.assertEqual((got["name"], asked), ("British spellings", None))

    def test_a_name_at_its_longest_is_renamed_within_its_length(self):
        was = P.save(mine("ask", name="x" * 60))
        got, asked = P.import_prompt(P.read_export(P.export_bytes(was["id"])))
        self.assertEqual((len(got["name"]), got["name"].endswith(" (2)")), (60, True))
        self.assertEqual(asked, "x" * 60)

    def test_a_file_that_is_not_a_prompt_this_parseh_reads_is_refused_in_words(self):
        good = json.loads(P.export_bytes(P.save(mine("ask"))["id"]))
        cases = [
            ("not json at all", "that file is not a prompt exported by Parseh"),
            ("[1]", "that file is not a prompt this Parseh reads (it wants %s)" % P.EXPORT_FORMAT),
            (json.dumps(dict(good, format="parseh-latex-theme/1")), "it wants parseh-prompt/1"),
            (json.dumps(dict(good, format="parseh-prompt/2")), "exported by a newer Parseh (it says parseh-prompt/2)"),
            (json.dumps({k: v for k, v in good.items() if k != "prompt"}), "a set of named fields"),
            (json.dumps(dict(good, prompt=dict(good["prompt"], surface="the-moon"))), "is not a place Parseh hands a prompt out from"),
            (json.dumps(dict(good, prompt=dict(good["prompt"], kind="both"))), "in place of them"),
            (json.dumps(dict(good, prompt=dict(good["prompt"], text=""))), "no words in it"),
            (json.dumps(dict(good, prompt=dict(good["prompt"], name=""))), "name is a few words"),
            (json.dumps(dict(good, prompt=dict(good["prompt"], text="{{FROM_A_LATER_PARSEH}}"))),
             "{{FROM_A_LATER_PARSEH}} is not something Parseh fills in"),
        ]
        for data, said in cases:
            with self.subTest(said):
                with self.assertRaises(P.PromptsError) as cm:
                    P.read_export(data)
                self.assertIn(said, str(cm.exception))
        self.assertEqual(len(P.all_of()), 1, "and nothing of them was kept")
        with self.assertRaises(P.PromptsError):
            P.read_export(b"\xff\xfe not utf 8")

    def test_the_import_route_says_the_same_and_keeps_nothing_of_a_bad_file(self):
        code, out = P.api("import", {"data": "{}"})
        self.assertEqual((code, out["ok"]), (400, False))
        self.assertIn("not a prompt this Parseh reads", out["error"])
        self.assertEqual(P.all_of(), [])
        code, out = P.api("import", {})
        self.assertEqual((code, out["error"]), (400, "data is missing"))

    def test_the_file_is_offered_under_the_prompts_name(self):
        for name, want in (("British spellings", "British-spellings.parseh-prompt.json"),
                           ("الفبا", "الفبا.parseh-prompt.json"), ("///", "prompt.parseh-prompt.json")):
            self.assertEqual(P.export_name({"name": name}), want)


class KeepingUpWithParsehsOwn(Stored):
    """A prompt in place of Parseh's says when Parseh's own changed since, and what."""

    def setUp(self):
        super().setUp()
        self.template = self.tmp / "region-prompt.md"
        shutil.copy(K.TEMPLATES["video-region"], self.template)
        patcher = mock.patch.dict(K.TEMPLATES, {"video-region": str(self.template)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def change_parsehs_own(self):
        text = self.template.read_text(encoding="utf-8")
        self.template.write_text(text.replace("You receive **one JSON document**",
                                              "You receive **one JSON document**, always", 1)
                                 .replace("# Gloss part", "# Gloss part (edited)", 1), encoding="utf-8")

    def test_it_says_nothing_until_parsehs_own_changes_and_then_shows_what_changed(self):
        p = P.save(mine("video-region", kind="replace", text=P.parseh("video-region")["text"]))
        self.assertFalse(P.public(p)["stale"])
        v = P.verdict(p)
        self.assertEqual((v["known"], v["stale"], v["diff"]), (True, False, []))
        self.change_parsehs_own()
        was, now = p["based_on"]["version"], P.parseh("video-region")["version"]
        self.assertNotEqual(was, now)
        p = P.find(p["id"])
        self.assertTrue(P.public(p)["stale"])
        v = P.verdict(p)
        self.assertEqual((v["known"], v["stale"], v["was"], v["now"]), (True, True, was, now))
        edits = [d for d in v["diff"] if d["op"] in "+-"]
        self.assertTrue(any(d["op"] == "-" and d["text"].startswith("# Gloss part") for d in edits), edits)
        self.assertTrue(any(d["op"] == "+" and d["text"].startswith("# Gloss part") and "(edited)" in d["text"]
                            for d in edits), edits)
        self.assertLess(len(edits), 6, "a line diff of what changed, not the whole prompt")

    def test_the_list_and_the_route_say_it_too_and_saying_mine_stands_ends_it(self):
        p = P.save(mine("video-region", kind="replace", text="Mine only."))
        self.change_parsehs_own()
        code, out = P.api("list", {"surface": "video-region"})
        self.assertEqual([x["stale"] for x in out["prompts"]], [True])
        code, out = P.api("get", {"id": p["id"]})
        self.assertEqual((out["prompt"]["stale"], out["verdict"]["stale"]), (True, True))
        self.assertTrue(out["verdict"]["diff"])
        code, out = P.api("uptodate", {"id": p["id"]})
        self.assertEqual((code, out["prompt"]["stale"], out["verdict"]["stale"]), (200, False, False))
        self.assertEqual(out["prompt"]["text"], "Mine only.", "the words of the person did not move")
        self.assertEqual(P.find(p["id"])["based_on"]["version"], P.parseh("video-region")["version"])

    def test_a_prompt_added_after_parsehs_is_never_out_of_date(self):
        p = P.save(mine("video-region"))
        self.change_parsehs_own()
        self.assertFalse(P.public(p)["stale"])
        self.assertIsNone(P.verdict(p))
        code, out = P.api("uptodate", {"id": p["id"]})
        self.assertEqual(code, 400)
        self.assertIn("only a prompt in place of Parseh's begins from one of Parseh's", out["error"])

    def test_the_studios_old_prompt_has_no_record_and_so_says_nothing(self):
        (self.tmp / "_prompt.md").write_text("My studio rules.", encoding="utf-8")
        made = P.move_studio_file(self.tmp / "_prompt.md")
        self.assertIsNone(made["based_on"])
        v = P.verdict(made)
        self.assertEqual((v["known"], v["stale"], v["diff"]), (False, False, []))
        self.assertFalse(P.public(made)["stale"])

    def test_the_prompt_the_editor_starts_a_new_one_from_is_parsehs_raw_text(self):
        for surface in P.SURFACES:
            with self.subTest(surface):
                code, out = P.api("parseh", {"surface": surface})
                self.assertEqual(code, 200)
                self.assertEqual(out["text"], P.parseh(surface)["text"])
                self.assertEqual(out["version"], P.version_of(out["text"]))
        code, out = P.api("parseh", {"surface": "video-region"})
        self.assertEqual(out["text"], K.instructions("video-region", template=self.template.read_text(encoding="utf-8")),
                         "the kit's raw instructions, placeholders and blocks and all")
        self.assertIn("{{?", out["text"])
        self.assertNotIn("What you answer", out["text"], "the contract is not part of what a person edits")

    def test_diff(self):
        a = "\n".join("line %d" % i for i in range(30))
        b = a.replace("line 15", "line fifteen").replace("line 29", "the end")
        got = P.diff(a, b)
        self.assertEqual([d for d in got if d["op"] in "+-"],
                         [{"op": "-", "text": "line 15"}, {"op": "+", "text": "line fifteen"},
                          {"op": "-", "text": "line 29"}, {"op": "+", "text": "the end"}])
        skips = [d for d in got if d["op"] == "…"]
        self.assertEqual([s["skipped"] for s in skips], [13, 9], "an unchanged stretch is counted, not printed")
        self.assertEqual([d["text"] for d in got if d["op"] == " "],
                         ["line 13", "line 14", "line 16", "line 17", "line 27", "line 28"],
                         "two lines of context round each change, and none where the text begins or ends")
        self.assertEqual(P.diff("same", "same"), [{"op": " ", "text": "same"}])
        self.assertEqual(P.diff("a", "b"), [{"op": "-", "text": "a"}, {"op": "+", "text": "b"}])


class ResolvingAnId(Stored):
    def test_no_id_is_parsehs_own_and_true_is_too(self):
        for asked in (None, "", True):
            self.assertIsNone(P.resolve("video-region", asked, "fa"))
            self.assertIsNone(P.instructions_for("video-region", asked, "fa"))

    def test_an_id_is_never_a_name_and_one_that_is_gone_is_a_404_in_words(self):
        P.save(mine("video-region", name="British spellings"))
        with self.assertRaises(P.NotFound) as cm:
            P.resolve("video-region", "British spellings", "fa")
        self.assertEqual(cm.exception.status, 404)
        self.assertIn("there is no prompt of yours with that id", str(cm.exception))
        for bad in (5, ["x"], False, {"a": 1}):
            with self.assertRaises(P.PromptsError, msg=repr(bad)) as cm:
                P.resolve("video-region", bad, "fa")
            self.assertIn("prompt is the id of one of your prompts", str(cm.exception))

    def test_a_prompt_for_another_place_or_another_language_is_refused_in_words(self):
        book = P.save(mine("book-region", name="for books"))
        only = P.save(mine("video-region", name="Persian only", languages=["fa"]))
        with self.assertRaises(P.PromptsError) as cm:
            P.resolve("video-region", book["id"], "fa")
        self.assertIn("for books is a prompt for a stretch of a book, glossed by an LLM, and this asks "
                      "for a stretch of a video, glossed by an LLM", str(cm.exception))
        with self.assertRaises(P.PromptsError) as cm:
            P.resolve("video-region", only["id"], "it")
        self.assertIn("Persian only is a prompt for Persian (fa) only, and this is Italian (it)", str(cm.exception))
        self.assertEqual(P.resolve("video-region", only["id"], "fa").name, "Persian only")
        self.assertEqual(P.resolve("video-region", only["id"], languages.get("fa")).id, only["id"])
        self.assertEqual(P.resolve("video-region", only["id"], None).id, only["id"], "no language known: not judged")

    def test_what_the_kit_is_handed_is_parsehs_then_the_persons_or_the_persons_alone(self):
        for surface in P.SURFACES:
            with self.subTest(surface):
                a = P.save(mine(surface, name="after", kind="added", text="After."))
                r = P.save(mine(surface, name="instead", kind="replace", text="Instead."))
                ours = P.parseh(surface)["text"] if surface in ("ask", "book-new") else K.instructions(surface)
                got = P.resolve(surface, a["id"], "fa")
                self.assertEqual(got.instructions, ours + "\n\nAfter.")
                self.assertEqual((got.name, got.kind, got.text), ("after", "added", "After."))
                got = P.resolve(surface, r["id"], "fa")
                self.assertEqual(got.instructions, "Instead.")
                self.assertEqual(P.instructions_for(surface, r["id"]), "Instead.")
                P.delete(a["id"])
                P.delete(r["id"])

    def test_a_book_from_scratch_and_ask_llm_lock_nothing_and_the_others_lock_the_contract(self):
        for surface in P.SURFACES:
            info = P.parseh(surface)
            self.assertEqual(info["locked"], surface in K.READS_BACK, surface)
            self.assertEqual(bool(info["contract"]), surface in K.READS_BACK, surface)
            self.assertEqual(bool(info["data"]), surface != "book-new", surface)
            self.assertIn(surface, P.LABELS)
        whole = P.parseh("book-new")["text"]
        self.assertIn("### The per-paragraph JSON", whole, "the whole prompt, the JSON's part too")
        # the marks of the parts are gone; the blocks of the short vowels stay as written, which the kit settles for each book
        for mark in ("{{?contract}}", "{{?data}}"):
            self.assertNotIn(mark, whole)

    def test_the_blocks_a_text_uses_are_told_apart_from_the_marks_of_the_parts(self):
        self.assertEqual(P.markers("{{?vocab}}a{{/vocab}} {{?gloss}}{{?vocab}}b{{/vocab}}{{/gloss}} {{LANGUAGE}}"),
                         ["gloss", "vocab"])
        self.assertEqual(P.markers("No boxes here, {{LANGUAGE}}."), [])
        self.assertEqual(P.markers("{{?contract}}x{{/contract}}{{?data}}y{{/data}}"), [])

    def test_the_editor_is_told_what_stays_parsehs_under_the_text(self):
        info = P.parseh("video-region")
        self.assertEqual(info["contract"], K.contract("video-region"))
        self.assertIn("## What you answer", info["contract"])
        self.assertEqual(info["data"], "the stretch of the video, as one JSON document")
        names = [n for n, _m in info["placeholders"]]
        self.assertEqual(names, [n for n, _m in K.placeholders("video-region")])
        self.assertTrue(all(m and "\n" not in m for _n, m in info["placeholders"]))
        # and the blocks its text may use: the kit's kinds and the ones its template uses, never a mark of a part
        self.assertTrue({"video", "book", "keep", "regloss", "perfield"} <= set(info["blocks"]), info["blocks"])
        self.assertFalse({"note", "contract", "data"} & set(info["blocks"]), info["blocks"])
        self.assertEqual(P.parseh("ask")["blocks"], ["book", "new", "region", "studio", "video"])

    def test_ask_llms_words_are_the_javascripts(self):
        # the kit has no template for Ask LLM (it is built in the page, offline too), so its
        # words are held here for a person's copy: each fixed piece of them is in lib/llm.js
        js = (ROOT / "lib" / "llm.js").read_text(encoding="utf-8")
        for line in P.ASK.split("\n"):
            for piece in re.split(r"\{\{[A-Z_]+\}\}", line):
                self.assertIn(piece.strip(), js, piece)
        self.assertIn("{{LANGUAGE}}", P.ASK)
        self.assertEqual([n for n, _m in P.known_names("ask")][-2:], ["GLOSS_LANGUAGE", "GLOSS_CODE"])
        with self.assertRaises(K.PromptError):
            K.parts("ask")                      # A1's own test pins it: the kit does not know it




class Handler(object):
    """What the studio's route functions ask of their handler, and no more."""

    def __init__(self, body=None, query=None):
        self.body, self.query, self.answer, self.status, self.raw = body or {}, query or {}, None, 200, None

    def _json_body(self):
        return self.body

    def send_json(self, answer, code=200):
        self.answer, self.status = answer, code

    def send_bytes(self, data, ctype, code=200, extra=None):
        self.raw, self.status, self.answer = data, code, (ctype, extra or {})


def ytpages_handler(body):
    """What the add page's doors ask of serve.py's handler, and no more."""
    class H(object):
        query = {}

        def __init__(self):
            self._raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.status = self.sent = None

        def send_json(self, obj, code=200):
            self.status, self.sent = code, obj
    return H()


class TheStudiosOldPrompt(Stored):
    """library/_prompt.md, which the studio kept its one custom prompt in until a0.4.2."""

    def setUp(self):
        super().setUp()
        self.library = self.tmp / "library"
        self.library.mkdir()
        patcher = mock.patch.object(store, "LIB", self.library)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.file = self.library / "_prompt.md"

    def kept(self):
        return Path(P.STORE).read_bytes() if os.path.exists(P.STORE) else None

    def test_it_moves_into_the_store_once_and_only_once(self):
        self.file.write_text("My studio rules.\r\nBe brief.", encoding="utf-8")
        made = store.move_prompt()
        self.assertEqual((made["id"], made["name"], made["surface"], made["kind"], made["languages"]),
                         (P.STUDIO_ID, "my studio prompt (from before a0.4.2)", "studio-doc", "replace", []))
        self.assertEqual(made["text"], "My studio rules.\nBe brief.")
        self.assertFalse(self.file.exists(), "the file is removed from the library after the move")
        self.assertEqual([p["name"] for p in P.all_of()], ["my studio prompt (from before a0.4.2)"])
        self.assertTrue(P.moved(P.STUDIO_MARK))
        after_the_move = self.kept()
        # ...and the next start does nothing at all
        self.assertIsNone(store.move_prompt())
        self.assertEqual(self.kept(), after_the_move)
        # an older Parseh, run over this tree, writes the file again: the marker is the store's,
        # not the file's absence, so it is never a second prompt
        self.file.write_text("Written by an older Parseh.", encoding="utf-8")
        self.assertIsNone(store.move_prompt())
        self.assertIsNone(store.move_prompt())
        self.assertTrue(self.file.exists(), "and it is left where it is, for that Parseh")
        self.assertEqual(len(P.all_of()), 1)
        self.assertEqual(P.all_of()[0]["text"], "My studio rules.\nBe brief.")
        self.assertEqual(self.kept(), after_the_move)
        self.assertEqual(store.get_prompt(), {"text": "My studio rules.\nBe brief.", "custom": True},
                         "a leftover file is nobody's prompt once the move was made")

    def test_where_there_is_nothing_to_move_nothing_is_written(self):
        self.assertIsNone(store.move_prompt())
        self.assertFalse(os.path.exists(P.STORE), "a store nobody needs is not made")
        self.assertFalse(P.moved(P.STUDIO_MARK))
        self.assertEqual(store.get_prompt(), {"text": store.default_prompt(), "custom": False})

    def test_an_empty_file_is_taken_away_and_makes_no_prompt(self):
        self.file.write_text(" \n\t\n", encoding="utf-8")
        self.assertIsNone(store.move_prompt())
        self.assertFalse(self.file.exists())
        self.assertEqual((P.all_of(), P.moved(P.STUDIO_MARK)), ([], True))

    def test_until_it_moves_the_old_routes_read_the_file_as_they_always_did(self):
        self.file.write_text("Before the move.", encoding="utf-8")
        self.assertEqual(store.get_prompt(), {"text": "Before the move.", "custom": True})
        self.assertFalse(os.path.exists(P.STORE), "reading is not moving")

    def test_a_store_that_cannot_be_written_leaves_the_file_for_the_next_start(self):
        self.file.write_text("Mine.", encoding="utf-8")
        with mock.patch.object(P, "_write", side_effect=PermissionError(13, "Permission denied")):
            with self.assertRaises(PermissionError):
                store.move_prompt()
        self.assertTrue(self.file.exists())
        self.assertFalse(P.moved(P.STUDIO_MARK))
        self.assertEqual(store.get_prompt()["text"], "Mine.", "and the studio still has it")
        self.assertEqual(store.move_prompt()["text"], "Mine.", "and the next start moves it")

    def test_a_prompt_by_that_name_already_is_not_written_over(self):
        P.save(mine("studio-doc", name="my studio prompt (from before a0.4.2)", text="Somebody else's."))
        self.file.write_text("Mine.", encoding="utf-8")
        made = store.move_prompt()
        self.assertEqual(made["name"], "my studio prompt (from before a0.4.2) (2)")
        self.assertEqual(sorted(p["text"] for p in P.all_of()), ["Mine.", "Somebody else's."])
        self.assertEqual(store.get_prompt()["text"], "Mine.")

    def test_the_start_of_the_studio_does_it_and_says_so(self):
        self.file.write_text("Mine.", encoding="utf-8")
        said = io.StringIO()
        with mock.patch.object(store, "follow_renames"), mock.patch.object(store, "migrate_once", return_value=None), \
                mock.patch("sys.stdout", said):
            studio_server.migrate_library()
            studio_server.migrate_library()                     # a second start
        self.assertEqual([p["text"] for p in P.all_of()], ["Mine."])
        self.assertEqual(said.getvalue().count("is now one of your prompts"), 1)
        self.assertIn("my studio prompt (from before a0.4.2)", said.getvalue())

    def test_a_start_that_cannot_move_it_says_so_and_still_starts(self):
        self.file.write_text("Mine.", encoding="utf-8")
        said = io.StringIO()
        with mock.patch.object(store, "follow_renames"), mock.patch.object(store, "migrate_once", return_value=None), \
                mock.patch.object(P, "_write", side_effect=PermissionError(13, "Permission denied")), \
                mock.patch("sys.stdout", said):
            studio_server.migrate_library()
        self.assertIn("could not be moved into your prompts", said.getvalue())

    def test_the_old_routes_go_on_working_on_the_prompt_that_was_moved(self):
        self.file.write_text("My studio rules.", encoding="utf-8")
        store.move_prompt()
        # what the menu chose is what the page is made from: this prompt is one of the person's own now, chosen
        # by its id like the others (tests/test_prompts_menu.py), and the route says so
        h = Handler(query={"target": ["fa"], "prompt": [P.STUDIO_ID]})
        studio_server.api_prompt_get(h)
        self.assertEqual((h.answer["custom"]["name"], h.answer["text"]), (P.STUDIO_NAME, "My studio rules."))
        self.assertTrue(h.answer["prompt"].startswith(K.version_line("studio-doc", "fa", None, None, P.STUDIO_NAME)))
        studio_server.api_prompt_put(Handler({"text": "Changed."}))
        self.assertEqual([p["text"] for p in P.all_of()], ["Changed."], "the one prompt, changed in the store")
        self.assertEqual(P.all_of()[0]["id"], P.STUDIO_ID)
        h = Handler(query={"target": ["fa"], "prompt": [P.STUDIO_ID]})
        studio_server.api_prompt_get(h)
        self.assertEqual((h.answer["custom"]["name"], h.answer["text"]), (P.STUDIO_NAME, "Changed."))
        studio_server.api_prompt_delete(h)
        self.assertFalse(h.answer["custom"])
        self.assertEqual(P.all_of(), [], "reset is the old route's word for taking it away")
        self.assertFalse(self.file.exists(), "and the file did not come back")

    def test_the_old_save_route_makes_the_prompt_where_there_was_none_and_refuses_an_empty_one_in_words(self):
        studio_server.api_prompt_put(Handler({"text": "Fresh."}))
        self.assertEqual([(p["name"], p["kind"], p["text"]) for p in P.all_of()],
                         [("my studio prompt (from before a0.4.2)", "replace", "Fresh.")])
        self.assertFalse(self.file.exists(), "the file is not written any more")
        with self.assertRaises(store.StoreError) as cm:
            studio_server.api_prompt_put(Handler({"text": "  "}))
        self.assertIn("no words in it", str(cm.exception))
        self.assertEqual([p["text"] for p in P.all_of()], ["Fresh."])

    def test_saving_over_a_file_the_move_has_not_reached_moves_it_first(self):
        self.file.write_text("Old.", encoding="utf-8")
        studio_server.api_prompt_put(Handler({"text": "New."}))
        self.assertFalse(self.file.exists())
        self.assertEqual([p["text"] for p in P.all_of()], ["New."])
        self.assertTrue(P.moved(P.STUDIO_MARK))


class TheStudiosOwnRoutes(Stored):
    """The routes the studio run alone has for the prompts (markdown/app/server.py)."""

    def route(self, method, path):
        for m, pattern, fn in studio_server.ROUTES:
            if m == method and re.match(pattern, path):
                return fn, re.match(pattern, path).groups()
        self.fail("the studio has no route %s %s" % (method, path))

    def call(self, method, path, body=None, query=None):
        fn, args = self.route(method, path)
        h = Handler(body, query)
        fn(h, *args)
        return h

    def test_every_route_of_the_toolbox_is_the_studios_too(self):
        import settingspage
        theirs = {r.rsplit("/", 1)[1] for r in settingspage.ROUTES if r.startswith("/settings/api/prompts/")}
        for what in sorted(theirs - {"export"}):
            self.assertEqual(self.route("POST", "/api/prompts/" + what)[1], (what,), what)
        self.route("GET", "/api/prompts/export")
        with self.assertRaises(AssertionError):
            self.route("POST", "/api/prompts/nothing")

    def test_they_are_the_one_module_answering_for_both(self):
        h = self.call("POST", "/api/prompts/save", mine("video-region", name="one"))
        self.assertEqual((h.status, h.answer["ok"]), (200, True))
        pid = h.answer["prompt"]["id"]
        h = self.call("POST", "/api/prompts/list", {"surface": "video-region", "lang": "fa"})
        self.assertEqual([p["id"] for p in h.answer["prompts"]], [pid])
        self.assertEqual(P.api("list", {"surface": "video-region", "lang": "fa"})[1], h.answer)
        h = self.call("GET", "/api/prompts/export", query={"id": [pid]})
        ctype, extra = h.answer
        self.assertEqual((h.status, ctype), (200, "application/json; charset=utf-8"))
        self.assertIn("filename*=UTF-8''one.parseh-prompt.json", extra["Content-Disposition"])
        self.assertEqual(json.loads(h.raw)["prompt"]["name"], "one")
        h = self.call("GET", "/api/prompts/export", query={"id": ["pgone0000"]})
        self.assertEqual((h.status, h.answer["ok"]), (404, False))
        h = self.call("POST", "/api/prompts/delete", {"id": pid})
        self.assertEqual((h.status, P.all_of()), (200, []))
        h = self.call("POST", "/api/prompts/delete", {"id": pid})
        self.assertEqual(h.status, 404)


class AnAnswerLandsAsOneToParsehsOwn(unittest.TestCase):
    """For every place Parseh reads an answer back: the answer contract and the data
    that follow a person's text are Parseh's, word for word, so an answer to a
    prompt of yours lands exactly as one to Parseh's own (brief 10.1, W5)."""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.td = td.name
        self.store = Path(td.name) / "config" / "prompts.json"
        patcher = mock.patch.object(P, "STORE", str(self.store))
        patcher.start()
        self.addCleanup(patcher.stop)
        os.makedirs(os.path.join(self.td, "shelves"))

    def kinds(self, surface, text=MINE):
        """One prompt of yours of each kind, for this place -> [(kind, id)]."""
        return [(kind, P.save(mine(surface, name="my " + kind, kind=kind,
                                   text=P.parseh(surface)["text"] + "\n" + text if kind == "replace" else text))["id"])
                for kind in P.KINDS]

    def held_the_same(self, own, made, kind, text=MINE):
        """`made` is `own` with the person's text: their words where Parseh's instructions
        were, and everything after them Parseh's own, word for word."""
        self.assertEqual(made.contract, own.contract, "the answer contract is Parseh's")
        self.assertEqual(made.data, own.data, "and the data")
        self.assertTrue(made.contract)
        self.assertIn(text, made.instructions)
        if kind == "added":
            self.assertTrue(made.instructions.startswith(own.instructions), "after Parseh's instructions")
            self.assertTrue(made.instructions.endswith("\n\n" + text))
        else:
            self.assertNotEqual(made.instructions, own.instructions, "in place of them")
        order = [made.text.find(x) for x in (made.instructions, made.contract) if x]
        self.assertEqual(order, sorted(order), "and in the kit's order")

    def test_a_stretch_of_a_book_or_a_video_in_every_language(self):
        for surface, fixtures, thing, door in (("book-region", TG.BOOKS, TG.Book, "book"),
                                               ("video-region", TG.VIDEOS, TG.Video, "video")):
            yours = self.kinds(surface)         # for every language: one prompt of each kind serves them all
            for fx in fixtures:
                with self.subTest(os.path.relpath(os.path.dirname(fx), str(FIX))):
                    self.stretch(surface, thing(self, fx), door, yours)

    def stretch(self, surface, x, door, yours):
        units = (lambda: GR._book_units(x.d, x.first, x.last)[:2]) if door == "book" else \
                (lambda: GR._video_units(x.d, x.frm, x.to)[:2])
        reports, mode = [], GR._mode(False, False)
        for kind, pid in [(None, None)] + yours:
            x.delete()
            r = x.prompt(prompt=pid)
            ctx, us = units()
            own = GR.assembled(ctx, us, mode)[0]
            if pid:
                chosen = P.resolve(surface, pid, ctx["L"])
                made = GR.assembled(ctx, us, mode, chosen.instructions, chosen.name)[0]
                self.held_the_same(own, made, kind)
                self.assertEqual(r["prompt"], made.text)
                self.assertEqual(r["prompt"].split("\n")[0],
                                 K.version_line(surface, ctx["L"], ctx["G"], None, "my " + kind))
                self.assertTrue(r["prompt"].split("\n")[0].endswith(" · custom: my " + kind))
                self.assertEqual(r["custom"], {"id": pid, "name": "my " + kind, "kind": kind})
            else:
                self.assertNotIn("custom", r)
                self.assertNotIn("custom:", r["prompt"].split("\n")[0])
                self.assertEqual(r["prompt"], own.text)
            doc = TG.data_of(r["prompt"])
            if door == "book":
                (u, j, c), = [t for t in TG.todos(doc, "sentences") if t[2]["fa"] == x.recs()[x.k]["fa"]]
            else:
                u, j, c = x.todo(doc)
            c.pop("todo")
            c.update(x.old)
            a = x.apply(doc)
            self.assertEqual((a["filled"], a["dropped"], a["kept"]), (1, [], []), a)
            self.assertEqual(TG.snap(x.d), x.before, "the %s is itself, byte for byte" % door)
            reports.append(a)
        self.assertEqual(reports[1], reports[0], "an answer to a prompt added to Parseh's lands as one to Parseh's")
        self.assertEqual(reports[2], reports[0], "and to one in place of it")

    def every_video(self, check):
        """check(dir, meta) for each language's fixture video, a subtest each."""
        for vj in TG.VIDEOS:
            with self.subTest(os.path.relpath(os.path.dirname(vj), str(FIX))):
                with open(vj, encoding="utf-8") as f:
                    check(os.path.dirname(vj), json.load(f))

    def test_a_video_from_its_transcript_the_add_pages_check_takes_the_same_answer_in_every_language(self):
        self.videos = os.path.join(self.td, "videos")
        for name, value in (("VIDEOS", self.videos), ("oembed", lambda vid: {})):
            patcher = mock.patch.object(ytpages, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        yours = self.kinds("video-new")
        self.every_video(lambda d, meta: self.a_video_from_its_transcript(d, meta, yours))

    def a_video_from_its_transcript(self, d, meta, yours):
        vid, code, gloss = os.path.basename(d), meta["language"], meta.get("gloss") or "en"
        with open(os.path.join(d, "parts", "01.json"), encoding="utf-8") as f:
            parts = json.load(f)
        answer = "```json\n%s\n```" % json.dumps(
            {"video": {"level": "beginner"},
             "captions": [{"i": i, "start": p["start"], "chunks": p["chunks"]} for i, p in enumerate(parts)]},
            ensure_ascii=False)
        with open(os.path.join(d, "transcript.txt"), encoding="utf-8") as f:
            transcript = f.read()
        L, G = languages.get(code), languages.gloss(gloss)
        caps = ytpages.parse_transcript_text(ytpages.as_transcript(transcript), L)
        # A FRESH SHELF FOR EVERY ROAD: what an answer writes there is compared between the three
        self.clean_shelf()
        own = ytpages.assembled_full(vid, {}, caps, None, L, G)
        body = {"url": vid, "lang": code, "gloss": gloss, "transcript": transcript}
        wrote = []
        for kind, pid in [(None, None)] + yours:
            h = ytpages_handler(dict(body, prompt=pid))
            ytpages.api_prepare(h)
            self.assertEqual(h.status, 200, h.sent)
            if pid:
                chosen = P.resolve("video-new", pid, L)
                made = ytpages.assembled_full(vid, {}, caps, None, L, G, chosen.instructions, chosen.name)
                self.held_the_same(own, made, kind)
                self.assertEqual(h.sent["prompt"], made.text)
                self.assertEqual(h.sent["prompt"].split("\n")[0],
                                 K.version_line("video-new", L, G, None, "my " + kind))
                self.assertEqual(h.sent["custom"], {"id": pid, "name": "my " + kind, "kind": kind})
            else:
                self.assertEqual(h.sent["prompt"], own.text)
                self.assertIsNone(h.sent["custom"])
            h = ytpages_handler(dict(body, answer=answer))
            ytpages.api_add(h)
            self.assertEqual((h.status, h.sent.get("ok")), (200, True), h.sent)
            wrote.append(TG.snap(self.videos))
            self.clean_shelf()
        self.assertEqual(wrote[1], wrote[0])
        self.assertEqual(wrote[2], wrote[0], "the video the answer makes does not depend on who asked")

    def clean_shelf(self):
        shutil.rmtree(self.videos, ignore_errors=True)
        os.makedirs(self.videos)

    def test_the_tidied_transcript_goes_back_into_the_box_by_the_same_door_in_every_language(self):
        yours = self.kinds("transcript-tidy")
        self.every_video(lambda d, meta: self.a_tidied_transcript(d, meta, yours))

    def a_tidied_transcript(self, d, meta, yours):
        code = meta["language"]
        L = languages.get(code)
        with open(os.path.join(d, "transcript.txt"), encoding="utf-8") as f:
            transcript = f.read()
        caps = ytpages.parse_transcript_text(ytpages.as_transcript(transcript), L)
        own = tidier.assembled(caps, code)
        tidy_answer = CA.transcript_text([dict(c, text=c["text"] + ".") for c in caps if not c.get("plain")])
        back = []
        for kind, pid in [(None, None)] + yours:
            h = ytpages_handler({"transcript": transcript, "lang": code, "prompt": pid or True})
            ytpages.api_transcript(h)
            self.assertEqual(h.status, 200, h.sent)
            if pid:
                chosen = P.resolve("transcript-tidy", pid, L)
                made = tidier.assembled(caps, code, chosen.instructions, chosen.name)
                self.held_the_same(own, made, kind)
                self.assertEqual(h.sent["prompt"], made.text)
                self.assertEqual(h.sent["prompt"].split("\n")[0],
                                 K.version_line("transcript-tidy", L, None, None, "my " + kind))
                self.assertEqual(h.sent["custom"], {"id": pid, "name": "my " + kind, "kind": kind})
            else:
                self.assertEqual((h.sent["prompt"], "custom" in h.sent), (own.text, False))
            h = ytpages_handler({"transcript": tidy_answer, "lang": code})
            ytpages.api_transcript(h)
            self.assertEqual(h.status, 200, h.sent)
            back.append(h.sent["captions"])
        self.assertEqual(back[1], back[0])
        self.assertEqual(back[2], back[0])

    def test_the_studios_two_take_the_answer_by_the_contract_the_kit_locks(self):
        answer = "Here it is:\n```markdown\n---\ntitle: T\ntarget: fa\n---\n\n## سلام\n```\nAnything else?"
        for surface in ("studio-doc", "studio-exercises"):
            with self.subTest(surface):
                flags = P._flags(surface)
                own = K.assemble(surface, "fa", flags=flags)
                for kind, pid in self.kinds(surface):
                    chosen = P.resolve(surface, pid, "fa")
                    made = K.assemble(surface, "fa", flags=flags, instructions=chosen.instructions,
                                      custom=chosen.name)
                    self.held_the_same(own, made, kind)
                    self.assertTrue(made.text.split("\n")[0].endswith(" · custom: my " + kind))
        self.assertEqual(store.extract_markdown(answer), "---\ntitle: T\ntarget: fa\n---\n\n## سلام\n",
                         "the studio's door reads the document out of the fence, whoever asked")

    def test_ask_and_a_book_from_scratch_are_wholly_the_persons_when_they_say_so(self):
        for surface in ("ask", "book-new"):
            with self.subTest(surface):
                (_a, added), (_r, replaced) = self.kinds(surface)
                whole = P.parseh(surface)["text"]
                self.assertEqual(P.instructions_for(surface, replaced), whole + "\n" + MINE)
                self.assertEqual(P.instructions_for(surface, added), whole + "\n\n" + MINE)
                self.assertFalse(P.parseh(surface)["locked"])


class TheRoutes(unittest.TestCase):
    """The real server: Settings' page and routes, the studio's copy of them, a device
    let in over the Wi-Fi, a request from another site, and `prompt=<id>` on the doors
    that hand a prompt out."""

    @classmethod
    def setUpClass(cls):
        import serve
        cls.serve = serve
        cls._td = tempfile.TemporaryDirectory()
        tmp = cls.tmp = Path(cls._td.name)
        root = tmp / "root"
        shutil.copytree(FIX / "books" / "persian" / "mini-fa", root / "books" / "persian" / "mini-fa",
                        ignore=shutil.ignore_patterns("reader", "*.pdf", "*.aux", "*.log", "*.toc", "*.out"))
        shutil.copytree(PERSIAN_VIDEO, root / "youtube" / "videos" / "persian" / "fA6bK2mQ8sT")
        cls.patches = [
            mock.patch.object(serve.Handler, "log_request", lambda *a, **k: None),
            mock.patch.object(network, "STORE", str(tmp / "config" / "network.json")),
            mock.patch.object(P, "STORE", str(tmp / "config" / "prompts.json")),
            mock.patch.object(store, "LIB", tmp / "library"),
            mock.patch.object(serve, "ROOT", str(root)),
            mock.patch.object(serve._AtRoot, "directory", str(root)),
            mock.patch.object(ytpages, "VIDEOS", str(root / "youtube" / "videos")),
            mock.patch.object(ytpages, "oembed", lambda vid: {}),
        ]
        for p in cls.patches:
            p.start()
        network._CACHE.update({"key": None, "doc": None})
        cls.srv = serve.Server(("127.0.0.1", 0), serve.Handler, None)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        for p in reversed(cls.patches):
            p.stop()
        network._CACHE.update({"key": None, "doc": None})
        cls._td.cleanup()

    def setUp(self):
        if os.path.exists(P.STORE):
            os.remove(P.STORE)

    def ask(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=60)
        data = None if body is None else json.dumps(body).encode("utf-8")
        sent = dict({"Content-Type": "application/json"} if data is not None else {}, **(headers or {}))
        c.request(method, path, body=data, headers=sent)
        r = c.getresponse()
        raw = r.read()
        c.close()
        try:
            got = json.loads(raw.decode("utf-8"))
        except ValueError:
            got = raw.decode("utf-8", "replace")
        return r.status, got, r

    def as_phone(self):
        return [mock.patch.object(network, "where", lambda ip, doc=None: network.LAN),
                mock.patch.object(network, "may_connect", lambda ip, doc=None: True),
                mock.patch.object(network, "let_in", lambda *a, **k: True)]

    def make(self, **more):
        status, got, _ = self.ask("POST", "/settings/api/prompts/save", mine("video-region", **more))
        self.assertEqual((status, got.get("ok")), (200, True), got)
        return got["prompt"]

    def test_the_store_the_routes_write_is_this_tests_and_not_the_computers(self):
        self.assertTrue(P.STORE.startswith(str(self.tmp)), P.STORE)
        self.make()
        self.assertTrue(os.path.exists(P.STORE))

    def test_the_page_is_a_door_of_settings_open_from_the_computer_and_a_phone(self):
        for who in ("the computer", "a phone let in over the Wi-Fi"):
            patches = self.as_phone() if "phone" in who else []
            for p in patches:
                p.start()
            try:
                with self.subTest(who):
                    self.make(name="British spellings " + who[:3])
                    status, page, r = self.ask("GET", "/settings/prompts/")
                    self.assertEqual(status, 200)
                    self.assertIn("text/html", r.getheader("Content-Type"))
                    state = json.loads(re.search(r'<script id="pr-state" type="application/json">(.*?)</script>',
                                                 page, re.S).group(1))
                    self.assertTrue(state["ok"])
                    self.assertIn("British spellings", " ".join(p["name"] for p in state["prompts"]))
                    self.assertEqual(state["may"], {"prompts.save": True, "prompts.delete": True})
                    self.assertIn("any device let in", page)
                    self.assertIn('href="/settings/prompts/" aria-current="page"', page, "one of Settings' doors")
                    self.assertIn('data-mobile-page', page)
                    self.assertNotIn('class="lockline"', page, "no lock line and no dead button on this door")
                    self.assertIn('<span class="gate open">', page.split('<h1 class="idx">', 1)[1].split("</p>", 1)[0],
                                  "its own pill says any device let in")
                    status, hub, _ = self.ask("GET", "/settings/")
                    self.assertIn('<a class="door" href="/settings/prompts/">', hub)
                    status, _, r = self.ask("GET", "/settings/prompts")
                    self.assertEqual((status, r.getheader("Location").endswith("/settings/prompts/")), (302, True))
                    self.assertEqual(self.ask("POST", "/settings/prompts/", {})[0], 405, "a page is not posted to")
            finally:
                for p in reversed(patches):
                    p.stop()

    def test_what_a_person_wrote_cannot_end_the_pages_script_or_add_a_tag(self):
        nasty = {"name": "a & <b>x</b>", "text": "Say \"hi\" & </script><script>alert(1)</script> and <img src=x>"}
        self.make(**nasty)
        status, page, _ = self.ask("GET", "/settings/prompts/")
        self.assertEqual(status, 200)
        self.assertNotIn("</script><script>alert(1)", page, "inside the script, only `</` could end it")
        state = json.loads(re.search(r'<script id="pr-state" type="application/json">(.*?)</script>', page, re.S)
                           .group(1).replace("<\\/", "</"))
        self.assertEqual((state["prompts"][0]["name"], state["prompts"][0]["text"]), (nasty["name"], nasty["text"]),
                         "read back as it was written, whatever it holds")

    def test_a_device_let_in_may_do_all_of_it_and_the_computer_sees_what_it_wrote(self):
        for p in self.as_phone():
            p.start()
            self.addCleanup(p.stop)
        made = self.make(name="from a phone")
        status, got, _ = self.ask("POST", "/settings/api/prompts/save", dict(mine("video-region"), id=made["id"],
                                                                             name="renamed", text="Changed."))
        self.assertEqual((status, got["prompt"]["name"], got["prompt"]["text"]), (200, "renamed", "Changed."))
        status, got, _ = self.ask("POST", "/settings/api/prompts/get", {"id": made["id"]})
        self.assertEqual((status, got["prompt"]["text"], got["verdict"]), (200, "Changed.", None))
        status, got, _ = self.ask("POST", "/settings/api/prompts/parseh", {"surface": "video-region"})
        self.assertEqual((status, got["surface"], got["locked"]), (200, "video-region", True))
        status, got, _ = self.ask("POST", "/settings/api/prompts/state", {})
        self.assertEqual([p["name"] for p in got["prompts"]], ["renamed"])
        status, got, _ = self.ask("POST", "/settings/api/prompts/delete", {"id": made["id"]})
        self.assertEqual((status, got["ok"], P.all_of()), (200, True, []))
        status, got, _ = self.ask("POST", "/settings/api/prompts/delete", {"id": made["id"]})
        self.assertEqual(status, 404)
        self.assertIn("there is no prompt of yours with that id", got["error"])

    def test_a_route_is_a_post_and_the_export_a_get(self):
        made = self.make()
        for what in ("state", "list", "get", "parseh", "save", "uptodate", "import", "delete"):
            self.assertEqual(self.ask("GET", "/settings/api/prompts/" + what)[0], 405, what)
        self.assertEqual(self.ask("POST", "/settings/api/prompts/export", {"id": made["id"]})[0], 405)
        self.assertEqual(self.ask("POST", "/settings/api/prompts/nothing", {})[0], 404, "a route nobody wrote down")

    def test_the_export_is_a_file_that_comes_back_in(self):
        made = self.make(name="British spellings")
        status, got, r = self.ask("GET", "/settings/api/prompts/export?id=" + made["id"])
        self.assertEqual(status, 200)
        self.assertEqual(r.getheader("Content-Type"), "application/json; charset=utf-8")
        self.assertIn("attachment; filename*=UTF-8''British-spellings.parseh-prompt.json",
                      r.getheader("Content-Disposition"))
        self.assertEqual(got["format"], P.EXPORT_FORMAT)
        status, back, _ = self.ask("POST", "/settings/api/prompts/import", {"data": json.dumps(got)})
        self.assertEqual((status, back["prompt"]["name"], back["renamed_from"]), (200, "British spellings (2)",
                                                                                   "British spellings"))
        status, gone, _ = self.ask("GET", "/settings/api/prompts/export?id=pgone0000")
        self.assertEqual((status, gone["ok"]), (404, False))

    def test_a_request_from_another_site_is_refused_and_writes_nothing(self):
        made = self.make(name="mine")
        body = {"data": json.dumps(json.loads(P.export_bytes(made["id"])))}
        before = Path(P.STORE).read_bytes()
        foreign = ({"Sec-Fetch-Site": "cross-site"}, {"Sec-Fetch-Site": "same-site"},
                   {"Origin": "https://evil.example"}, {"Origin": "null"})
        for prefix in ("/settings/api/prompts/", "/studio/api/prompts/"):
            for what, sent in (("save", mine("video-region", name="planted")), ("uptodate", {"id": made["id"]}),
                               ("import", body), ("delete", {"id": made["id"]})):
                for headers in foreign:
                    with self.subTest((prefix + what, headers)):
                        status, got, _ = self.ask("POST", prefix + what, sent, headers)
                        self.assertEqual((status, got["ok"]), (403, False))
                        self.assertEqual(Path(P.STORE).read_bytes(), before, "nothing was written")
        self.assertEqual([p["name"] for p in P.all_of()], ["mine"])
        # Parseh's own page is let through by the same check
        for headers in ({"Sec-Fetch-Site": "same-origin"}, {"Sec-Fetch-Site": "none"}, {}):
            status, got, _ = self.ask("POST", "/settings/api/prompts/list", {"surface": "video-region"}, headers)
            self.assertEqual((status, got["ok"]), (200, True), headers)

    def test_the_studios_copy_of_the_routes_answers_under_its_prefix_and_is_the_same_store(self):
        status, got, _ = self.ask("POST", "/studio/api/prompts/save", mine("studio-doc", name="from the studio"))
        self.assertEqual((status, got["ok"]), (200, True), got)
        pid = got["prompt"]["id"]
        status, got, _ = self.ask("POST", "/settings/api/prompts/list", {"surface": "studio-doc", "lang": "fa"})
        self.assertEqual([p["id"] for p in got["prompts"]], [pid], "one store, two doors")
        status, got, r = self.ask("GET", "/studio/api/prompts/export?id=" + pid)
        self.assertEqual((status, got["prompt"]["name"]), (200, "from the studio"))
        status, got, _ = self.ask("POST", "/studio/api/prompts/parseh", {"surface": "studio-doc"})
        self.assertEqual((status, got["locked"], got["surface"]), (200, True, "studio-doc"))
        status, got, _ = self.ask("POST", "/studio/api/prompts/delete", {"id": pid})
        self.assertEqual((status, P.all_of()), (200, []))
        status, got, _ = self.ask("POST", "/studio/api/prompts/nothing", {})
        self.assertEqual(status, 404)

    def test_the_add_pages_prepare_takes_a_prompt_by_its_id(self):
        transcript = (PERSIAN_VIDEO / "transcript.txt").read_text(encoding="utf-8")
        ask = lambda **more: self.ask("POST", "/youtube/api/prepare", dict(
            {"url": "fA6bK2mQ8sT", "lang": "fa", "gloss": "en", "transcript": transcript}, **more))
        added = self.ask("POST", "/settings/api/prompts/save", mine("video-new", name="mine", text="Never gloss names."))[1]["prompt"]
        status, got, _ = ask()
        self.assertEqual((status, got["custom"]), (200, None))
        own = got["prompt"]
        status, got, _ = ask(prompt=added["id"])
        self.assertEqual(status, 200, got)
        self.assertEqual(got["custom"], {"id": added["id"], "name": "mine", "kind": "added"})
        self.assertIn("Never gloss names.", got["prompt"])
        # the options' words come before the person's name (a free text stands last), and Persian says its marks
        self.assertEqual(got["prompt"].split("\n")[0], K.version_line("video-new", "fa", "en", None, "mine"))
        self.assertTrue(got["prompt"].split("\n")[0].endswith(" · fa → en · %s · no marks · custom: mine" % version.VERSION))
        self.assertTrue(got["prompt"].split("\n\n", 1)[1].startswith(own.split("\n\n", 1)[1][:400]))
        # a prompt for another place, one that is gone, one asked for by its name: refused in words
        other = self.make(name="not for this")
        status, got, _ = ask(prompt=other["id"])
        self.assertEqual((status, got["ok"]), (400, False))
        self.assertIn("is a prompt for a stretch of a video, glossed by an LLM, and this asks for a video from its transcript",
                      got["error"])
        status, got, _ = ask(prompt="pgone0000")
        self.assertEqual((status, got["ok"]), (404, False))
        status, got, _ = ask(prompt="mine")
        self.assertEqual(status, 404, "a name is not an id")
        status, got, _ = ask(prompt=7)
        self.assertEqual(status, 400)

    def test_the_tidys_prompt_is_true_for_parsehs_and_an_id_for_a_persons(self):
        transcript = (PERSIAN_VIDEO / "transcript.txt").read_text(encoding="utf-8")
        ask = lambda asked: self.ask("POST", "/youtube/api/transcript", {"transcript": transcript, "lang": "fa",
                                                                        "prompt": asked})
        made = self.ask("POST", "/settings/api/prompts/save",
                        mine("transcript-tidy", name="tidy mine", kind="replace", text="Tidy it your way."))[1]["prompt"]
        status, got, _ = ask(True)
        self.assertEqual((status, "custom" in got), (200, False))
        self.assertIn("WHAT TO GIVE BACK", got["prompt"])
        status, got, _ = ask(made["id"])
        self.assertEqual((status, got["custom"]["kind"]), (200, "replace"))
        self.assertIn("Tidy it your way.", got["prompt"])
        self.assertNotIn("THE RULES, in the order they matter", got["prompt"], "in place of Parseh's rules")
        self.assertIn("WHAT TO GIVE BACK", got["prompt"], "and Parseh's contract stays")
        self.assertIn("THE TRANSCRIPT:", got["prompt"], "and the transcript")
        status, got, _ = ask("pgone0000")
        self.assertEqual((status, got["ok"]), (404, False))

    def test_a_stretch_of_a_video_and_of_a_book_take_a_prompt_by_its_id(self):
        pid = self.make(name="never names", text="Never gloss names.", languages=["fa"])["id"]
        book = self.ask("POST", "/settings/api/prompts/save", mine("book-region", name="for books", text="Say it short."))[1]["prompt"]
        routes = (("/youtube/api/region/prompt", "video-region", {"video": "fA6bK2mQ8sT", "from": 0, "to": 3}, pid),
                  ("/books/persian/mini-fa/__region/prompt", "book-region", {"first": 0, "last": 5}, book["id"]))
        for path, surface, area, mine_ in routes:
            with self.subTest(path):
                status, own, _ = self.ask("POST", path, dict(area, regloss=True))
                self.assertEqual((status, own["ok"], "custom" in own), (200, True, False), own)
                status, got, _ = self.ask("POST", path, dict(area, regloss=True, prompt=mine_))
                self.assertEqual((status, got["ok"]), (200, True), got)
                self.assertEqual(got["custom"]["id"], mine_)
                first = got["prompt"].split("\n")[0]
                self.assertTrue(first.startswith("Parseh prompt · %s · fa → en · %s · re-gloss · no marks · custom: " % (surface, version.VERSION)), first)
                self.assertEqual(got["prompt"].split("\n\n", 2)[2].split("\n## What you answer")[1:],
                                 own["prompt"].split("\n\n", 2)[2].split("\n## What you answer")[1:], "the contract and the data are Parseh's")
                # one for another place, one that is gone
                status, bad, _ = self.ask("POST", path, dict(area, prompt=book["id"] if surface == "video-region" else pid))
                self.assertEqual((status, bad["ok"]), (400, False))
                self.assertIn("is a prompt for", bad["error"])
                status, bad, _ = self.ask("POST", path, dict(area, prompt="pgone0000"))
                self.assertEqual((status, bad["ok"]), (404, False))

    def test_a_prompt_for_one_language_is_refused_for_another_in_words(self):
        it = self.make(name="italian only", languages=["it"])
        status, got, _ = self.ask("POST", "/youtube/api/region/prompt",
                                  {"video": "fA6bK2mQ8sT", "from": 0, "to": 3, "prompt": it["id"]})
        self.assertEqual((status, got["ok"]), (400, False))
        self.assertIn("italian only is a prompt for Italian (it) only, and this is Persian (fa)", got["error"])

    def test_a_prompt_that_names_what_parseh_no_longer_fills_in_says_so_where_it_is_used(self):
        # written when Parseh's words had a name this Parseh does not fill in any more: it saved then,
        # and cannot be made now -- said in the person's words, not as a bug in a template
        transcript = (PERSIAN_VIDEO / "transcript.txt").read_text(encoding="utf-8")
        made = {surface: self.ask("POST", "/settings/api/prompts/save", mine(surface, name="old rules"))[1]["prompt"]["id"]
                for surface in ("video-region", "video-new", "transcript-tidy")}
        doc = json.loads(Path(P.STORE).read_text(encoding="utf-8"))
        for p in doc["prompts"]:
            p["text"] = "Use {{A_NAME_THAT_WENT}} well."
        Path(P.STORE).write_text(json.dumps(doc), encoding="utf-8")
        doors = (("/youtube/api/region/prompt", {"video": "fA6bK2mQ8sT", "from": 0, "to": 3}, "video-region"),
                 ("/youtube/api/prepare", {"url": "fA6bK2mQ8sT", "lang": "fa", "gloss": "en", "transcript": transcript}, "video-new"),
                 ("/youtube/api/transcript", {"transcript": transcript, "lang": "fa"}, "transcript-tidy"))
        for path, body, surface in doors:
            with self.subTest(path):
                status, got, _ = self.ask("POST", path, dict(body, prompt=made[surface]))
                self.assertEqual((status, got["ok"]), (400, False), got)
                self.assertIn("your prompt old rules could not be made: it names {{A_NAME_THAT_WENT}}, which this "
                              "Parseh does not fill in there", got["error"])
                self.assertIn("Open it from the prompt menu beside the copy button and save it again", got["error"])
                self.assertNotIn("bug", got["error"], "the words of a person's prompt, not of a template's")
        # and saving it again is where it is told which name it was
        status, got, _ = self.ask("POST", "/settings/api/prompts/save", dict(mine("video-region"), id=made["video-region"],
                                                                             text="Use {{A_NAME_THAT_WENT}} well."))
        self.assertEqual(status, 400)
        self.assertIn("{{A_NAME_THAT_WENT}} is not something Parseh fills in", got["error"])
        # Parseh's own prompt at the same door is untouched by any of it
        status, got, _ = self.ask("POST", "/youtube/api/region/prompt", {"video": "fA6bK2mQ8sT", "from": 0, "to": 3})
        self.assertEqual((status, got["ok"]), (200, True))


class TheStudioOnItsOwn(Stored):
    """The studio run by itself (markdown/app/server.py's own handler and its own check of
    another site): the same routes, over real HTTP, on the same store."""

    def setUp(self):
        super().setUp()
        import http.server
        quiet = mock.patch.object(studio_server.Handler, "log_message", lambda *a, **k: None)
        quiet.start()
        self.addCleanup(quiet.stop)
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), studio_server.Handler)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)

    def ask(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=60)
        data = None if body is None else json.dumps(body).encode("utf-8")
        c.request(method, path, body=data, headers=dict({"Content-Type": "application/json"} if data else {},
                                                        **(headers or {})))
        r = c.getresponse()
        raw = r.read()
        c.close()
        try:
            return r.status, json.loads(raw.decode("utf-8")), r
        except ValueError:
            return r.status, raw.decode("utf-8", "replace"), r

    def test_the_routes_answer_and_share_the_store_with_the_toolbox(self):
        status, got, _ = self.ask("POST", "/api/prompts/save", mine("studio-doc", name="from the studio alone"))
        self.assertEqual((status, got["ok"]), (200, True), got)
        pid = got["prompt"]["id"]
        self.assertEqual([p["id"] for p in P.all_of()], [pid], "the store the toolbox reads")
        status, got, _ = self.ask("POST", "/api/prompts/list", {"surface": "studio-doc", "lang": "fa"})
        self.assertEqual([p["name"] for p in got["prompts"]], ["from the studio alone"])
        status, got, _ = self.ask("POST", "/api/prompts/parseh", {"surface": "studio-doc"})
        self.assertEqual((status, got["surface"], got["locked"]), (200, "studio-doc", True))
        status, got, r = self.ask("GET", "/api/prompts/export?id=" + pid)
        self.assertEqual((status, got["format"]), (200, P.EXPORT_FORMAT))
        self.assertIn("from-the-studio-alone.parseh-prompt.json", r.getheader("Content-Disposition"))
        status, got, _ = self.ask("POST", "/api/prompts/import", {"data": json.dumps(got)})
        self.assertEqual((status, got["renamed_from"]), (200, "from the studio alone"))
        status, got, _ = self.ask("POST", "/api/prompts/delete", {"id": pid})
        self.assertEqual((status, got["ok"], len(P.all_of())), (200, True, 1))
        self.assertEqual(self.ask("POST", "/api/prompts/delete", {"id": pid})[0], 404)
        self.assertEqual(self.ask("POST", "/api/prompts/nothing", {})[0], 404)

    def test_the_studios_own_check_refuses_another_site_and_nothing_is_written(self):
        made = P.save(mine("studio-doc", name="mine"))
        before = Path(P.STORE).read_bytes()
        for what, body in (("save", mine("ask", name="planted")), ("delete", {"id": made["id"]}),
                           ("uptodate", {"id": made["id"]}), ("import", {"data": "{}"})):
            for headers in ({"Sec-Fetch-Site": "cross-site"}, {"Origin": "https://evil.example"}):
                status, got, _ = self.ask("POST", "/api/prompts/" + what, body, headers)
                self.assertEqual((status, got["ok"]), (403, False), (what, headers))
        self.assertEqual(Path(P.STORE).read_bytes(), before)
        status, got, _ = self.ask("POST", "/api/prompts/list", {"surface": "studio-doc"}, {"Sec-Fetch-Site": "same-origin"})
        self.assertEqual((status, got["ok"]), (200, True), "and Parseh's own page is let through")

    def test_the_old_prompt_route_answers_from_the_store(self):
        with mock.patch.object(store, "LIB", self.tmp / "library"):
            (self.tmp / "library").mkdir()
            P.set_studio_text("Kept in the store.")
            status, got, _ = self.ask("GET", "/api/prompt?target=fa")
            self.assertEqual((status, got["custom"], got["text"]), (200, False, "Kept in the store."),
                             "the prompt is Parseh's own until the menu chooses another; the text is the old field")
            status, got, _ = self.ask("GET", "/api/prompt?target=fa&prompt=" + P.STUDIO_ID)
            self.assertEqual((status, got["custom"]["id"]), (200, P.STUDIO_ID))
            self.assertIn("Kept in the store.", got["prompt"])


if __name__ == "__main__":
    unittest.main()
