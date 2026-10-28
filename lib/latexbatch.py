#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The LaTeX drawings of many documents, made in the background without opening one (a0.5.6; a helper of its own since a0.5.7).

    latexbatch.start(ids, env, page="/studio/", job="k3j9")   -> status(): the work begun, in a moment
    latexbatch.status()                                       -> what the page asks
    latexbatch.stop()                                         no new drawing is begun
    latexbatch.activity_entries(activity.entry, keep, now)    what every page's bar and the hub draw
    latexbatch.shutdown()                                     the helper goes with the server

A HELPER PROCESS, NOT A THREAD OF THE SERVER (a0.5.7, the owner: "just work in the background, without stalling the rest
of the software").  The first version read the documents, planned every drawing and compiled them in threads of the server
itself, and the server paid for it: the POST that began it did all the reading before it answered (seconds, on a library
of any size, with the page saying nothing), every threaded step took the GIL from the threads that answer a page, the
bookkeeping of each finished drawing rewrote one shared file under a lock the pages need, and the TeX it ran had the same
priority as the browser.  Now the server does one thing: it starts `python lib/latexbatch.py --worker <spec>` and answers
at once.  The helper

  * runs at the LOWEST PRIORITY of the computer (nice 19, or the idle class on Windows), and so do the TeX programs it
    starts, which inherit it: the browser, the server and everything else go first, always;
  * reads the documents itself (a first stage with its own count, "documents looked through"), then plans, then makes the
    drawings, at most as many side by side as the computer has cores to spare and memory for, and waits while the computer
    has little memory free rather than make it swap;
  * writes where it has got to in a small file (`status.json`, replaced whole each time), which is all the server reads
    -- one `stat` and, when it changed, a few hundred bytes -- to answer the page's question and the bar's;
  * does not touch the books of who owns which drawing (owners.json): the documents recorded their drawings when they
    were saved, and a second writer of that file could undo a save;
  * ends when the server does, killed or stopped (it asks for its parent every two seconds) and takes its TeX with it.

A page or the whole browser may go: the job belongs to the helper, and the next question finds it where it is.

ONE JOB AT A TIME.  Standard library only, besides lib/latexdraw.py (and the studio's store and parser in the helper).
"""
import json
import os
import signal
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
LOCK = threading.RLock()
_JOB = {}                   # the last job, as the server knows it: {id, dir, proc, started, page, job, asked}
PROBLEMS_SHOWN = 8          # how many failures the status names (the count is always whole)
KEEP_BELOW_MB = 900         # no new drawing is begun while this little memory is free (Linux and Windows)
MB_PER_WORKER = 900         # what a TeX run with the heavy packages may take, when counting how many fit
WRITE_EVERY = 0.2           # seconds between two writes of the status file while the work moves
WIN = os.name == "nt"
_ID = [0]


class Busy(Exception):
    """A batch is being made already."""


def batch_dir():
    import latexdraw
    return os.path.join(latexdraw.DRAWN, ".batch")


# ================================================================== the helper's side
def available_mb():
    """Memory free for a new program, in MB, or None where it cannot be told (macOS: left alone)."""
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/meminfo", encoding="ascii") as fh:
                for line in fh:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) // 1024
        elif WIN:
            import ctypes

            class Memory(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                            ("free", ctypes.c_ulonglong), ("ptotal", ctypes.c_ulonglong), ("pfree", ctypes.c_ulonglong),
                            ("vtotal", ctypes.c_ulonglong), ("vfree", ctypes.c_ulonglong), ("xfree", ctypes.c_ulonglong)]
            m = Memory()
            m.length = ctypes.sizeof(Memory)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return int(m.free // (1024 * 1024))
    except (OSError, ValueError, AttributeError):
        pass
    return None


def cores():
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except AttributeError:
        return max(1, os.cpu_count() or 1)


def workers(ncores=None, free_mb="unset"):
    """How many drawings are made side by side: half the cores, four at most, and as many as the free memory holds
    (MB_PER_WORKER each, after KEEP_BELOW_MB is kept) -- never fewer than one."""
    ncores = cores() if ncores is None else ncores
    free = available_mb() if free_mb == "unset" else free_mb
    by_cpu = max(1, min(4, ncores // 2))
    if free is None:
        return by_cpu
    return max(1, min(by_cpu, int((free - KEEP_BELOW_MB) // MB_PER_WORKER)))


def sort_out(wanted):
    """What the documents show -> (todo, made, failed): the distinct drawings not made yet, the number already made, and the
    ones known not to be makeable (with what was said).  Distinct by what LaTeX would compile, so a drawing two documents
    share, or one spelt with two names of the same theme, is one."""
    import latexdraw
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


class Writer(object):
    """The status file: the helper's whole state, written whole (replaced, never edited), at most WRITE_EVERY apart
    while it moves and always at a change of stage and at the end."""

    def __init__(self, path):
        self.path, self.state, self._at = path, {}, 0.0

    def set(self, force=False, **fields):
        self.state.update(fields)
        now = time.time()
        if not force and now - self._at < WRITE_EVERY:
            return
        self._at = now
        self.state["updated"] = now
        tmp = "%s.%d.tmp" % (self.path, os.getpid())
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.state, fh)
            os.replace(tmp, self.path)
        except OSError:
            pass


def work(spec, writer, draw=None, wanted_of=None, free_mb=available_mb, sleep=time.sleep):
    """The helper's whole job.  `spec` says which documents ({ids, ...}); `writer` is where it says how it goes.  The
    arguments after are the test's way in (draw, the way the documents are read, free memory, the clock); the helper
    itself uses the studio's own."""
    import latexdraw
    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
    stop_path = spec.get("stop")
    stopped = lambda: bool(stop_path) and os.path.exists(stop_path)           # noqa: E731
    draw = draw or latexdraw.draw
    ids = list(spec["ids"])
    writer.set(force=True, phase="scanning", docs_total=len(ids), docs_done=0, docs_found=0)
    # ---- 1. the documents, one at a time, yielding between two so that the helper never holds a core for long
    wanted, found = [], 0
    read = wanted_of or _wanted_of_studio(spec)
    for n, doc_id in enumerate(ids, 1):
        if stopped():
            break
        got = read(doc_id)
        if got is not None:
            found += 1
            wanted.extend(got)
        writer.set(docs_done=n, docs_found=found, wanted=len(wanted))
        sleep(0)
    if stopped():
        return writer.set(force=True, phase="over", stopped=True, finished=time.time(), total=0, done=0, made=0, failed=0,
                          active=0, problems=[], already=0, known_failed=0)
    # ---- 2. what is not made yet
    writer.set(force=True, phase="planning", docs_done=len(ids), docs_found=found, wanted=len(wanted))
    todo, already, bad = sort_out(wanted)
    writer.set(force=True, phase="making", total=len(todo), done=0, made=0, failed=0, active=0, already=already,
               known_failed=len(bad), problems=[], last="", waiting=False)
    # ---- 3. the drawings, a few side by side, each begun only when the computer has memory for it
    size = workers()
    problems, counts = [], {"done": 0, "made": 0, "failed": 0}
    pending, queue = {}, iter(todo)
    with ThreadPoolExecutor(max_workers=size) as pool:
        def feed():
            while len(pending) < size and not stopped():
                free = free_mb()
                if free is not None and free < KEEP_BELOW_MB and pending:
                    # little memory is free: no new run is begun beside the ones under way (the loop below asks again in
                    # half a second); with none under way one is begun all the same, or nothing would ever be made
                    writer.set(waiting=True, active=len(pending))
                    return
                item = next(queue, None)
                if item is None:
                    return
                pending[pool.submit(draw, item["tex"], item["theme"], inline=item["inline"])] = item
                writer.set(waiting=False, active=len(pending), last=item["doc"])

        feed()
        while pending:
            over, _ = wait(list(pending), timeout=0.5, return_when=FIRST_COMPLETED)
            for f in over:
                item = pending.pop(f)
                counts["done"] += 1
                try:
                    res = f.result()
                    ok, said = bool(res.get("ok")), str(res.get("said") or "This drawing could not be made.")
                except Exception as e:                                       # noqa: BLE001 -- one drawing never ends the batch
                    ok, said = False, "%s: %s" % (type(e).__name__, e)
                if ok:
                    counts["made"] += 1
                else:
                    counts["failed"] += 1
                    problems.append({"doc": item["doc"], "said": said})
                writer.set(done=counts["done"], made=counts["made"], failed=counts["failed"], active=len(pending),
                           last=item["doc"], problems=problems[:PROBLEMS_SHOWN])
            if spec.get("parent") and os.getppid() != spec["parent"]:
                latexdraw.stop_all()                                         # the server is gone: so is this, and its TeX
                break
            feed()
    writer.set(force=True, phase="over", active=0, done=counts["done"], made=counts["made"], failed=counts["failed"],
               stopped=bool(stopped() and counts["done"] < len(todo)), finished=time.time(),
               problems=problems[:PROBLEMS_SHOWN])


def _wanted_of_studio(spec):
    """The studio's own reading of a document: what drawings it shows -> [(tex, theme, inline, title)], or None when it is
    gone.  The paths the server was using are the ones the helper uses (a test points them somewhere else)."""
    for folder in ("markdown/app", "markdown/exlex", "youtube/lib", "lib"):
        path = os.path.join(ROOT, folder)
        if path not in sys.path:
            sys.path.insert(0, path)
    import htmlgen
    import latexdraw
    import latexthemes
    import store
    import texpackages
    env = spec.get("env") or {}
    if env.get("drawn"):
        latexdraw.DRAWN = env["drawn"]
    if env.get("themes"):
        latexthemes.STORE = env["themes"]
    if env.get("tex_tree"):
        texpackages.TREE = env["tex_tree"]
    if env.get("languages"):
        import languages
        languages.PERSONAL = env["languages"]
    if env.get("library"):
        store.use_library(env["library"])

    def read(doc_id):
        try:
            meta, markdown = store.get(doc_id)
        except (KeyError, OSError, ValueError):
            return None
        title = (meta.get("title") or doc_id) if isinstance(meta, dict) else doc_id
        return [(tex, theme, inline, title) for tex, theme, inline in htmlgen.latex_wanted(markdown)]
    return read


def _lower_priority():
    """The helper goes after everything else on the computer, and so does every TeX it starts."""
    try:
        if WIN:
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00000040)   # idle
        else:
            os.nice(19)
    except (OSError, AttributeError):
        pass


def _watch_parent(parent):
    """The helper ends when the server does -- killed or stopped, by any means -- and takes the TeX it started: asked every
    two seconds, from a thread of its own, so that no stage of the work has to remember to."""
    import latexdraw

    def watch():
        while True:
            time.sleep(2.0)
            if os.getppid() != parent:
                try:
                    latexdraw.stop_all()
                finally:
                    os._exit(1)
    if parent:
        threading.Thread(target=watch, name="watch-parent", daemon=True).start()


def worker_main(spec_path):
    _lower_priority()
    with open(spec_path, encoding="utf-8") as fh:
        spec = json.load(fh)
    for folder in ("lib",):
        if os.path.join(ROOT, folder) not in sys.path:
            sys.path.insert(0, os.path.join(ROOT, folder))
    import latexdraw
    latexdraw.BOOKKEEPING = False            # the documents recorded their drawings when they were saved: this writes no books
    if spec.get("env", {}).get("drawn"):
        latexdraw.DRAWN = spec["env"]["drawn"]
    writer = Writer(spec["status"])
    _watch_parent(spec.get("parent"))
    try:
        work(spec, writer)
    except Exception as e:                                                  # noqa: BLE001 -- said, not lost
        writer.set(force=True, phase="over", finished=time.time(), error="%s: %s" % (type(e).__name__, e))
        raise
    finally:
        # the helper's TeX programs end with it
        try:
            latexdraw.stop_all()
        except Exception:                                                   # noqa: BLE001
            pass


# ================================================================== the server's side
def _preexec():
    # NOT PR_SET_PDEATHSIG: Linux sends that signal when the THREAD that started the child ends, and the thread that started
    # this one is the short-lived one that answered a request -- the helper died at once, every time.  The helper watches its
    # parent itself (`_watch_parent`)
    try:
        os.nice(19)
    except OSError:
        pass


def _launch(spec_path):
    """Start the helper -> the process.  Its own session, so that stopping it stops the TeX it started."""
    kw = {"stdin": subprocess.DEVNULL, "cwd": ROOT}
    log = open(os.path.join(os.path.dirname(spec_path), "helper.log"), "ab")
    kw["stdout"] = kw["stderr"] = log
    if WIN:
        kw["creationflags"] = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
                               | 0x00000040)                                  # IDLE_PRIORITY_CLASS
    else:
        kw["start_new_session"] = True
        kw["preexec_fn"] = _preexec
    try:
        return subprocess.Popen([sys.executable, os.path.join(HERE, "latexbatch.py"), "--worker", spec_path], **kw)
    finally:
        log.close()


