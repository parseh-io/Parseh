# SPDX-License-Identifier: GPL-3.0-or-later
"""The pictures and the recording the starters show
(markdown/exlex/starters/assets/; store.starter_media, adopt_starter_media;
htmlgen's asset base; server.api_preview, serve_starter_media).

    python3 -m unittest discover -s tests -p test_starter_media.py

A new document is its language's starter, and a starter may show a picture
and a recording wherever the dialect puts one.  The document holds no files
yet, so the files those lines name ship beside the starters, and a save -- the
first one or any later one -- gives the document its own copy of each it names
and lacks, never over a file of its own, and never again once the owner has
deleted it (its meta.json lists what it has held); the renderer draws a
placeholder for a file its asset base gives no URL, and until a save has
copied one in, the editor's preview shows it from where the starters keep it.  Driven
through the studio's own routes on a temporary library (a fake handler, and
the real handler on a socket); the PDF of such a document is built by the
studio's own build when xelatex is here."""
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
import xml.etree.ElementTree as ET
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "markdown" / "exlex", ROOT / "markdown" / "app",
               ROOT / "lib", ROOT / "youtube" / "lib"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import audiofile  # noqa: E402
import clips      # noqa: E402
import htmlgen    # noqa: E402
import server     # noqa: E402
import store      # noqa: E402

ASSETS = ROOT / "markdown" / "exlex" / "starters" / "assets"
APPLE = ASSETS / "images" / "starter-apple.svg"
HOUSE = ASSETS / "images" / "starter-house.svg"
CHIME = ASSETS / "audio" / "starter-chime.mp3"
SVG_NS = "{http://www.w3.org/2000/svg}"

try:
    import pymupdf
except ImportError:
    pymupdf = None

HEAD = """---
title: Starter pictures
subtitle: a picture and a recording everywhere
note: a test document
lang: en
target: %s
---
"""
# everywhere the dialect puts a picture or a recording, naming the starter's
# files -- and one picture of the document's own, which it does not hold
EVERYWHERE = """
![an apple](images/starter-apple.svg)

![a chime](audio/starter-chime.mp3)

![a cat of its own](images/cat.png)

:::exercise flashcard
card-type: vocab
target: [house]{tl}
meaning: a building to live in
front-image: images/starter-house.svg
back-audio: audio/starter-chime.mp3
:::

:::exercise single-choice
image: images/starter-apple.svg
audio: audio/starter-chime.mp3
prompt: What is it?
- [x] an apple
- [ ] a house
:::
"""


class Fake:
    """What the studio's routes use of a handler, recording the answer."""

    def __init__(self, body=None, query=""):
        self.body = body
        self.query = urllib.parse.parse_qs(query)
        self.sent = None

    def _json_body(self):
        return self.body

    def send_json(self, payload, status=200):
        self.sent = (status, payload)

    def send_file(self, path, download_name=None, inline_type=None):
        # read now: a route may delete its temporary file once the answer is sent (the studio's Backup)
        self.sent = ("file", Path(path), download_name, Path(path).read_bytes())

    def send_bytes(self, data, ctype, status=200, headers=None):
        self.sent = (status, ctype, data)


def srcs(html):
    """(tag, src) of every picture and player a page draws, in order."""
    return re.findall(r'<(img|audio)\b[^>]*\bsrc="([^"]*)"', html)


