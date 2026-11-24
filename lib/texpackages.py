# SPDX-License-Identifier: GPL-3.0-or-later
"""TeX packages got for the LaTeX drawings, from Settings (TO-DO §8.39, a0.4.0).

WHERE THEY GO (the owner, 2026-09-25).  Into a folder of Parseh's own,
texmf/, through tlmgr's user mode -- which works on a TeX Live installed by
its own installer and on one a Linux distribution packaged alike, where a
plain `tlmgr install` refuses ("running on Debian, switching to user mode!"),
and needs no administrator -- from the repository of the installed TeX
Live's own year (a TeX Live of an earlier year is served by the historic
archive: a repository newer than the installation is refused by tlmgr).
Every drawing is pointed at the folder (TEXMFAUXTREES, lib/latexdraw.py).
On Windows with MiKTeX, MiKTeX's own package manager, which puts a package
in MiKTeX's own tree.  Removing only ever touches what Parseh itself put
there -- never a package of the system's TeX, and so never what Parseh's
own PDFs need (install.sh --pdf's list).

texmf/ IS CONTENT, like dict/: an update keeps it, a release ships it empty,
a backup copies it (lib/release.py CONTENT, lib/updater.py PERSONAL).  What
is in it is listed in texmf/parseh-packages.json, with each package's size
and licence as TeX Live gave them: the rows of Settings -> LaTeX drawings
and /licences/ read that list, and so does a drawing's key (state()), so a
package installed or removed draws afresh.

Getting a package is a job like a dictionary's download (lib/lookuppage.py):
what it costs said before it starts, its progress, Stop.
"""
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

LIB = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(LIB)
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import latexthemes                                           # noqa: E402

TREE = os.path.join(ROOT, "texmf")
MANIFEST_NAME = "parseh-packages.json"
# the shape of the list, as a number (lib/version.py FORMATS)
MANIFEST_FORMAT = 1
MAIN_REPO = "https://mirror.ctan.org/systems/texlive/tlnet"
HISTORIC_REPO = "https://ftp.math.utah.edu/pub/tex/historic/systems/texlive/%d/tlnet-final"
WIN = os.name == "nt"

# JOBS and the process table are observed by the Settings page while the
# worker changes them.  This is an RLock because a few of the small helpers
# below intentionally compose a snapshot from both tables.
_LOCK = threading.RLock()
# A TeX Live user tree has one tlpdb.  Concurrent tlmgr processes can both
# exit successfully while losing each other's database updates, so *every*
# change to that tree (install or remove) goes through this lock.
_MUTATION_LOCK = threading.RLock()
JOBS = {}           # package name -> the job (queued, running, or last result)
_PROCS = {}         # package name -> the running process
_QUEUE = []         # package names, in the order a person asked for them
_WORKER_RUNNING = False


def tree():
    return TREE


def manifest_path():
    return os.path.join(TREE, MANIFEST_NAME)


def manifest():
    """{"format", "packages": {name: {"at", "licence", "size", "via"}}}"""
    with _LOCK:
        try:
            with open(manifest_path(), encoding="utf-8") as fh:
                doc = json.load(fh)
            if isinstance(doc, dict) and isinstance(doc.get("packages"), dict):
                return doc
        except (OSError, ValueError):
            pass
        return {"format": MANIFEST_FORMAT, "packages": {}}


def _save_manifest(doc):
    # Most callers hold this lock over their preceding read too.  Taking it
    # here as well keeps standalone manifest repairs from colliding with an
    # installation.  It is re-entrant for the normal install/remove path.
    with _MUTATION_LOCK:
        with _LOCK:
            doc = dict(doc, format=MANIFEST_FORMAT)
            os.makedirs(TREE, exist_ok=True)
            tmp = manifest_path() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False, indent=1, sort_keys=True)
                fh.write("\n")
            os.replace(tmp, manifest_path())