def start(ids, env, page=None, job=None, launch=None):
    """Begin the drawings of the documents `ids` -> status(), at once: the helper is started and nothing is read here.
    `env` says where the studio keeps things ({library, drawn, themes, tex_tree, languages}), so that the helper reads the
    same.  Raises Busy while another batch is being made."""
    with LOCK:
        if _alive():
            raise Busy("The LaTeX drawings of other documents are being made already.")
        _ID[0] += 1
        job_id = _ID[0]
        folder = os.path.join(batch_dir(), "%d-%d" % (os.getpid(), job_id))
        os.makedirs(folder, exist_ok=True)
        _tidy(folder)
        spec = {"ids": list(ids), "env": dict(env or {}), "status": os.path.join(folder, "status.json"),
                "stop": os.path.join(folder, "stop"), "parent": os.getpid()}
        spec_path = os.path.join(folder, "spec.json")
        with open(spec_path, "w", encoding="utf-8") as fh:
            json.dump(spec, fh)
        now = time.time()
        _JOB.clear()
        _JOB.update({"id": job_id, "dir": folder, "status": spec["status"], "stop": spec["stop"], "started": now, "page": page,
                     "job": job, "asked": len(ids), "seen": None, "cache": None})
        try:
            _JOB["proc"] = (launch or _launch)(spec_path)
        except OSError as e:
            _JOB["proc"] = None
            _JOB["error"] = "The helper that makes the drawings could not be started: %s" % e
    return status()


