# SPDX-License-Identifier: GPL-3.0-or-later
"""Moving text from one caption of a video that is already on the shelf to the
caption before it or after it -- where a line ENDS.

WHY THIS DOOR EXISTS.  A caption is cut where YouTube, or Whisper, chose to cut
it, and that is often in the middle of a sentence: a line ends on "…وقتی" and the
next one begins "برمی‌گردم…".  A person who reads the transcript to learn from it
wants the lines to end where the sentences do.  captimes.py moves where a caption
STARTS and refuses to touch what it says; subedit.js, on the add page, can move
text between captions but only before the video exists.  This is the one that
does it afterwards.

WHY IT IS ALLOWED, when "a door that could rewrite the transcript would quietly
unmake the check" (subedit.js).  What check_annotations holds the two files to is
the same number of captions as segments, each start within half a second, and
the same text, the same `plain` mark and the same chapter for every caption.
Take the last words of caption 4 and put them in front of caption 5, in BOTH
files, and the count is the count it was, no word was written or lost -- the two
files still hold each other to the same words -- and the one thing that moved is
a boundary.  So this door moves a boundary, in every file that carries it, all
together or not at all, and runs the checker before and after (captimes._brought_in)
and refuses whatever its own move would break.

WHAT MOVES.  The phrases (chunks) with their glosses go across as they are: a
caption is a list of phrases, and a boundary between two captions sits between
two of them.  A boundary that falls INSIDE a phrase cuts it first, at a space, the
way the ✂ sheet does and with what that sheet proposes for the two halves
(chunkdiv): the second half is left with its meaning to write, which the checker
lists and the ✎ form fills.  A language that writes no spaces moves whole phrases
only.

THE TIME.  The caption that gains or loses its first words starts somewhere else.
Where the video was transcribed here, the speech to text kept the time each word
was HEARD (wordtimes.json, wordtimes.py; docs/word-times.md): the line now begins
with a word, so it begins when that word was heard -- or where a person set that
word's start by ear (a pin).  That is the rule the add page's ✂ split keeps
("a new caption starts at its first moved atom, never halfway to the next one").
Where there are no word times, or they do not cover that word (it was typed in
afterwards, or its time falls outside the two lines), the new start is worked out
from the TEXT instead, as much of the line's time as the moved words are of its
characters, rounded to a tenth.  That is an estimate, and the answer says which
of the two it used and why; the timings sheet is where either is put right by
ear.

THE WORD TIMES ARE A FILE THAT CARRIES THE BOUNDARY TOO.  wordtimes.json is a tape
of timed words cut into the captions; a move cuts the same tape elsewhere
(wordtimes.repartition), so it is written with the rest, and Undo cuts it back.
No word is said anew, so no word's time changes.

SENTENCE ENDS WITHOUT FULL STOPS.  The page marks a line that stops in the middle
of a sentence by its punctuation; auto-captions often have none.  `marks` reads
the word times for what stands in for it: a pause in the speech of at least
tidy.AUDIO_PAUSE_LEAST between two heard words (the cue the add page's "tidy by
the recording" uses), and which words have a heard time at all, so that the
card can say before a move which of the two ways the new start will be found.

EVERYTHING THAT NAMES A CAPTION BY ITS START follows the start that moved, as in
captimes: transcript.txt, the batches a legacy video still carries under parts/
(their starts only: they are the record of what an LLM answered, and nothing
rebuilds a video from them any more) and the notes anchored to the caption.

AND IT CAN BE TAKEN BACK, exactly: `move` answers the two captions as they were,
and `restore` puts them back -- but only while they are still as `move` left them,
because putting back an older state over newer work would lose it.

Standard library only: this is imported by the server.
"""
import copy
import json
import os
import re
import statistics

import annwrite
import captimes
import chunkdiv
import wordtimes
from check_annotations import (departs, parse_transcript_text, stamp_of,
                               transcript_text, video_language)