def state():
    """A drawing's key's share of the packages: what Parseh has installed,
    and when."""
    pk = manifest()["packages"]
    if not pk:
        return ""
    blob = json.dumps({k: v.get("at") for k, v in sorted(pk.items())})
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- the TeX
def distribution():
    """Which TeX this computer has -> {"kind": "texlive"|"miktex"|None,
    "year", "tool", "said"}."""
    for c in latexthemes.COMPILERS + ("tex",):
        path = shutil.which(c)
        if not path:
            continue
        try:
            out = subprocess.run([path, "--version"], capture_output=True, text=True,
                                 timeout=20, stdin=subprocess.DEVNULL).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        if "miktex" in out.lower():
            tool = shutil.which("miktex") or shutil.which("mpm")
            return {"kind": "miktex", "year": None, "tool": tool,
                    "said": out.splitlines()[0].strip() if out else "MiKTeX"}
        m = re.search(r"TeX Live (\d{4})", out)
        tlmgr = shutil.which("tlmgr")
        return {"kind": "texlive", "year": int(m.group(1)) if m else None, "tool": tlmgr,
                "said": ("TeX Live %s" % m.group(1)) if m else (out.splitlines() or [c])[0].strip()}
    return {"kind": None, "year": None, "tool": None, "said": "no TeX on this computer"}


_KIND = []


def local_rule():
    """Whether a theme's packages beyond the base must be Parseh's own
    (latexthemes.own_packages): on TeX Live, whose user tree Parseh fills.
    MiKTeX puts what it gets in its own tree, so there a package is simply
    there or not.  The TeX a computer has is asked once."""
    if not _KIND:
        _KIND.append(distribution()["kind"])
    return _KIND[0] == "texlive"


def _base_names():
    return ({n for p in latexthemes.BASE for n in latexthemes.PACKAGES[p]["tl"]} |
            {n for tl, _file, _lic in latexthemes.ALWAYS.values() for n in tl})


def own(name):
    """Is a TeX Live package one of a theme's own (not the base's), so that
    only Parseh's copy of it counts?"""
    return name in ({n for p in latexthemes.ORDER if p not in latexthemes.BASE
                     for n in latexthemes.PACKAGES[p]["tl"]} - _base_names())


def missing_for(theme, doc=None, found=None):
    """What a theme lacks -> [(id, [TeX Live names])]: a package of its own
    that Parseh has not got (local_rule), or a file of the base the
    computer's TeX cannot find.  `found` is installed_many's answer, when the
    caller has one."""
    doc = manifest() if doc is None else doc
    got = doc.get("packages", {})
    mine = set(latexthemes.own_packages(theme)) if local_rule() else set()
    needs = latexthemes.files_needed(theme)
    if found is None:
        found = installed_many([f for p, f, _tl, _lic in needs if p not in mine])
    out = []
    for p, file, tl, _lic in needs:
        if p in mine:
            want = [n for n in tl if n not in got]
        elif found.get(file) is False:
            want = [n for n in tl if n not in got] or list(tl)
        else:
            want = []
        if want:
            out.append((p, want))
    return out


def env():
    e = dict(os.environ)
    if os.path.isdir(TREE):
        e["TEXMFAUXTREES"] = TREE.replace("\\", "/") + ","
    return e


