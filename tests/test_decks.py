# SPDX-License-Identifier: GPL-3.0-or-later
"""The exercise deck store (markdown/app/decks.py): decks and their
exercises on disk, copying from a studio document, studying, export/import.

Every test works in a temporary exercises/ root (decks.set_dir), a temporary
studio library (store.use_library) and a temporary clip tray
(decks.set_clips_dir), all put back afterwards.  The recordings are real:
ffmpeg writes short tones into a temporary directory once (a format this
machine's ffmpeg cannot write skips the tests that need it)."""
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "markdown" / "exlex", ROOT / "markdown" / "app",
               ROOT / "lib", ROOT / "youtube" / "lib"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import audiofile  # noqa: E402
import decks      # noqa: E402
import htmlgen    # noqa: E402
import srs        # noqa: E402
import store      # noqa: E402

TEHRAN = timezone(timedelta(hours=3, minutes=30))
NOW = datetime(2026, 9, 14, 10, 0, tzinfo=TEHRAN)
TOMORROW_ROLLOVER = "2026-09-15T04:00:00+03:30"

CHOICE = (":::exercise single-choice\nprompt: Which is **hello**?\n"
          "- [x] [سلام]{tl}\n- [ ] [خداحافظ]{tl}\n:::")
FLASH = ":::exercise flashcard\nfront: [گربه]{tl}\nback: cat\n:::"
PICTURED = (":::exercise flashcard\nfront: [گربه]{tl}\nback: cat\n"
            "front-image: images/cat.png\nback-image: images/fig.pdf\n:::")
PNG = b"\x89PNG\r\n\x1a\n" + b"one"
PNG2 = b"\x89PNG\r\n\x1a\n" + b"two"
PDF = b"%PDF-1.4 not really"
SVG = b"<svg xmlns='http://www.w3.org/2000/svg'/>"

# (extension, frequency) -> the bytes of a real one-second tone
SOUNDS = {}
_SOUND_DIR = None
CODECS = {"mp3": "libmp3lame", "ogg": "libvorbis", "webm": "libopus"}


def setUpModule():
    global _SOUND_DIR
    _SOUND_DIR = tempfile.TemporaryDirectory(prefix="parseh-deck-sounds-")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return
    for ext, codec in CODECS.items():
        for freq in ((440, 660, 880) if ext == "mp3" else (440,)):
            out = Path(_SOUND_DIR.name) / ("tone-%d.%s" % (freq, ext))
            r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                                "sine=frequency=%d:duration=1" % freq, "-c:a", codec, str(out)],
                               capture_output=True)
            if r.returncode == 0 and out.is_file() and out.stat().st_size:
                SOUNDS[(ext, freq)] = out.read_bytes()
    # an MP4 with a picture track and no sound: its first bytes are an M4A's
    out = Path(_SOUND_DIR.name) / "video-only.mp4"
    r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc=duration=1:size=64x48:rate=5", "-an", "-c:v", "mpeg4", str(out)],
                       capture_output=True)
    if r.returncode == 0 and out.is_file() and out.stat().st_size:
        SOUNDS[("video-only", 0)] = out.read_bytes()


def tearDownModule():
    _SOUND_DIR.cleanup()


def sound(case, ext="mp3", freq=440):
    """A real recording, or the test is skipped: this machine cannot write it."""
    if (ext, freq) not in SOUNDS:
        case.skipTest("ffmpeg could not write a .%s here" % ext)
    return SOUNDS[(ext, freq)]

