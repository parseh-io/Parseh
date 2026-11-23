#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
r"""A book's text written into LaTeX, and read back out of it (TO-DO §6.5, §6.6).

    texesc.escape("50% of R&D")      ->  50\% of R\&D
    texesc.unescape(r"50\% of R\&D") ->  50% of R&D
    texesc.raw_percent(tex)          ->  where LaTeX would start a comment, or -1

The ten characters LaTeX reads as instructions -- \ { } $ % & # _ ^ ~ -- were
once refused in a book's text: "50%" or "R&D" in a chapter stopped the add,
and a chunk holding one could not be edited.  Now Parseh writes each as the
escape LaTeX prints as that character, and every reader of a chapter file
undoes it, so the text a person typed is the text the reader shows, the chunk
sheet offers, the timings key hashes and the PDF prints:

    \   \textbackslash{}      {  \{      }  \}      $  \$      %  \%
    &   \&                    #  \#      _  \_
    ~   \textasciitilde{}     ^  \textasciicircum{}

WHICH FIELDS.  The text of a chunk and what is set beside it as literal text:
fa, kana, tr and en (TEXT_FIELDS).  Not the vocabulary, which is LaTeX by
design (\dw, \vb, \textit ...) and is written as it is typed; not the word
line, which lib/wordline.lua cuts and which has its own rules.

ONE PASS EACH WAY.  `unescape` reads the escapes in one left-to-right scan,
so it is the exact inverse of `escape` for every string: undoing them one kind
at a time would turn the escaped form of a typed backslash followed by "{"
back into something else.  A backslash this does not recognise (\, or \- that
somebody wrote by hand) is left as it stands.

THE KEYS DO NOT MOVE.  A text with none of the ten characters is the same
string escaped and unescaped, and no book written before this held one (they
were refused at both doors), so the timings keys (lib/timestamp.py sub_key),
which hash a subparagraph's text, are what they always were.

lib/structure.py's chapter and section names use the same table: a name typed
into the reader is text too.
"""
import re

TEXT_FIELDS = ("fa", "kana", "tr", "en")

ESCAPES = {"\\": "\\textbackslash{}", "{": "\\{", "}": "\\}", "$": "\\$",
           "%": "\\%", "&": "\\&", "#": "\\#", "_": "\\_",
           "~": "\\textasciitilde{}", "^": "\\textasciicircum{}"}
SPECIALS = frozenset(ESCAPES)

_TO_TEX = re.compile("[%s]" % re.escape("".join(ESCAPES)))
_BACK = {tex: ch for ch, tex in ESCAPES.items()}
_FROM_TEX = re.compile("|".join(re.escape(t) for t in
                                sorted(_BACK, key=len, reverse=True)))


def escape(text):
    """`text` as it is written into a .tex: each special as its escape."""
    return _TO_TEX.sub(lambda m: ESCAPES[m.group()], str(text or ""))


def unescape(tex):
    """The text a .tex field means: each escape `escape` writes, undone."""
    return _FROM_TEX.sub(lambda m: _BACK[m.group()], str(tex or ""))


def raw_percent(tex, start=0, end=None):
    r"""The offset of the first % in tex[start:end] that LaTeX reads as a
    comment -- one not escaped by a backslash -- or -1.  `\%` is text; `\\%`
    (a line break, then a comment) is not, so the backslashes are counted."""
    end = len(tex) if end is None else end
    i = tex.find("%", start, end)
    while i >= 0:
        k = i
        while k > 0 and tex[k - 1] == "\\":
            k -= 1
        if (i - k) % 2 == 0:
            return i
        i = tex.find("%", i + 1, end)
    return -1


# A text field inside a regex that reads a chunk off one line (verify_book.py,
# check_batch.py): everything up to the first brace that closes it, where an
# escape this module writes is one step -- \} and the {} of \textbackslash{}
# do not close the field.
FIELD = r"((?:\\[A-Za-z]+\{\}|\\.|[^\\}])*?)"
