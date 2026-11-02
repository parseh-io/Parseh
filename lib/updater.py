#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Updating Parseh in place, from Settings (TO-DO §13.16): to a newer
version, back to an older one, or the same one again.

    import updater                      the server's half: the page, the plan, the start
    updater.installed(root)             which release this is, or why it cannot be updated
    updater.latest()                    GitHub's newest release, asked once
    updater.fetch(root, info, ...)      its zip downloaded, checked, made the candidate
    updater.take(root, path, ...)       a zip the person chose, checked, made the candidate
    updater.plan(root)                  what installing the candidate would do, in full
    updater.begin(root, ...)            the job written down; the helper does the rest

    python3 .parseh-update/helper.py run ROOT       the helper: stop, replace, start again
    python3 .parseh-update/helper.py resume ROOT    an update that did not finish, finished or undone
    python3 .parseh-update/helper.py rollback ROOT  the last update undone from its backup

The last three are run by Parseh itself -- by the server, by lib/launcher.py
and by the first lines of serve.py -- and never by a person: everything a
person does is a button on Settings > Updating Parseh (lib/updatepage.py).

WHY IT IS NOT "UNZIP OVER THE TOP".  A person's work lives inside the
install: books/, youtube/videos/, markdown/library/, exercises/,
youtube/anki/, clips/, dict/, corpus/, mt/, components/, stt/, arasaac/, config/, .tls/,
.runtime/.  A release zip is, by definition, the exact list of what belongs
to Parseh at one version -- everything else in the folder is the person's.
So an update is: write the new version's files, AND DELETE THE PATHS THE OLD
VERSION SHIPPED THAT THE NEW ONE DOES NOT (the half everybody forgets, and
without which a retired file lives for ever), and touch nothing that is in
neither list.  Both lists are the releases' manifests, .parseh-release.json
(lib/release.py writes one into every zip, and the zip puts it at the root
of every install): the one in the install says what is there, the one in the
zip what is wanted.