LESSON = """---
title: Lesson
target: fa
---

Intro[^n1].

:::exercise single-choice
prompt: Top question[^n1]
- [x] yes
- [ ] no
:::

> A box.
>
> :::exercise flashcard
> front: [گربه]{tl}[^n2]
> back: cat
> front-image: images/cat.png
> back-image: images/fig.pdf
> :::

:::exercise true-false
prompt: Last.
- It is. => true
:::

[^n1]: first note
[^n2]: second note
[^n3]: unused note
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.old_dir = decks.set_dir(self.root / "exercises")
        self.old_lib = store.use_library(self.root / "library")
        self.tray = self.root / "clips"
        self.old_tray = decks.set_clips_dir(self.tray)

    def tearDown(self):
        decks.set_dir(self.old_dir)
        store.use_library(self.old_lib)
        decks.set_clips_dir(self.old_tray)
        self.td.cleanup()

    def deck(self, name="Words", lang="fa"):
        s = decks.create_deck(name, lang)
        return s, (s["folder"], s["slug"])

    def doc(self, body, target="fa", title="Doc", images=None, audio=None):
        meta = store.create("---\ntitle: %s\ntarget: %s\n---\n\n%s" % (title, target, body))
        for d, files in ((store.images_dir(meta["id"]), images), (store.audio_dir(meta["id"]), audio)):
            if files:
                d.mkdir(parents=True, exist_ok=True)
                for name, data in files.items():
                    (d / name).write_bytes(data)
        return meta

    def deck_images(self, fs):
        d = decks.deck_dir(*fs) / "images"
        return sorted(os.listdir(d)) if d.is_dir() else []

    def deck_files(self, fs, kind):
        """name -> bytes of what the deck holds in images/ or audio/"""
        d = decks.deck_dir(*fs) / kind
        return {n: (d / n).read_bytes() for n in sorted(os.listdir(d))} if d.is_dir() else {}

    def in_tray(self, files):
        self.tray.mkdir(exist_ok=True)
        for name, data in files.items():
            (self.tray / name).write_bytes(data)


# ------------------------------------------------------------------ decks

class DeckTests(Base):
    def test_create_get_list_rename_options_and_delete_to_trash(self):
        s, fs = self.deck("  Common   verbs ", "fa")
        self.assertEqual(("Common verbs", "fa", "Persian", "persian", "common-verbs",
                          "persian/common-verbs"),
                         (s["name"], s["lang"], s["language"], s["folder"], s["slug"], s["path"]))
        self.assertRegex(s["id"], r"^[0-9a-f]{12}$")
        self.assertEqual(srs.settings(), s["settings"])
        self.assertEqual({"total": 0, "new": 0, "learning": 0, "review": 0}, s["counts"])
        self.assertEqual({"new": 0, "learning": 0, "review": 0}, s["study"])
        self.assertIsNone(s["next_due"])
        on_disk = json.loads((decks.deck_dir(*fs) / "deck.json").read_text("utf-8"))
        self.assertEqual((decks.FORMAT, s["id"], {}), (on_disk["format"], on_disk["id"],
                                                       on_disk["settings"]))

        self.assertEqual([s["id"]], [x["id"] for x in decks.list_decks()])
        self.assertEqual(1, len(decks.list_decks("fa")))
        self.assertEqual([], decks.list_decks("ja"))
        self.assertRaises(decks.DeckError, decks.list_decks, "xx")
        self.assertEqual(s["id"], decks.get_deck(*fs)["id"])

        renamed = decks.update_deck(*fs, name="Verbs")
        self.assertEqual(("Verbs", "common-verbs"), (renamed["name"], renamed["slug"]))
        decks.update_deck(*fs, settings={"new_per_day": 5})
        both = decks.update_deck(*fs, settings={"learning_steps": [2, 20]})
        self.assertEqual((5, [2.0, 20.0]), (both["settings"]["new_per_day"],
                                            both["settings"]["learning_steps"]))
        on_disk = json.loads((decks.deck_dir(*fs) / "deck.json").read_text("utf-8"))
        self.assertEqual({"new_per_day": 5, "learning_steps": [2.0, 20.0]}, on_disk["settings"])
        with self.assertRaisesRegex(decks.DeckError, "new_per_day"):
            decks.update_deck(*fs, settings={"new_per_day": -1})
        with self.assertRaises(decks.DeckError):
            decks.update_deck(*fs, settings=[1, 2])
        with self.assertRaises(decks.DeckError):
            decks.update_deck(*fs, name="   ")
        self.assertEqual(5, decks.get_deck(*fs)["settings"]["new_per_day"])

        decks.delete_deck(*fs)
        trash = decks.DIR / ".trash"
        gone = os.listdir(trash)
        self.assertEqual(1, len(gone))
        self.assertRegex(gone[0], r"^persian--common-verbs--\d{8}-\d{6}$")
        self.assertTrue((trash / gone[0] / "deck.json").is_file())
        self.assertEqual([], decks.list_decks())
        self.assertRaises(decks.NotFound, decks.get_deck, *fs)
        self.assertRaises(decks.NotFound, decks.delete_deck, *fs)

    def test_create_refuses_unknown_language_and_empty_name(self):
        self.assertRaisesRegex(decks.DeckError, "unknown language", decks.create_deck, "A", "xx")
        self.assertRaisesRegex(decks.DeckError, "name", decks.create_deck, " \t ", "fa")
        self.assertRaisesRegex(decks.DeckError, "name", decks.create_deck, None, "fa")
        self.assertRaisesRegex(decks.DeckError, "at most", decks.create_deck, "x" * 201, "fa")
        self.assertFalse((decks.DIR / "persian").exists())

    def test_slug_collisions_and_names_without_latin_letters(self):
        a, _ = self.deck("Verbs")
        b, _ = self.deck("verbs!")
        c, _ = self.deck("Verbs", "ja")
        self.assertEqual(["verbs", "verbs-2", "verbs"], [a["slug"], b["slug"], c["slug"]])
        self.assertEqual("japanese", c["folder"])
        p1, _ = self.deck("فعل‌ها")
        p2, _ = self.deck("اسم‌ها")
        self.assertRegex(p1["slug"], r"^deck-[0-9a-f]{8}$")
        self.assertRegex(p2["slug"], r"^deck-[0-9a-f]{8}$")
        self.assertNotEqual(p1["slug"], p2["slug"])
        self.assertEqual("فعل‌ها", decks.get_deck("persian", p1["slug"])["name"])
        self.assertEqual("isiklar", decks.slugify("Işıklar"))
        self.assertEqual("cafe-au-lait", decks.slugify("Café au lait"))
        self.assertLessEqual(len(decks.slugify("word " * 40)), 60)

    def test_deck_dir_refuses_what_is_not_a_deck(self):
        for folder, slug in (("klingon", "x"), ("Persian", "x"), ("persian", "../x"),
                             ("persian", "X"), ("persian", "a/b"), ("persian", "ok\n"),
                             ("persian", ""), (None, "x"), ("persian", None)):
            self.assertRaises(decks.NotFound, decks.deck_dir, folder, slug)
        self.assertEqual(decks.DIR / "persian" / "ok", decks.deck_dir("persian", "ok"))
        self.assertRaises(decks.NotFound, decks.get_deck, "persian", "nothing")

    def test_reads_never_create_the_store(self):
        decks.set_dir(self.root / "absent")
        self.assertEqual([], decks.list_decks())
        self.assertEqual({"decks": 0, "due": 0, "by_lang": {}}, decks.hub_stats())
        self.assertFalse((self.root / "absent").exists())

    def test_listing_skips_trash_staging_and_directories_without_a_deck(self):
        s, fs = self.deck("Real")
        parent = decks.DIR / "persian"
        (parent / "junk").mkdir()
        (parent / "broken").mkdir()
        (parent / "broken" / "deck.json").write_text("{not json", "utf-8")
        staged = parent / ".import-000000000000"
        staged.mkdir()
        (staged / "deck.json").write_bytes((decks.deck_dir(*fs) / "deck.json").read_bytes())
        (decks.DIR / ".trash" / "persian--old--20260101-000000").mkdir(parents=True)
        (decks.DIR / "klingon" / "deck").mkdir(parents=True)
        self.assertEqual([s["id"]], [x["id"] for x in decks.list_decks()])

    def test_hub_stats_sums_what_is_due(self):
        _, fa = self.deck("Persian words")
        _, ja = self.deck("Japanese words", "ja")
        decks.add_item(*fa, CHOICE)
        decks.add_item(*fa, FLASH)
        decks.add_item(*ja, ":::exercise flashcard\nfront: [猫]{tl}\nback: cat\n:::")
        decks.create_deck("Empty", "fa")
        self.assertEqual({"decks": 3, "due": 3,
                          "by_lang": {"fa": {"decks": 2, "due": 2}, "ja": {"decks": 1, "due": 1}}},
                         decks.hub_stats(now=NOW))

    def test_one_deck_that_cannot_be_counted_does_not_hide_the_rest(self):
        # OverflowError is what a time or a number at the edge of its range
        # raises; one such deck took the index, the deck API and the hub down
        _, good = self.deck("Healthy")
        _, odd = self.deck("Odd")
        decks.add_item(*good, CHOICE)
        broken = decks.add_item(*odd, FLASH)["id"]
        real = srs.queue

        def queue(entries, *args, **kw):
            entries = list(entries)
            if any(e[0] == broken for e in entries):
                raise OverflowError("date value out of range")
            return real(entries, *args, **kw)

        out = io.StringIO()
        with mock.patch.object(srs, "queue", queue), redirect_stdout(out):
            self.assertEqual(["Healthy"], [d["name"] for d in decks.list_decks(now=NOW)])
            self.assertEqual(1, decks.hub_stats(now=NOW)["decks"])
        self.assertIn("skipping persian/odd", out.getvalue())


# ------------------------------------------------------------------ exercises

class ItemTests(Base):
    KEYS = {"id", "subtype", "primitive", "label", "excerpt", "markdown", "footnotes",
            "errors", "created", "updated", "origin", "schedule", "reps", "lapses", "tags",
            "direction", "link", "mates", "steps"}

    def test_validation_refusals(self):
        _, fs = self.deck()
        boxed = "> " + CHOICE.replace("\n", "\n> ")
        cases = [
            ("", "empty"), ("\n  \n", "empty"), (None, "must be text"),
            ("just text", "not an exercise"),
            (CHOICE + "\n\n" + FLASH, "holds 2"),
            (CHOICE + "\n\nAfter.", "not one exercise"),
            ("Before.\n\n" + CHOICE, "not one exercise"),
            (CHOICE + "\n\n[^n1]: a footnote", "not one exercise"),
            ("---\n\n" + CHOICE, "not one exercise"),
            (boxed, "not one exercise"),
            (":::exercise single-choice\n- [x] a\n- [x] b\n:::", "needs attention: single-choice"),
            (":::exercise nonsense\n:::", "unknown exercise type"),
            (CHOICE[:-len("\n:::")], "closing"),
            (":::exercise flashcard\nfront: " + "x" * 70000 + "\n:::", "64 KB"),
        ]
        for md, fragment in cases:
            with self.subTest(md=(md or "")[:40]):
                self.assertRaisesRegex(decks.DeckError, fragment, decks.validate_markdown, md, "fa")
                self.assertRaisesRegex(decks.DeckError, fragment, decks.add_item, *fs, md)
        self.assertEqual([], decks.list_items(*fs))
        self.assertRaisesRegex(decks.DeckError, "unknown language",
                               decks.validate_markdown, CHOICE, "xx")

    def test_crlf_and_surrounding_blank_lines_are_normalised(self):
        _, fs = self.deck()
        messy = "\r\n  \r\n" + CHOICE.replace("\n", "\r\n") + "\r\n\r\n"
        self.assertEqual("single-choice", decks.validate_markdown(messy, "fa")["subtype"])
        self.assertEqual(CHOICE, decks.add_item(*fs, messy)["markdown"])

    def test_add_list_get_and_the_summary(self):
        s, fs = self.deck()
        a = decks.add_item(*fs, CHOICE, now=NOW)
        b = decks.add_item(*fs, FLASH, now=NOW + timedelta(seconds=1))
        self.assertEqual(self.KEYS | {"warnings"}, set(a))      # add_item's answer warns too
        self.assertEqual([], a.pop("warnings"))
        self.assertEqual(("single-choice", "choice", "Choose one answer", "Which is hello?", [],
                          srs.new_state(), 0, 0, None, "", NOW.isoformat(timespec="microseconds")),
                         (a["subtype"], a["primitive"], a["label"], a["excerpt"], a["errors"],
                          a["schedule"], a["reps"], a["lapses"], a["origin"], a["footnotes"],
                          a["created"]))
        self.assertEqual(("flashcard", "Flashcard", "گربه"), (b["subtype"], b["label"], b["excerpt"]))
        d = decks.deck_dir(*fs)
        self.assertTrue((d / "items" / (a["id"] + ".json")).is_file())
        self.assertFalse((d / "schedule" / (a["id"] + ".json")).exists())

        self.assertEqual([a["id"], b["id"]], [x["id"] for x in decks.list_items(*fs)])
        self.assertEqual(a, decks.get_item(*fs, a["id"]))
        self.assertRaises(decks.NotFound, decks.get_item, *fs, "0" * 12)
        self.assertRaises(decks.NotFound, decks.get_item, *fs, "../deck")
        counts = decks.get_deck(*fs, now=NOW)["counts"]
        self.assertEqual({"total": 2, "new": 2, "learning": 0, "review": 0}, counts)

        long = decks.add_item(*fs, ":::exercise single-choice\nprompt: %s\n- [x] a\n- [ ] b\n:::"
                              % ("[word]{tl} " * 60))["excerpt"]
        self.assertLessEqual(len(long), 160)
        self.assertTrue(long.startswith("word word") and long.endswith("…"))

    def test_a_duplicate_is_a_conflict_unless_forced(self):
        s, fs = self.deck("My deck")
        decks.add_item(*fs, CHOICE)
        with self.assertRaises(decks.Conflict) as caught:
            decks.add_item(*fs, "\n" + CHOICE.replace("\n", "  \n") + "\n")
        self.assertEqual("duplicate", caught.exception.kind)
        self.assertIn("My deck", str(caught.exception))
        decks.add_item(*fs, CHOICE, force=True)
        self.assertEqual(2, len(decks.list_items(*fs)))

    def test_update_prunes_footnotes_and_keeps_schedule_and_origin(self):
        _, fs = self.deck()
        md = ":::exercise single-choice\nprompt: Which?[^n1] Also[^n2].\n- [x] a\n- [ ] b\n:::"
        origin = {"doc_id": "lesson-123456", "doc_uid": "0123456789ab", "title": "T", "ordinal": 1}
        item = decks.add_item(*fs, md, footnotes="[^n1]: first\r\n[^n2]: second\n[^n3]: unused",
                              origin=origin, now=NOW)
        self.assertEqual("[^n1]: first\n[^n2]: second", item["footnotes"])
        reviewed = decks.review(*fs, item["id"], "good", True, now=NOW)
        self.assertEqual("learning", reviewed["schedule"]["state"])

        later = NOW + timedelta(minutes=5)
        edited = decks.update_item(*fs, item["id"], md.replace(" Also[^n2].", ""), now=later)
        self.assertEqual([], edited.pop("warnings"))
        self.assertEqual("[^n1]: first", edited["footnotes"])
        self.assertEqual(reviewed["schedule"], edited["schedule"])
        self.assertEqual(origin, edited["origin"])
        self.assertEqual((item["created"], later.isoformat(timespec="microseconds")),
                         (edited["created"], edited["updated"]))

        self.assertRaises(decks.DeckError, decks.update_item, *fs, item["id"], "nope")
        self.assertEqual(edited, decks.get_item(*fs, item["id"]))
        self.assertRaises(decks.NotFound, decks.update_item, *fs, "0" * 12, CHOICE)

    def test_duplicate_gets_a_fresh_schedule_and_delete_removes_both_files(self):
        _, fs = self.deck()
        src = decks.add_item(*fs, CHOICE, footnotes="", origin={"doc_id": "x-123456", "ordinal": 3})
        decks.review(*fs, src["id"], "good", now=NOW)
        dup = decks.duplicate_item(*fs, src["id"], now=NOW)
        self.assertNotEqual(src["id"], dup["id"])
        self.assertEqual((CHOICE, srs.new_state(), 0), (dup["markdown"], dup["schedule"], dup["reps"]))
        self.assertEqual({"doc_id": "x-123456", "ordinal": 3, "duplicate_of": src["id"]}, dup["origin"])
        plain = decks.add_item(*fs, FLASH)
        self.assertEqual({"duplicate_of": plain["id"]},
                         decks.duplicate_item(*fs, plain["id"])["origin"])

        d = decks.deck_dir(*fs)
        decks.delete_item(*fs, src["id"])
        self.assertFalse((d / "items" / (src["id"] + ".json")).exists())
        self.assertFalse((d / "schedule" / (src["id"] + ".json")).exists())
        self.assertRaises(decks.NotFound, decks.delete_item, *fs, src["id"])
        self.assertEqual(3, len(decks.list_items(*fs)))

    def test_an_origin_from_a_book_or_a_video_is_kept_only_as_links_can_use_it(self):
        _, fs = self.deck()
        book = {"book": "/books/english/tale", "label": "3.2", "title": "A tale",
                "url": "/books/english/tale/reader/#p12"}
        video = {"video": "dQw4w9WgXcQ", "time": 65.75, "label": "1:05", "title": "A film",
                 "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=65"}
        self.assertEqual(book, decks.add_item(*fs, CHOICE, origin=book)["origin"])
        self.assertEqual(video, decks.add_item(*fs, FLASH, origin=video)["origin"])
        self.assertEqual({"video": "x-y_z.1", "time": 0},
                         decks._clean_origin({"video": "x-y_z.1", "time": 0}))
        hostile = {
            "book": ["/books/../etc", "//evil.example/a/b", "/books/a", "/books/a/b/c",
                     "/books/a/..", "books/a/b", "/books/.hidden/b", 7],
            "video": ["../x", "a/b", "x" * 91, "..", "", "a b", "<script>", None],
            "time": [-1, True, "5", float("nan"), float("inf"), 10 ** 400, [3]],
            "url": ["//evil.example/x", "/\\evil.example", "javascript:alert(1)",
                    "https://evil.example/", "https://www.youtube.com.evil.example/",
                    "http://www.youtube.com/watch", "/ok\tbad", "/ok\nbad", "/" + "a" * 600,
                    " /x", "\u0000/x", 5],
            "label": [3, None, ["x"], "\ud800"],
        }
        for key, values in hostile.items():
            for value in values:
                with self.subTest(key=key, value=repr(value)[:40]):
                    self.assertIsNone(decks._clean_origin({key: value}))
        cleaned = decks._clean_origin({"label": "  a\x01b \n c " + "x" * 300, "extra": "dropped",
                                       "title": "t" * 600})
        self.assertEqual(({"label", "title"}, "ab c " + "x" * 195, 500),
                         (set(cleaned), cleaned["label"], len(cleaned["title"])))
        stored = json.loads((decks.deck_dir(*fs) / "items" / (decks.list_items(*fs)[1]["id"] + ".json"))
                            .read_text("utf-8"))["origin"]
        self.assertEqual(video, stored)

    def test_render_item(self):
        s, fs = self.deck()
        item = decks.add_item(*fs, PICTURED.replace("back: cat", "back: cat[^n1]"),
                              footnotes="[^n1]: a note")
        base = "/exercises/media/persian/%s/" % s["slug"]
        html = decks.render_item(s, item, base)
        self.assertIn('data-exercise="1"', html)
        self.assertIn('src="%simages/cat.png"' % base, html)
        self.assertIn('src="%simages/fig.pdf.svg"' % base, html)
        self.assertIn("a note", html)
        self.assertNotIn("colophon", html)
        self.assertNotIn("data-editor-preview", html)
        solved = decks.render_item(s, item, base, preview=True)
        self.assertIn('data-editor-preview="1"', solved)
        self.assertIn("ex-flashcard flipped", solved)

    def test_add_image_names_and_stores_an_uploaded_picture(self):
        _, fs = self.deck()
        images = decks.deck_dir(*fs) / "images"
        jpeg = b"\xff\xd8\xff\xe0" + b"jpeg"
        self.assertEqual("cat-photo.png", decks.add_image(*fs, "Cat Photo.PNG", PNG))
        self.assertEqual("cat-photo.png", decks.add_image(*fs, "cat photo.png", PNG))  # same bytes
        self.assertEqual("cat-photo-2.png", decks.add_image(*fs, "cat-photo.png", PNG2))
        # the extension follows the bytes, and no directory survives in the name
        self.assertEqual("evil.jpg", decks.add_image(*fs, "../../evil.png", jpeg))
        self.assertEqual("img.svg", decks.add_image(*fs, None, SVG))
        self.assertEqual("img.png", decks.add_image(*fs, "گربه.png", PNG))
        self.assertEqual("hidden.png", decks.add_image(*fs, "_.hidden.png", PNG2))
        # never the name of a PDF's twin
        self.assertEqual("x-pdf.svg", decks.add_image(*fs, "x.pdf.svg", SVG))
        self.assertEqual("fig.pdf", decks.add_image(*fs, "fig.pdf", PDF))
        self.assertEqual({"cat-photo.png": PNG, "cat-photo-2.png": PNG2, "evil.jpg": jpeg,
                          "img.svg": SVG, "img.png": PNG, "hidden.png": PNG2, "x-pdf.svg": SVG,
                          "fig.pdf": PDF},
                         {n: (images / n).read_bytes() for n in os.listdir(images)
                          if not n.endswith(".pdf.svg")})     # a twin, if PyMuPDF made one

    def test_add_image_refusals_write_nothing(self):
        _, fs = self.deck()
        saved = store.IMG_MAX
        try:
            store.IMG_MAX = 4
            self.assertRaisesRegex(decks.DeckError, "larger", decks.add_image, *fs, "a.png", PNG)
        finally:
            store.IMG_MAX = saved
        self.assertRaisesRegex(decks.DeckError, "empty", decks.add_image, *fs, "a.png", b"")
        self.assertRaisesRegex(decks.DeckError, "empty", decks.add_image, *fs, "a.png", None)
        self.assertRaisesRegex(decks.DeckError, "PNG, JPEG, SVG and PDF",
                               decks.add_image, *fs, "a.gif", b"GIF89a....")
        self.assertRaises(decks.NotFound, decks.add_image, "persian", "nope", "a.png", PNG)
        self.assertRaises(decks.NotFound, decks.add_image, "klingon", "x", "a.png", PNG)
        self.assertEqual([], self.deck_images(fs))

    def test_add_and_update_warn_of_pictures_the_deck_does_not_have(self):
        _, fs = self.deck()
        item = decks.add_item(*fs, PICTURED)
        self.assertEqual(2, len(item["warnings"]))
        self.assertTrue(item["warnings"][0].startswith("front-image: images/cat.png "))
        self.assertTrue(item["warnings"][1].startswith("back-image: images/fig.pdf "))
        self.assertNotIn("warnings", decks.get_item(*fs, item["id"]))
        decks.add_image(*fs, "cat.png", PNG)
        decks.add_image(*fs, "fig.pdf", PDF)
        self.assertEqual([], decks.update_item(*fs, item["id"], PICTURED)["warnings"])
        twin = PICTURED.replace("images/fig.pdf", "images/fig.pdf.svg")   # built when asked for
        self.assertEqual([], decks.update_item(*fs, item["id"], twin)["warnings"])
        odd = decks.update_item(*fs, item["id"], PICTURED.replace("images/cat.png", "images/Cat.png"))
        self.assertEqual(1, len(odd["warnings"]))
        self.assertIn("front-image: images/Cat.png cannot be a deck picture", odd["warnings"][0])
        self.assertEqual([], decks.add_item(*fs, CHOICE)["warnings"])


# ------------------------------------------------------------------ copying from a document

class SelectionTests(Base):
    def test_document_tags_follow_each_copied_exercise_and_export(self):
        _, fs = self.deck()
        meta = self.doc(CHOICE + "\n\n" + FLASH)
        meta = store.update_meta(meta["id"], {"tags": [" Grammar ", "Review"]})
        first = decks.copy_from_doc(*fs, meta["id"], 1, "single-choice", meta["updated"])["item"]
        second = decks.copy_from_doc(*fs, meta["id"], 2, "flashcard", meta["updated"])["item"]
        self.assertEqual(["grammar", "review"], first["tags"])
        self.assertEqual(first["tags"], second["tags"])
        copy = decks.duplicate_item(*fs, first["id"])
        self.assertEqual(first["tags"], copy["tags"])
        data, _ = decks.export_zip(*fs, False)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(["grammar", "review"],
                             json.loads(z.read("items/%s.json" % second["id"]))["tags"])

    def test_bulk_tags_keep_ids_and_schedules_until_deleted(self):
        _, fs = self.deck()
        one = decks.add_item(*fs, CHOICE, tags=["Old"])
        two = decks.add_item(*fs, FLASH)
        d = decks.deck_dir(*fs)
        schedule = d / "schedule" / (one["id"] + ".json")
        schedule.parent.mkdir(exist_ok=True)
        schedule.write_text('{"state":{"state":"review","reps":4},"history":[]}', encoding="utf-8")
        before = schedule.read_bytes()
        ids = [one["id"], two["id"]]
        self.assertEqual(2, decks.bulk_items(*fs, ids, "add-tag", " New "))
        self.assertEqual(["new", "old"], decks.get_item(*fs, one["id"])["tags"])
        self.assertEqual(["new"], decks.get_item(*fs, two["id"])["tags"])
        decks.bulk_items(*fs, ids, "remove-tag", "old")
        self.assertEqual(["new"], decks.get_item(*fs, one["id"])["tags"])
        self.assertEqual(before, schedule.read_bytes())
        self.assertEqual(2, decks.bulk_items(*fs, ids, "delete"))
        self.assertEqual([], decks.list_items(*fs))
        self.assertFalse(schedule.exists())

    def test_set_new_clears_schedule_and_history_but_keeps_exercises(self):
        _, fs = self.deck()
        one = decks.add_item(*fs, CHOICE, tags=["keep"])
        two = decks.add_item(*fs, FLASH)
        schedule = decks.deck_dir(*fs) / "schedule" / (one["id"] + ".json")
        schedule.parent.mkdir(exist_ok=True)
        schedule.write_text('{"state":{"state":"review","reps":4},"history":[{"rating":3}]}',
                            encoding="utf-8")
        self.assertEqual(2, decks.bulk_items(*fs, [one["id"], two["id"]], "set-new"))
        self.assertFalse(schedule.exists())
        self.assertEqual("new", decks.get_item(*fs, one["id"])["schedule"]["state"])
        self.assertEqual(["keep"], decks.get_item(*fs, one["id"])["tags"])
        self.assertEqual(2, len(decks.list_items(*fs)))

    def test_gloss_flashcards_copy_from_document_with_tags(self):
        _, fs = self.deck()
        meta = self.doc("[کتاب]{translit:ketâb} = *book*\n\nدرخت = *tree*")
        meta = store.update_meta(meta["id"], {"tags": ["Vocabulary"]})
        first = decks.copy_from_doc(*fs, meta["id"], 1, "gloss-flashcard", meta["updated"])["item"]
        second = decks.copy_from_doc(*fs, meta["id"], 2, "gloss-flashcard", meta["updated"])["item"]
        self.assertEqual(["vocabulary"], first["tags"])
        self.assertIn("card-type: vocab", first["markdown"])
        self.assertIn("target: کتاب", first["markdown"])
        self.assertIn("transliteration: ketâb", first["markdown"])
        self.assertIn("meaning: book", first["markdown"])
        self.assertIn("meaning: tree", second["markdown"])
        self.assertEqual("new", first["schedule"]["state"])
        with self.assertRaises(decks.Conflict):
            decks.copy_from_doc(*fs, meta["id"], 1, "gloss-flashcard", meta["updated"])

    def test_copy_and_move_to_another_deck_carry_media_tags_and_scheduling(self):
        _, source = self.deck("Source")
        _, target = self.deck("Target")
        decks.add_image(*source, "cat.png", PNG)
        decks.add_image(*target, "cat.png", PNG2)
        pictured = decks.add_item(*source, ":::exercise flashcard\nfront: cat\n"
                                  "front-image: images/cat.png\nback: animal\n:::", tags=["animals"])
        copied = decks.transfer_items(*source, [pictured["id"]], *target)
        self.assertEqual([], copied["warnings"])
        copy = decks.get_item(*target, copied["ids"][0])
        self.assertIn("front-image: images/cat-2.png", copy["markdown"])
        self.assertEqual(["animals"], copy["tags"])
        self.assertEqual(PNG, self.deck_files(target, "images")["cat-2.png"])
        self.assertEqual("new", copy["schedule"]["state"])
        self.assertEqual(1, len(decks.list_items(*source)))

        choice = decks.add_item(*source, CHOICE, tags=["practice"])
        src_schedule = decks.deck_dir(*source) / "schedule" / (choice["id"] + ".json")
        src_schedule.parent.mkdir(exist_ok=True)
        src_schedule.write_text('{"state":{"state":"review","reps":4},"history":[]}', encoding="utf-8")
        old_schedule = src_schedule.read_bytes()
        moved = decks.transfer_items(*source, [choice["id"]], *target, move=True)
        self.assertEqual(["practice"], decks.get_item(*target, moved["ids"][0])["tags"])
        self.assertEqual(old_schedule, (decks.deck_dir(*target) / "schedule" /
                                        (moved["ids"][0] + ".json")).read_bytes())
        self.assertFalse(src_schedule.exists())
        self.assertEqual([pictured["id"]], [it["id"] for it in decks.list_items(*source)])

    def test_a_copy_or_a_move_never_overwrites_the_other_decks_files(self):
        """The same names, other pictures and recordings: what comes in takes
        a name of its own, every reference follows it -- a field, a link in a
        jolly field -- and what the deck had is left as it was.  The same
        bytes again are found under the name they took, not written twice."""
        mp3, other = sound(self), sound(self, freq=660)
        _, source = self.deck("Source")
        _, target = self.deck("Target")
        _, third = self.deck("Third")
        decks.add_image(*source, "cat.png", PNG)
        decks.add_audio(*source, "hello.mp3", mp3)
        decks.add_image(*target, "cat.png", PNG2)
        decks.add_audio(*target, "hello.mp3", other)
        decks.add_image(*third, "cat.png", PNG2)
        ex = decks.add_item(*source, ":::exercise flashcard\ncard-type: vocab\ntarget: [cat]{tl}\n"
                            "meaning: animal\nfront-image: images/cat.png\nfront-audio: audio/hello.mp3\n"
                            "back-secondary: as in [audio/hello.mp3](audio/hello.mp3)\n:::")
        copied = decks.transfer_items(*source, [ex["id"]], *target)
        self.assertEqual([], copied["warnings"])
        md = decks.get_item(*target, copied["ids"][0])["markdown"]
        self.assertIn("\nfront-image: images/cat-2.png\n", md)
        self.assertIn("\nfront-audio: audio/hello-2.mp3\n", md)
        self.assertIn("as in [audio/hello-2.mp3](audio/hello-2.mp3)\n", md)
        self.assertEqual({"cat.png": PNG2, "cat-2.png": PNG}, self.deck_files(target, "images"))
        self.assertEqual({"hello.mp3": other, "hello-2.mp3": mp3}, self.deck_files(target, "audio"))
        # again: found under the names they took, nothing written twice
        again = decks.transfer_items(*source, [ex["id"]], *target)
        self.assertEqual(md, decks.get_item(*target, again["ids"][0])["markdown"])
        self.assertEqual(["cat-2.png", "cat.png"], sorted(self.deck_files(target, "images")))
        self.assertEqual(["hello-2.mp3", "hello.mp3"], sorted(self.deck_files(target, "audio")))
        # a move: renamed where the name is taken, kept where it is free
        moved = decks.transfer_items(*source, [ex["id"]], *third, move=True)
        md = decks.get_item(*third, moved["ids"][0])["markdown"]
        self.assertIn("\nfront-image: images/cat-2.png\n", md)
        self.assertIn("\nfront-audio: audio/hello.mp3\n", md)
        self.assertEqual({"cat.png": PNG2, "cat-2.png": PNG}, self.deck_files(third, "images"))
        self.assertEqual({"hello.mp3": mp3}, self.deck_files(third, "audio"))
        # and the source keeps its own files, the exercise gone from it
        self.assertEqual({"cat.png": PNG}, self.deck_files(source, "images"))
        self.assertEqual({"hello.mp3": mp3}, self.deck_files(source, "audio"))
        self.assertEqual([], decks.list_items(*source))

    def test_cram_reads_all_selected_exercises_without_scheduling(self):
        _, fs = self.deck()
        flash = decks.add_item(*fs, FLASH)
        choice = decks.add_item(*fs, CHOICE)
        before = [it["schedule"] for it in decks.list_items(*fs)]
        self.assertEqual([choice["id"], flash["id"]], [it["id"] for it in
                          decks.cram_items(*fs, [choice["id"], flash["id"]])])
        self.assertEqual(before, [it["schedule"] for it in decks.list_items(*fs)])
        self.assertFalse((decks.deck_dir(*fs) / "schedule").exists())


class CopyTests(Base):
    def test_exercise_blocks_follow_the_render_numbering(self):
        fm, blocks = decks.exercise_blocks(LESSON)
        html = htmlgen.render_document(LESSON)["html"]
        rendered = re.findall(r'data-exercise="(\d+)" data-subtype="([a-z-]+)"', html)
        self.assertEqual(["single-choice", "flashcard", "true-false"], [b["subtype"] for b in blocks])
        self.assertEqual([(str(i + 1), b["subtype"]) for i, b in enumerate(blocks)], rendered)
        self.assertTrue(blocks[1]["source"].startswith(":::exercise flashcard\nfront:"))
        self.assertEqual({"n1": "first note", "n2": "second note", "n3": "unused note"},
                         fm["_footnotes"])

    def test_copy_carries_footnotes_pictures_and_the_pdf_twin(self):
        s, fs = self.deck()
        meta = self.doc(LESSON.split("---\n\n", 1)[1], title="Lesson",
                        images={"cat.png": PNG, "fig.pdf": PDF, "fig.pdf.svg": SVG,
                                "other.png": PNG2})
        out = decks.copy_from_doc(*fs, meta["id"], 2, "flashcard", meta["updated"], now=NOW)
        item = out["item"]
        self.assertEqual([], out["warnings"])
        self.assertEqual(decks.exercise_blocks(store.get(meta["id"])[1])[1][1]["source"],
                         item["markdown"])
        self.assertEqual("[^n2]: second note", item["footnotes"])
        self.assertEqual({"doc_id": meta["id"], "doc_uid": meta["uid"], "title": "Lesson",
                          "ordinal": 2}, item["origin"])
        self.assertEqual(["cat.png", "fig.pdf", "fig.pdf.svg"], self.deck_images(fs))
        images = decks.deck_dir(*fs) / "images"
        self.assertEqual((PNG, PDF, SVG), tuple((images / n).read_bytes()
                                               for n in ("cat.png", "fig.pdf", "fig.pdf.svg")))

        first = decks.copy_from_doc(*fs, meta["id"], 1, "single-choice", None, now=NOW)["item"]
        self.assertEqual("[^n1]: first note", first["footnotes"])
        with self.assertRaises(decks.Conflict) as caught:
            decks.copy_from_doc(*fs, meta["id"], 2, "flashcard", meta["updated"])
        self.assertEqual("duplicate", caught.exception.kind)
        again = decks.copy_from_doc(*fs, meta["id"], 2, "flashcard", meta["updated"], force=True)
        self.assertEqual(item["markdown"], again["item"]["markdown"])
        self.assertEqual(["cat.png", "fig.pdf", "fig.pdf.svg"], self.deck_images(fs))
        self.assertEqual(3, len(decks.list_items(*fs)))

    def test_copy_carries_an_exercise_own_pictures_and_the_export_holds_them(self):
        _, fs = self.deck()
        meta = self.doc(":::exercise single-choice\nprompt: Where?\n"
                        "image: images/map.png\nimage-answer: images/key.png\n"
                        "- [x] north\n- [ ] south\n:::",
                        images={"map.png": PNG, "key.png": PNG2})
        out = decks.copy_from_doc(*fs, meta["id"], 1, "single-choice", meta["updated"], now=NOW)
        self.assertEqual([], out["warnings"])
        self.assertEqual(["key.png", "map.png"], self.deck_images(fs))
        images = decks.deck_dir(*fs) / "images"
        self.assertEqual((PNG, PNG2), ((images / "map.png").read_bytes(),
                                       (images / "key.png").read_bytes()))
        data, _name = decks.export_zip(*fs, False)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual({decks.MANIFEST, "items/%s.json" % out["item"]["id"],
                              "images/map.png", "images/key.png"}, set(z.namelist()))
        # a picture the document does not have keeps its path and is named
        gone = self.doc(":::exercise true-false\nprompt: So?\n"
                        "image: images/missing.png\n- It is. => true\n:::")
        warned = decks.copy_from_doc(*fs, gone["id"], 1, "true-false", gone["updated"], now=NOW)
        self.assertEqual(["images/missing.png is missing from the document; the path was kept"],
                         warned["warnings"])
        self.assertIn("image: images/missing.png", warned["item"]["markdown"])

    def test_copy_carries_pictures_in_matching_rows(self):
        _, fs = self.deck()
        meta = self.doc(":::exercise match-translations\n"
                        "prompt: Match pictures with labels\n"
                        "- ![snow](images/snow.jpg) => [برف]{tl}\n"
                        "- [گرم]{tl} => ![warm](images/warm.jpg)\n:::",
                        images={"snow.jpg": PNG, "warm.jpg": PNG2})
        out = decks.copy_from_doc(*fs, meta["id"], 1, "match-translations",
                                  meta["updated"], now=NOW)
        self.assertEqual([], out["warnings"])
        self.assertEqual(["snow.jpg", "warm.jpg"], self.deck_images(fs))
        html = decks.render_item(decks.get_deck(*fs), out["item"], "/d/")
        self.assertIn('src="/d/images/snow.jpg"', html)
        self.assertIn('src="/d/images/warm.jpg"', html)

    def test_copy_carries_an_exercise_own_recordings_and_the_export_holds_them(self):
        """The picture test over again, for the recordings that are their
        twins: copied into the deck, in the export, and a missing one keeping
        its path with a word about it."""
        mp3, other = sound(self), sound(self, "mp3", 660)
        _, fs = self.deck()
        meta = self.doc(":::exercise single-choice\nprompt: What do you hear?\n"
                        "audio: audio/q.mp3 {start=2 end=4}\naudio-answer: audio/a.mp3\n"
                        "- [x] north\n- [ ] south\n:::",
                        audio={"q.mp3": mp3, "a.mp3": other})
        out = decks.copy_from_doc(*fs, meta["id"], 1, "single-choice", meta["updated"], now=NOW)
        self.assertEqual([], out["warnings"])
        self.assertEqual({"a.mp3": other, "q.mp3": mp3}, self.deck_files(fs, "audio"))
        # the clip rides along with the path it belongs to
        self.assertIn("audio: audio/q.mp3 {start=2 end=4}", out["item"]["markdown"])
        data, _name = decks.export_zip(*fs, False)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual({decks.MANIFEST, "items/%s.json" % out["item"]["id"],
                              "audio/q.mp3", "audio/a.mp3"}, set(z.namelist()))
        gone = self.doc(":::exercise true-false\nprompt: So?\n"
                        "audio: audio/missing.mp3\n- It is. => true\n:::")
        warned = decks.copy_from_doc(*fs, gone["id"], 1, "true-false", gone["updated"], now=NOW)
        self.assertEqual(["audio/missing.mp3 is missing from the document; the path was kept"],
                         warned["warnings"])
        self.assertIn("audio: audio/missing.mp3", warned["item"]["markdown"])

    def flash_doc(self, back, data):
        return self.doc(":::exercise flashcard\nfront: [گربه]{tl}\nback: %s\n"
                        "front-image: images/cat.png\n:::" % back, images={"cat.png": data})

    def test_a_different_picture_of_the_same_name_is_renamed_in_its_field(self):
        _, fs = self.deck()
        a, b, c = self.flash_doc("cat", PNG), self.flash_doc("dog", PNG2), self.flash_doc("kitten", PNG)
        decks.copy_from_doc(*fs, a["id"], 1, "flashcard", a["updated"])
        second = decks.copy_from_doc(*fs, b["id"], 1, "flashcard", b["updated"])["item"]
        self.assertIn("\nfront-image: images/cat-2.png\n", second["markdown"])
        self.assertIn("\nback: dog\n", second["markdown"])
        third = decks.copy_from_doc(*fs, c["id"], 1, "flashcard", c["updated"])["item"]
        self.assertIn("\nfront-image: images/cat.png\n", third["markdown"])
        self.assertEqual(["cat-2.png", "cat.png"], self.deck_images(fs))
        images = decks.deck_dir(*fs) / "images"
        self.assertEqual((PNG, PNG2), ((images / "cat.png").read_bytes(),
                                       (images / "cat-2.png").read_bytes()))

    def test_a_missing_picture_keeps_its_path_and_warns(self):
        _, fs = self.deck()
        meta = self.doc(":::exercise flashcard\nfront: x\nback: y\nfront-image: images/nope.png\n:::")
        out = decks.copy_from_doc(*fs, meta["id"], 1, "flashcard", meta["updated"])
        self.assertEqual(1, len(out["warnings"]))
        self.assertIn("images/nope.png", out["warnings"][0])
        self.assertIn("front-image: images/nope.png", out["item"]["markdown"])
        self.assertEqual([], self.deck_images(fs))

    def test_stale_pages_other_languages_and_broken_exercises_are_refused(self):
        s, fs = self.deck("Persian deck")
        meta = self.doc(LESSON.split("---\n\n", 1)[1], images={"cat.png": PNG})

        def stale(*args):
            with self.assertRaises(decks.Conflict) as caught:
                decks.copy_from_doc(*fs, meta["id"], *args)
            self.assertEqual("stale", caught.exception.kind)

        stale(2, "flashcard", "2000-01-01T00:00:00")
        stale(4, "single-choice", meta["updated"])
        stale(0, "true-false", meta["updated"])
        stale(-1, "true-false", meta["updated"])
        stale(1, "flashcard", meta["updated"])
        # an unknown deck is a 404 before the page's freshness is looked at
        self.assertRaises(decks.NotFound, decks.copy_from_doc, "persian", "nope", meta["id"], 1,
                          "single-choice", "2000-01-01T00:00:00")
        self.assertRaises(decks.DeckError, decks.copy_from_doc, *fs, meta["id"], "one",
                          "single-choice", None)
        self.assertRaises(KeyError, decks.copy_from_doc, *fs, "missing-000000", 1,
                          "single-choice", None)

        _, ja = self.deck("Japanese deck", "ja")
        with self.assertRaisesRegex(decks.DeckError, "Persian.*Japanese deck.*Japanese"):
            decks.copy_from_doc(*ja, meta["id"], 1, "single-choice", meta["updated"])

        broken = self.doc(":::exercise single-choice\n- [x] a\n- [x] b\n:::")
        self.assertRaisesRegex(decks.DeckError, "needs attention", decks.copy_from_doc,
                               *fs, broken["id"], 1, "single-choice", broken["updated"])
        self.assertEqual([], decks.list_items(*fs) + decks.list_items(*ja))
        self.assertEqual([], self.deck_images(fs))

    def test_footnotes_cited_by_footnotes_come_along(self):
        _, fs = self.deck()
        meta = self.doc(":::exercise single-choice\nprompt: Pick one[^a]\n- [x] yes\n- [ ] no\n:::\n\n"
                        "[^a]: see also [^b]\n[^b]: the nested note\n[^d]: unused")
        item = decks.copy_from_doc(*fs, meta["id"], 1, "single-choice", meta["updated"])["item"]
        chain = "[^a]: see also [^b]\n[^b]: the nested note"
        self.assertEqual(chain, item["footnotes"])
        self.assertIn("the nested note", decks.render_item(decks.get_deck(*fs), item, "/x/"))
        edited = decks.update_item(*fs, item["id"], item["markdown"].replace("Pick one", "Choose"))
        self.assertEqual(chain, edited["footnotes"])
        # notes citing each other in a ring are each taken once (not rendered
        # here: htmlgen itself does not survive such a ring)
        ring = "[^a]: see [^b]\n[^b]: after [^c]\n[^c]: which cites [^a] again\n[^d]: unused"
        added = decks.add_item(*fs, CHOICE.replace("hello**?", "hello**?[^b]"), footnotes=ring)
        self.assertEqual("[^b]: after [^c]\n[^c]: which cites [^a] again\n[^a]: see [^b]",
                         added["footnotes"])

    def test_an_ordinal_in_other_digits_is_a_user_error(self):
        _, fs = self.deck()
        meta = self.doc(CHOICE)
        for ordinal in ("²", "١", "1.0", "1x", "", "-1", 1.0, None):
            with self.subTest(ordinal=ordinal):
                self.assertRaisesRegex(decks.DeckError, "whole number", decks.copy_from_doc,
                                       *fs, meta["id"], ordinal, "single-choice", meta["updated"])
        self.assertEqual([], decks.list_items(*fs))
        decks.copy_from_doc(*fs, meta["id"], " 1 ", "single-choice", meta["updated"])
        self.assertEqual(1, len(decks.list_items(*fs)))

    def test_a_pdf_and_a_stand_alone_svg_never_share_a_twin_name(self):
        # htmlgen shows images/x.pdf through images/x.pdf.svg: a PDF copied
        # beside an unrelated x.pdf.svg displayed that other picture
        _, fs = self.deck()
        images = decks.deck_dir(*fs) / "images"
        lone, twin_b = b"<svg>stand-alone A</svg>", b"<svg>twin of B</svg>"

        def card(back, path, files):
            meta = self.doc(":::exercise flashcard\nfront: x\nback: %s\nfront-image: images/%s\n:::"
                            % (back, path), images=files)
            return decks.copy_from_doc(*fs, meta["id"], 1, "flashcard", meta["updated"])["item"]

        card("a", "x.pdf.svg", {"x.pdf.svg": lone})
        b = card("b", "x.pdf", {"x.pdf": PDF, "x.pdf.svg": twin_b})
        self.assertIn("front-image: images/x-2.pdf\n", b["markdown"])
        again = card("b2", "x.pdf", {"x.pdf": PDF, "x.pdf.svg": twin_b})    # the same PDF: reused
        self.assertIn("front-image: images/x-2.pdf\n", again["markdown"])

        card("c", "y.pdf", {"y.pdf": PDF + b"y"})          # no twin yet: built when asked for
        d = card("d", "y.pdf.svg", {"y.pdf.svg": lone})
        self.assertIn("front-image: images/y.pdf-2.svg\n", d["markdown"])
        self.assertEqual({"x.pdf.svg": lone, "x-2.pdf": PDF, "x-2.pdf.svg": twin_b,
                          "y.pdf": PDF + b"y", "y.pdf-2.svg": lone},
                         {n: (images / n).read_bytes() for n in os.listdir(images)})

    def test_copy_from_notes_beside_a_book_or_a_video(self):
        _, fs = self.deck()
        own, notes = self.root / "library", self.root / "notes"
        store.use_library(notes)
        meta = self.doc(":::exercise flashcard\nfront: [گربه]{tl}[^n1]\nback: cat\n"
                        "front-image: images/cat.png\n:::\n\n[^n1]: a note", images={"cat.png": PNG})
        store.use_library(own)
        self.assertRaises(KeyError, decks.copy_from_doc, *fs, meta["id"], 1, "flashcard", None)

        prefix = "/books/persian/some-book/notes"
        out = decks.copy_from_doc(*fs, meta["id"], 1, "flashcard", meta["updated"],
                                  library=notes, source=prefix)
        self.assertEqual(own, store.lib())
        self.assertEqual({"doc_id": meta["id"], "doc_uid": meta["uid"], "title": "Doc",
                          "ordinal": 1, "source": prefix}, out["item"]["origin"])
        self.assertEqual("[^n1]: a note", out["item"]["footnotes"])
        self.assertEqual(["cat.png"], self.deck_images(fs))
        self.assertEqual(out["item"]["origin"], decks.get_item(*fs, out["item"]["id"])["origin"])

        self.assertRaises(KeyError, decks.copy_from_doc, *fs, "missing-000000", 1, "flashcard",
                          None, library=notes, source=prefix)
        self.assertEqual(own, store.lib())
        for bad in ("//evil.example/notes", "javascript:alert(1)", "/books/../x", "notes", ""):
            with self.subTest(source=bad):
                self.assertRaisesRegex(decks.DeckError, "not on this shelf", decks.copy_from_doc,
                                       *fs, meta["id"], 1, "flashcard", None, force=True,
                                       library=notes, source=bad)
        self.assertEqual(own, store.lib())
        self.assertEqual(1, len(decks.list_items(*fs)))
        # an origin from elsewhere (an import) keeps a source only if it is a path here
        kept = decks.add_item(*fs, CHOICE, origin={"doc_id": "a-123456",
                                                   "source": "/youtube/v/abc_DEF-12/notes"})
        dropped = decks.add_item(*fs, FLASH, origin={"doc_id": "a-123456",
                                                     "source": "javascript:alert(1)"})
        self.assertEqual("/youtube/v/abc_DEF-12/notes", kept["origin"]["source"])
        self.assertEqual({"doc_id": "a-123456"}, dropped["origin"])


# ------------------------------------------------------------------ pictures and recordings

JOLLY = """:::exercise flashcard
card-type: jolly
front-primary: |
  ![a cat](images/x.png)

  ![](audio/y.mp3){width=40}

  **Listen**[^n1], not to xaudio/y.mp3 nor audio/y.mp3x
