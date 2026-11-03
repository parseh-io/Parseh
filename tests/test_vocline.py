# SPDX-License-Identifier: GPL-3.0-or-later
"""A vocabulary line, read and drawn twice and held equal: lib/texparse.py
(parse_voc, voc_text) and lib/tex2html.py (render_voc) in Python, which the
reader and the PDF go by, and lib/vocline.js, which a video's player draws a
macro line with.

    python3 -m unittest tests/test_vocline.py

tests/fixtures/vocline.json holds the cases, as tests/fixtures/wordline.json
holds the word line's; the Python side is run here, the JavaScript side under
deno.  Beyond the fixture, every vocabulary line of every fixture book and
video is read by both, and so are a couple of thousand random lines, so an
equality that holds only for the lines somebody thought of would not pass.
The last class is lib/vocbuttons.js: the examples its four buttons show.
Standard library only.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "youtube" / "lib"))
import chunkdiv        # noqa: E402
import languages       # noqa: E402
import tex2html as X   # noqa: E402
import texparse as T   # noqa: E402
import texwrite        # noqa: E402

FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "vocline.json").read_text(encoding="utf-8"))
CASES = FIXTURE["cases"]
DENO = shutil.which("deno") or os.path.expanduser("~/miniconda3/envs/ilya-frank/bin/deno")
VOCLINE = ROOT / "lib" / "vocline.js"


def read_in_python(voc, code):
    """What the reader's own code makes of one line, in the fixture's shape."""
    L = languages.get(code)
    was = T._LANG, X.LANG
    T.set_lang(L)
    X.set_lang(L)
    try:
        return {"runs": [list(r) for r in T.parse_voc(voc, L)],
                "html": X.render_voc(voc), "text": T.voc_text(voc, L),
                "macro": chunkdiv.is_macro_line(voc)}
    except (AssertionError, IndexError):        # a group missing, or none left to read
        return {"error": "groups", "macro": chunkdiv.is_macro_line(voc)}
    except ValueError:                          # read_group: a { never closed
        return {"error": "unclosed", "macro": chunkdiv.is_macro_line(voc)}
    finally:
        T._LANG, X.LANG = was


def read_in_javascript(lines):
    """[{lang, voc}] -> what lib/vocline.js makes of each, run under deno."""
    codes = sorted({x["lang"] for x in lines})
    js = """
