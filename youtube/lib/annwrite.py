#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Edit one chunk of a video's annotations.json, and leave the file a
person can still edit by hand.

    from annwrite import edit_chunk
    edit_chunk("videos/persian/Gbfc-2sy_pc", 2, 1, {"en": "Midas is a king.",
                                                    "col": "red"})

annotations.json is AUTHORED, not generated.  Somebody opens it in an
editor, runs a find-and-replace over a gloss they have been spelling two
ways, saves, and reloads the player.  So an edit made from the player has
to land as the edit a hand would have made -- one line moved in the diff,
the same indentation, the same key order, the same unescaped Persian --
or the two ways of working stop being the same file and the player wins
by default.  Everything here exists to keep that true.

Three rules, and the reasons they are rules:

  * MATCH THE FILE, not this module's taste.  The indent, whether
    non-ASCII is escaped and whether the file ends in a newline are read
    off the file on disk (_style) and written back unchanged.  Only a
    video with no annotations.json yet gets a shape of our choosing, and
    that shape is merge_parts.py's, so a file written here and a file
    written by the pipeline are the same file.

  * VALIDATE FIRST.  The edit goes through check_annotations before
    anything is written, and is refused -- in the checker's own words --
    if it INTRODUCES an error the file does not already have.
    Introduces, not has: a video is glossed a box at a time, so in the
    middle of the work it is half glossed by definition, and an editor
    that refuses to work until the video is finished cannot be how the
    video gets finished.  So a chunk left half glossed is not this door's error
    (_errors); what it refuses instead is the one step backwards a hand
    can take, emptying a box a finished gloss needs (_emptied).

  * WRITE ATOMICALLY.  A temp file beside it, then a rename, so that a
    crash or a full disk cannot leave a video holding half a JSON file --
    which every reader of it, the player included, sees as no video at
    all.

Everything a caller gets wrong raises ValueError carrying a message meant
to be shown to the person who typed it; the server hands those back as a
400.  A video that has never been annotated raises OSError from the open,
because that is a missing file and not a bad request.

COLOURS is re-exported (`from annwrite import COLOURS`) so that whatever
draws the four buttons takes the four names from the checker rather than
writing them out again -- the same rule the registry keeps for languages.

Standard library only: this is imported by the server.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "lib"))
import chunkdiv                                            # noqa: E402
import wordline                                            # noqa: E402
import pathlock                                            # noqa: E402
from check_annotations import (CHUNK_FIELDS, COLOURS,      # noqa: E402,F401
                               check_segments, departs, parse_transcript,
                               required, unwritten, video_language)

# The fields the player may set.  Not every field a chunk can carry: "plain"
# is the author's, has no box in the player, and decides whether a chunk is
# asked for a gloss at all -- flipping it from an edit box would silently
# drop a chunk out of the checker's sight.  The note is the person's: it is
# the aside under the meaning (what the transcript really heard, a cultural
# point), a model leaves one, and it goes stale the moment the transcript is
# mended -- and it used to be the one field only the file could take off.
# Refusing everything else also means a mistyped key ("col0r") is answered on
# the spot instead of settling into the file, where only the checker's
# unknown-field warning would ever mention it again.  The word line and the
# note are two of these, although the divide sheet draws no box for either
# (_settle says what that changes).
EDITABLE = ("fa", "words", "kana", "tr", "voc", "en", "note", "col", "free")
# ...of which "free" is the one that is not text: true or gone (a chunk that
# departs from transcript.txt, check_annotations.departs)
_FLAGS = ("free",)
# ...and of those, the ones a page may leave out without clearing them: the
# divide sheet draws a box for none of them, so a divide that says nothing
# about them must leave what chunkdiv carried across rather than read the
# silence as "take it off" -- which for "free" would quietly put a caption the
# annotator has taken charge of back under transcript.txt, and for the note
# would wipe every note a cut or a join touches.
_CARRIED = ("words", "note", "free")

# What merge_parts.py writes, and so the shape of every annotations.json
# in the toolbox until a hand reformats one: a single space of indent,
# the target language unescaped (a file full of م is not one anybody
# edits), a newline at the end.
DEFAULT_STYLE = {"indent": " ", "ensure_ascii": False, "newline": True}


def path_of(video_dir):
    return os.path.join(video_dir, "annotations.json")