back-primary: a cat
back-secondary: see [audio/y.mp3](audio/y.mp3).
:::"""
VOCAB_AUDIO = """:::exercise flashcard
card-type: vocab
target: [گربه]{tl}
meaning: cat
front-audio: audio/y.mp3
back-audio: audio/gone.mp3
:::"""


class MediaTests(Base):
    """Pictures and recordings named anywhere in an exercise: in a field, in
    a line of a jolly card's `|` block, in a footnote."""

    def test_copy_brings_pictures_and_recordings_named_anywhere(self):
        mp3, other_mp3, ogg = sound(self), sound(self, "mp3", 660), sound(self, "ogg")
        _, fs = self.deck()
        # the deck already holds other files under two of the names
        decks.add_image(*fs, "x.png", PNG2)
        self.assertEqual("y.mp3", decks.add_audio(*fs, "y.mp3", other_mp3))
        meta = self.doc(JOLLY + "\n\n" + VOCAB_AUDIO
                        + "\n\n[^n1]: said as in audio/z.ogg, and slowly in audio/y.mp3.",
                        images={"x.png": PNG}, audio={"y.mp3": mp3, "z.ogg": ogg})

        out = decks.copy_from_doc(*fs, meta["id"], 1, "flashcard", meta["updated"], now=NOW)
        item = out["item"]
        # y.mp3x is a name of its own (the right edge), and no recording's
        self.assertEqual(["audio/y.mp3x: only lower-case MP3, M4A, AAC, Ogg, Opus, WAV, FLAC and WebM "
                          "names can be copied; the path was kept"], out["warnings"])
        self.assertEqual([], item["errors"])
        md = item["markdown"]
        # renamed where each is a whole reference, and nowhere else
        self.assertIn("  ![a cat](images/x-2.png)\n", md)
        self.assertIn("  ![](audio/y-2.mp3){width=40}\n", md)
        self.assertIn("not to xaudio/y.mp3 nor audio/y.mp3x", md)
        self.assertIn("back-secondary: see [audio/y-2.mp3](audio/y-2.mp3).", md)
        # and in the note, where a renamed one is written anew too
        self.assertEqual("[^n1]: said as in audio/z.ogg, and slowly in audio/y-2.mp3.",
                         item["footnotes"])
        self.assertEqual({"x.png": PNG2, "x-2.png": PNG}, self.deck_files(fs, "images"))
        self.assertEqual({"y.mp3": other_mp3, "y-2.mp3": mp3, "z.ogg": ogg},
                         self.deck_files(fs, "audio"))
        html = decks.render_item(decks.get_deck(*fs), item, "/d/")
        self.assertIn('<audio controls preload="metadata" src="/d/audio/y-2.mp3"', html)
        self.assertIn('src="/d/images/x-2.png"', html)

        # the vocabulary card: its recording is the one already copied (the
        # same bytes, reused under y-2.mp3); the one the document lacks warns
        out = decks.copy_from_doc(*fs, meta["id"], 2, "flashcard", meta["updated"], now=NOW)
        self.assertIn("\nfront-audio: audio/y-2.mp3\n", out["item"]["markdown"])
        self.assertIn("\nback-audio: audio/gone.mp3\n", out["item"]["markdown"])
        self.assertEqual(["audio/gone.mp3 is missing from the document; the path was kept"],
                         out["warnings"])
        self.assertEqual(["y-2.mp3", "y.mp3", "z.ogg"], sorted(self.deck_files(fs, "audio")))
        html = decks.render_item(decks.get_deck(*fs), out["item"], "/d/")
        self.assertIn('<span class="ex-card-audio" data-side="front"><audio preload="metadata" '
                      'src="/d/audio/y-2.mp3"></audio>', html)

    def test_a_copy_refused_as_a_duplicate_writes_no_file(self):
        mp3 = sound(self)
        _, fs = self.deck()
        meta = self.doc(VOCAB_AUDIO.replace("audio/gone.mp3", "audio/y.mp3"), audio={"y.mp3": mp3})
        decks.copy_from_doc(*fs, meta["id"], 1, "flashcard", meta["updated"])
        shutil.rmtree(decks.deck_dir(*fs) / "audio")
        with self.assertRaises(decks.Conflict):
            decks.copy_from_doc(*fs, meta["id"], 1, "flashcard", meta["updated"])
        self.assertEqual({}, self.deck_files(fs, "audio"))

    def test_names_a_deck_cannot_hold_are_kept_and_warned_of(self):
        _, fs = self.deck()
        meta = self.doc(":::exercise flashcard\ncard-type: jolly\nfront-primary: |\n"
                        "  ![](audio/Loud.MP3)\n  hi\nback-primary: audio/notes.txt and "
                        "images/Big.PNG, an audio/video lesson\n:::",
                        audio={"Loud.MP3": b"ID3" + b"\0" * 64})
        out = decks.copy_from_doc(*fs, meta["id"], 1, "flashcard", meta["updated"])
        self.assertEqual(
            ["audio/Loud.MP3: only lower-case MP3, M4A, AAC, Ogg, Opus, WAV, FLAC and WebM names "
             "can be copied; the path was kept",
             "audio/notes.txt: only lower-case MP3, M4A, AAC, Ogg, Opus, WAV, FLAC and WebM names "
             "can be copied; the path was kept",
             "images/Big.PNG: only lower-case PNG, JPEG, SVG and PDF names can be copied; "
             "the path was kept"], out["warnings"])
        self.assertEqual(({}, {}), (self.deck_files(fs, "audio"), self.deck_files(fs, "images")))
        # a file in the document that is not a recording stays behind
        meta = self.doc(VOCAB_AUDIO.replace("back-audio: audio/gone.mp3\n", ""),
                        audio={"y.mp3": b"not a recording, whatever its name says"})
        out = decks.copy_from_doc(*fs, meta["id"], 1, "flashcard", meta["updated"])
        self.assertEqual(["audio/y.mp3 is not a recording; the path was kept"], out["warnings"])
        self.assertEqual({}, self.deck_files(fs, "audio"))

    def test_add_item_brings_what_it_names_from_the_clip_tray(self):
        mp3, webm = sound(self), sound(self, "webm")
        _, fs = self.deck()
        self.in_tray({"word-a1b2c3.mp3": mp3, "frame-d4e5f6.png": PNG, "said-0f0f0f.webm": webm,
                      "fake-000000.mp3": b"text, not a recording, under a recording's name"})
        tray_before = {n: (self.tray / n).read_bytes() for n in os.listdir(self.tray)}
        md = (":::exercise flashcard\ncard-type: jolly\nfront-primary: |\n"
              "  ![](images/frame-d4e5f6.png)\n\n  ![](audio/word-a1b2c3.mp3)\n\n  [کتاب]{tl}[^n1]\n"
              "back-primary: |\n  ![](audio/fake-000000.mp3)\n\n  book\n"
              "back-secondary: audio/absent-111111.mp3\n:::")
        item = decks.add_item(*fs, md, footnotes="[^n1]: heard in audio/said-0f0f0f.webm\n"
                                                 "[^n2]: unused, audio/never-222222.mp3")
        self.assertEqual({"word-a1b2c3.mp3": mp3, "said-0f0f0f.webm": webm},
                         self.deck_files(fs, "audio"))
        self.assertEqual({"frame-d4e5f6.png": PNG}, self.deck_files(fs, "images"))
        self.assertEqual(md, item["markdown"])
        self.assertEqual(
            ["back-primary: audio/fake-000000.mp3 is not among this deck's recordings: "
             "upload it, or the card plays nothing",
             "back-secondary: audio/absent-111111.mp3 is not among this deck's recordings: "
             "upload it, or the card plays nothing"], item["warnings"])
        self.assertEqual(tray_before, {n: (self.tray / n).read_bytes() for n in os.listdir(self.tray)},
                         "the tray is left as it was: a clip may go elsewhere too")

        # refused (a duplicate, an exercise that is not sound): nothing comes
        # in, though the tray now holds what it names
        late = (":::exercise flashcard\ncard-type: jolly\nfront-primary: |\n"
                "  ![](audio/late-333333.mp3)\n\n  late\nback-primary: late\n:::")
        self.assertEqual(["front-primary: audio/late-333333.mp3 is not among this deck's "
                          "recordings: upload it, or the card plays nothing"],
                         decks.add_item(*fs, late)["warnings"])
        self.in_tray({"late-333333.mp3": mp3})
        with self.assertRaises(decks.Conflict):
            decks.add_item(*fs, late)
        with self.assertRaises(decks.DeckError):
            decks.add_item(*fs, ":::exercise flashcard\ncard-type: jolly\nfront-primary: |\n"
                                "  ![](audio/late-333333.mp3)\n:::")
        self.assertNotIn("late-333333.mp3", sorted(self.deck_files(fs, "audio")))
        # forced, the same exercise goes in, and what it names with it
        self.assertEqual([], decks.add_item(*fs, late, force=True)["warnings"])
        self.assertEqual(mp3, self.deck_files(fs, "audio")["late-333333.mp3"])

    def test_update_item_brings_from_the_tray_and_warns_of_the_rest(self):
        mp3 = sound(self)
        _, fs = self.deck()
        item = decks.add_item(*fs, FLASH)
        self.in_tray({"hello-abcdef.mp3": mp3})
        md = FLASH.replace("back: cat", "back: cat\nfront-audio: audio/hello-abcdef.mp3\n"
                                        "back-image: images/nope.png")
        edited = decks.update_item(*fs, item["id"], md)
        self.assertEqual({"hello-abcdef.mp3": mp3}, self.deck_files(fs, "audio"))
        self.assertEqual(["back-image: images/nope.png is not among this deck's pictures: upload it, "
                          "or the card shows a broken picture"], edited["warnings"])
        # the deck's own file of a name wins over the tray's
        self.in_tray({"hello-abcdef.mp3": sound(self, "mp3", 880)})
        self.assertEqual([], decks.update_item(*fs, item["id"], md.replace(
            "\nback-image: images/nope.png", ""))["warnings"])
        self.assertEqual({"hello-abcdef.mp3": mp3}, self.deck_files(fs, "audio"))
        odd = decks.update_item(*fs, item["id"], md.replace("hello-abcdef.mp3", "Hello.MP3"))
        self.assertIn("front-audio: audio/Hello.MP3 cannot be a deck recording: only lower-case MP3",
                      odd["warnings"][0])

    def test_footnotes_are_searched_and_warned_of_without_a_field(self):
        _, fs = self.deck()
        item = decks.add_item(*fs, CHOICE.replace("hello**?", "hello**?[^n1]"),
                              footnotes="[^n1]: listen: audio/missing.mp3, or look: images/cat.png")
        self.assertEqual(["audio/missing.mp3 is not among this deck's recordings: upload it, "
                          "or the card plays nothing",
                          "images/cat.png is not among this deck's pictures: upload it, "
                          "or the card shows a broken picture"], item["warnings"])

    def test_add_audio_names_and_stores_an_uploaded_recording(self):
        mp3, mp3b, ogg, webm = sound(self), sound(self, "mp3", 660), sound(self, "ogg"), sound(self, "webm")
        _, fs = self.deck()
        self.assertEqual("hello-there.mp3", decks.add_audio(*fs, "Hello There!.MP3", mp3))
        self.assertEqual("hello-there.mp3", decks.add_audio(*fs, "hello there.mp3", mp3))  # same bytes
        self.assertEqual("hello-there-2.mp3", decks.add_audio(*fs, "hello-there.mp3", mp3b))
        # the extension follows the bytes, and no directory survives in the name
        self.assertEqual("evil.ogg", decks.add_audio(*fs, "../../evil.mp3", ogg))
        self.assertEqual("said.webm", decks.add_audio(*fs, "said.wav", webm))
        self.assertEqual("audio.mp3", decks.add_audio(*fs, "سلام.mp3", mp3b))
        self.assertEqual("audio-2.mp3", decks.add_audio(*fs, None, mp3))
        self.assertEqual({"hello-there.mp3": mp3, "hello-there-2.mp3": mp3b, "evil.ogg": ogg,
                          "said.webm": webm, "audio.mp3": mp3b, "audio-2.mp3": mp3},
                         self.deck_files(fs, "audio"))

    def test_add_audio_refusals_write_nothing(self):
        mp3 = sound(self)
        _, fs = self.deck()
        with mock.patch.object(audiofile, "MAX_BYTES", len(mp3) - 1):
            self.assertRaisesRegex(decks.DeckError, "larger than", decks.add_audio, *fs, "a.mp3", mp3)
        self.assertRaisesRegex(decks.DeckError, "empty", decks.add_audio, *fs, "a.mp3", b"")
        self.assertRaisesRegex(decks.DeckError, "empty", decks.add_audio, *fs, "a.mp3", None)
        utf16 = b"\xff\xfe" + ("Only words, and no recording.\n" * 20).encode("utf-16-le")
        for data in (PNG, b"plain text, long enough to be looked at", utf16):
            self.assertRaisesRegex(decks.DeckError, "only MP3, M4A, AAC, Ogg, Opus, WAV, FLAC and WebM",
                                   decks.add_audio, *fs, "a.mp3", data)
        # an MP4 by its first bytes, and a film with no sound track decoded
        self.assertRaisesRegex(decks.DeckError, "^the recording holds no sound$",
                               decks.add_audio, *fs, "videoonly.mp3", sound(self, "video-only", 0))
        self.assertRaises(decks.NotFound, decks.add_audio, "persian", "nope", "a.mp3", mp3)
        self.assertRaises(decks.NotFound, decks.add_audio, "klingon", "x", "a.mp3", mp3)
        self.assertEqual({}, self.deck_files(fs, "audio"))

    def test_audio_file(self):
        mp3 = sound(self)
        _, fs = self.deck()
        decks.add_audio(*fs, "word.mp3", mp3)
        self.assertEqual(mp3, decks.audio_file(*fs, "word.mp3").read_bytes())
        (decks.deck_dir(*fs) / "audio" / "notes.txt").write_text("not served", "utf-8")
        for name in ("missing.mp3", "../deck.json", "deck.json", "Word.mp3", "notes.txt", "",
                     "../audio/word.mp3", None):
            self.assertRaises(decks.NotFound, decks.audio_file, *fs, name)
        self.assertRaises(decks.NotFound, decks.audio_file, "persian", "nope", "word.mp3")

    def test_references_and_their_rewriting_keep_both_edges(self):
        text = ("audio/a.mp3 xaudio/a.mp3 audio/a.mp3x /audio/a.mp3 (audio/a.mp3) "
                "audio/a.mp3. images/a.mp3 audio/video audio/a.mp3-b")
        refs = [(k, n, text[s:e]) for k, n, s, e in decks._media_refs(text)]
        self.assertEqual([("audio", "a.mp3", "a.mp3"), ("audio", "a.mp3x", "a.mp3x"),
                          ("audio", "a.mp3", "a.mp3"), ("audio", "a.mp3", "a.mp3"),
                          ("images", "a.mp3", "a.mp3"), ("audio", "a.mp3-b", "a.mp3-b")], refs)
        self.assertEqual("audio/b.mp3 xaudio/a.mp3 audio/a.mp3x /audio/a.mp3 (audio/b.mp3) "
                         "audio/b.mp3. images/a.mp3 audio/video audio/a.mp3-b",
                         decks._rename_refs(text, {("audio", "a.mp3"): "b.mp3"}))

    def test_the_excerpt_says_what_the_card_says_without_its_media(self):
        _, fs = self.deck()
        item = decks.add_item(*fs, ":::exercise flashcard\ncard-type: jolly\nfront-primary: |\n"
                                   "  ![a picture](images/x.png){width=30}\n\n  ![](audio/y.mp3)\n\n"
                                   "  ### [سلام]{tl}\n\n  - said on arriving\n\n  > at any hour\n"
                                   "back-primary: hello\n:::")
        self.assertEqual("سلام said on arriving at any hour", item["excerpt"])
        only = decks.add_item(*fs, ":::exercise flashcard\ncard-type: jolly\n"
                                   "front-primary: ![](audio/y.mp3)\nfront-secondary: heard it?\n"
                                   "back-primary: yes\n:::")
        self.assertEqual("heard it?", only["excerpt"])
        self.assertEqual("an audio/video lesson",
                         decks._plain("an audio/video lesson audio/y.mp3"))


