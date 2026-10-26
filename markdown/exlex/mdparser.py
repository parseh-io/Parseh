# SPDX-License-Identifier: GPL-3.0-or-later
"""mdparser — parse the exlex markdown dialect into a list of blocks.

The dialect is deliberately small; README.md documents it in full under
"The markdown dialect (authoritative)".
Block model: a list of dicts, each {'type': ..., **payload}.  All text
payloads are RAW markdown strings; inline conversion to TeX happens in
texgen.inline().  Keeping parse and TeX generation separate makes both
sides testable on their own.
"""
import math
import re
import sys
import textwrap
from pathlib import Path

# The language registry lives in the toolbox's lib/, two levels up from
# exlex/; the parser needs it for one decision only -- which headings are
# lemma entries -- but that decision has to know the document's target
# language before the first heading is read.
_LIB = Path(__file__).resolve().parent.parent.parent / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
import languages  # noqa: E402
# the latex block's fence, its themes' names and its layout words: lib's, so that
# what may not import the studio (lib/offline.py, a theme's rename) reads the
# same fence the pages are drawn from
import latexthemes  # noqa: E402
# the mark grammar (`{teal kana:… translit:…}`) is texgen's; the parser
# reads it in one place only, the headword of a lemma heading
from texgen import (parse_mark_fields, LA_RE, tl_re,  # noqa: E402
                    is_fa_only_paragraph, _is_pure_fa_paragraph,
                    set_target, cur_lang, spread_slots, is_target_line,
                    SLOT_RE, SLOT_SPLIT_RE)
from segcolour import parse_at as parse_segmented  # noqa: E402

# `lang:` is the prose language (hyphenation); `target:` the language being
# learned -- a registry code, Persian when absent (docs/languages.md, 5).
FM_KEYS = {"title", "subtitle", "note", "lang", "target"}

# The line under a table's header: a cell of dashes each, as in GFM -- ONE
# dash is enough (`|-|-|`, `:-:`); asking for two turned a table written
# that way into a paragraph of pipes.  The parser reads it on the line
# right after a header only, so a body row whose cells are nothing but `-`
# or `--` (the dialect's empty cell, drawn as a dash) is never taken for it.
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")

# `[^id]: text` — a footnote definition line.  Definitions are collected
# out of the block stream and handed to the renderers through the front
# matter under the private key "_footnotes"; the reference `[^id]` stays
# inline and is resolved there (see texgen.inline).
_FOOTNOTE_DEF = re.compile(r"^\[\^([^\]\s]+)\]:\s*(.*)$")

# `![caption](images/file.png){width=60 align=center offset=-10}` — an
# image on a line of its own (added by the human in the studio, never by
# the LLM).  The attribute block is optional; width and offset are
# percentages of the text-column width, align is left|center|right.
IMAGE_RE = re.compile(
    r"^!\[([^\[\]]*)\]\(\s*([^()\s]+)\s*\)(?:\{([^{}]*)\})?$")
IMAGE_PATH_RE = re.compile(r"^images/[A-Za-z0-9][A-Za-z0-9._\-]*$")
IMAGE_DEFAULTS = {"width": 60, "align": "left", "offset": 0}

# `![caption](audio/word.mp3){width=60 start=1:05.2 end=1:09}` — a
# recording, written exactly like a picture (so IMAGE_RE finds it, and it
# is laid out and counted like one) but with its path under audio/.  The
# formats are lib/audiofile.py's; the list is copied here so exlex stays
# usable on its own, and tests/test_audio_dialect.py holds the two together.
AUDIO_EXTS = ("mp3", "m4a", "aac", "ogg", "oga", "opus", "wav", "flac", "webm")
AUDIO_PATH_RE = re.compile(
    r"^audio/[A-Za-z0-9][A-Za-z0-9._\-]*\.(?:%s)$" % "|".join(AUDIO_EXTS), re.I)
AUDIO_FIELD_ERROR = "%s must name a file under audio/ (e.g. audio/word.mp3)"
IMAGE_FIELD_ERROR = "%s must name a file under images/ (e.g. images/map.png)"

# Every exercise but a flashcard may carry a picture with its question and
# another shown once it has been answered.  A flashcard's own pictures are
# its sides' (front-image, back-image), so it is told rather than ignored.
EXERCISE_IMAGE_FIELDS = ("image", "image-answer")

# and it may carry the layout a figure line carries, in the same words:
# `image: images/map.png {width=50 align=center}`.  Left out, a picture is
# drawn as a figure written without them is -- 60% of the column, on the left
EXERCISE_IMAGE_VALUE_RE = re.compile(
    r"^(images/[A-Za-z0-9][A-Za-z0-9._\-]*)\s*(?:\{([^{}]*)\})?$")

# A RECORDING IS WRITTEN EXACTLY AS A PICTURE IS, which is this dialect's
# rule for recordings everywhere (a recording line is a picture line whose
# path is under audio/): `audio: audio/question.mp3 {start=1:05.2 end=1:09}`.
# The question's recording and the answer's are the picture pair's twins,
# field for field -- shown in the same two places, held back on the same
# rule, copied into a deck by the same walk.  A flashcard's own recordings
# are its sides' (front-audio, back-audio), so it is told rather than ignored.
EXERCISE_AUDIO_FIELDS = ("audio", "audio-answer")
EXERCISE_AUDIO_VALUE_RE = re.compile(
    r"^(audio/[A-Za-z0-9][A-Za-z0-9._\-]*\.(?:%s))\s*(?:\{([^{}]*)\})?$"
    % "|".join(AUDIO_EXTS), re.I)


def exercise_image(value):
    """`images/map.png {width=50 align=center}` -> {path, width, align},
    or None when the field does not name a picture this dialect takes."""
    m = EXERCISE_IMAGE_VALUE_RE.match((value or "").strip())
    if not m:
        return None
    attrs = parse_image_attrs(m.group(2) or "")
    return {"path": m.group(1), "width": attrs["width"], "align": attrs["align"]}


def exercise_audio(value):
    """`audio/word.mp3 {width=40 start=1:05.2 end=1:09}` -> {path, width,
    align, start, end}, or None where the field names no recording.

    The width and the side are the picture's, read by the same parser; the
    clip is the recording line's, and a player laid out with one plays that
    stretch and no more."""
    m = EXERCISE_AUDIO_VALUE_RE.match((value or "").strip())
    if not m:
        return None
    attrs = parse_image_attrs(m.group(2) or "")
    return {"path": m.group(1), "width": attrs["width"], "align": attrs["align"],
            "start": attrs["start"], "end": attrs["end"]}