class Stale(ValueError):
    """The page is showing something the file no longer holds (the route says
    409, as the divide sheet does, and the page says to reload)."""


def _t(sg):
    return float(sg.get("start") or 0)


def _name(sg):
    """The caption as a person names it: by the time its line begins with."""
    return "the line at %s" % stamp_of(_t(sg))


def _units(text, L):
    """How many pieces a text counts in: words, or -- for a language that
    writes no spaces -- characters other than whitespace.  A caption and its
    phrases are counted the same way, which is what lets the words of the one
    be shared out by the other."""
    text = text or ""
    if L.spaced:
        return len(text.split())
    return len(re.sub(r"\s+", "", text))


def _cut_text(text, front_units, L):
    """(front, back): a text divided after its first `front_units` pieces."""
    if L.spaced:
        words = text.split()
        return (L.word_sep.join(words[:front_units]),
                L.word_sep.join(words[front_units:]))
    seen = 0
    for i, ch in enumerate(text):
        if ch.isspace():
            continue
        if seen == front_units:
            return text[:i].strip(), text[i:].strip()
        seen += 1
    return text.strip(), ""


def _rate(segs):
    """Characters a second over the whole video, the measure of a caption that
    has no next one to say where it ends."""
    rates = []
    for i in range(len(segs) - 1):
        d = _t(segs[i + 1]) - _t(segs[i])
        n = len(segs[i].get("text") or "")
        if 1 <= d <= 40 and n:
            rates.append(n / d)
    return statistics.median(rates) if rates else 14.0


def _ready(sg, idx):
    """A caption that can give or take text: one of the language's own, glossed
    into phrases, still held to the transcript."""
    why = _name(sg) if isinstance(sg, dict) else "caption %d" % idx
    if not isinstance(sg, dict):
        raise ValueError("%s is not a caption" % why)
    if sg.get("plain"):
        raise ValueError("%s is the video's own framing (plain): text does not "
                         "move into or out of a line that is never glossed" % why)
    chunks = sg.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("%s carries no phrases to move" % why)
    if departs(sg):
        raise ValueError(
            "%s has a phrase marked as departing from the transcript, so its "
            "words are no longer the transcript's to share out: put them back "
            "in the phrase's form first" % why)
    for j, ch in enumerate(chunks):
        if not isinstance(ch, dict) or not isinstance(ch.get("fa"), str):
            raise ValueError("%s: phrase %d is not text" % (why, j))
    annwrite._typed(chunks, idx)


def _halves(ch, k, L, seg, j, stamp):
    """The phrase cut before its k-th word, as the ✂ sheet proposes the two."""
    for place in chunkdiv.cuts(ch.get("fa") or "", L):
        if _units(place["a"], L) == k:
            pa, pb, _why = annwrite._split(ch, place["at"], L, seg, j)
            return annwrite._settle(pa, None, ch), annwrite._settle(pb, None, ch)
    raise ValueError("the phrase in %s cannot be cut there: the gap is not an "
                     "ordinary space" % stamp)


def _load(video_dir):
    """(ann, segs, L, caps, errors before) -- all of it in memory."""
    ann = annwrite.read(video_dir)
    segs = ann.get("segments") or []
    if not segs:
        raise ValueError("this video has no captions")
    meta = annwrite._meta(video_dir)
    L = video_language(video_dir, meta, ann)
    caps = None
    tpath = os.path.join(video_dir, "transcript.txt")
    if os.path.exists(tpath):
        with open(tpath, encoding="utf-8") as f:
            caps = parse_transcript_text(f.read(), L)
        if len(caps) != len(segs):
            raise ValueError(
                "transcript.txt carries %d captions and annotations.json %d: "
                "mend that before moving text between them" % (len(caps), len(segs)))
    return ann, segs, L, caps, annwrite._errors(ann, L, caps)


def _words(video_dir):
    """The video's word times, or None: none were kept, or the file is not
    word times (it is then left exactly as it is)."""
    try:
        with open(os.path.join(video_dir, "wordtimes.json"), encoding="utf-8") as f:
            return wordtimes.clean(json.load(f))
    except (OSError, ValueError, TypeError, RecursionError):
        return None