# ------------------------------------------------------------------ studying

class StudyTests(Base):
    def test_learning_into_review_with_counts(self):
        s, fs = self.deck()
        a = decks.add_item(*fs, CHOICE, now=NOW)["id"]
        b = decks.add_item(*fs, FLASH, now=NOW + timedelta(seconds=1))["id"]

        n = decks.next_card(*fs, now=NOW)
        self.assertEqual((False, a), (n["done"], n["item"]["id"]))
        self.assertEqual({"new": 2, "learning": 0, "review": 0}, n["counts"])
        self.assertEqual(("1m", "6m", "10m"), tuple(n["intervals"][r] for r in ("again", "hard", "good")))
        self.assertRegex(n["intervals"]["easy"], r"^[345]d$")

        self.assertEqual("learning", decks.review(*fs, a, "good", True, now=NOW)["schedule"]["state"])
        n = decks.next_card(*fs, now=NOW)
        self.assertEqual((b, {"new": 1, "learning": 1, "review": 0}), (n["item"]["id"], n["counts"]))

        decks.review(*fs, b, "again", None, now=NOW)
        n = decks.next_card(*fs, now=NOW + timedelta(minutes=2))
        self.assertEqual((b, {"new": 0, "learning": 2, "review": 0}), (n["item"]["id"], n["counts"]))
        decks.review(*fs, b, "good", None, now=NOW + timedelta(minutes=2))

        at = NOW + timedelta(minutes=11)
        self.assertEqual(a, decks.next_card(*fs, now=at)["item"]["id"])
        graduated = decks.review(*fs, a, "good", True, now=at)["schedule"]
        self.assertEqual(("review", 1, 2.5, TOMORROW_ROLLOVER),
                         (graduated["state"], graduated["interval"], graduated["ease"], graduated["due"]))

        n = decks.next_card(*fs, now=at)          # b is due in a minute: learn ahead
        self.assertEqual((b, {"new": 0, "learning": 1, "review": 0}), (n["item"]["id"], n["counts"]))
        decks.review(*fs, b, "easy", None, now=at)
        n = decks.next_card(*fs, now=at)
        self.assertEqual((True, None, None, TOMORROW_ROLLOVER),
                         (n["done"], n["item"], n["intervals"], n["next_due"]))
        self.assertEqual({"new": 0, "learning": 0, "review": 0}, n["counts"])

        tomorrow = datetime(2026, 9, 15, 9, 0, tzinfo=TEHRAN)
        n = decks.next_card(*fs, now=tomorrow)
        self.assertEqual((a, {"new": 0, "learning": 0, "review": 1}), (n["item"]["id"], n["counts"]))
        done = decks.review(*fs, a, "good", False, now=tomorrow)
        self.assertEqual("review", done["schedule"]["state"])
        self.assertGreaterEqual(done["schedule"]["interval"], 3)
        self.assertEqual(3, done["reps"])

        history = json.loads((decks.deck_dir(*fs) / "schedule" / (a + ".json")).read_text("utf-8"))["history"]
        self.assertEqual(["new", "learning", "review"], [h["before"] for h in history])
        self.assertEqual([True, True, False], [h["result"] for h in history])
        self.assertEqual((tomorrow.isoformat(timespec="microseconds"), "good",
                          done["schedule"]["interval"], done["schedule"]["ease"],
                          done["schedule"]["due"]),
                         tuple(history[-1][k] for k in ("at", "rating", "interval", "ease", "due")))
        self.assertEqual({"total": 2, "new": 0, "learning": 0, "review": 2},
                         decks.get_deck(*fs, now=tomorrow)["counts"])

    def test_the_daily_new_limit_and_skipping(self):
        _, fs = self.deck()
        decks.update_deck(*fs, settings={"new_per_day": 1})
        ids = [decks.add_item(*fs, ":::exercise flashcard\nfront: w%d\nback: x\n:::" % i,
                              now=NOW + timedelta(seconds=i))["id"] for i in range(3)]
        n = decks.next_card(*fs, now=NOW)
        self.assertEqual((ids[0], {"new": 1, "learning": 0, "review": 0}), (n["item"]["id"], n["counts"]))
        self.assertEqual(ids[1], decks.next_card(*fs, now=NOW, skip=[ids[0]])["item"]["id"])

        decks.review(*fs, ids[0], "easy", None, now=NOW)
        n = decks.next_card(*fs, now=NOW)
        self.assertEqual((True, {"new": 0, "learning": 0, "review": 0}, TOMORROW_ROLLOVER),
                         (n["done"], n["counts"], n["next_due"]))
        self.assertEqual({"new": 0, "learning": 0, "review": 0},
                         decks.get_deck(*fs, now=NOW)["study"])
        n = decks.next_card(*fs, now=datetime(2026, 9, 15, 5, 0, tzinfo=TEHRAN))
        self.assertEqual((ids[1], 1), (n["item"]["id"], n["counts"]["new"]))

    def test_review_refusals(self):
        _, fs = self.deck()
        item = decks.add_item(*fs, CHOICE)["id"]
        self.assertRaisesRegex(decks.DeckError, "rating", decks.review, *fs, item, "meh")
        self.assertRaisesRegex(decks.DeckError, "rating", decks.review, *fs, item, ["good"])
        self.assertRaisesRegex(decks.DeckError, "result", decks.review, *fs, item, "good", "yes")
        self.assertRaises(decks.NotFound, decks.review, *fs, "0" * 12, "good")
        self.assertRaises(decks.NotFound, decks.next_card, "persian", "nope")
        self.assertEqual(0, decks.get_item(*fs, item)["reps"])

    def test_an_answer_to_a_state_already_left_is_refused(self):
        # a second tab, or a retry after a lost reply, must not schedule twice
        _, fs = self.deck()
        item = decks.add_item(*fs, CHOICE)["id"]
        path = decks.deck_dir(*fs) / "schedule" / (item + ".json")
        self.assertEqual(1, decks.review(*fs, item, "good", True, now=NOW, reps=0)["reps"])
        before = path.read_bytes()
        for stale in (0, 2, True, False, "1", 1.0, [1]):
            with self.subTest(reps=stale):
                with self.assertRaises(decks.Conflict) as caught:
                    decks.review(*fs, item, "good", True, now=NOW, reps=stale)
                self.assertEqual("reviewed", caught.exception.kind)
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(2, decks.review(*fs, item, "good", True, now=NOW, reps=1)["reps"])
        self.assertEqual(3, decks.review(*fs, item, "again", False, now=NOW)["reps"])  # unchecked

    def test_a_reps_count_past_javascript_numbers_stays_answerable(self):
        # the page cannot hold a count above 2**53 exactly: the served and the
        # compared count are one capped reading, so the answer is not refused
        _, fs = self.deck()
        item = decks.add_item(*fs, CHOICE)["id"]
        path = decks.deck_dir(*fs) / "schedule" / (item + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        state = dict(srs.new_state(), state="review", due="2026-09-01T04:00:00+03:30",
                     interval=10, ease=2.5, reps=2 ** 53 + 1)
        path.write_text(json.dumps({"state": state, "history": []}), encoding="utf-8")
        served = decks.get_item(*fs, item)["reps"]
        self.assertEqual(2 ** 53 - 1, served)
        self.assertEqual(served, int(float(served)))      # exact as a JavaScript number
        self.assertEqual(2 ** 53 - 1,
                         decks.review(*fs, item, "good", True, now=NOW, reps=served)["reps"])


# ------------------------------------------------------------------ export / import

def manifest(scheduling=True, fmt=None, **deck):
    body = {"id": "0123456789ab", "name": "Imported", "lang": "fa", "settings": {},
            "created": NOW.isoformat()}
    body.update(deck)
    return json.dumps({"format": fmt or decks.FORMAT, "software": "Parseh",
                       "exported": NOW.isoformat(), "scheduling": scheduling,
                       "deck": body}).encode("utf-8")


def build_zip(entries):
    buf = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")          # a duplicate name, on purpose
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in entries:
                zf.writestr(name, data)
    return buf.getvalue()


def item_json(item_id, markdown):
    return json.dumps({"id": item_id, "created": NOW.isoformat(), "updated": NOW.isoformat(),
                       "markdown": markdown, "footnotes": "", "origin": None})


class ExportImportTests(Base):
    def setUp(self):
        super().setUp()
        self.summary, self.fs = self.deck("Travel deck")
        decks.update_deck(*self.fs, settings={"new_per_day": 7})
        images = decks.deck_dir(*self.fs) / "images"
        images.mkdir()
        for name, data in (("cat.png", PNG), ("fig.pdf", PDF), ("fig.pdf.svg", SVG),
                           ("stray.png", PNG2)):
            (images / name).write_bytes(data)
        # real recordings where ffmpeg made them; else the bytes audiofile.kind
        # knows an MP3, an Opus WebM and an Ogg by (the zip checks no more)
        self.sounds = {"say.mp3": SOUNDS.get(("mp3", 440), b"ID3\x04" + bytes(60)),
                       "note.webm": SOUNDS.get(("webm", 440), b"\x1a\x45\xdf\xa3webm" + bytes(60)),
                       "stray.ogg": SOUNDS.get(("ogg", 440), b"OggS" + bytes(60))}
        audio = decks.deck_dir(*self.fs) / "audio"
        audio.mkdir()
        for name, data in self.sounds.items():
            (audio / name).write_bytes(data)
        self.pictured = decks.add_item(*self.fs, PICTURED.replace(
            "back: cat\n", "back: cat\nfront-audio: audio/say.mp3\n"), now=NOW)["id"]
        # a recording named in a footnote travels too
        self.choice = decks.add_item(*self.fs, CHOICE.replace("hello**?", "hello**?[^n1]"),
                                     footnotes="[^n1]: note, heard in audio/note.webm",
                                     now=NOW + timedelta(seconds=1),
                                     origin={"doc_id": "d-123456", "title": "T", "ordinal": 1})["id"]
        decks.review(*self.fs, self.choice, "good", True, now=NOW)

    def snapshot(self, fs):
        return [(i["id"], i["created"], i["markdown"], i["footnotes"], i["origin"], i["schedule"])
                for i in decks.list_items(*fs)]

    def test_round_trip_with_scheduling(self):
        data, filename = decks.export_zip(*self.fs, True)
        self.assertEqual("exercises-travel-deck-with-scheduling.zip", filename)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            # the files the exercises name, in their fields or their
            # footnotes; not what the deck holds unnamed (stray.png, stray.ogg)
            self.assertEqual({decks.MANIFEST, "items/%s.json" % self.pictured,
                              "items/%s.json" % self.choice, "schedule/%s.json" % self.choice,
                              "images/cat.png", "images/fig.pdf", "images/fig.pdf.svg",
                              "audio/say.mp3", "audio/note.webm"},
                             set(zf.namelist()))
            self.assertEqual(self.sounds["say.mp3"], zf.read("audio/say.mp3"))
            # a recording is compressed already: stored as it is
            self.assertEqual({zipfile.ZIP_STORED}, {i.compress_type for i in zf.infolist()
                                                    if i.filename.startswith("audio/")})
            info = json.loads(zf.read(decks.MANIFEST))
        self.assertEqual((decks.FORMAT, "Parseh", True), (info["format"], info["software"],
                                                          info["scheduling"]))
        self.assertEqual({"id": self.summary["id"], "name": "Travel deck", "lang": "fa",
                          "settings": {"new_per_day": 7}, "created": self.summary["created"]},
                         info["deck"])
        before = self.snapshot(self.fs)

        for n, source in enumerate((data, io.BytesIO(data), self.root / "deck.zip")):
            if isinstance(source, Path):
                source.write_bytes(data)
            decks.set_dir(self.root / ("other%d" % n))
            out = decks.import_zip(source)
            deck = out["deck"]
            self.assertEqual((2, [], True), (out["imported"], out["skipped"], out["scheduling"]))
            self.assertEqual((self.summary["id"], "Travel deck", "travel-deck", 7),
                             (deck["id"], deck["name"], deck["slug"], deck["settings"]["new_per_day"]))
            fs = (deck["folder"], deck["slug"])
            self.assertEqual(before, self.snapshot(fs))
            self.assertEqual(["cat.png", "fig.pdf", "fig.pdf.svg"], self.deck_images(fs))
            self.assertEqual({n: self.sounds[n] for n in ("note.webm", "say.mp3")},
                             self.deck_files(fs, "audio"))
            self.assertEqual(self.sounds["say.mp3"], decks.audio_file(*fs, "say.mp3").read_bytes())
            self.assertEqual(1, deck["counts"]["learning"])

    def test_round_trip_without_scheduling(self):
        plain, filename = decks.export_zip(*self.fs, False)
        self.assertEqual("exercises-travel-deck.zip", filename)
        with zipfile.ZipFile(io.BytesIO(plain)) as zf:
            self.assertFalse([n for n in zf.namelist() if n.startswith("schedule/")])
            self.assertFalse(json.loads(zf.read(decks.MANIFEST))["scheduling"])
        full, _ = decks.export_zip(*self.fs, True)
        before = self.snapshot(self.fs)
        for n, (data, keep) in enumerate(((plain, True), (full, False))):
            decks.set_dir(self.root / ("fresh%d" % n))
            out = decks.import_zip(data, scheduling=keep)
            self.assertEqual((2, False), (out["imported"], out["scheduling"]))
            fs = (out["deck"]["folder"], out["deck"]["slug"])
            self.assertEqual([row[:5] + (srs.new_state(),) for row in before], self.snapshot(fs))

    def test_an_existing_deck_is_a_conflict_then_replaced_or_copied(self):
        data, _ = decks.export_zip(*self.fs, True)
        with self.assertRaises(decks.Conflict) as caught:
            decks.import_zip(data)
        self.assertEqual("exists", caught.exception.kind)
        self.assertIn("Travel deck", str(caught.exception))

        decks.add_item(*self.fs, FLASH)
        out = decks.import_zip(data, mode="replace")
        deck = out["deck"]
        self.assertEqual((self.summary["id"], self.summary["slug"], 2),
                         (deck["id"], deck["slug"], deck["counts"]["total"]))
        trash = decks.DIR / ".trash"
        gone = os.listdir(trash)
        self.assertEqual(1, len(gone))
        self.assertRegex(gone[0], r"^persian--travel-deck--\d{8}-\d{6}$")
        self.assertEqual(3, len(os.listdir(trash / gone[0] / "items")))

        copy = decks.import_zip(data, mode="copy")["deck"]
        self.assertNotEqual(self.summary["id"], copy["id"])
        self.assertEqual(("Travel deck (copy)", "travel-deck-copy", 2),
                         (copy["name"], copy["slug"], copy["counts"]["total"]))
        self.assertEqual(2, len(decks.list_decks()))
        self.assertEqual([], [n for n in os.listdir(decks.DIR / "persian") if n.startswith(".")])

        decks.set_dir(self.root / "elsewhere")
        for mode in ("replace", "copy"):     # nothing to collide with: like "new"
            deck = decks.import_zip(data, mode=mode)["deck"]
            self.assertEqual((self.summary["id"], "Travel deck"), (deck["id"], deck["name"]))
            decks.delete_deck(deck["folder"], deck["slug"])

    def test_refusals(self):
        good_id = "0123456789ab"
        good = [(decks.MANIFEST, manifest()), ("items/%s.json" % good_id, item_json(good_id, CHOICE))]
        link = zipfile.ZipInfo("images/link.png")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        cases = [
            (b"not a zip at all", "not a zip"),
            (build_zip(good[1:]), "is missing"),
            (build_zip([(decks.MANIFEST, b"{not json")]), "not readable"),
            (build_zip([(decks.MANIFEST, b"[1, 2]")]), "not readable"),
            (build_zip([(decks.MANIFEST, manifest(fmt="other-format/9"))]), "unsupported deck format"),
            (build_zip([(decks.MANIFEST, manifest(lang="xx"))]), "unknown language"),
            (build_zip([(decks.MANIFEST, manifest(id="../../x"))]), "valid deck id"),
            (build_zip([(decks.MANIFEST, manifest(name=""))]), "name"),
            (build_zip([(decks.MANIFEST, manifest(settings={"new_per_day": "many"}))]), "options"),
            (build_zip(good + [(link, b"target")]), "symbolic link"),
            (build_zip(good + [("items/%s.json" % good_id, item_json(good_id, FLASH))]), "twice"),
            # a recording's name with bytes that are no recording
            (build_zip(good + [("audio/x.mp3", b"<html><script>alert(1)</script></html>")]),
             "audio/x.mp3 is not a recording"),
            (build_zip(good + [("audio/x.ogg", PNG + bytes(40))]), "audio/x.ogg is not a recording"),
        ]
        for name in ("../evil.json", "/abs.json", "items/../../x.json", "images/../deck.json",
                     "items/ABC.json", "items/0123456789ab.json.txt", "notes.txt", "items/",
                     "images/Cat.PNG", "images/cat.gif", "schedule/x.json", "images/sub/cat.png",
                     "deck.json", "audio/UPPER.MP3", "audio/x.txt", "audio/sub/x.mp3",
                     "audio/../x.mp3", "audio/", "audio/.x.mp3", "images/x.mp3.mp3", "audio/x.png"):
            cases.append((build_zip(good + [(name, b"ID3" + bytes(60))]), "unexpected entry"))
        for data, fragment in cases:
            with self.subTest(fragment=fragment, size=len(data)):
                self.assertRaisesRegex(decks.DeckError, fragment, decks.import_zip, data)
        self.assertRaisesRegex(decks.DeckError, "mode", decks.import_zip, build_zip(good), mode="merge")
        self.assertRaisesRegex(decks.DeckError, "not there", decks.import_zip, str(self.root / "none.zip"))
        self.assertEqual(["travel-deck"], os.listdir(decks.DIR / "persian"))

    def test_size_limits(self):
        good_id = "0123456789ab"
        good = [(decks.MANIFEST, manifest()), ("items/%s.json" % good_id, item_json(good_id, CHOICE))]
        saved = (decks.MAX_ENTRIES, decks.MAX_JSON, decks.MAX_TOTAL, store.IMG_MAX)
        mp3 = SOUNDS.get(("mp3", 440), b"ID3\x04" + bytes(600))
        with mock.patch.object(audiofile, "MAX_BYTES", len(mp3) - 1):
            self.assertRaisesRegex(decks.DeckError, "audio/big.mp3 is too large", decks.import_zip,
                                   build_zip(good + [("audio/big.mp3", mp3)]))
        # a header that lies about the size is caught while reading
        lying = io.BytesIO(build_zip(good + [("audio/big.mp3", mp3)]))
        with mock.patch.object(audiofile, "MAX_BYTES", len(mp3) - 1), \
                mock.patch.object(decks, "_check_entries",
                                  lambda zf: {i.filename: i for i in zf.infolist()}):
            self.assertRaisesRegex(decks.DeckError, "too large", decks.import_zip, lying)
        try:
            decks.MAX_ENTRIES = 2
            self.assertRaisesRegex(decks.DeckError, "more than 2 entries", decks.import_zip,
                                   build_zip(good + [("images/cat.png", PNG)]))
            decks.MAX_ENTRIES = saved[0]
            decks.MAX_JSON = 400
            self.assertRaisesRegex(decks.DeckError, "too large", decks.import_zip,
                                   build_zip(good + [("schedule/%s.json" % good_id, b" " * 401)]))
            decks.MAX_JSON = saved[1]
            store.IMG_MAX = 10
            self.assertRaisesRegex(decks.DeckError, "too large", decks.import_zip,
                                   build_zip(good + [("images/cat.png", PNG)]))
            store.IMG_MAX = saved[3]
            decks.MAX_TOTAL = 600
            self.assertRaisesRegex(decks.DeckError, "uncompressed", decks.import_zip,
                                   build_zip(good + [("images/a.png", b"x" * 300),
                                                     ("images/b.png", b"y" * 300)]))
        finally:
            decks.MAX_ENTRIES, decks.MAX_JSON, decks.MAX_TOTAL, store.IMG_MAX = saved
        self.assertEqual(["travel-deck"], os.listdir(decks.DIR / "persian"))

    def test_unusable_exercises_are_skipped_and_reported(self):
        ids = ["%012x" % n for n in range(1, 5)]
        data = build_zip([
            (decks.MANIFEST, manifest(name="Mixed")),
            ("items/%s.json" % ids[0], item_json(ids[0], CHOICE)),
            ("items/%s.json" % ids[1], item_json(ids[1], "no exercise here")),
            ("items/%s.json" % ids[2], "{broken"),
            ("items/%s.json" % ids[3], item_json(ids[3], ":::exercise single-choice\n- [x] a\n- [x] b\n:::")),
            ("schedule/%s.json" % ids[0], json.dumps({"state": {"state": "review", "interval": 3,
                                                                  "ease": 2.5, "reps": 4,
                                                                  "due": "garbage"},
                                                        "history": [{"at": "x"}, 5]})),
        ])
        out = decks.import_zip(data)
        self.assertEqual(1, out["imported"])
        skipped = {s["id"]: s["errors"] for s in out["skipped"]}
        self.assertEqual(set(ids[1:]), set(skipped))
        self.assertIn("not an exercise", skipped[ids[1]][0])
        self.assertIn("single-choice exercise needs exactly one [x] answer", skipped[ids[3]])
        item = decks.list_items(out["deck"]["folder"], out["deck"]["slug"])[0]
        self.assertEqual(("review", 3, 4, None), tuple(item["schedule"][k] for k in
                                                       ("state", "interval", "reps", "due")))

    def test_times_no_datetime_can_convert_are_dropped_on_import(self):
        # they parse, but moved to UTC or to the learner's timezone they
        # overflow: installed as they were, every deck listing failed after
        edge = ("0001-01-01T00:00:00+05:00", "9999-12-31T23:30:00-05:00", "0001-01-01T00:00:00")
        for text in edge:
            self.assertIsNone(decks._moment(text), text)
        self.assertIsNotNone(decks._moment(NOW.isoformat()))
        ids = ["%012x" % n for n in (1, 2)]
        sched = {"state": {"state": "review", "interval": 3, "ease": 2.5, "reps": 2,
                           "due": edge[1], "last_review": edge[0]},
                 "history": [{"at": edge[0], "rating": "good", "before": "new"},
                             {"at": NOW.isoformat(), "rating": "good", "before": "learning",
                              "due": edge[1]}]}
        data = build_zip([
            (decks.MANIFEST, manifest(name="Edges", created=edge[0])),
            ("items/%s.json" % ids[0], json.dumps({"id": ids[0], "created": edge[0],
                                                     "updated": edge[1], "markdown": CHOICE})),
            ("items/%s.json" % ids[1], json.dumps({"id": ids[1], "created": edge[2],
                                                     "markdown": FLASH})),
            ("schedule/%s.json" % ids[0], json.dumps(sched)),
        ])
        out = decks.import_zip(data)
        self.assertEqual((2, []), (out["imported"], out["skipped"]))
        fs = (out["deck"]["folder"], out["deck"]["slug"])
        d = decks.deck_dir(*fs)
        for item_id in ids:
            on_disk = json.loads((d / "items" / (item_id + ".json")).read_text("utf-8"))
            self.assertIsNotNone(decks._moment(on_disk["created"]))
            self.assertIsNotNone(decks._moment(on_disk["updated"]))
        self.assertIsNotNone(decks._moment(json.loads((d / "deck.json").read_text("utf-8"))["created"]))
        stored = json.loads((d / "schedule" / (ids[0] + ".json")).read_text("utf-8"))
        self.assertEqual((None, None), (stored["state"]["due"], stored["state"]["last_review"]))
        self.assertEqual([(NOW.isoformat(), None)], [(h["at"], h["due"]) for h in stored["history"]])
        self.assertEqual(["Edges", "Travel deck"], [x["name"] for x in decks.list_decks(now=NOW)])
        self.assertEqual(2, decks.hub_stats(now=NOW)["decks"])
        self.assertEqual(ids[0], decks.next_card(*fs, now=NOW)["item"]["id"])

    def test_an_installed_import_is_reported_even_if_it_cannot_be_counted(self):
        data, _ = decks.export_zip(*self.fs, True)
        decks.set_dir(self.root / "other")
        out = io.StringIO()
        with mock.patch.object(srs, "queue", side_effect=OverflowError("date value out of range")), \
                redirect_stdout(out):
            got = decks.import_zip(data)
        deck = got["deck"]
        self.assertEqual((self.summary["id"], "Travel deck", "travel-deck", 2),
                         (deck["id"], deck["name"], deck["slug"], deck["counts"]["total"]))
        self.assertEqual(set(self.summary), set(deck))
        self.assertIn("cannot count", out.getvalue())
        self.assertEqual(2, decks.get_deck(deck["folder"], deck["slug"])["counts"]["total"])

    def test_a_replace_that_cannot_finish_puts_the_old_deck_back(self):
        data, _ = decks.export_zip(*self.fs, True)
        decks.add_item(*self.fs, FLASH)
        before = self.snapshot(self.fs)
        real = os.rename

        def rename(src, dst, *args, **kw):
            if Path(src).name.startswith(".import-"):
                raise PermissionError("the staged deck is held open")
            return real(src, dst, *args, **kw)

        with mock.patch("os.rename", rename):
            self.assertRaises(PermissionError, decks.import_zip, data, mode="replace")
        self.assertEqual(before, self.snapshot(self.fs))
        self.assertEqual([self.summary["id"]], [x["id"] for x in decks.list_decks()])
        self.assertEqual([], os.listdir(decks.DIR / ".trash"))
        self.assertEqual(["travel-deck"], os.listdir(decks.DIR / "persian"))

    def test_an_ease_no_deck_can_reach_is_dropped_on_import(self):
        ids = ["%012x" % n for n in (1, 2)]
        huge = "1" + "0" * 400              # valid JSON; float() of it overflows

        def schedule(ease, eases):
            return ('{"state": {"state": "review", "due": "2026-09-01T04:00:00+03:30", '
                    '"interval": 36500, "ease": %s}, "history": [%s]}'
                    % (ease, ", ".join('{"at": "2026-09-01T10:00:00+03:30", "rating": "good", '
                                       '"ease": %s}' % e for e in eases)))

        data = build_zip([
            (decks.MANIFEST, manifest(name="Eases")),
            ("items/%s.json" % ids[0], item_json(ids[0], CHOICE)),
            ("items/%s.json" % ids[1], item_json(ids[1], FLASH)),
            ("schedule/%s.json" % ids[0], schedule("1e305", ("1e305", "0.5", huge, "NaN", "1", "2.5"))),
            ("schedule/%s.json" % ids[1], schedule("1e6", ())),
        ])
        out = decks.import_zip(data)
        self.assertEqual(2, out["imported"])
        fs = (out["deck"]["folder"], out["deck"]["slug"])
        d = decks.deck_dir(*fs)
        first = json.loads((d / "schedule" / (ids[0] + ".json")).read_text("utf-8"))
        self.assertIsNone(first["state"]["ease"])
        self.assertEqual([None, None, None, None, 1.0, 2.5], [h["ease"] for h in first["history"]])
        second = json.loads((d / "schedule" / (ids[1] + ".json")).read_text("utf-8"))
        self.assertEqual(1e6, second["state"]["ease"])
        # studied and answered without an overflow
        self.assertEqual(ids[0], decks.next_card(*fs, now=NOW)["item"]["id"])
        self.assertEqual(4, len(decks.next_card(*fs, now=NOW, skip=[ids[0]])["intervals"]))
        for item_id in ids:
            decks.review(*fs, item_id, "easy", now=NOW)

    def test_an_item_naming_a_pdf_and_its_twin_exports_each_file_once(self):
        decks.add_item(*self.fs, ":::exercise flashcard\nfront: fig\nback: figure\n"
                       "front-image: images/fig.pdf\nback-image: images/fig.pdf.svg\n:::")
        with warnings.catch_warnings():
            warnings.simplefilter("error")          # zipfile warns of a duplicate name
            data, _ = decks.export_zip(*self.fs, True)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(["images/cat.png", "images/fig.pdf", "images/fig.pdf.svg"],
                         sorted(n for n in names if n.startswith("images/")))
        decks.set_dir(self.root / "moved")
        self.assertEqual(3, decks.import_zip(data)["imported"])

    def test_image_file(self):
        path = decks.image_file(*self.fs, "cat.png")
        self.assertEqual(PNG, path.read_bytes())
        for name in ("missing.png", "../deck.json", "deck.json", "Cat.png", ""):
            self.assertRaises(decks.NotFound, decks.image_file, *self.fs, name)
        self.assertRaises(decks.NotFound, decks.image_file, "persian", "nope", "cat.png")


class ShelfBackupTests(Base):
    """The WHOLE shelf, out and back -- the studio's Backup button for the
    exercises.  It is not export_zip of each deck, and the three places it
    differs are the reasons it exists:

      * deck.json travels whole, so the id everything is matched on, the
        settings and the created date come back as they were;
      * every picture and recording travels, named by an exercise or not,
        because one nothing names today is one somebody unlinked yesterday;
      * the scheduling always travels, because months of answers cannot be
        worked out again from anything.
    """

    def setUp(self):
        super().setUp()
        self.summary, self.fs = self.deck("Travel deck")
        decks.update_deck(*self.fs, settings={"new_per_day": 7})
        images = decks.deck_dir(*self.fs) / "images"
        images.mkdir()
        (images / "cat.png").write_bytes(PNG)
        (images / "stray.png").write_bytes(PNG2)        # named by nothing
        audio = decks.deck_dir(*self.fs) / "audio"
        audio.mkdir()
        (audio / "stray.ogg").write_bytes(SOUNDS.get(("ogg", 440), b"OggS" + bytes(60)))
        self.first = decks.add_item(*self.fs, FLASH, now=NOW)["id"]
        self.second = decks.add_item(
            *self.fs, CHOICE, now=NOW + timedelta(seconds=1),
            origin={"doc_id": "d-123456", "title": "T", "ordinal": 1})["id"]
        decks.review(*self.fs, self.second, "good", True, now=NOW)

    def shelf_snapshot(self, fs):
        return [(i["id"], i["created"], i["markdown"], i["footnotes"], i["origin"],
                 i["schedule"]) for i in decks.list_items(*fs)]

    def test_a_backup_holds_every_deck_behind_its_language_folder(self):
        self.deck("Arabic basics", "ar")
        data, name = decks.backup_zip()
        self.assertTrue(name.startswith("exercises-backup-") and name.endswith(".zip"), name)
        names = set(zipfile.ZipFile(io.BytesIO(data)).namelist())
        self.assertIn(decks.SHELF_MANIFEST, names)
        self.assertIn("persian/travel-deck/deck.json", names)
        self.assertIn("arabic/arabic-basics/deck.json", names)
        # what an export drops on purpose and a backup must not
        self.assertIn("persian/travel-deck/images/stray.png", names)
        self.assertIn("persian/travel-deck/audio/stray.ogg", names)
        self.assertTrue([n for n in names if n.startswith("persian/travel-deck/schedule/")],
                        "the scheduling is in it: %s" % sorted(names))

    def test_it_comes_back_with_its_id_its_settings_and_its_answers(self):
        data, _name = decks.backup_zip()
        was = self.shelf_snapshot(self.fs)
        deck_id = self.summary["id"]
        was_dir = decks.set_dir(self.root / "restored")
        try:
            out = decks.restore_zip(data)
            self.assertEqual((out["kept"], out["warnings"]), ([], []))
            self.assertEqual(out["restored"], ["Travel deck"])
            listed = decks.list_decks()
            self.assertEqual([(d["folder"], d["slug"]) for d in listed],
                             [("persian", "travel-deck")])
            self.assertEqual(listed[0]["id"], deck_id, "the id is the deck")
            self.assertEqual(listed[0]["settings"].get("new_per_day"), 7)
            self.assertEqual(self.shelf_snapshot(self.fs), was,
                             "every exercise, its origin and its schedule")
            d = decks.deck_dir(*self.fs)
            self.assertTrue((d / "images" / "stray.png").exists(),
                            "a picture no exercise names is still somebody's")
            self.assertTrue((d / "audio" / "stray.ogg").exists())
        finally:
            decks.set_dir(was_dir)

    def test_what_is_already_here_is_kept_until_replacing_is_asked_for(self):
        data, _name = decks.backup_zip()
        decks.add_item(*self.fs, FLASH.replace("cat", "kitten"), now=NOW)
        after = len(decks.list_items(*self.fs))
        out = decks.restore_zip(data)
        self.assertEqual((out["restored"], out["kept"]), ([], ["Travel deck"]))
        self.assertEqual(len(decks.list_items(*self.fs)), after,
                         "the newer exercise is still there")
        out = decks.restore_zip(data, replace=True)
        self.assertEqual((out["restored"], out["kept"]), (["Travel deck"], []))
        self.assertEqual(len(decks.list_items(*self.fs)), after - 1,
                         "and now the backup's copy is in its place")
        self.assertEqual(len(decks.list_decks()), 1, "one deck, not two")

    def test_what_it_refuses(self):
        with self.assertRaises(decks.DeckError) as e:
            decks.restore_zip(b"not a zip")
        self.assertIn("not a zip", str(e.exception))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../evil.json", "{}")
        with self.assertRaises(decks.DeckError) as e:
            decks.restore_zip(buf.getvalue())
        self.assertIn("unexpected entry", str(e.exception))
        # one deck's export is not a shelf backup: its entries carry no
        # language folder, and the shelf grammar says so rather than
        # guessing which deck they were meant for
        one, _n = decks.export_zip(*self.fs, True)
        with self.assertRaises(decks.DeckError) as e:
            decks.restore_zip(one)
        self.assertIn("unexpected entry", str(e.exception))

PAIR = ":::exercise flashcard\nfront: [گربه]{tl}\nback: cat\ndirection: both-repeat\n:::"
RANDOM_FACE = ":::exercise flashcard\nfront: [گربه]{tl}\nback: cat\ndirection: both-random\n:::"
FRONT_FIRST = ":::exercise flashcard\nfront: [گربه]{tl}\nback: cat\ndirection: forward\n:::"
BACK_FIRST = ":::exercise flashcard\nfront: [گربه]{tl}\nback: cat\ndirection: reverse\n:::"
LATER = datetime(2026, 9, 15, 9, 0, tzinfo=TEHRAN)         # the next day, after its rollover
LINK_RE = re.compile(r"^[0-9a-f]{12}$")


class LinkedTests(Base):
    """A both-repeat flashcard is TWO linked cards in a deck (TO-DO L17): made
    together, one link, front first; asked about whenever an edit or a
    delete would leave the other side as it was; held back for a day when
    the other side is answered.  Nothing here is stored beyond the one
    `link` field: the burying is read from the answers."""

    def setUp(self):
        super().setUp()
        self.s, self.fs = self.deck("Pairs")

    def pair(self, markdown=PAIR, now=NOW, **kw):
        return decks.add_item(*self.fs, markdown, now=now, **kw)["items"]

    def on_disk(self, item_id, fs=None):
        return json.loads((decks.deck_dir(*(fs or self.fs)) / "items" / (item_id + ".json"))
                          .read_text("utf-8"))

    def by_id(self, item_id, fs=None):
        return next(i for i in decks.list_items(*(fs or self.fs)) if i["id"] == item_id)

    def test_add_makes_two_linked_cards_front_first(self):
        made = decks.add_item(*self.fs, PAIR, origin={"doc_id": "d-123456", "title": "T"},
                              tags=["Animals"], now=NOW)
        a, b = made["items"]
        self.assertEqual(a["id"], made["id"])
        self.assertEqual(("forward", "reverse"), (a["direction"], b["direction"]))
        self.assertEqual(FRONT_FIRST, a["markdown"])
        self.assertEqual(BACK_FIRST, b["markdown"])
        self.assertRegex(a["link"], LINK_RE)
        self.assertEqual(a["link"], b["link"])
        self.assertEqual(([b["id"]], [a["id"]]), (a["mates"], b["mates"]))
        self.assertEqual((NOW.isoformat(timespec="microseconds"),
                          (NOW + timedelta(microseconds=1)).isoformat(timespec="microseconds")),
                         (a["created"], b["created"]))
        self.assertEqual([a["id"], b["id"]], [i["id"] for i in decks.list_items(*self.fs)])
        # the same origin, tags and footnotes: they are one card
        self.assertEqual(({"doc_id": "d-123456", "title": "T"}, ["animals"]),
                         (a["origin"], a["tags"]))
        self.assertEqual((a["origin"], a["tags"], a["footnotes"]),
                         (b["origin"], b["tags"], b["footnotes"]))
        self.assertEqual([b["id"]], decks.get_item(*self.fs, a["id"])["mates"])
        self.assertEqual(2, decks.get_deck(*self.fs, now=NOW)["counts"]["total"])
        self.assertNotIn("both-repeat", a["markdown"] + b["markdown"])
        # only a linked card's file carries the key
        self.assertEqual(a["link"], self.on_disk(a["id"])["link"])
        plain = decks.add_item(*self.fs, CHOICE, now=NOW)
        self.assertNotIn("link", self.on_disk(plain["id"]))
        self.assertEqual(([], None), (plain["mates"], plain["link"]))
        self.assertNotIn("items", plain)

    def test_the_queue_of_new_cards_keeps_front_before_back(self):
        # made at one instant: a microsecond apart, else their random ids would order them
        for n in range(5):
            _s, fs = self.deck("Order %d" % n)
            a, b = decks.add_item(*fs, PAIR, now=NOW)["items"]
            self.assertEqual(a["id"], decks.next_card(*fs, now=NOW)["item"]["id"])

    def test_both_random_is_stored_as_it_is(self):
        made = decks.add_item(*self.fs, RANDOM_FACE, now=NOW)
        self.assertNotIn("items", made)
        self.assertEqual((RANDOM_FACE, "both-random", None, []),
                         (made["markdown"], made["direction"], made["link"], made["mates"]))
        self.assertEqual(1, len(decks.list_items(*self.fs)))

    def test_a_pair_needs_no_second_look_at_a_card_that_is_not_a_flashcard(self):
        made = decks.add_item(*self.fs, CHOICE.replace("prompt:", "direction: both-repeat\nprompt:"),
                              now=NOW)
        self.assertNotIn("items", made)
        self.assertEqual(1, len(decks.list_items(*self.fs)))

    def test_either_side_already_there_is_a_duplicate_unless_forced(self):
        a, b = self.pair()
        for markdown in (PAIR, FRONT_FIRST, BACK_FIRST):
            with self.assertRaises(decks.Conflict) as e:
                decks.add_item(*self.fs, markdown, now=NOW)
            self.assertEqual("duplicate", e.exception.kind)
        # one side left: the pair is still refused, for the side that is there
        decks.delete_item(*self.fs, b["id"], linked="alone")
        with self.assertRaises(decks.Conflict):
            decks.add_item(*self.fs, PAIR, now=NOW)
        forced = decks.add_item(*self.fs, PAIR, force=True, now=NOW)["items"]
        self.assertEqual(3, len(decks.list_items(*self.fs)))
        self.assertNotIn(forced[0]["link"], (a["link"], None))
        self.assertEqual(forced[0]["link"], forced[1]["link"])
        self.assertEqual([], self.by_id(a["id"])["mates"])

    def test_copy_from_a_document_makes_the_pair_and_brings_its_picture_once(self):
        meta = self.doc(PAIR.replace("back: cat", "back: cat\nfront-image: images/cat.png"),
                        images={"cat.png": PNG})
        out = decks.copy_from_doc(*self.fs, meta["id"], 1, "flashcard", meta["updated"], now=NOW)
        a, b = out["items"]
        self.assertEqual(a["id"], out["item"]["id"])
        self.assertEqual([], out["warnings"])
        self.assertEqual(("forward", "reverse"), (a["direction"], b["direction"]))
        self.assertEqual(a["link"], b["link"])
        self.assertEqual(({"doc_id": meta["id"], "doc_uid": meta["uid"], "title": "Doc", "ordinal": 1},) * 2,
                         (a["origin"], b["origin"]))
        self.assertEqual(["cat.png"], self.deck_images(self.fs))
        with self.assertRaises(decks.Conflict) as e:
            decks.copy_from_doc(*self.fs, meta["id"], 1, "flashcard", meta["updated"], now=NOW)
        self.assertEqual("duplicate", e.exception.kind)
        self.assertEqual(2, len(decks.list_items(*self.fs)))
        again = decks.copy_from_doc(*self.fs, meta["id"], 1, "flashcard", meta["updated"],
                                    force=True, now=NOW)
        self.assertEqual(4, len(decks.list_items(*self.fs)))
        self.assertNotEqual(a["link"], again["items"][0]["link"])
        # a document's own card is one exercise, whatever it says
        self.assertEqual(1, len(decks.exercise_blocks(store.get(meta["id"])[1])[1]))
        # one exercise is still one item, with the same answer shape
        plain = self.doc(CHOICE)
        got = decks.copy_from_doc(*self.fs, plain["id"], 1, "single-choice", None, now=NOW)
        self.assertEqual(([got["item"]["id"]], []), ([i["id"] for i in got["items"]], got["item"]["mates"]))

    def test_pictures_from_the_clip_tray_come_in_once_for_both_sides(self):
        self.in_tray({"cat.png": PNG})
        a, b = self.pair(PAIR.replace("back: cat", "back: cat\nfront-image: images/cat.png"))
        self.assertEqual(["cat.png"], self.deck_images(self.fs))
        self.assertTrue(all("front-image: images/cat.png" in i["markdown"] for i in (a, b)))

    def test_a_hand_written_both_repeat_item_is_kept_and_studied_front_first(self):
        d = decks.deck_dir(*self.fs)
        (d / "items").mkdir()
        (d / "items" / ("a" * 12 + ".json")).write_text(json.dumps({
            "id": "a" * 12, "created": NOW.isoformat(), "updated": NOW.isoformat(),
            "markdown": PAIR, "footnotes": "", "origin": None}), encoding="utf-8")
        item = decks.list_items(*self.fs)[0]
        self.assertEqual(("both-repeat", []), (item["direction"], item["mates"]))
        self.assertEqual("a" * 12, decks.next_card(*self.fs, now=NOW)["item"]["id"])
        html = decks.render_item({"lang": "fa"}, item, "/media/", preview=False)
        self.assertLess(html.index("گربه"), html.index("cat"))       # the front is the first face
        # nothing but a deck's own add expands it: saving it leaves it whole
        decks.update_item(*self.fs, "a" * 12, PAIR.replace("cat", "kitten"))
        self.assertEqual(1, len(decks.list_items(*self.fs)))

    def test_the_link_travels_in_an_export_a_backup_and_an_import(self):
        a, b = self.pair()
        plain = decks.add_item(*self.fs, CHOICE, now=NOW)["id"]
        data, _name = decks.export_zip(*self.fs, True)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            self.assertEqual(a["link"], json.loads(zf.read("items/%s.json" % a["id"]))["link"])
            self.assertNotIn("link", json.loads(zf.read("items/%s.json" % plain)))
        imported = decks.import_zip(data, mode="copy")["deck"]
        copy_fs = (imported["folder"], imported["slug"])
        got = decks.list_items(*copy_fs)
        self.assertEqual({a["link"]}, {i["link"] for i in got if i["id"] in (a["id"], b["id"])})
        self.assertEqual(3, len(got))
        self.assertEqual(([b["id"]], [a["id"]]), tuple(next(i["mates"] for i in got if i["id"] == x)
                                                       for x in (a["id"], b["id"])))
        self.assertEqual([], next(i["mates"] for i in got if i["id"] == plain))
        # a shelf backup put back over the deck
        backup, _n = decks.backup_zip()
        decks.delete_item(*self.fs, a["id"], linked="both")
        self.assertEqual(1, len(decks.list_items(*self.fs)))
        decks.restore_zip(backup, replace=True)
        restored = decks.list_items(*self.fs)
        self.assertEqual(([b["id"]], [a["id"]], []),
                         tuple(next(i["mates"] for i in restored if i["id"] == x)
                               for x in (a["id"], b["id"], plain)))
        # a link that is not one is dropped, and a card left alone with it is not linked
        bad = decks.export_zip(*self.fs, False)[0]
        src = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(bad)) as zin, zipfile.ZipFile(src, "w") as zout:
            for info in zin.infolist():
                body = zin.read(info)
                if info.filename == "items/%s.json" % a["id"]:
                    body = json.dumps(dict(json.loads(body), link="not-a-link")).encode("utf-8")
                zout.writestr(info.filename, body)
        again = decks.import_zip(src.getvalue(), mode="copy")["deck"]
        self.assertEqual([[], [], []], [i["mates"] for i in decks.list_items(again["folder"], again["slug"])])

    def test_duplicate_gives_an_unlinked_copy(self):
        a, b = self.pair()
        copy = decks.duplicate_item(*self.fs, a["id"], now=NOW)
        self.assertEqual(([], None, a["id"]), (copy["mates"], copy["link"], copy["origin"]["duplicate_of"]))
        self.assertEqual([b["id"]], self.by_id(a["id"])["mates"])

    def test_copy_and_move_carry_a_pair_whole_and_a_single_side_alone(self):
        a, b = self.pair()
        other, ofs = self.deck("Other")
        # both sides, the back named first: they arrive in order, linked under a link of their own
        out = decks.transfer_items(*self.fs, [b["id"], a["id"]], *ofs)
        got = decks.list_items(*ofs)
        self.assertEqual(["forward", "reverse"], [i["direction"] for i in got])
        self.assertEqual(2, len(out["ids"]))
        self.assertEqual(got[0]["link"], got[1]["link"])
        self.assertNotEqual(a["link"], got[0]["link"])
        self.assertEqual([[got[1]["id"]], [got[0]["id"]]], [i["mates"] for i in got])
        self.assertEqual([b["id"]], self.by_id(a["id"])["mates"])               # the source is as it was
        # one side: linked with nothing there, and still linked here
        third, tfs = self.deck("Third")
        decks.transfer_items(*self.fs, [a["id"]], *tfs)
        (only,) = decks.list_items(*tfs)
        self.assertEqual(([], None), (only["mates"], only["link"]))
        self.assertEqual([b["id"]], self.by_id(a["id"])["mates"])
        # a move of one side leaves the other, alone
        fourth, ffs = self.deck("Fourth")
        decks.transfer_items(*self.fs, [b["id"]], *ffs, move=True)
        self.assertEqual([], self.by_id(a["id"])["mates"])
        self.assertNotIn("link", self.on_disk(a["id"]))
        # a move of both keeps them together, with their answers
        _s, fs2 = self.deck("Five")
        c, d = decks.add_item(*fs2, PAIR, now=NOW)["items"]
        decks.review(*fs2, c["id"], "good", None, now=NOW)
        _t, fs3 = self.deck("Six")
        decks.transfer_items(*fs2, [c["id"], d["id"]], *fs3, move=True)
        moved = decks.list_items(*fs3)
        self.assertEqual((0, ["learning", "new"]), (len(decks.list_items(*fs2)),
                                                    sorted(i["schedule"]["state"] for i in moved)))
        self.assertEqual(moved[0]["link"], moved[1]["link"])

    # ------------------------------------------------------------ editing

    def test_an_edit_that_changes_a_linked_card_must_say_what_becomes_of_the_other(self):
        a, b = self.pair()
        changed = a["markdown"].replace("back: cat", "back: kitten")
        with self.assertRaises(decks.Conflict) as e:
            decks.update_item(*self.fs, a["id"], changed, now=NOW)
        self.assertEqual("linked", e.exception.kind)
        self.assertEqual({"mates": [{"id": b["id"], "excerpt": "گربه", "side": "back"}]},
                         e.exception.detail)
        self.assertEqual(a["markdown"], self.by_id(a["id"])["markdown"])
        for bad in ("both ", "yes", True):
            with self.assertRaises(decks.DeckError):
                decks.update_item(*self.fs, a["id"], changed, linked=bad)
        # written differently, but the same card: nothing to ask, nothing to spread
        same = a["markdown"] + "\n\n"
        decks.update_item(*self.fs, a["id"], same.replace("back: cat", "back:   cat"), now=NOW)
        self.assertEqual([b["id"]], self.by_id(a["id"])["mates"])
        self.assertEqual(BACK_FIRST, self.by_id(b["id"])["markdown"])

    def test_change_both_writes_it_to_the_other_side_which_keeps_its_own_side(self):
        a, b = self.pair()
        decks.review(*self.fs, a["id"], "good", None, now=NOW)
        schedule = (decks.deck_dir(*self.fs) / "schedule" / (a["id"] + ".json")).read_bytes()
        later = NOW + timedelta(hours=1)
        got = decks.update_item(*self.fs, a["id"], a["markdown"].replace("back: cat", "back: kitten"),
                                now=later, linked="both")
        self.assertEqual([b["id"]], got["mates"])
        now_a, now_b = self.by_id(a["id"]), self.by_id(b["id"])
        self.assertEqual(FRONT_FIRST.replace("cat", "kitten"), now_a["markdown"])
        self.assertEqual(BACK_FIRST.replace("cat", "kitten"), now_b["markdown"])
        self.assertEqual(later.isoformat(timespec="microseconds"), now_b["updated"])
        self.assertEqual(a["link"], now_b["link"])
        # nobody's answers moved
        self.assertEqual(schedule, (decks.deck_dir(*self.fs) / "schedule" / (a["id"] + ".json")).read_bytes())
        self.assertFalse((decks.deck_dir(*self.fs) / "schedule" / (b["id"] + ".json")).exists())
        # which side a linked card shows is what makes the pair: an edit cannot turn one round
        decks.update_item(*self.fs, a["id"], BACK_FIRST.replace("cat", "lion"), now=later, linked="both")
        self.assertEqual(("forward", "reverse"), (self.by_id(a["id"])["direction"], self.by_id(b["id"])["direction"]))
        self.assertIn("back: lion", self.by_id(b["id"])["markdown"])

    def test_change_only_this_one_unlinks_the_two(self):
        a, b = self.pair()
        got = decks.update_item(*self.fs, b["id"], b["markdown"].replace("back: cat", "back: lion"),
                                now=NOW, linked="alone")
        self.assertEqual(([], None), (got["mates"], got["link"]))
        self.assertIn("back: lion", self.by_id(b["id"])["markdown"])
        self.assertIn("back: cat", self.by_id(a["id"])["markdown"])
        self.assertEqual(([], []), (self.by_id(a["id"])["mates"], self.by_id(b["id"])["mates"]))
        self.assertNotIn("link", self.on_disk(a["id"]))
        self.assertNotIn("link", self.on_disk(b["id"]))
        # and now an edit asks nothing
        decks.update_item(*self.fs, a["id"], a["markdown"].replace("cat", "tiger"), now=NOW)
        # turning a card round is a change too: allowed once it is alone
        c, d = self.pair(PAIR.replace("cat", "dog"))
        with self.assertRaises(decks.Conflict):
            decks.update_item(*self.fs, c["id"], c["markdown"].replace("forward", "reverse"))
        turned = decks.update_item(*self.fs, c["id"], c["markdown"].replace("forward", "reverse"),
                                   linked="alone")
        self.assertEqual("reverse", turned["direction"])

    def test_three_linked_cards_lose_one_and_stay_two(self):
        a, b = self.pair()
        c = decks.add_item(*self.fs, BACK_FIRST.replace("cat", "cow"), now=NOW)
        path = decks.deck_dir(*self.fs) / "items" / (c["id"] + ".json")
        item = json.loads(path.read_text("utf-8"))
        item["link"] = a["link"]
        path.write_text(json.dumps(item), encoding="utf-8")
        self.assertEqual(2, len(self.by_id(a["id"])["mates"]))
        decks.update_item(*self.fs, c["id"], item["markdown"].replace("cow", "calf"), linked="alone")
        self.assertEqual([b["id"]], self.by_id(a["id"])["mates"])
        decks.update_item(*self.fs, a["id"], a["markdown"].replace("back: cat", "back: dog"), linked="both")
        self.assertIn("back: dog", self.by_id(b["id"])["markdown"])
        self.assertIn("calf", self.by_id(c["id"])["markdown"])

    # ------------------------------------------------------------ deleting

    def test_deleting_a_linked_card_asks_what_becomes_of_the_other(self):
        a, b = self.pair()
        with self.assertRaises(decks.Conflict) as e:
            decks.delete_item(*self.fs, a["id"])
        self.assertEqual(("linked", "back"), (e.exception.kind, e.exception.detail["mates"][0]["side"]))
        self.assertEqual(2, len(decks.list_items(*self.fs)))
        with self.assertRaises(decks.DeckError):
            decks.delete_item(*self.fs, a["id"], linked="all")
        self.assertEqual([a["id"]], decks.delete_item(*self.fs, a["id"], linked="alone"))
        (left,) = decks.list_items(*self.fs)
        self.assertEqual((b["id"], [], None), (left["id"], left["mates"], left["link"]))
        self.assertNotIn("link", self.on_disk(b["id"]))
        # an unlinked card is deleted as it always was
        self.assertEqual([b["id"]], decks.delete_item(*self.fs, b["id"]))

    def test_delete_both_takes_the_other_side_and_both_schedules(self):
        a, b = self.pair()
        decks.review(*self.fs, a["id"], "good", None, now=NOW)
        decks.review(*self.fs, b["id"], "good", None, now=NOW)
        gone = decks.delete_item(*self.fs, b["id"], linked="both")
        self.assertEqual({a["id"], b["id"]}, set(gone))
        d = decks.deck_dir(*self.fs)
        self.assertEqual(([], []), (os.listdir(d / "items"), os.listdir(d / "schedule")))

    def test_a_selection_asks_once_for_the_sides_it_leaves_behind(self):
        a, b = self.pair()
        c, e = self.pair(PAIR.replace("cat", "dog"))
        with self.assertRaises(decks.Conflict) as caught:
            decks.bulk_items(*self.fs, [a["id"], c["id"]], "delete")
        self.assertEqual(("linked", 2, {b["id"], e["id"]}),
                         (caught.exception.kind, caught.exception.detail["count"],
                          {m["id"] for m in caught.exception.detail["mates"]}))
        self.assertEqual(4, len(decks.list_items(*self.fs)))
        # both sides of one pair, and nothing of the other: the whole selection is decided at once
        with self.assertRaises(decks.Conflict):
            decks.bulk_items(*self.fs, [a["id"], b["id"], c["id"]], "delete")
        self.assertEqual(2, decks.bulk_items(*self.fs, [a["id"], b["id"]], "delete"))
        self.assertEqual(2, decks.bulk_items(*self.fs, [c["id"]], "delete", linked="both"))
        self.assertEqual([], decks.list_items(*self.fs))
        p, q = self.pair(PAIR.replace("cat", "cow"))
        r, s = self.pair(PAIR.replace("cat", "ox"))
        self.assertEqual(2, decks.bulk_items(*self.fs, [p["id"], r["id"]], "delete", linked="alone"))
        self.assertEqual([([], None), ([], None)], [(i["mates"], i["link"]) for i in decks.list_items(*self.fs)])

    def test_tags_and_schedules_are_never_shared_between_the_sides(self):
        a, b = self.pair()
        decks.bulk_items(*self.fs, [a["id"]], "add-tag", "verbs")
        self.assertEqual(([b["id"]], ["verbs"], []),
                         (self.by_id(a["id"])["mates"], self.by_id(a["id"])["tags"], self.by_id(b["id"])["tags"]))
        decks.review(*self.fs, a["id"], "good", None, now=NOW)
        self.assertEqual(("new", "learning"), (self.by_id(b["id"])["schedule"]["state"],
                                               self.by_id(a["id"])["schedule"]["state"]))
        decks.bulk_items(*self.fs, [a["id"]], "set-new")
        self.assertEqual([b["id"]], self.by_id(a["id"])["mates"])

    # ------------------------------------------------------------ burying

    def test_answering_one_side_buries_the_other_until_the_next_day(self):
        a, b = self.pair()
        self.assertEqual(({"new": 2, "learning": 0, "review": 0}, 0),
                         (lambda n: (n["counts"], n["buried"]))(decks.next_card(*self.fs, now=NOW)))
        decks.review(*self.fs, a["id"], "easy", None, now=NOW)
        n = decks.next_card(*self.fs, now=NOW + timedelta(minutes=5))
        self.assertEqual((True, None, 1, {"new": 0, "learning": 0, "review": 0}, TOMORROW_ROLLOVER),
                         (n["done"], n["item"], n["buried"], n["counts"], n["next_due"]))
        summary = decks.get_deck(*self.fs, now=NOW + timedelta(minutes=5))
        self.assertEqual(({"new": 0, "learning": 0, "review": 0}, 1),
                         (summary["study"], summary["counts"]["new"]))
        # the day starts at the rollover, not at midnight
        self.assertTrue(decks.next_card(*self.fs, now=datetime(2026, 9, 15, 3, 59, tzinfo=TEHRAN))["done"])
        n = decks.next_card(*self.fs, now=LATER)
        self.assertEqual((b["id"], 0), (n["item"]["id"], n["buried"]))
        # ... and answering it buries nothing: the front is not due for days
        decks.review(*self.fs, b["id"], "easy", None, now=LATER)
        self.assertTrue(decks.next_card(*self.fs, now=LATER)["done"])
        self.assertEqual(0, decks.next_card(*self.fs, now=LATER)["buried"])

    def test_a_learning_step_buries_too_and_the_card_itself_comes_back(self):
        a, b = self.pair()
        decks.review(*self.fs, a["id"], "again", None, now=NOW)
        n = decks.next_card(*self.fs, now=NOW + timedelta(minutes=2))
        self.assertEqual((a["id"], 1), (n["item"]["id"], n["buried"]))
        decks.review(*self.fs, a["id"], "good", None, now=NOW + timedelta(minutes=2))
        n = decks.next_card(*self.fs, now=NOW + timedelta(minutes=13))
        self.assertEqual((a["id"], 1), (n["item"]["id"], n["buried"]))

    def test_a_side_that_is_not_due_is_not_touched(self):
        a, b = self.pair()
        decks.review(*self.fs, b["id"], "easy", None, now=NOW - timedelta(days=1))
        decks.review(*self.fs, a["id"], "easy", None, now=NOW)
        n = decks.next_card(*self.fs, now=NOW)
        self.assertEqual((True, 0), (n["done"], n["buried"]))                # b is due in days anyway

    def test_unlinked_cards_are_never_buried(self):
        x = decks.add_item(*self.fs, CHOICE, now=NOW)["id"]
        y = decks.add_item(*self.fs, FLASH, now=NOW + timedelta(seconds=1))["id"]
        decks.review(*self.fs, x, "easy", None, now=NOW)
        n = decks.next_card(*self.fs, now=NOW)
        self.assertEqual((y, 0), (n["item"]["id"], n["buried"]))

    def test_the_hold_ends_when_the_other_side_is_unlinked_deleted_or_set_new(self):
        for how in ("edited alone", "deleted alone", "set new", "deleted both"):
            _s, fs = self.deck("Hold %s" % how)
            a, b = decks.add_item(*fs, PAIR, now=NOW)["items"]
            decks.review(*fs, a["id"], "easy", None, now=NOW)
            self.assertTrue(decks.next_card(*fs, now=NOW)["done"], how)
            if how == "edited alone":
                decks.update_item(*fs, b["id"], b["markdown"].replace("cat", "dog"), linked="alone")
            elif how == "deleted alone":
                decks.delete_item(*fs, a["id"], linked="alone")
            elif how == "set new":
                decks.bulk_items(*fs, [a["id"]], "set-new")
            else:
                decks.delete_item(*fs, a["id"], linked="both")
            n = decks.next_card(*fs, now=NOW)
            self.assertEqual(how == "deleted both", n["done"], how)
            # set new: the front is new again, and comes first; the back is offered with it
            if how != "deleted both":
                self.assertEqual(a["id"] if how == "set new" else b["id"], n["item"]["id"], how)
                self.assertEqual(0, n["buried"], how)

    def test_the_hold_does_not_use_up_a_days_new_cards(self):
        decks.update_deck(*self.fs, settings={"new_per_day": 2})
        a, b = self.pair()
        c = decks.add_item(*self.fs, CHOICE, now=NOW + timedelta(seconds=1))["id"]
        decks.review(*self.fs, a["id"], "easy", None, now=NOW)
        n = decks.next_card(*self.fs, now=NOW)
        self.assertEqual((c, {"new": 1, "learning": 0, "review": 0}, 1), (n["item"]["id"], n["counts"], n["buried"]))
        decks.review(*self.fs, c, "easy", None, now=NOW)
        self.assertTrue(decks.next_card(*self.fs, now=NOW)["done"])
        # tomorrow: the limit is fresh, and the back is the one new card
        self.assertEqual(b["id"], decks.next_card(*self.fs, now=LATER)["item"]["id"])

    def test_skipping_a_side_does_not_bury_the_other(self):
        a, b = self.pair()
        n = decks.next_card(*self.fs, now=NOW, skip=[a["id"]])
        self.assertEqual((b["id"], 0), (n["item"]["id"], n["buried"]))

    def test_cramming_ignores_the_hold(self):
        a, b = self.pair()
        decks.review(*self.fs, a["id"], "easy", None, now=NOW)
        self.assertEqual([a["id"], b["id"]], [i["id"] for i in decks.cram_items(*self.fs, [a["id"], b["id"]])])

    def test_an_answer_replayed_from_a_phone_buries_by_the_day_it_was_given(self):
        a, b = self.pair()
        decks.review(*self.fs, a["id"], "easy", None, now=NOW - timedelta(days=1), by="phone")
        self.assertEqual(b["id"], decks.next_card(*self.fs, now=NOW)["item"]["id"])
        decks.review(*self.fs, b["id"], "easy", None, now=NOW, by="phone")
        self.assertEqual(0, decks.next_card(*self.fs, now=NOW)["buried"])


