# SPDX-License-Identifier: GPL-3.0-or-later
"""The exercise decks over HTTP (markdown/app/deckroutes.py), and where they
are mounted beside the studio (markdown/app/server.py).

Every route is driven through deckroutes.dispatch with a fake handler
offering exactly what both servers' handlers share; a recording's byte ranges
go over a real socket to the studio's own handler (a range is only a range
when it went over the wire).  Every test works in a temporary exercises/ root
(decks.set_dir), a temporary studio library (store.use_library) and a
temporary clip tray (decks.set_clips_dir), and puts back every module global
it changes.  The recordings are real tones ffmpeg writes once (a format it
cannot write here skips the tests that need it)."""
import contextlib
import http.client
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "markdown" / "exlex", ROOT / "markdown" / "app",
               ROOT / "lib", ROOT / "youtube" / "lib"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import audiofile           # noqa: E402
import deckroutes          # noqa: E402
import decks               # noqa: E402
import store               # noqa: E402

TEMPLATES = ROOT / "markdown" / "app" / "templates"

CHOICE = (":::exercise single-choice\nprompt: Which is **hello**?\n"
          "- [x] [سلام]{tl}\n- [ ] [خداحافظ]{tl}\n:::")
FLASH = ":::exercise flashcard\nfront: [گربه]{tl}\nback: cat\n:::"
PNG = b"\x89PNG\r\n\x1a\n" + b"pixels"

SOUNDS = {}          # extension -> the bytes of a real one-second tone
_SOUND_DIR = None


def setUpModule():
    global _SOUND_DIR
    _SOUND_DIR = tempfile.TemporaryDirectory(prefix="parseh-deckroute-sounds-")
    ffmpeg = shutil.which("ffmpeg")
    for ext, codec in (("mp3", "libmp3lame"), ("ogg", "libvorbis"), ("webm", "libopus")):
        out = Path(_SOUND_DIR.name) / ("tone." + ext)
        if ffmpeg and subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                                      "sine=frequency=440:duration=1", "-c:a", codec, str(out)],
                                     capture_output=True).returncode == 0 and out.is_file():
            SOUNDS[ext] = out.read_bytes()
    # an MP4 with a picture track and no sound: its first bytes are an M4A's
    out = Path(_SOUND_DIR.name) / "video-only.mp4"
    if ffmpeg and subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                                  "testsrc=duration=1:size=64x48:rate=5", "-an", "-c:v", "mpeg4",
                                  str(out)], capture_output=True).returncode == 0 and out.is_file():
        SOUNDS["video-only"] = out.read_bytes()


def tearDownModule():
    _SOUND_DIR.cleanup()


def sound(case, ext="mp3"):
    if ext not in SOUNDS:
        case.skipTest("ffmpeg could not write a .%s here" % ext)
    return SOUNDS[ext]

LESSON = """---
title: Lesson
target: fa
---

Intro.

:::exercise single-choice
prompt: Top question[^n1]
- [x] yes
- [ ] no
:::

> A box.
>
> :::exercise flashcard
> front: [گربه]{tl}
> back: cat
> front-image: images/cat.png
> :::

[^n1]: the first note
"""


class FakeHandler:
    """What deckroutes may use of a handler, recording the answer."""

    def __init__(self, query="", body=b"", spool=None):
        self.query = urllib.parse.parse_qs(query)
        self.raw = body
        if spool is not None:
            self._spool = spool
        self._head = False
        self.status = self.ctype = self.data = self.json = self.html = None
        self.extra = {}
        self.file = None

    def _body(self):
        return self.raw

    def _json_body(self):
        return json.loads(self.raw.decode("utf-8")) if self.raw else {}

    def send_bytes(self, data, ctype, code=200, extra=None):
        self.status, self.ctype, self.data, self.extra = code, ctype, data, dict(extra or {})

    def send_json(self, obj, code=200):
        # through the encoder, as a real answer would be: nothing unserialisable
        self.json = json.loads(json.dumps(obj, ensure_ascii=False))
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8", code)

    def send_html(self, text, code=200):
        self.html = text
        self.send_bytes(text.encode("utf-8"), "text/html; charset=utf-8", code)

    def send_file(self, path, download_name=None, inline_type=None):
        path = Path(path)
        if not path.is_file():
            return self.send_json({"error": "not found"}, 404)
        self.file = path
        self.send_bytes(path.read_bytes(), inline_type or "application/octet-stream", 200)


def call(method, target, body=None, raw=None, spool=None):
    """Dispatch one request; `target` is the path under /exercises, with its query."""
    path, _, query = target.partition("?")
    if raw is None:
        raw = b"" if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    h = FakeHandler(query, raw, spool)
    deckroutes.dispatch(h, method, path)
    return h


def templates_written(*names):
    return all((TEMPLATES / n).is_file() for n in names)


