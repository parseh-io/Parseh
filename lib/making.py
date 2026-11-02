#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""A book made by an agent, in place: its folder, its record, its asks, its end.

    making.make(fields, original, options=None, into=None)
                                    the book's folder, written into books/ -> {"dir", "path", ...}
    making.instructions_text(fields, options=None)
                                    what AGENTS.md would say, before any folder is made
    making.write_instructions(book_dir, facts, options)
                                    THE SEAM: AGENTS.md, CLAUDE.md and the project skill into the folder
    making.rewrite_instructions(book_dir)
                                    "write the instructions again": the same, for a folder already made
    making.method_template()        what docs/new-book-prompt.md says, made from docs/book-method/
    making.is_making(book_dir)      True while an agent may still be writing the .tex
    making.describe(book_dir)       everything the making panel shows
    making.ask(book_dir, line, chunk=None)
                                    one dated entry more in ASKS.md
    making.finish_start(book_dir)   verify_book and the full build, as a job the page polls
    making.finish_blockers(book_dir)
                                    what stands between the person and a Finish, in sentences
    making.add_part(book_dir, source, options)
                                    more text for the agent, a part at a time: a file or a pasted text
    making.set_more_coming(book_dir, flag)
                                    "this is all the text" (False), or that more is coming (True)
    making.reopen(book_dir)         a finished book's making taken up again
    making.open_folder(path)        the system's file manager, on the folder

PARSEH NEVER STARTS AN AGENT (TO-DO §18, the owner, 2026-09-28).  It prepares a
folder under books/, shows where it is, and the person opens whatever agent they
use on it.  The agent works on the REAL tree -- Parseh's own lib/*.py, run with
Parseh's own Python -- and writes only inside the book's folder, so the book is
in the library from the first minute and can be looked at while it grows.

WHAT THE FOLDER HOLDS beside the book's own files (book.json, main.tex, source/,
annot/, the chapters):

    original/<file>   the source text the book is made from -- in the book's own
                      folder and not in others/, which a release neither ships
                      nor keeps (lib/release.py CONTENT), so it travels with the
                      book (lib/bundle.py)
    NOTES.md          the book's journal: the source's oddities, the decisions
                      taken, what is open.  Kept by whoever makes the book
    ASKS.md           what the person asks of the agent, dated entries, written
                      from the making panel and from the reader's chunk sheet.
                      The agent reads it again before every batch
    making.json       the record of the making, below
    AGENTS.md         the instructions, in words any agent can be told to read
    CLAUDE.md         one line pointing at AGENTS.md, which Claude Code reads
                      by itself
    .claude/skills/parseh-book/, .agents/skills/parseh-book/
                      the same method as a project skill, for the agents that look for one
                      (Claude Code reads the first and not the second; Codex, Gemini CLI,
                      Cursor, GitHub Copilot and VS Code read the second).  Copies and not
                      links, for Windows.  Written by lib/skills.py where it is there

making.json is ONE small object that Parseh and the agent keep between them.
Every field is optional to read -- an agent's file may be half written, and the
panel says so instead of stopping:

    state     "making", or "finished".  PARSEH'S ALONE: written when the folder is
              made and by Finish (finish_start), never by the agent.  Anything but
              "finished" means the book is still being made
    parseh    the version of Parseh the folder was made under; the panel says
              "Parseh was updated during the making" when this Parseh differs
    started   when the folder was made (UTC, 2026-09-29T14:00:12Z)
    finished  when Finish ended the making
    updated   when the AGENT last wrote the file: it writes it every time it
              finishes something
    stage     the agent's: "source" (the original recovered), "chapters" (the
              chapter table written), "batch", "done" (every batch is in),
              "waiting" (every part is in and more is coming: it waits for the next)
    on        the agent's: one line, what it is on now
    chapters  the agent's chapter table: [{"chapter": 1, "paragraphs": 24, "part": 1}, ...]
              ("part", the part its first paragraphs came from, is optional)
    batches   the agent's: {"done": 3, "of": 12}
    checks    the agent's: what the tools last said, {"check_batch": "0 errors",
              "assemble": "ALL PARAGRAPHS CLEAN", "verify_book": "clean"}
    sources   the agent's alone: which parts of the text it has recovered,
              {"done": [1, 2], "of": 3, "decided": {"3": "a new chapter: it opens with a heading"}}
    asks_read the agent's: how many entries of ASKS.md it has read, so that the agent that takes
              over (or the same one, after a pause) starts at the next

THE TEXT COMES IN PARTS (brief 5.10): the person gives it a bit at a time, from any
device, as a file or pasted, and the agent takes each part before its next batch.
These two are PARSEH'S ALONE to write, never the agent's:

    parts       [{"n": 1, "file": "original/part-001-x.pdf", "pages": [0, 9], "chapter":
                "new", "join": "", "label": "", "added": "2026-10-05T10:00:00Z", "bytes":
                1234}, ...] -- the first original is part 1.  `chapter` says where the part
                goes: "auto" (the agent decides from the text and says what it decided in
                `sources.decided`), "new" (a chapter of its own) or "last" (more of the last
                chapter); `join` is "paragraph" when the part was cut in the middle of a
                paragraph and its first paragraph goes on the last one of the part before
    more_coming true while the person may still add text: they say "this is all the text"
                to set it false, and may set it true again

AND THIS ONE, written once when the folder is made, so that "write the instructions again" can
write them the same way (writing them again never touches making.json):

    instructions {"reference": "persian/farsi" or "", "examples": false, "marks": "marks" or
                "nomarks" where the language has them, "prompt": the id of the person's own
                prompt or ""}

WHAT FINISH WAITS FOR is not decided (the owner, 2026-09-29: more detail, next week): it is
ONE function, finish_blockers, and two settings beside it (FINISH_WAITS_FOR,
FINISH_CONFIRMABLE), so that every option the owner is offered is a small change here.

WHILE A BOOK IS BEING MADE its reader does not edit (serve.py refuses LOCKED
doors, lib/making.js says why): the pipeline's truth is annot/*.json and the
.tex is assembled from it, so a hand edit would be erased by the agent's next
assembly.  Finish ends that: the .tex is the truth from then on, and annot/
stays as the record of how it was made.

Standard library only: the server imports this.
"""
import calendar
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

LIB = os.path.dirname(os.path.realpath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import books as booklib                                        # noqa: E402
import languages                                               # noqa: E402
import promptkit                                               # noqa: E402  the meaning rule the gloss prompts carry
import version                                                 # noqa: E402

MAKING = "making.json"
ASKS = "ASKS.md"
NOTES = "NOTES.md"
AGENTS = "AGENTS.md"
CLAUDE = "CLAUDE.md"
ORIGINAL = "original"
# what the tools can recover the text of a book from: a PDF with a text layer,
# an epub, a plain text file.  It is also the allowlist of what the folder's
# original/ may hold when a bundle carries it (lib/bundle.py)
ORIGINAL_EXTS = (".pdf", ".epub", ".txt")
BATCH = 10                                  # paragraphs to a batch (docs/new-book-prompt.md)

# THE SHAPE OF annot/*.json, as a number (lib/version.py FORMATS): the annotation
# JSON the agent writes a paragraph and a batch at a time and lib/assemble.py
# builds the chapters from -- {"idx", "ch", "ann": {"sentences": [{"chunks": [...]}]}},
# a chunk holding fa, tr, voc, en and, for a language with a reading or words,
# kana and words (lib/check_batch.py's docstring).  It rides in a book's bundle
# from a0.4.2 (lib/bundle.py), so an older Parseh must be told it may not read it.
# RAISE IT when the shape changes so that the Parseh before this one would read
# what is written now wrong.
ANNOT_FORMAT = 1

# THE DOORS OF A BOOK'S READER THAT WRITE ITS .tex OR ITS TITLE PAGE, shut while
# the agent makes it (serve.py's _books_post asks is_making before any of them).
# A hand edit would be erased by the next assembly, and one that lands while the
# agent is appending a batch to main.tex could lose that line.  The passes, the
# clouds, the dictionary, the narration and the builds are not here: none of them
# writes what the agent writes.
LOCKED = ("__edit/chunk", "__edit/meta", "__divide/chunk", "__struct/section",
          "__struct/chapter", "__region/apply", "__reading/free")
LOCK_SAID = ("This book is being made by an agent. It writes the book's .tex from its own "
             "files (annot/), so whatever is changed here would be erased by its next batch: "
             "editing is off until the making is finished. To change something, ask -- the "
             "making panel has a box for it, and the chunk sheet has \u201cask about this "
             "chunk\u201d.")

# one writer at a time to ASKS.md: two devices asking together must not
# interleave their entries
_ASKS_LOCK = threading.Lock()

FIELD_MAX = 300                             # what the panel keeps of an agent's one-line fields
ASK_MAX = 4000
NOTES_TAIL = 2500                           # characters of NOTES.md the panel shows
TEX_SPECIAL = re.compile(r"[\\{}$%&#_^~]")

# THE TEXT IN PARTS (brief 5.10).  Where a part goes: the agent's call from the text ("auto", the
# recommended default), or the person's ("new", "last").  `join` is "paragraph" for a part cut in the
# middle of a paragraph, whose first paragraph goes on the last one of the part before.  Both are
# fields of the list already, so that whatever the owner decides about "auto" and about a cut
# paragraph is a change of the words the agent reads, not of this module.
PARTS_COPY = "parts.json"                   # original/parts.json, see _store
CHAPTER_WAYS = ("auto", "new", "last")
JOINS = ("", "paragraph")
LABEL_MAX = 120
TEXT_MAX = 32 * 1024 * 1024                 # a pasted part: the ceiling of any JSON body

# WHAT FINISH WAITS FOR is the owner's to decide (brief 5.10; the options are in the report of lane C2):
#   A  nothing: "agent" and "parts" left out of the tuple; the person's second press is all there is
#   B  the person's "this is all the text" and every part taken: add "text", and FINISH_CONFIRMABLE False
#   C  the agent's word that everything given so far is in (RECOMMENDED, and what is on): "agent",
#      "parts"; and a second press goes through where the agent has not said it is idle
FINISH_WAITS_FOR = ("parts", "agent")
FINISH_CONFIRMABLE = True


# ------------------------------------------------------------------ time
def _iso(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if t is None else t))


def _epoch(v):
    """A moment as making.json spells it -> seconds since 1970, or None.  The
    agent writes ISO 8601, in UTC unless it says another zone; a number is taken
    as seconds, so an agent that writes `time.time()` is read too."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, str):
        return None
    m = re.fullmatch(r"(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d)(?::(\d\d))?(?:\.\d+)?(Z|[+-]\d\d:?\d\d)?",
                     v.strip())
    if not m:
        return None
    y, mo, d, h, mi, s = (int(g or 0) for g in m.groups()[:6])
    zone = m.group(7)
    try:
        t = calendar.timegm((y, mo, d, h, mi, s, 0, 0, 0))
    except (ValueError, OverflowError):
        return None
    if zone and zone != "Z":
        digits = zone[1:].replace(":", "")
        t -= (1 if zone[0] == "+" else -1) * (int(digits[:2]) * 3600 + int(digits[2:]) * 60)
    return float(t)


