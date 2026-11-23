#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Turn the annotator's JSON into LaTeX, refusing anything that does not
reproduce the source text exactly once the language's marks are taken back
out (the harakat, for Persian and Arabic; nothing, for Japanese and Italian).

    python3 assemble.py <batch.json> <src_chN.json> <chapter label> <out.tex>
                        [--partial] [--no-open] [--book <dir-or-slug>]

The report goes to stderr and ends with ALL PARAGRAPHS CLEAN or N PROBLEMS;
the exit status is 0 only when clean.  The .tex is written either way, so a
problem can be looked at in what it produced, but a file written on
problems is not to be \\input: a chunk without its kana, say, would build a
pass 1 with no ruby over it.

Which book: --book, else $FRANK_BOOK, else the book the current directory is
in (books.find_book).  The book decides the language, and the language
decides what is stripped for the fidelity check, which digits the labels are
written in, and whether a chunk is a \\ch or -- for a language with a
reading, Japanese -- a \\chr{col}{fa}{kana}{tr}{voc}{en}, whose "kana" every
chunk must then carry.  The chapter label may be given in any language's
digits ("۱", "1"); it is written in the book's.

A chunk that carries a word line under "words" (Japanese, Chinese; lib/
wordline.py) is written \\chrw / \\chw, the same arguments with the line last.
wordline.check is the line's whole validation: what it refuses is a problem,
what it doubts is printed as a warning and counted nowhere.  A chunk of such
a language that arrives with no "words" at all is given lib/words.py's
proposal, where the analyzers are in the running Python: kept only when
check refuses nothing in it, and counted in one line of the report.  A blank
"words" is not filled -- it stays the problem it is.  Without the analyzers
the batch is written, and reported, exactly as it was before any was proposed.
"""
import json, os, re, sys, unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from books import find_book                                     # noqa: E402
import languages                                                # noqa: E402
import texesc                                                   # noqa: E402
import wordline                                                 # noqa: E402
import words                                                    # noqa: E402

ALLOWED = {"dw", "vb", "bw", "pw", "textit", "nobreak", "emph"}
BAD     = re.compile(r"[$%&#_^~]|\\\\")

# The language the module works in: set from the book in main(); the default
# is the toolbox's first language, so an import that never names a book
# behaves as the Persian-only version did.
LANG = languages.get(languages.DEFAULT)
# book.json's "reorders" (a kanbun text), set beside LANG: a reading that
# reorders the words is not compared with them
REORDERS = False


def strip(s):
    return LANG.strip(s)


def norm(s):
    """Whitespace normalised for the fidelity comparison.  Spaced languages
    keep single spaces; Japanese, whose chunks are joined with nothing, loses
    every space -- its source has none to preserve."""
    if LANG.spaced:
        return re.sub(r"\s+", " ", s).strip()
    return re.sub(r"\s+", "", s)


def join_chunks(fas):
    """The chunks put back together with the language's word separator."""
    return (LANG.word_sep or "").join(fas)


def check_para(chunks, source, warnings=None):
    """Return a list of problems for one paragraph.  The word lines' doubts
    are not problems: they go into `warnings`, when a list is given."""
    problems = []
    rebuilt = norm(strip(join_chunks(c.get("fa", "") for c in chunks)))
    want    = norm(strip(source))
    if rebuilt != want:
        # locate the first divergence so the report is actionable
        i = next((i for i, (a, b) in enumerate(zip(rebuilt, want)) if a != b),
                 min(len(rebuilt), len(want)))
        problems.append("TEXT MISMATCH at char %d\n   got:  ...%s...\n   want: ...%s..."
                        % (i, rebuilt[max(0, i-40):i+40], want[max(0, i-40):i+40]))
    for c in chunks:
        fa = c.get("fa", "")
        # en, tr and kana are text, written escaped (chunk_line); only the
        # vocabulary is LaTeX, and only there is a raw special a fault
        if BAD.search(c.get("voc", "") or ""):
            problems.append("unescaped TeX char in voc of %r" % fa)
        voc = c.get("voc", "")
        for m in re.finditer(r"\\([a-zA-Z]+)", voc):
            if m.group(1) not in ALLOWED:
                problems.append("macro \\%s not allowed, in %r" % (m.group(1), fa))
        if voc.count("{") != voc.count("}"):
            problems.append("unbalanced braces in voc of %r" % fa)
        tr = c.get("tr", "") or ""
        if strip(tr) != tr:
            problems.append("%s leaked into tr of %r"
                            % ("harakat" if LANG.script == "arabic" else "marks", fa))
        # a reading language sets the kana over the chunk in pass 1 and as a
        # line of the gloss; a chunk without one cannot be written as \chr
        if LANG.reading and not (c.get("kana", "") or "").strip():
            problems.append("no kana for %r -- %s needs the reading of every chunk"
                            % (fa, LANG.name))
        # the word line: refused, it is a line the PDF cannot set; doubted,
        # it is a reading somebody should look at, and the batch still builds
        if "words" in c:
            words = c["words"]
            if words is None or (isinstance(words, str) and not words.strip()):
                problems.append("blank words for %r -- a chunk without words "
                                "carries no \"words\" key" % fa)
            else:
                reading = (c.get("kana", "") or "") if LANG.reading else tr
                bad, doubts = wordline.check(fa, words, LANG, reading=reading,
                                             reorders=REORDERS, door=wordline.BOOK)
                problems.extend("words of %r: %s" % (fa, e) for e in bad)
                if warnings is not None:
                    warnings.extend("words of %r: %s" % (fa, w) for w in doubts)
    return problems

