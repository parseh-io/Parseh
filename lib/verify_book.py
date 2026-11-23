#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prove every built paragraph still reproduces its source.

assemble.py checks fidelity per batch, against the annotation JSON.  For the
older batches that JSON is gone, so nothing was left that could re-check them.
This walks the built .tex instead: it groups the \\ch / \\chr / \\chp chunks (and
\\chw / \\chrw, which only add a word line) by
\\parnum, strips the language's marks (the harakat, for Persian and Arabic;
nothing for Japanese and Italian), and compares against source/paras/.

A book may keep a characters.tex or a chapters.tex beside its chapters, and
the glob is ch*.tex: such a file is named and skipped rather than checked,
because source/paras/ch<N>_p<NN>.txt is named after a chapter number the file
has not got (chapter_of).  It is a note, never a fault.

    python3 verify_book.py [--book <dir-or-slug>]

Which book: --book, else $FRANK_BOOK, else the book the current directory is
in, else the first book under books/ -- so it runs unchanged in a folder made
for a new edition.  Labels are read in any language's digits.
"""
import glob
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from books import find_book, all_books                          # noqa: E402
import languages                                                # noqa: E402
import reading                                                  # noqa: E402
import texesc                                                   # noqa: E402

# \ch{col}{fa}..., \chr{col}{fa}{kana}..., \chp{col}{fa}, and the two that carry
# a word line last, \chw{col}{fa}... and \chrw{col}{fa}...: the text is the
# SECOND argument of all five.  The longer names first -- a name left out is a
# chunk this never sees, and a paragraph that mismatches for no visible reason
# The text field is read escape by escape (texesc.FIELD), so a \} or a
# \textbackslash{} in it does not end it early, and undone before it is
# compared with the source, which holds the text as typed (TO-DO §6.6).
CHUNK_RE = re.compile(r"\\ch(?:rw|w|r|p)?\{(.*?)\}\{" + texesc.FIELD + r"\}")
PARNUM_RE = re.compile(r"\\parnum\{([%s]+)\.[%s]+\}"
                       % (languages.digit_class(), languages.digit_class()))


def which_book(where=None):
    try:
        return find_book(where or os.environ.get("FRANK_BOOK") or None)
    except SystemExit:
        if where:
            raise
        bs = all_books()
        if not bs:
            raise
        return bs[0]


def chapter_of(path):
    """The chapter a file belongs to, from its name -- ch1.tex and ch1b.tex are
    both chapter 1 -- or None when the name carries no number.

    The glob below is ch*.tex and a book may keep a characters.tex or a
    chapters.tex beside its chapters: build.sh takes EVERY top-level .tex but
    frankdraft.tex as part of the book (cat_book_tex), and bundle.py carries
    what build.sh builds.  That definition and this one cannot be made into
    one, because the comparison below is against source/paras/ch<N>_p<NN>.txt
    and that name is MADE of the number: a file whose name has none names no
    source paragraph, so there is nothing to hold it against.  Such a file is
    reported and skipped -- an unguarded .group() here reached whoever
    uploaded the book as "AttributeError: 'NoneType' object has no attribute".

    The name is the only authority, deliberately.  texwrite.py's _chapter_no
    reads it exactly this way, and the two must agree: were this one to
    believe \\chapopen as well (as inject_parstart.py does), a chunk the
    reader's editor let through as unchecked would be one this refused the
    whole book for on upload.
    """
    m = re.match(r"ch(\d+)", os.path.basename(path))
    return int(m.group(1)) if m else None


def main(where=None):
    book = which_book(where)
    L = book.lang
    strip = L.strip
    if L.spaced:
        norm = lambda s: re.sub(r"\s+", " ", s).strip()
        sep = " "
    else:
        # no word separator: the chunks are joined with nothing and every
        # space is dropped from both sides, since the source has none to keep
        norm = lambda s: re.sub(r"\s+", "", s)
        sep = ""

    # paragraph (chapter, n) -> the fa of every chunk under it, in order
    built = {}
    aside = 0                    # ch*.tex that are not chapters, counted below
    for f in sorted(glob.glob(os.path.join(book.dir, "ch*.tex"))):
        ch = chapter_of(f)
        if ch is None:
            print("  NOT A CHAPTER %s: no chapter number in the name, so no "
                  "source/paras/ch<N>_p<NN>.txt names it"
                  % os.path.basename(f))
            aside += 1
            continue
        cur = None
        for line in io.open(f, encoding="utf-8"):
            # A line is matched from its first non-blank character, not from
            # column 0: texwrite and texparse (so the reader and the PDF) find
            # a chunk wherever it stands on its line, and a chunk the reader's
            # editor divides is written as two lines at the chunk's own
            # indent -- so a chapter that indents its chunks inside frank was
            # one whose paragraphs this saw as empty, and called mismatched,
            # and one that indented its \parnum as well was one it saw no
            # paragraph of at all, and passed.  A comment stays a comment: an
            # indented % line still opens with the %, and matches neither
            # pattern.
            line = line.lstrip()
            m = PARNUM_RE.match(line)
            if m:
                cur = (ch, int(languages.any_to_latin_digits(m.group(1))))
                built.setdefault(cur, [])
                continue
            m = CHUNK_RE.match(line)
            if m and cur:
                built[cur].append(texesc.unescape(m.group(2)))

    bad = missing = free = 0
    # read once, not once per paragraph: this runs on every bundle upload
    # (lib/bundle.py's check), where somebody is waiting for the answer
    freed = set(reading.load(book.dir)["free"])
    for (ch, n), fas in sorted(built.items()):
        # A PARAGRAPH SOMEBODY HAS TAKEN CHARGE OF (lib/reading.py).  The
        # reader lets an edit depart from the source only for a paragraph
        # marked here, and this is the other half of that promise: what the
        # editor allowed, the checker does not then call a fault.  It is not
        # counted against the book, and it is named, so a book full of them
        # says so plainly instead of looking clean.
        if reading.key(ch, n) in freed:
            print("  NOT CHECKED chapter %d paragraph %d: marked in reading.json "
                  "as departing from its source" % (ch, n))
            free += 1
            continue
        src_path = os.path.join(book.dir, "source", "paras", "ch%d_p%02d.txt" % (ch, n - 1))
        if not os.path.exists(src_path):
            print("  NO SOURCE for chapter %d paragraph %d (%s)" % (ch, n, os.path.basename(src_path)))
            missing += 1
            continue
        want = norm(strip(io.open(src_path, encoding="utf-8").read().strip()))
        got  = norm(strip(sep.join(fas)))
        if got != want:
            bad += 1
            i = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b),
                     min(len(got), len(want)))
            print("  MISMATCH chapter %d paragraph %d at char %d of %d" % (ch, n, i, len(want)))
            print("     built : ...%s..." % got[max(0, i - 50):i + 50])
            print("     source: ...%s..." % want[max(0, i - 50):i + 50])

    # `aside` is not counted as a fault: a .tex that is not a chapter has
    # nothing to have drifted from, and refusing one would refuse a book
    # build.sh builds happily
    print("\n%s [%s]: %d paragraphs built, %d reproduce their source exactly, %d mismatched, %d without a source%s%s"
          % (book.rel_from_books(), L.name, len(built),
             len(built) - bad - missing - free, bad, missing,
             ", %d marked as departing from it" % free if free else "",
             ", %d .tex beside the chapters" % aside if aside else ""))
    return 1 if (bad or missing) else 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default=None, help="book directory, slug or <folder>/<slug>")
    a = ap.parse_args()
    sys.exit(main(a.book))
