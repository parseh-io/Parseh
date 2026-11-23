#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
r"""A chapter's name, and the sections inside it -- written into the .tex.

Two structural marks, both optional, both kept in the book's own files rather
than in a sidecar beside them:

    \chapname{The Dam}      right after \chapopen{1}: what this chapter is
                            called.  A chapter without one is every chapter
                            written before names existed, and the PDF and the
                            reader both fall back to its number alone.

    \secmark{The Spillway}  on its own line BETWEEN two paragraphs: a section
                            opens at the paragraph that follows it.

WHY THE .TEX AND NOT A SIDECAR.  Every top-level .tex travels verbatim in a
bundle of the book -- lib/bundle.py's `_owned` ends "every .tex but
frankdraft.tex", and only the `% @par` timing comments are ever stripped from
one.  A new JSON file beside book.json would have to be named in bundle.SHAPE
or it is dropped on the way out AND on the way in; a mark written into the
chapter is carried by the rule that is already there.  So a book downloaded
and uploaded again keeps its sections, which is the whole point of putting
them where the text is.

WHAT A SECTION IS NOT.  It has no number of its own and it changes no other
number.  Paragraph numbers come from \parnum and from nothing else -- no tool
in this project counts lines, blank lines or \parend to derive one -- so a
mark inserted between two paragraphs cannot move any of them.  This file
proves that rather than trusting it: every write re-reads the file and
refuses unless every paragraph number, every subparagraph label and every
chunk is exactly what it was (`_proved`).

WHERE THE MARK MAY STAND.  Above \parstart, which is above \parnum, which is
above the `% @par` comment that carries a subparagraph's times.  A line put
BETWEEN `% @par` and its \begin{frank} would be flushed into the wrong slot
by tex2html.load_times and that subparagraph would silently lose its timings,
so this file inserts above \parstart and nowhere else.

A paragraph is named "<chapter>:<paragraph>", exactly as lib/reading.py names
one: the chapter number a chapter file carries in its NAME (ch1.tex and
ch1b.tex are both chapter 1), and the 1-based number of its \parnum.  The
number comes from texwrite.book_chapters, which is where that rule already
lives -- lib/tex2html.chapter_no, lib/verify_book.chapter_of and
texwrite._chapter_no are three readings of one rule and this is not a fourth.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import texesc  # noqa: E402
import texparse as T  # noqa: E402
import texwrite  # noqa: E402

# the refusals travel as texwrite's, so a caller that already catches those
# catches these too and says the same thing to whoever pressed the button
Refused = texwrite.Refused

CHAPNAME = "chapname"
SECMARK = "secmark"

# A title is typed into a box in the reader, so it is TEXT and not LaTeX: what
# is typed is what is printed.  The characters TeX would otherwise read as
# instructions -- a stray & or % in "Water & Waste" or "100% clear" would break
# the build or silently eat the rest of the line -- are escaped, by the one
# table a chunk's text is escaped with too (lib/texesc.py).


def escaped(title):
    """A typed title as it is written into the .tex."""
    return texesc.escape(title)


def plain(tex):
    r"""The inverse: what the box should show again, and what the reader
    prints -- the exact undoing of `escaped`, read in one pass so that
    \textbackslash{} is never mistaken for a backslash followed by text.

    A title written by hand in a .tex may hold a macro this cannot undo --
    \emph{x} say.  It is left as it stands rather than guessed at: the parser
    reads such a group whole (texparse reads \secmark's one argument with
    read_group), so nothing is lost, and what the box shows is what the file
    says."""
    return texesc.unescape(tex)


def check_title(title):
    """A title the GUI may write, or a refusal saying why not."""
    t = str(title or "").strip()
    if not t:
        raise Refused("a name cannot be empty -- delete it instead")
    if len(t) > 200:
        raise Refused("a name is at most 200 characters; this one is %d" % len(t))
    # a blank line inside an argument is \par, and LaTeX stops with
    # "Paragraph ended before \secmark was complete"
    if re.search(r"\n[ \t]*\n", t) or "\n" in t or "\r" in t:
        raise Refused("a name is one line")
    bad = [c for c in t if ord(c) < 32 or ord(c) == 127]
    if bad:
        raise Refused("a name cannot hold a control character (%r)" % bad[0])
    return t


# --- the files ---------------------------------------------------------------
def _read(path):
    """The file exactly as it sits on disk, line endings included
    (texwrite._read's reason, and its newline='')."""
    with io.open(path, encoding="utf-8", newline="") as f:
        return f.read()


def _write(path, text):
    """Beside and renamed over, so a chapter is never left half-written."""
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def _eol(text):
    """The line ending this file already uses, so an inserted line matches."""
    return "\r\n" if "\r\n" in text else "\n"


def _shape(path):
    """What a chapter holds, as the pair of lists a write must not change."""
    ch = T.parse_chapter(path)
    return ([p.no for p in ch.paragraphs],
            [s.label for s in ch.subs],
            [c.fa for c in T.all_chunks([ch])])


def _proved(path, before, want_name, want_secs, where):
    """Read the file back and refuse unless the edit did exactly one thing.

    `before` is `_shape` from before the write.  The text is compared as the
    parser sees it -- every paragraph number, every subparagraph label and
    every chunk -- because the guarantee that a structural mark cannot move a
    paragraph is worth more than the mark.  _proved is texwrite's word for
    this and this is the same idea applied to a whole chapter.
    """
    after = _shape(path)
    for got, was, what in zip(after, before,
                              ("the paragraph numbers", "the subparagraph labels",
                               "the chunks")):
        if got != was:
            raise Refused("%s: refusing -- %s changed (%d -> %d). Nothing was "
                          "kept." % (where, what, len(was), len(got)))
    ch = T.parse_chapter(path)
    if (ch.name or None) != (want_name or None):
        raise Refused("%s: refusing -- the chapter's name came back as %r, not %r"
                      % (where, ch.name, want_name))
    got_secs = {p.no: p.section for p in ch.paragraphs if p.section}
    if got_secs != want_secs:
        raise Refused("%s: refusing -- the sections came back as %r, not %r"
                      % (where, got_secs, want_secs))


def _chapter_files(book, chapter):
    """Every file of this chapter, in reading order.  A chapter written across
    ch1.tex and ch1b.tex is two files wearing one number."""
    want = int(chapter)
    out = [c for c in texwrite.book_chapters(book) if c.get("chapter") == want]
    if not out:
        raise Refused("there is no chapter %d in this book" % want)
    return out


def _file_with_para(book, chapter, para):
    """The chapter file that holds this paragraph, and its parse."""
    para = int(para)
    for c in _chapter_files(book, chapter):
        ch = T.parse_chapter(c["path"])
        if any(p.no == para for p in ch.paragraphs):
            return c, ch
    raise Refused("chapter %d has no paragraph %d" % (int(chapter), para))


# --- reading the structure ---------------------------------------------------
def read(book):
    """The book's chapters, their names and their sections.

        [{"chapter": 1, "file": "ch1.tex", "name": "The Dam",
          "paragraphs": [1, 2, 3],
          "sections": [{"para": 2, "title": "The Spillway"}]}]

    Names and titles come back PLAIN -- what the box should show -- not as the
    .tex spells them.
    """
    out = []
    for c in texwrite.book_chapters(book):
        ch = T.parse_chapter(c["path"])
        out.append({
            "chapter": c.get("chapter"), "file": c["file"],
            "name": plain(ch.name) if ch.name else "",
            "paragraphs": [p.no for p in ch.paragraphs],
            "sections": [{"para": p.no, "title": plain(p.section)}
                         for p in ch.paragraphs if p.section],
        })
    return out


# --- the anchors -------------------------------------------------------------
def _parstart_at(text, chapter, para):
    r"""Where \parstart{<chapter>.<paragraph>} begins, or None.

    Its label is <chapter>.<paragraph> -- \parnum's is
    <paragraph>.<subparagraph>, the other pair of numbers -- and it is read in
    the book's own digits, so ۱.۲ and 1.2 both answer.
    """
    want = "%d.%d" % (int(chapter), int(para))
    for m in re.finditer(r"\\parstart\s*\{", text):
        try:
            lab, _ = T.read_group(text, m.end() - 1)
        except ValueError:
            continue
        if T.latin_digits(lab.strip()) == want:
            return m.start()
    return None


def _parnum_at(text, para):
    r"""Where the first \parnum of this paragraph begins, or None.  The
    fallback for a chapter written before \parstart existed: still above the
    `% @par` comment, which is what matters."""
    for m in re.finditer(r"\\parnum\s*\{", text):
        try:
            lab, _ = T.read_group(text, m.end() - 1)
        except ValueError:
            continue
        got = T.latin_digits(lab.strip()).split(".")
        if got and got[0] == str(int(para)):
            return m.start()
    return None


def _open_of(text, pos):
    """The start of the line `pos` is on."""
    nl = text.rfind("\n", 0, pos)
    return 0 if nl < 0 else nl + 1


def _secmark_before(text, pos):
    r"""The (start, end) of a \secmark standing above `pos` with only blank
    lines and whole-line comments between, or None.  end is past its newline,
    so removing the span takes the line away entirely."""
    head = text[:pos]
    for m in re.finditer(r"\\secmark\s*\{", head):
        try:
            _, j = T.read_group(head, m.end() - 1)
        except ValueError:
            continue
        between = head[j:]
        if re.fullmatch(r"[\s]*(?:%[^\n]*\n[\s]*)*", between):
            start = _open_of(text, m.start())
            end = j
            while end < len(text) and text[end] in " \t":
                end += 1
            if text.startswith("\r\n", end):
                end += 2
            elif end < len(text) and text[end] == "\n":
                end += 1
            # and the blank line this file's own inserts leave behind
            while text.startswith(("\r\n", "\n"), end):
                end += 2 if text.startswith("\r\n", end) else 1
            return start, end
    return None


# --- writing -----------------------------------------------------------------
def set_chapter_name(book, chapter, title):
    r"""Name a chapter, rename it, or take its name away (title empty).

    The name goes immediately after \chapopen{N}, which is where \chapname is
    defined to be read.
    """
    files = _chapter_files(book, chapter)
    # the name belongs to the file that OPENS the chapter: the one carrying
    # \chapopen.  A continuation file has none and must not grow one.
    target = None
    for c in files:
        if re.search(r"\\chapopen\s*\{", _read(c["path"])):
            target = c
            break
    if target is None:
        raise Refused("chapter %s has no \\chapopen to hang a name on"
                      % chapter)
    path = target["path"]
    text = _read(path)
    before = _shape(path)
    where = "%s chapter %s" % (target["file"], chapter)
    eol = _eol(text)

    m = re.search(r"\\chapname\s*\{", text)
    if m is not None:
        _, j = T.read_group(text, m.end() - 1)
        start, end = _open_of(text, m.start()), j
        while end < len(text) and text[end] in " \t":
            end += 1
        if text.startswith("\r\n", end):
            end += 2
        elif end < len(text) and text[end] == "\n":
            end += 1
        text = text[:start] + text[end:]

    want = ""
    if str(title or "").strip():
        want = escaped(check_title(title))
        mo = re.search(r"\\chapopen\s*\{", text)
        _, j = T.read_group(text, mo.end() - 1)
        while j < len(text) and text[j] in " \t":
            j += 1
        if text.startswith("\r\n", j):
            j += 2
        elif j < len(text) and text[j] == "\n":
            j += 1
        text = text[:j] + "\\%s{%s}%s" % (CHAPNAME, want, eol) + text[j:]

    _write(path, text)
    ch = T.parse_chapter(path)
    try:
        _proved(path, before, want or None,
                {p.no: p.section for p in ch.paragraphs if p.section}, where)
    except Refused:
        raise
    return {"chapter": int(chapter), "file": target["file"],
            "name": plain(want) if want else ""}


def set_section(book, chapter, para, title, on=True):
    r"""Open a section at this paragraph, rename it, or take it away.

    `on` False deletes whatever \secmark stands before the paragraph; a title
    given where one already stands renames it.
    """
    target, ch = _file_with_para(book, chapter, para)
    path = target["path"]
    text = _read(path)
    before = _shape(path)
    where = "%s paragraph %s:%s" % (target["file"], chapter, para)
    eol = _eol(text)

    at = _parstart_at(text, chapter, para)
    if at is None:
        at = _parnum_at(text, para)
    if at is None:
        raise Refused("%s: there is no \\parstart or \\parnum to put a section "
                      "before" % where)
    at = _open_of(text, at)

    had = _secmark_before(text, at)
    if had:
        text = text[:had[0]] + text[had[1]:]
        at = had[0]

    want = ""
    if on and str(title or "").strip():
        want = escaped(check_title(title))
        text = text[:at] + "\\%s{%s}%s%s" % (SECMARK, want, eol, eol) + text[at:]
    elif on:
        raise Refused("a section needs a name")

    _write(path, text)
    wanted = {p.no: p.section for p in T.parse_chapter(path).paragraphs
              if p.section}
    _proved(path, before, T.parse_chapter(path).name, wanted, where)
    # and the mark really did land on the paragraph it was asked for
    got = {p.no: p.section for p in T.parse_chapter(path).paragraphs if p.section}
    if want and got.get(int(para)) != want:
        raise Refused("%s: refusing -- the section landed on %r instead"
                      % (where, sorted(got)))
    if not want and int(para) in got:
        raise Refused("%s: refusing -- the section is still there" % where)
    return {"chapter": int(chapter), "para": int(para), "file": target["file"],
            "title": plain(want) if want else ""}


if __name__ == "__main__":
    for c in read(sys.argv[1] if len(sys.argv) > 1 else "."):
        print("chapter %s (%s) %s" % (c["chapter"], c["file"],
                                      ("- " + c["name"]) if c["name"] else ""))
        for s in c["sections"]:
            print("    section at paragraph %s: %s" % (s["para"], s["title"]))
