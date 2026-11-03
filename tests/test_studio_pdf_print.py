# SPDX-License-Identifier: GPL-3.0-or-later
"""The studio's PDF at its print options, built and read back
(markdown/exlex/texgen.py, "print options"; the exercises' layouts on paper).

    python3 -m unittest discover -s tests -p test_studio_pdf_print.py

A document holding every exercise type and every source of colour is built
by the real `exlex.py build` -- at 11 pt in colour, in black and white, and
at 20 pt -- and by the studio's own build_pdf, and what is read is what the
builds leave: exit codes, the log, and the PDF through PyMuPDF (the colour
of every span and every drawn path, the size of the text, where the true /
false marks stand, how many lines construct-the-sentence draws).  Needs
xelatex with the extsizes package and PyMuPDF; without them the tests say
so and are skipped."""
import math
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXLEX = ROOT / "markdown" / "exlex" / "exlex.py"
for folder in (ROOT / "markdown" / "exlex", ROOT / "markdown" / "app", ROOT / "lib"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

TEX = bool(shutil.which("xelatex") and shutil.which("kpsewhich"))
EXTSIZES = TEX and bool(subprocess.run(["kpsewhich", "extarticle.cls"], capture_output=True,
                                       text=True).stdout.strip())
try:
    import pymupdf
    HAVE_PYMUPDF = True
except ImportError:
    HAVE_PYMUPDF = False

PICTURE = ROOT / "tests" / "fixtures" / "studio" / "feature-test" / "images" / "pattern.png"
AUDIO_FIXTURE = ROOT / "tests" / "fixtures" / "studio" / "audio"
PASSAGE = ("لیلا پانزده ساله است. وقتی به دبیرستان می رود، آیفون و آیپدش را با خود می برد. "
           "لیلا در طولِ راه از همه چیز عکس می گیرد، ایمیل هایش را می خواند و به موسیقی گوش می دهد. "
           "بر خلافِ پدرش، او وسایل و تکنولوژی های جدید را خیلی دوست دارد و کارکردن با آنها برایش آسان است. ")
DOC = """---
title: Printed exercises
lang: en
target: fa
---

Every colour: [کتاب]{teal}, [قلم]{#8E2B34}, [تند]{#AA3377 translit:tond}, a
[link](https://example.org), a note^[A note with [کند]{crimson} in it.], ✗غلط and ✅.

## [آهسته]{#1E7A3C} | âheste | a coloured lemma

> A box with a [link](https://example.com).

[من بی می ناب زیستن نتوانم]{tl bg=lilac}

![A pattern](images/pattern.png){width=40 align=center}

آهسته برو، آهسته بیا، که گربه شاخت نزنه و هیچ کس هم نفهمد که تو کجا رفتی و کی برگشتی

:::exercise true-false
prompt: Decide whether each statement is true or false.
- [پدر لیلا تکنولوژی را دوست دارد.]{tl} => false
- [معلّم هایِ لیلا بیشتر از او دربارۀ استفاده از تکنولوژی می دانند و این را همه در کلاس و در خانه می دانند.]{tl} => false
- [پیدا کردنِ اطلاعات از وبسایت ها برایِ لیلا آسان است.]{tl} => true
:::

:::exercise yes-no
prompt: Yes or no?
- Is this an English question long enough to wrap onto a second line of its own column at every size? => no
- Is it short? => yes
:::

:::exercise construct-sentence
prompt: Build the sentence.
- [1] [من]{tl}
- [2] [هر روز]{tl}
- [3] [قهوه می نوشم.]{tl}
:::

:::exercise construct-sentence
prompt: Build the long sentence.
- [1] [لیلا و دوستانش]{tl}
- [2] [روزها و ماه ها]{tl}
- [3] [منتظرِ ابزارهایِ جدید]{tl}
- [4] [می مانند و]{tl}
- [5] [وقتی مدلِ جدیدی می آید،]{tl}
- [6] [به فروشگاه هایِ بزرگ]{tl}
- [7] [مانند اپل می روند]{tl}
- [8] [و ساعت ها در صف می ایستند.]{tl}
:::

:::exercise match-translations
prompt: Match them.
- [سلام]{tl} => hello
- [خداحافظ]{tl} => goodbye
- ![A pattern](images/pattern.png) => [الگو]{tl}
:::

:::exercise fill-blanks
prompt: Fill the blank.
text: [من [[a]] می نوشم]{tl}
- [a] [قهوه]{tl}
- [ ] [کتاب]{tl}
:::

:::exercise order-sentences
prompt: Order them.
- [1] First line.
- [2] Second line.
:::

:::exercise flashcard
card-type: vocab
target: [کتاب]{tl}
meaning: book
:::

:::exercise single-choice
prompt: |
  Read, then choose.
  [[%s]{tl}]{no-bold}
- [x] [آری]{tl}
- [ ] [نه]{tl}
:::
""" % (PASSAGE * 5).strip()

# A Latin target, where TeX hyphenates: a statement long enough to wrap
# beside its marks, a matching entry that wraps beside the one it faces,
# and, for large print, words no column at 20 pt is wide enough for.
DOC_DE = """---
title: Lange Wörter
lang: en
target: de
---

:::exercise true-false
prompt: Richtig oder falsch?
- [Geschwindigkeitsbegrenzungsüberwachung ist in Deutschland streng.]{tl} => true
- [Jeden Morgen stehe ich früh auf, gehe im Park spazieren und trinke dann einen Kaffee in der kleinen Bar neben dem Bahnhof.]{tl} => true
- [Das ist kurz.]{tl} => false
- [Pi ist 3,14159265358979323846264338327950288 und so weiter.]{tl} => true
:::

:::exercise match-translations
prompt: Match them.
- [Geschwindigkeitsbegrenzung]{tl} => speed limit
- [Jeden Morgen trinke ich einen Kaffee in der kleinen Bar.]{tl} => every morning I drink a coffee in the little bar
- [Haus]{tl} => house
- [Wirtschaft]{tl} => socioeconomic/political
- [3,14159265358979323846264338327950288]{tl} => pi
:::
"""
# A vertical (tategaki) block whose column fits the page at 11 pt; its
# height is in ems, so at 20 pt the same column is almost twice as long.
DOC_TATE = """---
title: Tategaki
lang: en
target: ja
---

[
縦書きの文章です。縦書きの文章です。縦書きの文章です。縦書きの文章です。
]{tl vertical height=40}
"""
# Lemma heads whose transliteration (an IPA word) and meaning fit their
# column at 11 pt and are wider than it at 20.
DOC_LEMMA = """---
title: Lemmata
lang: en
target: de
---

## Geschwindigkeitsbegrenzung | ɡəˈʃvɪndɪçkaɪtsbəˌɡʁɛnt͡sʊŋ | speed limit

Some text.

## Donaudampfschifffahrt | ˈdoːnaʊ̯ˌdampfʃɪfˌfaːɐ̯t | Danube steamboat shipping (Donaudampfschifffahrtsgesellschaft)

More text.
"""
LONG_STATEMENT = "Jeden Morgen stehe ich früh auf, gehe im Park spazieren"
LONG_ENTRY = "Jeden Morgen trinke ich einen Kaffee in der kleinen Bar."

LABELS = ("True / False", "Yes / No", "Construct the sentence", "Match translations",
          "Fill the blanks", "Order the sentences", "Flashcard", "Choose one answer")


def build(md_dir, out, *options):
    r = subprocess.run([sys.executable, str(EXLEX), "build", str(md_dir / "doc.md"), "-o", str(out), "-q",
                        *options], cwd=str(ROOT / "markdown"), capture_output=True, text=True, timeout=600)
    return r


def spans(pdf):
    with pymupdf.open(str(pdf)) as d:
        return [(n, s) for n, page in enumerate(d) for b in page.get_text("dict")["blocks"]
                for l in b.get("lines", []) for s in l["spans"] if s["text"].strip()]


def construct_lines(log):
    """(W, L, N) of every construct-the-sentence the build set, from the line
    \\expaperwritelines writes into the log."""
    return [(float(w), float(l), int(n)) for w, l, n in re.findall(
        r"exlex construct-sentence: W=([\d.]+)pt\s+L=([\d.]+)pt\s+lines=(\d+)", log)]


def writing_rules(pdf, width):
    """The rules drawn as wide as an exercise's line (`width` in TeX points,
    the PDF's in big points) that are not the top or foot of a frame -- a
    chunk too long for the line is framed as wide as it: its writing lines."""
    width *= 72 / 72.27
    n = 0
    with pymupdf.open(str(pdf)) as d:
        for page in d:
            rects = [p["rect"] for p in page.get_drawings()]
            sides = [r for r in rects if r.width < 1.2 and r.height > 2]
            for r in rects:
                if abs(r.width - width) < 0.6 and r.height < 1.2 and not any(
                        abs(v.x0 - r.x0) < 1 and v.y0 - 1 <= r.y0 <= v.y1 + 1 for v in sides):
                    n += 1
    return n


def arabic(c):
    return 0x0600 <= ord(c) <= 0x06FF


def marks_and_statements(pdf, marks="True / False", below="Yes or no?", letter=arabic):
    """Per page, the rectangles of the marks, and the right edges of the
    statements' letters (Arabic script, or what `letter` accepts, the
    marks' own apart) on the rows beside them."""
    out = []
    with pymupdf.open(str(pdf)) as d:
        for page in d:
            # the exercise's own label reads the same, at the left of its box
            rects = [r for r in page.search_for(marks) if r.x0 > page.rect.width / 2]
            if not rects:
                continue
            stop = [r.y0 for r in page.search_for(below)] or [page.rect.y1]
            top, bottom = min(r.y0 for r in rects) - 1, min(stop)
            right = [c["bbox"][2] for b in page.get_text("rawdict")["blocks"] for l in b.get("lines", [])
                     for s in l["spans"] for c in s["chars"]
                     if letter(c["c"]) and top <= c["bbox"][1] < bottom
                     and not any(r.contains(pymupdf.Rect(c["bbox"])) for r in rects)]
            out.append((rects, right))
    return out


def entries_and_frames(pdf, prompt="Match them."):
    """Per page of a matching exercise: its entries' letters and digits
    (character, bbox) under the prompt, and the frames' white insides."""
    out = []
    with pymupdf.open(str(pdf)) as d:
        for page in d:
            hits = page.search_for(prompt)
            if not hits:
                continue
            paths = page.get_drawings()
            box = next(p["rect"] for p in paths
                       if p.get("fill") and p["rect"].contains(hits[0]) and p["rect"].width > page.rect.width / 2)
            frames = [p["rect"] for p in paths if p.get("fill") == (1.0, 1.0, 1.0)]
            glyphs = [(c["c"], pymupdf.Rect(c["bbox"])) for b in page.get_text("rawdict")["blocks"]
                      for l in b.get("lines", []) for s in l["spans"] for c in s["chars"]
                      if c["c"].isalnum() and hits[0].y1 < c["bbox"][1] and c["bbox"][3] < box.y1]
            out.append((frames, glyphs))
    return out


def card_frames(pdf):
    """Every flashcard printed, as the PDF draws it: (page number, its
    frame -- a stroked path wider than half the page, with the curves of its
    round corners --, its fold line -- a dashed line inside it --, the
    frame's colour, the letters inside the frame as (character, bbox))."""
    out = []
    with pymupdf.open(str(pdf)) as d:
        for page in d:
            paths = page.get_drawings()
            glyphs = [(c["c"], pymupdf.Rect(c["bbox"])) for b in page.get_text("rawdict")["blocks"]
                      for l in b.get("lines", []) for s in l["spans"] for c in s["chars"] if c["c"].strip()]
            for p in paths:
                r = p["rect"]
                if not (p.get("color") and r.width > page.rect.width / 2
                        and any(item[0] == "c" for item in p["items"])):
                    continue
                folds = [q["rect"] for q in paths if q.get("dashes") not in (None, "[] 0")
                         and q["rect"].width < 2 and r.x0 < q["rect"].x0 < r.x1
                         and r.y0 - 2 <= q["rect"].y0 and q["rect"].y1 <= r.y1 + 2]
                if len(folds) == 1:
                    out.append((page.number, r, folds[0], p["color"],
                                [(c, g) for c, g in glyphs if r.contains(g.tl) and r.contains(g.br)]))
    return out


def image_samples(pdf):
    with pymupdf.open(str(pdf)) as d:
        for page in d:
            for info in page.get_images(full=True):
                pm = pymupdf.Pixmap(d, info[0])
                if pm.width == 480:                  # the pattern, not the one in a cell
                    return pm.samples
    return None


@unittest.skipUnless(TEX, "needs xelatex and kpsewhich")
@unittest.skipUnless(EXTSIZES, "the TeX package extsizes (extarticle.cls) is not installed: no large print here")
@unittest.skipUnless(HAVE_PYMUPDF, "PyMuPDF is not installed in this Python")
class PrintedPdf(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="parseh-pdf-print-")
        cls.dir = Path(cls.tmp.name)
        (cls.dir / "images").mkdir()
        shutil.copy(PICTURE, cls.dir / "images" / "pattern.png")
        (cls.dir / "doc.md").write_text(DOC, encoding="utf-8")
        (cls.dir / "de").mkdir()
        (cls.dir / "de" / "doc.md").write_text(DOC_DE, encoding="utf-8")
        (cls.dir / "lemma").mkdir()
        (cls.dir / "lemma" / "doc.md").write_text(DOC_LEMMA, encoding="utf-8")
        (cls.dir / "tate").mkdir()
        (cls.dir / "tate" / "doc.md").write_text(DOC_TATE, encoding="utf-8")
        shutil.copytree(AUDIO_FIXTURE, cls.dir / "audio")
        (cls.dir / "audio" / "audio.md").rename(cls.dir / "audio" / "doc.md")
        cls.runs = {}
        for name, source, options in (
                ("colour", cls.dir, ()), ("mono", cls.dir, ("--mono",)),
                ("large", cls.dir, ("--size", "20")), ("both", cls.dir, ("--size", "14", "--mono")),
                ("de", cls.dir / "de", ()), ("de17", cls.dir / "de", ("--size", "17")),
                ("de20", cls.dir / "de", ("--size", "20")),
                ("audio17", cls.dir / "audio", ("--size", "17")),
                ("audio20", cls.dir / "audio", ("--size", "20")),
                ("tate20", cls.dir / "tate", ("--size", "20")),
                ("lemma20", cls.dir / "lemma", ("--size", "20"))):
            out = cls.dir / name
            cls.runs[name] = (build(source, out, *options), out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def built(self, name):
        r, out = self.runs[name]
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"verify: (\d+)/\1 ")
        return out

    def test_every_exercise_is_printed_in_every_mode(self):
        for name in ("colour", "mono", "large", "both"):
            out = self.built(name)
            text = " ".join(s["text"] for _, s in spans(out / "main.pdf"))
            for label in LABELS:
                self.assertIn(label, text, name)
            for words in ("goodbye", "Second line.", "Is it short?", "Read, then choose."):
                self.assertIn(words, text, name)

    def test_colour_is_colour(self):
        # the check below would see a colour: the colour build has them
        colours = {s["color"] for _, s in spans(self.built("colour") / "main.pdf")}
        self.assertGreater(len(colours - {0}), 3)

    def test_black_and_white_has_no_colour_and_no_grey_but_the_pictures(self):
        for name in ("mono", "both"):
            pdf = self.built(name) / "main.pdf"
            coloured = [(n, hex(s["color"]), s["text"][:20]) for n, s in spans(pdf) if s["color"] != 0]
            self.assertEqual([], coloured, name)
            bw = lambda c: c is None or all(abs(x) < 1e-6 for x in c) or all(abs(x - 1) < 1e-6 for x in c)
            with pymupdf.open(str(pdf)) as d:
                paths = [p for page in d for p in page.get_drawings()]
            self.assertGreater(len(paths), 20)       # frames, rules, the writing lines
            grey = [(p.get("color"), p.get("fill")) for p in paths
                    if not (bw(p.get("color")) and bw(p.get("fill")))]
            self.assertEqual([], grey, name)
        # the picture, pixel for pixel the one the colour build printed
        colour = image_samples(self.built("colour") / "main.pdf")
        self.assertIsNotNone(colour)
        self.assertEqual(colour, image_samples(self.built("mono") / "main.pdf"))
        rgb = [tuple(colour[i:i + 3]) for i in range(0, len(colour), 3 * 97)]
        self.assertTrue(any(len(set(px)) > 1 for px in rgb), "the pattern has colours in it")

    def test_large_print_is_large_and_the_exercises_larger(self):
        sizes = {}
        for name, least in (("colour", 10.9), ("large", 20), ("both", 14)):
            got = spans(self.built(name) / "main.pdf")
            # (a justified line may come out a span a word: the first word)
            body = next(s["size"] for _, s in got if s["text"].startswith("Every"))
            prompt = next(s["size"] for _, s in got if s["text"].startswith("Decide"))
            self.assertGreaterEqual(body, least * 72 / 72.27, name)    # PDF points
            sizes[name] = (body, prompt)
        self.assertEqual(sizes["colour"][0], sizes["colour"][1], "at 11 pt an exercise is the body's size")
        self.assertGreater(sizes["large"][1], sizes["large"][0] * 1.15, "at 20 pt an exercise is a step larger")

    def test_a_tall_exercise_goes_on_over_pages_and_nothing_is_cut_off(self):
        import languages
        import verify
        out = self.built("large")
        log = (out / "main.log").read_text(encoding="utf-8", errors="replace")
        self.assertNotIn("Overfull \\vbox", log)
        with pymupdf.open(str(out / "main.pdf")) as d:
            first = next(n for n, page in enumerate(d) if page.search_for("Read, then choose."))
            count = d.page_count
        # the passage and its choices are taller than a page at 20 pt: they
        # go on over the next, and the choices under the passage are there
        self.assertGreater(count - 1, first + 1)
        fa = languages.get("fa")
        lines = [verify._script_only(l, fa) for l in verify.logical_reconstruction(str(out / "main.pdf"))]
        self.assertTrue(any(verify._script_only("\u0622\u0631\u06cc", fa) in l for l in lines),
                        "the choice under the passage")

    def test_a_flashcard_is_a_card_to_cut_out_and_fold(self):
        # a frame with round corners, the front in its left half and the
        # back in its right, and a dashed line exactly between them, from
        # the frame's top to its foot: cut out and folded on it, the two
        # halves are back to back.  Nothing is set across the fold.
        for name in ("colour", "mono", "large", "both"):
            pdf = self.built(name) / "main.pdf"
            cards = card_frames(pdf)
            self.assertEqual(1, len(cards), name)            # the document's one card
            _n, frame, fold, colour, glyphs = cards[0]
            self.assertAlmostEqual((frame.x0 + frame.x1) / 2, fold.x0 + fold.width / 2, delta=0.05, msg=name)
            self.assertAlmostEqual(frame.y0, fold.y0, delta=1, msg=name)
            self.assertAlmostEqual(frame.y1, fold.y1, delta=1, msg=name)
            middle = fold.x0 + fold.width / 2
            self.assertEqual([], [c for c, r in glyphs if r.x0 < middle < r.x1], name)
            self.assertTrue(glyphs, name)
            front = "".join(c for c, r in glyphs if r.x1 <= middle)
            back = "".join(c for c, r in glyphs if r.x0 >= middle)
            self.assertIn("book", back, name)
            self.assertNotIn("book", front, name)
            self.assertTrue(any(arabic(c) for c in front) and not any(arabic(c) for c in back), name)
            # at least three fifths of a half as tall: an index card, folded
            self.assertGreaterEqual(frame.height, 0.6 * frame.width / 2 - 1, name)
            black = all(abs(x) < 1e-6 for x in colour)
            self.assertEqual(name in ("mono", "both"), black, (name, colour))

    def test_a_card_taller_than_a_page_is_made_to_fit_its_page_under_its_heading(self):
        # the audio fixture's first card is taller than a page at 17 pt and
        # at 20: a card is never split between pages, since two pieces could
        # not be folded -- it is made smaller instead, until it fits one page
        # with the heading it follows (a heading goes where its card goes),
        # its frame above the page number and nothing across its fold
        for name in ("audio17", "audio20"):
            out = self.built(name)
            log = (out / "main.log").read_text(encoding="utf-8", errors="replace")
            self.assertEqual([], re.findall(r"Overfull \\[hv]box.*", log), name)
            cards = card_frames(out / "main.pdf")
            self.assertEqual(2, len(cards), name)
            with pymupdf.open(str(out / "main.pdf")) as d:
                for n, frame, fold, _colour, glyphs in cards:
                    page = d[n]
                    number = [s["bbox"] for b in page.get_text("dict")["blocks"] for l in b.get("lines", [])
                              for s in l["spans"] if s["text"].strip() == str(n + 1)
                              and abs((s["bbox"][0] + s["bbox"][2]) / 2 - page.rect.width / 2) < 10]
                    self.assertEqual(1, len(number), (name, n))
                    self.assertLess(frame.y1, number[0][1], (name, n))
                    middle = fold.x0 + fold.width / 2
                    self.assertEqual([], [c for c, r in glyphs if r.x0 < middle < r.x1], (name, n))
                n, tall = cards[0][0], cards[0][1]
                self.assertGreater(tall.height, d[n].rect.height / 2, name)
                heading = d[n].search_for("A card made of blocks")
                self.assertTrue(heading, name)
                self.assertLess(heading[0].y1, tall.y0, name)
        # the back's علیک سلام wraps in its half, beside the front's lines:
        # the build verifies it (built() read N/N) by reading the halves as
        # columns, and without that it was reported missing
        import verify
        out = self.built("audio20")
        real = verify.side_by_side
        verify.side_by_side = lambda lines: []
        try:
            _ok, without = verify.check(str(out / "main.pdf"), str(out / "main.tex"))
        finally:
            verify.side_by_side = real
        self.assertEqual([("علیک سلام", "missing")], without)

    def test_a_lemma_heads_transliteration_stays_on_the_paper_in_large_print(self):
        # a one-word IPA 112 pt wider than its column at 20 pt ran off the
        # paper's edge; now it is scaled to the column, as the headword is
        out = self.built("lemma20")
        log = (out / "main.log").read_text(encoding="utf-8", errors="replace")
        self.assertEqual([], re.findall(r"Overfull \\hbox.*", log))
        with pymupdf.open(str(out / "main.pdf")) as d:
            page = d[0]
            glyphs = [(c["c"], c["bbox"]) for b in page.get_text("rawdict")["blocks"]
                      for l in b.get("lines", []) for s in l["spans"] for c in s["chars"]]
            margin = page.rect.width - 1.8 / 2.54 * 72          # the right margin at 20 pt
        self.assertIn("ʃ", [c for c, _ in glyphs])
        # every letter inside the margin (a hyphen hangs into it: microtype)
        self.assertEqual([], [c for c, box in glyphs if c.isalpha() and box[2] > margin + 1])

    def test_a_vertical_column_stays_on_the_paper_in_large_print(self):
        out = self.built("tate20")
        log = (out / "main.log").read_text(encoding="utf-8", errors="replace")
        self.assertEqual([], re.findall(r"Overfull \\vbox.*", log))
        with pymupdf.open(str(out / "main.pdf")) as d:
            page = d[0]
            number = [s["bbox"] for b in page.get_text("dict")["blocks"] for l in b.get("lines", [])
                      for s in l["spans"] if s["text"].strip() == "1"]
            column = [c["bbox"] for b in page.get_text("rawdict")["blocks"] for l in b.get("lines", [])
                      for s in l["spans"] for c in s["chars"] if 0x3000 <= ord(c["c"]) <= 0x9FFF]
        self.assertEqual(1, len(number))
        self.assertGreater(len(column), 20)              # the column starts on the first page
        self.assertLess(max(c[3] for c in column), number[0][1])

    def test_true_false_marks_stand_in_one_column_the_statements_never_under_them(self):
        for name in ("colour", "large"):
            found = marks_and_statements(self.built(name) / "main.pdf")
            rects = [r for rs, _ in found for r in rs]
            self.assertEqual(3, len(rects), name)            # one per statement, never split
            self.assertLess(max(r.x0 for r in rects) - min(r.x0 for r in rects), 0.05, name)
            self.assertLess(max(r.x1 for r in rects) - min(r.x1 for r in rects), 0.05, name)
            for rs, right in found:
                self.assertTrue(right, name)
                self.assertLess(max(right), min(r.x0 for r in rs) - 5, name)
            yes = marks_and_statements(self.built(name) / "main.pdf", "Yes / No", below="Build the sentence.")
            self.assertEqual(2, sum(len(rs) for rs, _ in yes), name)

    def test_a_run_wrapped_beside_the_marks_or_the_facing_entry_is_verified(self):
        # a left-to-right target: its lines are read whole, and the marks or
        # the facing entry stand between a wrapped run's pieces -- a correct
        # PDF was reported "missing" (built() reads the build's N/N)
        import verify
        out = self.built("de")
        pdf, tex = str(out / "main.pdf"), out / "main.tex"
        real = verify.column_runs
        verify.column_runs = lambda *a: ""
        try:
            _ok, without = verify.check(pdf, str(tex))
        finally:
            verify.column_runs = real
        missing = [a for a, _kind in without]
        self.assertTrue(any(a.startswith(LONG_STATEMENT) for a in missing), missing)
        self.assertIn(LONG_ENTRY, missing)
        # and the look down the columns accepts no run whose words are out
        # of order, nor one with a word the PDF does not have
        for wrong in (LONG_STATEMENT.replace("gehe im Park", "im Park gehe"),
                      LONG_ENTRY.replace("einen Kaffee", "keinen Kaffee")):
            right = LONG_STATEMENT if wrong.startswith("Jeden Morgen stehe") else LONG_ENTRY
            bad = self.dir / "de-wrong.tex"
            bad.write_text(tex.read_text(encoding="utf-8").replace(right, wrong), encoding="utf-8")
            _ok, failures = verify.check(pdf, str(bad))
            self.assertEqual(1, len(failures), wrong)

    def test_in_large_print_nothing_crosses_a_frame_or_the_marks(self):
        # at 17 and 20 pt no column is wide enough for the long words: the
        # statement hyphenates in its column, the entries in their frames,
        # a line ends after a slash, and what cannot break (digits) is
        # scaled down to its column -- nothing sticks out of one
        for name in ("de17", "de20"):
            out = self.built(name)
            log = (out / "main.log").read_text(encoding="utf-8", errors="replace")
            self.assertEqual([], re.findall(r"Overfull \\hbox.*", log), name)
            found = marks_and_statements(out / "main.pdf", below="Match them.", letter=str.isalnum)
            rects = [r for rs, _ in found for r in rs]
            self.assertEqual(4, len(rects), name)
            self.assertLess(max(r.x0 for r in rects) - min(r.x0 for r in rects), 0.05, name)
            for rs, right in found:
                self.assertTrue(right, name)
                self.assertLess(max(right), min(r.x0 for r in rs) - 5, name)
            pages = entries_and_frames(out / "main.pdf")
            self.assertTrue(pages, name)
            for frames, glyphs in pages:
                self.assertEqual(10, len(frames), name)      # five rows, two frames a row
                outside = [c for c, g in glyphs if not any(
                    f.x0 - 0.5 <= g.x0 and g.x1 <= f.x1 + 0.5 and f.y0 - 0.5 <= (g.y0 + g.y1) / 2 <= f.y1 + 0.5
                    for f in frames)]
                self.assertEqual([], outside, name)
            # "socioeconomic/" ended the line above
            self.assertIn("political", _lines(out / "main.pdf"), name)

    def test_construct_the_sentence_draws_the_lines_it_computed(self):
        for name in ("colour", "large", "both"):
            out = self.built(name)
            got = construct_lines((out / "main.log").read_text(encoding="utf-8", errors="replace"))
            self.assertEqual(2, len(got), name)
            for w, l, n in got:
                self.assertEqual(max(1, math.ceil(1.5 * w / l - 1e-9)), n, (name, w, l))
            (w1, l, n1), (w2, _l, n2) = got
            if name == "colour":
                self.assertEqual(1, n1)                      # a short sentence: one line at 11 pt
            self.assertGreater(n2, n1, name)                 # a long one: more
            self.assertEqual(n1 + n2, writing_rules(out / "main.pdf", l), name)

    def test_the_studio_builds_the_same_tex_and_records_the_options(self):
        import server
        import store
        with tempfile.TemporaryDirectory(prefix="parseh-pdf-print-lib-") as lib:
            was = store.use_library(Path(lib))
            try:
                meta = store.create(DOC)
                store.save_image(meta["id"], "pattern.png", PICTURE.read_bytes())
                build = server.build_pdf(meta["id"], 1.52, 14, True)
                self.assertEqual("ok", build["status"], build)
                self.assertEqual((14, True), (build["size"], build["mono"]))
                self.assertEqual((14, True), (store.get(meta["id"])[0]["build"]["size"],
                                              store.get(meta["id"])[0]["build"]["mono"]))
                studio = (store.doc_dir(meta["id"]) / "build" / "main.tex").read_text(encoding="utf-8")
            finally:
                store.use_library(was)
        self.assertEqual((self.built("both") / "main.tex").read_text(encoding="utf-8"), studio)

    def test_a_tex_without_extsizes_says_so(self):
        import texgen
        guard = texgen.print_class_tex(17).replace("{extarticle.cls}", "{exlex-no-such-class.cls}", 1)
        with tempfile.TemporaryDirectory(prefix="parseh-pdf-print-cls-") as td:
            (Path(td) / "t.tex").write_text(guard + "\n\\begin{document}x\\end{document}\n", encoding="utf-8")
            r = subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "t.tex"],
                               cwd=td, capture_output=True, text=True, timeout=120)
        self.assertNotEqual(0, r.returncode)
        self.assertIn("! Large print needs the TeX package extsizes", r.stdout)

    def test_a_run_that_wrapped_is_found_and_a_reversed_one_still_is_not(self):
        import verify
        out = self.built("large")
        # the display line wraps at 20 pt, and verifies (built() read N/N)
        tex = (out / "main.tex").read_text(encoding="utf-8")
        self.assertIn("{\\large\\pel{آهسته برو،", tex)
        ok, failures = verify.check(str(out / "main.pdf"), str(out / "main.tex"))
        self.assertEqual([], failures)
        # the classic bug put back -- runs without \beginR -- is still found,
        # and the second look across a line's end accepts none of it
        bug = self.dir / "bug"
        shutil.copytree(out, bug)
        broken = (tex.replace("\\mbox{\\tlfont\\beginR #1\\endR}", "\\mbox{\\tlfont #1}")
                     .replace("\\leavevmode{\\tlfont\\beginR #1\\endR}", "\\leavevmode{\\tlfont #1}"))
        self.assertNotEqual(tex, broken)
        (bug / "main.tex").write_text(broken, encoding="utf-8")
        subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
                       cwd=str(bug), capture_output=True, timeout=600, check=True)
        _ok, failures = verify.check(str(bug / "main.pdf"), str(bug / "main.tex"))
        self.assertTrue(failures)
        real = verify.wrapped_runs
        verify.wrapped_runs = lambda *a: ""
        try:
            _ok, without = verify.check(str(bug / "main.pdf"), str(bug / "main.tex"))
        finally:
            verify.wrapped_runs = real
        self.assertEqual(without, failures)


