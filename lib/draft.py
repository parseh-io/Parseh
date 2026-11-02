#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Start a book or a video from nothing: the text, cut up, every gloss blank.

    import draft
    draft.book_from_text(text, lang, title, gloss, ...)        -> a book's files
    draft.video_from_transcript(transcript, lang, gloss, ...)  -> a video's

Everything a learner reads in this toolbox has so far been written by asking
a model.  This is the other way in: a person who knows the language is handed
the text already divided, with the transliteration, the vocabulary and the
meaning left empty, and fills them in themselves -- in the reader, in the
player, or in the file itself, which is a file they can open in an editor and
find-and-replace through.

A draft declares two languages, and they are not one question: `lang` is what
the book or the video TEACHES, `gloss` is what its meanings will be WRITTEN
IN -- an Italian drafting an English reader glosses it in Italian.  The gloss
is written into book.json / video.json, and for a book into main.tex as
\\BookGloss beside \\BookLang, so that the preamble sets the gloss column in
the language it is actually in and hyphenates it by that language's rules.
Nothing said means English, which is what every draft made before the field
existed meant.

WHAT "EMPTY" MEANS, AND WHY IT STOPS WHERE IT DOES
--------------------------------------------------
The text is given.  The translation, the transliteration, the reading and the
vocabulary are not, and nothing here invents them.  Between those two lies
the division of the text, and it is three cuts, not one:

  * into PARAGRAPHS -- mechanical.  A blank line ends one; a text with no
    blank line in it is taken a line to a paragraph, which is how a pasted
    chapter usually arrives.  The book pipeline already keeps them one to a
    file (source/paras/chN_pNN.txt), and this writes exactly those files.
  * into SENTENCES -- mechanical, at the terminators of the script.  A
    sentence is a subparagraph, `\\parnum{p.s}` and one `frank` environment,
    which is what a sentence is everywhere else in the toolbox.
  * into CHUNKS -- EDITORIAL, and left undone.  Where a sentence breaks into
    phrases is the whole of the Frank method: it is the judgement the person
    doing this work is here to make, and a machine guessing at it would hand
    them somebody else's reading to undo before they could start their own.

So a draft is ONE CHUNK PER SENTENCE.  The author splits it by cutting one
`\\ch` line into several, or one chunk of a caption into several -- an
addition to a blank page, never an argument with a guess.  The mechanical two
cuts are safe to get wrong in a way the third is not: the fidelity checks
join the chunks back together and compare against the source, so a sentence
boundary in the wrong place still reproduces the text exactly, and moving it
is a local edit.

A LANGUAGE DIVIDED INTO WORDS -- Japanese and Chinese, the registry's
"words" -- gets one cut more in a book, and that one is proposed rather than
left undone: each chunk's word line, `山(やま) へ 柴刈り(しばかり) に 、`, cut
and read by lib/words.py (see _chunk_line).  It is a mechanical cut in the
sense above: the words must rejoin the chunk's text, so a boundary in the
wrong place is a local edit and never a lost character.  Its readings are a
dictionary's, and they sit in the word line.  The chunk's own reading --
kana where the language has one, tr (the pinyin) where it has not -- starts
as those readings run together (wordline.reading_from), so the two agree:
a proposal like the line it comes from, which the author corrects with it,
and which counts as nobody's writing while it still says exactly that
(wordline.seed).  Where the analyzers are not in the running Python nothing
is proposed, and the chunk is written as it always was.  A video's chunks get
their line and reading the same way, the line as the "words" key after "fa"
(see _blank_chunk).

A BLANK GLOSS IS LEGAL
----------------------
Nothing in a draft's gloss was written by a person: no meaning, no
vocabulary, and no transliteration or reading beyond the one a language
divided into words is proposed from its word line (above), which counts as
unwritten until somebody writes something else in the chunk.  Nothing needs
to say so: a chunk nobody has glossed yet is legal everywhere.
`check_batch.py` and `check_annotations.py` count it in a note, the reader
and the player show it and open it for editing, and the PDF sets it -- so a
drafted book or video is read, built and filled in from the first minute, in
the reader's chunk sheet or the player's form, a chunk at a time by hand or a
region at a time with an LLM.  What the checkers do call an error is a
HALF-written gloss -- a meaning with no transliteration beside it, in a
language that requires one -- and emptying every box of a chunk at once is
how a gloss is taken off again.  Nothing here writes a marker into
`book.json` or `video.json`: a drafted edition and a finished one are the
same kind of file, some of whose glosses are still blank.

WHAT IS REFUSED
---------------
Characters that are not text at all -- the control characters and the
unpaired surrogates -- in either door, because a caption reaches a page and a
file just as a paragraph does.  The reason is written out once, at
`lib/texwrite.py`'s `NOT_TEXT`, which refuses the same class at the other way
in: a control character is invisible, passes every check downstream because
it sits identically on both sides of them, and then breaks the reader, the
build and the wire at once.  The tab, the newline and the carriage return are
text; `paragraphs()` has already collapsed them to a space by the time a
book's text is judged.

TeX's own characters (\\ { } $ % & # _ ^ ~) in the text of a book.  They
cannot be escaped here: the reading editions measure fidelity by comparing
the second argument of each `\\ch` with the source paragraph character for
character (verify_book.py, check_batch.py), so a `\\%` in the .tex beside a
`%` in the source is a mismatch in every one of them.  The text is the
author's to fix, and this says which character and which paragraph.  Every
refusal from this module is a ValueError, so one `except ValueError` in a
route answers all of them.