def _panel(segs, caps):
    """The captions as the word times know them: the transcript's, which is
    the panel the tape was adopted for."""
    return [{"text": c.get("text") or "", "chapter": c.get("chapter")}
            for c in (caps if caps is not None else segs)]


def _cut(doc, segs, caps, L):
    """The tape cut into the captions as they now are -> the document, or None
    where the two do not line up caption for caption."""
    if doc is None:
        return None
    try:
        got, _how = wordtimes.repartition(doc, _panel(segs, caps),
                                          doc.get("language") or L.code)
    except ValueError:
        return None
    if len(got.get("captions") or []) != len(segs):
        return None
    return got


def _heard_start(doc, i, lo, hi):
    """(start, how, word) of caption `i` from the word times, or (None, why,
    word) -- `why` the reason, in a sentence, that the text decides instead.
    A start must fall strictly between `lo` and `hi`, the starts around it."""
    if doc is None:
        return None, ("this video has no word times; they are kept only for a "
                      "transcript made here by speech to text"), ""
    row = doc["captions"][i]
    atoms = doc.get("atoms") or []
    first, last = int(row.get("first") or 0), int(row.get("last") or 0)
    if not (0 <= first < last <= len(atoms)):
        return None, "the line has no spoken word to time it by", ""
    atom = atoms[first]
    word = atom.get("surface") or ""
    if row.get("start_pin") is not None:
        t, how = float(row["start_pin"]), "person"
    elif wordtimes.heard(atom):
        t, how = float(atom["start"]), atom.get("time_source") or "whisper"
    else:
        return None, ("“%s” has no time of its own: it was not heard by the "
                      "speech to text but written in afterwards" % word), word
    t = round(t, 2)
    if not (t > lo and (hi is None or t < hi)):
        return None, ("the time “%s” was heard, %s, is not between the lines "
                      "around it; were their starts moved since?"
                      % (word, stamp_of(t))), word
    return t, how, word


def marks(video_dir):
    """What stands in for the full stops of a transcript that has none, read
    from the word times -- for every caption, its phrases' words in the order
    the page draws them (a phrase's words split at the language's separator; a
    language written without spaces: the phrase as one), each a number:
    1 = its time was heard, 2 = a pause of at least AUDIO_PAUSE_LEAST follows
    it.  And `end` for each line: whether a pause (or the end of the video)
    follows its last word.  {words: false} where the video has no word times
    that fit its captions."""
    import tidy
    _ann, segs, L, caps, _before = _load(video_dir)
    doc = _cut(_words(video_dir), segs, caps, L)
    if doc is None:
        return {"words": False, "pause": tidy.AUDIO_PAUSE_LEAST}
    atoms = doc.get("atoms") or []
    lang = doc.get("language") or L.code

    def pause_after(t):
        if t == len(atoms) - 1:
            return True                          # the end of the video
        if not 0 <= t < len(atoms) - 1:
            return False
        a, b = atoms[t], atoms[t + 1]
        end = a.get("end") if a.get("end") is not None else a.get("start")
        return wordtimes.heard(a) and wordtimes.heard(b) and end is not None \
            and b["start"] - end >= tidy.AUDIO_PAUSE_LEAST

    lines, heard = [], 0
    for i, sg in enumerate(segs):
        row = doc["captions"][i]
        first, last = int(row.get("first") or 0), int(row.get("last") or 0)
        at, flags = first, []
        for ch in sg.get("chunks") or []:
            fa = ch.get("fa") if isinstance(ch, dict) else ""
            fa = fa if isinstance(fa, str) else ""
            parts = fa.split(L.word_sep) if L.spaced and L.word_sep else [fa]
            got = []
            for part in parts:
                n = len(wordtimes.pieces(part, lang))
                if not n:
                    got.append(0)
                    continue
                f = 1 if at < len(atoms) and wordtimes.heard(atoms[at]) else 0
                at += n
                if pause_after(at - 1):
                    f |= 2
                got.append(f)
            flags.append(got)
        if at != last:                   # the phrases do not add up to the line
            flags = None
        else:
            heard += sum(1 for t in range(first, last) if wordtimes.heard(atoms[t]))
        lines.append({"w": flags, "end": bool(last > first and pause_after(last - 1))})
    return {"words": heard > 0, "pause": tidy.AUDIO_PAUSE_LEAST, "lines": lines}