def _tidy(keep):
    """Folders of earlier jobs are of no use: the last is kept for the page still asking about it."""
    base = os.path.dirname(keep)
    try:
        for name in os.listdir(base):
            path = os.path.join(base, name)
            if path != keep and os.path.isdir(path) and time.time() - os.path.getmtime(path) > 3600:
                for inner in os.listdir(path):
                    try:
                        os.unlink(os.path.join(path, inner))
                    except OSError:
                        pass
                try:
                    os.rmdir(path)
                except OSError:
                    pass
    except OSError:
        pass


def _alive():
    proc = _JOB.get("proc")
    if proc is None:
        return False
    if proc.poll() is None:
        return True
    return False


def _read():
    """The helper's last words (cached by the file's time and size), or {}."""
    path = _JOB.get("status")
    try:
        st = os.stat(path)
    except (OSError, TypeError):
        return {}
    sig = (st.st_mtime_ns, st.st_size)
    if _JOB.get("seen") == sig and _JOB.get("cache") is not None:
        return _JOB["cache"]
    try:
        with open(path, encoding="utf-8") as fh:
            got = json.load(fh)
    except (OSError, ValueError):
        return _JOB.get("cache") or {}
    _JOB["seen"], _JOB["cache"] = sig, got
    return got


def status():
    """The job as a page reads it: {running, phase, started, finished, docs, docs_done, wanted, total, done, made, failed, active,
    already, known_failed, stopped, last, waiting, problems, error} -- or an idle one when none has ever been asked for.
    `phase` is starting, scanning, planning, making or over."""
    with LOCK:
        if not _JOB:
            return {"running": False, "phase": "idle", "started": None, "finished": None, "docs": 0, "docs_done": 0, "wanted": 0,
                    "total": 0, "done": 0, "made": 0, "failed": 0, "active": 0, "already": 0, "known_failed": 0,
                    "stopped": False, "last": "", "waiting": False, "problems": [], "error": None}
        got = dict(_read())
        proc = _JOB.get("proc")
        gone = proc is None or proc.poll() is not None
        over = got.get("phase") == "over"
        error = got.get("error") or _JOB.get("error")
        if gone and not over:
            # the helper ended without its last word: killed, or lost with the server's old session
            error = error or "The helper that makes the drawings stopped before it was done."
            over = True
        started = _JOB["started"]
        finished = got.get("finished") or (time.time() if over else None)
        if over and finished is not None:
            _JOB.setdefault("finished_at", finished)
            finished = _JOB["finished_at"]
        return {"running": not over, "phase": "over" if over else (got.get("phase") or "starting"), "started": started,
                "finished": finished if over else None, "docs": got.get("docs_found") or _JOB["asked"],
                "docs_total": got.get("docs_total", _JOB["asked"]),
                "docs_done": got.get("docs_done", 0), "wanted": got.get("wanted", 0), "total": got.get("total", 0),
                "done": got.get("done", 0), "made": got.get("made", 0), "failed": got.get("failed", 0),
                "active": got.get("active", 0), "already": got.get("already", 0),
                "known_failed": got.get("known_failed", 0), "stopped": bool(got.get("stopped")),
                "last": got.get("last", ""), "waiting": bool(got.get("waiting")),
                "problems": list(got.get("problems", []))[:PROBLEMS_SHOWN], "error": error}


