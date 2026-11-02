#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Gloss a region of a book or a video with an LLM: the prompt that asks for
it, and the answer put back, chunk by chunk, through the doors a hand uses.

    book_prompt(book, first, last, regloss, perfield, prompt, translit, marks)
                                                               -> {prompt, region, options, ...}
    book_apply(book, first, last, answer, regloss, perfield, confirm, marks)
    video_prompt(vdir, frm, to, regloss, perfield, prompt, translit, marks)
    video_apply(vdir, frm, to, answer, regloss, perfield, confirm, marks)
    json_blocks(text)                   the JSON documents in a pasted answer

serve.py wires the routes (<book>/reader/__region/prompt and /apply,
/youtube/api/region/prompt and /apply); these functions are the contract.  A
request that cannot be answered raises Refused (a 400) or NotFound (a 404),
in words worth showing.

WHAT A REGION IS.  In a book, a run of SENTENCES -- subparagraphs, one
\\parnum each -- named by the reader's book-wide chunk numbers (data-c, the
number __edit/chunk takes): `first` and `last` are widened to the whole
sentences they fall in, because a sentence is what an LLM glosses and what
the division is checked against.  In a video, a run of CAPTIONS by their
index in annotations.json -- every caption, plain ones included, the
numbering /youtube/api/edit uses; a plain caption goes into the prompt as
context and is never glossed.  A book paragraph that reading.json folds away
is left out of the prompt and never written, and the answer says how many.

THE TEXT SENT is the chunks as they stand: the .tex's own \\ch arguments, the
annotations.json chunks.  A paragraph marked free in reading.json, a caption
freed from its transcript, departs from source/paras/ or transcript.txt, and
the page shows the departed text -- so that is what the prompt sends, and
neither of those files is ever read here.

THE PAGE NEVER DECIDES WHAT IS PROTECTED.  Everything is worked out again
when the answer is applied, from the files as they are at that moment -- not
from the prompt, which may be an hour old and may have been pasted into a
chatbot that ignored half of it:

  * a chunk is WRITTEN when any of tr, voc, en, kana holds text, not counting
    a reading still exactly as wordline.seed proposed it from the chunk's
    word line (check_annotations.unwritten -- the one definition, asked of
    books and videos alike); it is COMPLETE when it is written and carries en,
    tr where the language requires_tr, kana where it has a reading -- and
    there a seeded reading counts as present;
  * per chunk (the default): a written chunk is kept whole, and whatever the
    answer says about it is listed in `kept`; an unglossed one takes the
    answer's kana, tr, voc and en;
  * per field: a written chunk keeps every field that holds text, and takes
    the answer's value only for a blank one;
  * re-gloss: every glossable chunk -- every one not plain, blank or
    written -- takes the answer's four fields (an omitted voc empties voc);
    a chunk that was blank counts as FILLED, one that was written as
    REPLACED.  Without `confirm` nothing is written when anything would
    be replaced: the answer says how many, and the page asks.

Only kana, tr, voc and en are ever written -- and one more thing, when the
request asks for it (`marks`, brief 3.10: for a language whose record has
`strip`, Persian and Arabic): the SHORT VOWELS of a chunk's fa.  fa, words, col,
free, note and plain never are otherwise: a chunk whose fa does not match the
page's (after the language's normalisation -- NFC, its marks stripped,
whitespace collapsed, or dropped where the language has no word separator) is
dropped; an answer that changed one of the others is told so in `kept`.  An
answer that divides a sentence differently cannot land, because the division
is a person's: the chunks it re-divided are dropped, and the ones before and
after the change, which are still the page's own chunks, may land.

THE SHORT VOWELS (_vowelled).  The request says whether they are asked for, and
this decides it again, from the request and the language's record, never from
the prompt or the page.  An answer's fa is then written, along with the gloss
of the chunk it lands with, ONLY WHEN it is the page's own text with marks
added and nothing else -- not a letter, a space, a joiner or a stop -- and
ONLY INTO A CHUNK THAT HAS NONE: a person's marks are judgement, and a word is
either fully vowelled or wrong, so a chunk half vowelled by hand is not
completed here.  It goes through the same door as the gloss, so the door's own
checks run (a book's fidelity to source/paras/, a video's to its transcript;
both set the marks aside, and the keys of timings.json hash the text with them
stripped, so no timing is lost).  A chunk the answer glosses but whose marks
these rules do not take is written without them, and `kept` says why; one
that a door refuses is refused whole, in the door's words (`dropped`).  The
count `vowelled` is in the report.