def _lines(pdf):
    with pymupdf.open(str(pdf)) as d:
        return [l.strip() for page in d for l in page.get_text("text").splitlines()]


# Ten pictures to match, each in its frame: taller than a page at the normal
# size, as a worksheet of colours or of the parts of the body is.
SWATCH = ROOT / "tests" / "fixtures" / "studio" / "exercises" / "images" / "swatch.png"
DOC_PICTURES = """---
title: Colours
lang: en
target: fa
---

:::exercise match-translations
prompt: Match the colours with their Persian names.
%s
:::
""" % "\n".join("- ![Colour %d](images/swatch.png) => [رنگ %d]{tl}" % (n, n) for n in range(1, 11))

# Headings, each over a matching exercise about a page tall -- six framed
# pictures and a prompt of one line more each time, so that between them
# they are shorter than a page with its heading, as tall as one, a little
# taller than a page, and taller than one -- each after a paragraph, so
# that the headings fall at every height of the page.
DOC_HEADINGS = """---
title: Quizzes
lang: en
target: fa
---
""" + "".join("""
%s

## Quiz %d

:::exercise match-translations
prompt: |
%s
%s
:::
""" % ("A paragraph before the quiz, long enough to take a line or two of the page. " * (1 + k % 3), k,
       "\n".join("  Line %d of the prompt." % (n + 1) for n in range(k + 1)),
       "\n".join("- ![Colour %d](images/swatch.png) => [رنگ %d]{tl}" % (n, n) for n in range(1, 7)))
    for k in range(9))