await import(%s);
const V = globalThis.ParsehVocline, LINES = %s, LANGS = %s, out = [];
for (const c of LINES) {
  const L = LANGS[c.lang], r = {macro: V.isMacro(c.voc)};
  try { r.runs = V.parse(c.voc, L); r.html = V.render(c.voc, L); r.text = V.flatten(c.voc, L); }
  catch (e) { r.error = e.code; }
  out.push(r);
}
console.log(JSON.stringify(out));
""" % (json.dumps("file://" + str(VOCLINE)), json.dumps(lines),
       json.dumps({c: languages.get(c).as_json() for c in codes}))
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as f:
        f.write(js)
    try:
        r = subprocess.run([DENO, "run", "--quiet", "--allow-read", f.name],
                           capture_output=True, text=True, timeout=120)
    finally:
        os.unlink(f.name)
    if r.returncode:
        raise AssertionError("deno failed: " + (r.stderr or r.stdout)[-600:])
    return json.loads(r.stdout.strip().split("\n")[-1])


def fixture_lines():
    """Every vocabulary line the fixture books and videos hold, with its
    language: what a real edition and a real video write, not what a test
    thought of."""
    import books
    out = []
    for d in sorted(glob.glob(str(ROOT / "tests" / "fixtures" / "books" / "*" / "*"))):
        if not os.path.isfile(os.path.join(d, "book.json")):
            continue
        code = books.Book(d).lang.code
        for path in sorted(glob.glob(os.path.join(d, "ch*.tex"))):
            out += [{"lang": code, "voc": c["voc"]} for c in texwrite.read_chunks(path) if c["voc"].strip()]
    for fx in sorted(glob.glob(str(ROOT / "tests" / "fixtures" / "videos" / "*" / "*" / "video.json"))):
        code = languages.get_or_default(json.loads(Path(fx).read_text(encoding="utf-8")).get("language")).code
        ann = json.loads((Path(fx).parent / "annotations.json").read_text(encoding="utf-8"))
        out += [{"lang": code, "voc": ch["voc"]} for sg in ann["segments"]
                for ch in (sg.get("chunks") or []) if isinstance(ch.get("voc"), str) and ch["voc"].strip()]
    return out


class Fixture(unittest.TestCase):
    def test_every_case_says_what_it_expects(self):
        for c in CASES:
            with self.subTest(voc=c["voc"]):
                self.assertIn(c["lang"], languages.CODES)
                self.assertIsInstance(c["macro"], bool)
                if "error" in c:
                    self.assertIn(c["error"], ("groups", "unclosed"))
                else:
                    self.assertEqual(sorted(k for k in c if not k.startswith("_")),
                                     ["html", "lang", "macro", "runs", "text", "voc"])

    def test_it_covers_what_it_is_for(self):
        """A fixture that has lost a kind of line has stopped guarding it:
        both labels of a \\vb, a pair left blank, a \\bw without its braces, a
        \\pw inside a meaning, a slash beside a macro, a \\textit,
        right-to-left, Japanese, a plain line -- and a line that cannot be
        read, of each of the two kinds."""
        def labels(c):
            L = languages.get(c["lang"])
            return {lab for lab in L.vb_labels
                    if any(k == "txt" and t == " · %s " % lab for k, t in c.get("runs", []))}
        kinds = {
            "both labels of a \\vb": lambda c: "\\vb{" in c["voc"] and len(labels(c)) == 2,
            "a pair left blank": lambda c: "\\vb{" in c["voc"] and len(labels(c)) == 1 and "{}{}" in c["voc"],
            "a \\bw without its braces": lambda c: "error" not in c and bool(
                re.search(r"\\bw\{[^{}]*\}\{[^{}]*\}[ \t]*[^{ \t]", c["voc"])),
            "a \\pw in a meaning": lambda c: "error" not in c and bool(
                re.search(r"\\vb(\{[^{}]*\}){6}\{[^{}]*\\pw\{", c["voc"])),
            "a slash beside a macro": lambda c: "}/\\pw{" in c["voc"] and "error" not in c,
            "a \\textit": lambda c: "\\textit{" in c["voc"] and "error" not in c,
            "Persian, right to left": lambda c: c["lang"] == "fa" and 'dir="rtl"' in c.get("html", ""),
            "Arabic, right to left": lambda c: c["lang"] == "ar" and 'dir="rtl"' in c.get("html", ""),
            "Japanese": lambda c: c["lang"] == "ja" and "error" not in c,
            "a plain line": lambda c: not c["macro"] and "error" not in c,
            "a macro short of its braces": lambda c: c.get("error") == "groups",
            "a brace never closed": lambda c: c.get("error") == "unclosed",
        }
        missing = [name for name, has in kinds.items() if not any(has(c) for c in CASES)]
        self.assertEqual(missing, [])
        # and every language of the registry has a \\vb of its own in it
        wrote = {c["lang"] for c in CASES if "\\vb{" in c["voc"] and "error" not in c}
        self.assertEqual(sorted(set(languages.CODES) - wrote), [])


class Python(unittest.TestCase):
    def test_the_reader_reads_the_fixture(self):
        for c in CASES:
            with self.subTest(voc=c["voc"]):
                got = read_in_python(c["voc"], c["lang"])
                want = {k: c[k] for k in ("runs", "html", "text", "error") if k in c}
                want["macro"] = c["macro"]
                self.assertEqual(got, want)


@unittest.skipUnless(os.path.exists(DENO), "no deno")
class JavaScript(unittest.TestCase):
    def test_the_page_reads_the_fixture(self):
        got = read_in_javascript([{"lang": c["lang"], "voc": c["voc"]} for c in CASES])
        self.assertEqual(len(got), len(CASES), "one answer for every case")
        for c, g in zip(CASES, got):
            with self.subTest(voc=c["voc"]):
                want = {k: c[k] for k in ("runs", "html", "text", "error") if k in c}
                want["macro"] = c["macro"]
                self.assertEqual(g, want)

    def test_and_every_line_of_every_fixture_edition_and_video(self):
        lines = fixture_lines()
        self.assertGreater(len(lines), 100, "the fixture books and videos hold vocabulary lines")
        got = read_in_javascript(lines)
        self.assertEqual(len(got), len(lines), "one answer for every line")
        for c, g in zip(lines, got):
            with self.subTest(lang=c["lang"], voc=c["voc"]):
                self.assertEqual(g, read_in_python(c["voc"], c["lang"]))


    def test_and_lines_nobody_thought_of(self):
        """Random lines from an alphabet of what a line is made of -- macros, braces open and shut, escapes, the
        joining punctuation, every kind of space, a character outside the basic plane -- read alike by both,
        errors included.  The seed is fixed: what failed once fails again."""
        import random
        pieces = ["\\dw", "\\vb", "\\bw", "\\pw", "\\textit", "\\emph", "\\nobreak", "\\foo", "\\,", "\\ ", "\\\\",
                  "\\%", "\\&", "\\{", "\\}", "{", "}", "{", "}", "{", "}", "a", "b", " ", "  ", "\n", "\t", ";", "; ",
                  " · ", "(", ")", "/", "‘", "’", ".", ",", ":", "~", "--", "---", "کتاب", "書く", "é", " ",
                  "　", "\x1c", "\x85", "﻿", "‌", "\U00020bb7", "x", "y y", "1", "%", "&", "<", ">", "'", '"']
        rnd = random.Random(20260929)
        voc = ["".join(rnd.choice(pieces) for _ in range(rnd.randint(1, 26))) for _ in range(1500)]
        for _ in range(1000):                       # macros with about the groups they take
            parts = []
            for _k in range(rnd.randint(1, 5)):
                m = rnd.choice(["dw", "vb", "bw", "pw", "textit", "emph"])
                n = max(0, T.VOC_MACROS[m] + rnd.choice([0, 0, 0, -1, 1]))
                groups = "".join("{%s}" % "".join(rnd.choice(pieces[7:]) for _ in range(rnd.randint(0, 4))) for _ in range(n))
                parts.append("\\" + m + groups + rnd.choice(["", " ", " text", "; ", " · ", "/"]))
            voc.append("".join(parts))
        cases = [{"lang": rnd.choice(languages.CODES), "voc": v} for v in voc]
        got = read_in_javascript(cases)
        self.assertEqual(len(got), len(cases))
        odd = [(c, g, read_in_python(c["voc"], c["lang"])) for c, g in zip(cases, got)
               if g != read_in_python(c["voc"], c["lang"])]
        self.assertEqual(odd[:3], [])


@unittest.skipUnless(os.path.exists(DENO), "no deno")
class Buttons(unittest.TestCase):
    """lib/vocbuttons.js: the four buttons' examples, one per language and kind."""

    KINDS = ("dw", "vb", "bw", "pw")

    @classmethod
    def setUpClass(cls):
        js = """
globalThis.document = {readyState: 'complete', getElementById: () => null};
await import(%s);
await import(%s);
const B = globalThis.ParsehVocButtons, LANGS = %s, out = {examples: {}, titles: {}};
// a language's own examples are its row's (examples.macros); the table holds the eleven of a0.6.0, for older readers
for (const [code, L] of Object.entries(LANGS)) out.examples[code] = (L.examples && L.examples.macros) || B.EXAMPLES[code];
// a language somebody added has no example of its own, nor forms in its registry row
out.added = ['dw', 'vb', 'bw', 'pw'].map(k => B.explain(k, {code: 'zz', name: 'Zzish'}, {name: 'English', code: 'en'}).title);
for (const [code, L] of Object.entries(LANGS)) {
  out.titles[code] = {};
  for (const k of %s) out.titles[code][k] = B.explain(k, L, {name: 'English', code: 'en'}).title;
}
console.log(JSON.stringify(out));
""" % (json.dumps("file://" + str(VOCLINE)), json.dumps("file://" + str(ROOT / "lib" / "vocbuttons.js")),
       json.dumps({c: languages.get(c).as_json() for c in languages.CODES}), json.dumps(list(cls.KINDS)))
        with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as f:
            f.write(js)
        try:
            r = subprocess.run([DENO, "run", "--quiet", "--allow-read", f.name], capture_output=True, text=True, timeout=120)
        finally:
            os.unlink(f.name)
        if r.returncode:
            raise AssertionError("deno failed: " + (r.stderr or r.stdout)[-600:])
        cls.got = json.loads(r.stdout.strip().split("\n")[-1])

    def test_every_language_has_an_example_for_every_kind(self):
        for code in languages.CODES:
            for kind in self.KINDS:
                with self.subTest(code=code, kind=kind):
                    self.assertTrue(self.got["examples"][code][kind].strip())

    def test_every_example_is_a_line_both_renderers_read_alike_and_both_doors_take(self):
        """The buttons stand in the book's chunk sheet and the video's form, so what they show as an example must be
        what either would accept -- a book's check (LaTeX's rules included), a video's -- and what the reader's code
        and the page's draw the same."""
        import check_annotations as CA
        lines = [{"lang": code, "voc": self.got["examples"][code][kind]}
                 for code in languages.CODES for kind in self.KINDS]
        drawn = read_in_javascript(lines)
        for line, js in zip(lines, drawn):
            with self.subTest(**line):
                self.assertTrue(chunkdiv.is_macro_line(line["voc"]), "an example is a line in the books' macros")
                self.assertEqual(js, read_in_python(line["voc"], line["lang"]))
                errs = []
                CA.check_voc(line["voc"], "example", errs.append)
                self.assertEqual(errs, [], "a video takes it")
                texwrite._check_voc(line["voc"], "example")           # and a book does, or raises Refused

    def test_a_language_somebody_added_is_explained_without_an_example(self):
        for title in self.got["added"]:
            with self.subTest(title=title):
                self.assertEqual(len(title.split("\n")), 2, "the kind and the braces, and no example to draw")
                self.assertNotIn("undefined", title)
                self.assertNotIn("looks like", title)
        self.assertIn("the form it is listed under · its pres. form · its past form", self.got["added"][1])

    def test_the_title_says_the_three_things_and_the_example_as_text(self):
        for code in languages.CODES:
            L = languages.get(code)
            for kind in self.KINDS:
                with self.subTest(code=code, kind=kind):
                    first, braces, look = self.got["titles"][code][kind].split("\n")
                    self.assertRegex(first, r"^(word|verb|compound|word in a meaning) — ")
                    self.assertTrue(braces.startswith("in the braces"))
                    self.assertEqual(look, "looks like: " + T.voc_text(self.got["examples"][code][kind], L))
            forms = " · ".join(L.vb_forms[:3])
            self.assertIn(forms, self.got["titles"][code]["vb"], "a verb's says the language's own three forms")
            self.assertIn("‘%s’ and ‘%s’" % tuple(L.vb_labels), self.got["titles"][code]["vb"])


if __name__ == "__main__":
    unittest.main()