# ------------------------------------------------------------------ the record
def path_of(book_dir, name):
    return os.path.join(book_dir, name)


def _write_json(path, doc):
    """A file replaced whole or not at all: the panel reads making.json while
    the agent may be writing it, and half a file is not what it should see."""
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def read(book_dir):
    """making.json as a dict -> (the dict, or None when the book has none; a
    sentence when the file is there and cannot be read).  A file that will not
    parse is still a book being made: an agent's write may be half done, and the
    lock on editing must not lift for it."""
    path = path_of(book_dir, MAKING)
    if not os.path.isfile(path):
        return None, ""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        return {}, "making.json cannot be read just now (%s): the agent may be writing it" % e
    if not isinstance(doc, dict):
        return {}, "making.json is not a JSON object: the agent has to write it again"
    return doc, ""


def state(book_dir):
    """"none" (an ordinary book), "making" or "finished"."""
    doc, _bad = read(book_dir)
    if doc is None:
        return "none"
    return "finished" if doc.get("state") == "finished" else "making"


def is_making(book_dir):
    return state(book_dir) == "making"


def _int(v, default=0):
    try:
        return max(0, int(v))
    except (TypeError, ValueError, OverflowError):
        return default


def _line(v, cap=FIELD_MAX):
    return " ".join(str(v if v is not None else "").split())[:cap]


def stage_words(doc):
    """Where the making stands, in the words the panel and the card say."""
    if doc.get("state") == "finished":
        return "finished"
    stage = _line(doc.get("stage")).lower() or "folder"
    b = doc.get("batches") if isinstance(doc.get("batches"), dict) else {}
    done, of = _int(b.get("done")), _int(b.get("of"))
    if stage == "batch":
        if of and done >= of:
            return "all batches in"
        return "batch %d of %d" % (done + 1, of) if of else "batch %d" % (done + 1)
    return {"folder": "not started yet", "source": "source recovered",
            "chapters": "chapter table", "done": "all batches in",
            "waiting": "waiting for the next part"}.get(stage, stage)


def _chapter_table(doc):
    out = []
    rows = doc.get("chapters")
    for row in rows[:500] if isinstance(rows, list) else ():
        if isinstance(row, dict) and not isinstance(row.get("chapter"), bool):
            n = _int(row.get("chapter"), -1)
            if n >= 0:
                out.append({"chapter": n, "paragraphs": _int(row.get("paragraphs"))})
                if _int(row.get("part")) > 0:
                    out[-1]["part"] = _int(row.get("part"))
        elif isinstance(row, int) and not isinstance(row, bool) and row >= 0:
            out.append({"chapter": row, "paragraphs": 0})
    return out


