# SPDX-License-Identifier: GPL-3.0-or-later
"""texgen — turn the mdparser block model into a complete .tex file.

The heart is inline(): it finds maximal runs of the target language,
freezes them as placeholders, LaTeX-escapes the Latin remainder, applies
the few inline markdown rules to the Latin only, then thaws the
placeholders as \\pe{...} (short, unbreakable) or \\pel{...} (long,
breakable).

Runs are treated as opaque: no markdown syntax is interpreted inside
them, which is what makes `*` (emphasis) and `*` (linguistics) coexist —
see README, "The markdown dialect (authoritative)".

Which language a document is about comes from its front matter
(`target:`, default Persian) and is held, like the footnote state, in a
thread-local set at the top of generate() -- set_target(); everything
that needs a regex for the script asks cur_lang() / run_re() /
has_script().  No regex for a script is written in this file: the
registry (lib/languages.json) owns them (docs/languages.md, 1 and 5).
"""
import re
import sys
import threading
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE.parent.parent / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
import languages  # noqa: E402
from segcolour import (PALETTE, HEX_RE, normalise_colour, parse_marks,
                       find_runs as segmented_runs)  # noqa: E402


class ThreadDict:
    """A dict whose contents are private to each thread.

    Footnote numbering is document-global state, but the studio server
    renders several documents concurrently; without this, two parallel
    renders would interleave their counters.  Behaves like a plain dict
    at every call site.
    """

    def __init__(self, **default):
        self._default = default
        self._local = threading.local()

    @property
    def _d(self):
        d = getattr(self._local, "d", None)
        if d is None:
            d = self._local.d = dict(self._default)
        return d

    def __getitem__(self, k):
        return self._d[k]

    def __setitem__(self, k, v):
        self._d[k] = v

    def __contains__(self, k):
        return k in self._d

    def get(self, k, default=None):
        return self._d.get(k, default)

    def update(self, *a, **kw):
        self._d.update(*a, **kw)

    def clear(self):
        self._d.clear()


# ----------------------------------------------------------------------
# the current target language
# ----------------------------------------------------------------------
# One code per thread; the studio's threaded server renders documents of
# different languages at the same time, and a module-level constant would
# hand one document the other's script.  Unset, it is Persian, which is
# what every document written before `target:` existed is.
_LANG = ThreadDict(code=languages.DEFAULT)

# a regex that never matches: the run detector of a Latin-script target,
# whose runs are marked, never detected
_NO_RUN = re.compile(r"(?!x)x")


def set_target(code):
    """Make `code` (a registry code, or anything false for the default)
    the language of every subsequent render in this thread."""
    L = languages.get_or_default(code)
    _LANG["code"] = L.code
    return L


def cur_lang():
    return languages.get_or_default(_LANG.get("code"))


def run_re():
    """Maximal runs of the target script (space-joined words for fa/ar,
    contiguous characters for ja).  Never matches for a Latin target."""
    return cur_lang().run_re or _NO_RUN


def has_script(s):
    return cur_lang().has_script(s)


def is_latin_target():
    return cur_lang().chars is None


# ----------------------------------------------------------------------
# print options: the size of the print, and black and white
# ----------------------------------------------------------------------
# Both are the build's, not the document's: the same worksheet is printed
# at 11 pt in colour for one class and at 20 pt in black and white for a
# child who reads with a magnifier, from one source.  Held per thread like
# the target language, and for the same reason: the studio builds several
# documents at once.
#
# LARGE PRINT is a larger class size (extarticle's 14, 17 and 20 pt; the
# standard article stops at 12), so everything set relative to it --
# headings, the em rules, the target script's Scale -- grows with it; the
# one absolute size, the lemma head, is scaled here by hand.  Exercises
# are set a step larger still (\large on the new base): they are what a
# child reads closest and writes on.
#
# BLACK AND WHITE is for the photocopier: every colour of the template is
# redefined as black and every tint as white (print_options_tex), and the
# colours this file writes inline -- a `{#8E2B34}` mark, a coloured lemma,
# the red of an exercise that needs attention -- are not written at all.
# xcolor's gray model would have been one line, and wrong: it turns the
# pale tints and the dim text into greys, which is exactly what a
# photocopy smudges.  Pictures are left alone, colours and all.
_PRINT = ThreadDict(size=11, mono=False)

PRINT_SIZES = (11, 14, 17, 20)
DEFAULT_PRINT_SIZE = 11

# Larger print wants the line it can get: a little of the margin goes.
_MARGINS = {
    11: "top=2.4cm,bottom=2.4cm,left=2.5cm,right=2.5cm",
    14: "top=2.2cm,bottom=2.2cm,left=2.2cm,right=2.2cm",
    17: "top=2.0cm,bottom=2.0cm,left=2.0cm,right=2.0cm",
    20: "top=1.8cm,bottom=1.8cm,left=1.8cm,right=1.8cm",
}


def set_print(size=DEFAULT_PRINT_SIZE, mono=False):
    """Make `size` (one of PRINT_SIZES) and `mono` the print options of
    every subsequent render in this thread."""
    size = int(size)
    if size not in PRINT_SIZES:
        raise ValueError("print size must be one of %s, not %r"
                         % (", ".join(map(str, PRINT_SIZES)), size))
    _PRINT["size"], _PRINT["mono"] = size, bool(mono)


def print_size():
    return _PRINT["size"]


def is_mono():
    return _PRINT["mono"]


def rule_width():
    """The thickness of a blank to write on, of a frame and of a writing
    line: 0.4 pt at the normal size, thicker as the print grows (a hair
    line under a 20 pt word is hard to find)."""
    return "%.1fpt" % (0.4 * print_size() / DEFAULT_PRINT_SIZE)


def blank_rule():
    """The blank a fill sentence leaves for its missing word."""
    return "\\rule{5em}{%s}" % rule_width()


def panel(colour):
    """The opening of a tinted panel, `\\colorbox{colour}`.  In black and
    white the tint is gone, and what set the panel off from the page would
    go with it: it becomes a white panel in a thin black frame instead."""
    if is_mono():
        return "\\fcolorbox{rulec}{white}"
    return "\\colorbox{%s}" % colour


def print_class_tex(size):
    """The %%DOCUMENTCLASS%% line.  At the normal size it is the one the
    template always had; the larger sizes need extarticle (TeX Live's
    `extsizes` package), and a TeX without it is stopped with a message that
    says so, rather than a bare `File not found`."""
    if size == DEFAULT_PRINT_SIZE:
        return "\\documentclass[11pt,a4paper]{article}"
    return ("\\IfFileExists{extarticle.cls}{}{\\errmessage{Large print needs "
            "the TeX package extsizes (extarticle.cls), which this TeX "
            "installation does not have. Install extsizes with the TeX "
            "package manager, or build at Normal print size}}\n"
            "\\documentclass[%dpt,a4paper]{extarticle}" % size)


# A table is set at the print size like everything else, and a table of
# six columns that fits the page at 11 pt runs off it at 20: its cells do
# not wrap.  In large print a table wider than the line is scaled down to
# the line -- as large as the page allows, which is still larger than it
# was at the normal size -- and one that fits is left alone.
_FIT_TEX = r"""% large print: a table wider than the line is scaled down to it
\newsavebox\exlexfitbox
\newcommand\exlexfit[1]{\sbox\exlexfitbox{#1}%
  \ifdim\wd\exlexfitbox>\linewidth\resizebox{\linewidth}{!}{\usebox\exlexfitbox}%
  \else\usebox\exlexfitbox\fi}"""


# A paragraph in a column that nothing may cross.  A matching entry in its
# frame, a true/false statement beside its marks, a chunk too long for its
# row: each is a paragraph of a fixed width, and a word in it that cannot
# break -- a compound TeX finds no hyphen in, a target phrase that is one
# box (\pe) -- runs out of the column when it is wider than it: across the
# frame, under the marks.  Large print makes that common (a German compound
# that fits a frame at 11 pt is twice the frame's width at 20).  So the
# paragraph is given every break it can take -- its callers start it with
# \hspace{0pt}, so that its first word can be hyphenated too (TeX
# hyphenates only a word that follows glue), and a line may end after a
# slash ("socioeconomic/political") -- and is set once with the complaint
# silenced; its lines are read back, and if one of them is still too wide,
# the paragraph is set again as wide as its widest line and scaled down to
# the column: smaller, but inside it.  A paragraph that fits, which is
# nearly every one, is the one set the first time.  In large print the
# column beside a lemma's headword is fitted by it too (_VOCEFIT_TEX).
_FITPAR_TEX = r"""% a paragraph in a column nothing may cross (texgen._FITPAR_TEX)
% \exlexfitpar[t or b]{width}{paragraph}: a \vtop (or \vbox) that wide.
% The paragraph closes any colour it opens in a group of its own: a colour
% left open would be reset after its last line and hide the lines from
% \lastbox, which reads them back -- and the paragraph is then left as set.
\newbox\exlexfitparbox
\newbox\exlexfitparline
\newlength\exlexfitparcol
\newlength\exlexfitparwidest
\newif\ifexlexfitparover
\newXeTeXintercharclass\exlexfitparslash
\XeTeXinterchartoks\exlexfitparslash 0 = {\allowbreak}
\makeatletter
\newcommand\exlexfitpar[3][t]{%
  \setlength\exlexfitparcol{#2}%
  \exlexfitpar@set\exlexfitparcol{#3}%
  \global\exlexfitparoverfalse\global\exlexfitparwidest\z@
  \setbox\z@\vbox{\hfuzz\maxdimen\hbadness\@M
    \unvcopy\exlexfitparbox\exlexfitpar@lines}%
  \ifexlexfitparover\exlexfitpar@set\exlexfitparwidest{#3}\fi
  \if#1b\setbox\exlexfitparbox\vbox{\unvbox\exlexfitparbox}%
  \else\setbox\exlexfitparbox\vtop{\unvbox\exlexfitparbox}\fi
  \ifexlexfitparover\resizebox{\exlexfitparcol}{!}{\box\exlexfitparbox}%
  \else\box\exlexfitparbox\fi}
\def\exlexfitpar@set#1#2{%
  \setbox\exlexfitparbox\vbox{\hsize#1\relax\@parboxrestore
    \hfuzz\maxdimen\hbadness\@M
    \XeTeXinterchartokenstate\@ne\XeTeXcharclass`\/=\exlexfitparslash
    \color@begingroup#2\par\color@endgroup}}
% the lines, from the last up: each packed again to its own width, where
% TeX's \badness says whether it was overfull, and to its natural width
\def\exlexfitpar@lines{%
  \exlexfitpar@strip
  \setbox\exlexfitparline\lastbox
  \ifvoid\exlexfitparline\else
    \setbox\tw@\hbox to\wd\exlexfitparline{\unhcopy\exlexfitparline}%
    \ifnum\badness>\@M\global\exlexfitparovertrue\fi
    \setbox\tw@\hbox{\unhcopy\exlexfitparline}%
    \ifdim\wd\tw@>\exlexfitparwidest\global\exlexfitparwidest\wd\tw@\fi
    \expandafter\exlexfitpar@lines
  \fi}
% the glue, kerns and penalties between two lines
\def\exlexfitpar@strip{%
  \ifcase\numexpr\lastnodetype-10\relax
  \or\unskip\expandafter\exlexfitpar@strip
  \or\unkern\expandafter\exlexfitpar@strip
  \or\unpenalty\expandafter\exlexfitpar@strip
  \fi}
\makeatother"""

# Large print, a lemma head: its reading, transliteration and meaning sit in
# a column 0.38 of the line wide, beside the headword, and a one-word IPA
# that fitted it at 11 pt ran off the paper's edge at 20.  The headword is
# measured and scaled to its column by the template; these three are
# paragraphs, and \exlexfitpar sets each (bottom-aligned, as the column
# is).  They break where they broke at 11 pt, and a first word is not
# hyphenated: a hyphen inside a transcription reads as part of it, so a
# one-word IPA too wide for the column is scaled, as the headword beside it
# is.  The template marks the three with %%VOCEFIT%%, which is nothing at
# the normal size -- the .tex is the one it always was -- and this macro in
# large print.  An empty field is left exactly as it was: a line of nothing
# would move the column.
_VOCEFIT_TEX = r"""% large print: a lemma head's reading, transliteration and meaning fit their column
\newbox\exlexfitvocebox
\newcommand\exlexfitvoce[1]{\sbox\exlexfitvocebox{#1}%
  \ifdim\wd\exlexfitvocebox=0pt {#1}%
  \else\leavevmode\exlexfitpar[b]{\linewidth}{\raggedleft\noindent{#1}}\fi}"""


# every colour the template defines, and what it becomes in black and white:
# the inks black, the tints white (a panel keeps a frame instead: panel())
_MONO_INK = ("accent", "accentlt", "rulec", "graytx", "facrimson", "faindigo",
             "fateal", "faviolet", "faamber", "linkc", "faungram", "faok")
_MONO_PAPER = ("boxbg", "rtlbgquote", "rtlbgsand", "rtlbgrose", "rtlbgsage",
               "rtlbglilac")


def print_options_tex(size, mono):
    """The %%PRINTOPTIONS%% block: nothing at all for 11 pt in colour, so
    that build is the one it always was."""
    out = []
    if size != DEFAULT_PRINT_SIZE:
        out.append("% large print: frames as heavy as the blanks and lines")
        out.append("\\setlength{\\fboxrule}{%s}" % rule_width())
        # a line holds fewer words, so fewer spaces to stretch: a paragraph
        # with a long unbreakable word (a `code` span) found no line loose
        # enough within the tolerance and set one into the margin instead
        out.append("% large print: a looser line rather than one into the margin")
        out.append("\\emergencystretch=3em")
        out.append(_FIT_TEX)
        # here, before the template's \voce, which uses it in large print;
        # the exercises' macros then do not define it again
        out.append(_FITPAR_TEX)
        out.append(_VOCEFIT_TEX)
    if mono:
        out.append("% black and white: every ink black, every tint white")
        out += ["\\definecolor{%s}{HTML}{000000}" % c for c in _MONO_INK]
        out += ["\\definecolor{%s}{HTML}{FFFFFF}" % c for c in _MONO_PAPER]
        out.append("\\hypersetup{allcolors=linkc}")
    return "\n".join(out)


# The Persian values, bound to the old names for any caller that still
# imports them.  No rendering path in this file or in htmlgen reads them:
# they would be wrong for every other language.
FA_CHARS = languages.get("fa").chars
FA_RE = languages.get("fa").re_chars
RUN_RE = languages.get("fa").run_re

PE_WORD_LIMIT = 4          # runs longer than this become \pel (breakable)
# a language without word separators (Japanese) counts characters instead
PE_CHAR_LIMIT = 8

_SPECIALS = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
             "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
             "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def escape_latin(s):
    return "".join(_SPECIALS.get(c, c) for c in s)


# ----------------------------------------------------------------------
# footnotes, links, colour marks
# ----------------------------------------------------------------------
# Five dark hues, legible on white paper and (via lighter CSS variants)
# on a dark screen.  The names are the authoring interface: `[متن]{teal}`.

# ^[nota inline] — tolerates one level of nested [..]{..}/[..](..), same
# as LA_RE, so a translit/colour/link mark can sit inside an inline note
# without the naive no-brackets-at-all form silently eating the footnote
# (before this it matched nothing, spilled "^[" as literal text, and the
# note vanished with no error).
FN_INLINE_RE = re.compile(
    r"\^\[((?:[^\[\]]|\[[^\[\]]*\](?:\{[^{}]*\}|\([^()\s]*\))?)*)\]")
FN_REF_RE = re.compile(r"\[\^([^\[\]\s]+)\]")           # [^id]
LINK_RE = re.compile(r"\[([^\[\]]*)\]\(\s*([^()\s]+)\s*\)")   # [testo](url)

# [](doc:The shape of a word) — a link to another document in the same
# library, by its NAME: the target's title, exactly as its front matter
# spells it, spaces and all.  A name is what a person can read and type,
# and what a file carried out of the studio still means; the studio keeps
# it pointing at the same document by rewriting the links when the
# document is renamed (store.py, "rename propagation"), and a document
# deleted leaves its links hanging until one of that name comes back.
# The bracket text is the label; left empty, the target's current title
# is shown.  Matched before LINK_RE, which would otherwise swallow it and
# then reject `doc:` as an unsafe scheme.
#
# The name runs to the closing parenthesis.  Parentheses inside it are
# written as they are when they pair up (two deep), a lone one and a
# backslash with a backslash in front -- `doc:Notes \(draft` --
# which is what escape_doc_name writes and unescape_doc_name reads back.
# A name never holds a line break.  A link written before names,
# `doc:9f3c1a7b20de`, is a name too, and resolves through the uid it
# spells when no document is called that (lookup_doclink).
#
# The label is text, and may hold marks one level deep: a word of the
# target language (`[[il nome]{tl}](doc:…)`, which is what the Doc link
# picker writes when the words selected are a mark), a word coloured or
# transliterated in it (`[the [verbs]{teal}](doc:…)`, which is what the
# hover tools write when a word of a label is recoloured).  The renderers
# assemble the marks inside first, then the link around them.
_DOCNAME_CH = r"(?:[^()\\\n]|\\[^\n])"
_DOCNAME = r"(?:%s|\((?:%s|\(%s*\))*\))+" % (_DOCNAME_CH, _DOCNAME_CH, _DOCNAME_CH)
_DOCLABEL = r"(?:[^\[\]]|\[[^\[\]]*\]\{[^{}]*\})*"
DOCLINK_RE = re.compile(r"\[(" + _DOCLABEL + r")\]\(\s*doc:(" + _DOCNAME + r")\)")
# the uid a link written before names spells
LEGACY_UID_RE = re.compile(r"[0-9a-fA-F]{6,32}")
# [testo]{teal} — or an arbitrary colour: [testo]{#8E2B34}
COLOR_RE = re.compile(
    r"\[([^\[\]]*)\]\{\s*(#[0-9A-Fa-f]{6}|[A-Za-z]+)\s*\}")

# [تند]{translit:tond} — a transliteration annotation: the text renders
# exactly as if unmarked (in the PDF the mark disappears entirely); the
# web keeps the transliteration as data for the hover overlay.  It may
# carry a colour too: [تند]{teal translit:tond}.  A reading language adds
# the kana as a third independent half, in any order:
# [漢字]{kana:かんじ translit:kanji}; `reading:` is an alias of `kana:`.
# Each value runs to the next key or the closing brace, so it can contain
# spaces.
MARK_KEYS = ("translit", "kana", "reading")
_MARK_KEY_RE = r"(?:translit|kana|reading)"
TRANSLIT_RE = re.compile(
    r"\[([^\[\]]*)\]\{\s*(?:(#[0-9A-Fa-f]{6}|[A-Za-z]+)\s+)?"
    r"(" + _MARK_KEY_RE + r":[^{}]*?)\s*\}")
_MARK_SPLIT_RE = re.compile(r"\s+(?=" + _MARK_KEY_RE + r":)")


def parse_mark_fields(raw):
    """`kana:かんじ translit:kanji` -> {"translit": "kanji", "kana": "かんじ"}.

    Keys may come in any order; a key given twice keeps the last value;
    `reading:` is stored under "kana".  Missing keys are absent.
    """
    return parse_marks(raw)


def _norm_colour(v):
    """Colour token -> normalised name/#HEX, or None when invalid."""
    return normalise_colour(v)

# `[…]{tl}`: the bracketed stretch is prose in the target language, laid
# out AS A WHOLE in that language's direction and font -- ASCII
# punctuation, digits, emoji and embedded Latin words included.  For an
# RTL language this is what keeps `!` or `PDF` from splitting the
# line into fragments whose order the LTR paragraph then scrambles.
# Content is opaque: no markdown inside.  The generic marker is `{tl}`;
# the document's OWN code is an alias (`{ja}`, `{ar}`, `{it}`), and
# `{fa}` / `{rtl}`, the markers of the Persian-only days, stay accepted
# in Persian documents (docs/languages.md, 5).  Another language's code
# is not a marker: in a Persian document `[bello]{it}` is what it always
# was, literal text -- so the regex is built per language, and cached.
# Optional styling attributes: `{tl font=nastaliq bg=quote vertical
# height=24}` — omitted, everything defaults to the plain behaviour.
_TL_CACHE = {}


def tl_re(code=None):
    """The block-marker regex of the current language (or of the language
    `code` names): group 1 the content, group 2 the attributes."""
    L = languages.get_or_default(code) if code else cur_lang()
    rx = _TL_CACHE.get(L.code)
    if rx is None:
        markers = ["tl", L.code]
        if L.code == languages.DEFAULT:
            markers.append("rtl")
        rx = re.compile(r"\[([^\[\]]+)\]\{\s*(?:%s)\b([^{}]*)\}"
                        % "|".join(re.escape(m) for m in markers))
        _TL_CACHE[L.code] = rx
    return rx


class TargetMark:
    """One balanced ``[content]{tl ...}`` mark.

    The historical regular expression remains the fast path for ordinary
    bracketless content.  This scanner is the narrow nested path needed by
    a target-language mark containing a segmented-colour word.
    """

    def __init__(self, start, end, content, attrs):
        self.start = start
        self.end = end
        self.content = content
        self.attrs = attrs


