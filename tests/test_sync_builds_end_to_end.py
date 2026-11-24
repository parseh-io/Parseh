#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Builds travel with their source, between two REAL installs (a0.7.0 lane G).

    flock ~/.cache/parseh-suite.lock python3 -m unittest tests/test_sync_builds_end_to_end.py

Two serve.py processes in their own trees (tests/sync_harness.py), paired over
real TLS through Settings -> Devices.  B is a computer WITHOUT TeX
(SYNC_BUILDS_FAKE "no_tex": latexdraw finds no compiler).  What is faked:

  * A's BOOK BUILD: the card's door (<book>/__build) runs bookbuild as always,
    through bookbuild.start's own `runner` seam, a stand-in for ./build.sh that
    writes a reader quoting main.tex and a PDF -- bookbuild's end then RECORDS
    the source exactly as after a real build (lib/syncbuilds.py);
  * A's XeLaTeX for a studio document's PDF: a script on A's PATH that writes a
    real one-page PDF (PyMuPDF) where xelatex would; build_pdf, its checks and
    its record are the real ones.

A's DRAWING of a LaTeX block is REAL: A's own lualatex compiles it.
"""
import http.client
import re
import json
import os
import shutil
import stat
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_sync_pairing import Install  # noqa: E402
from test_sync_end_to_end import ask, until, rules  # noqa: E402

BOOK = "books/english/three"
UID = "book:english/three"
FAKE_XELATEX = """#!%s
import os
import sys
if "main.tex" not in sys.argv:              # a drawing, or a question: the real one
    os.execv("%s", ["%s"] + sys.argv[1:])
