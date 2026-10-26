# SPDX-License-Identifier: GPL-3.0-or-later
"""A follow-up on paper (a0.5.4): the REAL build -- server.build_pdf, xelatex -- of a document holding one.

    python3 -m unittest discover -s tests -p test_follow_up_paper.py

The TeX it writes is pinned in tests/test_exercises.py (FollowUpDialectTests); this is the PDF.  It is built in every
print size and in black and white, left to right and right to left, and read back: every step has its number, in
order, and is whole on one page (a chain may part between two steps, never inside one); nothing said of a wrong
result is printed; a card is printed as Front and Back; and a step holding a LaTeX drawing includes the drawing's PDF
as a page does.  Skipped where xelatex or PyMuPDF is not installed."""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "markdown" / "exlex", ROOT / "markdown" / "app", ROOT / "lib", ROOT / "youtube" / "lib"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import latexdraw     # noqa: E402
import latexthemes   # noqa: E402
import server        # noqa: E402
import store         # noqa: E402
import texpackages   # noqa: E402

try:
    import pymupdf
except ImportError:
    pymupdf = None

PICTURE = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
           b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82")


def chain(target):
    """Five steps of five types, a card and a longish list among them; the words say which step they belong to"""
    rtl = target == "fa"
    word = (lambda s: "[%s]{tl}" % s) if rtl else (lambda s: s)
    return """---
title: Follow-up on paper
target: %(target)s
---

:::exercise follow-up
prompt: Read the dialogue on the page, then answer about it, one question at a time.
image: images/pattern.png
explanation-incorrect: SECRETEXPLANATION must never be printed.
::::exercise single-choice
prompt: STEPONE which one is it? %(w1)s
image: images/pattern.png
- [ ] %(w2)s
- [x] LASTCHOICE
::::
::::exercise flashcard
card-type: jolly
front-primary: STEPTWO front
front-secondary: |
  | a | b |
  |---|---|
  | one | two |
back-primary: %(w3)s
::::
::::exercise true-false
prompt: STEPTHREE decide.
- A statement to judge. => true
- LASTSTATEMENT to judge. => false
::::
::::exercise match-translations
prompt: STEPFOUR match them.
- %(w1)s => alpha
- %(w2)s => beta
- %(w3)s => LASTMATCH
::::
::::exercise order-sentences
prompt: STEPFIVE put in order.
- [1] first
- [2] second
- [3] third
- [4] fourth
- [5] fifth
- [6] LASTSENTENCE
::::
:::
""" % {"target": target, "w1": word("اول" if rtl else "uno"), "w2": word("دوم" if rtl else "due"),
       "w3": word("سوم" if rtl else "tre")}


# each step's first words and the last thing it holds: a step is whole when both are on one page
STEPS = (("STEPONE", "LASTCHOICE"), ("STEPTWO", "Back"), ("STEPTHREE", "LASTSTATEMENT"), ("STEPFOUR", "LASTMATCH"),
         ("STEPFIVE", "LASTSENTENCE"))


@unittest.skipUnless(shutil.which("xelatex"), "xelatex is not installed: no PDF to build")
@unittest.skipUnless(pymupdf, "PyMuPDF is not installed: the PDF cannot be read back")
class FollowUpPdfTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        root = Path(self.td.name)
        self.was = store.use_library(root / "library")
        (root / "library").mkdir()
        self.was_drawn, self.was_tree, self.was_themes = latexdraw.DRAWN, texpackages.TREE, latexthemes.STORE
        latexdraw.DRAWN = str(root / "drawn")
        texpackages.TREE = str(root / "texmf")
        latexthemes.STORE = str(root / "config" / "latex.json")

    def tearDown(self):
        latexdraw.DRAWN, texpackages.TREE, latexthemes.STORE = self.was_drawn, self.was_tree, self.was_themes
        store.use_library(self.was)
        self.td.cleanup()

    def build(self, markdown, size=11, mono=False):
        doc = store.create(markdown)["id"]
        store.images_dir(doc).mkdir(parents=True, exist_ok=True)
        (store.images_dir(doc) / "pattern.png").write_bytes(PICTURE)
        out = server.build_pdf(doc, 1.0, size, mono)
        self.assertEqual("ok", out["status"], str(out)[:1500])
        pdf = pymupdf.open(str(store.doc_dir(doc) / "build" / "main.pdf"))
        self.addCleanup(pdf.close)
        return pdf, (store.doc_dir(doc) / "build" / "main.tex").read_text(encoding="utf-8")

    @staticmethod
    def pages_of(pdf, text):
        return [i for i, page in enumerate(pdf) if text in page.get_text()]

    def check(self, pdf):
        whole = "\n".join(page.get_text() for page in pdf)
        self.assertIn("Follow-up questions", whole)
        # the steps' numbers, in order, once each
        self.assertEqual(["1", "2", "3", "4", "5"], re.findall(r"(?m)^\s*([1-5])\.(?:\s|$)", whole)[:5])
        # what is said of a wrong result is not on paper, as for every exercise
        self.assertNotIn("SECRETEXPLANATION", whole)
        # a step is whole on one page: its first words and the last thing it holds
        for first, last in STEPS:
            a, b = self.pages_of(pdf, first), self.pages_of(pdf, last)
            self.assertTrue(a and b, (first, last))
            self.assertEqual(a[0], b[-1], "%s is split across two pages" % first)

    def test_it_builds_in_every_print_size_and_in_black_and_white(self):
        for target in ("en", "fa"):
            for size, mono in ((11, False), (14, True), (17, False), (20, False)):
                with self.subTest(target=target, size=size, mono=mono):
                    pdf, tex = self.build(chain(target), size, mono)
                    self.check(pdf)
                    self.assertEqual(5, tex[tex.index("\\begin{document}"):].count("\\expaperstep{"))

    def test_the_card_is_printed_front_and_back_not_as_a_card_to_cut(self):
        pdf, tex = self.build(chain("en"))
        whole = "\n".join(page.get_text() for page in pdf)
        self.assertIn("Front", whole)
        self.assertIn("Back", whole)
        self.assertNotIn("\\expapercard*", tex[tex.index("\\begin{document}"):])

    def test_a_step_holding_a_drawing_includes_the_drawings_pdf(self):
        md = chain("en").replace("prompt: STEPONE which one is it? uno",
                                 "prompt: |\n  STEPONE a drawing, then a choice.\n  :::::latex\n  \\textbf{ciao} $E=mc^2$\n  :::::")
        pdf, tex = self.build(md)
        self.check(pdf)
        self.assertIn("latex/", tex)


if __name__ == "__main__":
    unittest.main()
