# SPDX-License-Identifier: GPL-3.0-or-later
"""Builds travel with their source (lib/syncbuilds.py, a0.7.0 lane G).

    flock ~/.cache/parseh-suite.lock python3 -m unittest tests/test_sync_builds.py

Two installs in one process (tests/syncfake.py).  A build is what a build
leaves behind -- reader/index.html, a PDF, a document's build/main.pdf --
written by the test and RECORDED as the builds record themselves
(syncbuilds.record, what bookbuild / tex2html / build_pdf call at their end).
The drawings of LaTeX blocks are files in each install's own markdown/latex/,
filed by their content as latexdraw files a drawing it made; the computer
"without TeX" is latexdraw.compiler answering None.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from syncfake import World      # noqa: E402
import latexdraw                # noqa: E402
import latexthemes              # noqa: E402
import syncbuilds as SB         # noqa: E402
import syncexchange as X        # noqa: E402
import syncrules as R           # noqa: E402

BOOK = "book:english/three"
BASE = "books/english/three/"


def build_book(inst, w, tag):
    inst.w(BASE + "reader/index.html", "<p>the reader, %s</p>" % tag)
    inst.w(BASE + "reader/ch1.html", "<p>chapter one, %s</p>" % tag)
    inst.w(BASE + "main.pdf", b"%PDF " + tag.encode())
    with w.on(inst):
        return SB.record(inst.p(BASE.rstrip("/")))


class Builds(unittest.TestCase):
    def setUp(self):
        self.w = World("A", "B").__enter__()
        self.A, self.B = self.w.A, self.w.B
        self._hooks = (list(X.ON_TAKEN), list(X.BEFORE_PULL), list(X.AFTER_PULL), dict(X.RULES))
        self._arrived = list(SB.ON_ARRIVED)
        self._compiler = latexdraw.compiler
        R.install()

    def tearDown(self):
        latexdraw.compiler = self._compiler
        SB.ON_ARRIVED[:] = self._arrived
        X.ON_TAKEN[:], X.BEFORE_PULL[:], X.AFTER_PULL[:] = self._hooks[:3]
        X.RULES.clear()
        X.RULES.update(self._hooks[3])
        R.close()
        self.w.__exit__(None, None, None)

    def both(self, a, b):
        with self.w.on(a):
            return X.sync_with(b.id)

    def book(self, text="\\chapter{One}\n"):
        self.A.w(BASE + "main.tex", text)
        self.A.w(BASE + "book.json", '{"title": "Three"}')

    def test_a_book_built_on_A_arrives_with_its_reader_and_PDF(self):
        arrived = []
        SB.ON_ARRIVED.append(arrived.append)
        self.book()
        rec = build_book(self.A, self.w, "A")
        self.assertEqual(sorted(rec), ["pdf", "reader"])
        got = self.both(self.B, self.A)
        self.assertIn(BOOK, got["taken"])
        self.assertEqual(sorted(got["builds"]), [BOOK + " pdf", BOOK + " reader"], got)
        self.assertEqual(self.B.read(BASE + "reader/index.html"), b"<p>the reader, A</p>")
        self.assertEqual(self.B.read(BASE + "reader/ch1.html"), b"<p>chapter one, A</p>")
        self.assertEqual(self.B.read(BASE + "main.pdf"), b"%PDF A")
        self.assertEqual(arrived, [[BOOK]])
        with self.w.on(self.B):
            u = SB.syncunits.locate(BOOK)
            self.assertEqual(SB.read_record(u)["reader"]["source"], SB.source_hash(u))
            self.assertFalse(R.is_out_of_date(BOOK))
            # the build is not part of the source: the book's hash is the same on both
        with self.w.on(self.A):
            ha = SB.source_hash(SB.syncunits.locate(BOOK))
        with self.w.on(self.B):
            self.assertEqual(SB.source_hash(SB.syncunits.locate(BOOK)), ha)
        # nothing travels again when nothing changed
        self.assertEqual(self.both(self.B, self.A)["builds"], [])

    def test_an_edit_marks_the_build_out_of_date_until_the_partners_rebuild_arrives(self):
        self.book()
        build_book(self.A, self.w, "first")
        self.both(self.B, self.A)
        self.A.w(BASE + "main.tex", "\\chapter{One, edited on A}\n")
        got = self.both(self.B, self.A)
        self.assertIn(BOOK, got["taken"])
        self.assertEqual(got["builds"], [], "A's build is of the old source")
        with self.w.on(self.B):
            self.assertTrue(R.is_out_of_date(BOOK))
            self.assertEqual([(o["unit"], o["title"], sorted(o["what"])) for o in R.out_of_date()],
                             [(BOOK, "Three", ["the PDF", "the reader"])])
        with self.w.on(self.A):
            self.assertTrue(R.is_out_of_date(BOOK), "A's own build is of the old source too")
        build_book(self.A, self.w, "second")                 # A rebuilds
        with self.w.on(self.A):
            self.assertFalse(R.is_out_of_date(BOOK))
        got = self.both(self.B, self.A)
        self.assertEqual(sorted(got["builds"]), [BOOK + " pdf", BOOK + " reader"])
        self.assertEqual(self.B.read(BASE + "reader/index.html"), b"<p>the reader, second</p>")
        with self.w.on(self.B):
            self.assertFalse(R.is_out_of_date(BOOK), "the rebuild's arrival cleared the mark")
            self.assertEqual(R.out_of_date(), [])

    def test_a_partner_known_to_hold_the_current_build_is_not_out_of_date(self):
        self.book()
        build_book(self.A, self.w, "first")
        self.both(self.B, self.A)
        self.A.w(BASE + "main.tex", "\\chapter{One, edited on A}\n")
        self.both(self.B, self.A)
        with self.w.on(self.B):
            self.assertTrue(R.is_out_of_date(BOOK))
            cur = SB.source_hash(SB.syncunits.locate(BOOK))
            # a partner said it holds a build of the current source (it comes at the next sync)
            SB._note_seen(self.A.id, {BOOK: {"pdf": {"source": cur}, "reader": {"source": cur}}}, True)
            self.assertFalse(R.is_out_of_date(BOOK))
            SB._note_seen(self.A.id, {}, True)
            self.assertTrue(R.is_out_of_date(BOOK))

    def test_a_left_out_book_never_has_its_build_fetched(self):
        self.book()
        build_book(self.A, self.w, "A")
        with self.w.on(self.B):
            X.set_holding(units=[BOOK])
        got = self.both(self.B, self.A)
        self.assertEqual(got["builds"], [])
        self.assertFalse(os.path.exists(self.B.p(BASE + "reader")))

    def test_a_studio_documents_pdf_travels(self):
        d = "markdown/library/english/a-doc/"
        self.A.w(d + "source.md", "---\ntitle: A doc\ntarget: en\n---\n\nText.\n")
        self.A.w(d + "meta.json", json.dumps({"id": "a-doc", "title": "A doc", "build": {"status": "ok"}}))
        self.A.w(d + "build/main.pdf", b"%PDF the document")
        self.A.w(d + "build/main.tex", "\\documentclass{article}")
        self.A.w(d + "build/main.aux", "never travels")
        with self.w.on(self.A):
            self.assertEqual(sorted(SB.record(self.A.p(d.rstrip("/")))), ["pdf"])
        got = self.both(self.B, self.A)
        self.assertEqual(got["builds"], ["doc:english/a-doc pdf"], got)
        self.assertEqual(self.B.read(d + "build/main.pdf"), b"%PDF the document")
        self.assertTrue(os.path.isfile(self.B.p(d + "build/main.tex")))
        self.assertFalse(os.path.exists(self.B.p(d + "build/main.aux")))

    def test_a_build_from_before_the_records_is_replaced_by_a_recorded_one(self):
        self.book()
        self.both(self.B, self.A)
        self.B.w(BASE + "main.pdf", b"%PDF unrecorded, B")
        build_book(self.A, self.w, "A")
        self.both(self.B, self.A)
        self.assertEqual(self.B.read(BASE + "main.pdf"), b"%PDF A")

    def test_a_drawing_made_on_A_is_found_on_B_without_TeX(self):
        md = "---\ntitle: Drawn\ntarget: en\n---\n\n::::latex\n\\draw (0,0) -- (1,1);\n::::\n"
        d = "markdown/library/english/drawn/"
        self.A.w(d + "source.md", md)
        self.A.w(d + "meta.json", json.dumps({"id": "drawn", "title": "Drawn"}))
        block = latexthemes.blocks_in(md)[0]
        with self.w.on(self.A):
            resolved = latexthemes.resolve(block["theme"])
            ck = latexdraw.content_key(block["tex"], resolved)
            key = "ab" * 32                       # A's own key: holds A's TeX installation
            p = latexdraw.paths(key)
            for kind, data in (("svg", b"<svg/>"), ("pdf", b"%PDF drawing"), ("meta", b'{"w": 10, "h": 5}')):
                os.makedirs(os.path.dirname(p[kind]), exist_ok=True)
                with open(p[kind], "wb") as fh:
                    fh.write(data)
            latexdraw._alias(ck, key, resolved["compiler"])
            self.assertEqual(latexdraw.by_content(ck), key)
        latexdraw.compiler = lambda name, fresh=False: None          # B has no TeX at all
        with self.w.on(self.B):
            before = latexdraw.plan(block["tex"], block["theme"])
            self.assertEqual((before["ok"], before["kind"]), (False, "compiler"))
        got = self.both(self.B, self.A)
        self.assertEqual(got["builds"], ["drawing %s" % ck], got)
        with self.w.on(self.B):
            pl = latexdraw.plan(block["tex"], block["theme"])
            self.assertEqual((pl["ok"], pl["key"], pl.get("elsewhere")), (True, key, True))
            drawn = latexdraw.draw(block["tex"], block["theme"])
            self.assertEqual((drawn["ok"], drawn["w"]), (True, 10), drawn)
            with open(drawn["svg"], "rb") as fh:
                self.assertEqual(fh.read(), b"<svg/>")
        # a computer WITH TeX never takes them: it draws by its own key
        latexdraw.compiler = lambda name, fresh=False: {"path": "/x", "version": "TeX 1", "miktex": False}
        other = "cd" * 32
        with self.w.on(self.B):
            theirs = {other: {"key": "ef" * 32, "compiler": "lualatex", "files": {"svg": "0" * 64}}}
            self.assertEqual(SB.take_drawings(None, theirs, lambda u: True), [])


class Leftovers(unittest.TestCase):
    def setUp(self):
        self.w = World("A", "B").__enter__()
        self.A, self.B = self.w.A, self.w.B

    def tearDown(self):
        self.w.__exit__(None, None, None)

    def test_a_partner_that_removed_this_computer_is_never_called(self):
        real = self.w.peer.partners

        def partners():
            return [dict(p, removed_you={"at": 1, "by": "A"}) if p["id"] == self.A.id else p for p in real()]
        self.w.peer.partners = partners
        self.w.calls.clear()
        with self.w.on(self.B):
            self.assertEqual(X._partners(), [])
            got = X.sync_with(self.A.id)
        self.assertTrue(got["removed_you"])
        self.assertEqual(self.w.calls, [], "no call at all")
        self.w.peer.partners = real
        with self.w.on(self.B):
            self.assertTrue(X.sync_with(self.A.id)["complete"], "paired again: it syncs")


if __name__ == "__main__":
    unittest.main()