import pymupdf
d = pymupdf.open()
d.new_page().insert_text((72, 72), "a document")
d.save("main.pdf")
open("main.log", "w").write("a stand-in for xelatex\\n")
"""


def get(inst, route):
    c = http.client.HTTPConnection("127.0.0.1", inst.port, timeout=30)
    try:
        c.request("GET", route, headers={"Host": "localhost:%d" % inst.port})
        r = c.getresponse()
        return r.status, r.read()
    finally:
        c.close()


def read(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


class BuildsEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp(prefix="sync-builds-e2e-", dir=os.environ.get("TMPDIR"))
        fakebin = os.path.join(cls.base, "fakebin")
        os.makedirs(fakebin)
        with open(os.path.join(fakebin, "xelatex"), "w") as fh:
            real = shutil.which("xelatex")
            fh.write(FAKE_XELATEX % (sys.executable, real, real))
        os.chmod(os.path.join(fakebin, "xelatex"), 0o755 | stat.S_IXUSR)
        jobs = json.dumps({})        # (the jobs' harness: never the checkout's library page)
        cls.A = Install(cls.base, "A", env={"SYNC_BUILDS_FAKE": json.dumps({"book_build": True}),
                                            "SYNC_JOBS_FAKE": jobs,
                                            "PATH": fakebin + os.pathsep + os.environ.get("PATH", "")})
        cls.B = Install(cls.base, "B", env={"SYNC_BUILDS_FAKE": json.dumps({"no_tex": True}),
                                            "SYNC_JOBS_FAKE": jobs})
        try:
            cls.A.wait()
            cls.B.wait()
            st, offer = cls.A.dev("pair-start")
            assert st == 200, offer
            st, out = cls.B.dev("pair-enter", {"code": offer["said"], "address": "127.0.0.1:%d" % cls.A.port,
                                               "fingerprint": offer["fingerprint"]})
            assert st == 200, out
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        for i in (getattr(cls, "A", None), getattr(cls, "B", None)):
            if i:
                i.stop()
        if os.environ.get("KEEP_SYNC_E2E"):
            print("trees kept in", cls.base)
        else:
            shutil.rmtree(cls.base, ignore_errors=True)

    def p(self, inst, *rel):
        return os.path.join(inst.tree, "root", *rel)

    def build_on_A(self):
        st, out = ask(self.A, "POST", "/%s/__build" % BOOK, {"what": "pdf"})
        self.assertEqual(st, 200, out)
        until("A's build", lambda: ask(self.A, "GET", "/%s/__build/status" % BOOK)[1].get("state") == "done")

    def test_1_a_book_built_on_A_is_read_on_B_which_has_no_LaTeX(self):
        d = self.p(self.A, *BOOK.split("/"))
        os.makedirs(d)
        with open(os.path.join(d, "book.json"), "w") as fh:
            json.dump({"title": "Three", "lang": "en"}, fh)
        with open(os.path.join(d, "main.tex"), "w") as fh:
            fh.write("\\chapter{One}\nThe first text.\n")
        self.build_on_A()
        rec = json.loads(read(os.path.join(d, ".built-from.json")))
        self.assertEqual(sorted(rec["parts"]), ["pdf", "reader"], "the build recorded its source")
        reader_b = self.p(self.B, *BOOK.split("/"), "reader", "index.html")
        until("the source and the reader on B", lambda: os.path.isfile(reader_b)
              and os.path.isfile(self.p(self.B, *BOOK.split("/"), "main.tex"))
              and os.path.isfile(self.p(self.B, *BOOK.split("/"), "main.pdf")))
        self.assertIn(b"The first text.", read(reader_b))
        self.assertTrue(read(self.p(self.B, *BOOK.split("/"), "main.pdf")).startswith(b"%PDF"))
        st, page = get(self.B, "/%s/reader/index.html" % BOOK)
        self.assertEqual(st, 200)
        self.assertIn(b"built from: \\chapter{One}", page)
        # the library page is written again on B (the harness notes it instead of writing the
        # checkout's books/index.html), and the card it writes opens the reader that arrived
        until("B's library rewritten", lambda: os.path.isfile(os.path.join(self.B.tree, "library-rewritten")))
        import books
        import make_index
        card = make_index.card(books.Book(self.p(self.B, *BOOK.split("/"))))
        self.assertIn("Three", card)
        self.assertIn("reader/index.html", card)
        self.assertFalse(rules(self.B, "out_of_date")["out_of_date"])

    def test_2_an_edit_on_A_marks_B_out_of_date_until_As_rebuild_arrives(self):
        with open(self.p(self.A, *BOOK.split("/"), "main.tex"), "w") as fh:
            fh.write("\\chapter{One}\nThe second text.\n")
        main_b = self.p(self.B, *BOOK.split("/"), "main.tex")
        until("the edit on B", lambda: b"second" in (read(main_b) or b""))

        def marked():
            return [o for o in rules(self.B, "out_of_date")["out_of_date"] if o["unit"] == UID]
        got = until("B's mark", marked)
        self.assertEqual(sorted(got[0]["what"]), ["the PDF", "the reader"])
        st, unit = ask(self.B, "POST", "/settings/api/devices/unit", {"unit": UID})
        self.assertEqual(st, 200, unit)
        self.assertTrue(unit.get("out_of_date"), unit)
        self.assertIn(b"The first text.", read(self.p(self.B, *BOOK.split("/"), "reader", "index.html")))
        self.build_on_A()                                       # A rebuilds
        until("the mark gone on B", lambda: not marked())
        until("the rebuilt reader on B", lambda: b"The second text." in (read(self.p(
            self.B, *BOOK.split("/"), "reader", "index.html")) or b""))

    def test_3_a_documents_pdf_and_a_drawing_arrive_on_B_without_TeX(self):
        md = ("---\ntitle: Drawn on A\nlanguage: english\n---\n\n# Drawn on A\n\n"
              "::::latex\n\\(x^2 + 1\\)\n::::\n")
        st, out = ask(self.A, "POST", "/studio/api/docs", {"markdown": md})
        self.assertIn(st, (200, 201), out)
        doc_id = out.get("id") or (out.get("meta") or {}).get("id")
        self.assertTrue(doc_id, out)
        # A draws the block with its own lualatex (the page's own door), then builds the PDF
        st, drawn = ask(self.A, "POST", "/studio/api/docs/%s/drawings" % doc_id, {})
        self.assertEqual(st, 200, drawn)
        self.assertRegex(drawn["html"], r"/latex/[0-9a-f]{64}\.svg", "A drew the block with its own TeX")
        st, built = ask(self.A, "POST", "/studio/api/docs/%s/build" % doc_id, {})
        self.assertEqual(st, 200, built)
        self.assertEqual(built["build"]["status"], "ok", built)

        def pdf_on_b():
            st, body = get(self.B, "/studio/pdf/%s" % doc_id)
            return st == 200 and body.startswith(b"%PDF")
        until("the document's PDF on B", pdf_on_b)

        def drawing_on_b():
            st, got = ask(self.B, "POST", "/studio/api/docs/%s/drawings" % doc_id, {})
            return st == 200 and re.search(r"/latex/([0-9a-f]{64})\.svg", got.get("html", ""))
        got = until("the drawing found on B by its content", drawing_on_b)
        key = got.group(1)
        st, svg = get(self.B, "/latex/%s.svg" % key)
        self.assertEqual(st, 200)
        self.assertIn(b"<svg", svg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