NEVER HALF A GLOSS.  A chunk the answer would leave written but incomplete
is dropped whole ("would leave it half glossed: missing tr").  Hand edits may
fill one box at a time; an LLM answer may not, because nobody is looking at
the chunk while it lands.  Every value is checked by the surface's own door
before anything is written -- the book's texwrite._value (the voc macros,
the TeX specials, the marks a tr may not carry, what is not text), the
video's check_annotations.check_chunk on the chunk as it would stand -- and
then written through that door, texwrite.edit_chunk or annwrite.edit_chunk,
one chunk at a time, only the fields that change.  A door that still refuses
puts its own words in `dropped`, and the rest land.
"""
import json
import math
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
YT_LIB = os.path.join(ROOT, "youtube", "lib")
for _p in (HERE, YT_LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import books                                                    # noqa: E402
import languages                                                # noqa: E402
import promptkit                                                # noqa: E402
import prompts                                                  # noqa: E402
import reading                                                  # noqa: E402
import texwrite                                                 # noqa: E402
import wordline                                                 # noqa: E402
import annwrite                                                 # noqa: E402
import check_annotations as CA                                  # noqa: E402

# The only fields an answer ever writes, in the order a chunk carries them.
GLOSS = ("kana", "tr", "voc", "en")
# ...and the ones it may carry but never writes: the text divided, the
# reader's colour, the video's note and its two flags.  A difference in one
# of them is reported, never applied.
CONTEXT = ("words", "col", "free", "note", "plain")
# How far an answer's caption start may be from the file's and still be the
# same caption: ytpages._align_answer's tolerance, for the same numbers.
NEAR = 0.05
# Past this many chunks a prompt is long enough that the page should say so.
LONG = 400


class Refused(ValueError):
    """A request that will not be answered, and why -- a 400."""


class NotFound(Refused):
    """What the request names is not there -- a 404."""


# --- the answer, as pasted ----------------------------------------------
# A fence and what it says it holds: ```json, ``` alone, ```text ...  The
# label is the first word after the backticks; the body runs to the next
# three backticks.  \s matches the \r of an answer pasted from Windows.  A
# fence OPENS only where Markdown opens one, at the start of a line: three
# backticks inside a sentence are a text quoting a fence ("inside one ````
# ```json ```` fence", as the prompt itself says it), and a model that
# repeats that sentence has not begun its answer.  One mid-line opening is
# made a fence all the same, by _GLUED below, because it is how a paste
# lands; any other mid-line fence is read only when NO fence in the text
# counts, by the whole-text and outermost-{...} rules of json_blocks -- once
# one has counted, a later fence that opens mid-line is not seen at all.
_FENCE = re.compile(r"^[ \t]{0,3}```(?!`)[ \t]*([^\s`]*)[^\n]*\n(.*?)```", re.S | re.M)
# An opening fence glued to the closing fence before it: "```" "```json" on
# one line, with nothing but spaces between them, and the label ending its
# line.  A correction, or the rest of an answer continued over messages, is
# pasted under the first answer with the cursor where that answer ended --
# right after its closing ``` -- and the prompt asks for exactly that paste.
# Read as it stands, that second block is no fence, and the correction would
# be dropped without a word while the first try is written.  The spaces
# between the two (if any) are what is replaced by a line break.  Only this:
# three backticks quoted inside a sentence (```` ```json ````) are not
# followed by the end of their line, and still open nothing.
_GLUED = re.compile(r"(?<=```)[ \t]*(?=```[ \t]*[^\s`]*[ \t]*\r?\n)")
# A SURROGATE CODE POINT, which in a Python string is always an unpaired one:
# a pair that arrives as two \uXXXX escapes is joined by json.loads into the
# one character it spells.  An unpaired one is what is left of an emoji or an
# astral character cut in half by a copy -- JSON.stringify sends it on as a
# \ud800 escape, and json.loads takes that back into the string without a
# word -- and UTF-8 cannot encode it.  Nothing that reads an answer here
# stumbles on it; serve.send_json does, when the report quotes the text it
# came in (a sentence's "at", a chunk's fa that did not match), and by then
# the good chunks of the same answer are written: the page got a 500 and no
# report of what landed.  So it is refused here, first, with nothing parsed
# further, planned or written, and without being quoted.  The add page's
# /youtube/api/add reads its answer through this function too, and is
# refused the same way.
_SURROGATE = re.compile("[\ud800-\udfff]")
_BROKEN = ("the answer carries a broken character (an unpaired surrogate) -- "
           "copy it again from the chat")
# A document nested deeper than the decoder will follow -- json.loads gives
# up with a RecursionError somewhere past ten thousand levels, which is no
# ValueError, so it went past every `except ValueError` below, past the
# routes' Refused, and reached the page as a 500.  Said in words instead.
_DEEP = "the answer nests too deep to be read"


def broken(value):
    """True when a JSON value -- a request body, an answer -- carries a lone
    surrogate anywhere in a key or a text (_broken).  The server's request
    bodies (serve.Handler._json_body, youtube/lib/ytpages._json_in) are
    refused on it before any route has written anything."""
    return _broken([value])


def _broken(docs):
    """True when a key or a text anywhere in the parsed documents holds a
    surrogate (_SURROGATE says why).  Walked with a list and not by
    recursion: a document json.loads could read may be deeper than Python's
    own recursion limit."""
    todo = list(docs)
    while todo:
        v = todo.pop()
        if isinstance(v, str):
            if _SURROGATE.search(v):
                return True
        elif isinstance(v, dict):
            for k, x in v.items():
                if isinstance(k, str) and _SURROGATE.search(k):
                    return True
                todo.append(x)
        elif isinstance(v, list):
            todo.extend(v)
    return False


def json_blocks(text):
    """Every JSON document in a pasted answer, in the order they stand.

    THE RULE, one for every door that takes an LLM's answer (the region fill
    here, and the add page's youtube/lib/ytpages._json_blocks, which hands its
    answer to this):

      * a fence labelled ```json must hold JSON: one that does not parse is
        an error, because the model said it was the answer and it is broken;
      * a fence with no label, or another label (```text, ```python), holding
        something that does not parse as a JSON object or array is PROSE --
        a model quoting a sentence, or showing its working -- and is
        ignored.  One that does parse counts like a ```json one: a model that
        forgot the label still answered;
      * no fence that counts -> the whole text, if it is JSON, or if it is
        nothing but JSON documents one after another (several unfenced
        answers pasted one under the other);
      * else the outermost {...} of the text.

    Several fences are several blocks (an answer continued over messages, or
    a correction pasted under the first answer); the caller merges them, a
    later block's unit replacing an earlier one with the same address.  A
    block pasted straight after the closing ``` of the one before it, its
    ```json on that same line, is a block like any other (_GLUED).

    An answer that is not text at all (a request sent by hand) is an empty
    one.  Raises ValueError, in words worth showing, when nothing usable is
    there -- and, before anything of it is read, for an answer carrying an
    unpaired surrogate, in its text or behind an escape in its JSON
    (_SURROGATE says why), and for one nested deeper than the decoder
    follows (_DEEP): both used to escape as a 500.
    """
    text = _GLUED.sub("\n", text if isinstance(text, str) else "").strip()
    if _SURROGATE.search(text):
        raise ValueError(_BROKEN)
    try:
        docs = _answer_docs(text)
    except RecursionError:
        # wherever it is raised: a ```json fence, a fence of prose, the whole
        # text or its outermost {...} -- falling through to the next rule
        # would only have the decoder give up on the same nesting again
        raise ValueError(_DEEP)
    if _broken(docs):
        raise ValueError(_BROKEN)
    return docs


def _answer_docs(text):
    """json_blocks' rules, on a text already joined (_GLUED) and stripped."""
    docs = []
    for m in _FENCE.finditer(text):
        label, body = m.group(1).strip().lower(), m.group(2).strip()
        if not body:
            continue
        try:
            doc = json.loads(body)
        except ValueError as e:
            if label == "json":
                raise ValueError("a ```json block is not valid JSON: %s" % e)
            continue                    # a fence of prose, not an answer
        if label != "json" and not isinstance(doc, (dict, list)):
            continue                    # a bare `42` or "yes" is prose too
        docs.append(doc)
    if docs:
        return docs
    if not text:
        raise ValueError("the answer is empty")
    try:
        return [json.loads(text)]
    except ValueError:
        pass
    # Several answers pasted one under the other with no fence round any of
    # them -- what a chat window's "copy" button hands over for each code
    # block -- are read as the several blocks they are, when the text is
    # nothing but JSON documents one after another.
    docs, dec, i = [], json.JSONDecoder(), 0
    while True:
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        try:
            doc, i = dec.raw_decode(text, i)
        except ValueError:
            docs = []
            break
        docs.append(doc)
    if len(docs) > 1 and all(isinstance(d, (dict, list)) for d in docs):
        return docs
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("no JSON found in the answer")
    try:
        return [json.loads(text[a:b + 1])]
    except ValueError as e:
        raise ValueError("the JSON in the answer does not parse: %s" % e)


# --- small things -------------------------------------------------------
def _a(name):
    """A language's name with its article, as the prompt says it: "an
    Italian video", "a Persian book" -- the registry's names are English
    words, and the ones opening with a vowel letter open with a vowel."""
    return ("an " if name[:1].upper() in "AEIOU" else "a ") + name


def _flat(v):
    """A value as it is compared: text with its whitespace collapsed, so a
    voc the .tex breaks across lines is the same voc an LLM sends on one."""
    return re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v


def _differs(a, b):
    return _flat(a) != _flat(b)


def _clip(s, n=32):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n - 1] + "…"