def target_marks(text, code=None):
    """Yield balanced target-language marks, including nested brackets."""
    L = languages.get_or_default(code) if code else cur_lang()
    markers = ["tl", L.code] + (["rtl"] if L.code == languages.DEFAULT else [])
    suffix = re.compile(r"\{\s*(?:%s)\b([^{}]*)\}"
                        % "|".join(re.escape(m) for m in markers))
    i = 0
    while i < len(text):
        start = text.find("[", i)
        if start < 0:
            return
        depth, at = 1, start + 1
        while at < len(text) and depth:
            if text[at] == "[":
                depth += 1
            elif text[at] == "]":
                depth -= 1
            at += 1
        if depth:
            i = start + 1
            continue
        mark = suffix.match(text, at)
        if mark:
            yield TargetMark(start, mark.end(), text[start + 1:at - 1], mark.group(1))
            i = mark.end()
        else:
            i = start + 1


def target_fullmatch(text, code=None):
    """The balanced target mark when it occupies *text* completely."""
    found = list(target_marks(text, code))
    return found[0] if len(found) == 1 and found[0].start == 0 \
        and found[0].end == len(text) else None


# The Persian regex under the old names, for callers that still import
# them; no rendering path reads them.
TL_RE = RTL_RE = re.compile(r"\[([^\[\]]+)\]\{\s*(?:tl|%s|rtl)\b([^{}]*)\}"
                            % re.escape(languages.DEFAULT))

# `[[slot]]`: the blank of a fill-in exercise, named so its answer row can
# claim it.  THE NAME HOLDS NO BRACKET -- which is what tells `[[[slot]]`
# apart: one `[` opening a mark, then the slot.  Read with `[^\]]+` the
# name came out as `[slot`, no answer row claimed it, and the exercise was
# refused as "slots and [slot] answer rows differ".
SLOT_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
SLOT_SPLIT_RE = re.compile(r"(\[\[[^\[\]]+\]\])")

# A target-language mark holding blanks: `[من بابک [[slot]]]{tl}`.  A
# mark's content is opaque and bracketless (tl_re), so this is not one --
# but it is the natural way to write a sentence of the target language
# with a blank in it, and the way this file's own prompt now teaches.
_SLOTTED_CACHE = {}


def _slotted_re():
    L = cur_lang()
    rx = _SLOTTED_CACHE.get(L.code)
    if rx is None:
        markers = ["tl", L.code]
        if L.code == languages.DEFAULT:
            markers.append("rtl")
        rx = re.compile(r"\[((?:[^\[\]]|\[\[[^\[\]]+\]\])+)\]\{\s*(%s)\b([^{}]*)\}"
                        % "|".join(re.escape(m) for m in markers))
        _SLOTTED_CACHE[L.code] = rx
    return rx


def spread_slots(text):
    """`[من بابک [[slot]]]{tl}` -> `[من بابک]{tl} [[slot]]`.

    ONE SENTENCE OF THE TARGET LANGUAGE, WRITTEN AS ONE.  A blank is not
    target-language text: it is a hole in it, and the renderers cut the
    sentence at every hole and set the pieces themselves.  A mark cannot
    hold the hole, then -- but the author should not have to know that, and
    should not have to mark each piece by hand (which also loses the fact
    that the pieces are one sentence, and with it the direction the whole
    thing is laid out in).  So the mark is spread over the pieces here, once,
    where the exercise is parsed: every renderer downstream sees marks it
    already understands, and `is_target_line` reads the same text to say that
    the line as a whole is the target's.

    The mark's own attributes ride along (`{tl font=nastaliq}`), the marker
    word the author wrote is kept, and the spaces round each hole stay
    OUTSIDE the marks -- a mark is one laid-out box, and a space inside its
    brackets would be set in the target font and hang at the box's edge.
    Text with no slotted mark comes back unchanged, so this is safe to run
    over every field of every exercise.
    """
    def one(m):
        content, marker, attrs = m.group(1), m.group(2), m.group(3)
        if not SLOT_RE.search(content):
            return m.group(0)               # an ordinary mark: leave it be
        out = []
        for piece in SLOT_SPLIT_RE.split(content):
            if not piece:
                continue
            if SLOT_SPLIT_RE.fullmatch(piece):
                out.append(piece)
                continue
            core = piece.strip()
            if not core:
                out.append(piece)           # the space between two blanks
                continue
            lead = piece[:len(piece) - len(piece.lstrip())]
            trail = piece[len(piece.rstrip()):]
            out.append("%s[%s]{%s%s}%s" % (lead, core, marker, attrs, trail))
        return "".join(out)
    return _slotted_re().sub(one, text or "")


def is_target_line(text):
    """Is this line the target language as a whole -- so that it is laid out
    in the target's direction, and not in the prose's?

    THE DIRECTION OF A RUN IS NOT THE DIRECTION OF ITS CONTAINER.  An RTL run
    inside a left-to-right line is one box in a left-to-right row of boxes:
    put a blank after a Persian phrase there and the blank is drawn to the
    RIGHT of it, which reads as the blank coming FIRST.  A line that is
    Persian throughout has to be laid out right-to-left, and then the boxes
    fall in reading order.

    Two ways a line can be the target's throughout: every run of it is marked
    (`[…]{tl}`), which is how a Latin-script target must be written and how
    any target may be; or it is the target's own script and nothing else,
    which the renderers detect already (is_fa_only_paragraph).  A blank is a
    hole in the sentence rather than text, and counts for neither.
    """
    bare = SLOT_RE.sub(" ", text or "")
    if not bare.strip():
        return False
    if tl_re().search(bare) and not re.search(r"[^\W\d_]", tl_re().sub(" ", bare)):
        return True                          # every word of it is marked
    return is_fa_only_paragraph(bare)

# A WORD, IN WHATEVER SCRIPT IT IS WRITTEN.  This was `[A-Za-zÀ-ÿ]`, which
# stops at Latin-1: ✗ tinted `çok` but gave up at Turkish ş, ğ and ı, and
# every Greek, Cyrillic, Devanagari and Arabic word lost the red after its
# first letter -- while the library card's word count missed those words
# altogether.  `[^\W\d_]` is every letter Unicode has.  The characters
# beside it are the ones that belong INSIDE a word without being letters,
# and would otherwise end it in the middle: the combining marks of the
# scripts the registry carries (Arabic harakat, Devanagari matras, the
# Latin, Greek and Cyrillic diacritics, the Japanese voicing marks) and the
# zero-width non-joiner Persian writes between the parts of one word.
WORD_MARKS = ("̀-ͯ҃-҉֑-ׇؐ-ؚ"
              "ً-ٰٟۖ-ܑۭܰ-݊"
              "ऀ-ःऺ-ॏ॑-ॗॢॣ"
              "ัิ-ฺ็-๎‌‍゙゚")
# what ✗ tints: one word, apostrophes and hyphens and all (`✗can't`, `✗ad-hoc`)
UNGRAM_WORD = r"(?:[^\W\d_]|['’\-%s])+" % WORD_MARKS
# what is counted as a word of the prose: two letters or more
PROSE_WORD_RE = re.compile(r"(?:[^\W\d_]|[%s]){2,}" % WORD_MARKS)

# `✗[…]{teal}`, `✗[…]{translit:…}`, `✗[…]{tl}`: a mark straight after ✗.
# The ungrammatical red cannot be overridden, so the colour and the
# annotations go; what the run becomes is per script (see inline()).
UNGRAM_MARK_RE = re.compile(
    r"✗\[([^\[\]]*)\]\{\s*(?:(?:#[0-9A-Fa-f]{6}|[A-Za-z]+)\s*)?"
    r"(?:" + _MARK_KEY_RE + r":[^{}]*)?\}")

# For a Latin-script target nothing can be detected, so every run of the
# target language is a mark: `[bello]{tl}`, `[bello]{it}`, or any mark
# that already exists (`[bello]{teal}`, `[bello]{translit:'bɛllo}`).  The
# rule (docs/languages.md, 5): a `[…]{…}` whose content has no nested
# brackets and whose attributes are not `la`/`ltr`, not a footnote, not a
# link.  Group 1 is the run, 2 the leading token (a colour, `tl`, the
# code, or an unknown word), 3 the key:value fields.
LATIN_RUN_RE = re.compile(
    r"(?<!\^)\[([^\[\]]+)\]\{\s*(?!(?:la|ltr|math)\b)"
    r"(?:(#[0-9A-Fa-f]{6}|[A-Za-z]+)\b\s*)?"
    r"((?:" + _MARK_KEY_RE + r":[^{}]*?)?)\s*\}")

# MATHS.  `[a^2+b^2]{math}` in a line, and a `:::math` fence on its own
# (mdparser).  Neither `$` nor `\[` is a marker here: `$` is a character
# somebody writing about money will type by accident, `\[` is already
# LaTeX's own and would have to be escaped everywhere else, and both would
# have to be hunted for inside every other mark's content.  A brace word
# after a bracketed text is what every other mark in this dialect looks
# like, so maths looks like one too.
#
# THE BODY MAY HOLD BRACKETS, which is the whole reason it is not written
# with `[^\[\]]+` as `tl_re` is: an interval `[0,1]` or `[0,1)` or `]0,1[`,
# a `\left[`, a `\sqrt[3]{x}`, an `a_{[i]}` are ordinary mathematics and
# would all fail that.  `]{math}` is the terminator, and no formula
# contains it.
#
# BUT THE FORMULA STARTS AT ITS OWN `[`, not at the first one of the text.
# Read as `\[(.+?)\]\{math\}` it started at the first `[` the text had, so
# `[تند]{teal} then [x^2]{math}` was the formula `تند]{teal} then [x^2`:
# a mark, a link, a blank written before a formula in the same paragraph
# went into it -- and colouring a word before one from the hover palette,
# which writes such a mark, broke the paragraph.  A bracket the formula
# opens and closes itself (_MATH_GROUP, three deep) may be followed by
# anything, `\sqrt[3]{x}`'s `{` included; a `]` it did not open may not be
# followed by `{`, `(` or `]` -- that is the end of another mark, a link or
# a blank -- except the formula's own last `]` before `]{math}` (`(0,1]`).
# Nor does a formula start at a blank's `[[`.  A group closed by the
# terminator is no group: in `[x + [0,1)]{math}` the second `[` is an
# interval's, and the formula is the whole of it.
_MATH_END = r"\]\{\s*math\s*\}"
_MATH_GROUP = r"\[[^\[\]]*\]"                              # one deep,
_MATH_GROUP = r"\[(?:[^\[\]]|%s)*\]" % _MATH_GROUP         # two,
_MATH_GROUP = r"\[(?:[^\[\]]|%s)*\]" % _MATH_GROUP         # three
_MATH_GROUP += r"(?!\{\s*math\s*\})"
_MATH_SLOT = r"\[\[[^\[\]]+\]\](?!\{\s*math\s*\})"     # SLOT_RE, uncaptured
MATH_RE = re.compile(
    r"(?!%s)\[((?:[^\[\]]|%s|(?!%s)\[|\](?![{(\]])|\](?=%s))+?)%s"
    % (_MATH_SLOT, _MATH_GROUP, _MATH_GROUP, _MATH_END, _MATH_END))

# INLINE LATEX (TO-DO §8.39's L8): `LATEX_INLINE_RE` and `inline_latex_pairs`
# live in lib/latexthemes.py, beside `blocks_in` -- the same light reading a
# phone's kept-page mechanism needs without importing the studio's parser
# (lib/offline.py) -- and are used here exactly as `MATH_RE`, just below,
# and every reason its own comment gives ("its body may hold brackets...").
from latexthemes import LATEX_INLINE_RE, inline_latex_pairs  # noqa: E402,F401

# A brace word that is NOT a run of the target language.  For a Latin
# target an unknown word in the braces marks a run (docs/languages.md, 5),
# and `math`/`latex` must not be swallowed that way: `[E=mc^2]{math}` in an
# Italian document is a formula, not Italian set in the target's font.
NOT_A_RUN = ("la", "ltr", "math", "latex")

# Soft background tints for target-language blocks (e.g. bg=quote marks a
# citation).  Hex pairs: on paper / on the dark web theme.
RTL_BG = {
    "quote": ("EEF3F6", "2A3640"),
    "sand":  ("F5EDDC", "3B3425"),
    "rose":  ("F7E8E8", "3D2B2E"),
    "sage":  ("EAF2E6", "2C372B"),
    "lilac": ("EFEAF6", "332C3F"),
}
TL_BG = RTL_BG
# the alternate face is per language now (fonts.alt_key: nastaliq for fa,
# gothic for ja); this tuple is the Persian value for old importers
RTL_FONTS = ("nastaliq",)
TL_HEIGHT_DEFAULT = 22       # em, the column height of a vertical block
TL_HEIGHT_MIN, TL_HEIGHT_MAX = 8, 60

# `[testo]{la …}` — the Latin mirror of `{tl}`: a whole paragraph whose
# block can be tinted (`bg=` — same tints), whose text can be aligned
# (`align=left|center|right`), and which can be narrowed and shifted
# sideways with the same knobs images use (`width=`/`offset=`, in % of
# the column).  Unlike `{tl}`, the content is ordinary markdown — the
# regex tolerates one level of inner brackets (links, colour marks,
# footnote refs).  Recognised only as a full paragraph.
LA_RE = re.compile(
    r"\[((?:[^\[\]]|\[[^\[\]]*\](?:\{[^{}]*\}|\([^()\s]*\))?)+)\]"
    r"\{\s*(?:la|ltr)\b([^{}]*)\}", re.S)


def parse_la_attrs(raw):
    """`align=right bg=quote width=60 offset=10` -> validated dict."""
    out = {"align": "left", "bg": None, "width": 100, "offset": 0}
    for m in re.finditer(r"([a-z]+)\s*=\s*(-?[\w-]+)", raw or ""):
        k, v = m.group(1), m.group(2).lower()
        if k == "align" and v in ("left", "center", "right"):
            out["align"] = v
        elif k == "bg" and v in RTL_BG:
            out["bg"] = v
        elif k in ("width", "offset"):
            try:
                n = int(round(float(v)))
            except ValueError:
                continue
            if k == "width":
                out["width"] = max(10, min(100, n))
            else:
                out["offset"] = max(-100, min(100, n))
    return out


def parse_tl_attrs(raw):
    """`font=gothic bg=quote vertical height=24` -> {"font", "bg",
    "vertical", "height"} (None/False = default).

    `font` is accepted only when it names the current language's alternate
    face (fonts.alt_key); `vertical` (also `mode=vertical`, `tategaki`)
    only when the language can be set vertically; `height` is the column
    height of a vertical block in em, clamped to 8..60, default 22.
    """
    L = cur_lang()
    out = {"font": None, "bg": None, "vertical": False,
           "height": TL_HEIGHT_DEFAULT}
    raw = raw or ""
    for m in re.finditer(r"([a-z]+)\s*=\s*([\w-]+)", raw):
        k, v = m.group(1), m.group(2).lower()
        if k == "font" and L.fonts.get("alt_key") and v == L.fonts["alt_key"]:
            out["font"] = v
        elif k == "bg" and v in RTL_BG:
            out["bg"] = v
        elif k == "mode" and v == "vertical" and L.vertical:
            out["vertical"] = True
        elif k == "height":
            try:
                out["height"] = max(TL_HEIGHT_MIN, min(TL_HEIGHT_MAX, int(v)))
            except ValueError:
                pass
    if L.vertical and re.search(r"(?<![=\w])(?:vertical|tategaki)\b", raw):
        out["vertical"] = True
    return out


parse_rtl_attrs = parse_tl_attrs      # the old name

# no PDF font here has emoji glyphs; they are kept on the web and
# silently dropped on paper
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF"   # emoji planes
                      "\u2600-\u26FF"            # misc symbols
                      "\u2700-\u27BF"            # dingbats
                      "\u2B00-\u2BFF"            # arrows, stars
                      "\uFE00-\uFE0F\u200D]")   # selectors, ZWJ

_MIRROR = {"(": ")", ")": "(", "[": "]", "]": "[", "<": ">", ">": "<",
           "{": "}", "}": "{"}


def is_fa_only_paragraph(text):
    """True when a paragraph has no Latin letters at all but does contain
    the target script — punctuation, digits and emoji allowed.  Such
    paragraphs are rendered as a block in the target language without any
    marker: right-to-left prose for fa/ar, a left-to-right paragraph in
    the target font for ja.  Never for a Latin-script target, whose text
    cannot be told from the prose."""
    L = cur_lang()
    if not L.re_chars:
        return False
    return (not re.search(r"[A-Za-z]", text)
            and len(L.re_chars.findall(text)) >= 2)


is_target_only_paragraph = is_fa_only_paragraph


# LATIN LETTERS IN THE TARGET'S OWN TEXT.  A Latin word inside a run or a
# block of the target language (`[أرسلت ملف PDF]{tl}`) is set in the
# target's face -- and Noto Naskh Arabic, Noto Nastaliq Urdu and the
# Devanagari faces have no Latin letters: the word was a blank on paper,
# and "Missing character" in the log.  Each stretch of Latin letters, with
# the ASCII round it (`(PDF)`, `e-mail`), is written `{\tllatin …}`;
# \tllatin (TARGET_LATIN_TEX) keeps a face that has the letters, as
# Vazirmatn and the Japanese and Chinese faces do, and sets them otherwise
# in the family the target's text was entered from.  Which face that is,
# is known only where TeX loads it.  Digits are left alone: every target
# face has them.  A Latin-script target's run is Latin all through, and
# is left as it was.
_LATIN_STRETCH_RE = re.compile(
    r"[\x21-\x7E\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u024F]*"
    r"[A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u024F]"
    r"[\x21-\x7E\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u024F]*")


def latin_in_target(text):
    """`text` escaped for TeX, each stretch of Latin letters in it in
    `{\\tllatin …}` -- for a target with its own script."""
    if is_latin_target():
        return escape_latin(text)
    out, at = [], 0
    for m in _LATIN_STRETCH_RE.finditer(text):
        out.append(escape_latin(text[at:m.start()]))
        out.append("{\\tllatin %s}" % escape_latin(m.group(0)))
        at = m.end()
    out.append(escape_latin(text[at:]))
    return "".join(out)


def rtl_fragment(content):
    """Persian-rich text -> TeXXeT fragment: base direction R with
    \\beginL…\\endL islands for Latin words/numbers, brackets mirrored
    in the RTL stream, emoji stripped (no glyphs on paper), and the ⏎
    symbol turned into a forced line break.

    Latin words next to each other are one island, which reads left to
    right as they were written: an island each, the right-to-left line
    ran them from right to left ("yesterday? go you did Where Neda:").
    And an island ends in `\\endL{}`, since a control word eats the space
    after it: the word after an island was set against it, "17ساله"."""
    content = EMOJI_RE.sub("", content)
    content = re.sub(r"\s*⏎\s*", " ⏎ ", content)
    out, latin = [], []

    def island():
        if latin:
            out.append(r"\beginL %s\endL{}" % " ".join(latin_in_target(t) for t in latin))
            del latin[:]
    for tok in content.split():
        if tok == "⏎":
            island()
            out.append(r"\newline")
        elif re.search(r"[A-Za-z0-9]", tok):
            latin.append(tok)
        else:
            island()
            out.append(escape_latin(
                "".join(_MIRROR.get(c, c) for c in tok)))
    island()
    return " ".join(out)


def ltr_fragment(content):
    """The same for a left-to-right language: no islands, no mirroring —
    only the emoji dropped, the specials escaped (a Latin word put in a
    face that has its letters) and ⏎ made a break."""
    content = EMOJI_RE.sub("", content)
    parts = re.split(r"\s*⏎\s*", content.strip())
    return r"\newline ".join(latin_in_target(p) for p in parts)


def block_fragment(content):
    """A target-language block's content, in the current language's
    direction."""
    return rtl_fragment(content) if cur_lang().rtl else ltr_fragment(content)


def _segmented_tex(node):
    """A segmented node as one shaped TeX word, without its outer run."""
    if is_mono():
        return escape_latin(node.plain_text) if is_latin_target() else node.plain_text
    pieces = []
    for piece in node.pieces:
        body = escape_latin(piece.text) if is_latin_target() else piece.text
        if not piece.colour:
            style = ""
        elif piece.colour.startswith("#"):
            style = r"\color[HTML]{%s}" % piece.colour[1:]
        else:
            style = r"\color{fa%s}" % piece.colour
        pieces.append(r"\segpiece{%s}{%s}" % (style, body))
    plain = escape_latin(node.plain_text) if is_latin_target() else node.plain_text
    return r"\segword{%s}{%s}" % (plain, "".join(pieces))


def target_fragment(content):
    """Target-language prose with segmented words preserved as TeX nodes."""
    nodes = list(segmented_runs(content))
    if not nodes:
        return block_fragment(content)
    held = []
    for node in reversed(nodes):
        token = "\x06%s\x06" % chr(0xE000 + len(held))
        held.append((token, _segmented_tex(node)))
        content = content[:node.start] + token + content[node.end:]
    rendered = block_fragment(content)
    for token, shaped in held:
        rendered = rendered.replace(token, shaped)
    return rendered