def _style(text):
    """The shape of the JSON file as it is on disk: the indent, whether
    non-ASCII is escaped, whether it ends in a newline.

    Sniffed rather than assumed, because the file is allowed to have been
    reformatted by hand -- and rewriting a two-space file with one-space
    indent turns a one-word edit into a diff of every line in the video,
    which is the one thing this module exists to prevent.
    """
    st = dict(DEFAULT_STYLE)
    st["newline"] = text.endswith("\n")
    # the first line indented at all gives the unit: the file opens "{"
    # and then "<indent>"video": ...", so in practice this is line 2
    for line in text.splitlines()[1:]:
        lead = line[:len(line) - len(line.lstrip(" \t"))]
        if lead:
            st["indent"] = lead
            break
    # One raw non-ASCII character proves ensure_ascii was off.  Escapes
    # and no raw character at all prove it was on.  A file that is pure
    # ASCII either way -- a Latin-script video with no accent in it --
    # keeps the pipeline's setting, which escapes nothing.
    if not text.isascii():
        st["ensure_ascii"] = False
    elif "\\u" in text:
        st["ensure_ascii"] = True
    return st


def read(video_dir):
    """The parsed annotations.json.

    A file that is not there raises OSError: the video has never been
    annotated, which is a different answer from a bad edit.  A file that
    is there and broken raises ValueError naming the path, so that a
    syntax error inside the video cannot be read as a fault in the
    request that found it.
    """
    with open(path_of(video_dir), encoding="utf-8") as f:
        text = f.read()
    try:
        ann = json.loads(text)
    except ValueError as e:
        raise ValueError("%s: not JSON (%s)" % (path_of(video_dir), e))
    if not isinstance(ann, dict) or not isinstance(ann.get("segments"), list):
        raise ValueError("%s: no \"segments\" list" % path_of(video_dir))
    return ann