def _move_parts(video_dir, caps, starts, changed):
    """The starts of a legacy video's batches follow, as captimes keeps them."""
    parts = captimes._read_parts(video_dir)
    if not parts or caps is None or not changed:
        return 0
    lined = captimes._batches(parts, caps)
    if not lined:
        return 0
    dirty = set()
    for (batch, k), i in lined:
        if i in changed:
            batch[k]["start"] = starts[i]
            dirty.add(id(batch))
    written = 0
    for path, batch in parts:
        if id(batch) not in dirty:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                style = annwrite._style(f.read())
        except OSError:
            style = {}
        captimes._write_json(path, batch, style)
        written += 1
    return written


def _commit(video_dir, ann, segs, L, caps, before, was_starts, words=None):
    """Check what the edit brought in, and only then write -- every file.

    The check is made against the transcript as it will be READ BACK, not as it
    is held here: `plain` is worked out from a caption's text when a transcript
    is read (a line with no letter of the language's script is the video's own
    framing), so a caption left with only English by this move would be one
    thing here and another on the next read."""
    panel = transcript_text(caps) if caps is not None else None
    reread = parse_transcript_text(panel, L) if panel is not None else None
    if reread is not None and len(reread) != len(segs):
        raise ValueError("that would leave a caption with no words")
    after = annwrite._errors(ann, L, reread)
    brought = captimes._brought_in(before, after)
    if brought:
        raise ValueError("that would break the video: " + "; ".join(brought[:3]))
    starts = [_t(sg) for sg in segs]
    changed = {i for i, s in was_starts.items() if abs(starts[i] - s) > 0.0005}
    olds = dict((round(was_starts[i], 3), captimes._num(starts[i])) for i in changed)
    annwrite.write(video_dir, ann)
    if caps is not None:
        tpath = os.path.join(video_dir, "transcript.txt")
        tmp = tpath + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(panel)
        os.replace(tmp, tpath)
    if words is not None:
        wordtimes._write(os.path.join(video_dir, "wordtimes.json"), words)
    written = _move_parts(video_dir, caps, starts, changed)
    return {"parts": written, "notes": captimes._move_notes(video_dir, olds),
            "changed": sorted(changed)}