def outside_the_body(pdf, size=11):
    """Every picture, drawn path (frames, rules) and line of text of the PDF
    that is not inside the page body, the page number apart.  The body ends
    at the bottom margin plus TeX's \\maxdepth, half the class size, which
    the last line's depth may hang into; a piece of text is placed by its
    baseline."""
    margin = {11: 2.4, 14: 2.2, 17: 2.0, 20: 1.8}[size] / 2.54 * 72
    out = []
    with pymupdf.open(str(pdf)) as d:
        for page in d:
            top, foot = margin - 1, page.rect.height - margin + size / 2 * 72 / 72.27 + 0.5
            for info in page.get_image_info():
                if info["bbox"][1] < top or info["bbox"][3] > foot:
                    out.append((page.number + 1, "picture", info["bbox"]))
            for path in page.get_drawings():
                if path["rect"].y0 < top or path["rect"].y1 > foot:
                    out.append((page.number + 1, "path", tuple(path["rect"])))
            for b in page.get_text("dict")["blocks"]:
                for l in b.get("lines", []):
                    text = "".join(s["text"] for s in l["spans"]).strip()
                    baseline = l["spans"][0]["origin"][1] if l["spans"] else 0
                    if text and baseline > foot and text != str(page.number + 1):
                        out.append((page.number + 1, "text", text))
    return out


