# SPDX-License-Identifier: GPL-3.0-or-later
"""The studio's prompts in parts a person chooses: what each part is called and
costs, which come ticked, and what a page already uses.

    BOXES / PRESETS / LEVELS / LENGTHS / TYPES   the catalogue, as data
    ticked(ids)                the ids of a request, checked (Refused says what is wrong)
    flags(L, ticked, ...)      what markdown/exlex/PROMPT.md's blocks ask for
    values(L)                  what its placeholders are filled with
    catalog(L, ticked)         every box as the routes answer it, its size measured
    page_uses(markdown)        the boxes and exercise types a page already uses

markdown/exlex/PROMPT.md holds every rule the studio's prompt can teach, each
in a `{{?id}}...{{/id}}` block named by a box; lib/promptkit.py resolves it.
A block is ticked, or it is not: what is not ticked is still named, in the
reserved list at the end of the prompt (the flags `no_<id>`), so that a model
that was not taught a mark does not write it by accident.  The routes are in
server.py; this file is only what they, the tests and the skills read.
"""
import os
import re
import sys
from collections import namedtuple

HERE = os.path.dirname(os.path.realpath(__file__))
EXLEX = os.path.join(os.path.dirname(HERE), "exlex")
LIB = os.path.join(os.path.dirname(os.path.dirname(HERE)), "lib")
for _p in (LIB, EXLEX):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import languages                                                    # noqa: E402
import mdparser                                                     # noqa: E402
import promptkit                                                    # noqa: E402
try:
    import segcolour                                                # noqa: E402
except ImportError:
    # WHY NOT A COPY: the word coloured in parts (`[[ab[cd]{teal}ef]]`) has one scanner, exlex/segcolour.py, which a
    # tree has once the a0.4.3 dialect is merged into it; its grammar written out here would be a second source of one
    # thing.  Without it a page is simply never found to use the box (nor would the parser show such a word).
    segcolour = None


class Refused(ValueError):
    """A request the routes answer 400, in words."""


# --- the boxes -------------------------------------------------------------
# What it says, how it is laid out, extras: the groups the page draws them in.
SAYS, LAID_OUT, EXTRAS, PASTED = "what it says", "how it is laid out", "extras", "a document you paste"
Box = namedtuple("Box", "id group name line need")
# THE ORDER IS THE PAGE'S.  `need` names what a language must have for the box to
# be offered at all: a box it cannot use is hidden (shown()), never merely empty.
BOXES = (
    Box("vocab", SAYS, "vocabulary entries",
        "a headword with its transliteration, origin and meaning", None),
    Box("gloss", SAYS, "glosses",
        "a word followed by its meaning in italics: word = *meaning*", None),
    Box("translit", SAYS, "transliteration on a word or short phrase",
        "a word or short phrase with its transliteration, shown when pointed at", None),
    Box("reading", SAYS, "reading marks",
        "the reading of a word, shown when pointed at", "reading"),
    Box("punct", SAYS, "the target language's own punctuation",
        "its own marks, only inside its own sentences", "punct"),
    Box("rtl", SAYS, "right-to-left sequences",
        "several right-to-left words in one left-to-right line, in the right order", "rtl"),
    Box("blocks", LAID_OUT, "passages and display lines",
        "whole passages and display lines of the language, line breaks, tinted blocks", None),
    Box("latin", LAID_OUT, "Latin blocks",
        "a set-apart paragraph in the prose language, tinted, narrowed or shifted", None),
    Box("forms", LAID_OUT, "wrong and right forms",
        "a wrong form in red (✗) and a right one with a green tick (✅)", None),
    Box("lists", LAID_OUT, "lists", "bullet, numbered and labelled lists", None),
    Box("tables", LAID_OUT, "tables", "tables with a header row", None),
    Box("boxes", LAID_OUT, "highlight boxes", "a tinted box for a rule of thumb or a caveat", None),
    Box("emphasis", LAID_OUT, "bold and italic", "bold and italic words", None),
    Box("notes", LAID_OUT, "footnotes", "notes at the foot of the page, or in a cloud on screen", None),
    Box("links", LAID_OUT, "links", "links to web pages", None),
    Box("colours", LAID_OUT, "colour marks", "a word in colour, to show a contrast", None),
    Box("colourparts", LAID_OUT, "colour inside a word",
        "part of a word in colour, to show its stem and its ending", None),
    Box("math", EXTRAS, "formulas", "formulas, in a line or on their own", None),
    Box("latex", EXTRAS, "LaTeX drawings", "chemistry, plots and diagrams drawn by LaTeX", None),
    Box("exercises", EXTRAS, "exercises", "exercises the learner can answer, of every type", None),
    Box("revise", PASTED, "keep what a pasted document has",
        "the marks, pictures, recordings and links a document you paste already holds", None),
)
BOX_IDS = tuple(b.id for b in BOXES)
BY_ID = {b.id: b for b in BOXES}
# the boxes the exercise dialog leaves to its own parts: the types are its exercises, and
# the mixed-direction rule is always in the prompt of a right-to-left target
NOT_IN_EXERCISES = ("exercises", "rtl")