# WHICH FILES A MARKDOWN NAMES -- the one answer the studio (store: what a
# document adopts from the clip tray, lists as used, zips and unzips) and the
# decks (what an exercise brings in, warns of, exports) both go by.  A name
# under images/ or audio/, anywhere in the text: a line of its own, a card's
# front-image or back-audio field, a jolly field, a footnote.  Both edges
# belong to the match: myimages/x.png, a web address's .../images/x.png and
# images/x.png2 name other things.
MEDIA_REF_RE = re.compile(
    r"(?<![A-Za-z0-9._/\-])(images|audio)/([A-Za-z0-9][A-Za-z0-9._\-]*)(?![A-Za-z0-9._\-])")


def media_refs(text):
    """(kind, name, start, end) of each picture or recording `text` names,
    kind "images" or "audio", start..end the span of the name alone.

    A name with no extension is a word, not a file ("an audio/video lesson"),
    and a full stop after a name ends the sentence the name is in.  Whether
    the name is one a store may hold (a lower-case PNG, an MP3) is the
    store's to say: this is what the text names."""
    for m in MEDIA_REF_RE.finditer(text or ""):
        name = m.group(2).rstrip(".")
        if "." in name:
            yield m.group(1), name, m.start(2), m.start(2) + len(name)


def media_names(texts):
    """The distinct (kind, name) the texts name, in the order named."""
    out = []
    for text in texts:
        for kind, name, _start, _end in media_refs(text):
            if (kind, name) not in out:
                out.append((kind, name))
    return out


def rename_media_refs(text, renamed):
    """`text` with the names `renamed` maps ((kind, name) -> new name)
    written anew where they are named: only the name, only where it is a
    whole reference (media_refs), so images/cat.png never becomes
    myimages/cat-2.png -- and all in one pass, so a name given to one file
    is never taken for the old name of another."""
    parts, at = [], 0
    for kind, name, start, end in media_refs(text):
        new = renamed.get((kind, name))
        if new and new != name:
            parts += [text[at:start], new]
            at = end
    return "".join(parts) + text[at:] if parts else text

# `@[caption](youtube url or id){width=70 align=center start=1:30 end=2:10}`
# — an embedded YouTube video on its own line, laid out exactly like an
# image; start/end clip the playback window.
VIDEO_RE = re.compile(
    r"^@\[([^\[\]]*)\]\(\s*([^()\s]+)\s*\)(?:\{([^{}]*)\})?$")
YT_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:[^()\s]*&)?v=|shorts/|embed/|live/)"
    r"|youtu\.be/)([A-Za-z0-9_\-]{11})|^([A-Za-z0-9_\-]{11})$")

# Interactive exercises use one fenced container and four primitives.  The
# subtype remains explicit for pedagogy, while parsing/rendering/correction
# can be shared.  The body deliberately resembles ordinary Markdown: scalar
# fields are ``name: value`` and answer rows are bullets.
EXERCISE_TYPES = {
    "fill-blanks": ("placement", "fill"),
    "flashcard": ("flashcard", "card"),
    "order-sentences": ("placement", "order"),
    "match-translations": ("matching", "pairs"),
    "match-opposites": ("matching", "pairs"),
    "match-definitions": ("matching", "pairs"),
    "yes-no": ("choice", "boolean"),
    "true-false": ("choice", "boolean"),
    "single-choice": ("choice", "single"),
    "construct-sentence": ("placement", "order"),
    "incorrect-part": ("choice", "single"),
    "choose-all": ("choice", "multiple"),
    "odd-one-out": ("choice", "single"),
    # the fourteenth (a0.5.4): a CHAIN, a run of exercises answered one after the other
    "follow-up": ("chain", "steps"),
}
EXERCISE_OPEN_RE = re.compile(r"^:::exercise(?:\s+([a-z][a-z0-9-]*))?\s*$", re.I)

# A STEP OF A FOLLOW-UP IS AN EXERCISE WRITTEN ONE FENCE DEEPER.  The dialect's one rule for a block inside a block, the
# one `::::latex` inside an exercise already follows, is ONE COLON MORE THAN THE FENCE AROUND IT: a follow-up is
# `:::exercise follow-up` … `:::`, its steps `::::exercise <type>` … `::::`, and inside a step every fence has one more
# colon than it would at the top level (a drawing is `:::::latex` … `:::::`).  A step is read by writing it out one
# colon shallower -- _denest -- and handing it to parse_exercise as the exercise it would be on its own: nothing in
# what a step may hold is written twice, and its `source` is the exercise as it reads at the top level.
STEP_OPEN_RE = re.compile(r"^::::exercise(?:\s+([a-z][a-z0-9-]*))?\s*$", re.I)
STEP_CLOSE = "::::"
_FENCE_LINE_RE = re.compile(r"^(\s*)(:{4,})(?=\s*$|[A-Za-z])")


def nest_step(source):
    """An exercise as it reads on its own -> the same as a step of a follow-up: one colon more on every fence line (the
    opening and closing lines, and a drawing's).  What _denest undoes."""
    return "\n".join(re.sub(r"^(\s*)(:{3,})(?=\s*$|[A-Za-z])", lambda m: m.group(1) + m.group(2) + ":", line, count=1)
                     for line in str(source).replace("\r\n", "\n").split("\n"))


def _denest(line):
    """One colon off a line that is a fence of four colons or more (an opening or a closing line): a step's way into
    the grammar of an exercise written on its own."""
    return _FENCE_LINE_RE.sub(lambda m: m.group(1) + m.group(2)[1:], line, count=1)

# A FORMULA ON ITS OWN, between `:::math` and `:::`, exactly as an exercise
# sits between `:::exercise` and `:::`.  The body is LaTeX and nothing here
# reads it: it is carried whole to the renderers, which draw it (HTML) or
# simply are LaTeX (paper).  Several lines are one formula -- `\\` and
# `\begin{aligned}` are how a formula is broken, not a blank line -- so the
# body is joined with newlines and handed over as it was typed.
MATH_OPEN_RE = re.compile(r"^:::math\s*$", re.I)
# a jolly card's four fields, each one line or a `key: |` block of any
# block content (htmlgen/texgen render them through parse())
JOLLY_FIELDS = ("front-primary", "front-secondary", "back-primary", "back-secondary")
# which side a flashcard shows first; only a flashcard's `direction` says
# this (a matching exercise's is another field with other values)
FLASHCARD_DIRECTIONS = ("forward", "reverse", "both-random", "both-repeat")
# which of a vocab or opposites card's fields go with the answer or with the
# question (card_extras), in the order they are drawn; the card says so with
# `<field>-side`
CARD_EXTRAS = {"vocab": ("context", "notes", "source"), "opposites": ("notes", "source")}
CARD_SIDES = ("answer", "question")
_EX_FIELD_RE = re.compile(r"^([a-z][a-z0-9-]*):\s*(.*)$", re.I)
_EX_MARKED_RE = re.compile(r"^-\s*\[([^\]]*)\]\s*(.*)$")


