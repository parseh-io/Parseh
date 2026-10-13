#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The verb entry a dictionary hit can carry: `hit["vb"]`, a \\vb ready to use.

    import verbs
    verbs.attach(result, "it", "vado a casa", "en")     # lookup.look_up's answer, in place
    verbs.build("it", hit, "vado", "vado a casa", "en")  # one hit -> the entry, or None

    python3 lib/verbs/__init__.py it "vado a casa"       # what each hit would offer

WHAT IT IS FOR.  A dictionary hit for a verb used to be offered to the chunk
editor as a \\dw -- `\\dw{ساختن}{mi-sāzam} to make` -- which is the one thing
a vocabulary line is told never to do with a verb (docs/new-book-prompt.md,
rule 6: "Every verb gets a \\vb"), and which paired the lemma with the
inflected form's sound besides.  The forms a \\vb prints are exactly what a
learner cannot guess and a dictionary CAN say: Wiktionary's conjugation table
is already in dict/<code>.db, one form row per cell with the cell's name in
the note.  So a verb hit now comes back carrying its \\vb, built from those
rows, in every shape a reader might want it:

    hit["vb"] = {
      "tex":   "\\vb{andare}{}{vado}{}{andato}{}{to go (aux. \\pw{essere})}",
      "tex_video": "\\vb{andare}{}{vado}{}{andato}{}{to go (aux. \\pw{essere})}",
      "plain": "andare · pres. vado · p.p. andato · to go (aux. essere)",
      "here":  "vado (andare · pres. vado · p.p. andato · to go (aux. essere))",
      "line":  "pres. vado · p.p. andato · aux. essere",
      "lemma": "andare", "parts": [["andare", ""], ["vado", ""], ["andato", ""]],
      "labels": ["pres.", "p.p."], "extras": ["aux. essere"],
      "meaning": "to go", "reading": "", "notes": [],
      "complete": true, "missing": [], "compound": null}

