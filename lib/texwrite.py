#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Change ONE chunk of a chapter .tex, and leave every other byte alone.

A chapter file is written by hand.  Its comments, its blank lines, the place
where a long \\voc was broken across lines, the \\parstart / \\parnum / frank
scaffolding are the author's, and none of it can be derived from the chunks --
so nothing here ever re-emits a parsed chapter.  edit_chunk finds the one
macro call, replaces only the argument groups that changed, and splices: the
prefix and the suffix are the bytes that were already there.

    read_chunks(path)                every chunk of one chapter, addressable
    edit_chunk(path, index, fields)  rewrite that one chunk, or refuse
    book_chapters(book)              the chapter files and their chunk counts

serve.py wires the routes; these functions are the contract.  A refusal is a
Refused, never a SystemExit -- the command-line tools beside this file exit,
but this one runs inside the server.

THE INDEX is the chunk's ordinal in the file, counting \\ch, \\chr, \\chw,
\\chrw and \\chp from 0 in source order: the order texparse yields, because
that is the number the reader was given (tex2html writes it into data-c) and
the number it hands back.  The two orders must not drift, so the walk below is
texparse.parse_chapter's own, step for step -- the same macro pattern, the
same rule that a % opening a line comments the line out, the same
read_args/read_group for the braces.  It keeps the offsets parse_chapter
throws away and changes nothing else.  (data-c counts across the whole book,
in the order main.tex \\inputs the files; book_chapters turns one of those
numbers into a file and a local index.)

WHAT MAY BE WRITTEN, and how it is escaped.  fa, kana, tr and en are set by
LaTeX as literal text, and they are TEXT here: what a person types, "50%" or
"R&D", is what they are handed back.  Each of \\ { } $ % & # _ ^ ~ is written
into the file as its LaTeX escape (\\%, \\&, \\textasciitilde{} ...) and read
back out of it by lib/texesc.py, at the two edges of this file and nowhere in
between: _values undoes the escapes of what it reads, and _render, the
regions edit_chunk splices and the \\parstart incipit write them.  Every check
in the middle -- fidelity against source/paras, the word line, the incipit,
the proof that nothing else moved -- compares the text as typed, so it
compares what the source paragraph says.  texparse undoes the same escapes, so
the reader, the timings keys and every export see the text, never the escape
(TO-DO §6.5, §6.6).  A text with none of the ten is the same string either
way, which is every chapter written before this.

voc is the exception, and is written through byte for byte: it is LaTeX by
design (\\dw, \\vb, \\bw, \\pw, \\textit, \\emph, \\nobreak, \\,), and escaping
it would destroy the field.  It is validated instead, with check_batch.py's
own ALLOWED, BADTEX and count_args -- imported rather than copied, so an edit
cannot disagree with the checker that judges the file afterwards -- plus one
check check_batch does not make: the braces must balance under read_group's
rule, since a voc that leaves one open would swallow the arguments after it.

WHAT IS NOT TEXT AT ALL is refused in every field, the vocabulary included.
A control character is invisible, and every check downstream looks straight
past it: a NUL posted into an en sits identically on both sides of the
fidelity comparison and passes it, is written into ch1.tex and into
source/paras/, is served raw inside reader/index.html -- a 0x00 going over
the wire -- and stops ./build.sh in LaTeX with a message that names neither
the chapter nor the chunk.  An unpaired surrogate is not a character at all:
UTF-8 cannot encode one, so it would leave a half-written .tex.tmp beside the
chapter and hand the request a traceback where a refusal belongs.  The tab,
the newline and the carriage return are the exception, because they are in
this data already -- a long voc is broken across lines, and a chapter written
on Windows ends every line with a CR.  Nothing else is taken away: every
script the toolbox teaches, the combining marks, the zero-width non-joiner
Persian needs (U+200C, which lib/languages.json lists in chars for fa) and
the studio's return sign are letters and marks, not controls.  lib/draft.py
refuses this same class at the other door and points here for the reason.

THE WORD LINE.  A Japanese or Chinese chunk may carry `words`, its text
divided into words with a reading on each (lib/wordline.py says the grammar
and why).  It is the LAST argument of two macros of its own, \\chw and \\chrw
-- \\ch and \\chr with a word line -- because the arity is in the name, so
setting words on a \\ch rewrites that one call as a \\chw and blanking them
rewrites it back; nothing else in the file moves, and the proof says so.
The line is written verbatim and judged by wordline.check at the book's door,
never by the rules above: it is not set as literal text but cut into words by
lib/wordline.lua.  And it is judged against the WHOLE chunk after every edit,
because it is the text divided -- an fa changed under a word line that no
longer rejoins it is refused, not left for the PDF to stop on.  The chunk's
own reading is compared with it only to warn, and a book whose text is read
out of its written order says "reorders": true in book.json and is not.