def installed(file):
    """Is a TeX file reachable, in the system's TeX or in texmf/?"""
    k = shutil.which("kpsewhich")
    if not k:
        return None
    try:
        r = subprocess.run([k, file], capture_output=True, text=True, timeout=20, env=env(),
                           stdin=subprocess.DEVNULL)
        return bool(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return None


def installed_many(files):
    """Which of these TeX files are reachable -> {file: True | False | None},
    from ONE kpsewhich (None: there is none to ask)."""
    files = list(dict.fromkeys(f for f in files if f))
    k = shutil.which("kpsewhich")
    if not k or not files:
        return {f: None for f in files}
    try:
        r = subprocess.run([k] + files, capture_output=True, text=True, timeout=30, env=env(),
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return {f: None for f in files}
    found = {os.path.basename(line.strip().replace("\\", "/")) for line in r.stdout.splitlines()
             if line.strip()}
    return {f: f in found for f in files}


def _representative_file(name):
    """A file that proves a single TeX Live package is already usable.

    The catalogue sometimes names a bundle of TeX Live packages for one
    feature (for example ``mhchem`` and ``chemgreek``).  One feature file
    cannot prove that every package in such a bundle is present, so this is
    deliberately conservative: only a catalogue entry owned by *one* TL
    package is evidence that that package need not be downloaded again.
    """
    for row in latexthemes.PACKAGES.values():
        if tuple(row["tl"]) == (name,):
            return row["file"]
    for _key, (tl, file, _licence) in latexthemes.ALWAYS.items():
        if tuple(tl) == (name,):
            return file
    return None


def availability(name, doc=None):
    """Where a package is available to the current TeX.

    ``parseh`` is a package recorded in Parseh's private tree; ``available``
    is a known package whose representative file TeX can already find;
    ``missing`` is a known absent representative; and ``unknown`` is used
    when a package has no safe representative or TeX cannot be asked.  The
    latter is intentionally not treated as missing: a typed package name
    should still be possible to quote from its repository.
    """
    doc = manifest() if doc is None else doc
    if name in doc.get("packages", {}):
        return {"here": "parseh", "file": None}
    if own(name) and local_rule():
        return {"here": "missing", "file": _representative_file(name)}
    file = _representative_file(name)
    if not file:
        return {"here": "unknown", "file": None}
    got = installed(file)
    if got is True:
        return {"here": "available", "file": file}
    if got is False:
        return {"here": "missing", "file": file}
    return {"here": "unknown", "file": file}


def licence_of(tl_name):
    """The TeX Catalogue's licence of a TeX Live package, as the checkboxes know it."""
    for row in latexthemes.PACKAGES.values():
        if tl_name in row["tl"]:
            return row["licence"]
    for tl, _f, lic in latexthemes.ALWAYS.values():
        if tl_name in tl:
            return lic
    return ""


def _tlmgr(args, repo=None, tree=None):
    d = distribution()
    tool = d.get("tool")
    if not tool:
        return None
    cmd = [tool, "--usermode", "--usertree", tree or TREE]
    if repo:
        cmd += ["--repository", repo]
    return cmd + list(args)


# `tlmgr info` refuses a tree with no tlpdb ("Cannot determine type of tlpdb"), which texmf/ is
# until a first package is got, and would race an install writing it: quotes go through a scratch tree.
_QUERY = {"dir": None}
_QUERY_LOCK = threading.Lock()


def _query_tree():
    with _QUERY_LOCK:
        if _QUERY["dir"] is None:
            tmp = tempfile.TemporaryDirectory(prefix="parseh-tlquote-")
            _QUERY["dir"] = tmp
            init = _tlmgr(["init-usertree"], tree=tmp.name)
            if init:
                try:
                    subprocess.run(init, capture_output=True, text=True, timeout=120,
                                   stdin=subprocess.DEVNULL)
                except (OSError, subprocess.SubprocessError):
                    pass
        return _QUERY["dir"].name


def _repositories():
    d = distribution()
    out = [MAIN_REPO]
    if d.get("year"):
        out.append(HISTORIC_REPO % d["year"])
    return out


def plan(names):
    """What getting these TeX Live packages costs, before anything starts ->
    {"packages": [{"name", "size", "licence", "here", "repository",
    "can_get", "why"}], "can", "why"}.

    ``here`` tells the page whether a known package is already usable by this
    TeX; ``repository`` tells it whether tlmgr explicitly says the requested
    package exists upstream.  They are separate facts: a system package may
    be available even when the selected historical repository no longer has
    it.
    """
    names = list(dict.fromkeys(n for n in names if isinstance(n, str)))
    d = distribution()
    doc = manifest()
    rows = []
    for n in names:
        here = availability(n, doc)
        rows.append({"name": n, "size": None, "licence": licence_of(n),
                     "here": here["here"], "repository": "unknown",
                     "can_get": False, "why": "", "file": here["file"]})
    if d["kind"] is None:
        for row in rows:
            row["why"] = "This computer has no TeX."
        return {"packages": rows, "can": False,
                "why": "This computer has no TeX. Install TeX Live or MiKTeX first: the "
                       "guide's Installing page says how."}
    if d["kind"] == "miktex" and not d.get("tool"):
        for row in rows:
            row["why"] = "MiKTeX's package manager was not found."
        return {"packages": rows, "can": False, "why": "MiKTeX's package manager was not found."}
    if d["kind"] == "texlive" and not d.get("tool"):
        for row in rows:
            row["why"] = "This TeX Live has no tlmgr."
        return {"packages": rows, "can": False,
                "why": "This TeX Live has no tlmgr, so Parseh cannot add packages to it."}
    if d["kind"] == "texlive":
        reached = False
        for repo in _repositories():
            cmd = _tlmgr(["info", "--json"] + list(names), repo, _query_tree())
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                                   stdin=subprocess.DEVNULL)
                info = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
            except (OSError, subprocess.SubprocessError, ValueError):
                info = None
            if not info:
                continue
            reached = True
            by = {x.get("name"): x for x in info if isinstance(x, dict)}
            for row in rows:
                x = by.get(row["name"]) or {}
                if x.get("available") is False:
                    row["repository"] = "unavailable"
                elif x:
                    # Older tlmgr JSON did not have ``available``.  A record
                    # for the requested name is still positive evidence.
                    row["repository"] = "available"
                try:
                    row["size"] = int(x.get("containersize") or 0) or None
                except (TypeError, ValueError):
                    row["size"] = None
                lic = ((x.get("cataloguedata") or {}).get("license")) or row["licence"]
                row["licence"] = lic
            break
        if not reached:
            for row in rows:
                if row["here"] not in ("available", "parseh"):
                    row["repository"] = "unreachable"
    for row in rows:
        if row["here"] == "parseh":
            row["why"] = "Already got through Parseh."
        elif row["here"] == "available":
            row["why"] = "Already available to this TeX."
        elif row["repository"] == "unavailable":
            row["why"] = "This TeX Live repository does not offer it."
        elif row["repository"] == "unreachable":
            row["why"] = "The TeX Live repository could not be reached."
        else:
            row["can_get"] = True
    return {"packages": rows, "can": True, "why": "", "tex": d["said"]}


# WHY A RUN FAILED.  tlmgr's last line is always "An error has occurred. See
# above messages. Exiting.", which said nothing to the person reading it here
# (nothing is above it on the page): the line before that names the cause --
# a package its repository does not have, a repository of another year, a
# host it could not reach -- and that is the one kept.
_GENERIC = re.compile(r"see above messages|an error has occurred", re.I)
_WHY = re.compile(r"not present in|older than remote|cannot|can't|could not|couldn't|unable|"
                  r"failed|refused|no route|resolve|timed out|not found|no such", re.I)


def _progress(job, line):
    # Status polling may take a snapshot while tlmgr writes a line.  Keep the
    # related fields together so the page never sees, for example, a new
    # numerator with an old total.
    with _LOCK:
        m = re.search(r"\[(\d+)/(\d+)", line)
        if m:
            job["done"], job["total"] = int(m.group(1)), int(m.group(2))
        s = line.strip()
        if s:
            job["say"] = s[:200]
            if _WHY.search(s) and not _GENERIC.search(s):
                job["why"] = s[:200]


def _stopped(job):
    with _LOCK:
        return bool(job.get("stopped"))


def _stop_queued(job):
    """Finish a queued job without ever starting a package manager."""
    with _LOCK:
        job.update({"queued": False, "running": False, "stopped": True,
                    "state": "stopped", "error": "Stopped.",
                    "finished": time.time()})


def _run(job, name):
    """Run one mutation of the TeX package database.

    This is deliberately locked here rather than only in the queue worker:
    direct callers (including repair code and focused tests) are safe too,
    and removal uses the same lock.
    """
    installed_ok = False
    try:
        with _MUTATION_LOCK:
            if _stopped(job):
                return
            d = distribution()
            if d["kind"] == "texlive":
                os.makedirs(TREE, exist_ok=True)
                if not os.path.exists(os.path.join(TREE, "tlpkg", "texlive.tlpdb")):
                    init = _tlmgr(["init-usertree"])
                    subprocess.run(init, capture_output=True, text=True, timeout=120,
                                   stdin=subprocess.DEVNULL)
                ok = False
                for repo in _repositories():
                    if _stopped(job):
                        break
                    cmd = _tlmgr(["install", name], repo)
                    with _LOCK:
                        job["why"] = None
                    ok = _stream(job, name, cmd)
                    if ok or _stopped(job):
                        break
                    with _LOCK:
                        job["tried"] = job.get("tried", []) + [repo]
                via = "tlmgr"
            elif d["kind"] == "miktex":
                tool = d["tool"]
                if os.path.basename(tool).lower().startswith("miktex"):
                    cmd = [tool, "packages", "install", name]
                else:
                    cmd = [tool, "--install=%s" % name]
                ok = _stream(job, name, cmd)
                via = "miktex"
            else:
                ok, via = False, ""
                with _LOCK:
                    job["error"] = "This computer has no TeX."
            if _stopped(job):
                with _LOCK:
                    job["error"] = "Stopped."
            elif ok:
                # _MUTATION_LOCK protects this read-modify-write from both
                # the next queued install and a concurrent Remove action.
                doc = manifest()
                doc["packages"][name] = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "via": via,
                                         "licence": licence_of(name),
                                         "size": _tree_size() if via == "tlmgr" else None}
                _save_manifest(doc)
                installed_ok = True
                import latexdraw
                latexdraw.forget_failures()
            else:
                with _LOCK:
                    if not job.get("error"):
                        job["error"] = ("%s could not be installed: %s"
                                        % (name, job.get("why") or job.get("say") or "it failed"))
    except Exception as e:                                   # noqa: BLE001
        with _LOCK:
            job["error"] = "%s could not be installed: %s" % (name, e)
    finally:
        with _LOCK:
            job["queued"] = False
            job["running"] = False
            if job.get("stopped"):
                job["state"] = "stopped"
                job["error"] = "Stopped."
            elif installed_ok:
                job["state"] = "installed"
                job["error"] = None
                job["say"] = "installed"
            else:
                job["state"] = "failed"
            job["finished"] = time.time()