def _exercise_split_pair(text):
    """Split the first unescaped ``=>`` in an exercise row."""
    m = re.search(r"(?<!\\)=>", text)
    if not m:
        return None
    clean = lambda s: s.strip().replace(r"\=>", "=>")
    return clean(text[:m.start()]), clean(text[m.end():])


def _parse_step(lines, at, limit):
    """The step of a follow-up whose opening line is `lines[at]` (four colons), which ends at or before `limit`, the line
    of the follow-up's own closing `:::` -> (the step as the exercise it is, the index of the line after it).  A step
    that is never closed does not swallow the follow-up's closing line: it says so, and ends before it."""
    end, drawing = at + 1, False
    while end < limit:
        s = lines[end].strip()
        if drawing:
            drawing = s != ":::::"
        elif re.match(r"^:::::latex\b", s, re.I):
            drawing = True
        elif s == STEP_CLOSE:
            break
        end += 1
    closed = end < limit
    last = end if closed else limit - 1
    norm = list(lines)
    for k in range(at, min(last, len(lines) - 1) + 1):
        norm[k] = _denest(norm[k])
    if not closed and last + 1 < len(norm):
        # a closing line of its own for it to find, which is not the follow-up's
        norm = norm[:last + 1] + [":::"] + norm[last + 1:]
    block, nxt = parse_exercise(norm, at)
    if not closed:
        block["errors"].append("step is missing its closing :::: line")
        return block, last + 1
    return block, nxt