def outside_the_lines(pdf, size=11):
    """Every letter and digit, picture and drawn path of the PDF that sticks
    out of the text block sideways.  Punctuation and a hyphen hang into the
    margin by design (microtype's protrusion); a letter may not."""
    margin = {11: 2.5, 14: 2.2, 17: 2.0, 20: 1.8}[size] / 2.54 * 72
    out = []
    with pymupdf.open(str(pdf)) as d:
        for page in d:
            left, right = margin - 1.5, page.rect.width - margin + 1.5
            for b in page.get_text("rawdict")["blocks"]:
                for l in b.get("lines", []):
                    for s in l["spans"]:
                        for c in s["chars"]:
                            if c["c"].isalnum() and (c["bbox"][0] < left or c["bbox"][2] > right):
                                out.append((page.number + 1, c["c"], round(c["bbox"][0]), round(c["bbox"][2])))
            for info in page.get_image_info():
                if info["bbox"][0] < left or info["bbox"][2] > right:
                    out.append((page.number + 1, "picture", info["bbox"]))
            for path in page.get_drawings():
                if path["rect"].x0 < left or path["rect"].x1 > right:
                    out.append((page.number + 1, "path", tuple(path["rect"])))
    return out


STARTERS = ROOT / "markdown" / "exlex" / "starters"