def _stream(job, name, cmd):
    kw = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL,
          "text": True, "env": env()}
    if WIN:
        kw["creationflags"] = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                               | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        kw["start_new_session"] = True
    proc = subprocess.Popen(cmd, **kw)
    with _LOCK:
        _PROCS[name] = proc
        stopped = job.get("stopped")
    # Stop can arrive in the small gap between Popen and publishing the
    # process in _PROCS.  Do not let that gap turn Stop into a no-op.
    if stopped:
        _terminate(proc)
    try:
        for line in proc.stdout:
            _progress(job, line)
        proc.wait()
    finally:
        with _LOCK:
            _PROCS.pop(name, None)
    return proc.returncode == 0


def _tree_size():
    total = 0
    for here, _d, files in os.walk(TREE):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(here, f))
            except OSError:
                pass
    return total


def _queue_worker():
    """Run requested packages in order, never more than one tlmgr at once."""
    global _WORKER_RUNNING
    while True:
        with _LOCK:
            job = None
            while _QUEUE:
                name = _QUEUE.pop(0)
                candidate = JOBS.get(name)
                if not candidate or candidate.get("state") != "queued":
                    continue
                if candidate.get("stopped"):
                    _stop_queued(candidate)
                    continue
                candidate.update({"queued": False, "running": True, "state": "running",
                                  "started": time.time(), "say": "starting"})
                job = candidate
                break
            if job is None:
                _WORKER_RUNNING = False
                return
        _run(job, name)


