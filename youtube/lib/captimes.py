# SPDX-License-Identifier: GPL-3.0-or-later
"""Moving a caption's start on a video that is already on the shelf.

WHY THERE IS A DOOR HERE AT ALL.  subedit.js says, and says plainly, that
there is no editor for a video already in the player: "its transcript is what
its annotations were checked against, and a door that could rewrite it would
quietly unmake that check."  That is true of an editor that rewrites what a
caption SAYS, or splits one, or joins two, or takes one away -- every one of
those changes what the check compares, and the check would afterwards be
passing over a thing it had never seen.

A START is not one of those.  What check_annotations holds the two files to
is: the same number of captions as segments, each segment's start within half
a second of its caption's, and the text, the `plain` mark and the chapter the
same.  Move a start in BOTH files by the same amount and every one of those
is exactly as true afterwards as before -- the count did not change, the
difference between the two starts is still nothing, and no word was touched.
The check is kept, not unmade, and this file keeps it the way annwrite does:
it runs the checker before and after and refuses any error the edit itself
brought in (`_introduced`).

THE FILES, AND THE NOTES.  A start is written in two files and read from two
more:
  * annotations.json -- what the player draws
  * transcript.txt   -- what the annotations were checked against
  * markdown/        -- the notes written into the seams of this video.  A
                        note anchored `after cap 126` names a caption by its
                        start; left behind, the note comes adrift
  * parts/NN.json    -- the batches, on a video added before parts/ was
                        retired (2026-09-23).  Nothing rebuilds the
                        annotations from them any more, but a tree that
                        still carries them is kept honest rather than left
                        half-moved
Moving one and not the others is the whole of the danger, so they move
together here or not at all.
"""
import json
import os
import re

import annwrite
import pathlock    # lib/, on the path once annwrite is imported (TO-DO §3.10)
from check_annotations import (parse_transcript_text, transcript_text,
                               video_language)

NEAR = 0.051            # the checker's own tolerance between the two files

# Where a note lives: `<the video>/markdown/`, a library root of the studio's
# own.  The studio owns that name -- it is `DIR` in markdown/app/notes.py --
# and it is written out again here instead of imported because importing
# notes.py would pull the whole studio (the store, the parser, the generator)
# into a tool that moves a number; lib/bundle.py keeps the same copy for the
# same reason, under the same name.  It said "notes" here until 2026-09-23,
# which is a folder the studio has never written, so every note stayed behind
# when its caption moved.
NOTES_DIR = "markdown"


def _num(x):
    """A start as the files write it: whole where it is whole.

    The page names a caption in a note's anchor with JavaScript's own
    String(), which prints 22 for 22 and 22.5 for 22.5 and never 22.0, and
    merge_parts matches a part against the transcript by equality; writing
    6.0 where every other hand writes 6 would be a difference that means
    nothing and shows up in every diff.
    """
    f = round(float(x), 3)
    return int(f) if f == int(f) else f


def _notes_dir(video_dir):
    return os.path.join(video_dir, NOTES_DIR)


def _read_parts(video_dir):
    """[(path, [segments])] for every batch, in the order merge_parts reads."""
    d = os.path.join(video_dir, "parts")
    if not os.path.isdir(d):
        return []
    out = []
    for name in sorted(os.listdir(d)):
        if not name.lower().endswith(".json"):
            continue
        p = os.path.join(d, name)
        try:
            with open(p, encoding="utf-8") as f:
                batch = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(batch, list):
            out.append((p, batch))
    return out


def _write_json(path, value, style):
    """As annwrite writes: the file's own shape, and never half a file."""
    text = json.dumps(value, ensure_ascii=False,
                      indent=style.get("indent", 1))
    if style.get("newline") is False:
        text = text.rstrip("\n")
    else:
        text = text.rstrip("\n") + "\n"
    tmp = pathlock.tmp(path)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _plan(segs, moves):
    """What each caption's start is to become, checked before anything moves.

    A move names a caption by its place AND by the start it had, and both
    must agree: the editor was opened on a file, and if that file has since
    been written by another hand, the index alone would move the wrong one.
    """
    if not isinstance(moves, list) or not moves:
        raise ValueError("no caption was asked to move")
    want = {}
    for m in moves:
        if not isinstance(m, dict):
            raise ValueError("a move is an object with i, from and to")
        try:
            i = int(m.get("i"))
            was, to = float(m.get("from")), float(m.get("to"))
        except (TypeError, ValueError):
            raise ValueError("a move names a caption by i and from, and its "
                             "new start by to")
        if not 0 <= i < len(segs):
            raise ValueError("there is no caption %d in this video" % i)
        if to < 0:
            raise ValueError("a caption cannot start before the video does")
        if abs(float(segs[i].get("start", 0)) - was) > 0.0011:
            raise ValueError(
                "caption %d starts at %s, not at %s: the video has been "
                "written by another hand since this was opened -- reload it "
                "and move it again"
                % (i, segs[i].get("start"), _num(was)))
        if i in want:
            raise ValueError("caption %d was asked to move twice" % i)
        want[i] = _num(to)
    starts = [_num(sg.get("start", 0)) for sg in segs]
    for i, to in want.items():
        starts[i] = to
    # the one rule a caption's start has of its own, and the checker's too:
    # it never goes backwards (equal is allowed -- two captions shown in the
    # same second are two captions)
    for i in range(1, len(starts)):
        if starts[i] < starts[i - 1]:
            raise ValueError(
                "that would put caption %d at %s, before caption %d at %s: "
                "a caption cannot start before the one in front of it"
                % (i, starts[i], i - 1, starts[i - 1]))
    return starts, want