# `pending` is non-None while rendering a construct where \footnote is
# unsafe (headings, tables, boxes): there we emit \footnotemark and flush
# \footnotetext after the construct — the standard LaTeX workaround.
_FN = ThreadDict(n=0, defs={}, pending=None, open=())


def reset_footnotes(defs=None):
    _FN["n"] = 0
    _FN["defs"] = dict(defs or {})
    _FN["pending"] = None
    _FN["open"] = ()


def _begin_defer():
    prev = _FN["pending"]
    _FN["pending"] = []
    return prev


def _end_defer(prev):
    pend, _FN["pending"] = _FN["pending"], prev
    if not pend:
        return ""
    if prev is not None:
        # still inside an outer construct (a table in a box, anything on a
        # flashcard): a \footnotetext here would land in its minipage, as
        # a lettered note at the foot of the box -- the outer one flushes
        prev.extend(pend)
        return ""
    return "\n" + "\n".join(
        r"\footnotetext[%d]{%s}\stepcounter{footnote}" % (num, body)
        for num, body in pend)


# The library a render resolves `doc:` links against: store.doc_index(),
# uid -> {"id", "title", "created"}, supplied per render by the studio and
# prepared here into the two ways a link finds its document (prepare_doc_index).
# Held thread-locally like the footnote state, so concurrent renders on the
# threaded server cannot read each other's library.  The CLI never sets it,
# and a `doc:` link there shows its own label, or the name it was given.
DOC_INDEX = ThreadDict(uids={}, names={})


def doc_name_key(name):
    """What two names are compared by: the same text in the same NFC form,
    trimmed, every run of blanks one space, and case-blind -- "Verbs  of
    motion" and "verbs of Motion" are one name, as they are one file name to
    a Mac or a Windows machine.  Names are unique in a library by this key
    (store.py), and a link finds its document by it."""
    s = unicodedata.normalize("NFC", str(name or ""))
    return " ".join(s.split()).casefold()


def escape_doc_name(name):
    """A document's name as it is written after `doc:` -- itself, with a
    backslash before every backslash and before every parenthesis that does
    not pair up (or pairs up more than two deep), so the link always closes
    where it should.  A line break, which no name holds, is a space."""
    s = re.sub(r"\s*\n\s*", " ", str(name or "")).strip()
    keep, open_ = set(), []
    for i, c in enumerate(s):
        if c == "(":
            open_.append((i, len(open_) + 1))
        elif c == ")" and open_:
            j, depth = open_.pop()
            if depth <= 2:
                keep.update((i, j))
    out = []
    for i, c in enumerate(s):
        if c == "\\" or (c in "()" and i not in keep):
            out.append("\\")
        out.append(c)
    return "".join(out)


def unescape_doc_name(target):
    """escape_doc_name undone: the name a link's `doc:` part spells."""
    return re.sub(r"\\(.)", r"\1", target or "").strip()


def doclink_markdown(label, name):
    """The markdown of a link to the document called `name`."""
    return "[%s](doc:%s)" % (label or "", escape_doc_name(name))


def prepare_doc_index(idx):
    """store.doc_index() -> {"uids": uid -> entry, "names": key -> entry}.

    Two documents can share a name only in a library that was written before
    names had to be unique (store.migrate_links puts that right): the one
    that held the name first, by `created`, is the one it finds, as it is
    the one the migration leaves it to.  An index prepared already is given
    back as it is (no uid is spelt "uids")."""
    if isinstance(idx, dict) and set(idx) == {"uids", "names"}:
        return idx
    idx = dict(idx or {})
    uids = dict((str(uid).lower(), info) for uid, info in idx.items())
    names = {}
    for info in sorted(idx.values(), key=lambda e: (str(e.get("created") or ""),
                                                   str(e.get("id") or ""))):
        key = doc_name_key(info.get("title"))
        if key and key not in names:
            names[key] = info
    return {"uids": uids, "names": names}


def set_doc_index(idx):
    DOC_INDEX.update(prepare_doc_index(idx))


def lookup_doclink(target, index=None):
    """The document a link's `doc:` part names -> its index entry, or None.

    By name first; a link written before names spells a uid, and it still
    reaches its document through that uid when no document is CALLED that
    (a name that happens to be twelve hex digits wins, since it is what the
    link says)."""
    index = index if index is not None else DOC_INDEX
    name = unescape_doc_name(target)
    info = index["names"].get(doc_name_key(name))
    if info is None and LEGACY_UID_RE.fullmatch(name):
        info = index["uids"].get(name.lower())
    return info


def resolve_doclink(target, label, index=None):
    """One `doc:` link -> (visible text, target document id or None).

    An explicit label always wins; without one the target's current title
    is shown.  A link to a document that is not in the library (deleted, or
    not made yet), and that was given no label of its own, shows the name it
    is waiting for -- a bare "?" on the page would say nothing about which
    document would bring it back -- and a link written before names, the
    `doc:<uid>` it points at, as it always did."""
    info = lookup_doclink(target, index)
    name = unescape_doc_name(target)
    text = ((label or "").strip()
            or (info or {}).get("title", "")
            or ("doc:" + name if LEGACY_UID_RE.fullmatch(name) else name))
    return text, (info or {}).get("id")


# A LINK AS THE SOURCE HOLDS IT.  The renderers find a link only after they
# have put a target-language mark, a formula and a footnote out of the way
# (inline(): `[[il nome]{tl}](doc:X)` is `[\x05N\x05](doc:X)` by the time
# DOCLINK_RE looks), so its label may hold one of them -- the Doc link picker
# writes exactly that when the words selected are a mark.  Whatever reads
# the links of a RAW text -- a rename rewriting them, the migration, the
# "Linked from" drawer, the hover tools blanking the names -- must find the
# links the page shows, no more and no fewer, or a link on the page is one a
# rename leaves behind.  So find_doclinks reads the text as inline() does:
# those marks blanked first, in inline()'s order and by its own regexes, at
# the same length (every offset still points into the source), then
# DOCLINK_RE; and a footnote's text on its own after that, as a footnote is
# rendered on its own.
#
# A PIECE AT A TIME, as inline() is handed them: a paragraph, a list item
# with the indented lines that go on with it, a heading, a cell of a table,
# a footnote's definition -- never two at once, so no mark it finds reaches
# from one into the next, and neither may one found here.  Read whole, a
# long chapter cost seconds a call (MATH_RE looks for its `]{math}` from
# every `[` of the text, to the end of the text when there is none, and does
# so again from the next one), and every rename, every new document and
# every "Linked from" read all of them; and a formula's `]{math}` found
# further on blanked the links in between, which the page shows.  Cut at
# blank lines only, a glossary of a thousand items or a table of a thousand
# rows, which has none, was still one piece: a second a call, and a formula
# in its last item hid the links of all the others.  So _doclink_pieces cuts
# the text where mdparser cuts it, reading its lines in the parser's order
# as notes.excerpt does; an exercise and a `:::math` formula, whose lines
# are joined in ways of their own, are cut at blank lines only, as they
# always were.  A piece that does not say "doc:" holds no link, and is not
# read at all; and MATH_RE, which cannot match without a `]{math}`, is not
# run over one that has none.
_BRACKETS = re.compile(r"[\[\]{}()]")
_MATH_END_RE = re.compile(_MATH_END)
_PIECE_QUOTE_RE = re.compile(r"[ \t]*((?:>[ \t]?)+)")      # a box's `>`s
_PIECE_RULE_RE = re.compile(r"-{3,}|\*{3,}|_{3,}")          # a rule: no piece
_PIECE_HEADING_RE = re.compile(r"#{1,3}\s")                 # its three levels
_PIECE_ITEM_RE = re.compile(r"\s*(?:[-*+]|\d+[.)])\s")      # a list item


class DocLink:
    """One `[label](doc:Name)` of a source text: `start`/`end` the whole
    link, `label` and `target` (the name as written, escapes and all) the
    source's own text, `target_start`/`target_end` where the name is."""
    __slots__ = ("start", "end", "label", "target", "target_start", "target_end")

    def __init__(self, text, m, masked_at):
        self.start, self.end = masked_at + m.start(), masked_at + m.end()
        self.target_start, self.target_end = masked_at + m.start(2), masked_at + m.end(2)
        self.label = text[masked_at + m.start(1):masked_at + m.end(1)]
        self.target = text[self.target_start:self.target_end]


def find_doclinks(text, code=None):
    """Every `[label](doc:Name)` link of `text` the page shows, in order ->
    [DocLink].  `code` is the document's language (its `{tl}` markers are
    its own); none given, the current one."""
    out = []
    if "doc:" not in text:
        return out
    for start, end in _doclink_pieces(text):
        out += _piece_doclinks(text[start:end], code, start, text)
    return out


def _doclink_pieces(text):
    """(start, end) of every piece of `text` inline() is handed on its own,
    in order: the text cut where mdparser.parse cuts it (above)."""
    import mdparser     # exlex's parser imports this module: not at the top
    lines = text.split("\n")
    out = []
    piece = []          # [start, end] of the piece being read, if one is
    # what a next line may add to it: "para" a plain line, "item" an indented
    # one that starts no item, "note" any indented one, "fence" anything up
    # to the `:::` (but a blank line); None nothing, it is a line of its own
    goes_on, depth, table = None, 0, False

    def cut():
        if piece:
            out.append(tuple(piece))
            del piece[:]

    def start(a, b, kind):
        nonlocal goes_on
        cut()
        piece[:] = [a, b]
        goes_on = kind

    def row(a, line):
        # a row of a table: each of its cells is a piece of its own
        nonlocal goes_on
        cut()
        goes_on, cell = None, a
        for k, ch in enumerate(line, a):
            if ch == "|":
                out.append((cell, k))
                cell = k + 1
        out.append((cell, a + len(line)))

    def dequote(line):
        m = _PIECE_QUOTE_RE.match(line)
        return (m.group(1).count(">"), line[m.end():]) if m else (0, line)

    at = 0
    for i, line in enumerate(lines):
        a, b = at, at + len(line)
        at = b + 1
        d, raw = dequote(line)
        s = raw.strip()
        if goes_on == "fence" and d >= depth:
            if not s:
                cut()
            elif piece:
                piece[1] = b
            else:
                piece[:] = [a, b]
            if s == ":::" and d == depth:
                cut()
                goes_on = None
            continue
        if d != depth or not s:
            # a box begins or ends, or a blank line: whatever was being read ends
            cut()
            depth, goes_on, table = d, None, False
            if not s:
                continue
        if table:
            if "|" in raw:
                row(a, line)
                continue
            table = False
        # the list goes on: a new item, or an indented line of the last one;
        # a footnote's definition goes on with any indented line
        if goes_on == "item" and _PIECE_ITEM_RE.match(raw):
            start(a, b, "item")
            continue
        if goes_on in ("item", "note") and raw.startswith(("  ", "\t")):
            piece[1] = b
            continue
        # a line read afresh, in the parser's order
        if _PIECE_RULE_RE.fullmatch(s):
            cut()
            goes_on = None
        elif (mdparser.EXERCISE_OPEN_RE.match(s) or mdparser.MATH_OPEN_RE.match(s)
              or mdparser.latexthemes.FENCE_OPEN_RE.match(s)):
            start(a, b, "fence")
        elif mdparser._FOOTNOTE_DEF.match(s):
            start(a, b, "note")
        elif (_PIECE_HEADING_RE.match(s) or mdparser.IMAGE_RE.match(s)
              or mdparser.VIDEO_RE.match(s)):
            start(a, b, None)
            cut()
        elif ("|" in s and i + 1 < len(lines)
              and dequote(lines[i + 1])[0] == depth
              and mdparser._TABLE_SEP.match(dequote(lines[i + 1])[1])):
            row(a, line)                # its header; the rows follow
            table = True
        elif _PIECE_ITEM_RE.match(raw):
            start(a, b, "item")
        elif goes_on == "para":
            piece[1] = b
        else:
            start(a, b, "para")
    cut()
    return out


def _piece_doclinks(text, code, at, whole):
    """find_doclinks of one piece (or of a footnote's text), `at`
    characters into `whole`."""
    if "doc:" not in text:
        return []
    blank = lambda m: _BRACKETS.sub("\x07", m.group(0))
    notes = []

    def note(m):
        notes.append((m.start(1), m.group(1)))
        return blank(m)
    masked = UNGRAM_MARK_RE.sub(blank, text.replace("❌", "✗"))
    masked = FN_INLINE_RE.sub(note, masked)
    masked = FN_REF_RE.sub(blank, masked)
    masked = tl_re(code).sub(blank, masked)
    if _MATH_END_RE.search(masked):
        masked = MATH_RE.sub(blank, masked)
    out = [DocLink(whole, m, at) for m in DOCLINK_RE.finditer(masked)]
    for start, body in notes:
        out += _piece_doclinks(text[start:start + len(body)], code, at + start, whole)
    out.sort(key=lambda l: l.start)
    return out


def escape_url(u):
    """Minimal escaping for the URL argument of \\href."""
    return u.replace("\\", "/").replace("%", r"\%").replace("#", r"\#")


def _footnote(num, content):
    # a note that cites itself, or a ring of notes, would expand forever:
    # a body already being expanded further up is left empty (htmlgen twin)
    opened, body = _FN["open"], ""
    if content.strip() and content not in opened:
        _FN["open"] = opened + (content,)
        try:
            body = inline(content)
        finally:
            _FN["open"] = opened
    if _FN["pending"] is not None:
        _FN["pending"].append((num, body))
        return r"\protect\footnotemark[%d]" % num
    return r"\footnote{%s}" % body


def run_is_long(run, size=DEFAULT_PRINT_SIZE):
    """Whether a run is long enough to be set breakable (\\pel): more than
    PE_WORD_LIMIT words, or, for a language without word separators, more
    than PE_CHAR_LIMIT characters -- a Japanese sentence in an \\mbox
    would run off the page.

    The limits are those of a line at the normal size.  A line of print
    `size` holds fewer words, fewer by the ratio of the sizes, and so does
    a run kept whole: four Italian words, one box, that sat inside the
    line at 11 pt ran off the paper at 20, and a Chinese sentence of three
    short runs between two blanks ran 115 pt past the frame.  In large
    print the limits shrink by that ratio.  The page (htmlgen) asks at
    the normal size, which is its own."""
    L = cur_lang()
    shrink = DEFAULT_PRINT_SIZE / float(size)
    if not L.spaced:
        return len(run) > PE_CHAR_LIMIT * shrink
    return len(run.split(" ")) > PE_WORD_LIMIT * shrink


def _fa_macro(run, force_breakable=False):
    # on a flashcard every run may break: half of a card is a narrow column,
    # as a matching exercise's frame is, and nothing may cross its fold
    breakable = force_breakable or _CARD["on"] or run_is_long(run, print_size())
    if is_latin_target():
        # a Latin run may carry TeX specials (an apostrophe is fine, a
        # per-cent sign is not); the scripts never do
        run = escape_latin(run)
    return ("\\pel{%s}" if breakable else "\\pe{%s}") % run


def fmt_time(s):
    """Seconds -> `1:30` / `1:02:03` (for video clip labels)."""
    if s is None:
        return ""
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, sec) if h else "%d:%02d" % (m, sec)


# A TITLE SHOWN FOR AN EMPTY LABEL (htmlgen's twin): the target's title is
# set on its own, as a title is (a run of the target script in its font, a
# mark in it coloured), and goes into the link whole, so that a bracket in
# it cannot break the link around it.  A title shown inside a title is set
# as its plain words: one holding a label-less link to itself would never
# end.
_SHOWING = ThreadDict(on=False)


def _shown_title(title, force_breakable=False):
    if _SHOWING["on"]:
        return escape_latin(title)
    _SHOWING["on"] = True
    try:
        # a note in a title would be one of this document's notes
        return inline(FN_REF_RE.sub("", FN_INLINE_RE.sub("", title)), force_breakable)
    finally:
        _SHOWING["on"] = False