class LibraryCase(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory(prefix="parseh-starter-media-")
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name)
        self.lib = self.tmp / "library"
        self.lib.mkdir()
        was = store.use_library(self.lib)
        self.addCleanup(store.use_library, was)
        # an empty clip tray: nothing here may come from the real one
        (self.tmp / "clips").mkdir()
        was_tray = store.CLIPS_DIR
        store.set_clips_dir(self.tmp / "clips")
        self.addCleanup(store.set_clips_dir, was_tray)

    @staticmethod
    def head(target, title="Starter pictures"):
        """HEAD under another title: a document's name is its title, and no
        two documents of one library share one (store, "names")."""
        return (HEAD % target).replace("title: Starter pictures", "title: " + title, 1)

    def create(self, body="", target="en"):
        # the first document is "Starter pictures", the next ones numbered
        self.made = getattr(self, "made", 0) + 1
        title = "Starter pictures" if self.made == 1 else "Starter pictures %d" % self.made
        h = Fake({"markdown": self.head(target, title) + body})
        server.api_create(h)
        self.assertEqual(h.sent[0], 201, h.sent)
        return h.sent[1]["meta"]["id"]

    def save(self, doc, body, target="en"):
        # saved under the name it has, so a save is never a rename
        h = Fake({"markdown": self.head(target, store.get(doc)[0]["title"]) + body})
        server.api_save(h, doc)
        self.assertEqual(h.sent[0], 200, h.sent)

    def files(self, doc, sub):
        d = store.doc_dir(doc) / sub
        return sorted(p.name for p in d.iterdir()) if d.is_dir() else []

    def preview(self, body, doc_id=None, target="en"):
        h = Fake({"markdown": HEAD % target + body, "doc_id": doc_id or ""})
        server.api_preview(h)
        self.assertTrue(h.sent[1]["ok"], h.sent)
        return h.sent[1]["doc"]["html"]


# ---------------------------------------------------------------- the files

class ShippedFiles(unittest.TestCase):
    def test_each_is_there_under_a_name_a_document_may_hold(self):
        for kind, f in (("images", APPLE), ("images", HOUSE), ("audio", CHIME)):
            self.assertTrue(f.is_file(), f)
            self.assertEqual(store.starter_media(kind, f.name), f)
        self.assertTrue(store.IMG_NAME_RE.match(APPLE.name) and store.IMG_NAME_RE.match(HOUSE.name))
        self.assertTrue(audiofile.NAME_RE.match(CHIME.name))
        # and whatever else is added beside them: a `starter-` name a
        # document's own file could have, so a save can copy it in
        for kind in ("images", "audio"):
            for f in (ASSETS / kind).iterdir():
                self.assertTrue(f.name.startswith("starter-"), f)
                self.assertEqual(store.starter_media(kind, f.name), f)

    def test_every_file_a_starter_names_is_shipped(self):
        # a starter naming a picture nobody ships would open every new
        # document of its language on a missing file
        import languages
        for L in languages.LANGS.values():
            md = server.new_template(L.code)
            for kind in ("images", "audio"):
                for name in store._named(md, kind):
                    self.assertIsNotNone(store.starter_media(kind, name),
                                         "the %s starter names %s/%s" % (L.code, kind, name))

    def test_the_pictures_are_small_self_contained_svg(self):
        for f in (APPLE, HOUSE):
            data = f.read_bytes()
            self.assertLess(len(data), 4096, f.name)
            self.assertEqual(store._img_kind(data), ".svg")
            root = ET.fromstring(data)
            self.assertEqual(root.tag, SVG_NS + "svg")
            self.assertEqual(root.get("version"), "1.1")
            self.assertEqual(root.get("viewBox"), "0 0 200 200")
            tags = {el.tag.replace(SVG_NS, "") for el in root.iter()}
            self.assertFalse(tags & {"script", "text", "image", "foreignObject", "use", "style"},
                             "%s: no script, no text, nothing fetched" % f.name)
            for el in root.iter():
                for attr, value in el.attrib.items():
                    self.assertNotIn("href", attr, f.name)
                    self.assertFalse(attr.startswith("on"), f.name)
                    self.assertNotIn("url(", value, f.name)

    @unittest.skipUnless(pymupdf, "PyMuPDF is not installed: the PDF build cannot turn an SVG into a PDF")
    def test_the_pdf_build_can_read_the_pictures(self):
        # what envsetup.stage_images does with every SVG before XeLaTeX sees it
        for f in (APPLE, HOUSE):
            with pymupdf.open(str(f)) as svg:
                pdf = svg.convert_to_pdf()
            with pymupdf.open("pdf", pdf) as doc:
                self.assertEqual(doc.page_count, 1)
                self.assertTrue(doc[0].get_drawings(), "%s is drawn, not blank" % f.name)

    def test_the_recording_is_a_short_small_mp3(self):
        data = CHIME.read_bytes()
        self.assertLess(len(data), 40 * 1024)
        self.assertEqual(audiofile.kind(data, CHIME.name), ".mp3")
        seconds = clips.plays(str(CHIME))
        if seconds is None:
            self.skipTest("no ffmpeg here to hear how long it is")
        self.assertAlmostEqual(seconds, 1.5, delta=0.3)
        ffprobe = shutil.which("ffprobe")
        if ffprobe:
            out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "stream=channels",
                                  "-of", "csv=p=0", str(CHIME)], capture_output=True, text=True)
            self.assertEqual(out.stdout.strip(), "1", "mono")

    def test_only_a_shipped_file_is_one(self):
        self.assertIsNone(store.starter_media("images", "cat.png"))
        self.assertIsNone(store.starter_media("audio", "starter-apple.svg"), "a picture is not a recording")
        self.assertIsNone(store.starter_media("images", "starter-chime.mp3"))
        self.assertIsNone(store.starter_media("images", "starter-apple.svg.pdf"), "a twin is made, never shipped")
        self.assertIsNone(store.starter_media("images", "../images/starter-apple.svg"))
        self.assertIsNone(store.starter_media("fonts", "starter-apple.svg"))
        self.assertIsNone(store.starter_media("images", ""))