Standard library only: the server imports this.
"""
import datetime
import io
import json
import os
import re
import sys
import unicodedata

LIB = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(LIB)
YT_LIB = os.path.join(ROOT, "youtube", "lib")
for _p in (LIB, YT_LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import chunker
import languages                                        # noqa: E402  the registry
import wordline                                         # noqa: E402  the word line's grammar
import words                                            # noqa: E402  and a proposal of one
import books                                            # noqa: E402  where books live
import ytpages                                          # noqa: E402  the video door

# Where the two doors keep their content, so a caller -- an HTTP route, the
# command line below -- can say into=draft.BOOKS_DIR and not work the path
# out again.
BOOKS_DIR = books.BOOKS_DIR
VIDEOS = ytpages.VIDEOS

# The characters LaTeX reads as instructions.  A book's text may not carry
# them (see the header); a video's may, since a caption never becomes TeX.
# The same class assemble.py and check_batch.py refuse in a gloss, plus the
# braces and the backslash -- those would end the \ch argument early and the
# chapter would not even parse, let alone build.
TEX_SPECIAL = re.compile(r"[\\{}$%&#_^~]")

# What is not text at all: the C0 controls, DEL, the C1 controls, and the
# unpaired surrogates UTF-8 cannot encode.  Refused in BOTH doors -- a
# caption is served and written just as a paragraph is.  The tab, the newline
# and the carriage return are left out because they are text.  The class and
# the reason for it are lib/texwrite.py's NOT_TEXT, written out there once.
NOT_TEXT = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff]")

# Where a sentence ends, in every script the toolbox sets: the ASCII three,
# the ellipsis, the Arabic question mark and full stop, and the CJK full stop
# with its full-width companions.  This is a fact about SCRIPTS and not about
# languages -- Italian and French end a sentence with the same character, and
# the registry has no field for it because a language does not decide it --
# so the class is written once and applied to every language, the way
# lib/tex2html.py's trimPunct is (docs/languages.md section 1: what a
# language decides comes from the registry; this is not one of those things).
SENT_END = ".!?…؟۔"
# The full-width ones are kept apart because they need no space after them.
# A space or the end of the text is what tells a full stop from a decimal
# point in every script that has spaces -- but a language written without
# them has no space to give (Japanese runs 。 straight into the next
# sentence), and these characters are never anything but a full stop, so
# they end a sentence wherever they stand.
SENT_END_WIDE = "。！？"
# a run of terminators, then any closing quote or bracket that belongs to the
# sentence they end ("«...!»", "…。」")
_CLOSERS = r"[)\]}»”’\"'」』）]*"
_SENT = re.compile(r"(?:[%s]+%s(?=\s|$)|[%s]+%s)"
                   % (re.escape(SENT_END), _CLOSERS,
                      re.escape(SENT_END_WIDE), _CLOSERS))
_LAST_TOKEN = re.compile(r"\S+$")


# --------------------------------------------------------------- the basics
def _lang(lang):
    """A registry code or a Lang.  An unknown code is refused, never taken as
    Persian: these functions WRITE files, and a book filed under the wrong
    folder, in the wrong font, with the wrong digits is worse than an error
    on the way in (books.find_book refuses the same thing for the same
    reason)."""
    if isinstance(lang, languages.Lang):
        return lang
    try:
        return languages.get(lang)
    except KeyError as e:
        raise ValueError(str(e.args[0] if e.args else e))


def _gloss(gloss):
    """A code a gloss may be written in, or a Gloss.  Nothing -> English.

    Refused rather than fallen back on, for _lang's reason and one more: the
    fallback would be silent.  A book whose language is wrong is filed in the
    wrong folder, in the wrong font, and somebody sees it that day; a book
    whose gloss language is wrong looks exactly right and merely breaks its
    meanings at the wrong points for the rest of its life.
    """
    if isinstance(gloss, languages.Gloss):
        return gloss
    try:
        return languages.gloss(gloss)
    except KeyError as e:
        raise ValueError(str(e.args[0] if e.args else e))


def slugify(title):
    """The directory name for a title: the toolbox's fold, then the ASCII
    NFKD leaves.

    Written a third time on purpose.  The studio's `store._slug` and the
    add-a-book page's `slugify` are the same three lines, and neither can be
    reached from here -- one sits inside the studio, and importing it pulls
    the whole studio in behind it; the other is JavaScript.  Folded
    first so that Turkish's dotless i becomes i instead of being dropped as
    un-ASCII: a directory name is where a locale-blind lower-case shows worst
    (lib/languages.py, `fold`).
    """
    s = unicodedata.normalize("NFKD", languages.fold(title or ""))
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40]


def paragraphs(text):
    """The text as a list of paragraphs, whitespace collapsed.

    A blank line ends a paragraph.  A text with no blank line in it is taken
    a line to a paragraph: a chapter pasted out of an epub or a PDF arrives
    that way, and treating the whole of it as one paragraph would give the
    book a single contents entry.

    Collapsing every run of whitespace to one space cannot cost fidelity:
    both fidelity checks normalise whitespace the same way before they
    compare (check_batch.norm, verify_book), and for a language without a
    word separator they drop it altogether.

    Takes no language, and neither does `sentences`: both of these cuts are
    the same in every script the toolbox sets, and a parameter nothing reads
    would be a promise this module does not keep.
    """
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not t:
        return []
    blocks = re.split(r"\n[ \t]*\n+", t)
    if len(blocks) == 1:
        blocks = t.split("\n")
    return [p for p in (re.sub(r"\s+", " ", b).strip() for b in blocks) if p]


def sentences(text):
    """One paragraph (or one caption) as a list of sentences.

    Split after a run of terminators -- with a space or the end of the text
    after it, except for the full-width stops, which a language written
    without spaces runs straight into the next sentence -- and two guards,
    both of them about the script and not about any one language:

      * a terminator with a lower-case letter after it did not end a
        sentence.  Every Latin-script language in the registry opens one with
        a capital, and the three written in their own scripts have no case at
        all, so for those the guard can never fire.  It is what keeps
        "e.g. the fox" in one piece.
      * a full stop after a lone letter or digit is an initial or a list
        number ("J. Smith", "1. "), not an end.

    An abbreviation this does not know ("Mr. Brown") still ends a sentence
    here, and that is a cheap mistake to live with: the chunks are joined
    back together for the fidelity check, so the text is intact either way,
    and merging two subparagraphs is a two-line edit.
    """
    s = (text or "").strip()
    if not s:
        return []
    out, start = [], 0
    for m in _SENT.finditer(s):
        rest = s[m.end():].lstrip()
        if rest[:1].islower():
            continue
        if m.group()[0] == "." and len(m.group()) == 1:
            tok = _LAST_TOKEN.search(s[start:m.start()])
            if tok and len(tok.group()) == 1 and tok.group().isalnum():
                continue
        piece = s[start:m.end()].strip()
        if piece:
            out.append(piece)
        start = m.end()
    tail = s[start:].strip()
    if tail:
        out.append(tail)
    return out or [s]


def _refuse_not_text(text, where):
    """No character that is not text may be written, in either door.

    `where` names the piece the author has to go and find.  Applied to what
    is about to be WRITTEN and not to what arrived: a book's paragraphs have
    been through `paragraphs()`, which turns the form feed a chapter pasted
    out of a PDF carries at a page break into the space it always meant, so
    that is never something to refuse; a video's transcript is written back
    verbatim, so it is judged whole.

    The character is invisible, so the message places it and names it by its
    code point instead of quoting it -- printing it would put it in the
    answer, which is a page that must not carry one either."""
    m = NOT_TEXT.search(text)
    if not m:
        return
    k, cp = m.start(), ord(m.group())
    why = ("an unpaired surrogate, and UTF-8 cannot encode one -- the files "
           "could not be written at all" if 0xd800 <= cp <= 0xdfff else
           "a control character: invisible, so nothing further on would show "
           "you where it is -- it would pass every fidelity check, reach the "
           "reader inside the HTML and stop the build in LaTeX")
    raise ValueError(
        "%s carries U+%04X at character %d, which is not text -- %s.  "
        "Here it is: %s\nTake it out and try again."
        % (where, cp, k, why, text[max(0, k - 30):k] + "<U+%04X>" % cp
           + text[k + 1:k + 31]))


def _refuse_tex_specials(paras, chapter):
    """A book's text may carry no character LaTeX reads as an instruction.
    Names the paragraph, the character and where it is, because the fix is
    in the author's text file and they have to find it."""
    for i, p in enumerate(paras):
        m = TEX_SPECIAL.search(p)
        if m:
            k = m.start()
            raise ValueError(
                "paragraph %d of chapter %d carries %r, which LaTeX reads as an "
                "instruction and the reading editions cannot hold in their text: "
                "...%s...\n"
                "Take it out of the text (or spell it in words) and try again -- "
                "escaping it here would make the .tex disagree with the source "
                "and every fidelity check would report a mismatch."
                % (i, chapter, m.group(), p[max(0, k - 30):k + 30]))