def inline(text, force_breakable=False):
    """Markdown inline fragment -> TeX fragment."""
    store = []
    aux = []
    latin = is_latin_target()

    # ❌ typed in the source is a synonym of the ✗ marker; and a colour
    # mark straight after ✗ is stripped — the ungrammatical red always
    # wins and cannot be overridden, not even by the user.  For a script
    # language the bare text is re-detected as a run below; for a Latin
    # target the mark IS the run, so it is written back as the plain
    # marker, which the block pass freezes and the ✗ rule then flags.
    text = text.replace("❌", "✗")
    text = UNGRAM_MARK_RE.sub(r"✗[\1]{tl}" if latin else r"✗\1", text)

    def _aux(*payload):
        aux.append(payload)
        return "\x05%d\x05" % (len(aux) - 1)

    def freeze(m):
        store.append(m.group(0))
        return "\x00%d\x00" % (len(store) - 1)

    def freeze_text(s):
        store.append(s)
        return "\x00%d\x00" % (len(store) - 1)

    # 0. constructs whose argument must not undergo escaping/markdown:
    #    footnote bodies, URLs and colour names.  The bracketed *text* of
    #    a link or colour mark stays in place so it is processed normally.
    def _fn_inline(m):
        _FN["n"] += 1
        return _aux("fn", _FN["n"], m.group(1))
    text = FN_INLINE_RE.sub(_fn_inline, text)

    def _fn_ref(m):
        _FN["n"] += 1
        return _aux("fn", _FN["n"], _FN["defs"].get(m.group(1), ""))
    text = FN_REF_RE.sub(_fn_ref, text)

    # A target-language stretch may itself contain a segmented word.  Hold
    # the balanced outer mark first; otherwise its opening bracket is
    # mistaken for part of the inner run and its placeholder leaks.
    for mark in reversed(list(target_marks(text))):
        if list(segmented_runs(mark.content)):
            text = (text[:mark.start]
                    + _aux("rtl-seg", mark.content, parse_tl_attrs(mark.attrs))
                    + text[mark.end:])

    # One semantic run, frozen before the ordinary inner colour marks.
    # ``[[slot]]`` has no valid colour piece and is deliberately untouched.
    for node in reversed(list(segmented_runs(text))):
        text = text[:node.start] + _aux("seg", node) + text[node.end:]

    #    target-language stretches (before links/colours: same [..]{..}
    #    shape).  For a script language an inline `[…]{tl}` is one opaque
    #    unit in the target's direction; for a Latin target it is simply
    #    a run -- the marker is how a run is written at all.
    if latin:
        text = tl_re().sub(lambda m: freeze_text(m.group(1)), text)
    else:
        text = tl_re().sub(
            lambda m: _aux("rtl", m.group(1), parse_tl_attrs(m.group(2))), text)

    #    maths, before every other bracketed mark: its body may hold
    #    brackets and braces that would otherwise be read as one of them,
    #    and its text is LaTeX already -- frozen here, it never meets
    #    escape_latin and goes out exactly as it was written
    text = MATH_RE.sub(lambda m: _aux("math", m.group(1)), text)

    #    inline latex (TO-DO §8.39's L8): the drawing's own theme, not this
    #    document's own packages -- so it is drawn apart, never inserted as
    #    text here (see the "latex" case of _lone, below)
    text = LATEX_INLINE_RE.sub(lambda m: _aux("latex", m.group(1), m.group(3)), text)

    #    cross-document links first: LINK_RE matches the same shape and
    #    would freeze `doc:…` as an ordinary URL
    def _doclink(m):
        label, target = resolve_doclink(m.group(2), m.group(1))
        # an empty label shows the target's title, set apart and handed
        # in whole (_shown_title)
        if not m.group(1).strip():
            label = _aux("tex", _shown_title(label, force_breakable))
        return "[%s]%s" % (label, _aux("doc", target))
    text = DOCLINK_RE.sub(_doclink, text)

    text = LINK_RE.sub(
        lambda m: "[%s]%s" % (m.group(1), _aux("url", m.group(2))), text)

    #    transliteration/reading annotations (optionally coloured) —
    #    before the plain-colour pass, whose regex would not match the colon
    def _translit(m):
        fields = parse_mark_fields(m.group(3))
        return "[%s]%s" % (m.group(1),
                           _aux("colt", _norm_colour(m.group(2)),
                                fields.get("translit", ""),
                                fields.get("kana", "")))
    text = TRANSLIT_RE.sub(_translit, text)

    def _col(m):
        v = m.group(2)
        if v.startswith("#"):        # arbitrary colour by hex
            return "[%s]%s" % (m.group(1), _aux("col", "#" + v[1:].upper()))
        name = v.lower()
        if name not in PALETTE:
            if latin and name not in NOT_A_RUN:
                # for a Latin target an unknown word in the braces is
                # still a mark, and so a run: keep the text, drop the
                # word -- except the Latin-block keywords, which
                # LATIN_RUN_RE excludes too (docs/languages.md, 5)
                return "[%s]%s" % (m.group(1), _aux("colt", None, "", ""))
            return m.group(0)        # unknown colour: leave the text alone
        return "[%s]%s" % (m.group(1), _aux("col", name))
    text = COLOR_RE.sub(_col, text)

    # 1. freeze the runs (opaque from here on).  A Latin target has no
    #    detectable runs: its runs are the bracketed texts of the colour
    #    and translit marks just processed (`[bello]{teal}` -> the run
    #    `bello` inside its wrapper), plus the `[…]{tl}` frozen above.
    if latin:
        def _mark_run(m):
            item = aux[int(m.group(2))]
            if item[0] in ("col", "colt"):
                return "[%s]\x05%s\x05" % (freeze_text(m.group(1)), m.group(2))
            return m.group(0)
        text = re.sub(r"\[([^\[\]\x00]*)\]\x05(\d+)\x05", _mark_run, text)
    else:
        text = run_re().sub(freeze, text)

    # 2. escape LaTeX specials in the Latin remainder
    text = escape_latin(text)

    # 3. inline markdown on Latin -------------------------------------
    #    code spans first (their content was already escaped in step 2)
    text = re.sub(r"`([^`]+)`", r"\\texttt{\1}", text)

    #    bold: allowed around Latin or around a single frozen run
    def bold(m):
        inner = m.group(1)
        pm = re.fullmatch(r"\x00(\d+)\x00", inner)
        if pm:                       # **فارسی** -> bold run
            store[int(pm.group(1))] = "\x01" + store[int(pm.group(1))]
            return inner
        return r"\textbf{%s}" % inner
    text = re.sub(r"\*\*(.+?)\*\*", bold, text)

    #    italic: never across a run (a stray `*` next to the target script
    #    is the linguistics asterisk and must stay literal)
    def ital(m):
        inner = m.group(1)
        if "\x00" in inner:
            return m.group(0)
        return r"\emph{%s}" % inner
    text = re.sub(r"(?<![\w*\\])\*([^*\n]+?)\*(?!\*)", ital, text)

    #    arrows.  `->` is replaced by a function, not a string: re.sub
    #    reads a replacement string's `\r` as a carriage return, and the
    #    .tex got one followed by `ightarrow` wherever `->` was written
    text = text.replace("→", r" $\rightarrow$ ").replace("-\\textgreater{}", "->")
    text = re.sub(r"\s*->\s*", lambda _m: r" $\rightarrow$ ", text)

    #    ⏎ forces a line break (source newlines are ignored, this is the
    #    explicit way to keep one)
    text = re.sub(r"\s*⏎\s*", r"\\newline ", text)

    #    ✗ tints the following form red (marker + form, never overridable);
    #    ✅ is a stand-alone green check with no effect on what follows
    def _ungram_run(m):
        idx = int(m.group(1).strip("\x00"))
        store[idx] = "\x02" + store[idx]
        return m.group(1)
    text = re.sub(r"✗(\x00\d+\x00)", _ungram_run, text)
    text = re.sub(r"✗(%s)" % UNGRAM_WORD, r"\\ungram{\1}", text)
    text = text.replace("✗", r"\ungramX{}")
    text = text.replace("✅", r"\okmark{}")

    # 4. thaw the runs -----------------------------------------------
    def thaw(m):
        raw = store[int(m.group(1))]
        flags = set()
        while raw[:1] in ("\x01", "\x02"):
            flags.add(raw[0])
            raw = raw[1:]
        out = ("\\peb{%s}" % (escape_latin(raw) if latin else raw)
               if "\x01" in flags else _fa_macro(raw, force_breakable))
        if "\x02" in flags:
            out = "\\ungram{%s}" % out
        return out
    text = re.sub(r"\x00(\d+)\x00", thaw, text)

    # 5. assemble links and colour marks around their (now rendered) text
    def _bracket(m):
        inner, item = m.group(1), aux[int(m.group(2))]
        if item[0] == "url":
            return r"\href{%s}{%s}" % (escape_url(item[1]), inner)
        if item[0] in ("doc", "col", "colt") and is_mono():
            # black and white: a colour written inline would print as a
            # grey (or not at all), so none is written -- the text stays
            return inner
        if item[0] == "doc":
            # a link between studio documents: on paper there is nothing
            # to click through to, so it is set in the link colour to
            # show it is a reference and left at that
            return r"\textcolor{linkc}{%s}" % inner
        if item[0] == "col":
            if item[1].startswith("#"):
                return r"\textcolor[HTML]{%s}{%s}" % (item[1][1:], inner)
            return r"\textcolor{fa%s}{%s}" % (item[1], inner)
        if item[0] == "colt":
            # translit and kana are screen-only annotations: on paper only
            # the colour (if any) survives, the text itself is unchanged
            col = item[1]
            if col is None:
                return inner
            if col.startswith("#"):
                return r"\textcolor[HTML]{%s}{%s}" % (col[1:], inner)
            return r"\textcolor{fa%s}{%s}" % (col, inner)
        return m.group(0)
    # innermost first: a mark inside a link's label (DOCLINK_RE) is set
    # before the link around it can be
    for _ in range(3):
        was, text = text, re.sub(r"\[([^\[\]]*)\]\x05(\d+)\x05", _bracket, text)
        if text == was:
            break
    # and a label still holding brackets -- a mark in it that is none
    # (`[[کتاب]{red}](doc:…)`: no such colour), printed as it was written,
    # as it is outside a link -- is a link all the same
    text = re.sub(r"\[((?:[^\[\]]|\[[^\[\]]*\])*)\]\x05(\d+)\x05", _bracket, text)

    # 6. footnote marks, target-language stretches, and any link whose
    #    [text] did not survive
    def _lone(m):
        item = aux[int(m.group(1))]
        if item[0] == "fn":
            return _footnote(item[1], item[2])
        if item[0] == "math":
            # ON PAPER THERE IS NOTHING TO RENDER.  The page draws a formula
            # with MathJax because a browser has no mathematics of its own;
            # here the document IS LaTeX, so the author's notation goes
            # through as itself and TeX sets it.  Frozen before escape_latin
            # (step 2), so not one backslash of it was touched.
            return "\\(%s\\)" % item[1]
        if item[0] == "latex":
            # UNLIKE MATHS, THIS IS A PICTURE HERE TOO (the owner, 2026-09-27,
            # "same picture as the screen"): a theme's own packages must
            # never reach this document's preamble, the same reason a block
            # is one (TO-DO §8.39, above) -- an inline mark is drawn apart
            # and included, raised by its own depth so it sits on the line
            # it is in, never on its own bottom edge.
            draw = LATEX["draw"]
            tex, theme = item[1], item[2] if len(item) > 2 else None
            if draw is None:
                _LATEX_RUN["failed"] += 1
                return r"\texttt{%s}" % escape_latin(tex)
            r = draw(tex, theme, inline=True)
            if not r.get("ok"):
                _LATEX_RUN["failed"] += 1
                return r"\texttt{%s}" % escape_latin(tex)
            _LATEX_RUN["used"].append((r["key"], r["pdf"]))
            scale = print_size() / 10.0
            depth = (r.get("d") or 0) * scale
            return (r"\raisebox{-%.3fpt}{\includegraphics[scale=%.3f]{%s}}"
                    % (depth, scale, "latex/%s.pdf" % r["key"]))
        if item[0] == "seg":
            node = item[1]
            plain = node.plain_text
            if is_mono():
                return _fa_macro(plain, force_breakable)
            breakable = force_breakable or _CARD["on"] \
                or run_is_long(plain, print_size())
            shaped = _segmented_tex(node)
            return ("\\pel{%s}" if breakable else "\\pe{%s}") % shaped
        if item[0] == "rtl-seg":
            attrs = item[2]
            fnt = "\\tlalt" if attrs["font"] else "\\tlfont"
            fragment = target_fragment(item[1])
            if cur_lang().rtl:
                body = "{%s\\beginR %s\\endR}" % (fnt, fragment)
            else:
                body = "{%s %s}" % (fnt, fragment)
            if attrs["bg"]:
                body = "%s{%s}" % (panel("rtlbg" + attrs["bg"]), body)
            return body
        if item[0] == "rtl":
            attrs = item[2] if len(item) > 2 else parse_tl_attrs("")
            fnt = "\\tlalt" if attrs["font"] else "\\tlfont"
            if cur_lang().rtl:
                body = "{%s\\beginR %s\\endR}" % (fnt, rtl_fragment(item[1]))
            else:
                body = "{%s %s}" % (fnt, ltr_fragment(item[1]))
            if attrs["bg"]:
                body = "%s{%s}" % (panel("rtlbg" + attrs["bg"]), body)
            return body
        if item[0] == "url":
            return r"\url{%s}" % escape_url(item[1])
        if item[0] == "tex":
            return item[1]
        return ""
    text = re.sub(r"\x05(\d+)\x05", _lone, text)

    # 7. cosmetics: grey `=` in glosses  (فارسی = translation), also when
    #    the run is wrapped in any number of closing braces — a colour
    #    mark, bold, or (translit) both stacked: \textbf{\textcolor{..}{
    #    \pe{..}}} still needs the "=" greyed right after its \pe{...}.
    text = re.sub(r"(\\pe[lb]?\{[^{}]*\}\}*) = ", r"\1 \\eqgl\\ ", text)
    return text


def _is_pure_fa_paragraph(text):
    """A paragraph consisting only of the target script (plus spaces) ->
    display line.  Never for a Latin-script target."""
    L = cur_lang()
    if not L.chars:
        return False
    stripped = re.sub("[%s ]" % L.chars, "", text)
    return stripped == "" and len(L.re_chars.findall(text)) >= 3


# ----------------------------------------------------------------------
# block renderers
# ----------------------------------------------------------------------

def _render_table(b):
    prev = _begin_defer()      # \footnote is inert inside tabular
    ncols = len(b["header"])
    size = "\\footnotesize" if ncols >= 6 else ("\\small" if ncols >= 4 else "")
    # pad: a separator row with fewer columns than the header would
    # otherwise yield a colspec narrower than the emitted cells, and
    # xelatex dies with "Extra alignment tab" (halt-on-error -> no PDF).
    colspec = "@{}" + " ".join((b["align"] + ["l"] * ncols)[:ncols]) + "@{}"
    # in large print a table too wide for the line is scaled to it (_FIT_TEX),
    # and on a flashcard at every size: half a card is narrow, and a table
    # must not cross the line the card is folded on
    fit = print_size() != DEFAULT_PRINT_SIZE or _CARD["on"]
    out = ["\\begin{center}", size,
           "\\setlength{\\tabcolsep}{5pt}",
           "\\renewcommand{\\arraystretch}{1.45}",
           ("\\exlexfit{" if fit else "") + "\\begin{tabular}{%s}" % colspec,
           "\\toprule"]
    out.append(" & ".join("\\textbf{%s}" % inline(c) for c in b["header"]) + "\\\\")
    out.append("\\midrule")
    for row in b["rows"]:
        row = (row + [""] * ncols)[:ncols]
        cells = []
        for c in row:
            cells.append("---" if c in {"—", "--", "-"} else inline(c))
        out.append(" & ".join(cells) + "\\\\")
    out += ["\\bottomrule", "\\end{tabular}" + ("}" if fit else ""), "\\end{center}"]
    return "\n".join(x for x in out if x) + _end_defer(prev)


def _render_list(b, ordered):
    labelled = all(re.match(r"^\*\*.+?\*\*", it[1]) for it in b["items"]) \
        and not ordered and len(b["items"]) > 1
    if labelled:
        # description list; long / target-script labels -> `lex` (label on
        # its own line), short Latin labels -> inline description.
        env = "description"
        for _, it in b["items"]:
            lab = re.match(r"^\*\*(.+?)\*\*", it).group(1)
            if has_script(lab) and len(lab) > 10:
                env = "lex"
                break
        out = ["\\begin{%s}" % env]
        for _, it in b["items"]:
            m = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", it, re.S)
            out.append("\\item[%s] %s" % (inline(m.group(1)), inline(m.group(2))))
        out.append("\\end{%s}" % env)
        return "\n".join(out)

    env = "enumerate" if ordered else "itemize"
    out, depth = ["\\begin{%s}" % env], 0
    base = min(ind for ind, _ in b["items"])
    for ind, it in b["items"]:
        want = 1 if ind > base else 0
        while depth < want:
            out.append("\\begin{itemize}"); depth += 1
        while depth > want:
            out.append("\\end{itemize}"); depth -= 1
        out.append("\\item %s" % inline(it))
    while depth > 0:
        out.append("\\end{itemize}"); depth -= 1
    out.append("\\end{%s}" % env)
    return "\n".join(out)


def image_indent(b):
    """Left indent as a fraction of the column, from align + offset.

    Shared with htmlgen so screen and paper agree: left -> 0,
    center -> (1-w)/2, right -> 1-w, then the offset (in percentage
    points of the column width) shifts the result either way.
    """
    w = b["width"] / 100.0
    base = {"left": 0.0, "center": (1 - w) / 2, "right": 1 - w}[b["align"]]
    ml = base + b["offset"] / 100.0
    return max(-0.25, min(ml, 1.25))


def _ex_image(fields, key):
    """An exercise's own picture, inside its box: `image` with the question.
    `image-answer` is not printed -- the printed exercise is the unsolved
    one, and nothing else of the answer is on the page either."""
    import mdparser                  # exlex's parser imports this module
    pic = mdparser.exercise_image(fields.get(key, ""))
    if not pic:
        return ""
    path = pic["path"]
    if path.lower().endswith(".svg"):
        path += ".pdf"               # XeLaTeX reads the build's twin
    w = pic["width"] / 100.0
    # the same indent the screen's margin gives it (image_indent, without an
    # offset: a picture in an exercise's box has no room to be nudged)
    ml = {"left": 0.0, "center": (1 - w) / 2, "right": 1 - w}[pic["align"]]
    return ("\\par\\smallskip\\noindent\\hspace*{%.3f\\linewidth}"
            "\\begin{minipage}{%.3f\\linewidth}"
            "\\includegraphics[width=\\linewidth,height=0.3\\textheight,"
            "keepaspectratio]{%s}"
            "\\end{minipage}\\par\\smallskip{}" % (ml, w, path))


def _ex_audio(fields, key):
    """An exercise's own recording, inside its box: `audio` with the
    question.  `audio-answer` is not printed, exactly as `image-answer` is
    not -- the printed exercise is the unsolved one.

    A recording cannot be played from paper (_render_audio), so what is
    printed is the same card: the file it is and the stretch of it, laid out
    in the share of the column and on the side the picture pair uses."""
    import mdparser                  # exlex's parser imports this module
    rec = mdparser.exercise_audio(fields.get(key, ""))
    if not rec:
        return ""
    w = rec["width"] / 100.0
    ml = {"left": 0.0, "center": (1 - w) / 2, "right": 1 - w}[rec["align"]]
    start, end = clip_window(rec["start"], rec["end"])
    return ("\\par\\smallskip\\noindent\\hspace*{%.3f\\linewidth}"
            "\\begin{minipage}{%.3f\\linewidth}"
            "%s{\\parbox{\\dimexpr\\linewidth-1.2em\\relax}"
            "{\\centering\\vspace{0.7ex}"
            "{\\Large\\color{accent}\\audioX}\\\\[0.4ex]"
            "{\\footnotesize\\color{graytx}audio · %s%s}"
            "\\vspace{0.7ex}}}"
            "\\end{minipage}\\par\\smallskip{}"
            % (ml, w, panel("boxbg"), escape_latin(rec["path"].split("/", 1)[1]),
               _clip_span(start, end, fmt_clip_time)))


def _render_image(b):
    if not b.get("valid"):
        return ""          # bad path: nothing to include
    w = b["width"] / 100.0
    ml = image_indent(b)
    path = b["path"]
    if path.lower().endswith(".svg"):
        # XeLaTeX cannot read SVG; the build converts each one to a
        # sibling PDF (see server.build_pdf) and we include that.
        path += ".pdf"
    cap = ("\\par\\vspace{0.4ex}{\\footnotesize\\color{graytx} %s\\par}"
           % inline(b["caption"]) if b["caption"] else "")
    return ("\\par\\medskip\\noindent"
            "\\hspace*{%.3f\\linewidth}"
            "\\begin{minipage}{%.3f\\linewidth}"
            "\\includegraphics[width=\\linewidth]{%s}"
            "%s\\end{minipage}\\par\\medskip"
            % (ml, w, path, cap))


def _render_video(b):
    """A video cannot live on paper: render a clickable play-card that
    opens the clip, positioned exactly like an image would be."""
    if not b.get("valid"):
        return ""
    w = b["width"] / 100.0
    ml = image_indent(b)
    url = "https://youtu.be/%s" % b["vid"]
    if b.get("start") is not None:
        # whole seconds, as YouTube takes them (fmt_time truncates too)
        url += "?t=%d" % int(b["start"])
    span = _clip_span(b.get("start"), b.get("end"))
    cap = ("{\\normalsize\\textbf{%s}}\\\\[0.3ex]" % inline(b["caption"])
           if b["caption"] else "")
    return ("\\par\\medskip\\noindent"
            "\\hspace*{%.3f\\linewidth}"
            "\\begin{minipage}{%.3f\\linewidth}"
            "\\href{%s}{%s{\\parbox{\\dimexpr\\linewidth-1.2em\\relax}"
            "{\\centering\\vspace{0.7ex}"
            "{\\Large\\color{accent}\\playX}\\\\[0.4ex]%s"
            "{\\footnotesize\\color{graytx}video YouTube%s}"
            "\\vspace{0.7ex}}}}"
            "\\end{minipage}\\par\\medskip"
            % (ml, w, url, panel("boxbg"), cap, span))


def fmt_clip_time(s):
    """Seconds -> `1:05`, or `1:05.25` when a recording's clip time carries
    a fraction (a video's never does: YouTube takes whole seconds)."""
    frac = round(s - int(s), 2)
    return fmt_time(s) + (("%.2f" % frac)[1:].rstrip("0") if frac else "")


def _clip_span(start, end, fmt=fmt_time):
    """` · 1:05–1:09`, ` · dal 1:05`, ` · fino a 1:09`, or nothing."""
    if start is not None and end is not None:
        return " · %s–%s" % (fmt(start), fmt(end))
    if start is not None:
        return " · dal %s" % fmt(start)
    if end is not None:
        return " · fino a %s" % fmt(end)
    return ""


def clip_window(start, end):
    """(start, end) of a clip, the one rule every writer and reader of one
    goes by (the page, the paper, the studio's layout editor): an end not
    after the start ends nothing -- nor, with no start (the clip starts at
    0), an end at 0, a clip that would never play."""
    if end is not None and end <= (start or 0):
        end = None
    return start, end


def audio_window(b):
    """(start, end) of a recording block's clip, as the page and the paper
    both draw it (clip_window)."""
    return clip_window(b.get("start"), b.get("end"))


def _render_audio(b):
    """A recording cannot be played from paper either: the same card as a
    video's, placed like an image, but no link -- the file stays in the
    studio, and the card says which one it is and which stretch of it."""
    if not b.get("valid"):
        return ""
    w = b["width"] / 100.0
    ml = image_indent(b)
    start, end = audio_window(b)
    name = b["path"].split("/", 1)[1]
    cap = ("{\\normalsize\\textbf{%s}}\\\\[0.3ex]" % inline(b["caption"])
           if b["caption"] else "")
    return ("\\par\\medskip\\noindent"
            "\\hspace*{%.3f\\linewidth}"
            "\\begin{minipage}{%.3f\\linewidth}"
            "%s{\\parbox{\\dimexpr\\linewidth-1.2em\\relax}"
            "{\\centering\\vspace{0.7ex}"
            "{\\Large\\color{accent}\\audioX}\\\\[0.4ex]%s"
            "{\\footnotesize\\color{graytx}audio · %s%s}"
            "\\vspace{0.7ex}}}"
            "\\end{minipage}\\par\\medskip"
            % (ml, w, panel("boxbg"), cap, escape_latin(name),
               _clip_span(start, end, fmt_clip_time)))


def _render_la_block(content, a):
    """A `[…]{la}` paragraph: aligned, optionally tinted, narrowed and
    shifted like an image."""
    aligncmd = {"left": "", "center": "\\centering ",
                "right": "\\raggedleft "}[a["align"]]
    w = a["width"] / 100.0
    ml = max(-0.25, min(a["offset"] / 100.0, 1.25))
    boxed = bool(a["bg"]) or a["width"] < 100 or a["offset"] != 0
    prev = _begin_defer() if boxed else None   # a minipage eats \footnote
    inner = inline(content)
    if not boxed:
        if aligncmd:
            return "\\par\\medskip{%s%s\\par}\\medskip" % (aligncmd, inner)
        return inner + "\n"
    if a["bg"]:
        core = ("%s{\\begin{minipage}"
                "{\\dimexpr%.3f\\linewidth-1.6em\\relax}"
                "\\vspace{0.6ex}%s%s\\par\\vspace{0.6ex}\\end{minipage}}"
                % (panel("rtlbg" + a["bg"]), w, aligncmd, inner))
    else:
        core = ("\\begin{minipage}{%.3f\\linewidth}%s%s\\par\\end{minipage}"
                % (w, aligncmd, inner))
    return ("\\par\\medskip\\noindent\\hspace*{%.3f\\linewidth}%s"
            "\\par\\medskip%s" % (ml, core, _end_defer(prev)))


