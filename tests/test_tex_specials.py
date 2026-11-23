#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
r"""TeX's special characters in a book's text: "50%" and "R&D" go round
unchanged (TO-DO §6.5, §6.6; lib/texesc.py).

Until a0.6.3 the add refused a text holding any of \ { } $ % & # _ ^ ~ ("Take
it out of the text (or spell it in words)", lib/draft.py), and the chunk
sheet refused to write one (lib/texwrite.py).  Now the chapter holds their
escapes and every reader undoes them.  For a spaced language left to right
(English), one right to left (Persian) and one with a reading and no spaces
(Japanese) this drives the whole road:

    add (draft.book_from_text) -> verify_book.py -> the reader (tex2html.py)
    -> the chunk sheet (texwrite.read_chunks / edit_chunk) -> texparse again
    -> the timings key -> the bundle -> check_batch.py

and, where lualatex is installed, the PDF of the English book, read back with
pdftotext.

    python3 -m unittest tests.test_tex_specials
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)

import draft      # noqa: E402
import languages  # noqa: E402
import texesc     # noqa: E402
import texparse   # noqa: E402
import texwrite   # noqa: E402
import timestamp  # noqa: E402

ALL = "\\{}$%&#_^~"

TEXTS = {
    "en": ("It costs 50% of the R&D budget, about $5 for item #1.\n\n"
           "Write a_b {and} c~d^e with a back\\slash in it."),
    "fa": "پنجاه درصد یعنی 50% و R&D هم هست.\n\nاین {متن} و $5 و #1 است.",
    "ja": "研究開発（R&D）は50%です。\n\n値段は$5で#1です。",
}


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       env=dict(os.environ, FRANK_BOOK=cwd))
    return p.returncode, p.stdout + p.stderr


def chunks_of(main, lang):
    here = os.getcwd()
    os.chdir(os.path.dirname(main))
    try:
        chapters = texparse.parse_book("main.tex", lang)
    finally:
        os.chdir(here)
    return chapters


class EscapeTests(unittest.TestCase):
    def test_escape_and_unescape_are_inverse_for_every_string(self):
        for s in ("", "plain", ALL, "50%", "R&D", "\\{", "\\%", "\\textbackslash{}",
                  "a\\\\b", "}{", "~~^^", "%" * 3, "پنجاه % درصد"):
            with self.subTest(s=s):
                tex = texesc.escape(s)
                self.assertEqual(texesc.unescape(tex), s)
                self.assertEqual(texesc.raw_percent(tex), -1, tex)
        self.assertEqual(texesc.escape("50% R&D"), "50\\% R\\&D")
        self.assertEqual(texesc.escape("no special"), "no special",
                         "a text without one is written as it is, so no old key moves")

    def test_a_raw_per_cent_is_found_and_an_escaped_one_is_not(self):
        self.assertEqual(texesc.raw_percent("a\\%b"), -1)
        self.assertEqual(texesc.raw_percent("a\\\\%b"), 3, "\\\\ is a line break, then a comment")
        self.assertEqual(texesc.raw_percent("a%b"), 1)


class RoundTripTests(unittest.TestCase):
    """add -> reader -> chunk sheet -> save, in three languages."""

    def make(self, code):
        td = tempfile.mkdtemp(prefix="parseh-texesc-")
        self.addCleanup(shutil.rmtree, td, True)
        # the tree a book lives in, so main.tex's ../../../lib reaches the
        # preamble for the PDF
        os.symlink(LIB, os.path.join(td, "lib"))
        L = languages.get(code)
        into = os.path.join(td, "books")     # the book goes to books/<folder>/<slug>
        os.makedirs(into)
        r = draft.book_from_text(TEXTS[code], L, "Specials", slug="specials-" + code,
                                 title_latin="Specials", into=into)
        return L, r["dir"]

    def every_chunk(self, d, L):
        return [c for ch in chunks_of(os.path.join(d, "main.tex"), L)
                for s in ch.subs for c in s.chunks]

    def test_the_road_in_every_shape_of_language(self):
        for code in TEXTS:
            with self.subTest(code):
                self.road(code)

    def road(self, code):
        L, d = self.make(code)            # the add: refused before §6.6
        tex = io.open(os.path.join(d, "ch1.tex"), encoding="utf-8").read()
        self.assertIn("50\\%", tex, "the chapter holds the escape")
        self.assertNotRegex(tex.split("\\chapopen", 1)[1], r"(?<!\\)%(?! @par)",
                            "and no raw per cent sign in the text")
        src = "".join(io.open(os.path.join(d, "source", "paras", f), encoding="utf-8").read()
                      for f in sorted(os.listdir(os.path.join(d, "source", "paras"))))
        self.assertIn("50%", src, "the source keeps the text as typed")

        # the fidelity check, and texparse, see the text
        rc, out = run([sys.executable, os.path.join(LIB, "verify_book.py")], d)
        self.assertTrue(rc == 0 and " 0 mismatched" in out, out[-600:])
        text = " ".join(c.fa for c in self.every_chunk(d, L))
        for typed in ("50%", "R&D", "$5", "#1"):
            self.assertIn(typed, text)

        # the reader prints what was typed, not its escape
        rc, out = run([sys.executable, os.path.join(LIB, "tex2html.py"), "--book", d], d)
        self.assertEqual(rc, 0, out[-600:])
        page = io.open(os.path.join(d, "reader", "index.html"), encoding="utf-8").read()
        self.assertIn("50%", page)
        self.assertIn("R&amp;D", page)
        self.assertNotIn("50\\%", page)
        self.assertNotIn("R\\&amp;D", page)

        # the chunk sheet: offered as typed, edited, saved, read back as typed
        path = texwrite.book_chapters(d)[0]["path"]
        recs = texwrite.read_chunks(path)
        k = next(i for i, r in enumerate(recs) if "50%" in r["fa"])
        self.assertNotIn("\\%", recs[k]["fa"])
        fields = {"en": "half & half, 100% {sure} ~ ^ _ # $ \\ done"}
        if L.require_tr:
            fields["tr"] = "fifty per cent"
        if L.reading:
            fields["kana"] = "けんきゅう"
        got = texwrite.edit_chunk(path, k, fields)
        self.assertIn("ok", got["fidelity"] + " ok")
        back = texwrite.read_chunks(path)[k]
        self.assertEqual(back["en"], fields["en"])
        self.assertEqual(back["fa"], recs[k]["fa"], "the text did not move")
        again = self.every_chunk(d, L)
        self.assertEqual([c.en for c in again if c.en], [fields["en"]])
        # the text itself, edited through the sheet with a special in it:
        # the same text sent back is accepted and changes nothing
        same = texwrite.edit_chunk(path, k, {"fa": recs[k]["fa"]})
        self.assertEqual(same["changed"], [])
        rc, out = run([sys.executable, os.path.join(LIB, "verify_book.py")], d)
        self.assertTrue(rc == 0 and " 0 mismatched" in out, out[-600:])

        # the timings key hashes the text as typed
        sub = next(s for ch in chunks_of(os.path.join(d, "main.tex"), L) for s in ch.subs
                   if any("50%" in c.fa for c in s.chunks))
        joined = (L.word_sep or "").join(c.fa for c in sub.chunks)
        self.assertEqual(timestamp.subkey(sub), "%s-%s" % (
            sub.num, hashlib.sha1(L.strip(joined).encode("utf-8")).hexdigest()[:12]))
        self.assertIn("50%", joined)

        # the bundle carries the chapter as it is, escapes and all
        import bundle
        data, _name = bundle.pack_book(d)
        z = zipfile.ZipFile(io.BytesIO(data))
        inside = [n for n in z.namelist() if n.endswith("ch1.tex")]
        self.assertTrue(inside and "50\\%" in z.read(inside[0]).decode("utf-8"))

        # check_batch passes the paragraph read back out of the .tex
        ch = chunks_of(os.path.join(d, "main.tex"), L)[0]
        para = ch.paragraphs[0]
        sents = [{"chunks": [dict({"fa": c.fa, "tr": c.tr, "voc": c.voc, "en": c.en},
                                  **({"kana": c.kana} if c.kana else {}),
                                  **({"words": c.wordline} if c.wordline else {}))
                             for c in s.chunks]} for s in para.subs]
        pj = os.path.join(d, "p0.json")
        json.dump({"idx": 0, "ch": 1, "ann": {"sentences": sents}},
                  io.open(pj, "w", encoding="utf-8"), ensure_ascii=False)
        rc, out = run([sys.executable, os.path.join(LIB, "check_batch.py"), pj, "--book", d], d)
        self.assertTrue("\n0 errors" in out, out[-600:])

    @unittest.skipUnless(shutil.which("lualatex") and shutil.which("pdftotext"),
                         "lualatex or pdftotext is not installed here")
    def test_the_pdf_prints_what_was_typed(self):
        L, d = self.make("en")
        p = subprocess.run(["lualatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
                           cwd=d, capture_output=True, text=True, timeout=900)
        self.assertTrue(os.path.isfile(os.path.join(d, "main.pdf")), p.stdout[-2000:])
        txt = subprocess.run(["pdftotext", "-layout", "main.pdf", "-"], cwd=d,
                             capture_output=True, text=True).stdout
        flat = re.sub(r"\s+", " ", txt)
        for typed in ("50%", "R&D", "$5", "#1", "a_b", "{and}", "back\\slash"):
            self.assertIn(typed, flat)


if __name__ == "__main__":
    unittest.main()