def _clock(sec):
    """Seconds as the player writes a time: 1:02, or 1:02:03."""
    try:
        s = int(float(sec))
    except (TypeError, ValueError, OverflowError):
        return "?"                  # OverflowError: an infinite or huge start
    h, m = divmod(s, 3600)
    m, s = divmod(m, 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def _int(v, what):
    """v as a request's number, or Refused.  bool is refused although it is an
    int: JSON's true would otherwise address chunk 1."""
    if not isinstance(v, int) or isinstance(v, bool) or v < 0:
        raise Refused("%s must be a number" % what)
    return v


def _required(L):
    """The fields a written chunk of this language must carry."""
    return (["kana"] if L.reading else []) + (["tr"] if L.require_tr else []) + ["en"]


def _seconds(v):
    """A caption's start as a float of seconds, or None when it is not a
    number at all (bool is not, though Python counts it an int).

    Normalised once, before it is compared: an answer's start is whatever
    the model typed, and json.loads takes an integer of four hundred digits,
    and NaN and Infinity, without a word.  An integer no float can hold made
    `abs(start - 12.5)` raise OverflowError, a 500; it is infinity here, of
    its own sign.  NaN stays NaN -- and the caller asks math.isfinite of the
    result, because `abs(nan - x) > NEAR` is False and let a NaN start pass
    for a start that matches."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        return float(v)
    except OverflowError:
        return math.inf if v > 0 else -math.inf     # compared as an int: no float


def _finite(v):
    """_seconds(v) when it is a finite number, else None: a caption start in
    the file that no answer can be held against."""
    s = _seconds(v)
    return s if s is not None and math.isfinite(s) else None


def _said(fields):
    fields = ["`%s`" % f for f in fields]
    return fields[0] if len(fields) == 1 else "%s and %s" % (", ".join(fields[:-1]), fields[-1])


def _norm_at(at):
    """A sentence's address as it is matched: its digits Latin, its spaces
    gone -- a model that writes "ch1:1.2" for "ch1:۱.۲" means the same one."""
    return re.sub(r"\s+", "", languages.any_to_latin_digits(at))


# --- the book -----------------------------------------------------------
def _book(book):
    """The books.Book, or NotFound / Refused."""
    if not book or not os.path.isfile(os.path.join(book, "book.json")):
        raise NotFound("no book here")
    try:
        b = books.Book(book)
    except (OSError, ValueError) as e:
        raise Refused("book.json will not read (%s)" % e)
    problem = b.language_problem()
    if problem:
        raise Refused(problem + " -- fix book.json before glossing")
    return b


def _book_units(book, first, last):
    """The sentences a book region holds.  -> (ctx, units, folded, known)

    `units` are the sentences the prompt sends and an answer may fill,
    `folded` the ones in the region that reading.json folds away, keyed by
    address, and `known` every address the book has -- so an answer naming a
    sentence of another region is told so, and one naming no sentence at all
    is told that instead."""
    b = _book(book)
    first, last = _int(first, "first"), _int(last, "last")
    if first > last:
        first, last = last, first
    try:
        chapters = texwrite.book_chapters(book)
    except texwrite.Refused as e:
        raise Refused(str(e))
    numbered = [c for c in chapters if c["first"] is not None]
    total = numbered[-1]["last"] + 1 if numbered else 0
    for n in (first, last):
        if n >= total:
            raise NotFound("no chunk %d in this book (it has %d)" % (n, total))
    L = b.lang
    doc = reading.load(book)
    units, folded, known, seen = [], {}, set(), set()
    for c in numbered:
        try:
            recs = texwrite.read_chunks(c["path"])
        except texwrite.Refused as e:
            raise Refused(str(e))
        stem = os.path.splitext(c["file"])[0]
        groups = []
        for r in recs:
            if groups and groups[-1][0] == r["label"]:
                groups[-1][1].append(r)
            else:
                groups.append((r["label"], [r]))
        for label, rs in groups:
            at = "%s:%s" % (stem, label or "?")
            key, k = _norm_at(at), 2
            while key in seen:                  # a label written twice by hand
                at = "%s:%s~%d" % (stem, label or "?", k)
                key, k = _norm_at(at), k + 1
            seen.add(key)
            known.add(key)
            ns = [c["first"] + r["index"] for r in rs]
            if ns[-1] < first or ns[0] > last:
                continue
            chunks = []
            for j, r in enumerate(rs):
                slots = tuple(f for f in GLOSS
                              if f in r["fields"] and (f != "kana" or L.reading))
                raw = {f: r.get(f, "") for f in GLOSS + ("words",)}
                chunks.append({"j": j, "fa": r["fa"], "words": r.get("words", ""),
                               "vals": {f: r.get(f, "") for f in GLOSS},
                               "raw": raw, "slots": slots,
                               "glossable": r["macro"] != "chp" and bool(r["fa"].strip()),
                               "extra": {"words": r.get("words", ""), "col": r.get("col", ""),
                                         "note": "", "free": None,
                                         "plain": True if r["macro"] == "chp" else None},
                               "n": c["first"] + r["index"], "local": r["index"],
                               "macro": r["macro"]})
            unit = {"key": key, "at": at, "label": label, "path": c["path"],
                    "file": c["file"], "chapter": c["chapter"],
                    "para": rs[0]["para"], "chunks": chunks}
            if (c["chapter"] is not None and rs[0]["para"] is not None
                    and reading.in_collapsed(doc, c["chapter"], rs[0]["para"])):
                folded[key] = unit
            else:
                units.append(unit)
    ctx = {"surface": "book", "dir": book, "L": L, "G": b.gloss_lang,
           "reorders": bool(b.meta.get("reorders")), "meta": b.meta,
           "first": first, "last": last,
           "folded": len({(u["chapter"], u["para"]) for u in folded.values()})}
    ctx["region"] = _book_region_words(units, ctx["folded"])
    # the region as the page should now show it: widened to whole sentences,
    # in the page's own numbering
    ctx["echo"] = ({"first": units[0]["chunks"][0]["n"], "last": units[-1]["chunks"][-1]["n"]}
                   if units else {"first": first, "last": last})
    return ctx, units, folded, known


def _book_region_words(units, folded):
    """The region in words: "chapter 1, ¶ 1.2 to ¶ 2.1 · 4 sentences"."""
    def lab(u):
        return languages.any_to_latin_digits(u["label"] or "?")
    if not units:
        return ("only paragraphs folded away in the reader (%d of them) -- unfold "
                "them to gloss them" % folded)
    else:
        a, b = units[0], units[-1]
        if a["chapter"] == b["chapter"]:
            said = ("chapter %s, ¶ %s" % (a["chapter"], lab(a)) if a is b else
                    "chapter %s, ¶ %s to ¶ %s" % (a["chapter"], lab(a), lab(b)))
        else:
            said = "chapter %s ¶ %s to chapter %s ¶ %s" % (a["chapter"], lab(a),
                                                          b["chapter"], lab(b))
        said += " · %d sentence%s" % (len(units), "" if len(units) == 1 else "s")
    if folded:
        said += " (%d folded paragraph%s left out)" % (folded, "" if folded == 1 else "s")
    return said


def _book_where(unit, ch=None):
    if ch is None:
        return {"where": "sentence %s" % unit["at"], "at": unit["at"],
                "chunk": None, "index": None}
    return {"where": "%s, chunk %d «%s»" % (unit["at"], ch["j"] + 1, _clip(ch["fa"])),
            "at": unit["at"], "chunk": ch["j"], "index": ch["n"]}


# --- the video ----------------------------------------------------------
def _video_units(vdir, frm, to):
    """The captions a video region holds.  -> (ctx, units, segs)"""
    if not vdir or not os.path.isdir(vdir):
        raise NotFound("no such video")
    try:
        ann = annwrite.read(vdir)
    except OSError:
        raise NotFound("this video has no annotations.json yet")
    except ValueError as e:
        raise Refused(str(e))
    meta = annwrite._meta(vdir)
    L = CA.video_language(vdir, meta, ann)
    G = CA.video_gloss(meta)
    segs = ann["segments"]
    frm, to = _int(frm, "from"), _int(to, "to")
    if frm > to:
        frm, to = to, frm
    if to >= len(segs):
        raise NotFound("no caption %d in this video (it has %d)" % (to, len(segs)))
    units = []
    for i in range(frm, to + 1):
        sg = segs[i] if isinstance(segs[i], dict) else {}
        start = sg.get("start")
        unit = {"key": i, "i": i, "start": start, "chunks": [],
                "plain": bool(sg.get("plain")) or not isinstance(sg.get("chunks"), list),
                "text": sg.get("text") if isinstance(sg.get("text"), str) else ""}
        if not unit["plain"]:
            for j, ch in enumerate(sg["chunks"]):
                ch = ch if isinstance(ch, dict) else {}
                fa = ch.get("fa") if isinstance(ch.get("fa"), str) else ""
                target = not L.chars or L.has_script(fa)
                unit["chunks"].append({
                    "j": j, "fa": fa,
                    "words": ch.get("words") if isinstance(ch.get("words"), str) else "",
                    "vals": {f: ch.get(f) if isinstance(ch.get(f), str) else "" for f in GLOSS},
                    "raw": ch,
                    "slots": tuple(f for f in GLOSS if f != "kana" or L.reading),
                    "glossable": bool(fa.strip()) and not ch.get("plain") and target,
                    "extra": {k: ch.get(k) for k in CONTEXT}})
        units.append(unit)
    first_t = units[0]["start"] if units else None
    last_t = units[-1]["start"] if units else None
    n = len(units)
    region = ("caption %d, %s" % (frm, _clock(first_t)) if n == 1 else
              "captions %d–%d, %s–%s · %d captions" % (frm, to, _clock(first_t),
                                                       _clock(last_t), n))
    ctx = {"surface": "video", "dir": vdir, "L": L, "G": G, "meta": meta,
           "id": meta.get("id") or os.path.basename(os.path.normpath(vdir)),
           "reorders": bool(meta.get("reorders")), "from": frm, "to": to,
           "folded": 0, "region": region, "echo": {"from": frm, "to": to}}
    return ctx, units, segs


def _video_where(unit, ch=None):
    head = "caption %d (%s)" % (unit["i"], _clock(unit["start"]))
    if ch is None:
        return {"where": head, "i": unit["i"], "chunk": None}
    return {"where": "%s, chunk %d «%s»" % (head, ch["j"] + 1, _clip(ch["fa"])),
            "i": unit["i"], "chunk": ch["j"]}


# --- what each chunk is, and what it is asked --------------------------
def _written(ch, L):
    return not CA.unwritten(ch["raw"], L)


def _todo(ch, L, mode):
    """What the prompt asks of this chunk: True (gloss it), a list of the
    blank fields to fill (per field), or None (context only)."""
    if not ch["glossable"]:
        return None
    if mode == "regloss" or not _written(ch, L):
        return True
    if mode == "perfield":
        blank = [f for f in ch["slots"] if not ch["vals"][f].strip()]
        return blank or None
    return None


def _mode(regloss, perfield):
    if not isinstance(regloss, bool) or not isinstance(perfield, bool):
        raise Refused("regloss and perfield are true or false")
    return "regloss" if regloss else "perfield" if perfield else "fill"


# --- the prompt ---------------------------------------------------------
def _shown(ch, todo, mode, analysis=None):
    """One chunk as the prompt shows it.  `analysis` is input and nothing else (lib/evidence.py): no
    answer can bring it back, because `_decided` reads only the fields of a gloss."""
    d = {"fa": ch["fa"]}
    if ch["words"].strip():
        d["words"] = ch["words"]
    if not ch["glossable"]:
        d["plain"] = True
        return d
    if mode != "regloss":
        for f in ch["slots"]:
            if ch["vals"][f].strip():
                d[f] = ch["vals"][f]
    if todo:
        d["todo"] = todo
        if analysis:
            d["analysis"] = analysis
    return d


def _evidence(ctx, units, mode):
    """What an analyzer says of the chunks to do, where somebody chose that on Settings -> Linguistic analysis
    -> lib/evidence.py's Evidence, empty when it is off, not ready or has nothing to say: the prompt is then the
    one there would have been.  It costs its own part and never the prompt."""
    import analysisconfig
    import evidence
    if analysisconfig.choice("evidence") != "on":
        return evidence.Evidence()
    try:
        L = ctx["L"]
        return evidence.for_units(L.code, units, lambda ch: _todo(ch, L, mode))
    except (OSError, ValueError, RuntimeError) as e:
        return evidence.Evidence(diagnostics=[str(e)])


def _data(ctx, units, mode, said=None):
    """The one JSON document the prompt ends with, laid out a chunk to a line
    so a person reading the prompt can find their way in it -- and proved to
    be JSON before it is sent.  `said` is lib/evidence.py's Evidence, if there
    is any.  -> (text, counts)"""
    L, book = ctx["L"], ctx["surface"] == "book"
    dump = lambda v: json.dumps(v, ensure_ascii=False)
    rows, fill, glossed, chunks = [], 0, 0, 0
    for u in units:
        if not book and u["plain"]:
            rows.append("  " + dump({"i": u["i"], "start": u["start"],
                                     "plain": True, "text": u["text"]}))
            continue
        head = ('{"at": %s, "chunks": [' % dump(u["at"]) if book else
                '{"i": %d, "start": %s, "chunks": [' % (u["i"], dump(u["start"])))
        lines = []
        for ch in u["chunks"]:
            todo = _todo(ch, L, mode)
            chunks += 1
            if todo:
                fill += 1
            elif ch["glossable"]:
                glossed += 1
            lines.append("    " + dump(_shown(ch, todo, mode, said.chunks.get((u.get("key", u.get("i")), ch["j"]))
                                               if said else None)))
        rows.append("  " + head + "\n" + ",\n".join(lines) + "\n  ]}")
    text = '{"%s": [\n%s\n]}' % ("sentences" if book else "captions", ",\n".join(rows))
    json.loads(text)                            # a prompt that is not JSON is a bug
    return text, {"units": len(units), "chunks": chunks, "fill": fill, "glossed": glossed}


def _about(ctx, counts):
    L, G = ctx["L"], ctx["G"]
    meta = ctx["meta"]
    gloss = ("- gloss language: **%s** (`%s`) — every `en`, and every meaning inside "
             "a `voc`, is written in %s%s" % (G.name, G.code, G.name,
                                              "" if G.code == languages.DEFAULT_GLOSS
                                              else ", not in English"))
    if ctx["surface"] == "book":
        out = ["## This book", ""]
        title = meta.get("title") or ""
        latin = meta.get("title_latin") or meta.get("title_en") or ""
        if title or latin:
            out.append("- title: %s" % (" — ".join(t for t in (title, latin) if t)
                                         if title != latin else title))
        if meta.get("author") or meta.get("author_latin"):
            out.append("- author: %s" % (meta.get("author_latin") or meta.get("author")))
    else:
        out = ["## This video", "", "- id: `%s`" % ctx["id"]]
        for k in ("title", "channel"):
            if meta.get(k):
                out.append("- %s: %s" % (k, meta[k]))
    out.append("- language: %s (`%s`)" % (L.name, L.code))
    out.append(gloss)
    out.append("- this stretch: %s — %d chunk%s, %d of them to gloss"
               % (ctx["region"], counts["chunks"], "" if counts["chunks"] == 1 else "s",
                  counts["fill"]))
    if ctx["folded"]:
        out.append("- %d paragraph%s inside it %s folded away in the reader and %s "
                   "not sent: the stretch jumps over %s"
                   % (ctx["folded"], "" if ctx["folded"] == 1 else "s",
                      "is" if ctx["folded"] == 1 else "are",
                      "is" if ctx["folded"] == 1 else "are",
                      "it" if ctx["folded"] == 1 else "them"))
    return "\n".join(out)


def substitutions(ctx, mode):
    """What fills a region prompt's blocks and placeholders for this book or video in this mode:
    (flags, values).  Beside `assembled`, lib/skills.py reads it, to say once what each name stands
    for in a book and in a video, in each mode, and for each language the meanings are written in."""
    L, G = ctx["L"], ctx["G"]
    book = ctx["surface"] == "book"
    fields = (["kana"] if L.reading else []) + ["tr", "voc", "en"]
    flags = {"keep": mode != "regloss", "regloss": mode == "regloss",
             "perfield": mode == "perfield", "reading": L.reading, "words": L.words,
             "seeded": L.words and mode != "regloss",
             "require_tr": L.require_tr, "optional_tr": not L.require_tr}
    subs = {
        "GLOSS_NOTE": "" if G.code == languages.DEFAULT_GLOSS else ", not in English",
        "A_LANGUAGE": _a(L.name),
        "SURFACE": ("%s reading edition" if book else "the captions of %s video")
                   % _a(L.name),
        "SURFACE_NOUN": "book" if book else "video",
        "OTHER_SURFACE": "video" if book else "book",
        "FIELD_LIST": _said(fields),
        "TEXT_FIELDS": _said(["fa"] + [f for f in fields if f != "voc"]),
        "REQUIRED": _said(_required(L)),
        "READING_FIELD": "kana" if L.reading else "tr",
        "UNIT": "sentence" if book else "caption",
        "UNITS": "sentences" if book else "captions",
        "LIST_KEY": "sentences" if book else "captions",
        "ADDRESS": "`at`" if book else "`i` and `start`",
    }
    return flags, subs


def assembled(ctx, units, mode, instructions=None, custom=None, options=None, flags=None, values=None):
    """The prompt for these units, in the parts the kit made it of.  The
    instructions are a person's own where they are given (lib/prompts.py),
    and `custom` names them in the version line.  `options` is what the
    request chose of the scheme of the transliteration and the short vowels
    (lib/promptkit.py OPTIONS); what it leaves unsaid is the book's or the
    video's own record of the scheme (its `translit`), else the default.
    `flags` and `values` take the place of what `substitutions` says, for a
    caller that has its reason (lib/skills.py leaves open what only a request knows).
    -> (promptkit.Assembled, counts)"""
    L, G = ctx["L"], ctx["G"]
    said = _evidence(ctx, units, mode)
    data, counts = _data(ctx, units, mode, said)
    if said.diagnostics:
        counts = dict(counts, analysis_notes=said.diagnostics)
    fl, subs = substitutions(ctx, mode)
    fl = dict(fl, evidence=bool(said))
    # THE TITLE AND THE CHUNKS ARE THE BOOK'S OR THE VIDEO'S, not the template's:
    # a title that says `{{DATA}}` is a title, and is put in as one
    return promptkit.assemble(
        "%s-region" % ctx["surface"], L, G, mode=mode, flags=dict(fl, **(flags or {})),
        values=dict(subs, **(values or {})),
        verbatim={"ABOUT": _about(ctx, counts), "DATA": data},
        instructions=instructions, custom=custom,
        options=promptkit.resolve("%s-region" % ctx["surface"], L, options, _facts(ctx))), counts


def _facts(ctx):
    """What the book's or the video's own record says of the options of a prompt: the scheme its
    transliteration is written in (book.json, video.json: "translit")."""
    return {"translit": ctx["meta"].get("translit")}


def render(ctx, units, mode, instructions=None, custom=None, options=None):
    """The prompt for these units.  -> (text, counts)"""
    a, counts = assembled(ctx, units, mode, instructions, custom, options)
    return a.text, counts


def _prompt(ctx, units, mode, prompt=None, options=None):
    """`prompt` is the id of one of the person's own prompts, or nothing for
    Parseh's: the instructions of it in place of Parseh's, the answer contract
    and the data Parseh's still.  `options` is what the request said of the
    scheme of the transliteration and the short vowels, as it said it: a value
    that is none of the option's is refused in words, one that does not apply
    (the short vowels of Italian) is left out, and the answer's `options` says
    what each came to."""
    if not units:
        raise Refused("nothing in this region can be sent: %s" % ctx["region"])
    try:
        chosen = prompts.resolve("%s-region" % ctx["surface"], prompt, ctx["L"])
    except prompts.NotFound as e:
        raise NotFound(str(e))
    except prompts.PromptsError as e:
        raise Refused(str(e))
    try:
        made, counts = assembled(ctx, units, mode, chosen and chosen.instructions,
                                 chosen and chosen.name, options)
    except promptkit.OptionError as e:
        raise Refused(str(e))
    except promptkit.PromptError as e:
        raise Refused(prompts.unmade(chosen, e) if chosen else
                      "the prompt could not be made: %s" % e)
    r = dict(counts, prompt=made.text, region=ctx["region"], folded=ctx["folded"],
             options=promptkit.describe("%s-region" % ctx["surface"], ctx["L"], made.options,
                                        _facts(ctx)),
             **ctx["echo"])
    if chosen:
        r["custom"] = {"id": chosen.id, "name": chosen.name, "kind": chosen.kind}
    # THE SHORT REQUEST for a chat that has the skill (lib/skills.py), made from the same prompt
    import skills
    r["skill"] = skills.safe(lambda: skills.for_region("%s-region" % ctx["surface"], made, ctx["L"], ctx["G"], mode,
                                                       chosen), "parseh-gloss")
    notes = []
    if not counts["fill"]:
        notes.append("nothing here is left to gloss: every chunk is glossed already"
                     + ("" if mode == "regloss" else
                        " -- tick re-gloss to have it glossed afresh"))
    if counts["chunks"] > LONG:
        notes.append("%d chunks is a long stretch: the LLM may answer over several "
                     "messages -- paste them all, one under the other -- or pick a "
                     "shorter one" % counts["chunks"])
    r["notes"] = notes
    return r


def book_prompt(book, first, last, regloss=False, perfield=False, prompt=None,
                translit=None, marks=None):
    """The prompt for a book region.  `translit` ("ipa" or "classic") and
    `marks` ("1", "0": the short vowels) are the options of the prompt, left
    to the book's own record and the defaults where not said.
    -> {prompt, region, units, chunks, fill, glossed, folded, notes, options,
    custom?}"""
    mode = _mode(regloss, perfield)
    ctx, units, _folded, _known = _book_units(book, first, last)
    return _prompt(ctx, units, mode, prompt, _asked(translit, marks))


def video_prompt(vdir, frm, to, regloss=False, perfield=False, prompt=None,
                 translit=None, marks=None):
    """The prompt for a video region.  -> as book_prompt, folded always 0"""
    mode = _mode(regloss, perfield)
    ctx, units, _segs = _video_units(vdir, frm, to)
    if not any(ch["glossable"] for u in units for ch in u["chunks"]):
        raise Refused("nothing in this region can be glossed: it holds no chunk of "
                      "%s text, only plain captions and the video's own framing"
                      % ctx["L"].name)
    return _prompt(ctx, units, mode, prompt, _asked(translit, marks))


def _asked(translit, marks):
    """The options a request named -> {name: value}, nothing for what it left out."""
    return promptkit.given({"translit": translit, "marks": marks})


# --- the answer ---------------------------------------------------------
def _entries(answer, surface):
    """Every unit the answer holds, in order, from every block."""
    if not isinstance(answer, str) or not answer.strip():
        raise Refused("the answer is empty: paste the LLM's reply")
    try:
        docs = json_blocks(answer)
    except ValueError as e:
        raise Refused(str(e))
    out = []
    for d in docs:
        if isinstance(d, list):
            out.extend(d)
            continue
        if not isinstance(d, dict):
            continue
        for k in ("sentences", "captions", "segments", "units"):
            if isinstance(d.get(k), list):
                out.extend(d[k])
                break
        else:
            if "chunks" in d:
                out.append(d)                   # a lone unit
    if not out:
        raise Refused("the answer holds no %s"
                      % ("sentences" if surface == "book" else "captions"))
    return out


class _Report(object):
    """What an apply found, as the route answers it."""

    def __init__(self, where):
        self.where = where
        self.kept, self.dropped, self.notes = [], [], []

    def keep(self, unit, ch, why):
        self.kept.append(dict(self.where(unit, ch), why=why))

    def drop(self, unit, ch, why):
        self.dropped.append(dict(self.where(unit, ch), why=why))


def _pairs(unit, chunks, L, rep):
    """The answer's chunks matched to the page's, by position.

    The same number of chunks: each is matched to the chunk in its place.  A
    different number: the answer divides the sentence differently, and only
    the chunks before and after the change -- the same text in the same
    place, so still the page's own chunks -- are matched; the ones in
    between are the division the answer changed, and are dropped."""
    page = unit["chunks"]
    norm = lambda s: CA.norm(s, L) if isinstance(s, str) else None
    fa = lambda a: norm(a.get("fa")) if isinstance(a, dict) else None
    joined = lambda xs: norm(L.word_sep.join(x if isinstance(x, str) else "" for x in xs))
    same_text = (joined([c["fa"] for c in page])
                 == joined([a.get("fa") if isinstance(a, dict) else "" for a in chunks]))
    redivided = ("the answer divides this %s differently; the division is kept as sent"
                 % ("sentence" if "at" in unit else "caption"))
    if len(chunks) == len(page):
        out = []
        for p, a in zip(page, chunks):
            if not isinstance(a, dict):
                rep.drop(unit, p, "the answer's chunk is not an object")
            elif fa(a) == norm(p["fa"]):
                out.append((p, a))
            elif same_text:
                rep.drop(unit, p, redivided)
            else:
                rep.drop(unit, p, "text does not match: the answer has «%s» here"
                         % _clip(a.get("fa") if isinstance(a.get("fa"), str) else ""))
        return out
    k = 0
    while k < min(len(page), len(chunks)) and fa(chunks[k]) == norm(page[k]["fa"]):
        k += 1
    t = 0
    while (t < min(len(page), len(chunks)) - k
           and fa(chunks[-1 - t]) == norm(page[-1 - t]["fa"])):
        t += 1
    head = list(zip(page[:k], chunks[:k]))
    tail = list(zip(page[len(page) - t:], chunks[len(chunks) - t:])) if t else []
    lost = page[k:len(page) - t]
    rep.drop(unit, None, "%s (%d chunk%s where it has %d)%s"
             % (redivided if same_text else
                "the answer's chunks do not give this %s's text back; the division "
                "is kept as sent" % ("sentence" if "at" in unit else "caption"),
                len(chunks), "" if len(chunks) == 1 else "s", len(page),
                "" if not lost else ": nothing is written to %s"
                % ", ".join("«%s»" % _clip(c["fa"], 20) for c in lost)))
    return head + tail


def _marks_on(ctx, marks):
    """Whether this request asks for the short vowels, said as the prompt's
    request said it (`marks`: "1" or "0", or the option's own words) and
    resolved by the kit: the surface's default where it says nothing -- no,
    so an apply that does not mention them is the apply it always was -- and
    never for a language whose record has no `strip`.  A word that is none of
    the option's is refused, in the kit's words, before anything is read."""
    try:
        chosen = promptkit.resolve("%s-region" % ctx["surface"], ctx["L"],
                                   promptkit.given({"marks": marks}))
    except promptkit.OptionError as e:
        raise Refused(str(e))
    return chosen.get("marks") == "marks"


def _vowelled(ctx, p, a, guarded):
    """The fa the answer's chunk `a` may put in the page's chunk `p`, or None:
    the answer's own text when it is the page's with marks added and nothing
    else, and the page's chunk has none (the module's docstring says why).

    COMPARED EXACTLY, NOT AS _pairs MATCHES THEM.  _pairs sets the marks
    aside and collapses whitespace, which is what lets a chunk be found; here
    the text that is WRITTEN must be the page's to the letter, the space and
    the joiner, so only the marks are stripped (and NFC, which orders them).
    `guarded` is told why marks the answer carried were not taken, and is told
    nothing when it carried none: that is what a model gives that was not
    asked for them, or did not do it, and it is the same answer as before."""
    if not ctx.get("marks"):
        return None
    got = a.get("fa")
    if not isinstance(got, str):
        return None
    L = ctx["L"]
    page = unicodedata.normalize("NFC", p["fa"]).strip()
    got = unicodedata.normalize("NFC", got).strip()
    if got == page or L.strip(got) == got:
        return None
    if L.strip(page) != page:
        guarded.append("`fa` already has its marks -- left as it is")
    elif L.strip(got) != page:
        guarded.append("`fa` differs from the page's in more than its marks (a space, "
                       "say) -- left as it is")
    else:
        return got
    return None


def _decide(ctx, unit, p, a, mode, rep):
    """What the answer's chunk `a` does to the page's chunk `p`: an action,
    or None -- with every reason it does less than it asks in `rep`, and
    what it tried to change that is protected in ONE `kept` line a chunk."""
    guarded = []
    act = _decided(ctx, unit, p, a, mode, rep, guarded)
    if guarded:
        rep.keep(unit, p, "; ".join(guarded))
    return act


def _decided(ctx, unit, p, a, mode, rep, guarded):
    L = ctx["L"]
    if not p["glossable"]:
        if any(isinstance(a.get(f), str) and a[f].strip() for f in GLOSS):
            guarded.append("plain text, never glossed -- left as it is")
        return None
    tried = [k for k in CONTEXT if k in a and a[k] not in (None, "", False)
             and _differs(a[k], p["extra"].get(k))]
    if tried:
        guarded.append("%s %s never written from an answer"
                       % (_said(tried), "is" if len(tried) == 1 else "are"))
    said = {}
    for f in GLOSS:
        v = a.get(f)
        if v is None:
            continue
        if not isinstance(v, str):
            rep.drop(unit, p, "%s must be text, not %s" % (f, type(v).__name__))
            return None
        said[f] = v.strip()
    old = p["vals"]
    was = _written(p, L)
    new = dict(old)
    if mode == "regloss":
        for f in p["slots"]:
            new[f] = said.get(f, "")
    elif not was:
        for f in p["slots"]:
            if said.get(f):
                new[f] = said[f]
    else:
        changed = [f for f in GLOSS if f in said and _differs(said[f], old[f])
                   and (mode != "perfield" or old[f].strip())]
        if mode == "perfield":
            for f in p["slots"]:
                if not old[f].strip() and said.get(f):
                    new[f] = said[f]
        if changed:
            guarded.append("already glossed -- left as it is (the answer changed %s)"
                           % _said(changed))
    changes = {f: new[f] for f in p["slots"] if _differs(new[f], old[f])}
    if not changes:
        return None
    after = dict(p["raw"], **{f: new[f] for f in p["slots"]})
    if CA.unwritten(after, L):
        # an answer with nothing for a chunk never takes a gloss off it
        rep.drop(unit, p, "the answer leaves it unglossed -- the gloss it has is kept")
        return None
    missing = [f for f in _required(L) if not (new.get(f) or "").strip()]
    if missing:
        why = "would leave it half glossed: missing %s" % _said(missing)
        if "kana" in missing and "kana" not in p["slots"]:
            why += " (\\%s has no kana slot)" % p.get("macro", "ch")
        rep.drop(unit, p, why)
        return None
    # THE SHORT VOWELS GO WITH A GLOSS THAT LANDS, and are checked below by the same doors
    vowels = _vowelled(ctx, p, a, guarded)
    if vowels is not None:
        changes = dict(changes, fa=vowels)
    for f, v in changes.items():
        m = wordline.NOT_TEXT.search(v)
        if m:
            rep.drop(unit, p, "%s carries U+%04X, which is not text"
                     % (f, ord(m.group())))
            return None
    if ctx["surface"] == "book":
        where = "%s chunk %d" % (unit["at"], p["j"] + 1)
        try:
            for f, v in changes.items():
                texwrite._value(f, v, L, where)
        except texwrite.Refused as e:
            rep.drop(unit, p, str(e))
            return None
    else:
        # the chunk as it would stand, asked of the checker annwrite asks --
        # and, as annwrite does, held only to what the answer INTRODUCES: a
        # word line already wrong in the file is not this answer's to refuse
        chunk = dict(p["raw"])
        for f, v in changes.items():
            if v:
                chunk[f] = v
            else:
                chunk.pop(f, None)
        where = "caption %d chunk %d" % (unit["i"], p["j"] + 1)
        before, errs = [], []
        CA.check_chunk(dict(p["raw"]), where, before.append, lambda w: None, L,
                       reorders=ctx["reorders"])
        CA.check_chunk(chunk, where, errs.append, lambda w: None, L,
                       reorders=ctx["reorders"])
        errs = annwrite._introduced(before, errs)
        if errs:
            rep.drop(unit, p, "; ".join(errs))
            return None
    kind = "fill" if not was else "replace" if mode == "regloss" else "complete"
    return {"unit": unit, "chunk": p, "changes": changes, "kind": kind}


def plan(ctx, units, entries, mode, rep, others):
    """Every action an answer asks for that may land, worked out from the
    files as they are now -> (actions, unanswered).  `others(address)` is
    the sentence that says why an address outside `units` is dropped: a
    folded paragraph of the region, another region of the book or the
    video, or nothing of it at all.  An entry for an address named twice
    replaces the earlier one -- a correction pasted under the answer -- and
    `unanswered` is every chunk the prompt asked for that the answer gave
    nothing and no line of `kept` or `dropped` already speaks of."""
    L = ctx["L"]
    book = ctx["surface"] == "book"
    here = {u["key"]: u for u in units}
    chosen = {}                                 # address -> the entry, later wins
    for n, e in enumerate(entries, 1):
        at = "entry %d of the answer" % n
        if not isinstance(e, dict):
            rep.dropped.append({"where": at, "why": "not an object"})
            continue
        if book:
            a = e.get("at")
            if not isinstance(a, str) or not a.strip():
                rep.dropped.append({"where": at, "why": 'it has no "at" naming its sentence'})
                continue
            key, at = _norm_at(a), "sentence %s" % a.strip()
        else:
            key = e.get("i")
            # the answer's start, made a number of seconds ONCE, before
            # either comparison below: _seconds says why
            given = e.get("start")
            start = _seconds(given)
            odd = start is not None and not math.isfinite(start)
            said = _clip("%s" % given, 24) + (", which is no number of seconds"
                                              if odd else "")
            if isinstance(key, bool) or not isinstance(key, int):
                near = [u for u in units if not u["plain"] and start is not None
                        and not odd and _finite(u["start"]) is not None
                        and abs(_finite(u["start"]) - start) <= NEAR]
                if len(near) != 1:
                    rep.dropped.append({"where": at, "why": 'it has no "i" naming its '
                                        'caption%s' % (
                                            "" if start is None else
                                            ", and its start (%s) is no number of "
                                            "seconds" % _clip("%s" % given, 24) if odd
                                            else ", and no caption of the region "
                                            "starts at %s" % said)})
                    continue
                key = near[0]["key"]
            at = "caption %s" % key
            u = here.get(key)
            if (u is not None and start is not None
                    and (odd or (_finite(u["start"]) is not None
                                 and abs(start - _finite(u["start"])) > NEAR))):
                # dropped here, before it can stand in for an entry that
                # does belong: a later block replaces an earlier one only
                # when it is about the same caption.  A start that is not a
                # finite number matches no caption, NaN included -- which
                # `abs(nan - x) > NEAR` alone would have let through
                rep.drop(u, None, "start does not match (the answer says %s, the "
                         "caption starts at %s): another video or another region?"
                         % (said, u["start"]))
                continue
        chosen[key] = (e, at)
    actions = []
    answered = set()
    for key, (e, at) in chosen.items():
        u = here.get(key)
        if u is None:
            rep.dropped.append(dict({"where": at, "chunk": None, "why": others(key)},
                                    **({"at": at[len("sentence "):]} if book else {"i": key})))
            continue
        if not book:
            if u["plain"]:
                if e.get("chunks"):
                    rep.drop(u, None, "a plain caption is never glossed")
                continue
        chunks = e.get("chunks")
        if not isinstance(chunks, list):
            rep.drop(u, None, "the answer gives it no chunks")
            continue
        for p, a in _pairs(u, chunks, L, rep):
            answered.add((key, p["j"]))
            act = _decide(ctx, u, p, a, mode, rep)
            if act:
                actions.append(act)
    # what the prompt asked for and the answer said nothing about -- not
    # counting a chunk already named in kept or dropped, or one whose whole
    # sentence or caption was dropped: those have their reason already
    unanswered = []
    addr = lambda r: r.get("at") if book else r.get("i")
    touched = {(addr(r), r.get("chunk")) for r in rep.kept + rep.dropped}
    for u in units:
        for ch in u["chunks"]:
            if _todo(ch, L, mode) and not any(act["chunk"] is ch for act in actions):
                w = rep.where(u, ch)
                if (addr(w), w["chunk"]) in touched or (addr(w), None) in touched:
                    continue
                w["why"] = ("not in the answer" if (u["key"], ch["j"]) not in answered
                            else "the answer gives it nothing")
                unanswered.append(w)
    return actions, unanswered


def _counts(actions):
    c = {"fill": 0, "complete": 0, "replace": 0, "vowelled": 0}
    for act in actions:
        c[act["kind"]] += 1
        if "fa" in act["changes"]:
            c["vowelled"] += 1
    return c


def _apply(ctx, units, entries, mode, confirm, others, write):
    if not isinstance(confirm, bool):
        raise Refused("confirm is true or false")
    rep = _Report(_book_where if ctx["surface"] == "book" else _video_where)
    actions, unanswered = plan(ctx, units, entries, mode, rep, others)
    c = _counts(actions)
    # `marks` says the short vowels were asked for, so that the page reports "vowelled N" (0 included)
    base = dict(ctx["echo"], region=ctx["region"], folded=ctx["folded"], kept=rep.kept,
                unanswered=unanswered, marks=bool(ctx.get("marks")))
    if mode == "regloss" and not confirm and c["replace"]:
        # nothing is written until the page has said so, with the number
        return dict(base, confirm_needed=True, replace=c["replace"], fill=c["fill"],
                    dropped=rep.dropped, notes=rep.notes, written=[],
                    filled=0, completed=0, replaced=0, vowelled=0, wrote=False)
    done = write(actions, rep)
    d = _counts(done)
    return dict(base, confirm_needed=False, filled=d["fill"], completed=d["complete"],
                replaced=d["replace"], vowelled=d["vowelled"], dropped=rep.dropped,
                notes=rep.notes, wrote=bool(done),
                written=[act["chunk"]["n"] if ctx["surface"] == "book"
                         else [act["unit"]["i"], act["chunk"]["j"]] for act in done])


def book_apply(book, first, last, answer, regloss=False, perfield=False, confirm=False,
               marks=None):
    """Put an LLM's answer for a book region into the chapter files.  `marks`
    ("1", "0") is the short vowels as the request asks them (_marks_on): with
    them the answer's fa may be written too, and `vowelled` counts the chunks.

    -> {confirm_needed, filled, completed, replaced, vowelled, marks, kept,
        dropped, unanswered, notes, written (data-c numbers), chunks, wrote,
        region, folded}
    or, for a re-gloss that would replace anything and was not confirmed,
       {confirm_needed: true, replace, fill, kept, dropped, ...} with nothing
       written.  The caller rebuilds the reader once when `wrote`.

    `chunks` is {"<data-c>": record} for every chunk written -- the record
    texwrite.edit_chunk read back off the file, the one __edit/chunk answers
    with -- so the page repaints exactly those in place, as it does after a
    save, instead of reloading and losing what it holds (an undo, the
    answer box)."""
    mode = _mode(regloss, perfield)
    ctx, units, folded, known = _book_units(book, first, last)
    ctx["marks"] = _marks_on(ctx, marks)
    entries = _entries(answer, "book")

    def others(key):
        if key in folded:
            # the entry already names the sentence (_book_where)
            return ("in a paragraph folded away in the reader (reading.json) -- "
                    "unfold it to gloss it")
        if key in known:
            return "outside the region you selected"
        return "no such sentence in this book"

    records = {}

    def write(actions, rep):
        done = []
        for act in actions:
            u, p = act["unit"], act["chunk"]
            try:
                r = texwrite.edit_chunk(u["path"], p["local"], act["changes"])
            except (texwrite.Refused, OSError) as e:
                rep.drop(u, p, str(e))
                continue
            for w in r.get("warnings") or []:
                rep.notes.append(dict(_book_where(u, p), note=w))
            records[str(p["n"])] = dict(r.get("chunk") or {}, index=p["n"])
            done.append(act)
        return done

    r = _apply(ctx, units, entries, mode, confirm, others, write)
    r["chunks"] = records
    return r


def video_apply(vdir, frm, to, answer, regloss=False, perfield=False, confirm=False,
                marks=None):
    """Put an LLM's answer for a video region into annotations.json.

    -> as book_apply, with `written` as [segment, chunk] pairs and `segments`
       {"<i>": segment} for every caption something was written to, so the
       player can redraw exactly those."""
    mode = _mode(regloss, perfield)
    ctx, units, segs = _video_units(vdir, frm, to)
    ctx["marks"] = _marks_on(ctx, marks)
    entries = _entries(answer, "video")

    def others(key):
        if not isinstance(key, int) or not 0 <= key < len(segs):
            return "no caption %s in this video (it has %d)" % (key, len(segs))
        return "caption %d is outside the region you selected" % key

    def write(actions, rep):
        done = []
        for act in actions:
            u, p = act["unit"], act["chunk"]
            try:
                annwrite.edit_chunk(vdir, u["i"], p["j"], act["changes"])
            except (ValueError, OSError) as e:
                rep.drop(u, p, str(e))
                continue
            done.append(act)
        return done

    r = _apply(ctx, units, entries, mode, confirm, others, write)
    r["segments"] = {}
    if r["wrote"]:
        now = annwrite.read(vdir)["segments"]
        for i in sorted({i for i, _j in r["written"]}):
            r["segments"][str(i)] = now[i]
    return r