def propose_words(chunks):
    """Give lib/words.py's word line to every chunk that arrived with no
    "words" key, and return how many were given one.  The caller asks only
    for a language divided into words whose analyzers are in this Python.

    A line the model wrote is never replaced, and a blank one is never
    filled: check_para judges both as it always has.  A proposal is kept only
    when check refuses nothing in it -- a batch must not fail on a line
    nobody wrote -- and what check doubts in it is printed like any other
    doubt, which is how a dictionary's reading that the chunk's own kana or
    tr contradicts gets looked at."""
    n = 0
    for c in chunks:
        if "words" in c:
            continue
        fa = c.get("fa", "")
        reading = c.get("kana", "") if LANG.reading else c.get("tr", "")
        # the model's own kana (or pinyin) for the chunk reads its words
        line = words.line(fa, LANG.code, reading if isinstance(reading, str) else "")
        if line and not wordline.check(fa, line, LANG, reading=reading or "",
                                       reorders=REORDERS, door=wordline.BOOK)[0]:
            c["words"] = line
            n += 1
    return n

def fix_diphthongs(chunks):
    """The harakat in this edition are pedagogical: they must agree with the
    romanisation beside them, since that is the whole reason they are there.
    /ey/ therefore takes a KASRA before the ya -- kasra is the book's e, and a
    fatha there would tell the reader to say paydā where it prints peydā.
    Only a chunk whose tr actually shows the diphthong is touched, so the
    negative prefix in na-yoftāde keeps its fatha.  Swapping the mark never
    changes the stripped text, so fidelity is unaffected.

    This is the Persian edition's convention (NOTES section 4) and runs for
    Persian alone: Arabic keeps whatever pointing its text has."""
    if LANG.code != "fa":
        return 0
    n = 0
    for c in chunks:
        if "ey" in c.get("tr", "") and "َی" in c["fa"]:
            c["fa"] = c["fa"].replace("َی", "ِی"); n += 1
    return n

def digits(n):
    """A number, or a label given in any language's digits, written in the
    book's digits (Persian ۰-۹, Arabic ٠-٩, Latin for the others)."""
    return LANG.to_native_digits(languages.any_to_latin_digits(str(n)))

def esc(s):
    return s.replace("&", r"\&").replace("%", r"\%").replace("#", r"\#")


def incipit(para, words=6, chars=12):
    """The opening of the paragraph's text -- the fa of the first
    subparagraph's chunks, which is exactly what pass 1 sets.  It is what
    names the paragraph in the PDF outline and in the printed contents.  Six
    words for a language that has them; a language without a word separator
    (Japanese) gets its first twelve characters instead."""
    chunks = para["sentences"][0]["chunks"]
    text = join_chunks(c["fa"] for c in chunks)
    if LANG.spaced:
        return texesc.escape(" ".join(text.split()[:words]))
    return texesc.escape(re.sub(r"\s+", "", text)[:chars])

def chunk_line(c):
    """One chunk as LaTeX.  The first argument is the highlight colour, left
    empty here: colouring is done by hand afterwards, never by the pipeline.
    \\chr is a distinct macro, not a sixth argument of \\ch, so every parser
    knows the arity from the name (docs/languages.md section 3).  So are
    \\chrw and \\chw, for a chunk with a word line: the same arguments, and
    the line after them, last."""
    voc = c.get("voc", "").strip()
    # Whitespace in a word line only parts words, and inside a reading is
    # collapsed to one space when the line is read, so a line an annotator
    # broke over two lines means exactly what it means on one -- and on one
    # it keeps the chunk on its own line of the .tex, which every reader of
    # the file walks by.
    words = c.get("words")
    words = " ".join(words.split()) if isinstance(words, str) else ""
    # the text fields are text: "50%" is written 50\% (lib/texesc.py)
    c = dict(c, **{f: texesc.escape(c.get(f, "")) for f in texesc.TEXT_FIELDS})
    if LANG.reading:
        args = "{}{%s}{%s}{%s}{%s}{%s}" % (c["fa"], c.get("kana", ""), c.get("tr", ""),
                                           voc, c["en"])
        return "\\chrw%s{%s}" % (args, words) if words else "\\chr" + args
    args = "{}{%s}{%s}{%s}{%s}" % (c["fa"], c.get("tr", ""), voc, c["en"])
    return "\\chw%s{%s}" % (args, words) if words else "\\ch" + args