ANY DIRECTION, BECAUSE THE MANIFESTS MAKE THEM ONE ALGORITHM.  Nothing here
asks "is it newer?".  Going BACK is how a release that went wrong is
escaped, and installing THE SAME VERSION AGAIN is how a build nobody has
seen yet is iterated on -- find a fault, fix it, build the same number,
install it again.  So the direction is only ever SAID: plan() names it, the
page words the button after it ("Update to", "Go back to", "Install ...
again"), and a step back is never presented as an ordinary update.

WHAT MAKES A STEP BACK DANGEROUS IS DATA, NOT FILES.  Old code can meet what
newer code wrote -- a deck's schedule, a video's annotations, the settings.
Each shape Parseh writes has a number of its own (lib/version.py FORMATS),
every manifest carries them, and a move that would take any of them DOWN is
refused unless the person insists, having been told in words what may not
survive.  When they insist, a copy of the content's small files -- the
json, the databases, the .tex, not the narrations and the films -- is taken
before anything is written, so that going forward again finds them.

A FILE OF PARSEH'S THAT WAS CHANGED BY HAND is overwritten, its old copy is
kept in the backup, and it is LISTED in the report -- never a question per
file (the owner, 2026-09-24): the installer compiles the guide into
html-guide/site/, which the release ships too, so asking would interrogate
somebody about dozens of files.  A file the new version ships that was
there already and was NOT Parseh's -- a language's lib/lang/<code>.tex
somebody added by hand, before Parseh shipped one of the same name -- is
treated the same way, and listed apart.

AND SUCH A FILE IS GIVEN BACK (the owner, 2026-09-25).  Its backup is the
only copy of something that was never Parseh's, so the day an update
installs a version that no longer ships that name -- going back, most
often, but any version will do -- the person's own file goes back where it
was, from the backup of the update that took it, and the report lists it as
put back.  Which update took which file is read from the jobs kept, newest
first (a report's "foreign" list, and what later reports settled); a job
removed with its backup (only the last KEEP_JOBS are kept) leaves its
unsettled paths in taken.json, so that the day the name is retired the
report can still say plainly that the person's copy is gone, rather than
say nothing.  A version that ships a folder where the file was cannot take
it back: it stays in its backup, and the report says where.

WHY A HELPER PROCESS.  The server runs from the very files an update
replaces, and Windows will not let a running program's files go.  So the
server writes the job down (begin) and stops; a helper -- a copy of THIS
FILE, taken into .parseh-update/helper.py, so that nothing it runs is
replaced under it -- applies it and starts the server again.  Who starts the
helper depends on who started the server:

  * lib/launcher.py (serve.bat on Windows) keeps the server in its own
    console window and waits on it.  The server leaves with LAUNCHER_EXIT,
    the launcher runs the helper in that window, then starts the server
    again there: the window the person knows stays the log.
  * anything else (serve.sh, Parseh.command, `python3 serve.py`): the server
    starts the helper as a process of its own, in a session of its own, so
    that the server's end does not take it along; the helper starts the new
    server exactly as the old one was started -- the same Python, the same
    arguments -- in the background, its log in serve.log and its pid where
    serve.sh looks.

WHILE THE SERVER IS DOWN, the helper answers on the server's own port from
this computer alone: /settings/api/update/state says how far it has got,
and any other address a page that says "Parseh is being updated" and comes
back by itself.  So the page that started the update shows every step, and
a tab left open elsewhere is not met by a refused connection.

A HALF-FINISHED UPDATE IS FINISHED OR UNDONE, NEVER LEFT.  The order is:
wait for the server to be gone; copy the content's small files (only for a
step back that lowers a data format); add to the environment what the new
version asks (only when it asks); back up every file of Parseh's that is
about to be overwritten or deleted; delete, then write, each write a
whole-file rename; write the new manifest; the post-steps; start again.
Every step is recorded as it finishes in the job's journal, and a file the
update CREATES is recorded before it is created -- which is all undoing
needs, since everything else it changed is in the backup.  If the helper is
killed (a power cut, a closed laptop, somebody's kill -9), the next start of
Parseh -- serve.py and lib/launcher.py ask finish_first() before they import
anything else of Parseh's -- runs the helper copy again: it carries the
update on where the release's zip is still whole, and undoes it from the
backup where it is not.  A new version that does not start is undone too,
and the old one started again.

THE ENVIRONMENT IS TOUCHED ONLY WHEN THE NEW VERSION ASKS (§13.3): each
manifest records what environment.yml required, and when the two differ the
packages the target asks for and this environment may lack are installed
BEFORE a file of Parseh's is replaced -- so a step that fails leaves the old
version exactly as it was.  A step back KEEPS the newer environment and says
so (an older Parseh runs with newer packages; going forward again then
needs nothing), and only adds what the older version needs and the
environment lacks.  A change of Python cannot be made inside the
environment Parseh runs in, and is refused in words rather than attempted.

WHERE THINGS ARE KEPT, all under .parseh-update/ at the root of the install
and in no manifest (an update never touches it, nor does the release
builder ship it):

    incoming/                 the candidate: the zip, and what it is
    jobs/<id>/                one update: its job, its journal, the zip it
                              installs, backup/ (Parseh's files as they
                              were), content/ (the small files, for a step
                              back), report.json, log.txt
    helper.py                 the helper, a copy of this file
    pending.json              there while an update is not finished
    state.json                how far the current or last update got
    taken.json                files of the person's that an update took,
                              whose backup has gone with that update

The last KEEP_JOBS jobs are kept; older ones are removed when an update
finishes.  config/updates.json keeps the one setting the updater has -- a
daily look at GitHub, off until ticked -- and what the last look found.

IT SENDS NOTHING ABOUT THE PERSON.  The look at GitHub is one question --
which release is newest -- asked with Parseh's name and version as its user
agent, from the address the computer already has.

STANDARD LIBRARY ONLY AT THE TOP, because the helper is this file run on its
own from .parseh-update/, beside an install that may be half replaced.  The
server's half imports lib/version.py, lib/release.py and lib/download.py
inside the functions that need them; the helper imports none of them, and
reaches lib/runtime.py only for the environment step, which runs before any
file is replaced.

A TEST HOOK, AND ONLY ONE: PARSEH_UPDATE_TEST_DELAY, seconds to wait after
each file written, makes the window in which a test kills the helper half
way (tests/test_updater.py).  Unset, it costs nothing.
"""
import errno
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
import zlib

NAME = "Parseh"
MANIFEST = ".parseh-release.json"
RELEASE_FORMAT = "parseh-release/1"
WORK = ".parseh-update"
# WHERE PARSEH LIVES -- the repository, the feed asked for the newest release, the
# releases page the refusals name -- is lib/project.py's, and nobody else's: read
# when an address is wanted (feed_url(), _releases()), never here at the top.  This
# file is also the HELPER, run on its own from .parseh-update/ beside an install that
# may be half replaced, and the helper never needs an address: so it imports nothing
# of Parseh's at the top (tests/test_project.py holds it to that).
# The feed is releases/latest: GitHub's newest PUBLISHED release that is not a
# prerelease -- which every Parseh release is (the owner, 2026-09-24: releases are
# not marked as prereleases), and never a draft.
# the one setting the updater has, and what the last look found
# (config/updates.json).  RAISE IT when the shape changes so that the Parseh
# before this one would read the file wrong (lib/version.py FORMATS).
STORE_FORMAT = 1
# the job file's own shape, read only by the helper copy that the same
# version wrote beside it
JOB_FORMAT = 1
# taken.json's shape.  Unlike a job, it is read by the helper of whichever
# version updates next -- an older one too -- so a helper that meets a
# number it does not know reads the file as empty rather than guess
TAKEN_FORMAT = 1
# what the server leaves with when lib/launcher.py is to run the helper
LAUNCHER_EXIT = 75
KEEP_JOBS = 3
DAY = 24 * 3600
LIMIT = 1 << 30                 # a release zip is some 15 MB; a gigabyte is a mistake

# WHAT NO MANIFEST MAY TOUCH.  A release never ships these (lib/release.py
# audits every build for them), so a manifest that names one is not a
# release of Parseh's, whatever else it is: its paths are refused before a
# byte is written, and the same test guards every deletion -- an OLD
# manifest is a zip's too.
PERSONAL = ("books/", "youtube/videos/", "youtube/anki/", "markdown/library/", "exercises/",
            "clips/", "config/", "dict/", "corpus/", "mt/", "components/", "texmf/", "stt/", "analysis/", "llm-scoring/",
            "arasaac/")
SCAFFOLDING = (".gitkeep", "README.md")
NEVER = (".tls/", ".runtime/", ".git/", WORK + "/", ".claude/")
NEVER_FILES = (".serve.pid", "serve.log", ".setup-done", ".git")

# The content's small files, copied before a step back that lowers a data
# format: everything under these folders but what is a recording, a film, a
# picture, a PDF, a font or an archive -- the narrations and the films are
# what is big, and no data format is kept in them.  NOT stt/ (speech to text's
# program and models): gigabytes, and no data format of Parseh's is kept in
# them -- a step back leaves it exactly as it is.  Nor arasaac/ (the ARASAAC
# pictograms): somebody else's pictures, fetched again by a button, and an
# older Parseh that does not know the folder simply leaves it alone.
CONTENT = ("books/", "youtube/videos/", "youtube/anki/", "markdown/library/", "exercises/",
           "clips/", "config/")
MEDIA = {".mp3", ".ogg", ".opus", ".oga", ".m4a", ".aac", ".wav", ".flac", ".weba", ".webm",
         ".wma", ".aiff", ".aif", ".amr", ".mka", ".caf",      # the other sounds a video may be (bundle.SOUND_EXTS)
         ".mp4", ".m4v", ".mkv", ".mov", ".avi", ".jpg", ".jpeg", ".png", ".gif", ".webp",
         ".avif", ".bmp", ".tif", ".tiff", ".heic", ".pdf", ".woff", ".woff2", ".ttf", ".otf",
         ".zip", ".apkg", ".colpkg", ".gz", ".bz2", ".xz", ".zst", ".tar"}

# WHAT THE INSTALLER MAKES AGAIN ON THIS COMPUTER, though the release ships
# it too: the guide's compiled pages (install.sh and the Windows wizard
# compile html-guide/markdown/ into html-guide/site/).  Such a file differs
# from the release's on nearly every install, so it is listed apart from the
# files somebody really changed by hand -- still overwritten, still kept in
# the backup, still listed, and compiled again by the post-steps.
COMPILED = ("html-guide/site/",)

WIN = os.name == "nt"


class Refused(Exception):
    """What the updater will not do, in words for the person who asked.
    `insist` is set when insisting is what would let it go on; `detail` is
    the technical line behind the words, if there is one (see plainly)."""

    def __init__(self, text, insist=False, detail=""):
        super().__init__(text)
        self.insist = insist
        self.detail = detail


# ------------------------------------------------------------------ small things
def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(path, obj):
    """Whole or not at all: a reader never sees half a file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    _replace(tmp, path)


def _replace(src, dest):
    """os.replace, a few times over on Windows, where a virus scanner or the
    indexer holds a file for a moment after it was written."""
    for attempt in range(8 if WIN else 1):
        try:
            os.replace(src, dest)
            return
        except PermissionError:
            if attempt == (7 if WIN else 0):
                raise
            time.sleep(0.25 * (attempt + 1))


def sha256_of(path):
    """A file's SHA-256, or None where there is no file."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()
    except (IsADirectoryError, FileNotFoundError, NotADirectoryError):
        return None
    except OSError:
        return None


def _mode(path):
    try:
        return "%04o" % (os.stat(path).st_mode & 0o777)
    except OSError:
        return None


def _runnable(mode):
    """Whether a mode ("0755", "0664" ...) lets the file be run: the one
    part of a mode a release decides.  The rest is this computer's umask --
    a 0664 where the release says 0644 is somebody's group, not a fault."""
    try:
        return bool(int(mode, 8) & 0o111)
    except (TypeError, ValueError):
        return False


def size_said(n):
    if n is None:
        return "an unknown size"
    if n >= 1e9:
        return "%.1f GB" % (n / 1e9)
    if n >= 1e6:
        return "%.1f MB" % (n / 1e6) if n < 1e7 else "%d MB" % round(n / 1e6)
    if n >= 1e3:
        return "%d kB" % round(n / 1e3)
    return "%d bytes" % n


def plainly(e, doing=""):
    """A failure -> (words, detail).

    THE PAGE SAYS WHAT FAILED IN WORDS, AND PYTHON'S LINE SMALLER BENEATH.
    "FileNotFoundError: [Errno 2] No such file or directory: '.../backup/
    .parseh-release.json.part'" is exactly what somebody mending Parseh
    needs, and tells the person who pressed the button nothing -- not even
    that the update stopped while it was keeping its copy of the files.  So
    a failure is said twice: `words`, a sentence naming the step it stopped
    in (`doing`, "keeping a copy of Parseh's files as they are") and the
    kind of thing that went wrong, and `detail`, Python's own line, which
    the page shows beneath in small type and the report keeps.  A Refused
    is in words already, and carries its own detail when it has one."""
    if isinstance(e, Refused):
        return str(e), getattr(e, "detail", "") or ""
    detail = _technical(e)
    if getattr(e, "errno", None) in (errno.ENOSPC, getattr(errno, "EDQUOT", errno.ENOSPC)):
        why = "the disk is full"
    elif isinstance(e, PermissionError):
        why = "this computer did not let it change a file"
    elif isinstance(e, FileNotFoundError):
        why = "a file it needed was not there"
    elif isinstance(e, (zipfile.BadZipFile, zlib.error, EOFError)):
        why = "the release's zip could not be read"
    elif isinstance(e, OSError):
        why = "a file could not be read or written"
    elif isinstance(e, MemoryError):
        why = "the computer ran out of memory"
    else:
        why = "something went wrong that %s did not expect" % NAME
    if doing:
        return "It stopped while %s: %s." % (doing, why), detail
    return why[0].upper() + why[1:] + ".", detail


def _technical(e):
    """Python's own line for the failure `e`: the cause inside a URLError
    rather than its wrapping."""
    reason = getattr(e, "reason", None)
    if isinstance(reason, BaseException):
        e = reason
    return "%s: %s" % (type(e).__name__, e)


def work(root, *parts):
    return os.path.join(root, WORK, *parts)


def guard(rel):
    """Why the path `rel` from a manifest may not be written or deleted by an
    update, or None when it may."""
    if not isinstance(rel, str) or not rel or rel != rel.strip():
        return "a path that is not one"
    if rel.startswith("/") or "\\" in rel or ":" in rel.split("/")[0]:
        return "%s is not a path inside Parseh's folder" % rel
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return "%s leaves Parseh's folder or names nothing" % rel
    if rel == MANIFEST:
        return "%s is written by the update itself" % rel
    if any(rel.startswith(n) for n in NEVER) or rel in NEVER_FILES:
        return "%s is this computer's own, and no release ships it" % rel
    if any(rel.startswith(p) for p in PERSONAL) and parts[-1] not in SCAFFOLDING:
        return "%s is somebody's content or settings, and Parseh ships none" % rel
    return None


def _abs(root, rel):
    return os.path.join(root, *rel.split("/"))


def _alive(pid):
    """Is the process `pid` still there?  (Asked without signalling it: on
    Windows os.kill(pid, 0) would END it.)"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if WIN:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x00100000 | 0x1000, False, pid)   # SYNCHRONIZE | QUERY_LIMITED
        if not h:
            return False
        try:
            return k.WaitForSingleObject(h, 0) == 0x102        # WAIT_TIMEOUT: still running
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # a zombie is not a server: its parent has not asked for its end yet
    try:
        with open("/proc/%d/stat" % pid, encoding="ascii", errors="replace") as f:
            return f.read().rsplit(")", 1)[-1].split()[0] != "Z"
    except OSError:
        return True


# ------------------------------------------------------------------ versions
def _lib(root):
    lib = os.path.join(root, "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)


def _compare(a, b):
    """lib/version.compare, the one rule for the order of versions."""
    import version
    return version.compare(a, b)


def direction_of(installed_version, incoming_version):
    """"newer", "older" or "same": which way installing `incoming` goes."""
    c = _compare(incoming_version, installed_version)
    return "newer" if c > 0 else "older" if c < 0 else "same"


def _what(fmt):
    try:
        import version
        return version.what(fmt)
    except (ImportError, KeyError, ValueError):
        return fmt


# ------------------------------------------------------------------ this install
def installed(root):
    """What is installed at `root` -> {"manifest", "version", "refused"}.

    `refused` is None when the install can be updated, and otherwise the
    words that say why not and what to do instead."""
    out = {"manifest": None, "version": None, "refused": None, "git": False}
    try:
        _lib(root)
        import version
        out["version"] = version.read(root)
    except (ImportError, ValueError):
        pass
    if os.path.exists(os.path.join(root, ".git")):
        out["git"] = True
        out["refused"] = (
            "This %s is a copy of its source code (a git checkout), not an install made from "
            "a release. Git keeps its files, and an update from here would fight it. "
            "Updating from Settings is for a %s installed from a release: download the "
            "release's zip from %s, unpack it into a folder of its own, and move your things "
            "into it." % (NAME, NAME, _releases()))
        return out
    path = os.path.join(root, MANIFEST)
    if not os.path.isfile(path):
        out["refused"] = (
            "This %s has no list of its own files (%s): it was installed before %s could "
            "update itself, or unpacked by hand. Without that list an update cannot tell %s's "
            "files from yours, so it will not guess. Install this version fresh from a "
            "release (%s) and move your things into it; every install made from a release "
            "can then be updated from here." % (NAME, MANIFEST, NAME, NAME, _releases()))
        return out
    m = _read_json(path)
    if not isinstance(m, dict) or not isinstance(m.get("files"), dict):
        out["refused"] = ("%s cannot be read, so an update cannot tell %s's files from yours. "
                          "Install this version fresh from a release (%s)."
                          % (MANIFEST, NAME, _releases()))
        return out
    if m.get("format") != RELEASE_FORMAT:
        out["refused"] = ("%s is of a kind this %s does not know (%s). Install fresh from a "
                          "release (%s)." % (MANIFEST, NAME, m.get("format"), _releases()))
        return out
    out["manifest"] = m
    out["version"] = m.get("version") or out["version"]
    return out


# ------------------------------------------------------------------ the setting
def store(root):
    return os.path.join(root, "config", "updates.json")


def settings(root):
    """{"daily": bool, "checked": seconds or 0, "latest": {...} or None,
    "error": str, "detail": str} -- config/updates.json, or the defaults: the
    daily look is OFF until somebody ticks it (the owner, 2026-09-24).  The
    last look's failure is kept in words (`error`) and in Python's
    (`detail`, which the page shows smaller; see plainly)."""
    doc = _read_json(store(root), {}) or {}
    return {"daily": bool(doc.get("daily")), "checked": float(doc.get("checked") or 0),
            "latest": doc.get("latest") if isinstance(doc.get("latest"), dict) else None,
            "error": str(doc.get("error") or ""), "detail": str(doc.get("detail") or "")}


def save_settings(root, **changes):
    doc = settings(root)
    for k, v in changes.items():
        if k in ("daily", "checked", "latest", "error", "detail"):
            doc[k] = v
    doc["_format"] = STORE_FORMAT
    _write_json(store(root), doc)
    return doc


def due(root, now=None):
    """Is the daily look due?  Only when somebody ticked it."""
    s = settings(root)
    return s["daily"] and (now or time.time()) - s["checked"] >= DAY - 600


# ------------------------------------------------------------------ GitHub
def _agent():
    try:
        import version
        return "%s/%s" % (NAME, version.VERSION)
    except (ImportError, ValueError):
        return NAME


def _releases():
    """The releases page, where the refusals send a person: lib/project.py's."""
    try:
        import project
        return project.RELEASES_URL
    except ImportError:             # an install half replaced: say where, without the address
        return "the releases page of the project on GitHub"


def feed_url():
    # PARSEH_UPDATE_FEED stands in for GitHub: a mirror, or a test's own server
    got = os.environ.get("PARSEH_UPDATE_FEED")
    if got:
        return got
    import project
    return project.FEED


def latest(timeout=20):
    """GitHub's newest release of Parseh -> {"version", "name", "published",
    "page", "notes", "zip", "sha256_url", "size"}; Refused, in words, when
    there is none or GitHub cannot be asked."""
    req = urllib.request.Request(feed_url(), headers={
        "Accept": "application/vnd.github+json", "User-Agent": _agent(),
        "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            doc = json.loads(r.read(4 << 20).decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise Refused("No release of %s has been published on GitHub yet." % NAME)
        if e.code in (403, 429):
            raise Refused("GitHub asks %s to wait before asking again (it answers some sixty "
                          "questions an hour from one address). Try again later." % NAME)
        raise Refused("GitHub answered %d (%s)." % (e.code, e.reason))
    except (urllib.error.URLError, OSError) as e:
        raise Refused("GitHub could not be reached: is this computer on the internet? Nothing "
                      "else was tried.", detail=_technical(e))
    except ValueError as e:
        raise Refused("GitHub's answer could not be read as a list of releases. Nothing else was "
                      "tried.", detail=_technical(e))
    tag = str(doc.get("tag_name") or "")
    try:
        import version
        version.parse(tag)
    except ValueError:
        raise Refused("GitHub's newest release is tagged %r, which is not a version this %s can "
                      "read." % (tag, NAME))
    assets = {a.get("name"): a for a in doc.get("assets") or [] if isinstance(a, dict)}
    name = "parseh-%s.zip" % tag
    if name not in assets or name + ".sha256" not in assets:
        raise Refused("GitHub's newest release, %s, has no %s with its checksum beside it, so "
                      "there is nothing %s can check and install." % (tag, name, NAME))
    return {"version": tag, "name": doc.get("name") or tag,
            "published": doc.get("published_at") or "", "page": doc.get("html_url") or "",
            "notes": str(doc.get("body") or "")[:20000], "zip": assets[name].get("browser_download_url"),
            "sha256_url": assets[name + ".sha256"].get("browser_download_url"),
            "size": assets[name].get("size"), "file": name}


def check(root):
    """Ask GitHub now, and keep what it said in config/updates.json -> the
    settings as they now stand."""
    try:
        found = latest()
    except Refused as e:
        return save_settings(root, checked=time.time(), error=str(e), detail=e.detail)
    return save_settings(root, checked=time.time(), latest=found, error="", detail="")


# ------------------------------------------------------------------ the candidate
def _incoming(root, *parts):
    return work(root, "incoming", *parts)


def candidate(root):
    """The version waiting to be installed -> its record, or None."""
    rec = _read_json(_incoming(root, "candidate.json"))
    if not isinstance(rec, dict) or not os.path.isfile(_incoming(root, "candidate.zip")):
        return None
    return rec


def candidate_manifest(root):
    return _read_json(_incoming(root, "candidate.manifest.json"))


def discard(root):
    """Throw the candidate away (and any download of one left half way)."""
    for name in ("candidate.zip", "candidate.json", "candidate.manifest.json"):
        try:
            os.unlink(_incoming(root, name))
        except OSError:
            pass
    shutil.rmtree(_incoming(root, "download"), ignore_errors=True)


def zip_manifest(path):
    """A zip -> its manifest, held to itself and to the rules of a release;
    Refused, in words, for anything that is not a release of Parseh's."""
    _lib(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    import release
    import version
    if not zipfile.is_zipfile(path):
        raise Refused("That file is not a zip, so it is not a release of %s." % NAME)
    try:
        manifest, problems = release.read_manifest(path)
    except release.Refused:
        raise Refused("That zip is not a release of %s: it has no %s in one folder at its top "
                      "(a release is parseh-<version>.zip, from the releases page or built "
                      "with lib/release.py)." % (NAME, MANIFEST))
    except (zipfile.BadZipFile, ValueError, OSError) as e:
        raise Refused("That zip cannot be read: %s." % e)
    if not isinstance(manifest, dict) or manifest.get("format") != RELEASE_FORMAT:
        raise Refused("That release's list of files is of a kind this %s does not know (%s): it "
                      "was made for a newer %s. Install it fresh instead."
                      % (NAME, (manifest or {}).get("format"), NAME))
    try:
        version.parse(str(manifest.get("version")))
    except ValueError as e:
        raise Refused("That release names no version this %s can read: %s" % (NAME, e))
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise Refused("That release lists no files.")
    bad = [w for w in (guard(rel) for rel in files) if w]
    if bad:
        raise Refused("That zip would write where no release of %s ever does: %s%s. Nothing "
                      "was installed." % (NAME, "; ".join(bad[:3]),
                                          " (and %d more)" % (len(bad) - 3) if len(bad) > 3 else ""))
    if problems:
        raise Refused("That zip is damaged, or was changed after it was built: %s%s. Nothing "
                      "was installed." % ("; ".join(problems[:3]),
                                          " (and %d more)" % (len(problems) - 3)
                                          if len(problems) > 3 else ""))
    return manifest


def take(root, path, source, name, meta=None):
    """Make the zip at `path` the candidate, once it has been checked; the
    file is moved in (never copied), and removed when it is refused."""
    try:
        manifest = zip_manifest(path)
    except Refused:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    os.makedirs(_incoming(root), exist_ok=True)
    digest = sha256_of(path)
    size = os.path.getsize(path)
    # moved out of the way first: the file may lie in the download folder
    # that throwing the old candidate away empties
    fresh = _incoming(root, "candidate.zip.new")
    shutil.move(path, fresh)
    discard(root)
    os.replace(fresh, _incoming(root, "candidate.zip"))
    _write_json(_incoming(root, "candidate.manifest.json"), manifest)
    rec = {"version": manifest["version"], "commit": manifest.get("commit") or "",
           "built": manifest.get("built") or "", "source": source, "name": name,
           "sha256": digest, "size": size, "at": time.time()}
    rec.update(meta or {})
    _write_json(_incoming(root, "candidate.json"), rec)
    return rec


def _small_get(url, limit=64 << 10, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": _agent()})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(limit).decode("utf-8", "replace")


def fetch(root, info, progress=None, cancel=None, say=None):
    """Download the release `info` (from latest()) and make it the
    candidate: its .sha256 first, then the zip, checked against it
    (lib/download.py resumes a download that was cut off)."""
    _lib(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    import download
    name = info.get("file") or "parseh-%s.zip" % info["version"]
    try:
        said = _small_get(info["sha256_url"]).split()
    except (urllib.error.URLError, OSError) as e:
        raise Refused("The release's checksum could not be downloaded, so nothing was: without "
                      "it the release cannot be checked.", detail=_technical(e))
    digest = said[0].lower() if said else ""
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise Refused("The release's checksum file does not hold a SHA-256.")
    dest = _incoming(root, "download", name)
    try:
        download.fetch(info["zip"], dest, say=say, progress=progress, cancel=cancel,
                       sha256=digest, headers={"User-Agent": _agent()},
                       size=info.get("size"), limit=LIMIT)
    except download.Mismatch as e:
        raise Refused(str(e))
    except download.Cancelled:
        raise
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise Refused("The release could not be downloaded to the end. What came is kept, and "
                      "getting it again carries on from there.", detail=_technical(e))
    return take(root, dest, "github", name,
                {"published": info.get("published") or "", "page": info.get("page") or "",
                 "notes": info.get("notes") or ""})


# ------------------------------------------------------------------ the plan
def diff(root, old, new):
    """What installing the manifest `new` over the install at `root` (whose
    own manifest is `old`) would do, file by file, from what is on the disk:

        write   [[path, kind]]: "new" (not there), "replace" (Parseh's, as
                installed), "edited" (Parseh's, changed since it was
                installed), "foreign" (there, and in no manifest: not Parseh's)
        delete  [[path, kind]]: "retired" (as installed) or "edited"
        modes   [path]: the right bytes with the wrong mode
        same    how many files are already exactly what `new` wants

    A path the old manifest names that is no longer there is simply gone;
    a path in neither manifest is never looked at."""
    old_files = (old or {}).get("files") or {}
    new_files = new.get("files") or {}
    out = {"write": [], "delete": [], "modes": [], "same": 0}
    for rel, want in new_files.items():
        if guard(rel):
            continue
        path = _abs(root, rel)
        have = sha256_of(path)
        if have == want.get("sha256"):
            if not WIN and want.get("mode") and _runnable(_mode(path)) != _runnable(want["mode"]):
                out["modes"].append(rel)
            else:
                out["same"] += 1
            continue
        if have is None:
            kind = "new"
        elif rel in old_files:
            kind = "replace" if have == old_files[rel].get("sha256") else "edited"
        else:
            kind = "foreign"
        out["write"].append([rel, kind])
    for rel, was in old_files.items():
        if rel in new_files or guard(rel):
            continue
        have = sha256_of(_abs(root, rel))
        if have is None:
            continue
        out["delete"].append([rel, "retired" if have == was.get("sha256") else "edited"])
    for k in ("write", "delete"):
        out[k].sort()
    out["modes"].sort()
    return out


# ------------------------------------------------------------------ the person's files an update took
def _jobs(root):
    """The updates kept in .parseh-update/jobs/, newest first, by when each
    was written down (job.json's "made"): by name alone, two made in the
    same second would sort by the names of their versions."""
    base = work(root, "jobs")
    try:
        names = [n for n in os.listdir(base) if os.path.isdir(os.path.join(base, n))]
    except OSError:
        return []

    def made(n):
        job = _read_json(os.path.join(base, n, "job.json"), {}) or {}
        try:
            return float(job.get("made") or 0)
        except (TypeError, ValueError):
            return 0.0
    return sorted(names, key=lambda n: (made(n), n), reverse=True)


def _paths_of(items):
    """A report's list of paths, or of [path, ...] rows -> the paths."""
    out = []
    for x in items or []:
        if isinstance(x, (list, tuple)) and x:
            x = x[0]
        if isinstance(x, str) and x:
            out.append(x)
    return out


def _taken_gone(root):
    """taken.json -> {path: {"from", "to", "at"}}: files of the person's
    that an update took, whose update -- and its backup -- has since been
    removed.  Empty for a shape this helper does not know (TAKEN_FORMAT)."""
    doc = _read_json(work(root, "taken.json"), {}) or {}
    if not isinstance(doc, dict) or doc.get("format") != TAKEN_FORMAT \
            or not isinstance(doc.get("gone"), dict):
        return {}
    return {rel: e for rel, e in doc["gone"].items() if isinstance(e, dict) and not guard(rel)}


def yours_taken(root, jobs=None):
    """The person's files that an update took and no later update has given
    back -> {path: {"job", "from", "to", "at"}}, "job" being "" where that
    update's backup has gone with it.

    THE NEWEST WORD ON A PATH HOLDS.  The finished updates `jobs` (ids,
    newest first; every kept one when None) are read in turn: one that put a
    path back, or said that it could not, settles it; one that took a path
    (its report's "foreign") holds it, unless a newer one settled it first.
    An update that did not happen -- failed, undone, never finished -- says
    nothing, since undoing it put the person's file back already.  What no
    update read here settles is then taken from taken.json: the paths that
    updates removed since were still holding."""
    ids = _jobs(root) if jobs is None else jobs
    settled, out = set(), {}
    for jid in ids:
        r = _read_json(work(root, "jobs", jid, "report.json"))
        if not isinstance(r, dict) or not r.get("ok") or r.get("rolled_back"):
            continue
        for key in ("put_back", "put_back_gone", "put_back_held"):
            settled.update(_paths_of(r.get(key)))
        for rel in _paths_of(r.get("foreign")):
            if rel not in settled and not guard(rel):
                settled.add(rel)
                out[rel] = {"job": jid, "from": r.get("from") or "", "to": r.get("to") or "",
                            "at": r.get("finished") or r.get("started") or 0}
    for rel, e in _taken_gone(root).items():
        if rel not in settled:
            out[rel] = {"job": "", "from": str(e.get("from") or ""), "to": str(e.get("to") or ""),
                        "at": e.get("at") or 0}
    return out


def returns(root, old, new, current=None):
    """The person's own files that moving from the manifest `old` to `new`
    gives back -> {"back": [[path, job, to]], "gone": [[path, to]], "held":
    [[path, job, to]]}, `to` being the version whose update took the file.

    A path is given back when `new` no longer ships it and an earlier update
    took the person's file there (yours_taken, the update `current` left
    out): "back" when that update's backup still holds the file; "gone" when
    it does not -- removed with its update, the last KEEP_JOBS being all that
    are kept, or by hand; "held" when `new` has a folder at that name, or a
    file where the path needs a folder, so that the file stays in the
    backup."""
    old_files = (old or {}).get("files") or {}
    new_files = (new or {}).get("files") or {}
    out = {"back": [], "gone": [], "held": []}
    retired = sorted(rel for rel in old_files if rel not in new_files and not guard(rel))
    if not retired:
        return out
    taken = yours_taken(root, [j for j in _jobs(root) if j != current])
    for rel in retired:
        e = taken.get(rel)
        if not e:
            continue
        src = os.path.join(work(root, "jobs", e["job"], "backup"), *rel.split("/")) \
            if e["job"] else ""
        parts = rel.split("/")
        blocked = (os.path.isdir(_abs(root, rel))
                   or any(p.startswith(rel + "/") for p in new_files)
                   or any("/".join(parts[:i]) in new_files for i in range(1, len(parts))))
        if not src or not os.path.isfile(src):
            out["gone"].append([rel, e["to"]])
        elif blocked:
            out["held"].append([rel, e["job"], e["to"]])
        else:
            out["back"].append([rel, e["job"], e["to"]])
    return out


def environment_plan(have, want, direction, target):
    """What the environment needs for a move to `target` -> {"install":
    [{"kind", "name", "line"}], "kept": [...], "blocked": str, "said": str}.

    `have` and `want` are the two manifests' "environment": {"conda":
    {name: line}, "pip": {name: line}}, environment.yml's own lines."""
    install, kept, blocked = [], [], ""
    for kind in ("conda", "pip"):
        h = (have or {}).get(kind) or {}
        w = (want or {}).get(kind) or {}
        for name in sorted(w):
            line = w[name]
            if name not in h:
                install.append({"kind": kind, "name": name, "line": line})
            elif h[name] != line:
                if name == "python" and direction != "older":
                    blocked = ("%s needs a different Python (%s, where this environment was made "
                               "for %s), and a Python cannot be changed inside the environment "
                               "%s runs in. Install %s fresh from its release instead."
                               % (target, line, h[name], NAME, target))
                elif direction == "older":
                    kept.append({"kind": kind, "name": name, "line": h[name], "wanted": line})
                else:
                    install.append({"kind": kind, "name": name, "line": line})
    if blocked:
        said = blocked
    elif install:
        said = ("%s asks for %s. They are added to %s's environment before any of its files is "
                "replaced, so a step that fails leaves this version as it is."
                % (target, ", ".join(i["line"] for i in install), NAME))
    else:
        said = "Nothing to install: %s asks for the packages this %s already has." % (target, NAME)
    if kept:
        said += (" The environment stays as the newer version made it (%s), because an older "
                 "%s runs with newer packages and going forward again then needs nothing."
                 % (", ".join("%s where %s asked %s" % (k["line"], target, k["wanted"])
                              for k in kept), NAME))
    return {"install": install, "kept": kept, "blocked": blocked, "said": said,
            "needed": bool(install)}


def formats_plan(old, new, target):
    """The data-format verdict: which shapes a move to `new` would take down
    (refused unless insisted) or up (said)."""
    of = (old or {}).get("data_formats") or {}
    nf = (new or {}).get("data_formats") or {}
    lowered = [{"name": k, "what": _what(k), "from": n, "to": nf.get(k)}
               for k, n in sorted(of.items()) if nf.get(k, 0) < n]
    raised = [{"name": k, "what": _what(k), "from": of.get(k), "to": n}
              for k, n in sorted(nf.items()) if of.get(k, 0) < n]
    said = ""
    if lowered:
        said = ("%s reads these in an older shape than this %s wrote them: %s. What was written "
                "in the newer shape may be read wrong there, or not at all. Before anything is "
                "replaced, a copy of the small files of your books, videos, decks and settings "
                "(not the narrations and films) is kept, so that going forward again finds them."
                % (target, NAME, "; ".join(x["what"] for x in lowered)))
    elif raised:
        said = ("%s writes these in a newer shape: %s. It reads what this %s wrote; going back "
                "below it later is refused unless you insist." % (
                    target, "; ".join(x["what"] for x in raised), NAME))
    return {"lowered": lowered, "raised": raised, "said": said}


def plan(root):
    """Everything installing the candidate would do, from what is on the
    disk now -> a dict the page draws and begin() holds itself to."""
    inst = installed(root)
    out = {"installed": {"version": inst["version"]}, "refused": inst["refused"],
           "candidate": candidate(root), "busy": running(root)}
    if inst["manifest"]:
        m = inst["manifest"]
        out["installed"].update(commit=m.get("commit") or "", built=m.get("built") or "")
    if inst["refused"] or not out["candidate"]:
        return out
    old, new = inst["manifest"], candidate_manifest(root)
    if not isinstance(new, dict):
        out["candidate"] = None
        return out
    target = new["version"]
    d = direction_of(old.get("version"), target)
    same_build = d == "same" and old.get("commit") == new.get("commit")
    acts = diff(root, old, new)
    env = environment_plan(old.get("environment"), new.get("environment"), d, target)
    fmts = formats_plan(old, new, target)
    edited = [p for p, k in acts["write"] if k == "edited"] + \
             [p for p, k in acts["delete"] if k == "edited"]
    compiled = [p for p in edited if p.startswith(COMPILED)]
    edited = [p for p in edited if not p.startswith(COMPILED)]
    if d == "newer":
        said = "%s is newer than this %s (%s)." % (target, NAME, old.get("version"))
    elif d == "older":
        said = ("%s is OLDER than this %s (%s): installing it goes back."
                % (target, NAME, old.get("version")))
    elif same_build:
        said = ("%s is the version this %s already is, built from the same commit: installing it "
                "again puts every file of %s's back as the release has it." % (target, NAME, NAME))
    else:
        said = ("%s is the version this %s already is, but built from another commit (%s, where "
                "this one is %s): installing it replaces this build with that one."
                % (target, NAME, (new.get("commit") or "?")[:12], (old.get("commit") or "?")[:12]))
    out.update({
        "direction": d, "target": target, "said": said, "same_build": same_build,
        "incoming": {"version": target, "commit": new.get("commit") or "",
                     "built": new.get("built") or ""},
        "write": len(acts["write"]), "added": sum(1 for _p, k in acts["write"] if k == "new"),
        "delete": [p for p, _k in acts["delete"]], "edited": edited, "compiled": compiled,
        "foreign": [p for p, k in acts["write"] if k == "foreign"],
        "modes": len(acts["modes"]), "same": acts["same"],
        "environment": env, "formats": fmts,
        "needs_insist": bool(fmts["lowered"]),
    })
    # the person's own files this move gives back, [path, the version whose
    # update took it]: put back, gone with an update no longer kept, or held
    ret = returns(root, old, new)
    out.update({"back": [[p, to] for p, _j, to in ret["back"]], "gone": ret["gone"],
                "held": [[p, to] for p, _j, to in ret["held"]]})
    if env["blocked"]:
        out["refused"] = env["blocked"]
    return out


# ------------------------------------------------------------------ starting it
def running(root):
    """The id of an update that has not finished, or ""."""
    p = _read_json(work(root, "pending.json"))
    return (p or {}).get("job") or ""


def state(root):
    """How far the current or last update got (state.json), or {}."""
    return _read_json(work(root, "state.json"), {}) or {}


STEPS = (("stop", "Stopping %s" % NAME),
         ("content", "Copying the small files of your books, videos, decks and settings"),
         ("environment", "Adding what the new version needs to the environment"),
         ("backup", "Keeping a copy of %s's files as they are" % NAME),
         ("replace", "Replacing %s's files" % NAME),
         ("manifest", "Writing down what is installed"),
         ("guide", "Compiling the guide"),
         ("readers", "Building the readers"),
         ("start", "Starting %s again" % NAME))


def begin(root, insist=False, back_to="", server=None):
    """Write the job down for the helper -> the job.  Refused, in words,
    when the plan refuses, when nothing is waiting, when a data format would
    go down and the person has not insisted, or when an update is running."""
    p = plan(root)
    if p.get("refused"):
        raise Refused(p["refused"])
    if p.get("busy"):
        raise Refused("An update is running already.")
    if not p.get("candidate") or not p.get("target"):
        raise Refused("No version is waiting to be installed: check GitHub, or choose a zip, "
                      "first.")
    if p["needs_insist"] and not insist:
        raise Refused(p["formats"]["said"] + " Tick the box that says you understand, to go "
                      "back anyway.", insist=True)
    old_version = p["installed"]["version"]
    jid = base = "%s-%s-to-%s" % (time.strftime("%Y%m%d-%H%M%S"), old_version, p["target"])
    # A FOLDER OF ITS OWN, ALWAYS: up, down and up again inside one second
    # would otherwise land in the first update's folder, whose journal says
    # its steps are done and whose report says what IT took
    n = 2
    while os.path.exists(work(root, "jobs", jid)):
        jid, n = "%s-%d" % (base, n), n + 1
    jdir = work(root, "jobs", jid)
    os.makedirs(jdir, exist_ok=True)
    shutil.move(_incoming(root, "candidate.zip"), os.path.join(jdir, "release.zip"))
    new = candidate_manifest(root)
    _write_json(os.path.join(jdir, "manifest.json"), new)
    shutil.copy2(os.path.join(root, MANIFEST), os.path.join(jdir, "old-manifest.json"))
    cand = candidate(root) or {}
    job = {"job_format": JOB_FORMAT, "id": jid, "root": root, "made": time.time(),
           "from": old_version, "to": p["target"], "direction": p["direction"],
           "same_build": p["same_build"], "insist": bool(insist),
           "lowered": [x["name"] for x in p["formats"]["lowered"]],
           "formats_said": p["formats"]["said"],
           "environment": p["environment"],
           "zip_sha256": sha256_of(os.path.join(jdir, "release.zip")),
           "source": cand.get("source") or "", "back_to": _clean_page(back_to),
           "server": server or {}}
    _write_json(os.path.join(jdir, "job.json"), job)
    discard(root)
    # the helper is THIS file as this version has it, copied out of the way
    # of the files it replaces
    shutil.copy2(os.path.realpath(__file__), work(root, "helper.py"))
    _write_json(work(root, "pending.json"), {"job": jid})
    steps = [{"id": sid, "title": title, "state": "waiting", "detail": ""}
             for sid, title in STEPS if _step_applies(sid, job)]
    _write_json(work(root, "state.json"), {
        "id": jid, "phase": "stop", "from": job["from"], "to": job["to"],
        "direction": job["direction"], "steps": steps, "done": 0, "total": 0,
        "said": "%s is stopping, to be replaced by %s." % (NAME, job["to"]),
        "back_to": job["back_to"], "updated": time.time()})
    return job


def _step_applies(sid, job):
    if sid == "content":
        return bool(job.get("lowered"))
    if sid == "environment":
        return bool((job.get("environment") or {}).get("install"))
    return True


def _clean_page(page):
    """A path on this server, or "" -- never an address elsewhere."""
    page = str(page or "")
    if not page.startswith("/") or page.startswith("//") or "\\" in page or len(page) > 500 \
            or any(ord(c) < 33 for c in page):
        return ""
    return page


def undo_begin(root, job):
    """The server could not hand the job over: put the candidate back and
    forget the job, so that nothing half-started waits for the next start."""
    jdir = work(root, "jobs", job["id"])
    try:
        os.unlink(work(root, "pending.json"))
    except OSError:
        pass
    try:
        os.makedirs(_incoming(root), exist_ok=True)
        shutil.move(os.path.join(jdir, "release.zip"), _incoming(root, "candidate.zip"))
        shutil.copy2(os.path.join(jdir, "manifest.json"), _incoming(root, "candidate.manifest.json"))
        _write_json(_incoming(root, "candidate.json"), {
            "version": job["to"], "source": job.get("source") or "", "name": "",
            "sha256": job.get("zip_sha256") or "", "at": time.time()})
    except OSError:
        pass
    shutil.rmtree(jdir, ignore_errors=True)


def launch(root, job):
    """Start the helper as a process of its own, which outlives the server
    that starts it -> its pid."""
    helper = work(root, "helper.py")
    log = open(os.path.join(work(root, "jobs", job["id"]), "log.txt"), "ab")
    kw = {"cwd": root, "stdin": subprocess.DEVNULL, "stdout": log, "stderr": subprocess.STDOUT}
    if WIN:
        # no console of its own, and a process group of its own, so that the
        # console window of whatever started the server can close without it
        kw["creationflags"] = 0x00000008 | 0x00000200      # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    try:
        p = subprocess.Popen([sys.executable, helper, "run", root], **kw)
    finally:
        log.close()
    return p.pid


def run_helper(root):
    """What lib/launcher.py runs when its server left with LAUNCHER_EXIT:
    the helper, in the launcher's own window -> its exit status."""
    helper = work(root, "helper.py")
    if not os.path.isfile(helper) or not running(root):
        return 0
    return subprocess.call([sys.executable, helper, "run", root], cwd=root)


def finish_first(root, script=None):
    """Asked by serve.py and lib/launcher.py before they import anything else
    of Parseh's: an update that did not finish -- the helper killed half way,
    the power cut -- is finished, or undone, by the helper copy the update
    left, before a line of the half-replaced files runs.  When `script` (the
    file asking) changed under it, the new one is started in its place."""
    work_dir = os.path.join(root, WORK)
    if not os.path.isfile(os.path.join(work_dir, "pending.json")):
        return False
    # THE SERVER THE HELPER ITSELF STARTS is not a start after a crash: the
    # update is pending only until that server answers, and waiting here for
    # the helper that waits for this server would wait for ever
    if os.environ.pop("PARSEH_UPDATE_JOB", None) == running(root):
        return False
    helper = os.path.join(work_dir, "helper.py")
    if not os.path.isfile(helper):
        print("!! an update did not finish, and its helper is gone: %s starts as it stands"
              % NAME, flush=True)
        return False
    lock = _read_json(os.path.join(work_dir, "lock.json"), {}) or {}
    if _alive(lock.get("pid")) and lock.get("pid") != os.getpid():
        print("%s: an update is running (process %s); waiting for it to finish ..."
              % (NAME, lock.get("pid")), flush=True)
        end = time.time() + 30 * 60
        while (os.path.isfile(os.path.join(work_dir, "pending.json")) and _alive(lock.get("pid"))
               and time.time() < end):
            time.sleep(1)
        if not os.path.isfile(os.path.join(work_dir, "pending.json")):
            return True
    print("%s: an update did not finish; finishing it (or undoing it) first ..." % NAME, flush=True)
    before = sha256_of(script) if script else None
    subprocess.call([sys.executable, helper, "resume", root], cwd=root)
    if script and sha256_of(script) != before:
        # the file running this is not the one on the disk any more
        argv = list(getattr(sys, "orig_argv", None) or [sys.executable] + sys.argv)
        argv[0] = sys.executable
        print("%s: starting the %s now on the disk" % (NAME, os.path.basename(script)), flush=True)
        sys.stdout.flush()
        if WIN:
            sys.exit(subprocess.call(argv, cwd=os.getcwd()))
        os.execv(sys.executable, argv)
    return True


# ====================================================================== the helper
class Apply:
    """One update, applied by the helper: every step, the journal it keeps,
    the state it tells, and the undoing."""

    def __init__(self, root, job):
        self.root = root
        self.job = job
        self.dir = work(root, "jobs", job["id"])
        self.journal_path = os.path.join(self.dir, "journal.jsonl")
        self.backup = os.path.join(self.dir, "backup")
        self.content = os.path.join(self.dir, "content")
        self.new = _read_json(os.path.join(self.dir, "manifest.json")) or {}
        self.old = _read_json(os.path.join(self.dir, "old-manifest.json")) or {}
        self.st = state(root) if state(root).get("id") == job["id"] else {}
        if not self.st:
            self.st = {"id": job["id"], "from": job["from"], "to": job["to"],
                       "direction": job["direction"], "back_to": job.get("back_to") or "",
                       "steps": [{"id": s, "title": t, "state": "waiting", "detail": ""}
                                 for s, t in STEPS if _step_applies(s, job)]}
        self.report = _read_json(os.path.join(self.dir, "report.json")) or {
            "from": job["from"], "to": job["to"], "direction": job["direction"],
            "started": time.time(), "backup": self.backup, "content_copy": "",
            "environment": {"ran": False, "ok": True, "said": ""}, "post": [],
            "back_to": job.get("back_to") or ""}
        self._tick = 0.0
        self.lock_held = False
        self.status = None
        # a resume runs inside a start of Parseh, which serve.sh and the
        # launcher give twenty seconds to answer: its post-steps (every
        # reader of the shelf, perhaps) go to a process of their own
        self.defer_post = False
        # post-steps run after the update has finished leave its phase alone
        self.keep_phase = False

    # ---- telling
    def say(self, text):
        print(time.strftime("%H:%M:%S ") + text, flush=True)

    def tell(self, force=False, **kw):
        self.st.update(kw)
        self.st["updated"] = time.time()
        now = time.monotonic()
        if force or now - self._tick > 0.25:
            self._tick = now
            _write_json(work(self.root, "state.json"), self.st)

    def step(self, sid, st, detail=""):
        for s in self.st.get("steps", []):
            if s["id"] == sid:
                s["state"] = st
                if detail or st in ("running", "done"):
                    s["detail"] = detail
        title = dict(STEPS).get(sid, sid)
        if st == "running":
            kw = {"said": title + (": " + detail if detail else "") + " ..."}
            if not self.keep_phase:
                kw["phase"] = sid
            self.tell(force=True, **kw)
        else:
            self.tell(force=True)
        if detail and st != "running":
            self.say("%s: %s" % (title, detail))

    # ---- the journal
    def rec(self, **obj):
        with open(self.journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def records(self):
        out = []
        try:
            with open(self.journal_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue             # a line the kill cut short
        except OSError:
            pass
        return out

    def done_phases(self):
        return {r.get("done") for r in self.records() if r.get("done")}

    def lock(self):
        _write_json(work(self.root, "lock.json"), {"pid": os.getpid(), "job": self.job["id"]})
        self.lock_held = True

    def unlock(self):
        try:
            os.unlink(work(self.root, "lock.json"))
        except OSError:
            pass

    # ---- the steps, forward
    def wait_for_server(self):
        """The server stops by itself once it has answered; wait until its
        port is free and its process gone -- and end it where it will not."""
        srv = self.job.get("server") or {}
        pid = srv.get("pid")
        self.step("stop", "running")
        end = time.time() + 60
        while time.time() < end and _alive(pid) and pid != os.getpid():
            time.sleep(0.2)
        if _alive(pid) and pid != os.getpid():
            self.say("the server did not stop by itself within a minute: ending it")
            try:
                import signal
                os.kill(int(pid), signal.SIGTERM)
            except (OSError, ValueError):
                pass
            end = time.time() + 15
            while time.time() < end and _alive(pid):
                time.sleep(0.2)
            if _alive(pid):
                raise Refused("%s did not stop, so nothing was replaced." % NAME)
        self.step("stop", "done", "stopped")

    def copy_content(self):
        """The small files of the person's things, before a step back that
        lowers a data format writes anything."""
        self.step("content", "running")
        n = size = 0
        for top in CONTENT:
            base = _abs(self.root, top.rstrip("/"))
            for here, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if d not in ("__pycache__",)]
                for fn in files:
                    if os.path.splitext(fn)[1].lower() in MEDIA:
                        continue
                    src = os.path.join(here, fn)
                    rel = os.path.relpath(src, self.root)
                    dest = os.path.join(self.content, rel)
                    if os.path.isfile(dest):
                        continue
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    try:
                        shutil.copy2(src, dest + ".part")
                        os.replace(dest + ".part", dest)
                    except OSError as e:
                        why = plainly(e)[0].rstrip(".")
                        raise Refused("The copy of your small files could not be made (%s%s), "
                                      "so nothing was replaced." % (why[:1].lower(), why[1:]),
                                      detail=_technical(e))
                    n += 1
                    size += os.path.getsize(dest)
        self.report["content_copy"] = self.content
        self.report["content_files"] = n
        self.rec(done="content")
        self.step("content", "done", "%d files, %s, kept in %s" % (n, size_said(size), self.content))

    def environment(self):
        env = self.job.get("environment") or {}
        todo = env.get("install") or []
        self.step("environment", "running", ", ".join(i["line"] for i in todo))
        ok, said = self._environment(todo)
        self.report["environment"] = {"ran": True, "ok": ok, "said": said}
        if not ok:
            self.step("environment", "failed", said)
            raise Refused("The environment could not be given what %s needs (%s), so none of "
                          "%s's files was replaced." % (self.job["to"], said, NAME))
        self.rec(done="environment")
        self.step("environment", "done", said)

    def _environment(self, todo):
        """Install `todo` into Parseh's environment -> (ok, words)."""
        _lib(self.root)
        try:
            import runtime
        except Exception as e:                           # noqa: BLE001 -- any reason at all
            return False, "lib/runtime.py could not be read: %s" % e
        prefix, python = runtime.find_env()
        if not prefix:
            return True, ("%s runs with this computer's own Python and has no environment of "
                          "its own, so nothing was installed; %s asks for %s"
                          % (NAME, self.job["to"], ", ".join(i["line"] for i in todo)))
        report = runtime.Report(out=sys.stdout)
        pip = [i["line"] for i in todo if i["kind"] == "pip"]
        conda = [i["line"] for i in todo if i["kind"] == "conda"]
        ok = True
        if conda:
            c = runtime._conda()
            if c and os.path.realpath(prefix) != os.path.realpath(runtime.LOCAL_ENV):
                ok = runtime.run([c, "install", "-y", "-p", prefix, "-c", "conda-forge"] + conda,
                                 report) == 0 and ok
            else:
                try:
                    mm = runtime.get_micromamba(report)
                except Exception as e:                   # noqa: BLE001 -- the network, most likely
                    return False, "micromamba could not be downloaded: %s" % e
                ok = runtime.run([mm, "install", "-y", "-r", runtime.MAMBA_ROOT, "-p", prefix,
                                  "-c", "conda-forge"] + conda, report,
                                 env=dict(os.environ, MAMBA_ROOT_PREFIX=runtime.MAMBA_ROOT)) == 0 \
                    and ok
        if pip:
            ok = runtime.run([python, "-m", "pip", "install"] + pip, report,
                             env=runtime.environ_for(prefix)) == 0 and ok
        return ok, ("installed %s" % ", ".join(conda + pip) if ok
                    else "installing %s failed; the log says why" % ", ".join(conda + pip))

    def actions(self):
        """The file-by-file plan, worked out ONCE, before the first file is
        backed up, and kept: a resumed update must not take a file it has
        already written for one that was changed by hand."""
        path = os.path.join(self.dir, "actions.json")
        acts = _read_json(path)
        if not isinstance(acts, dict):
            acts = diff(self.root, self.old, self.new)
            # and the person's own files it gives back, found while every
            # backup they could come from is still there
            acts.update(returns(self.root, self.old, self.new, current=self.job["id"]))
            _write_json(path, acts)
        return acts

    def backup_files(self, acts):
        self.step("backup", "running")
        rels = [p for p, k in acts["write"] if k != "new"] + [p for p, _k in acts["delete"]]
        rels += acts["modes"]
        n = 0
        for rel in rels:
            src = _abs(self.root, rel)
            dest = os.path.join(self.backup, *rel.split("/"))
            if os.path.isfile(dest) or not os.path.isfile(src):
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest + ".part")
            os.replace(dest + ".part", dest)
            n += 1
        # THE FOLDER IS MADE HERE TOO, not only beside a file copied into it:
        # the same release installed again, over files that are all as it
        # ships them, backs up no file at all, and the old manifest -- what
        # an undo reads -- still needs somewhere to go.
        os.makedirs(self.backup, exist_ok=True)
        man = os.path.join(self.backup, MANIFEST)
        if not os.path.isfile(man):
            shutil.copy2(os.path.join(self.dir, "old-manifest.json"), man + ".part")
            os.replace(man + ".part", man)
        self.rec(done="backup")
        self.step("backup", "done", "%d files, in %s" % (n, self.backup))

    def replace(self, acts):
        """Delete, then write: a folder a file is replacing is emptied first.
        Last, the person's own files this version no longer ships a file in
        place of go back (returns)."""
        writes, deletes = acts["write"], acts["delete"]
        back = acts.get("back") or []
        total = len(writes) + len(deletes) + len(acts["modes"]) + len(back)
        self.step("replace", "running", "%d files" % total)
        delay = float(os.environ.get("PARSEH_UPDATE_TEST_DELAY") or 0)
        files = self.new.get("files") or {}
        done = 0
        for rel, _kind in deletes:
            path = _abs(self.root, rel)
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            self._prune(os.path.dirname(path))
            done += 1
            self.tell(done=done, total=total, said="Replacing %s's files: %d of %d"
                      % (NAME, done, total))
        with zipfile.ZipFile(os.path.join(self.dir, "release.zip")) as z:
            prefix = _prefix(z)
            for rel, kind in writes:
                want = files[rel]
                path = _abs(self.root, rel)
                if sha256_of(path) == want["sha256"]:
                    done += 1                             # written before a kill
                    self.tell(done=done, total=total, said="Replacing %s's files: %d of %d"
                              % (NAME, done, total))
                    continue
                data = z.read(prefix + rel)
                if hashlib.sha256(data).hexdigest() != want["sha256"]:
                    raise Refused("%s in the release's zip is not the file its list of files "
                                  "names: the zip is damaged." % rel)
                if kind == "new":
                    self.rec(created=rel)
                self._put(path, data, want.get("mode"))
                done += 1
                self.tell(done=done, total=total, said="Replacing %s's files: %d of %d"
                          % (NAME, done, total))
                if delay:
                    time.sleep(delay)
        for rel in acts["modes"]:
            self._chmod(_abs(self.root, rel), files[rel].get("mode"))
            done += 1
        # THE PERSON'S OWN FILES, GIVEN BACK: each copied whole from the
        # backup of the update that took it, with the mode and the time it
        # had -- it is theirs, so nothing of a release's applies to it.  It
        # is journalled as created: an undo takes it away again where this
        # update found nothing there, and otherwise puts back what it found
        # (this update's own backup holds that).
        for rel, jid, _to in back:
            src = os.path.join(work(self.root, "jobs", jid, "backup"), *rel.split("/"))
            path = _abs(self.root, rel)
            want = sha256_of(src)
            if want is None or sha256_of(path) != want:     # (a copy gone since: copy2 says so)
                self.rec(created=rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                shutil.copy2(src, path + ".parseh-new")
                _replace(path + ".parseh-new", path)
            done += 1
            self.tell(done=done, total=total, said="Putting back a file of yours: %d of %d"
                      % (done, total))
        self.rec(done="replace")
        self.tell(done=total, total=total)
        self.step("replace", "done", "%d written, %d deleted%s" % (
            len(writes), len(deletes), ", %d of yours put back" % len(back) if back else ""))

    def _put(self, path, data, mode):
        d = os.path.dirname(path)
        # a file where the new version needs a folder is somebody's (a file
        # of Parseh's there was deleted above, as retired): it is never
        # removed to make room, and makedirs refusing undoes the update
        os.makedirs(d, exist_ok=True)
        if os.path.isdir(path) and not os.path.islink(path):
            raise Refused("%s is a folder where %s's new version has a file; it was left alone, "
                          "and the update undone." % (path, NAME))
        tmp = path + ".parseh-new"
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        self._chmod(tmp, mode)
        _replace(tmp, path)

    def _chmod(self, path, mode):
        """The release's mode, as far as this computer's umask lets it: a
        file written here is made as any other file the person makes."""
        if WIN or not mode:
            return
        try:
            mask = os.umask(0)
            os.umask(mask)
            want = int(mode, 8)
            os.chmod(path, (want & ~mask) | (want & 0o100))
        except (OSError, ValueError):
            pass

    def _prune(self, folder):
        """Folders a deletion left empty go too, up to the root and never it."""
        root = os.path.realpath(self.root)
        folder = os.path.realpath(folder)
        while folder.startswith(root + os.sep) and folder != root:
            try:
                os.rmdir(folder)
            except OSError:
                return
            folder = os.path.dirname(folder)

    def write_manifest(self):
        self.step("manifest", "running")
        with zipfile.ZipFile(os.path.join(self.dir, "release.zip")) as z:
            data = z.read(_prefix(z) + MANIFEST)
        tmp = os.path.join(self.root, MANIFEST + ".parseh-new")
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        _replace(tmp, os.path.join(self.root, MANIFEST))
        self.rec(done="manifest")
        self.step("manifest", "done", "%s %s" % (NAME, self.job["to"]))

    def forward(self):
        """Every step that changes the install, each skipped when the journal
        says it is done already."""
        done = self.done_phases()
        if self.job.get("lowered") and "content" not in done:
            self.copy_content()
        if (self.job.get("environment") or {}).get("install") and "environment" not in done:
            self.environment()
        acts = self.actions()
        self.report.update({
            "written": len(acts["write"]),
            "added": [p for p, k in acts["write"] if k == "new"],
            "replaced": sum(1 for _p, k in acts["write"] if k == "replace"),
            "edited": [p for p, k in acts["write"]
                       if k == "edited" and not p.startswith(COMPILED)],
            "compiled": [p for p, k in acts["write"] + acts["delete"]
                         if k == "edited" and p.startswith(COMPILED)],
            "foreign": [p for p, k in acts["write"] if k == "foreign"],
            "deleted": [p for p, k in acts["delete"] if k == "retired"],
            "deleted_edited": [p for p, k in acts["delete"]
                               if k == "edited" and not p.startswith(COMPILED)],
            "modes": len(acts["modes"]), "unchanged": acts["same"],
            # the person's own files (returns), each with the version whose
            # update took it -- and, held, where its copy is
            "put_back": [[p, to] for p, _j, to in acts.get("back") or []],
            "put_back_gone": [[p, to] for p, to in acts.get("gone") or []],
            "put_back_held": [[p, to, os.path.join(work(self.root, "jobs", j, "backup"),
                                                   *p.split("/"))]
                              for p, j, to in acts.get("held") or []]})
        self.save_report()
        self.rec(started="files")
        if "backup" not in done:
            self.backup_files(acts)
        if "replace" not in done:
            self.replace(acts)
        if "manifest" not in done:
            self.write_manifest()

    # ---- the post-steps
    def post(self, force=False):
        """What the installer does after it has put the files in: compile the
        guide, build what needs building.  A step that fails is a warning --
        the guide's own page compiles it again, a reader can be built from
        its card -- and never a reason to undo the update.  `force` runs
        them again after an undo, from the files put back."""
        if "post" in self.done_phases() and not force:
            return
        py = self._python()
        steps = []
        guide = _abs(self.root, "html-guide/build.py")
        if os.path.isfile(guide):
            steps.append(("guide", [py, guide]))
        if WIN or not shutil.which("sh"):
            steps.append(("readers", [py, _abs(self.root, "lib/launcher.py"), "readers"]))
        else:
            steps.append(("readers", ["sh", _abs(self.root, "build.sh"), "--html"]))
        self.report["post"] = []
        for sid, cmd in steps:
            self.step(sid, "running")
            ok, tail = self._run(cmd)
            said = "done" if ok else "did not finish: %s" % tail
            self.report["post"].append({"step": dict(STEPS)[sid], "ok": ok, "said": said})
            self.step(sid, "done" if ok else "failed", said)
        self.save_report()
        self.rec(done="post")

    def post_later(self):
        """The post-steps in a process of their own, which outlives this one
        and tells the page as it goes (helper `post`)."""
        for sid in ("guide", "readers"):
            self.step(sid, "running", "while %s starts" % NAME)
        kw = {"cwd": self.root, "stdin": subprocess.DEVNULL}
        log = open(os.path.join(self.dir, "log.txt"), "ab")
        kw.update(stdout=log, stderr=subprocess.STDOUT)
        if WIN:
            kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000
        else:
            kw["start_new_session"] = True
        try:
            subprocess.Popen([sys.executable, work(self.root, "helper.py"), "post", self.root,
                              self.job["id"]], **kw)
            self.report["post"] = [{"step": dict(STEPS)[sid], "ok": True,
                                    "said": "running while %s starts" % NAME}
                                   for sid in ("guide", "readers")]
        except OSError as e:
            self.report["post"] = [{"step": "the post-steps", "ok": False, "said": str(e)}]
        finally:
            log.close()

    def _python(self):
        """The environment's Python where there is one, else this one."""
        _lib(self.root)
        try:
            import runtime
            return runtime.find_env()[1] or sys.executable
        except Exception:                                # noqa: BLE001
            return sys.executable

    def _run(self, cmd):
        # the job's name goes with it: lib/launcher.py (the readers, on
        # Windows) asks finish_first() first thing, and must not wait for
        # the helper that is waiting for it
        kw = {"cwd": self.root, "stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE,
              "stderr": subprocess.STDOUT, "text": True, "encoding": "utf-8", "errors": "replace",
              "env": dict(os.environ, PARSEH_UPDATE_JOB=self.job["id"])}
        if WIN:
            kw["creationflags"] = 0x08000000             # CREATE_NO_WINDOW: no console flashing up
        try:
            p = subprocess.Popen(cmd, **kw)
        except OSError as e:
            return False, str(e)
        last = []
        for line in p.stdout:
            line = line.rstrip()
            if line.strip():
                print("    " + line, flush=True)
                last = (last + [line])[-3:]
        return p.wait() == 0, " / ".join(last)

    # ---- undoing
    def rollback(self, why, detail=""):
        """Put back every file the update wrote or deleted, from the backup,
        and take away every file it created -- then the old manifest.  `why`
        is said in words, `detail` is Python's line behind them (plainly)."""
        self.say("undoing the update: %s%s" % (why, " (%s)" % detail if detail else ""))
        self.rec(rollback=why)
        created = [r["created"] for r in self.records() if r.get("created")]
        for rel in created:
            if guard(rel):
                continue
            path = _abs(self.root, rel)
            if not os.path.isfile(os.path.join(self.backup, *rel.split("/"))):
                try:
                    os.unlink(path)
                except OSError:
                    pass
                self._prune(os.path.dirname(path))
        n = 0
        if os.path.isdir(self.backup):
            for here, _dirs, files in os.walk(self.backup):
                for fn in files:
                    if fn.endswith(".part"):
                        continue
                    src = os.path.join(here, fn)
                    rel = os.path.relpath(src, self.backup).replace(os.sep, "/")
                    if rel != MANIFEST and guard(rel):
                        continue
                    dest = _abs(self.root, rel)
                    if sha256_of(dest) == sha256_of(src) and (WIN or _mode(dest) == _mode(src)):
                        continue
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    shutil.copy2(src, dest + ".parseh-new")
                    _replace(dest + ".parseh-new", dest)
                    n += 1
        man = os.path.join(self.backup, MANIFEST)
        if not os.path.isfile(man) and os.path.isfile(os.path.join(self.dir, "old-manifest.json")):
            shutil.copy2(os.path.join(self.dir, "old-manifest.json"), os.path.join(self.root, MANIFEST))
        self.rec(done="rollback")
        self.report.update({"rolled_back": True, "error": why, "error_detail": detail,
                            "restored": n})
        self.save_report()
        self.say("undone: %d files put back, %d taken away" % (n, len(created)))
        if "post" in self.done_phases():
            # the guide and the readers were made by the version just taken
            # away: made again, by the one put back
            if self.defer_post:
                self.post_later()
            else:
                self.post(force=True)

    # ---- the status server, while the real one is down
    def status_up(self):
        srv = self.job.get("server") or {}
        if not srv.get("port"):
            return
        host = srv.get("host") or "127.0.0.1"
        if host in ("0.0.0.0", "::"):
            host = "127.0.0.1"                           # the computer alone
        try:
            self.status = _StatusServer(self, host, int(srv["port"]), srv.get("scheme"),
                                        srv.get("cert"))
        except (OSError, ValueError) as e:
            self.say("the progress page could not be served on port %s: %s" % (srv["port"], e))
            self.status = None

    def status_down(self):
        if self.status:
            self.status.stop()
            self.status = None

    # ---- starting again
    def start_server(self):
        """Start the server exactly as the old one was started -> (ok, why,
        detail): why it did not, in words, and the end of its log or the
        system's own words beneath them."""
        srv = self.job.get("server") or {}
        if srv.get("restart") == "launcher" or not srv.get("command"):
            return True, "", ""
        self.step("start", "running")
        cmd = [srv.get("exe") or sys.executable] + list(srv["command"][1:])
        kw = {"cwd": self.root, "stdin": subprocess.DEVNULL,
              "env": dict(os.environ, PARSEH_UPDATE_JOB=self.job["id"])}
        log = None
        if WIN:
            kw["creationflags"] = 0x00000010                  # CREATE_NEW_CONSOLE: its log window
        else:
            log = open(os.path.join(self.root, "serve.log"), "ab")
            kw.update(stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            p = subprocess.Popen(cmd, **kw)
        except OSError as e:
            return False, "it could not be started", _technical(e)
        finally:
            if log:
                log.close()
        if srv.get("pidfile"):
            try:
                with open(srv["pidfile"], "w", encoding="ascii") as f:
                    f.write("%d\n" % p.pid)
            except OSError:
                pass
        end = time.time() + 90
        while time.time() < end:
            if p.poll() is not None:
                return False, "it stopped as soon as it started", _log_tail(self.root)
            if _answers(srv):
                self.report["server_pid"] = p.pid
                self.step("start", "done", "running again, process %d" % p.pid)
                return True, "", ""
            time.sleep(0.3)
        try:
            p.terminate()
        except OSError:
            pass
        return False, "it did not answer within a minute and a half", _log_tail(self.root)

    # ---- ending
    def save_report(self):
        _write_json(os.path.join(self.dir, "report.json"), self.report)

    def failed(self, e):
        """The failure `e`, in the step that was running -> (words, detail);
        that step is marked failed, with Python's line under it (plainly)."""
        sid = self.st.get("phase") or ""
        title = dict(STEPS).get(sid, "")
        words, detail = plainly(e, title[:1].lower() + title[1:])
        if title:
            self.step(sid, "failed", detail or words)
        return words, detail

    def finish(self, ok, error="", detail=""):
        """`error` says in words why it did not happen; `detail` is the
        technical line the page shows smaller beneath them."""
        self.report.update({"ok": ok, "finished": time.time(),
                            "seconds": round(time.time() - self.report.get("started", time.time()), 1)})
        if error:
            self.report["error"] = error
        if detail:
            self.report["error_detail"] = detail
        self.save_report()
        phase = "done" if ok else ("rolled-back" if self.report.get("rolled_back") else "failed")
        self.rec(done="finished")
        try:
            os.unlink(work(self.root, "pending.json"))
        except OSError:
            pass
        said = ("%s is now %s." % (NAME, self.job["to"]) if ok else
                ("The update did not happen. %s" % (error or self.report.get("error") or "")).strip())
        self.tell(force=True, phase=phase, said=said, report=self.report)
        self.unlock()
        _prune_jobs(self.root, keep=self.job["id"])


def _prefix(z):
    names = [n for n in z.namelist() if n.count("/") == 1 and n.endswith("/" + MANIFEST)]
    if len(names) != 1:
        raise Refused("the release's zip has no %s" % MANIFEST)
    return names[0][:-len(MANIFEST)]


def _answers(srv):
    """Does a server answer on the address the old one had?"""
    import ssl
    host = srv.get("host") or "127.0.0.1"
    if host in ("0.0.0.0", "::", ""):
        host = "127.0.0.1"
    url = "%s://%s:%s/settings/api/ping" % (srv.get("scheme") or "https", host, srv.get("port"))
    try:
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(url, timeout=2, context=ctx) as r:
            return r.status == 200 and b'"updating"' not in r.read(2000)
    except Exception:                                    # noqa: BLE001 -- not answering, however
        return False


def _log_tail(root, n=6):
    try:
        with open(os.path.join(root, "serve.log"), encoding="utf-8", errors="replace") as f:
            lines = [ln.rstrip() for ln in f.readlines()[-n:] if ln.strip()]
        return " / ".join(lines) or "its log says nothing"
    except OSError:
        return "no log"


def _prune_jobs(root, keep):
    """Keep the last KEEP_JOBS jobs -- their backups are the way back.

    A JOB REMOVED WHILE IT STILL HOLDS A FILE OF THE PERSON'S -- one it took,
    that no later update has given back -- leaves that path in taken.json
    first (yours_taken over the jobs going, and what taken.json said
    before), so that the day a version stops shipping that name the report
    says plainly that the person's copy is gone, instead of saying nothing.
    What the jobs kept settle is never written there: they may yet be
    undone."""
    base = work(root, "jobs")
    ids = _jobs(root)
    kept = [keep] + [j for j in ids if j != keep][:KEEP_JOBS - 1]
    going = [j for j in ids if j not in kept]
    if not going:
        return
    held = yours_taken(root, going)
    try:
        _write_json(work(root, "taken.json"), {"format": TAKEN_FORMAT, "gone": {
            rel: {"from": e["from"], "to": e["to"], "at": e["at"]}
            for rel, e in sorted(held.items())}})
    except OSError:
        return                  # nothing removed, then: the next update tries again
    for n in going:
        shutil.rmtree(os.path.join(base, n), ignore_errors=True)


class _StatusServer:
    """How far the update has got, on the server's own port, while the
    server is down: the state for the page that started it, and a page that
    comes back by itself for any other address."""

    def __init__(self, apply, host, port, scheme, cert):
        import http.server
        import ssl
        updater = apply

        class Handler(http.server.BaseHTTPRequestHandler):
            server_version = "%s-update" % NAME

            def log_message(self, *_a):
                pass

            def _send(self, code, ctype, body, extra=()):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                for k, v in extra:
                    self.send_header(k, v)
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

            def do_GET(self):
                path = self.path.split("?", 1)[0]
                mine = self.client_address[0] in ("127.0.0.1", "::1", "::ffff:127.0.0.1")
                st = updater.st
                if path == "/settings/api/update/state" and mine:
                    # the shape the server answers this address in
                    # (lib/updatepage.py state_json), saying who answers
                    return self._send(200, "application/json; charset=utf-8", json.dumps(
                        {"ok": True, "helper": True, "update": st}, ensure_ascii=False).encode("utf-8"))
                if path == "/settings/api/ping":
                    return self._send(200, "application/json", b'{"ok": true, "updating": true}')
                said = _html(st.get("said") or "")
                page = ("<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport "
                        "content='width=device-width,initial-scale=1'><meta http-equiv=refresh "
                        "content=3><title>%s is being updated</title><style>body{font:17px/1.5 "
                        "system-ui,sans-serif;max-width:34rem;margin:3rem auto;padding:0 1.2rem;"
                        "color-scheme:light dark}p.s{opacity:.75}</style><h1>%s is being updated"
                        "</h1><p>From %s to %s.</p><p class=s>%s</p><p>This page comes back by "
                        "itself.</p></html>" % (NAME, NAME, _html(updater.job["from"]),
                                                _html(updater.job["to"]), said)).encode("utf-8")
                return self._send(503, "text/html; charset=utf-8", page, (("Retry-After", "3"),))

            do_HEAD = do_GET

            def do_POST(self):
                self._send(503, "application/json; charset=utf-8",
                           json.dumps({"ok": False, "error": "%s is being updated; try again in "
                                       "a moment." % NAME}).encode("utf-8"),
                           (("Retry-After", "3"),))

        class Server(http.server.ThreadingHTTPServer):
            # Windows' SO_REUSEADDR would let this bind a port the old
            # server still holds; elsewhere it only skips TIME_WAIT
            allow_reuse_address = not WIN
            daemon_threads = True

        end = time.time() + 20
        while True:
            try:
                self.httpd = Server((host, port), Handler)
                break
            except OSError:
                if time.time() > end:
                    raise
                time.sleep(0.25)
        if scheme == "https" and cert:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(cert[0], cert[1])
            self.httpd.socket = ctx.wrap_socket(self.httpd.socket, server_side=True,
                                                do_handshake_on_connect=False)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except OSError:
            pass


def _html(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


# ------------------------------------------------------------------ the helper's commands
def _pending_job(root):
    jid = running(root)
    if not jid:
        return None
    job = _read_json(work(root, "jobs", jid, "job.json"))
    if not isinstance(job, dict) or job.get("job_format") != JOB_FORMAT:
        return None
    return job


def _can_go_on(a):
    """Carrying an unfinished update on needs the zip it installs, whole."""
    z = os.path.join(a.dir, "release.zip")
    return os.path.isfile(z) and sha256_of(z) == a.job.get("zip_sha256") and bool(a.new)


def helper_run(root):
    """The helper, from the start: the server has been asked to stop."""
    job = _pending_job(root)
    if not job:
        print("no update is waiting", flush=True)
        return 0
    a = Apply(root, job)
    a.lock()
    a.say("updating %s at %s from %s to %s (%s)" % (NAME, root, job["from"], job["to"],
                                                  job["direction"]))
    try:
        a.wait_for_server()
    except Refused as e:
        a.finish(False, *plainly(e))
        return 1
    a.status_up()
    ok, error, detail = True, "", ""
    try:
        a.forward()
    except Exception as e:                               # noqa: BLE001 -- any failure is undone
        ok = False
        error, detail = a.failed(e)
        a.rollback(error, detail)
    if ok:
        a.post()
    a.status_down()
    started, why, detail2 = a.start_server()
    if ok and not started:
        error, detail = "%s %s did not start: %s." % (NAME, job["to"], why), detail2
        a.step("start", "failed", detail2 or why)
        a.rollback(error, detail)
        ok = False
        started, why2, detail2 = a.start_server()
        if not started:
            a.report["start_error"] = "%s%s" % (why2, " (%s)" % detail2 if detail2 else "")
    a.finish(ok, error, detail)
    return 0 if ok else 1


def helper_resume(root):
    """An update the helper did not finish: carried on where its zip is
    still whole, undone from the backup where it is not.  The caller starts
    the server afterwards (serve.py, lib/launcher.py)."""
    job = _pending_job(root)
    if not job:
        try:
            os.unlink(work(root, "pending.json"))
        except OSError:
            pass
        return 0
    a = Apply(root, job)
    a.lock()
    a.defer_post = True
    done = a.done_phases()
    a.say("resuming the update from %s to %s (done so far: %s)"
          % (job["from"], job["to"], ", ".join(sorted(p for p in done if p)) or "nothing"))
    ok, error, detail = True, "", ""
    rolling = any(r.get("rollback") for r in a.records())
    try:
        if rolling or "rollback" in done:
            ok, error = False, ("It was being undone when %s stopped, and the undoing has now "
                                "been finished." % NAME)
            a.rollback(error)
        elif "manifest" in done:
            pass
        elif _can_go_on(a):
            a.forward()
        else:
            ok, error = False, ("It was interrupted, and the release's zip it was installing from "
                                "is gone or damaged, so it was undone.")
            a.rollback(error)
    except Exception as e:                               # noqa: BLE001
        ok = False
        error, detail = a.failed(e)
        a.rollback(error, detail)
    if ok and "post" not in a.done_phases():
        a.post_later()
    a.report["resumed"] = True
    a.finish(ok, error, detail)
    return 0 if ok else 1


def helper_post(root, jid):
    """The post-steps of the update `jid`, on their own: after a resume,
    while the server that asked for it starts."""
    job = _read_json(work(root, "jobs", jid, "job.json"))
    if not isinstance(job, dict):
        return 1
    # the resume that started this finishes a moment later: its last word
    # on the state goes first, and this one's after it
    end = time.time() + 60
    while running(root) == jid and time.time() < end:
        time.sleep(0.2)
    a = Apply(root, job)
    a.keep_phase = True
    a.post(force=True)
    a.tell(force=True, report=a.report, said="%s is now %s." % (NAME, job["to"])
           if a.st.get("phase") == "done" else a.st.get("said", ""))
    return 0


def helper_rollback(root):
    """Undo the last update from its backup (lib/launcher.py, when the new
    version did not start in its window)."""
    st = state(root)
    jid = st.get("id")
    job = _read_json(work(root, "jobs", jid or "-", "job.json")) if jid else None
    if not isinstance(job, dict):
        print("no update to undo", flush=True)
        return 1
    a = Apply(root, job)
    a.rollback("%s %s did not start." % (NAME, job["to"]))
    a.finish(False, "%s %s did not start, so %s was put back." % (NAME, job["to"], job["from"]))
    return 0


def main(argv):
    if len(argv) < 2 or argv[0] not in ("run", "resume", "rollback", "post"):
        print(__doc__.split("\n\n")[0])
        return 2
    root = os.path.realpath(argv[1])
    try:
        os.chdir(root)
    except OSError:
        pass
    if argv[0] == "post":
        return helper_post(root, argv[2] if len(argv) > 2 else state(root).get("id") or "")
    return {"run": helper_run, "resume": helper_resume, "rollback": helper_rollback}[argv[0]](root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
