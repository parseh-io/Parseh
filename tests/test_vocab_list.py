# SPDX-License-Identifier: GPL-3.0-or-later
"""The vocabulary list (TO-DO 11.14) below the browser: lib/vocab.py, the
computer's reading of a book's vocabulary lines with each chunk's address, and
ParsehVocab.gather in lib/vocab.js, which makes the list of words out of them.

    python3 -m unittest tests.test_vocab_list

The cutting of a line into entries is tests/test_vocline.py's (Entries); the
list drawn and driven is tests/vocab_list.mjs's.
"""
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
sys.path.insert(0, str(ROOT / "tests"))
import languages   # noqa: E402
import vocab       # noqa: E402

DENO = shutil.which("deno") or os.path.expanduser("~/miniconda3/envs/ilya-frank/bin/deno")


def page_array(html, name):
    """A `const NAME=[...]` the reader carries, read back as JSON."""
    m = re.search(r"const %s=(\[.*?\]);" % name, html, re.S)
    return json.loads(m.group(1))


class Addresses(unittest.TestCase):
    """GET <book>/__vocab says where each chunk is the way the reader does:
    `n` is its data-c (SRC and TIMES are indexed by it) and `ci` its chapter."""

    @classmethod
    def setUpClass(cls):
        import later_harness
        import mobile_harness
        cls.tmp = Path(tempfile.mkdtemp(prefix="parseh-vocab-"))
        b = cls.tmp / "multi-en"
        shutil.copytree(ROOT / "tests/fixtures/books/english/mini-en", b,
                        ignore=shutil.ignore_patterns("reader", "source", "ch1.tex", "audio"))
        main = (b / "main.tex").read_text(encoding="utf-8")
        (b / "main.tex").write_text(main.replace("\\input{ch1.tex}\n", "".join(
            "\\input{ch%d.tex}\n" % k for k in (1, 2, 3))), encoding="utf-8")
        for k in (1, 2, 3):
            (b / ("ch%d.tex" % k)).write_text(later_harness.chapter(later_harness.EN_ROWS, str(k), paras=3),
                                             encoding="utf-8")
        mobile_harness.built_reader(b)
        cls.book = b
        cls.html = (b / "reader" / "index.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_every_chunk_is_where_the_reader_has_it(self):
        src, times = page_array(self.html, "SRC"), page_array(self.html, "TIMES")
        got = vocab.book_vocabulary(str(self.book))
        self.assertTrue(got["ok"])
        self.assertEqual(got["lang"], "en")
        self.assertEqual([c["ci"] for c in got["chapters"]], [0, 1, 2])
        listed = {c["n"] for c in got["chunks"]}
        self.assertEqual(listed, {n for n, s in enumerate(src) if s[4].strip()}, "every chunk with a line, none other")
        for c in got["chunks"]:
            with self.subTest(n=c["n"]):
                self.assertEqual(c["voc"], src[c["n"]][4])
                self.assertEqual(c["text"], src[c["n"]][1])
                self.assertEqual(c["ci"], times[c["n"]][3])
        self.assertEqual(sorted({c["ci"] for c in got["chunks"]}), [0, 1, 2], "chapters fetched later are read too")
        self.assertEqual(got["chunks"][0]["entries"][0]["key"], "old")

    def test_it_reads_and_writes_nothing_else(self):
        before = sorted((p.name, p.stat().st_mtime_ns) for p in self.book.rglob("*"))
        vocab.book_vocabulary(str(self.book))
        self.assertEqual(sorted((p.name, p.stat().st_mtime_ns) for p in self.book.rglob("*")), before)


@unittest.skipUnless(os.path.exists(DENO), "no deno")
class Gather(unittest.TestCase):
    """ParsehVocab.gather: one word per key, its meanings once each, every place."""

    def gather(self, code, chunks, order=None):
        js = """
globalThis.window = globalThis;
globalThis.document = {querySelector: () => null, createElement: () => ({}), head: null, documentElement: {appendChild() {}}};
globalThis.location = {protocol: 'file:'};
await import(%s);
await import(%s);
const L = %s, words = ParsehVocab.gather(%s, L);
const out = {words};
for (const how of ['seen', 'az', 'freq']) out[how] = words.slice().sort(ParsehVocab.sorter(L, how)).map(w => w.word);
console.log(JSON.stringify(out));
""" % (json.dumps("file://" + str(ROOT / "lib" / "vocline.js")), json.dumps("file://" + str(ROOT / "lib" / "vocab.js")),
            json.dumps(languages.get(code).as_json()), json.dumps(chunks, ensure_ascii=False))
        with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as f:
            f.write(js)
        try:
            r = subprocess.run([DENO, "run", "--quiet", "--allow-read", f.name], capture_output=True, text=True, timeout=120)
        finally:
            os.unlink(f.name)
        if r.returncode:
            raise AssertionError("deno failed: " + (r.stderr or r.stdout)[-800:])
        return json.loads(r.stdout.strip().split("\n")[-1])

    def test_one_word_written_two_ways_is_one_row(self):
        got = self.gather("fa", [
            {"at": 0, "voc": r"\dw{كتاب}{ketāb} book; \vb{دیدن}{didan}{بین}{bin}{دید}{did}{to see}"},
            {"at": 1, "voc": r"\dw{کِتاب}{ketāb} book; \vb{دیدن}{didan}{بین}{bin}{دید}{did}{to meet}"},
            {"at": 2, "voc": r"\pw{دیدن} To see; \dw{کتاب}{} a book"},
            {"at": 2, "voc": r"\dw{کتاب}{ketāb} book"},
            {"at": 3, "voc": "a plain line: nothing in it is a word"},
            {"at": 4, "voc": r"\dw{broken"},
        ])
        w = {x["key"]: x for x in got["words"]}
        self.assertEqual(list(w), ["کتاب", "دیدن"])
        self.assertEqual(w["کتاب"]["count"], 4)
        self.assertEqual(w["کتاب"]["meanings"], ["book", "a book"], "each meaning once")
        self.assertEqual(w["کتاب"]["at"], [0, 1, 2], "each place once, in order")
        self.assertEqual(w["کتاب"]["word"], "كتاب", "listed as it was first written")
        self.assertEqual(w["دیدن"]["meanings"], ["to see", "to meet"], "a meaning is the same written in another case")
        self.assertEqual(w["دیدن"]["kind"], "vb", "a verb keeps its stems where a later \\pw has none")
        self.assertEqual(w["دیدن"]["count"], 3)

    def test_a_word_first_met_bare_takes_its_fuller_form(self):
        got = self.gather("it", [{"at": 0, "voc": r"\pw{essere} to be"},
                                 {"at": 1, "voc": r"\vb{essere}{èssere}{sono}{sóno}{stato}{stàto}{to be}"}])
        self.assertEqual([(x["kind"], x["rom"], x["meanings"]) for x in got["words"]], [("vb", "èssere", ["to be"])])

    def test_the_orders(self):
        lines = [{"at": 0, "voc": r"\dw{سال}{sāl} year; \dw{جا}{jā} place"},
                 {"at": 1, "voc": r"\dw{تر}{tar} wet; \dw{جا}{jā} place"}]
        got = self.gather("fa", lines)
        self.assertEqual(got["seen"], ["سال", "جا", "تر"])
        self.assertEqual(got["az"], ["تر", "جا", "سال"], "A–Z in the language's own alphabet")
        self.assertEqual(got["freq"], ["جا", "سال", "تر"], "most frequent first, then as they come")
        ja = self.gather("ja", [{"at": 0, "voc": r"\dw{山}{yama} mountain; \dw{川}{kawa} river; \dw{秋}{aki} autumn"}])
        self.assertEqual(ja["az"], ["秋", "川", "山"], "Japanese A–Z by the reading the line gives")
        tr = self.gather("tr", [{"at": 0, "voc": r"\dw{ılık}{} warm; \dw{iyi}{} good; \dw{çok}{} very; \dw{cam}{} glass"}])
        self.assertEqual(tr["az"], ["cam", "çok", "ılık", "iyi"], "Turkish's own order: c ç ı i")


if __name__ == "__main__":
    unittest.main()