@unittest.skipUnless(TEX, "needs xelatex and kpsewhich")
@unittest.skipUnless(EXTSIZES, "the TeX package extsizes (extarticle.cls) is not installed: no large print here")
@unittest.skipUnless(HAVE_PYMUPDF, "PyMuPDF is not installed in this Python")
class StartersInLargePrint(unittest.TestCase):
    """Every language's starter -- a tour of the whole dialect -- at the three
    large sizes, as a new document of that language is built from the page
    (the studio's build_pdf): nothing on the paper outside the text block,
    and every target string verified.  A phrase kept in one box, a Chinese
    sentence of short runs between blanks, a `code` span in a short line ran
    into the margin or off the paper."""

    @classmethod
    def setUpClass(cls):
        from concurrent.futures import ThreadPoolExecutor
        import languages
        import server
        import store
        import texgen
        cls.tmp = tempfile.TemporaryDirectory(prefix="parseh-pdf-starters-")
        was = store.use_library(Path(cls.tmp.name))
        try:
            jobs = []
            for md in sorted(STARTERS.glob("*.md")):
                for size in (14, 17, 20):
                    meta = store.create(server.new_template(md.stem))
                    store.adopt_starter_media(meta["id"])
                    jobs.append((md.stem, size, meta["id"]))

            def one(job):
                # the library is the thread's own (store.use_library)
                code, size, doc = job
                store.use_library(Path(cls.tmp.name))
                scale = float(texgen.default_scale(languages.get(code)))
                return server.build_pdf(doc, scale, size, False), store.doc_dir(doc) / "build"
            with ThreadPoolExecutor(4) as pool:
                cls.runs = {(code, size): got for (code, size, _doc), got in zip(jobs, pool.map(one, jobs))}
        finally:
            store.use_library(was)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_starter_stays_inside_the_text_block_in_large_print(self):
        self.assertEqual(len(list(STARTERS.glob("*.md"))) * 3, len(self.runs))     # every starter, at three sizes
        for (code, size), (build, out) in sorted(self.runs.items()):
            # built, and every target string found where it is printed
            self.assertEqual("ok", build["status"], (code, size, build))
            self.assertEqual(0, build["verify_failed"], (code, size, build["failures"]))
            self.assertGreater(build["verify_ok"], 20, (code, size))
            log = (out / "main.log").read_text(encoding="utf-8", errors="replace")
            self.assertEqual([], [x for x in re.findall(r"Overfull \\hbox \(([\d.]+)pt", log) if float(x) > 1],
                             (code, size))
            self.assertEqual([], outside_the_lines(out / "main.pdf", size), (code, size))
            self.assertEqual([], outside_the_body(out / "main.pdf", size), (code, size))


