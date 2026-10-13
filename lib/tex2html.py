#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage 2 — build the audio-synced reader from the same .tex files.

    python3 tex2html.py            -> reader/index.html

Chapter order comes from the \\input lines of the book's main.tex; there is no
list of chapters anywhere else.  Every word of the text, transliteration,
vocabulary and meaning is read out of the .tex at build time and appears in
exactly one place in this program: the chunk it came from.  Passes 3 and 4 are
derived by stripping the language's marks, the same way frank_strip does in
LaTeX.

The page also carries SRC, one entry per chunk in data-c order, holding those
same fields AS THE .tex WRITES THEM.  That is the one deliberate second copy
here, and it is what the edit boxes are filled from: the page shows the
vocabulary rendered (\\dw{water}{ab} becomes two runs and a space), so the
source of that field cannot be read back out of the DOM, and an author handed
the rendering to edit is being handed something that is not in the file.  The
edit itself is the server's -- POST <reader>/__edit/chunk, which validates,
rewrites the one macro call and rebuilds this page -- and the answer, whether
it applied or refused, is shown in the words it arrived in.  A stretch of the
book glossed by an LLM goes through the same door, chunk by chunk: the page
asks <reader>/__region/prompt for the prompt to copy and hands the pasted
answer to <reader>/__region/apply, and lib/glossregion.py decides there, from
the files, what may be written.

The book's language (books.Book.lang, from book.json; Persian when undeclared)
decides everything that is not layout: the lang/dir attributes, which passes
exist and what the buttons say, the digits of the labels, how a chunk splits
into words, whether pass 1 carries a reading (<ruby>) and the gloss a kana
line, the font tokens the stylesheet reads (--tl-font, --tl-alt, from
/lib/langs.css keyed by data-lang on <html>).  Nothing in this file names a
language: the record is embedded as LANG for the script, and the CSS is
written against dir attributes and the tokens.

The book's SECOND language is what its glosses are written in
(books.Book.gloss_lang, book.json's "gloss"; English when it says nothing,
which is every book written before the field existed).  It decides what the
gloss row and the two sheets carry -- their lang and dir, and the name the
meaning field wears -- and it is embedded as GLOSS beside LANG.  The two are
different questions: an Italian learning English reads English chunks glossed
in Italian (docs/languages.md section 3).
"""
import argparse
import html
import json
import os
import re
import sys

import hashlib
import time

LIB = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, LIB)
import texparse as T                                           # noqa: E402
import languages                                               # noqa: E402
import reading                                                 # noqa: E402
import structure                                               # noqa: E402
import wordline                                                # noqa: E402
from timestamp import subkey                                   # noqa: E402
from books import find_book, FONTS, ROOT, BOOKS_DIR            # noqa: E402

# The language of the book being built.  Set once by build() (from the Book);
# every helper below reads it rather than threading a parameter through a
# dozen signatures.  The default is Persian, as for every book that predates
# the registry, so the helpers work unchanged when called from a shell.
LANG = languages.get(languages.DEFAULT)
# What its glosses are written in.  English by default, for the same reason:
# that is what a book.json with no "gloss" means, and what every book in the
# toolbox means today.
GLOSS = languages.gloss(languages.DEFAULT_GLOSS)


def set_lang(lang):
    global LANG
    LANG = languages.get_or_default(lang) if isinstance(lang, str) or lang is None else lang
    return LANG


def set_gloss(gloss):
    """A Gloss, or a code (an unusable one falls back to English rather than
    raising: the reader has to render the book regardless, and
    books.Book.check_placement is what says the code is wrong)."""
    global GLOSS
    GLOSS = (languages.gloss_or_default(gloss)
             if isinstance(gloss, str) or gloss is None else gloss)
    return GLOSS

AT_T = re.compile(r"^%\s*@t\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\w+)")
# The sixth field is the narration the time was measured in, and it is
# optional: a book with one recording has always written five and still does,
# and this pattern reads such a line exactly as it did before.
AT_PAR = re.compile(r"^%\s*@par\s+(\S+)\s+([\d.]+)\s+([\d.]+)"
                    r"(?:\s+([\d.]+)\s+(\w+)(?:\s+(\S+))?)?")


def load_times(chapters):
    """Read the % @par comments back out of the files.

    Positional only: each comment belongs to the \\begin{frank} on the next
    real line.  Never keyed by label -- chapter 1 and chapter 2 both have a
    4.3, and a label-keyed lookup silently returns the wrong one.
    """
    for ch in chapters:
        raw = open(ch.path, encoding="utf-8").read().split("\n")
        per_line, pend = {}, []
        for i, ln in enumerate(raw):
            if AT_T.match(ln) or AT_PAR.match(ln):
                pend.append(ln)
                continue
            if pend:
                per_line[i] = pend
                pend = []
        for s in ch.subs:
            for cm in per_line.get(s.begin_line, []):
                m = AT_PAR.match(cm)
                if m:
                    s.t0, s.t1 = float(m.group(2)), float(m.group(3))
                    s.conf = float(m.group(4)) if m.group(4) else 1.0
                    s.src = m.group(5) or "anchor"
                    # "" for a book with one recording: the times are seconds
                    # into it, which is what they have always been
                    s.nid = m.group(6) or ""
    return chapters


# \ch's first argument, the highlight colour.  It reaches pass 1 only, exactly
# as in the PDF: the marks are for the attempt the reader makes before any help
# arrives, and must not give the answer away in the chunks or the bare naskh.
# Hexes match \definecolor in lib/frank-preamble.tex.
HL = {"\\Cred": "red", "\\Cblue": "blue",
      "\\Corange": "orange", "\\Cgreen": "green"}


def hl_class(col):
    """The css class for a chunk's colour, or '' when the slot is empty."""
    name = HL.get((col or "").strip())
    return (" hl-" + name) if name else ""


def esc(s):
    return html.escape(s, quote=True)


def fa(s, cls=""):
    """A run of the book's language inside Latin text, isolated with its own
    lang and dir (the video player's bdi, and what \\pw does in the PDF)."""
    return '<bdi%s%s>%s</bdi>' % (LANG.html_attrs(),
                                  (' class="%s"' % cls) if cls else "", esc(s))


def words(s):
    """A chunk's text with each word in its own span.

    The hover gloss belongs to the whole chunk, but an Anki card usually
    wants one word -- so a modifier-click needs to know which word is under
    the cursor, exactly as in the video player.  Display is unchanged: the
    spans are unstyled and the separator stays between them.  The split is
    the language's: a Japanese chunk, having no word separator, is one span.
    """
    return LANG.word_sep.join('<span class="wd">%s</span>' % esc(w)
                              for w in LANG.split_words(s))


def ruby(s, kana):
    """Pass 1 of a reading language: the chunk with its kana over the whole of
    it (group ruby -- the reading is of the chunk, never per character).  A
    chunk without a kana, or a language without readings, is the bare words.
    A chunk that carries a word line is drawn by worded() instead."""
    if not (LANG.reading and kana.strip()):
        return words(s)
    return '<ruby>%s<rt>%s</rt></ruby>' % (words(s), esc(kana.strip()))


def worded(s, line):
    """A chunk drawn from its word line: the text cut where its words end,
    one .wd per word carrying its token (data-w, what "I know this"
    remembers) and its place in the line (data-k), the word's own reading
    over it where it has one, and the text's whitespace between -- exactly
    the markup Parseh.readings().renderWords builds in the page, so the page
    shows it with no script and hides the known words' readings at load.

    None when there is nothing to draw it from -- no line, a language with no
    word layer, or a line that does not give the text back -- and the chunk
    is then drawn as it always was: never one ruby over the whole of it and
    another over its words."""
    if not (LANG.words and (line or "").strip()):
        return None
    try:
        pairs = wordline.parse(line)
        spans = wordline.align(s, pairs)
        # a word with no token (山(( is 山( and nothing to be known by)
        # falls back with the rest, as it does in the page
        keys = [wordline.token(w, r) for w, r in pairs]
    except wordline.WordsError:
        return None
    out = []
    for text, reading, k in spans:
        if k is None:
            out.append(esc(text))
            continue
        inner = ('<ruby>%s<rt>%s</rt></ruby>' % (esc(text), esc(reading))
                 if reading else esc(text))
        out.append('<span class="wd" data-w="%s" data-k="%d">%s</span>'
                   % (esc(keys[k]), k, inner))
    return "".join(out)


def seeded(c):
    """The reading a draft proposed for this chunk from its word line, when
    that proposal is all the chunk's gloss holds; "" for every other chunk.

    lib/draft.py gives a chunk of a language divided into words its reading
    from its word line -- the kana run together, or the words' pinyin where
    the language has no other reading (wordline.seed) -- and while it still
    says exactly that, nobody has written it: the checkers and the edit door
    count such a chunk as one nobody has glossed yet (check_batch.unwritten,
    texwrite._unglossed).  The page has to say the same, or "delete gloss"
    is offered on a chunk with no gloss and throws the proposal away.  So the
    row of such a chunk carries it (data-seed), worked out here by the one
    wordline.seed rather than by a copy of it in the page, and a rebuilt
    reader's rows bring it up to date after every write.

    Only where nothing else is written: once anything is, the reading counts
    as the chunk's own, and the attribute would be bytes for nothing."""
    if not c.glossed:
        return ""
    field, seed = wordline.seed({"words": c.wordline or ""}, LANG)
    if not field or not seed:
        return ""
    have = {"kana": c.kana, "tr": c.tr, "voc": c.voc, "en": c.en}
    if (have[field] or "").strip() != seed:
        return ""
    return "" if any((v or "").strip() for f, v in have.items() if f != field) else seed


def render_voc(voc):
    """The vocabulary line: each word of the language isolated, as \\pw does.

    \\dw and \\vb put a real space between the word and its romanisation;
    keep it, or the two collide as زندگیzendegi.
    """
    out = []
    prev = ""
    for kind, text in T.parse_voc(voc):
        # the join rule texparse.voc_text uses for the video line, slash and
        # colon included, so the reader, the PDF and the plain text agree:
        # `aux. \pw{avere}/\pw{essere}` is "avere/essere", not "avere / essere"
        if out and not prev.endswith((" ", "(", "\u2018", "/")) and not text.startswith(
                (" ", ",", ";", ")", ".", "\u2019", ":", "/")):
            out.append(" ")
        if kind == "fa":
            out.append(fa(text, "v"))
        elif kind == "em":                   # the italic romanisation
            out.append("<i>%s</i>" % esc(text))
        else:
            out.append(esc(text))
        prev = text
    return "".join(out)


def fa_digits(s):
    """Latin digits -> the language's own (Persian ۰-۹, Arabic ٠-٩; Latin
    stays Latin).  The book numbers itself in its digits; ids do not."""
    return LANG.to_native_digits(s)


def incipit(para, words=6, chars=14):
    """The first few words of a paragraph, as the reader first meets them.

    Pass 1 is the vocalised text, so that is what the contents shows: a line
    the eye can match against the page it is about to jump to.  Taken from the
    first subparagraph only — six words never reach the end of one.  A language
    without word separators has no words to count, so it gets its first
    characters instead, the chunks run together as the page shows them.
    """
    if not para.subs:
        return ""
    if not LANG.spaced:
        return LANG.word_sep.join(c.fa for c in para.subs[0].chunks)[:chars]
    return " ".join(" ".join(c.fa for c in para.subs[0].chunks).split()[:words])


def pass_class(p):
    """The CSS class of a pass record from the registry: vocal->p1,
    chunks->p2, bare->p3, alt->p4 with a second class saying which kind of
    alternate it is.  'nast' is Persian's name for a font alternate and is
    kept for every language with one, because the stylesheet and every built
    Persian reader use it; a vertical alternate is 'vert'.  aloud, the
    reading alone of a language whose chunks carry words, came later and is
    p5 wherever it stands in the row: renumbering the others would have
    changed every built reader and every reader's stored pass toggles."""
    base = {"vocal": "p1", "chunks": "p2", "bare": "p3", "alt": "p4",
            "aloud": "p5"}[p["key"]]
    if p["key"] == "alt":
        base += " vert" if p.get("kind") == "vertical" else " nast"
    return base


def chapter_no(path):
    """The chapter a file belongs to, from its NAME -- ch1.tex and ch1b.tex
    are both chapter 1.

    verify_book.chapter_of and texwrite._chapter_no read it the same way, and
    they must: a paragraph is named "<chapter>:<paragraph>" in reading.json,
    and a key made from the chapter's LABEL (which is the book's own digits,
    ۱ for Persian) would name a different paragraph than the checkers exempt.
    """
    m = re.match(r"ch(\d+)", os.path.basename(path or ""))
    return int(m.group(1)) if m else None


def build(chapters, lang=None, gloss=None):
    """The <main> of the reader, plus the chunk times, the subparagraph
    times, the contents entries and every chunk's source.  `lang` is the
    book's Lang (default Persian); it fixes which passes are emitted and
    every attribute.  `gloss` is what the meanings are written in (default
    English), which decides the gloss row's own lang and dir.

    Last comes the same <main> cut where its chapters already are -- the
    sections in order as (chapter index, markup) pairs, and the one gap that
    closes the book -- which is what main() writes out as the per-chapter
    files a big book is read one piece at a time from.  The pieces are not
    a second rendering of anything: they are these very strings.
    """
    if lang is not None:
        set_lang(lang)
    if gloss is not None:
        set_gloss(gloss)
    keys = LANG.pass_keys
    attrs = LANG.html_attrs()                    # ' lang="fa" dir="rtl"'
    # ' lang="en" dir="ltr"' for a book that says nothing, which is what the
    # gloss row carried before a book could say anything else
    gattrs = GLOSS.html_attrs()
    alt = LANG.alt_pass
    parts = []
    times = []                                   # chunk spans, kept for review
    src = []                                     # what the .tex holds, per chunk
    subs = []                                    # what actually gets played
    toc = []                                     # one entry per paragraph
    seen_ids = set()
    toc_at = {}         # a paragraph's id -> its contents entry
    gi = 0
    si = 0
    paras = []          # [key, first sub, last sub] -- what a collapse folds
    last_key = None                 # the key of the last subparagraph written
    labels = []
    for ch in chapters:
        if ch.label not in labels:
            labels.append(ch.label)
    marks = []                      # (where it starts in parts, chapter index)
    # WHERE A CHAPTER OR A SECTION BEGINS, as the index of the first
    # subparagraph under it.  The player reads these to stop at a boundary
    # when it is asked to.  They are counted here rather than looked for in
    # the page because a chapter still in its own file has no elements to
    # look at -- the very reason PARAS is baked in beside them.
    bounds = []
    for ch in chapters:
        ci = labels.index(ch.label)
        cnum = T.latin_digits(ch.label or "")
        chname = structure.plain(ch.name) if ch.name else ""
        # the section a paragraph stands under, and the key of the paragraph
        # that opened it; both start empty again in every chapter
        sec_now, sec_key = "", ""
        marks.append((len(parts), ci))
        parts.append('<section class="chapter" data-ch="%d">' % ci)
        bounds.append(si)
        # THE CHAPTER, SAID IN THE TEXT ITSELF.  The PDF prints the number
        # centred between two rules (\chapopen) and its name under it
        # (\chapname); this is the same thing in the reader, so a change of
        # chapter is seen rather than inferred from a number changing.
        parts.append('<div class="chhead" data-ch="%d">'
                     '<div class="chnum"%s><bdi>%s</bdi></div>%s</div>'
                     % (ci, attrs, esc(ch.label or cnum),
                        ('<div class="chname"%s><bdi>%s</bdi></div>'
                         % (attrs, esc(chname))) if chname else ""))
        for para in ch.paragraphs:
            # WHICH PARAGRAPH THIS IS, for the page as well as for the id.
            # The id is only on the first half of a paragraph continued in
            # another file, and a collapse has to name the whole of it, so the
            # chapter and paragraph numbers are written out on every piece.
            # A .tex whose NAME carries no chapter number names no paragraph:
            # a book may keep a characters.tex beside its chapters, and
            # verify_book.py names and skips such a file for exactly this
            # reason -- source/paras/ch<N>_p<NN>.txt is MADE of the number.
            # Two of them would both say "0:1", and folding one would fold the
            # other, so they are given no key at all: not foldable, just as
            # they are not held against a source paragraph.
            # Read BEFORE the contents entry, because a section names the
            # paragraph it opens at and the entry carries that name.
            cno = chapter_no(ch.path)
            pkey = "%d:%d" % (cno, para.no) if cno is not None else ""
            # A SECTION OPENS HERE.  It is a place and not a container: what
            # it changes is what is drawn and what the contents groups, and
            # nothing else -- the paragraph keeps the number \parnum gave it.
            if para.section:
                sec_now = structure.plain(para.section)
                sec_key = pkey or ("%s:%d" % (cnum, para.no))
                bounds.append(si)
            # A chapter arrives as several files, so the same paragraph could in
            # principle open in one and continue in the next.  The id belongs to
            # where it starts; a continuation gets none, and no second contents
            # entry, rather than a duplicate id that both would answer to.
            pid = "par-%s-%d" % (cnum, para.no)
            fresh = pid not in seen_ids
            if fresh:
                seen_ids.add(pid)
                # The page prints paragraph.subparagraph (NOTES section 3), so an
                # entry reading "۱.۲" beside a page headed "۲.۱" is the same pair of
                # numbers the other way round.  The chapter already has its own
                # heading above the entry, so the entry shows the paragraph alone.
                label = fa_digits(para.no)
                inc = incipit(para)
                toc.append({
                    # "ch" is the PRINTED chapter number and "ci" the index of
                    # the section it is in.  They are not the same number and
                    # cannot be derived from one another: a chapter written
                    # across two files is two sections wearing one index, so
                    # the sequence is not even a constant shift.  The panel
                    # groups and filters by the printed number; fetching a
                    # chapter that is still a file needs the index, because
                    # that is what the build writes on the section.
                    "id": pid, "ch": cnum, "ci": ci, "chfa": ch.label,
                    "no": para.no, "label": label, "incipit": inc,
                    # the chapter's name, and the section this paragraph
                    # stands under: what the panel groups the row beneath.
                    # "" for a chapter with no name and for a paragraph
                    # before the first section -- which is every paragraph
                    # of every book written before sections existed.
                    "chname": chname, "sec": sec_now, "seckey": sec_key,
                    "pkey": pkey,
                    # what the filter box matches against: the number in both
                    # scripts, and the incipit both as printed and with the
                    # harakat off, since nobody types the vowels.  Folded,
                    # not lower-cased: the script does the same to what is
                    # typed, and a Turkish incipit opening "İyi" has to be
                    # findable by someone typing "iyi" (languages.fold).
                    "q": languages.fold(" ".join(["%s.%d" % (cnum, para.no),
                                                  label, inc, LANG.strip(inc)])),
                })
                toc_at[pid] = len(toc) - 1
            # the contents entry this paragraph is under -- a piece continued
            # in another file is under the entry of the piece that opened it
            entry = toc_at.get(pid, -1)
            if pkey:
                paras.append([pkey, si, si + max(0, len(para.subs) - 1)])
            # THE SECTION, SAID IN THE TEXT.  Smaller than the chapter's own
            # heading, as a subheading is smaller than a heading, and outside
            # the .para so that folding a run of paragraphs away never takes
            # the mark of a section with it.
            if para.section:
                parts.append('<div class="sechead" id="sec-%s-%d"%s%s>'
                             '<bdi%s>%s</bdi></div>'
                             % (cnum, para.no, ' data-ch="%d"' % ci,
                                (' data-p="%s"' % esc(pkey)) if pkey else "",
                                attrs, esc(sec_now)))
            parts.append('<div class="para"%s%s>'
                         % ((' data-p="%s"' % esc(pkey)) if pkey else "",
                            (' id="%s"' % pid) if fresh else ""))
            for s in para.subs:
                first = s.chunks[0] if s.chunks else None
                t0 = s.t0 if s.t0 is not None else (first.t0 if first else None)
                t1 = s.t1 if s.t1 is not None else None
                idx0 = gi
                # a subparagraph is the unit of playback: the transcript only
                # carries segment-level times, so a span of several seconds is
                # trustworthy where a 1-2 s chunk boundary is not
                if t0 is None or t1 is None:
                    got = [c for c in s.chunks if c.t0 is not None]
                    if got:
                        t0 = min(c.t0 for c in got)
                        t1 = max(c.t1 for c in got)
                # [start, end, chapter, narration].  The fourth is the id of
                # the recording those seconds are in, "" for a book with one
                # -- the chapter stays third, so everything already indexed
                # off it (crossesBound, a chapter's own lazy fetch) is
                # untouched.
                # The fifth and sixth are what the outline a stretch of the
                # book is picked from reads (outlinePicker): the contents
                # entry of the paragraph this subparagraph is in, and its
                # label.  Last, so nothing indexed off the first four moves.
                subs.append([round(t0, 2) if t0 is not None else None,
                             round(t1, 2) if t1 is not None else None, ci,
                             str(getattr(s, "nid", "") or ""), entry, s.num])
                # The gap a note sits in.  One before every subparagraph
                # and, after the loop, one after the last of the book -- so
                # every seam between two lines is a place, named by the key
                # the note's own `anchor:` line names (markdown/app/notes.py).
                # Empty here: what is in it is drawn at runtime from the
                # notes beside the book, which change without a rebuild.
                parts.append('<div class="gap" data-at="%s" data-after="%s">'
                             '</div>' % (esc(subkey(s)), esc(last_key or "")))
                parts.append('<div class="sub%s" data-s="%d" data-key="%s" '
                             'data-from="%d" data-to="%d">'
                             % ("" if t0 is not None else " noaudio", si,
                                esc(subkey(s)), idx0, idx0 + len(s.chunks) - 1))
                # Latin digits, not Persian: this is a control you quote back
                # to someone, not part of the text being read.
                parts.append('<button class="lab" lang="en" title="%s">'
                             '%s</button>'
                             % ("play this subparagraph" if t0 is not None
                                else "put the reading place here",
                                esc(s.num)))

                # The chunks of a pass are joined with the language's word
                # separator: a space between Persian chunks, nothing between
                # Japanese ones (a space there would show as a gap in the text).
                sep = LANG.word_sep

                # pass 1 — vocalised, no glosses; with the reading over each
                # chunk where the language has one -- or over each word, for
                # a chunk its word line draws, here and in the chunk column
                drawn = [worded(c.fa, c.wordline) for c in s.chunks]
                p1 = []
                for k, c in enumerate(s.chunks):
                    p1.append('<span class="w%s" data-c="%d">%s</span>'
                              % (hl_class(c.col), gi + k,
                                 ruby(c.fa, c.kana) if drawn[k] is None else drawn[k]))
                parts.append('<div class="pass p1"%s>%s</div>' % (attrs, sep.join(p1)))

                # the reading pass, where the chunks carry words: each chunk's
                # reading alone -- the kana, or the tr where the language has
                # no reading -- with the closing punctuation of its text the
                # reading leaves out, or the text itself where there is no
                # reading (wordline.aloud, which the PDF's pass reads through
                # wordline.lua).  A space between two chunks, widened by the
                # stylesheet: the gap is where one chunk ends.
                if "aloud" in keys:
                    # A language whose only reading is its romanisation
                    # (pinyin) says so on a chunk its word line draws: Latin
                    # letters, for the face and for whatever reads the page
                    # aloud.  A chunk without words keeps the span it had.
                    latn = "" if LANG.reading else ' lang="%s-Latn"' % esc(LANG.code)
                    p5 = ['<span class="w" data-c="%d"%s>%s</span>'
                          % (gi + k, latn if drawn[k] is not None and c.tr.strip() else "",
                             esc(wordline.aloud(c.kana if LANG.reading else c.tr, c.fa)))
                          for k, c in enumerate(s.chunks)]
                    parts.append('<div class="pass p5"%s>%s</div>' % (attrs, " ".join(p5)))

                # pass 2 — the chunks on the language's side, the gloss on the
                # other (the row is a flex row in the document's direction, so
                # the first cell is at the right in an RTL book and at the left
                # in an LTR one).  The kana, when there is one, is the first
                # line of the gloss, above the transliteration.
                parts.append('<div class="pass p2">')
                for k, c in enumerate(s.chunks):
                    n = gi + k
                    gl = ""
                    if c.glossed:
                        # The lang and dir are the GLOSS language's, not the
                        # book's: the lines inside are its prose, and the runs
                        # of the book's own language among them carry their
                        # own (bdi.v, from render_voc).  The transliteration
                        # takes them too -- it is Latin script, so it reads
                        # left to right inside a right-to-left gloss of its
                        # own accord, and inheriting the block's direction is
                        # what keeps it flush with the lines under it, as it
                        # is in the PDF.
                        gl = ('<div class="gl"%s>%s'
                              '<div class="tr">%s</div>%s<div class="en">%s</div></div>'
                              % (gattrs,
                                 ('<div class="kana"%s>%s</div>' % (attrs, esc(c.kana.strip())))
                                 if LANG.reading and c.kana.strip() else "",
                                 esc(c.tr),
                                 ('<div class="voc">%s</div>' % render_voc(c.voc))
                                 if c.voc.strip() else "",
                                 esc(c.en)))
                    # a reading nobody wrote, on the row of a chunk that
                    # holds nothing else (seeded(): the chunk sheet reads it)
                    seed = seeded(c)
                    parts.append('<div class="row" data-c="%d"%s>'
                                 '<div class="fa"%s>%s</div>%s</div>'
                                 % (n, ' data-seed="%s"' % esc(seed) if seed else "",
                                    attrs,
                                    words(c.fa) if drawn[k] is None else drawn[k], gl))
                parts.append('</div>')

                # passes 3 and 4 — the same chunks with the language's marks
                # filtered out (Persian and Arabic: the harakat; Japanese: the
                # text as it stands, without the ruby).  Only the passes the
                # language has: Italian has no bare pass, Arabic no fourth.
                stripped = []
                for k, c in enumerate(s.chunks):
                    stripped.append('<span class="w" data-c="%d">%s</span>'
                                    % (gi + k, words(c.plain)))
                joined = sep.join(stripped)
                if "bare" in keys:
                    parts.append('<div class="pass p3"%s>%s</div>' % (attrs, joined))
                if alt is not None:
                    parts.append('<div class="pass %s"%s>%s</div>'
                                 % (pass_class(alt), attrs, joined))
                parts.append(
                    '<div class="edit" dir="ltr">'
                    '<div class="erow"><span class="who" lang="en">%s</span>'
                    '<button data-e="p">&#9654;</button>'
                    '<span class="dur"></span></div>'
                    '<div class="erow"><span class="lbl">start</span>'
                    '<button data-e="s-1">&minus;1</button>'
                    '<button data-e="s-5">&minus;.5</button>'
                    '<button data-e="s-">&minus;.1</button>'
                    '<input class="e0" type="number" step="0.05">'
                    '<button data-e="s+">+.1</button>'
                    '<button data-e="s+5">+.5</button>'
                    '<button data-e="s+1">+1</button>'
                    '<button data-e="sh" title="set to the playhead">&#9673;</button></div>'
                    '<div class="erow"><span class="lbl">end</span>'
                    '<button data-e="e-1">&minus;1</button>'
                    '<button data-e="e-5">&minus;.5</button>'
                    '<button data-e="e-">&minus;.1</button>'
                    '<input class="e1" type="number" step="0.05">'
                    '<button data-e="e+">+.1</button>'
                    '<button data-e="e+5">+.5</button>'
                    '<button data-e="e+1">+1</button>'
                    '<button data-e="eh" title="set to the playhead">&#9673;</button>'
                    '<button data-e="rv" title="undo">undo</button></div>'
                    '</div>' % esc(s.num))
                parts.append('</div>')

                for c in s.chunks:
                    times.append([round(c.t0, 2) if c.t0 is not None else None,
                                  round(c.t1, 2) if c.t1 is not None else None,
                                  round(c.conf, 2) if c.conf is not None else 0,
                                  ci])
                    # The chunk as the .tex holds it, in the same order as
                    # `times`, so SRC[data-c] is the source of the chunk the
                    # page is showing.  The edit boxes are filled from here and
                    # never from the DOM: the vocabulary is LaTeX and the page
                    # shows the RENDERING of it (one \dw is two runs and a
                    # space), so reading it back off the page would hand the
                    # author a line to edit that is not the line in the file.
                    # Last, the word line ("" for a chunk without one): the
                    # page draws it rendered, and the word strip edits it.
                    src.append([HL.get(c.col, ""), c.fa, c.kana,
                                c.tr, c.voc, c.en, c.wordline])
                gi += len(s.chunks)
                si += 1
                last_key = subkey(s)
            parts.append('<div class="pmark">¶</div>')
            parts.append('</div>')
        parts.append('</section>')
    # the chapters as separate pieces, taken before the closing gap is added
    # so that the gap belongs to the book and not to its last chapter
    ends = [a for (a, _) in marks[1:]] + [len(parts)]
    sections = [(ci, "\n".join(parts[a:b])) for (a, ci), b in zip(marks, ends)]
    # the one gap that is not before anything
    tail = ""
    if last_key is not None:
        tail = ('<div class="gap last" data-at="" data-after="%s">'
                '</div>' % esc(last_key))
        parts.append(tail)
    return ("\n".join(parts), times, subs, toc, src,
            {"sections": sections, "tail": tail, "paras": paras,
             "bounds": sorted(set(bounds))})


CHAP_FILE_RE = re.compile(r"ch-\d+\.html")


def one_chapter_at_a_time(chaps, body):
    """The <main> the reader ships with, and the chapter files beside it.

    A whole book in one file is about 1.2 kB of markup per chunk: a novel is
    megabytes, and over a phone's connection to a server at home that is a
    long minute of staring at nothing before the first line can be read.  So
    every chapter after the first is left in a file of its own, and the page
    fetches one when it is wanted -- the contents jumped into it, the reading
    place is in it, the narration played into it, or it simply came near the
    window.

    NOTHING IS RENUMBERED.  A chapter file holds the very markup build()
    emitted, cut where the chapters already were, so data-c and data-s stay
    the book-wide counters that SUBS, SRC and TIMES are indexed by and every
    other part of the page goes on meaning what it meant.

    A book of ONE chapter is written exactly as it always was -- no
    fragments, no placeholders, nothing to fetch.
    """
    sections = chaps["sections"]
    if len(sections) < 2:
        return body, []
    bits, files = [], []
    for k, (ci, html) in enumerate(sections):
        if k == 0:                      # the first chapter travels with it
            bits.append(html)
            continue
        name = "ch-%d.html" % k
        files.append((name, html))
        bits.append('<section class="chapter" data-ch="%d" data-part="%s">'
                    '</section>' % (ci, esc(name)))
    if chaps["tail"]:
        bits.append(chaps["tail"])
    return "\n".join(bits), files


def toc_html(toc):
    """The contents panel, written out at build time.

    A real list of <a href="#par-..."> links rather than something the browser
    assembles: it is keyboard-reachable and greppable without running anything,
    and it borrows nothing from the player — one of the books has no audio at
    all and the contents has to work there just the same.
    """
    rows = []
    last_ch, last_sec = None, ""
    ch_open = sec_open = False
    attrs = LANG.html_attrs()
    for e in toc:
        if e["ch"] != last_ch:
            if sec_open:
                rows.append("</div></div>")
                sec_open = False
            if ch_open:
                rows.append("</div></div>")
            last_ch, last_sec, ch_open = e["ch"], "", True
            name = (('<span class="tocchn"%s><bdi>%s</bdi></span>'
                     % (attrs, esc(e.get("chname") or "")))
                    if e.get("chname") else "")
            rows.append(
                '<div class="tocgrp" data-ch="%s"><div class="tocch" data-ch="%s">'
                '<button type="button" class="tocfold" aria-expanded="true" '
                'title="fold this chapter">&#9662;</button>'
                '<span class="tocchl">chapter <bdi%s>%s</bdi></span>%s'
                '<button type="button" class="tocedit" data-kind="chapter" '
                'data-ch="%s" title="name this chapter">&#9998;</button></div>'
                '<div class="tocbody">'
                % (esc(e["ch"]), esc(e["ch"]), attrs, esc(e["chfa"]), name,
                   esc(e["ch"])))
        key = e.get("seckey") or ""
        if key != last_sec:
            if sec_open:
                rows.append("</div></div>")
                sec_open = False
            last_sec = key
            if key and e.get("sec"):
                sec_open = True
                rows.append(
                    '<div class="tocsgrp" data-p="%s"><div class="tocsec">'
                    '<button type="button" class="tocfold" aria-expanded="true" '
                    'title="fold this section">&#9662;</button>'
                    '<span class="tocsecn"%s><bdi>%s</bdi></span>'
                    '<button type="button" class="tocedit" data-kind="section" '
                    'data-p="%s" title="rename or remove this section">&#9998;'
                    '</button></div><div class="tocbody">'
                    % (esc(key), attrs, esc(e["sec"]), esc(key)))
        rows.append(
            '<a class="toce" href="#%s" data-ch="%s" data-ci="%d" data-p="%s" '
            'data-q="%s">'
            '<span class="tocn"><bdi%s>%s</bdi></span>'
            '<span class="toci"%s><bdi>%s</bdi></span></a>'
            % (esc(e["id"]), esc(e["ch"]), e["ci"], esc(e.get("pkey") or ""),
               esc(e["q"]), attrs, esc(e["label"]), attrs, esc(e["incipit"])))
    if sec_open:
        rows.append("</div></div>")
    if ch_open:
        rows.append("</div></div>")
    return """<div id="tocwrap" hidden>
<div id="tocback"></div>
<div id="tocpanel" lang="en" dir="ltr" role="dialog" aria-label="contents">
  <div class="tocbar">
    <input id="tocq" type="search" autocomplete="off" spellcheck="false"
           placeholder="filter by number or opening words" aria-label="filter the contents">
    <button id="tocx" title="close (Esc)">&times;</button>
  </div>
  <div class="tocbar2">
    <button type="button" id="tocfoldall" title="show the chapters alone">fold all</button>
    <button type="button" id="tocopenall" title="open every chapter and section">open all</button>
    <span class="sp"></span>
    <button type="button" id="tocsecs" title="open, rename or remove a section">sections&hellip;</button>
  </div>
  <div id="toclist">
%s
    <div id="tocempty" hidden>nothing matches</div>
  </div>
</div></div>""" % "\n".join(rows)


def download_html(narrated):
    """The header's download control: a link, or the button that opens the
    sheet of three.

    A narrated book has three downloads and not one, and which of them
    somebody wants is a question about what they mean to do with the zip: the
    sheet the button opens is three sentences, and the script builds it (see
    DL_SHEET in JS, and the Aa panel it is modelled on).

    A book with no narration keeps the plain link it has always had.  All
    three would hand it back the same bytes, a choice that cannot matter is
    worse than no choice at all, and a reader carrying a sheet about a
    narration its book has not got would be the same lie the text shape
    exists to prevent.
    """
    if not narrated:
        return """  <a class="dl" href="../__download" title="the whole edition as one zip: every .tex, book.json and the source paragraphs, but neither the PDF nor the narration &mdash; to keep, or to hand to another reader of Parseh, whose toolbox unpacks it whole">download</a>"""
    return """  <button class="dl" aria-expanded="false"
          title="the edition as one zip &mdash; with the recording, without it, or with nothing left pointing at one">download</button>"""


# The palette (--bg, --ink, --accent ...) and the faces are NOT here: the
# page links lib/parseh.css, the toolbox's one stylesheet, so a colour change
# reaches a built reader without a rebuild, and lib/langs.css, generated from
# the registry, which gives <html data-lang="..."> its --tl-font (the main
# face), --tl-alt (the alternate: nastaliq, gothic) and --tl-alt-lh (the
# leading the alternate wants).  Everything below is the reader's own layout,
# written against those tokens -- and against the dir attributes the HTML
# carries: no rule here says rtl or ltr, so the same stylesheet lays out a
# Persian book with the chunks at the right and an Italian one with them at
# the left.
CSS = r"""
body{padding-top:92px}
header{position:fixed;top:0;left:0;right:0;z-index:50;
  background:var(--card);border-bottom:1px solid var(--rule);
  display:flex;flex-direction:column;gap:0;padding:4px 10px}
.hrow{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:3px 0}
/* On a phone this header wraps into three rows and leaves too little page
   to read in, so it slides away as the reader moves down and comes back on
   the smallest move up -- parseh.js (bars()) toggles body.barhidden.  A
   TRANSFORM AND NOTHING ELSE: the height is what fitHeader() writes into
   body's inline padding from a ResizeObserver, and a header that collapsed
   would drag the whole page up with it.  Wide screens never see this.     */
@media (max-width:560px){
  header{transition:transform .18s ease}
  body.barhidden header{transform:translateY(-100%)}
}
/* THE WHOLE HEADER, PUT AWAY BY HAND.  Three rows of controls stand over
   the text; once the place to read from is set, they are in the way, and
   "bars" takes the header off outright and leaves one faint button in the
   corner (outside it, since the header itself is gone).  The phone's own
   hiding (above) stands down while this is on -- parseh.js -- so pressing
   the corner button is what decides, not the last scroll. */
body.chrome-off header{display:none}
.bars-show{
  position:fixed;top:.35rem;right:.5rem;z-index:51;
  padding:.1rem .5rem;font-size:.78rem;line-height:1.6;
  opacity:.42;transition:opacity .15s ease}
.bars-show:hover,.bars-show:focus-visible{opacity:1}
.hrow .grp{display:flex;align-items:center;gap:4px;
  padding-inline-end:8px;margin-inline-end:2px;border-inline-end:1px solid var(--rule)}
/* .dl is the download.  On a book with no narration it is a link, straight to
   a URL that answers with a Content-Disposition, so no script saves the file
   -- it only has to look like the buttons it stands among.  On a narrated one
   it is a button, because what it opens is a choice of three and not a file;
   the two share the class, and the script asks for whichever is there. */
header button,header select,header a.dl{font:inherit;font-size:13px;padding:5px 9px;
  border:1px solid var(--rule);background:var(--bg);color:var(--ink);
  border-radius:6px;cursor:pointer;white-space:nowrap}
header a.dl{text-decoration:none;line-height:1.4}
header a.dl:hover{border-color:var(--accent);color:var(--accent)}
header button.on{background:var(--accent);color:var(--accent-fg);border-color:var(--accent)}
header button:disabled{opacity:.45;cursor:default}
header a.home{color:var(--dim);text-decoration:none;font-size:15px;line-height:1.3;
  padding:4px 8px;border:1px solid var(--rule);border-radius:6px}
header a.home:hover{color:var(--accent);border-color:var(--accent)}
/* the hub's glyph is the toolbox's own mark (پ, Parseh), not the book's
   language: the same two faces parseh.css gives the hub's brand */
header a.home.glyph{font-family:'Noto Nastaliq Urdu',Vazirmatn,serif;
  color:var(--accent);padding:2px 9px 6px}
header .sp{flex:1}
#pos{font-variant-numeric:tabular-nums;color:var(--dim);font-size:12px}
/* the Aa panel in the header sets --rd-fa (the text), --rd-gl (the
   glosses), --rd-width (the column), --rd-lead (a line-height multiplier) and,
   for a vertical language, --rd-vh (the column height of pass 4, in em) on
   <html>; without it the fallbacks below are the page as it always was */
main{max-width:var(--rd-width,760px);margin:0 auto;padding:16px 14px 60vh;overflow-x:clip}
.chapter{margin-bottom:8px}
/* A CHANGE OF CHAPTER, SAID IN THE TEXT.  The PDF prints the number centred
   between two rules and the chapter's name under it (\chapopen, \chapname);
   this is the same thing here, so a new chapter is seen rather than inferred
   from a paragraph number starting again at 1.  No font-family: the book's
   own face is already on the text and a heading is part of the book. */
.chhead{text-align:center;margin:30px 0 20px;padding-top:16px;
  border-top:1px solid var(--rule)}
.chapter:first-of-type .chhead{border-top:none;padding-top:4px;margin-top:8px}
.chhead .chnum{font-size:26px;line-height:1.25;color:var(--ink)}
.chhead .chname{font-size:17px;line-height:1.4;color:var(--dim);margin-top:5px}
/* A SECTION: the same idea one step quieter, an h2 to the chapter's h1.  It
   has no number, and it is drawn OUTSIDE the .para that follows it so that
   folding a run of paragraphs away never takes a section's mark with it. */
.sechead{text-align:center;font-size:17px;line-height:1.4;color:var(--ink);
  margin:24px 0 14px;padding-top:12px;border-top:1px solid var(--rule);
  scroll-margin-top:calc(var(--headh, 92px) + 10px)}
/* a chapter whose markup is still a file beside the reader: it holds a
   screenful, so the scrollbar does not lie about the length of the book and
   so that reading on fetches the chapter being approached and not all of
   them at once (they would otherwise all sit at the same height) */
section.chapter[data-part]{min-height:70vh}
.para{border-bottom:1px solid var(--rule);padding-bottom:6px;margin-bottom:6px}
/* The header is fixed, so a paragraph scrolled to the top of the viewport
   lands underneath it.  --headh is the header as actually measured (it wraps
   to two or three rows on a phone), and scroll-margin makes every jump —
   ours, the URL hash, or the browser's own — stop that far short. */
.para{scroll-margin-top:calc(var(--headh, 92px) + 10px)}
.pmark{text-align:center;color:var(--faint);margin:6px 0 14px}
/* A RUN OF PARAGRAPHS FOLDED AWAY (lib/reading.py, kept with the book).  The
   text is not shown and a bar stands in its place; opening one from the bar
   shows it here without unfolding it in the book, which is why `opened` is a
   class on the page and not a decision written anywhere. */
.para.folded{display:none}
.para.folded.opened{display:block;opacity:.8}
.foldbar{margin:12px 0;text-align:center}
/* the direct child is the bar's own button; the row of note marks under it
   is a row of pills and wants the seam's look, not this one */
.foldbar > button{font:inherit;font-size:12px;color:var(--dim);background:var(--card);
  border:1px dashed var(--rule);border-radius:999px;padding:4px 14px;cursor:pointer}
.foldbar > button:hover{color:var(--accent);border-color:var(--accentlt)}
/* WHAT THE FOLD WOULD OTHERWISE SWALLOW.  A note lives in the seam above a
   line, a seam is drawn inside the paragraph it belongs to, and a folded
   paragraph is display:none -- so folding a run took its notes off the page
   with it, and nothing said so.  The bar carries them instead: the marks of
   every note inside the run, the first three and then the rest behind
   "+N more".  The row goes when the run is opened, because the notes are
   standing in their own seams again by then. */
.foldbar .fnotes{margin-top:7px;display:flex;flex-wrap:wrap;gap:6px;
  justify-content:center;align-items:center}
.foldbar.open .fnotes{display:none}
.foldbar .fmore{font:inherit;font-size:11.5px;line-height:1.3;padding:2px 9px;
  border:1px dashed var(--rule);border-radius:10px;background:none;
  color:var(--faint);cursor:pointer}
.foldbar .fmore:hover{color:var(--accent);border-color:var(--accent)}
.sub{margin:0 0 22px}
/* the label sits where the text starts: at the right of an RTL book, the
   left of an LTR one -- inline-start, never a bare right */
.lab{float:inline-start;font-size:12px;color:var(--faint);background:none;border:none;
  cursor:pointer;padding:2px 4px;font-variant-numeric:tabular-nums}
.lab:hover{color:var(--accent)}
/* Anything showing a number must use a Latin font and must not inherit the
   book's locale, or `locl` turns 1.1 into ۱.۱ on machines with Persian
   fonts installed. */
.lab,.who,.dur,#pos,#build,.edit input{
  font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace;
  font-feature-settings:'locl' 0;font-variant-numeric:tabular-nums}
.lab{direction:ltr;unicode-bidi:isolate}
.edit .who{color:var(--accent);font-weight:600;font-variant-numeric:tabular-nums}
.pass{clear:both}
.p1,.p3,.p5{font-family:var(--tl-font,serif);font-size:var(--rd-fa,20px);
  line-height:calc(2.0 * var(--rd-lead,1));margin:4px 0 12px}
/* the reading pass (p5, a language whose chunks carry words): the reading
   alone at the size of the text, and a gap wide enough to see between two
   chunks -- which is where the sentence divides */
.p5 .w+.w{margin-inline-start:.45em}
/* the reading over a chunk (a language with kana): small, in the text face,
   and the line already has the room -- pass 1 is set at twice the size */
.p1 rt{font-size:.5em;font-family:var(--tl-font,serif);color:var(--dim);
  ruby-align:center;user-select:none}
.p1 ruby{ruby-position:over}
/* a chunk its word line draws wears each word's reading in the chunk column
   too (nothing else there has one): set as the reading over pass 1 is, with
   the same Aa sliders -- and pinyin, which is Latin letters with tone
   marks, as lib/parseh.css sets it over pass 1: upright, small, unspaced */
.row .wd[data-w] rt{font-size:var(--kana-size,50%);letter-spacing:0;line-height:1.2;
  color:var(--dim);color:color-mix(in srgb,var(--ink) max(0%,var(--kana-contrast,0%)),
    color-mix(in srgb,var(--dim),transparent max(0%,calc(0% - var(--kana-contrast,0%)))));
  font-family:var(--tl-font,serif);ruby-align:center}
html[data-lang=zh] .row .wd[data-w] rt{
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,system-ui,sans-serif;
  font-size:max(10px,48%);font-style:normal;font-weight:400;line-height:1.1}
/* the highlight palette, pass 1 only -- see \Cred and friends in the preamble.
   The dark-theme values are lifted a little: the print hexes are chosen against
   paper and go muddy on a dark ground. */
.hl-red{color:#8e1b1b}
.hl-blue{color:#1f4e79}
.hl-orange{color:#bf5b04}
.hl-green{color:#22643a}
@media (prefers-color-scheme:dark){
  html:not([data-theme=light]):not([data-theme=sepia]) .hl-red{color:#e0736b}
  html:not([data-theme=light]):not([data-theme=sepia]) .hl-blue{color:#6fa8dc}
  html:not([data-theme=light]):not([data-theme=sepia]) .hl-orange{color:#e8974a}
  html:not([data-theme=light]):not([data-theme=sepia]) .hl-green{color:#6fbf8b}
}
html[data-theme=dark] .hl-red{color:#e0736b}
html[data-theme=dark] .hl-blue{color:#6fa8dc}
html[data-theme=dark] .hl-orange{color:#e8974a}
html[data-theme=dark] .hl-green{color:#6fbf8b}
.p3{margin-top:14px;border-top:1px solid var(--rule);padding-top:12px}
.p4{font-family:var(--tl-alt,var(--tl-font,serif));font-size:calc(var(--rd-fa,20px) - 1px);
  line-height:calc(var(--tl-alt-lh,2.6) * var(--rd-lead,1));margin:10px 0 4px;padding-top:6px}
/* the vertical alternate (Japanese tategaki): columns top to bottom, the
   first at the right; a fixed height so the columns wrap, and the block
   scrolls sideways when the sentence needs more of them than the width
   holds.  --rd-vh is a bare number of em (the Aa panel writes numbers), so
   the unit is put on here. */
.p4.vert{writing-mode:vertical-rl;text-orientation:mixed;
  height:calc(var(--rd-vh,22) * 1em);max-width:100%;overflow-x:auto;overflow-y:hidden;
  line-height:calc(2.0 * var(--rd-lead,1));padding:6px 0 10px;
  font-size:var(--rd-fa,20px)}
.p2{margin:10px 0}
.row{display:flex;gap:12px;align-items:flex-start;padding:5px 0}
/* the chunk cell carries the language's dir, so start is its own side */
.row .fa{font-family:var(--tl-font,serif);font-size:calc(var(--rd-fa,20px) - 1px);
  line-height:calc(1.9 * var(--rd-lead,1));width:38%;text-align:start;flex:0 0 38%}
.row .gl{flex:1;font-size:var(--rd-gl,12.5px);color:var(--dim);line-height:1.45;padding-top:3px}
.row .gl .tr{font-style:italic;color:var(--ink);font-size:calc(var(--rd-gl,12.5px) + .5px)}
.row .gl .kana{font-family:var(--tl-font,serif);color:var(--ink);
  font-size:calc(var(--rd-gl,12.5px) + 1.5px);text-align:start}
.row .gl .voc{margin:1px 0}
.row .gl .en{color:var(--dim)}
.row .gl bdi.v{font-family:var(--tl-font,serif);font-size:calc(var(--rd-gl,12.5px) + 1px)}
.w{border-radius:4px}
.sub.on-air{background:var(--hl);box-shadow:0 0 0 6px var(--hl);border-radius:6px}
.sub{cursor:pointer;border-radius:6px}
.sub:hover{box-shadow:0 0 0 6px var(--rule)}
/* A subparagraph without a time reads exactly like the rest: the text is the
   point, and the narration panel says what is timed and what is not.  It is
   still where you are: clicking one puts the reading place there, which is
   the whole of what the highlight means in a book with no narration -- so it
   keeps the pointer and the hover the timed ones have. */
.edit{display:none;margin:6px 0 2px;padding:6px 8px;
  background:var(--card);border:1px solid var(--rule);border-radius:8px;
  font-size:12px}
body.editing .edit{display:block}
.erow{display:flex;gap:4px;align-items:center;flex-wrap:wrap;padding:2px 0}
.erow .lbl{color:var(--dim);width:34px}
body.editing .sub{outline:1px dashed var(--rule)}
.edit input{width:82px;font:inherit;font-size:12px;padding:3px 5px;text-align:right;
  border:1px solid var(--rule);border-radius:5px;background:var(--bg);color:var(--ink);
  font-variant-numeric:tabular-nums}
.edit label{display:flex;gap:4px;align-items:center;color:var(--dim)}
.edit button{font:inherit;font-size:12px;padding:3px 7px;border:1px solid var(--rule);
  background:var(--bg);color:var(--ink);border-radius:5px;cursor:pointer}
.edit .dur{color:var(--faint);font-variant-numeric:tabular-nums}
.sub.dirty .edit{border-color:var(--accent);box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 15%,transparent)}
body.nogloss .row .gl{display:none}
/* a book with no narration: the controls are absent, not broken */
body.noaudio #play,body.noaudio #cont,body.noaudio #loop,body.noaudio #stopbnd,
body.noaudio #gapwrap,body.noaudio #listen,body.noaudio #seekwrap,
body.noaudio #listenfollow,body.noaudio #listenscroll,
body.noaudio #speed,body.noaudio #pos,body.noaudio #warn,body.noaudio .edit,
body.noaudio #editmode,body.noaudio #editbyear,body.noaudio #savetimes,body.noaudio #droptimes{display:none!important}
body.noaudio .lab{cursor:pointer}
/* the narration with its own controls: shown while editing the times, and
   whenever there is audio but not one time yet -- the audio-only case, where
   the subparagraphs are stamped by hand */
#scrub[hidden]{display:none}
body.noaudio #scrub{display:none!important}
#scrub audio{height:32px;flex:1;min-width:220px;max-width:640px}
#scrub .snote{font-size:12px;color:var(--dim)}

body.no1 .p1,body.no2 .p2,body.no3 .p3,body.no4 .p4,body.no5 .p5{display:none}

/* ---- the pass toggles, as one group -------------------------------------
   Buttons labelled 1, 2, 3... say nothing about what they are for.  The
   dashed box around them and the small caption under it name them once, for
   the group, which is the thing a reader needs told -- what each one hides
   is its own title, and the labels are the numbers the passes wear in the
   book itself.                                                             */
.pgrp{display:inline-flex;flex-direction:column;align-items:center;gap:2px;
  border:1px dashed var(--rule);border-radius:7px;padding:3px 7px 2px}
.pgrp .pgrpb{display:flex;align-items:center;gap:6px}
.pgrp .pgrpc{font-size:10px;line-height:1;color:var(--faint);white-space:nowrap}
button[data-toggle]:disabled{opacity:.45;cursor:default}

/* ---- hover mode ---------------------------------------------------------
   The optional other way to read, borrowed whole from the video player:
   the text passes only -- p1, the reading alone (p5) where there is one,
   and the bare p3 -- with the chunks living in a gloss cloud that opens over
   any chunk of p1.  These rules sit AFTER the no1..no5 rules, so entering
   the mode brings the text passes back; but a toggle switched off WHILE the
   mode is on still hides its pass, because reading the hoverable text alone
   is exactly what somebody turns the others off for.  The two passes the
   mode swallows -- the chunks (p2) and the alternate face (p4) -- have
   nothing to show either way, so their buttons go grey while it is on.    */
body.hovermode .p2,body.hovermode .p4{display:none}
body.hovermode:not(.no1) .p1,body.hovermode:not(.no3) .p3,
body.hovermode:not(.no5) .p5{display:block}
/* the affordance the video player uses: a quiet dotted underline, the card
   colour lifting the chunk while the pointer is on it */
body.hovermode .p1 .w{cursor:default;
  text-decoration:underline dotted var(--faint) 1px;
  text-decoration-skip-ink:none;text-underline-offset:7px}
body.hovermode .p1 .w:hover,body.hovermode .p1 .w.hot{background:var(--card);
  box-shadow:0 0 0 3px var(--card),0 2px 8px rgba(0,0,0,.14);
  text-decoration-color:var(--accent)}

/* ---- the gloss cloud ----------------------------------------------------
   Set like a .row .gl: 12.5px dim, italic ink transliteration, words of the
   language inside the gloss in its face via bdi.v.  The cloud is the page's
   chrome (dir=ltr in the markup); the runs of the book's language inside it
   carry their own direction, and so do the two lines that are the gloss
   itself -- fillCloud puts the gloss language on them.                    */
#cloud{position:fixed;z-index:80;max-width:min(380px,92vw);
  background:var(--card);border:1px solid var(--rule);border-radius:10px;
  box-shadow:0 8px 28px rgba(0,0,0,.22);padding:9px 12px 8px;
  text-align:start;
  font-size:var(--rd-gl,12.5px);color:var(--dim);line-height:1.45}
#cloud[hidden]{display:none}
#cloud .fa,#cloud .kana{font-family:var(--tl-font,serif);direction:var(--tl-dir,ltr);
  text-align:start;color:var(--ink)}
#cloud .fa{font-size:calc(var(--rd-fa,20px) * .8);line-height:1.9}
#cloud .kana{font-size:calc(var(--rd-gl,12.5px) + 1.5px)}
#cloud .tr{font-style:italic;color:var(--ink);font-size:calc(var(--rd-gl,12.5px) + .5px)}
#cloud .voc{margin:3px 0 0;padding-top:3px;border-top:1px solid var(--rule)}
#cloud .en{color:var(--dim);margin-top:3px}
#cloud bdi.v{font-family:var(--tl-font,serif);font-size:calc(var(--rd-gl,12.5px) + 1px);font-style:normal}
#cloud .arrow{position:absolute;width:10px;height:10px;
  background:var(--card);border:1px solid var(--rule);
  border-top:none;border-left:none;transform:rotate(45deg);
  bottom:-6px;left:calc(50% - 5px)}
#cloud.below .arrow{transform:rotate(225deg);bottom:auto;top:-6px}
/* THE DICTIONARY, AND WHY IT LOOKS NOTHING LIKE A GLOSS.
   A written gloss is somebody's judgement about this word in this sentence.
   A dictionary entry is a list of everything the word can ever mean, and the
   one thing it cannot tell you is which.  So it is drawn as a quotation from
   elsewhere -- ruled off, indented, in the borrowed tint, with the source
   named under it -- and never in the type the glosses are set in.  A reader
   glancing at the cloud must never have to work out which of the two they
   are reading. */
#cloud .dict{margin:6px -12px 0;padding:6px 12px 2px;
  border-top:1px solid var(--rule);background:var(--hl);
  border-inline-start:3px solid var(--rule)}
/* THREE BLOCKS, AND WHERE ONE ENDS HAS TO BE SEEN.  The dictionary, the
   machine's reading and the sentences somebody translated were told apart by
   a 1px dotted --rule line, and --rule on the --hl tint the panel is drawn
   on measures 1.08:1 in the light theme, 1.08:1 in the dark and 1.12:1 in
   sepia: no line at all.  Each block's source line wore the same dotted
   rule, so "the end of one" and "the start of the next" were one invisible
   stroke.  Now the gap BETWEEN two blocks is a solid 2px --faint rule with
   room either side of it (2.3-2.4:1 in all three themes), a block's head is
   --dim at weight 600 (4.1-5.7:1, where --faint was 2.3), and the source
   line under a block has no rule at all: a line belongs to the block above
   it, a rule to the gap between two.  Tokens only, so the three themes
   follow without a rule of their own. */
#cloud .dict>.ddict,#cloud .dict>.dmt,#cloud .dict>.dpairs{margin:0;padding:4px 0 6px}
#cloud .dict>*+.dmt,#cloud .dict>*+.dpairs{margin-top:8px;padding-top:10px;
  border-top:2px solid var(--faint)}
#cloud .dict .dhead{font-size:11px;letter-spacing:.07em;font-weight:600;
  text-transform:uppercase;color:var(--dim);margin-bottom:6px}
#cloud .dict .dw{margin:0 0 5px}
#cloud .dict .dwd{font-family:var(--tl-font,serif);direction:var(--tl-dir,ltr);
  font-size:calc(var(--rd-gl,12.5px) + 2px);color:var(--ink);unicode-bidi:isolate}
/* the reading a word of the chunk's word line carries, beside the word */
#cloud .dict .dwd .dread,#chside .sword .dread{font-size:calc(var(--rd-gl,12.5px) + .5px);
  color:var(--dim)}
#cloud .dict .dhit{margin:1px 0 0 10px}
#cloud .dict .dhead2{color:var(--ink)}
#cloud .dict .dpos{color:var(--faint);font-style:italic}
#cloud .dict .dnote{color:var(--faint)}
#cloud .dict .dsense{margin-inline-start:10px}
/* the definitions of a dictionary that defines its words in their own
   language: a sense's labels as the source prints them, the machine's
   reading of it in the glosses' language under it, and the button that
   shows the rest of the entry */
#cloud .dict .ddef .dlabel{color:var(--faint);font-style:italic}
#cloud .dict .ddef .dtr{color:var(--dim);margin-inline-start:10px}
#cloud .dict .ddef .dtr.dwaiting{color:var(--faint)}
#cloud .dict .ddefmore{font:inherit;font-size:11.5px;color:var(--accent);background:none;
  border:none;padding:0;margin:1px 0 2px 10px;cursor:pointer}
#cloud .dict .ddefmore:hover{text-decoration:underline}
#defmode:disabled,#defmt:disabled{opacity:.5;cursor:default}
#cloud .dict .dnone{color:var(--faint);font-style:italic;margin-inline-start:10px}
/* a verb's principal parts, under its headword: what \vb would print, which
   is the thing the infinitive's translation alone never told anybody */
#cloud .dict .dvb{margin-inline-start:10px;color:var(--dim)}
/* THE SOURCES, AS A COLUMN TO THE LEFT OF THE FIELDS.  It used to be a block
   ABOVE them in the same 680px sheet, so every word's entries, the model and
   the corpus pushed the boxes they were meant to fill below the fold.  Now
   the sheet grows by the column's width (#chbox.side, below), and the column
   scrolls on its own.  contain:size is what keeps the sheet from growing
   DOWNWARDS too: the column's contents no longer count towards the sheet's
   height, so it is exactly as tall as the fields beside it -- the fields do
   not move when the column opens or when a lookup lands in it. */
#chside{flex:1 1 0;min-width:260px;max-width:480px;overflow-y:auto;
  -webkit-overflow-scrolling:touch;contain:size;
  border:1px solid var(--rule);border-radius:9px;background:var(--hl);
  padding:10px 12px;margin:0}
#chside .anote{margin:0 0 8px}
/* the source tools are ruled off like the panel's blocks */
#chside h4{font-size:11px;letter-spacing:.07em;text-transform:uppercase;
  color:var(--dim);margin:14px 0 6px;padding-top:9px;font-weight:600;
  border-top:2px solid var(--faint)}
#chside h4:first-child{margin-top:0;padding-top:0;border-top:none}
/* the switch that reads English's senses in the glosses' language, over the
   dictionary's rows, and what it reads under each of them */
#chside .sdefbar{display:flex;justify-content:flex-end;margin:-4px 0 4px}
#chside .sdefmt{font:inherit;font-size:11px;color:var(--dim);background:var(--bg);
  border:1px solid var(--rule);border-radius:5px;padding:2px 8px;cursor:pointer}
#chside .sdefmt.on{background:var(--accent);border-color:var(--accent);color:var(--accent-fg)}
#chside .sdef{margin-top:4px;padding-inline-start:8px;border-inline-start:2px solid var(--rule)}
#chside .sdef .dtr{color:var(--ink);font-size:12.5px}
#chside .sdef .dtr.dwaiting{color:var(--faint)}
/* a word of the chunk's line, over the dictionary's rows for it */
#chside .sword{font-family:var(--tl-font,serif);font-size:16px;color:var(--ink);
  margin-top:8px}
#chside .srow{padding:4px 0;border-top:1px solid var(--rule);font-size:13px}
#chside .srow:first-of-type{border-top:none}
#chside .stxt{color:var(--ink)}
#chside .ssub{color:var(--dim);font-size:12.5px}
/* a verb's principal parts, and -- when the dictionary could not fill one --
   what is left for somebody to write, said on the row and not only in a
   tooltip nobody on a tablet can reach.  What is left is a list whose items
   can be sentences with colons of their own, so each takes a line, hung
   from the label.  A hint (.snote) is dimmer than the line it follows and
   still readable: a mix of --dim and --faint measures 3.8:1 on the column's
   --hl in the light theme, 4.0 in the dark and 3.2 in sepia, where --faint
   alone is 2.3 in all three. */
#chside .svb{color:var(--dim);font-size:12px;margin-top:1px}
#chside .svb .snote{color:color-mix(in srgb,var(--dim) 60%,var(--faint))}
#chside .svb .smiss{color:var(--warn);display:flex;gap:4px}
#chside .svb .smiss .sml{flex:0 0 auto}
#chside .svb .smis{flex:1 1 auto;min-width:0;overflow-wrap:anywhere}
#chside .svb .smis>span{display:block}
#chside .sput{margin-top:3px;display:flex;gap:5px;flex-wrap:wrap}
#chside .sput button{font:inherit;font-size:11px;color:var(--dim);
  background:var(--bg);border:1px solid var(--rule);border-radius:5px;
  padding:2px 7px;cursor:pointer}
#chside .sput button:hover{color:var(--accent);border-color:var(--accent)}
#chside .sput button.sgap{border-style:dashed}
#chside .snone{color:var(--faint);font-style:italic;font-size:12.5px}
#chside .shere{color:var(--accent);font-weight:600}
#chside .sllmctl{display:grid;gap:6px}
#chside .sllmctl textarea{box-sizing:border-box;width:100%;min-height:64px;resize:vertical;
  font:inherit;font-size:13px;line-height:1.45;color:var(--ink);background:var(--bg);
  border:1px solid var(--rule);border-radius:6px;padding:6px 8px}
#chside .sllmactions{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
#chside .sllmactions button{font:inherit;font-size:11.5px;color:var(--dim);
  background:var(--bg);border:1px solid var(--rule);border-radius:5px;
  padding:3px 8px;cursor:pointer}
#chside .sllmactions button:first-child{color:var(--accent);border-color:var(--accent)}
#chside .sllmactions button:hover{filter:brightness(1.08)}
#chside .sllmactions button:disabled{opacity:.55;cursor:wait}
#chside .sllmstat{font-size:11.5px;color:var(--faint)}
#chside .sllmstat.bad{color:var(--danger)}
#chside .sllmout{margin-top:7px}
/* the row that copies the prompt (lib/llmrow.js): a small button in the accent,
   like the ones it stood among, with its size and its reminder under it */
#chside .llmrow{margin:0;font-size:11.5px}
#chside .llmrow-bar button{font:inherit;font-size:11.5px;color:var(--accent);
  background:var(--bg);border:1px solid var(--accent);border-radius:5px;
  padding:3px 8px;cursor:pointer}
#chside .llmrow-bar button:hover{filter:brightness(1.08)}
#chside .llmrow-bar button:disabled{opacity:.55;cursor:wait}
#chside .llmrow-hand textarea{font-size:11px}
#chsrc.on{color:var(--accent)}
#cloud .dict .mtout{color:var(--ink)}
#cloud .dict .mtout .mthere{color:var(--accent);font-weight:600}
#cloud .dict .mtout .mthere.mtmaybe{font-weight:400;text-decoration:underline;
  text-decoration-style:dotted;color:var(--ink)}
#cloud .dict .dpair{margin:0 0 6px}
#cloud .dict .psrc{font-family:var(--tl-font,serif);direction:var(--tl-dir,ltr);
  color:var(--ink);unicode-bidi:isolate}
#cloud .dict .pdst{color:var(--dim)}
#cloud .dict .pwhy{color:var(--faint);font-size:10.5px;font-style:italic}
#cloud .dict .dsrc{font-size:10.5px;color:var(--faint);margin-top:5px;
  font-style:italic}
#cloud .dict .dmore{display:block;margin:7px auto 0;font:inherit;font-size:11.5px;
  color:var(--dim);background:var(--bg);border:1px solid var(--rule);
  border-radius:5px;padding:3px 10px;cursor:pointer}
#cloud .dict .dmore:hover{color:var(--accent);border-color:var(--accent)}
#cloud .dict .dmore:disabled{cursor:wait;opacity:.65}
/* A dictionary entry for a common word runs long, and two panels in one
   cloud can outgrow the screen -- at which point the buttons under them are
   unreachable.  The panels scroll; the cloud itself must not, because its
   arrow is positioned against it and would scroll away from the chunk. */
/* The way to the page that sets it up.  It sits beside the switch and NOT
   behind it: somebody who has no dictionary is exactly the person who needs
   to find it, and a link only shown once the feature works is a link shown
   to the people who do not need it. */
header #lookupset{font:inherit;font-size:12.5px;color:var(--dim);
  text-decoration:none;border:1px dashed var(--rule);border-radius:7px;
  padding:4px 9px;white-space:nowrap}
header #lookupset:hover{color:var(--accent);border-color:var(--accent)}
#cloud .dict{max-height:44vh;overflow-y:auto}
#cloud .dwait{color:var(--faint);font-style:italic}
#cloud .mkrow{margin-top:6px;padding-top:6px;border-top:1px solid var(--rule)}
#cloud .mkcard,#cloud .mkcopy,#cloud .mkedit{font:inherit;font-size:11.5px;color:var(--dim);
  background:var(--bg);border:1px solid var(--rule);border-radius:5px;
  padding:3px 8px;cursor:pointer}
#cloud .mkcard:hover,#cloud .mkcopy:hover,#cloud .mkedit:hover{
  color:var(--accent);border-color:var(--accent)}

/* while a modifier key is held, the word under the cursor shows it is the
   card-sized unit (alt-click / ctrl-click opens the dashboard) */
body.altdown .wd:hover{background:var(--hl);border-radius:3px;
  box-shadow:0 0 0 2px var(--hl);cursor:copy}

.akind{display:flex;gap:6px}
#anki .akind button.on{background:var(--accent);color:var(--accent-fg);border-color:var(--accent)}
.adir{display:flex;gap:6px;flex-wrap:wrap}
#anki .dbtn,.dbtn{font:inherit;font-size:12.5px;color:var(--dim);background:transparent;
  border:1px solid var(--rule);border-radius:16px;padding:4px 11px;cursor:pointer}
#anki .dbtn:hover,.dbtn:hover{border-color:var(--accent);color:var(--accent)}
#anki .dbtn.on,.dbtn.on{background:var(--accent);border-color:var(--accent);color:var(--accent-fg)}
#anki #aopptr{margin-top:6px}
/* ---- the anki card dashboard -------------------------------------------- */
#ankiback{position:fixed;inset:0;z-index:88;background:rgba(0,0,0,.32)}
#ankiback[hidden]{display:none}
#anki{position:fixed;z-index:89;top:50%;left:50%;
  transform:translate(-50%,-50%);width:min(620px,94vw);
  max-height:90vh;overflow-y:auto;-webkit-overflow-scrolling:touch;
  background:var(--card);border:1px solid var(--rule);border-radius:12px;
  box-shadow:0 12px 40px rgba(0,0,0,.35);padding:14px 18px 12px;
  font-size:13.5px;color:var(--ink);margin:0}
#anki[hidden]{display:none}
.ahead{display:flex;align-items:center;gap:10px;color:var(--dim);
  font-size:12px;letter-spacing:.12em;text-transform:uppercase;
  margin-bottom:12px}
.ahead #aref{color:var(--accent);
  font-family:ui-monospace,Menlo,monospace;font-feature-settings:'locl' 0;
  letter-spacing:0}
.ahead .sp{flex:1}
.arow{display:flex;gap:10px;margin:7px 0;align-items:flex-start}
.alab{flex:0 0 62px;text-align:right;color:var(--faint);font-size:11.5px;
  padding-top:8px;letter-spacing:.04em}
.actl{flex:1;min-width:0}
#anki input:not([type=checkbox]),
#anki textarea,#anki select{width:100%;font:inherit;font-size:13.5px;
  background:var(--bg);color:var(--ink);border:1px solid var(--rule);
  border-radius:6px;padding:6px 9px}
#anki textarea{resize:vertical;line-height:1.5}
#anki #afa,#anki #actx,#anki #aopp{font-family:var(--tl-font,serif);font-size:19px;
  line-height:1.9}
#anki #akana,#anki #aoppkana{font-family:var(--tl-font,serif);font-size:16px;margin-top:6px}
#anki #akanarow[hidden]{display:none}
#anki #adecknew{margin-top:6px}
#anki button{font:inherit;font-size:13px;padding:5px 10px;
  border:1px solid var(--rule);background:var(--bg);color:var(--ink);
  border-radius:6px;cursor:pointer}
#anki button:hover{border-color:var(--accent)}
.achk{display:flex;gap:8px;align-items:center;color:var(--dim);
  padding-top:5px;cursor:pointer}
.anote{color:var(--faint);font-size:11.5px;margin-top:6px;line-height:1.5}
.afoot{margin-top:12px;padding-top:10px;border-top:1px solid var(--rule)}
.afoot .actl{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
/* These three wear the accent, and they have to say #anki to get it: the
   sheet's own #anki button rule (an id plus an element) outweighs a bare
   #asave or a .on class, so without the prefix the palette's accent never
   landed and the save button, the picked card type and the picked direction
   all read as the plain buttons beside them. */
#anki #asave{background:var(--accent);color:var(--accent-fg);border-color:var(--accent)}
#anki #asave:hover{filter:brightness(1.08)}
#asave .kbd,#chsave .kbd{opacity:.7;font-size:11px}
#astat{color:var(--accent);font-size:12.5px}
#apvframe{width:100%;height:430px;border:1px solid var(--rule);
  border-radius:10px;background:var(--bg)}
#apvrow[hidden]{display:none}
#apvrow .anote button{font-size:11px;padding:1px 7px;margin-left:6px}
/* where the card goes -- Anki, an exercise deck, markdown -- picked as the
   card type is, and filled with the accent by the same #anki-prefixed rule */
.atarget{display:flex;gap:6px;flex-wrap:wrap}
#anki .atarget button.on{background:var(--accent);color:var(--accent-fg);border-color:var(--accent)}
#anki .arow[hidden],#anki #ajollyrow[hidden],#anki #akjolly[hidden],#anki #abuild[hidden]{display:none}
#astat{white-space:pre-line}
#astat a{color:inherit}
/* the jolly card's two sides: a main box and a smaller one under it */
#anki #ajollyrow textarea{line-height:1.5}
#anki #ajollyrow textarea + textarea{margin-top:6px;font-size:12.5px}
/* the recording cut for the card: it plays here, and says which side it is on */
#anki #asnd[disabled]{opacity:.55;cursor:not-allowed}
#asndprev{display:flex;flex-direction:column;gap:5px;margin-top:8px}
#asndprev[hidden],#asndsides[hidden]{display:none}
.asndplay{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
#asndaudio{flex:1 1 220px;min-width:0;max-width:360px;height:36px}
#asndname{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;color:var(--dim);
  overflow-wrap:anywhere}
.asndside{display:flex;gap:14px;align-items:center;flex-wrap:wrap;color:var(--dim)}
.asndside label{display:flex;gap:5px;align-items:center;cursor:pointer}
#anki .asndside input[type=radio]{width:auto;margin:0;padding:0}
/* in place of the sides on a jolly card: where its recording went */
.ajollyinto{color:var(--faint);font-size:12px}
/* the markdown, where the clipboard would not take it: to copy by hand */
#anki #amdout{font:12px/1.5 ui-monospace,Menlo,monospace;font-feature-settings:'locl' 0}

/* ---- the narration panel: the recordings of this book -------------------
   The panel is a LIST PAGE in a sheet, and its vocabulary is the deck pages'
   (markdown/app/static/app.css: .btn and its four variants, .badge, .dk-row
   with its meta line and its action column, .dropdown, .empty, the 620px
   collapse), written out here in the reader's OWN tokens -- a reader cannot
   link app.css, and must not grow a second palette.  The mapping is
   mechanical: --chrome-panel -> --card, --chrome-bg -> --bg, --chrome-fg ->
   --ink, --chrome-mut -> --dim, --chrome-line -> --rule; the rows sit on
   --boxbg so they read as panels ON the sheet, which is already --card.  The
   three-state pill colours are --ok / --warn / --danger, which every theme
   restates.  color-mix() carries the three pill borders, as it already
   carries the kana contrast, the dirty-edit ring and the source note.     */
header #narr.cta{border-color:var(--accent);color:var(--accent)}
#narrback{position:fixed;inset:0;z-index:88;background:rgba(0,0,0,.32)}
#narrback[hidden]{display:none}
/* Wider than the 700px it was, because a row now has an action column beside
   its text; and A FLEX COLUMN rather than one block that scrolls as a whole,
   so the counts, the actions and the close button stay put while the
   recordings scroll under them -- the chunk sheet's layout (#chbox, above),
   for the chunk sheet's reason. */
#narrbox{position:fixed;z-index:89;top:50%;left:50%;
  transform:translate(-50%,-50%);width:min(820px,94vw);
  max-height:90vh;display:flex;flex-direction:column;overflow:hidden;
  background:var(--card);border:1px solid var(--rule);border-radius:12px;
  box-shadow:0 12px 40px rgba(0,0,0,.35);padding:14px 18px 0;
  font-size:13.5px;color:var(--ink);margin:0;line-height:1.45}
#narrbox[hidden]{display:none}
/* the sheet takes the focus when it opens, so Escape reaches it and Tab
   starts inside; the ring belongs on the controls, not on the box */
#narrbox:focus{outline:none}
#narrbox>.ahead{flex:0 0 auto}
#narrbox .nmain{flex:1 1 auto;min-height:0;overflow-y:auto;
  -webkit-overflow-scrolling:touch;padding:0 2px}
#narrbox .ahead #nref{color:var(--accent);letter-spacing:0;text-transform:none}
/* close stays in reach while the list scrolls under it: the same sticky foot
   the chunk sheet uses, with nothing under the button (see the comment there:
   a padding below it drew a sliver of the row beneath at some window heights) */
#narrbox .nmain>.afoot{position:sticky;bottom:0;background:var(--card);
  margin-top:14px;padding:10px 0 12px;border-top:1px solid var(--rule)}

/* ONE BUTTON VOCABULARY, the deck pages': plain, .primary (the one verb of a
   section), .danger (it destroys something), .ghost (quiet), .small (inside a
   row).  A disabled button KEEPS ITS POINTER EVENTS -- unlike the deck's
   .btn:disabled -- because every dead control here carries a title saying why
   it cannot act, and pointer-events:none swallows the tooltip that is the
   whole answer to "why is this grey". */
#narrbox button,#narrbox .nbtn{display:inline-flex;align-items:center;gap:5px;
  font:inherit;font-size:13px;line-height:1.2;padding:6px 11px;
  border:1px solid var(--rule);background:var(--bg);color:var(--ink);
  border-radius:6px;cursor:pointer;white-space:nowrap;text-decoration:none}
#narrbox button:hover,#narrbox .nbtn:hover{border-color:var(--accentlt);color:var(--accent)}
#narrbox button.primary,#narrbox .nbtn.primary{background:var(--accent);
  color:var(--accent-fg);border-color:var(--accent)}
#narrbox button.primary:hover,#narrbox .nbtn.primary:hover{filter:brightness(1.08);
  color:var(--accent-fg)}
#narrbox button.danger{color:var(--danger);
  border-color:color-mix(in srgb,var(--danger) 40%,transparent)}
#narrbox button.danger:hover{background:var(--danger);color:var(--danger-fg);
  border-color:var(--danger)}
#narrbox button.ghost,#narrbox .nbtn.ghost{background:transparent}
#narrbox button.small,#narrbox .nbtn.small{padding:3px 8px;font-size:12px}
#narrbox button:disabled{opacity:.45;cursor:not-allowed}
#narrbox button:disabled:hover{border-color:var(--rule);color:var(--ink)}
#narrbox button:focus-visible,#narrbox .nbtn:focus-visible,
#narrbox select:focus-visible,#narrbox textarea:focus-visible,
#narrbox .ndrop>summary:focus-visible{
  outline:2px solid var(--accentlt);outline-offset:1px}
/* export and import under one summary, the deck page's .dropdown in the
   reader's tokens: two doors that are one idea, out of the reading order of
   the row until they are wanted */
#narrbox .ndrop{position:relative}
#narrbox .ndrop>summary{list-style:none}
#narrbox .ndrop>summary::-webkit-details-marker{display:none}
#narrbox .nmenu{position:absolute;left:0;top:calc(100% + 4px);z-index:2;
  display:flex;flex-direction:column;min-width:210px;background:var(--card);
  border:1px solid var(--rule);border-radius:8px;padding:4px;
  box-shadow:0 8px 26px rgba(0,0,0,.18)}
#narrbox .nmenu a,#narrbox .nmenu .nimport{display:block;padding:6px 9px;
  border-radius:5px;color:var(--ink);text-decoration:none;cursor:pointer;
  font-size:12.5px;white-space:nowrap}
#narrbox .nmenu a:hover,#narrbox .nmenu .nimport:hover{background:var(--hl);
  color:var(--accent)}
#narrbox .nmenu a[hidden]{display:none}
/* the panel had no select rule at all, so two 147-option pickers stood in a
   themed sheet as raw browser widgets; this is the fold sheet's rule */
#narrbox select{font:inherit;font-size:13px;max-width:100%;background:var(--bg);
  color:var(--ink);border:1px solid var(--rule);border-radius:6px;padding:5px 8px}
#narrbox code,#narrbox pre{font-family:ui-monospace,Menlo,monospace;font-size:12px}
#narrbox pre{background:var(--bg);border:1px solid var(--rule);border-radius:6px;
  padding:8px 10px;white-space:pre-wrap;word-break:break-word;margin:6px 0 0;
  max-height:220px;overflow:auto;direction:ltr}
#narrbox pre[hidden]{display:none}
#narrbox textarea{width:100%;font:inherit;font-size:12.5px;background:var(--bg);
  color:var(--ink);border:1px solid var(--rule);border-radius:6px;padding:6px 9px;
  resize:vertical;line-height:1.5}
#narrbox .nstate{color:var(--dim);font-size:12.5px}
#narrbox .nstate b{color:var(--ink);font-weight:600}
/* a tick is GREEN here and not the accent: the old .ok wore --accent, so a
   "rapidfuzz ✓" read as a link sitting beside a red ✗ */
#narrbox .ok{color:var(--ok)}
#narrbox .bad{color:var(--danger)}
#narrbox .anote{color:var(--faint);font-size:11.5px;margin-top:6px;line-height:1.5}

/* the head card: counts, problems, what to do about them, one row of actions */
#narrbox .nhead{background:var(--boxbg);border:1px solid var(--rule);
  border-radius:10px;padding:10px 12px;margin-bottom:10px}
#narrbox #nsum{font-size:13.5px;color:var(--dim);font-variant-numeric:tabular-nums}
#narrbox #nsum b{color:var(--ink);font-weight:600}
#narrbox #nwarn{margin-top:5px;color:var(--danger);font-size:12.5px;line-height:1.5}
#narrbox #nwarn[hidden]{display:none}
/* not a fault, so not red: the one sentence that says what a book in this
   state can actually do next */
#narrbox #nnote{margin-top:5px;color:var(--dim);font-size:12.5px;line-height:1.5}
#narrbox #nnote[hidden]{display:none}
#narrbox #nnote b{color:var(--ink);font-weight:600}
#narrbox .nacts{display:flex;flex-wrap:wrap;align-items:center;gap:6px}
#narrbox .nheadacts{margin-top:9px}
#narrbox .npush{margin-left:auto}
#narrbox #nwork{margin-top:6px}
#narrbox #nwork:empty{display:none}
/* the upload bar: a recording is hundreds of megabytes, and this is the only
   feedback for the longest thing that happens here */
#narrbox .nbar{height:4px;background:var(--rule);border-radius:2px;margin-top:8px;
  overflow:hidden}
#narrbox .nbar[hidden]{display:none}
#narrbox .nbar i{display:block;height:100%;width:0;background:var(--accent);
  transition:width .2s}

/* the page on screen is from before */
#narrbox .nredo{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  margin-bottom:10px;padding:8px 12px;border-radius:8px;font-size:12.5px;
  color:var(--ink);background:var(--hl);border:1px solid var(--accentlt)}
#narrbox .nredo[hidden]{display:none}

/* the sections that open from the head */
#narrbox .nsec{background:var(--boxbg);border:1px solid var(--rule);
  border-radius:10px;padding:10px 12px;margin-bottom:10px}
#narrbox .nsec[hidden]{display:none}
#narrbox .nsechead{color:var(--dim);font-size:11.5px;letter-spacing:.1em;
  text-transform:uppercase;margin-bottom:8px}
#narrbox .nfield{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:6px 0}
#narrbox .nfieldlab{color:var(--dim);font-size:12.5px}
#narrbox .nsep{color:var(--faint)}
#narrbox .npick{margin:2px 0 8px}
#narrbox .npick[hidden]{display:none}
#narrbox .nlist2{display:flex;flex-direction:column;align-items:flex-start;gap:6px}
/* the found-elsewhere rows, which have never had a rule of their own: a file
   somewhere on the disk, its size and where it was found, on one line that
   reads as a row rather than as a button with words trailing off it */
#narrbox .nfitem{display:flex;align-items:center;gap:8px;flex-wrap:wrap;
  width:100%;padding:6px 8px;background:var(--card);border:1px solid var(--rule);
  border-radius:8px}
#narrbox .nfitem .nstate{overflow-wrap:anywhere}

/* the list head, and its count -- the deck's .dk-browse-count */
#narrbox .nlisthead{display:flex;align-items:baseline;gap:10px;margin:14px 0 0}
#narrbox .nlisthead[hidden]{display:none}
#narrbox .nlabel{color:var(--dim);font-size:11.5px;letter-spacing:.1em;
  text-transform:uppercase}
#narrbox .ncount{margin-left:auto;color:var(--dim);font-size:12px;
  font-variant-numeric:tabular-nums;white-space:nowrap}

/* THE RECORDINGS.  One bordered row each, the deck page's .dk-row: the text
   in a column that may shrink, the buttons in a column that may not, and a
   drawer across the foot that opens IN PLACE -- which is where what a
   recording covers is edited now, instead of a pair of selects at the other
   end of the sheet.  The class is .nitem, which is what the rows have always
   been called; until now it had no rule anywhere in the repository, which is
   most of what "hard to read" meant. */
#narrbox #nlist{display:flex;flex-direction:column;gap:8px;margin-top:8px}
#narrbox #nlist[hidden]{display:none}
#narrbox .nitem{display:grid;grid-template-columns:minmax(0,1fr) auto;
  gap:4px 14px;align-items:start;padding:10px 12px;background:var(--boxbg);
  border:1px solid var(--rule);border-radius:10px;transition:border-color .12s}
#narrbox .nitem:hover{border-color:var(--accentlt)}
#narrbox .nitem.open{border-color:var(--accent)}
#narrbox .ntog{grid-column:1;display:flex;flex-direction:column;
  align-items:flex-start;gap:3px;min-width:0;padding:0;border:0;background:none;
  color:var(--ink);font:inherit;text-align:start;cursor:pointer}
#narrbox .ntog:hover{border-color:transparent;color:var(--accent)}
#narrbox .ntog:focus-visible{outline:2px solid var(--accentlt);outline-offset:3px;
  border-radius:4px}
#narrbox .nkick{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
#narrbox .nname{font-size:13.5px;font-weight:600;overflow-wrap:anywhere;
  text-align:start}
#narrbox .nmeta{grid-column:1;display:flex;flex-wrap:wrap;align-items:center;
  gap:2px 10px;color:var(--dim);font-size:12px;font-variant-numeric:tabular-nums}
#narrbox .nitem .nacts{grid-column:2;grid-row:1 / span 2;align-self:start;gap:5px}
/* WHY THE GREY BUTTON IS GREY, on a screen that has no hover.  A title is the
   whole answer here and a touch screen never shows one, so the row carries
   the sentence itself where there is no pointer to hover with. */
#narrbox .nwhy{grid-column:1 / -1;display:none;color:var(--dim);font-size:11.5px;
  line-height:1.5}
#narrbox .nwhy:empty{display:none}
/* AND WHAT THE LAST RUN SAID.  A toast lasts four seconds and holds one line;
   timestamp.py's refusals are neither, so the row keeps its own. */
#narrbox .nsay{grid-column:1 / -1;margin-top:2px;color:var(--dim);font-size:12.5px;
  line-height:1.5;overflow-wrap:anywhere}
#narrbox .nsay:empty{display:none}
#narrbox .nsay.bad{color:var(--danger)}
#narrbox .ndraw{grid-column:1 / -1;margin-top:8px;padding-top:8px;
  border-top:1px solid var(--rule);cursor:default}
#narrbox .ndraw[hidden]{display:none}
#narrbox .ndraw textarea{flex:1 1 220px;min-width:0}
/* the state marks: parseh.css's own .tag (linked by the reader), squared off
   to the deck's .badge and given three meanings -- green for done, amber for
   a guess, red for gone */
#narrbox .tag{font-size:11px;white-space:nowrap;border-radius:5px;padding:1px 6px}
#narrbox .tag.good{color:var(--ok);border-color:color-mix(in srgb,var(--ok) 40%,transparent)}
#narrbox .tag.warn{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 45%,transparent)}
#narrbox .tag.bad{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 45%,transparent)}
#narrbox .tag.id{font-family:ui-monospace,Menlo,monospace;font-size:10.5px}

/* nothing here yet -- the deck's .empty, with the next action named in bold */
#narrbox .nempty{text-align:center;color:var(--dim);padding:26px 0;font-size:13px}
#narrbox .nempty[hidden]{display:none}
#narrbox .nempty p{max-width:34rem;margin:0 auto 8px;line-height:1.6}
#narrbox .nempty b{color:var(--ink)}

/* a page with no server behind it: every door is dead, and the warn line
   says so -- the controls are dimmed rather than left to fail one by one */
#narrbox.noserver .nacts,#narrbox.noserver .nsec,#narrbox.noserver #nlist{
  opacity:.45;pointer-events:none}
/* A RUN IS OUT, AND IT IS THE WHOLE PANEL THAT WAITS.  align rebuilds the
   reader under every other row too, so no second run may start beside it;
   the buttons carry a real disabled, and these are the controls that cannot
   (a file input's label, a summary). */
#narrbox.working .nbtn,#narrbox.working .ndrop{opacity:.45;pointer-events:none}
#narrbox.working .nitem{opacity:.75}

/* THE QUESTION, ABOVE THE PANEL.  Its own backdrop, like the divide sheet's
   and for the same reason: one shared backdrop would mean a click on the dark
   closed the sheet underneath and left the question standing. */
#naskback{position:fixed;inset:0;z-index:90;background:rgba(0,0,0,.3)}
#naskback[hidden]{display:none}
#naskbox{position:fixed;z-index:91;top:50%;left:50%;
  transform:translate(-50%,-50%);width:min(460px,92vw);
  background:var(--card);border:1px solid var(--rule);border-radius:12px;
  box-shadow:0 12px 40px rgba(0,0,0,.35);padding:14px 16px 12px;
  font-size:13.5px;color:var(--ink);line-height:1.5}
#naskbox[hidden]{display:none}
#naskbox h3{margin:0 0 6px;font-size:14.5px;font-weight:600}
#naskbox .nstate{color:var(--dim);font-size:12.5px}
#naskbox .nstate code{font-family:ui-monospace,Menlo,monospace;font-size:12px}
#naskbox .achk{margin-top:10px;color:var(--ink)}
/* the refusal, kept in the sheet that asked: the whole point of not closing */
#naskbox #naskerr{margin-top:10px;white-space:pre-wrap;word-break:break-word;
  max-height:170px;overflow:auto}
#naskbox #naskerr.bad{color:var(--danger)}
#naskbox #naskerr[hidden]{display:none}
#naskbox .naskrow{display:flex;gap:8px;justify-content:flex-end;margin-top:14px}
#naskbox button{font:inherit;font-size:13px;padding:6px 11px;border:1px solid var(--rule);
  background:var(--bg);color:var(--ink);border-radius:6px;cursor:pointer}
#naskbox button:hover{border-color:var(--accentlt);color:var(--accent)}
#naskbox button:disabled{opacity:.45;cursor:not-allowed}
#naskbox button.primary{background:var(--accent);color:var(--accent-fg);
  border-color:var(--accent)}
#naskbox button.primary:hover{filter:brightness(1.08);color:var(--accent-fg)}
#naskbox button.danger{color:var(--danger);
  border-color:color-mix(in srgb,var(--danger) 40%,transparent)}
#naskbox button.danger:hover{background:var(--danger);color:var(--danger-fg);
  border-color:var(--danger)}

/* A PHONE.  The panel was named in none of the reader's three media queries,
   so on a 390px screen its rows and its action column simply overflowed.
   620px is the deck pages' own breakpoint for exactly this collapse, and it
   is also where a title stops being an explanation: .nwhy comes out. */
@media(max-width:620px){
  #narrbox .nitem{grid-template-columns:minmax(0,1fr)}
  #narrbox .nitem .nacts{grid-column:1;grid-row:auto;margin-top:6px}
  #narrbox .nwhy{display:block}
  #narrbox .nwhy:empty{display:none}
  #narrbox .nheadacts>*{flex:1 1 auto;justify-content:center}
  #narrbox .ndrop{flex:1 1 auto}
  #narrbox .ndrop>summary{justify-content:center}
  #narrbox .nmenu{left:auto;right:0}
  #narrbox .npush{margin-left:0}
  #narrbox .nfield{align-items:stretch;flex-direction:column;gap:4px}
  #narrbox .nfield select{width:100%}
}
/* ---- the fold sheet: which runs of paragraphs are folded away.  Its own
   backdrop and box, as every sheet here has: WITHOUT THESE IT OPENS IN THE
   NORMAL FLOW at the foot of the body, so the button looks dead -- it is not,
   the sheet is simply somewhere nobody is looking.  .nrow and .nstate are
   #narrbox's own rules, scoped to that id, so this sheet restates them rather
   than appearing to inherit something it cannot. */
#fdback{position:fixed;inset:0;z-index:88;background:rgba(0,0,0,.32)}
#fdback[hidden]{display:none}
#fdbox{position:fixed;z-index:89;top:50%;left:50%;
  transform:translate(-50%,-50%);width:min(560px,94vw);
  max-height:90vh;overflow-y:auto;-webkit-overflow-scrolling:touch;
  background:var(--card);border:1px solid var(--rule);border-radius:12px;
  box-shadow:0 12px 40px rgba(0,0,0,.35);padding:14px 18px 12px;
  font-size:13.5px;color:var(--ink);margin:0;line-height:1.45}
#fdbox[hidden]{display:none}
#fdbox .nrow{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
#fdbox .nstate{color:var(--dim);font-size:12.5px}
#fdbox #fdsum{margin:-4px 0 8px;font-size:13.5px}
#fdbox select{font:inherit;font-size:13px;max-width:100%;
  background:var(--bg);color:var(--ink);border:1px solid var(--rule);
  border-radius:6px;padding:5px 8px}
#fdbox button{font:inherit;font-size:13px;padding:5px 10px;
  border:1px solid var(--rule);background:var(--bg);color:var(--ink);
  border-radius:6px;cursor:pointer;white-space:nowrap}
#fdbox button:hover{border-color:var(--accent)}
#fdbox button.primary{background:var(--accent);color:var(--accent-fg);
  border-color:var(--accent)}
#fdbox #fdlist{flex-direction:column;align-items:flex-start;gap:6px}
/* the only thing the sheet ever says back, and a refusal has to look like one:
   every sibling gives its status line a size, a colour and a .bad */
#fdbox #fdstat{font-size:12.5px;color:var(--accent)}
#fdbox #fdstat.bad{color:var(--danger)}
#fdbox .fdrun{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
#fdbox .fdrun .fdsee{border:0;background:none;padding:2px 0;color:var(--ink);
  text-align:start;white-space:normal;text-decoration:underline dotted;
  text-underline-offset:3px}
#fdbox .fdrun .fdsee:hover{color:var(--accent)}

/* ---- the outline a stretch of the book is picked from (outlinePicker) ----
   The same control in the fold sheet, the sections sheet and the narration
   panel: rows a finger can hit, the pick tinted, its ends labelled, and the
   book's own words in the book's own face and direction.  Its buttons take
   each sheet's button look and are only made smaller here -- which has to
   say the sheet's id, since every sheet styles its buttons through it. */
.olwrap{margin:2px 0 4px}
.oltools{display:flex;gap:6px;align-items:center;margin-bottom:6px}
.oltools .olq{flex:1;min-width:0;font:inherit;font-size:13px;background:var(--bg);
  color:var(--ink);border:1px solid var(--rule);border-radius:6px;padding:5px 8px}
#fdbox .olwrap button,#secbox .olwrap button,#narrbox .olwrap button,
#rgbox .olwrap button{font-size:12px;padding:3px 9px}
.oltree{list-style:none;margin:0;padding:3px;max-height:min(44vh,360px);overflow:auto;
  border:1px solid var(--rule);border-radius:8px;background:var(--bg);
  overscroll-behavior:contain}
.oltree ul{list-style:none;margin:0;padding:0}
.oltree li{outline:none}
.oltree li[aria-expanded="false"] > ul{display:none}
.olr{display:flex;align-items:center;gap:8px;min-height:32px;border-radius:6px;
  padding:2px 8px 2px calc(4px + (var(--lv,1) - 1) * 20px);cursor:pointer;
  user-select:none;-webkit-user-select:none}
.olr:hover{box-shadow:inset 0 0 0 1px var(--rule);background:var(--card)}
.oltw{flex:0 0 22px;height:26px;display:inline-flex;align-items:center;
  justify-content:center;border-radius:5px;color:var(--faint);font-size:11px}
.oltw:hover{background:var(--hl);color:var(--accent)}
li[aria-expanded] > .olr > .oltw::before{content:"\25B8";transition:transform .12s}
li[aria-expanded="true"] > .olr > .oltw::before{transform:rotate(90deg)}
.olk{flex:0 0 auto;color:var(--dim);font-size:12px;white-space:nowrap;
  font-variant-numeric:tabular-nums}
li.ol-ch > .olr > .olk{color:var(--ink);font-weight:600}
li.ol-sec > .olr > .olk{color:var(--accent)}
.olt{flex:1;min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;
  font-family:var(--tl-font,serif);font-size:15px;line-height:1.8;color:var(--ink)}
li.ol-ch > .olr > .olt,li.ol-sec > .olr > .olt{font-size:14px}
.olc{flex:0 0 auto;color:var(--faint);font-size:11.5px;white-space:nowrap;
  font-variant-numeric:tabular-nums}
.olg{flex:0 0 auto;display:inline-flex;gap:4px}
.oltag{font-size:10.5px;line-height:1.5;padding:0 6px;border-radius:9px;
  border:1px solid var(--rule);color:var(--dim);white-space:nowrap}
.oltag.olend{background:var(--accent);border-color:var(--accent);color:var(--accent-fg)}
.oltag.olfold{border-style:dashed}
.oltag.olrec{font-family:ui-monospace,Menlo,monospace}
li.in > .olr{background:var(--hl)}
li.in > .olr:hover{background:var(--hl)}
li.part > .olr{box-shadow:inset 3px 0 0 var(--accent)}
li[aria-disabled="true"] > .olr{cursor:default}
li[aria-disabled="true"] > .olr > .olk,li[aria-disabled="true"] > .olr > .olt{opacity:.5}
li:focus-visible > .olr{outline:2px solid var(--accent);outline-offset:-2px}
.oltree.stretching .olr{cursor:crosshair}
.oltree.filtering li:not(.olpath):not(.olhit){display:none}
.oltree.filtering li.olpath[aria-expanded] > ul{display:block}
.olnone{color:var(--dim);font-size:12.5px;padding:6px 2px}
.olnone[hidden]{display:none}
.olbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px}
.olsay{flex:1;min-width:180px;font-size:13.5px;color:var(--ink)}
.olhint{color:var(--faint);font-size:11.5px;margin-top:4px;line-height:1.5}
.olhint:empty{display:none}

/* ---- the sections sheet: a chapter's name, and the sections inside it.
   #fdbox's rules, restated for this id rather than borrowed: .nrow and
   .nstate are scoped to an id everywhere in this file, so a sheet that
   appeared to inherit them would be inheriting nothing and open in the
   normal flow at the foot of the body, where nobody is looking. */
#secback{position:fixed;inset:0;z-index:88;background:rgba(0,0,0,.32)}
#secback[hidden]{display:none}
#secbox{position:fixed;z-index:89;top:50%;left:50%;
  transform:translate(-50%,-50%);width:min(620px,94vw);
  max-height:90vh;overflow-y:auto;-webkit-overflow-scrolling:touch;
  background:var(--card);border:1px solid var(--rule);border-radius:12px;
  box-shadow:0 12px 40px rgba(0,0,0,.35);padding:14px 18px 12px;
  font-size:13.5px;color:var(--ink);margin:0;line-height:1.45}
#secbox[hidden]{display:none}
#secbox .nrow{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
#secbox .nstate{color:var(--dim);font-size:12.5px}
#secbox #secsum{margin:-4px 0 8px;font-size:13.5px}
#secbox select,#secbox input[type=text]{font:inherit;font-size:13px;max-width:100%;
  background:var(--bg);color:var(--ink);border:1px solid var(--rule);
  border-radius:6px;padding:5px 8px}
#secbox input[type=text]{flex:1;min-width:150px}
#secbox button{font:inherit;font-size:13px;padding:5px 10px;
  border:1px solid var(--rule);background:var(--bg);color:var(--ink);
  border-radius:6px;cursor:pointer;white-space:nowrap}
#secbox button:hover{border-color:var(--accent)}
#secbox button.primary{background:var(--accent);color:var(--accent-fg);
  border-color:var(--accent)}
#secbox #secpick{margin:0 0 6px}
#secbox #secstat{font-size:12.5px;color:var(--accent)}
#secbox #secstat.bad{color:var(--danger)}
/* ---- the region sheet: a stretch of the book glossed by an LLM.  The fold
   sheet's box and backdrop, restated for this id for the reason the sections
   sheet gives above, and wider: the answer box and the report under it want
   the room.  Every colour is one of the theme's variables, so the sheet is
   the same sheet in the light theme, the dark one and sepia. */
#rgback{position:fixed;inset:0;z-index:88;background:rgba(0,0,0,.32)}
#rgback[hidden]{display:none}
#rgbox{position:fixed;z-index:89;top:50%;left:50%;
  transform:translate(-50%,-50%);width:min(640px,94vw);
  max-height:90vh;overflow-y:auto;-webkit-overflow-scrolling:touch;
  background:var(--card);border:1px solid var(--rule);border-radius:12px;
  box-shadow:0 12px 40px rgba(0,0,0,.35);padding:14px 18px 12px;
  font-size:13.5px;color:var(--ink);margin:0;line-height:1.45}
#rgbox[hidden]{display:none}
/* "the LLM's answer" is a label to read, not a word to glance at */
#rgbox .alab{flex:0 0 80px}
#rgbox .nrow{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
#rgbox .nstate{color:var(--dim);font-size:12.5px}
#rgbox button{font:inherit;font-size:13px;padding:5px 10px;
  border:1px solid var(--rule);background:var(--bg);color:var(--ink);
  border-radius:6px;cursor:pointer;white-space:nowrap}
#rgbox button:hover{border-color:var(--accent)}
#rgbox button.primary{background:var(--accent);color:var(--accent-fg);
  border-color:var(--accent)}
#rgbox button.primary:hover{filter:brightness(1.08)}
#rgbox button:disabled{opacity:.45;cursor:not-allowed;filter:none}
#rgbox button:not(.primary):disabled:hover{border-color:var(--rule)}
/* ARMED: the second press replaces glosses somebody wrote, so it wears the
   colour the header's "really stop?" and every other destructive second
   press here wears -- and its words say how many */
#rgbox #rgfill.armed{background:var(--danger);border-color:var(--danger);
  color:var(--danger-fg);white-space:normal}
#rgbox .achk{color:var(--ink);align-items:flex-start}
#rgbox .achk input{margin-top:3px}
#rgbox .achk + .anote{margin:0 0 4px 26px}
#rgbox textarea{width:100%;font-family:ui-monospace,Menlo,monospace;font-size:12px;
  line-height:1.5;background:var(--bg);color:var(--ink);border:1px solid var(--rule);
  border-radius:6px;padding:6px 9px;resize:vertical;direction:ltr;text-align:left}
#rgbox #rgans{min-height:8em}
#rgbox #rgsum{margin-top:6px;white-space:pre-line;color:var(--ink)}
#rgbox #rgsum:empty{display:none}
#rgbox #rgsum.bad{color:var(--danger)}
#rgbox #rgsum .rgnote{display:block;color:var(--dim);font-size:12px}
#rgoutrow[hidden],#rgreprow[hidden]{display:none}
#rgoutrow{margin-top:6px}
/* the report: the three counts, then a list for each thing that did not go
   in as asked, each folded to its heading once it is long */
#rgbox #rgreport{font-size:12.5px;line-height:1.5;color:var(--ink)}
#rgbox #rgreport .rgsaid{white-space:pre-line}
#rgbox #rgreport .rgsaid.bad{color:var(--danger)}
#rgbox #rgreport b{color:var(--accent)}
#rgbox #rgreport details{margin-top:6px;border-top:1px solid var(--rule);padding-top:4px}
#rgbox #rgreport summary{cursor:pointer;color:var(--dim)}
#rgbox #rgreport summary:hover{color:var(--accent)}
#rgbox #rgreport ul{margin:4px 0 0;padding-inline-start:18px;max-height:200px;
  overflow:auto;overscroll-behavior:contain}
#rgbox #rgreport li{margin:2px 0;overflow-wrap:anywhere}
#rgbox #rgreport .why{color:var(--dim)}
/* ---- the book-info sheet: title, author, year, blurb -- book.json's own
   fields, not a chunk's.  Built on .ahead/.arow/.alab/.actl/.afoot, the same
   generic classes #anki's markup defines, so only the sheet's own position
   and its inputs' width need restating here. */
#bmback{position:fixed;inset:0;z-index:88;background:rgba(0,0,0,.32)}
#bmback[hidden]{display:none}
#bmbox{position:fixed;z-index:89;top:50%;left:50%;
  transform:translate(-50%,-50%);width:min(480px,94vw);
  max-height:90vh;overflow-y:auto;-webkit-overflow-scrolling:touch;
  background:var(--card);border:1px solid var(--rule);border-radius:12px;
  box-shadow:0 12px 40px rgba(0,0,0,.35);padding:14px 18px 12px;
  font-size:13.5px;color:var(--ink);margin:0}
#bmbox[hidden]{display:none}
#bmbox input,#bmbox textarea{width:100%;font:inherit;font-size:13.5px;
  background:var(--bg);color:var(--ink);border:1px solid var(--rule);
  border-radius:6px;padding:6px 9px}
#bmbox textarea{resize:vertical;line-height:1.5}
#bmtitle,#bmauthor{font-family:var(--tl-font,inherit);font-size:16px}
#bmbox button{font:inherit;font-size:13px;padding:5px 10px;
  border:1px solid var(--rule);background:var(--bg);color:var(--ink);
  border-radius:6px;cursor:pointer}
#bmbox button:hover{border-color:var(--accent)}
#bmbox #bmsave{background:var(--accent);color:var(--accent-fg);border-color:var(--accent)}
#bmbox #bmsave:hover{filter:brightness(1.08)}
#bmstat{font-size:12.5px;color:var(--accent)}
#bmstat.bad{color:var(--danger)}
/* ---- writing a chunk ----------------------------------------------------
   Always on, as it is in the video player: there is no mode to turn on first,
   and a click on a chunk goes on doing what it did -- it plays, or opens the
   cloud.  The door is a pencil: the gloss cloud's (fillCloud) and, over a
   chunk that opens no cloud -- the rows of pass 2, any pass with hover mode
   off -- one of its own at the corner of the chunk under the pointer, or on a
   touch screen of the chunk last tapped (#chpen, placed by penAt).         */
#chpen{position:fixed;z-index:79;font:inherit;font-size:12px;line-height:1;
  padding:3px 6px;border:1px solid var(--rule);border-radius:6px;
  background:var(--card);color:var(--dim);cursor:pointer;
  box-shadow:0 2px 6px rgba(0,0,0,.14)}
#chpen:hover{color:var(--accent);border-color:var(--accent)}
#chpen[hidden]{display:none}
#chback{position:fixed;inset:0;z-index:88;background:rgba(0,0,0,.32)}
#chback[hidden]{display:none}
/* A COLUMN OF ITS OWN FOR THE FIELDS, AND ONE FOR THE SOURCES.  The sheet is
   a flex column -- the head, then .chcols -- and it no longer scrolls as a
   whole: .chmain (the fields) and #chside (the sources, when open) scroll
   each on their own, so a source and the box it is meant to fill are on the
   screen together, and the head with its close button never scrolls away. */
#chbox{position:fixed;z-index:89;top:50%;left:50%;
  transform:translate(-50%,-50%);width:min(680px,94vw);
  max-height:90vh;display:flex;flex-direction:column;overflow:hidden;
  background:var(--card);border:1px solid var(--rule);border-radius:12px;
  box-shadow:0 12px 40px rgba(0,0,0,.35);padding:14px 18px 12px;
  font-size:13.5px;color:var(--ink);margin:0}
#chbox[hidden]{display:none}
#chbox>.ahead{flex:0 0 auto}
#chbox .chcols{display:flex;gap:18px;flex:1 1 auto;min-height:0}
/* the few pixels of padding are the focus ring's: a scrolling column clips
   whatever is drawn outside its box, and the ring of a full-width textarea is */
#chbox .chmain{flex:1 1 auto;min-width:0;overflow-y:auto;
  -webkit-overflow-scrolling:touch;padding:0 4px}
/* save stays in reach while the fields scroll under it.  No z-index (being
   positioned already paints it over the fields) and nothing under the
   buttons: with either, Chromium drew a one-pixel sliver of the row below
   the footer whenever the column's height ended near a half pixel -- at
   1920x1080, 1366x768 and 2560x1440, never at 1280x800, found by reading
   the pixels under the buttons across five sizes and three chunks. */
#chbox .chmain>.afoot{position:sticky;bottom:0;
  background:var(--card);margin-bottom:0;padding-bottom:0}
/* THE WINDOW GROWS TO THE LEFT.  Opening the sources used to push them in
   above the fields; now the sheet keeps its right edge exactly where the
   680px sheet had it -- right:calc(50% - 340px) is that edge, in the same
   units left:50% is in, so a page scrollbar cannot shift it -- and takes
   the room to its left, down to 16px from the window's edge.  The fields
   keep their 642px while there is room for both, and give up some only
   when the column would drop under its 260px.  Measured at 1280x800: the
   sheet goes from 680px to 964px, the column is 266px, and the text box
   is at x=425 and 532px wide before and after, at the same height; at
   1920 the column reaches its 480px.  Physical left in every book, right
   to left included: the sheet is the page's chrome (dir=ltr on it), and
   only its text boxes are the book's. */
#chbox.side{left:auto;right:max(16px,calc(50% - 340px));transform:translateY(-50%);
  width:min(1180px,calc(100% - max(16px,calc(50% - 340px)) - 16px))}
#chbox.side .chmain{flex:0 1 642px}
/* A NARROW WINDOW HAS NO LEFT TO GROW INTO, so the sheet is what it always
   was there -- one column that scrolls as a whole -- with the fields first
   and the sources under them: a thumb reaches the box before the crowd
   around it, and what is looked up is a scroll away rather than on top. */
@media(max-width:820px){
  #chbox{display:block;overflow-y:auto;-webkit-overflow-scrolling:touch}
  #chbox.side{left:50%;right:auto;transform:translate(-50%,-50%);width:min(680px,94vw)}
  #chbox .chcols{flex-direction:column;gap:12px}
  #chbox .chmain,#chbox.side .chmain{flex:0 0 auto;overflow:visible;padding:0}
  #chside{order:2;flex:0 0 auto;min-width:0;max-width:none;contain:none;
    overflow:visible}
}
#chbox .ahead #chref{color:var(--accent);letter-spacing:0;text-transform:none;
  font-family:ui-monospace,Menlo,monospace;font-feature-settings:'locl' 0}
/* "transliteration" and "pronunciation" are the labels here, not "front" */
#chbox .alab{flex:0 0 92px}
/* the sheet's own fields and buttons, and not the word strip's: it brings
   its chips, reading boxes and ✂ from lib/parseh.css, and an id outweighs
   every class there.  :where() adds nothing to the weight these always had */
#chbox input:where(:not(.wordstrip *)):not([type=checkbox]),#chbox textarea:where(:not(.wordstrip *)){width:100%;font:inherit;font-size:13.5px;
  background:var(--bg);color:var(--ink);border:1px solid var(--rule);
  border-radius:6px;padding:6px 9px}
#chbox textarea:where(:not(.wordstrip *)){resize:vertical;line-height:1.5}
#chbox #chfa{font-family:var(--tl-font,serif);font-size:19px;line-height:1.9}
#chbox #chkana{font-family:var(--tl-font,serif);font-size:16px}
/* the vocabulary is source, so it is set as source: monospace, and LTR
   whatever the book's direction -- \dw{}{} runs left to right in the .tex,
   and an RTL box would put the backslash on the wrong end of it */
#chbox #chvoc{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;
  direction:ltr;text-align:left}
#chbox button:where(:not(.wordstrip *)){font:inherit;font-size:13px;padding:5px 10px;
  border:1px solid var(--rule);background:var(--bg);color:var(--ink);
  border-radius:6px;cursor:pointer}
#chbox button:where(:not(.wordstrip *)):hover{border-color:var(--accent)}
/* the id-plus-element rule above outweighs a bare #chsave, exactly as it does
   in the anki sheet, so the accent has to be asked for by the same name */
#chbox #chsave{background:var(--accent);color:var(--accent-fg);border-color:var(--accent)}
#chbox #chsave:hover{filter:brightness(1.08)}
/* delete gloss takes away what somebody wrote -- in one press, since undo is
   beside it -- so it says so in the danger colour, and fills with it only
   under the pointer.  Disabled on a chunk with nothing to delete. */
#chbox #chdel{color:var(--danger);
  border-color:color-mix(in srgb,var(--danger) 40%,transparent)}
#chbox #chdel:hover{background:var(--danger);color:var(--danger-fg);
  border-color:var(--danger)}
#chbox #chdel:disabled{opacity:.45;cursor:not-allowed;background:var(--bg);
  color:var(--danger);border-color:color-mix(in srgb,var(--danger) 40%,transparent)}
#chbox #chdel[hidden],#chbox #chundo[hidden]{display:none}
/* and the chosen colour, for the same reason: #chbox button beat the bare
   .dbtn.on, so all five chips computed one background in every theme and
   nothing on the sheet said which colour the chunk has, or that clicking one
   had done anything.  Filled with the accent, like the picked card type
   beside it (#anki .akind button.on) and the picked direction (#anki .dbtn.on) */
#chbox .dbtn.on{background:var(--accent);border-color:var(--accent);
  color:var(--accent-fg)}
#chbox code{font-family:ui-monospace,Menlo,monospace;font-size:11.5px}
/* --- the gap between two lines, and the notes that sit in it ---------
   A note is not shown in the page: the reading is the point.  What is shown
   is that there IS one, in the seam it was written into -- and a + to write
   one, at half strength until the pointer is in the seam -- a + nobody can
   see is a + nobody knows about, and one at full strength between every pair
   of lines would be a page of buttons with a book behind it. */
.gap{display:flex;align-items:center;gap:6px;min-height:16px;
  margin:-16px 0 2px;flex-wrap:wrap}
.gap.last{margin:8px 0 30px}
.gap .plus{opacity:.5;transition:opacity .12s;font-size:12px;line-height:1;
  padding:1px 7px;border:1px dashed var(--rule);border-radius:10px;
  background:none;color:var(--faint);cursor:pointer}
.gap:hover .plus,.gap .plus:focus{opacity:1}
.gap .plus:hover{border-style:solid;border-color:var(--accent);color:var(--accent)}
/* the same pill in the seam and on a fold bar: one note looks like one note
   wherever the page has had to put it */
.gap .mark,.fnotes .mark{font:inherit;font-size:11.5px;line-height:1.3;
  padding:2px 9px;cursor:pointer;
  border:1px solid var(--rule);border-radius:10px;background:var(--card);
  color:var(--dim);max-width:min(52ch,80%);overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.gap .mark:hover,.fnotes .mark:hover{border-color:var(--accent);color:var(--accent)}
.gap .mark::before,.fnotes .mark::before{content:'\270e\00a0';color:var(--accent)}
.gap .mark.adrift,.fnotes .mark.adrift{border-style:dashed}
/* A LOOK AT A NOTE BEFORE IT IS OPENED.  The mark is a pill cut to one line
   with an ellipsis, and opening it covers the whole page with the studio: a
   reader wondering what a note says had to leave the text to find out.  The
   peek is the note's title and the first few lines of it, as plain text, the
   gloss cloud's card and shadow -- over the page (z 82, above the cloud's
   80) and under every sheet and its backdrop (88 and up).  Each paragraph of
   it takes the direction of its own first letter: a note about a Persian
   line is as likely to be written in Persian as in English. */
#ntpeek{position:fixed;z-index:82;max-width:min(360px,90vw);max-height:40vh;
  overflow:hidden;background:var(--card);border:1px solid var(--rule);
  border-radius:10px;box-shadow:0 8px 28px rgba(0,0,0,.22);padding:8px 12px;
  font-size:12.5px;line-height:1.5;color:var(--ink);text-align:start}
#ntpeek .pkt{color:var(--accent);font-weight:600;font-size:13px;
  unicode-bidi:plaintext;overflow-wrap:anywhere}
#ntpeek .pkx{margin-top:3px;white-space:pre-line;unicode-bidi:plaintext;
  overflow-wrap:anywhere}
#ntpeek .pkf{margin-top:5px;color:var(--faint);font-size:11.5px;font-style:italic}
/* the note itself, over the whole page, rendered by the studio's own page in
   a frame -- which is what makes "the same rules" true rather than claimed */
#ntback{position:fixed;inset:0;z-index:94;background:rgba(0,0,0,.45)}
#ntback[hidden]{display:none}
#ntbox{position:fixed;z-index:95;inset:4vh 4vw;display:flex;
  flex-direction:column;background:var(--card);border:1px solid var(--rule);
  border-radius:12px;box-shadow:0 12px 40px rgba(0,0,0,.4);overflow:hidden}
#ntbox[hidden]{display:none}
#ntbox .ahead{flex:0 0 auto;padding:10px 14px;border-bottom:1px solid var(--rule);
  display:flex;align-items:center;gap:8px;font-size:12px;color:var(--faint);
  letter-spacing:.06em;text-transform:uppercase}
#ntbox #nttitle{color:var(--accent);letter-spacing:0;text-transform:none;
  font-size:13.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#ntbox button{font:inherit;font-size:13px;padding:4px 10px;
  border:1px solid var(--rule);background:var(--bg);color:var(--ink);
  border-radius:6px;cursor:pointer;letter-spacing:0;text-transform:none}
#ntbox button:hover{border-color:var(--accent)}
#ntbox #ntedit{background:var(--accent);color:var(--accent-fg);border-color:var(--accent)}
#ntframe{flex:1 1 auto;width:100%;border:0;background:var(--bg)}
/* --- the divide sheet: the same sheet, one level up, so that the chunk it
   is about is still behind it and a cancel comes back to it.  Its own
   backdrop, and not the chunk sheet's: one shared backdrop meant a click on
   the dark meant "close the sheet underneath", which left this one standing
   over a page it had already renumbered */
#dvback{position:fixed;inset:0;z-index:90;background:rgba(0,0,0,.3)}
#dvback[hidden]{display:none}
#dvbox{position:fixed;z-index:91;top:50%;left:50%;
  transform:translate(-50%,-50%);width:min(760px,95vw);
  max-height:92vh;overflow-y:auto;-webkit-overflow-scrolling:touch;
  background:var(--card);border:1px solid var(--rule);border-radius:12px;
  box-shadow:0 12px 40px rgba(0,0,0,.35);padding:14px 18px 12px;
  font-size:13.5px;color:var(--ink);margin:0}
#dvbox[hidden]{display:none}
#dvbox input,#dvbox textarea{width:100%;font:inherit;font-size:13px;
  background:var(--bg);color:var(--ink);border:1px solid var(--rule);
  border-radius:6px;padding:5px 8px}
#dvbox textarea{resize:vertical;line-height:1.5}
#dvbox button{font:inherit;font-size:13px;padding:5px 10px;
  border:1px solid var(--rule);background:var(--bg);color:var(--ink);
  border-radius:6px;cursor:pointer}
#dvbox button:hover{border-color:var(--accent)}
#dvbox #dvdo{background:var(--accent);color:var(--accent-fg);border-color:var(--accent)}
#dvbox #dvdo:hover{filter:brightness(1.08)}
#dvbox #dvdo[disabled]{opacity:.45;cursor:default;filter:none}
/* the text with a place to cut between each pair of words.  It is the book's
   own script and direction, set large, because choosing the boundary is
   reading and not form-filling */
#dvwhere .dvtext{font-family:var(--tl-font,serif);font-size:21px;line-height:2.4;
  padding:8px 10px;border:1px solid var(--rule);border-radius:8px;
  background:var(--bg);margin:8px 0}
#dvwhere .dvcut{font-size:12px;line-height:1;padding:2px 5px;margin:0 2px;
  vertical-align:middle;color:var(--faint)}
#dvwhere .dvcut.on{background:var(--accent);border-color:var(--accent);
  color:var(--accent-fg)}
#dvpair{display:flex;gap:14px;flex-wrap:wrap;margin-top:4px}
#dvpair .dvcol{flex:1 1 300px;min-width:0;border:1px solid var(--rule);
  border-radius:8px;padding:8px 10px;background:var(--bg)}
#dvpair .dvcol > h4{margin:0 0 6px;font-size:11.5px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--faint);font-weight:600}
#dvpair .dvfa{font-family:var(--tl-font,serif);font-size:19px;line-height:1.9;
  padding:4px 0 8px;border-bottom:1px solid var(--rule);margin-bottom:8px;
  word-break:break-word}
#dvpair label{display:block;font-size:11px;color:var(--faint);margin:6px 0 2px}
#dvpair .dvwords{font-family:var(--tl-font,serif);font-size:15px}
#dvpair .dvvoc{font-family:ui-monospace,Menlo,monospace;font-size:12px;
  direction:ltr;text-align:left}
/* one chip per vocabulary entry, on the side it has been given.  Clicking the
   arrow sends it across and rewrites both boxes -- the boxes stay the truth,
   and typing in them wins */
#dvbox .dvchips{display:flex;flex-direction:column;gap:3px;margin:4px 0 2px}
#dvbox .dvchip{display:flex;gap:6px;align-items:flex-start;font-size:11.5px;
  color:var(--dim);line-height:1.45}
#dvbox .dvchip button{font-size:11px;padding:1px 6px;flex:0 0 auto}
#dvbox .dvchip .dvtxt{font-family:ui-monospace,Menlo,monospace;direction:ltr;
  text-align:left;word-break:break-word}
#dvnotes{margin-top:10px;color:var(--faint);font-size:11.5px;line-height:1.6}
#dvnotes p{margin:3px 0}
#dvnotes p::before{content:'\2022\00a0'}
#dvstat{font-size:12px;color:var(--dim);white-space:pre-wrap}
#dvstat.bad{color:var(--danger)}
#chdivrow .actl{display:flex;gap:8px;flex-wrap:wrap}
#chdivrow .anote{flex:1 1 100%}
#chins{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
#chins .dbtn{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;padding:3px 8px}
#chcol .dbtn span{font-size:10px;vertical-align:1px}
/* what the vocabulary line reads as, set exactly as the gloss and the cloud
   set it -- it is the same render_voc output, cloned out of the page.  The
   caption is not decoration: a bordered box above a textarea reads as a
   second box to type in unless something says it is a rendering. */
.chcap{color:var(--faint);font-size:11px;letter-spacing:.06em;
  text-transform:uppercase;margin-bottom:3px}
#chnow{font-size:var(--rd-gl,12.5px);color:var(--dim);line-height:1.5;
  padding:6px 9px;margin-bottom:8px;border:1px dashed var(--rule);border-radius:6px}
#chnow bdi.v{font-family:var(--tl-font,serif);
  font-size:calc(var(--rd-gl,12.5px) + 1px);font-style:normal}
#chnow i{color:var(--ink)}
#chnow .none{color:var(--faint);font-style:italic}
#chkanarow[hidden],#chtrrow[hidden],#chvocrow[hidden],
#chenrow[hidden],#chplain[hidden],#chwordsrow[hidden],#chfreerow[hidden]{display:none}
#chplain{color:var(--dim);font-size:12px;margin-bottom:8px}
/* A refusal is a sentence written to be read, and the fidelity one quotes the
   text either side of the character that broke it, on its own lines: keep the
   newlines rather than reflowing them into porridge, and set the whole answer
   in the monospace the rest of the toolbox gives a file name and a quoted
   character -- got: and want: are meant to be read one under the other. */
#chstat{font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace;
  font-size:12px;color:var(--accent);white-space:pre-wrap;
  overflow-x:auto;max-width:100%;line-height:1.55}
#chstat.bad{color:var(--danger)}
#chstat .fid{color:var(--dim)}
#chstat .warn{color:var(--warn)}
/* the build stamp says which reader this is; beside it, when an edit has just
   made the PDF older than the text, what to run to catch it up */
#pdfstale{font-size:11px;color:var(--danger);cursor:help}
#pdfstale[hidden]{display:none}

/* ---- the contents panel -------------------------------------------------
   A sheet hanging from the bottom of the header rather than a dropdown: 109
   entries want the whole height of the screen, and one layout that is full
   width on a phone and a 520px column on a desktop beats two. */
#tocwrap[hidden]{display:none}
/* the backdrop starts below the header on purpose: play, pause and the pass
   toggles stay live while you are looking for a paragraph */
#tocback{position:fixed;top:var(--headh, 92px);left:0;right:0;bottom:0;
  z-index:59;background:rgba(0,0,0,.28)}
#tocpanel{position:fixed;z-index:60;top:var(--headh, 92px);bottom:0;right:0;
  width:min(520px,100vw);display:flex;flex-direction:column;
  background:var(--card);border-left:1px solid var(--rule);
  border-top:1px solid var(--rule);box-shadow:0 8px 28px rgba(0,0,0,.22)}
.tocbar{display:flex;gap:6px;padding:8px;border-bottom:1px solid var(--rule)}
#tocq{flex:1;min-width:0;font:inherit;font-size:15px;padding:8px 10px;
  border:1px solid var(--rule);border-radius:6px;
  background:var(--bg);color:var(--ink)}
.tocbar button{font:inherit;font-size:15px;padding:6px 12px;cursor:pointer;
  border:1px solid var(--rule);border-radius:6px;
  background:var(--bg);color:var(--ink)}
/* momentum scrolling, and room at the foot for a phone's home indicator */
#toclist{flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch;padding-bottom:28px}
/* ---- the contents as a TREE ---------------------------------------------
   A chapter holds its sections and a section holds its paragraphs, and each
   can be folded away on its own: fold every chapter and the panel is a list
   of chapter names to walk; open one and its sections show; open a section
   and its paragraphs do.  NOTHING IS FOLDED TO BEGIN WITH, so the panel
   opens as the flat list it has always been, and a book with no sections is
   a chapter holding paragraphs directly -- one level, folding just the same. */
.tocgrp.closed > .tocbody,.tocsgrp.closed > .tocbody{display:none}
.tocfold{flex:0 0 auto;width:22px;height:22px;line-height:1;font:inherit;
  font-size:11px;cursor:pointer;color:var(--dim);background:var(--bg);
  border:1px solid var(--rule);border-radius:6px;padding:0;
  transition:transform .12s ease}
.tocfold:hover{color:var(--accent);border-color:var(--accent)}
.tocgrp.closed > .tocch > .tocfold,.tocsgrp.closed > .tocsec > .tocfold{
  transform:rotate(-90deg)}
.tocchl{flex:0 0 auto}
.tocchn{flex:1;min-width:0;color:var(--ink);font-size:13px;letter-spacing:0;
  text-transform:none;overflow-wrap:anywhere}
.tocsecn{flex:1;min-width:0;overflow-wrap:anywhere}
.tocedit{flex:0 0 auto;font:inherit;font-size:11px;padding:3px 7px;cursor:pointer;
  color:var(--dim);background:var(--bg);border:1px solid var(--rule);
  border-radius:6px}
.tocedit:hover{color:var(--accent);border-color:var(--accent)}
/* a section's own row, and its paragraphs stepped in under it so the depth
   is visible without a guide line */
.tocsec{position:sticky;top:31px;z-index:1;display:flex;align-items:center;
  gap:8px;background:var(--card);color:var(--ink);font-size:13px;
  padding:6px 12px 6px 22px;border-bottom:1px solid var(--rule)}
.tocsgrp > .tocbody > a.toce{padding-inline-start:30px}
#toclist .tocgrp[hidden],#toclist .tocsgrp[hidden]{display:none}
/* the second bar: fold everything, open everything, and the sections sheet */
.tocbar2{display:flex;gap:6px;align-items:center;padding:6px 8px;
  border-bottom:1px solid var(--rule)}
.tocbar2 .sp{flex:1}
.tocbar2 button{font:inherit;font-size:12px;padding:4px 10px;cursor:pointer;
  border:1px solid var(--rule);border-radius:6px;
  background:var(--bg);color:var(--ink)}
.tocbar2 button:hover{border-color:var(--accent);color:var(--accent)}
.tocch{position:sticky;top:0;z-index:2;background:var(--card);color:var(--dim);
  font-size:12px;letter-spacing:.05em;padding:7px 12px;
  display:flex;align-items:center;gap:8px;
  border-bottom:1px solid var(--rule)}
a.toce{display:flex;gap:10px;align-items:baseline;text-decoration:none;
  color:var(--ink);padding:10px 12px;border-bottom:1px solid var(--rule)}
a.toce:hover{background:var(--hl)}
a.toce:focus{background:var(--hl);outline:2px solid var(--accent);outline-offset:-2px}
a.toce .tocn{flex:0 0 auto;font-family:var(--tl-font,serif);font-size:14px;
  color:var(--accent)}
a.toce .toci{flex:1;font-family:var(--tl-font,serif);font-size:16px;line-height:1.8;
  text-align:start;overflow-wrap:anywhere}
#toclist a.toce[hidden],#toclist .tocch[hidden]{display:none}
#tocempty{padding:16px 12px;color:var(--dim);font-size:13px}

/* ---- the download sheet -------------------------------------------------
   The contents panel's layout, for the contents panel's reason: three
   sentences want the whole width of a phone and a column of a desktop, and
   one set of rules is both.  It hangs from the header, and its backdrop
   starts below the header too, so the narration goes on playing while
   somebody reads what the three shapes are.  Height is the content's, not
   the screen's: this is three choices and not a list of 109.
   Classes and not ids, like the Aa panel: the script builds this, and only
   for a book that has a narration to choose about. */
.dlwrap[hidden]{display:none}
.dlback{position:fixed;top:var(--headh, 92px);left:0;right:0;bottom:0;
  z-index:59;background:rgba(0,0,0,.28)}
.dlsheet{position:fixed;z-index:60;top:var(--headh, 92px);right:0;
  width:min(430px,100vw);max-height:calc(100vh - var(--headh, 92px));
  overflow-y:auto;-webkit-overflow-scrolling:touch;
  background:var(--card);border:1px solid var(--rule);border-right:none;
  box-shadow:0 8px 28px rgba(0,0,0,.22)}
/* the sheet takes the focus when it opens, so Escape reaches it and Tab
   starts at the first choice; the ring belongs on the choices, not here */
.dlsheet:focus{outline:none}
.dlhead{display:flex;align-items:center;gap:10px;color:var(--dim);
  font-size:12px;letter-spacing:.12em;text-transform:uppercase;
  padding:9px 14px;border-bottom:1px solid var(--rule)}
.dlhead .sp{flex:1}
.dlhead button{font:inherit;font-size:15px;line-height:1;padding:4px 9px;
  cursor:pointer;border:1px solid var(--rule);border-radius:6px;
  background:var(--bg);color:var(--ink)}
a.dlopt{display:block;text-decoration:none;color:var(--ink);
  padding:11px 14px;border-bottom:1px solid var(--rule)}
a.dlopt:last-child{border-bottom:none}
a.dlopt:hover{background:var(--hl)}
a.dlopt:focus{background:var(--hl);outline:2px solid var(--accent);outline-offset:-2px}
a.dlopt b{display:block;font-size:14px;font-weight:600;color:var(--accent)}
a.dlopt span{display:block;font-size:12.5px;line-height:1.55;color:var(--dim);
  margin-top:3px}
/* the one number a browser will not warn anybody about */
a.dlopt .dlsz{color:var(--ink);font-size:12px;margin-top:5px}
a.dlopt .dlsz:empty{display:none}
a.dlopt code{font-family:ui-monospace,Menlo,monospace;font-size:11.5px}
@media(max-width:560px){
  main{padding:12px 10px 60vh}
  .row{flex-direction:column;gap:2px}
  .row .fa{width:100%;flex:0 0 auto}
  .p1,.p3,.p5{font-size:calc(var(--rd-fa,20px) - 1px)}
  /* a full-width sheet, and targets big enough for a thumb */
  #tocpanel{left:0;border-left:none}
  a.toce{padding:12px 12px}
  .dlsheet{left:0;border-left:none}
  a.dlopt{padding:13px 12px}
  /* "transliteration" beside a box on a 390px screen leaves the box a
     thumbnail: the labels go above what they name */
  #chbox .arow,#fdbox .arow,#rgbox .arow{flex-direction:column;gap:2px;align-items:stretch}
  #chbox .alab,#fdbox .alab,#rgbox .alab{flex:0 0 auto;text-align:left;padding-top:0}
  #rgbox{padding:12px 12px 10px}
  /* 18px of side padding leaves a 390px screen very little to read a file
     name in, and the sticky foot needs room under it for a thumb */
  #narrbox{padding:12px 12px 0}
  #narrbox .nmain>.afoot{padding:10px 0 14px}
}
"""

JS = r"""
const A = document.getElementById('audio');
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const N = SUBS.length;
let cur = -1, loop = false, cont = true, stopAt = null, gap = 0, waiting = null;
/* STOP AT A CHANGE OF CHAPTER OR OF SECTION.  Off to begin with: the book
   plays straight through, as it always has, and the setting is what turns
   the stop on.  `atBound` is where playback was held -- the FIRST
   subparagraph of the new chapter or section -- so that pressing play goes on
   INTO it rather than replaying the one that had just finished. */
let stopBound = false, atBound = null;
const BOUNDAT = new Set(typeof BOUNDS === 'undefined' ? [] : BOUNDS);
/* Whether stepping from `a` to `b` crosses the opening of a chapter or of a
   section.  Every index between them is asked, not just b: the step may skip
   over an untimed or folded subparagraph, and a boundary inside what was
   skipped is still a boundary that was crossed. */
function crossesBound(a, b) {
  for (let k = Math.min(a, b) + 1; k <= Math.max(a, b); k++)
    if (BOUNDAT.has(k)) return true;
  return false;
}
/* Two of the things kept in localStorage belong to THIS book and not to
   the reader in general: where you are in it, and the timing edits not yet
   saved.  They were both stored under one name, so opening a second book
   restored the first one's place into it -- which is why a book with no
   narration could sit with a subparagraph highlighted that nobody had
   clicked.  The reader's address is what makes a book a book here, so it is
   what they are filed under; the preferences beside them (the gap, the
   rate, hover, the last deck, the pass toggles) are the reader's and stay
   as they were. */
const MINE = (k) => 'bk_' + k + ':' + location.pathname;

/* ---------- which recording a subparagraph is in -------------------------
   A book can be read a part at a time: several recordings, each covering a
   stretch of the text, each kept as its own file.  NARR is what the build
   found (id, src, and the labels it covers) and SUBS[i][3] is the id of the
   recording that subparagraph's times are seconds INTO.

   A BOOK WITH ONE RECORDING TAKES NONE OF THIS.  Its ids are "", ONEFILE is
   true, the element keeps the src the build baked into it, and every path
   below falls through to what it has always done.

   The swap itself is the delicate part: pointing the element at another file
   resets readyState to 0, so a seek made in the same breath is discarded and
   the file plays from 0:00 -- the very bug seekTo's park-and-retry exists
   against.  So the swap goes THROUGH that machinery rather than around it:
   point the element, and let seekTo park the seek until metadata arrives.  A
   file already loaded is never re-pointed, because doing that on every play
   would restart the element and throw the position away.                   */
const NARRBY = {};
for (const n of (typeof NARR === 'undefined' ? [] : NARR)) NARRBY[n.id] = n;
const NARRN = Object.keys(NARRBY).length;
const ONEFILE = NARRN < 2;
/* The recording a subparagraph belongs to, by the id its times were measured
   under -- and, failing that, by WHERE IT IS IN THE BOOK.  A book whose
   recordings are declared but not yet aligned has no ids on its
   subparagraphs at all (nothing has been timed, so nothing has been
   attributed), and it still knows which file covers which labels: that is
   the half-finished state this whole feature is for, and it has to play. */
/* WHERE IT IS is the stretch the build worked out for each recording, lo..hi
   in subparagraphs (texparse.region_bounds): exact, where comparing labels
   was not -- every chapter has a 1.1, and a recording of chapter 2 used to
   answer for chapter 1's.  It needs nothing on the page, so a subparagraph in
   a chapter not fetched yet is placed as surely as one on the screen. */
function narrFor(i) {
  const id = SUBS[i] && SUBS[i][3];
  if (id && NARRBY[id]) return NARRBY[id];
  if (NARRN === 1) return NARR[0];
  for (const n of NARR) {
    // a record with neither end named covers the whole book
    if (!n.from && !n.to) return n;
    if (n.lo != null && i >= n.lo && i <= n.hi) return n;
  }
  return null;
}
// narrSrc and NOT srcOf: this page already has a srcOf(n), the chunk's source
// row for the write sheet, declared further down.  Two function declarations
// of one name in one script are not two functions -- the later wins -- so the
// first spelling of this handed the <audio> element a chunk object, and the
// element dutifully asked the server for "[object Object]".
function narrSrc(i) {
  const n = narrFor(i);
  // a string and nothing else ever reaches A.src
  return n && typeof n.src === 'string' && n.src ? n.src : null;
}
// a subparagraph with a time nobody can play -- its recording is not on the
// shelf -- is walked past like an untimed one instead of playing the wrong file
function playable(i) { return ONEFILE || !!narrSrc(i); }

/* ---------- paragraphs folded away ---------------------------------------
   A run of consecutive paragraphs somebody has folded (reading.json, which
   travels with the book): the text is not shown, a bar stands in its place,
   and reading walks past it -- WITH OR WITHOUT AUDIO.  With a narration the
   playhead jumps from the subparagraph before the run to the first one
   after; with none, the arrows do the same, because walking the text is what
   they do in a book that has no recording.

   THE BUILD KNOWS NOTHING OF THIS.  It emits every paragraph as it always
   did, and hands the page two tables: PARAS (each paragraph's first and last
   subparagraph) and FOLDED (the runs).  Folding here rather than there keeps
   the note seams, the timing editor and applyTimings walking a book that is
   all present, and lets a chapter fetched later be folded by the same call. */
const PARAT = {};                       // paragraph key -> [first sub, last sub]
// ONE ENTRY PER PARAGRAPH, even where the build wrote several.  A paragraph
// continued in a second chapter file -- ch1.tex and ch1b.tex are both chapter
// 1 -- is emitted as one .para per piece, each carrying the same key, so the
// pieces are merged here into the whole stretch they cover.  Keeping only the
// last would hide the text of every piece and walk past just one of them.
for (const p of (typeof PARAS === 'undefined' ? [] : PARAS)) {
  const had = PARAT[p[0]];
  PARAT[p[0]] = had ? [Math.min(had[0], p[1]), Math.max(had[1], p[2])]
                    : [p[1], p[2]];
}
let folded = (typeof FOLDED === 'undefined' ? [] : FOLDED).map(r => r.slice());
const pKey = k => { const b = String(k).split(':'); return [+b[0] || 0, +b[1] || 0]; };
const pLE = (a, b) => (a[0] !== b[0] ? a[0] < b[0] : a[1] <= b[1]);
const pIn = (run, here) => pLE(pKey(run[0]), here) && pLE(here, pKey(run[1]));
function foldedRun(key) {
  const here = pKey(key);
  return folded.find(r => pIn(r, here)) || null;
}
function runParas(run) {
  return Object.keys(PARAT).filter(k => pIn(run, pKey(k)));
}
/* The runs as ranges of subparagraph numbers, which is what the walk asks --
   ONE RANGE PER PIECE, read from PARAS itself rather than collapsed to the
   run's min..max.  A paragraph in a .tex whose name carries no chapter number
   has no key at all: it cannot be named, so it cannot be folded, and the build
   gives it no PARAS entry.  Such a paragraph lying between two paragraphs of a
   run would fall inside min..max and the walk would step over it -- over text
   that is still on the page, since nothing hides it.  The same holds for a
   paragraph written in two pieces with another paragraph between them.  Taking
   the pieces as they are cannot include anything that is not in the run. */
let foldedSubs = [];
function foldRanges() {
  foldedSubs = [];
  for (const run of folded)
    for (const p of (typeof PARAS === 'undefined' ? [] : PARAS))
      if (pIn(run, pKey(p[0]))) foldedSubs.push([p[1], p[2]]);
}
foldRanges();
function inFolded(i) {
  return foldedSubs.some(([lo, hi]) => i >= lo && i <= hi);
}
/* SHOWING A RUN IS NOT UNFOLDING IT.  The bar shows the text while somebody
   looks and the book stays folded, and the bar is the only place that state
   lives.  It is a function of its own because the bar is no longer the only
   one who needs it: a folded paragraph is display:none and therefore has no
   box, so scrollIntoView on one scrolls nowhere -- every way of jumping to a
   paragraph (the contents, a #par- link, the place a reader left off) has to
   open its run first or the jump is a control that visibly does nothing. */
/* WHICH RUNS ARE BEING LOOKED AT.  Held here rather than on the bar, and
   remembered by a PARAGRAPH OF THE RUN rather than by the run's two ends.
   Both halves of that matter.  A run whose head is in a chapter not yet
   fetched has no bar at all to carry the state; and a run that a later fold
   MERGES into gets new ends, so an id made of them no longer matches -- which
   shut the text under a reader who had opened it and was reading.  A
   paragraph inside the run survives both, since a merge only ever makes a run
   bigger, never smaller. */
let openKeys = new Set();
function runIsOpen(run) {
  for (const k of openKeys) if (pIn(run, pKey(k))) return true;
  return false;
}
function openRun(run, on) {
  if (!run) return;
  if (on) openKeys.add(run[0]);
  else for (const k of [...openKeys]) if (pIn(run, pKey(k))) openKeys.delete(k);
  const id = run[0] + '|' + run[1];
  const bar = document.querySelector('.foldbar[data-run="' + id + '"]');
  if (bar) {
    bar.classList.toggle('open', on);
    // the bar's OWN button: the row of note marks under it is buttons too
    const b = bar.querySelector(':scope > button');
    if (b) b.textContent = on ? 'fold them away again' : (bar.dataset.said || '');
  }
  document.querySelectorAll('.para[data-p]').forEach(el => {
    const r = foldedRun(el.dataset.p);
    if (r && r[0] + '|' + r[1] === id) el.classList.toggle('opened', on);
  });
}
function reveal(el, block, behavior) {
  const p = el && el.closest ? el.closest('.para[data-p]') : null;
  if (p) openRun(foldedRun(p.dataset.p), true);
  if (el) el.scrollIntoView({block: block || 'start',
                             behavior: behavior || 'auto'});
}
function foldBar(run) {
  const n = runParas(run).length;
  const said = n + (n === 1 ? ' paragraph folded away' : ' paragraphs folded away');
  const bar = document.createElement('div');
  bar.className = 'foldbar';
  bar.dataset.run = run[0] + '|' + run[1];
  bar.dataset.said = said;
  const b = document.createElement('button');
  b.type = 'button';
  b.textContent = said;
  b.title = 'show them here — the book keeps them folded, and the narration '
          + 'goes on skipping them';
  b.onclick = () => openRun(run, !bar.classList.contains('open'));
  bar.appendChild(b);
  return bar;
}
/* ---------- the notes a fold would otherwise swallow ---------------------
   A note is drawn in the seam above a line, and a seam is drawn INSIDE the
   paragraph it belongs to, so a folded paragraph took its notes down with
   it: a run of twelve paragraphs could be hiding six notes and the page
   said nothing at all.  The bar says it now -- the marks of every note
   inside the run, under the button, the first three and then "+N more",
   which opens the rest where it stands.  The row goes when the run is
   opened (the sheet's `.foldbar.open .fnotes`), because every one of those
   notes is then standing in its own seam again, where it belongs.

   FOUND BY WALKING THE PAGE, not by comparing keys.  Each mark already
   carries the note it was made for; what this asks is which marks are
   inside the paragraphs this bar has hidden, so what the bar shows is
   exactly what was hidden -- including a note whose anchor points at a seam
   the reader has no paragraph for, which is nobody's and stays adrift at
   the end of the book as it always did.

   A FRESH BUTTON PER MARK, never the hidden one moved or cloned: the one in
   the seam has to stay where it is for the moment the run is opened, and a
   clone would arrive without its click, its preview card and its place in
   the queue of notes to fetch ahead.  */
const FOLD_MARKS = 3;
// A bar's row of marks, let go.  They are watched for the read-ahead like
// any other mark, and an observer still holding a button that has left the
// page holds the note behind it too.  Called wherever a bar or a row is
// thrown away -- here, and in applyFold.
function dropFoldNotes(bar) {
  const row = bar.querySelector('.fnotes');
  if (row && nearNote)
    row.querySelectorAll('.mark').forEach(b => nearNote.unobserve(b));
  return row;
}
function foldNoteRow(bar) {
  const had = dropFoldNotes(bar);
  if (had) had.remove();
  const id = bar.dataset.run;
  const hidden = [];
  document.querySelectorAll('.para.folded[data-p]').forEach(el => {
    const r = foldedRun(el.dataset.p);
    if (!r || r[0] + '|' + r[1] !== id) return;
    el.querySelectorAll('.gap .mark').forEach(b => {
      if (b.noteRecord) hidden.push(b.noteRecord);
    });
  });
  if (!hidden.length) return;
  const row = document.createElement('div');
  row.className = 'fnotes';
  const put = n => row.appendChild(noteButton(n, false));
  hidden.slice(0, FOLD_MARKS).forEach(put);
  if (hidden.length > FOLD_MARKS) {
    const more = document.createElement('button');
    more.type = 'button';
    more.className = 'fmore';
    const rest = hidden.length - FOLD_MARKS;
    more.textContent = '+' + rest + ' more';
    more.title = rest === 1 ? 'one more note inside these paragraphs'
                            : rest + ' more notes inside these paragraphs';
    // in place, and not into a sheet: the reader is looking at this bar
    more.onclick = e => {
      e.stopPropagation();
      more.remove();
      hidden.slice(FOLD_MARKS).forEach(put);
    };
    row.appendChild(more);
  }
  bar.appendChild(row);
}
// Every bar, every time -- after the marks are drawn and after the bars are.
// The whole document, never the scope applyFold was given: a run may begin
// in one chapter and end in another, and the chapter that arrives second
// fills a bar that is standing in the first.
function paintFoldNotes() {
  $$('.foldbar[data-run]').forEach(foldNoteRow);
}
/* ---------- the book as an outline, to pick a stretch of it from ----------
   Three sheets name a part of the book: what a recording covers, what is
   folded away, where a section opens.  Each used to do it with a list of
   every paragraph -- or every subparagraph -- of the book, twice over,
   labelled by number alone: hundreds of rows to scroll through in a
   textbook, and nothing to know a paragraph by.  This is the one control the
   three share instead: the book as it is built, chapters holding their
   sections holding their paragraphs (and, for a recording, their
   subparagraphs), each paragraph shown by its number AND its opening words,
   in the book's own script.  It is read off the contents tree the build
   wrote, and off SUBS for the subparagraphs, so it cannot disagree with the
   contents panel about what the book holds.

   A CLICK TAKES A WHOLE THING -- a chapter, a section, a paragraph -- because
   most of what anybody names is exactly one of those: a recording is of a
   chapter, what gets folded is a section, a section opens at a paragraph.
   Clicking what is already picked opens it, to go finer.  A SHIFT-CLICK
   STRETCHES the pick from the last thing clicked to this one, as every list
   on a desktop does; "stretch it to…" does the same for a finger, or for
   anybody who has never heard of shift-clicking: the next thing picked is
   where it ends.  What is picked is tinted, its two ends say so, and the
   line under the outline says it in words.  The keys are a tree's (the
   WAI-ARIA pattern): the arrows walk it and open and close, Enter or Space
   picks, with Shift they stretch; the box above finds a paragraph by its
   number or its words.

   `o`: depth ('para' | 'sub', what a pick is made of), point (one thing,
   not a stretch), whole (nothing picked means the whole book, and says so),
   can(row) (may it be picked), tags(row) -> [[text, class, title]],
   redirect(row) (the row a click on this one picks), onChange(pick),
   label, hint.  A pick is {lo, hi, row} in the units of `depth`: contents
   entries, in reading order, or SUBS indices.                              */
function olModel(depth) {
  const paras = [], chapters = [];
  const text = el => (el ? el.textContent.trim() : '');
  let subsOf = null;
  if (depth === 'sub') {
    subsOf = [];
    SUBS.forEach((s, i) => {
      if (s[4] == null || s[4] < 0) return;
      (subsOf[s[4]] = subsOf[s[4]] || []).push(i);
    });
  }
  const span = node => {
    const kids = node.kids.filter(x => x.lo != null);
    node.lo = kids.length ? Math.min(...kids.map(x => x.lo)) : null;
    node.hi = kids.length ? Math.max(...kids.map(x => x.hi)) : null;
  };
  const para = (a, up) => {
    const k = paras.length, href = a.getAttribute('href') || '';
    const p = {kind: 'p', k, up, pkey: a.dataset.p || '', ch: a.dataset.ch || '',
               no: href.slice(href.lastIndexOf('-') + 1),
               text: text(a.querySelector('.toci')), q: a.dataset.q || ''};
    if (depth === 'sub') {
      const got = (subsOf && subsOf[k]) || [];
      p.kids = got.map(i => ({kind: 's', i, lo: i, hi: i, up: p, ch: p.ch,
                              label: String(SUBS[i][5] || '')}));
      span(p);
    } else p.lo = p.hi = k;
    paras.push(p);
    return p;
  };
  for (const g of $$('#toclist .tocgrp')) {
    const c = {kind: 'ch', ch: g.dataset.ch || '', kids: [],
               name: text(g.querySelector(':scope > .tocch > .tocchn'))};
    const body = g.querySelector(':scope > .tocbody');
    for (const node of (body ? [...body.children] : [])) {
      if (node.matches('.tocsgrp')) {
        const s = {kind: 'sec', up: c, ch: c.ch, p: node.dataset.p || '', kids: [],
                   name: text(node.querySelector(':scope > .tocsec > .tocsecn'))};
        for (const a of node.querySelectorAll(':scope > .tocbody > a.toce'))
          s.kids.push(para(a, s));
        span(s);
        c.kids.push(s);
      } else if (node.matches('a.toce')) c.kids.push(para(node, c));
    }
    span(c);
    chapters.push(c);
  }
  return {depth, chapters, paras};
}
// every paragraph under a row, or the row itself
function olParas(row) {
  if (row.kind === 'p') return [row];
  if (row.kind === 's') return [row.up];
  return row.kids.flatMap(olParas);
}
// the rows from the chapter down to the leaf `i`, outermost first
function olChain(m, i) {
  const out = [];
  let rows = m.chapters;
  for (;;) {
    const r = rows.find(x => x.lo != null && x.lo <= i && i <= x.hi);
    if (!r) return out;
    out.push(r);
    if (!r.kids || !r.kids.length) return out;
    rows = r.kids;
  }
}
const olIso = s => '⁨' + s + '⁩';     // a name in the book's script, isolated
function olNamed(row) {
  if (row.kind === 'ch') return 'chapter ' + row.ch + (row.name ? ' · ' + olIso(row.name) : '');
  if (row.kind === 'sec') return 'the section ' + olIso(row.name) + ', in chapter ' + row.ch;
  if (row.kind === 'p') return 'chapter ' + row.ch + ', ¶ ' + row.no;
  return 'chapter ' + row.ch + ', ' + row.label;
}
/* A pick said in words: the one thing it is ("chapter 2 · Geppetto", "the
   section …"), whole chapters ("chapters 2–4"), or its two ends; and how
   much it is. */
function olDescribe(m, pick) {
  const a = olChain(m, pick.lo), b = olChain(m, pick.hi);
  if (!a.length || !b.length) return '';
  const unit = m.depth === 'sub' ? 'subparagraph' : 'paragraph';
  const n = pick.hi - pick.lo + 1;
  const much = n + ' ' + unit + (n === 1 ? '' : 's');
  const exact = a.find(x => x.lo === pick.lo && x.hi === pick.hi);
  if (exact) return olNamed(exact) + ' · ' + much;
  const at = chain => { const x = chain[chain.length - 1];
                        return x.kind === 's' ? x.label : '¶ ' + x.no; };
  if (a[0] !== b[0] && a[0].lo === pick.lo && b[0].hi === pick.hi)
    return 'chapters ' + a[0].ch + '–' + b[0].ch + ' · ' + much;
  if (a[0] === b[0])
    return 'chapter ' + a[0].ch + ', ' + at(a) + ' to ' + at(b) + ' · ' + much;
  return 'chapter ' + a[0].ch + ', ' + at(a) + ' → chapter ' + b[0].ch + ', ' + at(b) +
         ' · ' + much;
}
function outlinePicker(o) {
  const wrap = document.createElement('div');
  wrap.className = 'olwrap';
  wrap.innerHTML =
    '<div class="oltools">' +
      '<input type="search" class="olq" autocomplete="off" spellcheck="false" ' +
        'placeholder="find a paragraph by its number or its words" ' +
        'aria-label="find a paragraph by its number or its words">' +
      '<button type="button" class="olopen" title="open every chapter">open all</button>' +
      '<button type="button" class="olshut" title="close every chapter">close all</button>' +
    '</div>' +
    '<ul class="oltree" role="tree"></ul>' +
    '<div class="olnone" hidden>No paragraph has those words.</div>' +
    '<div class="olbar">' +
      '<span class="olsay" role="status" aria-live="polite"></span>' +
      (o.whole ? '<button type="button" class="olwhole" title="a recording of all ' +
                 'of it">the whole book</button>' : '') +
      (o.point ? '' : '<button type="button" class="olstretch" aria-pressed="false" ' +
                 'title="the next thing you pick is where it ends — Shift-click does ' +
                 'the same">stretch it to…</button>') +
    '</div>' +
    '<div class="olhint"></div>';
  const tree = wrap.querySelector('.oltree'), q = wrap.querySelector('.olq');
  tree.setAttribute('aria-label', o.label || 'the book');
  if (!o.point) tree.setAttribute('aria-multiselectable', 'true');
  let m = null, pick = null, anchor = null, stretching = false;
  let rowOf = new WeakMap(), liOf = new Map();
  const count = row => {
    if (row.kind === 's') return row.i != null && SUBS[row.i][0] != null ? fmt(SUBS[row.i][0]) : '';
    if (row.kind === 'p') return '';
    const n = olParas(row).length;
    return n + (n === 1 ? ' paragraph' : ' paragraphs');
  };
  const bookText = (span, s) => {
    span.lang = META.lang || '';
    span.dir = META.dir || 'auto';
    const b = document.createElement('bdi');
    b.textContent = s || '';
    span.appendChild(b);
  };
  function item(row, level) {
    const el = document.createElement('li');
    el.setAttribute('role', 'treeitem');
    el.setAttribute('aria-level', String(level));
    el.tabIndex = -1;
    el.className = 'oli ol-' + row.kind;
    if (row.kids && row.kids.length) el.setAttribute('aria-expanded', 'false');
    // dim only a row nothing can be picked by: a section in the sections
    // sheet picks the paragraph it opens at, so it is as live as that is
    const via = o.redirect ? (o.redirect(row) || row) : row;
    if (via.lo == null || (o.can && !o.can(via))) el.setAttribute('aria-disabled', 'true');
    const r = document.createElement('div');
    r.className = 'olr';
    r.style.setProperty('--lv', String(level));
    const tw = document.createElement('span');
    tw.className = 'oltw';
    tw.setAttribute('aria-hidden', 'true');
    if (row.kids && row.kids.length) tw.title = 'open or close';
    const k = document.createElement('span'), t = document.createElement('span');
    const c = document.createElement('span'), g = document.createElement('span');
    k.className = 'olk'; t.className = 'olt'; c.className = 'olc'; g.className = 'olg';
    k.textContent = row.kind === 'ch' ? 'chapter ' + row.ch : row.kind === 'sec' ? '§'
                  : row.kind === 'p' ? '¶ ' + row.no : row.label;
    if (row.kind === 'ch' || row.kind === 'sec') bookText(t, row.name);
    else if (row.kind === 'p') bookText(t, row.text);
    c.textContent = count(row);
    r.append(tw, k, t, c, g);
    el.appendChild(r);
    if (row.kids && row.kids.length) {
      const ul = document.createElement('ul');
      ul.setAttribute('role', 'group');
      el.appendChild(ul);
    }
    rowOf.set(el, row);
    liOf.set(row, el);
    return el;
  }
  // a group's rows are made the first time it opens: a textbook of a
  // thousand subparagraphs draws its chapters and nothing more to begin with
  function kidsOf(el) {
    const row = rowOf.get(el), ul = el.querySelector(':scope > ul');
    if (ul && !ul.childElementCount && row.kids)
      for (const x of row.kids) ul.appendChild(item(x, +el.getAttribute('aria-level') + 1));
    return ul;
  }
  const isOpen = el => el.getAttribute('aria-expanded') === 'true';
  function setOpen(el, on) {
    if (!el || !el.hasAttribute('aria-expanded')) return;
    if (on) kidsOf(el);
    el.setAttribute('aria-expanded', on ? 'true' : 'false');
    if (on) paint();
  }
  // the rows above `row` opened, so that it is drawn -> its element
  function reveal(row) {
    const up = [];
    for (let x = row.up; x; x = x.up) up.unshift(x);
    for (const x of up) setOpen(liOf.get(x), true);
    return liOf.get(row);
  }
  function focusRow(el, scroll) {
    if (!el) return;
    for (const x of tree.querySelectorAll('li[tabindex="0"]')) x.tabIndex = -1;
    el.tabIndex = 0;
    el.focus({preventScroll: true});
    if (scroll !== false) el.firstElementChild.scrollIntoView({block: 'nearest'});
  }
  function tagsOf(el, row, from, to) {
    const g = el.querySelector(':scope > .olr > .olg');
    const want = [];
    if (from) want.push(['from', 'olend', 'what is picked starts here']);
    if (to) want.push(['to', 'olend', 'what is picked ends here']);
    if (o.tags) want.push(...(o.tags(row) || []));
    const key = JSON.stringify(want);
    if (g.dataset.k === key) return;
    g.dataset.k = key;
    g.textContent = '';
    for (const [tx, cls, title] of want) {
      const s = document.createElement('span');
      s.className = 'oltag ' + (cls || '');
      s.textContent = tx;
      if (title) s.title = title;
      g.appendChild(s);
    }
  }
  function paint() {
    for (const [row, el] of liOf) {
      let inn = false, part = false, from = false, to = false;
      if (pick && row.lo != null) {
        if (o.point) {
          inn = pick.row === row;
          // the rows the pick is inside say so, so that a closed chapter or
          // section still shows where the pick is
          part = !inn && row.lo <= pick.lo && pick.hi <= row.hi;
        } else {
          inn = row.lo >= pick.lo && row.hi <= pick.hi;
          part = !inn && row.lo <= pick.hi && row.hi >= pick.lo;
          // an end is marked on the outermost row that makes it, and only on
          // a pick that is more than that one row
          const upIn = row.up && row.up.lo >= pick.lo && row.up.hi <= pick.hi;
          const one = row.lo === pick.lo && row.hi === pick.hi;
          from = inn && !upIn && !one && row.lo === pick.lo;
          to = inn && !upIn && !one && row.hi === pick.hi;
        }
      }
      el.classList.toggle('in', inn);
      el.classList.toggle('part', part);
      el.setAttribute('aria-selected', inn ? 'true' : 'false');
      tagsOf(el, row, from, to);
    }
  }
  function say() {
    wrap.querySelector('.olsay').textContent = pick
      ? (o.point ? olNamed(pick.row) : olDescribe(m, pick))
      : (o.whole ? 'the whole book' : (o.none || 'nothing picked yet'));
    const st = wrap.querySelector('.olstretch');
    if (st) {
      st.disabled = !pick;
      st.setAttribute('aria-pressed', stretching ? 'true' : 'false');
    }
    const wb = wrap.querySelector('.olwhole');
    if (wb) wb.disabled = !pick;
    tree.classList.toggle('stretching', stretching);
    wrap.querySelector('.olhint').textContent = stretching
      ? 'Now pick where it ends: everything from what you picked to there is taken.'
      : (o.hint || (o.point ? '' :
         'Click a chapter, a section or a paragraph to take all of it — click it again to ' +
         'go inside. Shift-click another, or “stretch it to…” and pick it, to take ' +
         'everything in between.'));
  }
  function changed() { if (o.onChange) o.onChange(api.get()); }
  function choose(el, extend) {
    let row = rowOf.get(el);
    if (!row) return;
    if (o.redirect) row = o.redirect(row) || row;
    if (row.lo == null || (o.can && !o.can(row))) return;
    const target = liOf.get(row) || reveal(row);
    // the pick clicked again, plainly: open it (or close it), to go finer
    if (!extend && !stretching && pick && pick.lo === row.lo && pick.hi === row.hi &&
        (!o.point || pick.row === row) && target.hasAttribute('aria-expanded')) {
      setOpen(target, !isOpen(target));
      focusRow(target);
      return;
    }
    if (o.point) pick = {lo: row.lo, hi: row.hi, row};
    else if ((extend || stretching) && anchor)
      pick = {lo: Math.min(anchor.lo, row.lo), hi: Math.max(anchor.hi, row.hi)};
    else { pick = {lo: row.lo, hi: row.hi}; anchor = row; }
    stretching = false;
    focusRow(target);
    paint(); say(); changed();
  }
  tree.addEventListener('click', e => {
    const el = e.target.closest('li[role="treeitem"]');
    if (!el || !tree.contains(el)) return;
    if (e.target.closest('.oltw') && el.hasAttribute('aria-expanded')) {
      setOpen(el, !isOpen(el));
      focusRow(el, false);
      return;
    }
    choose(el, e.shiftKey);
  });
  // a double click would select the words under it, which nobody asked for
  tree.addEventListener('mousedown', e => { if (e.detail > 1 || e.shiftKey) e.preventDefault(); });
  const visible = () => [...tree.querySelectorAll('li[role="treeitem"]')]
    .filter(el => el.offsetParent !== null);
  tree.addEventListener('keydown', e => {
    const el = document.activeElement && document.activeElement.closest &&
               document.activeElement.closest('li[role="treeitem"]');
    if (!el || !tree.contains(el)) return;
    const vis = visible(), k = vis.indexOf(el);
    const go = x => { e.preventDefault(); if (x) focusRow(x); };
    const up = () => { const p = el.parentElement.closest('li[role="treeitem"]');
                       return p && tree.contains(p) ? p : null; };
    switch (e.key) {
      case 'ArrowDown': go(vis[k + 1]); break;
      case 'ArrowUp': go(vis[k - 1]); break;
      case 'Home': go(vis[0]); break;
      case 'End': go(vis[vis.length - 1]); break;
      case 'ArrowRight':
        e.preventDefault();
        if (el.hasAttribute('aria-expanded') && !isOpen(el)) setOpen(el, true);
        else if (isOpen(el)) { const f = kidsOf(el).querySelector('li'); if (f) focusRow(f); }
        break;
      case 'ArrowLeft':
        e.preventDefault();
        if (isOpen(el)) setOpen(el, false); else { const p = up(); if (p) focusRow(p); }
        break;
      case 'Enter': case ' ':
        e.preventDefault();
        choose(el, e.shiftKey);
        break;
      case 'Escape':
        // a stretch half made is let go of first; the sheet closes after
        if (stretching) { e.preventDefault(); e.stopPropagation(); stretching = false; say(); }
        break;
    }
  });
  function filter() {
    const want = stripMarks(foldCase(q.value.trim()));
    tree.classList.toggle('filtering', !!want);
    for (const el of tree.querySelectorAll('.olhit, .olpath'))
      el.classList.remove('olhit', 'olpath');
    let any = !want;
    if (want)
      for (const p of m.paras) {
        if (p.q.indexOf(want) < 0) continue;
        any = true;
        const el = reveal(p);
        el.classList.add('olhit');
        for (let x = p.up; x; x = x.up) liOf.get(x).classList.add('olpath');
      }
    wrap.querySelector('.olnone').hidden = any;
    paint();
  }
  q.addEventListener('input', filter);
  q.addEventListener('keydown', e => {
    if (e.key === 'Escape' && q.value) { e.preventDefault(); e.stopPropagation(); q.value = ''; filter(); }
    else if (e.key === 'ArrowDown') {
      const f = visible()[0];
      if (f) { e.preventDefault(); focusRow(f); }
    }
  });
  wrap.querySelector('.olopen').onclick = () => {
    for (const c of m.chapters) setOpen(liOf.get(c), true);
    for (const c of m.chapters) for (const s of c.kids) if (s.kind === 'sec') setOpen(liOf.get(s), true);
  };
  wrap.querySelector('.olshut').onclick = () => {
    for (const el of tree.querySelectorAll('li[aria-expanded="true"]')) setOpen(el, false);
  };
  const st = wrap.querySelector('.olstretch');
  if (st) st.onclick = () => {
    if (!pick) return;
    stretching = !stretching;
    if (stretching && !anchor) anchor = {lo: pick.lo, hi: pick.hi};
    say();
    const f = tree.querySelector('li[tabindex="0"]');
    if (stretching && f) f.focus({preventScroll: true});
  };
  const wb = wrap.querySelector('.olwhole');
  if (wb) wb.onclick = () => { api.set(null); changed(); };
  const api = {
    el: wrap,
    get model() { return m; },
    // (re)read the book from the contents tree: on first use, and whenever
    // what the book holds may have changed under the sheet
    load() {
      m = olModel(o.depth || 'para');
      tree.textContent = '';
      rowOf = new WeakMap(); liOf = new Map();
      for (const c of m.chapters) tree.appendChild(item(c, 1));
      // a book of one chapter has nothing to choose at that level
      if (m.chapters.length === 1) setOpen(liOf.get(m.chapters[0]), true);
      const first = tree.querySelector('li');
      if (first) first.tabIndex = 0;
      // a pick of one row names a row of the outline just thrown away
      if (o.point) { pick = null; anchor = null; }
      if (pick && (pick.hi >= (m.depth === 'sub' ? SUBS.length : m.paras.length))) pick = null;
      q.value = '';
      filter();
      say();
      return api;
    },
    get() { return pick ? {lo: pick.lo, hi: pick.hi, row: pick.row || null} : null; },
    // pick lo..hi (a row, in point mode), open what shows it, and bring it
    // into view -- null picks nothing, which for a recording is the whole book
    set(lo, hi, row) {
      stretching = false;
      if (lo == null) { pick = null; anchor = null; paint(); say(); return api; }
      if (o.point && row) { pick = {lo: row.lo, hi: row.hi, row}; anchor = row; }
      else {
        hi = hi == null ? lo : hi;
        pick = {lo: Math.min(lo, hi), hi: Math.max(lo, hi)};
        const chain = olChain(m, pick.lo);
        anchor = chain.find(x => x.lo === pick.lo && x.hi === pick.hi) || chain[chain.length - 1] || null;
      }
      const show = o.point ? pick.row : (anchor && anchor.lo === pick.lo && anchor.hi === pick.hi
                                        ? anchor : olChain(m, pick.lo).slice(-1)[0]);
      const el = show ? reveal(show) : null;
      if (!o.point && !(anchor && anchor.lo === pick.lo && anchor.hi === pick.hi)) {
        const end = olChain(m, pick.hi).slice(-1)[0];
        if (end) reveal(end);
      }
      if (el) focusRow(el, true);
      paint(); say();
      return api;
    },
    // what the pick is called in words, or '' with nothing picked
    said() { return pick ? (o.point ? olNamed(pick.row) : olDescribe(m, pick)) : ''; },
    paint() { paint(); return api; },
    focus() { const f = tree.querySelector('li[tabindex="0"]') || tree.querySelector('li');
              if (f) f.focus({preventScroll: true}); },
  };
  return api;
}

/* The sheet that folds and unfolds: the book as an outline to pick a run of
   paragraphs from (outlinePicker), and every run already folded, said in
   words, with a button to open it again.  The decision is the book's, so each
   press goes to the server, which writes reading.json and rebuilds the
   reader; the page then folds what it has without a reload, so the answer is
   immediate and the next open agrees. */
function fdLabel(k) {
  const b = String(k).split(':');
  return 'chapter ' + (b[0] || '?') + ', paragraph ' + (b[1] || '?');
}
let fdPicker = null;
function fdPick() {
  if (fdPicker) return fdPicker;
  fdPicker = outlinePicker({
    depth: 'para', label: 'the paragraphs of the book',
    // a paragraph in a .tex whose name carries no chapter number has no key:
    // it cannot be named, so it cannot be folded
    can: row => olParas(row).some(p => p.pkey),
    // what is folded already, said on the row: a run folded again is merged
    // with it, so this is information, not a refusal
    tags: row => {
      const ps = olParas(row).filter(p => p.pkey);
      const n = ps.filter(p => foldedRun(p.pkey)).length;
      if (!n) return [];
      return [[row.kind === 'p' || n === ps.length ? 'folded' : n + ' folded', 'olfold',
               'folded away in the book']];
    },
    onChange: fdState,
  });
  $('#fdpick').appendChild(fdPicker.el);
  return fdPicker;
}
// the first and the last paragraph of a pick that have a name, as the door
// wants them -- or null, with nothing that can be folded in it
function fdKeys(p) {
  if (!p || !fdPicker) return null;
  const ps = fdPicker.model.paras.slice(p.lo, p.hi + 1).filter(x => x.pkey);
  return ps.length ? {from: ps[0].pkey, to: ps[ps.length - 1].pkey} : null;
}
function fdState() {
  $('#fddo').disabled = !fdKeys(fdPicker && fdPicker.get());
}
// a folded run, as the stretch of the outline it is (null when its ends
// name paragraphs the book no longer has)
function fdSpan(run) {
  const ps = fdPick().model.paras;
  const a = ps.findIndex(p => p.pkey === run[0]);
  let b = -1;
  for (let k = ps.length - 1; k >= 0; k--) if (ps[k].pkey === run[1]) { b = k; break; }
  return a >= 0 && b >= a ? {lo: a, hi: b} : null;
}
function fdFill() {
  const pk = fdPick();
  const box = $('#fdlist');
  box.innerHTML = '';
  if (!folded.length) {
    const s = document.createElement('span');
    s.className = 'nstate';
    s.textContent = 'nothing is folded away in this book';
    box.appendChild(s);
  }
  folded.forEach(run => {
    const row = document.createElement('div');
    row.className = 'fdrun nstate';
    const sp = fdSpan(run), n = runParas(run).length;
    // THE RUN IN WORDS, and a way to see it: it is picked in the outline, its
    // chapter opened, so what "chapter 2, ¶ 3 to ¶ 7" is can be looked at
    const see = document.createElement('button');
    see.type = 'button';
    see.className = 'fdsee';
    see.textContent = sp ? olDescribe(pk.model, sp)
      : fdLabel(run[0]) + ' → ' + fdLabel(run[1]) + ' · ' + n +
        (n === 1 ? ' paragraph' : ' paragraphs');
    see.title = 'show it in the outline';
    see.onclick = () => { if (sp) { pk.set(sp.lo, sp.hi); fdState(); } };
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = 'unfold';
    b.title = 'show this run in the book again';
    b.onclick = () => fdSend({from: run[0], to: run[1], on: false});
    row.append(see, b);
    box.appendChild(row);
  });
  pk.paint();                      // the "folded" marks follow what is folded
  const total = folded.reduce((k, r) => k + runParas(r).length, 0);
  $('#fdsum').textContent = total
    ? total + (total === 1 ? ' paragraph is' : ' paragraphs are')
      + ' folded away in ' + folded.length + (folded.length === 1 ? ' run' : ' runs')
    : 'Fold a run of paragraphs away when you do not want to read or hear it.';
}
async function fdSend(body) {
  $('#fdstat').textContent = 'saving…';
  $('#fdstat').classList.remove('bad');   // each answer colours itself, once
  try {
    const r = await fetch('__reading/fold', {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    const j = await r.json();
    if (!j.ok) { $('#fdstat').textContent = j.error || 'refused';
                 $('#fdstat').classList.add('bad'); return; }
    folded = (j.reading && j.reading.collapsed ? j.reading.collapsed : []).map(x => x.slice());
    foldRanges();
    applyFold();
    fdFill();
    // FOLDED is baked into reader/index.html, so what the page has just done
    // only survives a reload if the server's rebuild succeeded.  Every other
    // writing door in this page says so when it did not, and so does this one:
    // an older edition is exactly where a rebuild is most likely to fail.
    const badBuild = !!(j.reader && !j.reader.ok);
    $('#fdstat').textContent = (body.on === false ? 'unfolded' : 'folded away')
      + (badBuild ? ' — but the reader would not rebuild: '
                    + (j.reader.error || 'no reason given') : '');
    $('#fdstat').classList.toggle('bad', badBuild);
  } catch (e) {
    $('#fdstat').textContent = 'the server did not answer (' + (e.message || e) + ')';
    $('#fdstat').classList.add('bad');
  }
}
/* Open the way every other sheet opens: a flag the player's keydown listener
   and the contents' own read, so space does not play and C does not pull the
   contents over it while it is up; Escape closes it, which its × already
   promises in a tooltip; and the form never submits, which would reload the
   reader and lose the reading place. */
let fdShown = false, fdWasPlaying = false, fdWasWaiting = false;
function fdOpen(on) {
  fdShown = !!on;
  $('#fdback').hidden = !on;
  $('#fdbox').hidden = !on;
  if (on) {
    // The sheet stands back from the book the way every other one does: the
    // gloss cloud goes, the recording stops, the armed continuation is
    // disarmed.  Folding is a decision made ABOUT what you are hearing, so
    // this is the ordinary case, and without it the book reads on and scrolls
    // under the open sheet.  BOTH halves of "playing" are remembered: between
    // repeats in loop mode and between subparagraphs in continuous mode the
    // audio is ALREADY paused and playback lives entirely in `waiting`, so
    // asking the element alone would record false, and clearing the timer
    // would then leave nothing to put back.
    closeCloud();
    fdWasPlaying = !A.paused;
    fdWasWaiting = waiting != null;
    if (!A.paused) A.pause();
    clearTimeout(waiting); waiting = null;
    $('#fdstat').textContent = '';
    $('#fdstat').classList.remove('bad');
    // read the book afresh, and start on the paragraph being read: folding
    // is most often decided about what is on the screen
    const pk = fdPick().load();
    const at = cur >= 0 && SUBS[cur] ? SUBS[cur][4] : -1;
    if (at != null && at >= 0 && at < pk.model.paras.length) pk.set(at, at);
    fdFill();
    fdState();
    pk.focus();
  } else {
    const wasPlaying = fdWasPlaying, wasWaiting = fdWasWaiting;
    fdWasPlaying = fdWasWaiting = false;
    // LISTENING RATHER THAN READING: there is no reading place to walk, and
    // moving one would drag the text about, which is the one thing listening
    // promises not to do.  What must still happen is the playhead leaving a
    // run just folded -- it is parked inside it -- and the next gate being
    // worked out again, since the runs have changed under it.
    if (listening) {
      const here = A.currentTime || 0;
      const shut = foldWindows().find(([a, b]) => here >= a - 0.05 && here < b);
      if (shut) seekTo(shut[1], () => { if (wasPlaying) A.play().catch(() => {}); });
      else if (wasPlaying) A.play().catch(() => {});
      armListen();
      setPlayBtn();
      return;
    }
    // What was being read may now be inside a run folded while the sheet was
    // up.  Walk the place out -- forwards, and then backwards, because the
    // run may reach the end of the book and a forward-only walk would leave
    // the mark inside it, to be saved there and read back on the next open --
    // AND MOVE THE PLAYHEAD WITH IT.  The element is still parked where it
    // was paused, which is inside that run: leaving it there means the next
    // press of play reads aloud the very text that has just been folded away.
    let n = cur;
    if (inFolded(n)) {
      n = nextStop(cur + 1, 1);
      if (n < 0) n = nextStop(cur - 1, -1);
    }
    if (n !== cur) {
      if (n < 0) { cur = -1; save(); setPlayBtn(); return; }
      if (wasPlaying || wasWaiting) { playSub(n, true); return; }
      // the place moves without the recording starting: playSub plays from
      // seekTo's callback, so the seek is made here rather than through it
      cur = n; hl(n, true); save();
      previewing = false; stopAt = null;
      if (SUBS[n][0] != null && playable(n)) {
        useFile(n); seekTo(SUBS[n][0]);
      }
      setPlayBtn();
      return;
    }
    if (wasPlaying) A.play().catch(() => {});
    else if (wasWaiting) playSub(cur, false);   // the timer was holding it
  }
}
$('#fold').onclick = () => fdOpen($('#fdbox').hidden);
$('#fdcancel').onclick = () => fdOpen(false);
$('#fdclose').onclick = () => fdOpen(false);
$('#fdback').onclick = () => fdOpen(false);
$('#fddo').onclick = () => {
  const k = fdKeys(fdPicker && fdPicker.get());
  if (k) fdSend({from: k.from, to: k.to, on: true});
};
$('#fdbox').addEventListener('submit', e => e.preventDefault());
addEventListener('keydown', e => {
  if (fdShown && e.key === 'Escape') { e.preventDefault(); fdOpen(false); } });

function applyFold(scope) {
  const root = scope || document;
  // A run somebody has unfolded leaves its paragraph in openKeys, and that
  // paragraph would open the run again if it were ever folded a second time.
  // Dropped here, where the runs have just changed, and nowhere else.
  for (const k of [...openKeys]) if (!foldedRun(k)) openKeys.delete(k);
  // rebuilt from nothing each time: a chapter that has just arrived, or a run
  // that has just changed, must not leave yesterday's bar behind
  root.querySelectorAll('.foldbar').forEach(b => { dropFoldNotes(b); b.remove(); });
  const drawn = new Set();
  root.querySelectorAll('.para[data-p]').forEach(el => {
    const run = foldedRun(el.dataset.p);
    el.classList.toggle('folded', !!run);
    if (!run) { el.classList.remove('opened'); return; }
    const id = run[0] + '|' + run[1];
    const open = runIsOpen(run);
    el.classList.toggle('opened', open);
    // ONE BAR FOR THE RUN, at its head.  A run may span a chapter boundary,
    // and the later chapter arrives on its own (fillChapter calls this with
    // that section as the scope): the bar already standing for this run is
    // then outside the scope, so it was not removed above and must not be
    // drawn again -- which is why the question is asked of the document.
    if (drawn.has(id)
        || document.querySelector('.foldbar[data-run="' + id + '"]')) return;
    drawn.add(id);
    const bar = foldBar(run);
    if (open) {
      bar.classList.add('open');
      const b = bar.querySelector(':scope > button');
      if (b) b.textContent = 'fold them away again';
    }
    el.parentNode.insertBefore(bar, el);
  });
  // the bars have just been rebuilt, so what each of them is hiding has to
  // be said again on it
  paintFoldNotes();
}
let loadedSrc = A.getAttribute('src') || '';
function useFile(i) {
  const want = narrSrc(i);
  if (typeof want !== 'string' || !want || want === loadedSrc) return false;
  loadedSrc = want;
  A.src = want;
  A.load();                 // readyState 0: seekTo will hold the seek for it
  return true;
}

/* ---------- seeking, done defensively -----------------------------------
   Setting currentTime while readyState < 1 is silently DISCARDED and the
   audio then plays from 0:00 -- which is exactly the "starts at zero" bug.
   So: hold the request until metadata arrives, then verify it landed and
   retry, and if the file is genuinely unseekable say so instead of playing
   the wrong thing.                                                        */
let pending = null, tries = 0;

function seekable() {
  try {
    if (!A.seekable.length) return false;
    const end = A.seekable.end(A.seekable.length - 1);
    // A part of a narration may be a minute long, and the test used to be
    // "more than a minute can be reached", which called such a file broken
    // and put the red warning over a perfectly good one.  What matters is
    // that the WHOLE of it can be reached; the old threshold stays for a
    // file whose duration the browser has not worked out yet.
    return end > 60 || (A.duration > 0 && end >= A.duration - 1);
  } catch (_) { return false; }
}
function diagnose() {
  if (A.readyState >= 1 && !seekable()) {
    $('#warn').style.display = 'inline';
    $('#warn').innerHTML = 'audio cannot be seeked — serve it with ' +
      '<code>python3 serve.py</code> (python -m http.server has no Range support), ' +
      'or <label style="text-decoration:underline;cursor:pointer">pick the file' +
      '<input id="pick" type="file" accept="audio/*" hidden></label>';
    bindPick();
    return false;
  }
  return true;
}
function seekTo(t, done) {
  if (A.readyState < 1) { pending = {t, done}; return; }
  if (!diagnose()) return;
  tries = 0;
  const target = Math.max(0, Math.min(t, (A.duration || 1e9) - 0.05));
  const verify = () => {
    if (Math.abs(A.currentTime - target) > 1.0 && tries < 4) {
      tries++; A.currentTime = target; setTimeout(verify, 220); return;
    }
    if (done) done();
  };
  A.currentTime = target;
  setTimeout(verify, 220);
}
A.addEventListener('loadedmetadata', () => {
  diagnose();
  if (pending) { const p = pending; pending = null; seekTo(p.t, p.done); }
});

/* ---------- chapters that arrive when they are asked for ------------------
   The build leaves every chapter after the first in a file of its own beside
   the reader (tex2html.one_chapter_at_a_time), and the page fetches one when
   it is wanted: the contents jumped into it, the reading place is in it, the
   narration played into it, or it simply came near the window.  A book of
   one chapter has no fragments and none of this ever runs.

   NOTHING IS RENUMBERED.  A fragment is the very markup the build emitted,
   cut where the chapters already were, so data-c and data-s stay the
   book-wide counters SUBS, SRC and TIMES are indexed by.  What a chapter
   needs on arrival is only what the page did to the whole book on load: the
   readings split, the times from timings.json, the seams' note buttons.

   The one thing lost is the browser's own find-in-page, which cannot see a
   chapter that has not arrived; the contents search is built from the
   incipits and travels with the page, so that still finds every paragraph. */
const chapFetches = new Map();            // file -> the fetch in flight
const chapOfSub = i => (SUBS[i] && SUBS[i][2]) || 0;
const chapOfChunk = n => (TIMES[n] && TIMES[n][3]) || 0;
const lazyChapters = () => !!$('section.chapter[data-part]');
async function fillChapter(sec) {
  const part = sec && sec.dataset.part;
  if (!part) return false;
  if (!chapFetches.has(part))
    chapFetches.set(part, (async () => {
      const r = await fetch(part, {cache: 'no-store'});
      if (!r.ok) throw new Error(part);
      return r.text();
    })());
  let html;
  try { html = await chapFetches.get(part); }
  catch (_) { chapFetches.delete(part); return false; }
  if (!sec.dataset.part) return true;          // another caller got there first
  const got = new DOMParser().parseFromString(html, 'text/html')
                             .querySelector('section.chapter');
  if (!got) return false;
  sec.innerHTML = got.innerHTML;
  // which file this section's markup came from, still known after it has
  // arrived: repainting an edited chunk re-reads exactly that file
  // (repaintChunks) -- asked of the section, not of the chapter's number,
  // which two sections share when a chapter runs across two .tex files
  sec.dataset.from = part;
  delete sec.dataset.part;
  if (READINGS) { splitReadings(sec.querySelectorAll('.p1 ruby')); READINGS.apply(); }
  applyTimings(sec);
  paintNotes();                 // the seams of this chapter can hold notes now
  applyFold(sec);               // and its folded runs are folded here too
  return true;
}
// A chapter LABEL may cover more than one section (a chapter written across
// two .tex files), so this fetches every section that wears the index.
async function needChapters(ci) {
  const secs = $$('section.chapter[data-part][data-ch="' + ci + '"]');
  let any = false;
  for (const s of secs) any = (await fillChapter(s)) || any;
  return any;
}
// and reading straight on: a chapter coming within a screen or two of the
// window is fetched before it is reached, so the text does not stop
if (window.IntersectionObserver && lazyChapters()) {
  const near = new IntersectionObserver(es => es.forEach(e => {
    if (!e.isIntersecting) return;
    near.unobserve(e.target);
    fillChapter(e.target);
  }), {rootMargin: '1200px 0px'});
  $$('section.chapter[data-part]').forEach(s => near.observe(s));
}

/* ---------- highlight ----------------------------------------------------
   The mark on a subparagraph is WHERE YOU ARE.  With a narration playing that
   is also what is being spoken, which is what it was named after; with no
   narration -- a book nobody has recorded, and every book on its first day --
   it is the reading place and nothing else, and it moves because somebody
   clicked.  Nothing about selecting a subparagraph asks whether it has a
   time: only playing one does. */
function clearHL() { $$('.on-air').forEach(e => e.classList.remove('on-air')); }
function hl(i, mayScroll) {
  clearHL();
  const el = document.querySelector('.sub[data-s="' + i + '"]');
  if (!el) {
    // the chapter it is in has not been fetched yet: bring it and mark it
    // then.  needChapters answers false once there is nothing left to fetch,
    // which is what stops this going round again.
    needChapters(chapOfSub(i)).then(got => { if (got) hl(i, mayScroll); });
    return;
  }
  el.classList.add('on-air');
  if (earLive) earPaint();
  // Only ever scroll when the reader did NOT put it there itself.  Scrolling
  // under a finger that has just pressed a button moves the next button out
  // from under it, which is what made editing unusable.
  if (!mayScroll || !autoscroll) return;
  const r = el.getBoundingClientRect();
  if (r.bottom < 60 || r.top > innerHeight - 60)
    el.scrollIntoView({block: 'center', behavior: 'smooth'});
}
let autoscroll = true;

/* ---------- playback, by SUBPARAGRAPH ------------------------------------ */
// from/to play a window inside the subparagraph instead of the whole of it:
// when you are nudging an edge by 0.1 s, replaying fifteen seconds to hear
// where it truncates is the wrong tool.  A preview never loops and never runs
// on into the next subparagraph.
const PREVIEW = 1.5;
let previewing = false;
function playSub(i, mayScroll, from, to) {
  if (i < 0 || i >= N) return;
  const t = SUBS[i];
  clearTimeout(waiting); waiting = null;
  // whatever was being waited for at a boundary, this is where the reading
  // place is going now -- a click or an arrow elsewhere ends that wait
  atBound = null;
  cur = i;
  hl(i, mayScroll);
  save();
  // Nothing recorded here: the reading place has moved and that is the whole
  // of it.  A book with no narration at all is every subparagraph in this
  // case, and used to be one where the mark could not be moved by any means.
  if (t[0] == null) { previewing = false; stopAt = null; setPlayBtn(); return; }
  previewing = from != null;
  stopAt = to != null ? to : t[1];
  // the recording this subparagraph is in, if it is not the one loaded: the
  // seek below is then held until the new file's metadata arrives
  useFile(i);
  seekTo(from != null ? from : t[0], () => { A.play().catch(() => {}); });
  setPlayBtn();
}
function playTail(i) {          // the last PREVIEW seconds, to hear the cut
  const t = SUBS[i];
  playSub(i, false, Math.max(t[0], t[1] - PREVIEW), t[1]);
}
function playHead(i) {          // the first PREVIEW seconds, to hear the entry
  const t = SUBS[i];
  playSub(i, false, t[0], Math.min(t[1], t[0] + PREVIEW));
}
function nextWithAudio(from, dir) {
  let n = from;
  while (n >= 0 && n < N) {
    if (SUBS[n][0] != null && playable(n) && !inFolded(n)) return n;
    n += dir;
  }
  return -1;
}
// The next place to stand.  With a narration that is the next subparagraph
// that has a time, because the arrows are how you walk the recording; where
// nothing ahead has one -- an untimed tail, or a book with no narration at
// all -- it is simply the next subparagraph, because the arrows are then how
// you walk the text.
function nextStop(from, dir) {
  const n = nextWithAudio(from, dir);
  if (n >= 0) return n;
  // A BOOK WITH NO NARRATION, or an untimed tail: the arrows walk the text,
  // and they have to walk past what is folded just the same -- the fold is
  // about the text, and only half of it would be honoured otherwise.
  let k = from;
  while (k >= 0 && k < N) {
    if (!inFolded(k)) return k;
    k += dir;
  }
  return -1;
}
/* ---------- listening, without following the text ------------------------
   Everything above plays a SUBPARAGRAPH: the playhead is the reading place,
   it stops at that subparagraph's end, and "keep going" steps it on to the
   next one -- walking the text, which is what a reading edition is for.
   Sometimes the recording is what is wanted and the text is not: put it on
   and listen, from wherever in the file you like.

   BUT A FOLD IS STILL A FOLD.  A run somebody folded away is text they have
   said they do not want; played straight through it would be read out all the
   same.  So listening holds at the first folded stretch ahead of it, and
   leaves the playhead at the END of that stretch -- ready to go on after it
   at the next press, which is what somebody who folded it meant, while the
   seek bar is right there for somebody who meant otherwise.

   The gate is worked out in the CURRENT recording's clock.  A book read from
   several files has one loaded at a time, and a stretch recorded in another
   file is no part of this one's timeline; it is gated when that file is the
   one playing. */
let listening = false, afterFold = null, seeking = false;
function foldWindows() {
  // [start, end] of each folded run that is timed AND in the file now loaded,
  // in that file's own clock
  const out = [];
  for (const [lo, hi] of foldedSubs) {
    let a = null, b = null;
    for (let i = lo; i <= hi && i < N; i++) {
      if (i < 0 || !SUBS[i] || SUBS[i][0] == null) continue;
      if (!ONEFILE && narrSrc(i) !== loadedSrc) continue;
      const s0 = SUBS[i][0], e0 = SUBS[i][1];
      if (a === null || s0 < a) a = s0;
      if (b === null || e0 > b) b = e0;
    }
    if (a !== null && b !== null && b > a) out.push([a, b]);
  }
  return out.sort((x, y) => x[0] - y[0]);
}
function foldGate(from) {
  // the next folded stretch to hold at, or null: one that STARTS after where
  // we are (a hair's grace, so the stretch just left does not hold us again)
  for (const [a, b] of foldWindows()) if (a > from + 0.05) return [a, b];
  return null;
}
function armListen() {
  const gate = foldGate(A.currentTime || 0);
  stopAt = gate ? gate[0] : null;
  afterFold = gate ? gate[1] : null;
}
function listenPlay() {
  clearTimeout(waiting); waiting = null;
  atBound = null; previewing = false;
  if (!A.paused) { A.pause(); stopAt = null; setPlayBtn(); return; }
  // nothing loaded yet: the recording the book starts in, at its beginning
  if (!ONEFILE && !loadedSrc) {
    const n = nextWithAudio(0, 1);
    if (n >= 0) useFile(n);
  }
  armListen();
  A.play().catch(() => {});
  setPlayBtn();
}
function showSeek() {
  const d = A.duration || 0;
  $('#seekwrap').style.display = listening ? 'inline' : 'none';
  if (!listening || seeking) return;
  $('#seek').value = String(d > 0 ? Math.round((A.currentTime / d) * 1000) : 0);
}

/* ---------- listening, with the mark let back in -------------------------
   Listening on its own never touches the mark (hl/clearHL): that is the
   whole of what it promises above, and most of the time it is enough --
   "not necessary, everything works without it".  "highlight" is the one door
   back in, for whoever wants to see where the recording has got to without
   giving up the hands-free play: it puts the mark on the subparagraph the
   PLAYHEAD is in, the way a video's captions follow the video (tick() /
   findSeg() in youtube/lib/player.js, read the same way here) -- not the
   way a book's own \stopAt does, which pauses at the end of one.  Following
   never sets stopAt and never touches `cur`: the reading place you left off
   at is exactly where it was, and turning "highlight" off, or listening off,
   puts the mark back on it (restoreHL).

   "keep in view" is the second, and only ever means anything together with
   the first: on its own, with nothing being followed, there is nothing to
   scroll to.  Off, the mark still moves under "highlight" -- the page does
   not, and the reader follows it by hand.  Both are grey until listening is
   on, and both start unpressed every time listening is turned on, the same
   "a habit of the moment" listening itself is. */
let listenFollow = false, listenScroll = false, listenAt = -1;
function restoreHL() { if (cur >= 0) hl(cur, false); else clearHL(); }
// the last subparagraph (in the file now loaded) whose start the playhead
// has reached, a hair early so the mark is there before the words are --
// held through a gap between two, as a video's caption is.  Never a folded
// one: the playhead pauses right at a fold's own start, which is also that
// first folded subparagraph's start, and the mark has to stay on the last
// thing actually on the page rather than land on text nobody can see.
function subAtTime(t) {
  let found = -1;
  for (let i = 0; i < N; i++) {
    if (SUBS[i][0] == null || inFolded(i)) continue;
    if (!ONEFILE && narrSrc(i) !== loadedSrc) continue;
    if (SUBS[i][0] <= t + 0.15) found = i;
  }
  return found;
}
function followTick() {
  const at = subAtTime(A.currentTime);
  if (at === listenAt) return;
  listenAt = at;
  if (at >= 0) hl(at, listenScroll); else clearHL();
}

A.addEventListener('timeupdate', () => {
  // with several recordings the clock is the CURRENT one's, so it says which
  // -- the same numbers without that would quietly mean something else
  const inn = (ONEFILE || cur < 0 || !SUBS[cur] || !SUBS[cur][3])
    ? '' : ' · ' + SUBS[cur][3];
  $('#pos').textContent = fmt(A.currentTime) + ' / ' + fmt(A.duration || 0) + inn;
  showSeek();
  if (listening && listenFollow) followTick();
  if (stopAt == null || A.currentTime < stopAt) return;
  A.pause(); stopAt = null; setPlayBtn();
  // held at a folded run: the playhead goes to the end of it, so the next
  // press goes on after the text that was folded away
  if (listening) {
    if (afterFold != null) { seekTo(afterFold, () => {}); afterFold = null; }
    return;
  }
  if (previewing) { previewing = false; return; }
  if (loop) {
    waiting = setTimeout(() => { if (!ankiOpen && !chOpen && !fdShown && !rgShown) playSub(cur, false); }, gap * 1000);
  } else if (cont) {
    const n = nextWithAudio(cur + 1, 1);
    // A CHANGE OF CHAPTER OR OF SECTION, where that has been asked for.  The
    // subparagraph just played is finished either way; what is held back is
    // the step INTO the next one.  BOUNDS is where each begins, counted at
    // build time -- a chapter still in its own file has no elements to look
    // at, which is why PARAS is baked in beside it for the very same reason.
    if (n >= 0 && stopBound && crossesBound(cur, n)) {
      atBound = n;
      hl(n, true);            // the new place is shown, so the wait is visible
      return;
    }
    if (n >= 0) waiting = setTimeout(() => { if (!ankiOpen && !chOpen && !fdShown && !rgShown) playSub(n, true); }, 120);
  }
});
function fmt(s) { s = Math.max(0, s | 0);
  const h = (s / 3600) | 0, m = ((s % 3600) / 60) | 0, x = s % 60;
  return (h ? h + ':' : '') + String(m).padStart(h ? 2 : 1, '0') + ':' + String(x).padStart(2, '0'); }

function togglePlay() {
  if (listening) { listenPlay(); return; }
  clearTimeout(waiting); waiting = null;
  if (!A.paused) { A.pause(); stopAt = null; setPlayBtn(); return; }
  // Held at a change of chapter or of section: play goes ON into it, which is
  // the whole of what the setting promises.  Resuming `cur` here would play
  // again the subparagraph that had just finished.
  if (atBound != null) { const n = atBound; atBound = null; playSub(n, true); return; }
  if (cur < 0) { playSub(nextWithAudio(0, 1), true); return; }
  // resuming where the loaded file is not the one this subparagraph is in:
  // start it again in its own recording rather than playing whatever is here
  if (useFile(cur)) { playSub(cur, false); return; }
  stopAt = SUBS[cur][1];
  A.play().catch(() => {}); setPlayBtn();
}
function setPlayBtn() { $('#play').textContent = A.paused ? '▶' : '‖'; }
/* However the playing started -- this page's button, the space bar, the
   element's own controls in edit times -- listening gates it.  Arming here
   as well as in listenPlay is what makes that true of every door. */
A.addEventListener('play', () => { if (listening && stopAt == null) armListen(); });
A.addEventListener('play', setPlayBtn);
A.addEventListener('pause', setPlayBtn);

/* ---------- clicks: anywhere in a subparagraph plays that subparagraph --- */
document.addEventListener('click', e => {
  if (e.altKey || e.ctrlKey || e.metaKey) return;   // that's a card gesture
  if (e.shiftKey) return;                           // that's a copy
  const sub = e.target.closest('.sub');
  if (!sub) return;                      // an untimed one selects, and stops
  playSub(+sub.dataset.s, false);        // there: playSub knows the difference
});

function save() { localStorage.setItem(MINE('pos'), JSON.stringify({i: cur})); }
addEventListener('beforeunload', save);

/* ---------- controls ----------------------------------------------------- */
$('#play').onclick = togglePlay;
$('#loop').onclick = e => { loop = !loop; e.target.classList.toggle('on', loop);
  $('#gapwrap').style.display = loop ? 'inline' : 'none'; };
/* KEEP GOING.  A reading habit and the person's, like the speed: remembered
   under bk_cont ("1" or "0"; absent means on, which is how every book has always
   played) and followed from one device to another (lib/prefs.js KEYS). */
cont = localStorage.getItem('bk_cont') !== '0';
$('#cont').onclick = e => { cont = !cont; e.target.classList.toggle('on', cont);
  localStorage.setItem('bk_cont', cont ? '1' : '0'); };
$('#cont').classList.toggle('on', cont);
/* Stop at a change of chapter or of section.  A reading habit rather than a
   fact about one book, so it is kept under a plain key beside the gap and the
   rate rather than under MINE(); absent means off, which is how every book
   has always played. */
stopBound = localStorage.getItem('bk_stopbnd') === '1';
$('#stopbnd').classList.toggle('on', stopBound);
$('#stopbnd').onclick = e => {
  stopBound = !stopBound;
  e.target.classList.toggle('on', stopBound);
  localStorage.setItem('bk_stopbnd', stopBound ? '1' : '0');
  if (!stopBound) atBound = null;      // nothing is being waited for any more
};
/* Listening rather than reading: a habit of the moment and not a fact about
   the book, so it is not remembered -- a reader who opens the book again is
   reading it.  Turned on while a subparagraph is playing, the playing goes
   ON: what stops is the stopping at that subparagraph's end. */
$('#listen').onclick = e => {
  listening = !listening;
  e.target.classList.toggle('on', listening);
  clearTimeout(waiting); waiting = null;
  atBound = null; previewing = false;
  if (listening) {
    if (!A.paused) armListen(); else { stopAt = null; afterFold = null; }
  } else {
    // back to reading: the subparagraph under the playhead is where the
    // reading place is, and it stops at its end as it always did
    afterFold = null;
    stopAt = (!A.paused && cur >= 0 && SUBS[cur] && SUBS[cur][1] != null)
      ? SUBS[cur][1] : null;
  }
  // "highlight" and "keep in view" mean nothing outside listening: grey, and
  // started fresh, every time listening is what has just changed
  listenFollow = false; listenScroll = false; listenAt = -1;
  $('#listenfollow').disabled = $('#listenscroll').disabled = !listening;
  $('#listenfollow').classList.remove('on'); $('#listenscroll').classList.remove('on');
  restoreHL();
  showSeek();
};
$('#listenfollow').onclick = e => {
  listenFollow = !listenFollow;
  e.target.classList.toggle('on', listenFollow);
  listenAt = -1;
  if (listenFollow) followTick(); else restoreHL();
};
$('#listenscroll').onclick = e => {
  listenScroll = !listenScroll;
  e.target.classList.toggle('on', listenScroll);
  // pressed while already following: jump to it at once, rather than
  // waiting on whatever moves the playhead next
  if (listenScroll && listening && listenFollow && listenAt >= 0) hl(listenAt, true);
};
$('#seek').oninput = () => {
  seeking = true;
  const d = A.duration || 0;
  if (d > 0) $('#pos').textContent = fmt((+$('#seek').value / 1000) * d) + ' / ' + fmt(d);
};
$('#seek').onchange = () => {
  const d = A.duration || 0;
  seeking = false;
  if (!(d > 0)) return;
  // WHEREVER THEY LIKE, folded or not: the seek bar is the way to start from
  // any moment of the recording, and what it is dragged onto is honoured --
  // the gate ahead is worked out again from there.
  seekTo((+$('#seek').value / 1000) * d, () => {});
  if (listening && !A.paused) armListen();
};
A.addEventListener('loadedmetadata', showSeek);
A.addEventListener('seeked', () => { if (listening) showSeek(); });
$('#gap').onchange = e => { gap = +e.target.value; localStorage.setItem('bk_gap', e.target.value); };
const g0 = localStorage.getItem('bk_gap');
if (g0 !== null) { $('#gap').value = g0; gap = +g0; }
/* THE SPEED, WHICH MUST NOT CHANGE BY ITSELF.  Loading a recording -- which
   this reader does whenever the narration moves into a part kept in another
   file -- runs the media load algorithm, and that puts playbackRate back to
   defaultPlaybackRate.  Left at 1, the sound went back to 1× while this
   menu still said 1.5× (the owner's report, 2026-09-22).  So the chosen rate
   is set on BOTH, and put back after every load.  lib/narrctl.js does the
   same from outside, for every reader built before today, and draws the
   chip that stands in for this menu. */
function setRate(v) {
  A.playbackRate = v;
  A.defaultPlaybackRate = v;
}
$('#speed').onchange = e => { setRate(+e.target.value);
  localStorage.setItem('bk_rate', e.target.value); };
const r0 = localStorage.getItem('bk_rate');
if (r0) { $('#speed').value = r0; setRate(+r0); }
else setRate(+$('#speed').value || 1);
['loadedmetadata', 'canplay', 'play'].forEach(n => A.addEventListener(n, () => {
  const want = +$('#speed').value || 1;
  if (Math.abs(A.playbackRate - want) > 0.001) setRate(want);
}));

function toggle(btn, cls) { document.body.classList.toggle(cls);
  btn.classList.toggle('on', !document.body.classList.contains(cls));
  localStorage.setItem('bk_' + cls, document.body.classList.contains(cls) ? '1' : '0'); }
$$('[data-toggle]').forEach(b => { const cls = b.dataset.toggle;
  if (localStorage.getItem('bk_' + cls) === '1') document.body.classList.add(cls);
  b.classList.toggle('on', !document.body.classList.contains(cls));
  b.onclick = () => toggle(b, cls); });

// the theme (light / dark / sepia) is the toolbox's own, one preference for
// every page: lib/parseh.js keeps it and wires the ◐ button

/* ---------- text size and margins ------------------------------------------
   Parseh.typo: four sliders that set the --rd-* tokens the stylesheet is
   written against.  Remembered per browser under bk_typo.  The Aa button
   opens the GEAR at its Text group (lib/gear-reader.js), which draws these
   very sliders from the fields given here and writes through the same
   typo(); the panel Parseh.typo draws itself is the page's own fallback,
   for a reader that has no gear (opened off the disk).                      */
// the first slider is the text itself, named after its language; a vertical
// language gets one more, the column height of its tategaki pass (em)
const TYPO_FIELDS = [
  {name: 'fa',    label: LANG.name, min: 7,    max: 43,   step: 0.5,  unit: 'px', def: 20,   prop: '--rd-fa'},
  {name: 'gl',    label: 'glosses', min: 7,    max: 23,   step: 0.5,  unit: 'px', def: 12.5, prop: '--rd-gl'},
  {name: 'width', label: 'width',   min: 200,  max: 1680, step: 10,   unit: 'px', def: 760,  prop: '--rd-width'},
  {name: 'lead',  label: 'leading', min: 0.5,  max: 1.9,  step: 0.05, unit: '×',  def: 1,    prop: '--rd-lead'}
];
if (LANG.vertical)
  TYPO_FIELDS.push({name: 'vh', label: 'columns height', min: 6, max: 54, step: 1, unit: 'em', def: 22, prop: '--rd-vh'});
Parseh.CharacterDecomposition.mount({lang: LANG.code, toolbar: $('#typo').parentNode,
  scope: 'main .p1,main .p3,main .p4,main .row .fa', observe: document.querySelector('main'),
  onModeChange: on => { if (on) closeCloud(); }, onOpen: () => A.pause()
});
Parseh.typo({key: 'bk_typo', button: $('#typo'), fields: TYPO_FIELDS.concat(Parseh.readingFields(LANG.code))});
/* The readings over the text.  A chunk without words wears its kana as one
   ruby over the whole of it, split here over its kanji as far as the kana
   allows; a chunk its word line draws (.wd[data-w]) came from the build a
   word at a time, each word under its own reading, and is left as it is.
   Then what is known is hidden -- in pass 1, and in the chunk column, where
   a worded chunk's words wear their readings too. */
const READINGS = (LANG.reading || LANG.words) ? Parseh.readings({
  scope: 'book:' + LANG.code + ':' + META.book, kind: 'book',
  selector: 'main :is(.p1,.row .fa)'
}) : null;
function splitReadings(rubies) {
  rubies.forEach(r => {
    if (r.closest('.wd[data-w]')) return;
    const kana = r.querySelector('rt').textContent, text = textOf(r);
    const holder = document.createElement('span'); holder.className = 'wd';
    READINGS.render(holder, text, kana); r.replaceWith(holder);
  });
}
if (READINGS) { splitReadings(document.querySelectorAll('.p1 ruby')); READINGS.apply(); }

addEventListener('keydown', e => {
  // the anki dashboard has textareas; a space in one must not toggle play
  if (ankiOpen || narrOpen || chOpen || fdShown || secShown || rgShown ||
      /^(SELECT|INPUT|TEXTAREA)$/.test(e.target.tagName)) return;
  if (e.key === ' ') { e.preventDefault(); togglePlay(); }
  else if (e.key === 'ArrowRight') { e.preventDefault();
    const n = nextStop(cur + 1, 1); if (n >= 0) playSub(n, true); }
  else if (e.key === 'ArrowLeft') { e.preventDefault();
    const n = nextStop(cur - 1, -1); if (n >= 0) playSub(n, true); }
  else if (e.key === 'r' || e.key === 'R') { loop = !loop;
    $('#loop').classList.toggle('on', loop);
    $('#gapwrap').style.display = loop ? 'inline' : 'none'; }
  else if (e.key === 'g' || e.key === 'G') { toggle($('[data-toggle=nogloss]'), 'nogloss'); }
  else if (e.key === 'h' || e.key === 'H') {
    setHover(!document.body.classList.contains('hovermode')); }
  // E writes the chunk the cloud or the pencil is on
  else if (e.key === 'e' || e.key === 'E') {
    const from = cloudC >= 0 ? cloudFor : penFor;
    const n = cloudC >= 0 ? cloudC : (penFor ? +penFor.dataset.c : -1);
    if (n >= 0) { e.preventDefault(); penOff(); openChunk(n, from); } }
});

function bindPick() { const el = $('#pick'); if (!el) return;
  el.onchange = ev => { const f = ev.target.files[0];
    // The hand-picked file stands in for whatever is loaded now.  The
    // sentinel is not any recording's src, so moving into another one
    // re-points the element instead of leaving every region playing this.
    if (f) { A.src = URL.createObjectURL(f); loadedSrc = '#picked';
             A.load(); $('#warn').style.display = 'none'; } }; }
bindPick();
A.addEventListener('error', () => { $('#warn').style.display = 'inline'; });

/* ---------- editing the timings, in place -------------------------------- */
const edits = {};
const STEP = {'s-1': -1, 's-5': -0.5, 's-': -0.1, 's+': 0.1, 's+5': 0.5, 's+1': 1,
              'e-1': -1, 'e-5': -0.5, 'e-': -0.1, 'e+': 0.1, 'e+5': 0.5, 'e+1': 1};
function subEl(i) { return document.querySelector('.sub[data-s="' + i + '"]'); }
function paint(i) {
  const el = subEl(i); if (!el) return;
  const t = SUBS[i];
  el.querySelector('.e0').value = t[0] == null ? '' : t[0].toFixed(2);
  el.querySelector('.e1').value = t[1] == null ? '' : t[1].toFixed(2);
  el.querySelector('.dur').textContent = t[0] == null ? '' : (t[1] - t[0]).toFixed(2) + 's';
  el.classList.toggle('dirty', !!edits[el.dataset.key]);
}
// Setting an end moves the NEXT subparagraph's start to meet it, so the
// narration has no gap.  They stay two separate records, so either can be
// pulled apart again afterwards.
function setTimes(i, t0, t1, quiet, chain, preview) {
  const el = subEl(i); if (!el) return;
  if (!(t1 > t0)) return;
  if (!el.dataset.orig) el.dataset.orig = JSON.stringify([SUBS[i][0], SUBS[i][1]]);
  SUBS[i][0] = +t0.toFixed(2); SUBS[i][1] = +t1.toFixed(2);
  edits[el.dataset.key] = {t0: SUBS[i][0], t1: SUBS[i][1]};
  localStorage.setItem(MINE('edits'), JSON.stringify(edits));
  paint(i);
  // ...and never across a seam between two recordings: the next
  // subparagraph's start is a time in ANOTHER file, and meeting this end
  // would put a number from one clock into the other
  if (chain && i + 1 < N && SUBS[i + 1][0] != null && SUBS[i + 1][2] === SUBS[i][2]
      && SUBS[i + 1][3] === SUBS[i][3]) {
    const nx = subEl(i + 1);
    if (nx && SUBS[i + 1][1] > SUBS[i][1]) {
      if (!nx.dataset.orig)
        nx.dataset.orig = JSON.stringify([SUBS[i + 1][0], SUBS[i + 1][1]]);
      SUBS[i + 1][0] = SUBS[i][1];
      edits[nx.dataset.key] = {t0: SUBS[i + 1][0], t1: SUBS[i + 1][1]};
      paint(i + 1);
    }
  }
  localStorage.setItem(MINE('edits'), JSON.stringify(edits));
  showEditCount();
  if (quiet) return;
  if (preview === 'tail') playTail(i);
  else if (preview === 'head') playHead(i);
  else playSub(i, false);
}
function showEditCount() {
  const n = Object.keys(edits).length;
  $('#savetimes').style.display = n ? 'inline' : 'none';
  $('#droptimes').style.display = n ? 'inline' : 'none';
  $('#savetimes').textContent = 'save times (' + n + ')';
}
function revert(el) {
  const i = +el.dataset.s;
  if (el.dataset.orig) {
    const o = JSON.parse(el.dataset.orig);
    SUBS[i][0] = o[0]; SUBS[i][1] = o[1];
    delete el.dataset.orig;
  }
  delete edits[el.dataset.key];
  paint(i);
}
document.addEventListener('click', e => {
  const b = e.target.closest('.edit button'); if (!b) return;
  e.stopPropagation();
  const el = b.closest('.sub'), i = +el.dataset.s, t = SUBS[i], act = b.dataset.e;
  if (act === 'p') { playSub(i, false); return; }
  // one dispatch off the STEP table, so every step size is wired by
  // construction -- the coarse buttons were previously drawn but dead
  if (STEP[act] !== undefined) {
    if (act[0] === 's') setTimes(i, t[0] + STEP[act], t[1], false, false, 'head');
    else setTimes(i, t[0], t[1] + STEP[act], false, true, 'tail');
  }
  else if (act === 'sh' || act === 'eh') {
    // THE PLAYHEAD IS A TIME IN THE FILE THAT IS LOADED.  Stamping it onto a
    // subparagraph belonging to another recording would write a number in
    // the wrong clock, and nothing afterwards could tell.
    if (!ONEFILE && narrSrc(i) && narrSrc(i) !== loadedSrc) {
      $('#editmsg').textContent =
        'that subparagraph is in another recording — play it first';
      return;
    }
    if (act === 'sh') { setTimes(i, A.currentTime, t[1], true); playHead(i); }
    else { setTimes(i, t[0], A.currentTime, true, true); playTail(i); }
  }
  else if (act === 'rv') {
    revert(el);
    localStorage.setItem(MINE('edits'), JSON.stringify(edits));
    showEditCount();
  }
}, true);
document.addEventListener('change', e => {
  const inp = e.target.closest('.edit input'); if (!inp) return;
  const el = inp.closest('.sub'), i = +el.dataset.s;
  const wasEnd = inp.classList.contains('e1');
  setTimes(i, +el.querySelector('.e0').value, +el.querySelector('.e1').value,
           false, wasEnd, wasEnd ? 'tail' : 'head');
});
$('#editmode').onclick = e => {
  document.body.classList.toggle('editing');
  const on = document.body.classList.contains('editing');
  e.target.classList.toggle('on', on);
  if (on) $$('.sub').forEach(el => paint(+el.dataset.s));
  showScrub();
};
try { Object.assign(edits, JSON.parse(localStorage.getItem(MINE('edits')) || '{}'));
  if (Object.keys(edits).length) {
    $$('.sub').forEach(el => { const e2 = edits[el.dataset.key];
      if (e2) { const i = +el.dataset.s;
        el.dataset.orig = JSON.stringify([SUBS[i][0], SUBS[i][1]]);
        SUBS[i][0] = e2.t0; SUBS[i][1] = e2.t1; } });
    showEditCount();
  } } catch (_) {}

$('#savetimes').onclick = async () => {
  $('#editmsg').textContent = 'saving…';
  try {
    // Relative, not '/__save/...': the reader is served from
  // /books/<slug>/reader/, so a relative URL tells the server which
  // book the edit belongs to.  An absolute one used to land at the
  // repo root, where there is no timings.json to merge into.
  const r = await fetch('__save/subtimes.json',
      {method: 'POST', headers: {'Content-Type': 'application/json'},
       body: JSON.stringify(edits)});
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || 'server error');
    $('#editmsg').textContent = 'saved ' + j.applied + ' to timings.json and the .tex';
    for (const k in edits) delete edits[k];
    localStorage.removeItem(MINE('edits'));
    $$('.sub').forEach(el => { delete el.dataset.orig; el.classList.remove('dirty'); });
    showEditCount();
  } catch (err) {
    // A fetch that rejects outright says only "NetworkError", which names
    // neither the cause nor the file.  The server answers every POST now,
    // even a failing one, so reaching this branch means nothing answered at
    // all -- almost always a serve.py still running the code it was started
    // with.  Say so, rather than leave the reader guessing.
    const dead = (err instanceof TypeError) || /NetworkError|Failed to fetch|Load failed/i.test(err.message || '');
    $('#editmsg').textContent = 'could not save (' + err.message + ')' +
      (dead ? ' — the server did not answer; restart python3 serve.py and reload this page' : '') +
      ' — edits are kept in this browser';
  }
};

$('#droptimes').onclick = e => {
  const b = e.target, n = Object.keys(edits).length;
  if (b.dataset.armed !== '1') {
    b.dataset.armed = '1'; b.textContent = 'discard ' + n + '?'; b.classList.add('on');
    setTimeout(() => { if (b.dataset.armed === '1') {
      b.dataset.armed = ''; b.textContent = 'discard edits'; b.classList.remove('on'); } }, 4000);
    return;
  }
  $$('.sub').forEach(el => { if (edits[el.dataset.key]) revert(el); });
  localStorage.removeItem(MINE('edits'));
  b.dataset.armed = ''; b.textContent = 'discard edits'; b.classList.remove('on');
  showEditCount();
  $('#editmsg').textContent = 'discarded ' + n + ' unsaved edit' + (n === 1 ? '' : 's');
};

// what timings.json said, kept: a chapter fetched later is stamped with the
// times belonging to ITS subparagraphs, exactly as the first one was on load
let TIMINGS = null;
function applyTimings(scope) {
  if (!TIMINGS) return 0;
  let n = 0;
  (scope || document).querySelectorAll('.sub').forEach(el => {
    const rec = TIMINGS[el.dataset.key];
    if (!rec) return;
    if (edits[el.dataset.key]) return;   // an unsaved local edit wins
    const i = +el.dataset.s;
    if (Math.abs(SUBS[i][0] - rec.t0) > 0.005 || Math.abs(SUBS[i][1] - rec.t1) > 0.005) {
      SUBS[i][0] = rec.t0; SUBS[i][1] = rec.t1; n++;
    }
  });
  return n;
}
(async () => {
  try {
    const r = await fetch('../timings.json', {cache: 'no-store'});
    if (!r.ok) return;
    const doc = await r.json();
    TIMINGS = doc.subs || {};
    const n = applyTimings(null);
    if (n) $('#editmsg').textContent = n + ' timing' + (n === 1 ? '' : 's') +
      ' loaded from timings.json';
  } catch (_) {}
})();

/* ---------- stop the server from here ------------------------------------ */
$('#stopsrv').onclick = e => {
  const b = e.target;
  if (b.dataset.armed !== '1') {
    b.dataset.armed = '1'; b.textContent = 'really stop?'; b.classList.add('on');
    setTimeout(() => { if (b.dataset.armed === '1') {
      b.dataset.armed = ''; b.textContent = 'stop server'; b.classList.remove('on'); } }, 4000);
    return;
  }
  // the place and the speed are already saved; say so and stop
  Parseh.stopServer({silent: true, before: () => { A.pause(); save(); }});
};

// A contents entry is a real link, so the address bar can carry #par-2-6 —
// someone reading on the phone sends themselves a paragraph.  Keep the saved
// place (it is where playback resumes) but let the link win the scroll.
const deepLink = /^#par-\d+-\d+$/.test(location.hash);
try { const p = JSON.parse(localStorage.getItem(MINE('pos')) || 'null');
  if (p && p.i >= 0 && p.i < N) { cur = p.i; autoscroll = false; hl(p.i);
    setTimeout(async () => {
      // the place may be in a chapter that has not been fetched: it is what
      // the reader came back for, so it is fetched before anything else
      await needChapters(chapOfSub(p.i));
      const el = document.querySelector('.sub[data-s="' + p.i + '"]');
      // A PLACE INSIDE A RUN FOLDED SINCE IT WAS SAVED is not a reason to
      // unfold it: the fold is the reader's own decision and coming back is
      // not an instruction to undo it.  So this one jump does not reveal --
      // it goes to the bar standing where the place is, which is where the
      // reader left off as the book now reads.
      if (el && !deepLink) {
        const run = inFolded(p.i) ? foldedRun((el.closest('.para[data-p]')
                                               || {dataset: {}}).dataset.p) : null;
        const bar = run && document.querySelector(
          '.foldbar[data-run="' + run[0] + '|' + run[1] + '"]');
        if (bar) bar.scrollIntoView({block: 'center'});
        else if (!run) reveal(el, 'center');
      }
      autoscroll = true; }, 120); } } catch (_) {}
// ...and a #par-2-6 sent to somebody: the browser cannot jump to a paragraph
// whose chapter is still a file, so its chapter is fetched and the jump made
// here.  The contents knows which chapter every paragraph belongs to.
if (deepLink) setTimeout(async () => {
  const a = $('#toclist a.toce[href="' + location.hash + '"]');
  if (!a) return;
  // A PARAGRAPH ALREADY IN THE PAGE still has to be revealed, which is why
  // this no longer returns on finding it: it may be folded away, and a folded
  // paragraph is display:none, so the browser's own jump to it lands nowhere
  // at all.  Returning here was right while every jump was only a scroll.
  let el = document.getElementById(location.hash.slice(1));
  if (el) { reveal(el, 'start'); return; }
  // BY INDEX, not by the printed chapter number: the sections carry the index
  // and the entry carries both, and the two are different numbers (a chapter
  // written across two files is two sections under one index).  Asking by the
  // label fetched somebody else's chapter and left this paragraph unfetched.
  if (await needChapters(+a.dataset.ci || 0)) {
    el = document.getElementById(location.hash.slice(1));
    if (el) reveal(el, 'start');
  }
}, 0);
setPlayBtn();
$('#build').textContent = META.build + ' \u00b7 ' + META.built;

/* ---------- contents: jump to a paragraph --------------------------------
   Nothing here touches SUBS, the player or the timings: farsi-shakar-ast has
   no narration at all and its contents has to work exactly the same.  The
   entries are ordinary links written at build time, so tabbing and Enter come
   for free; the click is intercepted only so the panel can close itself and
   the scroll can be smooth.                                                 */
const tocWrap = $('#tocwrap'), tocBtn = $('#toc'), tocQ = $('#tocq');
const tocEntries = $$('#toclist a.toce'), tocHeads = $$('#toclist .tocch');

function tocOpen(on, keepFocus) {
  tocWrap.hidden = !on;
  tocBtn.classList.toggle('on', on);
  tocBtn.setAttribute('aria-expanded', on ? 'true' : 'false');
  // focus() scrolls its target into view, and the button lives in a fixed
  // header -- without preventScroll, closing the panel throws you to the top.
  // On a touch screen the focus is withheld on purpose: it would raise the
  // keyboard over the very list you opened the panel to look at.
  if (on) {
    if (matchMedia('(pointer: fine)').matches) {
      tocQ.focus({preventScroll: true}); tocQ.select();
    }
  } else if (!keepFocus) tocBtn.focus({preventScroll: true});
}
tocBtn.onclick = () => tocOpen(tocWrap.hidden);
$('#tocx').onclick = () => tocOpen(false);
$('#tocback').onclick = () => tocOpen(false);

// the same range frank_strip drops in LaTeX (the language's, from the
// registry record): nobody types the vowel marks, so the query is matched
// against a copy of the incipit that has none either
const stripMarks = LANG.strip
  ? (re => s => s.replace(re, ''))(new RegExp('[' + LANG.strip + ']', 'g'))
  : s => s;
// the same fold the build applied to data-q (languages.fold / FOLD_JS): the
// two must agree character for character, and toLowerCase alone would spell
// a Turkish İ as i + a combining dot that nobody can type
const foldCase = __FOLD__;
function tocFilter() {
  const q = stripMarks(foldCase(tocQ.value.trim()));
  for (const a of tocEntries) a.hidden = !!q && a.dataset.q.indexOf(q) < 0;
  // A MATCH HAS TO BE REACHABLE.  Filtering with a chapter folded away would
  // find the entry and show nothing, so a search opens what it searches; what
  // was folded before is left folded once the box is empty again.
  if (q) tocGroups().forEach(g => tocSet(g, true));
  // a section or a chapter left with nothing under it is just noise
  for (const g of $$('#toclist .tocsgrp'))
    g.hidden = !g.querySelector('a.toce:not([hidden])');
  for (const h of tocHeads)
    h.hidden = !tocEntries.some(a => a.dataset.ch === h.dataset.ch && !a.hidden);
  for (const g of $$('#toclist .tocgrp'))
    g.hidden = !g.querySelector('a.toce:not([hidden])');
  $('#tocempty').hidden = tocEntries.some(a => !a.hidden);
}
tocQ.addEventListener('input', tocFilter);

function tocGo(a) {
  const el = document.getElementById(a.getAttribute('href').slice(1));
  if (!el) {
    // Its chapter is still a file beside the reader: fetch it, then jump --
    // BY INDEX (data-ci), which is what the build writes on the section.  The
    // entry's data-ch is the printed chapter number, and asking by that
    // fetched a different chapter's file, after which this retry found the
    // paragraph still missing and the jump died without a word.
    needChapters(+a.dataset.ci || 0).then(got => { if (got) tocGo(a); });
    return;
  }
  tocOpen(false, true);          // the paragraph is what should have the eye now
  reveal(el, 'start', 'smooth'); // and if it is folded away, it is shown first
}
$('#toclist').addEventListener('click', e => {
  const a = e.target.closest('a.toce');
  if (!a) return;
  e.preventDefault();            // scroll-margin handles the header either way
  tocGo(a);
});

// Its own listener rather than a branch inside the player's: Escape has to
// work while the caret is in the filter box, which that one deliberately
// ignores, and none of this should be able to break playback.
addEventListener('keydown', e => {
  // a sheet over the page is above the contents, and so is the download,
  // which hangs from the same edge of the header and would be buried by it
  if (ankiOpen || chOpen || dlOpen || fdShown || secShown || rgShown) return;
  if (e.defaultPrevented) return;  // e.g. the Escape that just closed it
  if (tocWrap.hidden) {
    if ((e.key === 'c' || e.key === 'C') && !e.metaKey && !e.ctrlKey && !e.altKey &&
        !/^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) {
      e.preventDefault(); tocOpen(true);
    }
    return;
  }
  if (e.key === 'Escape') { e.preventDefault(); tocOpen(false); return; }
  const vis = tocEntries.filter(a => !a.hidden);
  if (e.key === 'Enter' && e.target === tocQ) {
    if (vis.length) { e.preventDefault(); tocGo(vis[0]); }
  } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    if (!vis.length) return;
    e.preventDefault();
    const i = vis.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') vis[i < 0 ? 0 : Math.min(i + 1, vis.length - 1)].focus();
    else if (i <= 0) tocQ.focus({preventScroll: true});
    else vis[i - 1].focus();
  }
});

/* ---------- the contents as a tree, and the sections sheet ---------------
   The panel is chapters, the sections inside them and the paragraphs inside
   those.  Each chapter and each section folds on its own, so the book can be
   walked at whatever depth is wanted: fold everything and it is a list of
   chapter names; open one and its sections show; open a section and its
   paragraphs do.  A book with NO SECTIONS is a chapter holding paragraphs
   directly and folds exactly the same way.

   Nothing is folded to begin with -- the panel opens as the flat list it has
   always been -- so a reader who never touches this sees what they saw.    */
function tocGroups() { return $$('#toclist .tocgrp, #toclist .tocsgrp'); }
function tocSet(g, open) {
  if (!g) return;
  g.classList.toggle('closed', !open);
  const b = g.querySelector(':scope > .tocch > .tocfold, :scope > .tocsec > .tocfold');
  if (b) b.setAttribute('aria-expanded', open ? 'true' : 'false');
}
$('#toclist').addEventListener('click', e => {
  const f = e.target.closest('.tocfold');
  if (f) {
    e.preventDefault();
    const g = f.closest('.tocgrp, .tocsgrp');
    tocSet(g, g.classList.contains('closed'));
    return;
  }
  const ed = e.target.closest('.tocedit');
  if (ed) { e.preventDefault(); secOpen(true, ed.dataset); }
});
$('#tocfoldall').onclick = () => tocGroups().forEach(g => tocSet(g, false));
$('#tocopenall').onclick = () => tocGroups().forEach(g => tocSet(g, true));
$('#tocsecs').onclick = () => secOpen(true, null);

/* The sheet that writes them.  Every list in it is read off the contents
   tree, which the build wrote from the .tex -- so the sheet and the panel
   can never disagree about what the book holds, and there is no second
   endpoint to ask.                                                          */
let secShown = false;
function secSum() {
  const c = $$('#toclist .tocgrp').length, s = $$('#toclist .tocsgrp').length;
  $('#secsum').textContent =
    c + (c === 1 ? ' chapter' : ' chapters') + ', ' +
    (s ? s + (s === 1 ? ' section' : ' sections') : 'no sections') + ' in this book.';
}
let secPicker = null;
function secPick() {
  if (secPicker) return secPicker;
  secPicker = outlinePicker({
    depth: 'para', point: true, label: 'the chapters and paragraphs of the book',
    // a chapter is what is named; a paragraph is where a section opens (one
    // with no key -- a .tex whose name carries no chapter number -- cannot be
    // named, exactly as it cannot be folded)
    can: row => row.kind === 'ch' || (row.kind === 'p' && !!row.pkey),
    // a section already in the book is picked by its heading, and what that
    // picks is the paragraph it opens at: the place its mark is written
    redirect: row => row.kind === 'sec'
      ? (row.kids.find(p => p.pkey === row.p) || row.kids[0] || row) : row,
    hint: 'Pick a chapter to name it, or a paragraph to start a section there. A ' +
          'section already in the book is picked by its heading, to rename or remove it.',
    onChange: secShow,
  });
  $('#secpick').appendChild(secPicker.el);
  return secPicker;
}
// the section that opens at a paragraph of the outline, or null
function secAt(p) {
  return p && p.up && p.up.kind === 'sec' && p.up.p === p.pkey ? p.up : null;
}
function secPicked(kind) {
  const got = secPicker && secPicker.get();
  return got && got.row && got.row.kind === kind ? got.row : null;
}
// WHAT THE SHEET OFFERS FOLLOWS WHAT IS PICKED: a chapter's name for a
// chapter, a section's for a paragraph -- and "rename" and "remove" where a
// section already opens there, so the button always says what it will do
function secShow() {
  const ch = secPicked('ch'), para = secPicked('p');
  $('#secchrow').hidden = !ch;
  $('#secrow').hidden = !para;
  if (ch) $('#secchname').value = ch.name || '';
  if (para) {
    const sec = secAt(para);
    $('#secname').value = sec ? sec.name : '';
    $('#secdo').textContent = sec ? 'rename this section' : 'start a section here';
    $('#secdel').hidden = !sec;
  }
}
function secOpen(on, from) {
  secShown = !!on;
  $('#secback').hidden = !on;
  $('#secbox').hidden = !on;
  if (!on) return;
  const pk = secPick().load();
  secSum();
  // what to start on: what the contents' pencil was pressed beside, or else
  // the paragraph being read
  const m = pk.model;
  let row = null;
  if (from && from.kind === 'chapter' && from.ch) row = m.chapters.find(c => c.ch === from.ch);
  else if (from && from.kind === 'section' && from.p) row = m.paras.find(x => x.pkey === from.p);
  else if (cur >= 0 && SUBS[cur] && SUBS[cur][4] >= 0) row = m.paras[SUBS[cur][4]];
  if (row && row.lo != null && (row.kind === 'ch' || row.pkey)) pk.set(row.lo, row.hi, row);
  secShow();
  $('#secstat').textContent = '';
  $('#secstat').classList.remove('bad');
  $('#secreload').hidden = true;
  pk.focus();
}
async function secSend(url, body, said) {
  const stat = $('#secstat');
  stat.textContent = 'saving…';
  stat.classList.remove('bad');
  $('#secreload').hidden = true;
  try {
    const r = await fetch(url, {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    const j = await r.json();
    // A refusal is a sentence written to be read -- structure.py refuses by
    // naming what changed when it should not have.  Show it whole.
    if (!j.ok) { stat.textContent = j.error || 'refused';
                 stat.classList.add('bad'); return; }
    // The heading in the text and the rows in the panel are both written at
    // build time, so the page is behind the file until it is read again --
    // the same thing dividing a chunk says, and the same offer.
    const badBuild = !!(j.reader && !j.reader.ok);
    stat.textContent = said + (badBuild
      ? ' — but the reader would not rebuild: ' + (j.reader.error || 'no reason given')
      : ' — reload to see it in the book');
    stat.classList.toggle('bad', badBuild);
    $('#secreload').hidden = badBuild;
  } catch (e) {
    stat.textContent = 'the server did not answer (' + (e.message || e) + ') — an edit '
      + 'needs this page served by python3 serve.py; nothing was written';
    stat.classList.add('bad');
  }
}
$('#secchdo').onclick = () => {
  const ch = secPicked('ch');
  if (ch) secSend('__struct/chapter', {chapter: ch.ch, title: $('#secchname').value},
                  $('#secchname').value.trim() ? 'the chapter was named'
                                               : 'the chapter’s name was taken away');
};
$('#secdo').onclick = () => {
  const p = secPicked('p');
  if (p) secSend('__struct/section', {para: p.pkey, title: $('#secname').value, on: true},
                 'the section was written');
};
$('#secdel').onclick = () => {
  const p = secPicked('p');
  if (p) secSend('__struct/section', {para: p.pkey, on: false}, 'the section was taken away');
};
// Enter in a name box presses its button: the form itself never submits
for (const [box, btn] of [['#secchname', '#secchdo'], ['#secname', '#secdo']])
  $(box).addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); $(btn).click(); } });
$('#seccancel').onclick = () => secOpen(false);
$('#secclose').onclick = () => secOpen(false);
$('#secback').onclick = () => secOpen(false);
$('#secreload').onclick = () => location.reload();
$('#secbox').addEventListener('submit', e => e.preventDefault());
addEventListener('keydown', e => {
  if (secShown && e.key === 'Escape') { e.preventDefault(); secOpen(false); } });

/* ---------- the header states which build it is, and how tall it is ------- */
$('#build').textContent = META.build + ' ' + META.built;
function fitHeader() {
  const h = document.querySelector('header').offsetHeight;
  document.body.style.paddingTop = (h + 6) + 'px';
  // the contents hangs off the bottom of the header and every jump has to
  // clear it, so the measured height goes where the CSS can read it
  document.documentElement.style.setProperty('--headh', h + 'px');
}
fitHeader();
addEventListener('resize', fitHeader);
if (window.ResizeObserver)
  new ResizeObserver(fitHeader).observe(document.querySelector('header'));

/* ---------- the header, put away by hand ----------------------------------
   THREE ROWS STAND OVER THE TEXT: play controls, the book's own tools, and
   the narration scrub when it shows.  Once the place to read from is set
   they are in the way -- "bars" takes the header off outright (fitHeader
   reclaims the space the moment it does) and leaves one faint button in the
   corner, outside the header since the header itself is gone; pressing that
   brings it back.  Remembered for every book and not for one: it is a way
   of reading, not a property of a page -- the studio's own bars button,
   app.js bindBarsToggle, is the exact same idea, and the same class name,
   chrome-off.

   AND THE PHONE'S OWN HIDING STANDS DOWN WHILE THIS IS ON (parseh.js:
   bars()).  Scrolling still moves the page underneath, but it no longer
   touches the header while chrome-off is set: touching it regardless would
   only leave barhidden stuck however the reader last scrolled, so that
   bringing the header back by hand could hand it straight off-screen again.
   So coming back clears barhidden too -- pressing "bars" is what decides,
   not the last scroll. */
const BARS_KEY = 'bk_bars';
function setBars(v, byHand) {
  document.body.classList.toggle('chrome-off', v);
  fitHeader();
  $('#bars').hidden = v;
  $('#barsback').hidden = !v;
  $('#bars').setAttribute('aria-expanded', String(!v));
  $('#barsback').setAttribute('aria-expanded', String(!v));
  localStorage.setItem(BARS_KEY, v ? '1' : '0');
  if (!v) document.body.classList.remove('barhidden');
  if (byHand) (v ? $('#barsback') : $('#bars')).focus({preventScroll: true});
}
$('#bars').onclick = () => setBars(true, true);
$('#barsback').onclick = () => setBars(false, true);
setBars(localStorage.getItem(BARS_KEY) === '1', false);

/* ---------- hover mode: pass 2 as a gloss cloud over pass 1 ---------------
   Borrowed whole from the video player (youtube/lib/player.js): the same
   cloud, the same placement, the same touch behaviour.  The gloss text is
   never duplicated -- the cloud reads it out of the pass-2 row for the same
   chunk, which hover mode merely hides.                                    */
const HOVER_OK = matchMedia('(hover: hover)').matches;
/* WHETHER THE POINTER IN THE READER'S HAND IS A FINGER -- asked of the
   event, not of the device.  `hover: hover` is a claim a phone may make
   too (a tablet with a stylus, a browser answering for the mouse it might
   one day have), and where it did, the tap path stayed switched off while
   no hover ever came: the tap's own synthetic mouseover opened the cloud
   and the click behind it closed the same cloud again, so a finger got
   nothing.  Every pointer event now says what it was, and the hover paths
   stand down while the last pointer was a finger.  A mouse never sets it,
   so nothing here changes on a desktop.                                   */
let touchNow = false;
addEventListener('pointerdown', e => {
  touchNow = e.pointerType === 'touch' || e.pointerType === 'pen';
}, true);
const hoverPointer = () => HOVER_OK && !touchNow;
const cloud = $('#cloud');
let cloudFor = null, cloudC = -1, hideTimer = null, ankiOpen = false;

/* THE TOGGLES HOVER MODE TAKES AWAY.  The mode swallows the chunks and
   their glosses (p2) and the alternate face (p4); the gloss switch acts on
   nothing else.  While it is on, those buttons are disabled -- greyed and
   dead, the way `definitions` is without a dictionary -- because pressing
   them would change nothing on the page.  The text passes keep their
   buttons: hover mode showing pass 1 alone is what they are for.          */
const HOVER_LOCKS = ['no2', 'no4', 'nogloss'];
function passLocks(on) {
  HOVER_LOCKS.forEach(cls => {
    const b = $('[data-toggle=' + cls + ']');
    if (!b) return;
    if (b.dataset.t0 === undefined) b.dataset.t0 = b.title;
    b.disabled = on;
    b.title = on ? 'hover mode shows the glosses in the cloud instead'
                 : b.dataset.t0;
  });
}

function setHover(on) {
  document.body.classList.toggle('hovermode', on);
  $('#hovermode').classList.toggle('on', on);
  localStorage.setItem('bk_hover', on ? '1' : '0');
  passLocks(on);
  if (!on) closeCloud();
}
$('#hovermode').onclick = () => setHover(!document.body.classList.contains('hovermode'));
if (localStorage.getItem('bk_hover') === '1') setHover(true);

// the text of a pass-1 element WITHOUT its readings: textContent would run
// the kana of every <rt> into the words, and a copied chunk or a card's
// context sentence must be the text alone
function textOf(el) {
  if (!el.querySelector('rt')) return el.textContent;
  const c = el.cloneNode(true);
  c.querySelectorAll('rt').forEach(r => r.remove());
  return c.textContent;
}
function rowOf(n) { return document.querySelector('.row[data-c="' + n + '"]'); }
// A chunk's word line, where its language is divided into words and the
// chunk has one; '' for every other chunk, which is looked up, carded and
// edited exactly as it always was.
function lineOf(n) {
  const line = LANG.words ? (SRC[n] || [])[6] || '' : '';
  return line.trim() ? line : '';
}
// its words, [[surface, reading], ...], or null for a line that has none
function linePairs(line) {
  if (!line) return null;
  try { return ParsehWordline.parse(line); } catch (_) { return null; }
}
// a lookup's body with the chunk's word line, where it has one: the
// dictionary then looks up the words a person divided, one row each, and
// each row names its word's place in the line (`i`)
function withLine(body, line) { if (line) body.words = line; return body; }
function chunkData(n) {
  const row = rowOf(n); if (!row) return null;
  const q = s => row.querySelector(s);
  const t = el => el ? el.textContent.replace(/\s+/g, ' ').trim() : '';
  // the text without the readings a worded chunk's words wear in the column;
  // `drawn` says the build drew it from its line, `words` is that line
  const fa = q('.fa');
  return { fa: fa ? textOf(fa).replace(/\s+/g, ' ').trim() : '',
           kana: t(q('.gl .kana')), tr: t(q('.gl .tr')),
           en: t(q('.gl .en')), voc: t(q('.gl .voc')), vocEl: q('.gl .voc'),
           words: lineOf(n), drawn: !!q('.fa .wd[data-w]') };
}
function fillCloud(d) {
  cloud.textContent = '';
  const el = (cls, txt) => { const x = document.createElement('div');
    x.className = cls; if (txt) x.textContent = txt;
    cloud.appendChild(x); return x; };
  el('arrow');
  if (d.kana) el('kana', d.kana).setAttribute('lang', LANG.code);   // the reading, above the rōmaji
  if (d.tr) el('tr', d.tr);
  // The vocabulary and the meaning are prose in the gloss language, and the
  // cloud around them is the page's own chrome: they say which language they
  // are so the browser shapes and hyphenates them as the row does.
  const glossed = e => { e.setAttribute('lang', GLOSS.code);
    if (GLOSS.dir === 'rtl') e.setAttribute('dir', 'rtl'); return e; };
  // the vocabulary keeps its markup (the bdi.v isolates), so it is cloned
  // as HTML -- it is this build's own output, not user input
  if (d.vocEl) glossed(el('voc')).innerHTML = d.vocEl.innerHTML;
  if (d.en) glossed(el('en', d.en));
  // The panel never appears where somebody has written a vocabulary line.
  // That is the whole rule: it exists for the chunk nobody has got to yet,
  // and a finished edition should look exactly as it looked before it was
  // built.
  if (!d.voc && cloudC >= 0) {
    if ((DICT.ready || MT.ready) && DICT.on) dictInto(el('dict'), cloudC, d.fa);
    // NOTHING SET UP AT ALL, and the reader is looking at an empty chunk:
    // this is the one moment they want to know the feature exists, so say
    // so here rather than only in a header they have not read.
    if (!DICT.ready && !MT.ready) {
      const o = el('dict');
      o.innerHTML = '<div class="dhead">nothing glossed here yet</div>' +
        '<div class="dnone">A dictionary can look these words up, a corpus ' +
        'can show a sentence somebody translated, and a model can read the ' +
        'line. <a href=\"__HUB__settings/reading-help/\">Set any of them up</a> — it takes ' +
        'a couple of minutes.</div>';
    }
  }
  // "I know this" a word at a time for a chunk its word line drew, and a
  // kanji at a time for a chunk drawn without one
  if (READINGS && d.drawn) READINGS.wordControls(cloud, d.words);
  else if (READINGS && d.kana) READINGS.controls(cloud, d.fa);
  const row = el('mkrow');
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'mkcard'; b.textContent = '+ card';
  b.title = 'make a card of this chunk: for Anki, an exercise deck, or as markdown';
  row.appendChild(b);
  const c = document.createElement('button');
  c.type = 'button'; c.className = 'mkcopy'; c.textContent = '\u2a09 copy';
  c.title = 'copy this chunk';
  row.appendChild(c);
  // and the pencil, always, as the video player's cloud has it
  const p = document.createElement('button');
  p.type = 'button'; p.className = 'mkedit'; p.textContent = '\u270e edit';
  p.title = 'write this chunk back into the .tex (E)';
  row.appendChild(p);
}
/* ---------- the dictionary behind an unglossed chunk ----------------------
   A source of last resort, drawn in a borrowed panel and under one rule: IT
   IS NOT A GLOSS.  A gloss is somebody's judgement about this word in this
   sentence; a dictionary lists every sense the word can ever have and cannot
   say which is meant.  So it is ruled off, tinted, labelled with where it
   came from, and offered only where nobody has written a vocabulary line.
   It has its own switch in the header, and the switch defaults OFF: a reader
   who does not want it never sees it, and the page makes no request.

   The panel is built here and filled asynchronously, because the cloud must
   open at once and a lookup is a round trip.  Every answer is stamped with
   the chunk it was asked for and dropped if the cloud has moved on, which it
   will have. */
const DICT = { on: localStorage.getItem(MINE('dict')) === '1', ready: false, src: null,
               words: false, pairs: false, corpus: null, cache: new Map(),
               // English's definitions, and their translation: switches of
               // their own (see "English, explained in English" below)
               defines: false, defs: localStorage.getItem(MINE('defs')) === '1',
               defsMt: localStorage.getItem(MINE('defs_mt')) === '1' };
// how far ahead the preparing loop looks, in sentences
const AHEAD = 10;
// AND A TRANSLATION MODEL, if one has been fetched for this pair of
// languages.  It is a separate thing from the dictionary and asked for
// separately: a model reads the sentence, a dictionary reads the words, and
// neither is a gloss.  The 20 MB is loaded by the preparing loop's first
// batch once the switch is on, and not at all while it is off -- the switch
// is what guards it, where a button used to.
const MT = { ready: false, about: null,
             // WHAT IS KEPT, AND WHY TWO MAPS.  A sentence's translation is
             // shared by every chunk of that sentence and is what the panel
             // shows; a chunk's own translation is a probe, used only to
             // guess which words of the sentence are its.  Both are bounded:
             // a long book would otherwise hold every sentence it has passed.
             sent: new Map(), probe: new Map(), want: [] };
const MT_KEEP = 400;
// A person's pasted answer from an external chatbot.  The complete sentence
// is the key, just as it is for MT.sent: opening any other chunk in that
// sentence therefore reuses one answer and only changes which words are
// marked for the current chunk.
const LLM = {sent: new Map()};

function dictSwitch(st, btn, key, on) {
  st.on = on;
  btn.classList.toggle('on', on);
  localStorage.setItem(MINE(key), on ? '1' : '0');
  showDefs();
  if (cloudFor) { const sp = cloudFor; cloudFor = null; openCloud(sp); }
}
const dictBtn = $('#dictmode');
dictBtn.onclick = () => dictSwitch(DICT, dictBtn, 'dict', !DICT.on);

/* ---------- English, explained in English ----------------------------------
   Every dictionary here is the English Wiktionary's, and it explains the
   words of every language in English.  For Persian or Italian that is a
   translation -- خانه is "house" -- and for English itself it is a
   DEFINITION: `house` is "a structure serving as an abode of human beings",
   written in the very language the reader is learning and not necessarily
   one they can read yet.  So where the server says the dictionary defines its
   words in their own language (`definitions`), the definitions are a switch
   of their own, OFF until it is turned on, and an entry without them still
   says everything else it knows: the headword, how it is said, its part of
   speech, how the word was reached, a verb's parts.  On, every sense is there
   -- the first three, the rest one click away -- with the labels Wiktionary
   puts on it (transitive, countable, slang).  A second switch, where a
   translation model reads this pair, puts each definition into the language
   of the glosses under it: a machine's reading of a definition, drawn as
   one.  Both sit in the header, to flip while reading, remembered like the
   dictionary's own. */
const DEFS_SHOWN = 3;             // what an entry opens with: lookup's MAX_SENSES
const DEFT = new Map();           // a definition -> its translation
const DEFT_KEEP = 2000;
let DEFT_FAILED = false;          // the look-ahead's, after the model failed it once
const defBtn = $('#defmode'), defMtBtn = $('#defmt');
function defsOn() { return DICT.defines && DICT.defs; }
function defsTranslated() {
  return defsOn() && DICT.defsMt && MT.ready && typeof ParsehMT !== 'undefined';
}
// hidden where they mean nothing (another language, no model for the pair),
// greyed while the switch each hangs from is off
function showDefs() {
  defBtn.hidden = !DICT.defines;
  defBtn.disabled = !DICT.on;
  defBtn.classList.toggle('on', DICT.defs);
  defBtn.title = 'the dictionary\'s own definitions, in ' + LANG.name + ', under each word it finds';
  defMtBtn.hidden = !(DICT.defines && MT.ready);
  defMtBtn.disabled = !(DICT.on && DICT.defs);
  defMtBtn.classList.toggle('on', DICT.defsMt);
  defMtBtn.textContent = 'in ' + GLOSS.name.toLowerCase();
  defMtBtn.title = 'each definition put into ' + GLOSS.name + ' under it, by the translation ' +
                   'model on this machine: a machine\'s reading, not a gloss';
}
function defsSwitch(key, on) {
  DICT[key] = on;
  localStorage.setItem(MINE(key === 'defs' ? 'defs' : 'defs_mt'), on ? '1' : '0');
  showDefs();
  sideDefs();                     // and the sources of a sheet open over the page
  PRE.queue = [];                 // lined up for the switch as it was
  if (cloudFor) { const sp = cloudFor; cloudFor = null; openCloud(sp); }
}
defBtn.onclick = () => defsSwitch('defs', !DICT.defs);
defMtBtn.onclick = () => defsSwitch('defsMt', !DICT.defsMt);
// the whole entry is asked for with the definitions on, and only then
function withSenses(body) { if (defsOn()) body.senses = 'all'; return body; }
// a hit's definitions: the first DEFS_SHOWN, and the rest behind a button
function defsBlock(h) {
  const all = (h.senses || []).map((s, i) => [s, (h.marks || [])[i] || ''])
    .concat((h.more || []).map((s, i) => [s, (h.more_marks || [])[i] || '']));
  const box = document.createElement('div');
  box.className = 'ddefs';
  all.forEach(([s, mark], i) => {
    const d = document.createElement('div');
    d.className = 'dsense ddef';
    d.setAttribute('lang', LANG.code);
    d.dataset.def = s;
    if (i >= DEFS_SHOWN) d.hidden = true;
    // what Wiktionary labels the sense with (lib/parseh.js, the player's too)
    const label = Parseh.senseLabels(mark, h.pos).join(', ');
    if (label) {
      const l = document.createElement('span');
      l.className = 'dlabel'; l.textContent = '(' + label + ') ';
      d.appendChild(l);
    }
    d.appendChild(document.createTextNode(s));
    box.appendChild(d);
  });
  const more = all.length - DEFS_SHOWN;
  if (more > 0) {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'ddefmore';
    b.textContent = more + ' more definition' + (more === 1 ? '' : 's');
    b.onclick = () => {
      for (const d of box.querySelectorAll('.ddef[hidden]')) d.hidden = false;
      // hidden and not removed: to whatever asks after this handler, a click
      // whose target has left the page is a click outside the cloud
      b.hidden = true;
      defsInto(box);
      refitCloud(box);
    };
    box.appendChild(b);
  }
  return box;
}
// The definitions in `box` read in the glosses' language: each element `sel`
// names that shows holds its definition in data-def and is given the
// translation as a .dtr of its own -- the ones already read at once, the rest
// in one call.  `after` runs when a late answer lands; `onRead(el, text)`
// once for an element, when its translation is in.
function defsRead(box, sel, after, onRead) {
  // what shows inside `box`: neither the element nor anything between it and
  // the box hidden -- the cloud around a box may well be, for it is filled
  // before it is placed and shown
  const shows = d => { for (let e = d; e && e !== box; e = e.parentElement) if (e.hidden) return false; return true; };
  const shown = () => [...box.querySelectorAll(sel)].filter(shows);
  const draw = () => {
    for (const d of shown()) {
      let t = d.querySelector(':scope > .dtr');
      if (!t) {
        t = document.createElement('div');
        t.className = 'dtr';
        t.setAttribute('lang', GLOSS.code);
        if (GLOSS.dir === 'rtl') t.setAttribute('dir', 'rtl');
        d.appendChild(t);
      }
      const got = DEFT.get(d.dataset.def);
      t.textContent = got === undefined ? '…' : got;
      t.classList.toggle('dwaiting', got === undefined);
      if (got !== undefined && onRead && !d.dataset.read) { d.dataset.read = '1'; onRead(d, got); }
    }
  };
  const want = [];
  for (const d of shown())
    if (!DEFT.has(d.dataset.def) && want.indexOf(d.dataset.def) < 0) want.push(d.dataset.def);
  draw();
  if (!want.length) return;
  ParsehMT.translate(LANG.code, GLOSS.code, want).then(got => {
    want.forEach((s, k) => DEFT.set(s, got[k] || ''));
    deftTrim();
    if (!box.isConnected) return;
    draw();
    if (after) after();
  }).catch(err => {
    if (!box.isConnected) return;
    for (const t of box.querySelectorAll('.dtr.dwaiting'))
      t.textContent = (err && err.message) || 'the model could not be run';
    if (after) after();
  });
}
// the panel's definitions, while their switch is on
function defsInto(box) {
  if (defsTranslated()) defsRead(box, '.ddef', () => refitCloud(box));
}
function deftTrim() {
  while (DEFT.size > DEFT_KEEP) DEFT.delete(DEFT.keys().next().value);
}

// EVERY LOOKUP GOES THROUGH THE ONE ASK THAT CANNOT HANG (lib/parseh.js,
// `ask`).  A bare fetch towards a computer on the far side of a tunnel that
// has gone is not refused, it is swallowed: this page showed "looking it
// up\u2026" in the cloud for ever, and one opened away never grew its
// dictionary button at all.  The ask is not timed -- it is watched beside
// the one cheap question "is anybody there?", so an honestly slow answer is
// still waited for.  Where lib/parseh.js is not on the page (a reader opened
// straight off the disk) it is a plain fetch, exactly as it was.
function pAsk(u, i) {
  return (window.Parseh && Parseh.ask) ? Parseh.ask(u, i) : fetch(u, i);
}
// Ask once, on load, whether it is installed; a button nobody can use is a
// button that should not be there.  The question is quiet: a toolbox with
// no dictionary is exactly the toolbox as it was.
pAsk('__lookup', {method: 'POST', headers: {'Content-Type': 'application/json'},
                   body: JSON.stringify({about: 1})})
  .then(r => r.json()).then(j => {
    // THE SWITCH IS FOR ALL OF THEM, not for the dictionary alone.  The
    // dictionary and the corpus are separate downloads and either can be
    // here without the other; a reader with a corpus and no dictionary used
    // to get no button at all, and so no way to reach what they had
    // downloaded.
    if (!j || !j.help) return;
    DICT.ready = true; DICT.src = j.source || {};
    DICT.words = !!j.available; DICT.pairs = !!j.corpus_available;
    DICT.corpus = j.corpus || {};
    DICT.defines = !!j.definitions;
    showHelp();
    // one local SQLite read per chunk, so preparing ahead is free
    preStart();
  }).catch(() => {});

/* The header button, and what it says it is for -- which depends on which of
   the three a reader has actually got. */
function showHelp() {
  if (!(DICT.ready || MT.ready)) return;
  const has = [];
  if (DICT.words) has.push('look the words up');
  if (DICT.pairs) has.push('show a sentence somebody translated');
  if (MT.ready) has.push('translate the line');
  dictBtn.hidden = false;
  dictBtn.classList.toggle('on', DICT.on);
  dictBtn.title = has.length
    ? has.join(', ') + ' — where nothing is glossed'
    : 'reading help where nothing is glossed';
  showDefs();
}
if (typeof ParsehMT !== 'undefined')
  ParsehMT.has(LANG.code, GLOSS.code).then(m => {
    if (!m) return;
    MT.ready = true; MT.about = m;
    // a model alone is enough to want the switch: it is the one of the three
    // that reads the whole line
    showHelp();
    preStart();
    if (cloudFor) { const sp = cloudFor; cloudFor = null; openCloud(sp); }
  }).catch(() => {});

// a word's own reading, to sit beside it: kana, or a romanisation (pinyin)
// that is Latin letters and says so
function readingSpan(r) {
  const s = document.createElement('span');
  s.className = 'dread'; s.textContent = r;
  if (!LANG.reading) s.setAttribute('lang', LANG.code + '-Latn');
  return s;
}
// `at` is the word of the chunk's word line the row was asked for,
// [surface, reading]: the row is headed as the line writes it
function dictLine(w, at) {
  const wrap = document.createElement('div');
  wrap.className = 'dw';
  const head = document.createElement('div');
  head.className = 'dwd'; head.textContent = at ? at[0] : w.word;
  head.setAttribute('lang', LANG.code);
  if (at && at[1]) { head.appendChild(document.createTextNode(' ')); head.appendChild(readingSpan(at[1])); }
  wrap.appendChild(head);
  if (!w.hits.length) {
    const none = document.createElement('div');
    none.className = 'dnone';
    // what it looked for, not merely that it failed: a reader can then tell
    // "this word is not in the dictionary" from "the dictionary was never asked"
    none.textContent = 'not found (tried ' + w.tried.join(', ') + ')';
    wrap.appendChild(none);
    return wrap;
  }
  // WHAT THE SPOKEN PASS READ (lib/spoken.py): a hit that was read as another word is drawn by lib/parseh.js, the same in the
  // player's panel -- a pill, the word it was read as, why, its pieces, its sound -- and a word with several readings numbers
  // them.  A page without parseh.js draws the hit as it always did, and the hit's note says the reason.
  const SP = window.Parseh && Parseh.spoken;
  const many = SP ? SP.header(w) : null;
  if (many) wrap.appendChild(many);
  for (const [k, h] of w.hits.entries()) {
    const row = document.createElement('div');
    row.className = 'dhit' + (SP ? SP.row(h) : '');
    if (many) {
      const num = document.createElement('span');
      num.className = 'dsnum'; num.textContent = (k + 1) + '.';
      row.appendChild(num);
    }
    const hd = document.createElement('span');
    hd.className = 'dhead2';
    // as the book spells it, like the editor's row (sideHit): 帮忙 in a
    // simplified book, not the 幫忙 Wiktionary files it under
    hd.textContent = (h.spelled || h.headword) + (h.translit ? ' ' + h.translit : '');
    if (h.spelled && h.spelled !== h.headword)
      hd.title = 'the dictionary files it under ' + h.headword;
    row.appendChild(hd);
    if (h.pos) { const p = document.createElement('span');
      p.className = 'dpos'; p.textContent = ' ' + h.pos; row.appendChild(p); }
    const said = SP ? SP.note(h) : h.note;
    if (said) { const n = document.createElement('span');
      n.className = 'dnote'; n.textContent = ' — ' + said; row.appendChild(n); }
    if (SP && h.spoken) {
      const b = SP.block(h, {written: w.word, lang: LANG.code, dir: LANG.dir});
      if (b) row.appendChild(b);
    }
    // A VERB CARRIES ITS PRINCIPAL PARTS, under the headword and before the
    // senses: "to burn" is what the infinitive means, and the stem the
    // sentence is actually built on is what a reader was left to guess.
    // Present only where the language's recipe knew the hit for a verb --
    // and led by that verb when it is not this headword, as the editor's row
    // is (sideHit): stehen reached from `stand … auf` carries aufstehen's
    // parts, and `pret. stand auf` under "stehen" explains nothing.
    const vbl = h.vb ? [] : null;
    if (vbl && h.vb.lemma && wordKey(h.vb.lemma) !== wordKey(h.spelled || h.headword))
      vbl.push('→ ' + h.vb.lemma);
    if (vbl && h.vb.line) vbl.push(h.vb.line);
    if (vbl && vbl.length) {
      const v = document.createElement('div');
      v.className = 'dvb'; v.textContent = vbl.join(' · ');
      row.appendChild(v);
    }
    // a dictionary that defines its words in their own language shows its
    // senses only with that switch on, and then as definitions
    if (!DICT.defines) {
      for (const sn of h.senses) {
        const d = document.createElement('div');
        d.className = 'dsense'; d.textContent = sn; row.appendChild(d);
      }
    } else if (DICT.defs) {
      row.appendChild(defsBlock(h));
    }
    wrap.appendChild(row);
  }
  // (a word the spoken pass read says how in each of its cards: the line that says it again is left out)
  if (w.via && w.via !== 'as written' && !(SP && w.kind === 'spoken')) {
    const v = document.createElement('div');
    v.className = 'dnone'; v.textContent = 'found ' + w.via;
    wrap.appendChild(v);
  }
  return wrap;
}

function dictFill(box, j) {
  box.textContent = '';
  // Each of the three draws only if it has something to draw.  A reader with
  // a corpus and no dictionary gets the sentences and no empty heading; one
  // with only a model gets the button and nothing above it.
  const words = j.words || [];
  if (words.length) {
    // a block of its own, like the two after it, so the rule between blocks
    // has a block on either side to fall between
    const dd = document.createElement('div');
    dd.className = 'ddict';
    const h = document.createElement('div');
    h.className = 'dhead';
    h.textContent = 'dictionary — not a gloss';
    dd.appendChild(h);
    // asked with the chunk's word line, each row names its word's place in
    // the line (`i`): it goes under that word, and nothing is filtered here
    const pairs = linePairs(j.line);
    for (const w of words)
      dd.appendChild(dictLine(w, pairs && typeof w.i === 'number' ? pairs[w.i] || null : null));
    // the definitions off, their switch never touched: the one moment to say
    // there are any, since without them the entry looks as if there were not
    if (DICT.defines && !DICT.defs && localStorage.getItem(MINE('defs')) === null) {
      const n = document.createElement('div');
      n.className = 'dnone';
      n.textContent = 'the dictionary explains these words in ' + LANG.name +
                      ': “Show the dictionary\'s definitions”, in the ⚙ panel, shows what it says';
      dd.appendChild(n);
    }
    const src = document.createElement('div');
    src.className = 'dsrc';
    src.textContent = (j.source && j.source.source ? j.source.source : 'a dictionary') +
                      (j.source && j.source.licence ? ' · ' + j.source.licence : '') +
                      (defsTranslated() ? ' · the definitions put into ' + GLOSS.name + ' by ' +
                                          ((MT.about && MT.about.source) || 'a model') : '');
    dd.appendChild(src);
    box.appendChild(dd);
    defsInto(dd);
  }
  mtInto(box, cloudC, j.text || '', j.words || []);
  pairsInto(box, j);
  if (!box.childNodes.length) {
    const n = document.createElement('div');
    n.className = 'dnone';
    n.textContent = DICT.words
      ? 'the dictionary has nothing for these words'
      : 'nothing here has anything to say about this chunk';
    box.appendChild(n);
  }
}

/* ---------- sentences somebody has already translated ---------------------
   The dictionary lists every sense a word can carry and cannot say which one
   this line means.  A sentence a person translated, holding the same rare
   words, can -- so it is shown UNDER the entries, in its own block, labelled
   as what it is: not this chunk, and not a gloss of it, but the nearest
   thing anybody has written down.  The words it shares are named, because a
   reader should be able to see why a sentence is being offered.           */
function pairsInto(box, j) {
  const pairs = (j.pairs || []).slice();
  if (!pairs.length) return;
  const wrap = document.createElement('div');
  wrap.className = 'dpairs';
  const h = document.createElement('div');
  h.className = 'dhead';
  h.textContent = 'a sentence somebody translated — not this one';
  wrap.appendChild(h);
  const list = document.createElement('div');
  list.className = 'dpair-list';
  wrap.appendChild(list);
  const addPair = p => {
    const one = document.createElement('div');
    one.className = 'dpair';
    const a = document.createElement('div');
    a.className = 'psrc';
    a.setAttribute('lang', LANG.code);
    if (LANG.dir === 'rtl') a.setAttribute('dir', 'rtl');
    const marked = Parseh.pairMarkup(p, j, LANG, GLOSS);
    a.innerHTML = marked.src;
    const b = document.createElement('div');
    b.className = 'pdst';
    b.setAttribute('lang', GLOSS.code);
    if (GLOSS.dir === 'rtl') b.setAttribute('dir', 'rtl');
    b.innerHTML = marked.dst;
    one.appendChild(a); one.appendChild(b);
    if (p.matched && p.matched.length) {
      const m = document.createElement('div');
      m.className = 'pwhy';
      m.textContent = 'shares ' + p.matched.join(', ');
      one.appendChild(m);
    }
    list.appendChild(one);
  };
  pairs.forEach(addPair);
  const src = document.createElement('div');
  src.className = 'dsrc';
  const c = (j.corpus && j.corpus.source) ? j.corpus : (DICT.corpus || {});
  src.textContent = (c.source || 'a corpus') +
                    (c.licence ? ' · ' + c.licence : '');
  wrap.appendChild(src);
  if (j.pairs_more) {
    const more = document.createElement('button');
    more.type = 'button'; more.className = 'dmore'; more.textContent = 'Load more';
    more.addEventListener('click', () => {
      more.disabled = true; more.textContent = 'Loading…';
      pAsk('__lookup', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(withLine({text: j.text || '', sentence: j.sentence || '',
                                       corpus_only: true, corpus_offset: pairs.length,
                                       corpus_limit: 5}, j.line))})
        .then(r => r.json()).then(next => {
          if (!next || !next.ok) throw new Error('refused');
          const added = next.pairs || [];
          added.forEach(p => { pairs.push(p); addPair(p); });
          if (next.pairs_more) {
            more.disabled = false; more.textContent = 'Load more';
          } else more.remove();
          if (wrap.isConnected) refitCloud(wrap);
        }).catch(() => {
          more.disabled = false; more.textContent = 'Load more';
        });
    });
    wrap.appendChild(more);
  }
  box.appendChild(wrap);
}

/* ---------- a machine's reading, of the SENTENCE ---------------------------
   NOT OF THE CHUNK.  A chunk is a fragment by construction -- that is what a
   chunk is -- and a fragment translated alone comes back as one: `مثل ایران
   با هم` gave "The parable of Iran with Hem", while the sentence holding it
   gave sense.  So the sentence is what is translated, the whole of it is
   shown, and the words of it that seem to be THIS chunk's are marked inside
   it.  Which words those are is a guess and is drawn as one -- the engine
   offers no word alignment, so ParsehMT.align works from what the
   dictionary says the chunk's words mean (the lookup this panel has just
   drawn) and from the chunk's own translation, and never from where the
   chunk sits: word order is what a translation changes.

   NO BUTTON.  It is drawn the moment the panel is, because the sentences
   around the reading place have already been translated (preSentences), and
   what has not been is one call away.                                     */
function mtInto(box, n, text, words) {
  if (!MT.ready || typeof ParsehMT === 'undefined') return;
  const ctx = chunkCtx(n);
  const sentence = ctx.sentence || text;
  if (!sentence) return;
  const wrap = document.createElement('div');
  wrap.className = 'dmt';
  box.appendChild(wrap);
  const have = MT.sent.get(sentence), probe = MT.probe.get(text);
  if (have !== undefined && probe !== undefined) {
    mtShow(wrap, have, probe, words, sentence === text);
    return;
  }
  const w = document.createElement('div');
  w.className = 'dwait';
  w.textContent = 'reading the sentence…';
  wrap.appendChild(w);
  const want = [sentence];
  if (text && text !== sentence) want.push(text);
  ParsehMT.translate(LANG.code, GLOSS.code, want).then(got => {
    MT.sent.set(sentence, got[0] || '');
    if (want.length > 1) MT.probe.set(text, got[1] || '');
    if (!wrap.isConnected) return;
    wrap.textContent = '';
    mtShow(wrap, MT.sent.get(sentence), MT.probe.get(text) || '',
           words, sentence === text);
    refitCloud(wrap);
  }).catch(err => {
    if (!wrap.isConnected) return;
    w.textContent = (err && err.message) || 'the model could not be run';
    refitCloud(wrap);
  });
}

function mtShow(wrap, out, probe, words, whole) {
  const h = document.createElement('div');
  h.className = 'dhead';
  h.textContent = whole ? 'a machine\'s reading — not a gloss'
                        : 'a machine\'s reading of the sentence — not a gloss';
  wrap.appendChild(h);
  const t = document.createElement('div');
  t.className = 'mtout';
  t.setAttribute('lang', GLOSS.code);
  if (GLOSS.dir === 'rtl') t.setAttribute('dir', 'rtl');
  const span = whole || !out ? null : ParsehMT.align(out, probe, words, GLOSS.code);
  if (span) {
    // the sentence entire, with this chunk's share of it marked inside it --
    // in as many places as the chunk's meaning landed in
    for (const seg of ParsehMT.marked(out, span)) {
      if (!seg.here) { t.appendChild(document.createTextNode(seg.text)); continue; }
      const b = document.createElement('b');
      b.className = 'mthere' + (span.sure ? '' : ' mtmaybe');
      b.textContent = seg.text;
      t.appendChild(b);
    }
  } else {
    t.textContent = out || '(it produced nothing)';
  }
  wrap.appendChild(t);
  if (!whole && out) wrap.appendChild(mtWhy(span, 'chunk'));
  const srcline = document.createElement('div');
  srcline.className = 'dsrc';
  srcline.textContent = (MT.about && MT.about.source ? MT.about.source : 'a model') +
                        (MT.about && MT.about.engine ? ' \u00b7 ' + MT.about.engine : '');
  wrap.appendChild(srcline);
}

/* The line under the machine's reading: what the mark stands on -- which
   of the chunk's words the dictionary found there, "مثل → parable · ایران
   → Iran" -- or, where nothing matched, that nothing is marked and why.
   Nothing is marked by where the chunk sits: see ParsehMT.align. */
function mtWhy(span, what) {
  const g = document.createElement('div');
  g.className = 'dnone';
  if (!span) {
    g.textContent = 'no word of this reading matches what the dictionary says of the '
                    + what + ', so none is marked';
    return g;
  }
  const why = ParsehMT.why(span);
  g.textContent = (span.sure ? 'this ' + what + ' is likely: ' : 'part of this ' + what + ' is likely: ')
                  + '\u201c' + span.text + '\u201d'
                  + (why ? ' \u2014 ' + why
                         : span.by === 'translation' ? ' \u2014 by the ' + what + ' translated on its own' : '');
  return g;
}

// What a chunk's answer is kept under: its number, and its word line with it
// -- the same text divided otherwise is other words and another answer.
function dictKey(n) {
  const line = lineOf(n);
  // and the whole entry, asked for with the definitions on, kept apart: a
  // word line holds no newline, so the two keys cannot meet
  return (line ? n + '\n' + line : String(n)) + (defsOn() ? '\n\nall' : '');
}

function dictInto(box, n, text) {
  const key = dictKey(n), line = lineOf(n);
  if (DICT.cache.has(key)) { dictFill(box, DICT.cache.get(key)); return; }
  box.textContent = '';
  const w = document.createElement('div');
  w.className = 'dwait'; w.textContent = 'looking it up…';
  box.appendChild(w);
  const sentence = (chunkCtx(n) || {}).sentence || '';
  pAsk('__lookup', {method: 'POST', headers: {'Content-Type': 'application/json'},
                     body: JSON.stringify(withSenses(withLine({text: text, sentence: sentence}, line)))})
    .then(r => r.json()).then(j => {
      if (!j || !j.ok) throw new Error('refused');
      j.text = text; j.sentence = sentence; j.key = key; j.line = line;
      DICT.cache.set(key, j);
      // the cloud was placed at the size of "looking it up…" (placeCloud)
      if (cloudC === n) { dictFill(box, j); refitCloud(box); }
    }).catch(() => {
      w.textContent = 'the dictionary could not be reached';
      refitCloud(box);
    });
}

/* ---------- what the page knows and the server does not -------------------
   The sentence a chunk sits in.  The dictionary is looked up one chunk at a
   time, but which sense of a word is wanted depends on the sentence around
   it, and only the page knows which rows make up that sentence.  It was
   called suggCtx when the model wanted its neighbours too; the dictionary
   only ever wanted this. */
function chunkCtx(n) {
  const row = rowOf(n), sub = row ? row.closest('.sub') : null;
  const out = {sentence: ''};
  if (!sub) return out;
  const rows = [...sub.querySelectorAll('.pass.p2 .row')];
  const sep = LANG.word_sep === '' ? '' : ' ';
  out.sentence = rows.map(r => (SRC[+r.dataset.c] || [])[1] || '').join(sep);
  return out;
}

// Three real neighbouring sentences on either side.  A book sentence is one
// `.sub`, the same unit chunkCtx and the local translation model use.
function chunkContextWindow(n) {
  const row = rowOf(n), sub = row ? row.closest('.sub') : null;
  const out = {before: [], after: []};
  if (!sub) return out;
  const at = +sub.dataset.s;
  for (let d = 1; d <= 3; d++) {
    const prev = document.querySelector('.sub[data-s="' + (at - d) + '"]');
    const next = document.querySelector('.sub[data-s="' + (at + d) + '"]');
    const p = prev ? subSentence(prev).trim() : '';
    const q = next ? subSentence(next).trim() : '';
    if (p) out.before.unshift(p);
    if (q) out.after.push(q);
  }
  return out;
}

/* The sentences of the subparagraphs around the reading place, so the model
   can be given them all at once.  A sentence is the unit that translates:
   a chunk on its own is a fragment, and `مثل ایران با هم` came back "The
   parable of Iran with Hem" where the sentence holding it came back sense. */
function subSentence(sub) {
  const rows = [...sub.querySelectorAll('.pass.p2 .row')];
  const sep = LANG.word_sep === '' ? '' : ' ';
  return rows.map(r => (SRC[+r.dataset.c] || [])[1] || '').join(sep);
}

/* ---------- preparing what you are about to read -------------------------
   While nothing else is being asked, the chunks of the next AHEAD sentences
   that nobody has glossed are looked up and cached, so by the time the
   reader reaches them the panel opens with the answer already in it.

   Three rules, and every one is about not being in the way:

     ONE AT A TIME.  Firing ten would queue them and make the one the reader
     is waiting on the last to arrive.
     THE READER GOES FIRST.  A cloud open is a reader, and the lookup they
     asked for must not sit behind ten they did not.
     ONLY WHEN IDLE.  A moment's quiet after the last scroll, keypress or
     click.  Somebody paging through a chapter is not reading it.

   Every request is one local SQLite read, so this costs nothing but a little
   idle time. */
const PRE = {queue: [], busy: false, at: 0, timer: null, touched: Date.now()};
for (const ev of ['pointerdown', 'keydown', 'wheel', 'scroll', 'touchstart'])
  addEventListener(ev, () => { PRE.touched = Date.now(); }, {passive: true});

function subOfRow(row) {
  const sub = row.closest('.sub');
  return sub ? +sub.dataset.s : -1;
}
// the chunks nobody has glossed in the next AHEAD sentences
function aheadChunks() {
  // from the reading place, or from whatever is at the top of the screen
  let from = (typeof cur === 'number' && cur >= 0) ? cur : 0;
  const seen = document.querySelector('.sub.on-air');
  if (!seen) {
    for (const sub of $$('.sub')) {
      const r = sub.getBoundingClientRect();
      if (r.bottom > 0) { from = +sub.dataset.s; break; }
    }
  }
  const out = [];
  for (let sN = from; sN < from + AHEAD; sN++) {
    const sub = document.querySelector('.sub[data-s="' + sN + '"]');
    if (!sub) continue;
    for (const row of sub.querySelectorAll('.pass.p2 .row')) {
      if (row.querySelector('.voc')) continue;      // somebody wrote this one
      const n = +row.dataset.c;
      if (!Number.isNaN(n)) out.push(n);
    }
  }
  return out;
}
function preTargets() {
  if (!(DICT.ready && DICT.on)) return [];
  return aheadChunks().filter(n => !DICT.cache.has(dictKey(n))).map(n => ({n: n}));
}
/* THE DEFINITIONS AHEAD, where they are read in the glosses' language: the
   ones the chunks ahead open with, all in one call once their lookups are
   in.  A failure stops it; the panel still asks, and says why. */
function preDefinitions() {
  if (!defsTranslated() || DEFT_FAILED) return null;
  const want = [];
  for (const n of aheadChunks()) {
    const j = DICT.cache.get(dictKey(n));
    for (const w of (j && j.words) || [])
      for (const h of w.hits || [])
        for (const s of (h.senses || []).slice(0, DEFS_SHOWN))
          if (!DEFT.has(s) && want.indexOf(s) < 0) want.push(s);
    if (want.length >= 60) break;
  }
  if (!want.length) return null;
  return ParsehMT.translate(LANG.code, GLOSS.code, want).then(got => {
    want.forEach((s, k) => DEFT.set(s, got[k] || ''));
    deftTrim();
  }).catch(() => { DEFT_FAILED = true; });
}
function preOne(t) {
  const key = dictKey(t.n), src = SRC[t.n] || [];
  const text = src[1] || '', line = lineOf(t.n);
  if (!text) return Promise.resolve();
  const ctx = chunkCtx(t.n);
  const post = (where, body) => fetch(where, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)}).then(r => r.json());
  return post('__lookup', withSenses(withLine({text: text, sentence: ctx.sentence}, line)))
           .then(j => { if (j && j.ok) {
             j.text = text; j.sentence = ctx.sentence; j.key = key; j.line = line;
             DICT.cache.set(key, j); } })
           .catch(() => {});
}
/* THE SENTENCES AHEAD, ALL IN ONE CALL.  The engine's cost is almost all
   fixed -- ten Persian sentences came back in 74 ms against 30 ms for one --
   so the next AHEAD sentences are handed over together and the panel opens
   with the reading already done.  Only the sentences that hold a chunk
   nobody has glossed: a finished page asks for nothing. */
function preSentences() {
  // ONLY WHILE THE SWITCH IS ON.  The reading ahead is for somebody who has
  // asked to be helped; with the switch off the page should cost what it has
  // always cost.
  if (!MT.ready || !DICT.on || typeof ParsehMT === 'undefined') return null;
  let from = (typeof cur === 'number' && cur >= 0) ? cur : 0;
  const seen = document.querySelector('.sub.on-air');
  if (!seen) {
    for (const sub of $$('.sub')) {
      const r = sub.getBoundingClientRect();
      if (r.bottom > 0) { from = +sub.dataset.s; break; }
    }
  }
  const want = [];
  for (let sN = from; sN < from + AHEAD; sN++) {
    const sub = document.querySelector('.sub[data-s="' + sN + '"]');
    if (!sub) continue;
    const rows = [...sub.querySelectorAll('.pass.p2 .row')];
    if (!rows.some(r => !r.querySelector('.voc'))) continue;   // all written
    const sentence = subSentence(sub);
    if (sentence && !MT.sent.has(sentence) && want.indexOf(sentence) < 0)
      want.push(sentence);
  }
  if (!want.length) return null;
  return ParsehMT.translate(LANG.code, GLOSS.code, want).then(got => {
    want.forEach((sentence, k) => MT.sent.set(sentence, got[k] || ''));
    mtTrim();
  }).catch(() => {});
}

/* Bounded, because a long book would otherwise keep every sentence it has
   walked past.  The oldest go first; Map keeps insertion order. */
function mtTrim() {
  for (const m of [MT.sent, MT.probe])
    while (m.size > MT_KEEP) m.delete(m.keys().next().value);
}

function prePump() {
  if (PRE.busy || cloudFor) return;                 // a cloud open is a reader
  if (Date.now() - PRE.touched < 1500) return;      // still moving about
  // the model first: one call covers ten sentences, and it is what the panel
  // shows at the top
  const batch = preSentences();
  if (batch) {
    PRE.busy = true;
    batch.then(() => { PRE.busy = false; }, () => { PRE.busy = false; });
    return;
  }
  if (!PRE.queue.length) PRE.queue = preTargets();
  const t = PRE.queue.shift();
  if (!t) {
    // every lookup ahead is in: what their definitions say, in one call
    const defs = preDefinitions();
    if (defs) { PRE.busy = true; defs.then(() => { PRE.busy = false; }, () => { PRE.busy = false; }); }
    return;
  }
  PRE.busy = true;
  preOne(t).then(() => { PRE.busy = false; }, () => { PRE.busy = false; });
}
function preStart() {
  if (PRE.timer) return;
  PRE.timer = setInterval(prePump, 900);
}


/* THE CLOUD IS PLACED AGAIN WHEN ITS PANEL FILLS.  It opens at once,
   holding "looking it up…", and is placed at that size; the answer lands a
   round trip later and the cloud grows -- downwards, since its top is what
   was set.  Measured at 1280x800 on the fixture's first unglossed chunk:
   with its row at 685-721 the cloud opened above it at 545-675, 130px tall,
   and filled it was 455px tall at 545-1000 -- lying over the very chunk it
   was about, and 200px of it under the window's bottom edge; with the row
   at 205-241 it grew down over the chunk the same way.  Nor was a cloud
   whose answer was already cached safe: the rule never looked at the
   bottom edge, so at 445-481, too tall for the 427px above (455), it flipped
   below and ran to 946.  So when an answer lands -- the dictionary's, and
   the model's reading after it, which grows the cloud a second time
   (refitCloud) -- it is placed again:
     . on the SIDE IT OPENED ON, with its edge nearest the chunk where it
       was -- the pointer is on its way across that edge into it, and a
       cloud that jumped to the chunk's other side would close under it;
     . with the panel, the one part of the cloud that scrolls, cut to the
       room that side has, so the cloud stays inside the window;
     . and on the other side only when its own would leave the panel a slit
       (less than PANEL_LEAST).
   A cloud that opens with its answer already in hand -- cached, or with no
   panel at all -- is placed by the same rules less the first: above the
   chunk when it fits there, below when it fits there, and otherwise on the
   side that holds it with its panel cut. */
// the panel's least useful height, in px: its head, the first word, that
// word's first hit and sense, and the start of the next -- the fixture's
// مِثلِ has its first hit end 91px down the panel and its second at 128
const PANEL_LEAST = 120;
function placeCloud(target, again) {
  const r = target.getBoundingClientRect();
  // the side it is on now, before the measuring below forgets it
  const was = cloud.classList.contains('below');
  cloud.hidden = false;
  cloud.classList.remove('below');
  const panel = cloud.querySelector('.dict');
  if (panel) panel.style.maxHeight = '';
  // the PREVIOUS placement's inline left still constrains the shrink-to-fit
  // width; measure from a neutral position or the cloud comes out squeezed
  cloud.style.left = '8px'; cloud.style.top = '-9999px';
  const vw = document.documentElement.clientWidth || innerWidth;
  const vh = document.documentElement.clientHeight || innerHeight;
  const cw = cloud.offsetWidth;
  let chh = cloud.offsetHeight;
  const up = r.top - 18, down = vh - r.bottom - 18;
  // the least the cloud can be made, its panel cut but not below a slit
  const least = chh - (panel ? Math.max(0, panel.offsetHeight - PANEL_LEAST) : 0);
  // open towards the top of the page, and below only when the chunk hugs
  // the top of the viewport so that the cloud would bury it; placed again,
  // it stays on the side it is on
  let below;
  if (again && least <= (was ? down : up)) below = was;
  else if (chh <= up) below = false;
  else if (chh <= down) below = true;
  else if (least <= up) below = false;
  else if (least <= down) below = true;
  else below = down > up;
  const room = below ? down : up;
  if (panel && chh > room) {
    const h = panel.offsetHeight;
    panel.style.maxHeight = Math.max(Math.min(PANEL_LEAST / 2, h), h - (chh - room)) + 'px';
    chh = cloud.offsetHeight;
  }
  // a window too short for it on either side: inside the window, over the
  // chunk, rather than beside the chunk and out of reach
  const top = Math.max(8, Math.min(below ? r.bottom + 10 : r.top - chh - 10, vh - chh - 8));
  if (below) cloud.classList.add('below');
  const left = Math.min(Math.max(8, r.left + r.width / 2 - cw / 2),
                        vw - cw - 8);
  cloud.style.top = top + 'px';
  cloud.style.left = left + 'px';
  const ar = cloud.querySelector('.arrow');
  if (ar) ar.style.left = Math.min(Math.max(10, r.left + r.width / 2 - left - 5),
                                   cw - 20) + 'px';
}
// Something has just landed in the cloud (`el` is where): place it again,
// if it is still this cloud's -- an answer for a cloud since moved on lands
// in a box nobody shows, and must not move the one that is shown.
function refitCloud(el) {
  if (cloudFor && !cloud.hidden && cloud.contains(el)) placeCloud(cloudFor, true);
}
function openCloud(span) {
  if (cloudFor === span) { clearTimeout(hideTimer); return; }
  clearTimeout(hideTimer);
  if (cloudFor) cloudFor.classList.remove('hot');
  cloudFor = span; span.classList.add('hot');
  // the number may be on the span (a pass-1 word) or on the row around it
  // (a pass-2 text column, which is what an unglossed chunk is clicked on)
  const holder = span.dataset.c !== undefined ? span : span.closest('[data-c]');
  cloudC = holder ? +holder.dataset.c : -1;
  fillCloud(chunkData(cloudC) || { fa: '', kana: '', tr: '', en: '', voc: '', vocEl: null });
  placeCloud(span);
}
function closeCloud() {
  if (cloudFor) cloudFor.classList.remove('hot');
  cloudFor = null; cloudC = -1; cloud.hidden = true;
}
function scheduleClose() {
  clearTimeout(hideTimer);
  hideTimer = setTimeout(closeCloud, 120);
}
cloud.addEventListener('mouseenter', () => clearTimeout(hideTimer));
cloud.addEventListener('mouseleave', scheduleClose);
cloud.addEventListener('click', e => {
  if (!e.target.classList || cloudC < 0) return;
  if (e.target.classList.contains('mkedit')) {
    const n = cloudC, from = cloudFor;        // closeCloud() clears both
    openChunk(n, from);
    return;
  }
  if (e.target.classList.contains('mkcopy')) {
    const d = chunkData(cloudC);
    if (d) Parseh.copy(d.fa);
    return;
  }
  if (e.target.classList.contains('mkcard')) {
    const n = cloudC, from = cloudFor;       // closeCloud() clears both
    const d = chunkData(n);
    openAnki(d ? d.fa : '', n, from);
  }
});

/* ---------- shift-click: copy ---------------------------------------------
   A plain click plays and a modifier-click makes a card, so copying takes a
   held shift: the chunk under the cursor (the hoverable unit, in whichever
   pass), a pass-2 row's Persian, or the whole pass -- the sentence -- when
   the click lands beside a chunk.  Capture phase, and it stops right here,
   so neither the play-click nor the tap-for-gloss ever sees it.           */
document.addEventListener('click', e => {
  if (!e.shiftKey || e.altKey || e.ctrlKey || e.metaKey) return;
  if (!e.target.closest) return;
  if (e.target.closest('button,input,select,textarea,a,#cloud,#anki,#tocwrap')) return;
  const sub = e.target.closest('.sub');
  if (!sub) return;
  e.preventDefault(); e.stopImmediatePropagation();
  let unit = e.target.closest('.w, .row .fa');
  if (!unit) { const row = e.target.closest('.row'); if (row) unit = row.querySelector('.fa'); }
  if (!unit) unit = e.target.closest('.pass');
  const text = textOf(unit || sub.querySelector('.p1'));
  Parseh.copy(text);
}, true);
// ... and the shift-click must not start a text selection of its own
document.addEventListener('mousedown', e => {
  if (e.shiftKey && !(e.altKey || e.ctrlKey || e.metaKey) && e.target.closest &&
      e.target.closest('.sub') && !e.target.closest('input,textarea,button'))
    e.preventDefault();
});

// hover, delegated: the page holds thousands of chunks, so the listeners sit
// on the document rather than on every span
document.addEventListener('mouseover', e => {
  if (!hoverPointer() || !document.body.classList.contains('hovermode')) return;
  const w = e.target.closest ? e.target.closest('.p1 .w') : null;
  if (w) openCloud(w);
});
document.addEventListener('mouseout', e => {
  if (!cloudFor) return;
  const w = e.target.closest ? e.target.closest('.p1 .w') : null;
  if (w !== cloudFor) return;
  const to = e.relatedTarget;
  if (to && (cloudFor.contains(to) || cloud.contains(to))) return;
  scheduleClose();
});

/* ---------- anki cards ----------------------------------------------------
   Alt-click (or ctrl-click) any word -- in pass 1 or in a pass-2 row -- and
   the dashboard opens with that word; the "+ card" button in a gloss
   cloud does the same for the whole chunk.  Anki cards are saved into the
   SAME decks as the video player's (youtube/anki/), via the same endpoints;
   the sheet can send the card to an exercise deck, or copy it as markdown,
   instead (the card sheet, below).                                          */
// Opening and closing punctuation of any of the scripts, off the ends of a
// word -- and, in openAnki, off the chunk the word is compared with.  The
// ASCII comma, semicolon and question mark are here for the Latin-script
// languages: Persian and Arabic write ، ؛ ؟ instead, so before they were
// added a card cut from "Comment ça va ?" or "Ciao, bello" kept the
// punctuation on its front.  “ is in both halves on purpose -- it opens a
// quotation in English and Italian and closes one in German („Wort“) --
// and the apostrophe is in neither, because Italian's "po'" and Turkish's
// "İstanbul'da" wear it as part of the word.
const trimPunct = s => s.replace(/^[«"(「『（„“‹]+|[»".,;:?!،؛؟)」』、。！？）”“›…]+$/g, '') || s;
// capture phase, and registered before the tap-for-gloss listener below, so
// a modifier-click always means "card" and never reaches the play-on-click
// handler
document.addEventListener('click', e => {
  if (!(e.altKey || e.ctrlKey || e.metaKey)) return;
  const wd = e.target.closest ? e.target.closest('.wd') : null;
  if (!wd) return;
  const holder = wd.closest('[data-c]');
  if (!holder) return;
  // stopImmediatePropagation, not stopPropagation: the tap-for-gloss
  // listener below sits on the SAME node and would otherwise still run
  e.preventDefault(); e.stopImmediatePropagation();
  const n = +holder.dataset.c;
  // A WORD THE CHUNK'S LINE DREW: the card is that word, with the reading
  // the line gives it -- read off the word's own token (data-w), which is
  // the word on the page even where SRC has moved on (a repaint that failed)
  // -- and its place in that line (data-k), which is where in the sentence
  // the cut editor looks for it
  const said = wd.dataset.w !== undefined && (linePairs(wd.dataset.w) || [])[0];
  if (said) {
    openAnki(said[0], n, holder, said[1], {k: +wd.dataset.k, line: true});
    return;
  }
  // the same word, but vowelled: passes 3 and 4 show the bare form, and a
  // card wants the pass-1 form -- the chunks split into the same words
  // -- and a language without word separators has one word per chunk
  const k = [...holder.querySelectorAll('.wd')].indexOf(wd);
  const d = chunkData(n);
  let word = (d && k >= 0 && (LANG.word_sep ? d.fa.split(' ')[k] : d.fa)) || wd.textContent;
  word = trimPunct(word);
  openAnki(word, n, holder, undefined, LANG.word_sep && k >= 0 ? {k: k} : null);
}, true);

// a touch screen has no hover, so in hover mode a tap on a chunk opens its
// gloss instead of playing the subparagraph (capture, to pre-empt play)
document.addEventListener('click', e => {
  if (hoverPointer() || !document.body.classList.contains('hovermode')) return;
  const w = e.target.closest ? e.target.closest('.p1 .w') : null;
  if (!w) return;
  e.stopPropagation();
  if (cloudFor === w) closeCloud(); else openCloud(w);
}, true);

/* ---------- a click on a chunk nobody has glossed -------------------------
   The cloud is a hover-mode thing, and an unglossed chunk is exactly the one
   a reader cannot hover for: pass 2 shows its text with an empty column
   beside it.  So while the panel is switched on, clicking such a chunk
   opens the cloud on it in whatever mode the reader is in.  A chunk that HAS
   a vocabulary line is left alone -- the click still plays the subparagraph,
   as it always did.                                                        */
document.addEventListener('click', e => {
  if (!((DICT.ready || MT.ready) && DICT.on)) return;
  if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
  if (!e.target.closest) return;
  if (e.target.closest('button,input,select,textarea,a,#cloud,#anki,#tocwrap')) return;
  const row = e.target.closest('.row');
  if (!row || row.querySelector('.gl .voc')) return;
  const fa = row.querySelector('.fa');
  if (!fa) return;
  e.stopPropagation(); e.preventDefault();
  if (cloudFor === fa) closeCloud(); else openCloud(fa);
}, true);

// a click that lands outside both the cloud and a chunk closes the cloud
document.addEventListener('click', e => {
  if (!cloud.hidden && !cloud.contains(e.target) &&
      !(e.target.closest && e.target.closest('.p1 .w'))) closeCloud();
});

// while a modifier is down, the word under the cursor lights up
document.addEventListener('keydown', e => {
  if (e.altKey || e.ctrlKey || e.metaKey) document.body.classList.add('altdown');
});
document.addEventListener('keyup', e => {
  if (!e.altKey && !e.ctrlKey && !e.metaKey) document.body.classList.remove('altdown');
});
addEventListener('blur', () => document.body.classList.remove('altdown'));

/* ---------- the card sheet ------------------------------------------------
   One sheet, and three places the card it makes can go -- the last one
   picked is kept (bk_card_target):
     Anki           a note in the Anki store (youtube/anki/), as the sheet has
                    always made, built into an .apkg
     exercise deck  an exercise in one of the toolbox's exercise decks
                    (/exercises), which remembers this subparagraph and links
                    back to it from the deck's page
     markdown       a :::exercise flashcard block on the clipboard, for a
                    studio document or a deck's Add exercise
   The last two are written by the card kit (lib/cardkit.js,
   ParsehCards.markdown), and can be a jolly card as well.  Any of the three
   can carry a RECORDING: the stretch of the narration the word is heard in,
   cut by ear in the kit's cut editor, kept in the clip tray (clips/) and put
   on one side of the card.                                                  */
const AN = {
  back: $('#ankiback'), box: $('#anki'), ref: $('#aref'), title: $('#ahtitle'),
  deckRow: $('#adeckrow'), deck: $('#adeck'), deckNew: $('#adecknew'),
  fa: $('#afa'), kana: $('#akana'), tr: $('#atr'), en: $('#aen'), ctx: $('#actx'),
  notes: $('#anotes'), tags: $('#atags'), src: $('#asrc'),
  opp: $('#aopp'), oppTr: $('#aopptr'), oppKana: $('#aoppkana'),
  jfp: $('#ajfp'), jfs: $('#ajfs'), jbp: $('#ajbp'), jbs: $('#ajbs'),
  snd: $('#asnd'), sndPrev: $('#asndprev'), sndAudio: $('#asndaudio'), sndName: $('#asndname'),
  saveLab: $('#asavelab'), stat: $('#astat')
};
let ankiWasPlaying = false, ankiTime = 0, ankiPara = '', decksCache = [], exDecksCache = [];
// What the sheet was opened for, which is where the cut editor looks for the
// word: the chunk n, the subparagraph i it is in with its first and last
// chunk, and -- for one word out of the chunk -- that word's index among the
// chunk's words (k), counted in the chunk's word line when `line`.
let ankiAt = null;
// EVERY OPENING OF THE SHEET IS ITS OWN.  sheetSeq counts them, and whatever
// answers later -- a save, an add, a copy, the cut editor -- asks whether the
// sheet that asked is still the one open before it touches it.  closeTimer is
// the sheet closing itself after a save; cutting, how many cut editors are
// open over it (one: it is modal).
let sheetSeq = 0, closeTimer = 0, cutting = 0;
// "vocab" (the default) or "opposites" -- the second asks "what is the
// opposite of X?", and its answer side is written by hand right here --
// or, for an exercise deck and markdown, "jolly": four fields of your own
let ankiKind = 'vocab';
// which cards the note makes: 'both', 'forward' (fa->en only) or
// 'reverse' (en->fa only; vocab only -- the opposites note type has no
// ReverseOnly field, so the option is hidden there)
let ankiDir = 'both';
function setDir(d) {
  ankiDir = d;
  document.querySelectorAll('#adir .dbtn').forEach(b =>
    b.classList.toggle('on', b.dataset.dir === d));
}
document.querySelectorAll('#adir .dbtn').forEach(b => {
  b.onclick = () => setDir(b.dataset.dir);
});

// ---- where the card goes
const CARD_TO = {
  anki: {btn: '#atanki', title: 'anki card', save: 'save card',
         preview: 'how the finished card will look in Anki, both directions',
         note: 'rendered with the very templates and styles the .apkg carries — ' +
               'the line is where Anki flips to the answer'},
  deck: {btn: '#atdeck', title: 'exercise card', save: 'add to deck',
         preview: 'how the card will look in the exercise deck',
         note: 'drawn by the studio, as the deck’s page draws it — click the card to turn it'},
  md: {btn: '#atmd', title: 'card markdown', save: 'copy markdown',
       preview: 'how the card will look in a studio document or a deck',
       note: 'drawn by the studio, as a document and a deck draw it — click the card to turn it'}
};
let cardTo = localStorage.getItem('bk_card_target');
if (!CARD_TO[cardTo]) cardTo = 'anki';
const KIT_GONE = 'the card kit (lib/cardkit.js) did not load: reload the page';
// the name typed for a new deck, per destination: an Anki name nests with
// ::, an exercise deck's does not, and neither is the other's deck
const newDeckNames = {anki: '', deck: ''};
function setTarget(t) {
  if (!CARD_TO[t]) t = 'anki';
  if (cardTo !== 'md') newDeckNames[cardTo] = AN.deckNew.value;
  if (t !== 'md') AN.deckNew.value = newDeckNames[t];
  cardTo = t;
  localStorage.setItem('bk_card_target', t);
  Object.keys(CARD_TO).forEach(k => {
    const b = $(CARD_TO[k].btn);
    b.classList.toggle('on', k === t);
    b.setAttribute('aria-pressed', k === t ? 'true' : 'false');
  });
  AN.title.textContent = CARD_TO[t].title;
  AN.saveLab.textContent = CARD_TO[t].save;
  dupArmed = false;
  $('#apreview').title = CARD_TO[t].preview;
  $('#apvnote').textContent = CARD_TO[t].note;
  $('#apvrow').hidden = true;
  $('#amdrow').hidden = true;
  $('#akjolly').hidden = t === 'anki';
  // the direction, per destination: Anki's "both" is two cards; an exercise
  // asks both sides once (repeat) or draws one each time it is shown (random)
  const dir = $('#adir').dataset, both = $('#adirboth');
  $('#adirrnd').hidden = t === 'anki';
  if (t === 'anki' && ankiDir === 'both-random') setDir('both');
  both.textContent = both.textContent.replace(/ both.*/, t === 'anki' ? ' both' : ' both (repeat)');
  both.title = t === 'anki'
    ? 'two cards: ' + dir.from + ' \u2192 ' + dir.to + ' and ' + dir.to + ' \u2192 ' + dir.from
    : 'both (repeat): shown ' + dir.from + ' first, and in a deck two linked cards, one asked from each side';
  AN.deckRow.hidden = t === 'md';
  $('#abuild').hidden = t !== 'anki';
  // a jolly card is not a note Anki has: back to vocabulary there
  setKind(t === 'anki' && ankiKind === 'jolly' ? 'vocab' : ankiKind, true);
  AN.stat.textContent = t !== 'anki' && !window.ParsehCards ? KIT_GONE : '';
  loadDecks();
}
Object.keys(CARD_TO).forEach(k => {
  $(CARD_TO[k].btn).onclick = () => { if (k !== cardTo) setTarget(k); };
});

function setKind(k, quiet) {
  if (k === 'jolly' && cardTo === 'anki') k = 'vocab';
  // a jolly card is another card altogether: a preview of the other is gone
  if ((k === 'jolly') !== (ankiKind === 'jolly')) $('#apvrow').hidden = true;
  const was = ankiKind;
  ankiKind = k;
  const opp = k === 'opposites', jolly = k === 'jolly';
  $('#akvocab').classList.toggle('on', k === 'vocab');
  $('#akopp').classList.toggle('on', opp);
  $('#akjolly').classList.toggle('on', jolly);
  $('#aenrow').hidden = opp || jolly;
  $('#actxrow').hidden = opp || jolly;
  $('#aopprow').hidden = !opp;
  $('#adirrev').hidden = opp;
  // a jolly card is its four fields and nothing else, so the word's rows
  // step aside -- what they held is what the four start from (fillJolly)
  ['#afarow', '#atrrow', '#anotesrow', '#asrcrow', '#adirrow'].forEach(s => { $(s).hidden = jolly; });
  $('#akanarow').hidden = jolly || !LANG.reading;
  // tags are Anki's: an exercise has none
  $('#atagsrow').hidden = jolly || cardTo !== 'anki';
  $('#ajollyrow').hidden = !jolly;
  // the sides are named once, on #adir, and read back here rather than
  // spelt a second time: an opposites card runs between two words of the
  // language instead, so it names its own two sides
  const side = $('#adir').dataset;
  $('#adirfwd').textContent = opp
    ? '\u2192 word \u2192 opposite'
    : '\u2192 ' + side.from + ' \u2192 ' + side.to;
  if (opp && ankiDir === 'reverse') setDir('both');
  if (jolly && was !== 'jolly') {
    fillJolly();
    // a recording cut before jolly was picked goes where one cut now would:
    // into the box the cursor was last in, the back's main text when none
    // has been -- the side it was put on is a vocabulary card's, and jolly
    // has no sides.  Once: a line taken out by hand stays out
    offerClip();
  }
  sndSides();
  if (!quiet && opp && !AN.opp.value) AN.opp.focus();
}
$('#akvocab').onclick = () => setKind('vocab');
$('#akopp').onclick = () => setKind('opposites');
$('#akjolly').onclick = () => setKind('jolly');

// A deck belongs to a language and a card goes to the deck of its own
// language (the store refiles it if not), so this book's language comes
// first, under its own heading; the other languages' decks are still
// listed, each under its own, so an existing deck is never invisible --
// picking one just means the card lands in the deck of THIS language with
// that name, and the save says so.  The option value is "<folder>/<slug>":
// a slug alone no longer names one deck.
function deckOptions(list) {
  decksCache = list;
  const pick = deckChoice('anki', list.map(d => d.folder + '/' + d.slug),
                          localStorage.getItem('bk_deck') || '');
  AN.deck.innerHTML = '';
  AN.deck.dataset.of = 'anki';
  const groups = {}, order = [];
  list.forEach(d => {
    if (!groups[d.lang]) { groups[d.lang] = []; order.push(d.lang); }
    groups[d.lang].push(d);
  });
  order.sort((a, b) => (a === LANG.code ? 0 : 1) - (b === LANG.code ? 0 : 1));
  order.forEach(code => {
    const g = document.createElement('optgroup');
    g.label = groups[code][0].language +
              (code === LANG.code ? '' : ' (another language)');
    groups[code].forEach(d => {
      const o = document.createElement('option');
      o.value = d.folder + '/' + d.slug;
      o.textContent = d.name + ' (' + d.cards + ' card' + (d.cards === 1 ? '' : 's') + ')';
      if (o.value === pick) o.selected = true;
      g.appendChild(o);
    });
    AN.deck.appendChild(g);
  });
  const o = document.createElement('option');
  o.value = ''; o.textContent = '+ new deck…';
  if (!list.length || pick === '') o.selected = true;
  AN.deck.appendChild(o);
  deckPick();
}
// An exercise deck is of one language and reads its exercises in it, so
// only this book's language's decks are offered; the option value is the
// deck's path, "<folder>/<slug>", as the exercise decks' own routes name it.
function exDeckOptions(list) {
  exDecksCache = list;
  const pick = deckChoice('deck', list.map(d => d.path), localStorage.getItem('bk_exdeck') || '');
  AN.deck.innerHTML = '';
  AN.deck.dataset.of = 'deck';
  list.forEach(d => {
    const o = document.createElement('option'), n = (d.counts && d.counts.total) || 0;
    o.value = d.path;
    o.textContent = d.name + ' (' + n + ' exercise' + (n === 1 ? '' : 's') + ')';
    if (o.value === pick) o.selected = true;
    AN.deck.appendChild(o);
  });
  const o = document.createElement('option');
  o.value = ''; o.textContent = '+ new deck…';
  if (!list.length || pick === '') o.selected = true;
  AN.deck.appendChild(o);
  deckPick();
}
/* THE CHOICE ON THE SCREEN OUTLIVES A NEW LIST.  The options are drawn again
   whenever the decks are listed anew, and the answer can come after the
   owner has already picked -- "+ new deck…" with its name being typed, or
   another deck.  Drawn from the deck used last, that pick would be undone
   and the card go where it was not sent.  So once the owner has picked (the
   select's own change), a list for the same destination keeps the pick while
   it is still one of the options; a card gone somewhere (the deck used last
   is written) hands the choice back to the deck used last.  Returns the
   value to select: '' is "+ new deck…", a path no option has selects none. */
let deckPicked = false;
function deckChoice(kind, values, last) {
  if (deckPicked && AN.deck.dataset.of === kind && AN.deck.options.length) {
    const shown = AN.deck.value;
    if (shown === '' || values.includes(shown)) return shown;
  }
  return last && values.includes(last) ? last : (values.length ? null : '');
}
function deckPick() {
  AN.deckNew.hidden = AN.deck.value !== '';
  if (!AN.deckNew.hidden && !AN.deckNew.value) AN.deckNew.focus();
}
AN.deck.addEventListener('change', () => { deckPicked = true; deckPick(); });
// each answer is for the destination it was asked for: one picked since is
// not filled with the other's decks
let decksAsk = 0;
function loadDecks() {
  const n = ++decksAsk;
  if (AN.deck.dataset.of && AN.deck.dataset.of !== cardTo) {
    AN.deck.innerHTML = ''; AN.deck.dataset.of = '';
  }
  if (cardTo === 'anki') {
    // the deck-name hint suggests a name nested under THIS book's language,
    // since that is where a card made here will be filed
    AN.deckNew.placeholder = 'name the new deck (use :: to nest, e.g. ' + LANG.name + '::Books)';
    fetch('/anki/decks', { cache: 'no-store' })
      .then(r => r.json()).then(list => { if (n === decksAsk) deckOptions(list); })
      .catch(() => { if (n === decksAsk) deckOptions(decksCache); });
  } else if (cardTo === 'deck') {
    AN.deckNew.placeholder = 'name the new exercise deck';
    if (!window.ParsehCards) { exDeckOptions(exDecksCache); AN.stat.textContent = KIT_GONE; return; }
    ParsehCards.decks(LANG.code).then(list => { if (n === decksAsk) exDeckOptions(list); }, err => {
      if (n !== decksAsk) return;
      exDeckOptions(exDecksCache);
      AN.stat.textContent = 'the exercise decks could not be listed: ' + err.message;
    });
  }
}

// ---- the jolly card's four fields
// Filled from the card being made when jolly is picked -- the word (marked
// as the target's in a Latin-script language, which has no other way to say
// which words are), its reading and transliteration under it, the meaning on
// the back with the sentence under that -- and never again once somebody has
// written in them.  A recording goes in as a line of its own in the box the
// cursor was last in (lastJolly: focused, typed in or not), after the line
// the cursor was on; before any box has had the cursor, at the end of the
// back's main text.
let jollyEdited = false, lastJolly = null;
const JOLLY = [AN.jfp, AN.jfs, AN.jbp, AN.jbs];
JOLLY.forEach(ta => {
  ta.addEventListener('focus', () => { lastJolly = ta; });
  ta.addEventListener('input', () => { jollyEdited = true; });
});
function fillJolly() {
  if (jollyEdited) return;
  const word = AN.fa.value.trim();
  AN.jfp.value = word && LANG.script === 'latin' ? '[' + word.replace(/[\[\]]/g, '') + ']{tl}' : word;
  AN.jfs.value = [AN.kana.value.trim(), AN.tr.value.trim()].filter(Boolean).join(' · ');
  AN.jbp.value = AN.en.value.trim();
  AN.jbs.value = AN.ctx.value.trim();
  // written anew, so the recording is offered anew
  clipOffered = false;
}
// `line` on a line of its own, after the line the caret was last on (at the
// end when the box has not had the caret)
function putLine(ta, line, atCaret) {
  const v = ta.value;
  let at = atCaret && ta === lastJolly ? ta.selectionEnd : v.length;
  if (!(at >= 0 && at <= v.length)) at = v.length;
  const nl = v.indexOf('\n', at);
  at = nl < 0 ? v.length : nl;
  const head = v.slice(0, at), put = (head && !head.endsWith('\n') ? '\n' : '') + line;
  ta.value = head + put + v.slice(at);
  ta.selectionStart = ta.selectionEnd = at + put.length;
}

// ---- the recording
// ankiClip is the tray's record of the clip on the card.  A clip nobody used
// -- taken off again, replaced, or left on a sheet that was closed -- goes
// out of the tray, as the cut editor's own cancel does.  Two kinds are kept
// whatever happens to the sheet: a clip that went onto a card (saved, added,
// or copied as markdown: clipsUsed), and one a press has carried out and
// not yet had its answer for (clipsOut, a count per name) -- closing the
// sheet the moment after "add to deck" must not take out of the tray the
// recording the deck is about to fetch from it.
// clipOffered: its line was put in the jolly fields once, and is not put
// back if the person takes it out again (the card then goes without it)
let ankiClip = null, clipOffered = false;
const clipsUsed = new Set(), clipsOut = new Map();
const clipPath = c => c.path || 'audio/' + c.name;
const clipLine = c => '![](' + clipPath(c) + ')';
function offerClip() {
  if (!ankiClip || clipOffered) return;
  clipOffered = true;
  if (!JOLLY.some(ta => ta.value.indexOf(clipPath(ankiClip)) >= 0))
    putLine(lastJolly || AN.jbp, clipLine(ankiClip), true);
}
// the lines a clip was put in on, out of the jolly fields
function unlineClip(c) {
  const ends = '](' + clipPath(c) + ')';
  JOLLY.forEach(ta => {
    const lines = ta.value.split('\n');
    const kept = lines.filter(l => !(l.trim().startsWith('![') && l.trim().endsWith(ends)));
    if (kept.length !== lines.length) ta.value = kept.join('\n');
  });
}
function forgetClip(c) {
  if (!c || clipsUsed.has(c.name) || clipsOut.has(c.name)) return;
  fetch('/clips/api/' + encodeURIComponent(c.name), { method: 'DELETE' }).catch(() => {});
}
function sndSide() {
  const r = document.querySelector('input[name=asndside]:checked');
  return r && r.value === 'back' ? 'back' : 'front';
}
// the side radios name the card's own sides; a jolly card has the clip where
// its text puts it instead
function sndSides() {
  $('#asndsides').hidden = ankiKind === 'jolly';
  document.querySelectorAll('#asndprev .ajollyinto').forEach(el => { el.hidden = ankiKind !== 'jolly'; });
  const opp = ankiKind === 'opposites', side = $('#adir').dataset;
  $('#asndfront').textContent = opp ? 'with the word' : 'on the ' + side.from + ' side';
  $('#asndback').textContent = opp ? 'with the opposite' : 'on the ' + side.to + ' side';
}
// the stripped length of a stretch of text, as timestamp.spread measures a
// subparagraph: the vowel marks off, no whitespace, a character a code point
const unitsOf = s => Array.from(stripMarks(String(s || '')).replace(/\s+/g, '')).length;
// WHERE IN THE RECORDING THE WORD IS.  Only subparagraphs have times, so the
// guess is the word's share of its sentence: the subparagraph's [t0, t1] cut
// in proportion to the text before the chunk, the words before the word
// inside it, and its own length -- ParsehCards.guess widens that a little
// either side.  {why} when there is nothing to cut.
function clipPlan() {
  if (!ankiAt) return {why: 'there is no subparagraph under this card to cut its recording from'};
  if (!window.ParsehCards) return {why: KIT_GONE};
  if (location.protocol.indexOf('http') !== 0)
    return {why: 'cutting the audio needs this page opened from the toolbox’s server'};
  const i = ankiAt.sub, t = SUBS[i], id = t && t[3];
  if (!NARRN) return {why: 'this book has no narration file to cut the audio from'};
  // times measured in a recording whose file is not here are seconds into
  // THAT file: cut from another one at them, they would be somebody else's
  if (id && !NARRBY[id])
    return {why: (ankiAt.label || 'this subparagraph') + ' was timed in the recording ' + id +
                 ', whose file is not on this machine'};
  const rec = narrFor(i), src = narrSrc(i);
  if (!rec || !src)
    return {why: 'none of this book’s recordings covers ' + (ankiAt.label || 'this subparagraph') +
                 ' yet: add one for it, or widen what one covers, under narration'};
  if (!t || t[0] == null || t[1] == null || !(t[1] > t[0]))
    return {why: 'this subparagraph has no times yet: time it (narration, or edit times) and the audio can be cut'};
  const context = [t[0], t[1]];
  const n = ankiAt.n;
  let from = ankiAt.from, to = ankiAt.to;
  if (!(from <= n && n <= to)) from = to = n;
  let units = 0, pre = 0;
  for (let c = from; c <= to; c++) {
    const u = unitsOf((SRC[c] || [])[1]);
    units += u;
    if (c < n) pre += u;
  }
  let a = pre, b = pre + unitsOf((SRC[n] || [])[1]);
  if (ankiAt.k != null) {
    const words = ankiAt.line ? (linePairs(lineOf(n)) || []).map(p => p[0])
      : String((SRC[n] || [])[1] || '').replace(/\s+/g, ' ').trim().split(LANG.word_sep || ' ');
    if (ankiAt.k < words.length) {
      a = pre + words.slice(0, ankiAt.k).reduce((s, w) => s + unitsOf(w), 0);
      b = a + unitsOf(words[ankiAt.k]);
    }
  }
  return {src: new URL(src, location.href).href, narration: rec.id, context: context,
          guess: ParsehCards.guess(context, units, a, b)};
}
function sndState() {
  const p = clipPlan();
  AN.snd.disabled = !!p.why;
  AN.snd.title = p.why || 'cut the stretch of the narration this card is heard in, by ear, and put it on the card';
  // said under the button too: a phone shows no title
  $('#asndwhy').textContent = p.why || '';
  $('#asndwhy').hidden = !p.why;
}
AN.snd.onclick = () => {
  const p = clipPlan();
  if (p.why) { AN.stat.textContent = p.why; return; }
  const word = AN.fa.value.trim(), num = AN.ref.textContent.trim(), seq = sheetSeq;
  // somebody at work in the cut editor is still making this card: the sheet
  // does not close itself under it (closeSoon)
  cutting++;
  clearTimeout(closeTimer);
  ParsehCards.cut({
    source: {kind: 'book', src: p.src, cutUrl: '__clip/cut', peaksUrl: '__clip/peaks', narration: p.narration},
    context: p.context, guess: p.guess, lang: LANG.code,
    hint: word || META.book, label: num, text: word
  }).then(clip => {
    cutting--;
    if (!clip) return;
    // a clip used for a sheet no longer open is on nobody's card
    if (ankiOpen && seq === sheetSeq) takeClip(clip); else forgetClip(clip);
  }, () => { cutting--; });
};
function takeClip(clip) {
  const old = ankiClip;
  if (old && old.name !== clip.name) {
    // the clip it replaces leaves the card, its line with it
    unlineClip(old);
    forgetClip(old);
  }
  ankiClip = clip;
  clipOffered = false;
  if (ankiKind === 'jolly') offerClip();
  AN.sndAudio.src = clip.url;
  AN.sndName.textContent = clip.name + (clip.duration != null ? ' · ' + (+clip.duration).toFixed(2) + ' s' : '');
  AN.sndPrev.hidden = false;
  dupArmed = false; AN.saveLab.textContent = CARD_TO[cardTo].save;
  AN.stat.textContent = '';
}
function dropClip(closing) {
  const c = ankiClip;
  if (!c) return;
  ankiClip = null;
  AN.sndAudio.pause(); AN.sndAudio.removeAttribute('src'); AN.sndAudio.load();
  AN.sndPrev.hidden = true;
  // and out of the jolly fields: the line it was put in on goes with it
  if (!closing) unlineClip(c);
  forgetClip(c);
}
$('#asnddel').onclick = () => { dropClip(false); unarm(); };

// `reading`, for a word of the chunk's word line: the line's own reading of
// that word; `at`, for one word out of the chunk: {k: its index among the
// chunk's words, line: counted in the word line}
function openAnki(word, n, fromEl, reading, at) {
  const d = chunkData(n) || { fa: word, kana: '', tr: '', en: '', voc: '', vocEl: null };
  const sub = fromEl && fromEl.closest ? fromEl.closest('.sub') : null;
  const num = sub ? sub.querySelector('.lab').textContent.trim() : '';
  const sent = sub ? textOf(sub.querySelector('.p1')).replace(/\s+/g, ' ').trim() : '';
  const pe = sub ? sub.closest('.para[id]') : null;
  ankiPara = pe ? pe.id : '';
  ankiTime = (sub && SUBS[+sub.dataset.s] && SUBS[+sub.dataset.s][0] != null)
    ? SUBS[+sub.dataset.s][0] : 0;
  ankiAt = sub ? {n: n, sub: +sub.dataset.s, from: +sub.dataset.from, to: +sub.dataset.to,
                  k: at && at.k >= 0 ? at.k : null, line: !!(at && at.line), label: num} : null;
  // a sheet of its own: an answer still out for the last one is not this
  // one's, and neither is the last one's pending close
  sheetSeq++;
  clearTimeout(closeTimer);
  ankiWasPlaying = !A.paused;
  if (!A.paused) A.pause();
  // the loop/continuous timer may already be armed from timeupdate; left
  // alone it would start the audio underneath the open dashboard
  clearTimeout(waiting); waiting = null;
  closeCloud();
  AN.ref.textContent = num;
  AN.fa.value = word;
  // is the clicked word the whole chunk?  It is for a language without word
  // separators (one word per chunk), and otherwise when it equals the chunk
  // -- the click gesture trims the chunk's edge punctuation off the word,
  // so the chunk is compared trimmed the same way
  const ofLine = typeof reading === 'string';
  const whole = !ofLine && (!LANG.word_sep || word === d.fa || word === trimPunct(d.fa));
  // the reading is of the whole chunk; a single word out of it has none --
  // unless the word line gave the word its own, which is the kana where the
  // language has one and the romanisation (pinyin) where it has not
  AN.kana.value = ofLine ? (LANG.reading ? reading : '') : whole ? d.kana : '';
  AN.tr.value = ofLine && !LANG.reading ? reading : d.tr;
  AN.en.value = d.en;
  // a single word gets its chunk as context; a whole chunk gets its
  // subparagraph -- the sentence it lives in -- and so does a word of the
  // line, which its chunk would only repeat
  AN.ctx.value = whole || ofLine ? sent : d.fa;
  AN.notes.value = d.voc;
  AN.tags.value = LANG.tag + '-book ' + META.book;
  AN.src.value = (META.title_latin || META.book) + (num ? ' — ' + num : '');
  setDir('both');
  AN.opp.value = ''; AN.oppTr.value = ''; AN.oppKana.value = '';
  JOLLY.forEach(ta => { ta.value = ''; });
  jollyEdited = false; lastJolly = null;
  dropClip(true);
  document.querySelector('input[name=asndside][value=front]').checked = true;
  ankiKind = 'vocab';
  deckPicked = false;           // a new card starts from the deck used last
  setTarget(cardTo);
  sndState();
  $('#apvrow').hidden = true; $('#apvframe').srcdoc = '';
  AN.back.hidden = false; AN.box.hidden = false; ankiOpen = true;
  AN.fa.focus();
}
function closeAnki() {
  ankiOpen = false; AN.back.hidden = true; AN.box.hidden = true;
  clearTimeout(closeTimer);
  dropClip(true);
  if (ankiWasPlaying) A.play().catch(() => {});
  ankiWasPlaying = false;
}
$('#acancel').onclick = closeAnki;
AN.back.addEventListener('click', closeAnki);
AN.box.addEventListener('submit', e => e.preventDefault());
document.addEventListener('keydown', e => {
  if (!ankiOpen) return;
  if (e.key === 'Escape') { e.preventDefault(); closeAnki(); }
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); saveCard(); }
});

// one gatherer for saving AND previewing, so they can never disagree
function collectCard() {
  return { card: {
    lang: LANG.code,
    book: META.book,
    time: Math.round(ankiTime * 10) / 10,
    fa: AN.fa.value.trim(), kana: AN.kana.value.trim(), tr: AN.tr.value.trim(),
    en: AN.en.value.trim(), context: AN.ctx.value.trim(),
    opp: AN.opp.value.trim(), opp_kana: AN.oppKana.value.trim(),
    opp_tr: AN.oppTr.value.trim(),
    notes: AN.notes.value.trim(),
    kind: ankiKind,
    bidirectional: ankiDir !== 'forward',
    reverse_only: ankiDir === 'reverse',
    tags: AN.tags.value.trim().split(/\s+/).filter(Boolean),
    source: {
      label: AN.src.value.trim(),
      url: (ankiPara && location.protocol.indexOf('http') === 0)
        ? location.origin + location.pathname + '#' + ankiPara : ''
    }
  }, clip: ankiClip ? {side: sndSide(), name: ankiClip.name} : null };
}
function saveCard() {
  if (cardTo === 'deck') return addToDeck();
  if (cardTo === 'md') return copyMarkdown();
  return saveAnki();
}
// A PRESS IS KEPT, WHATEVER HAPPENS TO THE SHEET WHILE ITS ANSWER IS OUT.
// Each of the three takes the card as it stands at the press -- what it sends
// is read before anything is awaited -- and carries its clip out (clipsOut),
// so closing the sheet, or changing the card, the moment after changes
// nothing of what was pressed.  What comes back is said on the sheet that
// asked, and when that sheet has been closed since (or opened again for
// another word) in a toast over the page, the only place left to say it.
// `clip` is the recording the card names, or null; one press at a time per
// sheet (busyFor is the sheet whose press is out).
let busyFor = 0;
function press(clip) {
  const seq = sheetSeq;
  const here = () => ankiOpen && seq === sheetSeq;
  if (clip) clipsOut.set(clip.name, (clipsOut.get(clip.name) || 0) + 1);
  busyFor = seq;
  let over = false;
  return {
    here: here,
    // progress, for the sheet that asked only
    note(text) { if (here()) AN.stat.textContent = text; },
    // `link`: [its text, its href, what follows it] -- the link is said on
    // the sheet only, after a dash
    say(text, bad, link) {
      if (!here()) {
        ntoast((text + (link && link[2] ? link[2] : '')).replace(/\n+/g, ' — '), bad);
        return;
      }
      AN.stat.textContent = text + (link ? ' — ' : '');
      if (link) {
        const a = document.createElement('a');
        a.href = link[1]; a.target = '_blank'; a.textContent = link[0];
        AN.stat.appendChild(a);
        if (link[2]) AN.stat.appendChild(document.createTextNode(link[2]));
      }
      AN.stat.scrollIntoView({block: 'nearest'});
    },
    // the answer is in: a clip that went onto a card stays in the tray for
    // good; one that did not, and is on no open sheet, leaves it
    done(used) {
      if (over) return;
      over = true;
      if (busyFor === seq) busyFor = 0;
      if (!clip) return;
      const n = (clipsOut.get(clip.name) || 1) - 1;
      if (n > 0) clipsOut.set(clip.name, n); else clipsOut.delete(clip.name);
      if (used) clipsUsed.add(clip.name);
      else if (!(here() && ankiClip && ankiClip.name === clip.name)) forgetClip(clip);
    },
    // the sheet closes itself a moment after an Anki save, so the answer can
    // be read -- unless it is another sheet by then, or somebody is still at
    // work on this one (the cut editor is open, or they have typed or
    // clicked in it since).  An exercise deck's answer links to the deck,
    // and a copy refused leaves the markdown to copy by hand: those stay
    closeSoon(ms) {
      clearTimeout(closeTimer);
      closeTimer = setTimeout(() => {
        closeTimer = 0;
        if (here() && !cutting) closeAnki();
      }, ms);
    }
  };
}
const pressBusy = () => busyFor !== 0 && busyFor === sheetSeq;
['input', 'pointerdown'].forEach(t => AN.box.addEventListener(t, () => clearTimeout(closeTimer)));
function saveAnki() {
  // deckLang is the language of the deck the user is LOOKING at; the card
  // goes to the deck of its own language whatever that is, and the answer
  // says so when the two differ
  let deckName, deckLang = LANG.code;
  if (AN.deck.value === '') {
    deckName = AN.deckNew.value.trim();
    if (!deckName) { AN.stat.textContent = 'name the new deck first';
      AN.deckNew.focus(); return; }
  } else {
    const key = AN.deck.value;
    deckName = key;
    decksCache.forEach(d => {
      if (d.folder + '/' + d.slug === key) { deckName = d.name; deckLang = d.lang; }
    });
  }
  if (!AN.fa.value.trim()) { AN.stat.textContent = 'the ' + LANG.name + ' side is empty';
    AN.fa.focus(); return; }
  if (ankiKind === 'opposites' && !AN.opp.value.trim()) {
    AN.stat.textContent = 'write the opposite in first \u2014 that is the answer side';
    AN.opp.focus(); return; }
  if (pressBusy()) return;
  const c = collectCard();
  const body = { deck: deckName, deck_lang: deckLang, card: c.card };
  if (c.clip) body.clip = c.clip;
  const p = press(c.clip ? ankiClip : null);
  p.note('saving…');
  fetch('/anki/cards', { method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  }).then(r => r.json()).then(res => {
    if (!res.ok) throw new Error(res.error || 'save failed');
    p.done(true);
    localStorage.setItem('bk_deck', res.deck.folder + '/' + res.deck.slug);
    deckPicked = false;
    p.say('saved ✓ — “' + res.deck.name + '” (' +
      res.deck.language + ') now has ' + res.deck.cards + ' card' +
      (res.deck.cards === 1 ? '' : 's') +
      (res.refiled ? ' — ' + res.refiled.note : ''), false);
    p.closeSoon(res.refiled ? 2200 : 900);
  }).catch(e => { p.done(false); p.say(e.message, true); });
}
$('#asave').onclick = saveCard;

// ---- an exercise deck, and markdown: the card as the card kit writes it
function kitProblem() {
  if (ankiKind === 'jolly') {
    if (!AN.jfp.value.trim() && !AN.jfs.value.trim()) return [AN.jfp, 'the front is empty: write in one of its two fields'];
    if (!AN.jbp.value.trim() && !AN.jbs.value.trim()) return [AN.jbp, 'the back is empty: write in one of its two fields'];
    return null;
  }
  if (!AN.fa.value.trim()) return [AN.fa, 'the ' + LANG.name + ' side is empty'];
  if (ankiKind === 'opposites' && !AN.opp.value.trim())
    return [AN.opp, 'write the opposite in first — that is the answer side'];
  return null;
}
function kitMarkdown() {
  const c = collectCard().card, jolly = ankiKind === 'jolly';
  return ParsehCards.markdown({
    fa: c.fa, kana: c.kana, tr: c.tr, en: c.en, context: c.context,
    opp: c.opp, opp_kana: c.opp_kana, opp_tr: c.opp_tr, notes: c.notes,
    source: c.source, dir: ankiDir, image: null,
    // a jolly card has its recording where its text puts it
    audio: ankiClip && !jolly ? {side: sndSide(), path: clipPath(ankiClip)} : null,
    jolly: {'front-primary': AN.jfp.value, 'front-secondary': AN.jfs.value,
            'back-primary': AN.jbp.value, 'back-secondary': AN.jbs.value},
    latin: LANG.script === 'latin'
  }, ankiKind);
}
// the clip a card's markdown names -- a jolly card's text may not name it at
// all -- or null
const clipIn = md => ankiClip && md.indexOf(clipPath(ankiClip)) >= 0 ? ankiClip : null;
// the card, said back: "a vocabulary card for “clock”"
function whatCard() {
  const kind = {vocab: 'a vocabulary card', opposites: 'an opposites card', jolly: 'a jolly card'}[ankiKind];
  const word = ankiKind === 'jolly' ? '' : AN.fa.value.trim();
  return kind + (word ? ' for “' + word + '”' : '');
}
// what the markdown was to carry and does not name: the recording's line
// taken out of a jolly card's fields.  '' when it names it (the video
// player's sheet says the same of its frame)
function leftOut(md) {
  return ankiClip && !clipIn(md)
    ? 'the recording is not on the card: its line was taken out of the fields' : '';
}
// where a card made here came from, for the deck page's link back to it:
// the book's address, the subparagraph, and this page at its paragraph
function bookOrigin() {
  const o = {label: AN.ref.textContent.trim(), title: META.title || META.title_latin || META.book};
  const m = /^(\/books\/[^\/]+\/[^\/]+)\/reader\//.exec(location.pathname);
  if (m) o.book = m[1];
  if (location.protocol.indexOf('http') === 0) o.url = location.pathname + (ankiPara ? '#' + ankiPara : '');
  return o;
}
// A DUPLICATE IS ASKED ABOUT, NOT REFUSED.  The deck says it has the card
// already; the button then reads "add it again", and pressing it adds a
// second one.  Any change to the card first asks again.  (The video
// player's sheet asks the same way.)
let dupArmed = false;
function unarm() {
  if (!dupArmed) return;
  dupArmed = false;
  AN.saveLab.textContent = CARD_TO[cardTo].save;
}
AN.box.addEventListener('input', unarm);
AN.box.addEventListener('change', unarm);
$('#akvocab').addEventListener('click', unarm);
$('#akopp').addEventListener('click', unarm);
$('#akjolly').addEventListener('click', unarm);
// what a press came to, said where it can be read: the sheet scrolls, and
// a long answer -- a deck's warnings -- wraps below the fold of it
function tell(text) {
  AN.stat.textContent = text;
  AN.stat.scrollIntoView({block: 'nearest'});
}
async function addToDeck() {
  if (pressBusy()) return;
  if (!window.ParsehCards) { AN.stat.textContent = KIT_GONE; return; }
  const bad = kitProblem();
  if (bad) { AN.stat.textContent = bad[1]; bad[0].focus(); return; }
  let path = AN.deck.value, deck = exDecksCache.find(d => d.path === path);
  const force = dupArmed, newName = AN.deckNew.value.trim();
  if (!path && !newName) { AN.stat.textContent = 'name the new deck first';
    AN.deckNew.focus(); return; }
  // the card as it stands at the press, before the deck is even made
  const md = kitMarkdown(), origin = bookOrigin(), clip = clipIn(md), gone = leftOut(md);
  const went = whatCard() + (clip ? ', with its recording' : '');
  const p = press(clip);
  try {
    if (!path) {
      p.note('making the deck…');
      deck = await ParsehCards.newDeck(newName, LANG.code);
      path = deck.path;
      localStorage.setItem('bk_exdeck', path);
      deckPicked = false;
      if (AN.deckNew.value.trim() === newName) AN.deckNew.value = '';
      if (newDeckNames.deck === newName) newDeckNames.deck = '';
      if (p.here() && cardTo === 'deck') exDeckOptions(exDecksCache.concat([deck]));
    }
    p.note('adding…');
    const res = await ParsehCards.add(path, md, origin, force);
    if (!res.ok) {
      p.done(false);
      if (!p.here()) p.say(res.error + (res.conflict === 'duplicate' ? ' — nothing was added' : ''), true);
      else if (res.conflict === 'duplicate' && !force) {
        dupArmed = true;
        AN.saveLab.textContent = 'add it again';
        tell(res.error + ' — press “add it again” to add a second one');
      } else {
        unarm();
        tell(res.error);
      }
      return;
    }
    p.done(true);
    localStorage.setItem('bk_exdeck', path);
    deckPicked = false;
    const warnings = res.warnings || [];
    // the sheet stays, with a link to the deck and the deck's warnings; its
    // list is asked for again, for the count
    p.say('added ✓ — ' + went + (res.items && res.items.length > 1 ? ' (two linked cards, one each way)' : '') + ', to “' + (deck ? deck.name : path) + '”' + (gone ? ' — ' + gone : ''),
          warnings.length > 0,
          ['open the deck', '/exercises/deck/' + path + '/', warnings.length ? '\n' + warnings.join('\n') : '']);
    if (p.here()) { unarm(); if (cardTo === 'deck') loadDecks(); }
  } catch (e) {
    p.done(false);
    p.say(e.message, true);
  }
}
function copyMarkdown() {
  if (pressBusy()) return;
  if (!window.ParsehCards) { AN.stat.textContent = KIT_GONE; return; }
  const bad = kitProblem();
  if (bad) { AN.stat.textContent = bad[1]; bad[0].focus(); return; }
  const md = kitMarkdown(), clip = clipIn(md), gone = leftOut(md), card = whatCard();
  const p = press(clip);
  $('#amdrow').hidden = true;
  ParsehCards.copy(md).then(ok => {
    if (ok) {
      p.done(true);
      p.say('copied ✓ — ' + card + '. Paste it into a studio document or a deck’s “Add exercise”' +
            (clip ? ': the recording comes along from the clip tray when it is pasted there' : '') +
            (gone ? ' — ' + gone : ''), false);
      return;
    }
    if (!p.here()) {
      p.done(false);
      p.say('not copied — the browser would not put the card on the clipboard', true);
      return;
    }
    // there to copy by hand, so the recording it names is kept for it
    p.done(true);
    const out = $('#amdout');
    out.value = md;
    $('#amdrow').hidden = false;
    out.focus(); out.select();
    AN.stat.textContent = 'not copied — the browser would not put it on the clipboard: the markdown is below, to copy by hand' +
                          (gone ? ' — ' + gone : '');
  }, e => { p.done(false); p.say(e.message, true); });
}

/* ---------- the book-info sheet -------------------------------------------
   Title, author, year, the library card's blurb: book.json's own fields,
   not a chunk's, opened and saved the same way the anki dashboard is (a
   back/box pair, Esc and the backdrop close it, Ctrl+Enter saves) but
   against __edit/meta instead of /anki/cards.  META.editable carries
   book.json's fields under their own names (main()'s comment says why
   META's own title/author, meant for the anki dashboard, do not). */
const BM = {
  back: $('#bmback'), box: $('#bmbox'),
  title: $('#bmtitle'), titleLatin: $('#bmtitlelatin'), titleEn: $('#bmtitleen'),
  author: $('#bmauthor'), authorLatin: $('#bmauthorlatin'),
  year: $('#bmyear'), blurb: $('#bmblurb'), reorders: $('#bmreorders'),
  stat: $('#bmstat')
};
// "reorders" (kanbun) only means something where chunks have words
$('#bmreordersrow').hidden = !LANG.words;
let bmOpen = false, bmWasPlaying = false, bmWas = {};
function openBookMeta() {
  const m = META.editable || {};
  bmWas = {title: m.title || '', title_latin: m.title_latin || '',
           title_en: m.title_en || '', author: m.author || '',
           author_latin: m.author_latin || '', year: m.year || '',
           blurb: m.blurb || '', reorders: !!m.reorders};
  BM.title.value = bmWas.title; BM.titleLatin.value = bmWas.title_latin;
  BM.titleEn.value = bmWas.title_en; BM.author.value = bmWas.author;
  BM.authorLatin.value = bmWas.author_latin; BM.year.value = bmWas.year;
  BM.blurb.value = bmWas.blurb; BM.reorders.checked = bmWas.reorders;
  // title and author are the book's own language; every other field here
  // is written in the latin alphabet or in English, so only these two take
  // the book's font and direction (the add-video page's overrides do the
  // same, for the same reason: a select box cannot ask the registry)
  [BM.title, BM.author].forEach(el => {
    el.setAttribute('data-lang', LANG.code);
    if (LANG.dir === 'rtl') el.setAttribute('dir', 'rtl'); else el.removeAttribute('dir');
  });
  BM.stat.textContent = ''; BM.stat.classList.remove('bad');
  bmWasPlaying = !A.paused;
  if (!A.paused) A.pause();
  BM.back.hidden = false; BM.box.hidden = false; bmOpen = true;
  BM.title.focus();
}
function closeBookMeta() {
  bmOpen = false; BM.back.hidden = true; BM.box.hidden = true;
  if (bmWasPlaying) A.play().catch(() => {});
  bmWasPlaying = false;
}
$('#bookinfo').onclick = openBookMeta;
$('#buildbook').onclick = () => buildThisBook();
$('#bmcancel').onclick = closeBookMeta;
BM.back.addEventListener('click', closeBookMeta);
BM.box.addEventListener('submit', e => e.preventDefault());
document.addEventListener('keydown', e => {
  if (!bmOpen) return;
  if (e.key === 'Escape') { e.preventDefault(); closeBookMeta(); }
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); saveBookMeta(); }
});
async function saveBookMeta() {
  const fields = {};
  if (BM.title.value !== bmWas.title) fields.title = BM.title.value;
  if (BM.titleLatin.value !== bmWas.title_latin) fields.title_latin = BM.titleLatin.value;
  if (BM.titleEn.value !== bmWas.title_en) fields.title_en = BM.titleEn.value;
  if (BM.author.value !== bmWas.author) fields.author = BM.author.value;
  if (BM.authorLatin.value !== bmWas.author_latin) fields.author_latin = BM.authorLatin.value;
  if (BM.year.value !== bmWas.year) fields.year = BM.year.value;
  if (BM.blurb.value !== bmWas.blurb) fields.blurb = BM.blurb.value;
  if (BM.reorders.checked !== bmWas.reorders) fields.reorders = BM.reorders.checked;
  if (!Object.keys(fields).length) {
    BM.stat.textContent = 'nothing to change'; BM.stat.classList.remove('bad');
    return;
  }
  BM.stat.textContent = 'saving…'; BM.stat.classList.remove('bad');
  let j;
  try {
    // relative, like __edit/chunk: the reader is served from
    // /books/<folder>/<slug>/reader/, and the path is how the server knows
    // which book the edit belongs to
    const r = await fetch('__edit/meta', {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({fields})});
    j = await r.json();
  } catch (err) {
    BM.stat.textContent = 'the server did not answer (' + (err.message || err) +
      ') — an edit needs this page served by python3 serve.py; nothing was written';
    BM.stat.classList.add('bad');
    return;
  }
  if (!j.ok) { BM.stat.textContent = j.error || 'the edit was refused';
    BM.stat.classList.add('bad'); return; }
  // read back what was actually written, not what was typed, and keep
  // document.title and the anki dashboard's source label in step with it
  META.editable = {title: j.meta.title || '', title_latin: j.meta.title_latin || '',
                   title_en: j.meta.title_en || '', author: j.meta.author || '',
                   author_latin: j.meta.author_latin || '', year: j.meta.year || '',
                   blurb: j.meta.blurb || '', reorders: !!j.meta.reorders};
  // the page is not reloaded, so the word strip is told here
  META.reorders = META.editable.reorders;
  META.title = META.editable.title; META.title_latin = META.editable.title_latin;
  META.author = META.editable.author_latin;
  document.title = (META.title || '') + ' — Parseh';
  if (j.pdf_stale) pdfStale();
  let msg = 'saved ✓';
  if (j.reader && !j.reader.ok)
    msg += '\nthe files are written, but the reader would not rebuild: ' +
           (j.reader.error || 'no reason given');
  BM.stat.textContent = msg; BM.stat.classList.remove('bad');
  setTimeout(() => { if (bmOpen) closeBookMeta(); }, 900);
}
$('#bmsave').onclick = saveBookMeta;

function isNight() {
  // the toolbox's theme: auto follows the system, so ask the shared script
  return window.Parseh ? Parseh.theme.isDark()
    : document.documentElement.getAttribute('data-theme') === 'dark';
}
function showPreview() {
  $('#apvrow').hidden = false;
  AN.stat.textContent = '';
  setTimeout(() => {
    $('#apvrow').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, 60);
}
$('#apreview').onclick = () => {
  const frame = $('#apvframe');
  // an exercise deck and markdown: the studio's own renderer, and its own
  // script in the frame to turn the card (ParsehCards.preview gives the
  // frame the scripts it needs)
  if (cardTo !== 'anki') {
    if (!window.ParsehCards) { AN.stat.textContent = KIT_GONE; return; }
    AN.stat.textContent = 'rendering…';
    ParsehCards.preview(kitMarkdown(), LANG.code, frame, cardTo === 'deck')
      .then(showPreview, e => { AN.stat.textContent = e.message; });
    return;
  }
  // Anki's own templates need no script: the frame is given none
  frame.setAttribute('sandbox', 'allow-same-origin');
  const c = collectCard();
  AN.stat.textContent = 'rendering…';
  const body = { card: c.card, night: isNight() };
  if (c.clip) body.clip = c.clip;
  fetch('/anki/preview', { method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  }).then(r => r.json()).then(res => {
    if (!res.ok) throw new Error(res.error || 'preview failed');
    frame.srcdoc = res.html;
    showPreview();
  }).catch(e => { AN.stat.textContent = e.message; });
};
$('#apvhide').onclick = () => { $('#apvrow').hidden = true; };

$('#abuild').onclick = () => {
  // the value is "<folder>/<slug>", which is what the build URL names: two
  // languages may hold a deck of the same name, and the one-level URL
  // cannot tell them apart
  const key = AN.deck.value;
  if (!key) { AN.stat.textContent =
    'save a card first — the deck does not exist yet'; return; }
  // on the activity list while the deck is built and sent (lib/activity.js)
  if (window.ParsehActivity) ParsehActivity.download('/anki/build/' + key + '.apkg',
                                                     'Building the Anki deck…');
  else location.href = '/anki/build/' + key + '.apkg';
  AN.stat.textContent = 'building — import the downloaded .apkg into Anki';
};

/* ---------- the narration panel: the recordings of this book -------------
   THE SUBJECT HERE IS THE LIST OF RECORDINGS.  A book has one, or a dozen,
   each covering a stretch of the text; everything that can be done to one is
   done in ITS OWN ROW, and what is left for the head is what is true of the
   book: how much of it is timed, adding a recording, and the narration file
   that carries the lot to another copy.

   THERE IS ONE ALIGN AND IT IS ON THE ROW.  The whole-book button this panel
   used to lead with could not work on a book recorded in parts -- with no
   recording named, lib/timestamp.py exits "say which one to align" -- and on
   a book with ONE recording the row is the book, since books.py reads the old
   scalars as a single recording called n1.  So the button is gone, not moved,
   and every align posts {narration: id}.

   Answered by the server this page is served from (relative URLs, like
   __save/, so the server knows which book).  Most doors end by rebuilding the
   reader, and this page has TIMES/SUBS/NARR/META baked into it: from the
   first such change what is on screen is from before, which is what the bar
   at the top of the list says.  Opened from the disk none of it can work, and
   the panel says so instead of failing quietly, control by control.       */
const NR = {back: $('#narrback'), box: $('#narrbox'), main: $('#nmain'),
            askback: $('#naskback'), ask: $('#naskbox')};
let narrOpen = false, narrRebuilt = false, narrCands = [], NSTAT = null;
let narrAskDone = null;                 // the question on screen, waiting
let NBUSY = false;                      // a subprocess is out: the panel waits
const narrShown = new Set();            // rows whose drawer is open
/* AND WHAT EACH ROW'S LAST RUN SAID.  The log is written into the drawer and
   the drawer is then thrown away: every run ends in narrStatus, whose
   narrRows empties #nlist and builds it again.  So the log lives here, by
   recording id, exactly as the open/closed state does, and narrDraw puts it
   back when it builds the drawer. */
const narrLogs = new Map();
const noNarr = document.body.classList.contains('noaudio');
$('#narr').textContent = noNarr ? 'add a narration' : 'narration';
$('#narr').classList.toggle('cta', noNarr);
// the header's scrubber, whose visibility this block has always owned: it is
// shown while editing, and while nothing is timed
function showScrub() {
  $('#scrub').hidden = noNarr ||
    !(document.body.classList.contains('editing') || !META.timed);
}
showScrub();
function rebuilt() { narrRebuilt = true; $('#nredo').hidden = false; }
function nesc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g,
  c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})[c]); }
function nsize(n) { return n >= 1e6 ? (n / 1e6).toFixed(n >= 1e8 ? 0 : 1) + ' MB'
                                    : Math.round(n / 1e3) + ' kB'; }
// "1 recording", never "1 recordings" -- the deck pages' plural(), which is
// the difference between a panel that was written and one that was generated
function nplural(n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); }
function nfile(f, missing) {
  if (f.exists) return '<b>' + nesc(f.path) + '</b>' + (f.bytes ? ' · ' + nsize(f.bytes) : '');
  if (f.declared) return '<span class="bad">book.json names ' + nesc(f.declared) +
    ', which is not there</span>';
  return missing;
}
/* The toast every Parseh page can raise (lib/parseh.css, z-index 400): it
   floats above this sheet, so an outcome is seen wherever the sheet is
   scrolled.  It is the TRANSIENT notice and never the only copy -- what a run
   said is also in the row it was about.  With no lib/parseh.js behind the
   page there is no toast at all, and the message still has to land somewhere
   a person is looking. */
function ntoast(msg, bad) {
  if (window.Parseh && Parseh.toast) { Parseh.toast(msg, bad); return; }
  narrWork(msg, bad);
}

/* ---------- the doors ----------------------------------------------------
   A REFUSAL CARRIES ITS LOG.  serve.py's _run_steps hands back the
   subprocess's own output in `log` beside a one-line `error`, and the error
   alone is "align failed (timestamp.py)" -- the sentence that says WHY is in
   the log, so it travels on the Error and is rendered by whoever catches. */
/* EVERY DOOR IS ON THE ACTIVITY LIST (lib/activity.js, which parseh.js
   loads): an align or an upload takes minutes, and the hub and every other
   page say so while it runs.  The page's own entry is shown at once, and the
   request carries its token, so the server's entry for it -- with the book's
   title and the bytes -- is shown as the same one.  No list (opened off the
   disk, or no parseh.js): the doors work as they always did. */
const NARR_WORK = {align: 'Aligning the narration', spread: 'Spreading a recording',
                   region: 'Moving a recording\'s stretch', remove: 'Taking a recording off',
                   restore: 'Putting the narration back', transcript: 'Saving a transcript',
                   audio: 'Uploading a recording', 'import': 'Importing a narration file'};
function narrWorking(what, name) {
  const label = (NARR_WORK[what] || 'Working on the narration') + (name ? ' — ' + name : '');
  return (window.Parseh && Parseh.working) ? Parseh.working(label)
    : {url: u => u, end() {}, progress() {}};
}
async function narrPost(what, body) {
  const act = narrWorking(what);
  let r;
  try {
    r = await fetch(act.url('__narration/' + what),
                    {method: 'POST', headers: {'Content-Type': 'application/json'},
                     body: JSON.stringify(body)});
  } catch (e) { act.end(false); throw e; }
  let j = null;
  try { j = await r.json(); } catch (_) {}
  act.end(!!(j && j.ok));
  if (!j || !j.ok) {
    const e = new Error((j && j.error) || ('the server refused (' + r.status + ')'));
    e.log = (j && j.log) || '';
    throw e;
  }
  return j;
}
function narrUpload(blob, what, name, onProgress, extra) {
  return new Promise((resolve, reject) => {
    const act = narrWorking(what, name);
    const x = new XMLHttpRequest();
    x.open('POST', act.url('__narration/' + what + '?name=' + encodeURIComponent(name)
                           + (extra || '')));
    x.upload.onprogress = e => {
      if (!e.lengthComputable) return;
      act.progress(e.loaded, e.total);
      if (onProgress) onProgress(e.loaded / e.total);
    };
    x.onload = () => {
      let j = null;
      try { j = JSON.parse(x.responseText); } catch (_) {}
      act.end(!!(j && j.ok));
      if (j && j.ok) { resolve(j); return; }
      const e = new Error((j && j.error) || ('server error ' + x.status));
      e.log = (j && j.log) || '';
      reject(e);
    };
    x.onerror = () => {
      act.end(false);
      reject(new Error('the server did not answer — is this page served by serve.py?'));
    };
    x.send(blob);
  });
}

/* ---------- a question with a dangerous answer ---------------------------
   THE SHEET DOES THE WORK AND STAYS OPEN WHILE IT RUNS, as the deck page's
   dialogs do: a sheet that closes on "yes" and fails afterwards leaves the
   refusal nowhere, and timestamp.py's refusals are the ones worth reading --
   "covers 21 subparagraphs already timed for real (1.1 to 6.6): --force to
   lay a guess over them".  So the answer is read here, the tick that answers
   it is offered here even when the question did not carry one, and pressing
   the button again is the retry.                                          */
function narrAsk(o) {
  const yes = $('#naskok'), no = $('#naskno'), tick = $('#naskforce'),
        box = $('#naskforcebox'), err = $('#naskerr');
  $('#nasktitle').textContent = o.title;
  $('#naskhint').innerHTML = o.hint || '';
  tick.hidden = !o.force;
  box.checked = false; box.disabled = false;
  if (o.force) $('#naskforcelab').textContent = o.force;
  err.textContent = ''; err.hidden = true; err.classList.remove('bad');
  yes.textContent = o.ok;
  yes.disabled = no.disabled = false;
  yes.classList.toggle('danger', !!o.danger);
  yes.classList.toggle('primary', !o.danger);
  NR.askback.hidden = false; NR.ask.hidden = false;
  // a dangerous question starts focused on cancel, as the deck's dialogs do
  (o.danger ? no : yes).focus({preventScroll: true});
  return new Promise(res => {
    const shut = v => {
      narrAskDone = null;
      NR.askback.hidden = true; NR.ask.hidden = true;
      NR.box.focus({preventScroll: true});
      res(v);
    };
    narrAskDone = () => { if (!yes.disabled) shut(null); };   // Escape, backdrop
    no.onclick = narrAskDone;
    yes.onclick = async () => {
      if (!o.run) { shut({force: box.checked}); return; }
      yes.disabled = no.disabled = box.disabled = true;
      err.hidden = false; err.classList.remove('bad');
      err.textContent = o.saying || 'working…';
      try {
        const j = await o.run(box.checked);
        shut(j === undefined ? true : j);
      } catch (e) {
        err.classList.add('bad');
        err.textContent = e.message + (e.log ? '\n\n' + e.log : '');
        // the one option a refusal names, put where the refusal is
        if (tick.hidden && /--force/.test(e.message || '')) {
          $('#naskforcelab').textContent = o.force ||
            'go on anyway, over the times already there';
          tick.hidden = false;
        }
        yes.disabled = no.disabled = box.disabled = false;
        yes.focus({preventScroll: true});
      }
    };
  });
}
NR.askback.addEventListener('click', () => { if (narrAskDone) narrAskDone(); });

/* ---------- reading the state ------------------------------------------- */
async function narrStatus() {
  const r = await fetch('__narration/status', {cache: 'no-store'});
  const j = await r.json();
  if (!j.ok) throw new Error(j.error || 'no answer');
  NSTAT = j;
  NR.box.classList.remove('noserver');
  narrHead(j);
  // the outlines mark each chapter with the recordings already over it
  if (naddPicker) naddPicker.paint();
  narrRows(j);
}
function narrHead(j) {
  const a = j.audio, tr = j.transcript || {}, ns = j.narrations || [],
        ti = j.timings || {subs: 0, manual: 0}, tl = j.tools || {};
  $('#nref').textContent = j.title_latin || j.slug;
  $('#ndir').textContent = j.audio_dir;
  // ONE LINE OF COUNTS, rewritten after every action (aria-live): what the
  // book has, and how much of it is timed.  It replaces five branches of
  // prose that each said a different half of this.
  const usable = ns.filter(n => n.has_transcript && n.segments);
  const bits = [nplural(ns.length, 'recording'),
                j.timed + ' of ' + j.subs + ' subparagraphs timed'];
  if (ti.manual) bits.push(ti.manual + ' by hand');
  if (ns.length) bits.push(usable.length ? nplural(usable.length, 'transcript')
                                         : 'no transcript yet');
  $('#nsum').textContent = bits.join(' · ');
  // AND THE PROBLEMS, AND ONLY THE PROBLEMS.  A panel that says everything
  // at once says nothing; this line is empty on a book that is well.
  const bad = [];
  if (!a.exists && a.declared)
    bad.push('<code>book.json</code> names ' + nesc(a.declared) +
             ' as the audio, which is not there.');
  if (tr.declared && !tr.exists)
    bad.push('<code>book.json</code> names ' + nesc(tr.declared) +
             ' as the transcript, which is not there.');
  else if (tr.exists && !tr.segments)
    bad.push('the transcript <code>' + nesc(tr.path || tr.declared || '') + '</code> has no ' +
             'timestamps in it: it must carry clock lines (0:00, 1:23:45), .srt/.vtt cues, ' +
             'or whisper\'s segments.');
  if (ti.subs > j.subs)
    bad.push(nplural(ti.subs - j.subs, 'saved time') + ' no longer match any ' +
             'subparagraph — the text was edited after they were measured.');
  if (!tl.ffmpeg)
    bad.push('ffmpeg is not here: cuts are not snapped to silences, and the length of a ' +
             'recording can only be read from a <code>.wav</code>.');
  $('#nwarn').innerHTML = bad.join(' ');
  $('#nwarn').hidden = !bad.length;
  // THE STATE THIS BOOK IS ACTUALLY IN, said once, beside the buttons that
  // answer it -- rather than left to be worked out from four grey aligns.
  let note = '';
  // NOT A REASON ALIGN CANNOT RUN, so not in red above everything else:
  // lib/timestamp.py falls back to difflib when rapidfuzz is absent and only
  // rescues fewer near-misses inside the gaps.  It was being pushed onto the
  // warnings, which put a sentence saying "align still runs" in the colour
  // the panel uses for things that are broken.
  if (!tl.rapidfuzz)
    note = 'rapidfuzz is not installed (<code>pip install rapidfuzz</code>, or start ' +
           'serve.sh with the conda environment): align still runs, on difflib alone, ' +
           'and fewer near-misses are rescued. ';
  if (ns.length && !usable.length)
    note = 'No recording here has a transcript, so there is nothing to align yet. ' +
           '<b>estimate times</b> on a row shares that recording out over the stretch it ' +
           'covers — a first guess that plays, and that a real alignment later replaces ' +
           'without being asked twice. A transcript is added to a row from inside the row.';
  else if (ns.length && usable.length < ns.length)
    note = nplural(ns.length - usable.length, 'recording') + ' still without a usable ' +
           'transcript: those rows can be given a first guess with <b>estimate times</b>.';
  $('#nnote').innerHTML = note;
  $('#nnote').hidden = !note;
  $('#ntools').innerHTML =
    (tl.rapidfuzz ? '<span class="ok">rapidfuzz ✓</span>'
                  : '<span class="bad">rapidfuzz ✗</span> — optional: without it the ' +
                    'alignment is difflib\'s alone and rescues fewer near-misses') +
    ' and ' +
    (tl.ffmpeg ? '<span class="ok">ffmpeg ✓</span>'
               : '<span class="bad">ffmpeg ✗</span> — optional, but it is what tells how ' +
                 'long a file is and what snaps the cuts to silences');
  // [hidden] like everything else here; the old one hid itself with an
  // inline style, the only control in the panel that did
  $('#nexport').hidden = !a.exists;
  // a DOM property takes a raw string: escaping it here would put &amp; on
  // the screen, which is what nesc() in a title attribute has always done
  $('#nexport').title = ns.length > 1
    ? 'one file: ' + (a.path || '') + ', the transcript and every time. The other ' +
      nplural(ns.length - 1, 'recording') + ' do not travel in it yet'
    : 'one file: the audio, the transcript, the times and a manifest';
  $('#naudio').innerHTML = nfile(a, '');
  // EDIT TIMES BY HAND IS NOT REACHABLE ON A PAGE BUILT WITHOUT A RECORDING:
  // body.noaudio hides #editmode, .edit and #scrub with !important, so the
  // button would close this sheet onto a header that has nothing to press.
  const et = $('#nedittimes');
  const dead = noNarr && !narrRebuilt;
  et.dataset.off = dead ? '1' : '';
  et.disabled = dead || NBUSY;
  et.title = dead
    ? 'this page was built with no recording, so edit times is not in its header: add a ' +
      'recording first, and the reader is rebuilt with it'
    : narrRebuilt
    ? 'the reader was rebuilt: this reloads the page, where edit times is in the header'
    : 'close this and turn on edit times: play the recording and stamp each ' +
      'subparagraph\'s start and end by hand';
  narrCands = j.candidates || [];
  $('#nfound').hidden = !narrCands.length;
  if (narrCands.length) {
    $('#nfoundlist').innerHTML = narrCands.map((c, i) =>
      '<span class="nfitem"><button type="button" class="nuse small" data-i="' + i +
      '">use ' + nesc(c.path) + '</button> <span class="nstate">' + nsize(c.bytes) +
      ' · ' + nesc(c.where) + '</span></span>').join('');
    $$('#nfoundlist .nuse').forEach(b => {
      b.onclick = () => narrRestore(narrCands[+b.dataset.i]); });
  }
}
/* WHAT A RECORDING COVERS is picked from the book as an outline, down to
   its subparagraphs (outlinePicker): a chapter in one click, where it used
   to be two lists of every subparagraph label of the book -- 146 of them for
   a textbook, and each the same "1.1" in every chapter.  Nothing picked is
   the whole book.  An end is written WITH ITS CHAPTER, "2:1.1", which names
   one subparagraph where the label alone named one per chapter
   (texparse.region_bounds reads both).  Every other recording's stretch is
   marked on the rows it covers, so a gap or an overlap shows before it is
   made. */
function narrPicker(self) {
  return outlinePicker({
    depth: 'sub', whole: true, label: 'what this recording covers',
    hint: 'Nothing picked is the whole book. Click a chapter, a section or a paragraph ' +
          'to take all of it — click it again to go inside, down to its subparagraphs. ' +
          'Shift-click another, or “stretch it to…” and pick it, to take everything in ' +
          'between.',
    tags: row => {
      if (row.kind === 's' || row.lo == null) return [];
      return ((NSTAT && NSTAT.narrations) || [])
        .filter(n => n.id !== self && (n.from || n.to) && n.lo != null &&
                     row.lo <= n.hi && row.hi >= n.lo)
        .map(n => [n.id, 'olrec', n.id + ' (' + (n.audio || '') + ') covers ' +
                   (row.lo >= n.lo && row.hi <= n.hi ? 'all' : 'part') + ' of this']);
    },
  });
}
let naddPicker = null;
function naddPick() {
  if (!naddPicker) {
    naddPicker = narrPicker('');
    $('#naddpick').appendChild(naddPicker.el);
    naddPicker.load();
  }
  return naddPicker;
}
// a subparagraph as the door is told it: its chapter and its label, "2:1.1"
function narrQual(pk, i) {
  const p = pk.model.paras[SUBS[i][4]];
  return (p ? p.ch : '') + ':' + SUBS[i][5];
}
// the book as the outline reads it, once, for saying where a stretch is
let narrOl = null;
function narrWhere(n) {
  if (!n.from && !n.to) return 'the whole book';
  if (n.lo != null && n.hi != null) {
    narrOl = narrOl || olModel('sub');
    const said = olDescribe(narrOl, {lo: n.lo, hi: n.hi});
    if (said) return said;
  }
  // a stretch whose ends the book no longer has, said as it was written
  const end = x => { const c = String(x).lastIndexOf(':');
                     return c < 0 ? x : 'chapter ' + x.slice(0, c) + ', ' + x.slice(c + 1); };
  return (n.from ? end(n.from) : 'the beginning') + ' → ' + (n.to ? end(n.to) : 'the end') +
         (n.lo == null && 'lo' in n ? ' (not in this book any more)' : '');
}

/* ---------- one row per recording ---------------------------------------
   The deck page's row (markdown/app/static/decks.js itemRow): a toggle that
   opens a drawer, a line of facts, an action column that does not move, and
   values written with textContent rather than interpolated into markup.

   THREE ACTIONS, which is the deck's own count: align, estimate times,
   remove.  What a recording covers is not a fourth -- it is edited in the
   drawer the toggle opens, beside the transcript that belongs to the same
   recording -- and leaving it out is what leaves room for a long file name.
   The list head and the empty state are written from HERE and nowhere else,
   so a page opened off the disk never shows "the recordings" over nothing. */
function narrRows(j) {
  const box = $('#nlist'), ns = j.narrations || [], tl = j.tools || {};
  const ti = j.timings || {subs: 0};
  box.innerHTML = '';
  ns.forEach(n => box.appendChild(narrRow(n, tl)));
  // [hidden] stays on #nlist: tests/narration.mjs waits on
  // #nlist:not([hidden]) as its one synchronisation barrier for the panel
  box.hidden = !ns.length;
  $('#nlisthead').hidden = !ns.length;
  $('#ncount').textContent = ns.length ? nplural(ns.length, 'recording') : '';
  $('#nempty').hidden = !!ns.length;
  $('#nempty [data-x="empty-none"]').hidden = !!ti.subs;
  $('#nempty [data-x="empty-orphan"]').hidden = !ti.subs;
}
function narrRow(n, tl) {
  const row = document.createElement('div');
  row.className = 'nitem';
  row.dataset.id = n.id;
  row.innerHTML =
    '<button type="button" class="ntog" aria-expanded="false">' +
      '<span class="nkick"></span><span class="nname"></span></button>' +
    '<div class="nmeta"></div>' +
    '<div class="nwhy"></div>' +
    '<div class="nacts">' +
      '<button type="button" data-x="align">align</button>' +
      '<button type="button" data-x="spread">estimate times</button>' +
      '<button type="button" data-x="byear">by ear</button>' +
      '<button type="button" class="danger ghost" data-x="remove">remove</button>' +
    '</div>' +
    '<div class="nsay" data-x="state"></div>' +
    '<div class="ndraw" hidden></div>';
  const tog = row.querySelector('.ntog');
  tog.title = 'what it covers, its transcript, and the log of its last run';
  const kick = row.querySelector('.nkick'), tag = (text, cls, why) => {
    const s = document.createElement('span');
    s.className = 'tag ' + (cls || '');
    s.textContent = text;
    if (why) s.title = why;             // a property, so a raw string
    kick.appendChild(s);
  };
  const segs = n.segments || 0;
  tag(n.id, 'id', 'the name book.json and timings.json know this recording by');
  if (!n.exists) tag('file missing', 'bad', 'book.json names it, but it is not on the shelf');
  // THREE STATES AND NOT TWO.  serve.py sets segments to 0 when
  // parse_transcript throws, so a green "0 timestamps" was a file that could
  // not be read wearing the badge of one that had been.
  if (n.has_transcript && segs)
    tag(nplural(segs, 'timestamp'), 'good', 'its own transcript: ' + (n.transcript || ''));
  else if (n.has_transcript)
    tag('transcript unusable', 'bad', 'the file is there — ' + (n.transcript || '') +
        ' — but no timestamps could be read out of it');
  else tag('no transcript', 'warn', 'nothing to align against — it can still be timed by ' +
    'a first guess, or by hand');
  row.querySelector('.nname').textContent = n.audio || 'no file';
  // THE FACTS, ONE SPAN EACH, instead of four crushed into a middot sentence
  const meta = row.querySelector('.nmeta'), fact = t => {
    const s = document.createElement('span'); s.textContent = t; meta.appendChild(s); };
  fact('covers ' + narrWhere(n));
  if (n.exists) fact(nsize(n.bytes));
  // "21 of 21 timed" needs the region's own total, which the status door
  // sends: with an older server that has only the count, say the count and no
  // denominator rather than a fraction of nothing
  fact(typeof n.subs === 'number'
    ? n.timed + ' of ' + n.subs + ' timed'
    : (n.timed ? n.timed + ' timed' : 'nothing timed yet'));
  if (n.manual) fact(n.manual + ' by hand');
  // WHY A DEAD BUTTON IS DEAD, on the button itself -- and, where there is no
  // pointer to hover with, in the row.  The old panel had one sentence for
  // one case (#nwhy) and left every row's grey align unexplained.
  const b = x => row.querySelector('[data-x="' + x + '"]');
  const why = row.querySelector('.nwhy');
  const al = b('align');
  const canAlign = !!(n.exists && n.has_transcript && segs);
  al.disabled = !canAlign;
  al.classList.toggle('primary', canAlign && !n.timed);
  al.title = !n.exists ? 'the file is not on the shelf'
    : !n.has_transcript ? 'no transcript for this recording yet — open the row and add ' +
      'one, or give it a first guess with estimate times'
    : !segs ? 'its transcript has no timestamps in it, so there is nothing to align against'
    : 'align this recording against the text it covers';
  const est = b('spread');
  const wav = /\.wav$/i.test(n.audio || '');
  est.disabled = !n.exists || (!tl.ffmpeg && !wav);
  est.classList.toggle('primary', !!(n.exists && !canAlign && !n.timed && (tl.ffmpeg || wav)));
  est.title = !n.exists ? 'the file is not on the shelf'
    : (!tl.ffmpeg && !wav) ? 'this needs to know how long the file is, and without ffmpeg ' +
      '(ffprobe comes with it) that can only be read from a .wav'
    : 'share this recording out over the text it covers, in proportion to the length of ' +
      'each subparagraph — a first guess to fix by ear, not an alignment';
  b('remove').title = 'take this recording off the book — the file itself stays';
  // THE ONE DONE BY HAND, beside the two done for you.  align and estimate
  // times both answer "where is each subparagraph"; this answers "not
  // there, HERE", over a picture of the sound, and needs times already on
  // the text to move -- which either of the other two puts there first.
  const ear = b('byear');
  ear.disabled = !n.exists || !n.timed || !window.ParsehTimeline;
  ear.title = !n.exists ? 'the file is not on the shelf'
    : !window.ParsehTimeline ? 'the timeline (lib/timeline.js) did not load: reload the page'
    : !n.timed ? 'nothing this recording covers has a time yet — align it, or give it a '
      + 'first guess with estimate times, and the boundaries can then be moved by ear'
    : 'move the boundaries between one subparagraph and the next by ear, over a picture '
      + 'of the sound';
  why.textContent = !canAlign ? 'align: ' + al.title
                  : est.disabled ? 'estimate times: ' + est.title
                  : ear.disabled ? 'by ear: ' + ear.title : '';
  al.onclick = () => narrAlignOne(n);
  est.onclick = () => narrSpread(n);
  ear.onclick = () => narrByEar(n);
  b('remove').onclick = () => narrRemove(n);
  tog.onclick = () => narrDraw(row, n);
  // what each button's own state is, so releasing the panel-wide lock never
  // wakes one that should stay grey
  [...row.querySelectorAll('.nacts button')].forEach(x => {
    x.dataset.off = x.disabled ? '1' : '';
    x.disabled = x.disabled || NBUSY;
  });
  // a row whose drawer was open before the list was redrawn opens again,
  // with the log it was carrying
  if (narrShown.has(n.id)) narrDraw(row, n, true);
  return row;
}

/* The drawer: what this recording covers, its transcript, and its own log --
   all of it inside the row, built when it is first opened.  This is where
   "covers…" now leads: the old one set two selects at the other end of the
   sheet, relabelled a hidden button beside them, and reported its failures
   into a third place again.                                                */
function narrDraw(row, n, open) {
  const d = row.querySelector('.ndraw'), tog = row.querySelector('.ntog');
  if (open === undefined) open = d.hidden;
  tog.setAttribute('aria-expanded', String(open));
  row.classList.toggle('open', open);
  d.hidden = !open;
  if (!open) { narrShown.delete(n.id); return; }
  narrShown.add(n.id);
  if (!d.dataset.built) {
    d.dataset.built = '1';
    d.innerHTML =
      '<div class="nfield"><span class="nfieldlab">covers</span>' +
        '<span class="nstate" data-x="covsay"></span>' +
        '<button type="button" class="small" data-x="covchg" aria-expanded="false">' +
          'change&hellip;</button>' +
      '</div>' +
      '<div class="npick" data-x="covpick" hidden></div>' +
      '<div class="nfield" data-x="covsave" hidden>' +
        '<button type="button" class="primary small" data-x="savecovers">save what it covers</button>' +
      '</div>' +
      '<div class="anote">The times already measured are not touched: what changes is ' +
        'which subparagraphs the next run may re-time.</div>' +
      '<div class="nfield"><span class="nfieldlab">transcript</span>' +
        '<span class="nstate" data-x="trstate"></span>' +
        '<label class="nbtn small">pick a file<input type="file" data-x="trfile" ' +
          'accept=".txt,.srt,.vtt,.json,text/plain" hidden></label>' +
      '</div>' +
      '<div class="nfield"><textarea data-x="trtext" rows="2" ' +
          'placeholder="&hellip;or paste it here"></textarea>' +
        '<button type="button" class="small" data-x="savetext">save the pasted transcript</button>' +
      '</div>' +
      '<pre data-x="log" hidden></pre>';
    // the pasted transcript is in the BOOK's language and direction, which
    // the page already knows: META carries both, so the row's own textarea
    // takes them here rather than from an attribute written at build time
    const ta = d.querySelector('[data-x="trtext"]');
    ta.lang = META.lang || 'en';
    ta.dir = META.dir || 'ltr';
    // what it covers, said; the outline to change it opens under the words
    // (it is a long thing to show for a row that is only being looked at)
    const pk = narrPicker(n.id);
    d.querySelector('[data-x="covpick"]').appendChild(pk.el);
    d._pick = pk;
    d.querySelector('[data-x="covchg"]').onclick = ev => {
      const box = d.querySelector('[data-x="covpick"]'), on = box.hidden;
      box.hidden = !on;
      d.querySelector('[data-x="covsave"]').hidden = !on;
      ev.currentTarget.setAttribute('aria-expanded', String(on));
      if (!on) return;
      pk.load();
      if ((n.from || n.to) && n.lo != null) pk.set(n.lo, n.hi); else pk.set(null);
      pk.focus();
    };
    d.querySelector('[data-x="savecovers"]').onclick = () => narrSaveCovers(row, n);
    d.querySelector('[data-x="trfile"]').onchange = ev => {
      const f = ev.target.files[0]; ev.target.value = '';
      if (f) narrTranscript(row, n, f, f.name);
    };
    d.querySelector('[data-x="savetext"]').onclick = () => {
      const txt = d.querySelector('[data-x="trtext"]').value.trim();
      if (!txt) { ntoast('nothing pasted yet', true); return; }
      narrTranscript(row, n, new Blob([txt], {type: 'text/plain'}), 'transcript.txt');
    };
    if (NBUSY) [...d.querySelectorAll('button,select,textarea')].forEach(
      x => { x.disabled = true; });
  }
  d.querySelector('[data-x="covsay"]').textContent = narrWhere(n);
  const st = d.querySelector('[data-x="trstate"]');
  if (!n.has_transcript) st.textContent = 'none yet';
  else st.innerHTML = '<b>' + nesc(n.transcript || '') + '</b> · ' +
    (n.segments ? nplural(n.segments, 'timestamp') +
                  (n.span ? ' over ' + fmt(n.span) : '')
                : '<span class="bad">no timestamps could be read out of it</span>');
  // the log this row was carrying before the list was rebuilt under it
  const pre = d.querySelector('[data-x="log"]'), kept = narrLogs.get(n.id) || '';
  pre.textContent = kept;
  pre.hidden = !kept;
}

/* ---------- what a row can do -------------------------------------------
   ONE LOCK, AND IT IS THE PANEL'S.  A run rebuilds the reader under every
   other row as well, so no second run may start beside it; and the list this
   row lives in is REPLACED when the answer comes, so a lock held on the
   captured node would be released on a node that is no longer in the page.
   The lock is therefore read off the DOM as it stands at that moment, and
   data-off remembers what each button's own state was.                     */
function narrLock(on) {
  NBUSY = on;
  earPaint();
  NR.box.classList.toggle('working', on);
  $$('#narrbox .nitem button:not(.ntog),#narrbox .ndraw select,' +
     '#narrbox .ndraw textarea,#narrbox .nheadacts button:not(#nhowbtn)').forEach(x => {
    x.disabled = on || x.dataset.off === '1'; });
}
function narrFind(id) { return $$('#nlist .nitem').find(r => r.dataset.id === id) || null; }
/* WHERE A REFUSAL LIVES.  A toast is one line for 4200 ms, and timestamp.py
   refuses in three; so the row keeps what its last run said until its next
   one, and the toast is only the notice that something happened. */
function narrSay(id, text, bad) {
  const row = narrFind(id);
  if (!row) { narrWork(text, bad); return; }
  const s = row.querySelector('[data-x="state"]');
  s.textContent = text || '';
  s.classList.toggle('bad', !!bad);
}
/* opt.log     keep the run's log in the row (align and estimate times say
                what they did; what region and remove hand back is the
                rebuild's own output, which nobody asked for)
   opt.rebuilt false when the door does NOT rebuild the reader, so the bar
                does not promise a page that was never rebuilt             */
async function narrRun(n, saying, fn, opt) {
  opt = opt || {};
  narrLock(true);
  narrSay(n.id, saying, false);
  try {
    const j = await fn();
    narrLogs.delete(n.id);
    if (opt.log && j && j.log) { narrLogs.set(n.id, j.log); narrShown.add(n.id); }
    if (opt.rebuilt !== false) rebuilt();
    await narrStatus();                 // the row is rebuilt from the answer
    narrSay(n.id, opt.said || '', false);
    return j;
  } catch (e) {
    // the log is the half of a failure that says why: kept, and opened
    narrLogs.set(n.id, e.log || '');
    narrSay(n.id, e.message, true);
    const row = narrFind(n.id);
    if (row) narrDraw(row, n, true);
    ntoast(e.message, true);
    throw e;
  } finally {
    narrLock(false);
  }
}
/* A REFUSAL IS ANSWERED WHERE IT IS RAISED.  timestamp.py refuses to lay a
   guess over times that are already real and names --force in the sentence;
   narrAsk's own catch puts that sentence in the sheet, reveals the tick it
   names and re-enables the button, so the second press is the answer to the
   first.  There was a narrForce() here that opened a SECOND sheet for the
   same refusal -- two dialogs for one question, and the one that could act
   was the one that had not been asked. */
async function narrAlignOne(n) {
  const go = force => narrRun(n, 'aligning… a minute or two for a whole novel',
    () => narrPost('align', {narration: n.id, force: force}), {log: true})
    .then(j => { ntoast('aligned ' + n.id + ': ' + j.timed + ' of ' + j.subs +
                        ' subparagraphs timed in the book'); return j; });
  const ask = {
    title: 'Align ' + n.id + ' again?',
    hint: 'The times of the ' + (n.subs ? n.subs + ' subparagraphs' : 'subparagraphs') +
      ' it covers are worked out afresh from its transcript. Everything outside ' +
      nesc(narrWhere(n)) + ' is untouched.',
    force: 'start over, dropping the times fixed by hand' +
      (n.manual ? ' (' + n.manual + ' here)' : ''),
    ok: 'align', saying: 'aligning…', run: go};
  // asked only when it would overwrite something: an alignment on a stretch
  // that has nothing in it is not a question.  A refusal on this path has
  // already been said by narrRun -- in the row, in its log and in a toast --
  // and rethrown, so there is nothing left to do but let it settle.
  if (n.timed) { await narrAsk(ask); return; }
  try { await go(false); } catch (e) { /* said in the row already */ }
}
async function narrSpread(n) {
  const go = force => narrRun(n, 'sharing it out over the text it covers…',
    () => narrPost('spread', {narration: n.id, force: force}), {log: true})
    .then(j => { ntoast(nplural(j.spread || 0, 'subparagraph') + ' given a first guess — ' +
                        'play them and fix what drifts with edit times'); return j; });
  const ask = {
    title: 'Give ' + n.id + ' a first guess?',
    hint: 'A guess is laid over the WHOLE stretch it covers or none of it, so a stretch ' +
      'already timed for real is refused unless this says otherwise.',
    force: 'lay the guess over the times already there' +
      (n.manual ? ', including the ' + n.manual + ' fixed by hand' : ''),
    ok: 'estimate times', saying: 'sharing it out…', run: go};
  if (n.timed) { await narrAsk(ask); return; }
  try { await go(false); } catch (e) { /* said in the row already */ }
}
/* BY EAR: this recording's own stretch, boundary by boundary, over a
   picture of its sound.  align and estimate times both answer "where is
   each subparagraph" and answer it for the whole stretch at once; this is
   the hand afterwards, on the one boundary that came out wrong.

   It opens the shared timeline (lib/timeline.js), which knows nothing about
   books: what it is given is the pieces with their text and their two
   times, a way to draw the sound, a way to play a stretch of it, and a way
   to save.  Saving goes through the door `save times` has always used
   (__save/subtimes.json), so a time moved here and a time moved there are
   written, merged and rebuilt by exactly the same code.

   THE TEXT IS ON THE PAGE, and a chapter still in its own file has none, so
   the chapters this recording covers are fetched before the sheet opens --
   the same needChapters the reading place uses to jump into one.

   WHERE IT OPENS: on the first piece, or -- `where`, a subparagraph's index --
   on that one, or on the nearest that has a time when it has none.  The
   narration panel's button asks for no place; the header's `edit times by
   ear` asks for the reading place (editByEar, below). */
async function narrByEar(n, where) {
  if (!window.ParsehTimeline) {
    ntoast('the timeline (lib/timeline.js) did not load: reload the page', true);
    return;
  }
  const rec = NARRBY[n.id];
  const mine = [];
  for (let i = 0; i < N; i++) {
    const r = narrFor(i);
    if (r && r.id === n.id && SUBS[i][0] != null && SUBS[i][1] != null) mine.push(i);
  }
  if (!mine.length) {
    ntoast('nothing this recording covers has a time yet — align it, or estimate times', true);
    return;
  }
  ntoast('fetching the text…');
  for (const c of [...new Set(mine.map(i => SUBS[i][2]))]) {
    try { await needChapters(c); } catch (_) { /* what is here is enough */ }
  }
  const sep = (typeof LANG !== 'undefined' && LANG.word_sep) || ' ';
  const marks = [], at = [];
  for (const i of mine) {
    const el = subEl(i);
    if (!el || !el.dataset.key) continue;       // a chapter that would not come
    const a = +el.dataset.from, b = +el.dataset.to, out = [];
    for (let c = a; c <= b; c++) out.push(String((SRC[c] || [])[1] || ''));
    marks.push({key: el.dataset.key,
                label: el.dataset.key.replace(/-[0-9a-f]{6,}$/, ''),
                text: out.join(sep).replace(/\s+/g, ' ').trim(),
                t0: SUBS[i][0], t1: SUBS[i][1]});
    at.push(i);
  }
  if (!marks.length) {
    ntoast('the text of this recording’s stretch could not be fetched', true);
    return;
  }
  // the piece to open on: the one asked for, else the closest timed one,
  // the earlier of two that are as close
  let start = 0;
  if (where != null && where >= 0) {
    let best = Infinity;
    at.forEach((i, k) => {
      if (Math.abs(i - where) < best) { best = Math.abs(i - where); start = k; }
    });
  }
  const play = ParsehTimeline.media(rec && rec.src ? rec.src : '');
  // the reading place is not a preview: whatever the page was playing stops
  try { A.pause(); } catch (_) {}
  // how long the recording is, so "all" means all of it: the status says
  // how far the TRANSCRIPT reaches, which is not the same number and is
  // absent altogether for a recording that never had one
  const seconds = await new Promise(done => {
    const a = play.el, say = () => done(isFinite(a.duration) ? a.duration : 0);
    if (a.readyState >= 1) return say();
    a.addEventListener('loadedmetadata', say, {once: true});
    a.addEventListener('error', () => done(0), {once: true});
    setTimeout(say, 2500);
  });
  let saved = null;
  try {
    saved = await ParsehTimeline.open({
      title: 'by ear — ' + n.id + (n.audio ? ' · ' + n.audio.split('/').pop() : ''),
      kind: 'span',
      marks: marks,
      at: start,
      duration: seconds,
      dir: (typeof LANG !== 'undefined' && LANG.dir) || '',
      lang: (typeof LANG !== 'undefined' && LANG.code) || '',
      peaks: (a, b, buckets) => fetch('__clip/peaks', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({narration: n.id, start: a, end: b, buckets: buckets})})
        .then(r => r.json()).then(j => j && j.ok ? j : null).catch(() => null),
      // "estimate the rest" by the sound: the same recording, read whole
      // over the stretch asked about and laid out by lib/wavealign.py on the
      // server.  A refusal is the server's own words, for the sheet to say.
      // A DEADLINE, generous and growing with the stretch -- two minutes,
      // and a second more for every minute of sound -- so that a server
      // gone quiet does not hold the sheet for ever; a hand that will not
      // wait so long has the sheet's own stop.
      estimate: req => {
        const wait = 120000 + Math.max(0, req.end - req.start) * 1000 / 60;
        const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), wait);
        const failed = e => {
          throw new Error(ctl.signal.aborted
            ? 'the server gave no answer in ' + Math.round(wait / 60000)
              + ' minutes, so the estimate was given up — nothing was estimated'
            : 'the server did not answer (' + ((e && e.message) || e)
              + ') — nothing was estimated');
        };
        return fetch('__clip/estimate', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({narration: n.id, ...req}), signal: ctl.signal})
          .then(r => r.json().catch(() => null).then(j => {
            if (ctl.signal.aborted) failed();
            if (!r.ok || !j || !j.ok)
              throw new Error((j && j.error) || 'the sound could not be read to estimate from');
            return j;
          }), failed)
          .finally(() => clearTimeout(timer));
      },
      play: (a, b) => play.play(a, b),
      stop: () => play.stop(),
      now: () => play.now(),
      save: changed => narrSaveTimes(changed)
    });
  } finally {
    play.free();
  }
  if (!saved || !saved.length) return;
  // the page agrees with what was written, without being rebuilt under it
  const by = {};
  saved.forEach(c => { by[c.key] = c; });
  at.forEach((i, k) => {
    const c = by[marks[k].key];
    if (!c) return;
    SUBS[i][0] = c.t0; SUBS[i][1] = c.t1;
    const el = subEl(i);
    if (el) { delete el.dataset.orig; if (typeof paint === 'function') paint(i); }
    // it is on disk now: an older unsaved edit of the same one is not
    if (edits[c.key]) { delete edits[c.key]; }
  });
  try { localStorage.setItem(MINE('edits'), JSON.stringify(edits)); } catch (_) {}
  if (typeof showEditCount === 'function') showEditCount();
  ntoast(nplural(saved.length, 'boundary', 'boundaries') + ' moved and saved');
  narrStatus();
}
/* EDIT TIMES BY EAR, from the header: the by-ear sheet on the recording the
   text is following, at the subparagraph the reading place is on.  It is for
   the moment the alignment is heard to have been lost -- a line said over
   the wrong text -- when the road through the narration panel (open it, find
   the row, press by ear) lands on the FIRST piece of whichever recording was
   picked, and the piece wanted is somewhere in three hundred.

   THE RECORDING IS THE ONE THE MARK IS IN, not the one loaded: they are the
   same while a subparagraph plays (playSub loads the file it is in), and only
   the mark says where the reading is when nothing plays or a listening has
   gone on past it.  With no mark, or a mark no recording covers, it is the
   recording loaded, else the first that has any time.  The sheet then finds
   the piece itself, or the nearest one that has a time (narrByEar).      */
function earTimed(r) {
  for (let k = 0; k < N; k++) {
    const f = narrFor(k);
    if (f && f.id === r.id && SUBS[k][0] != null && SUBS[k][1] != null) return true;
  }
  return false;
}
function earTarget() {
  const i = (typeof cur === 'number' && cur >= 0 && cur < N) ? cur : -1;
  let n = i >= 0 ? narrFor(i) : null;
  if (!n) n = NARR.find(r => r.src === loadedSrc && earTimed(r)) || NARR.find(earTimed) || NARR[0] || null;
  const why = !window.ParsehTimeline
    ? 'the timeline (lib/timeline.js) did not load: reload the page'
    : !n ? 'this book has no recording to move times in'
    : NBUSY ? 'a recording is being worked on: wait for it to finish'
    : !earTimed(n)
    ? 'nothing this recording covers has a time yet — align it, or give it a first guess ' +
      'with estimate times (in narration), and the boundaries can then be moved by ear'
    : '';
  return {n: n, i: i, why: why};
}
// the button says what it will open, or why it will not: read again wherever
// the mark or the times move
function earPaint() {
  const b = $('#editbyear');
  if (!b) return;
  const t = earTarget();
  b.disabled = !!t.why;
  b.title = t.why || 'move where each subparagraph starts, by ear, over a picture of the sound: ' +
    'it opens at the subparagraph you are on' +
    (NARRN > 1 ? ', in the recording the text is following (' + t.n.id + ')' : '');
}
let earOpening = false;
async function editByEar() {
  const t = earTarget();
  if (t.why) { ntoast(t.why, true); return; }
  if (earOpening) return;
  earOpening = true;
  try {
    await narrByEar({id: t.n.id, audio: t.n.src}, t.i);
  } finally {
    earOpening = false;
    earPaint();
  }
}
$('#editbyear').onclick = editByEar;
// a var, and read by hl() above: the reading place is restored while this
// script is still running, before the lets this button reads are set
var earLive = true;
earPaint();

// the door `save times` has always used, so both hands write the same way
async function narrSaveTimes(changed) {
  const body = {};
  changed.forEach(c => { body[c.key] = {t0: c.t0, t1: c.t1}; });
  const r = await fetch('__save/subtimes.json', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)});
  let j = null;
  try { j = await r.json(); } catch (_) {}
  if (!r.ok || !j || !j.ok) throw new Error((j && j.error) || 'the times could not be saved');
  return j;
}
async function narrSaveCovers(row, n) {
  const d = row.querySelector('.ndraw'), pk = d._pick, got = pk && pk.get();
  const from = got ? narrQual(pk, got.lo) : '', to = got ? narrQual(pk, got.hi) : '';
  try {
    await narrRun(n, 'saving what it covers…',
                  () => narrPost('region', {id: n.id, from: from, to: to}));
    ntoast(n.id + ' covers ' + narrWhere({from: from, to: to,
                                          lo: got ? got.lo : null, hi: got ? got.hi : null}));
  } catch (_) { /* the row and the toast have it */ }
}
async function narrRemove(n) {
  await narrAsk({
    title: 'Take ' + n.id + ' off the book?',
    hint: '<b>' + nesc(n.audio || '') + '</b> stays on the shelf, and the times it ' +
      'measured stay in <code>timings.json</code>. Putting it back is not one press: ' +
      '<b>found elsewhere</b> points <code>book.json</code>\'s own <code>audio</code> at a ' +
      'file, which is not the same as a row in this list — to have it back as a recording, ' +
      'use <b>add a recording&hellip;</b> and say what it covers.',
    ok: 'remove ' + n.id, danger: true, saying: 'removing…',
    run: () => narrRun(n, 'removing…', () => narrPost('remove', {id: n.id}))
      .then(j => { narrShown.delete(n.id); narrLogs.delete(n.id);
                   ntoast(n.id + ' is off the book; the file stays'); return j; })});
}
/* A TRANSCRIPT BELONGS TO A RECORDING, not to a book: it is sent with the id
   of the row it was dropped on, and the server files it under that recording
   (a book with one whole-book recording keeps the single audio/transcript.<ext>
   it has always had).  THE DOOR DOES NOT REBUILD THE READER -- it ends at
   send_json -- so nothing here claims it did: what a transcript changes is
   what the next align can do, not a byte of this page.                      */
async function narrTranscript(row, n, blob, name) {
  try {
    const j = await narrRun(n, 'saving the transcript…',
      () => narrUpload(blob, 'transcript', name, null,
                       '&narration=' + encodeURIComponent(n.id)),
      {rebuilt: false});
    const ta = row.querySelector('[data-x="trtext"]');
    if (ta) ta.value = '';
    ntoast(nplural(j.segments || 0, 'timestamp') + ' over ' + fmt(j.span || 0) +
           ' — ' + n.id + ' can be aligned now');
  } catch (_) { /* the row and the toast have it */ }
}

/* ---------- what the book can do ---------------------------------------- */
function narrWork(text, bad) {
  $('#nwork').innerHTML = bad ? '<span class="bad">' + nesc(text) + '</span>' : nesc(text);
}
function narrBookLog(log) {
  $('#nlog').textContent = log || '';
  $('#nlog').hidden = !log;
}
async function narrBookRun(saying, fn, opt) {
  opt = opt || {};
  narrLock(true);
  narrWork(saying);
  narrBookLog('');
  try {
    const j = await fn();
    narrBookLog(opt.log ? (j && j.log) || '' : '');
    // the answer says whether the rebuild ran: the upload door reports
    // ok:true with rebuilt:false when tex2html.py itself failed
    if (opt.rebuilt !== false && !(j && j.rebuilt === false)) rebuilt();
    await narrStatus();
    narrWork('');
    if (j && j.error) { narrBookLog((j.log || '') || j.error); ntoast(j.error, true); }
    return j;
  } catch (e) {
    narrBookLog(e.log || '');
    narrWork(e.message, true);
    ntoast(e.message, true);
    throw e;
  } finally {
    narrLock(false);
    $('#nbarwrap').hidden = true;
  }
}
$('#npaudio').onchange = async ev => {
  const f = ev.target.files[0]; ev.target.value = '';
  if (!f) return;
  // what the picked file is a recording OF, sent with it: the server files
  // it beside the others instead of replacing the book's narration.  These
  // two selects belong to THIS upload and to nothing else -- a row says what
  // it covers in its own drawer.
  const pk = naddPick(), got = pk.get();
  const from = got ? narrQual(pk, got.lo) : '', to = got ? narrQual(pk, got.hi) : '';
  const ns = (NSTAT && NSTAT.narrations) || [];
  // AND WITH NEITHER END NAMED IT IS A REPLACEMENT.  serve.py takes the old
  // road there -- set_book_meta(audio=…) -- and the one recording this book
  // has stops being its narration without a word said. So the word is said.
  if (!from && !to && ns.length === 1) {
    const old = ns[0];
    const yes = await narrAsk({
      title: 'Replace ' + old.id + '?',
      hint: 'With neither end named, <b>' + nesc(f.name) + '</b> becomes the book\'s one ' +
        'recording and <b>' + nesc(old.audio || '') + '</b> stops being its narration. ' +
        'That file stays on the shelf and the times in <code>timings.json</code> stay as ' +
        'they are — they will be read as times into the new file. To keep both, cancel ' +
        'and name the stretch this one covers first.',
      ok: 'replace ' + old.id, danger: true});
    if (!yes) return;
  }
  $('#nbarwrap').hidden = false; $('#nabar').style.width = '0';
  try {
    const j = await narrBookRun('copying ' + f.name + ' (' + nsize(f.size) + ')…',
      () => narrUpload(f, 'audio', f.name,
        p => { $('#nabar').style.width = (100 * p).toFixed(1) + '%'; },
        '&from=' + encodeURIComponent(from) + '&to=' + encodeURIComponent(to)));
    $('#nadd').hidden = true; $('#naddbtn').setAttribute('aria-expanded', 'false');
    // the server gives a region-bounded recording its first guess as it
    // lands; the old panel threw that number away
    ntoast(j.spread ? f.name + ' is on the shelf — ' +
                      nplural(j.spread, 'subparagraph') + ' given a first guess'
                    : f.name + ' is on the shelf');
  } catch (_) { /* narrBookRun has said it */ }
};
$('#npimport').onchange = async ev => {
  const f = ev.target.files[0]; ev.target.value = '';
  $('#nkeep').open = false;
  if (!f) return;
  if (NSTAT && (NSTAT.narrations || []).length) {
    const yes = await narrAsk({
      title: 'Import over this narration?',
      hint: 'The audio and the transcript in the file are unpacked into <code>audio/</code> ' +
        'and <code>book.json</code> is pointed at them, and the times inside REPLACE ' +
        '<code>timings.json</code> whole — every recording\'s, not only the first\'s. The ' +
        'list of recordings itself is left as it is. The present <code>timings.json</code> ' +
        'is kept beside it as <code>audio/timings.before-import.json</code>.',
      ok: 'import', danger: true});
    if (!yes) return;
  }
  $('#nbarwrap').hidden = false; $('#nabar').style.width = '0';
  try {
    const j = await narrBookRun('importing ' + f.name + ' (' + nsize(f.size) + ')…',
      () => narrUpload(f, 'import', f.name,
        p => { $('#nabar').style.width = (100 * p).toFixed(1) + '%'; }),
      {log: true});
    ntoast('imported: ' + j.timed + ' of ' + j.subs + ' subparagraphs timed');
  } catch (_) { /* narrBookRun has said it */ }
};
async function narrRestore(c) {
  await narrAsk({
    title: 'Use ' + c.path + '?',
    hint: '<code>book.json</code>\'s own <code>audio</code> is pointed at that file — ' +
      nesc(c.where) + ' — and the reader is rebuilt with it. It does not join the list of ' +
      'recordings: on a book that lists them, the list is still what the reader plays, and ' +
      '<b>add a recording&hellip;</b> is what puts a file in it. The times already in ' +
      '<code>timings.json</code> are kept; nothing is re-aligned.',
    ok: 'use it', saying: 'connecting…',
    run: () => narrBookRun('connecting ' + c.path + '…',
      () => narrPost('restore', {path: c.path}))
      .then(j => { ntoast('connected: ' + j.timed + ' of ' + j.subs +
                          ' subparagraphs timed'); return j; })});
}

/* ---------- opening and closing ----------------------------------------- */
$('#naddbtn').onclick = e => {
  const on = $('#nadd').hidden;
  $('#nadd').hidden = !on;
  e.currentTarget.setAttribute('aria-expanded', String(on));
  if (on) {
    // read afresh, keeping what was picked before, and shown
    const pk = naddPick().load(), got = pk.get();
    pk.set(got ? got.lo : null, got ? got.hi : null);
    pk.focus();
  }
};
$('#nhowbtn').onclick = e => {
  const on = $('#nhow').hidden;
  $('#nhow').hidden = !on;
  e.currentTarget.setAttribute('aria-expanded', String(on));
};
// the menu closes when a choice is taken in it, or a click lands outside;
// the import label is not in this test, because closing the menu under a
// file input takes the file dialog with it -- it closes on its own change
document.addEventListener('click', e => {
  const d = $('#nkeep');
  if (!d || !d.open) return;
  if (!d.contains(e.target) || (e.target.closest && e.target.closest('.nmenu a')))
    d.open = false;
});
// the one thing a book with no transcript actually needs, reachable from
// here instead of described in a paragraph pointing at the header
$('#nedittimes').onclick = () => {
  if (narrRebuilt) { location.reload(); return; }   // edit what is stale: no
  closeNarr();
  if (!document.body.classList.contains('editing')) $('#editmode').click();
};
function openNarr() {
  if (!A.paused) A.pause();
  clearTimeout(waiting); waiting = null;
  closeCloud();
  NR.back.hidden = false; NR.box.hidden = false; narrOpen = true;
  NR.box.focus({preventScroll: true});
  $('#nsum').textContent = 'looking…';
  narrStatus().catch(e => {
    NR.box.classList.add('noserver');
    $('#nsum').textContent = 'the panel cannot reach the server';
    $('#nwarn').hidden = false;
    $('#nwarn').innerHTML = '<span class="bad">' + nesc(e.message) + '</span> — this panel ' +
      'needs the page served by serve.py; opened from the disk, nothing here can work.';
  });
}
function closeNarr() {
  if (narrAskDone) narrAskDone();
  narrOpen = false; NR.back.hidden = true; NR.box.hidden = true;
  $('#narr').focus({preventScroll: true});
  // the page has the times, the recordings and the counts baked in, and the
  // server has rebuilt it under us
  if (narrRebuilt) location.reload();
}
$('#narr').onclick = openNarr;
$('#ncancel').onclick = closeNarr;
$('#nclose').onclick = closeNarr;
$('#nreload').onclick = () => location.reload();
NR.back.addEventListener('click', closeNarr);
// the panel is a form: Enter in any field must not navigate
NR.box.addEventListener('submit', e => e.preventDefault());
addEventListener('keydown', e => {
  if (e.key !== 'Escape' || !narrOpen) return;
  e.preventDefault();
  // the question first, so a cancel comes back to the row it was about
  if (narrAskDone) narrAskDone(); else closeNarr();
});

/* ---------- the download: three shapes of one edition ---------------------
   It sits here, after the narration, because that is what it is about and
   because it asks the same endpoint.  The header's button opens a sheet the
   way the contents does; each choice is an ordinary link to the server's own
   ?audio= modes, so nothing here saves a file, and tabbing and Enter come
   for free.

   The sheet is BUILT here rather than written into the page, the way the Aa
   panel is: a book with no narration must carry no markup about one, and
   download_html gave it a plain link instead of the button.  Everything
   below is behind that one test, so an unnarrated reader runs none of it.

   The size is asked for when the sheet OPENS and not before: a reader who
   never downloads pays nothing for it, and it is exactly the number a
   browser will let somebody start a 228 MB download without.               */
const DL_SHEET = `<div class="dlback"></div>
<div class="dlsheet" lang="en" dir="ltr" role="dialog" tabindex="-1"
     aria-label="download this edition">
  <div class="dlhead">download this edition<span class="sp"></span>
    <button type="button" class="dlx" title="close (Esc)">&times;</button></div>
  <a class="dlopt" href="../__download?audio=text">
    <b>the text alone</b>
    <span>The chapters, book.json and the source paragraphs &mdash; and nothing
      left pointing at a narration: no timings, no alignment review, and
      book.json saying this book has none. For somebody who has no use for the
      recording.</span>
    <span class="dlsz" data-shape="text"></span></a>
  <a class="dlopt" href="../__download?audio=linked">
    <b>everything but the recording</b>
    <span>The text, and the whole narration except the audio file itself: the
      timings, the review, book.json still naming them. Drop <code>audio/</code>
      back in and the book is whole again. For somebody who already has the
      recording &mdash; and the one to keep as a working copy.</span>
    <span class="dlsz" data-shape="linked"></span></a>
  <a class="dlopt" href="../__download?audio=full">
    <b>all of it</b>
    <span>The text, the narration and the recording itself &mdash; the book
      exactly as it stands here.</span>
    <span class="dlsz" data-shape="full">a recording may be hundreds of megabytes</span></a>
</div>`;
let dlOpen = false;
if (META.narration) {
  const dlBtn = document.querySelector('header .dl');
  const dlWrap = document.createElement('div');
  dlWrap.className = 'dlwrap';
  dlWrap.hidden = true;
  dlWrap.innerHTML = DL_SHEET;
  document.body.appendChild(dlWrap);
  const dlBox = dlWrap.querySelector('.dlsheet');
  let dlAsked = false;
  // asked once and kept: the recording does not change size while the page is
  // open, and the sentence the sheet is built with is the honest answer when
  // there is no server to ask -- opened off the disk, where the download
  // itself could not have worked either
  const dlSize = () => {
    if (dlAsked) return;
    dlAsked = true;
    fetch('__narration/status', {cache: 'no-store'})
      .then(r => r.json())
      .then(j => {
        if (!j.ok) return;
        const say = (shape, text) => {
          const e = dlWrap.querySelector('.dlsz[data-shape="' + shape + '"]');
          if (e) e.textContent = text;
        };
        // WHAT EACH SHAPE CARRIES, as the server sums it from what the
        // bundle will pack (bundle.payload): "all of it" is EVERY recording
        // under audio/, and a book read in nine parts is nine files.  This
        // used to be the size of the first recording, which on such a book
        // said 2 MB of a 76 MB zip.  A server from before that sum is asked
        // for the recordings it lists instead.
        const B = j.bundle || {};
        const full = B.full || (() => {
          const ns = (j.narrations || []).filter(n => n.exists);
          const b = ns.reduce((t, n) => t + (n.bytes || 0), 0);
          return {bytes: b, media: ns.length, media_bytes: b};
        })();
        if (B.text) say('text', 'about ' + nsize(B.text.bytes));
        if (B.linked) say('linked', 'about ' + nsize(B.linked.bytes));
        const which = full.media > 1 ? 'the ' + full.media + ' recordings' : 'the recording';
        say('full', !full.media
          ? 'the recording is not on this machine — so this one gives what the ' +
            'middle one gives'
          : 'about ' + nsize(full.bytes) + (full.media_bytes >= 0.8 * full.bytes
              ? ', nearly all of it ' + which
              : ', ' + nsize(full.media_bytes) + ' of it ' + which));
      })
      .catch(() => {});
  };
  const dlShow = on => {
    dlWrap.hidden = !on; dlOpen = on;
    dlBtn.classList.toggle('on', on);
    dlBtn.setAttribute('aria-expanded', on ? 'true' : 'false');
    // preventScroll for the reason the contents gives: the button is in a
    // fixed header, and focusing it would otherwise throw the page to the top
    if (on) { dlSize(); dlBox.focus({preventScroll: true}); }
    else dlBtn.focus({preventScroll: true});
  };
  dlBtn.onclick = () => dlShow(dlWrap.hidden);
  dlWrap.querySelector('.dlx').onclick = () => dlShow(false);
  dlWrap.querySelector('.dlback').addEventListener('click', () => dlShow(false));
  // the sheet has done its work the moment a choice is made; the click itself
  // is not touched, so the browser goes on to save the file
  dlBox.addEventListener('click', e => {
    if (e.target.closest('a.dlopt')) dlShow(false);
  });
  addEventListener('keydown', e => {
    if (dlOpen && e.key === 'Escape') { e.preventDefault(); dlShow(false); } });
}

/* ---------- writing a chunk ----------------------------------------------
   The book is written HERE, by somebody who knows the language, and the page
   already knows every chunk: data-c is the book-wide number __edit/chunk
   takes, and SRC[data-c] is what the .tex holds.  The boxes are filled from
   SRC and never from the page, because the vocabulary is LaTeX and the page
   shows the RENDERING of it: the gloss reads "آب āb water", and the line that
   made it is \dw{آب}{āb} water.  Only the second one can be edited.

   THE DOOR IS A PENCIL, AND IT IS ALWAYS THERE, as in the video player: the
   gloss cloud's, and the one over a chunk that opens no cloud (penAt, below),
   and E for whichever of the two the chunk under the pointer has.  A click
   on the chunk itself goes on doing what it did -- it plays, or opens the
   cloud -- so reading and writing are one page with no mode between them.

   THE THREE ANSWERS, each of which has to be seen: the edit was made (the
   page shows it at once, without a reload); it was refused (the server's
   sentence, whole -- it names the rule, and a fidelity refusal quotes the
   character that broke it); and the PDF is now behind the text, which the
   header says beside the build stamp, with the button that catches it up. */
const CH = {back: $('#chback'), box: $('#chbox'), ref: $('#chref'),
            fa: $('#chfa'), kana: $('#chkana'), tr: $('#chtr'),
            voc: $('#chvoc'), en: $('#chen'), now: $('#chnow'),
            free: $('#chfree'), stat: $('#chstat')};
/* THE PARAGRAPHS SOMEBODY HAS TAKEN CHARGE OF (reading.json, with the book).
   A paragraph in here is out of the source check: the editor writes an edit
   that departs from source/paras/ instead of refusing it, and verify_book.py
   reports it as not checked.  It is a paragraph's decision and not a chunk's,
   because the check joins every chunk under one \parnum before comparing. */
const FREESET = new Set(typeof FREE === 'undefined' ? [] : FREE);
// the paragraph a chunk sits in, as the build named it on the .para
function paraOfChunk(n) {
  const row = rowOf(n), p = row && row.closest ? row.closest('.para') : null;
  return (p && p.dataset.p) || '';
}
// chOpen is read by the player and by the contents, both of which stand back
// while a sheet is over the page -- the same courtesy ankiOpen and narrOpen get
let chOpen = false;
let chN = -1, chWas = null, chCol = '', chGlossed = true, chWasPlaying = false;
// the subparagraph (SUBS index) the open chunk is in: where the region sheet
// starts when it is opened from this one
let chSub = -1;

function srcOf(n) {
  const s = SRC[n] || ['', '', '', '', '', '', ''];
  return {col: s[0], fa: s[1], kana: s[2], tr: s[3], voc: s[4], en: s[5], words: s[6] || ''};
}
function setCol(c) {
  chCol = c;
  $$('#chcol .dbtn').forEach(b => b.classList.toggle('on', b.dataset.col === c));
}
// what the vocabulary line reads as: the build's own render_voc output,
// cloned out of the gloss.  Nothing in this page renders that field a second
// time -- two renderers of one field drift, and the author would be shown a
// preview the PDF disagrees with.
function paintVoc(n) {
  const row = rowOf(n), v = row ? row.querySelector('.gl .voc') : null;
  CH.now.innerHTML = v && v.innerHTML.trim() ? v.innerHTML
    : '<span class="none">no vocabulary line yet</span>';
}
// `warns`: what the checker says of the words without refusing them, each
// on a line of its own under the answer
function chSaid(main, fid, bad, warns) {
  CH.stat.textContent = main;
  CH.stat.className = bad ? 'bad' : '';
  (warns || []).forEach(w => {
    const s = document.createElement('span');
    s.className = 'warn'; s.textContent = '\n' + w;
    CH.stat.appendChild(s);
  });
  if (!fid) return;
  // verify_book's verdict on the paragraph, under the answer and quieter than
  // it: it is news about the chapter, not about the button just pressed
  const s = document.createElement('span');
  s.className = 'fid'; s.textContent = '\n' + fid;
  CH.stat.appendChild(s);
}

function openChunk(n, fromEl) {
  const row = rowOf(n);
  // \chp -- a colour and its text and no gloss at all -- is told apart by the
  // row the build wrote: a plain chunk has no .gl beside its text.  (A \ch
  // nobody has glossed yet has one, empty, and every slot to write in.)  The
  // sheet must not offer a slot the macro has not got, or the save is refused
  // for a field the author was invited to fill.
  chGlossed = !!(row && row.querySelector('.gl'));
  const sub = (fromEl && fromEl.closest ? fromEl.closest('.sub') : null)
              || (row ? row.closest('.sub') : null);
  const lab = sub ? sub.querySelector('.lab').textContent.trim() : '';
  chN = n;
  chSub = sub && sub.dataset.s != null ? +sub.dataset.s : -1;
  chWas = srcOf(n);
  setCol(chWas.col);
  CH.fa.value = chWas.fa; CH.kana.value = chWas.kana; CH.tr.value = chWas.tr;
  CH.voc.value = chWas.voc; CH.en.value = chWas.en;
  $('#chkanarow').hidden = !(LANG.reading && chGlossed);
  $('#chtrrow').hidden = !chGlossed;
  $('#chvocrow').hidden = !chGlossed;
  $('#chenrow').hidden = !chGlossed;
  $('#chplain').hidden = chGlossed;
  // \chp has no form with words, so it is offered none
  if (LANG.words) {
    $('#chwordsrow').hidden = !chGlossed;
    stripMake(chGlossed ? chWas.words : null);
    askPropose();
  }
  // the paragraph's own decision, shown on the chunk being written: a chunk
  // whose paragraph the page cannot name (one built before data-p) is offered
  // nothing rather than a box that would go nowhere
  const pk = paraOfChunk(n);
  $('#chfreerow').hidden = !pk;
  if (CH.free) CH.free.checked = !!pk && FREESET.has(pk);
  $('#chjoinp').hidden = n <= 0;
  CH.ref.textContent = (lab ? lab + ' · ' : '') + 'chunk ' + n;
  paintVoc(n);
  chSaid('', '', false);
  chDelState();
  chWasPlaying = !A.paused;
  if (!A.paused) A.pause();
  // the loop/continuous timer may already be armed; left alone it starts the
  // audio underneath the open sheet
  clearTimeout(waiting); waiting = null;
  closeCloud();
  CH.back.hidden = false; CH.box.hidden = false; chOpen = true;
  // the sidebar remembers whether it was open, and is filled for THIS chunk
  // -- and shown only for a chunk that has a gloss to write.  It used to be
  // shown whenever it had been left open, and filled only when the chunk was
  // glossed: a \chp opened after a glossed chunk sat under the PREVIOUS
  // chunk's sources, with its door (#chsrc) hidden and so no way to shut it.
  $('#chsrc').hidden = !chGlossed;
  if (sideLay()) sideFill(n); else sideGen++;
  CH.fa.focus();
}
function closeChunk() {
  if (!chOpen) return;
  sideGen++;              // a lookup still on its way is for a sheet now shut
  stripMake(null);        // and so is a proposal
  chOpen = false; CH.back.hidden = true; CH.box.hidden = true;
  if (chWasPlaying) A.play().catch(() => {});
  chWasPlaying = false;
}

/* THE PENCIL OVER A CHUNK THAT OPENS NO CLOUD.  Pass 1 in hover mode has the
   gloss cloud, and the cloud has a pencil; everywhere else a chunk wears its
   gloss in line and opens no cloud, so the chunk under the pointer gets a
   pencil of its own at its corner -- one button for the whole page, moved to
   whichever chunk the pointer is on, so the built page carries nothing new
   and the click that plays is left alone.  A touch screen has no pointer to
   follow: there the pencil goes to the chunk last tapped. */
const pen = $('#chpen');
let penFor = null, penTimer = null;
// the chunk a pencil is for: any chunk of any pass, but pass 1's in hover
// mode, whose cloud offers one already
function penHolder(t) {
  const el = t && t.closest ? t.closest('.pass [data-c]') : null;
  if (!el || (document.body.classList.contains('hovermode') && el.closest('.p1'))) return null;
  return el;
}
function penAt(el) {
  if (chOpen || ankiOpen) return;
  clearTimeout(penTimer); penTimer = null;
  penFor = el;
  pen.hidden = false;
  penPlace();
}
// at its chunk's corner -- and again at every scroll, so that it goes with the
// chunk and not stays where the chunk was; a chunk scrolled out of sight
// takes it away
function penPlace() {
  if (!penFor || pen.hidden) return;
  const r = penFor.isConnected ? penFor.getBoundingClientRect() : null;
  if (!r || r.bottom < 0 || r.top > innerHeight) { penOff(); return; }
  const row = penFor.classList.contains('row'), w = pen.offsetWidth, h = pen.offsetHeight;
  // inside a row's corner; over the end of a chunk set in running text
  pen.style.top = Math.max(0, row ? r.top + 3 : r.top - h + 2) + 'px';
  pen.style.left = Math.max(0, Math.min(innerWidth - w - 4, r.right - (row ? w + 4 : w / 2))) + 'px';
}
function penOff() {
  clearTimeout(penTimer); penTimer = null;
  penFor = null; pen.hidden = true;
}
document.addEventListener('mouseover', e => {
  if (!HOVER_OK) return;
  if (pen.contains(e.target)) { clearTimeout(penTimer); penTimer = null; return; }
  const el = penHolder(e.target);
  if (el) {
    if (el !== penFor || pen.hidden) penAt(el);
    else { clearTimeout(penTimer); penTimer = null; }
    return;
  }
  // a moment's grace, to get from the chunk onto the pencil
  if (penFor && !penTimer) penTimer = setTimeout(penOff, 300);
});
addEventListener('scroll', penPlace, {passive: true, capture: true});
document.addEventListener('click', e => {
  if (HOVER_OK || pen.contains(e.target)) return;
  const el = penHolder(e.target);
  if (el) penAt(el); else penOff();
});
pen.addEventListener('click', e => {
  e.preventDefault(); e.stopPropagation();
  const el = penFor;
  penOff();
  if (el) openChunk(+el.dataset.c, el);
});

// \dw and its neighbours by name: the arity is the part nobody remembers, and
// a \vb one argument short is a refusal rather than a gloss.
const VOC_SKEL = {dw: '\\dw{}{} ', pw: '\\pw{}', bw: '\\bw{}{}{}',
                  vb: '\\vb{}{}{}{}{}{}{}'};
function insertVoc(name) {
  const t = CH.voc, skel = VOC_SKEL[name];
  if (!skel) return;
  const a = t.selectionStart, b = t.selectionEnd;
  t.value = t.value.slice(0, a) + skel + t.value.slice(b);
  const caret = a + skel.indexOf('{') + 1;      // inside the first group
  t.focus(); t.setSelectionRange(caret, caret);
}

/* THE WORD LINE, for a language divided into words: the shared strip
   (Parseh.wordstrip) under the text box, checked against what the text box
   and the reading box hold -- so it is made again, keeping its line,
   whenever either of them changes.  Propose is offered once the server has
   said, a single time for the page, that it can propose at all. */
let chStrip = null, proposing = null, canPropose = false;
// null takes the strip away
function stripMake(value) {
  if (chStrip) { chStrip.destroy(); chStrip = null; }
  if (!LANG.words || value === null) return;
  const o = {lang: LANG, fa: CH.fa.value, value: value,
             reading: (LANG.reading ? CH.kana : CH.tr).value,
             reorders: !!META.reorders, door: 'book',
             // what the server said of the last save was about another line
             onchange: () => chSaid('', '', false)};
  if (canPropose)
    o.propose = () => fetch('__words/propose', {method: 'POST',
        headers: {'Content-Type': 'application/json'},
        // the reading box as it stands reads the proposed words
        body: JSON.stringify({text: CH.fa.value,
                              reading: (LANG.reading ? CH.kana : CH.tr).value})})
      .then(r => r.json()).then(j => {
        if (!j || !j.ok) throw new Error((j && j.error) || 'nothing could be proposed');
        return j.available ? (j.words || '') : '';
      });
  chStrip = Parseh.wordstrip(o);
  $('#chwords').appendChild(chStrip.el);
}
function askPropose() {
  if (proposing) return;
  proposing = fetch('__words/propose', {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text: ''})})
    .then(r => r.json()).then(j => { canPropose = !!(j && j.ok && j.available); })
    .catch(() => {})
    .then(() => {
      // the sheet it was asked for gets the button -- unless somebody is at
      // work in its strip, and then the next chunk opened has it
      if (canPropose && chStrip && !chStrip.el.contains(document.activeElement))
        stripMake(chStrip.value());
    });
}
if (LANG.words)
  [CH.fa, LANG.reading ? CH.kana : CH.tr].forEach(el => el.addEventListener('input', () => {
    if (chStrip) stripMake(chStrip.value());
  }));

// Only what the author actually altered is sent: an untouched field is not
// this edit's business, and a field the macro has no slot for is never one.
function chunkEdits() {
  const w = chWas, out = {};
  if (chCol !== w.col) out.col = chCol;
  if (CH.fa.value !== w.fa) out.fa = CH.fa.value;
  if (chGlossed) {
    if (LANG.reading && CH.kana.value !== w.kana) out.kana = CH.kana.value;
    if (CH.tr.value !== w.tr) out.tr = CH.tr.value;
    if (CH.voc.value !== w.voc) out.voc = CH.voc.value;
    if (CH.en.value !== w.en) out.en = CH.en.value;
    // The word line when it was changed -- and with any changed text of a
    // chunk that has a line or is being given one, changed or not: the
    // server holds the two together and refuses a text its words no longer
    // give back.  A chunk that had none and was given none sends nothing.
    if (chStrip) {
      const line = chStrip.value().trim() ? chStrip.value() : '';
      if (line.trim() !== w.words.trim() || ('fa' in out && (w.words.trim() || line)))
        out.words = line;
    }
  }
  return out;
}
function pdfStale() {
  const el = $('#pdfstale');
  el.textContent = 'PDF behind the text — build it';
  el.title = 'the reader was rebuilt with the edit, and the PDF is LaTeX: ' +
             'click to build it on the server (./build.sh ' + META.book + ')';
  el.style.cursor = 'pointer';
  el.onclick = () => buildThisBook();
  el.hidden = false;
}
// The book's name as the server names its builds on the activity list
// (serve.py activity_now: the transliterated title, else the title), so the
// pill says the same from the click on -- this page's own messages say "the
// PDF" and "the reader", which name no book.
function bookName() {
  return META.title_latin || META.title || META.book;
}
// The PDF built from the page: the server runs ./build.sh as a job
// (lib/bookbuild.py) and parseh.js polls it, the build's last line said in the
// edit strip as it goes.  A build already running is followed, not doubled.
function buildThisBook() {
  const msg = $('#editmsg');
  const say = (text, isErr) => {
    msg.textContent = text;
    msg.style.color = isErr ? 'var(--danger)' : '';
  };
  Parseh.buildBook('__build', 'the PDF', {
    book: bookName(), button: $('#buildbook'), say: say,
    done: () => { $('#pdfstale').hidden = true; say('the PDF and the reader are built'); },
  });
}
/* THE READER ALONE, without LaTeX.  Everything a page can do is written into
   it at build time -- the fold button, PARAS, FOLDED, the data-p on every
   paragraph -- so a book built before a feature simply has not got it, and an
   old edition is the common case.  bookbuild has always known this build
   (WAYS' "html", build.sh --html); no page ever asked for it, so the only way
   to a new reader was the PDF: two lualatex passes, and a TeX installation
   the machine may not have. */
function buildThisReader() {
  const msg = $('#editmsg');
  const say = (text, isErr) => {
    msg.textContent = text;
    msg.style.color = isErr ? 'var(--danger)' : '';
  };
  Parseh.buildBook('__build', 'the reader', {
    what: 'html', book: bookName(), button: $('#buildhtml'), say: say,
    done: () => say('the reader is rebuilt — reload the page to read it'),
  });
}
$('#buildhtml').onclick = () => buildThisReader();
/* THE CHUNK AS THE FILE NOW HOLDS IT, SHOWN.  Every door in this page that
   writes chunks ends in the same two steps -- save, delete gloss, undo delete,
   and the region sheet's fill, which writes many at once -- so the four
   cannot come to disagree about what the page shows afterwards:

     chTake         the record the server read back off the .tex (the one
                    __edit/chunk answers with, and the region fill answers
                    with for each chunk it wrote) goes into SRC, which every
                    sheet is filled from; and, when the chunk sheet is open on
                    that chunk, into its "as saved" copy, its colour and word
                    strip -- or, for a write that was about the gloss alone,
                    into the gloss boxes, leaving what is being typed in the
                    others where it is;
     repaintChunks  the chunks themselves, every pass of them, out of the
                    reader the server has just rebuilt.

   The endpoint rebuilt reader/index.html before it answered, so the file on
   disk already shows the edit and this page does not.  Take the chunk out of
   that file rather than re-rendering it here: every pass, the colour class and
   the rendered vocabulary arrive together, from the one renderer -- and the
   gloss cloud is read off the row each time it opens, so it follows. */
function chTake(n, c, gloss) {
  const w = {col: c.col || '', fa: c.fa || '', kana: c.kana || '', tr: c.tr || '',
             voc: c.voc || '', en: c.en || '', words: c.words || ''};
  SRC[n] = [w.col, w.fa, w.kana, w.tr, w.voc, w.en, w.words];
  if (!chOpen || chN !== n) return w;
  chWas = w;
  if (gloss) {
    CH.kana.value = w.kana; CH.tr.value = w.tr; CH.voc.value = w.voc; CH.en.value = w.en;
    // the strip keeps its line, and is checked again against the reading box
    // as it now stands
    if (chStrip) stripMake(chStrip.value());
  } else {
    setCol(w.col);
    if (chStrip) stripMake(w.words);
  }
  chDelState();
  return w;
}
// One chunk out of a parsed reader file into the page -> true; false when the
// file and the page disagree about it; null when it is not on the page at all
// -- a chapter not fetched yet, which will come from the rebuilt file when it
// is wanted, so there is nothing to paint.
function paintFrom(doc, n) {
  const live = document.querySelectorAll('[data-c="' + n + '"]');
  if (!live.length) return null;
  const fresh = doc.querySelectorAll('[data-c="' + n + '"]');
  if (fresh.length !== live.length) return false;
  // the lang with them: a pinyin reading pass says it is Latin letters on a
  // chunk its words draw, so a chunk given words gains it and one whose
  // words are taken off loses it
  // -- and the row's data-seed, the reading nobody wrote (tex2html.seeded),
  // which a write can give or take away and which "delete gloss" asks of it
  live.forEach((el, i) => { el.className = fresh[i].className;
                            el.innerHTML = fresh[i].innerHTML;
                            for (const a of ['lang', 'data-seed']) {
                              const v = fresh[i].getAttribute(a);
                              if (v === null) el.removeAttribute(a);
                              else el.setAttribute(a, v);
                            } });
  if (READINGS)
    live.forEach(el => { if (el.closest('.p1')) splitReadings(el.querySelectorAll('ruby')); });
  return true;
}
// -> the chunks of `ns` that are on the page and could not be shown there (a
// reload shows them)
async function repaintChunks(ns) {
  // each file fetched and parsed once, however many of its chunks changed:
  // the region sheet writes whole sentences at a time
  const byFile = new Map();
  for (const n of ns) {
    // the file this chunk's markup was built into: the one the SECTION it
    // stands in came from -- the page itself for the first chapter (and for
    // a book of one), else the chapter file fetched into it, which is a
    // fraction of the page to fetch and to parse.  Asked of the section and
    // not of the chapter's number: a chapter written across two .tex files
    // is two sections wearing one number, each built into a file of its
    // own, and the number found only the first.  A chunk not on the page is
    // in a chapter not fetched yet -- it will come from the rebuilt file
    // when it is wanted, so there is nothing to paint.
    const live = document.querySelector('section.chapter [data-c="' + n + '"]');
    if (!live) continue;
    const f = live.closest('section.chapter').dataset.from || 'index.html';
    if (!byFile.has(f)) byFile.set(f, []);
    byFile.get(f).push(n);
  }
  const missed = [];
  let any = false;
  for (const [file, list] of byFile) {
    let doc = null;
    try {
      const r = await fetch(file, {cache: 'no-store'});
      if (r.ok) doc = new DOMParser().parseFromString(await r.text(), 'text/html');
    } catch (_) { doc = null; }
    for (const n of list) {
      const got = doc ? paintFrom(doc, n) : false;
      if (got === false) missed.push(n);
      else if (got) any = true;
    }
  }
  // and what the page did to the chunks when it loaded, done again: without
  // it a saved Japanese chunk wore one ruby over the whole of it until the
  // next reload, and a worded one showed the readings of words it knows
  if (READINGS && any) READINGS.apply();
  return missed;
}
async function repaintChunk(n) { return !(await repaintChunks([n])).length; }
// One chunk's fields through __edit/chunk -> the server's answer, or, when
// nothing answered at all, {ok: false} with the sentence that says so.
// Relative, like __save/ and __narration/: the reader is served from
// /books/<folder>/<slug>/reader/, and the path is how the server knows which
// book the edit belongs to.
async function chPost(n, fields) {
  try {
    const r = await fetch('__edit/chunk', {method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({index: n, fields})});
    return await r.json();
  } catch (err) {
    // Nothing answered at all -- this page opened off the disk, or a serve.py
    // still running the code it was started with.  Nothing was written, and
    // saying which is the difference between a retry and a restart.
    return {ok: false, error: 'the server did not answer (' + (err.message || err) +
            ') — an edit needs this page served by python3 serve.py; nothing was written'};
  }
}
// what a write says after its own words: the PDF now behind the text (the
// header says that), a reader that would not rebuild, or a chunk the page
// could not show
function chAfter(j, shown) {
  if (j.pdf_stale) pdfStale();
  if (j.reader && !j.reader.ok)
    return '\nthe .tex is written, but the reader would not rebuild: ' +
           (j.reader.error || 'no reason given');
  return shown ? '' : ' — reload to see it on the page';
}

async function saveChunk() {
  if (chN < 0) return;
  const n = chN, fields = chunkEdits();
  // THE PARAGRAPH'S DECISION GOES FIRST, and separately: it is not a field of
  // the chunk (texwrite refuses a field it does not know, and an edit that
  // changes nothing else never reaches the file at all), and the edit below
  // may be the very one this mark permits.
  const pk = paraOfChunk(n);
  const wantFree = !!(CH.free && CH.free.checked);
  const freeMoved = !!pk && wantFree !== FREESET.has(pk);
  if (!Object.keys(fields).length && !freeMoved) {
    chSaid('nothing to change — the boxes still say what the file says', '', false);
    return;
  }
  chSaid('saving…', '', false);
  if (freeMoved) {
    try {
      const rr = await fetch('__reading/free', {method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({para: pk, on: wantFree})});
      const jj = await rr.json();
      if (!jj.ok) { chSaid(jj.error || 'the mark was refused', '', true); return; }
      if (wantFree) FREESET.add(pk); else FREESET.delete(pk);
    } catch (err) {
      chSaid('the server did not answer (' + (err.message || err) + ') — nothing '
             + 'was written', '', true);
      return;
    }
    if (!Object.keys(fields).length) {
      chSaid(wantFree
        ? 'paragraph ' + pk + ' may now depart from its source'
        : 'paragraph ' + pk + ' is checked against its source again', '', false);
      return;
    }
  }
  const j = await chPost(n, fields);
  // A refusal is a sentence written to be read: the rule it broke, and for a
  // fidelity refusal the character and the two texts either side of it.  Show
  // it whole -- shortened to "failed" it says nothing anybody can act on.
  if (!j.ok) { chSaid(j.error || 'the edit was refused', '', true); return; }
  // the chunk read back off the file it was just written into, so the sheet
  // and SRC hold what is there rather than what was typed
  const changed = j.changed || [];
  chTake(n, j.chunk || {}, false);
  const shown = changed.length ? await repaintChunk(n) : true;
  if (chOpen && chN === n) { paintVoc(n); chDelState(); }
  const msg = (changed.length
    ? 'saved ' + changed.join(', ') + ' into ' + (j.file || 'the chapter')
    : 'nothing changed — the file already said that') + chAfter(j, shown);
  chSaid(msg, j.fidelity, false, j.warnings);
}

/* DELETE A GLOSS, AND TAKE THE DELETE BACK.  One press empties the chunk's
   transliteration, vocabulary and meaning, and its reading where it has one,
   through the door a save goes through: texwrite lets every box of a gloss be
   emptied at once -- it refuses emptying ONE box a language requires, which
   would leave half a gloss -- and what is left is a chunk nobody has glossed
   yet, which the checkers count and do not complain of.  The text, the colour
   and the word line stay, and so does the macro: a \chw keeps its words, and
   a \chp has no gloss to delete and is not offered the button.

   NO QUESTION FIRST, BECAUSE THERE IS AN ANSWER AFTER.  The gloss as it was
   is kept in this page, and "undo delete" writes it back through the same
   door, where filling boxes is never refused.  In a Map and not in storage,
   until the page is reloaded: an undo that outlived the page would be offered
   against a file that may have been rewritten since.  Keyed by the chunk's
   number AND its text, because dividing renumbers every chunk after it, and a
   number alone could put one chunk's gloss back onto another.  Reopening the
   sheet on the chunk later offers it again; the region sheet's fill does not
   touch it (an LLM's gloss can be undone into the one that was deleted).

   A GLOSS IS WHAT SOMEBODY WROTE.  In a language divided into words a draft
   gives each chunk its reading from its word line, and while it still says
   exactly that nobody wrote it: the checkers and the edit door count the
   chunk as unglossed, and so does this button -- greyed out, rather than
   offering to delete a proposal that the region prompt would otherwise
   send.  The build marks the row of such a chunk with that reading
   (data-seed, tex2html.seeded, from lib/wordline.py's own seed), and a write
   brings the mark up to date with the rest of the row (paintFrom).  Asked
   of the whole chunk only: beside anything else written, the reading is the
   chunk's own, and a delete takes it off with the rest. */
const chUndo = new Map();
const GLOSS_FIELDS = ['kana', 'tr', 'voc', 'en'];
const undoKey = (n, fa) => n + '\u0001' + fa;
// the field a word line's reading goes in: kana, or tr where that is the
// only reading the language has (wordline.seed)
const SEED_FIELD = LANG.words ? (LANG.reading ? 'kana' : 'tr') : '';
function hasGloss(w, n) {
  if (!w) return false;
  const row = SEED_FIELD ? rowOf(n) : null;
  const seed = (row && row.dataset.seed) || '';
  return GLOSS_FIELDS.some(f => {
    const v = (w[f] || '').trim();
    return v !== '' && !(f === SEED_FIELD && seed && v === seed);
  });
}
// the two buttons follow the chunk AS SAVED, not the boxes: delete for a
// chunk with a gloss to delete, undo whenever this page holds a gloss deleted
// from this very chunk.  Asked again once a write has repainted the row,
// whose data-seed is part of the answer.
function chDelState() {
  const del = $('#chdel'), undo = $('#chundo');
  del.hidden = !chGlossed;
  del.disabled = !hasGloss(chWas, chN);
  undo.hidden = !chGlossed || !chWas || !chUndo.has(undoKey(chN, chWas.fa));
}
async function deleteGloss() {
  if (chN < 0 || !chGlossed || !hasGloss(chWas, chN)) return;
  const n = chN, was = chWas;
  // the reading only where the chunk holds one: a macro without the slot is
  // refused a kana, even an empty one
  const fields = {tr: '', voc: '', en: ''};
  if (LANG.reading && was.kana.trim()) fields.kana = '';
  chSaid('deleting the gloss…', '', false);
  const j = await chPost(n, fields);
  if (!j.ok) { chSaid(j.error || 'the delete was refused', '', true); return; }
  const now = chTake(n, j.chunk || {}, true);
  chUndo.set(undoKey(n, now.fa), {kana: was.kana, tr: was.tr, voc: was.voc, en: was.en});
  if (chOpen && chN === n) chDelState();
  const shown = (j.changed || []).length ? await repaintChunk(n) : true;
  if (chOpen && chN === n) { paintVoc(n); chDelState(); }
  chSaid('gloss deleted' + chAfter(j, shown), '', false, j.warnings);
}
async function undoDelete() {
  if (chN < 0 || !chWas) return;
  const n = chN, key = undoKey(n, chWas.fa), old = chUndo.get(key);
  if (!old) return;
  // every box as it was -- a box that was empty then and is empty now is
  // left out, since a chunk without a reading slot is refused even an empty kana
  const fields = {tr: old.tr, voc: old.voc, en: old.en};
  if (LANG.reading && (old.kana.trim() || chWas.kana.trim())) fields.kana = old.kana;
  chSaid('writing the gloss back…', '', false);
  const j = await chPost(n, fields);
  if (!j.ok) { chSaid(j.error || 'the gloss could not be written back', '', true); return; }
  chUndo.delete(key);
  chTake(n, j.chunk || {}, true);
  if (chOpen && chN === n) chDelState();
  const shown = (j.changed || []).length ? await repaintChunk(n) : true;
  if (chOpen && chN === n) { paintVoc(n); chDelState(); }
  chSaid('the deleted gloss is written back' + chAfter(j, shown), '', false, j.warnings);
}

$('#chcancel').onclick = closeChunk;
$('#chsave').onclick = saveChunk;
$('#chdel').onclick = deleteGloss;
$('#chundo').onclick = undoDelete;
$('#chrevert').onclick = () => {
  if (!chWas) return;
  setCol(chWas.col);
  CH.fa.value = chWas.fa; CH.kana.value = chWas.kana; CH.tr.value = chWas.tr;
  CH.voc.value = chWas.voc; CH.en.value = chWas.en;
  if (chStrip) stripMake(chWas.words);
  // the box too, or a tick left standing would be sent with the next save
  const pk = paraOfChunk(chN);
  if (CH.free) CH.free.checked = !!pk && FREESET.has(pk);
  chSaid('back to what the file holds', '', false);
};
// The region sheet, opened on this chunk's sentence.  The chunk sheet makes
// way for it -- two sheets over one page is one too many -- and hands it the
// recording it paused, so it is closing the region sheet that puts it back
// on.  Edits not saved yet are not thrown away by the way: they are said --
// AND THE PARAGRAPH'S "need not reproduce source/paras/" BOX IS ONE OF THEM.
// chunkEdits() reads the chunk's own boxes only; saveChunk counts that box
// moved as an edit of its own (freeMoved), and openChunk sets it back from
// FREESET, so a tick not saved was lost here without a word.  Weighed the
// way saveChunk weighs it.
$('#chrgn').onclick = () => {
  const pk = paraOfChunk(chN);
  const freeMoved = !!pk && !!(CH.free && CH.free.checked) !== FREESET.has(pk);
  if (Object.keys(chunkEdits()).length) {
    chSaid('these boxes hold changes not saved yet — save them, or revert them, first',
           '', true);
    return;
  }
  if (freeMoved) {
    chSaid('the “need not reproduce source/paras/” box is changed and not saved yet — ' +
           'save it, or revert it, first', '', true);
    return;
  }
  const at = chSub, playing = chWasPlaying;
  chWasPlaying = false;
  closeChunk();
  rgOpen(true, at >= 0 ? at : null, playing);
};
$$('#chcol .dbtn').forEach(b => { b.onclick = () => setCol(b.dataset.col); });
$$('#chins .dbtn').forEach(b => { b.onclick = () => insertVoc(b.dataset.ins); });

/* ---------- a stretch of the book glossed by an LLM -----------------------
   The chunk sheet writes one chunk by hand; this sheet writes many from a
   chatbot's answer.  Three steps, each a button of its own: PICK a stretch
   -- the outline every stretch of this book is picked from, at the depth of a
   sentence (a subparagraph, one \parnum): click, shift-click, or "stretch it
   to…"; COPY THE PROMPT, which the server writes -- the chunks of those
   sentences as they stand in the .tex, each marked to be glossed or sent as
   it is -- and the page puts on the clipboard; and, once the chatbot has
   answered, FILL FROM THE ANSWER.

   THE PAGE DECIDES NOTHING ABOUT WHAT MAY BE WRITTEN.  lib/glossregion.py
   works that out when the answer lands, from the chapter files as they are
   then: a chunk somebody has glossed is kept unless re-gloss is ticked; a
   chunk whose text is not what the page shows, or that the answer divides
   differently, or that it would leave half glossed, is dropped and listed; a
   paragraph folded away is never written; and every chunk that does go in
   goes in through texwrite.edit_chunk, the chunk sheet's own door.  What the
   page does is send the stretch and the two boxes as they stand when fill is
   pressed, show the server's words whole, and paint what was written where it
   is -- with no reload, which would lose the answer box and every "undo
   delete" this page is holding.

   The stretch goes to the server as the book-wide chunk numbers the chunk
   sheet uses (data-c): the first chunk of the first sentence picked and the
   last of the last, read off the .sub elements -- which is why a chapter
   still in its own file is fetched first.  The server widens a pick to whole
   sentences in any case, and says in words what it took.                  */
let rgShown = false, rgWasPlaying = false, rgWasWaiting = false;
let rgPicker = null;
function rgPick() {
  if (rgPicker) return rgPicker;
  rgPicker = outlinePicker({
    depth: 'sub', label: 'the sentences of the book',
    // a folded paragraph may be picked across, and says what becomes of it
    tags: row => {
      const ps = olParas(row).filter(p => p.pkey);
      const n = ps.filter(p => foldedRun(p.pkey)).length;
      if (!n) return [];
      return [[row.kind === 'p' || row.kind === 's' || n === ps.length ? 'folded' : n + ' folded',
               'olfold', 'folded away in the book: left out of the prompt and of the fill']];
    },
    onChange: rgState,
  });
  $('#rgpick').appendChild(rgPicker.el);
  return rgPicker;
}
const rgFlags = () => ({regloss: $('#rgregloss').checked, perfield: $('#rgperfield').checked});
const rgN = (k, one, many) => k + ' ' + (k === 1 ? one : many);
// THE ROW OF CONTROLS AROUND THE PROMPT (lib/llmrow.js) asks for the prompt
// as soon as a stretch is picked, to say its size before the copy, and HOLDS
// it: a browser that refuses a copy made after a round trip to the server
// allows one made inside the press itself, before anything is awaited --
// Safari refuses the first press every time, so on an iPad the press used to
// fail and the prompt was shown in a box.  Only for the same stretch and the
// same two boxes, and only while nothing can have changed what it was made
// from: the pick or a box changing lets it go, so does the sheet closing
// (nothing else in this page that writes a chunk -- the chunk sheet with its
// save, delete, undo and divide -- can open under it), and so does a fill
// that wrote something.  Held any longer, a gloss deleted since would go out
// as context with its old words -- and an answer that echoes them back would
// write the deleted gloss in again.  A page without the row's script has no
// copy button and says so.
let rgMade = [], rgByHand = false;
const rgRow = window.ParsehLLMRow ? ParsehLLMRow.mount($('#rgrow'), {
  surface: 'book-region', cls: {copy: 'primary'},
  // THE OPTIONS OF THE PROMPT (the scheme of the transliteration, the short vowels) are asked of the
  // server for this book's language, and start from what the book's own record says of them
  lang: LANG.code, book: (/^(\/books\/[^\/]+\/[^\/]+)\//.exec(location.pathname) || [])[1],
  setFact: (name, value) => rgSetFact(name, value),
  ids: {copy: 'rgcopy', size: 'rgsize', say: 'rgcopysay', hand: 'rgout', handRow: 'rgoutrow'},
  remind: 'paste it into a chatbot, then paste its whole answer into the box below.',
  getText: () => rgText(), onCopied: (ok, text) => rgCopied(ok, text),
  // a press: what was said of the last one is not about this one, and a
  // confirmation to replace glosses was about what was counted
  onPress: () => { rgDisarm(); rgSum('', false); },
  onError: (e, which, press) => { if (press) rgSum(e.message, true); },
  measure: () => rgShown && !!(rgPicker && rgPicker.get())
}) : (() => {
  $('#rgrow').textContent = 'the prompt helper could not be loaded';
  const no = () => {};
  return {update: no, forget: no, invalidate: no, disable: no, enable: no};
})();
function rgDrop() {
  rgMade = [];
  rgRow.invalidate();
  if (!rgByHand) return;
  rgByHand = false;
  rgSum('', false);                 // the line said it was in the box below
}
function rgState() {
  const p = rgPicker && rgPicker.get();
  if (p) rgRow.enable(); else rgRow.disable('pick a stretch of the book first');
  $('#rgfill').disabled = !p;
  // a confirmation is for what was counted, and that has just changed
  rgDisarm();
  // and so is a prompt made for the stretch and the boxes as they were
  rgDrop();
}
// the stretch picked, as the chunk numbers the server takes -> {first, last},
// or null when it holds none
async function rgRange() {
  const p = rgPicker && rgPicker.get();
  if (!p) return null;
  for (const ci of new Set([chapOfSub(p.lo), chapOfSub(p.hi)])) await needChapters(ci);
  const a = document.querySelector('.sub[data-s="' + p.lo + '"]');
  const b = document.querySelector('.sub[data-s="' + p.hi + '"]');
  if (!a || !b) return null;
  const first = +a.dataset.from, last = +b.dataset.to;
  return Number.isInteger(first) && Number.isInteger(last) && first >= 0 && last >= first
    ? {first, last} : null;
}
// A CHOICE MADE AGAINST THE BOOK'S OWN RECORD may be made the book's (the row offers the button):
// written through the door the book's info sheet uses, which says in words why when it refuses
async function rgSetFact(name, value) {
  const r = await fetch('__edit/meta', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                        body: JSON.stringify({fields: {[name]: value}})});
  const j = await r.json();
  if (!j.ok) throw new Error(j.error || 'the edit was refused');
}
// relative, like __edit/chunk: the path says which book
async function rgPost(what, body) {
  try {
    const r = await fetch('__region/' + what, {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    return await r.json();
  } catch (err) {
    return {ok: false, error: 'the server did not answer (' + (err.message || err) +
            ') — this needs the page served by python3 serve.py; nothing was ' +
            (what === 'apply' ? 'written' : 'copied')};
  }
}
// one entry of kept, dropped, unanswered or notes, in words
function rgLine(e) {
  if (typeof e === 'string') return e;
  const why = e.why || e.note || '';
  return (e.where || '') + (why ? ' — ' + why : '');
}
// the line under "copy the prompt", and the server's notes under it
function rgSum(text, bad, notes) {
  const el = $('#rgsum');
  el.textContent = text;
  el.classList.toggle('bad', !!bad);
  for (const n of notes || []) {
    const s = document.createElement('span');
    s.className = 'rgnote';
    s.textContent = rgLine(n);
    el.appendChild(s);
  }
}
// what the prompt holds, in the server's words and counts
function rgSummary(j) {
  const parts = [j.region || ''];
  let much = rgN(j.chunks || 0, 'chunk', 'chunks') + ', ' + (j.fill || 0) + ' to gloss';
  if (j.glossed) much += ', ' + j.glossed + ' glossed sent as context';
  parts.push(much);
  // the region's words say how many folded paragraphs were left out; said
  // here only if they did not
  if (j.folded && !/folded/.test(j.region || ''))
    parts.push(rgN(j.folded, 'folded paragraph', 'folded paragraphs') + ' left out');
  // with nothing to gloss nothing is copied, and the server's note says why;
  // that the prompt reached the clipboard, or is below to copy by hand, is the
  // row's to say
  rgSum(parts.filter(Boolean).join(' · ') + (j.fill ? '' : '\nnothing was copied'),
        false, j.notes);
}
// THE PROMPT FOR WHAT IS PICKED NOW, made by the server -- a stretch with
// nothing to gloss gives the row an empty text, and nothing is copied
async function rgText() {
  const p = rgPicker && rgPicker.get();
  if (!p) return '';
  const range = await rgRange();
  // the prompt of the person's own that the menu in the row chose goes with this request, and only with it: the
  // answer is read the same way whoever wrote the prompt
  const own = rgRow.promptId && rgRow.promptId() ? {prompt: rgRow.promptId()} : {};
  const j = range ? await rgPost('prompt', Object.assign(range, rgFlags(), rgRow.options ? rgRow.options() : {}, own))
                  : {ok: false, error: 'what is picked holds no chunk to send'};
  // a refusal is the server's sentence, shown as it came
  if (!j.ok) throw new Error(j.error || 'the prompt was refused');
  const text = j.fill ? j.prompt : '';
  // THE SHORT REQUEST for a chat that has the skill is made with the prompt: the row holds it beside it
  if (rgRow.skillOf) rgRow.skillOf(j.fill ? j.skill : null);
  // by its text, since two askings can overlap and be answered out of order
  rgMade.push({j, text});
  if (rgMade.length > 4) rgMade.shift();
  return text;
}
// after a press: what was made of the text that was copied, and whether it reached the clipboard
function rgCopied(ok, text) {
  const made = rgMade.filter(m => m.text === text).pop();
  if (!made) return;
  rgByHand = ok === false;
  rgSummary(made.j);
}
/* THE CONFIRMATION, for a re-gloss that would replace what somebody wrote.
   The server counts first and writes nothing; the button then says how many
   and waits four seconds for a second press, as "discard edits" and "stop
   server" do.  Anything that changes what was counted -- the answer, the
   pick, either box -- takes the arm off. */
let rgArmed = false, rgArmTimer = null;
function rgDisarm() {
  clearTimeout(rgArmTimer); rgArmTimer = null;
  rgArmed = false;
  const b = $('#rgfill');
  b.textContent = 'fill from the answer';
  b.classList.remove('armed');
}
function rgArm(n) {
  const b = $('#rgfill');
  rgArmed = true;
  b.textContent = 'replace ' + (n === 1 ? '1 gloss' : n + ' glosses') + ' — press again';
  b.classList.add('armed');
  clearTimeout(rgArmTimer);
  rgArmTimer = setTimeout(rgDisarm, 4000);
}
// the report area: a sentence, and under it a list for each kind of chunk
// that did not go in as asked
function rgSay(text, bad) {
  const box = $('#rgreport');
  box.textContent = '';
  const s = document.createElement('div');
  s.className = 'rgsaid' + (bad ? ' bad' : '');
  s.textContent = text;
  box.appendChild(s);
  $('#rgreprow').hidden = false;
  return box;
}
function rgList(box, list, head) {
  if (!list || !list.length) return;
  const d = document.createElement('details');
  d.open = list.length <= 6;
  const s = document.createElement('summary');
  s.textContent = head + ' (' + list.length + ')';
  d.appendChild(s);
  const ul = document.createElement('ul');
  for (const e of list) {
    const li = document.createElement('li');
    if (typeof e === 'string') li.textContent = e;
    else {
      // the address in the book's own digits and the text in its own
      // script, isolated so a right-to-left chunk cannot reorder the line
      const w = document.createElement('bdi');
      w.textContent = e.where || '';
      const why = document.createElement('span');
      why.className = 'why';
      why.textContent = (e.why || e.note) ? ' — ' + (e.why || e.note) : '';
      li.append(w, why);
    }
    ul.appendChild(li);
  }
  d.appendChild(ul);
  box.appendChild(d);
}
function rgReport(j, missed) {
  let text = j.region ? j.region + '\n' : '';
  if (j.confirm_needed) {
    text += rgN(j.replace || 0, 'existing gloss', 'existing glosses') + ' will be replaced' +
      (j.fill ? ', and ' + rgN(j.fill, 'blank chunk', 'blank chunks') + ' filled' : '') +
      ' — press the button again to write them; nothing has been written yet';
  } else {
    text += 'filled ' + (j.filled || 0) + ' · completed ' + (j.completed || 0) +
            ' · replaced ' + (j.replaced || 0) + (j.marks ? ' · vowelled ' + (j.vowelled || 0) : '');
    if (!j.wrote) text += ' — nothing was written';
    if (j.reader && !j.reader.ok)
      text += '\nthe .tex files are written, but the reader would not rebuild: ' +
              (j.reader.error || 'no reason given');
    else if (missed.length)
      text += '\n' + rgN(missed.length, 'chunk', 'chunks') + ' could not be shown here — '
              + 'reload to see ' + (missed.length === 1 ? 'it' : 'them');
  }
  const box = rgSay(text, false);
  // KEPT IS NOT "ALREADY GLOSSED".  The server lists here every chunk whose
  // answer tried to change something an answer may not: a gloss already
  // there, and also the word line, the colour, a note, a plain chunk
  // (glossregion._decided) -- which a chunk it has just FILLED can be listed
  // for, when the answer tidied its word line too.  Headed "already glossed",
  // the report said "filled 3" and called one of the three untouched; each
  // row's own why says which case it is.
  rgList(box, j.kept, 'kept — what the answer tried to change and may not (a gloss already ' +
         'there, a word line, a colour, a note, the free mark, a plain chunk), left as it is');
  rgList(box, j.dropped, 'dropped — not written');
  rgList(box, j.unanswered, 'unanswered — the prompt asked for them, and the answer gave nothing');
  rgList(box, j.notes, 'notes');
}
async function rgFill() {
  const confirm = rgArmed;
  rgDisarm();
  // the two boxes as they are NOW decide, and the stretch picked now
  const flags = rgFlags(), answer = $('#rgans').value;
  if (!answer.trim()) {
    rgSay('paste the LLM’s answer into the box first', true);
    $('#rgans').focus();
    return;
  }
  const btn = $('#rgfill');
  btn.disabled = true;
  rgSay(confirm ? 'replacing…' : 'reading the answer…', false);
  const range = await rgRange();
  // THE SHORT VOWELS the row shows now go with the answer as they went with the prompt: whether the
  // answer's `fa` may be written is the server's to decide, from this word and the language's record
  const marks = rgRow.options ? rgRow.options().marks : undefined;
  const j = range ? await rgPost('apply', Object.assign(range, flags, {answer, confirm}, marks ? {marks} : {}))
                  : {ok: false, error: 'what is picked holds no chunk to fill'};
  btn.disabled = !(rgPicker && rgPicker.get());
  if (!j.ok) { rgSay(j.error || 'the answer was refused', true); return; }
  if (j.confirm_needed) {
    rgReport(j, []);
    rgArm(j.replace || 0);
    btn.focus();
    return;
  }
  // a prompt still held was made before these chunks were written
  if (j.wrote) rgDrop();
  // what was written, taken into the page and painted where it stands
  const recs = j.chunks || {};
  const ns = Object.keys(recs).map(Number).filter(n => Number.isInteger(n) && n >= 0);
  ns.forEach(n => chTake(n, recs[n], true));
  const missed = ns.length ? await repaintChunks(ns) : [];
  if (j.pdf_stale) pdfStale();
  rgReport(j, missed);
}
/* Open and close the way the fold sheet does: the cloud goes, the recording
   stops and is put back on when the sheet closes, the player's keys stand
   down while it is up, Escape closes it, and the form never submits. */
function rgOpen(on, at, playing) {
  // a prompt held by the row is for this opening of the sheet only: with it
  // closed, a chunk may be saved, deleted or undone (rgMade)
  rgDrop();
  rgShown = !!on;
  $('#rgback').hidden = !on;
  $('#rgbox').hidden = !on;
  if (on) {
    closeCloud();
    rgWasPlaying = playing !== undefined ? !!playing : !A.paused;
    rgWasWaiting = waiting != null;
    if (!A.paused) A.pause();
    clearTimeout(waiting); waiting = null;
    const pk = rgPick();
    const had = pk.get();
    pk.load();
    // where it starts: the chunk's own sentence when the chunk sheet opened
    // it; else what was picked when it last closed -- a prompt for it may be
    // out with a chatbot -- and else the sentence being read
    if (at != null && at >= 0 && at < SUBS.length) pk.set(at, at);
    else if (had) pk.set(had.lo, had.hi);
    else if (cur >= 0 && cur < SUBS.length) pk.set(cur, cur);
    rgState();
    pk.focus();
  } else {
    rgDisarm();
    const wasPlaying = rgWasPlaying, wasWaiting = rgWasWaiting;
    rgWasPlaying = rgWasWaiting = false;
    if (wasPlaying) A.play().catch(() => {});
    else if (wasWaiting && cur >= 0) playSub(cur, false);
  }
}
$('#rgn').onclick = () => rgOpen($('#rgbox').hidden);
$('#rgcancel').onclick = () => rgOpen(false);
$('#rgclose').onclick = () => rgOpen(false);
$('#rgback').onclick = () => rgOpen(false);
$('#rgfill').onclick = () => rgFill();
$('#rgregloss').addEventListener('change', rgState);
$('#rgperfield').addEventListener('change', rgState);
$('#rgans').addEventListener('input', rgDisarm);
// Ctrl+Enter in the answer box fills, as it saves in the chunk sheet
$('#rgans').addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    if (!$('#rgfill').disabled) rgFill();
  }
});
$('#rgbox').addEventListener('submit', e => e.preventDefault());
addEventListener('keydown', e => {
  if (rgShown && e.key === 'Escape') { e.preventDefault(); rgOpen(false); } });

/* ---------- the sources sidebar -------------------------------------------
   THE SAME THREE THINGS THE READER'S PANEL SHOWS, where the gloss is
   actually written.  Reading them in the cloud and then retyping them into
   the sheet was the whole of the work, and retyping is where a romanisation
   loses a macron.  So each line carries the buttons that put it into a
   field.

   IT WRITES INTO A BOX AND NEVER INTO THE BOOK.  Everything here lands in
   the sheet's own fields, unsaved, for somebody to correct before they press
   save -- the dictionary does not know which sense this sentence wants, the
   model is a machine, and the corpus is somebody else's sentence.  Closed by
   default, and the choice is remembered.                                   */
const SIDE_KEY = MINE('chside');
let sideOn = localStorage.getItem(SIDE_KEY) === '1';
// WHICH FILL IS THE LIVE ONE.  A lookup is a round trip, and the sidebar can
// be refilled before it comes back -- shut and opened again, or chunk A
// closed and chunk B opened -- and the answer used to land in whatever the
// sidebar held by then: chunk A's corpus sentences appended under chunk B's,
// another heading under the next chunk's. Every fill takes a number, and
// an answer whose number is no longer the current one is dropped.
let sideGen = 0;

// Shown, and the sheet widened for it, only while it is wanted AND the chunk
// has a gloss to write into; returns which, so a caller knows to fill it.
function sideLay() {
  const on = sideOn && chGlossed;
  $('#chside').hidden = !on;
  CH.box.classList.toggle('side', on);
  $('#chsrc').classList.toggle('on', sideOn);
  return on;
}
// the width under which the sheet stacks the column below the fields -- the
// same 820px as the @media rule that does the stacking
const SIDE_NARROW = matchMedia('(max-width: 820px)');
function sideShow(on) {
  sideOn = on;
  localStorage.setItem(SIDE_KEY, on ? '1' : '0');
  if (sideLay() && chN >= 0) {
    sideFill(chN);
    // Stacked under the fields, the column opens below the fold, and a door
    // that opens onto nothing visible reads as a door that did nothing: on
    // a phone the press scrolls the sheet down to what it opened.  Only the
    // press -- a chunk opened with the column remembered starts at its box.
    if (SIDE_NARROW.matches)
      CH.box.scrollTo({top: Math.max(0, $('#chside').offsetTop - 8), behavior: 'smooth'});
  } else sideGen++;
}
$('#chsrc').onclick = () => sideShow(!sideOn);

// append rather than replace: a vocabulary line is built up entry by entry,
// and a meaning is often two of these joined
function put(el, text, sep) {
  if (!text) return;
  const had = el.value.trim();
  el.value = had ? had + (sep === undefined ? ' ' : sep) + text : text;
  el.dispatchEvent(new Event('input', {bubbles: true}));
  el.focus();
  el.setSelectionRange(el.value.length, el.value.length);
}

function sideBtn(row, label, title, fn) {
  const b = document.createElement('button');
  b.type = 'button'; b.textContent = label; b.title = title;
  b.onclick = (e) => { e.preventDefault(); fn(); };
  row.appendChild(b);
  return b;
}

// `more` is a line under the sub-line: a verb's principal parts
function sideRow(into, main, sub, more) {
  const d = document.createElement('div');
  d.className = 'srow';
  const t = document.createElement('div');
  t.className = 'stxt';
  if (typeof main === 'string') t.textContent = main; else t.appendChild(main);
  d.appendChild(t);
  if (sub) {
    const u = document.createElement('div');
    u.className = 'ssub'; u.textContent = sub;
    d.appendChild(u);
  }
  if (more) {
    const v = document.createElement('div');
    v.className = 'svb';
    if (typeof more === 'string') v.textContent = more; else v.appendChild(more);
    d.appendChild(v);
  }
  const put = document.createElement('div');
  put.className = 'sput';
  d.appendChild(put);
  into.appendChild(d);
  return put;
}

// the word of the chunk's word line the rows under it were asked for
function sideWord(into, at) {
  const d = document.createElement('div');
  d.className = 'sword'; d.setAttribute('lang', LANG.code);
  d.textContent = at[0];
  if (at[1]) { d.appendChild(document.createTextNode(' ')); d.appendChild(readingSpan(at[1])); }
  into.appendChild(d);
}

function sideHead(into, text) {
  const h = document.createElement('h4');
  h.textContent = text;
  into.appendChild(h);
}
// a heading and the block under it, holding a "looking" line until its
// answer comes back
function sideSection(into, head, waiting) {
  sideHead(into, head);
  const box = document.createElement('div');
  box.innerHTML = '<div class="snone"></div>';
  box.firstChild.textContent = waiting;
  into.appendChild(box);
  return box;
}

/* THE \vb THIS BOOK ALREADY WRITES FOR A VERB, if it has written one.  The
   dictionary's principal parts are the dictionary's -- its romanisation, its
   first sense -- and a book that has glossed سوختن twenty times has settled
   on its own, which is the one the twenty-first should match.  Found by the
   verb's first argument, the lemma or the form the recipe put first (a
   German reflexive's is `sich waschen`, not `waschen`), in the vocabulary
   lines of SRC: what the .tex holds, not what the page shows. */
function bookVb(vb) {
  const seen = new Set();
  for (const name of [vb.lemma, ((vb.parts || [])[0] || [])[0]]) {
    if (!name || seen.has(name)) continue;
    seen.add(name);
    const key = '\\vb{' + name + '}{';
    for (const s of SRC) {
      const voc = (s && s[4]) || '';
      const at = voc.indexOf(key);
      if (at < 0) continue;
      const m = texGroups(voc, at, 7);
      if (m) return m;
    }
  }
  return '';
}
// The macro at `at` and its n brace groups, whole; '' if they do not close.
// Counted rather than matched with a pattern: the meaning, the seventh, may
// hold a \pw{..} of its own.
function texGroups(s, at, n) {
  let i = at + 1;
  while (i < s.length && /[A-Za-z]/.test(s[i])) i++;
  for (let k = 0; k < n; k++) {
    while (s[i] === ' ') i++;
    if (s[i] !== '{') return '';
    let depth = 0;
    for (; i < s.length; i++) {
      const c = s[i];
      if (c === '\\') { i++; continue; }
      if (c === '{') depth++;
      else if (c === '}' && --depth === 0) { i++; break; }
    }
    if (depth) return '';
  }
  return s.slice(at, i);
}

/* One dictionary hit, as a row and the buttons that put it into a field.

   THE LEMMA WITH THE LEMMA'S OWN SOUND.  `translit` is the romanisation of
   the form the lookup reached, which is what the transliteration box wants
   -- the chunk's romanisation is of the words on the page -- and it is the
   wrong half of a \dw: pressing the button on ساختن reached from می‌سازم
   used to write \dw{ساختن}{mi-sāzam}, the lemma with the inflected form's
   sound.  head_sound is the lemma's; a server that does not send it yet
   falls back to the pronunciation, and only then to translit.

   AS THIS BOOK SPELLS IT.  Wiktionary files Chinese under the traditional
   characters, so a hit reached from 帮忙 in a simplified book comes back
   headed 幫忙, and its \dw wrote a word the book never prints.  Where lookup
   knows the spelling the book uses it sends `spelled`; the row and the \dw
   take that, and the dictionary's headword only when there is none.

   A VERB GOES IN AS \vb.  Where the language's recipe knew the hit for a
   verb it sends h.vb, the whole \vb ready to insert, and that button stands
   where \dw did; a \vb the book has already written for the same verb is
   offered before it.  A \vb the dictionary could not complete still goes in,
   dashed, with the row saying what is left.

   THE \vb CAN BE ANOTHER VERB'S.  German puts a separated verb back
   together: `stand … auf` reaches stehen, and the \vb its recipe builds is
   aufstehen's, whose `pret. stand auf` would sit under "stehen" unexplained.
   So the row names the verb the \vb is for -- stehen → aufstehen -- and the
   same arrow shows a reflexive (freuen → sich freuen, lever → se lever), a
   compound's light verb (teşekkür etmek → etmek) and a suru verb (勉強 →
   勉強する).  Compared with the marks off: an Arabic hit is headed by its
   bare page title, كتب, and its \vb by the vowelled كَتَبَ -- one verb, and
   compared as written, every Arabic verb would wear an arrow to itself.

   WHAT IS LEFT, IN FULL AND ONE TO A LINE.  An item of `missing` can be a
   sentence with its own colon: Persian's compound leaves `bw for فکر fekr
   after it: to think`, Turkish's passive `meaning: the dictionary has
   yapılmak only as the passive of yapmak`.  Joined with commas, two of those
   read as one run-on list whose colons belong to nobody, so every item is a
   line of its own, on the row and in the button's title, and none is cut.
   Nor does the title say "it goes in blank" any more: the \bw a compound
   needs is a thing to ADD, not a slot left empty.

   A HINT IS NOT A GAP.  `notes` is what the recipe found and could not
   choose between -- Arabic's other masdars: 1,122 of 7,233 verb entries
   list two to seven, and which one is meant depends on the sense -- so it is
   shown under the line, dimmer, and is neither `missing` nor in the title:
   the \vb is complete, the hint is only worth a second look. */
// a list the server sends as a list, a lone string, or not at all
const strList = x => (Array.isArray(x) ? x : (x ? [x] : []))
  .map(s => String(s).replace(/\s+/g, ' ').trim()).filter(Boolean);
// one word however it is written: composed alike, the language's marks off
// (stripMarks, as the contents filter has them), its case folded
const wordKey = s => stripMarks(foldCase(String(s || '').normalize('NFC')
  .replace(/\s+/g, ' ').trim()));
function sideHit(into, h) {
  const sense = (h.senses || [])[0] || '';
  const said = h.head_sound || h.said || h.translit || '';
  const head = h.spelled || h.headword;
  const vb = h.vb && h.vb.tex ? h.vb : null;
  // incomplete is what the recipe SAYS, whether or not it could name the gap
  const partial = !!vb && vb.complete === false;
  const gaps = partial ? strList(vb.missing) : [];
  if (partial && !gaps.length) gaps.push('part of it (the dictionary did not say which)');
  const notes = vb ? strList(vb.notes) : [];
  let more = null;
  if (vb && (vb.line || partial || notes.length)) {
    more = document.createElement('div');
    if (vb.line) more.appendChild(document.createTextNode(vb.line));
    for (const t of notes) {
      const d = document.createElement('div');
      d.className = 'snote'; d.textContent = t;
      more.appendChild(d);
    }
    if (partial) {
      const m = document.createElement('div');
      m.className = 'smiss';
      const l = document.createElement('span');
      l.className = 'sml'; l.textContent = 'to fill in:';
      const list = document.createElement('span');
      list.className = 'smis';
      for (const g of gaps) {
        const d = document.createElement('span');
        d.textContent = g;
        list.appendChild(d);
      }
      m.appendChild(l); m.appendChild(list);
      more.appendChild(m);
    }
  }
  // A WORD THE SPOKEN PASS READ says so under its row, as the reading panel's card does (lib/parseh.js): the editor is told
  // that what it is about to put in the vocabulary is the formal word the chunk's word was read as
  if (window.Parseh && Parseh.spoken && h.spoken) {
    const b = Parseh.spoken.block(h, {lang: LANG.code, dir: LANG.dir});
    if (b) { if (!more) more = document.createElement('div'); more.appendChild(b); }
  }
  let line = head + (said ? ' \u00b7 ' + said : '');
  if (vb && vb.lemma && wordKey(vb.lemma) !== wordKey(head)) line += ' \u2192 ' + vb.lemma;
  if (h.of_form && h.of_form !== said) line += ' \u2014 here ' + h.of_form;
  let main = line;
  if (h.spelled && h.spelled !== h.headword) {
    main = document.createElement('span');
    main.textContent = line;
    main.title = 'the dictionary files it under ' + h.headword;
  }
  const row = sideRow(into, main, sense, more);
  if (h.translit)
    sideBtn(row, 'romanisation \u2192', 'put ' + h.translit + ' in the transliteration',
            () => put(CH.tr, h.translit));
  if (vb) {
    const mine = bookVb(vb);
    const todo = ' \u2014 then fill in by hand what the dictionary did not give:\n' +
                 gaps.map(g => '\u2022 ' + g).join('\n') + '\n\n';
    // A VERB THAT IS MORE THAN ONE WORD GETS ITS OWN BUTTON.  \u0641\u06a9\u0631 \u06a9\u0631\u062f\u0646 is
    // one verb, and what the row says under "to fill in" -- a \bw for \u0641\u06a9\u0631
    // after the light verb -- is the other half of ONE vocabulary entry, not
    // a second entry: run onto the \vb with nothing between them, as
    // docs/lang/fa.md, tr.md and hi.md write it, the reader prints the two
    // as one line and the compound is what it means.  So the button beside
    // "\vb -> vocabulary" is not that button with something added: it puts
    // in the compound, says in its title that this is one verb in two words,
    // and stands first, because for a compound it is the one to press.
    const cp = (vb.compound && vb.compound.bw) ? vb.compound : null;
    if (cp) {
      const said = cp.whole + (cp.sound ? ' ' + cp.sound : '');
      // the book's own \vb for the light verb where it has one, as the plain
      // button prefers it: the compound is written with the verb this book
      // already writes, not with a second spelling of it
      const tex = (mine || vb.tex) + cp.bw;
      const b = sideBtn(row, cp.name + ' \u2192 vocabulary',
                        said + ' is one verb written in two words, not two ' +
                        'vocabulary entries: ' + (vb.lemma || head) +
                        ' carries the forms, ' + cp.word +
                        ' never changes, and the pair means ' +
                        (cp.mean || 'what neither word means alone') +
                        '. It goes in as ONE entry' +
                        (cp.complete ? ':\n'
                         : ' \u2014 then fill in what the dictionary did not give:\n' +
                           (cp.missing || []).map(g => '\u2022 ' + g).join('\n') + '\n\n') +
                        tex,
                        () => put(CH.voc, tex, '; '));
      if (!cp.complete) b.classList.add('sgap');
    }
    // The book's own and the dictionary's can be the SAME text, and then only
    // the book's button is drawn -- so it is the one that has to say what is
    // left: the real کردن reached from `فکر می‌کنم` is exactly the fixture's
    // \vb{کردن}{kardan}{کن}{kon}{کرد}{kard}{}, and the \bw for فکر it still
    // wants was said nowhere but on the row.
    const same = mine === vb.tex;
    if (mine) {
      const b = sideBtn(row, '\\vb as this book glosses it \u2192',
                        'the \\vb this book already writes for ' + (vb.lemma || head) +
                        ', with its own romanisation and meaning' +
                        (same && partial ? todo : ':\n') + mine,
                        () => put(CH.voc, mine, '; '));
      if (same && partial) b.classList.add('sgap');
    }
    if (!same) {
      const b = sideBtn(row, (mine ? 'the dictionary\u2019s \\vb' : '\\vb') + ' \u2192 vocabulary',
                        'add this verb, with its principal parts, to the vocabulary line' +
                        (partial ? todo : ':\n') + vb.tex,
                        () => put(CH.voc, vb.tex, '; '));
      if (partial) b.classList.add('sgap');
    }
  } else {
    sideBtn(row, '\\dw \u2192 vocabulary',
            'add this word to the vocabulary line',
            () => put(CH.voc, '\\dw{' + head + '}{' + said + '} ' + sense, '; '));
  }
  if (sense)
    sideBtn(row, 'meaning \u2192', 'put this sense in the meaning',
            () => put(CH.en, sense));
  // ENGLISH, EXPLAINED IN ENGLISH, read in the glosses' language here too:
  // where the dictionary defines its words and a model reads the pair, the
  // sense as the model puts it, under the row, with the buttons that put THAT
  // -- while the switch over the dictionary's rows (or the header's) is on
  if (sense && DICT.defines && MT.ready) {
    const t = document.createElement('div');
    t.className = 'sdef'; t.dataset.def = sense;
    if (!vb) t.dataset.dw = '\\dw{' + head + '}{' + said + '} ';
    t.hidden = !DICT.defsMt;
    row.parentNode.appendChild(t);
  }
}
// the buttons under a sense read in the glosses' language, once it is in
function sideDefPut(el, text) {
  if (!text) return;
  const row = document.createElement('div');
  row.className = 'sput';
  el.appendChild(row);
  if (el.dataset.dw !== undefined)
    sideBtn(row, '\\dw \u2192 vocabulary', 'add this word to the vocabulary line, its sense in ' +
            GLOSS.name, () => put(CH.voc, el.dataset.dw + text, '; '));
  sideBtn(row, 'meaning \u2192', 'put this sense, in ' + GLOSS.name + ', in the meaning',
          () => put(CH.en, text));
}
// the switch where the sheet can reach it -- the sheet lies over the header --
// just over the dictionary's rows
function sideDefsSwitch(dict) {
  if (!dict || !(DICT.defines && MT.ready)) return;
  const bar = document.createElement('div');
  bar.className = 'sdefbar';
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'sdefmt';
  b.textContent = 'in ' + GLOSS.name.toLowerCase();
  b.title = 'each sense put into ' + GLOSS.name + ' under it, by the translation model ' +
            'on this machine: a machine\'s reading, not a gloss';
  b.classList.toggle('on', DICT.defsMt);
  b.onclick = e => { e.preventDefault(); defsSwitch('defsMt', !DICT.defsMt); };
  bar.appendChild(b);
  dict.parentNode.insertBefore(bar, dict);
}
// an open sheet's sources after the switch moved: the senses in the glosses'
// language shown or hidden, and read where they are wanted
function sideDefs() {
  const body = $('#chsrcbody');
  if (!body || !chOpen) return;
  for (const b of body.querySelectorAll('.sdefmt')) b.classList.toggle('on', DICT.defsMt);
  for (const t of body.querySelectorAll('.sdef')) t.hidden = !DICT.defsMt;
  if (DICT.defsMt && DICT.defines && MT.ready) defsRead(body, '.sdef', null, sideDefPut);
}

// The one renderer for a complete-sentence translation in the Source
// sidebar.  Bergamot and a pasted chatbot answer both come through here, so
// they receive the same dictionary-based marks and the same insertion
// buttons.  `probe` is available from Bergamot; the external answer has no
// fragment translation and is aligned from the dictionary rows alone.
function sideTranslation(box, whole, probe, words, text, sentence) {
  box.textContent = '';
  const split = !!(text && sentence && text !== sentence);
  const span = split && whole
    ? ParsehMT.align(whole, probe || '', words || [], GLOSS.code) : null;
  if (span) {
    const holder = document.createElement('span');
    for (const seg of ParsehMT.marked(whole, span)) {
      if (!seg.here) { holder.appendChild(document.createTextNode(seg.text)); continue; }
      const b = document.createElement('span');
      b.className = 'shere'; b.textContent = seg.text;
      holder.appendChild(b);
    }
    const why = ParsehMT.why(span);
    const row = sideRow(box, holder,
                        (span.sure ? 'the marked words are this chunk\u2019s'
                                   : 'the marked words are part of this chunk\u2019s')
                        + (why ? ': ' + why
                               : span.by === 'translation'
                                 ? ', by the chunk translated on its own' : ''));
    sideBtn(row, 'the marked words \u2192 meaning',
            'put the guess in the meaning', () => put(CH.en, span.text));
    sideBtn(row, 'the whole sentence \u2192 meaning',
            'put the whole translation in the meaning', () => put(CH.en, whole));
  } else {
    const row = sideRow(box, whole || '(it produced nothing)',
                        whole && split
                          ? 'no word of it matches what the dictionary says of this chunk'
                          : '');
    if (whole)
      sideBtn(row, 'meaning \u2192', 'put it in the meaning',
              () => put(CH.en, whole));
  }
}

function sideLLM(box, n, text, ctx, evidence, live) {
  box.textContent = '';
  if (typeof ParsehLLM === 'undefined' || !window.ParsehLLMRow) {
    box.innerHTML = '<div class="snone">the prompt helper could not be loaded</div>';
    return;
  }
  const sentence = ctx.sentence || text;
  const around = chunkContextWindow(n);
  const controls = document.createElement('div');
  controls.className = 'sllmctl';
  // THE ROW (lib/llmrow.js) draws the button, the size and the reminder
  const askBox = document.createElement('div');
  const actions = document.createElement('div');
  actions.className = 'sllmactions';
  const use = document.createElement('button');
  use.type = 'button'; use.textContent = 'Use translation';
  use.title = 'use the translation pasted below';
  actions.appendChild(use);
  const paste = document.createElement('textarea');
  paste.rows = 3;
  paste.placeholder = 'Paste the chatbot\u2019s translation here';
  paste.setAttribute('aria-label', 'Chatbot translation');
  paste.setAttribute('lang', GLOSS.code);
  if (GLOSS.dir === 'rtl') paste.setAttribute('dir', 'rtl');
  const status = document.createElement('div');
  status.className = 'sllmstat'; status.setAttribute('aria-live', 'polite');
  const result = document.createElement('div');
  result.className = 'sllmout';
  controls.appendChild(askBox); controls.appendChild(paste); controls.appendChild(actions);
  controls.appendChild(status); controls.appendChild(result);
  box.appendChild(controls);

  const cached = LLM.sent.get(sentence);
  if (cached !== undefined) {
    paste.value = cached;
    status.textContent = 'Reusing the translation pasted for this sentence.';
    sideTranslation(result, cached, '', evidence.words || [], text, sentence);
  }

  let allPairs = null, ver = '';
  function corpusPage(offset) {
    return pAsk('__lookup', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(withLine({text: text, sentence: sentence, corpus_only: true,
                                     corpus_offset: offset, corpus_limit: 50}, lineOf(n)))})
      .then(r => r.json()).then(j => {
        if (!j || !j.ok) throw new Error('the corpus request was refused');
        return j;
      });
  }
  // THE PROMPT, made when it is asked for: Parseh's words, or -- where the menu in the row chose one of the
  // person's own -- theirs, read from the computer each time (ParsehLLM.own), so a prompt written again a
  // moment ago is the one used
  const build = () => ParsehLLM.own(row.promptId()).then(mine => ParsehLLM.prompt({
    sourceName: LANG.name, targetName: GLOSS.name, sourceCode: LANG.code, targetCode: GLOSS.code,
    sourceNative: LANG.native, trLabel: LANG.translit_label,
    version: ver, sentence: sentence, before: around.before, after: around.after,
    words: evidence.words || [], pairs: allPairs,
    instructions: mine && mine.text, instructionsKind: mine && mine.kind, custom: mine && mine.name
  }));
  const row = ParsehLLMRow.mount(askBox, {
    surface: 'ask', label: 'Ask LLM', title: 'copy a prompt for an external chatbot',
    lang: LANG.code, options: false,
    remind: 'paste it into a chatbot, then paste its translation below.',
    // a failed preparing has said why in the line below, and gives no prompt
    getText: () => allPairs ? build() : preparePairs().then(() => allPairs ? build() : ''),
    onCopied: () => { status.textContent = ''; status.classList.remove('bad'); }
  });
  // Prepare the corpus evidence while the user reads the sidebar.  The row
  // then holds the prompt, so the clipboard write happens directly inside the
  // button's click -- which Safari and Firefox insist on: waiting for a
  // network request first would lose that permission -- and its size is said
  // before the copy.
  function preparePairs() {
    row.disable('preparing the prompt\u2026'); status.classList.remove('bad');
    status.textContent = evidence.pairs_more
      ? 'Preparing Ask LLM with all Tatoeba examples\u2026' : 'Preparing Ask LLM\u2026';
    return Promise.all([ParsehLLM.collectPairs(evidence, corpusPage), ParsehLLM.version()])
      .then(([pairs, number]) => {
        allPairs = pairs; ver = number;
        if (!live() || !box.isConnected) return;
        row.enable();
        status.textContent = LLM.sent.has(sentence)
          ? 'Reusing the translation pasted for this sentence.' : '';
        return build().then(text => {
          if (live() && box.isConnected) row.update(text);
        }, err => {
          // the person's own prompt could not be made: its words, not the corpus, are what failed
          if (!live() || !box.isConnected) return;
          status.textContent = err.message; status.classList.add('bad');
        });
      }).catch(() => {
        if (!live() || !box.isConnected) return;
        allPairs = null; row.enable();
        status.textContent = 'Could not collect all Tatoeba examples. Press Ask LLM to retry.';
        status.classList.add('bad');
      });
  }
  preparePairs();
  function accept() {
    const out = paste.value.trim();
    if (!out) {
      status.textContent = 'Paste the chatbot\u2019s translation first.';
      status.classList.add('bad'); paste.focus(); return;
    }
    LLM.sent.set(sentence, out);
    while (LLM.sent.size > MT_KEEP) LLM.sent.delete(LLM.sent.keys().next().value);
    status.textContent = 'Translation ready for this whole sentence.';
    status.classList.remove('bad');
    sideTranslation(result, out, '', evidence.words || [], text, sentence);
  }
  use.onclick = e => { e.preventDefault(); accept(); };
  paste.addEventListener('keydown', e => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault(); accept();
    }
  });
}

function sideFill(n) {
  const body = $('#chsrcbody');
  if (!body) return;
  const gen = ++sideGen, live = () => gen === sideGen;
  body.textContent = '';
  const src = srcOf(n), text = src.fa || '';
  if (!text) { body.innerHTML = '<div class="snone">this chunk has no text yet</div>'; return; }

  /* THE SOURCE TOOLS, DRAWN AT ONCE AND IN THEIR ORDER -- dictionary, model,
     corpus, then the external-chatbot handoff -- each holding its
     place until its answer arrives.  The corpus's heading used to be drawn
     only when the lookup came back, so a lookup that failed left two
     headings, and one that came back late put its heading wherever the
     sidebar had got to. */
  const dict = sideSection(body, 'dictionary', 'looking the words up\u2026');
  sideDefsSwitch(dict);
  const mt = sideSection(body, 'a machine\u2019s reading', 'reading the sentence\u2026');
  const pairs = sideSection(body, 'sentences somebody translated', 'looking\u2026');
  const llm = sideSection(body, 'external chatbot', 'waiting for the sources\u2026');

  /* 1 -- the dictionary: every sense it has for every word, and the two
     places a sense can go (the vocabulary line, as LaTeX, or the meaning) --
     and 3, the sentences somebody translated, which ride back on the same
     request */
  const ctx = chunkCtx(n);
  // ONE lookup, read twice: by the dictionary block, and by the model's,
  // which marks the chunk's share of the sentence by what it says the
  // chunk's words mean
  const line = lineOf(n), lineWords = linePairs(line);
  const look = pAsk('__lookup', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                  body: JSON.stringify(withLine({text: text, sentence: ctx.sentence}, line))})
    .then(r => r.json());
  look.then(j => {
      if (!live()) return;
      dict.textContent = '';
      const wordsFound = (j && j.words) || [];
      if (!wordsFound.length) {
        dict.innerHTML = '<div class="snone">the dictionary has nothing for these words</div>';
      }
      for (const w of wordsFound) {
        // asked with the word line, a row goes under its word (`i`, the
        // word's place in the line), written as the line writes it
        const at = lineWords && typeof w.i === 'number' && (w.hits || []).length ? lineWords[w.i] : null;
        if (at) sideWord(dict, at);
        for (const h of (w.hits || [])) sideHit(dict, h);
      }
      if (DICT.defsMt && DICT.defines && MT.ready) defsRead(dict, '.sdef', null, sideDefPut);
      sidePairs(pairs, j);
      sideLLM(llm, n, text, ctx, j || {}, live);
    }).catch(() => {
      if (!live()) return;
      dict.innerHTML = '<div class="snone">the dictionary could not be reached</div>';
      pairs.innerHTML = '<div class="snone">the corpus could not be reached</div>';
      llm.innerHTML = '<div class="snone">the prompt needs the dictionary and corpus results</div>';
    });

  /* 2 -- the model, reading the whole sentence and guessing this chunk's
     share of it */
  if (!MT.ready) {
    mt.innerHTML = '<div class="snone">no translation model for this pair</div>';
  } else {
    const want = [ctx.sentence || text];
    if (text && text !== ctx.sentence) want.push(text);
    Promise.all([ParsehMT.translate(LANG.code, GLOSS.code, want),
                 look.catch(() => null)]).then(([got, j]) => {
      MT.sent.set(want[0], got[0] || '');
      if (want.length > 1) MT.probe.set(text, got[1] || '');
      if (!live()) return;
      const whole = got[0] || '', probe = want.length > 1 ? (got[1] || '') : '';
      sideTranslation(mt, whole, probe, (j && j.words) || [], text, want[0]);
    }).catch(() => {
      if (!live()) return;
      mt.innerHTML = '<div class="snone">the model could not be run</div>';
    });
  }
}

/* 3 -- sentences somebody translated, which come back with the lookup,
   into the block sideFill has already put under its heading */
function sidePairs(box, j) {
  box.textContent = '';
  const pairs = (j && j.pairs) || [];
  if (!pairs.length) {
    box.innerHTML = '<div class="snone">nothing in the corpus is about this chunk</div>';
    return;
  }
  for (const p of pairs) {
    const row = sideRow(box, p.src, p.dst);
    const marked = Parseh.pairMarkup(p, j, LANG, GLOSS);
    row.parentNode.querySelector('.stxt').innerHTML = marked.src;
    const sub = row.parentNode.querySelector('.ssub');
    if (sub) sub.innerHTML = marked.dst;
    sideBtn(row, 'its meaning \u2192', 'put the translation in the meaning',
            () => put(CH.en, p.dst));
  }
}
CH.back.addEventListener('click', closeChunk);
CH.box.addEventListener('submit', e => e.preventDefault());
addEventListener('keydown', e => {
  if (!chOpen) return;
  if (e.key === 'Escape') { e.preventDefault(); closeChunk(); }
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); saveChunk(); }
});

/* ---------- where a chunk ends -------------------------------------------
   A chunk is a sense group, and the groups an LLM cut on its first pass are
   the first thing somebody who knows the language wants to move.  Two
   operations, one sheet above the chunk sheet:

     JOIN this chunk to the next one.  The texts go end to end with the
     language's word separator, so the paragraph reproduces its source
     character for character and no check can fail; everything else -- the
     romanisation, the vocabulary, the meaning -- is put end to end with the
     separator its own field uses, and the server says in a note whatever
     could not simply be run together (two colours, two meanings).

     CUT it in two.  The only places offered are the places the text divides:
     a space, for a language written with spaces, and any two characters for
     one without.  What goes to which half is then a judgement, and the sheet
     is where it is made -- the vocabulary entries arrive on the side whose
     text holds their headword and move across with an arrow, and every box
     is typed over freely.

   The proposals are worked out by the server (lib/chunkdiv.py) and drawn
   here, so the video player's sheet and this one are one set of rules shown
   twice rather than two sets that drift.  Nothing is written until the button
   is pressed, and what is written is what is in the boxes.

   AFTERWARDS THE PAGE IS STALE, and this is the whole reason the sheet does
   not simply close.  data-c runs across the book, so joining or cutting moves
   every chunk after it by one; the per-chunk repaint cannot see that and the
   numbers left in this page would address the wrong text.  So the sheet turns
   into the outcome and one button, which reloads.  A page reloaded late is
   safe as well: every divide sends the text it is looking at, and the server
   refuses when the file no longer says that. */
const DV = {box: $('#dvbox'), back: $('#dvback'), title: $('#dvtitle'),
            where: $('#dvwhere'), pair: $('#dvpair'), notes: $('#dvnotes'),
            act: $('#dvdo'), stat: $('#dvstat'), cancel: $('#dvcancel')};
let dvOn = false, dvMode = '', dvData = null, dvEntries = null, dvSides = [];

function dvSay(m, bad) { DV.stat.textContent = m; DV.stat.className = bad ? 'bad' : ''; }

function dvShut() {
  if (!dvOn) return;
  dvOn = false; DV.box.hidden = true; DV.back.hidden = true;
}

async function dvAsk(body) {
  const r = await fetch('__divide/chunk', {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  return await r.json();
}

function dvNotes(list) {
  DV.notes.textContent = '';
  (list || []).forEach(t => {
    const p = document.createElement('p'); p.textContent = t;
    DV.notes.appendChild(p);
  });
}

// one column of boxes: the half's text above, unchangeable, and every field
// the macro has under it.  The text is not a box because a split divides and
// does not rewrite -- changing a letter is the chunk sheet's to do.
function dvCol(head, ch, worded) {
  const c = document.createElement('div');
  c.className = 'dvcol';
  c.dataset.fa = ch.fa || '';
  c.dataset.col = ch.col || '';
  const h = document.createElement('h4'); h.textContent = head; c.appendChild(h);
  const fa = document.createElement('div');
  fa.className = 'dvfa'; fa.dir = LANG.dir; fa.textContent = ch.fa || '';
  c.appendChild(fa);
  if (!chGlossed) return c;
  const add = (key, label, rows, mono) => {
    const l = document.createElement('label'); l.textContent = label;
    const t = document.createElement('textarea');
    t.rows = rows; t.value = ch[key] || ''; t.dataset.k = key;
    if (mono) t.className = 'dvvoc'; else t.dir = key === 'en' ? 'auto' : 'ltr';
    c.appendChild(l); c.appendChild(t);
    return t;
  };
  // the half's word line, where the chunk it comes from has one: the server
  // will not divide a line away without being told what becomes of it
  if (worded) {
    const t = add('words', 'words', 2);
    t.classList.add('dvwords'); t.lang = LANG.code;
  }
  if (LANG.reading) add('kana', LANG.reading_label || 'reading', 1);
  add('tr', LANG.translit_label || 'transliteration', 1);
  const chips = document.createElement('div');
  chips.className = 'dvchips'; c.appendChild(chips); c._chips = chips;
  add('voc', 'vocabulary', 3, true);
  add('en', 'meaning', 2);
  return c;
}

function dvRead(col) {
  const out = {fa: col.dataset.fa, col: col.dataset.col};
  col.querySelectorAll('textarea').forEach(t => { out[t.dataset.k] = t.value.trim(); });
  return out;
}

// the chips rewrite the two vocabulary boxes; typing in a box wins, because
// the box is what is sent
function dvPaintChips() {
  const cols = DV.pair.querySelectorAll('.dvcol');
  if (cols.length !== 2 || !dvEntries) return;
  cols.forEach(c => { if (c._chips) c._chips.textContent = ''; });
  ['a', 'b'].forEach((side, k) => {
    const box = cols[k].querySelector('textarea[data-k="voc"]');
    if (box) box.value = dvEntries.filter((_e, i) => dvSides[i] === side)
                                  .map(e => e.text).join(dvData.voc_sep);
  });
  dvEntries.forEach((e, i) => {
    const host = cols[dvSides[i] === 'a' ? 0 : 1]._chips;
    if (!host) return;
    const row = document.createElement('div'); row.className = 'dvchip';
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = dvSides[i] === 'a' ? '→' : '←';
    b.title = 'send this entry to the other chunk';
    b.onclick = () => { dvSides[i] = dvSides[i] === 'a' ? 'b' : 'a'; dvPaintChips(); };
    const t = document.createElement('span');
    t.className = 'dvtxt'; t.textContent = e.text;
    row.appendChild(b); row.appendChild(t); host.appendChild(row);
  });
}

function dvPick(i) {
  const c = dvData.cuts[i];
  $$('#dvwhere .dvcut').forEach((b, k) => b.classList.toggle('on', k === i));
  dvEntries = c.entries || []; dvSides = dvEntries.map(e => e.side);
  DV.pair.textContent = '';
  const worded = !!(dvData.chunk.words || '').trim();
  DV.pair.appendChild(dvCol('first chunk', c.first, worded));
  DV.pair.appendChild(dvCol('second chunk', c.second, worded));
  DV.pair.dataset.at = String(c.at);
  dvPaintChips();
  dvNotes(c.notes);
  DV.act.disabled = false;
}

function dvSplitUI() {
  DV.act.textContent = 'divide'; DV.act.disabled = true;
  DV.where.textContent = ''; DV.pair.textContent = ''; dvNotes([]);
  const cuts = dvData.cuts || [];
  const hint = document.createElement('div'); hint.className = 'anote';
  if (!cuts.length) {
    hint.textContent = LANG.word_sep
      ? 'This chunk is one word, and a chunk of a language written with spaces '
        + 'divides at a space. Join it to its neighbour first, or leave it.'
      : 'This chunk is a single character, so there is nothing to divide.';
    DV.where.appendChild(hint);
    return;
  }
  const box = document.createElement('div');
  box.className = 'dvtext'; box.dir = LANG.dir;
  (dvData.pieces || []).forEach((pc, i) => {
    box.appendChild(document.createTextNode(pc.text));
    if (i >= cuts.length) return;
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'dvcut'; b.textContent = '✂';
    b.title = 'divide here'; b.onclick = () => dvPick(i);
    box.appendChild(b);
  });
  DV.where.appendChild(box);
  hint.textContent = LANG.word_sep
    ? 'Pick where it divides. Joined back with the space, the two halves have '
      + 'to be this text again — which is why a word is never cut through.'
    : 'Pick where it divides. This language writes no spaces, so it divides '
      + 'between any two characters.';
  DV.where.appendChild(hint);
  if (cuts.length === 1) dvPick(0);
}

function dvMergeUI() {
  DV.act.textContent = 'join'; DV.where.textContent = '';
  DV.pair.textContent = ''; dvEntries = null; dvSides = [];
  if (!dvData.merge) {
    const n = document.createElement('div'); n.className = 'anote';
    n.textContent = dvData.merge_error || 'these two chunks cannot be joined';
    DV.where.appendChild(n); DV.act.disabled = true; dvNotes([]);
    return;
  }
  DV.act.disabled = false;
  const two = document.createElement('div');
  two.className = 'dvtext'; two.dir = LANG.dir;
  two.textContent = (dvData.chunk.fa || '') + '  ·  ' + ((dvData.next || {}).fa || '');
  DV.where.appendChild(two);
  const worded = [dvData.chunk, dvData.next || {}].some(x => (x.words || '').trim());
  DV.pair.appendChild(dvCol('the one chunk they become', dvData.merge.fields, worded));
  dvNotes(dvData.merge.notes);
}

let dvIndex = -1;
async function dvStart(mode, index) {
  if (chN < 0) return;
  // a merge is always "this one and the one after it", so joining BACKWARDS
  // ("join the previous to it") is the same operation asked about the chunk
  // before.  Every chunk of the book has the pencil and this sheet, \chp and
  // a chunk nobody has glossed yet included, so the index is only ever this
  // chunk or the one before it
  dvIndex = (index === undefined || index === null) ? chN : index;
  if (dvIndex < 0) return;
  dvMode = mode; dvData = null; dvEntries = null;
  DV.title.textContent = (mode === 'split' ? 'cut chunk ' : 'join chunk ')
                       + dvIndex + (mode === 'split' ? ' in two' : ' to the next');
  DV.where.textContent = ''; DV.pair.textContent = ''; dvNotes([]);
  DV.act.disabled = true; DV.cancel.hidden = false;
  DV.act.onclick = dvCommit;                 // dvDone leaves it on its reload
  dvSay('reading the chapter…', false);
  DV.box.hidden = false; DV.back.hidden = false; dvOn = true;
  let j;
  try { j = await dvAsk({action: 'preview', index: dvIndex}); }
  catch (err) {
    dvSay('the server did not answer (' + (err.message || err) + ') — this '
          + 'needs the page served by python3 serve.py', true);
    return;
  }
  if (!j.ok) { dvSay(j.error || 'the chapter would not open', true); return; }
  dvData = j; dvSay('', false);
  if (mode === 'split') dvSplitUI(); else dvMergeUI();
}

// The outcome, and the one thing left to do.  The sheet does not close: the
// numbers in this page have moved and the next click would use the old ones.
function dvDone(j) {
  // the sheet underneath is looking at a number that has just moved: take
  // its index away so nothing it still listens for can write with it
  chN = -1; chWas = null;
  DV.where.textContent = ''; DV.pair.textContent = ''; DV.cancel.hidden = true;
  const said = [];
  said.push(dvMode === 'split'
    ? 'The chunk is two chunks now, in ' + (j.file || 'the chapter') + '.'
    : 'The two chunks are one, in ' + (j.file || 'the chapter') + '.');
  if (j.fidelity) said.push(j.fidelity);
  if (j.parstart) said.push(j.parstart);
  if (j.reader && !j.reader.ok)
    said.push('The .tex is written, but the reader would not rebuild: '
              + (j.reader.error || 'no reason given'));
  said.push('Every chunk after this one has a new number, so this page is out '
            + 'of date until it is reloaded.');
  dvNotes(said);
  dvSay('', false);
  DV.act.textContent = 'reload the reader';
  DV.act.disabled = false;
  DV.act.onclick = () => {
    try { sessionStorage.setItem(MINE('at'), String(j.index)); } catch (_) {}
    location.reload();
  };
  DV.act.focus();
}

async function dvCommit() {
  if (!dvData) return;
  const cols = DV.pair.querySelectorAll('.dvcol');
  let body;
  if (dvMode === 'split') {
    if (cols.length !== 2) return;
    body = {action: 'split', index: dvIndex, expect: dvData.chunk.fa,
            first: dvRead(cols[0]), second: dvRead(cols[1])};
  } else {
    if (!cols.length) return;
    body = {action: 'merge', index: dvIndex, expect: dvData.chunk.fa,
            expect_next: (dvData.next || {}).fa, fields: dvRead(cols[0])};
  }
  DV.act.disabled = true; dvSay('writing…', false);
  let j;
  try { j = await dvAsk(body); }
  catch (err) {
    dvSay('the server did not answer (' + (err.message || err) + ') — '
          + 'nothing was written', true);
    DV.act.disabled = false; return;
  }
  if (!j.ok) { dvSay(j.error || 'refused', true); DV.act.disabled = false; return; }
  if (j.pdf_stale) pdfStale();
  dvDone(j);
}

$('#chsplit').onclick = () => dvStart('split');
$('#chjoin').onclick = () => dvStart('merge');
$('#chjoinp').onclick = () => dvStart('merge', chN - 1);
DV.cancel.onclick = dvShut;
DV.act.onclick = dvCommit;
DV.box.addEventListener('submit', e => e.preventDefault());
addEventListener('keydown', e => {
  if (!dvOn) return;
  if (e.key === 'Escape' && !DV.cancel.hidden) { e.preventDefault(); dvShut(); }
});

/* ---------- notes: what the book does not have room to say -----------------
   A reading edition is a text and its gloss, and there is nowhere in it to
   say the other thing -- that this idiom is the one from chapter two, that
   the next four lines are a quotation.  A note is that: a markdown file in
   the seam between two lines, kept in the book's own folder under markdown/
   and written with the studio's editor.

   IT IS NOT SHOWN IN THE PAGE.  The reading is the point, and a page that
   put an essay between two subparagraphs would not be a reading edition any
   more.  What is shown is that there is one -- a small mark in the seam --
   and clicking it opens the note over the whole page, rendered by the
   studio's own renderer in a frame.  Rendered by it, not like it: the
   marks, the glossary, the colours and the typography are the studio's
   because it IS the studio, mounted over this book's markdown/ directory.

   WHAT IT OPENS IS THE BARE PAGE (markdown/app/templates/note.html): the
   rendered note on the studio's sheet, with no editor and none of the
   studio's scripts.  The document page it used to open was about 1.3 MB
   fetched afresh on every click, for a page that is read a dozen times in a
   session and written on almost never; "open in the studio", in the bare
   page's own header, is one click from the whole of it, and a note that
   holds an exercise is sent there by the server without being asked.

   The seams are written into the page at build time (one `.gap` before every
   subparagraph, one after the last); what is IN them is asked for at runtime,
   because notes are written and retitled without rebuilding a book.

   An anchor naming a subparagraph that is no longer there -- the text was
   rewritten, or the note was moved by hand to a key that does not exist --
   is not dropped and not an error: the note is shown at the end of the book
   under `adrift`, which is where somebody will look for it. */
const NOTES = '../notes';
const NT = {back: $('#ntback'), box: $('#ntbox'), title: $('#nttitle'),
            frame: $('#ntframe'), edit: $('#ntedit'), read: $('#ntread'),
            close: $('#ntclose')};
let ntOpen = false, ntId = '', noteList = [];

/* ---------- the notes within a screen, fetched before they are wanted -----
   The same bargain the chapters already make (fillChapter's observer): a
   note whose mark comes near the window is read now, so that the click that
   opens it costs nothing.  It is held as text and put into the frame with
   srcdoc, rather than left to the browser's cache, because the studio
   answers `no-cache` for everything it renders -- a page somebody may be
   editing must never come back stale -- and a revalidation over a tunnel is
   the very wait this is here to remove.

   CAPPED, because a textbook has hundreds of notes and a reader walking it
   would otherwise carry every one of them for the rest of the session; the
   oldest goes when the cap is reached, and it is only ever a copy of
   something the server still has.

   NEVER WHILE A NOTE IS OPEN.  The note being read is what the connection
   is for; anything that came near meanwhile waits and goes when it closes.

   A NOTE THAT HOLDS AN EXERCISE is not held at all.  The server answers the
   bare address for one with a redirect to the studio's full page (an
   exercise with no script is a box that cannot be answered), and `redirected`
   is how that is known here: the id is remembered, and from then on it is
   opened as the full page directly, without the extra hop.

   AND AWAY FROM THE COMPUTER THERE IS NO REDIRECT TO SEE.  A kept book keeps
   its notes, and for a note that holds an exercise what was kept IS the
   studio's full page -- so it can be answered on a train, exactly as it is at
   the desk (TO-DO §0, "the notes, kept with their book or video").  The
   worker hands that page straight back at the bare address, without a hop,
   and `redirected` is false: a test that believed it would put a document
   page, scripts and all, into the frame through srcdoc, where a bare note
   was expected.  So the page is asked what it is as well.  The studio writes
   that on its own <body> -- `data-page="doc"` on the document page,
   `data-page="note"` on the bare one -- which is an honest answer whoever
   gave it, and one the renderer can never forge: everything a note's own
   text contributes to this html went through htmlgen's escaping. */
const NOTE_HOLD = 12;
// the studio's document page saying so itself (templates/doc.html)
const NOTE_FULL_MARK = '<body data-page="doc"';
const noteHeld = new Map();     // id -> the bare page's html
const noteFull = new Set();     // ids the server sends to the studio instead
const noteWaiting = new Set();  // came near while a note was open
const noteFetching = new Set();

async function holdNote(id) {
  if (!id || noteHeld.has(id) || noteFull.has(id) || noteFetching.has(id)) return;
  if (ntOpen) { noteWaiting.add(id); return; }
  noteFetching.add(id);
  try {
    const r = await fetch(NOTES + '/note/' + encodeURIComponent(id));
    if (!r.ok) return;
    const html = await r.text();
    // the computer's redirect, or the kept page saying what it is: either
    // way this note is answered by the studio's whole document page, and
    // the frame is sent to that address rather than fed these bytes
    if (r.redirected || html.includes(NOTE_FULL_MARK)) { noteFull.add(id); return; }
    noteHeld.set(id, html);
    // a Map keeps its keys in the order they were put in, so the first is
    // the one held longest
    while (noteHeld.size > NOTE_HOLD)
      noteHeld.delete(noteHeld.keys().next().value);
  } catch (_) {
    // off the disk, or a server that does not know the bare address: the
    // mark still opens the note, it simply opens it when it is clicked
  } finally {
    noteFetching.delete(id);
  }
}
// Rebuilt with the marks: paintNotes throws every button away and makes new
// ones, and an observer still watching the old ones would hold them alive.
const nearNote = window.IntersectionObserver
  ? new IntersectionObserver(es => es.forEach(e => {
      if (!e.isIntersecting) return;
      nearNote.unobserve(e.target);
      holdNote(e.target.dataset.note);
    }), {rootMargin: '600px 0px'})
  : null;

function ntFrame(url, html) {
  // A FRESH element, not a new src.  Setting src on a live iframe navigates
  // it, and an iframe's navigations go on the joint session history: reading
  // three notes would take three presses of Back to leave the page you were
  // reading.  A newly inserted frame's first load replaces instead.
  const old = NT.frame;
  const f = document.createElement('iframe');
  f.id = 'ntframe'; f.title = old.title;
  // srcdoc for one already in hand: the same bytes the address would have
  // answered, drawn without going back for them.  Every address the note
  // page writes is absolute (the studio's own prefix), so nothing in it
  // depends on where the frame thinks it is.
  if (html != null) f.srcdoc = html; else f.src = url;
  old.replaceWith(f);
  NT.frame = f;
}
// '' the bare page, 'edit' the studio's editor, 'full' its document page
function noteUrl(id, how) {
  const at = NOTES + '/' + (how ? 'doc' : 'note') + '/' + encodeURIComponent(id);
  return how === 'edit' ? at + '/edit' : at;
}
function ntShow(id, title, how) {
  peekHide();
  // one already known to need the studio's page goes straight there, rather
  // than to a bare address that would only redirect
  if (!how && noteFull.has(id)) how = 'full';
  ntId = id; ntOpen = true;
  NT.title.textContent = title || 'note';
  const held = how ? null : noteHeld.get(id);
  if (held) ntFrame(null, held); else ntFrame(noteUrl(id, how));
  NT.edit.hidden = how === 'edit'; NT.read.hidden = how !== 'edit';
  NTOLD.hidden = !notesAway;    // what is in the frame is as of when it was kept
  NT.back.hidden = false; NT.box.hidden = false;
}
function ntShut() {
  if (!ntOpen) return;
  ntOpen = false; NT.box.hidden = true; NT.back.hidden = true;
  ntFrame('about:blank');
  // The one that was open is the one that may have just been written: the
  // editor is reached through this very frame, so the copy in hand is the
  // only one that can have gone stale, and it is dropped rather than shown
  // again.  Whether it now holds an exercise is a fresh question too.
  noteHeld.delete(ntId); noteFull.delete(ntId);
  const waited = [...noteWaiting];
  noteWaiting.clear();
  waited.forEach(holdNote);       // what came near while it was open
  loadNotes();          // the title may have changed, or the note may be gone
}
// A key pressed inside the frame belongs to the frame's document, and this
// page cannot hear it.  The note posts up instead (both the bare page and
// the studio's own do so only when they are framed), so the button's
// "close (Esc)" is true wherever the pointer happens to be.
//
// `open-note-full` is the bare page's own header asking for the whole of the
// studio.  It is done from out here, and not by the link navigating itself,
// because a navigation inside the frame lands on the joint session history:
// a note opened in full would cost a press of Back before the book moved.
addEventListener('message', e => {
  if (e.origin !== location.origin) return;
  const d = e.data;
  if (!d || !d.parseh) return;
  if (d.parseh === 'close-note') ntShut();
  else if (d.parseh === 'open-note-full' && ntOpen)
    ntShow(ntId, NT.title.textContent, 'full');
});
NT.close.onclick = ntShut;
NT.back.addEventListener('click', ntShut);
NT.edit.onclick = () => ntShow(ntId, NT.title.textContent, 'edit');
NT.read.onclick = () => ntShow(ntId, NT.title.textContent, '');
// registered in the capture phase and stopped immediately, so the sheets
// underneath -- the divide sheet, the chunk sheet, the card dashboard -- do
// not all close behind the note that was on top of them
addEventListener('keydown', e => {
  if (ntOpen && e.key === 'Escape') {
    e.preventDefault(); e.stopImmediatePropagation(); ntShut();
  }
}, true);

function gapFor(a) {
  if (!a || a.kind !== 'sub') return null;
  // The seam between two lines has two names -- after the one above, before
  // the one below -- and both find it.  Compared rather than put into a
  // selector: the anchor is a line somebody typed into a file, and a quote
  // in it would throw out of querySelector and take every mark on the page
  // with it.
  const at = String(a.at), want = a.side === 'after' ? 'after' : 'at';
  return $$('.gap').find(g => g.dataset[want] === at) || null;
}
/* ---------- a look at a note before it is opened ---------------------------
   The mark is the title cut to one line, and opening the note puts the
   studio over the whole page: to learn what a note said, a reader had to
   leave the text.  So a pointer resting on a mark (or the keyboard's focus
   arriving at one) shows the title and the note's first lines, in a card
   beside the mark, after a moment -- 350 ms, long enough that sweeping the
   pointer across a seam on the way to a word does not light up every note
   it crosses.  It goes on leaving, on a click anywhere, on Escape, on a
   scroll (the card is fixed and the mark is not), and when the note opens.

   PLAIN TEXT, AND ONLY EVER textContent.  A note is a file that travels:
   it comes inside a book's bundle, from somebody else's toolbox, and its
   title and its excerpt (which /api/marks cuts from its markdown, markup
   and front matter stripped) are that person's words.  A click on the mark
   already runs the note's page in a frame; a pointer merely passing over
   one must never do more than show letters.

   NONE ON A TOUCH SCREEN (HOVER_OK), where there is no hover to rest: a tap
   opens the note, as it always did.  The card is made here, by the script,
   and not written into the page: a reader built before it has none, and
   the page test reads a built reader. */
const PEEK = document.createElement('div');
PEEK.id = 'ntpeek';
PEEK.setAttribute('role', 'tooltip');
PEEK.lang = 'en'; PEEK.dir = 'ltr';
PEEK.hidden = true;
document.body.appendChild(PEEK);
// peekFor: the mark the card is showing for; peekArmed: the one it is about
// to show for (and whose aria-describedby names it meanwhile)
let peekFor = null, peekArmed = null, peekShowT = null, peekHideT = null;

function peekFill(n, why) {
  PEEK.textContent = '';
  const add = (cls, text) => {
    const d = document.createElement('div');
    d.className = cls; d.textContent = text;
    PEEK.appendChild(d);
  };
  add('pkt', n.title || 'note');
  // `excerpt` is new in /api/marks: a server that does not send it yet
  // still gets a card, with the title and the way in
  const ex = typeof n.excerpt === 'string' ? n.excerpt.trim() : '';
  if (ex) add('pkx', ex);
  if (why) add('pkf', why);
  else if (!ex) add('pkf', 'click to open');
}
// Above the mark, as the gloss cloud opens above its chunk; below it when
// the header would cover it; and inside the window whichever it is.
function peekPlace(el) {
  const r = el.getBoundingClientRect();
  PEEK.style.left = '8px'; PEEK.style.top = '-9999px';
  PEEK.hidden = false;
  const vw = document.documentElement.clientWidth || innerWidth;
  const vh = document.documentElement.clientHeight || innerHeight;
  const pw = PEEK.offsetWidth, ph = PEEK.offsetHeight;
  const head = document.querySelector('header');
  const roof = (head ? head.getBoundingClientRect().bottom : 0) + 6;
  let top = r.top - ph - 8;
  if (top < roof)
    top = vh - r.bottom >= ph + 16 ? r.bottom + 8 : Math.max(roof, vh - ph - 8);
  const left = Math.min(Math.max(8, r.left + r.width / 2 - pw / 2), vw - pw - 8);
  PEEK.style.top = Math.max(8, top) + 'px';
  PEEK.style.left = Math.max(8, left) + 'px';
}
function peekHide() {
  clearTimeout(peekShowT); clearTimeout(peekHideT);
  peekShowT = peekHideT = null;
  if (peekArmed) peekArmed.removeAttribute('aria-describedby');
  peekFor = peekArmed = null;
  PEEK.hidden = true;
}
function peekWire(b, n, why) {
  const arm = () => {
    clearTimeout(peekHideT); clearTimeout(peekShowT);
    if (peekFor === b && !PEEK.hidden) return;
    // one card already up: the next comes at once, the way a row of
    // tooltips behaves once the first has been waited for
    const warm = !PEEK.hidden;
    if (peekArmed && peekArmed !== b) peekArmed.removeAttribute('aria-describedby');
    peekFill(n, why);
    peekArmed = b;
    b.setAttribute('aria-describedby', 'ntpeek');
    const show = () => {
      if (!b.isConnected || ntOpen) return;
      peekFor = b; peekPlace(b);
    };
    if (warm) show(); else peekShowT = setTimeout(show, 350);
  };
  // a moment's grace on leaving, so the pointer can cross onto the card
  const disarm = () => {
    clearTimeout(peekShowT); clearTimeout(peekHideT);
    peekHideT = setTimeout(peekHide, 150);
  };
  b.addEventListener('mouseenter', arm);
  b.addEventListener('focus', arm);
  b.addEventListener('mouseleave', disarm);
  b.addEventListener('blur', disarm);
}
PEEK.addEventListener('mouseenter', () => clearTimeout(peekHideT));
PEEK.addEventListener('mouseleave', () => {
  clearTimeout(peekHideT); peekHideT = setTimeout(peekHide, 150); });
addEventListener('keydown', e => { if (e.key === 'Escape' && peekArmed) peekHide(); });
// A card up is hidden by any scroll.  One only waiting is left alone when
// the mark has the keyboard's focus: Tab scrolls a mark into view on its way
// to it, and that scroll is not the reader moving on.
addEventListener('scroll', () => {
  if (peekFor || (peekArmed && document.activeElement !== peekArmed)) peekHide();
}, {capture: true, passive: true});
document.addEventListener('click', () => { if (peekArmed) peekHide(); }, true);

function noteButton(n, adrift) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'mark' + (adrift ? ' adrift' : '');
  b.textContent = n.title || 'note';
  // The note this mark stands for, kept ON the mark.  A fold bar has to say
  // which notes it is hiding, and the only honest answer to that is the
  // marks that are inside the paragraphs it hid (foldNoteRow): the page is
  // asked, not the anchors compared a second time.
  b.noteRecord = n;
  b.dataset.note = n.id;
  const why = adrift
    ? 'this note names a place that is no longer in the book — open it to see '
      + 'what it says, and change its anchor line'
    : (notesAway ? NT_KEPT : '');
  // with a pointer the card says it, and a native tooltip would sit on top
  // of the card saying less; without one the title is all there is
  // Without a hover the title is all there is, and lib/explain.js puts it
  // under "?" on a touch screen: what the mark DOES comes first and the
  // kept copy is said after it, rather than in place of it.
  if (HOVER_OK) peekWire(b, n, why);
  else b.title = (adrift ? why : 'read this note')
               + (notesAway ? ' — ' + NT_KEPT : '');
  b.onclick = e => { e.stopPropagation(); peekHide(); ntShow(n.id, n.title, ''); };
  // read ahead when it comes near the window, so the click costs nothing
  if (nearNote) nearNote.observe(b);
  return b;
}
async function newNote(gap) {
  // the seam names the line below it, except the last, which names the one
  // above -- and the anchor written is the one the seam actually has
  const body = gap.dataset.at
    ? {side: 'before', kind: 'sub', at: gap.dataset.at, target: LANG.code}
    : {side: 'after', kind: 'sub', at: gap.dataset.after, target: LANG.code};
  let j;
  try {
    const r = await fetch(NOTES + '/api/marks', {method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)});
    j = await r.json();
  } catch (err) { return; }
  if (!j.ok || !j.note) return;
  await loadNotes();
  ntShow(j.note.id, j.note.title, 'edit');    // straight into the editor
}
function paintNotes() {
  peekHide();           // the marks it was showing for are about to be replaced
  // every mark is about to be thrown away, and an observer still watching
  // the old ones would keep them (and their notes) alive for the session
  if (nearNote) nearNote.disconnect();
  $$('.gap').forEach(g => {
    g.textContent = '';
    const plus = document.createElement('button');
    plus.type = 'button'; plus.className = 'plus'; plus.textContent = '+';
    plus.title = 'write a note here';
    plus.onclick = e => { e.stopPropagation(); newNote(g); };
    g.appendChild(plus);
  });
  const last = $('.gap.last');
  // A note whose seam is not in the page hangs at the end, marked adrift --
  // but while chapters are still arriving, "not in the page" mostly means
  // "not fetched yet", and a shelf of adrift notes at the end of the book
  // would be a lie that repaints itself away.  They come as their chapters do.
  const waiting = lazyChapters();
  noteList.forEach(n => {
    const g = gapFor(n.anchor);
    if (g) g.appendChild(noteButton(n, false));
    else if (last && !waiting) last.appendChild(noteButton(n, true));
  });
  // the marks are the fold bars' source: what each bar is hiding has just
  // changed under it
  paintFoldNotes();
}
async function loadNotes() {
  try {
    const r = await fetch(NOTES + '/api/marks');
    const j = await r.json();
    // ONLY AN ANSWER THE COMPUTER REALLY GAVE MAY REPLACE THE MARKS.  The
    // seams' list is a door (lib/sw.js, isDoor): the computer is asked first
    // and the copy kept with the book answers when it does not, so a kept
    // note stays reachable -- there would be no mark to click on otherwise.
    // What tells the two apart is `ok`: the studio answers this address with
    // {ok:true, notes:[...]} and nothing else, whether that answer comes
    // down the wire now or out of the cache where the wire last put it, so
    // an `ok` answer is the computer's own and an empty `notes` in it is the
    // truth -- the seams empty.  A REFUSAL IS NOT AN ANSWER ABOUT THE MARKS.
    // Away from the computer the worker writes {ok:false, offline:true} with
    // a 503 of its own for a book kept without its notes, and in the moment
    // before the kept copy lands; it is well-formed JSON and it knows
    // nothing, and letting it empty the seams would take away the very notes
    // the book was kept for.  So the marks in hand stay.
    if (j && j.ok && j.notes) noteList = j.notes;
  } catch (_) {
    // Off the disk, a server that does not know about notes, or the
    // computer gone mid-session with nothing kept: a request that never
    // arrived knows no more than a refusal does, and the marks already in
    // hand are kept rather than swept away -- they were true when they were
    // read, and a book whose notes vanish as the train enters a tunnel is
    // the failure this whole section is here to prevent.  With none in hand
    // the seams simply stay empty, as they always did.
  }
  paintNotes();
}
/* ---------- the marks, and the computer being away ------------------------
   What is kept was kept at a moment, and the marks are as of that moment: a
   note written at the desk this morning is not in a list read last night.
   Said quietly, and only while the computer cannot be reached -- lib/keep.js
   asks that question for the whole toolbox and puts the answer on <html>, so
   nothing here pings anything -- and said in the two places it is actually
   wanted: on the frame the note is read in, which is where a reader wonders
   whether what is in front of them is current, and in the card a mark shows
   before it is opened.  The moment the computer answers again it goes, and
   the marks are repainted with the wording it changed. */
let notesAway = document.documentElement.hasAttribute('data-parseh-away');
const NT_KEPT = 'the computer cannot be reached — the notes and their marks '
              + 'are as they were when this book was kept on this phone';
// Made here and not written into the page, exactly as the peek card is: a
// book built before this line existed has no #ntold in its markup, and the
// page test reads a built reader.
const NTOLD = document.createElement('span');
NTOLD.id = 'ntold';
NTOLD.hidden = true;
NTOLD.textContent = 'as kept';
NTOLD.title = NT_KEPT;
NTOLD.style.cssText = 'color:var(--faint);letter-spacing:0;text-transform:none;'
                    + 'font-size:11.5px;font-style:italic;white-space:nowrap';
if (NT.title && NT.title.parentNode) NT.title.after(NTOLD);
// The attribute is put on by another script, twenty seconds after the page
// opened at the earliest, and taken off again when the computer comes back;
// watching it is how this page hears both without asking anybody.
new MutationObserver(() => {
  const away = document.documentElement.hasAttribute('data-parseh-away');
  if (away === notesAway) return;
  notesAway = away;
  NTOLD.hidden = !away;
  paintNotes();                 // the marks' explanations have just changed
}).observe(document.documentElement,
           {attributes: true, attributeFilter: ['data-parseh-away']});
loadNotes();
// and what is folded away, folded: the runs the build handed the page, once
// the whole of the first chapter is standing
applyFold();

// after a divide the page comes back at the chunk it was working on
addEventListener('load', () => {
  let at = null;
  try { at = sessionStorage.getItem(MINE('at'));
        sessionStorage.removeItem(MINE('at')); }
  catch (_) { return; }
  if (at === null) return;
  (async () => {
    await needChapters(chapOfChunk(+at));   // it may not be in the page yet
    const el = document.querySelector('[data-c="' + at + '"]');
    if (el) el.scrollIntoView({block: 'center'});
  })();
});
"""

# The one case fold, written once in languages.py and spliced in here, so
# the filter key this file builds and the query the page folds cannot drift
# apart.  Done at import, not at build: tex2html.JS is what every reader
# ships, and the tests parse that.
JS = JS.replace("__FOLD__", languages.FOLD_JS)


def pass_buttons():
    """The header's level toggles, one per pass the language has; the face is
    the level's NAME (the registry's `name`, which a person may change on their
    own pages: lib/gear-reader.js wears theirs over it on the live page) and
    the title is the registry's one-line description of what it shows.  NEVER A
    DIGIT: a number meant one thing in Persian and another in Chinese, and
    names a level far better (docs/languages.md, the levels' names).

    They come out as ONE GROUP -- a dashed box with a caption under it --
    because buttons on their own do not say what the row of them is: the
    caption says it (levels), and each button's title says what that one
    shows.

    WHAT EACH BUTTON HIDES IS TAKEN FROM `pass_class`, NOT FROM ITS POSITION.
    The passes are drawn with a class named for their KEY -- `alt` is always
    `p4`, whether or not the language has a `bare` pass at p3 -- while this
    used to number the toggles 1, 2, 3... down the list.  For Japanese, which
    has all four, the two agreed by coincidence.  Chinese is the first
    language with an `alt` pass and no `bare` one, so its third button asked
    the page to hide `.p3`, which a Chinese reader does not have, and the
    vertical pass could not be turned off at all.  The reading pass of a
    language whose chunks carry words is the same case again: its toggle is
    `no5` wherever its button stands.
    """
    btns = "\n".join(
        '      <button data-toggle="no%s" title="%s">%s</button>'
        % (pass_class(p).split()[0][1:], esc(p.get("title", "")),
           esc(p.get("name") or p.get("key", "")))
        for p in LANG.passes)
    return ('  <span class="pgrp" title="the ways this edition sets the same '
            'text, one button each">\n    <span class="pgrpb">\n%s\n'
            '    </span>\n    <span class="pgrpc">levels</span>'
            '\n  </span>' % btns)


def hover_title():
    """The hover button's title, naming the levels the mode keeps -- the text
    ones: the sentence, the reading alone, the plain text -- by the names their
    buttons wear (and lib/gear-reader.js says it again with the names a person
    gave them)."""
    names = [p.get("name") or p.get("key", "") for p in LANG.passes
             if p.get("key") in ("vocal", "aloud", "bare")]
    said = (" and ".join(names) if len(names) < 3
            else ", ".join(names[:-1]) + " and " + names[-1])
    return ("the text alone (the level%s %s), the glosses in a hover cloud over it (H)"
            % ("s" if len(names) > 1 else "", said))


def lang_tokens():
    """The language's font tokens, as the page's own fallback.

    lib/langs.css (generated from the registry, served by the Parseh server)
    is where the tokens come from and it wins: it targets [data-lang=..],
    which beats this type selector whatever the order of the sheets.  The
    fallback exists because a built reader also opens straight off the disk,
    where no server generates that file.
    """
    return ("html{--tl-font:%s;--tl-alt:%s;--tl-dir:%s;--tl-alt-lh:%s}"
            % (LANG.css_font(), LANG.css_font(alt=True), LANG.dir,
               LANG.fonts.get("alt_line_height") or 1))


def card_sides():
    """The two sides a card runs between, as the dashboard names them.

    A card runs from the book's language to the language its glosses are
    written in, and saying so is worth it: a Persian card glossed in English
    really does ask Persian and answer English, and an English one glossed in
    Italian asks English and answers Italian.  When the two are the same --
    an English edition glossed in English, a monolingual Italian one --
    "English → English" names neither side, so the sides are called what they
    hold, the word and its meaning: the way the registry already calls that
    note type's first field Headword rather than English, and the way the
    opposites card has always said "word → opposite".
    """
    return (("word", "meaning") if GLOSS.name == LANG.name
            else (LANG.name, GLOSS.name))


def meaning_label():
    """What the two sheets call the field that holds the meaning.

    The gloss language's own name, so that an annotator writing Italian is
    told which language to write in by the label of the box.  It is *meaning*
    and not the name when the book is glossed in the language it teaches: the
    text row above wears that name already, and an English edition with two
    rows labelled "english" says of neither which is which.
    """
    return "meaning" if GLOSS.name == LANG.name else GLOSS.name.lower()


def gloss_dir_attrs():
    """What a box the meanings are typed into carries, the way dir_attrs in
    page() does it for the book's own language: the direction only when it is
    right to left, because an LTR box needs no attribute, and the lang always,
    so the browser hyphenates and spell-checks the right language."""
    return GLOSS.html_attrs() if GLOSS.rtl else ' lang="%s"' % esc(GLOSS.code)


def chunk_editor(dir_attrs):
    """The sheet that writes one chunk back into its .tex.

    Set like the Anki dashboard and for the same reason: a form over the page,
    opened for one chunk, closed by Escape.  WHICH rows it shows is decided in
    the browser and not here -- \\chp carries a colour and its text and nothing
    else, and the page can see that from the row the build wrote for it.

    The fields wear the language's own names (the registry's translit_label
    and reading_label): a Japanese chunk's tr is its rōmaji and an Italian
    one's is a pronunciation, and neither is called a transliteration.  The
    vocabulary says out loud that it is LaTeX, because it is the one field
    that is, and shows the macros with the arity nobody remembers.

    The last row wears the GLOSS language's name (meaning_label above), and
    its box takes that language's direction: an annotator told to write the
    meanings in Italian is told so again by the box they are typed into, and
    a Persian gloss of an Arabic text is typed right to left.

    The \\vb button says what ITS language's three forms are, from the
    registry's vb_forms: it said "infinitive, pres. stem, past stem" in every
    book, which is Persian's \\vb and nobody else's -- an Arabic verb is filed
    under its perfect, a Japanese one under its dictionary form, and the
    third Italian form is a participle and not a stem.  A registry without
    vb_forms falls back to the two labels the gloss itself prints.  The three
    are joined with a middle dot because an item may hold a comma of its
    own (Arabic's first is "perfect, 3rd m. sg., ...").

    Beside save and revert, "delete gloss" empties every box of the gloss in
    one press and "undo delete" writes it back (the page keeps it until it
    is reloaded); a chunk left like that is one nobody has glossed yet, legal
    everywhere.  The "an LLM" row opens the region sheet (#rgbox, after the
    fold sheet here, from the header's "gloss with an LLM" too) on this
    chunk's sentence: a prompt for a chatbot copied, its answer pasted back
    and written chunk by chunk through the same door, by lib/glossregion.py.
    """
    pres, past = LANG.vb_labels
    forms = [str(f) for f in (getattr(LANG, "vb_forms", None) or []) if f][:3]
    if len(forms) == 3:
        vb_title = ("a verb: %s · %s · %s — each with its romanisation "
                    "— then the meaning" % tuple(forms))
    else:
        vb_title = ("a verb: the form it is listed under, its %s form and its %s "
                    "form — each with its romanisation — then the meaning"
                    % (pres, past))
    return """<div id="chback" hidden></div>
<form id="chbox" lang="en" dir="ltr" hidden autocomplete="off">
  <div class="ahead">chunk <span id="chref"></span><span class="sp"></span>
    <button type="button" id="chsrc" title="what the dictionary, the model,
      the corpus and an external chatbot can offer for this chunk">&#8853; sources</button>
    <button type="button" id="chcancel" title="close (Esc)">&#10005;</button></div>
  <div class="chcols">
  <aside id="chside" hidden>
    <div class="anote">Everything the toolbox already knows about this chunk.
      Nothing here is a gloss and nothing writes itself: each line has the
      buttons that put it into a field, where it is yours to correct.</div>
    <div id="chsrcbody">looking&hellip;</div>
  </aside>
  <div class="chmain">
  <div id="chplain" hidden>A plain chunk (<code>\\chp</code>): it carries a
    colour and its text, and has no slot for a gloss.</div>
  <div class="arow"><span class="alab">colour</span>
    <div class="actl">
      <div class="adir" id="chcol">
        <button type="button" class="dbtn on" data-col="">none</button>
        <button type="button" class="dbtn" data-col="red"><span class="hl-red">&#9679;</span> red</button>
        <button type="button" class="dbtn" data-col="blue"><span class="hl-blue">&#9679;</span> blue</button>
        <button type="button" class="dbtn" data-col="orange"><span class="hl-orange">&#9679;</span> orange</button>
        <button type="button" class="dbtn" data-col="green"><span class="hl-green">&#9679;</span> green</button>
      </div>
      <div class="anote">Marks <b>the first level only</b>, here and in the PDF &mdash; the
        attempt you make before any help arrives. It means nothing to any tool:
        it is your own mark on the text, and <b>none</b> takes it off again.</div>
    </div></div>
  <div class="arow"><label class="alab" for="chfa">%(lname)s</label>
    <div class="actl"><textarea id="chfa"%(dir)s rows="2"></textarea></div></div>
%(words)s  <div class="arow" id="chkanarow" hidden><label class="alab" for="chkana">%(reading)s</label>
    <div class="actl"><input id="chkana"%(dir)s></div></div>
  <div class="arow" id="chtrrow"><label class="alab" for="chtr">%(translit)s</label>
    <div class="actl"><input id="chtr"></div></div>
  <div class="arow" id="chvocrow"><label class="alab" for="chvoc">vocabulary</label>
    <div class="actl">
      <div class="chcap">reads as</div>
      <div id="chnow"></div>
      <textarea id="chvoc" rows="4" dir="ltr" spellcheck="false"></textarea>
      <div id="chins">
        <button type="button" class="dbtn" data-ins="dw"
          title="a word, its romanisation, then what it means">\\dw{}{}</button>
        <button type="button" class="dbtn" data-ins="pw"
          title="a word of the language inside the %(gname)s">\\pw{}</button>
        <button type="button" class="dbtn" data-ins="bw"
          title="a word, its romanisation, and the phrase it makes">\\bw{}{}{}</button>
        <button type="button" class="dbtn" data-ins="vb"
          title="%(vbtitle)s">\\vb{}{}{}{}{}{}{}</button>
      </div>
      <div class="anote">The one field that is LaTeX, and the back end reads it as
        LaTeX: <code>\\dw{word}{romanisation} what it means</code>, entries divided by
        <code>;</code> &mdash; <code>\\pw{word}</code> for a word of the language inside the
        %(gname)s, <code>\\bw{word}{romanisation}{the phrase}</code>, and
        <code>\\vb{verb}{rom}{%(pres)s}{rom}{%(past)s}{rom}{to do}</code>. Nothing else
        is allowed in, and <b>reads as</b> above is this line set the way the gloss and
        the hover cloud set it.</div>
    </div></div>
  <div class="arow" id="chenrow"><label class="alab" for="chen">%(meaning)s</label>
    <div class="actl"><textarea id="chen"%(gdir)s rows="2"></textarea></div></div>
  <div class="arow" id="chfreerow"><span class="alab">the source</span>
    <div class="actl">
      <label class="achk"><input type="checkbox" id="chfree">
        this paragraph need not reproduce <code>source/paras/</code></label>
      <div class="anote">The check that a paragraph still reproduces the text it was
        made from is what stops a model, or a careless edit of a file, quietly
        rewriting the book &mdash; and it stays on for every other paragraph. Ticked,
        <b>this paragraph is yours</b>: an edit that departs from the source is written
        instead of refused, and <code>verify_book.py</code> reports the paragraph as not
        checked rather than as a fault. It is the PARAGRAPH and not the chunk because
        the check is: every chunk under one <code>\\parnum</code> is joined before it is
        compared, so one chunk departing takes its paragraph with it.</div>
    </div></div>
  <div class="arow" id="chdivrow"><span class="alab">where it ends</span>
    <div class="actl">
      <button type="button" id="chsplit">cut this chunk in two&hellip;</button>
      <button type="button" id="chjoin">join it to the next&hellip;</button>
      <button type="button" id="chjoinp">join the previous to it&hellip;</button>
      <div class="anote">A chunk is a sense group, and where the groups fall is a
        judgement somebody makes while reading &mdash; an LLM&#8217;s first pass
        most of all. These move the boundary and change no letter: both show what
        they propose, field by field, before anything is written.</div>
    </div></div>
  <div class="arow" id="chrgnrow"><span class="alab">an LLM</span>
    <div class="actl">
      <button type="button" id="chrgn">gloss around here with an LLM&hellip;</button>
      <div class="anote">The sheet that copies a prompt for a chatbot and fills the
        chunks in from its answer, opened on this chunk's sentence &mdash; stretch it
        there to take more. What somebody has glossed already is left as it is
        unless you say otherwise in it.</div>
    </div></div>
  <div class="arow afoot"><span class="alab"></span>
    <div class="actl">
      <button type="button" id="chsave">save chunk <span class="kbd">Ctrl+&#8629;</span></button>
      <button type="button" id="chrevert" title="put the boxes back to what the .tex holds">revert</button>
      <button type="button" id="chdel" title="empty this chunk's transliteration, vocabulary and meaning (and its reading) &mdash; the text, the colour and the word line stay; undo delete puts the gloss back">delete gloss</button>
      <button type="button" id="chundo" hidden title="write the deleted gloss back">undo delete</button>
      <span id="chstat"></span>
    </div></div>
  </div>
  </div>
</form>
<div id="fdback" hidden></div>
<form id="fdbox" lang="en" dir="ltr" hidden autocomplete="off">
  <div class="ahead">folded away<span class="sp"></span>
    <button type="button" id="fdcancel" title="close (Esc)">&#10005;</button></div>
  <div class="nstate" id="fdsum">&hellip;</div>
  <div class="arow"><span class="alab">fold</span>
    <div class="actl">
      <div id="fdpick"></div>
      <div class="nrow">
        <button type="button" id="fddo" class="primary" disabled>fold these away</button>
      </div>
      <div class="anote">The text of a folded run is not shown, and reading walks past
        it: with a narration the playhead jumps from the subparagraph before the run to
        the first one after, and with no narration the arrows do the same. It is kept
        with the book &mdash; in <code>reading.json</code>, which travels in a bundle
        &mdash; so it is the edition that is folded, not one machine's view of it. The
        bar the run leaves behind opens it on the page whenever you want to look.</div>
    </div></div>
  <div class="arow"><span class="alab">folded</span>
    <div class="actl"><div id="fdlist" class="nrow"></div></div></div>
  <div class="arow afoot"><span class="alab"></span>
    <div class="actl"><button type="button" id="fdclose">close</button>
      <span id="fdstat"></span></div></div>
</form>
<div id="rgback" hidden></div>
<form id="rgbox" lang="en" dir="ltr" hidden autocomplete="off">
  <div class="ahead">gloss a stretch with an LLM<span class="sp"></span>
    <button type="button" id="rgcancel" title="close (Esc)">&#10005;</button></div>
  <div class="nstate">Pick a stretch of the book, copy the prompt into a chatbot, and
    paste its answer back here: the chunks it glosses are written into the book the
    way the chunk sheet writes one.</div>
  <div class="arow"><span class="alab">stretch</span>
    <div class="actl">
      <div id="rgpick"></div>
      <div class="anote">Whole sentences are sent, each divided into its chunks as it is
        now: the answer fills them and may not cut or join them. A paragraph folded
        away is left out of the prompt and of the fill. What is filled is the stretch
        picked <b>when you press fill</b>: a sentence of the answer outside it is left
        out, and listed.</div>
    </div></div>
  <div class="arow"><span class="alab">what</span>
    <div class="actl">
      <label class="achk"><input type="checkbox" id="rgregloss">
        re-gloss what is already glossed</label>
      <div class="anote">its glosses are not sent, and the answer replaces them</div>
      <label class="achk"><input type="checkbox" id="rgperfield">
        also fill the empty boxes of partly glossed chunks</label>
      <div class="anote">otherwise a chunk with any gloss is left exactly as it is</div>
      <div class="anote">What these say when you press <b>fill from the answer</b> is
        what decides, and it is decided from the files as they are then: a gloss
        written since the prompt was copied is kept like any other.</div>
    </div></div>
  <div class="arow"><span class="alab">prompt</span>
    <div class="actl">
      <!-- copy the prompt, its size, what to do next, and the prompt itself to
           copy by hand where the clipboard is refused: drawn by lib/llmrow.js
           (the row keeps this sheet's ids: #rgcopy, #rgoutrow, #rgout) -->
      <div id="rgrow"></div>
      <div id="rgsum" class="nstate" role="status" aria-live="polite"></div>
    </div></div>
  <div class="arow"><label class="alab" for="rgans">the LLM's answer</label>
    <div class="actl">
      <textarea id="rgans" rows="7" spellcheck="false"
        placeholder="paste the chatbot's whole reply here &mdash; if it answered in several messages, paste them all, one under the other"></textarea>
      <div class="nrow">
        <button type="button" id="rgfill" class="primary" disabled>fill from the answer</button>
      </div>
      <div class="anote">Only whole glosses are written: a chunk the answer leaves
        half glossed, whose text does not match the page, or that it divides
        differently is left out and listed. Every chunk written can be corrected,
        or its gloss deleted, in its own sheet afterwards.</div>
    </div></div>
  <div class="arow" id="rgreprow" hidden><span class="alab">result</span>
    <div class="actl"><div id="rgreport" role="status" aria-live="polite"></div></div></div>
  <div class="arow afoot"><span class="alab"></span>
    <div class="actl"><button type="button" id="rgclose">close</button></div></div>
</form>
<div id="secback" hidden></div>
<form id="secbox" lang="en" dir="ltr" hidden autocomplete="off">
  <div class="ahead">chapters and sections<span class="sp"></span>
    <button type="button" id="seccancel" title="close (Esc)">&#10005;</button></div>
  <div class="nstate" id="secsum">&hellip;</div>
  <div id="secpick"></div>
  <div class="arow" id="secchrow" hidden><span class="alab">chapter</span>
    <div class="actl">
      <div class="nrow">
        <input id="secchname" type="text" placeholder="what this chapter is called">
        <button type="button" id="secchdo" class="primary">name it</button>
      </div>
      <div class="anote">Shown under the chapter's number in the text, and beside it
        in the contents. Leave the box empty and press the button to take a name
        away: the chapter is then called by its number alone, as it was before.</div>
    </div></div>
  <div class="arow" id="secrow" hidden><span class="alab">section</span>
    <div class="actl">
      <div class="nrow">
        <input id="secname" type="text" placeholder="what this section is called">
        <button type="button" id="secdo" class="primary">start a section here</button>
        <button type="button" id="secdel" hidden>remove this section</button>
      </div>
      <div class="anote">A section marks a place between two paragraphs: the one you
        pick is where it starts. It has <b>no number of its own</b> and it changes
        no paragraph's number &mdash; it is a heading in the text and a row in the
        contents, nothing more. The mark is written into the chapter's own file, so
        it travels with the book when you download it.</div>
    </div></div>
  <div class="arow afoot"><span class="alab"></span>
    <div class="actl"><button type="button" id="secclose">close</button>
      <button type="button" id="secreload" hidden>reload the reader</button>
      <span id="secstat"></span></div></div>
</form>
<div id="dvback" hidden></div>
<form id="dvbox" lang="en" dir="ltr" hidden autocomplete="off">
  <div class="ahead"><span id="dvtitle"></span><span class="sp"></span>
    <button type="button" id="dvcancel" title="close (Esc)">&#10005;</button></div>
  <div id="dvwhere"></div>
  <div id="dvpair"></div>
  <div id="dvnotes"></div>
  <div class="arow afoot"><span class="alab"></span>
    <div class="actl">
      <button type="button" id="dvdo">divide</button>
      <span id="dvstat"></span>
    </div></div>
</form>
<div id="ntback" hidden></div>
<div id="ntbox" hidden>
  <div class="ahead"><span id="nttitle">note</span><span class="sp"></span>
    <button type="button" id="ntedit" title="write this note">edit</button>
    <button type="button" id="ntread" hidden title="back to the note as it reads">read</button>
    <button type="button" id="ntclose" title="close (Esc)">&#10005;</button></div>
  <iframe id="ntframe" title="a note beside this book"></iframe>
</div>""" % {"lname": esc(LANG.name.lower()), "dir": dir_attrs,
              # the word line, under the text it divides, for a language
              # divided into words (the strip is buttons and boxes of its
              # own, so the row is labelled by a span and not a label)
              "words": ('  <div class="arow" id="chwordsrow" hidden><span class="alab">words</span>\n'
                        '    <div class="actl" id="chwords"></div></div>\n'
                        if LANG.words else ""),
              "reading": esc(LANG.reading_label or "reading"),
              "translit": esc(LANG.translit_label),
              "meaning": esc(meaning_label()), "gdir": gloss_dir_attrs(),
              "gname": esc(GLOSS.name),
              "pres": esc(pres), "past": esc(past), "vbtitle": esc(vb_title)}


def page(body, times, subs, audio_rel, meta, tocpanel, src, narr=(), paras=(),
         folded=(), free=(), bounds=()):
    attrs = LANG.html_attrs()                       # ' lang="fa" dir="rtl"'
    # meta["narration"] and not audio_rel: a book whose recording has been
    # moved away still has timings and a book.json naming it, and those are
    # exactly what the three shapes differ over -- so it is offered the
    # choice even though nothing here can play
    dl_control = download_html(meta.get("narration"))
    # the dashboard's text fields take the language's direction only when it
    # is RTL: an LTR field needs no attribute, and a lang alone is enough
    dir_attrs = attrs if LANG.rtl else ' lang="%s"' % esc(LANG.code)
    html_page = """<!doctype html>
<html%s data-lang="%s"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s &mdash; Parseh</title>
<link rel="stylesheet" href="__LIB__/parseh.css">
<link rel="stylesheet" href="__LIB__/langs.css">
<script src="__LIB__/wordline.js"></script>
<script src="__LIB__/parseh.js"></script>
<script src="__LIB__/llm.js"></script>
<script src="__LIB__/llmrow.js"></script>
<script src="__LIB__/mt.js"></script>
<link rel="stylesheet" href="__LIB__/decomposition.css">
<script src="__LIB__/decomposition.js"></script>
<link rel="stylesheet" href="__LIB__/cardkit.css">
<script src="__LIB__/cardkit.js"></script>
<link rel="stylesheet" href="__LIB__/timeline.css">
<script src="__LIB__/timeline.js"></script>
<style>%s
%s</style>
</head><body class="%s">
<header lang="en" dir="ltr"><div class="hrow">
  <a class="home glyph" href="__HUB__" title="Parseh &mdash; the hub">&#x67E;</a>
  <a class="home" href="__LIBRARY__" title="all books">&#9636;</a>
  <button id="play" title="play / pause (space)" style="min-width:38px;font-size:15px">&#9654;</button>
  <button id="cont" title="keep playing into the next line instead of stopping at the end of each one">keep going</button>
  <button id="loop" title="repeat this subparagraph (R)">loop</button>
  <button id="stopbnd" title="when a new chapter or section begins, stop there and wait for play">stop at a change</button>
  <button id="listen" title="play the recording on its own, without following the text — it holds where the text is folded, ready to go on after it">listen</button>
  <span id="seekwrap" style="display:none">
    <input id="seek" type="range" min="0" max="1000" value="0" step="1"
           title="where the recording plays from: drag it anywhere, folded or not"
           style="width:150px;vertical-align:middle"></span>
  <button id="listenfollow" disabled title="highlight the sentence being said while the recording plays on its own, the way a video’s captions follow the video — it moves with the sound but no longer stops it at a sentence’s end. Not needed: everything above works the same without it">highlight</button>
  <button id="listenscroll" disabled title="and scroll to keep it in view. Off, the highlight still moves — follow it by scrolling yourself">keep in view</button>
  <span id="gapwrap" style="display:none;font-size:12px;color:var(--dim)">between repeats
    <select id="gap" title="pause between repeats">
      <option value="0">0s</option><option value="0.5">0.5s</option>
      <option value="1">1s</option><option value="1.5">1.5s</option>
      <option value="2">2s</option><option value="3">3s</option>
      <option value="5">5s</option>
    </select></span>
  <select id="speed" title="speed">
    <option>0.25</option><option>0.5</option><option>0.6</option><option>0.75</option>
    <option>0.9</option><option selected>1</option><option>1.1</option>
    <option>1.25</option><option>1.5</option><option>1.75</option><option>2</option>
  </select>
%s
  <button data-toggle="nogloss" title="glosses (G)">gloss</button>
  <button id="hovermode" title="%(HOVER)s">hover</button>
  <button id="dictmode" hidden title="look the words of an unglossed chunk up in a dictionary">dictionary</button>
  <button id="defmode" hidden disabled>definitions</button>
  <button id="defmt" hidden disabled>translated</button>
  <a id="lookupset" href="__HUB__settings/reading-help/" title="get a dictionary for this language, to look words up where nothing is glossed">reading help</a>
  <span class="sp"></span>
  <span id="warn" style="display:none;font-size:12px;color:var(--danger)">
    audio not seekable — <label style="text-decoration:underline;cursor:pointer">
    pick the file<input id="pick" type="file" accept="audio/*" hidden></label></span>
  <span id="pos">0:00 / 0:00</span>
  <span id="build" style="font-size:11px;color:var(--faint)" title="build id"></span>
  <span id="pdfstale" hidden></span>
  </div><div class="hrow">
  <button id="toc" title="jump to a paragraph (C)" aria-expanded="false">contents</button>
  <button id="bookinfo" title="edit the title, the author and the other details this book is filed under">book info</button>
  <button id="buildbook" title="build this book's PDF, and its reader with it, on the server (./build.sh)">build PDF</button>
  <button id="buildhtml" title="rebuild this page alone, without LaTeX — what a book built before a new feature needs to gain it">rebuild the reader</button>
  <button id="theme" data-parseh-theme title="theme: light / dark / sepia">◐</button>
  <button id="typo" title="text size and margins">Aa</button>
  <button id="narr" title="the recordings of this book: add one, align one, or take one off">narration</button>
  <button id="fold" title="fold a run of paragraphs away: the text is not shown, and the narration skips it">fold</button>
  <button id="rgn" title="copy a prompt that has an LLM gloss a stretch of the book, and fill in its answer">gloss with an LLM</button>
  <button id="editmode" title="edit the subparagraph timings">edit times</button>
  <button id="editbyear" title="move where each subparagraph starts, by ear, over a picture of the sound">edit times by ear</button>
  <button id="savetimes" style="display:none">save times</button>
  <button id="droptimes" style="display:none" title="throw away every unsaved timing edit">discard edits</button>
  <span id="editmsg" style="font-size:12px;color:var(--dim)"></span>
  <span class="sp"></span>
%s
  <button id="stopsrv" title="stop the local server">stop server</button>
  <button id="bars" type="button" aria-expanded="true"
          title="Put the bars away and give the whole window to the text">&#8963; hide bars</button>
</div><div class="hrow" id="scrub" hidden>
  <span class="snote">the narration</span>
  <audio id="audio" preload="metadata" controls%s></audio>
  <span class="snote">play it; in <b>edit times</b>, &#9673; stamps a subparagraph's start or end at the playhead</span>
</div></header>
<button id="barsback" type="button" class="bars-show" hidden
        aria-expanded="false" title="Bring the bars back">&#8964; show bars</button>
%s
<div id="cloud" lang="en" dir="ltr" hidden></div>
<button id="chpen" type="button" hidden title="write this chunk: its text, its gloss, its colour (E)">&#9998;</button>
<div id="ankiback" hidden></div>
<form id="anki" lang="en" dir="ltr" hidden autocomplete="off">
  <div class="ahead"><span id="ahtitle">anki card</span> <span id="aref"></span><span class="sp"></span>
    <button type="button" id="acancel" title="close (Esc)">&#10005;</button></div>
  <!-- WHERE THE CARD GOES.  Anki, as it always went; an exercise deck of
       this toolbox's, as an exercise with a link back to this page; or a
       :::exercise flashcard block on the clipboard, for a studio document or
       a deck's Add exercise.  The sheet below is the same one, less the rows
       the choice has no use for. -->
  <div class="arow"><span class="alab">to</span>
    <div class="actl atarget" role="group" aria-label="where the card goes">
      <button type="button" id="atanki" class="on" aria-pressed="true" title="a note in one of your Anki decks, built into an .apkg to import">Anki</button>
      <button type="button" id="atdeck" aria-pressed="false" title="an exercise in one of the toolbox's exercise decks, studied on the deck's page">exercise deck</button>
      <button type="button" id="atmd" aria-pressed="false" title="a :::exercise flashcard block on the clipboard, to paste into a studio document or a deck's Add exercise">markdown</button>
    </div></div>
  <div class="arow" id="adeckrow">
    <label class="alab" for="adeck">deck</label>
    <div class="actl">
      <select id="adeck"></select>
      <input id="adecknew" placeholder="name the new deck (use :: to nest)" hidden>
    </div>
  </div>
  <div class="arow"><span class="alab">type</span>
    <div class="actl akind">
      <button type="button" id="akvocab" class="on">vocabulary</button>
      <button type="button" id="akopp">opposites</button>
      <button type="button" id="akjolly" hidden title="a front and a back of your own, each any studio markdown">jolly</button>
    </div></div>
  <div class="arow" id="afarow"><label class="alab" for="afa">%s</label>
    <div class="actl"><textarea id="afa"%s rows="1"></textarea></div></div>
  <div class="arow" id="akanarow"%s><label class="alab" for="akana">reading</label>
    <div class="actl"><input id="akana"%s placeholder="the kana of the whole chunk"></div></div>
  <div class="arow" id="atrrow"><label class="alab" for="atr">translit.</label>
    <div class="actl"><input id="atr"></div></div>
  <div class="arow" id="aenrow"><label class="alab" for="aen">%(MEANING)s</label>
    <div class="actl"><textarea id="aen"%(GDIR)s rows="2"></textarea></div></div>
  <div class="arow" id="actxrow"><label class="alab" for="actx">context</label>
    <div class="actl"><textarea id="actx"%s rows="2"></textarea></div></div>
  <div class="arow" id="aopprow" hidden><label class="alab" for="aopp">opposite</label>
    <div class="actl">
      <textarea id="aopp"%s rows="1" placeholder="&#8230;the opposite, written by you"></textarea>
      <input id="aoppkana"%s%s placeholder="its reading (kana)">
      <input id="aopptr" placeholder="its transliteration (optional)">
    </div></div>
  <div class="arow" id="anotesrow"><label class="alab" for="anotes">notes</label>
    <div class="actl"><textarea id="anotes" rows="3"></textarea></div></div>
  <div class="arow" id="atagsrow"><label class="alab" for="atags">tags</label>
    <div class="actl"><input id="atags"></div></div>
  <div class="arow" id="asrcrow"><label class="alab" for="asrc">source</label>
    <div class="actl"><input id="asrc"></div></div>
  <div class="arow" id="adirrow"><span class="alab">direction</span>
    <div class="actl adir" id="adir" data-from="%(A)s" data-to="%(B)s">
      <button type="button" class="dbtn on" data-dir="both" id="adirboth" title="two cards: %(A)s &rarr; %(B)s and %(B)s &rarr; %(A)s">&#8646; both</button>
      <button type="button" class="dbtn" data-dir="both-random" id="adirrnd" hidden title="one card that shows %(A)s first or %(B)s first, drawn each time it is shown">&#8646; both (random)</button>
      <button type="button" class="dbtn" data-dir="forward" id="adirfwd" title="one card: %(A)s &rarr; %(B)s">&rarr; %(A)s &rarr; %(B)s</button>
      <button type="button" class="dbtn" data-dir="reverse" id="adirrev" title="one card: %(B)s &rarr; %(A)s &mdash; for a meaning whose %(A)s side lists several words, each asked separately by its own forward-only card">&larr; %(B)s &rarr; %(A)s only</button>
    </div></div>
  <!-- A JOLLY CARD: its own front and back, a main line and a smaller one
       under it on each side, and any studio markdown in all four -- an
       exercise deck and a studio document draw it; Anki has no such note. -->
  <div id="ajollyrow" hidden>
    <div class="arow"><label class="alab" for="ajfp">front</label>
      <div class="actl">
        <textarea id="ajfp" rows="2" dir="auto" title="front-primary: the front's main line" placeholder="the front"></textarea>
        <textarea id="ajfs" rows="2" dir="auto" aria-label="front, the smaller line" title="front-secondary: a smaller line under it" placeholder="a smaller line under it (optional)"></textarea>
      </div></div>
    <div class="arow"><label class="alab" for="ajbp">back</label>
      <div class="actl">
        <textarea id="ajbp" rows="2" dir="auto" title="back-primary: the back's main line" placeholder="the back"></textarea>
        <textarea id="ajbs" rows="2" dir="auto" aria-label="back, the smaller line" title="back-secondary: a smaller line under it" placeholder="a smaller line under it (optional)"></textarea>
      </div></div>
    <div class="arow"><span class="alab"></span>
      <div class="actl anote">Any studio markdown: paragraphs, lists, tables, &gt; boxes,
        pictures, recordings. A side needs one of its two. A recording cut below goes
        into the box the cursor was last in (the back's main text until one has been).</div></div>
  </div>
  <!-- THE RECORDING: this stretch of the narration, cut to the word by ear
       (lib/cardkit.js), kept in the clip tray and put on one side of the card -->
  <div class="arow" id="asndrow"><span class="alab">recording</span>
    <div class="actl">
      <button type="button" id="asnd">&#128266; cut the audio&hellip;</button>
      <div class="anote" id="asndwhy" hidden></div>
      <div id="asndprev" hidden>
        <div class="asndplay">
          <audio id="asndaudio" controls preload="metadata"></audio>
          <button type="button" id="asnddel" title="take the recording off the card">remove</button>
        </div>
        <span id="asndname"></span>
        <div class="asndside" id="asndsides">
          <label class="asndpick"><input type="radio" name="asndside" value="front" checked> <span id="asndfront">on the %(A)s side</span></label>
          <label class="asndpick"><input type="radio" name="asndside" value="back"> <span id="asndback">on the %(B)s side</span></label>
        </div>
        <span class="ajollyinto" hidden>in the jolly box the cursor was last in (the back's main text until one has been)</span>
      </div>
    </div></div>
  <div class="arow afoot"><span class="alab"></span>
    <div class="actl">
      <button type="button" id="asave"><span id="asavelab">save card</span> <span class="kbd">Ctrl+&#8629;</span></button>
      <button type="button" id="apreview" title="how the finished card will look in Anki, both directions">preview card</button>
      <button type="button" id="abuild" title="build the deck's .apkg and download it">build .apkg</button>
      <span id="astat" role="status"></span>
    </div></div>
  <!-- the markdown, where the clipboard could not be reached: to copy by hand -->
  <div class="arow" id="amdrow" hidden><label class="alab" for="amdout">markdown</label>
    <div class="actl"><textarea id="amdout" rows="8" readonly></textarea>
      <div class="anote">the clipboard could not be reached: select this and copy it</div></div></div>
  <div class="arow" id="apvrow" hidden>
    <span class="alab">preview</span>
    <div class="actl">
      <iframe id="apvframe" sandbox="allow-same-origin" title="card preview"></iframe>
      <div class="anote"><span id="apvnote">rendered with the very templates and styles the
        .apkg carries &mdash; the line is where Anki flips to the answer</span>
        <button type="button" id="apvhide">hide</button></div>
    </div>
  </div>
</form>
<div id="narrback" hidden></div>
<form id="narrbox" lang="en" dir="ltr" hidden autocomplete="off"
      role="dialog" aria-modal="true" aria-label="the narration of this book"
      tabindex="-1">
  <div class="ahead">narration <span id="nref"></span><span class="sp"></span>
    <button type="button" id="ncancel" title="close (Esc)">&#10005;</button></div>

  <!-- everything below the head scrolls; the head and the close button do not -->
  <div class="nmain" id="nmain">

    <!-- WHAT THIS BOOK'S NARRATION IS.  One line of counts, one line of what
         is wrong, one line of what to do about the state it is in, and one
         row of actions -- and every one of those actions is about the BOOK.
         What is about a recording is in that recording's row. -->
    <div class="nhead">
      <div class="nsum" id="nsum" aria-live="polite">&hellip;</div>
      <div class="nwarn" id="nwarn" hidden></div>
      <div class="nnote" id="nnote" hidden></div>
      <div class="nacts nheadacts">
        <button type="button" class="primary" id="naddbtn" aria-expanded="false"
                aria-controls="nadd">add a recording&hellip;</button>
        <button type="button" class="ghost" id="nedittimes">edit times by hand</button>
        <!-- export and import are one thing said twice, and neither is what
             somebody came here for: behind one menu, as the deck page puts
             its two exports, so the row stays scannable -->
        <details class="ndrop" id="nkeep">
          <summary class="nbtn" title="the narration file: the audio, the transcript and the times in one zip">keep it &#9662;</summary>
          <div class="nmenu">
            <a id="nexport" href="__narration/export" download>export a narration file</a>
            <label class="nimport">import a narration file&hellip;<input id="npimport"
                type="file" accept=".zip,application/zip" hidden></label>
          </div>
        </details>
        <button type="button" class="ghost npush" id="nhowbtn" aria-expanded="false"
                aria-controls="nhow">how this works</button>
      </div>
      <div class="nbar" id="nbarwrap" hidden><i id="nabar"></i></div>
      <div class="nstate" id="nwork"></div>
      <pre id="nlog" hidden></pre>
    </div>

    <!-- THE PAGE ON SCREEN IS FROM BEFORE.  Most doors here end by running
         tex2html.py again, and this page has TIMES/SUBS/NARR/META baked into
         it: a bar that stays, rather than a button hidden in the footer. -->
    <div class="nredo" id="nredo" hidden>
      <span>The reader was rebuilt &mdash; what is on this page is from before.</span>
      <button type="button" class="primary small" id="nreload">reload the reader</button>
    </div>

    <!-- ADD A RECORDING.  The outline belongs to THIS file and to nothing
         else: a row says what it covers in its own drawer, so this can never
         be read by an action somebody did not mean. -->
    <div class="nsec" id="nadd" hidden>
      <div class="nsechead">add a recording</div>
      <div class="nfield"><span class="nfieldlab">covers</span></div>
      <div class="npick" id="naddpick"></div>
      <div class="nfield">
        <label class="nbtn primary">pick the audio file<input id="npaudio" type="file"
            accept="audio/*,.webm,.m4a,.opus,.ogg" hidden></label>
        <span class="nstate" id="naudio"></span>
      </div>
      <div class="anote">mp3, m4a, webm, ogg, wav&hellip; The file is copied into
        <code id="ndir">books/&lsaquo;book&rsaquo;/audio/</code> &mdash; a narration is
        yours, never committed &mdash; and the reader is rebuilt with it at once.
        Pick a stretch and the file joins the recordings already here, and is given a
        first guess at its times as it lands. Leave it at <i>the whole book</i> and it
        becomes the book's one recording &mdash; which, on a book that already has one,
        means that one stops being the narration; you are asked first, by name.</div>
    </div>

    <!-- A NARRATION LEFT SOMEWHERE ELSE: by an earlier layout of the toolbox,
         or put there by hand.  Using one keeps the times already measured. -->
    <div class="nsec" id="nfound" hidden>
      <div class="nsechead">found elsewhere</div>
      <div class="nlist2" id="nfoundlist"></div>
      <div class="anote">Using one points <code>book.json</code>'s own <code>audio</code>
        at that file and keeps the times already in <code>timings.json</code>; nothing is
        re-aligned. It does not join the list of recordings below &mdash; that is what
        <b>add a recording&hellip;</b> is for.</div>
    </div>

    <div class="nlisthead" id="nlisthead" hidden><span class="nlabel">the recordings</span>
      <span class="ncount" id="ncount"></span></div>
    <div id="nlist" hidden></div>

    <div class="nempty" id="nempty" hidden>
      <div data-x="empty-none">
        <p>No recording yet.</p>
        <p>Press <b>add a recording&hellip;</b> above. The audio alone is enough to
          start: a recording that names the stretch it is of is shared out over that
          stretch as it lands, so it plays at once and what drifts can be nudged by ear
          afterwards. A transcript with timestamps is what makes an <b>align</b>
          possible, and it can come later, or never.</p>
      </div>
      <div data-x="empty-orphan" hidden>
        <p><code>timings.json</code> holds times, but no recording is on the shelf.</p>
        <p>Pick the file with <b>add a recording&hellip;</b>, use one of the files
          <b>found elsewhere</b>, or <b>import a narration file</b>. The times already
          saved are kept whichever way it comes back.</p>
      </div>
    </div>

    <!-- THE PROSE, ALL OF IT, BEHIND ONE BUTTON.  It is worth keeping -- it is
         how somebody gets a transcript at all -- but it is read once and then
         never again, so it must not sit between a person and the buttons. -->
    <div class="nsec" id="nhow" hidden>
      <div class="nsechead">how this works</div>
      <div class="anote"><b>A recording, and the stretch of text it is of.</b> A book can
        be read a part at a time: each file says which subparagraphs it covers, each is
        timed on its own, and re-timing one touches nothing else. A book read in one
        sitting is one recording covering the whole book, which is what every book had
        before this existed.</div>
      <div class="anote"><b>A transcript is a time index, never a text:</b> not a word of
        it goes into the book. Any of: YouTube's transcript panel copied whole
        (<i>&hellip; more &rsaquo; Show transcript</i>, click into the panel, select all,
        copy &mdash; the &ldquo;N seconds&rdquo; lines can stay); an <code>.srt</code> or
        <code>.vtt</code>; or, for a recording of your own, whisper's output:
        <code>whisper narration.m4a --language %s --output_format srt</code>
        (<code>pip install openai-whisper</code>). It belongs to one recording: a book in
        parts has one transcript per part, saved from that part's own row.</div>
      <div class="anote"><b>align</b> needs that transcript. The transcript says roughly
        <i>when</i>, the text says <i>what</i>, the cuts are snapped to the silences in the
        audio, and the times go into the <code>.tex</code> as comments and into
        <code>timings.json</code>. A whole novel takes a minute or two.
        <b>estimate times</b> needs no transcript at all: it shares the recording out over
        the stretch it covers in proportion to the length of each subparagraph &mdash; a
        first guess to play and to nudge, which a real alignment later replaces without
        being asked twice. Needs <span id="ntools">&hellip;</span>.</div>
      <div class="anote"><b>Then.</b> Every timed subparagraph plays on a click, &#9654;
        and the arrow keys walk through them, and <b>edit times</b> in the header fixes
        any that drift, or stamps the ones that have no time yet.</div>
      <div class="anote"><b>Keeping it.</b> <b>export</b> writes the audio, the
        transcript, the times and a manifest into one file, to keep beside the book or to
        hand to another reader of the same edition; <b>import</b> takes such a file on
        another copy and lays it over this book's audio, transcript and
        <code>timings.json</code> &mdash; the times fixed by hand included &mdash; keeping
        the previous <code>timings.json</code> beside it as
        <code>audio/timings.before-import.json</code>.</div>
    </div>

    <div class="afoot"><button type="button" id="nclose">close</button></div>
  </div>
</form>

<!-- A QUESTION WITH A DANGEROUS ANSWER, in a sheet of its own ABOVE the panel
     (90/91, as the divide sheet sits above the chunk sheet) and with its own
     backdrop, so that a cancel comes back to the row it was asked about
     instead of closing everything.  IT DOES NOT CLOSE WHEN THE WORK STARTS:
     the deck page's dialogs hold their ground until the work is done, because
     a refusal is unreadable in a sheet that has already gone -- and the tick
     that answers a refusal asking for --force is right there to turn on and
     press again.  Outside the form: it is the panel's question, not one of
     its fields. -->
<div id="naskback" hidden></div>
<div id="naskbox" lang="en" dir="ltr" hidden role="dialog" aria-modal="true"
     aria-labelledby="nasktitle">
  <h3 id="nasktitle"></h3>
  <div class="nstate" id="naskhint"></div>
  <label class="achk" id="naskforce" hidden><input type="checkbox" id="naskforcebox">
    <span id="naskforcelab"></span></label>
  <div class="nstate" id="naskerr" hidden></div>
  <div class="naskrow">
    <button type="button" id="naskno">cancel</button>
    <button type="button" id="naskok" class="primary"></button>
  </div>
</div>
<div id="bmback" hidden></div>
<form id="bmbox" lang="en" dir="ltr" hidden autocomplete="off">
  <div class="ahead">book info<span class="sp"></span>
    <button type="button" id="bmcancel" title="close (Esc)">&#10005;</button></div>
  <div class="arow"><label class="alab" for="bmtitle">title</label>
    <div class="actl"><input id="bmtitle"></div></div>
  <div class="arow"><label class="alab" for="bmtitlelatin">translit.</label>
    <div class="actl"><input id="bmtitlelatin"></div></div>
  <div class="arow"><label class="alab" for="bmtitleen">English</label>
    <div class="actl"><input id="bmtitleen"></div></div>
  <div class="arow"><label class="alab" for="bmauthor">author</label>
    <div class="actl"><input id="bmauthor"></div></div>
  <div class="arow"><label class="alab" for="bmauthorlatin">translit.</label>
    <div class="actl"><input id="bmauthorlatin"></div></div>
  <div class="arow"><label class="alab" for="bmyear">year</label>
    <div class="actl"><input id="bmyear" style="max-width:120px"></div></div>
  <div class="arow"><label class="alab" for="bmblurb">blurb</label>
    <div class="actl"><textarea id="bmblurb" rows="2"></textarea></div></div>
  <div class="arow" id="bmreordersrow"><span class="alab">order</span>
    <div class="actl"><label><input type="checkbox" id="bmreorders" style="width:auto;margin:0 .4em 0 0;vertical-align:middle">
      read out of its written order (kanbun)</label></div></div>
  <div class="anote">title, translit. and author, translit. are also the PDF's
    title page (main.tex) &mdash; saving rewrites both, or neither if one of them
    cannot hold the new value.  The PDF itself only catches up at its next
    build (<b>build PDF</b>, in the header).</div>
  <div class="arow afoot"><span class="alab"></span>
    <div class="actl">
      <button type="button" id="bmsave">save <span class="kbd">Ctrl+&#8629;</span></button>
      <span id="bmstat"></span>
    </div></div>
</form>
%s
<main>
%s
</main>
<script>const TIMES=%s;const SUBS=%s;const NARR=%s;const PARAS=%s;const FOLDED=%s;const FREE=%s;const BOUNDS=%s;const META=%s;const LANG=%s;const GLOSS=%s;const SRC=%s;</script>
<script>%s</script>
</body></html>
"""
    # the direction buttons name both sides of the card several times over,
    # so that stretch is filled by name first; every other slot is positional
    a_side, b_side = card_sides()
    html_page = (html_page.replace("%(A)s", esc(a_side))
                          .replace("%(B)s", esc(b_side))
                          .replace("%(MEANING)s", esc(meaning_label()))
                          .replace("%(HOVER)s", esc(hover_title()))
                          .replace("%(GDIR)s", gloss_dir_attrs()))
    return html_page % (
        attrs, esc(LANG.code), esc(meta.get("title", "")), lang_tokens(), CSS,
        "" if (audio_rel or narr) else "noaudio",
        pass_buttons(),
        dl_control,
        ("" if not audio_rel else ' src="%s"' % esc(audio_rel)),
        tocpanel,
        # the dashboard: the first field named after the language (lower-case,
        # like its neighbours), the reading row only for a reading language
        esc(LANG.name.lower()), dir_attrs,
        "" if LANG.reading else " hidden", dir_attrs,
        dir_attrs, dir_attrs,
        dir_attrs, "" if LANG.reading else " hidden",
        esc(LANG.code),
        chunk_editor(dir_attrs),
        body, json.dumps(times, separators=(",", ":")),
        json.dumps(subs, separators=(",", ":")),
        json.dumps(list(narr), ensure_ascii=False, separators=(",", ":")),
        json.dumps(list(paras), ensure_ascii=False, separators=(",", ":")),
        json.dumps(list(folded), ensure_ascii=False, separators=(",", ":")),
        json.dumps(list(free), ensure_ascii=False, separators=(",", ":")),
        # where a chapter or a section begins, as subparagraph indices
        json.dumps(list(bounds), separators=(",", ":")),
        json.dumps(meta, ensure_ascii=False),
        json.dumps(LANG.as_json(), ensure_ascii=False),
        json.dumps(GLOSS.as_json(), ensure_ascii=False),
        json.dumps(src, ensure_ascii=False, separators=(",", ":")), JS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default=None,
                    help="book directory or slug (default: the current one)")
    args = ap.parse_args()
    book = find_book(args.book)
    OUT = book.reader_dir
    os.makedirs(OUT, exist_ok=True)
    fonts_rel = os.path.relpath(FONTS, OUT)
    lib_rel = os.path.relpath(LIB, OUT)           # parseh.css and parseh.js
    # the header's two home links, relative like the stylesheets: a reader
    # sits at books/<folder>/<slug>/reader/, a legacy one a level higher,
    # and a reader opened off the disk has no server to redirect for it
    hub_rel = os.path.relpath(ROOT, OUT).replace(os.sep, "/") + "/"
    library_rel = os.path.relpath(BOOKS_DIR, OUT).replace(os.sep, "/") + "/"
    # Every recording the book has, each with the stretch of text it covers.
    # A book with one -- or with only the old scalar, which is every book
    # written before this -- gets exactly one record and exactly the src it
    # always had; a book recorded in parts gets one per file and the reader
    # swaps between them.  A record whose file is not on disk is left out, so
    # the page never offers a source that cannot play.
    narr = []
    for n in book.narrations:
        if not (n["audio"] and os.path.exists(n["audio"])):
            continue
        narr.append({"id": n["id"], "src": book.rel_from_reader(n["audio"]),
                     "from": n["from"], "to": n["to"]})
    # the element's own src: the scalar's file where there is one (unchanged),
    # otherwise the first recording, so a book recorded in parts starts on the
    # part that opens it
    legacy = book.audio if (book.audio and os.path.exists(book.audio)) else None
    audio_rel = (book.rel_from_reader(legacy) if legacy
                 else (narr[0]["src"] if narr else ""))
    book.check_placement()
    set_lang(book.lang)
    set_gloss(book.gloss_lang)
    chapters = load_times(T.parse_book(book.main, LANG))
    # WHERE EACH RECORDING IS, as the first and last subparagraph it covers --
    # indices in the order SUBS has -- read the way the aligner and the server
    # read a stretch (texparse.region_bounds).  The player finds the file a
    # subparagraph is in by these; it used to compare bare labels, which
    # every chapter repeats, so a recording of chapter 2 answered for chapter
    # 1's subparagraphs of the same numbers.
    pairs = [(T.chapter_of(x), x.num)
             for ch in chapters for pp in ch.paragraphs for x in pp.subs]
    for n in narr:
        try:
            n["lo"], n["hi"] = T.region_bounds(pairs, n["from"], n["to"])
        except ValueError as e:
            n["lo"] = n["hi"] = None
            print("%s: recording %s covers nothing in this book: %s"
                  % (book.slug, n["id"], e), file=sys.stderr)
    body, times, subs, toc, src, chaps = build(chapters, LANG, GLOSS)
    shell, chap_files = one_chapter_at_a_time(chaps, body)
    tocpanel = toc_html(toc)
    os.makedirs(OUT, exist_ok=True)
    timed = sum(1 for t in subs if t[0] is not None)
    stamp = hashlib.sha1((body + tocpanel + json.dumps(subs) + CSS + JS)
                         .encode("utf-8")).hexdigest()[:6]
    meta = {"chunks": len(times), "subs": len(subs), "timed": timed,
            "paragraphs": len(toc),
            "build": stamp, "built": time.strftime("%H:%M"),
            "book": book.slug, "title": book.title,
            "title_latin": book.title_latin, "author": book.author_latin,
            "audio": bool(audio_rel),
            # Whether the download is a choice or a link.  Wider than "audio"
            # on purpose: a book whose recording has been moved away still
            # has timings.json and a book.json naming the file, and those are
            # what the text shape strips and the linked shape keeps -- so the
            # three still differ and the choice is still real.  With none of
            # the three there is nothing to strip, all three give the same
            # bytes, and the header keeps its single link.
            "narration": bool(book.has_audio or book.meta.get("audio")
                              or os.path.exists(book.timings)),
            # book.json's "reorders": true, a text read out of its written
            # order (kanbun), whose words the word strip does not compare
            # with a chunk's reading
            "reorders": book.reorders,
            "lang": LANG.code, "dir": LANG.dir,
            "chapters": sorted({c.label for c in chapters}),
            # book.json's own fields, by book.json's own names -- unlike
            # "title" and "author" above (kept as they are for the anki
            # dashboard, which wants title_latin and author_latin and calls
            # the second one "author"), this is what the book-info sheet
            # reads and writes, so it needs the native author too and the
            # three fields nothing else on this page has ever wanted
            "editable": {"title": book.title, "title_latin": book.title_latin,
                        "title_en": book.meta.get("title_en", ""),
                        "author": book.author, "author_latin": book.author_latin,
                        "year": book.meta.get("year", ""),
                        "blurb": book.meta.get("blurb", ""),
                        # a switch: a text read out of its written order
                        "reorders": book.reorders}}
    # what somebody has folded away, and every paragraph's span of
    # subparagraphs so the player can walk past a folded run without asking
    # the page (a chapter still in its own file has no elements to ask)
    decided = reading.load(book.dir)
    html_out = page(shell, times, subs, audio_rel, meta, tocpanel, src, narr,
                    chaps.get("paras") or [], decided["collapsed"], decided["free"],
                    chaps.get("bounds") or [])
    html_out = (html_out.replace("__FONTS__", fonts_rel).replace("__LIB__", lib_rel)
                .replace("__HUB__", hub_rel).replace("__LIBRARY__", library_rel))
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html_out)
    for name, piece in chap_files:
        open(os.path.join(OUT, name), "w", encoding="utf-8").write(piece)
    # a book that has lost a chapter since the last build must not be read
    # with yesterday's still lying beside it
    keep = {name for name, _ in chap_files}
    for old in sorted(os.listdir(OUT)):
        if CHAP_FILE_RE.fullmatch(old) and old not in keep:
            os.remove(os.path.join(OUT, old))
    size = os.path.getsize(os.path.join(OUT, "index.html"))
    if chap_files:
        print("reader/  %d chapter files, %.1f MB in all"
              % (len(chap_files),
                 (size + sum(len(p.encode("utf-8")) for _, p in chap_files)) / 1e6))
    print("reader/index.html  %.1f MB  [%s glossed in %s, passes %s]"
          % (size / 1e6, LANG.code, GLOSS.code, "/".join(LANG.pass_keys)))
    print("subparagraphs: %d, with audio: %d, without: %d  (%d chunks)"
          % (len(subs), timed, len(subs) - timed, len(times)))
    # the two counts differ only if a paragraph ran across two files, which is
    # worth seeing rather than hiding
    print("paragraphs: %d, contents entries: %d"
          % (sum(len(ch.paragraphs) for ch in chapters), len(toc)))
    print("chapters:", ", ".join(str(c.label) for c in chapters))


if __name__ == "__main__":
    main()