# ---------------------------------------------------------------- on save

class AdoptTests(LibraryCase):
    def test_creating_a_document_gives_it_its_own_copy_of_what_it_names(self):
        doc = self.create(EVERYWHERE)
        self.assertEqual(self.files(doc, "images"), ["starter-apple.svg", "starter-house.svg"])
        self.assertEqual(self.files(doc, "audio"), ["starter-chime.mp3"])
        d = store.doc_dir(doc)
        self.assertEqual((d / "images" / "starter-apple.svg").read_bytes(), APPLE.read_bytes())
        self.assertEqual((d / "images" / "starter-house.svg").read_bytes(), HOUSE.read_bytes())
        self.assertEqual((d / "audio" / "starter-chime.mp3").read_bytes(), CHIME.read_bytes())
        # the document's own files now: listed as in use, and taken away in its zip
        self.assertEqual([(i["name"], i["referenced"]) for i in store.list_images(doc)],
                         [("starter-apple.svg", True), ("starter-house.svg", True)])
        self.assertEqual([(r["name"], r["referenced"]) for r in store.list_audio(doc)],
                         [("starter-chime.mp3", True)])
        z = zipfile.ZipFile(io.BytesIO(store.doc_zip(doc, "starter")))
        self.assertEqual(sorted(z.namelist()), ["audio/starter-chime.mp3", "images/starter-apple.svg",
                                                "images/starter-house.svg", "starter.md"])
        # and the tray is asked for nothing the starter already gave
        self.assertEqual(server._adopt(doc), {"adopted": [], "missing": ["images/cat.png"]})

    def test_only_what_the_document_names_comes_in(self):
        doc = self.create("\nNo pictures at all.\n")
        self.assertEqual((self.files(doc, "images"), self.files(doc, "audio")), ([], []))
        self.assertFalse((store.doc_dir(doc) / "images").exists(), "no empty folder is made")
        doc = self.create("\n![a house](images/starter-house.svg)\n")
        self.assertEqual((self.files(doc, "images"), self.files(doc, "audio")),
                         (["starter-house.svg"], []))

    def test_a_later_save_brings_in_what_it_newly_names(self):
        doc = self.create("\nNothing yet.\n")
        self.save(doc, "\nA recording now:\n\n![a chime](audio/starter-chime.mp3)\n")
        self.assertEqual(self.files(doc, "audio"), ["starter-chime.mp3"])
        self.assertEqual(self.files(doc, "images"), [])
        self.save(doc, EVERYWHERE)
        self.assertEqual(self.files(doc, "images"), ["starter-apple.svg", "starter-house.svg"])

    def test_a_file_of_the_documents_own_is_never_replaced(self):
        doc = self.create("\nNothing yet.\n")
        mine = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
                b'<rect width="10" height="10" fill="#123456"/></svg>')
        self.assertEqual(store.save_image(doc, "starter-apple.svg", mine), "starter-apple.svg")
        (store.audio_dir(doc)).mkdir()
        (store.audio_dir(doc) / "starter-chime.mp3").write_bytes(b"the owner's own recording")
        self.save(doc, EVERYWHERE)
        self.assertEqual((store.images_dir(doc) / "starter-apple.svg").read_bytes(), mine)
        self.assertEqual((store.audio_dir(doc) / "starter-chime.mp3").read_bytes(),
                         b"the owner's own recording")
        self.assertEqual(self.files(doc, "images"), ["starter-apple.svg", "starter-house.svg"],
                         "what it lacked came in beside it, and nothing was renamed")
        self.assertEqual(store.adopt_starter_media(doc), [], "nothing more to bring")
        # held all the same: the owner's own, deleted, is not made up for
        self.assertEqual(store.starter_media_held(doc), {"images/starter-apple.svg",
                                                         "images/starter-house.svg",
                                                         "audio/starter-chime.mp3"})
        store.delete_image(doc, "starter-apple.svg")
        self.save(doc, EVERYWHERE)
        self.assertEqual(self.files(doc, "images"), ["starter-house.svg"])

    def test_a_copy_the_owner_deleted_stays_deleted(self):
        # the ✕ in Images... or Recordings... is the owner's say, as for any
        # file of the document's: no save copies it in again, while the text
        # still names it or when it names it afresh
        doc = self.create(EVERYWHERE)
        self.assertEqual(store.starter_media_held(doc), {"images/starter-apple.svg",
                                                         "images/starter-house.svg",
                                                         "audio/starter-chime.mp3"})
        self.assertEqual(sorted(json.loads((store.doc_dir(doc) / "meta.json").read_text())
                                ["starter_media"]),
                         ["audio/starter-chime.mp3", "images/starter-apple.svg",
                          "images/starter-house.svg"])
        store.delete_image(doc, "starter-house.svg")
        store.delete_audio(doc, "starter-chime.mp3")
        self.save(doc, EVERYWHERE)
        self.assertEqual((self.files(doc, "images"), self.files(doc, "audio")),
                         (["starter-apple.svg"], []))
        self.assertEqual(store.adopt_starter_media(doc), [])
        self.save(doc, "\nNo pictures now.\n")
        self.save(doc, EVERYWHERE, target="fa")       # named again, and moved to persian/
        self.assertEqual(store.doc_dir(doc).parent.name, "persian")
        self.assertEqual((self.files(doc, "images"), self.files(doc, "audio")),
                         (["starter-apple.svg"], []))
        self.assertEqual(len(store.starter_media_held(doc)), 3, "the record moved with it")
        # a picture the owner uploads under that name is theirs, and stays
        mine = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
                b'<rect width="10" height="10" fill="#654321"/></svg>')
        self.assertEqual(store.save_image(doc, "starter-house.svg", mine), "starter-house.svg")
        self.save(doc, EVERYWHERE, target="fa")
        self.assertEqual((store.images_dir(doc) / "starter-house.svg").read_bytes(), mine)

    def test_a_record_that_is_no_list_is_read_as_none(self):
        doc = self.create("\nNothing yet.\n")
        d = store.doc_dir(doc)
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        meta["starter_media"] = "images/starter-apple.svg"       # edited by hand
        (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        self.assertEqual(store.starter_media_held(doc), set())
        self.save(doc, "\n![an apple](images/starter-apple.svg)\n")
        self.assertEqual(self.files(doc, "images"), ["starter-apple.svg"])
        self.assertEqual(store.starter_media_held(doc), {"images/starter-apple.svg"})
        self.assertEqual(store.starter_media_held("no-such-doc"), set())

    def test_a_duplicate_and_a_backup_keep_the_list(self):
        doc = self.create(EVERYWHERE)
        store.delete_image(doc, "starter-house.svg")
        copy = store.duplicate(doc)["id"]
        self.assertEqual(store.starter_media_held(copy), store.starter_media_held(doc))
        self.assertEqual(store.get(copy)[0]["title"], store.get(doc)[0]["title"] + " (copy)")
        self.save(copy, EVERYWHERE)
        self.assertEqual(self.files(copy, "images"), ["starter-apple.svg"],
                         "deleted in the original, deleted in its copy")
        # the library's Backup, put back over an emptied library
        h = Fake()
        server.api_export(h)
        # sent from a file in Parseh's .tmp/ (a library carries every recording), named as a zip
        self.assertEqual(h.sent[0], "file")
        self.assertTrue(h.sent[2].endswith(".zip"), h.sent[2])
        shutil.rmtree(store.doc_dir(doc))
        self.assertEqual(store.import_library(h.sent[3])["restored"], [doc])
        self.assertEqual(len(store.starter_media_held(doc)), 3)
        self.save(doc, EVERYWHERE)
        self.assertEqual(self.files(doc, "images"), ["starter-apple.svg"],
                         "deleted before the backup, deleted after it")

    def test_a_zip_without_them_takes_them_from_the_starters(self):
        # "Download N shown" as .md sources, uploaded again: the starters'
        # files are not in the zip, and are no reason for a warning
        buf = io.BytesIO()
        mine = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
                b'<circle cx="5" cy="5" r="4"/></svg>')
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("bare.md", HEAD % "fa" + EVERYWHERE)
            z.writestr("own/own.md", self.head("ja", "Its own apple") + "\n![](images/starter-apple.svg)\n")
            z.writestr("own/images/starter-apple.svg", mine)
        out = store.import_zip(buf.getvalue())
        self.assertEqual(out["warnings"], ["bare.md: images/cat.png is not in the zip"])
        bare, own = (m["id"] for m in out["docs"])
        self.assertEqual(self.files(bare, "images"), ["starter-apple.svg", "starter-house.svg"])
        self.assertEqual(self.files(bare, "audio"), ["starter-chime.mp3"])
        self.assertEqual((store.images_dir(bare) / "starter-apple.svg").read_bytes(), APPLE.read_bytes())
        self.assertEqual((store.images_dir(own) / "starter-apple.svg").read_bytes(), mine,
                         "the zip's own file under that name is the one kept")

    def test_a_markdown_given_is_read_instead_of_the_saved_one(self):
        doc = self.create("\nNothing yet.\n")
        self.assertEqual(store.adopt_starter_media(doc, "![](images/starter-house.svg)\n"),
                         ["images/starter-house.svg"])
        self.assertEqual(store.adopt_starter_media(doc), [], "the saved source names none")
        with self.assertRaises(KeyError):
            store.adopt_starter_media("no-such-doc", "")

    def test_a_copy_that_fails_never_fails_the_save(self):
        doc = self.create("\nNothing yet.\n")
        body = "\n![an apple](images/starter-apple.svg)\n"
        with mock.patch.object(store, "adopt_starter_media", side_effect=OSError("disk full")), \
                mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self.save(doc, body)
            made = Fake({"markdown": self.head("en", "Another apple") + body})
            server.api_create(made)
        self.assertEqual(store.get(doc)[1], HEAD % "en" + body)
        self.assertEqual(made.sent[0], 201)
        self.assertIn("disk full", err.getvalue())

    def test_every_language_and_a_notes_mount_alike(self):
        # the files are the same whatever the language, and a note beside a
        # book or a video (another library, another prefix) is a document
        # like any other
        import languages
        for L in languages.LANGS.values():
            doc = self.create("\n![a house](images/starter-house.svg)\n", target=L.code)
            self.assertEqual(self.files(doc, "images"), ["starter-house.svg"], L.code)
            self.assertEqual(store.doc_dir(doc).parent.name, L.folder)
        notes = self.tmp / "book" / "markdown"
        notes.mkdir(parents=True)
        was_lib = store.use_library(notes)
        was_mount = server.use_mount("/books/english/mini/notes", html_only=True)
        try:
            doc = self.create("\n![a chime](audio/starter-chime.mp3)\n")
            self.assertTrue(str(store.doc_dir(doc)).startswith(str(notes)))
            self.assertEqual(self.files(doc, "audio"), ["starter-chime.mp3"])
            html = self.preview("\n![a chime](audio/starter-chime.mp3)\n\n![](images/starter-apple.svg)\n",
                                doc_id=doc)
            self.assertEqual(srcs(html), [
                ("audio", "/books/english/mini/notes/media/%s/audio/starter-chime.mp3" % doc),
                ("img", "/books/english/mini/notes/starter-media/images/starter-apple.svg")])
            self.assertEqual(srcs(self.preview("\n![](images/starter-apple.svg)\n")),
                             [("img", "/books/english/mini/notes/starter-media/images/starter-apple.svg")])
        finally:
            server.restore_mount(was_mount)
            store.use_library(was_lib)