def lines_with_blanks(pdf):
    """Each line of the PDF as it reads, left to right, with a fill-in blank
    -- a rule as wide as a word and as thin as a line -- read as "＿" where
    it stands: a line that begins with its blank does not begin with the
    mark after it."""
    out = []
    with pymupdf.open(str(pdf)) as d:
        for page in d:
            items = [(c["origin"][1], c["bbox"][0], c["c"])
                     for b in page.get_text("rawdict")["blocks"] for l in b.get("lines", [])
                     for s in l["spans"] for c in s["chars"] if not c["c"].isspace()]
            items += [(p["rect"].y1, p["rect"].x0, "＿") for p in page.get_drawings()
                      if p["rect"].height < 2.5 and p["rect"].width > 20]
            lines = {}
            for y, x, c in items:
                k = next((k for k in lines if abs(k - y) <= 3), y)
                lines.setdefault(k, []).append((x, c))
            out += ["".join(c for _x, c in sorted(v)) for _y, v in sorted(lines.items())]
    return out


# A Chinese and a Japanese fill sentence, thirty times over with the blanks
# at another place on the line each time, each blank before a mark that
# closes (。，、？) or after one that opens （「.  Wherever the lines end, the
# next may not begin with the closing mark, nor a line end with the opening
# one: the break beside a blank set "？" alone at the head of a line.
KINSOKU = {"zh": ("我们每天早上七点半一起去学校上课然后中午在食堂吃饭下午再回家",
                  "%s[[1]]。他说%s[[2]]，对吗[[3]]？（[[4]]）「[[5]]」"),
           "ja": ("わたしはまいにちあさしちじにがっこうへいきますそしてひるごはんを",
                  "%s[[1]]。かれは%s[[2]]、といった[[3]]？（[[4]]）「[[5]]」")}