def render(paragraphs, sources, chapter_label, close_chapter=True, open_chapter=True, first_index=0):
    chapter_label = digits(chapter_label)
    out = ([r"\chapopen{%s}" % chapter_label, ""] if open_chapter else [])
    for n, (para, src) in enumerate(zip(paragraphs, sources)):
        # paragraph.subparagraph, so any sentence can be named exactly
        pn = digits(first_index + n + 1)
        # The reader navigates by the PARAGRAPH, so the anchor, the outline
        # bookmark and the contents line are emitted once, here, before the
        # first subparagraph.  \parstart sets nothing visible.
        out.append(r"\parstart{%s.%s}{%s}" % (chapter_label, pn, incipit(para)))
        for k, sent in enumerate(para["sentences"]):
            out.append(r"\parnum{%s.%s}" % (pn, digits(k + 1)))
            out.append(r"\begin{frank}")
            for c in sent["chunks"]:
                out.append(chunk_line(c))
            out.append(r"\end{frank}")
            out.append("")
        is_last = (n == len(paragraphs) - 1)
        out.append(r"\chapend" if (is_last and close_chapter) else r"\parend")
        out.append("")
    return "\n".join(out)

if __name__ == "__main__":
    # --partial : the chapter continues in a later batch, so close with \parend
    # --no-open : this batch is a continuation, so emit no \chapopen
    # --book X  : the book (else $FRANK_BOOK, else the current directory's)
    args, flags, book = sys.argv[1:], [], None
    argv = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--book" and i + 1 < len(args):
            book = args[i + 1]; i += 2; continue
        if a.startswith("--book="):
            book = a.split("=", 1)[1]
        elif a.startswith("--"):
            flags.append(a)
        else:
            argv.append(a)
        i += 1
    if len(argv) != 4:
        sys.exit("usage: assemble.py <batch.json> <src_chN.json> <chapter label> <out.tex> "
                 "[--partial] [--no-open] [--book <dir-or-slug>]")
    the_book = find_book(book or os.environ.get("FRANK_BOOK") or None)
    LANG, REORDERS = the_book.lang, the_book.reorders
    blob    = json.load(open(argv[0], encoding="utf-8"))
    allsrc  = json.load(open(argv[1], encoding="utf-8"))
    label   = argv[2]
    entries = sorted(blob["paragraphs"], key=lambda x: x["idx"])
    idxs    = [e["idx"] for e in entries]
    if idxs != list(range(idxs[0], idxs[0] + len(idxs))):
        sys.exit("paragraphs are not contiguous: %s" % idxs)
    paras   = [e["ann"] for e in entries]
    sources = [allsrc[i] for i in idxs]
    print("paragraphs %d..%d of %d  [%s]" % (idxs[0], idxs[-1], len(allsrc), LANG.name),
          file=sys.stderr)
    # the lines the model left out are proposed only where they can be; any
    # other language, or this one without its analyzers, is asked nothing and
    # reported exactly as before
    proposing = LANG.words and words.available(LANG.code)
    bad = proposed = total = 0
    for i, (p, s) in enumerate(zip(paras, sources)):
        chunks = [c for sent in p["sentences"] for c in sent["chunks"]]
        nfix = fix_diphthongs(chunks)
        if proposing:
            proposed += propose_words(chunks)
            total += len(chunks)
        doubts = []
        probs = check_para(chunks, s, doubts)
        n_sent = len(p["sentences"])
        print("P%-3d %3d chunks in %2d sentences  %s%s%s"
              % (i, len(chunks), n_sent,
                 "OK" if not probs else "*** %d PROBLEM(S)" % len(probs),
                 "  (%d diphthong fix)" % nfix if nfix else "",
                 "  (%d warning(s))" % len(doubts) if doubts else ""),
              file=sys.stderr)
        for pr in probs:
            bad += 1
            print("      " + pr, file=sys.stderr)
        for w in doubts:
            print("      warn  " + w, file=sys.stderr)
    if proposing:
        print("words proposed for %d of %d chunks" % (proposed, total), file=sys.stderr)
    print("\n%s" % ("ALL PARAGRAPHS CLEAN" if not bad else "%d PROBLEMS" % bad), file=sys.stderr)
    open(argv[3], "w", encoding="utf-8").write(
        render(paras, sources, label,
               close_chapter="--partial" not in flags,
               open_chapter="--no-open" not in flags,
               first_index=idxs[0]))
    # the file is written for inspection, but a caller that only reads the
    # exit status (the recipe's scripts, a Makefile) must not take a batch
    # with problems for a clean one
    if bad:
        sys.exit(1)