def _render_tl_block(content, attrs):
    """A whole-paragraph target-language block: prose in the target
    language's direction and font, optionally in the alternate face, on a
    tint, or (vertical languages) set as rotated columns."""
    L = cur_lang()
    if attrs["vertical"]:
        # the tint is dropped on paper: a \colorbox around a rotated box
        # of columns would paint a page-high slab
        return "\\tlvertical{%d}{%s}" % (attrs["height"], target_fragment(content))
    if L.rtl:
        fnt = ("\\tlalt\\linespread{1.8}\\selectfont" if attrs["font"] else "")
        if attrs["bg"]:
            return ("\\par\\medskip\\noindent"
                    "%s{\\begin{minipage}"
                    "{\\dimexpr\\linewidth-1.6em\\relax}"
                    "\\vspace{0.6ex}{\\tlfont%s\\raggedleft\\leavevmode"
                    "\\beginR %s\\endR\\par}\\vspace{0.6ex}"
                    "\\end{minipage}}\\par\\medskip"
                    % (panel("rtlbg" + attrs["bg"]), fnt, target_fragment(content)))
        # the space ends \\selectfont: the first word was read into its name
        return "\\begin{fapar}%s%s\\end{fapar}" % (fnt and fnt + " ", target_fragment(content))
    fnt = "\\tlalt" if attrs["font"] else ""
    if attrs["bg"]:
        return ("\\par\\medskip\\noindent"
                "%s{\\begin{minipage}"
                "{\\dimexpr\\linewidth-1.6em\\relax}"
                "\\vspace{0.6ex}{\\tlfont%s\\raggedright\\leavevmode "
                "%s\\par}\\vspace{0.6ex}"
                "\\end{minipage}}\\par\\medskip"
                % (panel("rtlbg" + attrs["bg"]), fnt, target_fragment(content)))
    return "\\begin{fapar}%s %s\\end{fapar}" % (fnt, target_fragment(content))


def _render_box(b):
    prev = _begin_defer()      # a minipage would swallow the footnote
    inner = render_blocks(b["blocks"], inside_box=True)
    return ("\\begin{center}\n"
            + panel("boxbg") + "{\\begin{minipage}{0.93\\linewidth}"
            "\\vspace{0.8ex}\\raggedright\n"
            f"{inner}\n"
            "\\vspace{0.8ex}\\end{minipage}}\n\\end{center}") + _end_defer(prev)


_EX_TEX_LABELS = {
    "fill-blanks": "Fill the blanks", "flashcard": "Flashcard",
    "order-sentences": "Order the sentences", "match-translations": "Match translations",
    "match-opposites": "Match opposites", "match-definitions": "Match definitions",
    "yes-no": "Yes / No", "true-false": "True / False",
    "single-choice": "Choose one answer", "construct-sentence": "Construct the sentence",
    "incorrect-part": "Identify the incorrect part", "choose-all": "Choose all correct answers",
    "odd-one-out": "Odd one out", "follow-up": "Follow-up questions",
}


# set while a flashcard's own blocks are rendered: a heading there is a
# label on the card, never a numbered section of the document
_CARD = ThreadDict(on=False)

# A FLASHCARD ON PAPER IS A CARD TO CUT OUT AND FOLD (\expapercard, in
# CARD_PAPER): its front in the left half of a frame, its back in the right,
# each side drawn as the page's card draws it (htmlgen._render_exercise_
# flashcard) -- the picture, the recording, then the fields one under
# another in the middle of the half, at their sizes and in their shades,
# the main ones bold.  The fields a card's kind shows, and which of them are
# secondary (88 per cent and grey, where the main ones are 120 and ink):
_CARD_SECONDARY = ("front-secondary", "back-secondary", "reading", "transliteration",
                   "context", "notes", "source", "opposite-reading",
                   "opposite-transliteration")


def _card_look(f, key, rich=False):
    """A field's size and colour on paper, read exactly as the page's card
    reads them (htmlgen._card_style): (per cent of the text round the card,
    the TeX that sets its colour, or nothing for the ink).  A field of
    blocks is at the page's size unless a size is written for it.  In black
    and white every shade is the ink."""
    secondary = key in _CARD_SECONDARY
    default = 88 if secondary else 120
    try:
        size = max(50, min(250, int(f.get(key + "-size", default) or default)))
    except ValueError:
        size = default
    if rich and size == default:
        size = 100
    if is_mono():
        return size, ""
    shade = (f.get(key + "-shade") or ("subdued" if secondary else "primary")).lower()
    colour = {"subdued": "\\color{graytx}", "muted": "\\color{graytx!72}",
              "accent": "\\color{accent}"}.get(shade, "")
    if not colour and re.fullmatch(r"#[0-9a-f]{6}", shade):
        colour = "\\color[HTML]{%s}" % shade[1:].upper()
    return size, colour


def _card_line(f, key, text, primary=False):
    """A field of one paragraph -- a line, or several (⏎) -- in the middle of
    its half.  Fitted to the half (\\exlexfitpar): nothing on a card crosses
    the line it is folded on, at any print size."""
    if not text:
        return ""
    size, colour = _card_look(f, key)
    return ("\\exlexfitpar{\\linewidth}{\\expapercardsize{%d}\\centering"
            "\\let\\newline\\expapercardcr\\hspace{0pt}{%s%s %s}}"
            % (size, colour, "\\bfseries" if primary else "",
               _ex_inline(text, force_breakable=True)))


def _card_blocks(f, key, blocks, primary=False):
    """A Jolly field that is blocks, drawn as the page draws them (a heading
    a label on the card, _CARD).  Several of them -- a table, a list, a box,
    a figure -- are laid out from the start of the line at the page's
    weight, as the page's card lays them out.  One paragraph of the page's
    own kind is the card's own line still: a target-language block in the
    middle of the half, as the screen puts it, and a line of nothing but the
    target script without the indent and the size it has on a page."""
    import mdparser     # exlex's parser imports this module: not at the top
    rich = mdparser.card_field_is_rich(blocks)
    size, colour = _card_look(f, key, rich)
    was, _CARD["on"] = _CARD["on"], True
    try:
        txt = "" if rich else blocks[0]["text"].strip()
        if rich or LA_RE.fullmatch(txt):
            inner = render_blocks(blocks, inside_box=True)
        elif _is_pure_fa_paragraph(txt):
            inner = "\\pel{%s}" % txt
        else:
            inner = render_blocks(blocks, inside_box=True)
            if inner:
                inner = ("\\let\\raggedleft\\centering\\let\\raggedright\\centering"
                         "\\let\\newline\\expapercardcr " + inner)
    finally:
        _CARD["on"] = was
    if not inner:
        return ""
    if rich:
        return "{\\raggedright\\expapercardsize{%d}%s %s\\par}" % (size, colour, inner)
    return "{\\expapercardsize{%d}%s%s %s\\par}" % (
        size, colour, "\\bfseries" if primary else "", inner)


def _card_jolly(f, key, field, primary=False):
    """A Jolly field (mdparser.card_field, read the same for both
    renderers), or nothing when it is empty."""
    if field is None:
        return ""
    how, content, _notes = field
    if how == "inline":
        return _card_line(f, key, content, primary)
    return _card_blocks(f, key, content, primary)


def _card_picture(f, key):
    """`front-image: images/cat.png`: the picture, never larger than it is,
    nor wider than its half or taller than the page's card lets it be
    (\\expapercardpic).  An SVG is read through the build's .svg.pdf twin."""
    import mdparser
    path = f.get(key, "")
    if not path or not mdparser.IMAGE_PATH_RE.match(path):
        return ""
    if path.lower().endswith(".svg"):
        path += ".pdf"
    return "\\expapercardpic{%s}" % path


def _card_audio(f, key):
    """`front-audio: audio/word.mp3`: a recording cannot be played from
    paper, so the side says it has one -- ♪ and its file's name, as a
    recording's card does."""
    import mdparser
    path = f.get(key, "")
    if not path or not mdparser.AUDIO_PATH_RE.match(path):
        return ""
    return ("{\\footnotesize{\\color{accent}\\audioX}~{\\color{graytx}%s}\\par}"
            % escape_latin(path.split("/", 1)[1]))


def _card_sides(f, kind, cards):
    """(front, back) of a card on paper: the pieces of each side, the
    picture, the recording, then the fields, as the page shows them --
    turned round by `direction: reverse`, since the left half is the side
    the card shows first.  The example, the notes and the source go where
    mdparser.card_extras puts them: on paper a `both-random` card is the
    front first, so they stay on the back unless a `-side` says otherwise."""
    import mdparser     # exlex's parser imports this module: not at the top
    if kind == "jolly":
        front = [_card_jolly(f, "front-primary", cards.get("front-primary"), True),
                 _card_jolly(f, "front-secondary", cards.get("front-secondary"))]
        back = [_card_jolly(f, "back-primary", cards.get("back-primary"), True),
                _card_jolly(f, "back-secondary", cards.get("back-secondary"))]
    else:
        line = lambda key, primary=False: _card_line(f, key, f.get(key, ""), primary)
        word, meaning = mdparser.card_extras(f)
        if kind == "opposites":
            front = [line("target", True), line("reading"), line("transliteration")]
            back = [line("opposite", True), line("opposite-reading"),
                    line("opposite-transliteration")]
        else:
            front = ([line("front", True)] if f.get("front") else
                     [line("target", True), line("reading"), line("transliteration")])
            back = [line("back", True)] if f.get("back") else [line("meaning", True)]
        front += [line(key) for key in word]
        back += [line(key) for key in meaning]
        front = [_card_picture(f, "front-image"), _card_audio(f, "front-audio")] + front
        back = [_card_picture(f, "back-image"), _card_audio(f, "back-audio")] + back
    if (f.get("direction") or "forward").lower() == "reverse":
        front, back = back, front
    side = lambda parts: "\\expapercardgap\n".join(p for p in parts if p)
    return side(front), side(back)


# A BLANK IS DRAWN OVER THE SET SENTENCE, and a formula is part of that
# sentence by the time it is drawn.  SLOT_RE looks for `[[name]]`, and a
# formula may hold a doubled bracket of its own (`\big[[`, a bracket
# straight after one) which is not a blank and must not become a rule.  So
# the rule is written everywhere EXCEPT inside `\( ... \)`.
#
# A blank cannot sit inside a formula, and nothing here pretends it could:
# spread_slots spreads a target-language mark over the pieces a blank cuts
# it into, but a formula cut in half is two halves of nothing.
_MATH_SPAN_RE = re.compile(r"\\\((?:[^\\]|\\(?!\)))*\\\)")


# NOT EVERY CHARACTER MAY END OR BEGIN A LINE.  A line of Chinese or
# Japanese never begins with a mark that closes what went before (。，、？！
# ）」”, the small kana, ー, 々) nor ends with one that opens what follows
# (（「“) or a currency sign before its amount (kinsoku); XeTeX's line
# breaking keeps to it between two characters, and so must a break written
# beside a blank.  The unicode category says which: closing, final and other
# punctuation and the modifier letters may not begin a line, opening and
# initial punctuation and currency signs may not end one.
def _may_not_begin_line(c):
    return bool(c) and (
        unicodedata.category(c) in ("Pe", "Pf", "Po", "Lm")
        or unicodedata.name(c, "").startswith(("HIRAGANA LETTER SMALL", "KATAKANA LETTER SMALL")))


def _may_not_end_line(c):
    return bool(c) and unicodedata.category(c) in ("Ps", "Pi", "Sc")


_TEX_WORD_RE = re.compile(r"\\[A-Za-z@]+\*?")


def _beside(text, at, step):
    """The character printed next to a blank: text[at], or past the LaTeX
    _ex_inline wrapped the sentence in, the next one in the direction of
    `step` (1 after the blank, -1 before it).  Braces and the name of a
    command (`\\pe{`, `\\textbf{`) are passed over, an escaped character
    (`\\%`) is that character, and any other command, or the end of the
    text, is nothing."""
    while 0 <= at < len(text):
        c = text[at]
        if c in "{}":
            at += step
            continue
        if step > 0 and c == "\\":
            word = _TEX_WORD_RE.match(text, at)
            if word:
                at = word.end()
                continue
            nxt = text[at + 1:at + 2]
            return nxt if nxt in ("%", "&", "#", "$", "_") else ""
        if step < 0 and c.isascii() and c.isalpha():
            first = at
            while first > 0 and text[first - 1].isascii() and text[first - 1].isalpha():
                first -= 1
            if first > 0 and text[first - 1] == "\\":
                at = first - 2
                continue
        return c
    return ""


def _slots_outside_math(line):
    out, at = [], 0
    rule = blank_rule()

    def blank(m):
        # A language written without spaces (Chinese, Japanese) breaks a
        # line between any two characters, and a blank is one more: without
        # a space beside it, nothing let a line end there, and a sentence
        # of short runs (each one box) and blanks was one unbreakable line.
        # A blank beside a space already has its break; a blank inside a
        # word of a spaced language is part of the word.  No break goes
        # between the blank and a mark after it that may not begin a line,
        # or one before it that may not end a line: "对吗[[3]]？" set the ？
        # alone at the head of a line, at every size.  The line ends on the
        # blank's other side instead.
        if cur_lang().spaced:
            return rule
        text = m.string
        before = (m.start() > 0 and not text[m.start() - 1].isspace()
                  and not _may_not_end_line(_beside(text, m.start() - 1, -1)))
        after = (m.end() < len(text) and not text[m.end()].isspace()
                 and not _may_not_begin_line(_beside(text, m.end(), 1)))
        return (("\\allowbreak" if before else "") + rule
                + ("\\allowbreak " if after else ""))
    for m in _MATH_SPAN_RE.finditer(line):
        out.append(SLOT_RE.sub(blank, line[at:m.start()]))
        out.append(m.group(0))
        at = m.end()
    out.append(SLOT_RE.sub(blank, line[at:]))
    return "".join(out)


_EX_INLINE_IMAGE_RE = re.compile(r"!\[[^\[\]]*\]\(\s*[^()\s]+\s*\)(?:\{[^{}]*\})?")


def _ex_inline(text, force_breakable=False):
    """Print pictures wherever exercise prose can appear."""
    import mdparser     # exlex's parser imports this module: not at the top
    out, end = [], 0
    for found in _EX_INLINE_IMAGE_RE.finditer(text):
        out.append(inline(text[end:found.start()], force_breakable))
        image = mdparser.IMAGE_RE.fullmatch(found.group(0))
        path = image.group(2) if image else ""
        if mdparser.IMAGE_PATH_RE.fullmatch(path):
            if path.lower().endswith(".svg"):
                path += ".pdf"
            width = mdparser.parse_image_attrs(image.group(3))["width"] / 100
            out.append("\\includegraphics[width=%.2f\\linewidth,height=0.12\\textheight,"
                       "keepaspectratio]{%s}" % (width, path))
        else:
            out.append(inline(found.group(0), force_breakable))
        end = found.end()
    out.append(inline(text[end:], force_breakable))
    return "".join(out)


def prompt_lines(source):
    """Split a prompt into lines and optional regular-weight spans.

    A ``[...]{no-bold}`` span may contain another inline mark, such as
    ``[فارسی]{tl}``, so a flat bracket regex would stop at the inner mark.
    Explicit ⏎ breaks inside a target-language mark stay inside that run;
    breaks outside it start another prompt line.
    """
    source = str(source or "")
    spans = []
    start = i = 0
    marker = "{no-bold}"
    while i < len(source):
        if source[i] == "[":
            depth, end = 1, i + 1
            while end < len(source) and depth:
                if source[end] == "[":
                    depth += 1
                elif source[end] == "]":
                    depth -= 1
                end += 1
            if depth == 0 and source.startswith(marker, end):
                if i > start:
                    spans.append((source[start:i], False))
                spans.append((source[i + 1:end - 1], True))
                i = start = end + len(marker)
                continue
        i += 1
    if start < len(source):
        spans.append((source[start:], False))

    lines = [[]]
    for span, regular in spans:
        at = 0
        # Keep explicit breaks inside any opaque inline mark inside that
        # mark, just as inline() does. Only breaks around marks split lines.
        marks = [(m.start(), m.end(), m.group(0))
                 for rx in (tl_re(), LA_RE, MATH_RE, COLOR_RE, TRANSLIT_RE)
                 for m in rx.finditer(span)]
        marks.extend((m.start, m.end, span[m.start:m.end])
                     for m in target_marks(span))
        marks.extend((m.start, m.end, span[m.start:m.end])
                     for m in segmented_runs(span))
        for mark_start, mark_end, raw in sorted(set(marks), key=lambda m: (m[0], -m[1])):
            if mark_start < at:
                continue
            for n, piece in enumerate(span[at:mark_start].split("⏎")):
                if n:
                    lines.append([])
                if piece:
                    lines[-1].append((piece, regular))
            lines[-1].append((raw, regular))
            at = mark_end
        for n, piece in enumerate(span[at:].split("⏎")):
            if n:
                lines.append([])
            if piece:
                lines[-1].append((piece, regular))
    for line in lines:
        while line:
            first, regular = line[0]
            first = first.lstrip()
            if first:
                line[0] = (first, regular)
                break
            line.pop(0)
        while line:
            last, regular = line[-1]
            last = last.rstrip()
            if last:
                line[-1] = (last, regular)
                break
            line.pop()
    return lines