OPENING, CLOSING = "（「『“", "，。、？！）」』”：；"


def kinsoku_doc(code):
    words, sentence = KINSOKU[code]
    return ("---\ntitle: Blanks\nlang: en\ntarget: %s\n---\n\n## Blanks beside punctuation\n" % code
            + "".join("\n:::exercise fill-blanks\nprompt: Fill the gaps.\ncontent-direction: target\ntext: %s\n"
                      "- [1] 好\n- [2] 对\n- [3] 吗\n- [4] 是\n- [5] 不\n:::\n"
                      % (sentence % (words[:n], words[:1 + n % 8])) for n in range(1, 31)))


@unittest.skipUnless(TEX, "needs xelatex and kpsewhich")
@unittest.skipUnless(HAVE_PYMUPDF, "PyMuPDF is not installed in this Python")
class BlanksBesidePunctuation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="parseh-pdf-kinsoku-")
        cls.dir = Path(cls.tmp.name)
        cls.runs = {}
        for code in KINSOKU:
            (cls.dir / code).mkdir()
            (cls.dir / code / "doc.md").write_text(kinsoku_doc(code), encoding="utf-8")
            for size in ((11, 20) if EXTSIZES else (11,)):
                out = cls.dir / code / str(size)
                cls.runs[code, size] = (build(cls.dir / code, out, "--size", str(size)), out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_no_line_begins_with_a_closing_mark_or_ends_with_an_opening_one(self):
        for (code, size), (r, out) in sorted(self.runs.items()):
            self.assertEqual(0, r.returncode, (code, size, r.stdout + r.stderr))
            self.assertRegex(r.stdout, r"verify: (\d+)/\1 ")
            lines = lines_with_blanks(out / "main.pdf")
            self.assertGreater(sum(l.count("＿") for l in lines), 30 * 5 - 1, (code, size))
            self.assertEqual([], [(lines[n - 1], l) for n, l in enumerate(lines) if l[:1] in CLOSING],
                             (code, size))
            self.assertEqual([], [l for l in lines if l[-1:] in OPENING], (code, size))


@unittest.skipUnless(TEX, "needs xelatex and kpsewhich")
@unittest.skipUnless(HAVE_PYMUPDF, "PyMuPDF is not installed in this Python")
class ExerciseOnItsPages(unittest.TestCase):
    """An exercise taller than a page goes on over pages at the normal size
    too, one frame a page: a box cannot break, and its foot was cut off."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="parseh-pdf-pages-")
        cls.dir = Path(cls.tmp.name)
        (cls.dir / "images").mkdir()
        shutil.copy(SWATCH, cls.dir / "images" / "swatch.png")
        (cls.dir / "doc.md").write_text(DOC_PICTURES, encoding="utf-8")
        cls.result = build(cls.dir, cls.dir / "out")
        (cls.dir / "headings" / "images").mkdir(parents=True)
        shutil.copy(SWATCH, cls.dir / "headings" / "images" / "swatch.png")
        (cls.dir / "headings" / "doc.md").write_text(DOC_HEADINGS, encoding="utf-8")
        cls.headings = {size: build(cls.dir / "headings", cls.dir / "headings" / str(size),
                                    *(("--size", str(size)) if size != 11 else ()))
                        for size in ((11, 20) if EXTSIZES else (11,))}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_ten_framed_pictures_print_whole_at_the_normal_size(self):
        r, out = self.result, self.dir / "out"
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"verify: (\d+)/\1 ")
        log = (out / "main.log").read_text(encoding="utf-8", errors="replace")
        self.assertEqual([], re.findall(r"Overfull \\vbox.*", log))
        self.assertEqual([], outside_the_body(out / "main.pdf"))
        with pymupdf.open(str(out / "main.pdf")) as d:
            pictures = [(page.number, info["bbox"]) for page in d for info in page.get_image_info()]
            pages = {n for n, _ in pictures}
        self.assertEqual(10, len(pictures))              # every one printed, none off the paper
        self.assertEqual(2, len(pages))                  # over two pages, a frame on each

    def test_an_exercise_stays_with_its_heading_and_on_the_paper(self):
        # a heading cannot be parted from what follows it: a new page for
        # the exercise left it alone at a page's foot, and an exercise that
        # fits a page, but not with its heading, ran off the page's foot
        for size, r in self.headings.items():
            out = self.dir / "headings" / str(size)
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            self.assertRegex(r.stdout, r"verify: (\d+)/\1 ")
            log = (out / "main.log").read_text(encoding="utf-8", errors="replace")
            self.assertEqual([], re.findall(r"Overfull \\vbox.*", log), size)
            self.assertEqual([], outside_the_body(out / "main.pdf", size), size)
            with pymupdf.open(str(out / "main.pdf")) as d:
                pictures = sum(len(page.get_image_info()) for page in d)
                for page in d:
                    lines = sorted((l["bbox"][1], "".join(s["text"] for s in l["spans"]).strip())
                                   for b in page.get_text("dict")["blocks"] for l in b.get("lines", []))
                    lines = [t for _y, t in lines if t and t != str(page.number + 1)]
                    for n, text in enumerate(lines):
                        if re.fullmatch(r"\d+\.\s*Quiz \d", text):
                            # the exercise's label under its heading, on its page
                            self.assertIn("Match translations", lines[n + 1:n + 2], (size, page.number, text))
            self.assertEqual(9 * 6, pictures, size)



class _FakePage:
    """One line of glyphs, as PyMuPDF's rawdict gives them."""

    def __init__(self, glyphs):
        self.glyphs = glyphs

    def get_text(self, _kind):
        return {"blocks": [{"type": 0, "lines": [{"spans": [{"size": 24.0, "chars": [
            {"c": c, "bbox": (x0, 700.0, x1, 720.0), "origin": (x0, 715.0)}
            for c, x0, x1 in self.glyphs]}]}]}]}


class _FakePdf(list):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@unittest.skipUnless(HAVE_PYMUPDF, "PyMuPDF is not installed in this Python")
class VisualOrder(unittest.TestCase):
    # "Kaffee" as XeTeX sets it and PyMuPDF reads it back (German, 20 pt):
    # the ff ligature's second letter is a glyph of no width at the
    # ligature's right edge, a float's last digit right of the next glyph's
    # left edge -- ordered by left edges the line read "Kafefe"
    KAFFEE = [("K", 58.4, 76.39), ("a", 76.39, 88.78), ("f", 88.78, 104.23),
              ("f", 104.2300001, 104.2300001), ("e", 104.23, 116.1), ("e", 116.1, 127.97)]

    def test_a_ligature_is_read_in_order(self):
        from unittest import mock
        import languages
        import verify
        with mock.patch.object(verify.pymupdf, "open", lambda _p: _FakePdf([_FakePage(self.KAFFEE)])):
            self.assertEqual(["Kaffee"], ["".join(v) for v in verify.visual_lines("x.pdf")])
            self.assertEqual("kaffee", verify.column_runs("x.pdf", languages.get("de")))

    def test_devanagari_is_read_in_the_order_it_is_written(self):
        # as a PDF of the Hindi starter reads back: the vowel sign i drawn
        # before its cluster (with the anusvara of हिंदी, or a glyph with no
        # character, in between), र् drawn over the end of its cluster
        import languages
        import verify
        hi = languages.get("hi")
        for drawn, written in (("िकताब", "किताब"), ("िस्थ", "स्थि"), ("िंह͆दी", "ंहि͆दी"),
                               ("कुसर्ी", "कुर्सी"), ("धमर्", "धर्म"), ("कायर्", "कार्य"),
                               ("अच्छा नमस्ते", "अच्छा नमस्ते"),
                               # a reph with a consonant after its cluster
                               ("दशर्क", "दर्शक"), ("कमर्चारी", "कर्मचारी"), ("कायर्क्रम", "कार्यक्रम"),
                               ("अथर्व्यवस्था", "अर्थव्यवस्था"), ("पयर्टक", "पर्यटक"),
                               ("वषर्गांठ", "वर्षगांठ"), ("मागर्दशर्न", "मार्गदर्शन"),
                               ("आशीवार्द", "आशीर्वाद"), ("िनमार्ण", "निर्माण"),
                               # the reph on its own glyph, then a ि of the next cluster
                               ("मयार्िदत", "मर्यादित"), ("धमर्िनरपेक्ष", "धर्मनिरपेक्ष"),
                               # the reph in one glyph with the ि of its own cluster
                               ("धार्\ufdd0म͆क", "धार्मि͆क"), ("शर्\ufdd0ंम͆दा", "शर्ंमि͆दा"),
                               ("मागर्दर्\ufdd0श͆का", "मार्गदर्शि͆का"),
                               # o and au, cut in two by the reph
                               ("धमार्ें", "धर्मों"), ("सवार्ेच्च", "सर्वोच्च"), ("सवार्ैषिध", "सर्वौषधि")):
            self.assertEqual(written, verify._written_order(drawn, hi), drawn)
        # drawn where it is written, ि is moved past the next consonant and र्
        # before the one in front: a PDF set without the shaping reads wrong,
        # as it is
        self.assertEqual("कातबि", verify._written_order("कातिब", hi))
        self.assertEqual("कतिाब", verify._written_order("किताब", hi))
        self.assertEqual("र्दशक", verify._written_order("दर्शक", hi))
        self.assertEqual("अथ", verify._written_order("अर्थ", hi))
        self.assertEqual("अर्थ", verify._written_order("अथर्", hi))
        # and no other script is touched
        self.assertEqual("िकताब", verify._written_order("िकताब", languages.get("fa")))

    # धार्मिक and मर्यादित as Noto Serif Devanagari draws them at 11 pt: both
    # read back with र्ि between two clusters.  In the first the reph and the
    # ि are one glyph, whose ि comes back with no width, and the reph is on
    # मि; in the second each is a glyph of its own, and the reph is on या.
    # Read as characters alone, one of the two was always wrong.
    DHARMIK = [("ध", 122.0, 129.4), ("ा", 129.4, 132.6), ("र", 132.6, 135.8), ("्", 135.8, 135.8),
               ("ि", 135.8, 135.8), ("म", 135.8, 143.1), ("क", 143.1, 152.4)]
    MARYADIT = [("म", 116.6, 123.9), ("य", 123.9, 131.2), ("ा", 131.2, 134.4), ("र", 134.4, 134.4),
                ("्", 134.4, 134.4), ("ि", 134.4, 137.6), ("द", 137.6, 143.7), ("त", 143.7, 150.7)]

    def test_a_reph_drawn_with_its_i_is_told_from_one_before_it(self):
        from unittest import mock
        import languages
        import verify
        hi = languages.get("hi")
        pages = _FakePdf([_FakePage(self.DHARMIK), _FakePage(self.MARYADIT)])
        with mock.patch.object(verify.pymupdf, "open", lambda _p: pages):
            self.assertEqual(["धार्मिक", "मर्यादित"],
                             [verify._written_order("".join(v), hi) for v in verify.visual_lines("x.pdf")])
            self.assertEqual("धारमिक\x00मरयादित", verify.column_runs("x.pdf", hi))


if __name__ == "__main__":
    unittest.main()