# --- the presets: the brief's, as data ---------------------------------------------
SHORT = ("gloss", "translit", "lists", "emphasis")
LESSON = SHORT + ("vocab", "tables", "boxes", "notes", "links", "forms")
Preset = namedtuple("Preset", "id name boxes default")
PRESETS = (
    Preset("short", "a short answer", SHORT, False),
    Preset("lesson", "a lesson", LESSON, True),
    Preset("vocabulary", "a vocabulary study",
           ("vocab", "gloss", "translit", "reading", "tables", "lists"), False),
    Preset("exercises", "a lesson with exercises", LESSON + ("exercises",), False),
    Preset("all", "all", BOX_IDS, False),
    Preset("none", "none", (), False),
)
DEFAULT_PRESET = next(p for p in PRESETS if p.default)

# --- level and length: each is copied as ONE line -----------------------------------
LEVELS = (("", "not said", ""),
          ("beginner", "beginner", "Write for a learner at the beginner level."),
          ("lower-intermediate", "lower-intermediate", "Write for a learner at the lower-intermediate level."),
          ("intermediate", "intermediate", "Write for a learner at the intermediate level."),
          ("upper-intermediate", "upper-intermediate", "Write for a learner at the upper-intermediate level."),
          ("advanced", "advanced", "Write for a learner at the advanced level."))
LENGTHS = (("", "not said", ""),
           ("short", "short", "Keep it short: the essentials only."),
           ("page", "about a page", "Make it about a page long."),
           ("exhaustive", "exhaustive", "Be exhaustive: cover everything the subject calls for, and invent nothing."))

# --- the exercise types: the ids are the parser's own words for them ----------------
# markdown/exlex/EXERCISES_PROMPT.md has one block a type, `{{?type_<id, hyphens as underscores>}}`.
Type = namedtuple("Type", "id name line")
TYPES = (
    Type("fill-blanks", "fill in the blanks", "a sentence with blanks, filled from the answers and distractors"),
    Type("flashcard", "flashcard", "a card with a front and a back: words, opposites, or any content"),
    Type("order-sentences", "put in order", "sentences to put in the right order"),
    Type("match-translations", "match translations", "pairs of a word and its translation"),
    Type("match-opposites", "match opposites", "pairs of a word and its opposite"),
    Type("match-definitions", "match definitions", "pairs of a word and its definition"),
    Type("yes-no", "yes or no", "statements to answer yes or no, or true or false"),
    Type("single-choice", "single choice", "one correct answer among several"),
    Type("construct-sentence", "build the sentence", "chunks to arrange into a sentence"),
    Type("incorrect-part", "find the mistake", "the part of a sentence that is wrong"),
    Type("choose-all", "choose all that apply", "every correct answer among several"),
    Type("odd-one-out", "odd one out", "the item that does not belong"),
    Type("follow-up", "follow-up questions", "a chain of exercises answered one after the other"),
)
TYPE_IDS = tuple(t.id for t in TYPES)
# the parser's second spelling of a type the prompt teaches once
TYPE_ALIASES = {"true-false": "yes-no"}
# the types whose rows are `left => right`
PAIRS = ("match-translations", "match-opposites", "match-definitions", "yes-no")