# ------------------------------------------------------------------- a book
def _incipit(text, L, words=6, chars=12):
    """What names a paragraph in the contents and the PDF outline: the
    opening of its first sentence.  Six words, or the first twelve characters
    for a language with no word separator -- assemble.py's rule and
    inject_parstart.py's, which is why it says so here too."""
    if L.spaced:
        return " ".join(text.split()[:words])
    return re.sub(r"\s+", "", text)[:chars]


def _chunk_line(fa, L):
    """One chunk as LaTeX, with every gloss empty.  \\chr for a language with
    a reading, exactly as assemble.py writes it: the arity is in the name, so
    filling a draft in must never mean renaming the macro and counting a new
    argument -- the blanks are the only thing that changes.

    A language divided into words gets its proposed word line as the LAST
    argument -- \\chrw{col}{fa}{kana}{tr}{voc}{en}{words}, or
    \\chw{col}{fa}{tr}{voc}{en}{words} without a reading -- so everything that
    counts its way to {en} counts as it always did (docs/languages.md section
    3).  No line, no w: where lib/words.py proposes nothing (the analyzers are
    not in this Python, or could not cut the text) the chunk is the one
    written before words existed, because a w-macro with an empty last
    argument is an error and not a chunk without words.  A line the book door
    would refuse is dropped the same way: lib/words.py only makes sure it
    rejoins the text, and a draft must not be born failing its own checker.
    Only the errors are asked for, and they do not depend on "reorders".
    lib/words.py makes one proposal at a time for the whole process, so
    drafts made at once on serve.py's threads each get their words.

    With the words comes the chunk's own reading: {kana} for a language with
    a reading, {tr} (the pinyin) for one without, starts as the words'
    readings run together (wordline.reading_from), so the chunk says what its
    words say.  It is a proposal like them, and the checker counts a chunk
    whose only written field is that reading as unwritten (wordline.seed)."""
    line = ""
    if L.words:
        line = words.line(fa, L.code)
    if line and wordline.check(fa, line, L, reading="", door=wordline.BOOK)[0]:
        line = ""
    said = wordline.reading_from(line, L) if line else ""
    if L.reading:
        return (r"\chrw{}{%s}{%s}{}{}{}{%s}" % (fa, said, line) if line
                else r"\chr{}{%s}{}{}{}{}" % fa)
    return (r"\chw{}{%s}{%s}{}{}{%s}" % (fa, said, line) if line
            else r"\ch{}{%s}{}{}{}" % fa)


# The third %s is the one clause that depends on the chapter: once a chunk
# carries words the meaning is no longer the last field, and CH_WORDS follows
# to say what is.
CH_HEADER = """\
%% chapter %s of a DRAFT.  Every chunk is one whole sentence, and every gloss
%% is empty: the {tr}{voc}{en} after the text (a language with a reading has
%% {kana} in front of those).  Fill them in.  %s
%% and the language it is written in is %s.
%% book.json's "gloss" says so and \\BookGloss repeats it to the preamble,
%% which sets that column in it and hyphenates it by that language's rules.
%% The key is called {en} for the reason the text is called fa: it is the
%% name of a slot (docs/languages.md section 3).  To split a sentence into
%% the phrases it should be read in, cut its line into several -- the
%% chunking is the editorial work, which is why nothing guessed at it here.
%% A blank gloss is legal: the reader shows the chunk as it is, the PDF sets
%% it and check_batch.py counts it in a note, so the book reads and builds
%% while the glosses are filled in -- here, or in the reader, a chunk at a
%% time by hand or a region at a time with an LLM.  A chunk with only part
%% of its gloss written is an error to the checker until the rest is in.
"""
CH_WORDS = """\
%% The last field is the chunk's WORDS (\\chrw and \\chw are \\chr and \\ch
%% with it), and it is not left blank: a machine divided the text into words
%% and read each one -- 山(やま) へ 柴刈り(しばかり) に 、 -- a reading in ( )
%% closing its word.  The chunk's own reading, {kana} (for Chinese the pinyin
%% in {tr}), starts as those readings run together, so the two agree.  Correct
%% the cut and the readings where they are wrong, and the chunk's reading with
%% them; the checker compares the two and warns where they part.  Cutting a
%% line in two cuts its words with it, and a chunk with no words goes back to
%% \\chr or \\ch -- the field is taken out, never left empty.
"""