class DirectionLineTests(unittest.TestCase):
    """mdparser.set_block_direction: the line the PARSER read as the
    `direction` field is the one rewritten -- never one a search of the text
    finds, for the two can disagree."""

    def check(self, source, want_line=None, value="reverse"):
        import mdparser
        out = mdparser.set_block_direction(source, value)
        _fm, blocks = mdparser.parse(out)
        self.assertEqual(1, len(blocks))
        self.assertEqual(([], value), (blocks[0]["errors"], blocks[0]["fields"]["direction"]))
        if want_line is not None:
            self.assertEqual(want_line, out)
        return out

    def test_a_line_is_replaced_in_place_a_missing_one_goes_under_the_opening(self):
        self.check(":::exercise flashcard\nfront: a\ndirection: both-repeat\nback: b\n:::",
                   ":::exercise flashcard\nfront: a\ndirection: reverse\nback: b\n:::")
        self.check(":::exercise flashcard\nfront: a\nback: b\n:::",
                   ":::exercise flashcard\ndirection: reverse\nfront: a\nback: b\n:::")
        self.check(":::exercise flashcard\nfront: a\ndirection:     forward   \nback: b\n:::",
                   ":::exercise flashcard\nfront: a\ndirection: reverse\nback: b\n:::")
        # around it, as written: blank lines, an indented line, CRLF
        self.check("\n\n:::exercise flashcard\n  direction: both-repeat\nfront: a\nback: b\n:::\n",
                   "\n\n:::exercise flashcard\n  direction: reverse\nfront: a\nback: b\n:::\n")
        self.check(":::exercise flashcard\r\nfront: a\r\ndirection: both-repeat\r\nback: b\r\n:::",
                   ":::exercise flashcard\nfront: a\ndirection: reverse\nback: b\n:::")

    def test_a_block_written_direction_pipe_becomes_one_line(self):
        self.check(":::exercise flashcard\nfront: a\ndirection: |\n  both-repeat\nback: b\n:::",
                   ":::exercise flashcard\nfront: a\ndirection: reverse\nback: b\n:::")
        self.check(":::exercise flashcard\nfront: a\nback: b\ndirection: |\n:::",
                   ":::exercise flashcard\nfront: a\nback: b\ndirection: reverse\n:::")

    def test_the_line_the_parser_reads_is_the_one_rewritten(self):
        # the parser takes an unindented `direction:` under a card's own field as the field
        # (it is a line that starts with a key), so that is the line to change -- and a
        # `direction:` that only looks like one, inside another field's block, is left alone
        jolly = ":::exercise flashcard\ncard-type: jolly\nfront-primary: a\n  direction: x\nback-primary: b\n:::"
        self.check(jolly, jolly.replace("direction: x", "direction: reverse"))
        inside = (":::exercise flashcard\ncard-type: jolly\nfront-primary: |\n  the word direction: here\n"
                  "  is text\nback-primary: b\n:::")
        self.check(inside, inside.replace(":::exercise flashcard\n",
                                          ":::exercise flashcard\ndirection: reverse\n", 1))
        # the last of two is the one the parser keeps
        twice = ":::exercise flashcard\ndirection: forward\nfront: a\ndirection: both-repeat\nback: b\n:::"
        self.assertEqual(":::exercise flashcard\ndirection: forward\nfront: a\ndirection: reverse\nback: b\n:::",
                         self.check(twice))

    def test_what_it_refuses(self):
        import mdparser
        for value in ("Reverse", "", "two words", "-x", None, 3):
            with self.assertRaises(ValueError):
                mdparser.set_block_direction(":::exercise flashcard\nfront: a\nback: b\n:::", value)
        for text in ("just words", "", "# heading\n\n> :::exercise flashcard\n> front: a\n> back: b\n> :::"):
            with self.assertRaises(ValueError):
                mdparser.set_block_direction(text, "reverse")
        # the first exercise of a text, wherever it stands
        text = "# heading\n\n:::exercise flashcard\nfront: a\nback: b\n:::\n"
        self.assertEqual("# heading\n\n:::exercise flashcard\ndirection: reverse\nfront: a\nback: b\n:::\n",
                         mdparser.set_block_direction(text, "reverse"))