# ----------------------------------------------------------------------
# exercises on paper: the macros of the layouts that are measured by TeX
# ----------------------------------------------------------------------
# Written into the preamble (%%EXERCISEPAPER%%) only when the body uses
# one, so a document without these exercises is set exactly as before.
# Everything is measured where it is set -- in the exercise's own box, at
# its own size, in the fonts it is printed in -- which is the one way the
# same rule holds at 11 pt and at 20 pt, in Persian and in Japanese.  The
# frames are graytx, a dark grey near black, on white: the document's
# chrome, and black in black and white.
EXERCISE_PAPER = r"""% ----------------------- EXERCISES ON PAPER ----------------------
% An exercise is set in a box, and the box goes to the next page whole when
% it does not fit on this one -- but a box taller than the page is cut off
% at its foot, words and all: at 20 pt a reading passage and its questions,
% at 11 pt a matching exercise of ten pictures, each in its frame.  Such an
% exercise starts a page and goes on over as many as it needs, in one frame
% a page: the box is split between two of its lines.  One that fits a page
% is framed as it always was, in a minipage, and these are the lines that
% minipage would have set: the same box, in the same place.
%
% Straight after a heading it is not free to start a page: nothing may
% part a heading from what follows it, so the heading went with it.  A new
% page before it left the heading alone at the foot of the one before; and
% a box that fits a page, but not with the heading above it, ran off the
% foot of the page they went to together.  After a heading, an exercise
% that does not fit what is left of the page, and that a page might not
% hold together with its heading (five lines are left for one), starts
% right under the heading, in a piece as tall as the page has room for;
% when the page has room for less than three lines, the heading goes over
% with a first piece that leaves it those five lines.  A box inside
% another (a quotation) is never split: there is no page to measure.
\newbox\expaperexbox
\newbox\expaperexpiece
\def\expaperexframe{rulec}
\def\expaperexfill{boxbg}
\newlength\expaperexfits
\newlength\expaperexwidth
\newlength\expaperexto
\newlength\expaperexroom
\newif\ifexpaperexhead
\makeatletter
\newcommand\expaperexercise[1]{%
  \par
  \if@nobreak\expaperexheadtrue\else\expaperexheadfalse\fi
  \setlength\expaperexwidth{\dimexpr\linewidth-1.6em\relax}%
  \setbox\expaperexbox\vbox{\color@begingroup
    \hsize\expaperexwidth\textwidth\hsize\columnwidth\hsize
    \@parboxrestore\let\@listdepth\@mplistdepth\@mplistdepth\z@
    \@setminipage#1\par\color@endgroup}%
  % a box that fits the page's text, frame and all, is never split; the
  % pieces of one that does not are a line shorter than that page
  \setlength\expaperexfits{\dimexpr\textheight-2\fboxsep-2\fboxrule-\baselineskip\relax}%
  \setlength\expaperexto{\maxdimen}% the first piece's height: none, not split
  \ifinner\else
    \ifdim\dimexpr\ht\expaperexbox+\dp\expaperexbox\relax>\dimexpr\expaperexfits+\baselineskip\relax
      \setlength\expaperexto{\expaperexfits}%
    \fi
    \ifexpaperexhead
      \ifdim\pagegoal<\maxdimen
        \setlength\expaperexroom{\dimexpr\pagegoal-\pagetotal-\pagedepth
          -2\fboxsep-2\fboxrule-\baselineskip\relax}%
      \else
        \setlength\expaperexroom{\expaperexfits}%
      \fi
      \ifdim\dimexpr\ht\expaperexbox+\dp\expaperexbox\relax>\expaperexroom
        \ifdim\dimexpr\ht\expaperexbox+\dp\expaperexbox\relax>\dimexpr\expaperexfits-5\baselineskip\relax
          \ifdim\expaperexroom<3\baselineskip
            \setlength\expaperexto{\dimexpr\expaperexfits-5\baselineskip\relax}%
          \else
            \setlength\expaperexto{\expaperexroom}%
          \fi
        \fi
      \fi
    \fi
  \fi
  \ifdim\expaperexto<\maxdimen
    \ifexpaperexhead\else\newpage\fi
    % the depth of a piece's last line (a statement's column hangs from its
    % first) counts as height, or a piece would be taller than its page; and
    % every piece is as wide as the exercise -- one holding nothing but the
    % writing lines would otherwise be as wide as they are, which is nothing
    % (a rule takes the width of the box it is in).  A piece is packed again
    % at its natural height, so the last one is no taller than what it
    % holds; but \vsplit may have fitted a piece to the page only by
    % shrinking its glue, and packed at its natural height it would be
    % taller than the page again and run over the page number: that piece
    % is packed to the page's height, shrunk as \vsplit had it.  Every
    % piece after the first is as tall as a page.
    \begingroup\splitmaxdepth\z@
    \loop
      \setbox\expaperexpiece\vsplit\expaperexbox to \expaperexto
      \setbox\expaperexpiece\vbox{\unvbox\expaperexpiece\boxmaxdepth\z@}%
      \ifdim\ht\expaperexpiece>\expaperexto
        \setbox\expaperexpiece\vbox to\expaperexto{\unvbox\expaperexpiece\boxmaxdepth\z@}%
      \fi
      \wd\expaperexpiece\expaperexwidth
      \noindent\fcolorbox{\expaperexframe}{\expaperexfill}{\box\expaperexpiece}\par
      \setlength\expaperexto{\expaperexfits}%
    \ifvoid\expaperexbox\else\repeat
    \endgroup
  \else
    \noindent\fcolorbox{\expaperexframe}{\expaperexfill}{\begin{minipage}{\expaperexwidth}%
      \unvbox\expaperexbox\end{minipage}}\par
  \fi}
\makeatother
% A STEP OF A FOLLOW-UP is an exercise's box one fence lighter: the same breaking rules (it keeps together, or goes on
% over the pages a tall one needs), on white, in a thinner line, so that the inner frames do not fight the chain's
% own head above them.
\newcommand\expaperstep[1]{%
  \begingroup\def\expaperexframe{rulec}\def\expaperexfill{white}%
  \setlength\fboxrule{0.75\fboxrule}\expaperexercise{#1}\endgroup}
%
% Matching: each entry of each column in a frame of its own, the columns
% equal in width with a gap between them for the line the student draws.
% Both frames of a row are as tall as the taller entry and level with it
% (its first baseline), so a row reads as one row.  An entry never crosses
% its frame (\exlexfitpar).
\newlength\expapercol
\newlength\expaperht
\newlength\expaperdp
\newsavebox\expaperleft
\newsavebox\expaperright
\newcommand\expapercell[1]{%
  \exlexfitpar{\dimexpr\expapercol-2\fboxsep-2\fboxrule\relax}{#1}}
\newcommand\expaperframe[1]{%
  \fcolorbox{graytx}{white}{\raisebox{0pt}[\expaperht][\expaperdp]{\usebox#1}}}
\newcommand\expaperpair[2]{%
  \setlength\expapercol{\dimexpr(\linewidth-0.14\linewidth)/2\relax}%
  \sbox\expaperleft{\expapercell{#1}}\sbox\expaperright{\expapercell{#2}}%
  \setlength\expaperht{\ht\strutbox}\setlength\expaperdp{\dp\strutbox}%
  \ifdim\ht\expaperleft>\expaperht \setlength\expaperht{\ht\expaperleft}\fi
  \ifdim\ht\expaperright>\expaperht \setlength\expaperht{\ht\expaperright}\fi
  \ifdim\dp\expaperleft>\expaperdp \setlength\expaperdp{\dp\expaperleft}\fi
  \ifdim\dp\expaperright>\expaperdp \setlength\expaperdp{\dp\expaperright}\fi
  \par\noindent\expaperframe\expaperleft\hfill\expaperframe\expaperright\par
  \vspace{1ex}}
%
% Construct the sentence: the chunks in a row, each in a frame, and under
% them the lines the sentence is written on -- as many as one and a half
% times the chunks' width set end to end with a space between each (W)
% fills in lines as wide as the box (L), rounded up: N = ceil(3W / 2L).
% W is added up chunk by chunk as each is set, so every chunk is written
% into the .tex once.  \numexpr rounds its division, so a quotient that
% came out short is raised by one; the widths are counted in units of
% 16sp, which keeps 3W far inside TeX's integers.
\newlength\expapersentence
\newcount\expaperchunkcount
\newcount\expaperlinecount
\newsavebox\expaperchunkbox
\newcommand\expaperchunks[1]{% r or l: the side a line of chunks starts at
  \global\expapersentence=0pt \global\expaperchunkcount=0
  \if#1r\def\expaperchunkalign{\raggedleft}\else\def\expaperchunkalign{\raggedright}\fi}
% A row set right to left is reversed by TeX when it is shipped out, and
% XeTeX reverses what the boxes in it hold as well: the words of a Latin
% chunk come out backwards, and the colour a frame pushes is popped before
% it is pushed, which paints the chunk solid.  So each framed chunk is one
% left-to-right segment inside the row; a chunk of right-to-left text
% carries its own \beginR, and that, the innermost, is what it is set by.
\newcommand\expaperchunk[1]{%
  \sbox\expaperchunkbox{\strut#1}% (the strut: every frame of the row alike)
  \ifnum\expaperchunkcount>0 \global\advance\expapersentence\fontdimen2\font\fi
  \global\advance\expapersentence\wd\expaperchunkbox
  \global\advance\expaperchunkcount 1
  \mbox{\beginL\ifdim\wd\expaperchunkbox>\dimexpr\linewidth-2\fboxsep-2\fboxrule\relax
    \fcolorbox{graytx}{white}{\exlexfitpar{\dimexpr\linewidth-2\fboxsep-2\fboxrule\relax}%
      {\expaperchunkalign\noindent\hspace{0pt}#1}}%
  \else
    \fcolorbox{graytx}{white}{\usebox\expaperchunkbox}%
  \fi\endL}}
\newcommand\expaperchunkgap{\hspace{0.6em plus 0.3em}}
\newcommand\expaperwritelines{%
  \par
  \global\expaperlinecount=\numexpr(3*(\expapersentence/16))/(2*(\linewidth/16))\relax
  \ifnum\numexpr\expaperlinecount*2*(\linewidth/16)\relax<\numexpr3*(\expapersentence/16)\relax
    \global\advance\expaperlinecount 1 \fi
  \ifnum\expaperlinecount<1 \global\expaperlinecount=1 \fi
  \typeout{exlex construct-sentence: W=\the\expapersentence\space
    L=\the\linewidth\space lines=\the\expaperlinecount}%
  % a line every 1.8 lines of the exercise's own text: 8.6 mm at the normal
  % size, and as much more as the print is larger
  \loop\ifnum\expaperlinecount>0
    \vskip 1.8\baselineskip
    {\color{graytx}\hrule height %%RULE%%}%
    \global\advance\expaperlinecount -1
  \repeat
  \vskip 0.6ex}
%
% True / False, Yes / No: the statement in a column of its own, which it
% wraps inside, and the marks in a column at the right that nothing else
% is ever set in -- one box, so they never part -- level with the
% statement's first line and at the same place on every row.  The
% statement never runs under them (\exlexfitpar).
\newlength\expapermarks
\newcommand\expaperboolmarks[1]{%
  \settowidth\expapermarks{#1}\addtolength\expapermarks{1.5em}}
\newcommand\expaperbool[2]{%
  \par\noindent\exlexfitpar{\dimexpr\linewidth-\expapermarks\relax}{#1}%
  \makebox[\expapermarks][r]{#2}\par\vspace{1.2ex}}"""


CARD_PAPER = r"""% ----------------------- FLASHCARDS ON PAPER ----------------------
% A flashcard is printed as a card to cut out and fold: a frame with round
% corners -- the scissors on it say it is cut along -- its front in the left
% half and its back in the right, and a dashed line exactly between them to
% fold it on.  Folded, the two halves are back to back, a card in the hand,
% both faces the right way up.  Each half holds its side as the page's card
% draws it, in the middle of the half (texgen._card_sides); the card is as
% tall as its taller side, and never less than three fifths of a half's
% width, the shape of an index card.  The label and the prompt stand above
% the frame and never part from it, and a card is never split between two
% pages, which could not be folded: one taller than a page is made smaller,
% until it fits one.
%
% The frame is drawn by TikZ; a TeX without it (no pgf) draws a square one.
\IfFileExists{tikz.sty}{\usepackage{tikz}}{}
\newlength\expapercardwd
\newlength\expapercardhalf
\newlength\expapercardht
\newlength\expapercardpad
\newlength\expapercardfs
\newlength\expapercardroom
\newlength\expapercardrule
\setlength\expapercardrule{%%CARDRULE%%}
\newsavebox\expapercardfront
\newsavebox\expapercardback
\newsavebox\expapercardpicbox
\newbox\expapercardbox
\ifdefined\symfont\newcommand\expapercutX{{\symfont ✂}}\else\newcommand\expapercutX{}\fi
\makeatletter
% a field's size, #1 per cent of the text round the card
\newcommand\expapercardsize[1]{%
  \setlength\expapercardfs{\dimexpr\f@size pt*#1/100\relax}%
  \fontsize{\expapercardfs}{1.25\expapercardfs}\selectfont}
\newcommand\expapercardgap{\par\vskip.35em\relax}
% a line break (⏎) in the middle of a half: the \hfil a \newline ends its
% line with would push the line off the middle
\newcommand\expapercardcr{\unskip\break}
% a card's picture: its own size, or smaller to fit its half and 8em in
% height -- never larger; a file the build does not have is named instead
\newcommand\expapercardpic[1]{%
  \IfFileExists{#1}{%
    \sbox\expapercardpicbox{\includegraphics{#1}}%
    \ifdim\wd\expapercardpicbox>\linewidth
      \sbox\expapercardpicbox{\includegraphics[width=\linewidth,height=8em,keepaspectratio]{#1}}%
    \else\ifdim\ht\expapercardpicbox>8em
      \sbox\expapercardpicbox{\includegraphics[width=\linewidth,height=8em,keepaspectratio]{#1}}%
    \fi\fi
    \usebox\expapercardpicbox}%
   {{\footnotesize\color{graytx}\detokenize{#1}}}\par}
% one side, set in its half less the card's padding, each paragraph centred
\newcommand\expapercardside[2]{%
  \sbox#1{\begin{minipage}{\dimexpr\expapercardhalf-2\expapercardpad\relax}%
    \centering#2\par\end{minipage}}}
% a half: its side in the middle of it, across and down
\newcommand\expapercardhalfbox[1]{%
  \vbox to\expapercardht{\vss\hbox to\expapercardhalf{\hss\usebox#1\hss}\vss}}
% the frame, drawn from the card's foot on the left, where the pen stands
\@ifpackageloaded{tikz}{%
  \newcommand\expapercardframe{%
    \begin{tikzpicture}[overlay]
      \draw[line width=\expapercardrule, draw=accentlt, fill=white, rounded corners=.9em]
        (0,0) rectangle (\expapercardwd,\expapercardht);
      \draw[line width=.75\expapercardrule, draw=graytx,
            dash pattern=on 5\expapercardrule off 3.5\expapercardrule]
        (\expapercardhalf,0) -- (\expapercardhalf,\expapercardht);
      \node[fill=white, inner sep=.12em, text=graytx]
        at (2.4em,\expapercardht) {\Large\expapercutX};
    \end{tikzpicture}}%
}{%
  \newcommand\expapercardframe{\rlap{\color{accentlt}%
    \hskip-.5\expapercardrule
    \vrule width\dimexpr\expapercardwd+\expapercardrule\relax
      height.5\expapercardrule depth.5\expapercardrule
    \hskip-\dimexpr\expapercardwd+\expapercardrule\relax
    \vrule width\dimexpr\expapercardwd+\expapercardrule\relax
      height\dimexpr\expapercardht+.5\expapercardrule\relax
      depth-\dimexpr\expapercardht-.5\expapercardrule\relax
    \hskip-\dimexpr\expapercardwd+\expapercardrule\relax
    \vrule width\expapercardrule
      height\dimexpr\expapercardht+.5\expapercardrule\relax depth.5\expapercardrule
    \hskip\dimexpr\expapercardwd-\expapercardrule\relax
    \vrule width\expapercardrule
      height\dimexpr\expapercardht+.5\expapercardrule\relax depth.5\expapercardrule
    \hskip-\dimexpr\expapercardhalf+.875\expapercardrule\relax
    {\color{graytx}\vbox to\expapercardht{\cleaders\vbox to 8.5\expapercardrule{\vss
      \hrule width.75\expapercardrule height 5\expapercardrule\vss}\vfill}}}}%
}
% \expapercard{above it}{front}{back}
\newcommand\expapercard[3]{%
  \par
  \setlength\expapercardwd{\dimexpr\linewidth-\expapercardrule\relax}%
  \setlength\expapercardhalf{.5\expapercardwd}%
  \setlength\expapercardpad{1.2em}%
  \expapercardside\expapercardfront{#2}%
  \expapercardside\expapercardback{#3}%
  \setlength\expapercardht{\dimexpr\ht\expapercardfront+\dp\expapercardfront\relax}%
  \ifdim\dimexpr\ht\expapercardback+\dp\expapercardback\relax>\expapercardht
    \setlength\expapercardht{\dimexpr\ht\expapercardback+\dp\expapercardback\relax}%
  \fi
  \addtolength\expapercardht{2\expapercardpad}%
  \ifdim\expapercardht<.6\expapercardhalf \setlength\expapercardht{.6\expapercardhalf}\fi
  \setbox\expapercardbox\vbox{\hsize\linewidth\@parboxrestore
    #1\par\vskip1.2ex
    \hbox{\hskip.5\expapercardrule\expapercardframe
      \expapercardhalfbox\expapercardfront\expapercardhalfbox\expapercardback}%
    \vskip.5\expapercardrule}%
  % the most a card may be: a page less a line -- and straight after a
  % heading, which goes wherever the card goes, a page less five lines (the
  % two go over together), or what is left of this page when that is more
  \setlength\expapercardroom{\dimexpr\textheight-\baselineskip\relax}%
  \ifinner\else\if@nobreak
    \setlength\expapercardroom{\dimexpr\textheight-5\baselineskip\relax}%
    \ifdim\pagegoal<\maxdimen
      \ifdim\dimexpr\pagegoal-\pagetotal-\pagedepth-\baselineskip\relax>\expapercardroom
        \setlength\expapercardroom{\dimexpr\pagegoal-\pagetotal-\pagedepth-\baselineskip\relax}%
      \fi
    \fi
  \fi\fi
  \ifdim\dimexpr\ht\expapercardbox+\dp\expapercardbox\relax>\expapercardroom
    \setbox\expapercardbox\hbox to\linewidth{\hss
      \resizebox{!}{\expapercardroom}{\box\expapercardbox}\hss}%
  \fi
  \noindent\box\expapercardbox\par}
\makeatother"""


def exercise_paper_tex(cards=False):
    """The %%EXERCISEPAPER%% block, its writing lines as heavy as the print
    size's blanks, and \\exlexfitpar first unless large print has already
    defined it (print_options_tex); with `cards`, the flashcards' own
    (CARD_PAPER), whose frame is twice as heavy as the blanks."""
    paper = EXERCISE_PAPER.replace("%%RULE%%", rule_width())
    if print_size() == DEFAULT_PRINT_SIZE:
        paper = _FITPAR_TEX + "\n" + paper
    if cards:
        if print_size() == DEFAULT_PRINT_SIZE:
            paper += "\n" + _FIT_TEX          # a card's tables, at every size
        paper += "\n" + CARD_PAPER.replace(
            "%%CARDRULE%%", "%.1fpt" % (0.8 * print_size() / DEFAULT_PRINT_SIZE))
    return paper


def _ex_cell_rtl(text, fields):
    """Is this cell of an exercise -- one side of a pair, one statement --
    set right to left?  When it is the RTL target's throughout, as a fill
    sentence is (is_target_line), unless the exercise asks for left to
    right.  A mixed cell stays left to right: TeX has no bidi algorithm,
    and \\beginR round a Latin phrase would reverse its words."""
    if (fields.get("content-direction") or "").strip().lower() == "ltr":
        return False
    return cur_lang().rtl and is_target_line(text)


def _ex_cell(text, fields):
    """One cell's text, aligned to the side it is read from: an RTL cell
    flush right in one right-to-left segment (its continuation lines too),
    anything else flush left.

    A cell is a narrow column, and in large print a word can be wider than
    it: so its target runs may break (\\pel, never the one box of a \\pe),
    and the \\hspace{0pt} lets TeX hyphenate its first word (TeX hyphenates
    only a word that follows glue; the glue is not a place a line can end).
    A German compound hyphenated at 20 pt is still 20 pt; kept whole, it
    would have been scaled to fit (\\exlexfitpar) to half that."""
    body = _ex_inline(text, force_breakable=True)
    if _ex_cell_rtl(text, fields):
        return "\\raggedleft\\noindent\\hspace{0pt}\\beginR %s\\endR" % body
    return "\\raggedright\\noindent\\hspace{0pt}%s" % body


def _exercise_prompt(prompt):
    rendered = []
    for line in prompt_lines(prompt):
        if not line:
            rendered.append(r"\vspace{\baselineskip}")
            continue
        source = "".join(span for span, _ in line)
        parts = [("{\\mdseries %s}" if regular else "\\textbf{%s}") % _ex_inline(span)
                 for span, regular in line]
        text = "".join(parts)
        if cur_lang().rtl and is_target_line(source):
            rendered.append("{\\raggedleft\\noindent %s\\par}" % text)
        else:
            rendered.append(text + "\\par")
    return "".join(rendered) + "\\smallskip{}"