def parse_exercise(lines, start):
    """Normalize one ``:::exercise`` body into a primitive-driven block."""
    opening = lines[start].strip()
    m = EXERCISE_OPEN_RE.match(opening)
    subtype = (m.group(1) or "").lower()
    end = start + 1
    body = []
    # A LATEX BLOCK IN A CARD'S FIELD IS OPAQUE to the exercise: its lines are
    # the drawing's, and no line of them -- a `:::`, a `- (1,0)` of TikZ, a
    # `key: value` -- ends the exercise or starts a row or a field.  Its fence
    # is four colons so that it may sit here at all (latexthemes).
    in_latex = False
    while end < len(lines):
        s_ = lines[end].strip()
        if in_latex:
            in_latex = s_ != latexthemes.FENCE_CLOSE
        elif latexthemes.FENCE_OPEN_RE.match(s_):
            in_latex = True
        elif s_ == ":::":
            break
        body.append(lines[end])
        end += 1

    fields, raw_fields, rows, errors = {}, {}, [], []
    steps = []                          # a follow-up's steps, each an exercise of its own (_parse_step)
    # the line each row is written on, and each item made of one: the page
    # numbers the words of an exercise in the order they are written, not
    # the order it draws them in (htmlgen._EX_ORDER), and the studio's
    # searches skip what it does not draw (store._mask_uncountable)
    row_lines, item_lines = [], []
    # where each field's text is, as (first, last) indices into `lines`: the
    # key's own line for a one-line value, the lines under `key: |` for a
    # block (card_spans reads it)
    field_lines = {}
    if end >= len(lines):
        errors.append("exercise is missing its closing ::: line")
    # A JOLLY CARD'S FIELD MAY SIMPLY GO ON.  Its four fields hold blocks of
    # the page's own markdown, and a block is written on several lines: the
    # lines under one, until another field or a row, belong to it, written
    # `key: |` or not.  Anywhere else an unknown line is still the error it
    # was: a mistyped row must not be swallowed by the prompt above it.
    pending = None                      # [key, first line, [lines as written]]

    def carry_on():
        if pending is None:
            return
        key, first, kept = pending
        while kept and not kept[-1].strip():
            kept.pop()
        if len(kept) > 1:
            fields[key] = " ⏎ ".join(x.strip() for x in kept).strip()
            raw_fields[key] = "\n".join(
                [kept[0].strip()] + textwrap.dedent("\n".join(kept[1:])).split("\n"))
            field_lines[key] = (first, first + len(kept) - 1)

    i = 0
    while i < len(body):
        raw, s = body[i], body[i].strip()
        if subtype == "follow-up" and STEP_OPEN_RE.match(s):
            # a step: its lines are its own, through its closing `::::`
            carry_on()
            pending = None
            step, upto = _parse_step(lines, start + 1 + i, end)
            steps.append(step)
            i = upto - (start + 1)
            continue
        if pending is not None and latexthemes.FENCE_OPEN_RE.match(s):
            # a drawing in a field written without `|`: every line of it goes
            # to the field as it is, through its closing fence
            pending[2].append(raw)
            i += 1
            while i < len(body):
                pending[2].append(body[i])
                i += 1
                if body[i - 1].strip() == latexthemes.FENCE_CLOSE:
                    break
            continue
        if not s or s.startswith("<!--"):
            if pending is not None and not s:
                pending[2].append("")   # a blank line parts two paragraphs
            i += 1
            continue
        fm = _EX_FIELD_RE.match(s)
        if fm and not s.startswith("-"):
            carry_on()
            pending = None
            key, value = fm.group(1).lower(), fm.group(2)
            if key == "type" and not subtype:
                subtype = value.strip().lower()
            elif value.strip() == "|":
                more = []
                i += 1
                first = i
                in_drawing = False
                while i < len(body) and (in_drawing or not body[i].strip()
                                         or body[i].startswith((" ", "\t"))):
                    s_ = body[i].strip()
                    if in_drawing:
                        in_drawing = s_ != latexthemes.FENCE_CLOSE
                    elif latexthemes.FENCE_OPEN_RE.match(s_):
                        in_drawing = True
                    more.append(body[i])
                    i += 1
                field_lines[key] = (start + 1 + first, start + i)
                # the inline renderers read the lines joined by ⏎; a field
                # that holds blocks (a jolly card's list, table or picture)
                # needs them as written, the indentation that nests a list
                # included -- so the dedented text is kept beside it
                fields[key] = " ⏎ ".join(x.lstrip() for x in more).strip()
                text = textwrap.dedent("\n".join(more)).split("\n")
                while text and not text[0].strip():
                    text.pop(0)
                while text and not text[-1].strip():
                    text.pop()
                raw_fields[key] = "\n".join(text)
                continue
            else:
                fields[key] = value.strip()
                field_lines[key] = (start + 1 + i, start + 1 + i)
                if key in JOLLY_FIELDS:
                    pending = [key, start + 1 + i, [value.strip()]]
        elif s.startswith("-"):
            carry_on()
            pending = None
            rows.append(s)
            row_lines.append(start + 1 + i)
        elif pending is not None:
            pending[2].append(raw)
        else:
            errors.append("unrecognized line: " + s)
        i += 1
    carry_on()

    # A MARK MAY HOLD A BLANK.  `text: [من بابک [[slot]]]{tl}` is one
    # sentence of the target language with a hole in it, and the renderers
    # cut the sentence at the hole; the mark is spread over the pieces here,
    # once, so that every renderer and the check below read the same text
    # (texgen.spread_slots).  Nothing else changes: a field with no blank
    # inside a mark comes back exactly as it was written.
    fields = {k: spread_slots(v) for k, v in fields.items()}
    raw_fields = {k: spread_slots(v) for k, v in raw_fields.items()}

    primitive, mode = EXERCISE_TYPES.get(subtype, ("", ""))
    if not subtype:
        errors.append("exercise type is missing")
    elif not primitive:
        errors.append("unknown exercise type: " + subtype)
    items = []
    if primitive == "chain":
        if rows:
            errors.append("follow-up has no answer rows; write its steps")
        if len(steps) < 2:
            errors.append("follow-up needs at least two steps")
        for n, step in enumerate(steps, 1):
            if step["subtype"] == "follow-up":
                errors.append("a follow-up cannot hold a follow-up")
                continue
            errors.extend("step %d: %s" % (n, e) for e in step["errors"])
    if primitive in ("choice", "placement") and mode != "boolean":
        for row, line in zip(rows, row_lines):
            mm = _EX_MARKED_RE.match(row)
            # `- [سلام]{tl}` IS NOT A MARKED ROW.  A marker is a bracket of
            # its own with the answer after it; here the bracket is the
            # content of a target-language mark, and taking it for the marker
            # left `{tl}` as the answer -- silently, which is the worst way to
            # be wrong.  The `{` right after the bracket says which it is.
            if mm and mm.group(2).lstrip().startswith("{"):
                mm = None
            if not mm:
                errors.append("answer row needs [ ] or an explicit position "
                              "before the answer")
                continue
            mark, text = mm.group(1).strip(), mm.group(2).strip()
            items.append({"mark": mark, "text": text})
            item_lines.append(line)
    elif primitive == "matching" or mode == "boolean":
        for row, line in zip(rows, row_lines):
            pair = _exercise_split_pair(re.sub(r"^-\s*", "", row))
            if not pair or not all(pair):
                errors.append("pair row needs left => right")
                continue
            items.append({"left": pair[0], "right": pair[1]})
            item_lines.append(line)

    if primitive == "choice" and mode != "boolean":
        for item in items:
            item["correct"] = item.pop("mark").lower() in ("x", "yes", "true", "correct")
        ncorrect = sum(1 for x in items if x["correct"])
        if not items:
            errors.append("choice exercise has no alternatives")
        elif mode == "multiple" and ncorrect < 1:
            errors.append("choose-all needs at least one [x] answer")
        elif mode == "single" and ncorrect != 1:
            errors.append("single-choice exercise needs exactly one [x] answer")
    elif primitive == "placement" and mode == "fill":
        slots = set(SLOT_RE.findall(fields.get("text", "")))
        marked = [x["mark"] for x in items if x["mark"]]
        if not slots:
            errors.append("fill-blanks text needs at least one [[slot]]")
        if slots != set(marked):
            errors.append("fill-blanks slots and [slot] answer rows differ")
    elif primitive == "placement" and mode == "order":
        ranks = [x["mark"] for x in items]
        if not items or any(not re.fullmatch(r"\d+", x) for x in ranks):
            errors.append("ordering rows need numeric positions such as [1]")
        elif len(set(ranks)) != len(ranks):
            errors.append("ordering positions must be unique")
        if subtype == "construct-sentence" and fields.get("answer-direction") \
                and fields["answer-direction"].lower() not in ("rtl", "ltr"):
            errors.append("answer-direction must be rtl or ltr")
    elif primitive == "matching" and not items:
        errors.append("matching exercise has no pairs")
    elif mode == "boolean":
        accepted = {"yes", "no"} if subtype == "yes-no" else {"true", "false"}
        if not items:
            errors.append("boolean exercise has no questions")
        for item in items:
            item["answer"] = item["right"].strip().lower()
            if item["answer"] not in accepted:
                errors.append("%s answer must be %s" %
                              (subtype, " or ".join(sorted(accepted))))
    elif primitive == "flashcard":
        kind = (fields.get("card-type") or "vocab").lower()
        if kind not in ("vocab", "opposites", "jolly"):
            errors.append("unknown flashcard card-type: " + kind)
        elif kind == "jolly":
            # each field may hold any block content, so a side needs only
            # one of its two
            if not (fields.get("front-primary") or fields.get("front-secondary")) \
                    or not (fields.get("back-primary") or fields.get("back-secondary")):
                errors.append("a Jolly flashcard needs a front field and a back field")
            for key in JOLLY_FIELDS:
                # wherever it would be read as one, a box on the card included
                text = raw_fields.get(key, fields.get(key, ""))
                if text.strip() and _holds_exercise(parse(text, card=True)[1]):
                    errors.append("%s cannot hold an exercise" % key)
        elif kind == "opposites" and (not fields.get("target") or not fields.get("opposite")):
            errors.append("an opposites flashcard needs target and opposite")
        elif kind == "vocab" and not (fields.get("front") or fields.get("target")):
            errors.append("a vocab flashcard needs front or target")
        if fields.get("direction") and \
                fields["direction"].strip().lower() not in FLASHCARD_DIRECTIONS:
            errors.append("direction must be forward, reverse, both-random "
                          "or both-repeat")
        for key in CARD_EXTRAS["vocab"]:
            if fields.get(key + "-side") and \
                    fields[key + "-side"].strip().lower() not in CARD_SIDES:
                errors.append("%s-side must be answer or question" % key)
        for key in ("front-audio", "back-audio"):
            if fields.get(key) and not AUDIO_PATH_RE.match(fields[key]):
                errors.append(AUDIO_FIELD_ERROR % key)
        for key in EXERCISE_IMAGE_FIELDS:
            if fields.get(key):
                errors.append("a flashcard's pictures are front-image and "
                              "back-image, not %s" % key)
        for key in EXERCISE_AUDIO_FIELDS:
            if fields.get(key):
                errors.append("a flashcard's recordings are front-audio and "
                              "back-audio, not %s" % key)
        if rows:
            # they would be answer rows on any other exercise, and a card has
            # no answers: said nothing, a list written this way would vanish
            errors.append("a flashcard has no answer rows: write a list "
                          "inside a field, as `%s: |` and its lines under it"
                          % (JOLLY_FIELDS[0] if kind == "jolly" else "notes"))

    if primitive and primitive != "flashcard":
        for key in EXERCISE_IMAGE_FIELDS:
            if fields.get(key) and not exercise_image(fields[key]):
                errors.append(IMAGE_FIELD_ERROR % key)
        for key in EXERCISE_AUDIO_FIELDS:
            if fields.get(key) and not exercise_audio(fields[key]):
                errors.append(AUDIO_FIELD_ERROR % key)

    block = {"type": "exercise", "subtype": subtype,
             "primitive": primitive, "mode": mode, "fields": fields,
             "raw_fields": raw_fields, "_field_lines": field_lines,
             "_row_lines": row_lines, "_item_lines": item_lines,
             "items": items, "errors": errors, "_line": start,
             "_end_line": min(end, len(lines) - 1),
             "source": "\n".join(lines[start:min(end + 1, len(lines))])}
    if primitive == "chain":
        block["steps"] = steps
    return block, min(end + 1, len(lines))