def stop():
    """No new drawing is begun after this; the ones under way finish, and what was made stays made."""
    with LOCK:
        if _JOB and _alive():
            try:
                with open(_JOB["stop"], "w", encoding="ascii") as fh:
                    fh.write("stop")
            except OSError:
                pass
    return status()


def shutdown():
    """The server is stopping: the helper and the TeX it started go with it."""
    with LOCK:
        proc = _JOB.get("proc")
        if proc is not None and proc.poll() is None:
            try:
                if WIN:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=10)
                else:
                    os.killpg(proc.pid, signal.SIGKILL)
            except (OSError, subprocess.SubprocessError):
                pass


def clear():
    """Forget the job -- for a test."""
    with LOCK:
        shutdown()
        _JOB.clear()


def activity_entries(entry, keep, now=None):
    """The job as the activity list has it (lib/activity.py entry()), so that every page's bar and the hub's panel know the
    drawings are being made, and how far.  Kind `compile`; the work is counted in documents looked through and then in drawings
    made, not in bytes (`unit` "items"), so the bar is a true share of what there is to do, at every moment of it."""
    now = time.time() if now is None else now
    st = status()
    with LOCK:
        j = dict(_JOB)
    if not j:
        return []
    over = not st["running"]
    if over and (st["finished"] is None or now - st["finished"] > keep):
        return []
    if over and not st["total"] and not st["error"]:
        return []                       # nothing was to be made: the page says so itself, no "Done" for it
    asked = j.get("asked") or 0
    if st["phase"] in ("starting", "scanning", "planning"):
        label = "Looking through %d document%s for LaTeX drawings" % (asked, "" if asked == 1 else "s")
        done, total = (st["docs_done"], st["docs_total"] or asked) if st["phase"] != "planning" else (asked, asked)
        stage = "reading the documents" if st["phase"] != "planning" else "working out what is not made yet"
    else:
        n = st["docs"] or asked
        label = "Making the LaTeX drawings of %d document%s" % (n, "" if n == 1 else "s")
        done, total = st["done"], st["total"]
        stage = ("waiting for memory" if st["waiting"] else
                 ("%d being made%s" % (st["active"], " · " + st["last"] if st["last"] else "")) if st["active"] else (st["last"] or None))
    return [entry("latex:make@%.3f" % j["started"], "compile", label, j["started"],
                  done=None if over else done, total=None if over else total, stage=None if over else stage,
                  page=j.get("page"), job=j.get("job"), finished=st["finished"] if over else None,
                  ok=not st["failed"] and not st["stopped"] and not st["error"], unit="items")]


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        worker_main(sys.argv[2])
    else:
        sys.exit("usage: latexbatch.py --worker <spec.json>   (started by the studio; not a command)")