def type_flag(type_id):
    return "type_" + type_id.replace("-", "_")


# --- what a language can use -----------------------------------------------------
def shown(box, L):
    """Whether a language is offered this box: a reading only where it has one, its
    own punctuation only where its script has some, the mixed-direction rule only
    for a right-to-left target."""
    return {None: True, "reading": L.reading, "punct": bool(L.chars), "rtl": L.rtl}[box.need]


def shown_ids(L, exercising=False):
    return {b.id for b in BOXES if shown(b, L) and not (exercising and b.id in NOT_IN_EXERCISES)}


# THE MARKS A SCRIPT HAS OF ITS OWN, by the registry's `script`: what the punctuation box and the
# reserved list name.  A script nobody wrote a row for says so in general words, so that a language a
# person adds still gets a true sentence.
OWN_MARKS = {
    "arabic": "the Arabic comma `،`, semicolon `؛` and question mark `؟`",
    "japanese": "the Japanese `。`, `、` and `「」`",
    "cjk": "the Chinese `。`, `，`, `、`, `；`, `：` and `？`",
    "devanagari": "the Devanagari danda `।`",
}
OWN_MARKS_ANY = "the marks its script has of its own"
# the same marks, for reading a page: is any of them in it?
OWN_CHARS = {"arabic": "،؛؟", "japanese": "。、「」",
             "cjk": "。，、；：？！", "devanagari": "।॥"}


def latex_themes():
    """The themes this machine has, as a prompt says them: the name, and for each package it adds to the default's
    -- the ones it ticks and the ones its own lines load -- what the package is for, so that a drawing's commands can
    be matched to the theme that has them.  Nothing at all if the store cannot be read: the rule still stands."""
    try:
        import latexthemes
        found = latexthemes.themes()
        base = set(next((t["packages"] for t in found if t["name"] == latexthemes.DEFAULT), ()))
    except Exception:                                       # noqa: BLE001
        return "`default`"
    out = []
    for t in found:
        extra = []
        for p in latexthemes.uses(t):
            if p in base:
                continue
            what = str(latexthemes.PACKAGES[p]["what"]).split(". ")[0].rstrip(".")
            if what[1:2].islower():
                what = what[:1].lower() + what[1:]
            extra.append("%s — %s" % (p, what))
        extra += latexthemes.other_packages(t)
        said = "adds %s" % "; ".join(extra) if extra else ""
        if t.get("languages"):
            said += ("; and " if said else "") + "sets words in the languages Parseh teaches"
        out.append("`%s`%s" % (t["name"], " (%s)" % said if said else ""))
    return ", ".join(out)


def values(L):
    """The placeholders of the studio's prompt that are not the kit's own."""
    return {"OWN_MARKS": OWN_MARKS.get(L.script, OWN_MARKS_ANY) if L.chars else "",
            "ALT_FONT": L.fonts.get("alt_key") or "",
            "LATEX_THEMES": latex_themes()}


def exercise_blocks():
    """The section of EXERCISES_PROMPT.md that the exercises box of the studio's prompt shares with the
    exercise prompt: what an exercise is, per type.  Kept as the marked text it is, for the kit to fill."""
    with open(os.path.join(EXLEX, "EXERCISES_PROMPT.md"), encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"\{\{\?exercise_blocks\}\}(.*)\{\{/exercise_blocks\}\}", text, re.S)
    if not m:
        raise promptkit.PromptError("EXERCISES_PROMPT.md has lost its exercise_blocks section")
    return m.group(1).strip()


def includes():
    return {"EXERCISE_BLOCKS": exercise_blocks}


# where the reserved list begins in the instructions of the prompt: what is before it is the rules and
# the boxes ticked, what is after it the marks the studio reads (PROMPT.md's last section)
RESERVED = "**Reserved marks.**"