def _finished_job(name, state, say):
    return {"name": name, "state": state, "queued": False, "running": False,
            "done": 0, "total": 0, "say": say, "error": None,
            "started": None, "finished": time.time()}


def start(name):
    """Queue one TeX package, in the background -> its truthful job state."""
    global _WORKER_RUNNING
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,60}$", name or ""):
        raise ValueError("%r is not a package's name" % name)
    here = availability(name)
    with _LOCK:
        job = JOBS.get(name)
        if job and job.get("state") in ("queued", "running"):
            return job
        if here["here"] == "parseh":
            job = JOBS[name] = _finished_job(name, "installed", "already got through Parseh")
            return job
        if here["here"] == "available":
            job = JOBS[name] = _finished_job(name, "available", "already available to this TeX")
            return job
        job = JOBS[name] = {"name": name, "state": "queued", "queued": True,
                            "running": False, "done": 0, "total": 0,
                            "say": "waiting", "error": None, "requested": time.time(),
                            "started": None}
        _QUEUE.append(name)
        if not _WORKER_RUNNING:
            _WORKER_RUNNING = True
            threading.Thread(target=_queue_worker, daemon=True).start()
    return job


def stop(name=None):
    with _LOCK:
        names = ([name] if name else
                 list(dict.fromkeys(list(_PROCS) + list(_QUEUE) +
                                    [n for n, j in JOBS.items()
                                     if j.get("state") in ("queued", "running")])))
        for n in names:
            job = JOBS.get(n)
            if not job:
                continue
            if job.get("state") == "queued":
                _stop_queued(job)
            elif job.get("state") == "running":
                # Keep the state truthful until the process actually exits.
                job["stopped"] = True
                job["stopping"] = True
                job["say"] = "stopping"
        _QUEUE[:] = [n for n in _QUEUE if not JOBS.get(n, {}).get("stopped")]
        procs = [(n, _PROCS.get(n)) for n in names]
    for n, p in procs:
        if p is None:
            continue
        _terminate(p)