_DIRECTION_WORD_RE = re.compile(r"[a-z][a-z0-9-]*")


def set_block_direction(source, value):
    """`source` -- the text of one exercise, as a block's "source" reads --
    with its `direction:` field set to `value`.

    The line is found where the PARSER read the field (`_field_lines`), never
    by a search of the text: a line that starts `direction:` is the field
    wherever it stands, even under a card's own field, and a search that
    disagreed with the parser would rewrite the wrong line.  A field written
    as `direction: |` and its lines under it becomes one line; an exercise
    with no `direction:` gets one, right under its `:::exercise` line.  The
    line's own indentation is kept.  Everything else is left as written.

    The first exercise of the text is the one changed (a text of one exercise
    is what it is for).  ValueError for a value that is not a lower-case
    word, and for a text with no exercise in it."""
    if not isinstance(value, str) or not _DIRECTION_WORD_RE.fullmatch(value):
        raise ValueError("a direction is a lower-case word, such as forward or reverse")
    text = source.replace("\r\n", "\n")
    block = next((b for b in parse(text)[1] if b["type"] == "exercise"), None)
    if block is None:
        raise ValueError("this is not an exercise")
    lines = text.split("\n")
    at = block["_field_lines"].get("direction")
    if at is None:
        lines.insert(block["_line"] + 1, "direction: " + value)
    else:
        # a `key: |` block's lines are the ones under the key; the key is above
        key = at[0] - 1 if "direction" in block["raw_fields"] else at[0]
        indent = lines[key][:len(lines[key]) - len(lines[key].lstrip())]
        lines[key:max(at[1], key) + 1] = [indent + "direction: " + value]
    return "\n".join(lines)


def _holds_exercise(blocks):
    return any(b["type"] == "exercise"
               or (b["type"] == "box" and _holds_exercise(b["blocks"]))
               for b in blocks)


def plain_para(text, target=None):
    """Is this paragraph ordinary prose?

    A line that is one target-language block (`[…]{tl}`, with its font,
    tint and tategaki), one Latin block (`[…]{la align=right width=60}`) or
    nothing but the target script is a BLOCK on the page -- its own
    direction, face and width -- so a card draws it as the page does
    rather than as a run of text inside a line."""
    t = (text or "").strip()
    if not t:
        return True
    was = cur_lang().code
    set_target(target or languages.DEFAULT)
    try:
        return not (LA_RE.fullmatch(t) or tl_re().fullmatch(t)
                    or is_fa_only_paragraph(t) or _is_pure_fa_paragraph(t))
    finally:
        set_target(was)


def card_extras(fields):
    """Where a vocab or opposites card draws its `context`, `notes` and
    `source`, as both renderers read it: (the keys that go with the word --
    its target, reading and transliteration -- and the keys that go with its
    meaning), each in the order they are drawn, after the half's own fields.
    The halves are the ones a card is composed in, the word's first; a
    `reverse` card is turned round after, by the renderers.

    THEY GO ON THE ANSWER, the side the flip reveals.  A card turned round
    asks its meaning and answers with the word, so the example, the notes
    and the source would give the word away on the side that opens the card:
    on that card they are the word's.  `<field>-side: question` puts one on
    the side shown first instead.  A both-random card is composed forward and
    its page moves them with the draw (app.js drawFirstSide); a both-repeat
    one is two cards in a deck, each with its own direction (decks._faces).
    A custom `back` replaces them all, as it always did.  The value is read
    in any case; one that is neither is the default here, and an error of the
    card itself (parse_exercise)."""
    kind = (fields.get("card-type") or "vocab").strip().lower()
    keys = CARD_EXTRAS.get(kind)
    if not keys or (kind == "vocab" and fields.get("back")):
        return (), ()
    turned = (fields.get("direction") or "").strip().lower() == "reverse"
    word, meaning = [], []
    for key in keys:
        question = (fields.get(key + "-side") or "").strip().lower() == "question"
        # the answer is the meaning's half, and on a card turned round the word's
        (meaning if question == turned else word).append(key)
    return tuple(word), tuple(meaning)


def card_field(block, key, target=None):
    """One flashcard field as both renderers read it, or None when empty.

    ("inline", text, footnotes) when the field is one paragraph of ordinary
    prose -- rendered inline, exactly as such a field always was (the ⏎
    joined text, so a field written on several lines keeps its line breaks)
    -- and when it reads as no block at all (a rule, a lone note
    definition), which would otherwise leave the card blank where it always
    showed the text; else ("blocks", blocks, footnotes), which is the page's
    own rendering of what the field says.  `footnotes` are the definitions
    written inside the field.
    """
    fields = block.get("fields") or {}
    text = (block.get("raw_fields") or {}).get(key) or fields.get(key, "")
    if not text.strip():
        return None
    code = target or languages.DEFAULT
    fm, blocks = parse(text, target=code, card=True)
    notes = fm.get("_footnotes") or {}
    if not blocks or (len(blocks) == 1 and blocks[0]["type"] == "para"
                      and not notes and plain_para(blocks[0]["text"], code)):
        return "inline", fields.get(key, ""), notes
    return "blocks", blocks, notes


def card_field_is_rich(blocks):
    """Is a field's content more than one paragraph -- a table, a list, a
    box, a figure, several blocks?  Such a field is drawn as a page's column
    is; one paragraph, a target-language or Latin block included, stays the
    card's own line, at the card's size and in its place
    (htmlgen._card_jolly_field)."""
    return not (len(blocks) == 1 and blocks[0]["type"] == "para")


