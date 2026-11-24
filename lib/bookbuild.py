#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""A book built from a page -- its PDF and its reader -- as a job the page polls.

    bookbuild.start(book_dir, "pdf")    the PDF and the reader, as ./build.sh <folder>/<slug>
    bookbuild.start(book_dir, "html")   the reader alone, as ./build.sh --html <folder>/<slug>
    bookbuild.start(book_dir, "draft", chapters=["ch1", "ch1b"])
                                        the PDF of those chapters alone, as ./build.sh <folder>/<slug> --draft ch1 ch1b
    bookbuild.status(book_dir)          {"state", "what", "log", "started", "finished", "ok", "code"}

    python3 lib/bookbuild.py <book dir> [--html]    the same build, in Python, where there is no sh

WHY A JOB.  A book's PDF is lualatex over every pass of every chapter: a few
seconds for a two-paragraph example, three quarters of an hour for the Persian
edition of 2,500 pages.  No request can wait for that, so the card's build
button and the reader's start a job and poll it: `state` is "running",
"done" or "failed" ("idle" for a book nothing has built since the server
started), and `log` is the build's own output, its last lines kept.  One
build a book at a time; asking again while one runs answers with that one.

WHAT RUNS.  ./build.sh wherever there is a POSIX shell: its cache, its log
checks and its retry are the build, and nothing here copies them.  Windows
has no sh, so there the same steps run in Python (build() below): the
narration's timing comments restored, lualatex twice where the machine has
it, the reader, the library page -- without build.sh's cache, which only
ever saves time.  Either way the build runs in the ilya-frank environment
(lib/runtime.py), whose python3 has the packages the reader is built with.
"""
import os
import re
import shutil
import subprocess
import sys
import threading
import time

LIB = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.realpath(os.path.join(LIB, ".."))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import runtime  # noqa: E402

WAYS = {"pdf": "the PDF and the reader", "html": "the reader",
        # a book being made by an agent, looked at while it grows (lib/making.py):
        # only the chapters so far, under a jobname of their own
        "draft": "the PDF of these chapters"}
KEEP = 400                      # lines of a build's output a job keeps
JOBS = {}                       # the book's directory -> its job
LOCK = threading.Lock()


def book_arg(book_dir):
    """The book as build.sh names it: <folder>/<slug>, or <slug> for a book
    from before languages, lying directly under books/."""
    return os.path.relpath(os.path.realpath(book_dir),
                           os.path.realpath(os.path.join(ROOT, "books"))).replace(os.sep, "/")


def available(what):
    """Whether this way can be run on this machine -> (True, "") or (False,
    why, in words).  Only the draft can be missing: it is build.sh's own
    --draft, and build.sh is a shell script.  Where there is no sh -- Windows
    above all -- the reader can still be built (the Python build below does it),
    the PDF of a few chapters cannot, and the page says so plainly."""
    if what == "draft" and (runtime.WIN or not shutil.which("sh")):
        return False, ("the PDF of these chapters is not available on this computer, which has no shell "
                       "to make it. The reader is available: look at it now")
    return True, ""


def command(book_dir, what, chapters=()):
    """The command that builds this book this way on this machine."""
    if what == "draft":
        return ["sh", os.path.join(ROOT, "build.sh"), book_arg(book_dir), "--draft"] + list(chapters)
    if not runtime.WIN and shutil.which("sh"):
        return (["sh", os.path.join(ROOT, "build.sh")] + (["--html"] if what == "html" else [])
                + [book_arg(book_dir)])
    python = runtime.find_env()[1] or sys.executable
    return [python, os.path.realpath(__file__), os.path.realpath(book_dir)] + (
        ["--html"] if what == "html" else [])


def _view(job):
    return {"state": job["state"], "what": job["what"], "log": list(job["log"]),
            "started": job["started"], "finished": job["finished"],
            "ok": job["ok"], "code": job["code"]}


def status(book_dir):
    with LOCK:
        job = JOBS.get(os.path.realpath(book_dir))
        return _view(job) if job else {"state": "idle", "what": None, "log": [], "ok": None}


def jobs():
    """Every build started since the server did -> [(book dir, its view)].

    For the list of what the server is busy with (serve.py's /__activity),
    which shows a running build on every page and not only on the one that
    polls its status."""
    with LOCK:
        return [(key, _view(job)) for key, job in JOBS.items()]


# WHAT THE PAGE IS TOLD (TO-DO §5.8).  build.sh is a terminal tool as well,
# and a few of its lines speak to somebody at a terminal: the closing "Serve
# everything with: ./serve.sh", a missing log called NO LOG, and a hyphenation
# warning whose fix is a command.  A build started from a page reaches the
# page through this job's log (the card's toast, the reader's PDF line, the
# making panel's finish step), where nobody has a terminal: so those lines are
# said here in plain words -- what happened, and what to do from the pages --
# and the terminal-only ones are left out.  Every other line is kept as it is.
NO_LOG = re.compile(r"^\s*NO LOG at .* lualatex did not run")
NO_HYPHEN = re.compile(r"^\s*NO HYPHENATION PATTERNS for (\S+)")
TERMINAL_ONLY = re.compile(r"^\s*(Serve everything with:|points\.\s+The PDF is sound and the line breaks are wrong"
                           r"|\./install\.sh --pdf and rebuild with --force)")
NO_LATEX_SAID = ("   the PDF was not made -- LaTeX could not run: LuaLaTeX is not on this computer, or it was "
                 "stopped before it began. The reader is built all the same. Parseh cannot install LaTeX from "
                 "its pages yet.")
HYPHEN_SAID = ("   no hyphenation patterns for %s on this computer: the PDF is sound, but its lines are broken "
               "where an English word would break. Parseh cannot install the patterns from its pages yet.")


def _language_of_babel(name):
    """The registry's name for a babel language ('ngerman' -> German), or
    babel's own where no language of the registry is called that."""
    import languages
    for code in languages.CODES:
        L = languages.get(code)
        if (L.tex or {}).get("babel") == name:
            return L.name
    return name


def plain(line):
    """A line of build.sh's output as a page should read it: in plain words,
    or None for a line that only means something at a terminal."""
    if TERMINAL_ONLY.match(line):
        return None
    if NO_LOG.match(line):
        return NO_LATEX_SAID
    m = NO_HYPHEN.match(line)
    if m:
        return HYPHEN_SAID % _language_of_babel(m.group(1))
    return line


def _say(job, line):
    line = line.rstrip()
    if not line.strip():
        return
    line = plain(line)
    if line is None:
        return
    with LOCK:
        job["log"].append(line)
        del job["log"][:-KEEP]


def _record(book_dir, what):
    """A build that ended well records the source it was made from, so the
    reader and the PDF may travel with it (lib/syncbuilds.py, a0.7.0)."""
    if what not in ("pdf", "html") or not book_dir:
        return
    try:
        import syncbuilds
        syncbuilds.record(book_dir, ["reader", "pdf"] if what == "pdf" else ["reader"])
    except Exception:                                   # noqa: BLE001 -- never the build
        pass


def _run(job, cmd, runner, book_dir=None):
    try:
        if runner is not None:
            code = runner(cmd, lambda line: _say(job, line))
        else:
            env = runtime.environ_for(runtime.find_env()[0])
            env["PYTHONUNBUFFERED"] = "1"
            p = subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace", bufsize=1)
            for line in p.stdout:
                _say(job, line)
            code = p.wait()
    except Exception as e:                      # sh missing, the environment gone
        _say(job, "the build could not run: %s" % e)
        code = 127
    if code == 0:
        _record(book_dir, job.get("what"))
    with LOCK:
        job.update(code=code, ok=code == 0, state="done" if code == 0 else "failed",
                   finished=time.time())


def start(book_dir, what="pdf", runner=None, chapters=()):
    """Start building this book -> (job, True), or (the build already
    running, False).  `runner(cmd, say) -> exit status` stands in for the
    subprocess, for a test.  A refusal to start is a ValueError with the
    sentence to show; only the draft can be refused, for `chapters` it has not
    got or a machine that cannot make it."""
    if what not in WAYS:
        raise ValueError("no such build: %r (%s)" % (what, ", ".join(WAYS)))
    if what == "draft":
        ok, why = available(what)
        if not ok and runner is None:
            raise ValueError(why)
        if not chapters:
            raise ValueError("there is no chapter in the book yet: nothing to typeset")
    key = os.path.realpath(book_dir)
    with LOCK:
        job = JOBS.get(key)
        if job and job["state"] == "running":
            return _view(job), False
        job = {"state": "running", "what": what, "log": [], "started": time.time(),
               "finished": None, "ok": None, "code": None}
        JOBS[key] = job
        view = _view(job)
    # the chapters go to `command` only for the draft: the other ways are called as they always were
    cmd = command(book_dir, what, chapters) if what == "draft" else command(book_dir, what)
    threading.Thread(target=_run, args=(job, cmd, runner, key), daemon=True).start()
    return view, True


# ------------------------------------------------------------------ without sh
def _first_error(log_text):
    lines = log_text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("!"):
            return lines[i:i + 5]
    return []


def _log_matches(log_text, pattern, most, before=0, after=0):
    """The lines a pattern hits, with their neighbours and their numbers --
    `grep -n -m<most> -B<before> -A<after>`, which is what build.sh prints,
    so a failure reads the same on Windows as it does through the shell."""
    lines = log_text.splitlines()
    out, seen, hits = [], set(), 0
    for i, line in enumerate(lines):
        if hits >= most or not re.search(pattern, line):
            continue
        hits += 1
        for n in range(max(0, i - before), min(len(lines), i + after + 1)):
            if n not in seen:
                seen.add(n)
                out.append("%d:%s" % (n + 1, lines[n]))
    return out


# A PDF IS NOT PROOF OF SUCCESS AND NEITHER IS A SILENT LOG.  This is
# build.sh's check_log, line for line, for the machines that have no sh --
# Windows above all, where this is the only build there is.  The Python side
# used to check two of its five things, "Output written on" and a `!` line,
# and so reported success for the two failures that cost the most:
#
#   * a Lua error inside \directlua, which does NOT start with a ! -- the
#     one that dropped 145 pages of Persian out of a book and reported 0
#     errors, and the whole reason build.sh's check is as long as it is;
#   * lualatex never running at all, or dying before it wrote anything: the
#     log and the PDF of the PREVIOUS run are still lying there, and a
#     missing log then read as an empty one, which says nothing about a PDF
#     that is quietly a week old.
#
# The log is deleted before each run (below), so its absence is a failure
# and not a mystery.
def _check_log(log, pdf, base, say):
    """True when this run really did produce this PDF."""
    try:
        with open(log, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        say("   NO LOG at %s -- lualatex did not run" % log)
        return False
    if "no output PDF file produced" in text or not os.path.isfile(pdf):
        say("   PDF FAILED -- first error from %s:" % log)
        for line in _first_error(text):
            say("     " + line)
        return False
    if not re.search(r"Output written on .*%s\.pdf" % re.escape(base), text):
        say('   %s has no "Output written on" -- the run did not finish;' % log)
        say("   the PDF beside it is from an earlier build and is NOT current")
        return False
    if re.search(r"^!", text, re.M):
        say("   LaTeX ERRORS in %s (a PDF was still produced, so check it):" % log)
        for line in _log_matches(text, r"^!", 3, after=3):
            say("     " + line)
        return False
    lua = r"^\[\\directlua\]|attempt to (get|call|index|perform|concatenate)"
    if re.search(lua, text, re.M):
        n = len(re.findall(r"^\[\\directlua\]", text, re.M))
        say("   LUA ERRORS in %s (%d of them) -- \\directlua abandoned its chunk,"
            % (log, n))
        say("   so whatever it was printing is MISSING from the PDF:")
        for line in _log_matches(text, r"^\[\\directlua\]|attempt to ", 2,
                                 before=1, after=4):
            say("     " + line)
        return False
    return True


def build(book_dir, html_only=False, say=print, index=True):
    """What ./build.sh does for one book, in Python, for a machine with no sh
    -> True when everything asked for was built.  No cache: a rebuild it could
    have skipped costs time, never a stale page."""
    import books
    b = books.Book(book_dir)
    if not os.path.isfile(b.main):
        say("no %s yet: nothing to build" % os.path.basename(b.main))
        return False
    python = sys.executable
    if os.path.isfile(os.path.join(book_dir, "timings.json")):
        subprocess.run([python, os.path.join(LIB, "timestamp.py"), "--from-sidecar"],
                       cwd=book_dir, capture_output=True)
    ok = True
    if not html_only:
        lualatex = shutil.which("lualatex")
        if not lualatex:
            say("no lualatex on this machine: the PDF needs TeX Live (or MiKTeX); "
                "building the reader alone")
            ok = False
        else:
            base = os.path.splitext(os.path.basename(b.main))[0]
            log = os.path.join(book_dir, base + ".log")
            pdf = os.path.join(book_dir, base + ".pdf")
            fonts = [os.path.join(LIB, "fonts")] + ([os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")]
                                                   if runtime.WIN else [])
            env = dict(os.environ, OSFONTDIR=os.pathsep.join(fonts))
            text = ""
            for n in (1, 2):
                say("lualatex, pass %d" % n)
                if os.path.exists(log):
                    os.remove(log)
                subprocess.run([lualatex, "-interaction=nonstopmode", os.path.basename(b.main)],
                               cwd=book_dir, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    with open(log, encoding="utf-8", errors="replace") as f:
                        text = f.read()
                except OSError:
                    text = ""
                if not _check_log(log, pdf, base, say):
                    ok = False
                    break
            else:
                pages = re.findall(r"%s\.pdf \((\d+) pages" % re.escape(base), text)
                say("   pdf: %s pages" % (pages[-1] if pages else "?"))
    say("the reader")
    r = subprocess.run([python, os.path.join(LIB, "tex2html.py")], cwd=book_dir,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in (r.stdout + r.stderr).splitlines():
        say("   " + line)
    if r.returncode != 0:
        say("   reader FAILED")
        ok = False
    if not index:
        return ok
    r = subprocess.run([python, os.path.join(LIB, "make_index.py")], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        say("the library page could not be rewritten: " + (r.stderr.strip().splitlines() or [""])[-1])
        ok = False
    return ok


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__.strip().split("\n\n")[0])
        return 2
    return 0 if build(args[0], html_only="--html" in argv) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