def _cut_all(texts, code, how):
    """New text, cut: with an analyzer's help where somebody chose that (Settings -> Linguistic analysis), and
    with nothing else different."""
    assist = chunker.assisting(code) if how != "sentence" else None
    return chunker.chunk_all(texts, code, how, assist) if assist else chunker.chunk_all(texts, code, how)


def _cuts_for(paras, L, how):
    """Every sentence of the chapter, cut -> {(paragraph, sentence): [chunk]}.

    The whole chapter in one call, so the chapter and the count that goes
    into book.json are cut by the same pass and cannot disagree.
    """
    flat = [(i, k, sent)
            for i, para in enumerate(paras)
            for k, sent in enumerate(sentences(para))]
    got = _cut_all([f[2] for f in flat], L.code, how)
    return {(i, k): c for (i, k, _s), c in zip(flat, got)}


def _chapter_tex(paras, L, G, chapter, how=chunker.DEFAULT_WAY, cuts=None,
                 offset=0):
    """The chapter file: \\chapopen, then a \\parstart per paragraph and a
    \\parnum per sentence, each holding one blank chunk.

    assemble.py's render() writes this same shape from an annotator's JSON,
    and calling it was the first plan.  It takes its language from a module
    global that only its main() sets, and serve.py is a threading server: two
    drafts of different languages at once would each render in the other's
    digits.  So the shape is written out here instead, and the two rules that
    are repeated -- the label in the language's digits, the incipit -- are the
    ones inject_parstart.py already repeats, for the same kind of reason.
    """
    num = lambda n: L.to_native_digits(str(n))          # noqa: E731
    lab = num(chapter)
    cuts = _cuts_for(paras, L, how) if cuts is None else cuts
    out, worded = [None, r"\chapopen{%s}" % lab, ""], False
    for i, para in enumerate(paras):
        sents = sentences(para)
        pn = num(offset + i + 1)
        out.append(r"\parstart{%s.%s}{%s}" % (lab, pn, _incipit(sents[0], L)))
        for k, s in enumerate(sents):
            out.append(r"\parnum{%s.%s}" % (pn, num(k + 1)))
            out.append(r"\begin{frank}")
            for c in cuts.get((i, k)) or [s]:
                line = _chunk_line(c, L)
                worded = worded or line.startswith((r"\chrw{", r"\chw{"))
                out.append(line)
            out.append(r"\end{frank}")
            out.append("")
        out.append(r"\chapend" if i == len(paras) - 1 else r"\parend")
        out.append("")
    # the header last: what it says the fields are depends on whether any
    # chunk came out with words
    out[0] = (CH_HEADER + (CH_WORDS if worded else "")) % (
        chapter, "The meaning is next to last," if worded
        else "The last field is the meaning,", G.name)
    return "\n".join(out)


MAIN_TEX = r"""%% {byline}.  Build:  ./build.sh {slug}
% Drafted from its text (lib/draft.py): every gloss starts blank, and a blank
% gloss is legal -- fill them in in the reader, or in the chapter files.
% The language taught, the language the glosses are written in, and where the
% shared preamble lives come first: the preamble reads all three before it
% does anything (docs/languages.md section 6).
\newcommand{{\BookLang}}{{{lang}}}
\newcommand{{\BookGloss}}{{{gloss}}}
\newcommand{{\FrankLib}}{{../../../lib}}
\newcommand{{\BookTitle}}{{{title}}}
\newcommand{{\BookAuthor}}{{{author}}}
\newcommand{{\BookTitleLatin}}{{{title_latin}}}
\newcommand{{\BookAuthorLatin}}{{{author_latin}}}
\input{{\FrankLib/frank-preamble.tex}}
\input{{\FrankLib/frank-frontmatter.tex}}

% one \input per chapter, in reading order -- this list is the only place the
% order is written down (texparse.parse_book reads it)
\input{{{chapter_file}}}

\end{{document}}
"""