`tex` goes into a book's vocabulary line, and `tex_video` into a video's,
which may hold the books' macros: it is `tex` with what only a video says
added in the meaning's parenthesis (Persian's colloquial present), its words
bare where a video's are (Arabic), and -- where the chunk's word is none of
the three forms the \\vb prints -- the chunk's own form named after it as the
books name one, `; here \\pw{vint} \\textit{vẽ}`.  `plain` is the lemma's entry
as a video's plain-text line has it, and `here` the same entry hung on the word
the chunk actually has, with that word's own sound where anything says it;
`line` is shown under the hit in the reading panel, and `notes` beside it --
hints that are not missing (Arabic's other masdars).

`compound` IS THE VERB THAT IS MORE THAN ONE WORD, whole: Persian's فکر
کردن, Turkish's teşekkür etmek, Hindi's conjunct काम करना, French's
locution avoir peur -- the four languages whose file writes such a verb as a
\vb and a \bw, where German's aufstehen, English's give up, Chinese's 睡觉
and Japanese's 勉強する are each one entry already and need none of this.  The
hit is the light verb alone -- کردن, "to do" -- and the verb is the pair,
"to think"; so the entry is not that verb and a word beside it but ONE
entry for one verb, and `compound` is that entry, written both ways:

      "compound": {"name": "compound verb", "whole": "فکر کردن",
        "sound": "fekr kardan", "mean": "to think",
        "bw":    "\\bw{فکر}{fekr}{to think}",
        "tex":   "\\vb{کردن}{kardan}{کن}{kon}{کرد}{kard}{}\\bw{فکر}{fekr}{to think}",
        "tex_video": "\\vb{کردن}{kardan}{کن}{kon}{کرد}{kard}{(coll. \\pw{می‌کنم} \\textit{mi-konam})}\\bw{فکر}{fekr}{to think}",
        "plain": "فکر کردن fekr kardan to think (کردن kardan · pres. کن kon · past کرد kard)",
        "complete": true, "missing": []}

`tex` is the one entry a book writes -- the light verb's \vb, its meaning
empty, and the \bw for the carried word run straight onto it with nothing
between them, which is what makes it one entry and not two (docs/lang/fa.md,
tr.md, hi.md) -- and `bw` is that second half alone, for a book that already
has its own \vb to hang it on.  `plain` is the one line a video writes, the
compound said and glossed as a whole with the verb that conjugates in it
after (docs/lang/fa.md's `compounds as فکر کردن fekr kardan to think`).
`missing` NAMES the same thing in prose, and goes on naming it; a recipe
fills `compound` from what the source gave and leaves a piece empty where it
gave none, marking it `complete: false` -- nothing here guesses, here as
everywhere else.  `reading` is the kana a Japanese headword is read with,
which the video's shapes print after it and the book's never do.

    verbs.attach(result, "de", "und stand langsam", "en",
                 sentence="Der Schuster lächelte und stand langsam von seinem Stuhl auf.")

The sentence round the chunk, where the reader sends it (both do), goes to
the recipe as ctx.sentence: a German chunk can hold a verb whose prefix is
in the next one -- that chunk's `stand` is stehen alone, and aufstehen with
its sentence.

WHICH FORMS, AND WHAT ELSE, IS THE LANGUAGE'S BUSINESS and never this file's.
Persian wants the present stem, German the preterite and the auxiliary,
Arabic the masdar and the verb's form number, Japanese the class; Chinese
wants no \\vb at all except for two kinds of verb, and English none for a
modal.  Each language says so in a recipe, lib/verbs/<code>.py, a function
`recipe(ctx)` that reads the entry's rows and returns a Parts, or None for a
hit that is not a verb it can describe.  A language with no recipe offers no
\\vb -- the same way a language with no dictionary offers no lookup -- and a
hit without one is offered as the \\dw it always was.  What IS here is what
every language needs and none should write twice: finding the rows, the
meaning, taking out what LaTeX would read as an instruction, and writing the
four shapes from one description so that they cannot disagree.

NOTHING HERE GUESSES.  A recipe fills a slot from a row the source wrote or
leaves it empty and names it in `missing`; `complete` is false then and the
editor's button says what is left to fill.  A \\vb that looks finished and is
wrong costs more than one that says it is not finished.

Standard library only: the server imports it.
"""
import collections
import copy
import importlib
import importlib.util
import json
import os
import re
import sys
import threading
import traceback
import unicodedata

HERE = os.path.dirname(os.path.realpath(__file__))
LIB = os.path.dirname(HERE)
LANG_DIR = os.path.join(LIB, "lang")
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import languages                                               # noqa: E402
import lookup                                                  # noqa: E402
import translit                                                # noqa: E402
import texwrite                                                # noqa: E402

# ---------------------------------------------------------------- the knobs
# THE MEANING IS ONE LINE OF A VOCABULARY ENTRY, and a Wiktionary sense is
# written for a dictionary page.  Over the verbs of the installed
# dictionaries, the first ranked sense runs past sixty characters for 5935 of
# 47138 Italian verbs and 1634 of 11856 Spanish ones, and carries a
# parenthesis of more than twenty-five for 1711 Italian ones: `piottare` is
# "to go (on a vehicle) at 100 km/h (~62 mph) or beyond".  A qualifier that
# short -- "(transitive)", "(of a liquid)" -- is information a learner uses;
# one that long is a definition, and the gloss already has a line for that.
MEANING_CAP = 60
QUALIFIER_MAX = 25

# How many built entries to keep.  One per (dictionary, entry, word, gloss),
# a few hundred bytes each: a long evening's reading is a few thousand.
CACHE_MAX = 4096

# A TEST HOOK, and the only way to give a language a recipe without a file:
# {code: recipe function, or None for "this language has none"}.  Checked
# before lib/verbs/<code>.py is looked for, so a test can put a throwaway
# recipe in front of a real one and take it away again.  The cache is keyed
# on the function, so nothing built by the one is ever handed out as the
# other's.
RECIPES_OVERRIDE = {}

# ------------------------------------------------------ what a recipe returns
# What a recipe says about one verb.  `parts` is three (form, sound) pairs --
# the forms the language's two \vb labels name, after the lemma -- and a pair
# whose form is blank is not printed at all (the preamble's \ifblank), which
# is how Chinese and a masdar-less Arabic verb leave one out.  `meaning` is
# None for "the core's", which is the first ranked sense, trimmed; a string
# replaces it.  `extras` are what the language adds after the meaning, in one
# parenthesis, and `extras_video` what it adds only in a video's plain line
# (Persian's colloquial present: videos are spoken Tehrani, books are not).
# `missing` names, in words a person reads, what the language needs and the
# data did not have.
#
# `notes` are hints that are NOT missing, and so could not go in `missing`,
# which both editors read as "this slot goes in blank": Arabic lists 2-7
# masdars for 1,122 of its 7,233 verbs and the right one depends on the
# sense (وَصَلَ "to arrive" lists صِلَة before وُصُول), so the slot is filled
# with the first and the rest are a note -- `masdar also: مَقَال maqāl` --
# shown beside the line and never printed in the \vb.  `reading` is how a
# headword is READ where its writing does not say, printed after form 1 in a
# video's line and never in a book's \vb, whose chunk has its kana line:
# docs/lang/ja.md's video verb is `書く かく kaku · stem 書き kaki · …`.
# A reading makes the plain line more than texparse's reading of `tex`, as
# `extras_video` already does; notes are in no shape at all.
Parts = collections.namedtuple(
    "Parts", "parts meaning extras extras_video missing notes reading compound",
    defaults=(None, (), (), (), (), "", None))


class Form(collections.namedtuple("Form", "form note tags roman rowid ipa",
                                  defaults=("",))):
    """One row of the entry's form table.

    `tags` is the note as a set.  getdict.py writes a note two ways: the
    entry's own head and table rows JOIN THEIR TAGS WITH SPACES ("first-person
    present singular"), while a page that is only "first-person singular of
    X" -- a pointer, linked to the first entry with that headword -- joins them
    with commas ("first-person, indicative, present, singular").  Split on
    both, so one set of tags finds either.

    `ipa` is how the source says THIS form, where it says: a French table
    row carries it (prends /pʁɑ̃/) and so does an English page that is only
    "past of go" (went /wɛnt/), and the lemma's pronunciation can give
    neither.  '' where the row has none or the dictionary predates the
    column.  Last, and with a default, so a recipe that builds a Form from
    its own query with five values still builds one.
    """
    __slots__ = ()

    @property
    def own(self):
        """Is this the entry's own row rather than somebody's pointer at it?

        The difference is real and it is measured.  Pointer rows are linked to
        the FIRST entry with the headword they name, so a homograph collects
        its twin's forms: Persian's `present, stem` row روب (of roftan, to
        sweep) is filed under raftan, to go.  Only the entry's own rows are
        certain to be about this entry, and they are the ones with no comma.
        """
        return "," not in self.note


def split_tags(note):
    """A form row's note as a set of tags, whichever way it was joined."""
    return frozenset(t for t in re.split(r"[ ,]+", (note or "").strip()) if t)


def form_rows(conn, eid):
    """One entry's form rows, as Form, in the order the source wrote them --
    what ctx.rows gives for the hit's own entry, for any entry.  The romanised
    and the pronounced columns are read where the dictionary has them."""
    roman = "roman" if lookup._has_col(conn, "roman", "form") else "''"
    ipa = "ipa" if lookup._has_col(conn, "ipa", "form") else "''"
    return [Form(r["form"] or "", r["note"] or "", split_tags(r["note"]),
                 r["roman"] or "", r["rowid"], r["ipa"] or "")
            for r in conn.execute(
                "SELECT rowid, form, note, %s AS roman, %s AS ipa FROM form "
                "WHERE entry_id = ? ORDER BY rowid" % (roman, ipa), (eid,))]


def own_run(rows):
    """The entry's own rows out of its rows (rowid order): the block getdict
    wrote with the entry, and nothing filed after it.

    Form.own -- no comma in the note -- is not enough, and that is measured:
    a pointer page with ONE tag has no comma to give it away, and 3,531
    Japanese verbs carry such rows (書く's rowid 645371 書いた `past`, from
    the 書いた page; 来る kuru's 来った `past`, which is kitaru's).  getdict
    inserts an entry's rows together, headword first, and files the pointer
    pages' rows only after every entry is in: so the entry's own are the
    unbroken run of rowids its rows start with, and everything after a gap
    is somebody else's page pointing here.  A comma ends the run as well,
    for the very last entry in the file, which has no gap before the
    pointers.  (lib/verbs/ja.py and fr.py each wrote this for themselves.)
    """
    out = []
    for i, f in enumerate(rows):
        if f.rowid != rows[0].rowid + i or "," in f.note:
            break
        out.append(f)
    return out


def _tagset(x):
    """What a recipe passed as tags -- a string of them or any collection --
    as a set.  A string is split, not iterated: require="present stem" means
    the two tags, not eleven letters."""
    if x is None:
        return frozenset()
    if isinstance(x, str):
        return split_tags(x)
    return frozenset(x)


# ------------------------------------------------ a word of the language, inside
# A TARGET-LANGUAGE WORD INSIDE AN EXTRA is \pw{...} in a book and bare text in
# a video, and the recipe must not have to write either: it would write the
# TeX, and then the sanitiser -- which takes every backslash and brace out of
# every slot, because texwrite refuses them -- would take its own \pw apart.
# So a recipe marks the word with tl() and only the core ever writes the
# macro, after the text around it has been cleaned.  The marks are private-use
# characters no dictionary holds, taken out of anything that is not a token.
_TL_OPEN, _TL_MID, _TL_SHUT = "\ue000", "\ue001", "\ue002"
_TL_ANY = re.compile("[\ue000-\ue002]")
_TL_RE = re.compile("\ue000([^\ue000-\ue002]*)\ue001([^\ue000-\ue002]*)\ue002")


def tl(form, sound=""):
    """A word of the language, with its sound if it has one, for an extra:
    `"aux. " + tl("essere")` is `aux. \\pw{essere}` in a book and
    `aux. essere` in a video."""
    return "%s%s%s%s%s" % (_TL_OPEN, _TL_ANY.sub("", str(form or "")), _TL_MID,
                           _TL_ANY.sub("", str(sound or "")), _TL_SHUT)


# ------------------------------------------------------------ sanitising
# WHAT LATEX WOULD READ AS AN INSTRUCTION IS TAKEN OUT, NOT ESCAPED.  texwrite
# refuses `$ % & # _ ^ ~ \ { }` in a vocabulary line escaped as well as raw --
# no escape satisfies the PDF, check_batch.py and the reader at once -- and it
# refuses the whole save, not the one word.  Wiktionary's senses carry them:
# Chinese 研發 is "to research and develop; to do R&D", Italian piottare's
# "(~62 mph)", German einüben's "to drill, # to practice".  The set is
# texwrite's own, imported and not restated, so a slot cannot pass here and
# be refused there; so is its test for what is not text at all (a control
# character refuses a save just the same).
_BADTEX = re.compile("[%s]" % re.escape(texwrite.TEX_SPECIALS))


def sanitise(s, strip=True):
    """One slot's text, safe to put in a \\vb: TeX's specials and control
    characters out, TeX's dash ligatures written as the dashes they print,
    whitespace collapsed.

    THE DASHES ARE WRITTEN OUT because the plain line is the TeX line read
    back (see _flatten), and that reading turns `--` into `–` on the way
    (texparse.voc_text), so a sense that kept `--` would make a plain line
    that is not the reading of its own \\vb.

    TWO OF THE SPECIALS ARE WORDS, and they are written as the words: taken
    out, Chinese 研發's "to do R&D" read "to do RD" and a "50%" read "50".
    `&` is "and", `%` is "per cent" (50% -> 50 per cent).
    """
    s = texwrite.NOT_TEXT.sub("", "" if s is None else str(s))
    s = re.sub(r"\s*%", " per cent", s).replace("&", " and ")
    s = _TL_ANY.sub("", _BADTEX.sub("", s))
    s = s.replace("---", "—").replace("--", "–")
    s = re.sub(r"\s+", " ", s)
    return s.strip() if strip else s


_MARKS = {}


def strip_marks(s, ranges):
    """`s` with every character in `ranges` taken out: a regex character
    class body as the registry writes one (fa's `strip`, "\\u064B-\\u0652",
    the harakat), or a languages.Lang, whose own is used.  None takes nothing
    out.  A head row writes its stems vowelled -- کُن, شَو -- and the book's
    \\vb writes them bare."""
    if isinstance(ranges, languages.Lang):
        ranges = ranges.strip_range
    if not ranges or not s:
        return s or ""
    rx = _MARKS.get(ranges)
    if rx is None:
        rx = _MARKS[ranges] = re.compile("[%s]" % ranges)
    return rx.sub("", s)


# ------------------------------------------------------------ the meaning
def _depth0(s, ch):
    """Where `ch` first occurs outside every parenthesis, or -1."""
    depth = 0
    for i, c in enumerate(s):
        if c == "(":
            depth += 1
        elif c == ")":
            depth = max(0, depth - 1)
        elif c == ch and depth == 0:
            return i
    return -1


def _tidy(s):
    """Spaces where a cut left them wrong: none inside a parenthesis's
    edges or before a stop, one between words, none at the ends.  An
    ellipsis keeps the space before it: in "it is necessary to ..., one must
    ..." (Italian occorrere) it stands for a word, and is not a stop."""
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\(\s+", "(", s)
    s = re.sub(r"\s+([),;:]|\.(?!\.))", r"\1", s)
    s = re.sub(r"\(\)", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _unqualified(s):
    """`s` without its long parenthetical qualifiers and cross-references.

    ONLY THE LONG ONES GO.  `(intransitive) to go`, `to dry (of paint)`:
    what is short is a fact about the verb a learner can use.  What is long is
    the definition a dictionary gives beside the equivalent, and the chunk's
    own meaning line already says what the word means here.  A reference to
    the source's page -- بودن's "to be (See the Usage Notes)" -- goes whatever
    its length: it points at a page the reader does not have.
    A parenthesis never closed (a sense cut short by its source) is taken
    from its opening to the end if that is long, and otherwise only the
    bracket goes; a stray closing one goes too.
    """
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == ")":
            i += 1                                 # closes nothing: not text
            continue
        if c != "(":
            out.append(c)
            i += 1
            continue
        depth, j = 0, i
        while j < len(s):
            if s[j] == "(":
                depth += 1
            elif s[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if j >= len(s):                            # never closed
            rest = s[i + 1:]
            if len(rest.strip()) > QUALIFIER_MAX:
                break
            i += 1
            continue
        inner = s[i + 1:j].strip()
        if (len(inner) > QUALIFIER_MAX
                or re.match(r"(?i)see\b", inner)
                or re.search(r"(?i)usage notes?\b", inner)):
            i = j + 1
            continue
        out.append(s[i:j + 1])
        i = j + 1
    return _tidy("".join(out))


# The words a phrase cannot end on.  A cut at the last word that fits can
# leave one hanging: Chinese 上島's first sense came out "to have a mobile
# application’s activity appear in the".
_DANGLING = frozenset(("the", "a", "an", "of", "in", "to", "and", "or", "for",
                       "with", "at", "on"))


def _capped(s, cap):
    """`s` no longer than `cap`, cut where a reader would cut it: after the
    last equivalent that fits (at a comma outside the brackets), else at the
    last word that fits -- never inside a word, and never leaving a
    parenthesis open, or a word the phrase cannot end on (_DANGLING).

    ONLY A CUT BETWEEN WORDS LOSES ITS DANGLING WORDS.  A cut at a comma
    keeps a whole equivalent, and one may end in a preposition that is part
    of it: "to look at, to watch, ..." is cut to "to look at", which is a
    verb, where "to look" is another one."""
    if len(s) <= cap:
        return s
    head = s[:cap + 1]
    cut = -1
    depth = 0
    for i, c in enumerate(head[:cap]):
        if c == "(":
            depth += 1
        elif c == ")":
            depth = max(0, depth - 1)
        elif c == "," and depth == 0 and i >= cap // 4:
            cut = i
    at_comma = cut >= 0
    if cut < 0:
        cut = head.rfind(" ")
        if cut <= 0:
            cut = cap
    s = s[:cut]
    if s.count("(") > s.count(")"):
        s = s[:s.rfind("(")]
    s = s.rstrip(" ,;:")
    if not at_comma:
        words = s.split(" ")
        while len(words) > 1 and words[-1].lower() in _DANGLING:
            words.pop()
        s = " ".join(words).rstrip(" ,;:")
    return s


# The abbreviations a sense ends with, whose stop is part of the word.  Over
# the installed dictionaries' verbs, `etc.` is nearly all of it (50 Italian
# first senses, 34 Japanese, 12 German) and `sth.` most of the rest; a token
# with a stop inside it -- e.g., s.o. -- is one too, and is not listed.
_ABBREV = frozenset(("etc", "sth", "smth", "sb", "smb", "esp", "usu", "cf",
                     "approx", "lit", "fig", "incl", "pl", "sg"))


# A SENSE WRITTEN AS A SENTENCE starts with a capital, and a vocabulary
# line's meaning is not a sentence: the second Arabic قال is "To nap." in
# its source and `to nap` in the \vb, as every other verb's `to go` is.  Of
# the verb entries' first senses (the installed fa, de, hi, ja; the scratch
# builds of ar, fr, tr), Turkish has 173 that open "To" and a small word,
# French 69, Japanese 31, German 21, Arabic 16 (and 3 "Of rain: to pour down"),
# Persian 12, Hindi 7.  Only the `To` of the infinitive and the `Of` of such
# a label are lowered, and only before a word written small: a capital
# after them may be a name's (Arabic's five "To Germanize, to make German")
# or an acronym's, and that sense is left as the source wrote it.
_SENTENCE_TO = re.compile(r"(To|Of) (?=\w)")


def trim_meaning(sense, cap=MEANING_CAP):
    """One ranked sense as the meaning slot of a \\vb.

    The first equivalent the source gives, which is everything before its
    first semicolon (outside the brackets): Persian شدن is "to become; a light
    verb used in a large number of intransitive compound verbs.", and a
    vocabulary line wants the first half.  Then without its long qualifiers
    (_unqualified), then no longer than `cap`, then without the full stop a
    dictionary sentence ends with -- "to take a shower or bath." -- unless
    the stop is an abbreviation's (`etc.`) or an ellipsis, which are text;
    and a sentence's opening `To`/`Of` written small (_SENTENCE_TO).
    """
    s = sanitise(sense)
    k = _depth0(s, ";")
    if k >= 0:
        s = s[:k]
    s = _unqualified(s)
    s = _capped(s, cap)
    s = s.rstrip(" ,;:")
    m = re.search(r"(\S+)\.$", s)
    if m and not s.endswith(".."):
        w = m.group(1).lower().lstrip("(\"'“‘")
        if "." not in w and w not in _ABBREV:
            s = s[:-1]
    s = s.strip()
    m = _SENTENCE_TO.match(s)
    if m and s[m.end()].islower():
        s = s[0].lower() + s[1:]
    return s


def one_equivalent(meaning):
    """The meaning up to its first comma outside the brackets: "to see, to
    look" -> "to see".  Not applied by the core, because the languages
    disagree: docs/lang/es.md's own model entry is `{to do, to make (...)}`,
    while Persian's check_batch warns on "two English equivalents where the
    rule wants one".  A recipe that wants one calls this on ctx.meaning."""
    s = meaning or ""
    k = _depth0(s, ",")
    return s[:k].rstrip() if k >= 0 else s


def gloss_is_en(gloss):
    """Wiktionary's senses are English.  A book glossed in Italian gets no
    meaning at all rather than an English one in an Italian line."""
    return (gloss or "").strip().lower() == "en"


_gloss_is_en = gloss_is_en          # the name the recipes were written with


# -------------------------------------------------------------- the context
class Ctx:
    """Everything a recipe may read about one hit, fetched when it asks.

        ctx.code, ctx.L          the language: its code and registry record
        ctx.conn                 the dictionary: sqlite3, rows by name, read-only
        ctx.hit                  the hit as lookup built it
        ctx.word, ctx.text       the word as the chunk has it, and the chunk
        ctx.sentence             the whole sentence round the chunk, where the
                                 reader sent it ('' where it did not)
        ctx.gloss                what the book or video is glossed in
        ctx.entry                the entry's row: id headword translit ipa
                                 reading pos sense sense_tags head ('' where the
                                 dictionary predates the column)
        ctx.rows                 its form rows, as Form, in the order written
        ctx.own_rows             the ones getdict wrote with the entry (own_run)
        ctx.rows_of(id)          another entry's form rows, the same way
        ctx.other(id)            a Ctx on another entry, for the same word,
                                 chunk, sentence and gloss (or None)
        ctx.head                 entry.head, the head template's facts, as a dict
        ctx.senses               the raw sense lines
        ctx.sense_tags           one set of register tags per raw sense line
        ctx.meaning              the first ranked sense, trimmed ('' unless
                                 the gloss is English)
        ctx.head_sound           the LEMMA's sound: never the reached form's
        ctx.pick(...) / picks(...), ctx.data(), ctx.in_script(s), ctx.bare(s)

    Nothing is read before a recipe asks for it: a recipe that looks at the
    part of speech and answers None has cost one indexed row.
    """

    def __init__(self, code, L, conn, hit, word, text, gloss, entry,
                 sentence=""):
        self.code, self.L, self.conn = code, L, conn
        self.hit, self.word, self.gloss = hit, word, gloss
        self.entry = entry
        self._text = text or ""
        self._sentence = sentence or ""
        self.read_text = False
        self._parent = None                    # the Ctx other() made this from
        self._rows = None
        self._rows_of = {}
        self._head = None

    def _reads_text(self):
        """This answer depends on the chunk: say so here, and to the Ctx this
        one was made from by other(), whose answer it is part of -- the
        cache is told by the Ctx build() made, and a recipe that reads the
        chunk only through another entry's Ctx has read it all the same."""
        c = self
        while c is not None:
            c.read_text = True
            c = c._parent

    @property
    def text(self):
        """The chunk.  READING IT MAKES THE ANSWER DEPEND ON IT, and the cache
        is told: a German `fährt` is `fahren` in one chunk and, with an `ab`
        at the end of the clause, `abfahren` in the next, while every other
        verb is the same entry wherever it is met and is built once."""
        self._reads_text()
        return self._text

    @property
    def sentence(self):
        """The sentence the chunk is a piece of, as the reader sent it ('' if
        it did not).  A CHUNK IS OFTEN LESS THAN A CLAUSE, and German leaves
        what makes a verb at the clause's end: the fixture book's chunk `und
        stand langsam` holds stehen, and its sentence `... und stand langsam
        von seinem Stuhl auf.` holds aufstehen, which is what the \\vb must
        say.  Read like the chunk, and it tells the cache the same way: an
        answer that read it is kept for this chunk AND this sentence."""
        self._reads_text()
        return self._sentence

    @sentence.setter
    def sentence(self, s):
        self._sentence = s or ""

    @property
    def rows(self):
        if self._rows is None:
            self._rows = form_rows(self.conn, self.entry["id"])
        return self._rows

    @property
    def own_rows(self):
        """The entry's own form rows: the run getdict wrote with it, before
        any pointer page's (own_run).  Form.own is left meaning what it
        meant -- no comma in the note -- because recipes were written on it."""
        return own_run(self.rows)

    def rows_of(self, entry_id):
        """Another entry's form rows, as ctx.rows gives this one's: a
        conjunct's light verb (Hindi इंतज़ार करना is करना's table), a
        homograph's table that its twin has not (Turkish yakmak)."""
        if entry_id == self.entry["id"]:
            return self.rows
        got = self._rows_of.get(entry_id)
        if got is None:
            got = self._rows_of[entry_id] = form_rows(self.conn, entry_id)
        return got

    def other(self, entry_id, hit=None):
        """A Ctx on another entry of this dictionary, for the same word,
        chunk, sentence and gloss -- or None where there is no such entry.

        FOR THE VERB THE HIT TURNS OUT TO BE A PIECE OF: the separable verb
        a German finite form belongs to (`stand ... auf` is aufstehen), the
        verb an Italian compound names (alzandosi is alzarsi), a Turkish
        homograph's table.  Its `hit` is that entry's own, carrying the
        lemma's sound the way lookup works it out -- never the finite form's,
        whose entry this is not -- unless one is given.  Its chunk and
        sentence are this one's, and reading them through it tells the cache
        that this answer read them (_reads_text)."""
        row = entry_row(self.conn, entry_id)
        if row is None:
            return None
        if hit is None:
            hit = {"entry": row["id"], "headword": row["headword"],
                   "pos": row["pos"],
                   "said": translit.from_ipa(self.code, row["ipa"] or "")}
        sub = Ctx(self.code, self.L, self.conn, hit, self.word, self._text,
                  self.gloss, row, self._sentence)
        sub._parent = self
        return sub

    @property
    def head(self):
        if self._head is None:
            try:
                d = json.loads(self.entry["head"] or "{}")
            except (ValueError, TypeError):
                d = {}
            self._head = d if isinstance(d, dict) else {}
        return self._head

    @property
    def senses(self):
        return (self.entry["sense"] or "").split("\n")

    @property
    def sense_tags(self):
        tags = (self.entry["sense_tags"] or "").split("\n")
        return [set(t.strip() for t in (tags[i] if i < len(tags) else "").split(",")
                    if t.strip())
                for i in range(len(self.senses))]

    @property
    def meaning(self):
        if not gloss_is_en(self.gloss):
            return ""
        senses = [s for s in (self.hit.get("senses") or []) if (s or "").strip()]
        if not senses:
            # a hit built without its senses (a caller of build() that made
            # its own): rank the entry's, the way lookup does
            ranked = lookup.rank_senses(
                [s for s in self.senses if s.strip()],
                (self.entry["sense_tags"] or "").split("\n"))
            senses = [r[0] for r in ranked]
        return trim_meaning(senses[0]) if senses else ""

    @property
    def head_sound(self):
        """How the lemma is said.  The hit's `translit` is the REACHED form's
        where the source romanised it -- می‌سازم is mi-sāzam -- and slot 1 of a
        \\vb is the infinitive's, sāxtan: pairing the two was the sidebar's
        old bug.  So: what lookup worked out for the lemma, else the
        pronunciation, else the source's romanisation of the headword."""
        h = self.hit
        return (h.get("head_sound") or h.get("said")
                or translit.tidy_roman(self.code, self.entry["translit"] or ""))

    def in_script(self, s):
        """Is every letter of `s` in the language's own script?  Always True
        for a Latin-script language, whose text cannot be told from anything
        else.  A form table carries Latin junk under Persian tags -- بودن has
        `bâš` as a "past stem" -- and a \\vb must not print it as Persian."""
        if self.L.re_chars is None:
            return True
        letters = [ch for ch in s or "" if unicodedata.category(ch)[0] in "LM"]
        return bool(letters) and all(self.L.re_chars.match(ch) for ch in letters)

    def bare(self, s):
        """`s` without the language's marks and without a joiner left at an
        edge: کُن -> کن, and a stem cut from نمی‌کنم is not ‌کن."""
        return lookup._trim(strip_marks(s or "", self.L.strip_range)).strip()

    def picks(self, require=(), forbid=(), exact=None, where=None, own=None,
              script=None):
        """Every form row matching, in the order the source wrote them.

        require   tags every row must have      ("present stem", or a set)
        forbid    tags no row may have          ("archaic dialectal")
        exact     the row's tags, exactly
        where     a function of the Form, for anything else
        own       True: the entry's own rows only; False: pointers only
        script    True: only forms in the language's script (see in_script)
        """
        req, bad = _tagset(require), _tagset(forbid)
        ex = _tagset(exact) if exact is not None else None
        out = []
        for f in self.rows:
            if req and not req <= f.tags:
                continue
            if bad and bad & f.tags:
                continue
            if ex is not None and f.tags != ex:
                continue
            if own is not None and f.own != bool(own):
                continue
            if script and not self.in_script(f.form):
                continue
            if where is not None and not where(f):
                continue
            out.append(f)
        return out

    def pick(self, require=(), forbid=(), exact=None, where=None, own=None,
             script=None):
        """The first form row matching (see picks), or None."""
        got = self.picks(require, forbid, exact, where, own, script)
        return got[0] if got else None

    def data(self):
        """lib/lang/<code>.verbs.json, the language's hand-kept table, as a
        dict: {} where there is none."""
        return _data(self.code)


_DATA = {}


def _data_path(code):
    return os.path.join(LANG_DIR, "%s.verbs.json" % code)


def _data(code):
    """A language's hand-kept verb table, read again when it changes.

    For what no dictionary records: which Hindi verbs take ने in the
    perfective, English's closed list of verbs with a present worth printing.
    Somebody edits it while the server runs, and being told the old one until
    a restart is how a fix looks like it did not work.
    """
    p = _data_path(code)
    stamp = lookup._stamp(p)
    got = _DATA.get(code)
    if got is not None and got[0] == stamp:
        return got[1]
    d = {}
    if stamp is not None:
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            _report(code, "data", "lib/lang/%s.verbs.json could not be read, "
                    "so the recipe is given {}" % code)
            d = {}
    if not isinstance(d, dict):
        d = {}
    _DATA[code] = (stamp, d)
    return d


# ---------------------------------------------------------------- recipes
_RECIPES = {}
_TOLD = set()
_TOLD_LOCK = threading.Lock()


def _report(code, kind, said):
    """A failure, on stderr, ONCE per language and kind -- "import", "data",
    "recipe", "core" -- whichever word it failed on.

    Once, because the reader's look-ahead asks about ten chunks at a time and
    a broken recipe fails on every verb in all of them: the first traceback
    is the useful one and the four hundredth buries it.  Called from inside
    the `except`, so the traceback is the one being handled.
    """
    k = (code, kind)
    with _TOLD_LOCK:
        if k in _TOLD:
            return
        _TOLD.add(k)
    sys.stderr.write("verbs: %s: %s -- answered without the \\vb; said once, "
                     "the next failures of this kind are not\n" % (code, said))
    if sys.exc_info()[0] is not None:
        traceback.print_exc()
    sys.stderr.flush()


def recipe_for(code):
    """This language's recipe function, or None.

    LAZY, AND A MISSING FILE IS AN ANSWER.  The recipe is imported the first
    time a hit of that language asks, so a server reading Persian never loads
    German's; and a language without lib/verbs/<code>.py simply has no \\vb,
    exactly as before any recipe existed.  A recipe that exists and cannot be
    imported is a bug, and is said once, and costs that language its \\vb and
    nothing else.
    """
    code = languages.get_or_default(code).code
    if code in RECIPES_OVERRIDE:
        return RECIPES_OVERRIDE[code]
    if code not in _RECIPES:
        fn = None
        name = "%s.%s" % (__name__, code)
        try:
            mod = importlib.import_module(name)
        except ModuleNotFoundError as e:
            if e.name != name:                 # the recipe is there; its import is not
                _report(code, "import", "lib/verbs/%s.py could not be imported" % code)
        except Exception:
            _report(code, "import", "lib/verbs/%s.py could not be imported" % code)
        else:
            fn = getattr(mod, "recipe", None)
            if not callable(fn):
                fn = None
        _RECIPES[code] = fn
    return _RECIPES[code]


# ------------------------------------------------------------ composition
# The four shapes are written from one list of PIECES -- ("txt", text) and
# ("tl", form, sound) -- so that a book's \vb and a video's line are one
# description rendered twice, and cannot say different things.
def _add_txt(out, t):
    t = sanitise(t, strip=False)
    if not t:
        return
    if out and out[-1][0] == "txt":
        out[-1] = ("txt", re.sub(r"\s+", " ", out[-1][1] + t))
    else:
        out.append(("txt", t))


def _pieces(s):
    """A slot as a recipe wrote it (text with tl() tokens in it) -> pieces,
    cleaned, with no space at either end."""
    s = "" if s is None else str(s)
    out, pos = [], 0
    for m in _TL_RE.finditer(s):
        _add_txt(out, s[pos:m.start()])
        f, snd = sanitise(m.group(1)), sanitise(m.group(2))
        if f:
            out.append(("tl", f, snd))
        pos = m.end()
    _add_txt(out, s[pos:])
    return _ends(out)


def _ends(out):
    if out and out[0][0] == "txt":
        out[0] = ("txt", out[0][1].lstrip())
    if out and out[-1][0] == "txt":
        out[-1] = ("txt", out[-1][1].rstrip())
    return [p for p in out if p[0] != "txt" or p[1]]


def _cat(*lists):
    """Pieces end to end, adjacent text run together -- which is what TeX's
    reader does with them too (texparse keeps literal text in one run until
    a macro), and the flattening below depends on it: two text runs are
    joined with a space, one is not split."""
    out = []
    for lst in lists:
        for p in lst:
            if p[0] == "txt":
                if out and out[-1][0] == "txt":
                    out[-1] = ("txt", out[-1][1] + p[1])
                elif p[1]:
                    out.append(p)
            else:
                out.append(p)
    return out


def _tail_paren(meaning):
    """A plain-text meaning that already ends in a short parenthetical --
    `to wait (for)`, kept by trim_meaning's _unqualified because it is
    short -- split into its base and that parenthetical's insides, or
    `(meaning, None)` where there is nothing to split.

    WITHOUT THIS, THE EXTRAS OPENED A SECOND PARENTHESIS right after the
    first one: German `warten` (an intransitive verb whose object needs
    `auf`) came out `to wait (for) (auf + acc.)`, and Japanese verbs read
    `to come (toward the speaker) (irregular; intr.)` the same way.  Once
    split, _paren below joins the two into one: `to wait (for; auf +
    acc.)`.

    ONLY PLAIN TEXT IS SPLIT.  `meaning` is one piece and it is `txt`: a
    recipe that built its own meaning with a tl() token inside the
    trailing parenthesis (none does, today) keeps that parenthesis of its
    own rather than have this function guess where inside it a `\\pw{}`
    might be cut."""
    if len(meaning) != 1 or meaning[0][0] != "txt":
        return meaning, None
    s = meaning[0][1]
    if not s.endswith(")"):
        return meaning, None
    depth = 0
    for i in range(len(s) - 1, -1, -1):
        if s[i] == ")":
            depth += 1
        elif s[i] == "(":
            depth -= 1
            if depth == 0:
                base, inner = s[:i].rstrip(), s[i + 1:-1].strip()
                if not inner:
                    return meaning, None
                return ([("txt", base)] if base else []), inner
    return meaning, None                            # never balanced: leave it


def _paren(meaning, extras):
    """The meaning slot: the meaning, then the extras in ONE parenthesis
    joined by "; " -- `to drive (er fährt; aux. sein)` -- or the parenthesis
    alone where there is no meaning (a book not glossed in English).  A
    parenthetical the meaning already carries joins that same parenthesis
    rather than opening a second one beside it (_tail_paren)."""
    if not extras:
        return meaning
    meaning, tail = _tail_paren(meaning)
    inner = [("txt", tail)] if tail else []
    for k, e in enumerate(extras):
        inner = _cat(inner, [("txt", "; ")] if (k or tail) else [], e)
    return _cat(meaning, [("txt", " (" if meaning else "(")], inner, [("txt", ")")])


def _tex(pieces):
    out = []
    for p in pieces:
        if p[0] == "txt":
            out.append(p[1])
        else:
            out.append("\\pw{%s}%s" % (p[1], (" \\textit{%s}" % p[2]) if p[2] else ""))
    return "".join(out)


def _runs(pieces):
    """The runs texparse reads out of these pieces' TeX: literal text, the
    word ('fa') and its sound ('em')."""
    out = []
    for p in pieces:
        if p[0] == "txt":
            out.append(("txt", p[1]))
        else:
            out.append(("fa", p[1]))
            if p[2]:
                out.append(("em", p[2]))
    return out


def _flatten(runs):
    """Runs as one line of plain text: texparse.parse_voc's tidying, then
    texparse.voc_text's join, restated.

    A video's vocabulary is plain text, and the one way a book's \\vb has
    ever become a video's is voc_text (it began as the old-video importer's
    tex_text): so a video's line built here must be exactly what voc_text
    would make of the same \\vb, or one verb reads two ways in two readers.
    Its rule is a space between two runs unless the first ends in a space,
    an opening bracket or a slash or the second starts with a stop or a
    slash -- which is why `+\\pw{ने}` reads `+ ने` in a video while
    `aux. \\pw{avere}/\\pw{essere}` reads `avere/essere`, as the PDF prints
    it, and why a composition that simply concatenated strings would
    disagree with it.

    RESTATED, AND HELD TO IT BY A TEST, RATHER THAN CALLED.  The video's line
    is not the reading of `tex`: it carries the video's own extras, which the
    book's \\vb does not, so calling voc_text would mean writing a second \\vb
    only to parse it again.  The runs are built here from the same pieces the
    TeX is written from, which is that round trip without the parser, and the
    test that compares the two is what keeps the restatement honest.
    """
    tidy = [(k, re.sub(r"\s+", " ", t)) for k, t in runs
            if re.sub(r"\s+", "", t or "")]
    out, prev = [], ""
    for _kind, text in tidy:
        if out and not prev.endswith((" ", "(", "‘", "/")) and \
           not text.startswith((" ", ",", ";", ")", ".", "’", ":", "/")):
            out.append(" ")
        out.append(text)
        prev = text
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _pair(x):
    """One of a recipe's three parts as (form, sound): a pair, a bare form,
    a Form row (its form and its source romanisation), or nothing."""
    if x is None:
        return "", ""
    if isinstance(x, Form):
        return x.form, x.roman
    if isinstance(x, str):
        return x, ""
    x = list(x)
    return (x[0] if x else "") or "", (x[1] if len(x) > 1 else "") or ""


def _listed(x):
    if x is None:
        return []
    if isinstance(x, str):
        return [x]
    return list(x)


def _same_word(a, b, L):
    """The same word, as far as a reader can see: case, marks and joiners
    aside.  `Andare` at the head of a sentence is the lemma andare, and a
    video's line need not repeat it."""
    return lookup._fold(a, L) == lookup._fold(b, L)


def _letters(s, L):
    """`s` letter by letter, each with the set of the language's marks that
    sit on it: [(the letter case-folded, frozenset of its marks)].  The
    joiners are not letters."""
    rx = L._strip_re
    out = []
    for ch in s:
        if ch in "\u200c\u200d":
            continue
        if rx is not None and rx.fullmatch(ch):
            if out:
                out[-1][1].add(ch)
            continue
        out.append((ch.casefold(), set()))
    return [(c, frozenset(m)) for c, m in out]


def _spelt_as(word, form, L):
    """Is the chunk's `word` this pair's `form`?  The same letters once the
    language's marks and the joiners are off and the case is folded (as
    lookup reads a word, _fold) -- and no letter marked one way in the one
    and another way in the other.

    THE MARKS COME OFF because a reading edition vowels what the \\vb writes
    bare.  The Persian fixture book's chunk 'وُ کَرَجی بان وُ حَمّال اُفتاد.'
    has اُفتاد, whose ُ is the o of oftād: it IS the past stem افتاد, and
    compared marks and all it was not -- so `here` took lookup's sound for
    it, aftād (Wiktionary's Dari, the one romanisation its two form rows
    carry), beside the entry's own `past افتاد oftād`: one word said two
    ways in one line.
    A MARK THAT DISAGREES STILL COUNTS, because the marks are how the word is
    said.  Arabic يَصِلْ (the jussive, yaṣil), يَصِلَ (the subjunctive,
    yaṣila) and يُكْتَبُ (the passive, yuktabu) are the imperfects يَصِلُ
    yaṣilu and يَكْتُبُ yaktubu once the marks are off, and lookup had each
    one's own sound right (measured on the Arabic scratch build); the pair's
    would have been wrong for all three.  A letter marked in one and bare in
    the other agrees -- a partly vowelled word is the word -- and so does a
    letter whose marks are some of the other's (a shadda without its
    vowel)."""
    a = unicodedata.normalize("NFC", word or "")
    b = unicodedata.normalize("NFC", form or "")
    if not a or lookup._fold(a, L) != lookup._fold(b, L):
        return False
    la, lb = _letters(a, L), _letters(b, L)
    if len(la) != len(lb):
        return True                  # the same letters to lookup, unaligned
    return all(not x or not y or x <= y or y <= x
               for (_c, x), (_d, y) in zip(la, lb))


def compose(code, parts, word="", of_form="", gloss="en", meaning=""):
    """A Parts -> hit["vb"], or None when it names no verb.

    `meaning` is used where the Parts leaves its own as None.  The meaning
    is dropped whatever it is when the gloss is not English.  `of_form` is
    how the chunk's word is said, for `here`: lookup's romanisation of the
    form it reached, '' where it has none or the word was reached through
    another form (attach).  Where the word is the form of pair 2 or 3 and
    that pair has a sound, `here` says the word with the pair's sound
    instead (_spelt_as).
    """
    L = languages.get_or_default(code)
    raw = list(parts.parts or [])[:3]
    pairs = []
    for i in range(3):
        f, s = _pair(raw[i] if i < len(raw) else None)
        f, s = sanitise(f), sanitise(s)
        pairs.append((f, s if f else ""))          # a sound with no form says nothing
    (f1, s1), (f2, s2), (f3, s3) = pairs
    if not f1:
        return None
    lab2, lab3 = (list(L.vb_labels) + ["", ""])[:2]
    m = parts.meaning if parts.meaning is not None else meaning
    if not gloss_is_en(gloss):
        m = ""
    mean = _pieces(m)
    extras = [e for e in (_pieces(x) for x in _listed(parts.extras)) if e]
    extras_v = [e for e in (_pieces(x) for x in _listed(parts.extras_video)) if e]
    reading = sanitise(parts.reading)
    slot = _paren(mean, extras)
    tex = "\\vb{%s}{%s}{%s}{%s}{%s}{%s}{%s}" % (f1, s1, f2, s2, f3, s3, _tex(slot))

    # A VIDEO'S LINE CAN BE WRITTEN BARE where the registry says the language
    # is (`vb_video_bare`): a video's captions are Arabic as it is written,
    # without the harakat, and docs/lang/ar.md's verb line is `أراد arāda
    # (IV) · impf. يريد yurīdu · …`, while the dictionary's forms -- and so
    # the \vb, whose book is vowelled -- carry every mark.  The words of the
    # language lose them (the three forms, the chunk's word, every tl()
    # word); the sounds and the English do not.
    bare = bool(getattr(L, "vb_video_bare", False))

    def video(rs):
        return [(k, strip_marks(t, L) if k == "fa" else t) for k, t in rs] \
            if bare else rs

    # the video's line: the same \vb, read back the way texparse reads it --
    # a pair whose form is blank is not printed (the preamble's \ifblank),
    # and the video's own extras join the book's in the one parenthesis
    runs = [("fa", f1)] + ([("fa", reading)] if reading else []) + [("em", s1)]
    for f, s, lab in ((f2, s2, lab2), (f3, s3, lab3)):
        if f:
            runs += [("txt", " · %s " % lab), ("fa", f), ("em", s)]
    vslot = _paren(mean, extras + extras_v)
    if _tex(vslot).strip():
        runs += [("txt", " · ")] + _runs(vslot)
    plain = _flatten(video(runs))

    # THE BOOK'S \vb, FOR A VIDEO: a video's vocabulary line may hold the books'
    # macros, and the entry that goes into it is the book's own -- with what
    # only a video says added in the meaning's parenthesis (Persian's
    # colloquial present), and its words written bare where a video's are
    # (Arabic).  It is `tex` where a video adds nothing, and it reads back to
    # `plain` (texparse.voc_text), which is what holds the two to each other.
    def vword(f):
        return strip_marks(f, L) if bare else f

    def vpieces(pieces):
        return [p if p[0] == "txt" else (p[0], vword(p[1]), p[2]) for p in pieces]
    vb_video = "\\vb{%s}{%s}{%s}{%s}{%s}{%s}{%s}" % (
        vword(f1), s1, vword(f2), s2, vword(f3), s3, _tex(vpieces(vslot)))

    w, of = sanitise(lookup._bare(word or "", L)), sanitise(of_form)
    if w and not _same_word(w, f1, L):
        # THE WORD'S OWN SOUND FROM THE \vb ITSELF, where the word is one of
        # its forms (_spelt_as), and before lookup's.  The line prints that
        # pair with its sound a few words later, and lookup's is another
        # source's: Persian افتاد's form rows carry Wiktionary's Dari aftād
        # while the entry's literary table says oftād, and `here` read
        # `اُفتاد aftād (افتادن oftādan · pres. افت oft · past افتاد oftād ·
        # to fall)` -- one word said two ways in one line.  So did 77 of the
        # 792 Persian stems looked up as themselves (ایستاد īstād beside
        # `past ایستاد istād`).  Where lookup has none it is the only sound
        # there is: English has no romanised form rows, and `here` read
        # `went (go goʊ · past went wɛnt · …)` where docs/lang/en.md writes
        # `went wɛnt (go …)`.  A pair with no sound says nothing, and a word
        # that is no pair's form (خریدم, 書いた) keeps lookup's sound -- ''
        # where attach found the word through another form (_routed).
        of = next((s for f, s in ((f2, s2), (f3, s3))
                   if f and s and _spelt_as(w, f, L)), "") or of
        here = "%s%s (%s)" % (_flatten(video([("fa", w)])), (" " + of) if of else "",
                              plain)
    else:
        here = plain

    # AND THE CHUNK'S OWN FORM AFTER THE ENTRY, as the books name one: `; here
    # \pw{vint} \textit{vẽ}` (docs/lang/zh.md writes it so; fr.md puts the same
    # note inside the meaning, after its parenthesis, and the two read alike).
    # It goes OUTSIDE the \vb because the description a person adds after it
    # ("past historic") is typed at the end of the line, where the sidebar's
    # entry leaves the caret.  A video's older line hung the form in front and
    # the entry in brackets after it (`here`); the books put the entry first.
    # Only a form that is none of the three the \vb prints is named -- the
    # entry already shows the others, and the ones its parenthesis names
    # (`p.r. \pw{accadde}`), and a bare Arabic word that is letter for letter
    # one of them.
    tex_video = vb_video
    printed = {vword(f) for f in (f1, f2, f3) if f}
    if w and not _same_word(w, f1, L) and vword(w) not in printed \
            and not any(f and _spelt_as(w, f, L) for f, _s in ((f2, s2), (f3, s3))) \
            and not any(p[0] == "tl" and _same_word(w, p[1], L) for p in vslot):
        tex_video += "; here \\pw{%s}%s" % (vword(w), (" \\textit{%s}" % of) if of else "")

    bits = [_flatten([("txt", lab + " "), ("fa", f), ("em", s)])
            for f, s, lab in ((f2, s2, lab2), (f3, s3, lab3)) if f]
    shown = [_flatten(_runs(e)) for e in extras]
    missing = [sanitise(x) for x in _listed(parts.missing) if sanitise(x)]
    compound = _compound(parts.compound, video, pairs, (lab2, lab3), tex)
    if compound:
        compound["tex_video"] = vb_video + compound["bw"]
    notes = [n for n in (_flatten(_runs(_pieces(x))) for x in _listed(parts.notes))
             if n]
    return {"tex": tex, "tex_video": tex_video, "plain": plain, "here": here,
            "line": " · ".join(bits + shown),
            "lemma": f1,
            "parts": [[f, s] for f, s in pairs],
            "labels": [lab2, lab3],
            "extras": shown,
            "meaning": _flatten(_runs(mean)),
            "reading": reading,
            "notes": notes,
            "complete": not missing,
            "missing": missing,
            "compound": compound}


def _compound(given, video, pairs, labels, vb_tex):
    """The verb that is more than one word, as ONE entry and not two.

    A recipe hands over the pieces -- the whole verb and the word the light
    verb carries -- and this writes the entry the conventions ask for, both
    ways, so that the two doors cannot come to disagree about what a compound
    is.  `video` is compose's own, so a language whose video line is written
    bare (Arabic) loses its marks here exactly as it does there.

    THE BOOK'S ENTRY IS ONE ENTRY.  `\vb{کردن}{...}{}\bw{فکر}{fekr}{to
    think}` with NOTHING between the two macros is how docs/lang/fa.md,
    tr.md and hi.md all write a compound, and the reader prints it as one
    run; a `; ` between them would make it two vocabulary entries, a verb
    meaning nothing and a noun beside it, which is exactly what a compound
    is not.

    THE VIDEO'S IS THE COMPOUND ITSELF.  A video's line is plain text with
    no macro to say which word belongs to which, so the compound goes in as
    a whole and is glossed as a whole -- docs/lang/fa.md's `compounds as
    فکر کردن fekr kardan to think` -- with the verb that does the
    conjugating after it, in the brackets that file hangs an entry in.
    """
    c = given if isinstance(given, dict) else None
    if not c:
        return None
    take = lambda k: sanitise((c.get(k) or "").strip())
    word, wsound = take("word"), take("word_sound")
    whole, wsnd, mean = take("whole"), take("whole_sound"), take("mean")
    # what the \bw's third slot holds is the language's business: Persian and
    # Turkish put the compound's meaning there, Hindi the carried noun's own
    # with its gender (docs/lang/hi.md).  Said nothing, it is the compound's.
    wmean = take("word_mean") or mean
    if not (word and whole):
        return None                      # nothing here guesses at the rest
    (f1, s1), (f2, s2), (f3, s3) = pairs
    lab2, lab3 = labels
    inner = [("fa", f1), ("em", s1)]
    for f, s, lab in ((f2, s2, lab2), (f3, s3, lab3)):
        if f:
            inner += [("txt", " · %s " % lab), ("fa", f), ("em", s)]
    runs = [("fa", whole), ("em", wsnd)] + _runs(_pieces(mean)) + \
           [("txt", " (")] + inner + [("txt", ")")]
    bw = "\\bw{%s}{%s}{%s}" % (word, wsound, _tex(_pieces(wmean)))
    return {"name": take("name") or "compound verb",
            "whole": whole, "sound": wsnd, "mean": mean, "word": word,
            "bw": bw, "tex": vb_tex + bw,
            "plain": _flatten(video(runs)),
            # A PIECE THE SOURCE DID NOT GIVE still goes in, empty, so the
            # entry is there to finish by hand -- and the door says so, as it
            # says it of a half-made \vb.
            "complete": bool(wmean),
            "missing": [] if wmean else ["what the compound means"]}


# ------------------------------------------------------------- the entry
def entry_row(conn, eid):
    """The entry's row, every column a recipe may ask for present under its
    name -- '' where this dictionary was built before the column was -- or
    None where there is no such entry."""
    cols = ["id", "headword", "translit",
            "ipa" if lookup._has_col(conn, "ipa") else "'' AS ipa",
            "reading" if lookup._has_col(conn, "reading") else "'' AS reading",
            "pos", "sense",
            "sense_tags" if lookup._has_col(conn, "sense_tags") else "'' AS sense_tags",
            "head" if lookup._has_col(conn, "head") else "'' AS head"]
    return conn.execute("SELECT %s FROM entry WHERE id = ?" % ", ".join(cols),
                        (eid,)).fetchone()


_entry_row = entry_row              # the name the recipes were written with


def _entry_id(conn, hit):
    """Which entry this hit is.

    The hit says, where lookup put its id in (`entry`).  Where it did not --
    an older lookup, a hit a caller made -- it is found by headword and part
    of speech, and a homograph is told apart by its first sense: Persian has
    two رفتن, raftan "to go" and roftan "to sweep", and the headword alone
    would give every one of them the stems of the first.
    """
    eid = hit.get("entry")
    if isinstance(eid, int) and not isinstance(eid, bool):
        return eid
    if isinstance(eid, str) and eid.isdigit():
        return int(eid)
    rows = conn.execute(
        "SELECT id, sense FROM entry WHERE headword = ? AND pos = ? ORDER BY id",
        (hit.get("headword") or "", hit.get("pos") or "")).fetchall()
    if not rows:
        return None
    first = next((s for s in hit.get("senses") or [] if (s or "").strip()), "")
    if len(rows) > 1 and first:
        for r in rows:
            if first in (r["sense"] or "").split("\n"):
                return r["id"]
    return rows[0]["id"]


# ---------------------------------------------------------------- caching
# THE SAME ENTRY IS BUILT AGAIN AND AGAIN, and it is not free.  The reader
# looks ahead ten chunks and asks again as it moves, a page repeats its
# commonest verbs, and the installed dictionaries have no index on
# form(entry_id): reading one verb's table is a scan, 7 ms on Persian's
# 166,810 rows and 61 ms on German's 2,429,661.  So an entry is built once
# per dictionary file, recipe, entry, word, the word's sound and gloss -- the
# word and its sound because the `here` shape names them, the gloss because
# it decides the meaning -- and the chunk and its sentence join the key only
# for a recipe that read them (Ctx.text, Ctx.sentence).
_CACHE = collections.OrderedDict()
_CACHE_LOCK = threading.Lock()
_BY_TEXT = object()            # "this one depends on the chunk: look it up with it"


def clear_cache():
    """Forget every built entry (a test that swaps recipes or rows)."""
    with _CACHE_LOCK:
        _CACHE.clear()


def _cache_get(key, text):
    with _CACHE_LOCK:
        if key not in _CACHE:
            return False, None
        got = _CACHE[key]
        if got is _BY_TEXT:
            k2 = key + (text,)
            if k2 not in _CACHE:
                return False, None
            _CACHE.move_to_end(key)
            key, got = k2, _CACHE[k2]
        _CACHE.move_to_end(key)
        return True, got


def _cache_put(key, text, vb, by_text):
    with _CACHE_LOCK:
        if by_text:
            _CACHE[key] = _BY_TEXT
            _CACHE.move_to_end(key)
            key = key + (text,)
        _CACHE[key] = vb
        _CACHE.move_to_end(key)
        while len(_CACHE) > CACHE_MAX:
            _CACHE.popitem(last=False)


# ----------------------------------------------------------- the two doors
def build(code, hit, word="", text="", gloss="en", sentence="", of_form=None):
    """The \\vb one hit offers (see the module docstring), or None.

    None for everything that is not a verb this language's recipe
    recognises -- which, for a language with no recipe, is everything.  A
    recipe that raises is reported once and the hit simply has no \\vb.
    `sentence` is the sentence the chunk is part of, where the reader sent
    one; `of_form` how the word is said, for `here` (None: the hit's own).
    """
    L = languages.get_or_default(code)
    code = L.code
    fn = recipe_for(code)
    if fn is None or not isinstance(hit, dict) or not hit.get("headword"):
        return None
    conn = lookup._conn(code)
    if conn is None:
        return None
    eid = _entry_id(conn, hit)
    if eid is None:
        return None
    word = lookup._bare(word or "", L)
    gloss = (gloss or "").strip().lower()
    of = (hit.get("of_form") or "") if of_form is None else of_form
    key = (code, lookup._stamp(lookup.path_for(code)),
           lookup._stamp(_data_path(code)), id(fn), eid, word, of, gloss)
    where = (text or "", sentence or "")
    found, vb = _cache_get(key, where)
    if found:
        return copy.deepcopy(vb)
    row = entry_row(conn, eid)
    if row is None:
        return None
    ctx = Ctx(code, L, conn, hit, word, text, gloss, row, sentence)
    vb = None
    try:
        parts = fn(ctx)
        if parts is not None and not isinstance(parts, Parts):
            raise TypeError("recipe(ctx) returned %s, not a verbs.Parts or None"
                            % type(parts).__name__)
    except Exception:
        _report(code, "recipe", "lib/verbs/%s.py failed, first on %s"
                % (code, hit.get("headword")))
        parts = None
    if parts is not None:
        try:
            vb = compose(code, parts, word, of, gloss, ctx.meaning)
            if vb is not None:
                # THE LAST WORD IS THE SAVE'S OWN.  Everything above is meant
                # to make a \vb texwrite accepts; this asks texwrite, so a
                # button in the editor can never offer a line the save then
                # refuses.
                texwrite._check_voc(vb["tex"], "the \\vb built for %s" % vb["lemma"])
        except Exception:
            _report(code, "core", "the \\vb for %s could not be written, or "
                    "texwrite would refuse it" % hit.get("headword"))
            vb = None
    _cache_put(key, where, vb, ctx.read_text)
    return copy.deepcopy(vb)


def _routed(w):
    """Did lookup reach this word's hits through ANOTHER form -- an ending
    taken off (an `affix` route), or a spelling offered with it (`under
    ...`)?  Then the hits' of_form is how that other form is said and not
    how the word is: いらっしゃいます, reached through `polite, -masu taken
    off`, carried the rōmaji of いらっしゃい, and `here` read `いらっしゃいます
    irasshai (いらっしゃる …)`; Persian خوانان, through its -ān, read `xwān
    /xān`.  The word as written, or only without its marks and its capital,
    is the word, and its row's sound is its own.  (lookup's `via` is never
    empty -- a word found as itself says `as written` -- so it is the route's
    kind that tells.)"""
    return w.get("kind") in ("affix", "spoken") or (w.get("via") or "").startswith("under ")


def attach(result, code, text="", gloss="en", sentence=""):
    """Give every verb hit in a lookup.look_up answer its `vb`, in place.

    Returns the answer.  Safe on None (no dictionary) and on an answer with
    no words; a hit its recipe does not recognise, or that fails, is left as
    lookup made it.  NEVER RAISES FOR A RECIPE: the dictionary's answer is the
    feature and the \\vb is an extra on it, so a recipe's bug may cost the
    \\vb and never the lookup.  (serve.py guards the call a second time, for
    a bug in this file.)  `sentence` is the sentence round the chunk, where
    the reader sent it: both do (serve.py _lookup hands it on).
    """
    if not result:
        return result
    for w in result.get("words") or []:
        of = "" if _routed(w) else None
        for h in w.get("hits") or []:
            try:
                vb = build(code, h, w.get("word") or "", text, gloss, sentence, of)
            except Exception:
                _report(languages.get_or_default(code).code, "core",
                        "the \\vb of %s could not be built" % h.get("headword"))
                vb = None
            if vb:
                h["vb"] = vb
            else:
                h.pop("vb", None)
    return result


# ----------------------------------------------------------------- the CLI
def _cli(argv):
    """`python3 lib/verbs/__init__.py <code> <text> [--gloss=it]
    [--sentence=...]` -- each hit of the lookup, and the \\vb it would offer,
    or `no vb`.  The sentence is the one the chunk is part of, as a reader
    sends it.

    Reads and never writes, like lookup.py's own command line, which it
    follows: the quickest way to see what a recipe makes of real rows.
    """
    gloss, sentence = "en", ""
    args = []
    for a in argv[1:]:
        if a.startswith("--gloss="):
            gloss = a.split("=", 1)[1]
        elif a.startswith("--sentence="):
            sentence = a.split("=", 1)[1]
        else:
            args.append(a)
    if len(args) < 2:
        print("usage: python3 lib/verbs/__init__.py <language code> <text> "
              "[--gloss=<code>] [--sentence=<the sentence round it>]")
        return 2
    code, text = args[0], " ".join(args[1:])
    L = languages.get_or_default(code)
    if not lookup.available(L.code):
        print("no dict/%s.db -- build one with: python3 lib/getdict.py %s"
              % (L.code, L.code))
        return 1
    if recipe_for(L.code) is None:
        there = importlib.util.find_spec("%s.%s" % (__name__, L.code)) is not None
        print("(no recipe: lib/verbs/%s.py %s, so no hit gets a \\vb)"
              % (L.code, "did not import -- the traceback is above" if there
                 else "does not exist"))
    r = lookup.look_up(L.code, text)
    attach(r, L.code, text, gloss, sentence)
    for w in r["words"]:
        print("\n%s" % w["word"])
        if not w["hits"]:
            print("    (nothing found)")
        for h in w["hits"]:
            head = h["headword"] + ("  [%s]" % h["pos"] if h.get("pos") else "")
            vb = h.get("vb")
            if not vb:
                print("    %s  no vb" % head)
                continue
            print("    %s" % head)
            for k in ("tex", "plain", "here", "line"):
                print("        %-6s %s" % (k, vb[k]))
            if vb["missing"]:
                print("        missing: %s" % ", ".join(vb["missing"]))
            if vb["notes"]:
                print("        notes: %s" % "; ".join(vb["notes"]))
    return 0


if __name__ == "__main__":
    # THE PACKAGE, NOT THIS COPY OF IT.  Run as a file, this module is
    # __main__, and a recipe's `from verbs import Parts` would load a second
    # copy with a second Parts -- whose instances this copy's isinstance
    # check refuses.  Handing over to the imported package keeps one.
    import verbs as _verbs                                     # noqa: E402
    raise SystemExit(_verbs._cli(sys.argv))