CHAIN = (":::exercise follow-up\nprompt: Read, then answer.\n"
         "::::exercise single-choice\nprompt: Where?\n- [ ] home\n- [x] station\n::::\n"
         "::::exercise true-false\n- Late. => true\n::::\n"
         "::::exercise flashcard\ncard-type: vocab\ntarget: [binario]{tl}\nmeaning: platform\n::::\n:::")


class FollowUpTests(Base):
    """A follow-up (a0.5.4) is ONE exercise of a deck: counted once, scheduled once, copied whole; its history rows
    carry how many of its scored steps were right."""

    def test_it_is_one_exercise_that_says_how_long_it_is(self):
        s, fs = self.deck("Dialoghi", "it")
        item = decks.add_item(*fs, CHAIN, now=NOW)
        self.assertEqual(("follow-up", "Follow-up questions", 3, [], "Read, then answer."),
                         (item["subtype"], item["label"], item["steps"], item["errors"], item["excerpt"]))
        decks.add_item(*fs, CHOICE.replace("fa", "it"), now=NOW + timedelta(seconds=1))
        self.assertEqual(2, len(decks.list_items(*fs)))
        self.assertEqual(2, decks.next_card(*fs, now=NOW)["counts"]["new"])
        self.assertEqual(0, decks.list_items(*fs)[1]["steps"])

    def test_with_no_prompt_its_excerpt_is_its_first_steps(self):
        s, fs = self.deck("Dialoghi", "it")
        item = decks.add_item(*fs, CHAIN.replace("prompt: Read, then answer.\n", ""), now=NOW)
        self.assertEqual("Where?", item["excerpt"])

    def test_a_step_with_a_mistake_refuses_the_whole_exercise_and_says_which(self):
        s, fs = self.deck("Dialoghi", "it")
        with self.assertRaises(decks.DeckError) as e:
            decks.add_item(*fs, CHAIN.replace("- [x] station", "- [ ] station"), now=NOW)
        self.assertIn("step 1: single-choice exercise needs exactly one [x] answer", str(e.exception))
        with self.assertRaises(decks.DeckError) as e:
            decks.add_item(*fs, ":::exercise follow-up\n::::exercise single-choice\n- [x] a\n- [ ] b\n::::\n:::", now=NOW)
        self.assertIn("at least two steps", str(e.exception))
        self.assertEqual([], decks.list_items(*fs))

    def test_copying_from_a_page_takes_the_follow_up_whole_and_a_step_alone_if_asked(self):
        body = (":::exercise single-choice\nprompt: A\n- [x] a\n- [ ] b\n:::\n\n" + CHAIN + "\n\n"
                ":::exercise single-choice\nprompt: B\n- [x] a\n- [ ] b\n:::\n")
        meta = self.doc(body, target="it")
        # the page numbers the follow-up 2 and its three steps 3-5, so B is the sixth
        for ordinal, subtype, steps, excerpt in ((2, "follow-up", 3, "Read, then answer."), (3, "single-choice", 0, "Where?"),
                                                 (5, "flashcard", 0, ""), (6, "single-choice", 0, "B")):
            s, fs = self.deck("From %d" % ordinal, "it")
            got = decks.copy_from_doc(*fs, meta["id"], ordinal, subtype, meta["updated"], now=NOW)["item"]
            self.assertEqual((got["subtype"], got["steps"], got["origin"]["ordinal"]), (subtype, steps, ordinal))
            if excerpt:
                self.assertEqual(excerpt, got["excerpt"])
        s, fs = self.deck("Whole", "it")
        got = decks.copy_from_doc(*fs, meta["id"], 2, "follow-up", meta["updated"], now=NOW)["item"]
        self.assertEqual(CHAIN, got["markdown"])
        # a type that is not the one on the page at that place is refused, as it is for any exercise
        with self.assertRaises(decks.DeckError):
            decks.copy_from_doc(*fs, meta["id"], 3, "follow-up", meta["updated"], now=NOW)

    def test_the_history_keeps_how_many_steps_were_right(self):
        s, fs = self.deck("Dialoghi", "it")
        a = decks.add_item(*fs, CHAIN, now=NOW)["id"]
        row = decks.review(*fs, a, "again", False, now=NOW, steps={"right": 1, "of": 2})
        hist = decks._read_schedule(decks.deck_dir(*fs), a)["history"]
        self.assertEqual([("again", False, {"right": 1, "of": 2})], [(h["rating"], h["result"], h["steps"]) for h in hist])
        self.assertEqual("learning", row["schedule"]["state"])
        # an exercise that is not a chain has no such field
        b = decks.add_item(*fs, CHOICE.replace("fa", "it"), now=NOW + timedelta(seconds=1))["id"]
        decks.review(*fs, b, "good", True, now=NOW)
        self.assertNotIn("steps", decks._read_schedule(decks.deck_dir(*fs), b)["history"][0])

    def test_a_count_that_does_not_add_up_is_not_kept(self):
        s, fs = self.deck("Dialoghi", "it")
        a = decks.add_item(*fs, CHAIN, now=NOW)["id"]
        for n, bad in enumerate(({"right": 3, "of": 2}, {"right": -1, "of": 2}, {"right": "1", "of": 2}, {"right": True, "of": 2},
                                 {"right": 1}, [1, 2], "1/2", 5, {"right": 1, "of": 5000})):
            decks.review(*fs, a, "again", False, now=NOW + timedelta(minutes=n), steps=bad)
        hist = decks._read_schedule(decks.deck_dir(*fs), a)["history"]
        self.assertEqual(9, len(hist))
        self.assertTrue(all("steps" not in h for h in hist))

    def test_an_answer_made_away_carries_its_steps_to_the_computer(self):
        s, fs = self.deck("Dialoghi", "it")
        a = decks.add_item(*fs, CHAIN, now=NOW)["id"]
        decks.checkout(*fs, "a phone", "phone-1", now=NOW)
        out = decks.answers_from(*fs, "phone-1", [{"item": a, "rating": "good", "result": True, "steps": {"right": 2, "of": 2},
                                                   "at": NOW.isoformat()}])
        self.assertEqual((1, []), (out["applied"], out["refused"]))
        hist = decks._read_schedule(decks.deck_dir(*fs), a)["history"]
        self.assertEqual({"right": 2, "of": 2}, hist[0]["steps"])

    def test_the_steps_travel_in_an_export_with_the_scheduling(self):
        s, fs = self.deck("Dialoghi", "it")
        a = decks.add_item(*fs, CHAIN, now=NOW)["id"]
        decks.review(*fs, a, "again", False, now=NOW, steps={"right": 1, "of": 2})
        data, _name = decks.export_zip(*fs, True)
        got = decks.import_zip(data, scheduling=True, mode="copy")
        deck = got.get("deck") or {}
        fs2 = (deck.get("folder"), deck.get("slug"))
        self.assertNotEqual(fs, fs2)
        items = decks.list_items(*fs2)
        self.assertEqual([("follow-up", 3)], [(i["subtype"], i["steps"]) for i in items])
        hist = decks._read_schedule(decks.deck_dir(*fs2), items[0]["id"])["history"]
        self.assertEqual({"right": 1, "of": 2}, hist[0]["steps"])

    def test_exercises_of_a_page_become_one_follow_up_with_the_files_of_every_step(self):
        meta = self.doc(":::exercise single-choice\nprompt: A\nimage: images/cat.png\n- [x] a\n- [ ] b\n:::\n\n"
                        ":::exercise true-false\n- B => true\n:::\n\n"
                        ":::exercise single-choice\nprompt: C\naudio: audio/tone.mp3\n- [x] a\n- [ ] b\n:::\n",
                        target="it", images={"cat.png": PNG}, audio={"tone.mp3": b"ID3 not really"})
        s, fs = self.deck("Dialoghi", "it")
        out = decks.copy_from_doc(*fs, meta["id"], None, "follow-up", meta["updated"], now=NOW, ordinals=[3, 1, 2])
        item = out["item"]
        self.assertEqual(("follow-up", 3, "Follow-up of 3 exercises"), (item["subtype"], item["steps"], item["origin"]["label"]))
        # the steps are in the order given, one fence deeper
        self.assertEqual(["::::exercise single-choice", "::::exercise single-choice", "::::exercise true-false"],
                         [l for l in item["markdown"].split("\n") if l.startswith("::::exercise")])
        self.assertLess(item["markdown"].index("prompt: C"), item["markdown"].index("prompt: A"))
        self.assertEqual((["cat.png"], ["tone.mp3"]), (self.deck_images(fs), sorted(self.deck_files(fs, "audio"))))
        self.assertEqual(1, len(decks.list_items(*fs)))
        # the same chain twice is refused, and a different order is a different chain
        with self.assertRaises(decks.Conflict) as e:
            decks.copy_from_doc(*fs, meta["id"], None, "follow-up", meta["updated"], now=NOW, ordinals=[3, 1, 2])
        self.assertEqual("duplicate", e.exception.code if hasattr(e.exception, "code") else "duplicate")
        # what cannot be made one
        for bad in ([1], [1, 1], [1, 9], "1,2", [1, 2, 3, 4] * 40):
            with self.assertRaises((decks.DeckError, decks.Conflict)):
                decks.copy_from_doc(*fs, meta["id"], None, "follow-up", meta["updated"], now=NOW, ordinals=bad)

    def test_a_follow_up_cannot_be_a_step_of_another_when_made_from_a_page(self):
        meta = self.doc(CHAIN.replace(":::exercise follow-up", ":::exercise follow-up") + "\n\n"
                        ":::exercise true-false\n- B => true\n:::\n", target="it")
        s, fs = self.deck("Dialoghi", "it")
        # the page numbers the chain 1, its three steps 2-4 and the true/false 5
        with self.assertRaises(decks.DeckError) as e:
            decks.copy_from_doc(*fs, meta["id"], None, "follow-up", meta["updated"], now=NOW, ordinals=[1, 5])
        self.assertIn("a follow-up cannot be a step of another", str(e.exception))

    def test_a_follow_ups_files_travel_in_an_export(self):
        meta = self.doc(":::exercise single-choice\nprompt: A\nimage: images/cat.png\n- [x] a\n- [ ] b\n:::\n\n"
                        ":::exercise true-false\n- B => true\n:::\n", target="it", images={"cat.png": PNG})
        s, fs = self.deck("Dialoghi", "it")
        decks.copy_from_doc(*fs, meta["id"], None, "follow-up", meta["updated"], now=NOW, ordinals=[1, 2])
        data, _name = decks.export_zip(*fs, False)
        names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        self.assertIn("images/cat.png", names)         # named by a step, so the deck keeps it and the export carries it
        got = decks.import_zip(data, scheduling=False, mode="copy")
        fs2 = (got["deck"]["folder"], got["deck"]["slug"])
        self.assertEqual((["cat.png"], 1), (self.deck_images(fs2), len(decks.list_items(*fs2))))
        self.assertEqual(2, decks.list_items(*fs2)[0]["steps"])


if __name__ == "__main__":
    unittest.main()