def book_from_text(text, lang, title, gloss="", slug=None, author="",
                   title_latin="", title_en="", author_latin="", year="",
                   blurb="", chapter=1, into=None,
                   how=chunker.DEFAULT_WAY):
    """A whole reading edition, drafted from the text of one chapter.

    `text` is the chapter as the author has it -- paragraphs separated by
    blank lines, or one to a line.  `lang` is a registry code (or a Lang) and
    `title` the title in that language.  `gloss` is the language the meanings
    will be written in -- a registry code or a prose one (languages.gloss),
    and English when nothing is said, which is what every edition here was
    glossed in before a book could say otherwise.  `slug` is the directory name;
    without one it is made from `title_latin` or `title`, and a title that
    leaves no ASCII behind is refused rather than filed under a made-up name.
    `chapter` numbers the chapter.  `into` makes a NEW book and refuses to
    touch one that is already there, so a second chapter is drafted by
    calling this without `into` and putting the three files it names for that
    chapter (chN.tex and its two source files) into the book by hand, with
    one more \\input line in main.tex -- which is where chapter order is
    written down and the only place it is.

    Returns a dict: the counts, and `files`, every file the book needs keyed
    by its path inside the book's directory --

        book.json  main.tex  chN.tex
        source/paras/chN_pNN.txt        what the fidelity checks compare against
        source/src_chN.json             the list assemble.py indexes into

    With `into` (the books/ directory) the files are also written, to
    into/<language folder>/<slug>/, and `dir` is where they went.  An
    existing book there is never overwritten.
    """
    L = _lang(lang)
    G = _gloss(gloss)
    title = (title or "").strip()
    if not title:
        raise ValueError("a book needs a title in %s" % L.name)
    chapter = int(chapter)
    if chapter < 1:
        raise ValueError("chapter numbers start at 1, not %d" % chapter)
    wanted = slug or title_latin or title
    slug = slugify(wanted)
    if not slug:
        raise ValueError(
            "no directory name could be made from %r: pass a slug of ascii "
            "letters, digits and hyphens (a title written in its own script "
            "leaves none behind)" % wanted)
    paras = paragraphs(text)
    if not paras:
        raise ValueError("the text is empty: there is nothing to draft")
    for i, p in enumerate(paras):
        _refuse_not_text(p, "paragraph %d of chapter %d" % (i, chapter))
    _refuse_tex_specials(paras, chapter)

    meta = {
        "slug": slug,
        "language": L.code,
        # beside the language and never merged with it: one says what the
        # book teaches, the other what its meanings are written in, and a
        # reader of either that took it for the other would be wrong about
        # half the page (docs/languages.md section 3)
        "gloss": G.code,
        "title": title,
        "title_latin": (title_latin or "").strip() or slug,
        "title_en": (title_en or "").strip(),
        "author": (author or "").strip(),
        "author_latin": (author_latin or "").strip(),
        "year": (year or "").strip(),
        "blurb": (blurb or "").strip(),
        "main": "main.tex",
        "audio": None,
        "transcript": None,
    }
    chapter_file = "ch%d.tex" % chapter
    # cut once, and hand the same cutting to the chapter and to the count
    cuts = _cuts_for(paras, L, how)
    files = {
        "book.json": json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        "main.tex": MAIN_TEX.format(
            lang=L.code, gloss=G.code, slug=slug, title=title,
            author=meta["author"],
            # the first line of a main.tex names the book the way the Persian
            # one does, and a draft usually has no author yet: no dash, then
            byline="%s%s (%s)" % (meta["title_latin"],
                                  " - " + meta["author_latin"]
                                  if meta["author_latin"] else "", L.name),
            title_latin=meta["title_latin"],
            # NOT upper-cased: the add-a-book page does that in the browser,
            # where toLocaleUpperCase knows that Turkish's i goes to I with a
            # dot on it.  Python's str.upper() does not, and the registry
            # holds no case table (languages.py has `lower` and `fold` and
            # deliberately no `upper`), so a draft prints the half title as
            # it was typed and the author capitalises it if they want it so.
            author_latin=meta["author_latin"], chapter_file=chapter_file),
        chapter_file: _chapter_tex(paras, L, G, chapter, how, cuts),
        # chapter_src.py's format, so the file it would write next time is
        # the file that is here now
        "source/src_ch%d.json" % chapter:
            json.dumps(paras, ensure_ascii=False, indent=0) + "\n",
    }
    for i, p in enumerate(paras):
        files["source/paras/ch%d_p%02d.txt" % (chapter, i)] = p + "\n"

    n_sent = sum(len(sentences(p)) for p in paras)
    n_chunk = sum(len(v) for v in cuts.values())
    out = {"slug": slug, "language": L.code, "gloss": G.code, "folder": L.folder,
           "title": title, "chapter": chapter, "paragraphs": len(paras),
           "sentences": n_sent, "chunks": n_chunk,
           "how": how,
           "dir": None, "files": files}
    if into:
        out["dir"] = _write(os.path.join(into, L.folder, slug), files, "book.json")
    return out


CH_RE = re.compile(r"^ch(\d+)\.tex$")


def chapters_of(book_dir):
    """The chapter numbers a book already has, in order."""
    out = []
    try:
        for name in os.listdir(book_dir):
            m = CH_RE.match(name)
            if m:
                out.append(int(m.group(1)))
    except OSError:
        pass
    return sorted(out)


def _para_count(tex):
    r"""How many paragraphs a chapter file already holds -- its \parstart
    lines, which is the one thing that numbers them."""
    return len(re.findall(r"^\\parstart\{", tex, re.M))