def _render_exercise(b, step=None):
    """Printable, deliberately unsolved twin of an interactive exercise.

    `step` is (k, n) for a STEP OF A FOLLOW-UP (a0.5.4): what comes back is the exercise's inside, numbered, to be set in
    the step's own frame by _render_chain -- laid out exactly as the type is laid out on its own, except that a card is
    its two sides one under the other, labelled Front and Back, which a card to cut and fold would not be inside a
    frame; the footnotes are deferred by the chain, past its last step."""
    if b.get("primitive") == "chain" and not b.get("errors") and step is None:
        return _render_chain(b)
    f, items = b.get("fields", {}), b.get("items", [])
    label = _EX_TEX_LABELS.get(b.get("subtype"), "Exercise")
    body = []
    # the whole exercise is a minipage, which would swallow a \footnote
    # written anywhere inside it: defer them all past its end
    prev = None if step else _begin_defer()
    end_defer = (lambda: "") if step else (lambda: _end_defer(prev))
    kind = (f.get("card-type") or "vocab").lower()
    cards = {}
    import mdparser     # exlex's parser imports this module: not at the top
    if b.get("primitive") == "flashcard" and kind == "jolly":
        # every note written on the card is known before anything cites one
        cards, notes = mdparser.card_fields(b, cur_lang().code)
        _FN["defs"].update(notes)
    # the prompt is printed first, so its notes are numbered first.  Ordinary
    # prose is set exactly as it always was; a prompt that is a fence on its
    # own (a ::::latex drawing, TO-DO §8.39's L8) is not -- card_field tells
    # the two apart for it, the same rule it already used for a jolly card.
    prompt = ""
    if f.get("prompt"):
        field = mdparser.card_field(b, "prompt", cur_lang().code)
        if field and field[0] == "blocks":
            _FN["defs"].update(field[2])
            prompt = render_blocks(field[1])
            # what follows is set right after \smallskip (below), a control
            # WORD: TeX would read a letter straight after it as part of its
            # own name (found only by compiling: his own single-choice
            # example became the undefined command \smallskipChoose).
            # _exercise_prompt's own output never starts with one; this is
            # the one new road that can, so it alone needs the empty group.
            if prompt[:1].isalpha():
                prompt = "{}" + prompt
        else:
            prompt = _exercise_prompt(f["prompt"])
    if b.get("primitive") != "flashcard":
        prompt += _ex_image(f, "image") + _ex_audio(f, "audio")
    elif not b.get("errors"):
        front, back = _card_sides(f, kind, cards)
        if step:
            # inside a step's frame: the two sides one under the other, each said what it is
            inside = ("%s\\par\\smallskip%s{\\sffamily\\bfseries\\footnotesize Front}\\par\\smallskip %s\\par\\medskip"
                      "{\\sffamily\\bfseries\\footnotesize Back}\\par\\smallskip %s"
                      % (_step_head(step, label), prompt, front, back))
            return "\\large " + inside if print_size() != DEFAULT_PRINT_SIZE else inside
        # a card to cut out and fold, its label and prompt above its frame
        # (\expapercard); in large print a step larger, as every exercise is
        head = ("{\\sffamily\\bfseries\\footnotesize\\color{accent}%s}\\par\\smallskip%s"
                % (escape_latin(label), prompt))
        card = "\\expapercard{%s}{%s}{%s}" % (head, front, back)
        if print_size() != DEFAULT_PRINT_SIZE:
            card = "{\\large %s}" % card
        return "\\par\\bigskip%s\\medskip%s" % (card, end_defer())
    if b.get("errors"):
        # black and white keeps the words and loses the red, as every
        # colour written in this file does there
        body.append("{\\bfseries Exercise needs attention in the Markdown source.}"
                    if is_mono() else
                    "{\\color{red}Exercise needs attention in the Markdown source.}")
    elif b.get("mode") == "fill":
        # the blanks are drawn after the sentence is set: a rule written
        # before would be escaped into its own text by _ex_inline()
        line = _slots_outside_math(_ex_inline(f.get("text", "")))
        # The whole line, including its blanks, needs RTL reading order.
        # Its paragraph also needs right alignment: \beginR alone leaves
        # the last line flush left when TeX finishes the paragraph.
        direction = (f.get("content-direction") or "").strip().lower()
        rtl_line = (direction == "rtl" or
                    (direction == "target" and cur_lang().rtl) or
                    (not direction and cur_lang().rtl and is_target_line(f.get("text", ""))))
        if rtl_line:
            line = "{\\raggedleft\\noindent\\beginR %s\\endR\\par}" % line
        body.append(line)
        distractors = [x["text"] for x in items]
        if distractors:
            body.append("\\par\\smallskip\\textit{Blocks:} " + " \\quad ".join(_ex_inline(x) for x in distractors))
    elif b.get("primitive") == "matching":
        # every entry framed, so what is joined to what is plain: the
        # student draws a line from a frame on the left to one on the right
        left = [x["left"] for x in items]
        right = [x["right"] for x in items]
        if len(right) > 1:
            right = right[1:] + right[:1]
        body.append("".join(
            "\\expaperpair{%s}{%s}\n" % (_ex_cell(a, f), _ex_cell(c, f))
            for a, c in zip(left, right)))
    elif b.get("mode") == "boolean":
        # the statement wraps in its own column and never runs under the
        # marks, which stay one unbroken box at the same place on every row
        # (a long statement once pushed "/ False" onto a line of its own)
        marks = "Yes / No" if b.get("subtype") == "yes-no" else "True / False"
        body.append("\\expaperboolmarks{%s}" % marks + "".join(
            "\\expaperbool{%s}{%s}\n" % (_ex_cell(x["left"], f), marks)
            for x in items))
    elif b.get("primitive") == "choice":
        body.append("\\begin{itemize}%s\\end{itemize}" % "".join(
            "\\item $\\square$ %s" % _ex_inline(x["text"]) for x in items))
    elif b.get("subtype") == "construct-sentence":
        # the chunks in a row, as the page shows them, flowing the way the
        # answer is read (answer-direction, else the target's), and under
        # them lines to write the sentence on -- numbers written beside
        # the chunks were never the sentence
        shown = items[1:] + items[:1] if len(items) > 1 else items
        rtl = (f.get("answer-direction") or cur_lang().dir).strip().lower() == "rtl"
        row = "\\expaperchunkgap ".join(
            "\\expaperchunk{%s}" % _ex_inline(x["text"]) for x in shown)
        body.append("\\expaperchunks{%s}%s\\expaperwritelines" % (
            "r" if rtl else "l",
            ("{\\raggedleft\\noindent\\beginR %s\\endR\\par}" if rtl
             else "{\\raggedright\\noindent %s\\par}") % row))
    else:
        shown = items[1:] + items[:1] if len(items) > 1 else items
        body.append("\\begin{itemize}%s\\end{itemize}" % "".join(
            "\\item %s" % _ex_inline(x["text"]) for x in shown))
    head = _step_head(step, label) if step else (
        "{\\sffamily\\bfseries\\footnotesize\\color{accent}%s}" % escape_latin(label))
    inside = "%s\\par\\smallskip%s%s" % (head, prompt, "\\par".join(body))
    if print_size() != DEFAULT_PRINT_SIZE:
        # in large print an exercise is set a step larger than the text
        # round it: it is what the reader holds closest, and writes on
        inside = "\\large " + inside
    if step:
        return inside
    # in a box that goes on over pages when it is taller than one
    # (\expaperexercise): ten framed rows of pictures are, at any size
    return "\\par\\medskip\\expaperexercise{%s}\\medskip%s" % (inside, end_defer())


def _step_head(step, label):
    """The head of a step's frame: its number, then what kind of exercise it is."""
    return ("{\\sffamily\\bfseries\\footnotesize\\color{accent}%d.\\enspace %s}"
            % (step[0], escape_latin(label)))


def _render_chain(b):
    """A FOLLOW-UP ON PAPER (a0.5.4): one exercise under its label, its prompt and its shared picture once at the top;
    then its steps numbered 1., 2., ..., each in a lighter frame of its own and each laid out exactly as its type is
    laid out on paper -- so a chain may part between two steps at a page's foot (every step is a frame that keeps
    together, or continues over pages as a tall exercise does) and never inside a step, and a step's picture stays with
    its step.  Answers, explanations and the pictures of an answer are left out, as for every exercise.  Each step is
    seen at once, whether or not the one before gives it away: the guide says so."""
    import mdparser     # exlex's parser imports this module: not at the top
    f = b.get("fields", {})
    prev = _begin_defer()
    prompt = ""
    if f.get("prompt"):
        field = mdparser.card_field(b, "prompt", cur_lang().code)
        if field and field[0] == "blocks":
            _FN["defs"].update(field[2])
            prompt = render_blocks(field[1])
            if prompt[:1].isalpha():
                prompt = "{}" + prompt
        else:
            prompt = _exercise_prompt(f["prompt"])
    shared = _ex_image(f, "image") + _ex_audio(f, "audio")
    prompt += shared
    head = ("{\\sffamily\\bfseries\\footnotesize\\color{accent}%s}\\par\\smallskip%s"
            % (escape_latin(_EX_TEX_LABELS["follow-up"]), prompt))
    if print_size() != DEFAULT_PRINT_SIZE:
        head = "\\large " + head
    steps = b.get("steps") or []
    out = ["\\par\\medskip\\expaperexercise{%s}" % head]
    for k, step in enumerate(steps, 1):
        # the head holds on to the first step, which never leaves it alone at the foot of a page -- unless the head
        # carries a picture of its own, which with a large print and a picture on the step too would push the whole
        # chain to a page of its own and leave the one before empty; a page may end between any two steps, never
        # inside one (the step's own frame keeps together, or goes on over the pages)
        out.append("\\par%s\\medskip\\expaperstep{%s}"
                   % ("\\nopagebreak" if k == 1 and not shared else "", _render_exercise(step, (k, len(steps)))))
    out.append("\\medskip" + _end_defer(prev))
    return "".join(out)


# LATEX BLOCKS ON PAPER (TO-DO §8.39) are the same drawing the screen shows:
# the PDF lib/latexdraw.py compiled on its own, included as a picture and
# laid out as a figure -- never the block's LaTeX set in this document, whose
# preamble a theme's packages must not touch (the owner, 2026-09-24).  The
# drawer is handed in (set_latex) by whoever builds; the files each .tex
# needs are what latex_used() says, staged beside it as latex/<key>.pdf.
LATEX = {"draw": None}
_LATEX_RUN = ThreadDict(used=[], failed=0)


def set_latex(draw):
    LATEX["draw"] = draw


def latex_used():
    """([(key, pdf path)], how many blocks could not be drawn) of the last
    generate() on this thread."""
    return list(_LATEX_RUN["used"]), _LATEX_RUN["failed"]


def _latex_note(said):
    """A drawing that could not be made, said on the paper where it would
    have stood -- as an exercise that needs attention is."""
    _LATEX_RUN["failed"] += 1
    return (r"\par\medskip\noindent\fbox{\parbox{\dimexpr\linewidth-2\fboxsep-2\fboxrule\relax}"
            r"{\small\textbf{LaTeX drawing.} %s}}\par\medskip" % escape_latin(said))


def _latex_captioned(b, f, align, offset):
    """A drawing with a caption, set as the screen sets it (htmlgen's
    _latex_captioned), in one minipage so that a page never parts the two.
    The dimens are local: \\dimen0 the drawing, 1 the caption's box, 2 and 3
    their left edges."""
    if b.get("width"):
        left = r"\dimen2=%.3f\linewidth" % image_indent({"width": b["width"], "align": align,
                                                        "offset": offset})
        scale = (r"\setbox0\hbox{\includegraphics[width=%.3f\linewidth]{%s}}\dimen0=\wd0"
                 % (b["width"] / 100.0, f))
    else:
        scale = (r"\setbox0\hbox{\includegraphics[scale=%.3f]{%s}}"
                 r"\ifdim\wd0>\linewidth\setbox0\hbox{\includegraphics[width=\linewidth]{%s}}\fi"
                 r"\dimen0=\wd0" % (print_size() / 10.0, f, f))
        left = {"left": r"\dimen2=%.3f\linewidth" % (offset / 100.0),
                "right": r"\dimen2=\dimexpr\linewidth-\dimen0+%.3f\linewidth\relax" % (offset / 100.0)
                }.get(align, r"\dimen2=\dimexpr(\linewidth-\dimen0)/2+%.3f\linewidth\relax" % (offset / 100.0))
    return (r"\par\medskip\noindent\begingroup%s%s"
            r"\dimen1=20em\relax\ifdim\dimen1>\linewidth\dimen1=\linewidth\fi"
            r"\ifdim\dimen1<\dimen0\dimen1=\dimen0\fi"
            r"\dimen3=\dimexpr\dimen2+(\dimen0-\dimen1)/2\relax"
            r"\ifdim\dimen3<0pt\dimen3=0pt\fi"
            r"\ifdim\dimen3>\dimexpr\linewidth-\dimen1\relax\dimen3=\dimexpr\linewidth-\dimen1\relax\fi"
            r"\edef\lxpic{\the\dimen0}\edef\lxbox{\the\dimen1}"
            r"\edef\lxleft{\the\dimen2}\edef\lxcap{\the\dimen3}"
            r"\begin{minipage}{\linewidth}\noindent\hspace*{\lxleft}\includegraphics[width=\lxpic]{%s}\par"
            r"\vspace{0.4ex}\noindent\hspace*{\lxcap}\begin{minipage}{\lxbox}\%s\noindent"
            r"{\footnotesize\color{graytx} %s\par}\end{minipage}\end{minipage}"
            r"\endgroup\par\medskip"
            % (scale, left, f,
               {"left": "raggedright", "right": "raggedleft"}.get(align, "centering"),
               inline(b["caption"])))


def _render_latex(b):
    if b.get("errors"):
        return _latex_note("; ".join(b["errors"]).capitalize() + ".")
    draw = LATEX["draw"]
    if draw is None:
        return _latex_note("It is drawn by LaTeX where Parseh can compile it.")
    r = draw(b.get("tex", ""), b.get("theme") or None)
    if not r.get("ok"):
        return _latex_note(r.get("said") or "This drawing could not be made.")
    _LATEX_RUN["used"].append((r["key"], r["pdf"]))
    f = "latex/%s.pdf" % r["key"]
    align = b.get("align") or "center"
    offset = 0 if _CARD["on"] else (b.get("offset") or 0)
    if (b.get("caption") or "").strip():
        return _latex_captioned(b, f, align, offset)
    if b.get("width"):
        w = b["width"] / 100.0
        ml = image_indent({"width": b["width"], "align": align, "offset": offset})
        return (r"\par\medskip\noindent\hspace*{%.3f\linewidth}"
                r"\begin{minipage}{%.3f\linewidth}\includegraphics[width=\linewidth]{%s}"
                r"\end{minipage}\par\medskip" % (ml, w, f))
    # its natural size: set at 10 pt, it grows with the print size as the
    # text round it does, and never past the column
    scale = print_size() / 10.0
    place = {"left": r"\hspace*{%.3f\linewidth}" % (offset / 100.0),
             "right": r"\hfill"}.get(align, r"\hfill")
    after = "" if align in ("left", "right") else r"\hfill\null"
    return (r"\par\medskip\noindent\begingroup\setbox0\hbox{\includegraphics[scale=%.3f]{%s}}"
            r"\ifdim\wd0>\linewidth\setbox0\hbox{\includegraphics[width=\linewidth]{%s}}\fi"
            r"%s\box0%s\endgroup\par\medskip" % (scale, f, f, place, after))


def render_blocks(blocks, inside_box=False):
    out = []
    card = _CARD["on"]
    for b in blocks:
        t = b["type"]
        if card and t in ("section", "subsection"):
            # a heading on a flashcard: a label, unnumbered (and a sectioning
            # command inside the exercise's minipage would not sit well)
            prev = _begin_defer()
            size, colour = (("\\large", "accent") if t == "section"
                            else ("\\normalsize", "accentlt"))
            out.append("{\\sffamily\\bfseries%s\\color{%s} %s\\par}\\smallskip"
                       % (size, colour, inline(b["text"])) + _end_defer(prev))
        elif card and t == "exercise":
            continue        # mdparser refuses a card holding one
        elif t == "section":
            prev = _begin_defer()
            out.append("\\section{%s}" % inline(b["text"]) + _end_defer(prev))
        elif t == "subsection":
            prev = _begin_defer()
            out.append("\\subsection{%s}" % inline(b["text"]) + _end_defer(prev))
        elif t == "voce":
            prev = _begin_defer()
            head = escape_latin(b["fa"]) if is_latin_target() else b["fa"]
            if b.get("fa_segments") and not is_mono():
                pieces = []
                for text_, colour_ in b["fa_segments"]:
                    body_ = escape_latin(text_) if is_latin_target() else text_
                    if not colour_:
                        style_ = ""
                    elif colour_.startswith("#"):
                        style_ = r"\color[HTML]{%s}" % colour_[1:]
                    else:
                        style_ = r"\color{fa%s}" % colour_
                    pieces.append(r"\segpiece{%s}{%s}" % (style_, body_))
                head = r"\segword{%s}{%s}" % (head, "".join(pieces))
            core = "\\voce{%s}{%s}{%s}{%s}" % (
                head, escape_latin(b.get("kana") or ""),
                inline(b["translit"]), inline(b["etym"]))
            # a coloured lemma: the group colour reaches only the \pe head
            # (translit/etym/rules all set their own colours explicitly)
            col = None if is_mono() else b.get("fa_color")
            if col and HEX_RE.match(col):
                core = ("\\begingroup\\color[HTML]{%s}%s\\endgroup"
                        % (col[1:].upper(), core))
            elif col in PALETTE:
                core = ("\\begingroup\\color{fa%s}%s\\endgroup"
                        % (col, core))
            out.append(core + _end_defer(prev))
        elif t == "para":
            txt = b["text"].strip()
            la_whole = LA_RE.fullmatch(txt)
            tl_whole = tl_re().fullmatch(txt)
            tl_nested = target_fullmatch(txt) if tl_whole is None else None
            if la_whole:
                out.append(_render_la_block(
                    la_whole.group(1), parse_la_attrs(la_whole.group(2))))
            elif _is_pure_fa_paragraph(txt):
                out.append("\\par\\medskip\\noindent\\hspace*{1.5em}"
                           "{\\large\\pel{%s}}\\par\\medskip" % txt)
            elif tl_whole or tl_nested or is_fa_only_paragraph(txt):
                # prose in the target language (punctuation/latin islands
                # included): a block in its direction, optionally styled
                content = (tl_whole.group(1) if tl_whole else
                           (tl_nested.content if tl_nested else txt))
                attrs = parse_tl_attrs(tl_whole.group(2) if tl_whole else
                                       (tl_nested.attrs if tl_nested else ""))
                out.append(_render_tl_block(content, attrs))
            else:
                out.append(inline(b["text"]) + ("" if inside_box else "\n"))
        elif t in ("list", "enum"):
            out.append(_render_list(b, ordered=(t == "enum")))
        elif t == "table":
            out.append(_render_table(b))
        elif t == "image":
            out.append(_render_image(b))
        elif t == "audio":
            out.append(_render_audio(b))
        elif t == "video":
            out.append(_render_video(b))
        elif t == "box":
            out.append(_render_box(b))
        elif t == "exercise":
            out.append(_render_exercise(b))
        elif t == "latex":
            out.append(_render_latex(b))
        elif t == "math":
            # `\[ ... \]` is display mathematics in LaTeX's own words, and
            # the body is the author's, untouched -- nothing in this file
            # has escaped it, because the fence never went through inline()
            out.append("\\[\n%s\n\\]" % b.get("tex", ""))
    return "\n\n".join(x for x in out if x)


# ----------------------------------------------------------------------
# whole document
# ----------------------------------------------------------------------

def _titleblock(fm):
    if not fm.get("title"):
        return ""
    lines = ["\\begin{center}",
             "  {\\sffamily\\bfseries\\color{accent}\\Huge %s}\\\\[0.8ex]"
             % inline(fm["title"])]
    if fm.get("subtitle"):
        lines.append("  {\\sffamily\\large\\color{accentlt} %s}\\\\[1.6ex]"
                     % inline(fm["subtitle"]))
    lines.append("  {\\color{rulec}\\rule{0.55\\linewidth}{0.8pt}}\\\\[1.2ex]")
    if fm.get("note"):
        lines.append("  {\\small\\color{graytx} %s}" % inline(fm["note"]))
    lines += ["\\end{center}", "\\vspace{1.2ex}"]
    return "\n".join(lines)


# The colophon names the target language and its face; the direction
# sentence is only for right-to-left scripts, whose word order is what
# the TeXXeT primitives exist for.  The Persian colophon is the
# historical text, byte for byte -- line breaks included -- because the
# Persian example must build to the same PDF text as before languages
# were declared (docs/languages.md, 11); the generic sentence is for the
# other languages only.
_COLOPHON_FA = r"""\par\vspace{2.5em}
\noindent{\color{rulec}\rule{\linewidth}{0.5pt}}\\[0.4ex]
{\scriptsize\color{graytx}
\textbf{Nota tecnica.} Documento generato dalla toolchain \emph{exlex}
(markdown $\rightarrow$ XeLaTeX). Il persiano usa \emph{Vazirmatn} di Saber
Rastikerdar (SIL OFL 1.1), ricavato dai file \texttt{.woff2} ufficiali e
decompresso in TrueType. La direzione destra\,$\rightarrow$\,sinistra è
ottenuta con i primitivi TeXXeT \texttt{\textbackslash beginR}\,/\,%
\texttt{\textbackslash endR}: XeTeX inverte già le \emph{lettere} dentro ogni
parola tramite lo shaper OpenType, ma senza questi primitivi l'ordine delle
\emph{parole} nella riga resterebbe da sinistra a destra. Testo latino:
TeX Gyre Pagella e Heros.}"""

_COLOPHON_HEAD = r"""\par\vspace{2.5em}
\noindent{\color{rulec}\rule{\linewidth}{0.5pt}}\\[0.4ex]
{\scriptsize\color{graytx}
\textbf{Nota tecnica.} Documento generato dalla toolchain \emph{exlex}
(markdown $\rightarrow$ XeLaTeX). %s Testo latino:
TeX Gyre Pagella e Heros.}"""

_COLOPHON_RTL = (
    r"La direzione destra\,$\rightarrow$\,sinistra è "
    r"ottenuta con i primitivi TeXXeT \texttt{\textbackslash beginR}\,/\,%"
    "\n"
    r"\texttt{\textbackslash endR}: XeTeX inverte già le \emph{lettere} dentro ogni "
    r"parola tramite lo shaper OpenType, ma senza questi primitivi l'ordine delle "
    r"\emph{parole} nella riga resterebbe da sinistra a destra.")


def colophon_for(L, font_name):
    """The colophon text for a language whose target face is `font_name`
    (Persian keeps its historical text, whatever the face resolved to)."""
    if L.code == languages.DEFAULT:
        return _COLOPHON_FA
    about = (r"La scrittura della lingua di studio (%s) usa \emph{%s}."
             % (escape_latin(L.name.lower()), escape_latin(font_name)))
    if L.rtl:
        about += " " + _COLOPHON_RTL
    return _COLOPHON_HEAD % about


COLOPHON = colophon_for(languages.get("fa"), "Vazirmatn")   # the old name


# Front-matter `lang:` -> the name TeX knows the patterns by, plus that
# language's hyphenation minima.  Only the name matters for correctness:
# the template activates a language solely if the running format has it,
# so an unknown or missing entry costs nothing but TeX's default (which
# is language 0, US English) rather than a wrong set of break points.
#
# Italian is the one language exlex vendors patterns for, because it is
# absent from many TeX Live installs; everything else here is expected to
# come from the distribution.
#
# These are PROSE languages -- what a note is WRITTEN in -- and that is a
# wider set than the languages the toolbox teaches: nobody studies English
# or Russian here, but notes are written in them, so their pattern names
# have nowhere else to live.  A code that is also a registry code is left
# `None` and takes its name from `tex.hyphen`, because one word must not
# break one way in a reading edition and another in the studio
# (docs/languages.md, 1).  German is what made the rule worth writing
# down: babel's `german` is the pre-1996 pattern set, under which Zucker,
# backen and Drucker do not break at all, while the registry's `ngerman`
# gives Zu-cker, ba-cken, Dru-cker -- which is what a book printed today
# wants.  The minima are ours either way; the registry does not carry them.
_HYPHEN_PROSE = {
    "en": ("english", 2, 3),
    "en-gb": ("british", 2, 3), "en-us": ("USenglish", 2, 3),
    "it": (None, 2, 2), "fr": (None, 2, 3),
    "de": (None, 2, 2), "tr": (None, 2, 2),
    "es": ("spanish", 2, 2),
    "pt": ("portuguese", 2, 3), "nl": ("dutch", 2, 2),
    "ca": ("catalan", 2, 2), "ro": ("romanian", 2, 2),
    "pl": ("polish", 2, 2), "ru": ("russian", 2, 2),
}
# The ISO 639-2 spellings of the same prose languages: a writer told to
# give "the ISO code" sometimes gives three letters.
_HYPHEN_ISO3 = {"eng": "en", "ita": "it", "fra": "fr",
                "deu": "de", "spa": "es"}
