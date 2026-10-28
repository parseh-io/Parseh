#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The LaTeX drawings of many documents, made in the background without opening one (a0.5.6).

    wanted = [(tex, theme, inline, "Title of the document"), ...]       what the documents show
    job = latexbatch.start(wanted, docs=12, page="/studio/", job="k3j9")   -> status(), the work begun
    latexbatch.status()                                                 -> what the page asks every second
    latexbatch.stop()                                                   no new drawing is begun
    latexbatch.activity_entries(activity.entry, activity.KEEP, now)     what every page's bar draws

WHY A JOB OF ITS OWN.  A document opened before its drawings are made has them made by its page, a few at a time,
each round answered with the page rendered again (static/latexwait.js, `/api/docs/<id>/drawings`): with forty
drawings that is ten rounds, each one drawing the whole page, under a bar that is that one page's.  A library of
documents wants them all made once, without being opened, with a bar that is true however much there is to do.  So the
server does it, in a thread, from the list of what the documents show: the TOTAL is known before the first compile
(the distinct drawings not made yet, a drawing two documents share counted once), `done` goes up by one each time a
drawing is over, and the bar every page and the hub already draw for long work (lib/activity.py, drawn by
lib/activity.js, merged by serve.py from `activity_entries`) is moved by those two numbers and by nothing else.

ONE JOB AT A TIME.  The drawings are compiled by lib/latexdraw.py's own pool, which a page's deferred drawings use
too: this keeps only as many of its own compiles in that pool as it has workers, so that a page opened meanwhile waits
for one compile and never for the rest of the batch.  A drawing that cannot be made is counted as over and kept as a
problem (its document, and what LaTeX said); an earlier failure is not made again, as `latexdraw.draw` does not.
Nothing here writes anywhere but where `latexdraw` keeps its drawings.

Standard library only, besides lib/latexdraw.py.
"""
import threading
import time

import latexdraw

LOCK = threading.Lock()
_JOB = {}               # the last job: running, or over
PROBLEMS_SHOWN = 8      # how many failures the status names (the count is always whole)
_ID = [0]


class Busy(Exception):
    """A batch is being made already."""


def workers():
    """How many of its compiles the job keeps in latexdraw's pool at a time: all the pool has."""
    return max(1, int(getattr(latexdraw._POOL, "_max_workers", 2) or 2))


def sort_out(wanted):
    """What the documents show -> (todo, made, failed): the distinct drawings not made yet, the number already made,
    and the ones known not to be makeable (with what was said).  Distinct by what LaTeX would compile, so a drawing
    two documents share, or one spelt with two names of the same theme, is one."""
    todo, failed, made, seen = [], [], 0, set()
    for tex, theme, inline, doc in wanted:
        peek = latexdraw.peek(tex, theme, inline=bool(inline))
        key = peek.get("key")
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        item = {"tex": tex, "theme": theme, "inline": bool(inline), "doc": doc or ""}
        if peek.get("ok") is None:
            todo.append(item)
        elif peek.get("ok"):
            made += 1
        else:
            failed.append(dict(item, said=str(peek.get("said") or "This drawing could not be made.")))
    return todo, made, failed


def start(wanted, docs=0, page=None, job=None):
    """Begin making what `wanted` needs -> status().  Raises Busy while another batch runs.  Where nothing is left
    to make, no thread is started and the status says so (`total` 0), over at once.  `job` is the token the page that
    asked put on its request (activity.clean_job): the entry the bar draws carries it, which is how that page knows the
    entry is its own and shows it once, from the first moment."""
    todo, made, failed = sort_out(wanted)
    with LOCK:
        if _JOB.get("running"):
            raise Busy("The LaTeX drawings of other documents are being made already.")
        _ID[0] += 1
        now = time.time()
        _JOB.clear()
        _JOB.update({"id": _ID[0], "running": bool(todo), "started": now, "finished": None if todo else now,
                     "total": len(todo), "done": 0, "made": 0, "docs": int(docs or 0), "already": made,
                     "known_failed": [{"doc": f["doc"], "said": f["said"]} for f in failed],
                     "problems": [], "failed": 0, "stop": False, "stopped": False, "last": "", "page": page, "job": job})
    if todo:
        threading.Thread(target=_run, args=(_ID[0], todo), name="latex-batch", daemon=True).start()
    return status()