def add_to_book(book_dir, text, how=chunker.DEFAULT_WAY, chapter=None):
    r"""More text onto the end of a book that is already here.

    Everything the from-scratch draft does, except deciding what the book IS:
    the language, the gloss language, the title and the author are the book's
    already and are read from its book.json rather than asked again.  The
    text goes through the same paragraph split, the same sentence split, the
    same refusal of control characters and LaTeX specials, and the same
    choice of how to cut it -- one chunk per sentence, sense groups, or sense
    groups a model has corrected.

    `chapter` says where it lands:
      None / "new"   the NEXT chapter, its own \chapopen and its own
                     \input line in main.tex.  A new text in the same
                     edition -- another story, another lesson.
      "last"         the end of the LAST chapter, as more paragraphs of it,
                     numbered on from what is there.  The same text, continued.

    Nothing already written is re-cut or re-glossed: the old chapters are not
    read except to be numbered from, and continuing one appends after its last
    paragraph without touching a line of it.  -> a dict of counts, and `files`
    written, the shape book_from_text returns.
    """
    book_dir = os.path.abspath(book_dir)
    meta_path = os.path.join(book_dir, "book.json")
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError) as e:
        raise ValueError("no book here: %s (%s)" % (book_dir, e))
    L = _lang(meta.get("language"))
    G = _gloss(meta.get("gloss"))
    paras = paragraphs(text)
    if not paras:
        raise ValueError("the text is empty: there is nothing to add")
    have = chapters_of(book_dir)
    if not have:
        raise ValueError("this book has no chapters to add to (no chN.tex)")
    where = (chapter or "new").strip().lower()
    if where not in ("new", "last"):
        raise ValueError("no such place to add text: %r (new, last)" % chapter)
    n = (have[-1] + 1) if where == "new" else have[-1]
    for i, para in enumerate(paras):
        _refuse_not_text(para, "paragraph %d of chapter %d" % (i, n))
    _refuse_tex_specials(paras, n)

    cuts = _cuts_for(paras, L, how)
    written, num = {}, lambda k: L.to_native_digits(str(k))     # noqa: E731
    if where == "new":
        written["ch%d.tex" % n] = _chapter_tex(paras, L, G, n, how, cuts)
        first = 0
    else:
        path = os.path.join(book_dir, "ch%d.tex" % n)
        with open(path, encoding="utf-8") as f:
            was = f.read()
        first = _para_count(was)
        if not first:
            raise ValueError("chapter %d holds no paragraphs to add to" % n)
        # THE CHAPTER'S END MOVES.  \chapend closes the last paragraph of a
        # chapter and \parend every other one, so the paragraph that was
        # last becomes an ordinary one and the new last carries \chapend.
        if "\\chapend" not in was:
            raise ValueError(r"chapter %d has no \chapend to move" % n)
        head = was.rstrip("\n")
        at = head.rfind("\\chapend")
        head = head[:at] + "\\parend" + head[at + len("\\chapend"):]
        body = _chapter_tex(paras, L, G, n, how, cuts, offset=first)
        # its own header and \chapopen belong to the chapter that exists
        body = body.split("\\chapopen{", 1)[-1].split("\n", 1)[-1].lstrip("\n")
        written["ch%d.tex" % n] = head.rstrip("\n") + "\n\n" + body
    for i, para in enumerate(paras):
        written["source/paras/ch%d_p%02d.txt" % (n, first + i)] = para + "\n"
    src = os.path.join(book_dir, "source", "src_ch%d.json" % n)
    older = []
    if where == "last":
        try:
            with open(src, encoding="utf-8") as f:
                older = json.load(f) or []
        except (OSError, ValueError):
            older = []
    written["source/src_ch%d.json" % n] = json.dumps(
        list(older) + paras, ensure_ascii=False, indent=0) + "\n"

    for rel, body in written.items():
        full = os.path.join(book_dir, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(body if body.endswith("\n") else body + "\n")
    if where == "new":
        _add_input(os.path.join(book_dir, "main.tex"), "ch%d.tex" % n)
    return {"slug": meta.get("slug") or os.path.basename(book_dir),
            "language": L.code, "gloss": G.code, "folder": L.folder,
            "chapter": n, "where": where, "how": how,
            "paragraphs": len(paras),
            "sentences": sum(len(sentences(p)) for p in paras),
            "chunks": sum(len(v) for v in cuts.values()),
            "dir": book_dir, "files": sorted(written)}


def _add_input(main_tex, chapter_file):
    r"""One more \input, after the last one there.

    main.tex's own comment says that list is the only place the reading order
    is written down, so a chapter that is not in it is a chapter the book
    does not have -- and a new one belongs at the end, which is where the
    text was added.
    """
    with open(main_tex, encoding="utf-8") as f:
        was = f.read()
    line = r"\input{%s}" % chapter_file
    if line in was:
        return
    hits = list(re.finditer(r"^\\input\{ch\d+\.tex\}\s*$", was, re.M))
    if hits:
        at = hits[-1].end()
        now = was[:at] + "\n" + line + was[at:]
    else:                                    # no chapter listed yet: before \end
        at = was.rfind(r"\end{document}")
        now = (was[:at] + line + "\n" + was[at:]) if at >= 0 else was + line + "\n"
    with open(main_tex, "w", encoding="utf-8") as f:
        f.write(now)


# ------------------------------------------------------------------ a video
def _blank_chunk(fa, L):
    """One chunk of a caption, every gloss blank.  The empty keys are written
    out rather than left off: this file is edited by hand, and an empty slot
    is something to fill where a missing key is something to remember.  The
    order is check_annotations.CHUNK_FIELDS', so a draft and a finished file
    diff cleanly.

    A language divided into words gets its proposed word line as "words",
    directly after "fa" where CHUNK_FIELDS puts it, on _chunk_line's terms at
    the video door: nothing proposed, or a line the checker would refuse, and
    there is no key at all -- a blank "words" is an error, not a chunk
    without words.  With the words the chunk's reading -- "kana", or "tr"
    for a language without one -- starts as their readings run together, as
    a book's chunk does (_chunk_line).  A plain caption has no chunks and
    never comes here."""
    c = {"fa": fa}
    line = words.line(fa, L.code) if L.words else ""
    if line and not wordline.check(fa, line, L, reading="", door=wordline.VIDEO)[0]:
        c["words"] = line
    said = wordline.reading_from(c["words"], L) if "words" in c else ""
    if L.reading:
        c["kana"] = said
    c["tr"] = "" if L.reading else said
    c["voc"] = ""
    c["en"] = ""
    return c


def _level(level):
    """One of ytpages.LEVELS, defaulting as its add page does."""
    v = languages.lower(level or "").strip()
    return v if v in ytpages.LEVELS else "beginner"


def video_from_transcript(transcript, lang, gloss="", video_id=None, url="",
                          title="", title_native="", channel="",
                          level="beginner", blurb="", into=None,
                          how=chunker.DEFAULT_WAY):
    """A video's three files, drafted from the transcript YouTube shows.

    `transcript` is that panel pasted whole, timestamps and all -- it is the
    single source of truth for the captions everywhere else in this door, and
    it is parsed here by the one thing that parses it
    (check_annotations.parse_transcript, through ytpages), so a draft cannot
    disagree with what the checker will read back.

    `gloss` is the language those meanings will be written in (English when
    nothing is said, as everywhere else).  It goes in video.json and not in
    annotations.json because it is true of the whole video, not of one
    caption (and, when this was written, because `merge_parts.py` would have
    dropped it -- it no longer rewrites anything once a video is on the
    shelf).

    Every caption becomes a segment; a segment's text becomes one chunk per
    sentence with `tr`, `voc`, `en` (and `kana`, for a language with a
    reading) empty -- and, for a language divided into words, with its
    proposed `words` where one can be proposed.  A PLAIN caption -- for a
    script language, one with not a character of the script in it: the
    English these videos open with --
    carries no chunks at all, as it does in a finished file.

    Returns a dict of counts and `files` (video.json, transcript.txt,
    annotations.json).  With `into` (the youtube/videos/ directory) they are
    written to into/<language folder>/<id>/, and `dir` says where; a video
    already there is never overwritten -- nor one with the same id filed
    under ANOTHER language's folder (_video_on_shelf says why).
    """
    L = _lang(lang)
    G = _gloss(gloss)
    # Both the id and the URL go through the same reader, which accepts a
    # YouTube URL in any of its spellings and a bare id of the eleven
    # characters YouTube uses, and nothing else.  That is a validation as
    # much as a convenience: the id becomes a DIRECTORY NAME below, and a
    # route that passed a typed "../../lib" through would write a book's
    # worth of files wherever it pointed.
    given = (video_id or "").strip()
    vid = ytpages.video_id(given or url)
    if not vid and ytpages.is_local_id(given):
        # A VIDEO THAT IS A FILE ON THIS MACHINE has no YouTube id and needs
        # none; what it needs is the same guarantee, and `is_local_id` gives
        # it: ASCII, no slashes, no leading dot, so this cannot become a
        # write outside videos/ either.
        vid = given
    if not vid:
        raise ValueError(
            "no video to draft: pass the YouTube URL, or the 11-character id"
            + ("" if not given else " -- %r is neither" % given))
    if into:
        # before anything is cut: the answer does not depend on the text
        there = _video_on_shelf(into, vid)
        if there:
            where, marker = there
            raise ValueError(
                "%s already exists in %s -- draft into a new name, or move "
                "that one out of the way%s"
                % (marker, where,
                   "" if os.path.abspath(where) == os.path.abspath(
                       os.path.join(into, L.folder, vid))
                   else " (a video's id is its address in every language, "
                        "so one id cannot be two videos)"))
    text = (transcript or "").replace("\r\n", "\n").replace("\r", "\n")
    # before the parse, because transcript.txt is written back whole: a
    # control character between two captions would reach the file even though
    # no caption carried it
    _refuse_not_text(text, "the transcript")
    captions = ytpages.parse_transcript_text(text, L)
    if not captions:
        raise ValueError("no captions found -- paste the transcript as YouTube "
                         "shows it, timestamps included")
    want = [c for c in captions if not c["plain"]]
    if not want:
        raise ValueError("every caption is plain (not one character of %s "
                         "script) -- there would be nothing to gloss; is the "
                         "language right?" % L.name)

    segs = []
    # The whole transcript in one pass, kept by POSITION -- a caption
    # repeated in a song or a drill would otherwise be given the first
    # one's cut.
    flat = [(ci, si, sent)
            for ci, cap in enumerate(captions) if not cap["plain"]
            for si, sent in enumerate(sentences(cap["text"]))]
    vcuts = {(ci, si): c for (ci, si, _t), c
             in zip(flat, _cut_all([f[2] for f in flat], L.code, how))}
    nchunks = 0
    for ci, cap in enumerate(captions):
        sg = {"start": cap["start"]}
        if cap["chapter"]:
            sg["chapter"] = cap["chapter"]
        if cap["plain"]:
            sg["plain"] = True
            sg["text"] = cap["text"]
        else:
            sg["text"] = cap["text"]
            chunks = [_blank_chunk(c, L)
                      for si, s in enumerate(sentences(cap["text"]))
                      for c in vcuts.get((ci, si)) or [s]]
            nchunks += len(chunks)
            sg["chunks"] = chunks
        # merge_parts.py's key order, so a file this writes and a file that
        # writes are the same file
        segs.append({k: sg[k] for k in ("start", "chapter", "plain", "text",
                                        "chunks") if k in sg})

    # A BARE ID IS NO ADDRESS.  The add page's URL box takes the eleven
    # characters alone as readily as a whole URL, and "Start it empty" hands
    # the box to this function as `url` -- so the id alone went into
    # video.json's "url", the one field a person opens to find the source,
    # while the LLM road (ytpages.api_add) writes the watch URL for the same
    # typing.  An 11-character YouTube id is written as that URL here too.
    # Only a YouTube id: ytpages.video_id returns the text itself only when
    # it IS one, and never for a local id (is_local_id refuses that shape),
    # so a film on this machine keeps the url it was given -- none -- and a
    # URL in any spelling is kept as it was typed.
    said = (url or "").strip()
    if said and ytpages.video_id(said) == said:
        said = "https://www.youtube.com/watch?v=" + said
    meta = {
        "id": vid,
        # A LOCAL VIDEO HAS NO ADDRESS and is given none: writing
        # youtube.com/watch?v=<a local id> would be a link to a video that
        # does not exist, in the one field a person opens to find the source.
        "url": (said or
                ("" if ytpages.is_local_id(vid)
                 else "https://www.youtube.com/watch?v=" + vid)),
        "title": (title or "").strip() or vid,
        "title_native": (title_native or "").strip(),
        "channel": (channel or "").strip() or "Unknown channel",
        "language": L.code,
        "gloss": G.code,                # what the glosses are written IN
        # the same three the add page offers and ytpages writes; anything
        # else is a typo, and the index would file the video under a level
        # no chip can pick
        "level": _level(level),
        "duration": ytpages.fmt_time(captions[-1]["start"]),
        "added": datetime.date.today().isoformat(),
        "blurb": (blurb or "").strip(),
    }
    ann = {"video": vid, "language": L.code, "segments": segs}
    files = {
        "video.json": json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        "transcript.txt": text if text.endswith("\n") else text + "\n",
        "annotations.json": json.dumps(ann, ensure_ascii=False, indent=1) + "\n",
    }
    out = {"id": vid, "language": L.code, "gloss": G.code, "folder": L.folder,
           "captions": len(captions), "glossed": len(want),
           "plain": len(captions) - len(want), "chunks": nchunks,
           "dir": None, "files": files}
    if into:
        out["dir"] = _write(os.path.join(into, L.folder, vid), files,
                            "annotations.json")
    return out


def _video_on_shelf(videos, vid):
    """(directory, the file that shows a video is there) for a video with
    this id anywhere under `videos` -- the youtube/videos/ directory, or the
    one a caller named -- or None.

    _write refuses a directory that already holds the video, but it is handed
    ONE directory, into/<language folder>/<id>/, and a video's id is unique
    across languages: the player's address is /v/<id>/ with no folder in it,
    and ytpages.find_video opens the first folder that has it.  So the same
    id drafted into a second language's folder would be a second video under
    one address, and whichever came first in folder order would hide the
    other.  This looks where find_video looks, over this directory rather
    than the server's own: videos/<folder>/<id>/ in every folder (holding
    annotations.json, _write's marker, or video.json), videos/<id>/ in the
    layout before languages, and then a video.json under any other name that
    declares the id.  Dot-directories (videos/.trash/) are never content."""
    try:
        names = sorted(os.listdir(videos))
    except OSError:
        return None
    homes = []                  # every directory that might hold a video
    for name in names:
        top = os.path.join(videos, name)
        if name.startswith(".") or not os.path.isdir(top):
            continue
        if os.path.isfile(os.path.join(top, "video.json")):
            homes.append(top)                       # legacy: videos/<id>/
            continue
        try:
            subs = sorted(os.listdir(top))
        except OSError:
            continue
        homes.extend(os.path.join(top, sub) for sub in subs
                     if not sub.startswith("."))
    for d in homes:
        if os.path.basename(d) == vid:
            for marker in ("annotations.json", "video.json"):
                if os.path.isfile(os.path.join(d, marker)):
                    return d, marker
    for d in homes:
        try:
            with io.open(os.path.join(d, "video.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(meta, dict) and meta.get("id") == vid:
            return d, "video.json"
    return None


# ------------------------------------------------------------------ writing
def _write(directory, files, marker):
    """Write the files under `directory`, refusing to touch one that is
    already there (`marker` is the file whose presence means "already a
    book"/"already a video").  A draft is a beginning: overwriting somebody's
    half-finished work with a fresh set of blanks is the one mistake this
    module could make that could not be undone."""
    if os.path.exists(os.path.join(directory, marker)):
        raise ValueError("%s already exists in %s -- draft into a new name, or "
                         "move that one out of the way"
                         % (marker, directory))
    for rel, body in sorted(files.items()):
        path = os.path.join(directory, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(body)
    return directory


# ---------------------------------------------------------------------- CLI
def _read(path):
    if path == "-":
        return sys.stdin.read()
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(
        description="draft an empty book or video: the text, chunked, every "
                    "gloss blank")
    # --show belongs to both subcommands, not to the program: argparse hands
    # everything after the subcommand's name to the subparser, so a top-level
    # flag can only be typed before it, which nobody does
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--show", action="store_true", help="print every file's text")
    sub = ap.add_subparsers(dest="what")
    b = sub.add_parser("book", parents=[common],
                       help="a reading edition from a chapter's text")
    b.add_argument("--text", required=True, help="the chapter's text ('-' for stdin)")
    b.add_argument("--lang", required=True, help="registry code (%s)" % ", ".join(languages.CODES))
    b.add_argument("--title", required=True, help="the title, in the language")
    b.add_argument("--gloss", default="",
                   help="what the meanings will be written in (default en; %s)"
                        % ", ".join(languages.GLOSS_CODES))
    b.add_argument("--slug", default=None)
    b.add_argument("--author", default="")
    b.add_argument("--title-latin", default="")
    b.add_argument("--title-en", default="")
    b.add_argument("--author-latin", default="")
    b.add_argument("--year", default="")
    b.add_argument("--blurb", default="")
    b.add_argument("--chapter", type=int, default=1)
    b.add_argument("--into", default=None,
                   help="the books/ directory to write into (default: print only)")
    v = sub.add_parser("video", parents=[common],
                       help="an annotations.json from a pasted transcript")
    v.add_argument("--transcript", required=True, help="the pasted transcript ('-' for stdin)")
    v.add_argument("--lang", required=True)
    v.add_argument("--gloss", default="",
                   help="what the meanings will be written in (default en)")
    v.add_argument("--url", default="", help="the YouTube URL, or the bare id")
    v.add_argument("--id", dest="video_id", default=None)
    v.add_argument("--title", default="")
    v.add_argument("--title-native", default="")
    v.add_argument("--channel", default="")
    v.add_argument("--level", default="beginner")
    v.add_argument("--blurb", default="")
    v.add_argument("--into", default=None,
                   help="the youtube/videos/ directory to write into")
    a = ap.parse_args(argv)
    if not a.what:
        ap.error("say what to draft: book, or video")
    try:
        if a.what == "book":
            r = book_from_text(_read(a.text), a.lang, a.title, gloss=a.gloss,
                               slug=a.slug, author=a.author,
                               title_latin=a.title_latin, title_en=a.title_en,
                               author_latin=a.author_latin, year=a.year,
                               blurb=a.blurb, chapter=a.chapter, into=a.into)
            print("%s [%s, glossed in %s]: %d paragraphs, %d sentences, "
                  "%d blank chunks"
                  % (r["slug"], r["language"], r["gloss"], r["paragraphs"],
                     r["sentences"], r["chunks"]))
        else:
            r = video_from_transcript(_read(a.transcript), a.lang, gloss=a.gloss,
                                      video_id=a.video_id, url=a.url,
                                      title=a.title, title_native=a.title_native,
                                      channel=a.channel, level=a.level,
                                      blurb=a.blurb, into=a.into)
            print("%s [%s, glossed in %s]: %d captions (%d to gloss, %d plain), "
                  "%d blank chunks"
                  % (r["id"], r["language"], r["gloss"], r["captions"],
                     r["glossed"], r["plain"], r["chunks"]))
    except ValueError as e:
        sys.exit("refused: %s" % e)
    for rel in sorted(r["files"]):
        print("  %-34s %6d bytes" % (rel, len(r["files"][rel].encode("utf-8"))))
    if a.show:
        for rel in sorted(r["files"]):
            print("\n==> %s <==\n%s" % (rel, r["files"][rel]), end="")
    if r["dir"]:
        print("written to %s" % r["dir"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