DEFAULT_HYPHEN = ("english", 2, 3)


def _hyphen_table():
    """_HYPHEN_PROSE with the registry's pattern name filled in wherever
    the table defers to it.  A code the registry no longer carries names
    itself instead ("de"), which no TeX format answers to, so the
    template leaves \\language alone -- the harmless half of a wrong
    guess, and better than silently hyphenating German as English."""
    t = {}
    for code, (name, lmin, rmin) in _HYPHEN_PROSE.items():
        if name is None:
            L = languages.LANGS.get(code)
            name = (L.tex.get("hyphen") if L else None) or code
        t[code] = (name, lmin, rmin)
    for three, two in _HYPHEN_ISO3.items():
        t[three] = t[two]
    return t


HYPHEN_LANGS = _hyphen_table()


def hyphenation_for(lang):
    """`lang:` front-matter value -> (TeX language name, lmin, rmin).

    A bare language name that TeX might know ("italian", "ngerman") is
    passed through untouched; anything unrecognised falls back to English,
    which is what an undeclared document used to get from TeX anyway.
    """
    key = (lang or "").strip().lower().replace("_", "-")
    if not key:
        return DEFAULT_HYPHEN
    if key in HYPHEN_LANGS:
        return HYPHEN_LANGS[key]
    base = key.split("-")[0]
    if base in HYPHEN_LANGS:
        return HYPHEN_LANGS[base]
    # spelled out as the TeX language name itself ("italian", "french"):
    # keep that language's own minima rather than the generic ones
    for name, lmin, rmin in HYPHEN_LANGS.values():
        if name.lower() == key:
            return (name, lmin, rmin)
    # not a code we map: if it looks like a TeX language name, let the
    # template decide whether the format actually has it
    if re.fullmatch(r"[A-Za-z]{4,}", key):
        return (key, 2, 3)
    return DEFAULT_HYPHEN


# ----------------------------------------------------------------------
# the per-language part of the preamble
# ----------------------------------------------------------------------
# The default size of the target script relative to the Latin text.  The
# Arabic-script faces are small on the x-height, which is why Persian was
# always set "very big" (1.52); CJK glyphs fill their em box and want
# less; a Latin-script target is the same alphabet as the prose and gets
# no enlargement at all.  The studio's slider and the CLI's --scale
# override this.
def default_scale(L):
    if L.chars is None:
        return "1.00"
    if L.script == "arabic":
        return "1.52"
    return "1.20"


# The fonts a build carries with it sit in the build's fonts/ directory
# (copied from lib/fonts by envsetup); a font that is not there is asked
# of the system by name.  Which file a family name maps to is derived
# from the name itself (spaces dropped: "Noto Naskh Arabic" ->
# NotoNaskhArabic-Regular.ttf), so no list of file names lives here.
_FONT_DIRS = (HERE / "assets" / "fonts", LIB / "fonts")


def bundled_font_files(name):
    """(regular file, bold file or None) of a bundled face, or None when
    the toolbox does not carry it."""
    stem = name.replace(" ", "")
    for d in _FONT_DIRS:
        for reg in (stem + "-Regular.ttf", stem + ".ttf"):
            if (d / reg).exists():
                bold = stem + "-Bold.ttf"
                return reg, (bold if (d / bold).exists() else None)
    return None


def _font_decl(cmd, name, options, scale):
    """One \\newfontfamily for `name`, from the bundled file when the
    toolbox carries it, else by system name; and the condition under
    which the declaration can be made at all."""
    opts = list(options)
    if scale:
        opts.append("Scale=%s" % scale)
    files = bundled_font_files(name)
    if files:
        reg, bold = files
        fopts = ["Path=./fonts/", "UprightFont=%s" % reg]
        if bold:
            fopts.append("BoldFont=%s" % bold)
        decl = ("\\newfontfamily%s[\n    %s]{%s}"
                % (cmd, ",\n    ".join(fopts + opts), name.replace(" ", "")))
        return "[./fonts/%s]" % reg, decl
    decl = "\\newfontfamily%s[%s]{%s}" % (cmd, ", ".join(opts), name)
    return name, decl


def _font_chain(cmd, names, options, scale, fallback):
    """Nested \\IfFontExistsTF down `names`; `fallback` when none exists."""
    if not names:
        return fallback
    cond, decl = _font_decl(cmd, names[0], options, scale)
    rest = _font_chain(cmd, names[1:], options, scale, fallback)
    return "\\IfFontExistsTF{%s}{%%\n  %s}{%%\n  %s}" % (cond, decl, rest)


def target_fonts_tex(L, scale):
    """The %%TARGETFONTS%% block: \\tlfont (main face, with fallbacks),
    \\tlalt (the alternate face, or \\tlfont again), for Japanese the
    vertical family and the line-breaking locale.  \\vaz and \\nasta stay
    as aliases of \\tlfont and \\tlalt."""
    tex = L.tex
    script_opts = []
    if tex.get("script"):
        script_opts.append("Script=%s" % tex["script"])
    if tex.get("language"):
        script_opts.append("Language=%s" % tex["language"])
    out = ["% the target language's faces (docs/languages.md, 5)"]
    mains = [n for n in [tex.get("main")] + list(tex.get("main_fallbacks") or []) if n]
    if mains:
        # last resort: the body face, so the document still compiles and
        # says what is missing in the log
        fallback = ("\\newfontfamily\\tlfont[Extension=.otf,UprightFont=*-regular,"
                    "BoldFont=*-bold,ItalicFont=*-italic,BoldItalicFont=*-bolditalic,"
                    "Scale=%s]{texgyrepagella}"
                    "\\PackageWarning{exlex}{no %s font found; using the body face}"
                    % (scale, escape_latin(L.name)))
        out.append(_font_chain("\\tlfont", mains, script_opts, scale, fallback))
        main_name = mains[0]
    else:
        # a Latin-script target: the body face, at the target scale
        out.append("\\newfontfamily\\tlfont[Extension=.otf,UprightFont=*-regular,"
                   "BoldFont=*-bold,ItalicFont=*-italic,BoldItalicFont=*-bolditalic,"
                   "Scale=%s]{texgyrepagella}" % scale)
        main_name = "TeX Gyre Pagella"
    out.append("\\let\\vaz\\tlfont")
    if tex.get("alt"):
        # the registry's alt_options (Language=Urdu for the nastaliq face)
        # replace the language, never the script
        extra = [o.strip() for o in (tex.get("alt_options") or "").split(",")
                 if o.strip()]
        keys = {o.split("=")[0] for o in extra}
        alt_opts = [o for o in script_opts if o.split("=")[0] not in keys] + extra
        out.append(_font_chain("\\tlalt", [tex["alt"]], alt_opts, scale,
                               "\\let\\tlalt\\tlfont"))
    else:
        out.append("\\let\\tlalt\\tlfont")
    out.append("\\let\\nasta\\tlalt")
    if L.vertical:
        # tategaki: the same face with its glyphs rotated, set in a box
        # that \tlvertical then turns by -90 degrees (docs/languages.md, 5)
        out.append(_font_chain("\\tlvert", mains,
                               script_opts + ["Vertical=RotatedGlyphs"], scale,
                               "\\let\\tlvert\\tlfont"))
    if not L.spaced:
        # a language with no word separator breaks lines between characters,
        # which XeTeX will only do with an ICU locale -- the language's own
        # code is that locale.  Tested against Japanese; the condition is the
        # registry's word_sep rather than the code, so the next unspaced
        # language gets it without an edit here.
        out.append("\\XeTeXlinebreaklocale \"%s\"\n"
                   "\\XeTeXlinebreakskip = 0pt plus 1pt" % L.code)
    # The transliteration line of a lemma heading: for a Latin-script
    # target it is a pronunciation in an IPA-lite scheme (ʎ ɲ ʃ ṡ, the
    # stress mark), glyphs TeX Gyre Pagella does not have; XeTeX has no
    # glyph fallback, so that line is set in a face that carries them when
    # the machine has one.  For a script language the line stays in the
    # body face, exactly as it always was.
    if L.chars is None:
        out.append("\\IfFontExistsTF{DejaVu Serif}{\\newfontfamily\\trfont[Scale=MatchLowercase]"
                   "{DejaVu Serif}}{\\newcommand{\\trfont}{}}")
    else:
        out.append("\\newcommand{\\trfont}{}")
    return "\n".join(out), main_name


# \tllatin, round each Latin word of the target's own text (latin_in_target):
# written into the preamble only when the document has one, so that every
# other document's .tex is the one it was.  \tlfont and \tlalt note the
# family they are entered from, as long as it has Latin letters -- the
# prose's serif, a heading's sans -- and a Latin word in a target face
# that has none is set in that family, at the size, weight and shape round
# it.  In a face that has them (Vazirmatn, the Japanese and Chinese faces)
# \tllatin does nothing, and the word is set as it always was.
TARGET_LATIN_TEX = r"""% Latin letters in the target's own text (texgen.TARGET_LATIN_TEX)
\makeatletter
\def\exlex@latinfamily{\rmdefault}
\def\exlex@entertl{\iffontchar\font`A \edef\exlex@latinfamily{\f@family}\fi}
\let\exlex@tlfont\tlfont
\let\exlex@tlalt\tlalt
\protected\def\tlfont{\exlex@entertl\exlex@tlfont}
\protected\def\tlalt{\exlex@entertl\exlex@tlalt}
\protected\def\tllatin{\iffontchar\font`A \else\fontfamily{\exlex@latinfamily}\selectfont\fi}
\makeatother"""


def target_dir_tex(L):
    """The %%TARGETDIR%% block: \\pe/\\pel/\\peb and the fapar
    environment in the language's direction, plus \\tlvertical."""
    if L.rtl:
        macros = r"""% \pe  : inline target text, atomic box (never breaks across lines)
% \pel : breakable target text (long phrases, display lines)
% \peb : bold target text
% Right-to-left: the TeXXeT primitives reverse the word order (see BIDI).
\DeclareRobustCommand{\pe}[1]{\mbox{\tlfont\beginR #1\endR}}
\DeclareRobustCommand{\pel}[1]{\leavevmode{\tlfont\beginR #1\endR}}
\DeclareRobustCommand{\peb}[1]{\mbox{\tlfont\bfseries\beginR #1\endR}}

% A segmented-colour word remains one shaped run.  Its uncoloured full-word
% box is the ink and the advance; clipped, coloured full-word copies replace
% only the selected horizontal slices.  Logical RTL pieces advance from the
% right edge.  In particular, no colour command ever interrupts Arabic
% joining.
\newsavebox{\segfullbox}
\newsavebox{\segpiecebox}
\newsavebox{\segmeasurebox}
\newsavebox{\segoverlaybox}
\newsavebox{\segclipbox}
\newlength{\segoffset}
\newlength{\segright}
\DeclareRobustCommand{\segpiece}[2]{#2}% safe in moving heading arguments
\makeatletter
\newcommand{\segclip}[3]{%
  \sbox{\segclipbox}{#3}%
  \@trimbox\segclipbox{#1}{0pt}{#2}{0pt}%
  \@cliptoboxdim\segclipbox
  \usebox{\segclipbox}}%
\makeatother
\DeclareRobustCommand{\segword}[2]{%
  \begingroup
  \sbox{\segfullbox}{#1}%
  % Isolated Arabic letters are wider than those same letters in their
  % joined word.  Do the clipping in the isolated-pieces measuring space,
  % then shrink the completed overlay back to the full word.  The two
  % horizontal transforms cancel, preserving the uninterrupted shaping.
  \def\segpiece##1##2{##2}%
  \sbox{\segmeasurebox}{#2}%
  \setlength{\segoffset}{\wd\segmeasurebox}%
  \sbox{\segoverlaybox}{\hbox{\beginL
    \def\segpiece##1##2{%
      \sbox{\segpiecebox}{##2}%
      \addtolength{\segoffset}{-\wd\segpiecebox}%
      \setlength{\segright}{\wd\segmeasurebox}%
      \addtolength{\segright}{-\segoffset}%
      \addtolength{\segright}{-\wd\segpiecebox}%
      \if\relax\detokenize{##1}\relax\else
        \rlap{\kern\segoffset
          \segclip{\the\segoffset}{\the\segright}%
            {\resizebox*{\wd\segmeasurebox}%
              {\dimexpr\ht\segfullbox+\dp\segfullbox\relax}%
              {\hbox{##1#1}}}}%
      \fi}%
    #2\kern\wd\segmeasurebox
  \endL}}%
  \ht\segoverlaybox=\ht\segfullbox
  \dp\segoverlaybox=\dp\segfullbox
  \leavevmode\hbox{\beginL
    \rlap{\usebox{\segfullbox}}%
    \rlap{\resizebox*{\wd\segfullbox}%
      {\dimexpr\ht\segfullbox+\dp\segfullbox\relax}%
      {\usebox{\segoverlaybox}}}%
    \kern\wd\segfullbox
  \endL}\endgroup}

\pdfstringdefDisableCommands{%
  \def\pe#1{#1}\def\pel#1{#1}\def\peb#1{#1}%
  \def\segword#1#2{#1}\def\segpiece#1#2{}%
}

% A paragraph of prose in the target language (ASCII punctuation and
% \beginL islands for Latin words included): right-aligned, whole
% paragraph in TeXXeT R direction so nothing splits the reading order.
\newenvironment{fapar}
  {\par\medskip\begingroup\tlfont\raggedleft\leavevmode\beginR}
  {\endR\par\endgroup\medskip}"""
    else:
        macros = r"""% \pe  : inline target text, atomic box (never breaks across lines)
% \pel : breakable target text (long phrases, display lines)
% \peb : bold target text
% Left-to-right: no TeXXeT, the run is set as it is.
\DeclareRobustCommand{\pe}[1]{\mbox{\tlfont #1}}
\DeclareRobustCommand{\pel}[1]{\leavevmode{\tlfont #1}}
\DeclareRobustCommand{\peb}[1]{\mbox{\tlfont\bfseries #1}}

% The LTR counterpart of the shaped overlay above.  Pieces advance from the
% left edge; the underlying word and every coloured layer are still shaped
% as an uninterrupted full word.
\newsavebox{\segfullbox}
\newsavebox{\segpiecebox}
\newsavebox{\segclipbox}
\newlength{\segoffset}
\newlength{\segright}
\DeclareRobustCommand{\segpiece}[2]{#2}% safe in moving heading arguments
\makeatletter
\newcommand{\segclip}[3]{%
  \sbox{\segclipbox}{#3}%
  \@trimbox\segclipbox{#1}{0pt}{#2}{0pt}%
  \@cliptoboxdim\segclipbox
  \usebox{\segclipbox}}%
\makeatother
\DeclareRobustCommand{\segword}[2]{%
  \begingroup
  \sbox{\segfullbox}{#1}%
  \setlength{\segoffset}{0pt}%
  \leavevmode\hbox{%
    \rlap{\usebox{\segfullbox}}%
    \def\segpiece##1##2{%
      \sbox{\segpiecebox}{##2}%
      \setlength{\segright}{\wd\segfullbox}%
      \addtolength{\segright}{-\segoffset}%
      \addtolength{\segright}{-\wd\segpiecebox}%
      \if\relax\detokenize{##1}\relax\else
        \rlap{\kern\segoffset
          \segclip{\the\segoffset}{\the\segright}%
            {\hbox{##1#1}}}%
      \fi
      \addtolength{\segoffset}{\wd\segpiecebox}}%
    #2\kern\wd\segfullbox
  }\endgroup}

\pdfstringdefDisableCommands{%
  \def\pe#1{#1}\def\pel#1{#1}\def\peb#1{#1}%
  \def\segword#1#2{#1}\def\segpiece#1#2{}%
}

% A paragraph of prose in the target language: a left-to-right
% paragraph in the target face.
\newenvironment{fapar}
  {\par\medskip\begingroup\tlfont\raggedright\leavevmode}
  {\par\endgroup\medskip}"""
    note, height = _tlvertical_height()
    macros += r"""

% \tlvertical{height}{text}: columns top-to-bottom progressing right-to-
% left -- the text set in a minipage whose WIDTH is the column height, in
% the face whose glyphs are pre-rotated, then the whole box turned by -90
% degrees.  True tategaki without any CJK package (verified with Noto
% Serif CJK JP); a language that cannot be set vertically never emits it.@NOTE@
\newcommand{\tlvertical}[2]{%
  \par\medskip{\centering\tlvert
    \rotatebox[origin=lt]{-90}{\begin{minipage}{@HEIGHT@}%
      \setlength{\parindent}{0pt}\raggedright #2\end{minipage}}%
    \par}\medskip}""".replace("@NOTE@", note).replace("@HEIGHT@", height)
    return macros


def _tlvertical_height():
    """The note and the column height of \\tlvertical.  The height is in
    ems of the print, so in large print the same `height=40` is a column
    twice as long: at 20 pt one that fitted the page at 11 ran off the
    paper's foot.  There it is never longer than the page less a few lines;
    at the normal size it is exactly what it always was."""
    if print_size() == DEFAULT_PRINT_SIZE:
        return "", "#1em"
    return ("\n% In large print a column is never longer than the page less four\n"
            "% lines: its height is in ems, and the ems have grown with the print.",
            "\\dimexpr\\ifdim#1em>\\dimexpr\\textheight-4\\baselineskip\\relax"
            "\\textheight-4\\baselineskip\\else#1em\\fi\\relax")


def _placeholder_line(tex, name, content):
    """Put `content` in place of the template's `%%NAME%% ...` line, the
    note after the name included; nothing at all -- not even the line --
    when there is no content, so an option left at its default leaves the
    .tex exactly as it was before the option existed."""
    return re.sub(r"^%%" + name + r"%%.*\n",
                  lambda _m: content + "\n" if content else "", tex, flags=re.M)


def generate(fm, blocks, fa_scale=None, voce_size="38", voce_lead="44",
             colophon=True, docs=None, font_size=DEFAULT_PRINT_SIZE, mono=False):
    """The whole .tex of a document.  `font_size` (one of PRINT_SIZES) and
    `mono` are the print options (set_print); at their defaults, 11 pt in
    colour, the .tex is the one the generator always wrote."""
    template = (HERE / "template.tex").read_text(encoding="utf-8")
    L = set_target(fm.get("target"))
    set_print(font_size, mono)
    _LATEX_RUN.update({"used": [], "failed": 0})
    reset_footnotes(fm.get("_footnotes"))
    set_doc_index(docs)
    scale = str(fa_scale) if fa_scale else default_scale(L)
    size = print_size()
    if size != DEFAULT_PRINT_SIZE:
        # the lemma head is the document's one absolute size: it grows by
        # the ratio everything relative to the class size grows by
        voce_size = "%d" % round(float(voce_size) * size / DEFAULT_PRINT_SIZE)
        voce_lead = "%d" % round(float(voce_lead) * size / DEFAULT_PRINT_SIZE)
    hlang, lmin, rmin = hyphenation_for(fm.get("lang"))
    fonts_tex, main_name = target_fonts_tex(L, scale)
    # the title first: a note in it is the document's first footnote
    title = _titleblock(fm)
    body = render_blocks(blocks)
    if "\\tllatin" in title + body:
        fonts_tex += "\n" + TARGET_LATIN_TEX
    tex = _placeholder_line(template, "DOCUMENTCLASS", print_class_tex(size))
    tex = _placeholder_line(tex, "PRINTOPTIONS", print_options_tex(size, is_mono()))
    # the exercises' own macros, only where one of them is printed
    tex = _placeholder_line(tex, "EXERCISEPAPER",
                            exercise_paper_tex("\\expapercard" in body)      # \expapercard{ for a card, \expapercardsize for a step's
                            if "\\expaper" in body else "")
    tex = (tex
           .replace("%%MARGINS%%", _MARGINS[size])
           .replace("%%TARGETMARK%%", "%% exlex-target: %s %s" % (L.code, L.dir))
           .replace("%%HYPHENLANG%%", hlang)
           .replace("%%HYPHENLMIN%%", str(lmin))
           .replace("%%HYPHENRMIN%%", str(rmin))
           .replace("%%TARGETFONTS%%", fonts_tex)
           .replace("%%TARGETDIR%%", target_dir_tex(L))
           .replace("%%FASCALE%%", scale)
           .replace("%%VOCESIZE%%", voce_size)
           .replace("%%VOCELEAD%%", voce_lead)
           .replace("%%VOCEFIT%%", "" if size == DEFAULT_PRINT_SIZE else "\\exlexfitvoce")
           .replace("%%TITLEBLOCK%%", title)
           .replace("%%BODY%%", body)
           .replace("%%COLOPHON%%",
                    colophon_for(L, main_name) if colophon else ""))
    return tex
