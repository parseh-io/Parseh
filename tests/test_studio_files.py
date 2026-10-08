# SPDX-License-Identifier: GPL-3.0-or-later
"""A studio document in and out as files: the header an upload is asked for,
the zip a document downloads as, and the zip the library takes back
(markdown/app/store.py, markdown/app/server.py).

    python3 -m unittest discover -s tests -p test_studio_files.py

No socket: the routes are driven through a fake handler, in a temporary
studio library (store.use_library)."""
import io
import json
import re
import sys
import tempfile
import unittest
import urllib.parse
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "markdown" / "exlex", ROOT / "markdown" / "app",
               ROOT / "lib", ROOT / "youtube" / "lib"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import server   # noqa: E402
import store    # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"pixels"
PNG_B = b"\x89PNG\r\n\x1a\n" + b"other pixels"
FULL = """---
title: Cats
subtitle: about cats
note: a small line
lang: en
target: fa
author: somebody
---

Body [گربه]{tl}.
"""


def zip_of(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


class Fake:
    """What the studio's routes use of a handler, recording the answer."""

    def __init__(self, body=None, query="", raw=b""):
        self.body, self.raw = body, raw
        self.query = urllib.parse.parse_qs(query)
        self.sent = None

    def _json_body(self):
        return self.body

    def _body(self):
        return self.raw

    def send_json(self, payload, status=200):
        self.sent = (status, payload)

    def send_bytes(self, data, ctype, status=200, headers=None):
        self.sent = (status, data, ctype, headers or {})


class HeaderTests(unittest.TestCase):
    def test_a_complete_header_is_complete_whatever_else_it_holds(self):
        state = store.header_state(FULL)
        self.assertEqual((state["present"], state["missing"]), (True, []))
        self.assertEqual(store.fill_header(FULL, {"title": "Something else"}), FULL,
                         "and nothing in it is touched")

    def test_no_header_is_asked_for_whole_and_goes_above_the_text(self):
        text = "# Cats and *dogs*\n\nBody.\n"
        state = store.header_state(text)
        self.assertEqual((state["present"], state["missing"]), (False, list(store.HEADER_KEYS)))
        self.assertEqual(store.header_defaults(text, "notes/cat-notes.md")["title"], "Cats and dogs")
        self.assertEqual(store.header_defaults("no heading", "notes/cat-notes.md")["title"], "Cat notes")
        out = store.fill_header(text, {"title": "Cats", "subtitle": "", "note": "n",
                                       "lang": "en", "target": "FA"})
        self.assertEqual(out, "---\ntitle: Cats\nsubtitle:\nnote: n\nlang: en\ntarget: fa\n---\n\n"
                              "# Cats and *dogs*\n\nBody.\n")
        self.assertEqual(store.header_state(out)["missing"], [])

    def test_a_header_short_of_some_fields_gets_only_those(self):
        text = "---\ntitle: Cats\nauthor: me\ntarget:\n---\nBody\n"
        self.assertEqual(store.header_state(text)["missing"], ["subtitle", "note", "lang", "target"])
        out = store.fill_header(text, {"title": "not asked", "subtitle": "s", "note": "",
                                       "lang": "it", "target": "ar"})
        self.assertEqual(out, "---\ntitle: Cats\nauthor: me\ntarget: ar\nsubtitle: s\nnote:\nlang: it\n---\nBody\n",
                         "the lines it had stay, the empty target is filled, the rest are added")
        self.assertEqual(store.header_defaults(text)["title"], "Cats", "what the header says is offered")

    def test_what_cannot_be_filled_in_is_refused_and_a_value_is_one_line(self):
        five = {"title": "T", "subtitle": "", "note": "", "lang": "en", "target": "fa"}
        for bad in ({"title": ""}, {"lang": ""}, {"target": "klingon"}):
            with self.assertRaises(store.StoreError):
                store.fill_header("Body", dict(five, **bad))
        self.assertIn("title: Two lines\n", store.fill_header("Body", dict(five, title="Two\nlines")))
        self.assertFalse(store.header_state("---\ntitle: T\nnever closed\n")["present"])


class LibraryCase(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.lib = Path(td.name)
        was = store.use_library(self.lib)
        self.addCleanup(store.use_library, was)

    def made(self):
        return sorted(p.parent.name for p in self.lib.rglob("source.md"))

    def cats(self):
        meta = store.create(FULL + "\n![a cat](images/cat.png){width=40}\n")
        store.save_image(meta["id"], "cat.png", PNG)
        store.save_image(meta["id"], "unused.png", PNG_B)
        return meta


class ZipTests(LibraryCase):
    def test_the_download_holds_the_markdown_and_the_pictures_it_shows(self):
        meta = self.cats()
        z = zipfile.ZipFile(io.BytesIO(store.doc_zip(meta["id"], "cats")))
        self.assertEqual(sorted(z.namelist()), ["cats.md", "images/cat.png"])
        self.assertEqual(z.read("images/cat.png"), PNG)
        self.assertEqual(z.read("cats.md"), (store.doc_dir(meta["id"]) / "source.md").read_bytes())

    def test_the_download_carries_the_tags_and_brings_them_back(self):
        """A DOCUMENT'S TAGS ARE NOT IN ITS MARKDOWN.  They live in meta.json,
        which does not travel, so the zip carries them beside the text and the
        upload reads them back -- otherwise a document came home untagged."""
        meta = store.create(FULL, tags=["Kitchen", "verbs"])
        data = store.doc_zip(meta["id"], "cats")
        z = zipfile.ZipFile(io.BytesIO(data))
        self.assertIn("cats.tags.json", z.namelist())
        said = z.read("cats.tags.json").decode("utf-8")
        self.assertIn('"kitchen"', said)
        self.assertIn('"verbs"', said)
        store.delete(meta["id"])                 # its name is free again
        out = store.import_zip(data)
        self.assertEqual(out["docs"][0]["tags"], ["kitchen", "verbs"])

    def test_a_document_with_no_tags_carries_no_such_file(self):
        """so its zip is exactly what it always was"""
        meta = store.create(FULL)
        names = zipfile.ZipFile(io.BytesIO(store.doc_zip(meta["id"], "plain"))).namelist()
        self.assertEqual(names, ["plain.md"])

    def test_tags_beside_a_markdown_in_a_zip_made_by_hand(self):
        """a bare list, and whitespace nobody meant: tags are worth carrying
        and not worth refusing a zip over"""
        out = store.import_zip(zip_of({"notes/cats.md": FULL,
                                       "notes/cats.tags.json": '["Kitchen", " verbs "]'}))
        self.assertEqual(out["docs"][0]["tags"], ["kitchen", "verbs"])

    def test_a_tags_file_that_is_not_readable_is_no_tags_at_all(self):
        out = store.import_zip(zip_of({"notes/cats.md": FULL,
                                       "notes/cats.tags.json": "{not json"}))
        self.assertEqual((len(out["docs"]), out["docs"][0]["tags"]), (1, []))

    def test_the_download_comes_back_as_it_went(self):
        # into a library where its name is free again: the one it came from
        # is deleted first (a name is one document's, test_doclinks.py)
        meta = self.cats()
        data, text = store.doc_zip(meta["id"], "cats"), store.get(meta["id"])[1]
        store.delete(meta["id"])
        out = store.import_zip(data)
        self.assertEqual((len(out["docs"]), out["warnings"]), (1, []))
        new = out["docs"][0]["id"]
        self.assertNotEqual(new, meta["id"])
        self.assertEqual(store.get(new)[1], text)
        self.assertEqual((store.images_dir(new) / "cat.png").read_bytes(), PNG)
        self.assertFalse((store.images_dir(new) / "unused.png").exists())

    def test_pictures_are_found_beside_their_markdown_and_named_as_the_store_keeps_them(self):
        md = (FULL + "\n![](images/Cat.PNG)\n\n:::exercise flashcard\nfront: x\nback: y\n"
              "front-image: images/dog.png\n:::\n\n![](images/gone.png)\n")
        out = store.import_zip(zip_of({"notes/cats.md": md, "notes/images/Cat.PNG": PNG,
                                       "notes/dog.png": PNG_B, "../evil.md": "x",
                                       "__MACOSX/notes/._cats.md": "junk"}))
        self.assertEqual(len(out["docs"]), 1, "the files from outside the zip's tree are no documents")
        doc = out["docs"][0]["id"]
        text = store.get(doc)[1]
        self.assertIn("![](images/cat.png)", text)
        self.assertNotIn("Cat.PNG", text)
        self.assertIn("front-image: images/dog.png", text)
        self.assertEqual((store.images_dir(doc) / "cat.png").read_bytes(), PNG)
        self.assertEqual((store.images_dir(doc) / "dog.png").read_bytes(), PNG_B)
        self.assertEqual(out["warnings"], ["notes/cats.md: images/gone.png is not in the zip"])

    def test_headers_are_asked_for_before_anything_is_made(self):
        data = zip_of({"a.md": FULL, "b.md": "# Bee\n\nbuzz\n", "c.md": "---\ntitle: C\n---\nsee\n"})
        with self.assertRaises(store.HeaderNeeded) as caught:
            store.import_zip(data)
        needs = {f["name"]: f for f in caught.exception.files}
        self.assertEqual(sorted(needs), ["b.md", "c.md"], "the complete one is not asked about")
        self.assertEqual((needs["b.md"]["present"], needs["b.md"]["defaults"]["title"]), (False, "Bee"))
        self.assertEqual(needs["c.md"]["missing"], ["subtitle", "note", "lang", "target"])
        self.assertEqual(self.made(), [], "nothing was made")
        out = store.import_zip(data, {"b.md": {"title": "Bee", "subtitle": "", "note": "",
                                               "lang": "en", "target": "it"},
                                      "c.md": None})
        self.assertEqual(sorted(d["title"] for d in out["docs"]), ["Bee", "Cats"])
        self.assertEqual(len(self.made()), 2, "c.md was left out")

    def test_what_is_not_a_zip_of_markdown_is_refused(self):
        for data, why in ((b"not a zip", "not a zip"), (zip_of({"a.txt": "x"}), "no markdown")):
            with self.assertRaises(store.StoreError) as caught:
                store.import_zip(data)
            self.assertIn(why, str(caught.exception))


KEY = "ab" * 32            # a drawing's key, as latexdraw makes them: 64 hex digits
OTHER = "cd" * 32
DRAWING = "::::latex\n\\begin{tikzpicture}\\draw (0,0) -- (1,1);\\end{tikzpicture}\n::::\n"
RESOLVED = {"name": "drawing", "compiler": "xelatex", "preamble": "\\documentclass{standalone}\n\\usepackage{tikz}\n"}


class LatexZipTests(LibraryCase):
    """A document's LaTeX as a zip (markdown/app/texzip.py): what the last build made, with everything main.tex includes."""

    def built(self, extra_tex="", with_drawing=True):
        meta = store.create(FULL + "\n![a cat](images/cat.png){width=40}\n\n" + (DRAWING if with_drawing else ""))
        store.save_image(meta["id"], "cat.png", PNG)
        build = store.doc_dir(meta["id"]) / "build"
        for folder in ("images", "latex", "fonts"):
            (build / folder).mkdir(parents=True)
        (build / "images" / "cat.png").write_bytes(PNG)
        (build / "images" / "unused.png").write_bytes(PNG_B)                  # staged by every build, shown by nobody
        (build / "latex" / (KEY + ".pdf")).write_bytes(b"%PDF drawing")
        (build / "latex" / (OTHER + ".pdf")).write_bytes(b"%PDF a drawing the document no longer has")
        for font in ("Vazirmatn-Regular.ttf", "NotoNaskhArabic-Regular.ttf"):
            (build / "fonts" / font).write_bytes(b"font " + font.encode())
        (build / "main.tex").write_text(
            "\\documentclass{extarticle}\n\\newfontfamily\\fa[Path=./fonts/,UprightFont=Vazirmatn-Regular.ttf]{Vazirmatn}\n"
            "\\begin{document}\n\\includegraphics{images/cat.png}\n\\includegraphics[width=3cm]{latex/%s.pdf}\n%s\\end{document}\n" % (KEY, extra_tex),
            encoding="utf-8")
        return meta

    def get(self, meta, kind="texzip"):
        h = Fake()
        server.serve_download(h, meta["id"], kind)
        return h.sent

    def plan(self):
        return mock.patch("latexdraw.plan", return_value={"ok": True, "key": KEY, "resolved": RESOLVED})

    def test_the_zip_holds_main_tex_with_what_it_includes_and_nothing_else(self):
        meta = self.built()
        with self.plan():
            status, data, ctype, headers = self.get(meta)
        self.assertEqual((status, ctype), (200, "application/zip"))
        self.assertIn('filename="cats-latex.zip"', headers["Content-Disposition"])
        z = zipfile.ZipFile(io.BytesIO(data))
        self.assertEqual(sorted(z.namelist()), ["README.txt", "fonts/OFL.txt", "fonts/Vazirmatn-Regular.ttf", "images/cat.png",
                                                "latex/%s.pdf" % KEY, "latex/%s.tex" % KEY, "main.tex"],
                         "the picture it shows, the drawing as PDF and as LaTeX, the font it names with its licence: not the picture "
                         "nobody shows, not the drawing it does not include, not the font it does not ask for")
        self.assertEqual(z.read("main.tex"), (store.doc_dir(meta["id"]) / "build" / "main.tex").read_bytes())
        self.assertEqual(z.read("images/cat.png"), PNG)
        self.assertEqual(z.read("latex/%s.pdf" % KEY), b"%PDF drawing")
        self.assertEqual(z.read("fonts/Vazirmatn-Regular.ttf"), b"font Vazirmatn-Regular.ttf")

    def test_a_drawings_tex_is_the_file_it_was_compiled_from(self):
        import latexdraw
        meta = self.built()
        with self.plan():
            z = zipfile.ZipFile(io.BytesIO(self.get(meta)[1]))
        block = DRAWING.split("\n", 1)[1].rsplit("\n::::", 1)[0]
        self.assertEqual(z.read("latex/%s.tex" % KEY).decode("utf-8"), latexdraw.source(block, RESOLVED))
        self.assertEqual(z.read("latex/%s.tex" % KEY).decode("utf-8").splitlines()[:2], ["\\documentclass{standalone}", "\\usepackage{tikz}"],
                         "its theme's preamble first: a file that compiles by itself")
        note = z.read("README.txt").decode("utf-8")
        self.assertIn("XeLaTeX", note)
        self.assertIn('latex/%s.tex   theme "drawing", compiled with xelatex' % KEY, note, "the README says how to remake each drawing")

    def test_a_drawing_whose_latex_cannot_be_found_is_said_not_left_out(self):
        meta = self.built()
        with mock.patch("latexdraw.plan", return_value={"ok": True, "key": OTHER, "resolved": RESOLVED}):     # the document changed since
            z = zipfile.ZipFile(io.BytesIO(self.get(meta)[1]))
        self.assertIn("latex/%s.pdf" % KEY, z.namelist(), "its PDF is still there, main.tex includes it")
        self.assertNotIn("latex/%s.tex" % KEY, z.namelist())
        self.assertIn("WITHOUT THEIR LaTeX", z.read("README.txt").decode("utf-8"))
        self.assertIn("latex/%s.pdf" % KEY, z.read("README.txt").decode("utf-8").split("WITHOUT THEIR LaTeX", 1)[1])

    def test_a_document_without_drawings_or_fonts_has_just_its_pictures(self):
        meta = store.create(FULL + "\n![a cat](images/cat.png)\n")
        store.save_image(meta["id"], "cat.png", PNG)
        build = store.doc_dir(meta["id"]) / "build"
        (build / "images").mkdir(parents=True); (build / "fonts").mkdir()
        (build / "images" / "cat.png").write_bytes(PNG)
        (build / "fonts" / "Vazirmatn-Regular.ttf").write_bytes(b"font")
        (build / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\\includegraphics{images/cat.png}\\end{document}\n")
        z = zipfile.ZipFile(io.BytesIO(self.get(meta)[1]))
        self.assertEqual(sorted(z.namelist()), ["README.txt", "images/cat.png", "main.tex"], "no font it does not ask for, no empty folders")
        self.assertNotIn("THE DRAWINGS", z.read("README.txt").decode("utf-8"))

    def test_nothing_is_taken_from_outside_the_build_and_an_unbuilt_document_has_no_zip(self):
        meta = self.built(extra_tex="\\includegraphics{images/../../source.md}\\includegraphics{latex/../main.tex}\n")
        with self.plan():
            z = zipfile.ZipFile(io.BytesIO(self.get(meta)[1]))
        self.assertNotIn("images/../../source.md", z.namelist())
        self.assertEqual([n for n in z.namelist() if n.endswith("source.md")], [], "a path that climbs out of the build is not followed")
        fresh = store.create(FULL.replace("Cats", "Dogs"))
        status, answer = self.get(fresh)
        self.assertEqual(status, 404)
        self.assertIn("build the PDF first", answer["error"])

    def test_a_note_beside_a_book_never_comes_away_as_latex_either(self):
        meta = self.built()
        server._MOUNT.html_only = True
        self.addCleanup(setattr, server._MOUNT, "html_only", False)
        self.assertEqual(self.get(meta)[0], 404)
        self.assertEqual(self.get(meta, "tex")[0], 404)


class BackupTests(LibraryCase):
    """The Backup button's zip, put back.

    A backup is not markdown somebody wrote: it carries meta.json, so what
    comes back is the document that went in -- its id, its uid, the name
    every [...](doc:Name) link spells, its tags and its pictures -- and not a new
    document with the same text.
    """

    def backup(self):
        """the library as api_export writes it: every file, named relative to
        the library's root"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(self.lib.rglob("*")):
                if f.is_file():
                    zf.write(f, str(f.relative_to(self.lib)))
        return buf.getvalue()

    def elsewhere(self, data, **kw):
        """restore into a library of its own -> (answer, what it holds)"""
        with tempfile.TemporaryDirectory() as td:
            was = store.use_library(Path(td))
            try:
                out = store.import_library(data, **kw)
                held = {doc_id: (store.get(doc_id)[0], store.get(doc_id)[1])
                        for doc_id in out["restored"]}
                pics = {doc_id: sorted(p.name for p in store.images_dir(doc_id).glob("*"))
                        for doc_id in out["restored"]}
            finally:
                store.use_library(was)
        return out, held, pics

    def test_a_restore_brings_the_document_back_and_not_a_new_one(self):
        meta = store.create(FULL, tags=["Kitchen", "verbs"])
        store.save_image(meta["id"], "cat.png", PNG)
        out, held, pics = self.elsewhere(self.backup())
        self.assertEqual((out["restored"], out["kept"], out["warnings"]),
                         ([meta["id"]], [], []))
        back, text = held[meta["id"]]
        self.assertEqual(back["uid"], meta["uid"], "the uid every link points at")
        self.assertEqual(back["tags"], ["kitchen", "verbs"])
        self.assertEqual(back["created"], meta["created"])
        self.assertEqual(text, store.get(meta["id"])[1])
        self.assertEqual(pics[meta["id"]], ["cat.png"])

    def test_what_is_already_here_is_kept_until_replacing_is_asked_for(self):
        meta = store.create(FULL)
        data = self.backup()
        after = store.save_markdown(meta["id"], FULL + "\nwritten since the backup\n")
        self.assertIn("written since", store.get(meta["id"])[1])

        out = store.import_library(data)
        self.assertEqual((out["restored"], out["kept"]), ([], [meta["id"]]))
        self.assertIn("written since", store.get(meta["id"])[1],
                      "the newer text is still here")

        out = store.import_library(data, replace=True)
        self.assertEqual((out["restored"], out["kept"]), ([meta["id"]], []))
        self.assertNotIn("written since", store.get(meta["id"])[1],
                         "asked for, the backup's copy takes its place")
        self.assertEqual(store.get(meta["id"])[0]["uid"], after["uid"])

    def test_a_zip_that_is_no_library_is_refused_and_nothing_outside_it_is_read(self):
        with self.assertRaises(store.StoreError) as caught:
            store.import_library(b"not a zip")
        self.assertIn("not a zip", str(caught.exception))
        for bad in ({"../evil/meta.json": "{}", "../evil/source.md": "x"},
                    {"notes.md": "no library here"}):
            with self.assertRaises(store.StoreError) as caught:
                store.import_library(zip_of(bad))
            self.assertIn("no library", str(caught.exception))


class RouteTests(LibraryCase):
    def test_deleting_a_document_answers_ok_once_it_is_really_gone(self):
        meta = store.create(FULL)
        self.assertEqual(self.made(), [meta["id"]])
        h = Fake()
        server.api_delete(h, meta["id"])
        self.assertEqual(h.sent, (200, {"ok": True}),
                         "the library's own answer: the route must not fail after the delete")
        self.assertEqual(self.made(), [])

    def test_a_document_that_is_not_there_is_the_404_page_where_the_route_is_a_page(self):
        # _dispatch answers a KeyError with the studio's 404 page when the
        # route is in PAGES, and with JSON otherwise (an API call, a download)
        for page in (server.page_doc, server.page_note, server.page_edit):
            self.assertIn(page, server.PAGES)
            with self.assertRaises(KeyError):
                page(Fake(), "no-such-document")
        for other in (server.api_get, server.api_delete, server.serve_download):
            self.assertNotIn(other, server.PAGES)
        self.assertIn('href="/"', server.render_template("404.html", {}))

    def test_create_asks_for_the_header_and_makes_nothing_until_it_has_it(self):
        h = Fake({"markdown": "# Owls\n\nhoot\n", "check_header": True, "name": "owls.md"})
        server.api_create(h)
        status, answer = h.sent
        self.assertEqual((status, answer["header_needed"], answer["missing"]), (422, True, list(store.HEADER_KEYS)))
        self.assertEqual(answer["defaults"]["title"], "Owls")
        self.assertIn({"code": "fa", "name": "Persian"}, answer["targets"])
        self.assertIn("en", [o["code"] for o in answer["langs"]])
        self.assertEqual(self.made(), [])
        h = Fake({"markdown": "# Owls\n\nhoot\n",
                  "header": {"title": "Owls", "subtitle": "", "note": "", "lang": "en", "target": "fa"}})
        server.api_create(h)
        self.assertEqual(h.sent[0], 201)
        meta = h.sent[1]["meta"]
        self.assertEqual((meta["title"], meta["target"], meta["lang"]), ("Owls", "fa", "en"))
        self.assertTrue(store.get(meta["id"])[1].startswith("---\ntitle: Owls\nsubtitle:\n"))

    def test_a_complete_header_goes_straight_in_and_a_create_without_the_check_as_ever(self):
        h = Fake({"markdown": FULL, "check_header": True})
        server.api_create(h)
        self.assertEqual(h.sent[0], 201)
        self.assertEqual(store.get(h.sent[1]["meta"]["id"])[1], FULL)
        h = Fake({"markdown": "no header at all"})
        server.api_create(h)
        self.assertEqual(h.sent[0], 201)

    def test_the_zip_goes_out_and_comes_back_through_the_routes(self):
        meta = self.cats()
        route = [p for m, p, fn in server.ROUTES if fn is server.serve_download][0]
        self.assertTrue(re.match(route, "/download/%s/zip" % meta["id"]))
        h = Fake()
        server.serve_download(h, meta["id"], "zip")
        status, data, ctype, headers = h.sent
        self.assertEqual((status, ctype), (200, "application/zip"))
        self.assertEqual(headers["Content-Disposition"], 'attachment; filename="cats.zip"')
        self.assertEqual(sorted(zipfile.ZipFile(io.BytesIO(data)).namelist()), ["cats.md", "images/cat.png"])
        # its name is still the document's it came from: asked about, then
        # given another (test_doclinks.py covers the dialog's answers)
        up = Fake(raw=data)
        server.api_import_zip(up)
        self.assertEqual((up.sent[0], up.sent[1]["name_conflicts"][0]["existing"]["id"]),
                         (409, meta["id"]))
        answer = json.dumps({"incoming": {"cats.md": "Cats again"}})
        up = Fake(raw=data, query="renames=" + urllib.parse.quote(answer))
        server.api_import_zip(up)
        self.assertEqual((up.sent[0], up.sent[1]["ok"], len(up.sent[1]["docs"])), (201, True, 1))
        self.assertEqual(up.sent[1]["docs"][0]["title"], "Cats again")
        bare = zip_of({"bee.md": "# Bee\n\nbuzz\n"})
        up = Fake(raw=bare)
        server.api_import_zip(up)
        self.assertEqual((up.sent[0], [f["name"] for f in up.sent[1]["files"]]), (422, ["bee.md"]))
        self.assertIn("targets", up.sent[1])
        answer = '{"bee.md": {"title": "Bee", "subtitle": "", "note": "", "lang": "en", "target": "it"}}'
        up = Fake(raw=bare, query="headers=" + urllib.parse.quote(answer))
        server.api_import_zip(up)
        self.assertEqual((up.sent[0], up.sent[1]["docs"][0]["target"]), (201, "it"))
        up = Fake(raw=bare, query="headers=not-json")
        server.api_import_zip(up)
        self.assertEqual(up.sent[0], 400)


if __name__ == "__main__":
    unittest.main()