def split_reserved(instructions):
    """(the rules and boxes, the reserved list) of a studio prompt's instructions."""
    at = instructions.index(RESERVED)
    return instructions[:at], instructions[at:]


# --- what a request may say -------------------------------------------------------
def _ids(given, known, what):
    if given is None:
        return None
    if isinstance(given, str):
        given = [x for x in given.split(",") if x.strip()]
    if not isinstance(given, (list, tuple, set)):
        raise Refused("%s must be a list" % what)
    given = [str(x).strip() for x in given]
    wrong = [x for x in given if x not in known]
    if wrong:
        raise Refused("%s is not %s (they are: %s)" % (", ".join(repr(x) for x in wrong), what,
                                                        ", ".join(known)))
    return [x for x in known if x in given]


def ticked(given):
    """The boxes a request ticks, in the page's order: None is the default preset, an empty list none;
    an id that is no box's is refused."""
    got = _ids(given, BOX_IDS, "a box")
    return list(DEFAULT_PRESET.boxes) if got is None else got


def ticked_types(given, fallback=TYPE_IDS):
    got = _ids(given, TYPE_IDS, "an exercise type")
    return list(fallback) if got is None else got


def level_line(level):
    row = next((r for r in LEVELS if r[0] == (level or "")), None)
    if row is None:
        raise Refused("%r is not a level (they are: %s)" % (level, ", ".join(repr(r[0]) for r in LEVELS)))
    return row[2]


def length_line(length):
    row = next((r for r in LENGTHS if r[0] == (length or "")), None)
    if row is None:
        raise Refused("%r is not a length (they are: %s)" % (length, ", ".join(repr(r[0]) for r in LENGTHS)))
    return row[2]


def level_length(level, length):
    """The two lines a request adds after the contract; a choice left as `not said` adds none."""
    return "\n\n".join(x for x in (level_line(level), length_line(length)) if x)


# --- what the prompt's blocks ask for ------------------------------------------------
def flags(L, on, types=None, exercising=False):
    """Every flag markdown/exlex/PROMPT.md (and EXERCISES_PROMPT.md, which it shares a section with)
    uses.  A box's own id is true where it is ticked and offered; `no_<id>` is its opposite, which is
    what the reserved list asks for; `lang_*` say what the language is; `authoring` is the studio's
    own prompt against the exercise prompt, which shares its rules but not its task."""
    on = set(on) & shown_ids(L, exercising)
    out = {}
    for b in BOXES:
        out[b.id] = b.id in on
        out["no_" + b.id] = b.id not in on
    types = set(TYPE_IDS if types is None else types)
    for t in TYPE_IDS:
        out[type_flag(t)] = t in types
    out.update({
        "type_pairs": bool(types & set(PAIRS)),
        "exercise_blocks": True,
        "authoring": not exercising, "exercising": exercising,
        "lang_own_script": bool(L.chars), "lang_latin_script": not L.chars,
        "lang_reading": bool(L.reading), "lang_vertical": bool(L.vertical),
        "lang_alt_font": bool(L.fonts.get("alt_key")), "lang_rtl": bool(L.rtl),
        "lang_arabic_script": L.script == "arabic", "lang_other_script": L.script != "arabic"})
    return out


def has_box_marks(text):
    """Whether a person's own text carries the studio's blocks -- `{{?id}}` of a box, or of its `no_<id>`
    -- so that the boxes ticked apply to it; a text with none is copied whole, and the boxes cannot
    change it (the page greys them, and says why)."""
    marks = set(BOX_IDS) | {"no_" + b for b in BOX_IDS}
    return bool(set(re.findall(r"\{\{\?(\w+)\}\}", text or "")) & marks)


def legacy_text(L):
    """The prompt as a page of before the boxes knew it, one text: every box this language is offered,
    then the answer contract.  A person's own prompt of that time was written over it and is kept
    whole, so this is what such a page shows as the default."""
    a = promptkit.assemble("studio-doc", L, flags=flags(L, BOX_IDS), values=values(L), includes=includes())
    return (a.instructions + "\n\n" + a.contract).strip() + "\n"