def move(video_dir, seg, edge, chunk, word=None, expect=None):
    """Move the boundary of the line `seg`.

    `edge` is "end" -- the line is to END after the chosen place, and what
    came after it goes to the front of the next line -- or "start" -- the line
    is to BEGIN at the chosen place, and what came before it goes to the end of
    the previous line.  The place is phrase `chunk`, and word `word` of it
    (None for the phrase as a whole: after it for "end", before it for
    "start").  `expect` is what the page is looking at, {text, chunk}, and a
    page that is out of date is refused by name (Stale).

    Answers {pair, segments, before, moved, start, ...}: the two captions as
    they now are and as they were, so that the page redraws them and the same
    answer is what `restore` takes back.  Raises ValueError, whose message is
    the sentence the person reads, when anything at all is wrong -- and then
    nothing on disk has been touched.
    """
    if edge not in ("end", "start"):
        raise ValueError("edge must be \"end\" or \"start\"")
    ann, segs, L, caps, before = _load(video_dir)
    seg = annwrite._index(seg, len(segs), "caption")
    a = seg if edge == "end" else seg - 1
    b = a + 1
    if edge == "end" and b >= len(segs):
        raise ValueError("this is the last line of the video: there is no line "
                         "after it to take its words")
    if edge == "start" and a < 0:
        raise ValueError("this is the first line of the video: there is no line "
                         "before it to take its words")
    _ready(segs[a], a)
    _ready(segs[b], b)
    if segs[b].get("chapter"):
        raise ValueError(
            "%s opens the chapter “%s”: words do not move across the start of "
            "a chapter" % (_name(segs[b]), segs[b]["chapter"]))
    donor = segs[seg]
    stamp = _name(donor)
    chunks = donor["chunks"]
    j = annwrite._index(chunk, len(chunks), "phrase", " in %s" % stamp)
    if isinstance(expect, dict):
        if isinstance(expect.get("text"), str) and \
                " ".join(expect["text"].split()) != " ".join((donor.get("text") or "").split()):
            raise Stale("the page is showing %s as “%s” and the file has “%s” -- "
                        "reload the player before moving words: somebody has "
                        "changed the video underneath it"
                        % (stamp, expect["text"], donor.get("text")))
        if isinstance(expect.get("chunk"), str) and expect["chunk"] != chunks[j].get("fa"):
            raise Stale("the page is showing phrase %d of %s as “%s” and the "
                        "file has “%s” -- reload the player before moving words"
                        % (j, stamp, expect["chunk"], chunks[j].get("fa")))
    ch = chunks[j]
    n = _units(ch.get("fa"), L)
    if word is not None:
        if not L.spaced:
            raise ValueError("%s is written without spaces: a phrase is the "
                             "smallest piece of it that moves" % L.name)
        word = annwrite._index(word, n, "word", " in that phrase")
    cut = False
    if edge == "end":
        if word is None or word == n - 1:
            keep, take = chunks[:j + 1], chunks[j + 1:]
        else:
            first, second = _halves(ch, word + 1, L, seg, j, stamp)
            keep, take, cut = chunks[:j] + [first], [second] + chunks[j + 1:], True
        if not take:
            raise ValueError("%s already ends there: there is nothing after it "
                             "to move" % stamp)
    else:
        if word is None or word == 0:
            take, keep = chunks[:j], chunks[j:]
        else:
            first, second = _halves(ch, word, L, seg, j, stamp)
            take, keep, cut = chunks[:j] + [first], [second] + chunks[j + 1:], True
        if not take:
            raise ValueError("%s already begins there: there is nothing before "
                             "it to move" % stamp)

    text = donor.get("text") or ""
    moved_units = sum(_units(c.get("fa"), L) for c in take)
    kept_units = sum(_units(c.get("fa"), L) for c in keep)
    if moved_units + kept_units != _units(text, L):
        raise ValueError("the phrases of %s do not add up to its text: mend "
                         "that first (check_annotations says where)" % stamp)
    if edge == "end":
        kept_text, moved_text = _cut_text(text, kept_units, L)
    else:
        moved_text, kept_text = _cut_text(text, moved_units, L)
    sep = L.word_sep
    recv = segs[b] if edge == "end" else segs[a]
    recv_text = recv.get("text") or ""

    was_starts = {a: _t(segs[a]), b: _t(segs[b])}
    old_pair = [copy.deepcopy(segs[a]), copy.deepcopy(segs[b])]

    sa, sb = _t(segs[a]), _t(segs[b])
    nxt = _t(segs[b + 1]) if b + 1 < len(segs) else None
    doc = _words(video_dir)

    if edge == "end":
        segs[a]["chunks"], segs[a]["text"] = keep, kept_text
        segs[b]["chunks"] = take + segs[b]["chunks"]
        segs[b]["text"] = (moved_text + sep + recv_text).strip()
    else:
        segs[a]["chunks"] = segs[a]["chunks"] + take
        segs[a]["text"] = (recv_text + sep + moved_text).strip()
        segs[b]["chunks"], segs[b]["text"] = keep, kept_text
    if caps is not None:
        for k in (a, b):
            caps[k]["text"] = segs[k]["text"]

    # ---- the new start of the second line: when its first word was heard,
    # where the word times say so -- and else the moved words' share of the
    # line they lived in, in characters (an estimate: nothing here hears)
    words = _cut(doc, segs, caps, L)
    if doc is not None and words is None:
        heard_at, how, first_word = None, ("the word times kept with this video "
                                           "do not match its lines"), ""
    else:
        heard_at, how, first_word = _heard_start(words, b, sa, nxt)
    if heard_at is not None:
        new_sb = heard_at
        timed = {"by": "words", "source": how, "word": first_word}
    else:
        timed = {"by": "share", "why": how, "word": first_word}
        share = len(moved_text) / max(1, len(text))
        if edge == "end":
            new_sb = sb - (sb - sa) * share
            high = sb
        else:
            span = (nxt - sb) if nxt is not None else len(text) / _rate(segs)
            new_sb = sb + span * share
            high = nxt if nxt is not None else new_sb
        new_sb = min(max(round(new_sb, 1), sa), max(high, sa))
    segs[b]["start"] = captimes._num(new_sb)
    if caps is not None:
        caps[b]["start"] = segs[b]["start"]

    done = _commit(video_dir, ann, segs, L, caps, before, was_starts, words)
    moved_here = abs(_t(segs[b]) - sb) > 0.0005
    return {"pair": a, "segments": [segs[a], segs[b]], "before": old_pair,
            "moved": {"text": moved_text, "units": moved_units, "cut": cut,
                      "phrases": len(take),
                      "direction": "next" if edge == "end" else "previous",
                      "from": seg, "to": b if edge == "end" else a},
            "start": {"i": b, "was": sb, "now": _t(segs[b])}, "timed": timed,
            "estimated": moved_here and timed["by"] == "share", "parts": done["parts"], "notes": done["notes"]}