# ---------------------------------------------------------------- the renderer

class AssetUrlTests(unittest.TestCase):
    """htmlgen's asset base as a function that may give a file no URL."""

    def test_a_file_given_no_url_is_drawn_as_with_no_asset_base(self):
        md = HEAD % "en" + EVERYWHERE
        none = htmlgen.render_document(md, asset_base=lambda path: None)["html"]
        bare = htmlgen.render_document(md)["html"]
        self.assertEqual(srcs(none), [])
        self.assertEqual(none, bare)

    def test_each_file_is_asked_for_on_its_own(self):
        # the apple has a URL, the house, the chime and the cat none: every
        # place the dialect puts a file follows its own answer
        asked = []

        def url(path):
            asked.append(path)
            return "/x/" + path if "apple" in path else None
        html = htmlgen.render_document(HEAD % "en" + EVERYWHERE, asset_base=url)["html"]
        self.assertEqual(srcs(html), [("img", "/x/images/starter-apple.svg"),
                                      ("img", "/x/images/starter-apple.svg")])
        self.assertEqual(sorted(set(asked)), ["audio/starter-chime.mp3", "images/cat.png",
                                              "images/starter-apple.svg", "images/starter-house.svg"])
        for placeholder in ('<div class="img-placeholder">🔊 <code>audio/starter-chime.mp3</code></div>',
                            '<div class="img-placeholder">🖼 <code>images/cat.png</code></div>',
                            '<span class="ex-card-image-placeholder">images/starter-house.svg</span>',
                            'ex-card-audio-placeholder', 'ex-audio-placeholder'):
            self.assertIn(placeholder, html)


