#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""What the server is working on right now, for every page to show.

    tok = activity.begin("upload", "Uploading momotaro-book.zip (219 MB)",
                         page="/books/", job="k3j9...", total=229638144)
    activity.progress(tok, done=got)             # bytes so far, where known
    activity.progress(tok, stage="installing")   # what it is doing now
    activity.end(tok, ok=True)
    activity.snapshot()   -> {"now", "running": [...], "finished": [...]}

WHY A LIST AT ALL.  A book's PDF takes minutes, a backup of a shelf of
narrated books is gigabytes, and every one of those used to be a request
that said nothing until it was over: the page that started it showed at
most a line of its own, and every other page -- the hub above all, where a
person goes to do the next thing -- showed nothing, so a restore still
running looked exactly like a restore that had died.  serve.py registers
each long request here before it reads the body (so the upload itself is
covered) and takes it off after the last byte of the answer is written (so
a download covers the packing AND the sending), and /__activity hands the
list to lib/activity.js, which draws it on every page.

ONE ENTRY, ONE SHAPE, wherever the work is: a request here, a book build
in lib/bookbuild.py's job table, the HTML guide's compile in
lib/guidebuild.py's, a dictionary being fetched in serve.py's.
The job tables keep their own state and are merged in by serve.py at the
moment of asking, in the shape entry() makes, so nothing is kept twice.

    id        this entry's name, unique while the server runs
    kind      build, upload, download, backup, restore, narration, install,
              compile, lookup -- what the page may draw beside it
    unit      only where `done` and `total` do not count bytes: "items" (a share
              of work, in drawings made; lib/latexbatch.py)
    label     what is happening, in words: "Building the PDF of ..."
    started   when, in the server's seconds (time.time())
    done      bytes so far, or None where nothing is counted
    total     bytes in all, or None where it is not known
    stage     what it is doing inside that ("receiving", "sending", the
              build log's last line), or None
    page      the address of the page that started it, where the browser
              said (the Referer), so a list elsewhere can link back to it
    job       the token the starting page put on the request (?job=...),
              which is how that page knows this entry is its own and how
              a download started by a plain link knows when it is over

A FINISHED ENTRY STAYS KEEP SECONDS longer, under "finished" with `ok` and
`finished` added: a download packed in a second would otherwise come and go
between two polls, and the page that started it could not tell "not begun
yet" from "already over".  It is also what lets a page flash "done" for a
short job it would have missed.

Thread-safe: the server is a ThreadingTCPServer, and every request that
registers runs on a thread of its own.
"""
import itertools
import re
import threading
import time
import urllib.parse

KEEP = 8.0                  # seconds a finished entry is still reported
LOCK = threading.Lock()
_RUNNING = {}               # id -> entry
_FINISHED = []              # finished entries, oldest first
_NEXT = itertools.count(1)

# A token a page makes up (lib/activity.js: a few random letters).  Anything
# else is dropped rather than echoed back to every page that polls.
JOB_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def clean_job(value):
    """The ?job= token, or None when it is not one."""
    return value if isinstance(value, str) and JOB_RE.match(value) else None


# A path on THIS server, as a link can be made of it: one slash and then
# anything but a second slash or a backslash, and no space or control
# character anywhere.  "//evil.example/x" is a path to urlsplit and an
# address on another site to a browser (so is "/\evil.example/x", a
# backslash being a slash to one), and a tab or a newline is dropped by a
# browser before it reads the rest.
PAGE_RE = re.compile(r"^/(?![/\\])[^\x00-\x20\x7f\\]*$")


def clean_page(referer):
    """The page a request came from -> its path and query, or None.

    Only the path is kept: the list links back to the page on whichever
    address the person reading it used, and a Referer is the browser's word
    about a URL, not something to be printed whole on every other page.

    And only a path that stays on this server: every page that polls makes
    it the href of "open the page", and a Referer is whatever the request
    said -- a page on another site can send one of its choosing to a
    backup's address, and the hub would then offer a link off to that site
    for as long as the backup ran."""
    if not isinstance(referer, str) or not referer:
        return None
    try:
        parts = urllib.parse.urlsplit(referer)
    except ValueError:
        return None
    page = parts.path + ("?" + parts.query if parts.query else "")
    if len(page) > 400:
        page = parts.path[:400]
    return page if PAGE_RE.match(page) else None


def size(n):
    """A byte count as a person says it: 812 kB, 219 MB, 2.3 GB."""
    n = max(0, int(n or 0))
    if n < 1000:
        return "%d bytes" % n
    for unit, k in (("GB", 1e9), ("MB", 1e6), ("kB", 1e3)):
        if n >= k:
            v = n / k
            return ("%.1f %s" if v < 10 else "%.0f %s") % (v, unit)
    return "%d bytes" % n


def entry(id, kind, label, started, done=None, total=None, stage=None,
          page=None, job=None, finished=None, ok=None, unit=None):
    """One entry in the shape the list is drawn from: a finished one has
    `finished` (a time) and `ok`, a running one has neither.  `unit` is what
    `done` and `total` count where it is not bytes (`"items"`: drawings made, a
    share of work to do, drawn as "12 of 41" and a bar); an entry that counts
    bytes has no `unit` key at all."""
    out = {"id": id, "kind": kind, "label": label, "started": started,
           "done": done, "total": total, "stage": stage, "page": page, "job": job}
    if unit:
        out["unit"] = unit
    if finished is not None:
        out["finished"] = finished
        out["ok"] = bool(ok)
    return out


def begin(kind, label, page=None, job=None, total=None, stage=None, now=None):
    """Something long has started -> the name to report on it by."""
    tok = "r%d" % next(_NEXT)
    with LOCK:
        _RUNNING[tok] = entry(tok, kind, label, time.time() if now is None else now,
                              total=total, stage=stage, page=page, job=clean_job(job))
    return tok


def progress(tok, done=None, total=None, stage=None):
    """How far it has got: bytes done of total, and/or the stage it is in.
    A name that is not running (already ended, or None) is ignored, so the
    loops that report need not know whether anybody registered them."""
    if not tok:
        return
    with LOCK:
        e = _RUNNING.get(tok)
        if e is None:
            return
        if done is not None:
            e["done"] = done
        if total is not None:
            e["total"] = total
        if stage is not None:
            e["stage"] = stage or None


def relabel(tok, label):
    """What it is turns out to be clearer once it has started."""
    with LOCK:
        e = _RUNNING.get(tok)
        if e is not None and label:
            e["label"] = label


def end(tok, ok=True, now=None):
    """It is over: off the running list, onto the finished one for KEEP s."""
    if not tok:
        return
    t = time.time() if now is None else now
    with LOCK:
        e = _RUNNING.pop(tok, None)
        if e is None:
            return
        e["finished"] = t
        e["ok"] = bool(ok)
        _FINISHED.append(e)
        _prune(t)


def _prune(now):
    while _FINISHED and now - _FINISHED[0]["finished"] > KEEP:
        _FINISHED.pop(0)


def running():
    """How many requests are doing long work right now."""
    with LOCK:
        return len(_RUNNING)


def snapshot(extra=(), now=None):
    """Everything running and everything finished in the last KEEP seconds
    -> {"now", "running", "finished"}, each list oldest first.

    `extra` is entries made elsewhere (the job tables, by entry()); those
    with `finished` go with the finished ones and are dropped once older
    than KEEP, exactly like a request's."""
    t = time.time() if now is None else now
    with LOCK:
        _prune(t)
        run = [dict(e) for e in _RUNNING.values()]
        fin = [dict(e) for e in _FINISHED]
    for e in extra:
        if e.get("finished") is None:
            run.append(dict(e))
        elif t - e["finished"] <= KEEP:
            fin.append(dict(e))
    run.sort(key=lambda e: (e.get("started") or 0, e["id"]))
    fin.sort(key=lambda e: (e.get("finished") or 0, e["id"]))
    return {"now": t, "running": run, "finished": fin}


def clear():
    """Forget everything -- for a test."""
    with LOCK:
        _RUNNING.clear()
        del _FINISHED[:]