def card_fields(block, target=None):
    """A jolly card's fields, {key: card_field(...)}, and the footnote
    definitions written anywhere on it: a renderer merges those into the
    document's before it draws the card, so a front field may cite a note
    written at the card's end."""
    cards, notes = {}, {}
    for key in JOLLY_FIELDS:
        cards[key] = card_field(block, key, target)
        if cards[key]:
            notes.update(cards[key][2])
    return cards, notes


def card_spans(text):
    """Where a document's jolly cards draw a field as blocks: [(line,
    column)], each a source line whose text from `column` on is such a
    field's.  The studio page offers nothing drawn there to its hover
    editors -- a word to colour, a target-text or Latin block to reopen --
    as it offers no picture on a card to the layout editor; store blanks
    these stretches before it counts, so the n-th word the page names is
    the n-th the store finds.  A field that is one paragraph is inline, and
    offered and counted as it always was."""
    fm, blocks = parse(text)
    lines = text.replace("\r\n", "\n").split("\n")
    out = []

    def walk(blocks, base):
        for b in blocks:
            if b["type"] == "box":      # its lines count from the box's first
                walk(b["blocks"], base + b["_line"])
                continue
            if b["type"] == "exercise" and b.get("steps") and not b["errors"]:
                walk(b["steps"], base)  # a follow-up's steps are exercises of their own
                continue
            # a card with errors draws its error list, not its fields; like
            # every exercise that needs attention, it is left as it was
            if (b["type"] != "exercise" or b["errors"] or b["primitive"] != "flashcard"
                    or (b["fields"].get("card-type") or "").lower() != "jolly"):
                continue
            for key, field in card_fields(b, fm["target"])[0].items():
                if not field or field[0] != "blocks":
                    continue
                first, last = b["_field_lines"][key]
                if key in b["raw_fields"]:
                    out.extend((base + k, 0) for k in range(first, last + 1))
                else:
                    line = lines[base + first].rstrip()
                    out.append((base + first, len(line) - len(b["fields"][key])))
    walk(blocks, 0)
    return out


def youtube_id(url):
    m = YT_ID_RE.search(url or "")
    return (m.group(1) or m.group(2)) if m else None


def parse_time(v):
    """`90`, `1:30`, `1:02:03`, or with a fraction on the seconds (`65.5`,
    `1:05.25`) -> seconds: an int when whole, else a float to two decimals;
    None when unreadable.  A recording is cut finer than the second; a
    YouTube clip is not, and its renderers take int() of what this gives."""
    parts = str(v).split(":")
    try:
        secs = 0
        for p in parts[:-1]:
            secs = secs * 60 + int(p)
        last = parts[-1]
        secs = secs * 60 + (float(last) if re.fullmatch(r"-?\d*\.\d*", last)
                            else int(last))
    except (ValueError, OverflowError):
        # OverflowError: a minute count too long for a float to add to
        return None
    if isinstance(secs, float) and not math.isfinite(secs):
        return None             # 309 digits and more read as infinity
    secs = round(max(0, secs), 2)
    return int(secs) if secs == int(secs) else secs


def clip_seconds(v):
    """A clip time as the dialect writes it and the page's media fragment
    takes it (the inverse of parse_time's plain-seconds form): whole seconds
    bare, anything else to two decimals at most -- `65`, `65.5`, `1.25`."""
    v = round(float(v), 2)
    return "%d" % v if v == int(v) else ("%.2f" % v).rstrip("0")


def parse_image_attrs(raw):
    """`width=60 align=center offset=-10 start=1:30 end=95` -> dict."""
    out = dict(IMAGE_DEFAULTS, start=None, end=None)
    for m in re.finditer(r"([a-z]+)\s*=\s*(-?[\w.:]+)", raw or ""):
        k, v = m.group(1), m.group(2)
        if k in ("width", "offset"):
            try:
                n = int(round(float(v)))
            except ValueError:
                continue
            if k == "width":
                out["width"] = max(5, min(100, n))
            else:
                out["offset"] = max(-100, min(100, n))
        elif k == "align" and v in ("left", "center", "right"):
            out["align"] = v
        elif k in ("start", "end"):
            out[k] = parse_time(v)
    return out

# A "voce" (lemma) heading: `## فارسی | translit | etymology`.  For a
# script language (fa, ar, ja) the first field must start with a character
# of the target script -- what the Persian-only rule always was, now read
# from the registry.  A Latin-script target (it) cannot be told from the
# prose, so there a heading is a lemma when it has two or more `|` fields;
# the prompt tells the model a section title can then never contain `|`.
def _is_lemma_head(L, f0, nfields):
    if L.chars:
        return bool(L.re_chars.match(f0))
    return nfields >= 2


# A lemma may carry a colour mark, `## [آهسته]{teal} | …`; for a Latin
# target the run marker itself may sit there too, `## [bello]{tl} | …`,
# which is no colour at all.  The mark may also carry the annotations a
# run mark carries (`## [bello]{teal translit:ˈbɛl.lo} | …`): the studio
# writes exactly that when the headword's transliteration or reading is
# edited by hover, and a heading the parser then failed to read came out
# as a numbered section with literal brackets.  Group 1 is the headword,
# 2 the leading token, 3 the key:value fields (the shape of
# texgen.LATIN_RUN_RE).
_HEAD_MARK = re.compile(
    r"\[([^\[\]]+)\]\{\s*(?:(#[0-9A-Fa-f]{6}|[A-Za-z]+)\b\s*)?"
    r"((?:(?:translit|kana|reading):[^{}]*?)?)\s*\}")


# `## فارسی | translit | etym | = *fast, sharp*` — the trailing gloss on a
# lemma heading, in two accepted shapes.  As its own field the pipe
# delimits it, so the italics are optional; hung off the end of the
# etymology instead, the italics are what mark it — otherwise an ordinary
# `=` inside an etymology note ("mp. tund, 'x = y'") would be mistaken
# for a gloss and take half the note with it.
_VOCE_GLOSS_FIELD = re.compile(r"\|\s*=\s*(?:\*(?P<i>.+?)\*|(?P<p>.+?))\s*$")
_VOCE_GLOSS_TAIL = re.compile(r"\s*=\s*\*(?P<i>.+?)\*\s*$")


def _split_voce_gloss(txt):
    """`## fa | tr | etym | = *gloss*` -> ('## fa | tr | etym', 'gloss')."""
    for rx in (_VOCE_GLOSS_FIELD, _VOCE_GLOSS_TAIL):
        m = rx.search(txt)
        if m:
            gloss = (m.groupdict().get("i") or m.groupdict().get("p") or "")
            return txt[:m.start()].rstrip().rstrip("|").rstrip(), gloss.strip()
    return txt, ""