# ---------------------------------------------------------------- the preview

class PreviewTests(LibraryCase):
    def setUp(self):
        super().setUp()
        was = server.use_mount("/studio")
        self.addCleanup(server.restore_mount, was)

    def test_a_document_not_saved_yet_shows_the_starters_files_and_placeholders_for_its_own(self):
        html = self.preview(EVERYWHERE)
        self.assertEqual(srcs(html), [
            ("img", "/studio/starter-media/images/starter-apple.svg"),
            ("audio", "/studio/starter-media/audio/starter-chime.mp3"),
            ("img", "/studio/starter-media/images/starter-house.svg"),
            ("audio", "/studio/starter-media/audio/starter-chime.mp3"),
            ("img", "/studio/starter-media/images/starter-apple.svg"),
            ("audio", "/studio/starter-media/audio/starter-chime.mp3")])
        self.assertIn('<div class="img-placeholder">🖼 <code>images/cat.png</code></div>', html)
        # a picture inside a card's text, as a line of it
        html = self.preview(":::exercise flashcard\ncard-type: jolly\n"
                            "front-primary: |\n  ![an apple](images/starter-apple.svg)\n\n"
                            "  ![a cat](images/cat.png)\nfront-secondary: x\nback-primary: y\n"
                            "back-secondary: z\n:::\n")
        self.assertEqual(srcs(html), [("img", "/studio/starter-media/images/starter-apple.svg")])
        self.assertIn("images/cat.png", html)

    def test_a_saved_document_shows_its_own_copy_and_the_starters_until_it_has_one(self):
        doc = self.create("\nNothing yet.\n")
        body = "\n![an apple](images/starter-apple.svg)\n\n![a cat](images/cat.png)\n"
        self.assertEqual(srcs(self.preview(body, doc_id=doc)), [
            ("img", "/studio/starter-media/images/starter-apple.svg"),
            ("img", "/studio/media/%s/images/cat.png" % doc)])
        self.save(doc, body)
        self.assertEqual(srcs(self.preview(body, doc_id=doc)), [
            ("img", "/studio/media/%s/images/starter-apple.svg" % doc),
            ("img", "/studio/media/%s/images/cat.png" % doc)])
        # an id that is no document is a document not saved yet
        self.assertEqual(srcs(self.preview(body, doc_id="no-such-doc"))[0],
                         ("img", "/studio/starter-media/images/starter-apple.svg"))

    def test_a_starters_file_the_owner_deleted_is_missing_from_the_preview_too(self):
        # the reading view and the PDF have no starters to fall back on: the
        # editor shows the same missing file, not the starters' copy
        body = "\n![an apple](images/starter-apple.svg)\n"
        doc = self.create(body)
        store.delete_image(doc, "starter-apple.svg")
        self.assertEqual(srcs(self.preview(body + "\n![](images/starter-house.svg)\n", doc_id=doc)), [
            ("img", "/studio/media/%s/images/starter-apple.svg" % doc),
            ("img", "/studio/starter-media/images/starter-house.svg")])
        self.save(doc, body)
        self.assertEqual(srcs(self.preview(body, doc_id=doc)),
                         [("img", "/studio/media/%s/images/starter-apple.svg" % doc)])
        self.assertEqual(self.files(doc, "images"), [])

    def test_the_route_serves_the_shipped_files_and_nothing_else(self):
        route = next(p for m, p, fn in server.ROUTES if fn is server.serve_starter_media)
        m = re.match(route, "/starter-media/images/starter-apple.svg")
        self.assertEqual(m.groups(), ("images", "starter-apple.svg"))
        for bad in ("/starter-media/images/../audio/starter-chime.mp3", "/starter-media/fonts/x.ttf",
                    "/starter-media/images/", "/starter-media/images/a/b.svg"):
            self.assertIsNone(re.match(route, bad), bad)
        h = Fake()
        server.serve_starter_media(h, "images", "starter-house.svg")
        self.assertEqual(h.sent[:3], ("file", HOUSE, None))
        h = Fake()
        server.serve_starter_media(h, "audio", "starter-chime.mp3")
        self.assertEqual(h.sent[:3], ("file", CHIME, None))
        for kind, name in (("images", "cat.png"), ("audio", "starter-house.svg")):
            h = Fake()
            server.serve_starter_media(h, kind, name)
            self.assertEqual(h.sent, (404, {"error": "not found"}))