def write(video_dir, ann):
    """Write annotations.json in the shape it already has, atomically.

    The style is read off the file being replaced rather than carried
    along from an earlier read(), so that no caller can lose it by
    passing the data through a queue or a request handler; a video with
    no annotations.json yet is written the way merge_parts.py would have
    written it.
    """
    path = path_of(video_dir)
    try:
        with open(path, encoding="utf-8") as f:
            st = _style(f.read())
    except OSError:
        st = dict(DEFAULT_STYLE)
    tmp = pathlock.tmp(path)        # this write's own name (TO-DO §3.10)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(ann, f, ensure_ascii=st["ensure_ascii"],
                      indent=st["indent"])
            if st["newline"]:
                f.write("\n")
        os.replace(tmp, path)      # never a half file under a real name
    except BaseException:
        # a full disk stops the dump halfway; the half file must not be
        # left in the video's directory, which the owner browses, backs
        # up and hands around as the video
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _meta(video_dir):
    """video.json, or {} -- it carries the language, and a video that
    declares none is Persian, the rule check_annotations already follows.
    A broken video.json is not this module's error to raise: the checker
    reports it, and an edit to a gloss should not be blocked by it."""
    try:
        with open(os.path.join(video_dir, "video.json"), encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return {}
    return meta if isinstance(meta, dict) else {}


def _index(v, n, what, where=""):
    """v as a list index into n items, or ValueError saying which end it
    fell off.  bool is refused although it is an int, because JSON's true
    would otherwise address chunk 1 -- the player sends these two numbers
    from a page that may be stale, and a stale page must be told so, not
    quietly handed its neighbour to edit."""
    if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v < n:
        raise ValueError("no %s %r%s: there %s %d"
                         % (what, v, where, "is" if n == 1 else "are", n))
    return v


def _caption(ann, seg):
    """The caption (segment) at `seg`."""
    segs = ann["segments"]
    return segs[_index(seg, len(segs), "segment")]


def _retext(sg, L, was_free=False):
    """The caption's own text, from its chunks.

    Only for a caption that departs from the transcript: there the chunks
    ARE the text, and the fidelity check holds the two together, so a
    corrected chunk has to take the caption's text with it.  Everywhere
    else the text is transcript.txt's and nothing here rewrites it.

    `was_free` is the mark as it stood BEFORE this edit, and is the way
    back: an edit that takes the mark off gets its text written from its
    chunks one last time, so putting the words back as the transcript has
    them and unticking the box in the same save leaves a caption that
    reproduces the transcript again.  Without it the text would keep the
    correction it no longer has leave to make and nothing could be
    unticked at all.
    """
    chunks = sg.get("chunks") or []
    if not (departs(sg) or was_free) or not chunks:
        return
    sg["text"] = L.word_sep.join((ch.get("fa") or "") if isinstance(ch, dict) else ""
                                 for ch in chunks)


def _at(ann, seg, chunk):
    """The chunk at (seg, chunk), or ValueError."""
    segs = ann["segments"]
    sg = segs[_index(seg, len(segs), "segment")]
    chunks = sg.get("chunks") if isinstance(sg, dict) else None
    if not isinstance(chunks, list) or not chunks:
        # a plain caption is shown as it stands and holds no chunks at all
        raise ValueError("segment %d carries no chunks" % seg)
    ch = chunks[_index(chunk, len(chunks), "chunk",
                       " in segment %d" % seg)]
    if not isinstance(ch, dict):
        raise ValueError("segment %d chunk %d is not an object" % (seg, chunk))
    return ch


def _set(ch, key, value):
    """Set one field of a chunk, keeping the chunk's own key order.

    An empty value REMOVES the key, because absent and empty already mean
    the same thing to every reader of this format ("col": "" is no
    colour, "voc": "" is no vocabulary line) and leaving the empty string
    behind puts a line in the file that says nothing.

    A key the chunk did not have is slotted in at its CHUNK_FIELDS
    position among the keys that are there -- so a colour lands after the
    gloss and not in front of the text -- while the keys already present
    are never moved.  Reordering a chunk somebody arranged by hand is
    exactly the whole-file diff this module refuses to make, so an
    unknown key (one a later format added, or a hand did) ranks last and
    stays where it is.
    """
    if not value:
        ch.pop(key, None)
        return
    if key in ch:
        ch[key] = value
        return
    rank = CHUNK_FIELDS.index(key)
    items = list(ch.items())
    pos = len(items)
    for i, (k, _v) in enumerate(items):
        kr = CHUNK_FIELDS.index(k) if k in CHUNK_FIELDS else len(CHUNK_FIELDS)
        if kr > rank:
            pos = i
            break
    items.insert(pos, (key, value))
    ch.clear()                     # in place: the list still holds this dict
    ch.update(items)


def _errors(ann, L, captions=None):
    """Every error check_annotations finds in these segments, as a list.

    The whole file and not merely the segment being edited, so that each
    message carries the segment number the reader actually sees.  The
    transcript is not passed (captions=None) for an ordinary edit: a
    chunk's gloss cannot change a caption's text, its start or its
    chapter, so those checks can neither newly pass nor newly fail -- and
    a video being written from nothing may have no transcript.txt yet.

    An edit that moves the "free" mark is the exception, and passes the
    captions in (_transcript): the mark is exactly what decides whether a
    caption is held to the transcript, and taking it off a caption whose
    text has departed must be refused, and refused in the checker's own
    words, or the file would go back under a rule it no longer keeps.

    A chunk HALF GLOSSED -- the meaning typed, the transliteration not yet
    -- is not an error here: the checker's `half` messages are dropped.
    Every door that writes through this one leaves it so on purpose: the
    ✎ form fills a chunk a box at a time, a cut hands the second half a
    meaning nobody has typed yet, a hand editing the file does the same,
    and a caption moved (captimes) changes no chunk at all.  A chunk
    nobody has glossed yet is no error anywhere.  What a hand must not do
    -- empty a box a finished gloss needs -- edit_chunk refuses by its own
    rule (_emptied), and the checker still lists every half-glossed chunk
    on the command line.
    """
    errors = []
    check_segments(ann["segments"], captions, errors.append, lambda w: None,
                   L, half=lambda m: None)
    return errors


def _transcript(video_dir, L):
    """transcript.txt as check_annotations reads it, or None when the video
    has none yet (a draft being written from nothing)."""
    tpath = os.path.join(video_dir, "transcript.txt")
    return parse_transcript(tpath, L) if os.path.exists(tpath) else None


# The way out of the refusal below, said in the words the book reader's chunk
# sheet uses for the same rule (lib/texwrite.py), since the two sheets carry
# the same button.
_DELETE = ("empty every box of the gloss (\"delete gloss\") to take the "
           "whole gloss off")


def _emptied(old, ch, L, where):
    """Refuse an edit that EMPTIES a box a finished gloss needs.

    A chunk nobody has glossed yet is legal everywhere, and so is one being
    filled in a box at a time: an edit that writes an en beside a blank tr
    is saved, and the checker lists what the chunk still lacks.  What is
    refused is emptying a field the language requires (check_annotations.
    required: en always, tr where the language romanises every chunk, kana
    where it has a reading) that held something before this edit, because
    that turns a finished gloss into a half-finished one -- UNLESS the
    edit leaves the whole chunk unglossed (check_annotations.unwritten,
    which does not count a reading still exactly as the word line proposed
    it, nor a kana at all in a language with no reading): emptying every
    box at once is how a gloss is deleted, and the chunk goes back to being
    one nobody has started, its text, word line, colour, note and
    transcript mark kept.  So in Chinese or Persian, emptying tr, voc and
    en is a delete even where an LLM's answer left a stray kana beside
    them -- the boxes the player shows are every box of the gloss there,
    and the kana, which nothing reads, is left as it is (the checker warns
    of it) unless the page sends it emptied too.  A field sent blank that was
    already blank changes nothing and is never refused, and voc may always
    be emptied -- no language requires it.

    `old` is the chunk as it was, `ch` as the edit leaves it.  The book
    reader's chunk sheet keeps the same rule (texwrite._check_required).
    """
    if unwritten(ch, L):
        return
    why = {"en": "a glossed phrase needs its meaning -- check_annotations.py "
                 "calls an empty en an error",
           "tr": "%s romanises every phrase, so tr cannot be emptied on its "
                 "own" % L.name,
           "kana": "%s needs the reading of every phrase, so kana cannot be "
                   "emptied on its own" % L.name}
    for f in required(ch, L):
        was, now = old.get(f), ch.get(f)
        if (isinstance(was, str) and was.strip()
                and not (isinstance(now, str) and now.strip())):
            raise ValueError("%s: %s; %s" % (where, why[f], _DELETE))


def _introduced(before, after):
    """The errors in `after` that were not already in `before`.

    Counted rather than set-subtracted: one message can legitimately
    stand twice -- two chunks of a segment both missing 'en' -- and an
    edit that adds the second copy has broken something even though the
    words were already on the list.
    """
    left = list(before)
    out = []
    for e in after:
        if e in left:
            left.remove(e)
        else:
            out.append(e)
    return out


def _cannot(bad, divide=False):
    """The refusal of a key a page may not set: the keys it may, and -- for
    "plain", the one a person might reach for -- why it is not among them.  A
    mistyped key is told the list alone, which is all there is to say of it."""
    why = []
    if "plain" in bad:
        why.append("plain decides whether a phrase is asked for a gloss at all, "
                   "so it belongs to whoever authored the video")
    if divide:
        why.append("what a divide does not name is carried across unchanged")
    return "cannot set %s on a chunk: %s%s" % (
        ", ".join(map(repr, bad)), ", ".join(EDITABLE),
        " -- " + "; ".join(why) if why else "")


@pathlock.serialised(lambda video_dir, *_a, **_k: video_dir)
def edit_chunk(video_dir, seg, chunk, fields):
    """Change some of one chunk's fields; return the chunk as it now is.

    `fields` names any of EDITABLE and only those: a field it does not
    mention is left alone, and a field whose value is empty is removed
    from the chunk.  Values are text, and are trimmed -- a text box hands
    back whatever spaces the typist left, and a gloss differing from its
    neighbour by a trailing space is a diff nobody can read.

    The note is one of them: the aside under the meaning is the person's to
    change or to take off (an emptied box removes the key), and it is no gloss
    -- a phrase with only a note is still one nobody has glossed
    (check_annotations.unwritten), and "delete gloss" leaves it where it is.

    Setting "col" to one of check_annotations.COLOURS marks the chunk;
    setting it to "" clears the mark.  The colour means nothing to any
    tool -- it is the reader's own -- but it is spelled and checked the
    same as the books' \\Cred and friends, so the two doors agree.

    Editing "fa" is narrow by design.  The caption's text belongs to
    transcript.txt, and the fidelity check holds the chunks and the text
    together, so an fa edit may vocalise a chunk or repunctuate it but
    may not change its words: moving a word to the next chunk is a
    re-split, which is not one chunk's edit and is refused as one.  UNLESS
    THE CHUNK IS MARKED "free" -- what YouTube heard is sometimes wrong,
    and a chunk marked so is the annotator's: its caption's text is written
    from its chunks and is no longer held against transcript.txt.  Send the
    mark with the edit it permits, as the reading editions' chunk sheet
    sends its own (lib/reading.py).  A chunk
    divided into words holds its text a second time, in "words", so an fa
    edit that leaves the line behind is refused by check_chunk as well: send
    the two together.

    The gloss is filled a box at a time -- an en typed beside a blank tr is
    saved -- and taken off whole: sending tr, voc, en and kana all empty
    ("delete gloss") leaves the chunk as one nobody has glossed yet, its
    fa, word line, colour, note and transcript mark untouched.  What is
    refused is emptying ONE box a finished gloss needs while the rest stays
    (_emptied says why, and the refusal says how to delete instead).

    A word line edited on a chunk nobody has glossed yet takes its proposed
    reading with it: the reading lib/draft.py proposed from the old line is
    proposed again from the new one (and goes when the line is taken off),
    so the chunk stays blank -- unless the edit sends that reading too,
    which is then the person's.

    A refused edit writes nothing at all: the file is byte for byte as it
    was, and the caller has the checker's message to show.
    """
    if not isinstance(fields, dict) or not fields:
        raise ValueError("nothing to change")
    clean = {}
    for k, v in fields.items():
        if k not in EDITABLE:
            raise ValueError(_cannot([k]))
        if v is None:                      # JSON null: the player's way of
            v = ""                         # saying "clear this box"
        if k in _FLAGS:
            if not isinstance(v, bool):
                raise ValueError("%s is true or false, not %s"
                                 % (k, type(v).__name__))
            clean[k] = v or ""             # false: _set removes the key
            continue
        if not isinstance(v, str):
            raise ValueError("%s must be text, not %s"
                             % (k, type(v).__name__))
        clean[k] = v.strip()

    ann = read(video_dir)
    L = video_language(video_dir, _meta(video_dir), ann)
    sg = _caption(ann, seg)
    ch = _at(ann, seg, chunk)
    # only an edit that moves the mark is weighed against the transcript,
    # so every other edit costs and refuses exactly what it always did
    caps = _transcript(video_dir, L) if "free" in clean else None
    before = _errors(ann, L, captions=caps)
    was_free = departs(sg)
    old = dict(ch)
    # A WORD LINE EDITED UNDER A PROPOSED READING.  A chunk nobody has
    # glossed yet may carry the reading lib/draft.py proposed from its line
    # (kana where the language has a reading, tr where it has not; unwritten
    # does not count it).  An edit that sends only "words" -- a boundary
    # moved, a reading corrected in the line -- would leave that OLD reading
    # beside the NEW line, where it is no longer the line's proposal: the
    # chunk would read as written though nobody wrote a gloss ("missing 'en'"
    # from the checker, "delete gloss" offered, the region fill passing it
    # over).  So the reading is proposed again from the new line, as _split
    # and _join already propose it for each chunk they make (_unseeded,
    # _seeded), and a line taken off takes the proposal with it: the chunk
    # stays blank.  Only when the edit does not send the reading itself (one
    # typed in the same edit is the person's), and only on a chunk that was
    # blank with its reading still the old line's proposal.  lib/texwrite.py
    # does the same for the books.
    if "words" in clean:
        _bare, seed_field = _unseeded(old, L)
        if seed_field and seed_field not in clean:
            proposed = _seeded(dict(old, words=clean["words"]), seed_field, L)
            clean[seed_field] = proposed.get(seed_field, "")
    for k, v in clean.items():
        _set(ch, k, v)
    _emptied(old, ch, L, "segment %d (start %s) chunk %d"
             % (seg, sg.get("start"), chunk))
    # a caption that departs from the transcript is its chunks' own: the
    # text follows them, and the checker no longer holds it to what YouTube
    # heard.  One that does not depart keeps transcript.txt's text, so an fa
    # edit that changes the words is refused there, as it always was
    _retext(sg, L, was_free)
    new = _introduced(before, _errors(ann, L, captions=caps))
    if new:
        # the file has not been opened for writing at all, so there is
        # nothing to undo -- ann is this call's own copy and goes away
        raise ValueError("; ".join(new))
    write(video_dir, ann)
    return ch


# --- where a chunk ends -------------------------------------------------
# The checker names a chunk by its number in its segment ("segment 1 (start
# 6) chunk 2: missing 'en'"), and dividing a chunk renumbers every one after
# it.  _introduced compares messages as strings, so without this every
# pre-existing complaint about a later chunk would come back under a new
# number and be counted as a fresh one -- refusing an operation that made
# nothing worse.  Only the segment being worked on is blurred, so a real new
# error anywhere else still stands out by name.
def _blur(msgs, seg):
    pat = re.compile(r"^(segment %d \(.*?\) chunk )\d+" % seg)
    return [pat.sub(r"\1N", m) for m in msgs]


def _order(ch):
    """A chunk's keys in CHUNK_FIELDS order, with anything unknown last and
    in the order it arrived.  A chunk built here has never been through a
    hand, so it is written in the file's own order rather than in whatever
    order the fields were worked out."""
    known = [(CHUNK_FIELDS.index(k), i, k) for i, k in enumerate(ch)
             if k in CHUNK_FIELDS]
    rest = [(len(CHUNK_FIELDS), i, k) for i, k in enumerate(ch)
            if k not in CHUNK_FIELDS]
    return {k: ch[k] for _r, _i, k in sorted(known + rest)}


def _keep_blanks(new, old):
    """Put back the slots the old chunk carried as an explicit empty string.

    lib/draft.py writes "kana", "tr", "voc" and "en" as "" on purpose -- "an
    empty slot is something to fill where a missing key is something to
    remember" -- and a chunk that came out of dividing one of those should
    still be a chunk somebody can see the shape of.  Not the word line: a
    blank one is no slot but an error (check_chunk), and a division that
    kept it would make two of it.
    """
    for k, v in old.items():
        if (isinstance(v, str) and not v.strip() and k not in new
                and k != "words"):
            new[k] = ""
    return new


# the two keys that are flags and not text: `plain` says what KIND of chunk
# this is, "free" what its caption's text is held against.  Neither is
# something chunkdiv divides, and neither is text
_FLAGKEYS = ("plain",) + _FLAGS


def _typed(chunks, seg):
    """Every field of every chunk of one caption is text (`plain` and "free"
    excepted, which are flags).

    chunkdiv works on strings throughout, so a caption holding a number where
    a gloss should be would come back from it as a TypeError -- which the
    route does not catch, and which reaches the page as a 500 with a Python
    type name in it instead of a sentence about the file.
    """
    for j, ch in enumerate(chunks):
        if not isinstance(ch, dict):
            raise ValueError("segment %d chunk %d is not an object" % (seg, j))
        for k, v in ch.items():
            if k in _FLAGKEYS:
                continue
            if not isinstance(v, str):
                raise ValueError("segment %d chunk %d: %s is %s, and every "
                                 "field of a chunk is text"
                                 % (seg, j, k, type(v).__name__))


def _unseeded(ch, L):
    """(the chunk as chunkdiv should cut or join it, the field its reading was
    taken out of -- None when nothing was).

    An unglossed chunk of a language divided into words may carry the
    reading lib/draft.py proposed from its word line (check_annotations.
    unwritten does not count it as anybody's writing).  chunkdiv cannot
    divide that reading: a romanisation it cannot count the words of, or a
    kana that does not open with the first half's own text, goes whole to
    the first half -- which then reads as written, a chunk half glossed by a
    cut, while the second reads as blank.  So the reading comes off before
    chunkdiv sees the chunk and is proposed again from each new chunk's own
    line afterwards (_seeded): a blank chunk divides into two blank halves,
    and two blank chunks join into one blank chunk.  lib/texwrite.py does
    the same for the books."""
    field, seeded = wordline.seed(ch, L)
    if field and seeded and isinstance(ch.get(field), str) \
            and ch[field].strip() and unwritten(ch, L):
        return {k: v for k, v in ch.items() if k != field}, field
    return ch, None


def _seeded(ch, field, L):
    """`ch` with the reading in `field` proposed from its own word line, as
    lib/draft.py proposes one, or with none when the chunk has no line to
    read (a join drops a line only one side had) -- a chunk unwritten()
    calls blank either way.  `ch` unchanged when `field` is None."""
    if field is None:
        return ch
    out = {k: v for k, v in ch.items() if k != field}
    _field, reading = wordline.seed(out, L)
    if reading:
        out[field] = reading
    return _order(out)


def _split(ch, at, L, seg, i):
    """chunkdiv.split, with a word line that cannot be read refused by the
    chunk's address.  chunkdiv reads the line to find where its words end, so
    an unreadable one stops the division; the grammar's own sentence says
    what is wrong but not where, which on a page of captions is the half the
    reader needs.  The line is mended with an edit of "words" first.  A
    blank chunk's proposed reading is proposed again for each half
    (_unseeded)."""
    bare, field = _unseeded(ch, L)
    try:
        a, b, why = chunkdiv.split(bare, at, L, chunkdiv.AUTO)
    except wordline.WordsError as e:
        raise ValueError("segment %d chunk %d: its words cannot be divided "
                         "until the line is mended -- %s" % (seg, i, e))
    return _seeded(a, field, L), _seeded(b, field, L), why


def _join(a, b, L):
    """chunkdiv.merge of two chunks, (chunk, notes) -- with the proposed
    reading of a pair nobody has glossed yet proposed again for the chunk
    they become (_unseeded says why).  A pair with anything written in
    either is joined as it stands."""
    ba, fa_ = _unseeded(a, L)
    bb, fb_ = _unseeded(b, L)
    if (fa_ or fb_) and unwritten(a, L) and unwritten(b, L):
        one, notes = chunkdiv.merge(ba, bb, L, chunkdiv.AUTO)
        return _seeded(one, fa_ or fb_, L), notes
    return chunkdiv.merge(a, b, L, chunkdiv.AUTO)


def _asked(side, name):
    """What a page may set on a chunk: EDITABLE, and only that.

    edit_chunk refuses the rest by name and says why (the comment over
    EDITABLE); a divide must refuse them for the same reason and not for a
    weaker one, or the route that moves a boundary becomes the way round the
    rule the route that edits a field keeps.
    """
    if not isinstance(side, dict):
        raise ValueError("the %s chunk must be an object" % name)
    bad = sorted(k for k in side if k not in EDITABLE)
    if bad:
        raise ValueError(_cannot(bad, divide=True))
    out = {}
    for k, v in side.items():
        if v is None:
            v = ""
        if not isinstance(v, str):
            raise ValueError("%s must be text, not %s" % (k, type(v).__name__))
        out[k] = v.strip()
    return out


def _settle(proposed, asked, was):
    """The chunk to write.

    The fields a page may set are the page's, absence included: what it sends
    IS the gloss, so a field it leaves out is a field the chunk has not got.
    Everything else -- `plain`, a key a later format added -- comes from what
    chunkdiv proposed, which is to say from the chunk being divided, and no page
    has a say in it.  `asked` is None for a caller that wants the proposal whole
    (the command line, and the tests).

    The word line, the note and the transcript mark are the exceptions
    (_CARRIED).  The divide sheet draws no box for any of them, so a page that
    leaves one out has said nothing about it, and what chunkdiv divided or
    joined stands -- the note on the first half of a cut, both notes joined by a
    join; one the page does send replaces it, and an empty one removes it.

    Then emptied fields are dropped, as every writer here drops them, and the
    slots the old chunk kept explicitly blank are kept blank.
    """
    page = (asked if asked is not None
            else {k: v for k, v in proposed.items() if k in EDITABLE})
    out = {k: v for k, v in proposed.items()
           if k not in EDITABLE or (k in _CARRIED and k not in page)}
    out.update(page)
    out = {k: v for k, v in out.items()
           if not (isinstance(v, str) and not v.strip())}
    return _order(_keep_blanks(out, was))


def _divide(video_dir, seg, fn, what):
    """The shape both operations share: read, find the segment, let `fn`
    rewrite its chunk list, refuse whatever that introduced, write.

    `fn` is handed the chunk list and returns the new one.  The segment's own
    keys -- text, start, chapter, plain -- are never passed to it and never
    touched: they belong to transcript.txt, and check_segments is called here
    without the captions (as it is for an edit) precisely because they cannot
    change.

    What comes out may be glossed, unglossed or half glossed, whatever went
    in: cutting a chunk nobody has glossed makes two of them, which is
    legal everywhere, and cutting a finished one hands the second half a
    meaning nobody has typed yet unless the sheet's boxes are filled -- the
    middle of the work, which _errors does not count, so re-chunking is
    never held up by a gloss that is still to come.  Everything else the
    checker says is weighed here exactly as for an edit: the texts still
    reproducing their caption, the word lines, the colours, the types.
    """
    ann = read(video_dir)
    meta = _meta(video_dir)
    L = video_language(video_dir, meta, ann)
    segs = ann["segments"]
    sg = segs[_index(seg, len(segs), "segment")]
    if isinstance(sg, dict) and sg.get("plain"):
        raise ValueError("segment %d is a plain caption: it is shown as it "
                         "stands and holds no chunks to divide" % seg)
    chunks = sg.get("chunks") if isinstance(sg, dict) else None
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("segment %d carries no chunks" % seg)
    before = _errors(ann, L)
    made = fn(list(chunks), L)
    if not made:
        raise ValueError("a caption cannot be left with no chunks")
    sg["chunks"] = made
    # blurred to compare, plain to report: the numbers are what makes a
    # renumbered old complaint look new, and they are also the only way
    # somebody reading the refusal finds the chunk it is about
    after = _errors(ann, L)
    left, new = list(_blur(before, seg)), []
    for real, blurred in zip(after, _blur(after, seg)):
        if blurred in left:
            left.remove(blurred)
        else:
            new.append(real)
    if new:
        raise ValueError("; ".join(new))
    write(video_dir, ann)
    return {"segment": seg, "chunks": made, "count": len(made), "what": what}


@pathlock.serialised(lambda video_dir, *_a, **_k: video_dir)
def merge_chunks(video_dir, seg, chunk, fields=None):
    """Join chunk `chunk` of segment `seg` with the one after it.

    `fields` is the joined chunk, whole; when it is None chunkdiv.merge works
    it out -- the texts end to end with the language's word separator, the
    romanisations and meanings with a space, the vocabulary with its own
    separator (a middle dot for a plain line, a semicolon once the line holds
    one of the books' macros) -- and its notes come back with the answer.  A
    colour the two did not share, and anything else that could not simply be
    put end to end, is named there rather than lost quietly.

    Returns {segment, chunks, count, what, index, notes}: `chunks` is the
    segment's whole new list, because every chunk after the join has moved and
    the page has to be redrawn from it rather than patched.
    """
    notes = []

    def join(chunks, L):
        i = _index(chunk, len(chunks), "chunk", " in segment %d" % seg)
        if i + 1 >= len(chunks):
            raise ValueError("chunk %d is the last of segment %d: there is "
                             "nothing after it to join it to" % (i, seg))
        a, b = chunks[i], chunks[i + 1]
        if not isinstance(a, dict) or not isinstance(b, dict):
            raise ValueError("segment %d chunk %d is not an object" % (seg, i))
        _typed([a, b], seg)
        one, why = _join(a, b, L)
        notes.extend(why)
        asked = _asked(fields, "joined") if fields is not None else None
        return chunks[:i] + [_settle(one, asked, a)] + chunks[i + 2:]

    out = _divide(video_dir, seg, join, "merge")
    out["index"] = chunk
    out["notes"] = notes
    return out


@pathlock.serialised(lambda video_dir, *_a, **_k: video_dir)
def split_chunk(video_dir, seg, chunk, first, second):
    """Cut chunk `chunk` of segment `seg` into the two given, in that order.

    The two are whole chunks, as chunkdiv.split proposes them and a hand has
    since typed over them.  Their texts must be one of the places the chunk
    divides -- character for character, not merely something that compares
    equal: the fidelity check strips the harakat before it looks, so a cut
    that fell inside a Persian word would pass it and leave a bare mark
    opening the second chunk.  A split divides; changing a letter is what
    edit_chunk is for.

    Returns {segment, chunks, count, what, index}.
    """
    def cut(chunks, L):
        i = _index(chunk, len(chunks), "chunk", " in segment %d" % seg)
        ch = chunks[i]
        if not isinstance(ch, dict):
            raise ValueError("segment %d chunk %d is not an object" % (seg, i))
        _typed([ch], seg)
        ask_a = _asked(first, "first")
        ask_b = _asked(second, "second")
        was = ch.get("fa") or ""
        places = chunkdiv.cuts(was, L)
        pair = [ask_a.get("fa") or "", ask_b.get("fa") or ""]
        if pair not in [[c["a"], c["b"]] for c in places]:
            raise ValueError(
                "those two texts are not this chunk divided in two -- a split "
                "moves the boundary and changes no letter. It divides at: %s"
                % (" | ".join("%s / %s" % (c["a"], c["b"]) for c in places)
                   or "nowhere: %s" % ("it is one word, and a language written "
                                       "with spaces divides at a space"
                                       if L.spaced else "it is one character")))
        at = next(c["at"] for c in places
                  if [c["a"], c["b"]] == pair)
        pa, pb, _why = _split(ch, at, L, seg, i)
        return chunks[:i] + [_settle(pa, ask_a, ch),
                             _settle(pb, ask_b, ch)] + chunks[i + 1:]

    out = _divide(video_dir, seg, cut, "split")
    out["index"] = chunk
    return out


def divide_preview(video_dir, seg, chunk):
    """What a page needs to offer both operations on one chunk.

        {segment, index, chunk, cuts, next, merge, merge_error}

    The same answer the books' texwrite.divide_preview gives, in the same
    shape, so that the two pages draw one thing twice rather than two things
    once: `cuts` is every place the chunk divides, each carrying the two
    chunks it would become, and `merge` is what it and the next one would
    join into -- or None with the reason beside it.
    """
    ann = read(video_dir)
    meta = _meta(video_dir)
    L = video_language(video_dir, meta, ann)
    segs = ann["segments"]
    sg = segs[_index(seg, len(segs), "segment")]
    if isinstance(sg, dict) and sg.get("plain"):
        raise ValueError("segment %d is a plain caption: it is shown as it "
                         "stands and holds no chunks to divide" % seg)
    chunks = sg.get("chunks") if isinstance(sg, dict) else None
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("segment %d carries no chunks" % seg)
    i = _index(chunk, len(chunks), "chunk", " in segment %d" % seg)
    _typed(chunks, seg)
    ch = chunks[i]
    out = {"segment": seg, "index": i, "chunk": ch, "cuts": [], "next": None,
           "merge": None, "merge_error": None,
           "voc_sep": chunkdiv.VOC_SEP[chunkdiv.style_of(ch.get("voc"))],
           "pieces": chunkdiv.pieces(ch.get("fa") or "", L)}
    for c in chunkdiv.cuts(ch.get("fa") or "", L):
        a, b, notes = _split(ch, c["at"], L, seg, i)
        out["cuts"].append({"at": c["at"], "end": c["end"],
                            "a": c["a"], "b": c["b"],
                            "first": _order(a), "second": _order(b),
                            "notes": notes,
                            "entries": chunkdiv.entries_for(ch, c["at"],
                                                            L, chunkdiv.AUTO)})
    if i + 1 < len(chunks):
        nxt = chunks[i + 1]
        out["next"] = nxt if isinstance(nxt, dict) else None
        if out["next"] is None:
            out["merge_error"] = "the chunk after this one is not an object"
        else:
            try:
                one, notes = _join(ch, nxt, L)
                out["merge"] = {"fields": _order(one), "notes": notes,
                                "words": len(L.split_words(one.get("fa") or ""))}
            except ValueError as e:
                out["merge_error"] = str(e)
    else:
        out["merge_error"] = ("chunk %d is the last of segment %d: there is "
                              "nothing after it to join it to" % (i, seg))
    return out