def _split_cells(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def parse(text, target=None, card=False):
    """Return (frontmatter: dict, blocks: list).

    `fm["target"]` is always present afterwards, normalised to a registry
    code (default Persian); an unknown code falls back to Persian and is
    reported in `fm["_target_error"]` so the studio can say so instead of
    silently rendering the wrong script.  `target` is passed by the
    recursive call that parses a blockquote's inside, which has no front
    matter of its own but belongs to the same document.  A flashcard
    field is parsed with it too, and with `card=True`: it has no front
    matter (a card that opens on a `---` rule keeps its first lines), and
    a `#` heading is a heading on the card, not a title for it.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    i, n = 0, len(lines)
    fm = {}
    # The lines whose text no renderer draws as words: the front matter but
    # for the title, the subtitle and the note; a `#` heading that does not
    # become the title; a formula, drawn as mathematics.  The studio's
    # searches for the n-th word the page offers skip them
    # (store._mask_uncountable).  `shown` is the title's, the subtitle's
    # and the note's own lines, drawn above the document -- and nowhere
    # when this is a box's inside.
    silent, shown = [], {}

    # ---- front matter -------------------------------------------------
    while i < n and not lines[i].strip():
        i += 1
    if not card and i < n and lines[i].strip() == "---":
        silent.append(i)
        j = i + 1
        while j < n and lines[j].strip() != "---":
            m = re.match(r"^([A-Za-z_]+)\s*:\s*(.*)$", lines[j])
            key = m.group(1).lower() if m else ""
            if key in FM_KEYS:
                fm[key] = m.group(2).strip()
            if key in ("title", "subtitle", "note"):
                if key in shown:                # the last one given is it
                    silent.append(shown[key])
                shown[key] = j
            else:
                silent.append(j)
            j += 1
        if j < n:
            silent.append(j)
        i = j + 1 if j < n else j

    # the language is fixed here, before any heading is read
    raw_target = (fm.get("target") or "").strip().lower()
    if target is not None:
        L = languages.get_or_default(target)
    elif raw_target and raw_target not in languages.LANGS:
        L = languages.get_or_default(None)
        fm["_target_error"] = ("unknown target language %r -- rendered as %s"
                               % (raw_target, L.name))
    else:
        L = languages.get_or_default(raw_target)
    fm["target"] = L.code

    blocks = []
    fn_defs = {}
    # where each footnote definition is, as (first, last) line indices: its
    # text renders nowhere in place, and the studio's searches for the n-th
    # word the page offers must not count what is written there
    # (store._blank_footnotes)
    fn_lines = []
    para_start = [None]

    # A paragraph's lines are consecutive -- anything else between them
    # would have ended it -- so its last line is its first plus its count.
    # The store reads the span: a word wrapped from one line of it to the
    # next is one word on the page (store._run_matches).
    def flush_para(buf):
        if buf:
            blocks.append({"type": "para", "text": " ".join(buf),
                           "_line": para_start[0],
                           "_end_line": para_start[0] + len(buf) - 1})
            buf.clear()
        para_start[0] = None

    para = []
    while i < n:
        line = lines[i]
        s = line.strip()

        # blank line ----------------------------------------------------
        if not s:
            flush_para(para)
            i += 1
            continue

        # horizontal rule (ignored: sections give the structure) --------
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):
            flush_para(para)
            i += 1
            continue

        # interactive exercise container --------------------------------
        # Kept ahead of ordinary paragraphs so everything through the
        # closing ::: is opaque to the normal list/heading parser.
        if EXERCISE_OPEN_RE.match(s):
            flush_para(para)
            exercise, i = parse_exercise(lines, i)
            blocks.append(exercise)
            continue

        # A DRAWING MADE BY LaTeX ITSELF (latexthemes): `::::latex`, a
        # theme's name, the layout in braces, and a line `::::`.  The body is
        # LaTeX, carried whole to lib/latexdraw.py, which compiles it on its
        # own; nothing here reads it.
        op = latexthemes.opening(s)
        if op is not None:
            flush_para(para)
            start = i
            i += 1
            body = []
            while i < len(lines) and lines[i].strip() != latexthemes.FENCE_CLOSE:
                body.append(lines[i])
                i += 1
            closed = i < len(lines)
            if closed:
                i += 1                      # the closing fence
            errors = list(op["errors"])
            if not closed:
                errors.append("a latex block is closed by a line of four colons, ::::, "
                              "and this one never is")
            attrs = latexthemes.parse_attrs(op["attrs"], card=card)
            blocks.append({"type": "latex", "tex": latexthemes.dedent_body(body),
                           "theme": op["theme"], "errors": errors,
                           "_line": start, "_end_line": i - 1, **attrs})
            silent.extend(range(start, i))
            continue

        # a formula on its own line, the same fence one line shorter
        if MATH_OPEN_RE.match(s):
            flush_para(para)
            start = i
            i += 1
            body = []
            while i < len(lines) and lines[i].strip() != ":::":
                body.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1                      # the closing fence
            blocks.append({"type": "math",
                           "tex": "\n".join(body).strip("\n"),
                           "_line": start})
            silent.extend(range(start, i))
            continue

        # footnote definition ------------------------------------------
        m = _FOOTNOTE_DEF.match(s)
        if m:
            flush_para(para)
            fid, txt = m.group(1), m.group(2).strip()
            first = i
            i += 1
            while i < n and lines[i].strip() and (lines[i].startswith("  ")
                                                  or lines[i].startswith("\t")):
                txt += " " + lines[i].strip()
                i += 1
            fn_defs[fid] = txt
            fn_lines.append((first, i - 1))
            continue

        # headings ------------------------------------------------------
        m = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m:
            flush_para(para)
            level, txt = len(m.group(1)), m.group(2).strip()
            if level == 1 and card:
                blocks.append({"type": "section", "text": txt, "_line": i})
            elif level == 1:
                if "title" in fm:
                    silent.append(i)            # dropped: one title is had
                else:
                    fm["title"], shown["title"] = txt, i
            elif level == 2:
                # A lemma may end with a gloss, `… | = *fast, sharp*`.
                # It is stripped here and rendered nowhere: the heading
                # already carries the transliteration and the etymology,
                # and a translation printed beside them would just repeat
                # what the entry below says.  It exists to put the lemma
                # into the glossary, which otherwise only ever sees words
                # glossed in running prose.  Written as a fourth field or
                # appended to the third — the `=` is what marks it, not
                # the pipe, so both read the same.
                txt, voce_gloss = _split_voce_gloss(txt)
                fields = [f.strip() for f in txt.split("|")]
                # the lemma may carry a colour mark: `## [آهسته]{teal} | …`
                f0, fa_color, head_fields, fa_segments = fields[0], None, {}, None
                seg = parse_segmented(f0, 0)
                if seg and seg.end == len(f0) \
                        and _is_lemma_head(L, seg.plain_text.strip(), len(fields)):
                    f0 = seg.plain_text.strip()
                    fa_segments = [(p.text, p.colour) for p in seg.pieces]
                    head_fields = dict(seg.marks)
                mw = _HEAD_MARK.fullmatch(f0)
                if mw and _is_lemma_head(L, mw.group(1).strip(), len(fields)):
                    f0 = mw.group(1).strip()
                    v = mw.group(2)
                    if v is None:
                        fa_color = None        # annotations only
                    elif v.startswith("#"):
                        fa_color = "#" + v[1:].upper()
                    elif v.lower() in ("tl", L.code):
                        fa_color = None        # the run marker, not a colour
                    else:
                        fa_color = v.lower()
                    head_fields = parse_mark_fields(mw.group(3))
                if len(fields) >= 2 and _is_lemma_head(L, f0, len(fields)):
                    # with a reading language the fields are
                    # `漢字 | かんじ | kanji | etym`: the reading comes
                    # BEFORE the transliteration, and the field exists only
                    # when the target has a reading -- a Persian heading
                    # keeps its three fields exactly as before.  The
                    # heading's own fields win; a transliteration or
                    # reading carried by the headword's mark fills in
                    # only where the heading left the field empty.
                    rest = fields[1:]
                    kana = ""
                    if L.reading:
                        kana = rest[0] if rest else ""
                        rest = rest[1:]
                        kana = kana or head_fields.get("kana", "")
                    translit = rest[0] if len(rest) > 0 else ""
                    blocks.append({"type": "voce", "_line": i,
                                   "fa": f0, "fa_color": fa_color,
                                   "fa_segments": fa_segments,
                                   "kana": kana,
                                   "translit": translit or head_fields.get("translit", ""),
                                   "etym": rest[1] if len(rest) > 1 else "",
                                   "gloss": voce_gloss})
                else:
                    # sections are numbered by the renderers; strip a
                    # hand-typed number so it cannot come out doubled
                    blocks.append({"type": "section",
                                   "text": re.sub(r"^\d+[.)]\s+", "", txt),
                                   "_line": i})
            else:
                blocks.append({"type": "subsection", "text": txt,
                               "_line": i})
            i += 1
            continue

        # blockquote -> highlighted box ---------------------------------
        if s.startswith(">"):
            flush_para(para)
            q0 = i
            qlines = []
            while i < n and lines[i].strip().startswith(">"):
                qlines.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            inner_fm, inner = parse("\n".join(qlines), target=L.code)
            fn_defs.update(inner_fm.get("_footnotes", {}))
            # the box's lines are the document's, one for one; a title
            # its inside has is nobody's, and is drawn nowhere
            fn_lines.extend((q0 + a, q0 + b)
                            for a, b in inner_fm.get("_footnote_lines", ()))
            silent.extend(q0 + k for k in inner_fm.get("_silent_lines", ()))
            silent.extend(q0 + k for k in inner_fm.get("_title_lines", ()))
            blocks.append({"type": "box", "blocks": inner, "_line": q0})
            continue

        # table ---------------------------------------------------------
        if "|" in s and i + 1 < n and _TABLE_SEP.match(lines[i + 1]):
            flush_para(para)
            t0 = i
            header = _split_cells(lines[i])
            seps = _split_cells(lines[i + 1])
            align = []
            for c in seps:
                if c.startswith(":") and c.endswith(":"):
                    align.append("c")
                elif c.endswith(":"):
                    align.append("r")
                else:
                    align.append("l")
            i += 2
            rows = []
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append(_split_cells(lines[i]))
                i += 1
            blocks.append({"type": "table", "header": header,
                           "align": align, "rows": rows, "_line": t0})
            continue

        # image (or recording) on its own line --------------------------
        m = IMAGE_RE.match(s)
        if m:
            flush_para(para)
            attrs = parse_image_attrs(m.group(3))
            path = m.group(2)
            if path.startswith("audio/"):
                blocks.append({"type": "audio", "_line": i,
                               "caption": m.group(1).strip(),
                               "path": path,
                               "valid": bool(AUDIO_PATH_RE.match(path)),
                               **attrs})
            else:
                blocks.append({"type": "image", "_line": i,
                               "caption": m.group(1).strip(),
                               "path": path,
                               "valid": bool(IMAGE_PATH_RE.match(path)),
                               **attrs})
            i += 1
            continue

        # YouTube embed on its own line ---------------------------------
        m = VIDEO_RE.match(s)
        if m:
            flush_para(para)
            attrs = parse_image_attrs(m.group(3))
            vid = youtube_id(m.group(2))
            blocks.append({"type": "video", "_line": i,
                           "caption": m.group(1).strip(),
                           "url": m.group(2), "vid": vid,
                           "valid": vid is not None, **attrs})
            i += 1
            continue

        # lists ---------------------------------------------------------
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if m:
            flush_para(para)
            l0 = i
            items, ordered = [], bool(re.match(r"\d", m.group(2)))
            # the line each item starts on: a line of the list that starts
            # none is the one above it going on (store._run_matches)
            item_lines = []
            while i < n:
                mm = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", lines[i])
                if mm:
                    items.append([len(mm.group(1)), mm.group(3).strip()])
                    item_lines.append(i)
                    i += 1
                elif lines[i].strip() and (lines[i].startswith("  ")
                                           or lines[i].startswith("\t")) \
                        and not re.match(r"^\s*([-*+]|\d+[.)])\s", lines[i]):
                    # continuation line of the previous item
                    items[-1][1] += " " + lines[i].strip()
                    i += 1
                else:
                    break
            blocks.append({"type": "enum" if ordered else "list",
                           "items": items, "_line": l0, "_end_line": i - 1,
                           "_item_lines": item_lines})
            continue

        # plain paragraph line ------------------------------------------
        if para_start[0] is None:
            para_start[0] = i
        para.append(s)
        i += 1

    flush_para(para)
    fm["_footnotes"] = fn_defs
    fm["_footnote_lines"] = fn_lines
    if not fm.get("title"):
        # a subtitle and a note are drawn under the title, or not at all
        silent.extend(shown.values())
        shown = {}
    fm["_silent_lines"] = sorted(silent)
    fm["_title_lines"] = sorted(shown.values())
    return fm, blocks