def _terminate(proc):
    """Ask a package-manager process and all of its children to stop."""
    try:
        if WIN:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            os.killpg(proc.pid, signal.SIGTERM)
    except OSError:
        pass


def _in_tlmgr_tree(name):
    """Whether a package is really still registered in Parseh's tlpdb.

    This is deliberately a local check rather than another tlmgr command:
    it works after tlmgr has returned its misleading non-zero status and it
    cannot accidentally consult the system TeX tree.  ``None`` means the
    database could not be read, not that the package is absent.
    """
    path = os.path.join(TREE, "tlpkg", "texlive.tlpdb")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return None
    return bool(re.search(r"(?m)^name\s+%s\s*$" % re.escape(name), text))


def remove(name):
    """Remove a package Parseh installed -- and only one it did."""
    with _MUTATION_LOCK:
        doc = manifest()
        got = doc["packages"].get(name)
        if not got:
            raise ValueError("%s was not installed by Parseh, so Parseh does not remove it" % name)
        if got.get("via") == "tlmgr":
            cmd = _tlmgr(["remove", name])
        else:
            d = distribution()
            tool = d.get("tool") or ""
            cmd = ([tool, "packages", "remove", name] if os.path.basename(tool).lower().startswith("miktex")
                   else [tool, "--uninstall=%s" % name])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL,
                           env=env())
        still_there = _in_tlmgr_tree(name) if got.get("via") == "tlmgr" else None
        # TeX Live's user mode sometimes says exit 1 after it has removed the
        # package (when a dependency belongs to the system tree).  The private
        # tlpdb is the authoritative answer.  MiKTeX has no corresponding
        # Parseh-owned database, so retain the old exit-status fallback there.
        removed = still_there is False or (still_there is None and r.returncode == 0)
        if not removed:
            detail = (r.stdout or r.stderr).strip()[-300:]
            if still_there is True:
                detail = "it is still registered in Parseh's TeX Live tree"
            raise ValueError("%s could not be removed: %s" % (name, detail or "it failed"))
        doc["packages"].pop(name, None)
        _save_manifest(doc)
    with _LOCK:
        JOBS.pop(name, None)        # else the page went on saying "installed" beside it
    import latexdraw
    latexdraw.forget_failures()


def status():
    doc = manifest()
    with _LOCK:
        jobs = {k: {x: v.get(x) for x in ("name", "state", "queued", "running", "stopping",
                                         "done", "total", "say", "error", "requested",
                                         "started", "finished")}
                for k, v in JOBS.items()}
    # A single state map saves clients from guessing whether a missing job is
    # installed, while retaining the old ``installed`` manifest for callers
    # that need licence, size and provenance.
    states = {name: "installed" for name in doc["packages"]}
    states.update({name: job.get("state") for name, job in jobs.items()})
    # The page also needs to suppress a stale "not installed" shortcut
    # before its next full state reload.  It asks this map only whether a
    # package is already reachable; provenance remains in ``states``.
    available = {name: True for name in doc["packages"]}
    available.update({name: True for name, job in jobs.items()
                      if job.get("state") == "available"})
    return {"jobs": jobs, "installed": doc["packages"], "states": states,
            "available": available}