class Base(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        root = Path(self.td.name)
        self.store_dir = root / "exercises"
        was_dir = decks.set_dir(self.store_dir)
        self.addCleanup(decks.set_dir, was_dir)
        was_lib = store.use_library(root / "library")
        self.addCleanup(store.use_library, was_lib)
        was_studio = deckroutes.STUDIO
        deckroutes.set_studio_base("/studio")
        self.addCleanup(deckroutes.set_studio_base, was_studio)
        was_shutdown = deckroutes._SHUTDOWN["fn"]
        self.addCleanup(deckroutes.set_shutdown, was_shutdown)
        self.tray = root / "clips"
        was_tray = decks.set_clips_dir(self.tray)
        self.addCleanup(decks.set_clips_dir, was_tray)

    def ok(self, h, code=200):
        self.assertEqual(code, h.status, h.json or h.html)
        self.assertTrue(h.json.get("ok"), h.json)
        return h.json

    def refused(self, h, code, conflict=None):
        self.assertEqual(code, h.status, h.json or (h.html or "")[:200])
        self.assertIsNotNone(h.json, "a refusal answers JSON")
        self.assertIs(False, h.json.get("ok"), h.json)
        self.assertTrue(h.json.get("error"), h.json)
        if conflict:
            self.assertEqual(conflict, h.json.get("conflict"))
        return h.json

    def deck(self, name="Greetings", lang="fa"):
        return self.ok(call("POST", "/api/decks", {"name": name, "lang": lang}), 201)["deck"]

    def item(self, deck, markdown=CHOICE, force=False):
        body = {"markdown": markdown}
        if force:
            body["force"] = True
        return self.ok(call("POST", "/api/decks/%s/items" % deck["path"], body), 201)["item"]


class DeckRouteTests(Base):
    def test_create_list_get_update_delete(self):
        deck = self.deck()
        self.assertEqual(("persian", "greetings", "persian/greetings", "fa"),
                         (deck["folder"], deck["slug"], deck["path"], deck["lang"]))
        self.assertEqual(0, deck["counts"]["total"])
        self.assertEqual({"new", "learning", "review"}, set(deck["study"]))

        listed = self.ok(call("GET", "/api/decks"))["decks"]
        self.assertEqual(["persian/greetings"], [d["path"] for d in listed])
        self.assertEqual(1, len(self.ok(call("GET", "/api/decks?lang=fa"))["decks"]))
        self.assertEqual([], self.ok(call("GET", "/api/decks?lang=ja"))["decks"])
        self.refused(call("GET", "/api/decks?lang=zz"), 400)

        got = self.ok(call("GET", "/api/decks/persian/greetings"))
        self.assertEqual(deck["id"], got["deck"]["id"])
        self.assertEqual([], got["items"])

        changed = self.ok(call("PATCH", "/api/decks/persian/greetings",
                               {"name": "Hellos", "settings": {"new_per_day": 5}}))["deck"]
        self.assertEqual(("Hellos", 5, "greetings"),
                         (changed["name"], changed["settings"]["new_per_day"], changed["slug"]))
        self.refused(call("PATCH", "/api/decks/persian/greetings",
                          {"settings": {"new_per_day": -1}}), 400)

        self.ok(call("DELETE", "/api/decks/persian/greetings"))
        self.refused(call("GET", "/api/decks/persian/greetings"), 404)
        self.assertEqual(1, len(list((self.store_dir / ".trash").iterdir())))
        self.assertEqual([], self.ok(call("GET", "/api/decks"))["decks"])

    def test_bad_bodies_are_refused_with_ok_false(self):
        self.refused(call("POST", "/api/decks", {"lang": "fa"}), 400)
        self.refused(call("POST", "/api/decks", {"name": "x", "lang": "zz"}), 400)
        self.refused(call("POST", "/api/decks", ["name", "x"]), 400)
        self.assertEqual("bad JSON body",
                         self.refused(call("POST", "/api/decks", raw=b"{nope"), 400)["error"])
        self.refused(call("POST", "/api/decks", raw=b"\xff\xfe"), 400)

    def test_one_answer_when_the_handler_answers_bad_bodies_itself(self):
        # serve.py's _json_body answers an unusable body on its own and gives
        # back None.  A route that went on would write a second answer into
        # the keep-alive connection; the routes read h._body() instead.
        class ParsehStyle(FakeHandler):
            answers = 0

            def _json_body(self):
                try:
                    body = json.loads(self.raw.decode("utf-8"))
                except Exception:
                    self.send_json({"ok": False, "error": "not JSON"}, 400)
                    return None
                if not isinstance(body, dict):
                    self.send_json({"ok": False, "error": "expected a JSON object"}, 400)
                    return None
                return body

            def send_bytes(self, data, ctype, code=200, extra=None):
                self.answers += 1
                super().send_bytes(data, ctype, code, extra)

        for raw in (b"", b"[]", b"{nope", b"\xff", b"[" * 100000):
            h = ParsehStyle("", raw)
            deckroutes.dispatch(h, "POST", "/api/decks")
            self.assertEqual(1, h.answers, raw[:10])
            self.refused(h, 400)
        self.assertFalse(self.store_dir.exists(), "a refused body wrote nothing")

    def test_unknown_decks_are_404(self):
        for method, path in (("GET", "/api/decks/persian/nothing-here"),
                             ("PATCH", "/api/decks/persian/nothing-here"),
                             ("DELETE", "/api/decks/persian/nothing-here"),
                             ("GET", "/api/decks/klingon/greetings"),
                             ("GET", "/api/decks/persian/nothing-here/next"),
                             ("GET", "/api/decks/persian/nothing-here/export"),
                             ("POST", "/api/decks/persian/nothing-here/items"),
                             ("POST", "/api/decks/persian/nothing-here/preview")):
            body = {"markdown": CHOICE} if method != "GET" else None
            self.refused(call(method, path, body), 404)


class ItemRouteTests(Base):
    def test_add_get_update_duplicate_delete(self):
        deck = self.deck()
        base = "/api/decks/persian/greetings"
        item = self.item(deck)
        self.assertEqual(("single-choice", []), (item["subtype"], item["errors"]))

        dup = self.refused(call("POST", base + "/items", {"markdown": CHOICE}), 409, "duplicate")
        self.assertIn("Greetings", dup["error"])
        forced = self.item(deck, force=True)
        self.assertNotEqual(item["id"], forced["id"])
        self.refused(call("POST", base + "/items", {"markdown": "just prose"}), 400)
        self.refused(call("POST", base + "/items", {"markdown": CHOICE + "\n\n" + FLASH}), 400)

        got = self.ok(call("GET", base + "/items/" + item["id"]))
        self.assertEqual(item["id"], got["item"]["id"])
        self.assertIn('data-subtype="single-choice"', got["html"])
        self.assertIn('class="ex-edit"', got["html"], "items/I is the solved (editor) preview")

        edited = self.ok(call("PUT", base + "/items/" + item["id"], {"markdown": FLASH}))["item"]
        self.assertEqual(("flashcard", item["created"]), (edited["subtype"], edited["created"]))
        self.refused(call("PUT", base + "/items/" + item["id"], {"markdown": ""}), 400)

        copy = self.ok(call("POST", base + "/items/%s/duplicate" % item["id"]), 201)["item"]
        self.assertEqual(item["id"], copy["origin"]["duplicate_of"])

        self.ok(call("DELETE", base + "/items/" + item["id"]))
        self.refused(call("GET", base + "/items/" + item["id"]), 404)
        self.refused(call("DELETE", base + "/items/" + item["id"]), 404)
        self.refused(call("PUT", base + "/items/0123456789ab", {"markdown": FLASH}), 404)
        self.assertEqual(2, self.ok(call("GET", base))["deck"]["counts"]["total"])

    def test_preview_renders_unsaved_markdown_with_the_items_footnotes(self):
        deck = self.deck()
        base = "/api/decks/persian/greetings"
        html = self.ok(call("POST", base + "/preview", {"markdown": "\n" + FLASH + "\n"}))["html"]
        self.assertIn('data-subtype="flashcard"', html)
        self.refused(call("POST", base + "/preview", {"markdown": 3}), 400)
        self.refused(call("POST", base + "/preview",
                          {"markdown": "x" * (decks.MAX_MARKDOWN + 1)}), 400)
        # a control character is htmlgen's sentinel: cleaned, not a crash
        self.ok(call("POST", base + "/preview", {"markdown": FLASH.replace("cat", "c\x00a\x01t")}))
        # a lone surrogate is refused the way saving refuses it, not answered with a 500
        # (sent as the browser sends it: JSON.stringify escapes it as \ud800)
        raw = json.dumps({"markdown": FLASH.replace("cat", "\ud800")}).encode("ascii")
        out = self.refused(call("POST", base + "/preview", raw=raw), 400)
        self.assertEqual("the exercise must be text", out["error"])

        doc = store.create(LESSON)
        copied = self.ok(call("POST", base + "/copy", {
            "doc_id": doc["id"], "ordinal": 1, "subtype": "single-choice",
            "updated": doc["updated"]}), 201)["item"]
        self.assertIn("the first note", copied["footnotes"])
        html = self.ok(call("POST", base + "/preview",
                            {"markdown": copied["markdown"], "item": copied["id"]}))["html"]
        self.assertIn("the first note", html)
        self.refused(call("POST", base + "/preview",
                          {"markdown": FLASH, "item": "0123456789ab"}), 404)


class CopyRouteTests(Base):
    def setUp(self):
        super().setUp()
        self.doc = store.create(LESSON)
        images = store.images_dir(self.doc["id"])
        images.mkdir(parents=True, exist_ok=True)
        (images / "cat.png").write_bytes(PNG)
        self.deck()
        self.base = "/api/decks/persian/greetings"

    def copy(self, **over):
        body = {"doc_id": self.doc["id"], "ordinal": 2, "subtype": "flashcard",
                "updated": self.doc["updated"]}
        body.update(over)
        return call("POST", self.base + "/copy", body)

    def test_copy_answers_item_warnings_and_the_deck(self):
        out = self.ok(self.copy(), 201)
        self.assertEqual(("flashcard", []), (out["item"]["subtype"], out["warnings"]))
        self.assertEqual({"doc_id": self.doc["id"], "doc_uid": self.doc["uid"],
                          "title": "Lesson", "ordinal": 2}, out["item"]["origin"])
        self.assertEqual(1, out["deck"]["counts"]["total"])
        self.assertEqual("persian/greetings", out["deck"]["path"])

        self.refused(self.copy(), 409, "duplicate")
        self.ok(self.copy(force=True), 201)

        # and its picture is served from the deck's own media address
        h = call("GET", "/media/persian/greetings/images/cat.png")
        self.assertEqual((200, PNG), (h.status, h.data))

    def test_refusals(self):
        self.refused(self.copy(updated="2000-01-01T00:00:00+00:00"), 409, "stale")
        self.refused(self.copy(ordinal=9), 409, "stale")
        self.refused(self.copy(subtype="single-choice"), 409, "stale")
        self.assertEqual("document not found",
                         self.refused(self.copy(doc_id="no-such-doc-123456"), 404)["error"])
        self.refused(self.copy(doc_id=None), 404)
        self.refused(self.copy(doc_id=17), 404)
        self.refused(self.copy(subtype=None), 400)
        self.refused(self.copy(ordinal="two"), 400)
        self.ok(call("POST", "/api/decks", {"name": "Japanese", "lang": "ja"}), 201)
        wrong = self.refused(call("POST", "/api/decks/japanese/japanese/copy", {
            "doc_id": self.doc["id"], "ordinal": 1, "subtype": "single-choice",
            "updated": self.doc["updated"]}), 400)
        self.assertIn("Persian", wrong["error"])
        self.refused(call("POST", "/api/decks/persian/nothing-here/copy", {
            "doc_id": self.doc["id"], "ordinal": 1, "subtype": "single-choice"}), 404)

    def test_a_store_error_is_a_400(self):
        with mock.patch.object(decks, "copy_from_doc", side_effect=store.StoreError("corrupt meta")):
            self.assertEqual("corrupt meta", self.refused(self.copy(), 400)["error"])


class StudyRouteTests(Base):
    def setUp(self):
        super().setUp()
        deck = self.deck()
        self.first = self.item(deck, CHOICE)
        self.second = self.item(deck, FLASH)
        self.base = "/api/decks/persian/greetings"

    def test_next_renders_the_card_unsolved_with_its_intervals(self):
        out = self.ok(call("GET", self.base + "/next"))
        self.assertFalse(out["done"])
        self.assertEqual(self.first["id"], out["item"]["id"])
        self.assertEqual({"again", "hard", "good", "easy"}, set(out["intervals"]))
        self.assertEqual({"new": 2, "learning": 0, "review": 0}, out["counts"])
        self.assertIn('data-subtype="single-choice"', out["html"])
        self.assertNotIn('class="ex-edit"', out["html"], "a study card is not the editor preview")
        self.assertIn("/exercises/media/persian/greetings/", deckroutes._asset_base("persian", "greetings"))

    def test_skip_leaves_ids_out_of_the_queue(self):
        out = self.ok(call("GET", self.base + "/next?skip=" + self.first["id"]))
        self.assertEqual(self.second["id"], out["item"]["id"])
        out = self.ok(call("GET", self.base + "/next?skip=%s,%s,not-an-id"
                           % (self.first["id"], self.second["id"])))
        self.assertTrue(out["done"])
        self.assertEqual((None, None, None), (out["item"], out["html"], out["intervals"]))

    def test_review_schedules_and_answers_the_next_card(self):
        out = self.ok(call("POST", self.base + "/review",
                           {"item": self.first["id"], "rating": "good", "result": True}))
        nxt = out["next"]
        self.assertEqual(self.second["id"], nxt["item"]["id"])
        self.assertIn("html", nxt)
        self.assertNotIn("ok", nxt)
        got = self.ok(call("GET", self.base + "/items/" + self.first["id"]))["item"]
        self.assertEqual(("learning", 1), (got["schedule"]["state"], got["reps"]))
        # the skipped ids travel with a review too
        out = self.ok(call("POST", self.base + "/review?skip=" + self.second["id"],
                           {"item": self.first["id"], "rating": "again", "result": False}))
        self.assertNotEqual(self.second["id"], (out["next"]["item"] or {}).get("id"))

        self.refused(call("POST", self.base + "/review",
                          {"item": self.first["id"], "rating": "perfect"}), 400)
        self.refused(call("POST", self.base + "/review",
                          {"item": self.first["id"], "rating": "good", "result": "yes"}), 400)
        self.refused(call("POST", self.base + "/review",
                          {"item": "0123456789ab", "rating": "good"}), 404)

    def test_a_follow_ups_review_carries_how_many_steps_were_right(self):
        # (a0.5.4) the scheduler sees one exercise; the history row keeps {right, of}
        chain = self.ok(call("POST", self.base + "/items", {"markdown": (
            ":::exercise follow-up\n::::exercise single-choice\n- [x] a\n- [ ] b\n::::\n"
            "::::exercise single-choice\n- [x] a\n- [ ] b\n::::\n:::")}), 201)["item"]
        self.assertEqual(("follow-up", 2), (chain["subtype"], chain["steps"]))
        self.ok(call("POST", self.base + "/review", {"item": chain["id"], "rating": "again", "result": False,
                                                    "steps": {"right": 1, "of": 2}}))
        sched = decks.deck_dir("persian", "greetings") / "schedule" / (chain["id"] + ".json")
        row = json.loads(sched.read_text(encoding="utf-8"))["history"][0]
        self.assertEqual(("again", False, {"right": 1, "of": 2}), (row["rating"], row["result"], row["steps"]))
        # a count that does not add up is not kept
        self.ok(call("POST", self.base + "/review", {"item": chain["id"], "rating": "again", "result": False,
                                                    "steps": {"right": 9, "of": 2}}))
        rows = json.loads(sched.read_text(encoding="utf-8"))["history"]
        self.assertEqual([True, False], ["steps" in r for r in rows])

    def test_a_page_copied_as_one_follow_up_asks_for_its_ordinals_and_the_type(self):
        meta = store.create("---\ntitle: Two\ntarget: fa\n---\n\n:::exercise true-false\n- a => true\n:::\n\n"
                            ":::exercise yes-no\n- b => yes\n:::\n")
        out = self.ok(call("POST", self.base + "/copy", {"doc_id": meta["id"], "ordinals": [1, 2], "subtype": "follow-up",
                                                         "updated": meta["updated"]}), 201)
        self.assertEqual(("follow-up", 2), (out["item"]["subtype"], out["item"]["steps"]))
        # ordinals go with the type follow-up, and are a list
        self.refused(call("POST", self.base + "/copy", {"doc_id": meta["id"], "ordinals": [1, 2], "subtype": "yes-no"}), 400)
        self.refused(call("POST", self.base + "/copy", {"doc_id": meta["id"], "ordinals": "1,2", "subtype": "follow-up"}), 400)
        self.refused(call("POST", self.base + "/copy", {"doc_id": meta["id"], "ordinals": [1], "subtype": "follow-up"}), 400)

    def test_an_answer_to_a_state_already_left_is_refused(self):
        # a second tab, or a retry after a lost reply, answers with the reps
        # the page showed: scheduled again, a review's interval would be
        # multiplied a second time
        body = {"item": self.first["id"], "rating": "good", "result": True, "reps": 0}
        self.ok(call("POST", self.base + "/review", body))
        sched = decks.deck_dir("persian", "greetings") / "schedule" / (self.first["id"] + ".json")
        saved = sched.read_bytes()
        for reps in (0, 2, "1", True, [1]):
            self.refused(call("POST", self.base + "/review", dict(body, reps=reps)),
                         409, "reviewed")
            self.assertEqual(saved, sched.read_bytes(), "a refused answer writes nothing: %r" % reps)
        self.ok(call("POST", self.base + "/review", dict(body, reps=1)))
        got = self.ok(call("GET", self.base + "/items/" + self.first["id"]))["item"]
        self.assertEqual(2, got["reps"])

    def test_an_answer_saved_is_reported_saved_when_next_cannot_be_built(self):
        with mock.patch.object(decks, "next_card", side_effect=RuntimeError("render broke")), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            h = call("POST", self.base + "/review",
                     {"item": self.first["id"], "rating": "good", "result": True, "reps": 0})
        self.assertIsNone(self.ok(h)["next"], "the page asks /next itself")
        self.assertIn("Traceback", err.getvalue())
        self.assertIn("render broke", err.getvalue())
        got = self.ok(call("GET", self.base + "/items/" + self.first["id"]))["item"]
        self.assertEqual(("learning", 1), (got["schedule"]["state"], got["reps"]))
        # a client that went away is still the server's to handle
        with mock.patch.object(decks, "next_card", side_effect=BrokenPipeError()):
            with self.assertRaises(BrokenPipeError):
                call("POST", self.base + "/review", {"item": self.second["id"], "rating": "good"})


class FileRouteTests(Base):
    def setUp(self):
        super().setUp()
        self.deck_summary = self.deck()
        self.card = self.item(self.deck_summary, CHOICE)
        self.base = "/api/decks/persian/greetings"
        self.ok(call("POST", self.base + "/review",
                     {"item": self.card["id"], "rating": "good", "result": True}))

    def export(self, query):
        h = call("GET", self.base + "/export" + query)
        self.assertEqual((200, "application/zip"), (h.status, h.ctype))
        return h

    def test_export_is_an_attachment_with_or_without_scheduling(self):
        h = self.export("?scheduling=1")
        self.assertEqual('attachment; filename="exercises-greetings-with-scheduling.zip"',
                         h.extra.get("Content-Disposition"))
        names = zipfile.ZipFile(io.BytesIO(h.data)).namelist()
        self.assertIn(decks.MANIFEST, names)
        self.assertIn("schedule/%s.json" % self.card["id"], names)

        h = self.export("?scheduling=0")
        self.assertEqual('attachment; filename="exercises-greetings.zip"',
                         h.extra.get("Content-Disposition"))
        names = zipfile.ZipFile(io.BytesIO(h.data)).namelist()
        self.assertEqual([], [n for n in names if n.startswith("schedule/")])
        self.assertIn("-with-scheduling", self.export("").extra["Content-Disposition"])

    def test_import_from_the_raw_body(self):
        blob = self.export("?scheduling=1").data
        clash = self.refused(call("POST", "/api/import", raw=blob), 409, "exists")
        self.assertIn("Greetings", clash["error"])

        out = self.ok(call("POST", "/api/import?mode=copy&scheduling=0", raw=blob))
        self.assertEqual(("Greetings (copy)", 1, [], False),
                         (out["deck"]["name"], out["imported"], out["skipped"], out["scheduling"]))
        self.assertEqual(1, out["deck"]["counts"]["new"])

        out = self.ok(call("POST", "/api/import?mode=replace", raw=blob))
        self.assertEqual(("greetings", True), (out["deck"]["slug"], out["scheduling"]))
        self.assertEqual(1, out["deck"]["counts"]["learning"])

        self.refused(call("POST", "/api/import", raw=b"not a zip"), 400)
        self.refused(call("POST", "/api/import", raw=b""), 400)
        self.refused(call("POST", "/api/import?mode=sideways", raw=blob), 400)

    def test_import_from_a_spooled_body(self):
        blob = self.export("?scheduling=1").data
        self.ok(call("DELETE", self.base))
        spool = Path(self.td.name) / "upload.zip"
        spool.write_bytes(blob)
        # the body in memory is empty: Parseh streamed it to the spool file
        out = self.ok(call("POST", "/api/import", raw=b"", spool=str(spool)))
        self.assertEqual(("Greetings", "greetings", 1), (out["deck"]["name"], out["deck"]["slug"],
                                                         out["imported"]))

    def test_the_shelf_backs_up_and_comes_back_through_its_doors(self):
        h = call("GET", "/api/backup")
        self.assertEqual(h.status, 200)
        said = h.extra.get("Content-Disposition", "")
        self.assertIn("attachment", said)
        self.assertIn("exercises-backup-", said)
        blob = h.data
        names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
        self.assertIn(decks.SHELF_MANIFEST, names)
        self.assertIn("persian/greetings/deck.json", names)
        # taken off the shelf, and put back by the door
        self.ok(call("DELETE", self.base))
        self.assertEqual(decks.list_decks(), [])
        out = self.ok(call("POST", "/api/restore", raw=blob), 201)
        self.assertEqual(out["restored"], ["Greetings"])
        self.assertEqual([d["slug"] for d in decks.list_decks()], ["greetings"])

    def test_a_restore_keeps_what_is_here_until_replace_is_asked(self):
        blob = call("GET", "/api/backup").data
        out = self.ok(call("POST", "/api/restore", raw=blob), 201)
        self.assertEqual((out["restored"], out["kept"]), ([], ["Greetings"]))
        out = self.ok(call("POST", "/api/restore?replace=1", raw=blob), 201)
        self.assertEqual((out["restored"], out["kept"]), (["Greetings"], []))
        self.assertEqual(len(decks.list_decks()), 1)

    def test_a_restore_from_a_spooled_body(self):
        """A shelf is the largest body this toolbox takes; the hub streams
        it to disk and the handler must read it from there."""
        blob = call("GET", "/api/backup").data
        self.ok(call("DELETE", self.base))
        spool = Path(self.td.name) / "shelf.zip"
        spool.write_bytes(blob)
        out = self.ok(call("POST", "/api/restore", raw=b"", spool=str(spool)), 201)
        self.assertEqual(out["restored"], ["Greetings"])

    def test_a_restore_with_no_body_says_so(self):
        self.refused(call("POST", "/api/restore", raw=b""), 400)

    def test_media_is_served_and_nothing_else_is(self):
        images = decks.deck_dir("persian", "greetings") / "images"
        images.mkdir(parents=True, exist_ok=True)
        (images / "cat.png").write_bytes(PNG)
        (self.store_dir / "persian" / "secret.png").write_bytes(b"not yours")
        h = call("GET", "/media/persian/greetings/images/cat.png")
        self.assertEqual((200, PNG), (h.status, h.data))

        self.refused(call("GET", "/media/persian/greetings/images/missing.png"), 404)
        self.refused(call("GET", "/media/persian/greetings/images/.."), 404)
        self.refused(call("GET", "/media/persian/greetings/images/deck.json"), 404)
        self.refused(call("GET", "/media/persian/nothing-here/images/cat.png"), 404)
        self.refused(call("GET", "/media/klingon/greetings/images/cat.png"), 404)
        for path in ("/media/persian/greetings/images/../../secret.png",
                     "/media/persian/greetings/images/%2e%2e%2fsecret.png",
                     "/media/persian/../persian/greetings/images/cat.png"):
            h = call("GET", path)
            self.assertEqual(404, h.status, path)
            self.assertIsNone(h.file, path)


class ImageRouteTests(Base):
    """Pictures uploaded into a deck (POST .../images), and the warnings of
    the add and update answers for pictures a deck does not have."""

    def setUp(self):
        super().setUp()
        self.deck()
        self.base = "/api/decks/persian/greetings"
        self.images = decks.deck_dir("persian", "greetings") / "images"

    def upload(self, data, name="Cat Photo.png", deck="persian/greetings"):
        query = "" if name is None else "?name=" + urllib.parse.quote(name)
        return call("POST", "/api/decks/%s/images%s" % (deck, query), raw=data)

    def stored(self):
        return sorted(p.name for p in self.images.iterdir()) if self.images.is_dir() else []

    def test_a_picture_is_stored_and_its_path_answered(self):
        out = self.ok(self.upload(PNG), 201)
        self.assertEqual({"ok": True, "name": "cat-photo.png", "path": "images/cat-photo.png",
                          "url": "/exercises/media/persian/greetings/images/cat-photo.png"}, out)
        h = call("GET", out["url"][len(deckroutes.BASE):])
        self.assertEqual((200, PNG), (h.status, h.data))
        # the same bytes are the same picture; other bytes of that name another
        self.assertEqual("cat-photo.png", self.ok(self.upload(PNG), 201)["name"])
        self.assertEqual("cat-photo-2.png", self.ok(self.upload(PNG + b"-other"), 201)["name"])
        self.assertEqual("img.png", self.ok(self.upload(PNG + b"-3", name=None), 201)["name"])
        self.assertEqual(["cat-photo-2.png", "cat-photo.png", "img.png"], self.stored())

    def test_add_and_update_answer_the_warnings(self):
        self.ok(self.upload(PNG), 201)
        md = FLASH.replace("back: cat", "back: cat\nfront-image: images/cat-photo.png")
        added = self.ok(call("POST", self.base + "/items", {"markdown": md}), 201)
        self.assertEqual([], added["warnings"])
        missing = md.replace("cat-photo.png", "dog.png")
        edited = self.ok(call("PUT", self.base + "/items/" + added["item"]["id"],
                              {"markdown": missing}))
        self.assertEqual(1, len(edited["warnings"]), edited["warnings"])
        self.assertIn("front-image", edited["warnings"][0])
        self.assertIn("images/dog.png", edited["warnings"][0])
        again = self.ok(call("POST", self.base + "/items", {"markdown": missing, "force": True}), 201)
        self.assertEqual(edited["warnings"], again["warnings"])

    def test_what_is_not_a_picture_is_refused_and_nothing_is_written(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            for data in (b"", b"not a picture", b'{"markdown": "x"}', b"GIF89a\x01\x00"):
                self.refused(self.upload(data), 400)
            # the body is looked at before the deck: an unknown deck with a
            # body that is not a picture is a 400 that reads nothing
            self.refused(self.upload(b"not a picture", deck="persian/nothing-here"), 400)
            self.refused(self.upload(PNG, deck="persian/nothing-here"), 404)
            self.refused(self.upload(PNG, deck="klingon/greetings"), 404)
            with mock.patch.object(store, "IMG_MAX", len(PNG) - 1):
                self.refused(self.upload(PNG), 400)
            self.refused(call("PUT", self.base + "/images", raw=PNG), 404)
        self.assertNotIn("Traceback", err.getvalue())
        self.assertEqual([], self.stored())
        self.assertEqual(["greetings"], sorted(p.name for p in (self.store_dir / "persian").iterdir()))


class AudioRouteTests(Base):
    """Recordings uploaded into a deck (POST .../audio), served from its
    media address, named by its exercises and carried by its export."""

    def setUp(self):
        super().setUp()
        self.deck()
        self.base = "/api/decks/persian/greetings"
        self.audio = decks.deck_dir("persian", "greetings") / "audio"

    def upload(self, data, name="Hello There.mp3", deck="persian/greetings"):
        query = "" if name is None else "?name=" + urllib.parse.quote(name)
        return call("POST", "/api/decks/%s/audio%s" % (deck, query), raw=data)

    def stored(self):
        return sorted(p.name for p in self.audio.iterdir()) if self.audio.is_dir() else []

    def test_a_recording_is_stored_served_and_its_path_answered(self):
        mp3, ogg = sound(self), sound(self, "ogg")
        out = self.ok(self.upload(mp3), 201)
        self.assertEqual({"ok": True, "name": "hello-there.mp3", "path": "audio/hello-there.mp3",
                          "url": "/exercises/media/persian/greetings/audio/hello-there.mp3"}, out)
        h = call("GET", out["url"][len(deckroutes.BASE):])
        self.assertEqual((200, mp3, self.audio / "hello-there.mp3"), (h.status, h.data, h.file))
        self.assertEqual("hello-there.mp3", self.ok(self.upload(mp3), 201)["name"])
        # the extension follows the bytes
        self.assertEqual("hello-there.ogg", self.ok(self.upload(ogg), 201)["name"])
        self.assertEqual("audio.mp3", self.ok(self.upload(mp3, name=None), 201)["name"])
        self.assertEqual(["audio.mp3", "hello-there.mp3", "hello-there.ogg"], self.stored())

        md = FLASH.replace("back: cat", "back: cat\nfront-audio: audio/hello-there.mp3")
        added = self.ok(call("POST", self.base + "/items", {"markdown": md}), 201)
        self.assertEqual([], added["warnings"])
        html = self.ok(call("GET", self.base + "/items/" + added["item"]["id"]))["html"]
        self.assertIn('src="/exercises/media/persian/greetings/audio/hello-there.mp3"', html)
        missing = md.replace("hello-there.mp3", "gone.mp3")
        edited = self.ok(call("PUT", self.base + "/items/" + added["item"]["id"], {"markdown": missing}))
        self.assertEqual(["front-audio: audio/gone.mp3 is not among this deck's recordings: "
                          "upload it, or the card plays nothing"], edited["warnings"])

    def test_what_is_not_a_recording_is_refused_and_nothing_is_written(self):
        mp3 = sound(self)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            utf16 = b"\xff\xfe" + ("Only words, and no recording.\n" * 20).encode("utf-16-le")
            for data in (b"", b"not a recording at all", PNG, b'{"markdown": "x"}', utf16):
                self.assertIn(self.refused(self.upload(data), 400)["error"],
                              ("the upload is empty: send the recording as the body",
                               "only MP3, M4A, AAC, Ogg, Opus, WAV, FLAC and WebM recordings can be added"))
            # an MP4 by its first bytes, a film with no sound track decoded
            self.assertEqual(self.refused(self.upload(sound(self, "video-only")), 400)["error"],
                             "the recording holds no sound")
            # the body is looked at before the deck: an unknown deck with a
            # body that is not a recording is a 400 that reads nothing
            with mock.patch.object(decks, "deck_dir", side_effect=AssertionError("looked")):
                self.refused(self.upload(b"not a recording", deck="persian/nothing-here"), 400)
                self.refused(self.upload(PNG, deck="klingon/greetings"), 400)
            self.refused(self.upload(mp3, deck="persian/nothing-here"), 404)
            self.refused(self.upload(mp3, deck="klingon/greetings"), 404)
            with mock.patch.object(audiofile, "MAX_BYTES", len(mp3) - 1):
                self.assertIn("larger than", self.refused(self.upload(mp3), 400)["error"])
            self.refused(call("PUT", self.base + "/audio", raw=mp3), 404)
            self.refused(call("POST", "/api/decks/persian/greetings/../greetings/audio", raw=mp3), 404)
        self.assertNotIn("Traceback", err.getvalue())
        self.assertEqual([], self.stored())
        self.assertEqual(["greetings"], sorted(p.name for p in (self.store_dir / "persian").iterdir()))

    def test_only_a_recording_of_the_deck_is_served(self):
        mp3 = sound(self)
        self.ok(self.upload(mp3, name="word.mp3"), 201)
        (self.audio / "notes.txt").write_text("not a recording", "utf-8")
        (self.store_dir / "persian" / "secret.mp3").write_bytes(mp3)
        (decks.deck_dir("persian", "greetings") / "images").mkdir()
        (decks.deck_dir("persian", "greetings") / "images" / "cat.png").write_bytes(PNG)
        for path in ("/media/persian/greetings/audio/missing.mp3",
                     "/media/persian/greetings/audio/notes.txt",
                     "/media/persian/greetings/audio/Word.mp3",
                     "/media/persian/greetings/audio/..",
                     "/media/persian/greetings/audio/../../secret.mp3",
                     "/media/persian/greetings/audio/%2e%2e%2fsecret.mp3",
                     "/media/persian/greetings/audio/../images/cat.png",
                     "/media/persian/../persian/greetings/audio/word.mp3",
                     "/media/persian/nothing-here/audio/word.mp3",
                     "/media/klingon/greetings/audio/word.mp3"):
            h = call("GET", path)
            self.assertEqual(404, h.status, path)
            self.assertIsNone(h.file, path)
        self.assertEqual((200, mp3), (call("GET", "/media/persian/greetings/audio/word.mp3").status,
                                      call("GET", "/media/persian/greetings/audio/word.mp3").data))

    def test_the_export_names_exactly_what_the_exercises_use(self):
        mp3, webm = sound(self), sound(self, "webm")
        self.ok(self.upload(mp3, name="word.mp3"), 201)
        self.ok(self.upload(webm, name="note.webm"), 201)
        self.ok(self.upload(mp3 + b"-other", name="unused.mp3"), 201)
        jolly = (":::exercise flashcard\ncard-type: jolly\nfront-primary: |\n"
                 "  ![](audio/word.mp3)\n\n  [سلام]{tl}\nback-primary: hello\n:::")
        item = self.ok(call("POST", self.base + "/items", {"markdown": jolly}), 201)["item"]
        h = call("GET", self.base + "/export?scheduling=0")
        self.assertEqual(200, h.status)
        with zipfile.ZipFile(io.BytesIO(h.data)) as zf:
            self.assertEqual([decks.MANIFEST, "items/%s.json" % item["id"], "audio/word.mp3"],
                             zf.namelist())
            self.assertEqual(mp3, zf.read("audio/word.mp3"))
        # back in, as a copy beside it: the recording plays from the copy
        out = self.ok(call("POST", "/api/import?mode=copy", raw=h.data))
        copy = out["deck"]["path"]
        got = call("GET", "/media/%s/audio/word.mp3" % copy)
        self.assertEqual((200, mp3), (got.status, got.data))
        self.refused(call("GET", "/media/%s/audio/unused.mp3" % copy), 404)

    def test_an_exercise_brings_its_clips_from_the_tray(self):
        mp3 = sound(self)
        self.tray.mkdir()
        (self.tray / "said-a1b2c3.mp3").write_bytes(mp3)
        md = FLASH.replace("back: cat", "back: cat\nback-audio: audio/said-a1b2c3.mp3")
        added = self.ok(call("POST", self.base + "/items", {"markdown": md}), 201)
        self.assertEqual([], added["warnings"])
        self.assertEqual(["said-a1b2c3.mp3"], self.stored())
        got = call("GET", "/media/persian/greetings/audio/said-a1b2c3.mp3")
        self.assertEqual((200, mp3), (got.status, got.data))

    def test_the_form_preview_plays_a_clip_still_in_the_tray(self):
        # pasted into the Add exercise form, a card cut in a book names a
        # recording and a frame the deck does not have until it is saved: the
        # preview loads them from the tray, and everything else from the deck
        mp3, png = sound(self), PNG
        self.tray.mkdir()
        (self.tray / "said-a1b2c3.mp3").write_bytes(mp3)
        (self.tray / "frame-d4e5f6.png").write_bytes(png)
        (self.tray / "fake-000000.mp3").write_bytes(b"words that only call themselves a recording")
        self.ok(self.upload(mp3, name="mine.mp3"), 201)
        (self.tray / "mine.mp3").write_bytes(mp3)          # the deck's own wins
        md = (":::exercise flashcard\ncard-type: jolly\nfront-primary: |\n"
              "  ![said](audio/said-a1b2c3.mp3)\n  hello\nfront-secondary: x\n"
              "back-primary: |\n  ![](audio/mine.mp3)\n\n  ![](audio/gone-111111.mp3)\n"
              "back-secondary: |\n  ![](audio/fake-000000.mp3)\n\n  ![](images/frame-d4e5f6.png)\n:::")
        preview = self.ok(call("POST", self.base + "/preview", {"markdown": md}))["html"]
        srcs = re.findall(r'<(?:audio|img)\b[^>]*\bsrc="([^"]*)"', preview)
        deck = "/exercises/media/persian/greetings/"
        self.assertEqual(["/clips/media/said-a1b2c3.mp3", deck + "audio/mine.mp3",
                          deck + "audio/gone-111111.mp3", deck + "audio/fake-000000.mp3",
                          "/clips/media/frame-d4e5f6.png"], srcs)
        vocab = FLASH.replace("back: cat", "back: cat\nfront-audio: audio/said-a1b2c3.mp3\n"
                              "front-image: images/frame-d4e5f6.png")
        preview = self.ok(call("POST", self.base + "/preview", {"markdown": vocab}))["html"]
        self.assertIn('src="/clips/media/said-a1b2c3.mp3"', preview)
        self.assertIn('src="/clips/media/frame-d4e5f6.png"', preview)
        # saved, the deck has them: its own preview and the study card load
        # them from the deck, and the editing form's preview too
        added = self.ok(call("POST", self.base + "/items", {"markdown": vocab}), 201)
        item = added["item"]["id"]
        for html in (self.ok(call("POST", self.base + "/preview", {"markdown": vocab, "item": item}))["html"],
                     self.ok(call("GET", self.base + "/items/" + item))["html"]):
            self.assertIn('src="%saudio/said-a1b2c3.mp3"' % deck, html)
            self.assertIn('src="%simages/frame-d4e5f6.png"' % deck, html)
            self.assertNotIn("/clips/media/", html)
        self.assertEqual(["mine.mp3", "said-a1b2c3.mp3"], self.stored())


class OriginRouteTests(Base):
    """POST .../items with the origin a book's or a video's card sheet sends."""

    def test_the_origin_is_kept_as_far_as_it_can_be_linked(self):
        self.deck()
        base = "/api/decks/persian/greetings/items"
        book = {"book": "/books/persian/tale", "label": "3.2", "title": "A tale",
                "url": "/books/persian/tale/reader/#p3.2"}
        out = self.ok(call("POST", base, {"markdown": CHOICE, "origin": book}), 201)
        self.assertEqual(book, out["item"]["origin"])
        video = {"video": "abc_DEF-123", "time": 65.4, "label": "1:05", "title": "A film"}
        out = self.ok(call("POST", base, {"markdown": FLASH, "origin": dict(
            video, url="javascript:alert(1)", book="//evil.example/books/x", source="//evil",
            extra={"nested": True})}), 201)
        self.assertEqual(video, out["item"]["origin"])
        listed = self.ok(call("GET", "/api/decks/persian/greetings"))["items"]
        self.assertEqual([book, video], [i["origin"] for i in listed])
        hostile = {"video": "../../x", "time": -3, "url": "//evil.example/", "label": 7,
                   "book": "/books/../../etc"}
        out = self.ok(call("POST", base, {"markdown": FLASH, "force": True, "origin": hostile}), 201)
        self.assertIsNone(out["item"]["origin"])
        for origin in ("a string", ["book"], 12, None):
            md = CHOICE.replace("hello", "hi %r" % (origin,))
            self.assertIsNone(self.ok(call("POST", base, {"markdown": md, "origin": origin}),
                                      201)["item"]["origin"])


class RangeOverTheWireTests(unittest.TestCase):
    """A deck's recording from the studio's own server on 127.0.0.1: the
    whole file, or the byte range a player asks for when it seeks."""

    @classmethod
    def setUpClass(cls):
        import server
        cls.td = tempfile.TemporaryDirectory(prefix="parseh-deck-range-")
        root = Path(cls.td.name)
        cls.was_dir = decks.set_dir(root / "exercises")
        cls.was_lib = store.LIB
        store.LIB = root / "library"
        store.LIB.mkdir()
        cls.quiet = mock.patch.object(server.Handler, "log_message", lambda *a: None)
        cls.quiet.start()
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.srv.daemon_threads = True
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.port = cls.srv.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.quiet.stop()
        decks.set_dir(cls.was_dir)
        store.LIB = cls.was_lib
        cls.td.cleanup()

    def ask(self, conn, method, path, body=None, headers=None):
        conn.request(method, path, body=body, headers=headers or {})
        r = conn.getresponse()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()

    def test_a_recording_is_served_whole_or_a_range_at_a_time(self):
        mp3 = sound(self)
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        self.addCleanup(c.close)
        status, _h, data = self.ask(c, "POST", "/exercises/api/decks",
                                    json.dumps({"name": "Sounds", "lang": "fa"}).encode())
        self.assertEqual(201, status, data)
        status, _h, data = self.ask(c, "POST", "/exercises/api/decks/persian/sounds/audio?name=tone.mp3",
                                    mp3)
        self.assertEqual((201, "audio/tone.mp3"), (status, json.loads(data)["path"]))
        url, size = "/exercises/media/persian/sounds/audio/tone.mp3", len(mp3)
        status, h, data = self.ask(c, "GET", url)
        self.assertEqual((200, "audio/mpeg", "bytes", mp3), (status, h["content-type"],
                                                             h["accept-ranges"], data))
        status, h, data = self.ask(c, "GET", url, headers={"Range": "bytes=0-99"})
        self.assertEqual((206, "audio/mpeg", "bytes 0-99/%d" % size, "100", mp3[:100]),
                         (status, h["content-type"], h["content-range"], h["content-length"], data))
        status, h, data = self.ask(c, "GET", url, headers={"Range": "bytes=-10"})
        self.assertEqual((206, "bytes %d-%d/%d" % (size - 10, size - 1, size), mp3[-10:]),
                         (status, h["content-range"], data))
        status, h, data = self.ask(c, "GET", url, headers={"Range": "bytes=1000-"})
        self.assertEqual((206, mp3[1000:]), (status, data))
        status, h, data = self.ask(c, "GET", url, headers={"Range": "bytes=%d-" % (size + 5)})
        self.assertEqual((416, "bytes */%d" % size, b""), (status, h["content-range"], data))
        status, _h, _data = self.ask(c, "GET", "/exercises/media/persian/sounds/audio/..%2fdeck.json",
                                     headers={"Range": "bytes=0-9"})
        self.assertEqual(404, status)


class NotesCopyTests(Base):
    """"+ Deck" on a note beside a book or a video: the copy names the notes
    page's prefix, and deckroutes asks the registered resolver which notes
    library that is."""

    PREFIX = "/books/persian/tale/notes"

    def setUp(self):
        super().setUp()
        self.notes_dir = Path(self.td.name) / "books" / "persian" / "tale" / "markdown"
        self.main_lib = store.use_library(self.notes_dir)
        try:
            self.doc = store.create(LESSON)
            images = store.images_dir(self.doc["id"])
            images.mkdir(parents=True, exist_ok=True)
            (images / "cat.png").write_bytes(PNG)
        finally:
            store.use_library(self.main_lib)
        was = deckroutes.set_notes_resolver(
            lambda prefix: self.notes_dir if prefix == self.PREFIX else None)
        self.addCleanup(deckroutes.set_notes_resolver, was)
        self.deck()
        self.base = "/api/decks/persian/greetings"

    def copy(self, deck="persian/greetings", **over):
        body = {"doc_id": self.doc["id"], "ordinal": 2, "subtype": "flashcard",
                "updated": self.doc["updated"], "source": self.PREFIX}
        body.update(over)
        return call("POST", "/api/decks/%s/copy" % deck, body)

    def test_a_note_is_copied_from_its_own_library(self):
        # the document is only among the notes: without its source, not found
        self.refused(self.copy(source=None), 404)
        self.refused(self.copy(source=""), 404)
        out = self.ok(self.copy(), 201)
        origin = out["item"]["origin"]
        self.assertEqual((self.doc["id"], "Lesson", self.PREFIX),
                         (origin["doc_id"], origin["title"], origin["source"]))
        self.assertEqual([], out["warnings"])
        h = call("GET", "/media/persian/greetings/images/cat.png")
        self.assertEqual((200, PNG), (h.status, h.data), "the note's picture came along")
        one = self.ok(self.copy(ordinal=1, subtype="single-choice"), 201)["item"]
        self.assertIn("the first note", one["footnotes"])
        self.assertEqual(Path(self.td.name) / "library", store.lib(),
                         "the thread is given back its own library")

    def test_notes_on_no_shelf_are_refused_before_anything_is_read(self):
        for source in ("/books/persian/other/notes", "javascript:alert(1)",
                       "//evil.example/books/persian/tale/notes", "/books/../tale/notes",
                       17, [self.PREFIX]):
            out = self.refused(self.copy(source=source), 400)
            self.assertEqual("those notes are not on this shelf", out["error"], source)
        with mock.patch.object(decks, "copy_from_doc") as copy_from_doc:
            self.refused(self.copy(deck="persian/nothing-here", source="/books/persian/other/notes"),
                         400)
        copy_from_doc.assert_not_called()
        deckroutes.set_notes_resolver(None)            # the studio alone knows no notes
        self.refused(self.copy(), 400)
        self.assertEqual(0, self.ok(call("GET", self.base))["deck"]["counts"]["total"])

    def test_notes_source_ok(self):
        self.assertTrue(deckroutes.notes_source_ok(self.PREFIX))
        self.assertEqual(self.notes_dir, deckroutes.notes_library(self.PREFIX))
        self.assertFalse(deckroutes.notes_source_ok("/books/persian/other/notes"))
        # a resolver that would say yes to anything still never sees a prefix
        # that is not a path on this server
        deckroutes.set_notes_resolver(lambda prefix: self.notes_dir)
        for bad in ("//evil.example/notes", "javascript:x", "/a/../b", "", None, 3):
            self.assertFalse(deckroutes.notes_source_ok(bad), bad)
        deckroutes.set_notes_resolver(mock.Mock(side_effect=OSError("File name too long")))
        self.assertFalse(deckroutes.notes_source_ok(self.PREFIX))


class PageAndDispatchTests(Base):
    def assert_filled(self, h, name):
        self.assertEqual(200, h.status, (h.html or "")[:300] or h.json)
        self.assertIn("text/html", h.ctype)
        if not templates_written(name):
            self.skipTest("templates/%s is not written yet: placeholders not checked" % name)
        self.assertNotIn("{{", h.html, "every placeholder of %s is filled" % name)
        self.assertIn('data-base="/exercises"', h.html)
        self.assertIn("/studio/static/", h.html)

    def test_decks_page(self):
        if not templates_written("decks.html"):
            self.skipTest("templates/decks.html is not written yet")
        self.deck()
        h = call("GET", "/")
        self.assert_filled(h, "decks.html")
        self.assertIn("parseh-langs", h.html)

    def test_deck_page(self):
        if not templates_written("deck.html"):
            self.skipTest("templates/deck.html is not written yet")
        # no braces in the name: a learner's "{{" is kept as typed (the test
        # of single-pass templating below), and would trip the check here
        self.deck(name="A <b>bold</b> deck")
        slug = self.ok(call("GET", "/api/decks"))["decks"][0]["slug"]
        for path in ("/deck/persian/%s" % slug, "/deck/persian/%s/" % slug):
            h = call("GET", path)
            self.assert_filled(h, "deck.html")
            self.assertNotIn("<b>bold</b>", h.html)
            self.assertIn('"lang": "fa"', h.html)

    def test_study_page(self):
        if not templates_written("study.html"):
            self.skipTest("templates/study.html is not written yet")
        deck = self.deck()
        h = call("GET", "/deck/%s/study" % deck["path"])
        self.assert_filled(h, "study.html")
        self.assertIn('data-lang="fa"', h.html)

    def test_unknown_decks_and_paths_get_the_404_page(self):
        for path in ("/deck/persian/nothing-here", "/deck/persian/nothing-here/study",
                     "/deck/klingon/greetings", "/nowhere", "/deck/persian/Upper"):
            h = call("GET", path)
            self.assertEqual(404, h.status, path)
            self.assertIn("404", h.html)
            self.assertIn('href="/studio/static/app.css"', h.html)
            self.assertNotIn("{{", h.html)
        self.refused(call("POST", "/nowhere"), 404)
        self.refused(call("PUT", "/api/decks"), 404)

    def test_pages_fill_every_placeholder_the_contract_names(self):
        """Independent of the real templates: stand-ins naming exactly the
        placeholders DESIGN.md section 3 promises each page."""
        common = ["BASE", "STUDIO", "TITLE", "LANGS_JSON"]
        per_deck = common + ["DECK_JSON", "LANG_JSON", "TARGET", "TARGET_NAME"]
        wanted = {"decks.html": common + ["LANG_CHIPS"], "deck.html": per_deck,
                  "study.html": per_deck}
        stand_in = Path(self.td.name) / "templates"
        stand_in.mkdir()
        for name, keys in wanted.items():
            (stand_in / name).write_text("\n".join("%s={{%s}}" % (k, k) for k in keys),
                                         encoding="utf-8")
        was = deckroutes.TEMPLATES
        deckroutes.TEMPLATES = stand_in
        self.addCleanup(setattr, deckroutes, "TEMPLATES", was)

        deck = self.deck(name="<Tehran> & co")
        pages = {"decks.html": call("GET", "/"),
                 "deck.html": call("GET", "/deck/" + deck["path"]),
                 "study.html": call("GET", "/deck/%s/study" % deck["path"])}
        for name, h in pages.items():
            self.assertEqual(200, h.status, name)
            self.assertNotIn("{{", h.html, name)
            values = dict(line.split("=", 1) for line in h.html.split("\n"))
            self.assertEqual(("/exercises", "/studio"), (values["BASE"], values["STUDIO"]), name)
            self.assertEqual("fa", json.loads(values["LANGS_JSON"])[0]["code"], name)
        decks_page = dict(l.split("=", 1) for l in pages["decks.html"].html.split("\n"))
        self.assertIn('data-pick="fa"', decks_page["LANG_CHIPS"])
        self.assertEqual(1, next(c["count"] for c in json.loads(decks_page["LANGS_JSON"])
                                 if c["code"] == "fa"))
        for name in ("deck.html", "study.html"):
            values = dict(l.split("=", 1) for l in pages[name].html.split("\n"))
            self.assertEqual(deck["id"], json.loads(values["DECK_JSON"])["id"])
            self.assertNotIn("<Tehran>", values["DECK_JSON"], "json for a script: < escaped")
            self.assertNotIn("<Tehran>", values["TITLE"])
            self.assertEqual(("fa", "Persian", "fa"),
                             (values["TARGET"], values["TARGET_NAME"],
                              json.loads(values["LANG_JSON"])["code"]))

    def test_mapping_values_are_not_substituted_twice(self):
        # TITLE is filled before TARGET: a replace-per-key loop would turn
        # the {{TARGET}} typed into the name into "fa"
        deck = self.deck(name="{{TARGET}} {{STUDIO}}")
        m = deckroutes._deck_mapping(deck["name"], deck)
        with mock.patch.object(Path, "read_text",
                               return_value="{{TITLE}}|{{STUDIO}}|{{NOPE}}|{{TARGET}}"):
            self.assertEqual("{{TARGET}} {{STUDIO}}|/studio|{{NOPE}}|fa",
                             deckroutes.render_template("x", m))

    def test_a_bug_is_a_500_that_still_answers_and_a_gone_client_is_raised(self):
        with mock.patch.object(decks, "list_decks", side_effect=RuntimeError("boom")), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            h = call("GET", "/api/decks")
        self.assertEqual((500, False), (h.status, h.json["ok"]))
        self.assertIn("boom", h.json["error"])
        self.assertIn("Traceback", err.getvalue())
        with mock.patch.object(decks, "list_decks", side_effect=BrokenPipeError()):
            with self.assertRaises(BrokenPipeError):
                call("GET", "/api/decks")

    def test_shutdown_delegates_to_the_registered_callable(self):
        deckroutes.set_shutdown(None)
        self.refused(call("POST", "/api/shutdown"), 404)
        seen = []
        deckroutes.set_shutdown(lambda h: (seen.append(h), h.send_json({"ok": True})))
        self.ok(call("POST", "/api/shutdown"))
        self.assertEqual(1, len(seen))


class MountTests(Base):
    """server.py hands /exercises to deckroutes, tells it the studio's base
    and registers its shutdown."""

    @classmethod
    def setUpClass(cls):
        import server
        cls.server = server

    def handler(self, method, path, body=b""):
        h = self.server.Handler.__new__(self.server.Handler)
        h.headers = {"Content-Length": str(len(body))}
        h.rfile = io.BytesIO(body)
        h.path = path
        h._head = False
        sent = {}

        def send_bytes(data, ctype, code=200, extra=None):
            sent.update(data=data, ctype=ctype, code=code, extra=extra or {})
        h.send_bytes = send_bytes
        h._dispatch(method)
        return sent

    def test_the_studio_on_its_own_mounts_the_decks(self):
        self.assertEqual(deckroutes.BASE, self.server.DECKS_BASE)
        self.assertIs(self.server.api_shutdown, deckroutes._SHUTDOWN["fn"])

        sent = self.handler("GET", "/exercises")
        self.assertEqual((302, "/exercises/"), (sent["code"], sent["extra"].get("Location")))

        self.deck()
        sent = self.handler("GET", "/exercises/api/decks?lang=fa")
        j = json.loads(sent["data"])
        self.assertEqual((200, True, ["persian/greetings"]),
                         (sent["code"], j["ok"], [d["path"] for d in j["decks"]]))
        body = json.dumps({"name": "Posted", "lang": "fa"}).encode()
        sent = self.handler("POST", "/exercises/api/decks", body)
        self.assertEqual((201, "Posted"), (sent["code"], json.loads(sent["data"])["deck"]["name"]))
        # the studio's own routes are untouched by the mount
        sent = self.handler("GET", "/api/exercise-decks")
        self.assertEqual(200, sent["code"])

    def test_a_note_offers_decks_when_its_notes_are_known(self):
        class Page:
            query = {}

            def send_html(self, text, code=200):
                self.html = text

        doc = store.create(LESSON)
        button = 'class="ex-to-deck"'
        prefix = "/books/persian/tale/notes"
        was = deckroutes.set_notes_resolver(
            lambda p: Path(self.td.name) / "notes" if p == prefix else None)
        self.addCleanup(deckroutes.set_notes_resolver, was)

        def page(mount=None):
            h = Page()
            was_mount = self.server.use_mount(mount, html_only=True) if mount else None
            try:
                self.server.page_doc(h, doc["id"])
            finally:
                if was_mount is not None:
                    self.server.restore_mount(was_mount)
            self.assertNotIn("{{NOTES_SOURCE}}", h.html)
            self.assertNotIn("{{DECKS_BASE}}", h.html)
            return h.html

        studio = page()
        self.assertIn('data-decks-base="/exercises"', studio)
        self.assertIn('data-notes-source=""', studio)
        self.assertEqual(2, studio.count(button))

        note = page(prefix)
        self.assertIn('data-decks-base="/exercises"', note)
        self.assertIn('data-notes-source="%s"' % prefix, note)
        self.assertEqual(2, note.count(button))

        for unknown in ("/books/persian/other/notes", "/books/notes"):
            other = page(unknown)
            self.assertIn('data-decks-base=""', other, unknown)
            self.assertIn('data-notes-source=""', other, unknown)
            self.assertNotIn(button, other, unknown)

    def test_set_base_tells_deckroutes_where_the_studio_is(self):
        was = self.server.BASE
        self.addCleanup(self.server.set_base, was)
        self.server.set_base("/studio/")
        self.assertEqual("/studio", deckroutes.STUDIO)
        self.server.set_base("")
        self.assertEqual("", deckroutes.STUDIO)


PAIR = ":::exercise flashcard\nfront: [گربه]{tl}\nback: cat\ndirection: both-repeat\n:::"


class LinkedRouteTests(Base):
    """A both-repeat flashcard is two linked cards in a deck (TO-DO L17), over
    HTTP: what an add or a copy answers, the "linked" refusal of an edit or a
    delete that says nothing of the other side (409, naming it), and the
    drawings' owners of every card made or lost -- both sides of a pair,
    a copy, a move and a selection."""

    def setUp(self):
        super().setUp()
        self.deck()
        self.base = "/api/decks/persian/greetings"
        # the owners of a card's LaTeX drawings, recorded and not written
        own = mock.patch.object(deckroutes.latexdraw, "own_source")
        forget = mock.patch.object(deckroutes.latexdraw, "forget_owner")
        self.own, self.forget = own.start(), forget.start()
        self.addCleanup(own.stop)
        self.addCleanup(forget.stop)

    def owner(self, item_id, deck="greetings"):
        return deckroutes._latex_owner("persian", deck, item_id)

    def pair(self, markdown=PAIR, base=None):
        out = self.ok(call("POST", (base or self.base) + "/items", {"markdown": markdown}), 201)
        return out

    def test_an_add_answers_the_first_and_both_and_owns_each(self):
        out = self.pair()
        a, b = out["items"]
        self.assertEqual(a["id"], out["item"]["id"])
        self.assertEqual(("forward", "reverse", [b["id"]], [a["id"]]),
                         (a["direction"], b["direction"], a["mates"], b["mates"]))
        self.assertEqual({self.owner(a["id"]), self.owner(b["id"])},
                         {c.args[0] for c in self.own.call_args_list})
        # a card that is one exercise still answers `items`
        single = self.ok(call("POST", self.base + "/items", {"markdown": CHOICE}), 201)
        self.assertEqual([single["item"]["id"]], [i["id"] for i in single["items"]])
        self.assertEqual(3, self.own.call_count)
        self.refused(call("POST", self.base + "/items", {"markdown": PAIR}), 409, "duplicate")
        self.assertEqual(3, self.ok(call("GET", self.base))["deck"]["counts"]["total"])

    def test_a_copy_from_a_page_answers_both_and_owns_each(self):
        doc = store.create("---\ntitle: T\ntarget: fa\n---\n\n" + PAIR + "\n")
        out = self.ok(call("POST", self.base + "/copy", {
            "doc_id": doc["id"], "ordinal": 1, "subtype": "flashcard", "updated": doc["updated"]}), 201)
        a, b = out["items"]
        self.assertEqual((a["id"], 2, out["deck"]["counts"]["total"]), (out["item"]["id"], len(out["items"]), 2))
        self.assertEqual({self.owner(a["id"]), self.owner(b["id"])},
                         {c.args[0] for c in self.own.call_args_list})

    def test_an_edit_and_a_delete_that_say_nothing_of_the_other_side_are_refused(self):
        a, b = self.pair()["items"]
        item = self.base + "/items/" + a["id"]
        changed = a["markdown"].replace("back: cat", "back: kitten")
        refused = self.refused(call("PUT", item, {"markdown": changed}), 409, "linked")
        self.assertEqual([{"id": b["id"], "excerpt": "گربه", "side": "back"}], refused["detail"]["mates"])
        refused = self.refused(call("DELETE", item), 409, "linked")
        self.assertEqual("back", refused["detail"]["mates"][0]["side"])
        self.assertEqual(2, self.ok(call("GET", self.base))["deck"]["counts"]["total"])
        # nothing else says "detail"
        dup = self.refused(call("POST", self.base + "/items", {"markdown": PAIR}), 409, "duplicate")
        self.assertNotIn("detail", dup)
        self.refused(call("PUT", item, {"markdown": changed, "linked": "everyone"}), 400)
        self.refused(call("DELETE", item + "?linked=everyone"), 400)
        self.forget.assert_not_called()

    def test_change_both_and_change_only_this_one(self):
        a, b = self.pair()["items"]
        self.own.reset_mock()
        got = self.ok(call("PUT", self.base + "/items/" + a["id"],
                           {"markdown": a["markdown"].replace("back: cat", "back: kitten"), "linked": "both"}))
        self.assertEqual([b["id"]], got["item"]["mates"])
        self.assertIn("back: kitten", self.ok(call("GET", self.base + "/items/" + b["id"]))["item"]["markdown"])
        self.assertEqual({self.owner(a["id"]), self.owner(b["id"])},
                         {c.args[0] for c in self.own.call_args_list})
        alone = self.ok(call("PUT", self.base + "/items/" + b["id"],
                             {"markdown": b["markdown"].replace("kitten", "lion"), "linked": "alone"}))
        self.assertEqual(([], None), (alone["item"]["mates"], alone["item"]["link"]))
        self.assertIn("kitten", self.ok(call("GET", self.base + "/items/" + a["id"]))["item"]["markdown"])
        self.assertEqual([], self.ok(call("GET", self.base + "/items/" + a["id"]))["item"]["mates"])

    def test_delete_one_or_both_and_forget_the_owners_of_what_went(self):
        a, b = self.pair()["items"]
        self.ok(call("DELETE", self.base + "/items/" + a["id"] + "?linked=alone"))
        self.assertEqual([self.owner(a["id"])], [c.args[0] for c in self.forget.call_args_list])
        self.assertEqual([], self.ok(call("GET", self.base + "/items/" + b["id"]))["item"]["mates"])
        c, d = self.pair(PAIR.replace("cat", "dog"))["items"]
        self.forget.reset_mock()
        self.ok(call("DELETE", self.base + "/items/" + d["id"] + "?linked=both"))
        self.assertEqual({self.owner(c["id"]), self.owner(d["id"])}, {x.args[0] for x in self.forget.call_args_list})
        self.assertEqual(1, self.ok(call("GET", self.base))["deck"]["counts"]["total"])

    def test_a_selection_is_asked_once_and_every_deleted_card_is_forgotten(self):
        a, b = self.pair()["items"]
        c, d = self.pair(PAIR.replace("cat", "dog"))["items"]
        plain = self.item(self.ok(call("GET", self.base))["deck"], CHOICE)
        refused = self.refused(call("POST", self.base + "/items/bulk",
                                    {"action": "delete", "ids": [a["id"], c["id"], plain["id"]]}), 409, "linked")
        self.assertEqual(2, refused["detail"]["count"])
        self.forget.assert_not_called()
        out = self.ok(call("POST", self.base + "/items/bulk", {
            "action": "delete", "ids": [a["id"], c["id"], plain["id"]], "linked": "both"}))
        self.assertEqual(5, out["count"])
        self.assertEqual({self.owner(x) for x in (a["id"], b["id"], c["id"], d["id"], plain["id"])},
                         {x.args[0] for x in self.forget.call_args_list})
        # tags and the like are never asked about
        e, f = self.pair(PAIR.replace("cat", "cow"))["items"]
        self.ok(call("POST", self.base + "/items/bulk", {"action": "add-tag", "ids": [e["id"]], "tag": "x"}))
        out = self.ok(call("POST", self.base + "/items/bulk", {"action": "delete", "ids": [e["id"]], "linked": "alone"}))
        self.assertEqual(1, out["count"])
        self.assertEqual([], self.ok(call("GET", self.base + "/items/" + f["id"]))["item"]["mates"])

    def test_a_copy_to_another_deck_owns_what_arrived_and_a_move_forgets_what_left(self):
        a, b = self.pair()["items"]
        self.deck("Other")
        theirs = "/api/decks/persian/other"
        target = {"folder": "persian", "slug": "other"}
        self.own.reset_mock()
        out = self.ok(call("POST", self.base + "/items/bulk",
                           {"action": "copy", "ids": [a["id"], b["id"]], "target": target}))
        self.assertEqual({self.owner(i, "other") for i in out["ids"]}, {c.args[0] for c in self.own.call_args_list})
        self.assertEqual(2, len(out["ids"]))
        arrived = self.ok(call("GET", theirs + "/items/" + out["ids"][0]))["item"]
        self.assertEqual(1, len(arrived["mates"]))
        self.forget.assert_not_called()
        self.ok(call("POST", self.base + "/items/bulk", {"action": "move", "ids": [b["id"]], "target": target}))
        self.assertEqual([self.owner(b["id"])], [c.args[0] for c in self.forget.call_args_list])
        self.assertEqual([], self.ok(call("GET", self.base + "/items/" + a["id"]))["item"]["mates"])

    def test_the_study_page_holds_the_other_side_back_and_says_so(self):
        a, b = self.pair()["items"]
        first = self.ok(call("GET", self.base + "/next"))
        self.assertEqual((a["id"], [b["id"]], 0), (first["item"]["id"], first["item"]["mates"], first["buried"]))
        out = self.ok(call("POST", self.base + "/review", {"item": a["id"], "rating": "easy", "result": None}))
        self.assertEqual((True, 1, None), (out["next"]["done"], out["next"]["buried"], out["next"]["item"]))
        self.assertEqual(1, self.ok(call("GET", self.base + "/next"))["buried"])

    def test_a_phone_is_sent_one_side_of_a_pair_and_the_other_comes_with_the_next_pack(self):
        a, b = self.pair()["items"]
        plain = self.item(self.ok(call("GET", self.base))["deck"], CHOICE)
        pack = self.ok(call("POST", self.base + "/checkout", {"device": "phone", "id": "p1"}))["pack"]
        self.assertEqual([a["id"], plain["id"]], [c["item"]["id"] for c in pack["cards"]])


if __name__ == "__main__":
    unittest.main()