class HttpTests(unittest.TestCase):
    """The studio's own handler on 127.0.0.1: what the browser is sent."""

    @classmethod
    def setUpClass(cls):
        cls.quiet = mock.patch.object(server.Handler, "log_message", lambda *a: None)
        cls.quiet.start()
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.srv.daemon_threads = True
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.quiet.stop()

    def ask(self, path, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=30)
        self.addCleanup(c.close)
        c.request("GET", server.BASE + path, headers=headers or {})
        r = c.getresponse()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()

    def test_a_picture_and_a_recording_as_a_page_asks_for_them(self):
        status, headers, data = self.ask("/starter-media/images/starter-apple.svg")
        self.assertEqual((status, headers["content-type"], data),
                         (200, "image/svg+xml", APPLE.read_bytes()))
        self.assertIn("default-src 'none'", headers["content-security-policy"])
        status, headers, data = self.ask("/starter-media/audio/starter-chime.mp3",
                                         {"Range": "bytes=0-99"})
        self.assertEqual((status, headers["content-type"], data),
                         (206, "audio/mpeg", CHIME.read_bytes()[:100]))
        self.assertEqual(self.ask("/starter-media/images/cat.png")[0], 404)


# ---------------------------------------------------------------- the PDF

@unittest.skipUnless(shutil.which("xelatex"), "xelatex is not installed: no PDF to build")
@unittest.skipUnless(pymupdf, "PyMuPDF is not installed: the build cannot turn an SVG into a PDF")
class PdfTests(LibraryCase):
    def test_a_document_showing_the_starters_pictures_builds(self):
        # left to right and right to left alike: the picture is no language's
        for target in ("en", "fa"):
            with self.subTest(target=target):
                # the house on a line of its own too: a card's picture is
                # not printed (texgen), a figure and an exercise's are
                doc = self.create(EVERYWHERE.replace("\n![a cat of its own](images/cat.png)\n",
                                                     "\n![a house](images/starter-house.svg)\n"),
                                  target=target)
                build = server.build_pdf(doc, 1.52)
                self.assertEqual(build["status"], "ok", json.dumps(build)[:2000])
                out = store.doc_dir(doc) / "build"
                for name in ("starter-apple.svg.pdf", "starter-house.svg.pdf"):
                    self.assertTrue((out / "images" / name).is_file(), name)
                tex = (out / "main.tex").read_text(encoding="utf-8")
                self.assertIn("images/starter-apple.svg.pdf", tex)
                self.assertIn("images/starter-house.svg.pdf", tex)
                # the apple's red is on the first page: the picture was drawn
                # (some ten thousand such pixels at this size; the title and
                # the rules in the accent colour, a couple of hundred)
                with pymupdf.open(str(out / "main.pdf")) as pdf:
                    pix = pdf[0].get_pixmap(dpi=40)
                red = 0
                for i in range(0, len(pix.samples), pix.n):
                    r, g, b = pix.samples[i:i + 3]
                    if r > 180 and g < 110 and b < 100:
                        red += 1
                self.assertGreater(red, 2000, "no red apple on the page")

    def test_a_picture_deleted_since_the_last_build_is_not_printed(self):
        # the build's own copy of it stayed behind and went on being
        # printed, the reading view showing it missing; a picture the page
        # names and the document lacks stops the build instead, by name
        body = "\n![an apple](images/starter-apple.svg)\n\n![a house](images/starter-house.svg)\n"
        doc = self.create(body)
        self.assertEqual(server.build_pdf(doc, 1.52)["status"], "ok")
        staged = store.doc_dir(doc) / "build" / "images"
        self.assertTrue((staged / "starter-apple.svg.pdf").is_file())
        store.delete_image(doc, "starter-apple.svg")
        self.save(doc, body)
        build = server.build_pdf(doc, 1.52)
        self.assertEqual(build["status"], "error")
        self.assertIn("images/starter-apple.svg.pdf", build.get("error", ""))
        self.assertEqual(sorted(p.name for p in staged.iterdir()),
                         ["starter-house.svg", "starter-house.svg.pdf"])
        # the line taken out, it builds, the house alone
        self.save(doc, "\n![a house](images/starter-house.svg)\n")
        self.assertEqual(server.build_pdf(doc, 1.52)["status"], "ok")


if __name__ == "__main__":
    unittest.main()