def restore(video_dir, pair, expect, to):
    """Put the two captions `pair` and `pair + 1` back as `to` says -- the
    `before` that `move` answered -- if they are still exactly as `expect`
    says: what `move` answered as `segments`.  A pair that has been touched
    since is refused, since an older state over newer work would lose it."""
    ann, segs, L, caps, before = _load(video_dir)
    pair = annwrite._index(pair, len(segs) - 1, "caption pair")
    if not (isinstance(expect, list) and isinstance(to, list)
            and len(expect) == 2 and len(to) == 2):
        raise ValueError("a pair of captions is asked for twice: as they are "
                         "now and as they are to be")
    now = [segs[pair], segs[pair + 1]]
    if now != expect:
        raise Stale("these two lines have been written since that move, so "
                    "undoing it would lose what was done after it")
    for k, new in enumerate(to):
        old = now[k]
        if not isinstance(new, dict) or not isinstance(new.get("text"), str) \
                or not isinstance(new.get("chunks"), list) or not new["chunks"] \
                or not isinstance(new.get("start"), (int, float)) \
                or isinstance(new.get("start"), bool):
            raise ValueError("the caption to put back is not a caption")
        if bool(new.get("plain")) != bool(old.get("plain")) or \
                (new.get("chapter") or None) != (old.get("chapter") or None):
            raise ValueError("a caption's chapter and its plainness are not "
                             "this door's to change")
    was_starts = {pair: _t(segs[pair]), pair + 1: _t(segs[pair + 1])}
    for k, new in enumerate(to):
        segs[pair + k].clear()
        segs[pair + k].update(copy.deepcopy(new))
        if caps is not None:
            caps[pair + k]["text"] = segs[pair + k]["text"]
            caps[pair + k]["start"] = segs[pair + k]["start"]
    words = _cut(_words(video_dir), segs, caps, L)
    done = _commit(video_dir, ann, segs, L, caps, before, was_starts, words)
    return {"pair": pair, "segments": [segs[pair], segs[pair + 1]],
            "start": {"i": pair + 1, "was": was_starts[pair + 1], "now": _t(segs[pair + 1])},
            "parts": done["parts"], "notes": done["notes"]}