def dialect_text(L, on, types=None, options=None):
    """What the exercise prompt teaches of the page's dialect: the studio's rules, only the ticked boxes
    and the reserved list, without the task, the front matter or the structure of a whole document.
    `options` is the scheme of the transliteration the request chose (lib/promptkit.py OPTIONS)."""
    return promptkit.assemble("studio-doc", L, flags=flags(L, on, types, exercising=True), values=values(L),
                              includes=includes(), options=options).instructions


# --- sizes ---------------------------------------------------------------------------
def tokens(text):
    """A chatbot's count, roughly (brief 3.5): about 4 characters a token in Latin script, about 2 in
    Arabic script, CJK and Devanagari."""
    wide = sum(1 for c in text if "؀" <= c <= "ۿ" or "ݐ" <= c <= "ݿ"
               or "ﭐ" <= c <= "﻿" or "ऀ" <= c <= "ॿ"
               or "　" <= c <= "鿿" or "豈" <= c <= "￯")
    return int((len(text) - wide) / 4 + wide / 2 + 0.5)


def size(text):
    return {"chars": len(text), "tokens": tokens(text)}


def _studio_chars(L, on):
    return len(promptkit.assemble("studio-doc", L, flags=flags(L, on), values=values(L), includes=includes(),
                                  extras=[promptkit.language_text("studio-doc", L)]).text)


def catalog(L, on, exercising=False):
    """Every box as the routes answer it: the id, its name, its group, one plain line, its size for this
    language, whether this language is offered it, and whether this request ticks it.  A box's size is
    what ticking it adds to a prompt with nothing else ticked (the sum of the boxes is a little under the
    prompt: what two features say to each other is only there when both are ticked)."""
    out, here = [], shown_ids(L, exercising)
    if exercising:
        bare = len(dialect_text(L, ()))
    else:
        bare = _studio_chars(L, ())
    for b in BOXES:
        offered = b.id in here
        if not offered:
            chars = 0
        elif exercising:
            chars = len(dialect_text(L, (b.id,))) - bare
        else:
            chars = _studio_chars(L, (b.id,)) - bare
        out.append({"id": b.id, "name": b.name, "group": b.group, "line": b.line, "chars": chars,
                    "shown": offered, "on": offered and b.id in on})
    return out


def types_catalog(L, on):
    """The exercise types, each with the size ticking it adds to an exercise prompt with none ticked."""
    out = []
    bare = len(_exercise_text(L, ()))
    for t in TYPES:
        out.append({"id": t.id, "name": t.name, "line": t.line,
                    "chars": len(_exercise_text(L, (t.id,))) - bare, "on": t.id in on})
    return out


def _exercise_text(L, types):
    return promptkit.assemble("studio-exercises", L, flags=flags(L, (), types, exercising=True)).instructions


def presets():
    return [{"id": p.id, "name": p.name, "boxes": list(p.boxes), **({"default": True} if p.default else {})}
            for p in PRESETS]


def levels():
    return [{"id": i, "name": n} for i, n, _ in LEVELS]


def lengths():
    return [{"id": i, "name": n} for i, n, _ in LENGTHS]


# --- what a page already uses -----------------------------------------------------------
_COLOURS = r"(?:crimson|indigo|teal|violet|amber|#[0-9A-Fa-f]{6})"
# `\]\{` opens the braces of a mark; the words after it say which mark
_USES = (
    ("colours", re.compile(r"\]\{\s*" + _COLOURS + r"\b", re.I)),
    ("translit", re.compile(r"\]\{[^{}]*\btranslit:")),
    ("reading", re.compile(r"\]\{[^{}]*\b(?:kana|reading):")),
    ("latin", re.compile(r"\]\{\s*(?:la|ltr)\b")),
    ("gloss", re.compile(r"\S\s=\s\*[^*]+\*")),
    ("forms", re.compile("[✗❌✅]")),
    ("links", re.compile(r"\]\(\s*(?:https?://|mailto:)")),
    ("emphasis", re.compile(r"\*\*[^*\s][^*]*\*\*|(?<![*\w])\*[^*\s][^*]*\*")),
    ("math", re.compile(r"\]\{\s*math\s*\}")),
    # a mark, or a drawing's fence at the head of a line of a field (an exercise's prompt written `|`, a card's field)
    ("latex", re.compile(r"\]\{\s*latex\b|(?:^|⏎|\n)\s*:{4,}latex\b")),
    ("revise", re.compile(r"\]\(\s*doc:")),
)