THE CONTENTS.  \\parstart{chapter.paragraph}{incipit} carries the opening of
a paragraph, and it is what the PDF outline, the printed contents and the
reader's contents panel show.  The incipit is DERIVED from the text -- the fa
of the chunks of the paragraph's first subparagraph, six words, or twelve
characters for a language whose words are not separated -- and three tools
already derive it that way (assemble.py's incipit, inject_parstart.py's,
lib/draft.py's _incipit; lib/frank-preamble.tex says what it is for).  So an
edit to that text leaves it stale, and the contents would name a sentence no
longer in the book while the edit came back with fidelity "ok".  Rather than
report that and leave it, this file keeps the two in step -- derived data
following the text it is derived from -- and the byte-for-byte promise covers
TWO regions instead of one: the argument groups of the chunk, and the second
argument of one \\parstart.  Nothing else moves, and the proof before the
write says so.  A \\parstart that was not the derived incipit BEFORE the edit
either was written by hand: it is reported and left alone, the rule the
fidelity check already uses for a paragraph that did not reproduce its source
before the edit either.

FIDELITY.  verify_book.py proves every built paragraph against
source/paras/: its chunks, joined with the language's separator and stripped
of the language's marks, must reproduce the source paragraph exactly.
Changing fa can break that, and a chapter that has quietly stopped
reproducing its source is worse than a refused edit -- so an fa that would
break it is refused, in verify_book's own words.  A paragraph with no source
file, or one that did not reproduce its source before the edit either, cannot
be judged: the edit goes through and the result says which it was.
"""
import bisect
import glob
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import books                                                    # noqa: E402
import chunkdiv                                                 # noqa: E402
import languages                                                # noqa: E402
import pathlock                                                 # noqa: E402
import reading                                                  # noqa: E402
import texesc                                                   # noqa: E402
import texparse as T                                            # noqa: E402
import wordline                                                 # noqa: E402
from check_batch import ALLOWED, BADTEX, count_args             # noqa: E402


class Refused(ValueError):
    """An edit that will not be made, and why, in words worth showing a user.

    A ValueError so a caller that already catches one is not surprised.  The
    tools beside this file raise SystemExit; that would take the server down
    with the request.
    """


# Which macro takes which arguments, in order.  The arity is in the NAME and
# is never guessed (docs/languages.md section 3): these lists must say what
# frank-preamble.tex defines and what texparse.parse_chapter reads, and the
# smoke test reads a chapter back through texparse to prove they do.
SLOTS = {"ch":   ("col", "fa", "tr", "voc", "en"),
         "chr":  ("col", "fa", "kana", "tr", "voc", "en"),
         "chp":  ("col", "fa"),
         "chw":  ("col", "fa", "tr", "voc", "en", "words"),
         "chrw": ("col", "fa", "kana", "tr", "voc", "en", "words")}

# every field name edit_chunk answers to, in the order a chunk carries them
FIELDS = ("col", "fa", "kana", "tr", "voc", "en", "words")

# The macro a chunk is written with once it carries a word line, and back:
# words are always the last argument, so the two of a pair differ by it and
# by nothing else.  \chp has no form with words -- it is the unglossed chunk.
_WITH_WORDS = {"ch": "chw", "chr": "chrw"}
_WITHOUT_WORDS = {w: n for n, w in _WITH_WORDS.items()}

# The four colours, named as the user names them everywhere, and the macro
# each becomes.  \Cred..\Cgreen are defined in lib/frank-preamble.tex and
# mapped back to the reader's hl-<name> classes by tex2html.HL; this is the
# third face of one table, and the smoke test reads it against tex2html's so
# the three cannot drift.
COLOURS = {"red": "\\Cred", "blue": "\\Cblue",
           "orange": "\\Corange", "green": "\\Cgreen"}
_COLOUR_OF = {v: k for k, v in COLOURS.items()}

# What LaTeX reads as an instruction.  Escaped in fa, kana, tr and en (the
# docstring says how); refused in the word line, which is wordline's own list
# (lib/bookmeta.py and youtube/lib/ytpages.py read both names from here).
TEX_SPECIALS = wordline.TEX_SPECIALS

# What is not text, in ANY field: the C0 controls, DEL, the C1 controls, and
# the unpaired surrogates UTF-8 cannot encode.  The tab, the newline and the
# carriage return are left out because a voc is broken across lines and a
# chapter written on Windows ends every one of them with a CR.  The docstring
# says what a control character does to the PDF, the checker and the reader.
NOT_TEXT = wordline.NOT_TEXT

# parse_chapter's own pattern, and a second copy of its list of names: a name
# missing here numbers the chunks differently from the reader, and an edit
# lands on the wrong one.  The longer names first -- with the \b, "ch" does
# not match at "\chr" nor "chr" at "\chrw", and the chunk would be skipped
# without a word.
_MACRO = re.compile(r"\\(chapopen|chapname|secmark|parnum|chrw|chw|chr|chp|ch"
                    r"|parend|chapend)\b")

# The contents anchor.  It is deliberately NOT in _MACRO: that walk is
# texparse.parse_chapter's, step for step, and parse_chapter does not know
# \parstart -- adding it would make a malformed anchor refuse an edit to a
# chunk that has nothing to do with it.  _parstart_spans looks for it apart.
_PARSTART = re.compile(r"\\parstart\b")

# a blank line inside an argument is \par, and LaTeX stops with "Paragraph
# ended before \ch was complete" -- an error whose message names neither the
# chapter nor the chunk
_BLANK_LINE = re.compile(r"\n[ \t]*\n")


# --- reading the file ---------------------------------------------------
def _read(path):
    """The file exactly as it sits on disk.  newline='' so a chapter written
    on Windows keeps its CRLF through an edit: "byte for byte" is meant to
    include the line endings.  texparse opens the same file with universal
    newlines, which changes the offsets but not the order or the count of the
    macros, so the two still agree about which chunk is which."""
    with io.open(path, encoding="utf-8", newline="") as f:
        return f.read()


def _write(path, text):
    """Written beside the file and renamed over it, so a chapter is never
    left half-written by a crash or a full disk (languages.write_css does the
    same replace).  The temporary name is this write's own (TO-DO §3.10): two
    writes through one fixed name truncated each other's file."""
    tmp = pathlock.tmp(path)
    try:
        with io.open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


# ONE WRITER AT A TIME FOR EACH BOOK (TO-DO §3.10): an edit reads the chapter,
# changes one chunk and writes the whole chapter back, and two of them at once
# (two tabs, a phone and the computer) lost the earlier one's change.  Each
# door below holds its book's lock (lib/pathlock.py) from the read to the
# write; the server holds the same lock around the whole request.
def _book_folder(path, *_a, **_k):
    return os.path.dirname(os.path.abspath(path))


def _line_starts(text):
    """Where each line begins, so a position becomes the 0-based line number
    parse_chapter reports as Chunk.line -- what an error message quotes and
    what a caller shows beside a chunk."""
    starts = [0]
    for m in re.finditer("\n", text):
        starts.append(m.end())
    return starts


class _Call:
    """One chunk macro call: where it is, and where each argument's contents
    are.  The spans are of the CONTENTS, so a splice never touches a brace."""
    __slots__ = ("name", "start", "end", "args", "label", "line")

    def __init__(self, name, start, end, args, label, line):
        self.name, self.start, self.end = name, start, end
        self.args, self.label, self.line = args, label, line


def _arg_spans(text, i, n, where):
    """The (start, end) of the contents of the next n argument groups.

    texparse.read_args does this same walk and throws the offsets away, and
    the brace counting is read_group's, called here unchanged: the file that
    reads a chunk and the file that writes it have to cut a call into the
    same pieces, or the reader would edit a chunk other than the one it
    showed.  read_group treats a backslash as stepping over the next
    character, so \\{ inside a field is not a brace to either of them."""
    spans = []
    for k in range(n):
        while i < len(text) and text[i] in " \t\r\n":
            i += 1
        if i >= len(text) or text[i] != "{":
            raise Refused("%s: argument %d of %d is missing -- the arity is in "
                          "the macro's name" % (where, k + 1, n))
        try:
            _, j = T.read_group(text, i)
        except ValueError as e:
            raise Refused("%s: %s" % (where, e))
        spans.append((i + 1, j - 1))
        i = j
    return spans, i


def _scan(text, path="<text>"):
    """Every chunk macro call in one chapter, in source order.

    parse_chapter's loop with the offsets kept: the same comment rule (a %
    that opens a line comments the line out, and a % anywhere else is text to
    both files), the same \\parend / \\chapend reset of the current label."""
    starts = _line_starts(text)
    calls, label, i = [], None, 0
    while i < len(text):
        if text.startswith("%", i) and (i == 0 or text[i - 1] == "\n"):
            i = text.find("\n", i)
            if i < 0:
                break
            continue
        m = _MACRO.match(text, i)
        if not m:
            i += 1
            continue
        name, j = m.group(1), m.end()
        line = bisect.bisect_right(starts, m.start()) - 1
        where = "%s:%d \\%s" % (os.path.basename(path), line + 1, name)
        if name in ("chapopen", "chapname", "secmark"):
            # one group each, READ rather than stepped over: a chapter's name
            # or a section's is ordinary text and may hold a brace or a macro,
            # and walking into it would scan that as the chapter's own
            _, j = _arg_spans(text, j, 1, where)
        elif name == "parnum":
            (span,), j = _arg_spans(text, j, 1, where)
            label = text[span[0]:span[1]].strip()
        elif name in SLOTS:
            args, j = _arg_spans(text, j, len(SLOTS[name]), where)
            calls.append(_Call(name, m.start(), j, args, label, line))
        else:                                   # \parend, \chapend
            label = None
        i = j
    return calls


def _values(text, call):
    """The argument groups of one call, by field name: as written, except that
    the text fields (texesc.TEXT_FIELDS) are read back to what was typed --
    "50\\%" in the file is "50%" here."""
    return {f: (texesc.unescape(text[a:b]) if f in texesc.TEXT_FIELDS else text[a:b])
            for f, (a, b) in zip(SLOTS[call.name], call.args)}


def _tex(field, value):
    """A field's value as it is written into the file: the text fields with
    their TeX specials escaped, the others as they are."""
    return texesc.escape(value) if field in texesc.TEXT_FIELDS else value


def _label_no(label, k):
    """The k-th part of a dotted label, in whatever digits the book writes it:
    '۳.۱' is (3, 1).  WHICH part is the paragraph depends on the macro --
    \\parnum is paragraph.subparagraph and \\parstart is chapter.paragraph --
    so every caller says which one it means and none of them assumes."""
    if not label:
        return None
    parts = languages.any_to_latin_digits(label).split(".")
    if k >= len(parts):
        return None
    try:
        return int(parts[k])
    except ValueError:
        return None


def _para_no(label):
    """The paragraph a \\parnum labels: '۳.۱' is paragraph 3, in whatever
    digits the book writes it (texparse.Sub.para_no)."""
    return _label_no(label, 0)


def _record(text, index, call):
    """One chunk as a dict, ready for json.dump."""
    raw = _values(text, call)
    d = {"index": index, "macro": call.name, "line": call.line,
         "label": call.label or "", "para": _para_no(call.label),
         "glossed": call.name != "chp", "fields": list(SLOTS[call.name]),
         "span": [call.start, call.end],
         # the colour under the name the user knows it by, and beside it what
         # the slot actually holds -- a hand-written slot that is neither
         # empty nor one of the four is reported, never quietly dropped
         "col": _COLOUR_OF.get(raw["col"].strip(), ""), "col_tex": raw["col"]}
    for f in ("fa", "kana", "tr", "voc", "en", "words"):
        d[f] = raw.get(f, "")
    return d


def read_chunks(path):
    """Every chunk of one chapter file, in the order texparse yields them.

    A list of dicts, one per \\ch / \\chr / \\chw / \\chrw / \\chp:

        index    its ordinal in the file, which is what edit_chunk takes
        macro    'ch' | 'chr' | 'chw' | 'chrw' | 'chp'
        fields   the fields this macro has a slot for
        line     0-based line of the macro, as texparse's Chunk.line
        label    the \\parnum in force ('۱.۲'), and `para` its paragraph number
        col      '' or red/blue/orange/green; col_tex is the slot as written
        fa kana tr voc en words   the argument groups ('' for a slot the
                 macro does not have -- words for all but \\chw and \\chrw):
                 voc and words verbatim, the other four as typed, their TeX
                 escapes undone (lib/texesc.py)
        span     [start, end] of the whole call in the file as _read gives it

    Raises Refused when a macro call is malformed -- an argument missing, a
    brace never closed -- naming the line: texparse fails on the same file,
    less legibly, and a caller about to offer an edit box wants to know.
    """
    text = _read(path)
    return [_record(text, k, c) for k, c in enumerate(_scan(text, path))]


# --- what a field may hold ----------------------------------------------
def _check_common(field, value, where):
    """The two rules every field obeys, the vocabulary included."""
    if not isinstance(value, str):
        raise Refused("%s: %s must be a string, not %s"
                      % (where, field, type(value).__name__))
    m = NOT_TEXT.search(value)
    if m:
        # The character is invisible, so the message has to place it and name
        # it instead of quoting it: printing it would put it in the answer,
        # which is the page that must not carry one either.
        k, cp = m.start(), ord(m.group())
        why = ("an unpaired surrogate, which UTF-8 cannot encode"
               if 0xd800 <= cp <= 0xdfff else
               "a control character, and the only ones a field may hold are "
               "the tab, the newline and the carriage return")
        raise Refused("%s: %s carries U+%04X at character %d, which is not text "
                      "-- %s: %s"
                      % (where, field, cp, k, why,
                         value[max(0, k - 30):k] + "<U+%04X>" % cp
                         + value[k + 1:k + 31]))
    if _BLANK_LINE.search(value):
        raise Refused("%s: a blank line inside %s ends the paragraph -- LaTeX "
                      "would stop with 'Paragraph ended before \\ch was "
                      "complete'" % (where, field))


def _balanced(value, where):
    """Braces balanced under read_group's rule, where a backslash steps over
    the next character.  check_batch counts { against } and so misses \\{
    exactly; a voc that leaves a brace open would swallow the arguments after
    it when the chunk is read back, which is the one way an edit could damage
    a chunk it does not name."""
    depth, i = 0, 0
    while i < len(value):
        c = value[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth < 0:
                raise Refused("%s: voc closes a brace it never opened" % where)
        i += 1
    if depth:
        raise Refused("%s: voc leaves %d brace%s open"
                      % (where, depth, "" if depth == 1 else "s"))


def _check_voc(value, where):
    """check_batch.py's rules for the vocabulary field, applied before it is
    written instead of after the chapter is built.  Its ALLOWED, BADTEX and
    count_args are imported, not restated, so an edit cannot pass here and
    fail there.  count_args, like check_batch, wants the argument groups run
    together: \\dw{a} {b} counts as one, and the checker would call it short."""
    m = BADTEX.search(value)
    if m:
        raise Refused("%s: voc may not contain %r -- check_batch.py rejects it "
                      "escaped as well as raw" % (where, m.group(0)))
    for m in re.finditer(r"\\([a-zA-Z]+)", value):
        if m.group(1) not in ALLOWED:
            raise Refused("%s: voc may not use \\%s -- the gloss macros are %s"
                          % (where, m.group(1),
                             ", ".join("\\" + a for a in sorted(ALLOWED))))
    if value.count("{") != value.count("}"):
        raise Refused("%s: unbalanced braces in voc (%d open, %d closed)"
                      % (where, value.count("{"), value.count("}")))
    _balanced(value, where)
    for name, n in (("dw", 2), ("bw", 3), ("vb", 7)):
        for m in re.finditer(r"\\%s(?![a-zA-Z])" % name, value):
            got = count_args(value, m.end())
            if got < n:
                raise Refused("%s: \\%s needs %d arguments and has %d"
                              % (where, name, n, got))


def _check_words(value, lang, where):
    """A word line on its own terms: what lib/wordline.py refuses in one at a
    book's door -- a LaTeX special, a blank line, a grammar it cannot read, a
    language with no word layer -- short of whether it rejoins the chunk's
    text, which needs the chunk and is _words_fit's.  Asked of wordline.check
    itself with the line's own words standing in for the text, so there is
    one list of refusals and not a second one written out here."""
    try:
        own = (lang.word_sep or "").join(s for s, _ in wordline.parse(value))
    except wordline.WordsError:
        own = ""                        # check() refuses it before the text
    errors, _ = wordline.check(own, value, lang, door=wordline.BOOK)
    if errors:
        raise Refused("%s: words: %s" % (where, "; ".join(errors)))


def _words_fit(values, lang, reorders, where, written=None):
    """The whole-chunk rule: a chunk that carries words, judged as a chunk --
    its fa, its word line and its own reading (kana where the language has
    one, tr where it has not) -- by wordline.check at the book's door.
    Returns the warnings, which are never refusals; raises Refused on an
    error.  `written` is the fields the edit set, None for a chunk written
    whole: a line the edit did not bring was either left behind by an fa
    that moved, or was already wrong, and the message says which."""
    line = values.get("words") or ""
    if not line.strip():
        return []
    reading = values.get("kana") if lang.reading else values.get("tr")
    errors, warnings = wordline.check(values.get("fa") or "", line, lang,
                                      reading=reading or "", reorders=reorders,
                                      door=wordline.BOOK)
    if not errors:
        return ["words: %s" % w for w in warnings]
    said = "; ".join(errors)
    if written is None or "words" in written:
        raise Refused("%s: words: %s" % (where, said))
    if "fa" in written:
        raise Refused("%s: the words no longer fit this chunk -- %s.  The word "
                      "line is the text divided into words, so it changes "
                      "with the text: fix the words too, in the same edit, or "
                      "send them blank to take them off" % (where, said))
    raise Refused("%s: the word line already written here does not fit this "
                  "chunk -- %s.  Fix the words, or send them blank to take "
                  "them off, before anything else is edited" % (where, said))


def _form(name, words):
    """The macro of `name`'s pair for a chunk that does, or does not, carry
    words: \\ch and \\chw, \\chr and \\chrw.  None for \\chp with words, which
    has no such form."""
    plain = _WITHOUT_WORDS.get(name, name)
    return _WITH_WORDS.get(plain) if words else plain


def _name_for(name, values, lang, where):
    """The macro a chunk that has just come into being is written with: the
    one of `name`'s pair its fields call for, so a half or a join that holds
    a word line is a \\chw or \\chrw and one that does not is not."""
    words = values.get("words")
    if words is None or (isinstance(words, str) and not words.strip()):
        return _form(name, False)
    if not isinstance(words, str):
        raise Refused("%s: words must be a string, not %s"
                      % (where, type(words).__name__))
    if not lang.words:
        raise Refused("%s: %s has no word layer, so a chunk carries no words "
                      "(docs/languages.md section 3)" % (where, lang.name))
    if _form(name, True) is None:
        raise Refused("%s: \\%s has no words slot -- \\chp is the unglossed "
                      "chunk" % (where, name))
    return _form(name, True)


def _value(field, value, lang, where):
    """The text to put in the group, or a Refused saying why there is none."""
    _check_common(field, value, where)
    if field == "col":
        name = value.strip()
        if name and name not in COLOURS:
            raise Refused("%s: %r is not a colour -- the four are %s, or '' for "
                          "none" % (where, value, ", ".join(COLOURS)))
        return COLOURS[name] if name else ""
    if field == "voc":
        _check_voc(value, where)
        return value
    if field == "words":
        if not value.strip():
            return ""                           # no words: the macro without them
        _check_words(value, lang, where)
        return value
    # fa, kana, tr, en: text, any character of it -- a TeX special is escaped
    # when it is written (_tex), never refused
    if field == "fa" and not value.strip():
        raise Refused("%s: a chunk with no text is not a chunk -- an empty fa is "
                      "an error to check_batch.py, glossed or not" % where)
    if field == "tr" and lang.strip(value) != value:
        marks = "harakat" if lang.script == "arabic" else "marks"
        raise Refused("%s: %s leaked into tr -- the romanisation carries none"
                      % (where, marks))
    return value


# the fields that make up a chunk's gloss: the word line is not one of them
# (it is the text divided, and has its own rules), and neither is the colour
GLOSS = ("tr", "voc", "en", "kana")

# what taking the whole gloss off is called, on the reader's chunk sheet and
# in every refusal that points at it
_DELETE = ("emptying every box of the gloss at once (\"delete gloss\") "
           "takes the whole gloss off")


def _unglossed(values, lang):
    """True when not one part of this chunk's gloss is written: check_batch's
    unwritten(), asked of a chunk as it will stand in the file.

    The vocabulary counts, though no language requires it -- a field somebody
    has typed into is a chunk somebody is working on.  The one exception is
    the reading lib/draft.py gave the chunk from its word line (kana where
    the language has a reading, tr where it has not: wordline.seed), while it
    still says exactly that, because nobody wrote it.  Seed-aware for this
    whole-chunk question only: once anything else is written, that reading
    is the reading the chunk has, and counts as present."""
    field, seeded = wordline.seed({"words": values.get("words") or ""}, lang)
    return not any((values.get(f) or "").strip()
                   and not (f == field and seeded
                            and (values.get(f) or "").strip() == seeded)
                   for f in GLOSS)


def _unseeded(values, lang):
    """(the chunk as chunkdiv should cut or join it, the field its reading was
    taken out of -- None when nothing was).

    An unglossed chunk of a language divided into words may carry the
    reading lib/draft.py proposed from its word line (_unglossed).  That
    reading is the line's, not anybody's writing, and chunkdiv cannot divide
    it: a romanisation it cannot count the words of, or a kana that does not
    open with the first half's own text, goes whole to the first half.  That
    half then reads as written -- a chunk half glossed by a cut, which
    check_batch calls an error -- and the second as blank.  So the reading
    comes off before chunkdiv sees the chunk and is proposed again from each
    new chunk's own line afterwards (_seeded): a blank chunk divides into two
    blank halves, and two blank chunks join into one blank chunk."""
    field, seeded = wordline.seed({"words": values.get("words") or ""}, lang)
    if field and seeded and (values.get(field) or "").strip() \
            and _unglossed(values, lang):
        return {k: v for k, v in values.items() if k != field}, field
    return values, None


def _seeded(values, field, lang):
    """`values` with the reading in `field` proposed from its own word line,
    as lib/draft.py proposes one, or with none when the chunk has no line to
    read (a join drops a line that only one side had) -- either way a chunk
    _unglossed calls blank.  `values` unchanged when `field` is None."""
    if field is None:
        return values
    out = {k: v for k, v in values.items() if k != field}
    _field, reading = wordline.seed({"words": out.get("words") or ""}, lang)
    if reading:
        out[field] = reading
    return out


def _check_required(written, old, merged, lang, where):
    """The gloss fields check_batch.py insists on, guarded where a hand can
    take them away.

    A chunk nobody has glossed yet is legal everywhere, and so is one being
    filled in a box at a time: an edit that writes an en beside a blank tr is
    saved, and check_batch lists what the chunk still lacks.  What is refused
    is EMPTYING a field the language requires -- en always, tr where the
    language romanises every chunk (require_tr), kana where it has a reading
    -- that held something before this edit, because that turns a finished
    gloss into a half-finished one.  Unless the edit leaves the whole chunk
    unglossed (_unglossed, seed-aware as check_batch is): emptying every box
    at once is how a gloss is deleted, and the chunk goes back to being one
    nobody has started.  A field sent blank that was already blank changes
    nothing and is never refused, and voc may always be emptied -- no
    language requires it.

    `written` is what the edit sets, `old` the chunk's fields before it and
    `merged` after it, words included."""
    if _unglossed(merged, lang):
        return
    required = [("en", "a glossed chunk needs its meaning -- check_batch.py "
                       "calls an empty en an error")]
    if lang.require_tr:
        required.append(("tr", "%s romanises every chunk, so tr cannot be "
                               "emptied on its own" % lang.name))
    if lang.reading:
        required.append(("kana", "%s needs the reading of every chunk, so kana "
                                 "cannot be emptied on its own" % lang.name))
    for f, why in required:
        if f in written and not written[f].strip() \
                and (old.get(f) or "").strip():
            raise Refused("%s: %s; %s" % (where, why, _DELETE))


# --- fidelity to source/paras/ ------------------------------------------
def _norm(s, lang):
    """The whitespace normalisation check_batch.norm and verify_book do: single
    spaces for a language whose words are separated by them, no spaces at all
    for one whose are not (the chunks of a Japanese paragraph are joined with
    nothing, and the source has no space to keep).  Written out here because
    check_batch's reads a module global its main() sets, and this one is
    handed the language."""
    if lang.spaced:
        return re.sub(r"\s+", " ", s).strip()
    return re.sub(r"\s+", "", s)


def _chapter_no(path):
    """The chapter a file belongs to, from its name: verify_book.chapter_of,
    so ch1.tex and ch1b.tex are both chapter 1 and share its paragraphs."""
    m = re.match(r"ch(\d+)", os.path.basename(path))
    return int(m.group(1)) if m else None


def _paragraph(path, text, calls, chapter, para, lang, swap=None):
    """The fa of every chunk of one paragraph, joined the way the source was
    cut.  A paragraph can be continued in a second file of the same chapter
    (the Persian book's ch1.tex and ch1b.tex), so every ch*.tex of the book is
    walked, in the order verify_book walks them.  The file being edited is
    read from `text`, not from the disk, so it is the edit that gets judged;
    `swap` is {index: [fa, ...]} to stand in for a chunk's own -- a list, so
    that one chunk can become two (a split), or none (the second of a pair
    being merged), and not only another one."""
    here = os.path.abspath(path)
    out = []
    for f in sorted(glob.glob(os.path.join(os.path.dirname(here), "ch*.tex"))):
        if _chapter_no(f) != chapter:
            continue
        mine = os.path.abspath(f) == here
        if mine:
            body, cs = text, calls
        else:
            body = _read(f)
            cs = _scan(body, f)
        for k, c in enumerate(cs):
            if _para_no(c.label) != para:
                continue
            a, b = c.args[SLOTS[c.name].index("fa")]
            if swap and mine and k in swap:
                out.extend(swap[k])
            else:
                out.append(texesc.unescape(body[a:b]))
    return (lang.word_sep or "").join(out)


def _fidelity(path, text, calls, index, swap, lang):
    """What verify_book.py will say about this paragraph once the fa changes.

    Returns the note for the caller; raises Refused when a paragraph that
    reproduced its source would stop.  The rebuild is verify_book's, so what
    passes here is exactly what the checker will pass, and nothing is refused
    that it would accept."""
    label = calls[index].label
    if not label:
        return "not checked: the chunk sits under no \\parnum"
    chapter, para = _chapter_no(path), _para_no(label)
    if chapter is None or para is None:
        return "not checked: %s is not a ch<N>.tex with numbered paragraphs" \
               % os.path.basename(path)
    # A PARAGRAPH SOMEBODY HAS TAKEN CHARGE OF.  The check stays for every
    # other paragraph -- it is what stops a model, or a careless edit of a
    # file, quietly rewriting a book -- but a person editing in the reader can
    # say that this one is theirs, and then it is (lib/reading.py).  Asked
    # before the source file is even opened, so a paragraph may depart from a
    # source it no longer has.
    here = os.path.dirname(os.path.abspath(path))
    if reading.is_free(here, chapter, para):
        return ("not checked: paragraph %d is marked as departing from its "
                "source, in reading.json" % para)
    name = "ch%d_p%02d.txt" % (chapter, para - 1)
    src = os.path.join(here, "source", "paras", name)
    if not os.path.isfile(src):
        return "not checked: no source paragraph at source/paras/%s" % name
    with io.open(src, encoding="utf-8") as f:
        want = _norm(lang.strip(f.read().strip()), lang)
    after = _norm(lang.strip(_paragraph(path, text, calls, chapter, para, lang,
                                        swap)), lang)
    if after == want:
        return "ok: paragraph %d still reproduces source/paras/%s" % (para, name)
    before = _norm(lang.strip(_paragraph(path, text, calls, chapter, para, lang)), lang)
    if before != want:
        return ("not checked: paragraph %d did not reproduce source/paras/%s "
                "before this edit either" % (para, name))
    i = next((i for i, (a, b) in enumerate(zip(after, want)) if a != b),
             min(len(after), len(want)))
    raise Refused("this text would stop paragraph %d reproducing source/paras/%s, "
                  "which verify_book.py checks, at char %d of %d\n"
                  "        got:  ...%s...\n"
                  "        want: ...%s..."
                  % (para, name, i, len(want),
                     after[max(0, i - 60):i + 60], want[max(0, i - 60):i + 60]))


# --- the contents entry -------------------------------------------------
def _parstart_spans(text):
    """Every \\parstart in one chapter: (label, the span of its incipit).

    The spans are of the CONTENTS of the second argument, as everywhere else
    here, so a splice never touches a brace.  _scan's comment rule again -- a
    % that opens a line comments the line out -- and one difference from it: a
    malformed \\parstart is skipped rather than refused, because it belongs to
    a paragraph this edit may have nothing to do with and texparse ignores the
    macro entirely.  The one this edit needs is checked against the text
    before anything is written into it, so a skipped anchor costs an update
    and never a wrong one."""
    out = []
    for m in _PARSTART.finditer(text):
        if text[text.rfind("\n", 0, m.start()) + 1] == "%":
            continue
        try:
            (lab, inc), _ = _arg_spans(text, m.end(), 2, "\\parstart")
        except Refused:
            continue
        out.append((text[lab[0]:lab[1]].strip(), inc))
    return out


def _incipit(text, calls, para, lang, swap=None, words=6, chars=12):
    """What \\parstart carries: the opening of a paragraph's text -- the fa of
    the chunks of its FIRST subparagraph, six words, or twelve characters for
    a language whose words are not separated.

    The fourth copy of one rule, and the count is written out in all four:
    assemble.py's incipit() derives it from the annotator's JSON,
    inject_parstart.py's from the .tex of a batch built before it wrote them,
    lib/draft.py's _incipit from the sentence it has just cut, and this one
    from the chunks as they will read after the edit.  They have to agree --
    a book whose contents was written by one and updated by another would
    disagree with itself.  (lib/tex2html.py's incipit is a fifth, and is not
    one of these: it derives the READER's contents panel from the chunks at
    build time, so it is never stale, and it takes fourteen characters rather
    than twelve where there are no words to count -- the reader's own choice
    about its own panel.)  `swap` is {index: [fa, ...]}, as _paragraph
    takes it, so the incipit can be asked for before the file is written."""
    out = []
    for k, c in enumerate(calls):
        if _para_no(c.label) != para or _label_no(c.label, 1) != 1:
            continue
        a, b = c.args[SLOTS[c.name].index("fa")]
        if swap and k in swap:
            out.extend(swap[k])
        else:
            out.append(texesc.unescape(text[a:b]))
    # the text as typed, so twelve characters never end inside an escape;
    # _parstart_edit escapes it again on its way into the file
    joined = (lang.word_sep or "").join(out)
    if lang.spaced:
        return " ".join(joined.split()[:words])
    return re.sub(r"\s+", "", joined)[:chars]


def _parstart_edit(text, calls, index, swap, lang):
    """Whether this edit moves the paragraph's contents entry, and what to.

    Returns ((start, end, incipit) or None, the note for the caller).  A
    paragraph whose \\parstart is not the incipit the rule derives from the
    text AS IT STANDS was written by hand -- and being written by hand is the
    one thing about a chapter this file never overrules -- so it is reported
    and left alone, exactly as _fidelity leaves a paragraph that did not
    reproduce its source before the edit either."""
    label = calls[index].label
    para, sub = _para_no(label), _label_no(label, 1)
    if para is None or sub is None:
        return None, "not checked: the chunk sits under no numbered \\parnum"
    if sub != 1:
        return None, ("not changed: the contents prints where a paragraph "
                      "opens, and this chunk is in subparagraph %d" % sub)
    before = _incipit(text, calls, para, lang)
    after = _incipit(text, calls, para, lang, swap)
    if after == before:
        return None, "not changed: the paragraph still opens with the same words"
    mine = [s for lab, s in _parstart_spans(text) if _label_no(lab, 1) == para]
    if len(mine) != 1:
        return None, ("not changed: paragraph %d has %s, so what the contents "
                      "prints is not this file's to work out"
                      % (para, "no \\parstart" if not mine
                         else "%d \\parstart anchors" % len(mine)))
    a, b = mine[0]
    if texesc.unescape(text[a:b]) != before:
        return None, ("behind: paragraph %d's \\parstart is not the opening of "
                      "its text, so somebody wrote it by hand and it is left "
                      "alone -- the contents still reads %r, and the paragraph "
                      "now opens %r" % (para, texesc.unescape(text[a:b]), after))
    return (a, b, texesc.escape(after)), ("updated: the contents entry for paragraph %d now "
                           "reads %r" % (para, after))


def _outside(text, spans):
    """Everything that is NOT in these spans, in order: the bytes an edit
    promises to leave alone.  The spans are ascending and do not overlap."""
    out, k = [], 0
    for a, b in spans:
        out.append(text[k:a])
        k = b
    out.append(text[k:])
    return out


# --- the language a chapter is written in -------------------------------
def _book_of(path):
    """The books.Book a chapter file belongs to, or None when it sits beside
    no book.json.  A book.json naming a code the registry does not have is
    refused rather than read as its folder's language: this file writes, and
    books.find_book refuses for the same reason."""
    d = os.path.dirname(os.path.abspath(path))
    if not os.path.isfile(os.path.join(d, "book.json")):
        return None
    try:
        book = books.Book(d)
    except (OSError, ValueError) as e:
        raise Refused("%s: book.json will not read (%s)" % (d, e))
    problem = book.language_problem()
    if problem:
        raise Refused(problem + " -- fix book.json before editing a chunk")
    return book


def _lang_of(path, lang=None, book=None):
    """The book's language: what the caller says, else book.json's, else the
    folder the file sits under, else Persian -- the registry's rule and never
    a guess written here (docs/languages.md section 1).  `book` is the Book a
    caller has already looked up, so it is not read twice."""
    if lang is not None:
        return lang if isinstance(lang, languages.Lang) else languages.get_or_default(lang)
    book = book if book is not None else _book_of(path)
    if book is not None:
        return book.lang
    return languages.detect_from_path(path) or languages.get(languages.DEFAULT)


# --- the edit -----------------------------------------------------------
@pathlock.serialised(_book_folder)
def edit_chunk(path, index, fields, lang=None):
    """Rewrite one chunk's argument groups, and the incipit they name.

    `fields` holds any of col, fa, kana, tr, voc, en, words; only the keys
    present change.  col is '' or red/blue/orange/green and becomes the
    \\C<colour> macro or nothing.  `lang` overrides the book's own (a Lang or
    a code).

    Nothing else in the file moves.  The one thing outside the macro call
    that can is the second argument of the paragraph's \\parstart, which is
    the opening of this text and nothing but: when an fa in the paragraph's
    first subparagraph changes, the contents entry follows it (the docstring
    says why, and when it does not).  words set on a \\ch or \\chr, or blanked
    on a \\chw or \\chrw, change the macro's NAME with them, and then the one
    call is written again whole -- every other field as it was -- instead of
    group by group.

    Returns {path, index, macro, changed, fidelity, parstart, warnings,
    chunk} -- `macro` the name the chunk has now, `changed` the fields that
    actually differed (empty when the values were already there and the file
    was left alone), `fidelity` what verify_book.py would now say about the
    paragraph, `parstart` what became of the contents entry ("updated: ...",
    "not changed: ...", or "behind: ..." for an anchor written by hand, which
    is left as it is), `warnings` what wordline.check says of the chunk's
    words without refusing them, `chunk` the record read back off the new
    file.

    Raises Refused for an index the file does not have, a colour that is not
    one of the four, a field the macro has no slot for, a kana in a language
    with no reading, words in a language with no word layer, anything
    check_batch.py would reject in a field, a character that is not text, a
    word line that does not rejoin the chunk's text as it stands after the
    edit, an fa that would stop the paragraph reproducing its source, and
    emptying a field the language requires (en; tr where it romanises; kana
    where it has a reading) that holds something -- unless every box of the
    gloss is emptied with it, which deletes the gloss and leaves the chunk
    as one nobody has started (_check_required).  Filling the boxes one at
    a time is never refused: a chunk with part of its gloss written is saved
    as it is.  A \\chw or \\chrw whose gloss is emptied keeps its word line
    and its macro.  A word line edited on a chunk nobody has glossed yet
    takes its proposed reading with it: the reading lib/draft.py proposed
    from the old line is proposed again from the new one (and goes when the
    line is taken off), so the chunk stays blank -- unless the edit sends
    that reading too, which is then the person's.
    """
    if not isinstance(fields, dict):
        raise Refused("fields must be a dict of any of %s" % ", ".join(FIELDS))
    unknown = sorted(k for k in fields if k not in FIELDS)
    if unknown:
        raise Refused("no such field: %s -- a chunk has %s"
                      % (", ".join(map(repr, unknown)), ", ".join(FIELDS)))
    book = _book_of(path)
    lang = _lang_of(path, lang, book)
    # a book read out of its written order (kanbun) is not warned that its
    # words and its readings disagree
    reorders = bool(book.meta.get("reorders")) if book is not None else False
    text = _read(path)
    calls = _scan(text, path)
    if isinstance(index, bool) or not isinstance(index, int) \
            or not 0 <= index < len(calls):
        raise Refused("there is no chunk %r in %s: it holds %s"
                      % (index, os.path.basename(path),
                         "%d, numbered 0 to %d" % (len(calls), len(calls) - 1)
                         if calls else "no chunks at all"))
    call = calls[index]
    slots = SLOTS[call.name]
    old = _values(text, call)
    where = "%s:%d chunk %d" % (os.path.basename(path), call.line + 1, index)
    # A per cent sign inside the call is where read_group and LaTeX part
    # company: read_group reads it as text, LaTeX comments out the rest of the
    # line and the arguments left on it with it.  The chunk this file would
    # splice into is then not the chunk the PDF sets, so it is not spliced
    # into at all.  Nothing the pipeline writes can hold one -- check_batch
    # rejects a per cent sign in every field, escaped as well as raw -- so
    # this fires only on a file that is already wrong, and says where.
    if texesc.raw_percent(text, call.start, call.end) >= 0:
        raise Refused("%s: there is a per cent sign inside the macro call, so "
                      "LaTeX and this file disagree about where the chunk ends "
                      "-- take it out by hand before editing here" % where)

    new = {}
    for f in FIELDS:                            # a fixed order, so the first
        if f not in fields:                     # refusal does not depend on
            continue                            # how the caller built the dict
        if f == "kana" and not lang.reading:
            raise Refused("%s: %s has no reading, so a chunk carries no kana "
                          "(docs/languages.md section 3)" % (where, lang.name))
        if f == "words":
            # not a slot to look for: a chunk without words has a macro with
            # them, and the name changes below
            if not lang.words:
                raise Refused("%s: %s has no word layer, so a chunk carries no "
                              "words (docs/languages.md section 3)"
                              % (where, lang.name))
            if _form(call.name, True) is None:
                raise Refused("%s: \\%s has no words slot; it takes %s -- \\chp "
                              "is the unglossed chunk"
                              % (where, call.name, ", ".join(slots)))
        elif f not in slots:
            extra = (" -- a chunk with a reading is written \\%s"
                     % _form("chr", "words" in slots) if f == "kana"
                     else " -- \\chp is the unglossed chunk" if call.name == "chp"
                     else "")
            raise Refused("%s: \\%s has no %s slot; it takes %s%s"
                          % (where, call.name, f, ", ".join(slots), extra))
        new[f] = _value(f, fields[f], lang, where)
    # A WORD LINE EDITED UNDER A PROPOSED READING.  A chunk nobody has
    # glossed yet may carry the reading lib/draft.py proposed from its line
    # (_unglossed: kana where the language has a reading, tr where it has
    # not).  The reader's chunk sheet sends only "words" when the line alone
    # is edited -- a boundary moved, a reading corrected -- and merged with
    # the OLD reading, the chunk would hold a reading that is no longer what
    # its NEW line proposes: written, then, though nobody wrote a gloss --
    # check_batch's "empty en" ERROR on a chunk nobody glossed, "delete
    # gloss" offered on it, and the region fill passing it over as glossed.
    # So the reading is proposed again from the new line, as divide_preview,
    # split_chunk and merge_chunks already propose it for each chunk they
    # make (_unseeded, _seeded): the chunk stays blank, carrying its new
    # line's reading, and a line taken off (words "") takes that proposal
    # with it.  Only when the page did not send the reading itself -- a
    # reading typed in the same edit is the person's -- and only on a chunk
    # that was blank with its reading still the old line's proposal.
    if "words" in new:
        _bare, seed_field = _unseeded(old, lang)
        if seed_field and seed_field not in new and seed_field in slots:
            proposed = _seeded(dict(old, words=new["words"]), seed_field, lang)
            new[seed_field] = _value(seed_field, proposed.get(seed_field, ""),
                                     lang, where)
    merged = dict(old, **new)
    _check_required(new, old, merged, lang, where)
    # The arity is in the name: words given to a chunk without them make it
    # the macro with them, and words taken away make it the macro without.
    name = _form(call.name, bool(new["words"])) if "words" in new else call.name
    merged = {f: merged.get(f, "") for f in SLOTS[name]}

    changed = [f for f in FIELDS if f in new and new[f] != old.get(f, "")]
    if name != call.name and "words" not in changed:
        changed.append("words")         # a \chw{...}{} written by hand, blanked
    if not changed:
        return {"path": os.path.abspath(path), "index": index, "macro": call.name,
                "changed": [], "fidelity": "not checked: nothing changed",
                "parstart": "not checked: nothing changed", "warnings": [],
                "chunk": _record(text, index, call)}
    # The whole chunk, not the field: a word line is its text divided, so an
    # fa changed under one that no longer rejoins it is refused here -- before
    # fidelity, whose complaint about the same fa would not mention the words.
    warnings = _words_fit(merged, lang, reorders, where, written=new)
    note = (_fidelity(path, text, calls, index, {index: [new["fa"]]}, lang)
            if "fa" in changed else "not checked: fa unchanged")
    # The contents entry is derived from this text, so it moves with it (the
    # docstring says why here rather than in an answer nobody has to read).
    # After _fidelity, so an fa that would break the paragraph is refused
    # before anything has been worked out about the anchor.
    ps, ps_note = ((None, "not checked: fa unchanged") if "fa" not in changed
                   else _parstart_edit(text, calls, index, {index: [new["fa"]]}, lang))

    # The regions this edit is allowed to touch: the argument groups that
    # changed -- or the one call whole, when its name changes with its words,
    # as a merge writes one -- and at most one \parstart incipit.  Proved
    # before the file is written rather than trusted: `out` is `text` with
    # exactly these regions replaced (_splice), and reading it back with the
    # same walk gives the same chunks with this one changed, under the name
    # asked for, and no other (_proved).  A chapter written by hand can hold
    # something this file has not met, and the guarantee is worth more than
    # the edit.
    if name == call.name:
        regions = [(a, b, _tex(f, new[f])) for f, (a, b) in zip(slots, call.args)
                   if f in changed]
    else:
        regions = [(call.start, call.end, _render(name, merged))]
    out = _splice(text, regions + ([ps] if ps else []), where,
                  "the chunk and the \\parstart of its paragraph" if ps
                  else "the chunk")
    got = _proved(path, text, calls, out, index, 1, 1, [(name, merged)], where)
    _write(path, out)
    return {"path": os.path.abspath(path), "index": index, "macro": name,
            "changed": changed, "fidelity": note, "parstart": ps_note,
            "warnings": warnings, "chunk": _record(out, index, got[index])}


# --- where a chunk ends -------------------------------------------------
def _render(name, values):
    """One macro call as the pipeline writes it: the macro, then its argument
    groups run together with nothing between them -- which is what
    assemble.py writes and what every chapter of every book already has."""
    return "\\" + name + "".join("{%s}" % _tex(f, values.get(f) or "")
                                 for f in SLOTS[name])


def _named(raw, where):
    """A call's values with the colour under the name a person uses, ready for
    chunkdiv.  A colour slot holding something that is not one of the four is
    refused rather than read as no colour: it was written by a hand, and
    dropping it silently is exactly what this file does not do."""
    d = dict(raw)
    tex = (raw.get("col") or "").strip()
    if tex and tex not in _COLOUR_OF:
        raise Refused("%s: the colour slot holds %r, which is none of %s -- "
                      "somebody wrote it by hand, so this is not the file's to "
                      "move" % (where, tex, ", ".join(COLOURS)))
    d["col"] = _COLOUR_OF.get(tex, "")
    return d


def _indent_of(text, pos):
    """The whitespace opening the line `pos` is on, when that is all there is
    before it -- so a chunk written on its own line stays on its own line, at
    the indent the chapter uses."""
    nl = text.rfind("\n", 0, pos) + 1
    head = text[nl:pos]
    return head if head and not head.strip() else ""


def _alone(text, start, end, where):
    """Refuse when anything but whitespace shares the lines these calls are on.

    verify_book.py reads a chunk with a line-anchored regex (CHUNK_RE.match on
    each line, after its indent), so a call that does not open its own line
    is a call it cannot see and a paragraph it cannot rebuild.  Dividing a
    chunk writes a line, and joining two takes one away; both leave the lines
    around them exactly as they were only if there was nothing else on them.
    A chapter that already puts two chunks on one line is left for a hand to
    sort out rather than relaid out here.
    """
    head = text[text.rfind("\n", 0, start) + 1:start]
    nl = text.find("\n", end)
    tail = text[end:nl if nl >= 0 else len(text)]
    if head.strip() or tail.strip():
        raise Refused("%s: something else is on the line with %s (%r), and "
                      "verify_book.py reads one chunk per line -- move it "
                      "before dividing them here"
                      % (where, "these chunks" if head.strip() and tail.strip()
                         else "this chunk", (head.strip() or tail.strip())[:60]))


def _no_percent(text, start, end, where):
    """edit_chunk's rule, applied to a stretch of the file rather than to one
    call: LaTeX reads a per cent sign as the end of the line and this file
    does not, so where there is one the two disagree about where a chunk ends
    and nothing here may touch it.  An escaped one, \\%, is text to both
    (lib/texesc.py): it is how "50%" is written."""
    if texesc.raw_percent(text, start, end) >= 0:
        raise Refused("%s: there is a per cent sign in these chunks, so LaTeX "
                      "and this file disagree about where they end -- take it "
                      "out by hand before dividing them here" % where)


def _splice(text, regions, where, what):
    """`text` with each (start, end, replacement) put in, proved rather than
    trusted: what comes back is `text` with exactly these regions replaced by
    exactly these strings, and every byte between, before and after them is
    the byte that was there.  edit_chunk's own arithmetic, lifted out because
    three operations now do it."""
    regions = sorted(regions)
    out, spans, shift, last = text, [], 0, 0
    for a, b, s in regions:
        if a < last:
            raise Refused("%s: refusing -- %s overlap in the file" % (where, what))
        spans.append((a + shift, a + shift + len(s)))
        shift += len(s) - (b - a)
        last = b
    for a, b, s in reversed(regions):
        out = out[:a] + s + out[b:]
    if _outside(out, spans) != _outside(text, [(a, b) for a, b, _ in regions]) \
            or [out[a:b] for a, b in spans] != [s for _, _, s in regions]:
        raise Refused("%s: refusing -- the edit reached outside %s" % (where, what))
    return out


def _proved(path, text, calls, out, index, gone, made, expect, where):
    """The new file read back with the same walk, and every chunk that was not
    meant to change proved unchanged.

    `gone` is how many calls the operation consumed at `index`, `made` how
    many it put there, and `expect` the values those new ones must have.  A
    chapter written by hand can hold something this file has not met, and the
    guarantee is worth more than the edit -- so the arithmetic is not trusted
    even once it has been checked.
    """
    got = _scan(out, path)
    if len(got) != len(calls) - gone + made:
        raise Refused("%s: refusing -- the edit would turn %d chunks into %d, "
                      "not %d" % (where, len(calls), len(got),
                                  len(calls) - gone + made))
    for k in range(index):
        if got[k].name != calls[k].name or _values(out, got[k]) != _values(text, calls[k]):
            raise Refused("%s: refusing -- the edit would change chunk %d as well"
                          % (where, k))
    for k in range(made):
        want_name, want = expect[k]
        if got[index + k].name != want_name or _values(out, got[index + k]) != want:
            raise Refused("%s: refusing -- chunk %d did not come out as asked"
                          % (where, index + k))
    for k in range(index + gone, len(calls)):
        j = k - gone + made
        if got[j].name != calls[k].name or _values(out, got[j]) != _values(text, calls[k]):
            raise Refused("%s: refusing -- the edit would change chunk %d as well"
                          % (where, k))
    return got


def _open(path, index, lang, n_at_least=1):
    """The file, its calls, the language, the reorders flag and a checked
    index.  The three operations begin the same way and this is that
    beginning."""
    book = _book_of(path)
    lang = _lang_of(path, lang, book)
    reorders = bool(book.meta.get("reorders")) if book is not None else False
    text = _read(path)
    calls = _scan(text, path)
    top = len(calls) - n_at_least
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < top + 1:
        raise Refused("there is no chunk %r to work on in %s: it holds %s"
                      % (index, os.path.basename(path),
                         "%d, numbered 0 to %d" % (len(calls), len(calls) - 1)
                         if calls else "no chunks at all"))
    return text, calls, lang, reorders


def _fields_for(name, values, lang, reorders, where):
    """Every slot of one macro, checked as edit_chunk checks the ones it is
    given -- because a chunk that has just come into being has all of them
    written, and none of them was there before to fall back on.  `name` is
    _name_for's, so a word line is never handed to a macro with no slot for
    it.  Returns the values and what wordline.check warns of them.

    What each value may HOLD is checked; which of them are FILLED is not.
    Cutting a chunk or joining two moves a boundary, and the gloss comes
    along as it was: a half glossed chunk divides into halves that may be
    blank, half glossed or complete, and none of that is the cut's to refuse
    -- check_batch lists a half-glossed chunk, and the chunk sheet is where
    it is finished.  A blank chunk is proposed as two blank halves, its
    reading from the word line proposed again for each (divide_preview,
    _unseeded); what is written is what the page sends back."""
    new = {}
    for f in SLOTS[name]:
        if f == "kana" and not lang.reading:
            raise Refused("%s: %s has no reading, so a chunk carries no kana"
                          % (where, lang.name))
        new[f] = _value(f, values.get(f) or "", lang, where)
    return new, _words_fit(new, lang, reorders, where)


def _mergeable(text, calls, index, path):
    """Everything that must be true before two chunks may be joined into one,
    asked without writing anything -- so that a preview can show the button
    greyed out with the reason on it rather than offering an edit that will be
    refused.  Returns (first, second, where); raises Refused with the reason.
    """
    first, second = calls[index], calls[index + 1]
    where = "%s:%d chunks %d and %d" % (os.path.basename(path), first.line + 1,
                                        index, index + 1)
    _no_percent(text, first.start, first.end, where)
    _no_percent(text, second.start, second.end, where)
    _alone(text, first.start, first.end, where)
    _alone(text, second.start, second.end, where)
    # \ch and \chw are one kind of chunk with and without a word line, as \chr
    # and \chrw are, and join: a line on one side only is dropped, and
    # chunkdiv.merge says so
    if _form(first.name, False) != _form(second.name, False):
        raise Refused("%s: one is \\%s and the other \\%s -- a chunk with a "
                      "reading, a plain one and a glossed one are not the same "
                      "kind of thing" % (where, first.name, second.name))
    if (first.label or "") != (second.label or ""):
        raise Refused("%s: they are in different subparagraphs (%s and %s), and "
                      "a subparagraph is a unit of the text rather than of the "
                      "gloss" % (where, first.label or "none", second.label or "none"))
    gap = text[first.end:second.start]
    if gap.strip():                             # a comment, a macro, anything
        raise Refused("%s: there is something between them in the file (%r) -- "
                      "it would be lost, so the merge is refused rather than "
                      "made" % (where, gap.strip()[:60]))
    return first, second, where


def _join(first, second, lang):
    """chunkdiv.merge of two chunks, (chunk, notes) -- with the proposed
    reading of a pair nobody has glossed yet proposed again for the chunk
    they become (_unseeded says why), so that two blank chunks join into one
    blank chunk even where a line on one side only is dropped.  A pair with
    anything written in either is joined as it stands."""
    a, fa_ = _unseeded(first, lang)
    b, fb_ = _unseeded(second, lang)
    if (fa_ or fb_) and _unglossed(first, lang) and _unglossed(second, lang):
        one, notes = chunkdiv.merge(a, b, lang, chunkdiv.TEX)
        return _seeded(one, fa_ or fb_, lang), notes
    return chunkdiv.merge(first, second, lang, chunkdiv.TEX)


def divide_preview(path, index, lang=None):
    """What a page needs to offer both operations on one chunk, worked out
    here so that the rules live in one place and the page only draws them.

        {index, macro, chunk, cuts, next, merge, merge_error}

    `cuts` is every place the chunk divides, each already carrying the two
    chunks it would become; `merge` is the chunk the next one would join it
    into, or None with `merge_error` saying why they cannot be joined.  A
    proposal and nothing more: what is written is what comes back POSTed.
    """
    text, calls, lang, _reorders = _open(path, index, lang)
    call = calls[index]
    where = "%s:%d chunk %d" % (os.path.basename(path), call.line + 1, index)
    mine = _named(_values(text, call), where)
    out = {"index": index, "macro": call.name,
           "chunk": _record(text, index, call), "cuts": [], "next": None,
           "merge": None, "merge_error": None,
           "voc_sep": chunkdiv.VOC_SEP[chunkdiv.TEX],
           "pieces": chunkdiv.pieces(mine.get("fa") or "", lang)}
    # a blank chunk's proposed reading is proposed again for each half
    bare, seeded = _unseeded(mine, lang)
    for c in chunkdiv.cuts(mine.get("fa") or "", lang):
        try:
            a, b, notes = chunkdiv.split(bare, c["at"], lang, chunkdiv.TEX)
        except wordline.WordsError as e:
            # a line written by hand that does not read cannot be divided:
            # the halves are proposed without one rather than not at all
            a, b, notes = chunkdiv.split(dict(bare, words=""), c["at"], lang,
                                         chunkdiv.TEX)
            notes.append("the word line does not read (%s), so neither half "
                         "has words until it is divided into words again" % e)
        a, b = _seeded(a, seeded, lang), _seeded(b, seeded, lang)
        out["cuts"].append({"at": c["at"], "end": c["end"],
                            "a": c["a"], "b": c["b"],
                            "first": a, "second": b, "notes": notes,
                            "entries": chunkdiv.entries_for(mine, c["at"],
                                                            lang, chunkdiv.TEX)})
    if index + 1 >= len(calls):
        out["merge_error"] = ("chunk %d is the last of %s: there is nothing "
                              "after it to join it to"
                              % (index, os.path.basename(path)))
        return out
    out["next"] = _record(text, index + 1, calls[index + 1])
    try:
        first, second, w = _mergeable(text, calls, index, path)
        one, notes = _join(_named(_values(text, first), w),
                           _named(_values(text, second), w), lang)
        out["merge"] = {"fields": one, "notes": notes}
    except Refused as e:
        out["merge_error"] = str(e)
    except ValueError as e:                     # chunkdiv on two unlike chunks
        out["merge_error"] = str(e)
    return out


@pathlock.serialised(_book_folder)
def merge_chunks(path, index, fields=None, lang=None):
    """Join chunk `index` and the one after it into one chunk.

    The two must be the same kind of macro -- \\ch or \\chw with either, \\chr
    or \\chrw with either -- under the same \\parnum, with nothing but
    whitespace between them in the file -- which is the same as saying they
    are two chunks of one subparagraph and nothing has been written between
    them.  A comment line between two chunks (a narration's `% @par`) is
    something, and stops the merge rather than being swallowed by it.

    `fields` is the merged chunk's values, col by name; when it is None
    chunkdiv.merge works them out -- the texts end to end with the language's
    word separator, the romanisations and meanings with a space, the
    vocabulary with its own semicolon, two word lines with a space and one
    word line alone not at all -- and the notes it returns come back with the
    result; two chunks nobody has glossed yet join into one, their proposed
    reading proposed again from the joined line (_join).  The merged chunk
    is written with words exactly when it has them.  A merge cannot break the paragraph's fidelity to its source (the
    join is the string it was), and the check is run anyway.

    Returns {path, index, macro, fidelity, parstart, notes, warnings, chunk,
    chunks}: `chunks` how many the file holds now, `notes` what could not
    simply be put end to end, `warnings` what wordline.check says of the
    words.  Raises Refused for everything edit_chunk refuses in a value, for
    two chunks that are not a pair this may join, and for `fields` that say
    nothing of words when both chunks have a line -- blank takes them off,
    silence is a caller that has not heard of them.  Never for a gloss left
    blank: the joined chunk may be unglossed, half glossed or complete
    (_fields_for says why).
    """
    text, calls, lang, reorders = _open(path, index, lang, n_at_least=2)
    first, second, where = _mergeable(text, calls, index, path)

    a_raw, b_raw = _values(text, first), _values(text, second)
    if fields is None:
        merged, notes = _join(_named(a_raw, where), _named(b_raw, where), lang)
    else:
        if not isinstance(fields, dict):
            raise Refused("fields must be a dict of any of %s" % ", ".join(FIELDS))
        unknown = sorted(k for k in fields if k not in FIELDS)
        if unknown:
            raise Refused("no such field: %s -- a chunk has %s"
                          % (", ".join(map(repr, unknown)), ", ".join(FIELDS)))
        # split_chunk's rule: two lines the join would keep, and fields that
        # do not mention words at all, are a caller that has not heard of
        # them -- not one taking them off (a line on one side only is dropped
        # by the proposal as well, so that join is written as it comes)
        if "words" not in fields and (a_raw.get("words") or "").strip() \
                and (b_raw.get("words") or "").strip():
            raise Refused("%s: both chunks are divided into words and the joined "
                          "chunk says nothing of them -- send its words "
                          "(divide_preview joins the two lines), or send them "
                          "blank to take them off" % where)
        merged, notes = dict(fields), []
    name = _name_for(first.name, merged, lang, where)
    new, warnings = _fields_for(name, merged, lang, reorders, where)
    # A join changes no letter, as a cut does not: the text must be the two
    # texts run together with the language's separator.  Without this the
    # promise above holds only for a page that behaves, and a paragraph the
    # fidelity check cannot judge -- no \parnum, no source/paras/ file, or one
    # that did not reproduce before either -- would take whatever was sent.
    want = (lang.word_sep or "").join(
        [a_raw["fa"].rstrip(), b_raw["fa"].lstrip()]).strip()
    if _norm(lang.strip(new["fa"]), lang) != _norm(lang.strip(want), lang):
        raise Refused("%s: this text is not the two texts joined -- a join "
                      "moves the boundary and changes no letter, and "
                      "edit_chunk is what changes one\n        joined: %s\n"
                      "        sent:   %s" % (where, want, new["fa"]))

    swap = {index: [new["fa"]], index + 1: []}
    note = _fidelity(path, text, calls, index, swap, lang)
    ps, ps_note = _parstart_edit(text, calls, index, swap, lang)

    line = _render(name, new)
    out = _splice(text, [(first.start, second.end, line)] + ([ps] if ps else []),
                  where, "the chunks and the \\parstart of their paragraph")
    got = _proved(path, text, calls, out, index, 2, 1, [(name, new)], where)
    _write(path, out)
    return {"path": os.path.abspath(path), "index": index, "macro": name,
            "fidelity": note, "parstart": ps_note, "notes": notes,
            "warnings": warnings, "chunks": len(got),
            "chunk": _record(out, index, got[index])}


@pathlock.serialised(_book_folder)
def split_chunk(path, index, first, second, lang=None):
    """Cut chunk `index` into the two chunks given, in that order.

    `first` and `second` are whole chunks -- every slot the macro has, col by
    name -- because a chunk that has just come into being has nothing to fall
    back on.  chunkdiv.split proposes them from a cut offset; what arrives
    here is what somebody looked at and typed over, and it is checked from
    scratch: their two texts joined with the language's word separator must be
    the chunk's own, each half's words must rejoin its own text, and the
    paragraph must still reproduce its source.  Each half is written with
    words (\\chw, \\chrw) exactly when it has them; a chunk with a line whose
    halves neither of them mention words is refused, not stripped of it.

    The two are written on two lines at the chunk's own indent, so a chapter
    goes on looking like a chapter and the diff is the two lines the hand
    would have made.

    Returns {path, index, macro, fidelity, parstart, warnings, chunks, first,
    second}.
    """
    text, calls, lang, reorders = _open(path, index, lang)
    call = calls[index]
    where = "%s:%d chunk %d" % (os.path.basename(path), call.line + 1, index)
    _no_percent(text, call.start, call.end, where)
    _alone(text, call.start, call.end, where)
    for side, name in ((first, "first"), (second, "second")):
        if not isinstance(side, dict):
            raise Refused("the %s chunk must be a dict of any of %s"
                          % (name, ", ".join(FIELDS)))
        unknown = sorted(k for k in side if k not in FIELDS)
        if unknown:
            raise Refused("no such field on the %s chunk: %s -- a chunk has %s"
                          % (name, ", ".join(map(repr, unknown)), ", ".join(FIELDS)))
    # A half sent with words blank is a half without them, and says so.  A
    # half sent with no words key at all, on BOTH sides of a chunk that has a
    # line, says nothing: that is a caller written before chunks had words
    # (the reader's divide sheet sends the boxes it draws), and the line
    # would be gone from the file without a word to anybody.
    if (_values(text, call).get("words") or "").strip() \
            and "words" not in first and "words" not in second:
        raise Refused("%s: this chunk is divided into words and neither half "
                      "says what becomes of them -- send words for each half "
                      "(divide_preview proposes them), or send them blank to "
                      "take them off" % where)
    na = _name_for(call.name, first, lang, where + ", first half")
    nb = _name_for(call.name, second, lang, where + ", second half")
    a, wa = _fields_for(na, first, lang, reorders, where + ", first half")
    b, wb = _fields_for(nb, second, lang, reorders, where + ", second half")

    # The two texts must be one of the places this chunk divides, character
    # for character.  Comparing what the checkers compare would be too weak
    # here: they strip the harakat before they look, so a cut that fell inside
    # a Persian word -- leaving a bare kasra opening the second chunk -- would
    # pass every one of them and set a PDF nobody meant.  A split divides; it
    # does not rewrite, and editing a half is edit_chunk's to do afterwards.
    was = _values(text, call)["fa"]
    places = chunkdiv.cuts(was, lang)
    if [a["fa"], b["fa"]] not in [[c["a"], c["b"]] for c in places]:
        raise Refused(
            "%s: these two texts are not this chunk divided in two -- a split "
            "moves the boundary and changes no letter, and edit_chunk is what "
            "changes one\n        chunk:  %s\n        halves: %s | %s\n"
            "        the places it divides: %s"
            % (where, was, a["fa"], b["fa"],
               " | ".join("%s / %s" % (c["a"], c["b"]) for c in places) or "none"))

    swap = {index: [a["fa"], b["fa"]]}
    note = _fidelity(path, text, calls, index, swap, lang)
    ps, ps_note = _parstart_edit(text, calls, index, swap, lang)

    indent = _indent_of(text, call.start)
    # the file's own line ending, not this file's taste: _read and _write keep
    # CRLF on purpose, and a lone LF spliced into a CRLF chapter is a line
    # ending nothing else in it has
    nl = "\r\n" if "\r\n" in text else "\n"
    two = _render(na, a) + nl + indent + _render(nb, b)
    out = _splice(text, [(call.start, call.end, two)] + ([ps] if ps else []),
                  where, "the chunk and the \\parstart of its paragraph")
    got = _proved(path, text, calls, out, index, 1, 2, [(na, a), (nb, b)], where)
    _write(path, out)
    return {"path": os.path.abspath(path), "index": index, "macro": call.name,
            "fidelity": note, "parstart": ps_note,
            "warnings": ["first half: " + w for w in wa] +
                        ["second half: " + w for w in wb],
            "chunks": len(got),
            "first": _record(out, index, got[index]),
            "second": _record(out, index + 1, got[index + 1])}


# --- the book ------------------------------------------------------------
def _main_of(book):
    """main.tex, from a books.Book, a book directory, or the path itself.
    book.json may name another file under "main", so it is asked."""
    if isinstance(book, books.Book):
        return book.main
    p = os.path.abspath(book)
    if not os.path.isdir(p):
        return p
    if not os.path.isfile(os.path.join(p, "book.json")):
        return os.path.join(p, "main.tex")
    try:
        return books.Book(p).main
    except (OSError, ValueError) as e:
        raise Refused("%s: book.json will not read (%s)" % (p, e))


def book_chapters(book):
    """Which chapter files a book has and how many chunks each holds.

        [{"file": "ch1.tex", "path": "...", "chapter": 1, "chunks": 2712,
          "glossed": 2708, "first": 0, "last": 2711}]

    In the order main.tex \\inputs them, which is the order texparse.parse_book
    reads them and so the order tex2html numbers the whole book's chunks in:
    `first` is the number the reader's data-c gives this file's chunk 0, so a
    server holding a book-wide index finds the file it belongs to and
    subtracts.  The two tests -- the file exists and carries \\begin{frank} --
    are parse_book's, because a file it skips is a file the reader never
    numbered.  `chapter` is the number in the name, which is what names the
    paragraphs under source/paras/ (ch1.tex and ch1b.tex are both chapter 1).
    """
    main = _main_of(book)
    if not os.path.isfile(main):
        raise Refused("no %s to read the chapter order from" % main)
    base = os.path.dirname(os.path.abspath(main))
    with io.open(main, encoding="utf-8") as f:
        src = f.read()
    out, n = [], 0
    for line in src.split("\n"):
        if line.lstrip().startswith("%"):
            continue
        m = re.search(r"\\input\{([^}]+)\}", line)
        if not m:
            continue
        path = os.path.join(base, m.group(1))
        if not os.path.exists(path):
            continue
        text = _read(path)
        # main.tex also inputs the preamble and the front matter; a chapter is
        # a file that actually carries text, and \begin{frank} appears only in
        # one -- the preamble merely defines the environment
        if "\\begin{frank}" not in text:
            continue
        calls = _scan(text, path)
        out.append({"file": os.path.basename(path), "path": os.path.abspath(path),
                    "chapter": _chapter_no(path), "chunks": len(calls),
                    "glossed": sum(1 for c in calls if c.name != "chp"),
                    "first": n if calls else None,
                    "last": n + len(calls) - 1 if calls else None})
        n += len(calls)
    return out


if __name__ == "__main__":
    # Reading only: an edit belongs to a caller that has something to say
    # about who made it, so no shell line can rewrite a chapter by accident.
    #   texwrite.py <book dir or main.tex>       the chapters and their counts
    #   texwrite.py <chapter.tex> [index]        the chunks, or one in full
    arg = sys.argv[1] if len(sys.argv) > 1 else "."
    if os.path.isdir(arg) or os.path.basename(arg) == "main.tex":
        rows = book_chapters(arg)
        for r in rows:
            print("%-12s chapter %-3s %5d chunks (%d glossed)  data-c %s..%s"
                  % (r["file"], r["chapter"], r["chunks"], r["glossed"],
                     r["first"], r["last"]))
        print("total: %d chunks in %d files" % (sum(r["chunks"] for r in rows), len(rows)))
    else:
        cs = read_chunks(arg)
        if len(sys.argv) > 2:
            c = cs[int(sys.argv[2])]
            for k in ("index", "macro", "line", "label", "para", "col", "col_tex",
                      "fa", "kana", "tr", "voc", "en", "words", "span"):
                print("%-8s %s" % (k, c[k]))
        else:
            for c in cs:
                print("%4d  %-4s %-7s %s" % (c["index"], c["macro"], c["col"], c["fa"]))
            print("%d chunks [%s]" % (len(cs), _lang_of(arg).code))