def _record(job_id, item, result, error=None):
    with LOCK:
        if _JOB.get("id") != job_id:
            return
        _JOB["done"] += 1
        _JOB["last"] = item["doc"]
        if not error and result.get("ok"):
            _JOB["made"] += 1
        else:
            _JOB["failed"] += 1
            _JOB["problems"].append({"doc": item["doc"], "said": error or str(result.get("said") or "This drawing could not be made.")})


def _run(job_id, todo):
    from concurrent.futures import FIRST_COMPLETED, wait
    pending, queue = {}, iter(todo)
    window = workers()

    def feed():
        while len(pending) < window:
            with LOCK:
                if _JOB.get("id") != job_id or _JOB.get("stop"):
                    return
            item = next(queue, None)
            if item is None:
                return
            pending[latexdraw._POOL.submit(latexdraw.draw, item["tex"], item["theme"], inline=item["inline"])] = item

    try:
        feed()
        while pending:
            over, _ = wait(list(pending), return_when=FIRST_COMPLETED)
            for f in over:
                item = pending.pop(f)
                try:
                    _record(job_id, item, f.result())
                except Exception as e:                                   # noqa: BLE001 -- one drawing never ends the batch
                    _record(job_id, item, {}, error="%s: %s" % (type(e).__name__, e))
            feed()
    finally:
        with LOCK:
            if _JOB.get("id") == job_id:
                _JOB["running"] = False
                _JOB["finished"] = time.time()
                _JOB["stopped"] = bool(_JOB.get("stop")) and _JOB["done"] < _JOB["total"]


def stop():
    """No drawing is begun after this; the ones under way finish, and what was made stays made."""
    with LOCK:
        if _JOB.get("running"):
            _JOB["stop"] = True
    return status()


def status():
    """The job as a page reads it: {running, started, finished, total, done, made, failed, docs, already, stopped,
    last, problems, known_failed} -- or {running: False, total: 0, ...} when none has ever been asked for."""
    with LOCK:
        j = dict(_JOB)
        problems = [dict(p) for p in j.get("problems", [])]
        known = [dict(p) for p in j.get("known_failed", [])]
    if not j:
        return {"running": False, "started": None, "finished": None, "total": 0, "done": 0, "made": 0, "failed": 0,
                "docs": 0, "already": 0, "stopped": False, "last": "", "problems": [], "known_failed": 0}
    return {"running": bool(j["running"]), "started": j["started"], "finished": j["finished"], "total": j["total"],
            "done": j["done"], "made": j["made"], "failed": j["failed"], "docs": j["docs"], "already": j["already"],
            "stopped": bool(j["stopped"]), "last": j["last"], "problems": problems[:PROBLEMS_SHOWN],
            "known_failed": len(known)}


def clear():
    """Forget the job -- for a test."""
    with LOCK:
        _JOB.clear()


def activity_entries(entry, keep, now=None):
    """The job as the activity list has it (lib/activity.py entry()), so that every page's bar and the hub's panel
    know the drawings are being made, and how far.  Kind `compile`; the work is counted in drawings, not bytes
    (`unit` "items"), so the bar is a true share of what there is to do, whatever that is."""
    now = time.time() if now is None else now
    with LOCK:
        j = dict(_JOB)
    if not j or not j.get("total"):
        return []
    over = not j["running"]
    if over and now - (j.get("finished") or now) > keep:
        return []
    n = j.get("docs") or 0
    label = "Making the LaTeX drawings of %d document%s" % (n, "" if n == 1 else "s") if n else "Making LaTeX drawings"
    out = entry("latex:make@%.3f" % j["started"], "compile", label, j["started"],
                done=None if over else j["done"], total=None if over else j["total"],
                stage=None if over else (j.get("last") or None), page=j.get("page"), job=j.get("job"),
                finished=j["finished"] if over else None, ok=not j["failed"] and not j["stopped"], unit="items")
    return [out]