def page_uses(markdown):
    """(boxes, types) a page already uses -- the boxes of the dialect its text is written in, the
    exercise types it already holds -- read with the parser, so that the exercise prompt teaches what
    the page needs and the person ticks the rest.  -> ([box ids in the page's order], [type ids])"""
    fm, blocks = mdparser.parse(markdown)
    L = languages.get_or_default(fm.get("target"))
    found, kinds, texts = set(), [], []

    def walk(items):
        for b in items:
            t = b["type"]
            if t in ("para", "section", "subsection"):
                texts.append(b["text"])
            elif t == "voce":
                found.add("vocab")
                texts.append(b.get("fa", ""))
                if b.get("fa_segments"):
                    # a headword coloured in parts reaches the block already flattened, its pieces beside it
                    found.add("colourparts")
            elif t in ("list", "enum"):
                found.add("lists")
                texts.extend(x for _, x in b["items"])
            elif t == "table":
                found.add("tables")
                texts.extend(list(b["header"]) + [c for row in b["rows"] for c in row])
            elif t == "box":
                found.add("boxes")
                walk(b["blocks"])
            elif t == "math":
                found.add("math")
            elif t == "latex":
                found.add("latex")
            elif t in ("image", "audio", "video"):
                found.add("revise")
            elif t == "exercise":
                kinds.append(TYPE_ALIASES.get(b["subtype"], b["subtype"]))
                texts.extend(b["fields"].values())
                texts.extend(str(v) for item in b["items"] for v in item.values())
                # a follow-up's steps are exercises of their own: their types, their marks and their drawings count
                walk(b.get("steps") or [])

    walk(blocks)
    if fm.get("_footnotes"):
        found.add("notes")
    text = "\n".join(str(x) for x in texts)
    if "^[" in text:
        found.add("notes")
    runs = bool(segcolour and next(segcolour.find_runs(text), None))
    if runs:
        found.add("colourparts")
    for box, pattern in _USES:
        # THE PIECES OF A COLOURED WORD ARE NOT A COLOUR MARK: `[ت]{crimson}` inside `[[…]]` is the other box's
        # business, so the colours box reads the page with each such word taken for the plain word it is
        if pattern.search(segcolour.flatten(text) if runs and box == "colours" else text):
            found.add(box)
    mark = r"\]\{\s*(?:tl|%s)\b" % re.escape(L.code)
    if L.chars:
        # a language with a script of its own: a run marked `{tl}` holds a Latin word, which the box teaches
        wrote = re.search(mark, text)
    else:
        # a Latin-script target marks EVERY run (taught to it always): only a block, a tint or a line break is the box's
        alone = re.compile(r"\[[^\[\]]+\]\{\s*(?:tl|%s)\b[^{}]*\}" % re.escape(L.code))
        wrote = re.search(mark + r"[^{}]*\b(?:bg|font|vertical)\b", text) \
            or any(b["type"] == "para" and alone.fullmatch(b["text"].strip()) for b in blocks)
    if wrote or "⏎" in text:
        found.add("blocks")
    if L.chars and any(c in text for c in OWN_CHARS.get(L.script, "")):
        found.add("punct")
    if any(True for _ in mdparser.media_refs(text)):
        found.add("revise")
    used_types = [t for t in TYPE_IDS if t in kinds]
    return [b for b in BOX_IDS if b in found and b in shown_ids(L, True)], used_types