def _move_notes(video_dir, olds):
    """Carry every note anchored to a moved caption along with it.

    A note names its caption by that caption's start (`anchor: after cap
    126`).  Left behind it is not lost -- the index reports it adrift and
    the reader shows it at the end -- but it is in the wrong place, and the
    whole reason a start moved is that the wrong place is not wanted.
    `olds` is {the start it had: the start it now has}.
    """
    d = _notes_dir(video_dir)
    if not os.path.isdir(d) or not olds:
        return 0
    line = re.compile(r"^(\s*anchor\s*:\s*[\"\']?\s*(?:before|after)\s+cap\s+)"
                      r"(\S+?)([\"\']?\s*)$", re.I)
    moved = 0
    for base, _dirs, names in os.walk(d):
        for name in names:
            if not name.lower().endswith(".md"):
                continue
            path = os.path.join(base, name)
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except OSError:
                continue
            out, hit = [], False
            for row in text.split("\n"):
                m = line.match(row)
                if m:
                    try:
                        at = round(float(m.group(2)), 3)
                    except ValueError:
                        at = None
                    if at is not None and at in olds:
                        row = "%s%s%s" % (m.group(1), _num(olds[at]), m.group(3))
                        hit = True
                out.append(row)
            if not hit:
                continue
            tmp = pathlock.tmp(path)
            with open(tmp, "w", encoding="utf-8") as f:
                f.write("\n".join(out))
            os.replace(tmp, path)
            moved += 1
    return moved


# The checker names a segment by its place AND by the start it has --
# "segment 1 (start 3): no chunks" -- so a message about a segment this edit
# moved is not the same string before and after even when it is the very same
# complaint.  Comparing blind to that number is what makes "an error this edit
# brought in" mean what it says: a video with any old complaint about a
# caption -- one with no chunks under it, a word line that no longer gives
# its text back, a colour nobody can paint -- could otherwise never have that
# caption moved at all.
_START_IN = re.compile(r"\(start\s+[-\d.]+\)")


def _brought_in(before, after):
    """The errors in `after` that `before` did not already have, counted the
    way annwrite counts them, but blind to a moved start."""
    left = [_START_IN.sub("(start)", m) for m in before]
    out = []
    for raw in after:
        key = _START_IN.sub("(start)", raw)
        if key in left:
            left.remove(key)
        else:
            out.append(raw)
    return out


def _batches(parts, caps):
    """[(batch, k)] lined up with the captions that want glossing, or None.

    merge_parts pairs the batches' segments with the NON-PLAIN captions, in
    order, and matches their starts by equality.  Where the two do not line
    up this answers None and the batches are left exactly as they are:
    merge_parts says what is wrong with them in its own words, and a guess
    here could only bury that.
    """
    glossed = [i for i, c in enumerate(caps) if not c.get("plain")]
    flat = [(batch, k) for _p, batch in parts for k in range(len(batch))]
    return list(zip(flat, glossed)) if len(flat) == len(glossed) else None


def move(video_dir, moves):
    """Move some captions' starts, in every file that carries one.

    `moves` is [{i, from, to}].  Answers what was written; raises
    ValueError, whose message is the sentence the person who pressed the
    button reads, when anything at all is wrong -- and then nothing on disk
    has been touched.
    """
    ann = annwrite.read(video_dir)
    segs = ann.get("segments") or []
    if not segs:
        raise ValueError("this video has no captions to move")
    starts, want = _plan(segs, moves)
    olds = dict((round(float(segs[i].get("start", 0)), 3), to)
                for i, to in want.items())

    meta = annwrite._meta(video_dir)
    L = video_language(video_dir, meta, ann)

    tpath = os.path.join(video_dir, "transcript.txt")
    caps = None
    if os.path.exists(tpath):
        with open(tpath, encoding="utf-8") as f:
            caps = parse_transcript_text(f.read(), L)
        if len(caps) != len(segs):
            raise ValueError(
                "transcript.txt carries %d captions and annotations.json %d: "
                "mend that before moving any of them"
                % (len(caps), len(segs)))

    before = annwrite._errors(ann, L, caps)

    # ---- all of it in memory, before a byte is written ----
    for i, to in want.items():
        segs[i]["start"] = to
        if caps is not None:
            caps[i]["start"] = to

    after = annwrite._errors(ann, L, caps)
    brought = _brought_in(before, after)
    if brought:
        raise ValueError("that would break the video: " + "; ".join(brought[:3]))

    parts = _read_parts(video_dir)
    lined = _batches(parts, caps) if (parts and caps is not None) else None
    if lined:
        for (batch, k), i in lined:
            batch[k]["start"] = starts[i]

    # ---- and only now, the files ----
    annwrite.write(video_dir, ann)
    if caps is not None:
        tmp = pathlock.tmp(tpath)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(transcript_text(caps))
        os.replace(tmp, tpath)
    written = 0
    if lined:
        for path, batch in parts:
            try:
                with open(path, encoding="utf-8") as f:
                    style = annwrite._style(f.read())
            except OSError:
                style = {}
            _write_json(path, batch, style)
            written += 1
    return {"moved": len(want), "captions": len(segs), "parts": written,
            "notes": _move_notes(video_dir, olds),
            "starts": [starts[i] for i in sorted(want)]}
