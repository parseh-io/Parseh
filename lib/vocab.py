# SPDX-License-Identifier: GPL-3.0-or-later
"""A book's vocabulary lines read from its sources, chunk by chunk (TO-DO 11.14).

    GET /books/<folder>/<slug>/__vocab     (or <reader>/__vocab)
    -> {"ok": true, "lang": "fa", "chapters": [{"ci", "label", "name"}],
        "chunks": [{"n", "ci", "sub", "text", "voc", "entries": [...]}]}

`n` is the chunk's place in the whole book -- the reader's data-c, the index
SRC and TIMES go by -- so a page can go straight to it; `ci` the chapter's
index (the reader's section data-ch); `sub` the subparagraph's label; `text`
the chunk as the .tex writes it; `voc` its vocabulary line as written; and
`entries` the line cut into words (texparse.voc_entries), each with its
comparison key.  Only chunks with a vocabulary line are listed.

The reader does not need this: it carries every chunk's source (SRC), so its
Vocabulary panel reads the whole book in the page, offline and in an export
alike.  This is the same reading done on the computer, for what reads more
than one book at once -- the search across every book (TO-DO 5.29) is meant to
stand on it.  Read-only: nothing is written anywhere, nothing kept.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import books      # noqa: E402
import texparse as T  # noqa: E402


def book_chunks(book_dir):
    """Every chunk of the book in reading order, with its address:
    yields (n, ci, chapter, sub, chunk)."""
    book = books.Book(book_dir)
    T.set_lang(book.lang)
    chapters = T.parse_book(book.main, book.lang)
    labels = []
    for ch in chapters:
        if ch.label not in labels:
            labels.append(ch.label)
    n = 0
    for ch in chapters:
        ci = labels.index(ch.label)
        for p in ch.paragraphs:
            for s in p.subs:
                for c in s.chunks:
                    yield n, ci, ch, s, c
                    n += 1


def book_vocabulary(book_dir):
    """The answer of GET <book>/__vocab (see the module's docstring)."""
    book = books.Book(book_dir)
    lang = book.lang
    chapters, seen, out = [], set(), []
    for n, ci, ch, s, c in book_chunks(book_dir):
        if ci not in seen:
            seen.add(ci)
            chapters.append({"ci": ci, "label": T.latin_digits(ch.label or ""), "name": ch.name or ""})
        if not (c.voc or "").strip():
            continue
        try:
            entries = T.voc_entries(c.voc, lang)
        except (AssertionError, IndexError, ValueError):
            entries = []            # a line the reader cannot read either: listed with none
        out.append({"n": n, "ci": ci, "sub": s.label, "text": c.fa, "voc": c.voc, "entries": entries})
    return {"ok": True, "lang": lang.code, "chapters": chapters, "chunks": out}