# ------------------------------------------------------------------ chapters and drafts
def chapter_inputs(book_dir):
    """The chapter files main.tex inputs, in the order it inputs them -- the one
    place chapter order is written down (lib/texparse.py reads it the same way)
    -- and that are on the disk.  A commented-out \\input is not one."""
    try:
        with open(path_of(book_dir, "main.tex"), encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return []
    out = []
    for line in text.split("\n"):
        # THE READER'S OWN RULE (lib/texparse.py parse_book), so that what this says is written is
        # what the reader shows: a line that starts with % is a comment, and the first \input on
        # a line is the one that counts
        if line.lstrip().startswith("%"):
            continue
        m = re.search(r"\\input\{([^}]+)\}", line)
        if not m or not re.match(r"ch[^\\]*$", m.group(1)):
            continue
        name = m.group(1)[:-4] if m.group(1).endswith(".tex") else m.group(1)
        if os.path.isfile(path_of(book_dir, name + ".tex")) and name not in out:
            out.append(name)
    return out


def _chapter_number(name):
    m = re.match(r"ch(\d+)", name)
    return int(m.group(1)) if m else None


def draft_state(book_dir):
    """Whether the PDF of the chapters so far can be made here, and the last
    one made.  build.sh's --draft is a shell script that typesets just the
    chapters named under a jobname of its own (frankdraft), so it can never
    touch main.pdf: where there is no sh -- Windows -- there is no draft, and
    the panel says so and offers the reader instead."""
    import bookbuild
    can, why = bookbuild.available("draft")
    names = chapter_inputs(book_dir)
    if can and not names:
        can, why = False, "there is no chapter in the book yet: nothing to typeset"
    pdf = path_of(book_dir, "frankdraft.pdf")
    made = os.path.getmtime(pdf) if os.path.isfile(pdf) else None
    newest = max((os.path.getmtime(path_of(book_dir, n + ".tex")) for n in names), default=0)
    return {"can": can, "why": why, "chapters": names,
            "pdf": "frankdraft.pdf" if made else "", "pdf_at": made,
            "pdf_old": bool(made and newest > made)}


# ------------------------------------------------------------------ what the panel shows
def _tail(path, chars):
    """The last `chars` characters of a text file, from the start of a line."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - chars * 4))
            text = f.read().decode("utf-8", "replace")
    except OSError:
        return ""
    cut = size > chars * 4 or len(text) > chars
    text = text[-chars:]
    if cut and "\n" in text:
        text = text.split("\n", 1)[1]           # what is left of the line the cut went through
    return text.strip("\n")


# what Parseh itself writes into ASKS.md, because the agent reads that file before every batch: not the
# person's asks, and not counted as such
NOT_ASKS = ("finished", "reopened", "a part was added", "this is all the text", "more text is coming")


def _asks(book_dir):
    """How many asks ASKS.md holds, and the last of them."""
    try:
        with open(path_of(book_dir, ASKS), encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return {"count": 0, "last": ""}
    parts = re.split(r"(?m)^(?=## )", text)
    entries = [p.strip() for p in parts if p.startswith("## ")
               and not p.split("\n", 1)[0].strip().endswith(NOT_ASKS)]
    return {"count": len(entries), "last": entries[-1][:ASK_MAX] if entries else ""}


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _instructions_view(book_dir, doc):
    """What the panel says of the instructions in the folder: when they were written, and the two choices
    that are the book's own facts (the short vowels, the scheme of the transliteration)."""
    kept = doc.get("instructions") if isinstance(doc.get("instructions"), dict) else {}
    try:
        with open(path_of(book_dir, "book.json"), encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        meta = {}
    return {"written": _mtime(path_of(book_dir, AGENTS)), "marks": kept.get("marks") or "",
            "translit": "ipa" if isinstance(meta, dict) and meta.get("translit") == "ipa" else ""}


def describe(book_dir):
    """What the making panel shows of a book -> a plain dict.  For a book that
    was never made this way it says so and nothing else."""
    doc, bad = read(book_dir)
    now = time.time()
    if doc is None:
        return {"ok": True, "making": False, "state": "none", "now": now}
    finished = doc.get("state") == "finished"
    store = _heal(book_dir)
    inputs = chapter_inputs(book_dir)
    present = sorted({n for n in map(_chapter_number, inputs) if n is not None})
    table = _chapter_table(doc)
    wanted = sorted({row["chapter"] for row in table})
    b = doc.get("batches") if isinstance(doc.get("batches"), dict) else {}
    checks = doc.get("checks") if isinstance(doc.get("checks"), dict) else {}
    try:
        stamp = os.path.getmtime(path_of(book_dir, MAKING))
    except OSError:
        stamp = None
    # WHETHER THE READER IS OLDER THAN WHAT THE AGENT HAS WRITTEN, said by the files' own
    # times: a page built before the last batch lands is the page the person is looking at
    written = [path_of(book_dir, n) for n in [name + ".tex" for name in inputs] + ["main.tex"]]
    newest = max((os.path.getmtime(p) for p in written if os.path.isfile(p)), default=0)
    reader = os.path.join(book_dir, "reader", "index.html")
    built = os.path.getmtime(reader) if os.path.isfile(reader) else None
    ran_under = _line(doc.get("parseh"), 40)
    return {
        "ok": True, "making": not finished, "state": "finished" if finished else "making",
        "stage": _line(doc.get("stage")).lower() or "folder", "words": stage_words(doc),
        "on": _line(doc.get("on")), "batches": {"done": _int(b.get("done")), "of": _int(b.get("of"))},
        "chapters": table, "present": present,
        "to_come": [n for n in wanted if n not in present],
        "parts": _parts_view(store, doc, present, table),
        "more_coming": bool(store and store["more_coming"]),
        "blockers": [] if finished else finish_blockers(book_dir), "confirmable": FINISH_CONFIRMABLE,
        "stale": bool(newest and (built is None or newest > built)),
        "checks": {_line(k, 40): _line(v) for k, v in list(checks.items())[:12]},
        "started": _epoch(doc.get("started")),
        "updated": _epoch(doc.get("updated")) or stamp,
        "finished_at": _epoch(doc.get("finished")),
        "parseh": ran_under, "parseh_now": version.VERSION,
        "updated_by_parseh": bool(ran_under and ran_under != version.VERSION),
        "notes": _tail(path_of(book_dir, NOTES), NOTES_TAIL), "asks": _asks(book_dir),
        "instructions": _instructions_view(book_dir, doc),
        "draft": draft_state(book_dir), "broken": bad, "now": now}


# ------------------------------------------------------------------ steering
def _clean_text(text, cap):
    text = str(text if text is not None else "").replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(c for c in text if c == "\n" or c == "\t" or ord(c) >= 32)
    return text.strip()[:cap]


def ask(book_dir, line, chunk=None, when=None):
    """One dated entry more in ASKS.md -> {"ok", "at", "count"}.  `chunk`, from
    the reader's chunk sheet, is {"address": "chapter 1, paragraph 2, ...",
    "text": "the chunk as it stands"}: the remark is anchored where it was seen.

    A finished book is refused: nothing reads ASKS.md any more, and an ask that
    goes nowhere is worse than being told so.  Every entry is one write, opened
    for appending, so an agent reading the file between two of them never finds
    half of one."""
    line = _clean_text(line, ASK_MAX)
    if not line:
        raise ValueError("write what to change first: there is nothing in the box")
    if state(book_dir) == "finished":
        raise ValueError("this book is finished: the agent is not reading its asks any more")
    if state(book_dir) == "none":
        raise ValueError("this book was not made by an agent, so there is nobody to ask")
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(when))
    if isinstance(chunk, dict) and (chunk.get("address") or chunk.get("text")):
        where = _line(chunk.get("address"), 200)
        text = " ".join(_clean_text(chunk.get("text"), 600).split())
        entry = "## %s \u2014 about a chunk\n\n%s%s\n%s\n" % (
            stamp, where + ":\n" if where else "", "> " + text + "\n" if text else "", line)
    else:
        entry = "## %s \u2014 what to change from now on\n\n%s\n" % (stamp, line)
    with _ASKS_LOCK:
        path = path_of(book_dir, ASKS)
        need_gap = os.path.isfile(path) and os.path.getsize(path) > 0
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(("\n" if need_gap else "") + entry)
    return {"ok": True, "at": stamp, "count": _asks(book_dir)["count"]}


# ------------------------------------------------------------------ the text, in parts
_PARTS_LOCK = threading.Lock()              # one writer of the list at a time: two devices adding together


def _store(book_dir):
    """Parseh's own copy of the list of parts, and the flag -> {"parts": [...], "more_coming": bool}, or
    None for a book made before the text could come in parts.

    WHY A COPY: making.json is the agent's file too, and an agent that writes it whole from what it
    read minutes ago erases a part that arrived meanwhile -- silently, for that part is then never
    taken.  The copy lies in original/, where the agent is not told to write, and whenever the two
    differ what Parseh keeps is put back into making.json (_publish)."""
    doc = None
    try:
        with open(os.path.join(book_dir, ORIGINAL, PARTS_COPY), encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        pass
    if not (isinstance(doc, dict) and isinstance(doc.get("parts"), list)):
        doc, _bad = read(book_dir)
    if isinstance(doc, dict) and isinstance(doc.get("parts"), list):
        return {"parts": [p for p in doc["parts"] if isinstance(p, dict)], "more_coming": bool(doc.get("more_coming"))}
    return None


def _publish(book_dir, store):
    """Parseh's list into making.json, where the agent reads it -> whether it had to be written.  A
    file the agent is half way through writing is left alone: the next call puts it right."""
    doc, bad = read(book_dir)
    if doc is None or bad or (doc.get("parts") == store["parts"] and doc.get("more_coming") == store["more_coming"]):
        return False
    _write_json(path_of(book_dir, MAKING), dict(doc, parts=store["parts"], more_coming=store["more_coming"]))
    return True


def _heal(book_dir):
    """The list as Parseh keeps it, made true in making.json as well -> the list (None: this book has none).
    Under the lock the writers take, so that a look that read the list just before a part was added cannot
    put the old one back over it."""
    with _PARTS_LOCK:
        store = _store(book_dir)
        if store is not None:
            _publish(book_dir, store)
        return store


def _save(book_dir, store):
    os.makedirs(os.path.join(book_dir, ORIGINAL), exist_ok=True)
    _write_json(os.path.join(book_dir, ORIGINAL, PARTS_COPY), store)
    _publish(book_dir, store)


def _entry(n, file, pages, chapter, join, label, added, size):
    return {"n": n, "file": file, "pages": pages, "chapter": chapter, "join": join, "label": label,
            "added": added, "bytes": size}


def _first_part(book_dir):
    """The list of a book made before parts: the original it was made from is part 1."""
    meta = {}
    try:
        with open(path_of(book_dir, "book.json"), encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        pass
    meta = meta if isinstance(meta, dict) else {}
    rel = meta.get("source_pdf")
    full = os.path.join(book_dir, *str(rel).split("/")) if rel else ""
    if not (rel and os.path.isfile(full)):
        return {"parts": [], "more_coming": True}
    pages = meta.get("source_pages") if isinstance(meta.get("source_pages"), list) else None
    return {"parts": [_entry(1, str(rel), pages, "new", "", "", _iso(os.path.getmtime(full)), os.path.getsize(full))],
            "more_coming": True}


def _taken(doc):
    """The part numbers the agent says it has recovered, and what it said it decided for each."""
    src = doc.get("sources") if isinstance(doc.get("sources"), dict) else {}
    done = src.get("done") if isinstance(src.get("done"), list) else []
    said = src.get("decided") if isinstance(src.get("decided"), dict) else {}
    return ({_int(n, -1) for n in done if not isinstance(n, bool)} - {-1},
            {_int(k, -1): _line(v, 200) for k, v in said.items()}, _int(src.get("of")))


def _parts_view(store, doc, present, table):
    """The list, for the panel: each part with where it stands.  `added` (waiting for the agent),
    `recovered` (the agent has taken it: its numbered paragraphs are in source/), `worked` (and a
    chapter its table says came from the part is in the reader)."""
    if store is None:
        return []
    done, said, _of = _taken(doc)
    in_book = {row["part"] for row in table if row.get("part") and row["chapter"] in present}
    out = []
    for p in store["parts"]:
        n = _int(p.get("n"))
        if n < 1:
            continue
        pages = p.get("pages")
        out.append({"n": n, "file": _line(p.get("file"), 200), "label": _line(p.get("label"), LABEL_MAX),
                    "name": _line(os.path.basename(str(p.get("file") or "")), 120),
                    "chapter": p.get("chapter") if p.get("chapter") in CHAPTER_WAYS else "auto",
                    "join": p.get("join") if p.get("join") in JOINS else "",
                    "pages": [_int(pages[0]), _int(pages[1])] if isinstance(pages, list) and len(pages) == 2 else None,
                    "added": _epoch(p.get("added")), "bytes": _int(p.get("bytes")),
                    "state": ("worked" if n in in_book else "recovered") if n in done else "added",
                    "decided": said.get(n, "")})
    return out


def _on_disk(book_dir):
    out = set()
    for name in os.listdir(os.path.join(book_dir, ORIGINAL)) if os.path.isdir(os.path.join(book_dir, ORIGINAL)) else ():
        m = re.match(r"part-(\d+)-", name)
        if m:
            out.add(int(m.group(1)))
    return out


def _note_asks(book_dir, title, body):
    """One dated entry in ASKS.md that is not an ask: the file an agent reads again before every
    batch, so that a part, or a word that no more text is coming, reaches an agent that does not
    parse making.json too."""
    with _ASKS_LOCK:
        path = path_of(book_dir, ASKS)
        gap = "\n" if os.path.isfile(path) and os.path.getsize(path) else ""
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write("%s## %s — %s\n\n%s\n" % (gap, time.strftime("%Y-%m-%d %H:%M"), title, body))


def add_part(book_dir, source, options=None):
    """More text for the agent, a part at a time -> the part's entry (see `parts` in the docstring).

    `source` is {"name", "data"} or {"name", "path"} -- a file, sent and not named, a PDF with a text layer,
    an epub or a plain text file -- or {"text": "..."}, pasted.  `options`: "pages" (a PDF's "3-9",
    counted from 0), "chapter" ("auto" by default, "new" or "last"), "join" ("" or "paragraph") and
    "label".  Refused in the words make() uses for the first original -- empty, wrong kind -- and for a
    book that is finished (reopen it first) or was never made by an agent.

    Whole or not at all: the file is written beside its place and renamed, then the list is written, so
    a disk that fills leaves the folder as it was, and the agent never reads an entry whose file is not
    there.  The text goes into ASKS.md as well as the list: that file is read before every batch."""
    options = options or {}
    st = state(book_dir)
    if st == "none":
        raise ValueError("this book was not made by an agent, so there is nobody to give a part to")
    if st == "finished":
        raise ValueError("this book is finished: reopen the making to give the agent more text, or add the "
                         "text by hand from the add page")
    chapter = _line(options.get("chapter") or "auto", 12).lower()
    join = _line(options.get("join"), 12).lower()
    if chapter not in CHAPTER_WAYS:
        raise ValueError("no such place for a part: %r (%s)" % (chapter, ", ".join(CHAPTER_WAYS)))
    if join not in JOINS:
        raise ValueError("a part is joined to the paragraph before it with %s, or not at all (empty)" % " or ".join(JOINS[1:]))
    if join and chapter == "new":
        raise ValueError("a part that goes on in the paragraph before it cannot start a new chapter")
    label = _line(options.get("label"), LABEL_MAX)
    if "text" in source:
        text = _clean_text(source.get("text"), TEXT_MAX)
        if not text:
            raise ValueError("the text is empty: there is nothing to add")
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-.")[:40] or "pasted"
        name, data, size, pages = stem + ".txt", text.encode("utf-8"), len(text.encode("utf-8")), None
    else:
        name = _original_name(source.get("name"))
        data = source.get("data")
        pages = _pages(options.get("pages")) if name.endswith(".pdf") else None
        if data is not None:
            size, head = len(data), data[:4096]
        else:
            size = os.path.getsize(source["path"])
            with open(source["path"], "rb") as f:
                head = f.read(4096)
        _refuse_original(name, size, head)
    with _PARTS_LOCK:
        store = _store(book_dir) or _first_part(book_dir)
        n = max([_int(p.get("n")) for p in store["parts"]] + list(_on_disk(book_dir)) + [0]) + 1
        rel = "%s/part-%03d-%s" % (ORIGINAL, n, name)
        target = os.path.join(book_dir, *rel.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        try:
            with open(target + ".part", "wb") as f:
                if data is not None:
                    f.write(data)
                else:
                    with open(source["path"], "rb") as src:
                        shutil.copyfileobj(src, f, 1 << 20)
            os.replace(target + ".part", target)
        except OSError as e:
            try:
                os.unlink(target + ".part")
            except OSError:
                pass
            raise ValueError("the part could not be written (%s); nothing was changed" % e)
        entry = _entry(n, rel, pages, chapter, join, label, _iso(), size)
        store["parts"].append(entry)
        _save(book_dir, store)
    _note_asks(book_dir, "a part was added",
               "Part %d%s was added: `%s`. Read `parts` in making.json before your next batch, and take it "
               "as its `chapter` says." % (n, " (%s)" % label if label else "", rel))
    return entry


def recovered_text(source, lang, pages=None):
    """The text of a SENT file, for the door that adds text onto a book that is already here -> one string,
    the paragraphs parted by blank lines, which lib/draft.py takes as it takes a pasted text.  The same
    kinds and the same refusals as the first original and every part, and the recovery is
    lib/sourcetext.py's -- the agent's own -- so that a text is read one way wherever it comes in."""
    import sourcetext
    name = _original_name(source.get("name"))
    ext = os.path.splitext(name)[1]
    page_range = _pages(pages) if ext == ".pdf" else None
    path, made = source.get("path"), None
    if path is None:
        data = source["data"]
        _refuse_original(name, len(data), data[:4096])
        fd, path = tempfile.mkstemp(prefix="parseh-text-", suffix=ext)
        made = path
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    else:
        with open(path, "rb") as f:
            _refuse_original(name, os.path.getsize(path), f.read(4096))
    try:
        paras = sourcetext.recover(path, lang, page_range, kind=ext.lstrip("."))
    finally:
        if made:
            os.unlink(made)
    if not paras:
        raise ValueError("no text could be recovered from %s" % name)
    return "\n\n".join(paras)


def set_more_coming(book_dir, flag):
    """"This is all the text" (False), or that more is coming after all (True) -> the flag."""
    st = state(book_dir)
    if st != "making":
        raise ValueError("this book is finished: reopen the making first" if st == "finished"
                         else "this book was not made by an agent")
    with _PARTS_LOCK:
        store = _store(book_dir) or _first_part(book_dir)
        if store["more_coming"] == bool(flag):
            return bool(flag)
        store["more_coming"] = bool(flag)
        _save(book_dir, store)
    _note_asks(book_dir, "more text is coming" if flag else "this is all the text",
               "The person says more text will be given: after the parts in making.json, wait for the next "
               "(`stage`: `waiting`)." if flag else
               "The person says there is no more text. When every part in making.json is taken and the "
               "batches are in, say \"the text is complete\" and stop.")
    return bool(flag)


def _library_again():
    """The library page written again, so that a card says what the book is now; it catches up at the
    next build where this cannot be done."""
    try:
        subprocess.run([sys.executable, os.path.join(LIB, "make_index.py")], cwd=booklib.ROOT,
                       capture_output=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        pass


def reopen(book_dir):
    """A finished book's making taken up again, so that a part added next month goes on where it stopped.

    `state` is "making" again, which brings the lock on editing back; `finished` is removed.  annot/,
    original/ and NOTES.md are untouched, and the reader and the .tex stay as they are until the agent
    assembles again.  The agent is told in ASKS.md, after the entry that told it to stop."""
    if state(book_dir) != "finished":
        raise ValueError("this book is not finished: there is nothing to reopen" if state(book_dir) == "making"
                         else "this book was not made by an agent")
    with _PARTS_LOCK:
        doc, _bad = read(book_dir)
        doc = dict(doc or {}, state="making")
        doc.pop("finished", None)
        _write_json(path_of(book_dir, MAKING), doc)
    # THE FINISH THAT ENDED IT IS OVER: a panel that still found it "done" would take the making for ended
    # and reload itself for ever
    with _FINISH_LOCK:
        FINISH.pop(os.path.realpath(book_dir), None)
    _note_asks(book_dir, "reopened",
               "The person reopened the making: the entry above that said to stop is taken back. Read "
               "`parts` in making.json: new text may be waiting.")
    _library_again()
    return {"state": "making"}


# WHAT FINISH WAITS FOR, one small function to each thing it may wait for (FINISH_WAITS_FOR)
def _waits_text(book_dir, doc):
    store = _store(book_dir)
    return ["you have not said that this is all the text: more may be coming"] if store and store["more_coming"] else []


def _waits_parts(book_dir, doc):
    store = _store(book_dir)
    done, _said, _of = _taken(doc)
    return ["part %d%s has not been taken by the agent yet" % (_int(p.get("n")), " (%s)" % _line(p.get("label"), 60)
                                                                if p.get("label") else "")
            for p in (store["parts"] if store else ()) if _int(p.get("n")) > 0 and _int(p.get("n")) not in done]


def _waits_agent(book_dir, doc):
    stage = _line(doc.get("stage")).lower() or "folder"
    if stage in ("done", "waiting"):
        return []
    return ["the agent has not said it is done: its record says \"%s\", and what it writes next is lost "
            "once the book is finished" % stage_words(doc)]


_WAITS = {"text": _waits_text, "parts": _waits_parts, "agent": _waits_agent}


def finish_blockers(book_dir):
    """What stands between the person and a Finish, in sentences ([] when nothing does).  WHAT IT
    WAITS FOR IS THE OWNER'S TO DECIDE (FINISH_WAITS_FOR above): a book is finished when everything
    given so far is in it, and with parts that is not a thing Parseh can know by itself."""
    doc, bad = read(book_dir)
    if doc is None or doc.get("state") == "finished":
        return []
    if bad:
        return [bad]
    return [s for key in FINISH_WAITS_FOR for s in _WAITS[key](book_dir, doc)]


def finish_gate(book_dir, confirmed=False):
    """May a Finish start? -> (yes or no, the sentences that stand in the way).  A second press, with
    `confirmed`, goes through unless FINISH_CONFIRMABLE says the sentences are not to be passed."""
    blockers = finish_blockers(book_dir)
    return (not blockers or (FINISH_CONFIRMABLE and bool(confirmed))), blockers


# ------------------------------------------------------------------ the instructions (the seam)
_TOKEN = re.compile(r"\{\{([A-Z_]+)\}\}")


def _fill(text, values):
    return _TOKEN.sub(lambda m: str(values.get(m.group(1), m.group(0))), text)


def _reading_and_words(L, folder_python, lib, book_dir):
    """What only a language with a reading, or one that divides a chunk into words, needs told: the
    fields it adds, the tool that starts the division from the machine's, and a chunk that shows them.
    Returns (KANA_RULE, WORDS_STEP, KANA_EXAMPLE) -- three strings, empty where the language has none."""
    reading_word = "`kana`" if L.reading else "`tr`"
    rule = ""
    if L.reading:
        rule += (" %s is a **reading language**: every glossed chunk also carries `kana`, the reading of the "
                 "whole chunk (never a per-character alignment); `assemble.py` writes it as `\\chr` and "
                 "refuses a chunk without it, and `check_batch.py` reports one." % L.name)
    step = ""
    if L.words:
        rule += (" %s also divides every glossed chunk into **words**, and the division is required: `words` is "
                 "one line, the words parted by spaces and each word's %s after it in parentheses, and the "
                 "words joined with nothing between them must be `fa` exactly (the `## Words` section of the "
                 "conventions below is the rule). **The machine starts the words and the annotator corrects "
                 "them** (step 2b): the division is never written from nothing. `words` never replaces %s, "
                 "which stays the reading of the whole chunk; `assemble.py` writes a chunk with words as `\\%s` "
                 "and `check_batch.py` checks the line, and warns about a paragraph none of whose chunks has "
                 "one." % (L.name, "kana" if L.reading else L.translit_label, reading_word,
                           "chrw" if L.reading else "chw"))
        step = ("For %s every chunk's words start from the machine's, as a text pasted into a draft does. As "
                "soon as a paragraph's chunks are cut and their %s written, run `%s %s --lang %s --json "
                "%s/annot/chN_pNN.json`, which gives every chunk without words the proposed `words` -- each "
                "word's reading cut from the chunk's own -- and fills a reading still blank from the words. "
                "Then read every line against `## Words` and correct, in the JSON, the division and the "
                "readings: the proposal is where the words start, never where they end. A chunk cut again "
                "afterwards gets its `words` deleted and the tool run once more. "
                % (L.name, reading_word, folder_python, os.path.join(lib, "fill_words.py"), L.code, book_dir))
    example = ""
    if L.reading or L.words:
        example = ("\nFor %s every chunk has %s%s%s:\n\n```json\n{\"fa\": \"...\"%s%s, \"tr\": \"...\", "
                   "\"voc\": \"...\", \"en\": \"...\"}\n```\n"
                   % (L.name, "the reading beside the transliteration" if L.reading else "",
                      ", and " if L.reading and L.words else "", "its words" if L.words else "",
                      ", \"words\": \"...\"" if L.words else "", ", \"kana\": \"...\"" if L.reading else ""))
    return rule, step, example


# THE METHOD IS AUTHORED ONCE, as parts (docs/book-method/): method.md is the entry -- what the agent does,
# in order -- and every other *.md there is a reference the entry points to, in the order of METHOD_ORDER.
# They are resolved two ways, and neither is written twice: AGENTS.md is the whole of them in one file,
# filled in for this book; the project skill parseh-book (lib/skills.py) is the entry as SKILL.md and the
# references as its references.  docs/new-book-prompt.md -- the one readable template the kit, the person's
# editor ("prompt: Parseh's") and the tests all read -- is made from the parts by method_template(), and
# a test holds the two equal: edit the parts, then run `python3 lib/making.py template`.
# THE PARTS' RULES (the skill is made from them by someone else, and a test holds each): a part is
# markdown that starts with its `##` title; only the placeholders the kit lists for book-new
# (promptkit.placeholders) and the kit's flags are in it; and only the entry links to the others, as
# [Title](name.md), the text being the title of that part -- a reference never sends the reader to another.
METHOD_DIR = os.path.join(booklib.ROOT, "docs", "book-method")
METHOD_ENTRY = "method"
METHOD_ORDER = ("files", "source", "parts", "batch-recipe", "fields", "meaning", "error-classes",
                "verification", "language")
METHOD_LINK = re.compile(r"\[([^\]\n]+)\]\(([a-z][a-z0-9-]*)\.md\)")


def method_parts():
    """The parts of the method -> [(name, text)], the entry first and then the references in
    METHOD_ORDER; the text as written, placeholders and all."""
    out = []
    for name in (METHOD_ENTRY,) + METHOD_ORDER:
        with open(os.path.join(METHOD_DIR, name + ".md"), encoding="utf-8", newline="") as f:
            out.append((name, f.read().replace("\r\n", "\n").strip("\n")))
    return out


def method_template():
    """What docs/new-book-prompt.md says -> str: the parts in one file, each reference a section of it.  A
    link between parts, [Title](name.md), says where the section is when they are separate files; in
    one file the section is under that very title, so it is written as the title and nothing more."""
    return "\n\n".join(METHOD_LINK.sub(lambda m: "**%s**" % m.group(1), text)
                       for _name, text in method_parts()) + "\n"


def method_values(facts):
    """Every placeholder of the book's instructions that is a fact of this book -> {NAME: text}: where
    things are, who the book is by, how a chunk of its language is told, what the page chose to show."""
    book, orig = facts["book"], facts["original"]
    ref = facts.get("reference")
    ex = facts.get("examples") or []
    L, G = languages.get(book["language"]), languages.gloss_or_default(book["gloss"])
    pages = ", pages %d-%d of it (counted from 0)" % tuple(orig["pages"]) if orig.get("pages") else ""
    latin = book["title_latin"] or book["slug"]
    rule, step, example = _reading_and_words(L, facts["python"], facts["lib"], book["dir"])
    values = {
        "TITLE_NOTE": " (%s)" % book["title"] if book["title"] and book["title"] != latin else "",
        "TITLE_LATIN": latin,
        "AUTHOR_LATIN": book["author_latin"] or book["author"] or "an unnamed author",
        "LANG_NAME": L.name, "LANG_NATIVE": L.native, "LANG": L.code,
        "GLOSS_NAME": G.name, "GLOSS": G.code,
        "BOOK_DIR": book["dir"], "BOOK_REL": book["rel"], "ROOT": facts["root"],
        "LIB": facts["lib"], "PYTHON": facts["python"], "BATCH": str(facts.get("batch", BATCH)),
        "BATCH_LAST": str(facts.get("batch", BATCH) - 1),
        "ORIGINAL": os.path.join(book["dir"], *orig["file"].split("/")), "PAGES": pages,
        "PAGE_ARGS": "--from %d --to %d" % tuple(orig["pages"]) if orig.get("pages") else "",
        "CONVENTIONS": os.path.join(facts["root"], "docs", "lang", L.code + ".md"),
        "REFERENCE": ("- A finished edition to learn the method from -- read it, change nothing: "
                      "`%s`\n" % ref["path"]) if ref else "",
        "EXAMPLES": ("- The person's finished books in %s, as examples only -- read them, change "
                     "nothing: `%s` (%s)\n" % (L.name, facts["examples_dir"],
                                               ", ".join(e["rel"] for e in ex[:12]))) if ex else "",
        "STRIP_NOTE": ("once the marks (harakat) are stripped from both sides" if L.strip_range else
                       "-- %s carries no marks to strip, so exactly" % L.name),
        "LANG_DIGIT_EXAMPLE": L.to_native_digits("3"), "LANG_LABEL_EXAMPLE": L.to_native_digits("3.1"),
        "KANA_RULE": rule, "WORDS_STEP": step, "KANA_EXAMPLE": example,
        "EVIDENCE_HELPER": evidence_helper(facts, L),
    }
    return values


def evidence_helper(facts, L):
    """The line of the method that says how to ask the analyzers (lib/evidence.py), or nothing where nobody chose
    that on Settings -> Linguistic analysis, or no analyzer here covers the language."""
    import analysisconfig
    import analyzer
    if analysisconfig.choice("evidence") != "on" or not analyzer.available(L.code, syntax=True):
        return ""
    return ("A linguistic analyzer may be asked about a sentence: `%s %s %s --text \"...\"` prints what it read, "
            "and writes nothing. What it prints is evidence and can be wrong: where it disagrees with what the sentence "
            "plainly says, the sentence is right. It gives no right to change the text or the chunks, and nothing of it "
            "goes into a file you write. "
            % (facts["python"], os.path.join(facts["lib"], "evidence.py"), L.code))


def _asked(facts, options):
    """The kit's options for this book: the scheme of its transliteration is the book's own fact, and the
    short vowels are what the page chose."""
    return promptkit.given({"translit": facts["book"].get("translit"), "marks": (options or {}).get("marks")})


def _chosen(prompt_id, L):
    """The person's own prompt for the book's instructions, by its id (lib/prompts.py), or None for Parseh's.
    Refused in words when it is gone, or is for another place or another language."""
    if not prompt_id:
        return None
    import prompts
    try:
        return prompts.resolve("book-new", str(prompt_id), L)
    except prompts.PromptsError as e:
        raise ValueError(str(e))


def resolved_parts(facts, options=None):
    """The parts of the method filled in for THIS book -> [(name, text)], entry first: the placeholders and
    the flags resolved by the kit, the rule on the meaning and the language's conventions in, the links
    between parts left as they are.  What a project skill is made from (skill_files), and the same words
    as AGENTS.md's -- a person's own prompt apart, which is theirs."""
    book = facts["book"]
    L, G = languages.get(book["language"]), languages.gloss_or_default(book["gloss"])
    values, asked = method_values(facts), _asked(facts, options)
    return [(name, promptkit.assemble("book-new", L, G, values=values, options=asked, template=text).instructions)
            for name, text in method_parts()]


def instructions_text(facts, options=None):
    """What AGENTS.md says for these facts -> str: docs/new-book-prompt.md, assembled by the prompt kit
    (the language's conventions and the rule on the meaning come in by it), or the person's own prompt
    for it (`options["prompt"]`, an id).  The seam is write_instructions, which calls this."""
    book = facts["book"]
    L, G = languages.get(book["language"]), languages.gloss_or_default(book["gloss"])
    chosen = _chosen((options or {}).get("prompt"), L)
    try:
        made = promptkit.assemble("book-new", L, G, values=method_values(facts), options=_asked(facts, options),
                                  instructions=chosen and chosen.instructions, custom=chosen and chosen.name)
    except promptkit.PromptError as e:
        import prompts
        raise ValueError(prompts.unmade(chosen, e) if chosen else "the instructions could not be made: %s" % e)
    return made.text


CLAUDE_LINE = "Read AGENTS.md in this folder before anything else, and follow it.\n"
# THE PROJECT SKILL, where the agents that look for one look: Claude Code reads .claude/skills/<name>/ and
# does not read .agents/skills/; Codex, Gemini CLI, Cursor, GitHub Copilot and VS Code read the second (the
# last three the first as well), so the same folder is written to both.  Copies, not links: Windows
SKILL = "parseh-book"
SKILL_HOMES = (".claude/skills", ".agents/skills")
INSTRUCTIONS_AGAIN_SAID = ("The instructions are written again. The agent you opened in this folder has already "
                           "read the old ones: tell it to read AGENTS.md again before its next batch.")


def skill_files(facts, options=None):
    """THE PROJECT SKILL of this book -> {path inside the skill's folder: text}, `SKILL.md` and its `references/`;
    empty where lib/skills.py is not there.

    lib/skills.py (lane G) makes it, `skills.build_for_book(L, G, options, values)`: the method of the job as the
    parts of docs/book-method/ say it, settled for THIS book -- its language, its options, the values of its names
    -- so that the skill is the same words as the instructions' and never a copy written by hand.  Only the import
    may fail quietly: whatever else goes wrong in the skill is a bug and says so."""
    try:
        import skills
    except ImportError:
        return {}
    book = facts["book"]
    L, G = languages.get(book["language"]), languages.gloss_or_default(book["gloss"])
    try:
        return dict(skills.build_for_book(L, G, _asked(facts, options), method_values(facts)).files)
    except Exception as e:                  # a bug of Parseh's, said in words and not as a stack, and nothing is written
        raise ValueError("the project skill could not be made (%s): nothing was written" % (e or type(e).__name__))


def _write_text(path, text):
    """A file replaced whole or not at all, as making.json is: an agent that reads AGENTS.md while it is
    written again must not find half of it."""
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def _skill_names(files):
    """The skill's files, refused before any is written when one would land outside the skill's folder."""
    for name in files:
        parts = name.split("/")
        if not parts[0] or os.path.isabs(name) or ".." in parts or "\\" in name:
            raise ValueError("a skill file named %r would land outside the skill's folder" % name)
    return files


def _write_skill(book_dir, home, files):
    """One copy of the skill, written whole: its own folder replaced and nothing beside it touched (the
    person may keep other skills of their own in the same place) -> [the relative paths written]."""
    folder = os.path.join(book_dir, *home.split("/"), SKILL)
    shutil.rmtree(folder, ignore_errors=True)
    out = []
    for name, text in sorted(files.items()):
        parts = name.split("/")
        target = os.path.join(folder, *parts)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        out.append("/".join([home, SKILL] + parts))
    return out


def write_instructions(book_dir, facts, options=None):
    """THE SEAM for the agent's instructions -> [the relative paths written]: AGENTS.md, CLAUDE.md, and
    the project skill in both places agents look for one.

    `book_dir` is where to write, which may not be the folder's final name yet
    (make() writes into a staging directory and renames it); everything the text
    says about places comes from `facts`.  `facts` is what make() knows -- see
    facts_for -- and `options` what the page chose ("reference", "examples", "marks", "prompt").
    Written again at any time, it replaces only its own files -- never NOTES.md, ASKS.md,
    making.json or anything the agent made.  Whatever can be refused is refused before the
    first file is written.  Parseh writes no tool's permission file: the agent and its
    permissions are the person's."""
    text, skill = instructions_text(facts, options), _skill_names(skill_files(facts, options))
    for name, body in ((AGENTS, text), (CLAUDE, CLAUDE_LINE)):
        _write_text(path_of(book_dir, name), body)
    written = [AGENTS, CLAUDE]
    if skill:
        for home in SKILL_HOMES:
            written += _write_skill(book_dir, home, skill)
    return written


def rewrite_instructions(book_dir):
    """THE INSTRUCTIONS WRITTEN AGAIN for a folder that is made -> {"written": [relative paths], "said":
    what the person is to do next, "notes": [what could not be as it was]}.

    What an agent reads is made from Parseh's words (which an update, or the person's editing of their own
    prompt, may have changed) and from the book's facts (book.json, and what making.json recorded of how the
    folder was made), so it is made again from the same places: nothing is asked of the person.  Only the
    agent's reading is written -- AGENTS.md, CLAUDE.md, the skill folders -- and never NOTES.md, ASKS.md,
    making.json or anything the agent made.  The agent whose chat has already read the old file is not
    told by this: `said` says that it must be."""
    state_now = state(book_dir)
    if state_now == "none":
        raise ValueError("this book was not made by an agent, so it has no instructions to write")
    if state_now == "finished":
        raise ValueError("this book is finished: no agent is reading its instructions any more")
    try:
        with open(path_of(book_dir, "book.json"), encoding="utf-8") as f:
            meta = json.load(f)
        meta = meta if isinstance(meta, dict) else {}
    except (OSError, ValueError):
        raise ValueError("book.json cannot be read, so the instructions cannot be written again")
    made_with = (read(book_dir)[0] or {}).get("instructions")
    made_with = made_with if isinstance(made_with, dict) else {}
    notes = []
    options = {"examples": bool(made_with.get("examples")), "marks": made_with.get("marks") or None,
               "reference": str(made_with.get("reference") or ""), "prompt": str(made_with.get("prompt") or "")}
    shelf = os.path.dirname(os.path.dirname(os.path.abspath(book_dir)))
    if options["reference"]:
        try:
            _shelf_book(options["reference"], shelf)
        except ValueError:
            notes.append("the finished edition it was told to learn from (%s) is not on the shelf any more: "
                         "left out" % options["reference"])
            options["reference"] = ""
    ident = _identity({"lang": meta.get("language"), "gloss": meta.get("gloss"), "title": meta.get("title"),
                       "title_latin": meta.get("title_latin"), "title_en": meta.get("title_en"),
                       "author": meta.get("author"), "author_latin": meta.get("author_latin"),
                       "year": meta.get("year"), "blurb": meta.get("blurb"), "slug": meta.get("slug"),
                       "translit": meta.get("translit") or ""})
    first = str(meta.get("source_pdf") or "")
    if not first.startswith(ORIGINAL + "/"):
        raise ValueError("book.json does not say which file the book is made from, so the instructions "
                         "cannot be written again")
    pages = meta.get("source_pages") if isinstance(meta.get("source_pages"), list) else None
    if options["prompt"]:
        import prompts
        try:
            prompts.resolve("book-new", options["prompt"], ident["lang"])
        except prompts.PromptsError as e:
            notes.append("the prompt of yours it was written with cannot be used now (%s): Parseh's own "
                         "was written" % e)
            options["prompt"] = ""
    facts = facts_for(ident, first.split("/", 1)[1], pages, options, os.path.abspath(book_dir), shelf)
    return {"written": write_instructions(book_dir, facts, options), "said": INSTRUCTIONS_AGAIN_SAID,
            "notes": notes}


# ------------------------------------------------------------------ making the folder
def _shelf_book(rel, shelf):
    """A book on the shelf by its address (persian/farsi-shakar-ast) -> its
    directory, or a refusal.  Checked as serve.py's book_dir checks a URL: no
    climb out of books/, and a book.json there."""
    parts = str(rel or "").strip("/").split("/")
    if not (1 <= len(parts) <= 2) or any(p in ("", ".", "..") or p.startswith(".") for p in parts):
        raise ValueError("%r is not a book on the shelf" % rel)
    d = os.path.join(shelf, *parts)
    if not os.path.isfile(os.path.join(d, "book.json")):
        raise ValueError("there is no book called %r on the shelf to learn from" % rel)
    return d


def _identity(fields, need=True):
    """The book's facts, checked -> a dict.  `need` is False for the preview of
    the instructions, which is asked for while the form is still being filled."""
    import draft                                        # noqa: E402  lazily: it pulls the video door in
    fields = fields or {}
    L = draft._lang(fields.get("lang"))
    G = draft._gloss(fields.get("gloss"))
    title = _line(fields.get("title"), 200)
    if need and not title:
        raise ValueError("a book needs a title in %s" % L.name)
    got = {"title": title}
    for k in ("title_latin", "title_en", "author", "author_latin", "year", "blurb"):
        got[k] = _line(fields.get(k), 400)
    # what goes into main.tex is TeX, and one of these characters ends the book
    # there as surely as it would in a paragraph: refused here, in words, and not
    # found days later in a LaTeX log
    for k, said in (("title", "the title"), ("title_latin", "the transliterated title"),
                    ("author", "the author"), ("author_latin", "the transliterated author")):
        bad = TEX_SPECIAL.search(got[k])
        if bad:
            raise ValueError("%s cannot hold %s: TeX reads it as an instruction. Write it out in "
                             "words." % (said, "a backslash" if bad.group() == "\\" else
                                         "the character " + bad.group()))
    upper = _line(fields.get("title_latin_upper"), 400)
    if upper and TEX_SPECIAL.search(upper):
        upper = ""
    wanted = _line(fields.get("slug"), 80) or got["title_latin"] or title
    slug = draft.slugify(wanted)
    if need and not slug:
        raise ValueError("no directory name could be made from %r: give a slug of ascii letters, "
                         "digits and hyphens (a title written in its own script leaves none "
                         "behind)" % wanted)
    got.update(slug=slug or "new-book", lang=L, gloss=G,
               upper=upper or (got["title_latin"] or slug or "new-book").upper())
    # THE SCHEME OF THE BOOK'S TRANSLITERATION is a fact of the book (book.json "translit"), written
    # only when it is not the language's usual one: "ipa", or "" (promptkit.OPTIONS; a value that is
    # neither is refused in words)
    got["translit"] = "ipa" if promptkit.resolve(
        "book-new", L, promptkit.given(fields)).get("translit") == "ipa" else ""
    return got


def _pages(v):
    m = re.fullmatch(r"\s*(\d+)\s*[-\u2013]\s*(\d+)\s*", str(v or ""))
    if not v or not str(v).strip():
        return None
    if not m or int(m.group(1)) > int(m.group(2)):
        raise ValueError("the page range is two numbers, the first not after the last: 13-21")
    return [int(m.group(1)), int(m.group(2))]


def _original_name(name):
    base = os.path.basename(str(name or "").replace("\\", "/")).strip()
    stem, ext = os.path.splitext(base)
    ext = ext.lower()
    if ext not in ORIGINAL_EXTS:
        raise ValueError("the original has to be a PDF with a text layer, an epub or a plain text "
                         "file (%s): %r is none of them" % (", ".join(ORIGINAL_EXTS), base or "no file"))
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-.")[:60] or "original"
    return stem + ext


def _looks_like(ext, head):
    if ext == ".pdf":
        return head.lstrip().startswith(b"%PDF-")
    if ext == ".epub":
        return head.startswith(b"PK")
    return b"\x00" not in head[:4096]


def _refuse_original(name, size, head):
    """What the first original and every part are refused for, in the same words."""
    if not size:
        raise ValueError("the original is empty: choose the file again")
    if not _looks_like(os.path.splitext(name)[1], head):
        raise ValueError("%s does not look like %s: choose the right file" % (
            name, {"pdf": "a PDF", "epub": "an epub"}.get(name.rsplit(".", 1)[1], "a text file")))


def facts_for(identity, orig_file, pages, options, dest, shelf=None):
    """Everything the instructions may need, as one plain dict.  `dest` is the
    folder's final place; the Python is the environment's (runtime.find_env) and
    its full path, so the agent needs no conda of its own.  A reference is read
    where it lies and never copied; the person's other books are named only when
    the page's box says so, and only the ones in this book's language."""
    import runtime
    shelf = shelf or booklib.BOOKS_DIR
    L, G = identity["lang"], identity["gloss"]
    reference = None
    if options.get("reference"):
        rd = _shelf_book(options["reference"], shelf)
        rb = booklib.Book(rd)
        reference = {"rel": os.path.relpath(rd, shelf).replace(os.sep, "/"), "path": rd,
                     "title": rb.title_latin or rb.title, "language": rb.language,
                     "has_notes": os.path.isfile(path_of(rd, NOTES))}
    examples = []
    if options.get("examples"):
        for b in booklib.all_books(shelf, language=L.code):
            if os.path.realpath(b.dir) != os.path.realpath(dest) and not is_making(b.dir):
                examples.append({"rel": os.path.relpath(b.dir, shelf).replace(os.sep, "/"),
                                 "path": b.dir, "title": b.title_latin or b.title})
    return {
        "parseh": version.VERSION, "root": booklib.ROOT, "lib": LIB,
        "python": runtime.find_env()[1] or sys.executable, "batch": BATCH,
        "book": {"dir": dest, "rel": "books/%s/%s" % (L.folder, identity["slug"]),
                 "folder": L.folder, "slug": identity["slug"],
                 "title": identity["title"], "title_latin": identity["title_latin"],
                 "title_en": identity["title_en"], "author": identity["author"],
                 "author_latin": identity["author_latin"], "year": identity["year"],
                 "blurb": identity["blurb"], "language": L.code, "language_name": L.name,
                 "gloss": G.code, "gloss_name": G.name, "translit": identity["translit"]},
        "original": {"file": "%s/%s" % (ORIGINAL, orig_file), "pages": pages},
        "reference": reference, "examples": examples,
        "examples_dir": os.path.join(shelf, L.folder)}


def form_facts(fields, options=None, into=None):
    """The facts of the make page's form as it stands, half filled or not -> facts (what instructions_text and
    the skill's request are made from); a reference that is not on the shelf is still refused."""
    options = options or {}
    into = into or booklib.BOOKS_DIR
    ident = _identity(fields, need=False)
    try:
        name = _original_name(fields.get("original"))
    except ValueError:
        name = "the-book.pdf"
    try:
        pages = _pages(fields.get("pages")) if name.endswith(".pdf") else None
    except ValueError:
        pages = None
    dest = os.path.join(into, ident["lang"].folder, ident["slug"])
    return facts_for(ident, name, pages, options, dest, into)


def instructions_for(fields, options=None, into=None):
    """What the folder's AGENTS.md would say for what is in the form now, written
    nowhere: the page shows it, and copies it for an agent that does not read the
    file by itself.  The form may be half filled -- what is missing reads as a
    placeholder -- but a reference that is not on the shelf is still refused."""
    options = options or {}
    return instructions_text(form_facts(fields, options, into), options)


def skill_request_for(facts, options, chars):
    """THE SHORT REQUEST FOR THE BOOK'S SKILL (lib/skills.py, lane G), which the row beside the instructions offers
    to copy for a chat that has the parseh-book skill installed: `chars` is the size of the instructions it stands
    in for.  None where there is no skills module; a reason, said in words, where it cannot be made."""
    try:
        import skills
    except ImportError:
        return None
    book = facts["book"]
    L, G = languages.get(book["language"]), languages.gloss_or_default(book["gloss"])
    chosen = _chosen((options or {}).get("prompt"), L)
    return skills.safe(lambda: skills.for_book(L, G, _asked(facts, options), method_values(facts), chars, chosen),
                       "parseh-book")


NOTES_START = """\
# {title} -- notes

The journal of this edition: what the source needed, the decisions taken, what is open. It is
kept by whoever makes the book, and it is the first thing to read if you take over.

- Made from `{original}`{pages}, started {when}.
"""


def make(fields, original, options=None, into=None):
    """The book's folder, written whole or not at all -> {"dir", "path", "slug",
    "folder", "language", "files", "instructions"}.

    `fields` is the book's facts (the ones the add page asks, and `pages`);
    `original` is {"name": the file's name, "data": bytes} or {"name", "path"} for
    an upload spooled to disk; `options` is {"reference": "<folder>/<slug>" or "",
    "examples": bool, "marks": the short vowels' option as the page chose it, "prompt": the id
    of the person's own prompt for the instructions, "more_coming": bool (True unless it says
    False)}.  Every refusal is a ValueError with a sentence to show.

    The tree is built beside its place, in a directory with a dot in front (which
    nothing on the shelf reads as a book), and renamed into place at the end: a
    refusal, or a disk that fills, leaves nothing behind, and a book already there
    is never written over."""
    options = options or {}
    into = into or booklib.BOOKS_DIR
    ident = _identity(fields)
    name = _original_name(original.get("name"))
    # a page range is a PDF's: an epub or a text file has no pages to count
    pages = _pages(fields.get("pages")) if name.endswith(".pdf") else None
    if "data" in original:
        size, head = len(original["data"]), original["data"][:4096]
    else:
        size = os.path.getsize(original["path"])
        with open(original["path"], "rb") as f:
            head = f.read(4096)
    _refuse_original(name, size, head)
    L = ident["lang"]
    parent = os.path.join(into, L.folder)
    dest = os.path.join(parent, ident["slug"])
    if os.path.exists(dest):
        raise ValueError("a book is already at books/%s/%s/ -- choose another slug, or move that "
                         "one out of the way" % (L.folder, ident["slug"]))
    facts = facts_for(ident, name, pages, options, dest, into)     # a reference not on the shelf is refused here, before a file is written
    import newbook                                      # noqa: E402  its skeleton is the one place the main.tex is written
    made_parent = not os.path.isdir(parent)
    os.makedirs(parent, exist_ok=True)
    stage = tempfile.mkdtemp(prefix=".making-", dir=parent)
    tree = os.path.join(stage, ident["slug"])
    try:
        os.makedirs(tree)
        for sub in (ORIGINAL, "source/paras", "annot"):
            os.makedirs(os.path.join(tree, *sub.split("/")))
        target = os.path.join(tree, ORIGINAL, name)
        if "data" in original:
            with open(target, "wb") as f:
                f.write(original["data"])
        else:
            shutil.copyfile(original["path"], target)
        meta = {"slug": ident["slug"], "language": L.code, "gloss": ident["gloss"].code,
                "title": ident["title"],
                "title_latin": ident["title_latin"] or ident["slug"], "title_en": ident["title_en"],
                "author": ident["author"], "author_latin": ident["author_latin"],
                "year": ident["year"], "blurb": ident["blurb"], "main": "main.tex",
                "audio": None, "transcript": None, "source_pdf": "%s/%s" % (ORIGINAL, name)}
        if pages:
            meta["source_pages"] = pages
        if ident["translit"]:
            meta["translit"] = ident["translit"]
        _write_json(os.path.join(tree, "book.json"), meta)
        values = {"TITLE": ident["title"], "AUTHOR": ident["author"],
                  "TITLE_LATIN": meta["title_latin"], "AUTHOR_LATIN": ident["author_latin"],
                  "TITLE_LATIN_UPPER": ident["upper"], "LANG": L.code, "LANG_NAME": L.name,
                  "GLOSS": ident["gloss"].code, "GLOSS_NAME": ident["gloss"].name,
                  "SLUG": ident["slug"]}
        with open(os.path.join(tree, "main.tex"), "w", encoding="utf-8", newline="\n") as f:
            f.write(_fill(newbook.MAIN_TEX, values) + "\n")
        with open(os.path.join(tree, NOTES), "w", encoding="utf-8", newline="\n") as f:
            f.write(NOTES_START.format(
                title=meta["title_latin"], original="%s/%s" % (ORIGINAL, name),
                pages=", pages %d-%d" % tuple(pages) if pages else "",
                when=time.strftime("%Y-%m-%d")))
        open(os.path.join(tree, ASKS), "w", encoding="utf-8").close()
        now = _iso()
        # THE ORIGINAL IS PART 1, so that the list is whole from the first minute; "more text later" is
        # what a folder starts with, and the make page may say "this is all the text" at once
        first = {"parts": [_entry(1, "%s/%s" % (ORIGINAL, name), pages, "new", "", "", now, size)],
                 "more_coming": options.get("more_coming") is not False}
        _write_json(os.path.join(tree, ORIGINAL, PARTS_COPY), first)
        # HOW THE INSTRUCTIONS WERE WRITTEN, kept so that they can be written again the same way
        kept = {"reference": (facts["reference"] or {}).get("rel", ""), "examples": bool(options.get("examples")),
                "prompt": str(options.get("prompt") or "")}
        marks = promptkit.resolve("book-new", L, _asked(facts, options)).get("marks")
        if marks:
            kept["marks"] = marks
        _write_json(os.path.join(tree, MAKING), dict({
            "state": "making", "parseh": version.VERSION, "started": now, "updated": now,
            "stage": "folder", "on": "", "chapters": [], "batches": {"done": 0, "of": 0},
            "checks": {}, "instructions": kept}, **first))
        written = write_instructions(tree, facts, options)
        try:
            os.rename(tree, dest)
        except OSError as e:
            raise ValueError("the folder could not be put in place (%s); nothing was written" % e)
    except BaseException:
        if made_parent:
            # THE STAGING DIRECTORY GOES FIRST: while it is there the language's folder is not empty, and
            # a refusal would leave that folder behind
            shutil.rmtree(stage, ignore_errors=True)
            try:
                os.rmdir(parent)
            except OSError:
                pass
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return {"slug": ident["slug"], "folder": L.folder, "language": L.code,
            "dir": os.path.relpath(dest, into).replace(os.sep, "/"), "path": dest,
            "original": "%s/%s" % (ORIGINAL, name), "instructions": written,
            "files": sorted(["book.json", "main.tex", NOTES, ASKS, MAKING, "%s/%s" % (ORIGINAL, name)]
                            + written)}


# ------------------------------------------------------------------ opening the folder
# A FACT AND NOT A PERMISSION (the owner, 2026-09-29: everything else is open to every device let in):
# the file manager opens on the screen of the computer Parseh runs on, so only a request from that
# computer asks for it (serve.py).  What any other device is told:
OPEN_SAID = ("Opening the folder shows it on the screen of the computer Parseh runs on, so that is where it "
             "is done: from this device, copy the path.")


def open_program(path):
    """The command that shows a folder in this system's file manager, or None."""
    if os.name == "nt":
        return ["explorer", path]
    if sys.platform == "darwin":
        return ["open", path]
    return [shutil.which("xdg-open") or "xdg-open", path]


def open_folder(path):
    """The system's file manager on `path` -> None, or a sentence saying why it
    could not be opened.  Never waited for: a file manager runs as long as the
    person keeps it open."""
    if not os.path.isdir(path):
        return "the folder is not there any more"
    try:
        subprocess.Popen(open_program(path), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=os.name != "nt")
    except OSError as e:
        return ("this computer has no file manager Parseh can start (%s): open the folder "
                "from the path above" % (e.strerror or e))
    return None


# ------------------------------------------------------------------ Finish
FINISH = {}                         # a book's directory -> its Finish job
_FINISH_LOCK = threading.Lock()


def _job_view(job):
    return {"state": job["state"], "steps": [dict(s) for s in job["steps"]], "said": job["said"],
            "started": job["started"], "finished": job["finished"], "ok": job["ok"]}


def finish_status(book_dir):
    with _FINISH_LOCK:
        job = FINISH.get(os.path.realpath(book_dir))
        return _job_view(job) if job else {"state": "idle", "steps": [], "said": "", "ok": None}


def _python():
    import runtime
    return runtime.find_env()[1] or sys.executable


def verify_words(code, out):
    """verify_book's output in words: (clean, one sentence, [the lines that say what]).
    It prints one summary line, and a line or three for every paragraph that fails."""
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    m = re.search(r"(\d+) paragraphs built, (\d+) reproduce their source exactly, (\d+) mismatched, "
                  r"(\d+) without a source", out)
    built, ok, bad, missing = (int(g) for g in m.groups()) if m else (0, 0, 0, 0)
    problems = []
    for l in lines:
        mm = re.match(r"MISMATCH chapter (\d+) paragraph (\d+) at char (\d+)", l)
        if mm:
            problems.append("chapter %s paragraph %s does not reproduce its source (it differs at "
                            "character %s)" % mm.groups())
        mm = re.match(r"NO SOURCE for chapter (\d+) paragraph (\d+)", l)
        if mm:
            problems.append("chapter %s paragraph %s has no source file in source/paras/" % mm.groups())
    if m and not built:
        return False, "there is no chapter in the book yet, so there is nothing to finish", []
    if code == 0 and m:
        return True, "every paragraph reproduces its source (%d paragraphs)" % built, []
    if not m:
        return False, "the check itself could not run: %s" % (lines[-1] if lines else "it said nothing"), []
    return (False, "%d paragraph%s do%s not reproduce %s source" % (
        bad + missing, "" if bad + missing == 1 else "s", "es" if bad + missing == 1 else "",
        "its" if bad + missing == 1 else "their"), problems[:9])


def build_words(log):
    """The first thing a failed build says was wrong, as buildWhy in lib/parseh.js
    puts it: TeX's own first error, else the line that names what failed."""
    log = [str(l).strip() for l in (log or []) if str(l).strip()]
    err = next((l for l in log if l.startswith("!")), "")
    failed = next((l for l in log if re.search(r"FAILED|could not run|no lualatex", l, re.I)), "")
    if err:
        return (re.sub(r"\s*--.*$", "", failed) + ": " if failed else "") + err
    return failed or " / ".join(log[-2:]) or "the server's log says why"


def finish_start(book_dir, runner=None, wait=1.0):
    """Check the book and build it, as a job -> (the job's view, started).

    Two steps.  verify_book proves every paragraph still reproduces its source;
    then the full build (lib/bookbuild.py, the job the page's build button
    runs -- the ONE build of a book at a time).  Both clean ends the making:
    making.json says finished, and the reader's doors edit the .tex from then on.
    Either not clean says why, in words, and leaves the book being made.

    A COMPUTER WITH NO TeX cannot build the PDF, and would never be able to
    finish.  There the second step builds the reader alone and says the PDF was
    left, which is all that machine could ever have had.

    `runner(cmd, say) -> exit status` stands in for the subprocesses, for a test."""
    key = os.path.realpath(book_dir)
    if state(book_dir) != "making":
        raise ValueError("this book is not being made" if state(book_dir) == "none"
                         else "this book is finished already")
    with _FINISH_LOCK:
        job = FINISH.get(key)
        if job and job["state"] == "running":
            return _job_view(job), False
        job = {"state": "running", "started": time.time(), "finished": None, "ok": None, "said": "",
               "steps": [{"name": "check", "state": "running", "said": "", "lines": []},
                         {"name": "build", "state": "waiting", "said": "", "lines": []}]}
        FINISH[key] = job
        view = _job_view(job)
    threading.Thread(target=_finish, args=(job, book_dir, runner, wait), daemon=True).start()
    return view, True


def _step(job, i, **kw):
    with _FINISH_LOCK:
        job["steps"][i].update(kw)


def _finish(job, book_dir, runner, wait):
    import bookbuild
    import runtime
    clean = False
    try:
        # 1. every paragraph against its source
        cmd = [_python(), os.path.join(LIB, "verify_book.py"), "--book", book_dir]
        out = []
        if runner is not None:
            code = runner(cmd, out.append)
        else:
            r = subprocess.run(cmd, cwd=booklib.ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               env=runtime.environ_for(runtime.find_env()[0]))
            code, out = r.returncode, (r.stdout + r.stderr).splitlines()
        ok, said, lines = verify_words(code, "\n".join(out))
        _step(job, 0, state="done" if ok else "failed", said=said, lines=lines)
        # 2. the full build -- or the reader alone where TeX is not installed
        if not ok:
            _step(job, 1, state="skipped", said="not tried: the check above comes first")
        else:
            no_tex = not shutil.which("lualatex")
            way = "html" if no_tex else "pdf"
            _step(job, 1, state="running")
            while True:
                view, started = bookbuild.start(book_dir, way, runner=runner)
                if started:
                    break
                time.sleep(wait)                    # another build of this book is running: after it
            while bookbuild.status(book_dir)["state"] == "running":
                time.sleep(wait)
            built = bookbuild.status(book_dir)
            if built["state"] == "done":
                _step(job, 1, state="done", said=(
                    "the reader was built; the PDF was left, because TeX is not installed on this "
                    "computer" if no_tex else "the PDF and the reader were built"))
                clean = True
            else:
                _step(job, 1, state="failed", said="the build failed: " + build_words(built["log"]))
    except Exception as e:                              # a bug here must not leave the job running for ever
        _step(job, 1 if job["steps"][0]["state"] == "done" else 0, state="failed",
              said="%s: %s" % (type(e).__name__, e))
    if clean:
        _end_making(book_dir)
    with _FINISH_LOCK:
        job.update(ok=clean, finished=time.time(), state="done" if clean else "failed",
                   said=("finished: the .tex is the book now, and annot/ stays as the record of how "
                         "it was made" if clean else
                         "not finished: the book is still being made; put what is said above right, "
                         "then finish again"))


def _end_making(book_dir):
    """The making is over: making.json says so, the agent is told in ASKS.md (an
    agent still working reads that file before its next batch), and the library
    page is written again so that the card stops saying `being made`."""
    doc, _bad = read(book_dir)
    doc = dict(doc or {}, state="finished", finished=_iso(), updated=_iso())
    _write_json(path_of(book_dir, MAKING), doc)
    with _ASKS_LOCK:
        path = path_of(book_dir, ASKS)
        gap = "\n" if os.path.isfile(path) and os.path.getsize(path) else ""
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write("%s## %s \u2014 finished\n\nThe person finished this book from Parseh. Stop: the "
                    ".tex is the book now. Do not assemble or write anything more in this folder.\n"
                    % (gap, time.strftime("%Y-%m-%d %H:%M")))
    _library_again()


if __name__ == "__main__":
    if sys.argv[1:2] == ["template"]:
        # THE ONE COMMAND OF THE METHOD: docs/new-book-prompt.md written from docs/book-method/
        # (`--check` writes nothing and says whether the file is what the parts make)
        made = method_template()
        with open(promptkit.TEMPLATES["book-new"], encoding="utf-8", newline="") as f:
            same = f.read() == made
        if "--check" in sys.argv:
            sys.exit(0 if same else "docs/new-book-prompt.md is not what docs/book-method/ makes: "
                                    "run python3 lib/making.py template")
        if not same:
            with open(promptkit.TEMPLATES["book-new"], "w", encoding="utf-8", newline="\n") as f:
                f.write(made)
        print("docs/new-book-prompt.md %s" % ("is what docs/book-method/ makes" if same else "written"))
        sys.exit(0)
    for b in booklib.all_books():
        s = state(b.dir)
        if s != "none":
            print("%-40s %-9s %s" % (b.rel_from_books(), s, stage_words(read(b.dir)[0] or {})))
