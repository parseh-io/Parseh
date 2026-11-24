# SPDX-License-Identifier: GPL-3.0-or-later
"""A personal store that cannot be read is never written over (TO-DO §2.29).

The person's own JSON stores in config/ -- the settings and reading places
(lib/prefs.py), who may reach Parseh (lib/network.py), their prompts
(lib/prompts.py), the analyzers' choice, the LaTeX themes, speech to text's
choice, the likelihood scoring's -- each read a file that does not parse as
EMPTY, which is right for a reader (a page must still open), and then wrote
their next save over it, which is not: every reading place, every prompt, every
device let in went with one save, without a word.

So every such store writes through `write_json` here, which, BEFORE it moves
the new file into place, looks at the one it would replace: when that one is
there and does not parse (or parses to something the store cannot be -- `ok`),
it is SET ASIDE under a dated name beside it,

    config/prefs.json.damaged-20261122-101500

never deleted, never overwritten, and the new file starts the store fresh.
What was set aside is found again by its name (`found`), which is how the hub
says so, in plain words, until somebody presses "I have read this" (`seen`):
the names that were read are kept in `damaged-seen.json` in the same folder,
and the files themselves stay where they are, for the person to open.

The write itself is whole or nothing, and DURABLE: a temporary file of its own
(process, thread-safe counter), flushed and fsync'd before `os.replace`, and the
folder fsync'd after where the platform allows (lib/updater.py's way) -- a power
cut leaves the old file or the new one, never an empty one.
"""
import itertools
import json
import os
import re
import threading
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import synctouch                                               # noqa: E402

SUFFIX = ".damaged-"
STAMP = "%Y%m%d-%H%M%S"
SEEN = "damaged-seen.json"
# what a set-aside file is called: the store's name, the suffix, the stamp,
# and -2, -3 ... when two were set aside in one second
NAME_RE = re.compile(r"^(?P<store>.+\.json)\.damaged-(?P<at>\d{8}-\d{6})(?:-\d+)?$")

_SEQ = itertools.count(1)
# the file each store last wrote or found readable, by (size, mtime): a store
# written a hundred times a minute (the reading place) is parsed again only
# when something else has changed it
_GOOD = {}
_LOCK = threading.Lock()


def _stat_key(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns)


def damaged(path, ok=None):
    """True when there is a file at `path` and it is not a store: it does not
    decode, does not parse, or parses to something `ok` refuses.  A file that
    is not there is not damaged; one that cannot be opened at all (a
    permission) is left to the write, which will fail on it in words."""
    key = _stat_key(path)
    if key is None:
        return False
    with _LOCK:
        if _GOOD.get(path) == key:
            return False
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return False
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):
        return True
    if ok is not None and not ok(doc):
        return True
    with _LOCK:
        _GOOD[path] = key
    return False


def set_aside(path, ok=None):
    """Move a damaged store out of the way, under a dated name beside it ->
    that name, or None when there was nothing to set aside."""
    if not damaged(path, ok):
        return None
    base = "%s%s%s" % (path, SUFFIX, time.strftime(STAMP))
    aside, n = base, 2
    while os.path.exists(aside):
        aside, n = "%s-%d" % (base, n), n + 1
    os.replace(path, aside)
    print("!! %s could not be read: it is kept as %s, and the store starts fresh"
          % (path, os.path.basename(aside)), flush=True)
    return aside


def write_text(path, text, ok=None, private=False):
    """`text` as the whole of `path`: through a temporary file of this write's
    own, fsync'd, after a damaged file there has been set aside."""
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    tmp = "%s.%d.%d.tmp" % (path, os.getpid(), next(_SEQ))
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        if private:
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
        set_aside(path, ok)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    _sync_dir(folder)
    key = _stat_key(path)
    with _LOCK:
        _GOOD[path] = key
    # the change log's hint (lib/synctouch.py: one set.add; docs/sync.md)
    synctouch.touch(path)


def write_json(path, doc, ok=None, private=False, indent=1, sort_keys=False):
    write_text(path, json.dumps(doc, ensure_ascii=False, indent=indent, sort_keys=sort_keys)
               + "\n", ok=ok, private=private)


def _sync_dir(folder):
    # the rename is in the folder's own record: on POSIX, fsync the folder
    # too, or a crash may remember the old name.  Windows has no such call.
    if os.name == "nt":
        return
    try:
        fd = os.open(folder, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


# ------------------------------------------------------------------ saying so
def _seen(folder):
    try:
        with open(os.path.join(folder, SEEN), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return set()
    names = doc.get("seen") if isinstance(doc, dict) else None
    return set(str(n) for n in names) if isinstance(names, list) else set()


def found(folders, all_=False):
    """Every store set aside in these folders and not yet marked as read ->
    [{"name", "store", "folder", "path", "at"}], oldest first.  `all_` lists
    the read ones as well."""
    out, done = [], set()
    for folder in folders:
        folder = os.path.abspath(folder)
        if folder in done:
            continue
        done.add(folder)
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        seen = set() if all_ else _seen(folder)
        for name in names:
            m = NAME_RE.match(name)
            if not m or name in seen:
                continue
            at = m.group("at")
            out.append({"name": name, "store": m.group("store"), "folder": folder,
                        "path": os.path.join(folder, name),
                        "at": "%s-%s-%s %s:%s:%s" % (at[:4], at[4:6], at[6:8],
                                                     at[9:11], at[11:13], at[13:15])})
    out.sort(key=lambda r: (r["at"], r["name"]))
    return out


def seen(folders, names):
    """Mark these set-aside names as read in whichever of the folders holds
    them -> how many were marked.  The files stay."""
    marked = 0
    for folder in set(os.path.abspath(f) for f in folders):
        here = [n for n in names if NAME_RE.match(str(n))
                and os.path.exists(os.path.join(folder, str(n)))]
        if not here:
            continue
        have = _seen(folder)
        have.update(here)
        write_json(os.path.join(folder, SEEN), {"seen": sorted(have)})
        marked += len(here)
    return marked


# what each store is, for the sentence on the hub
WHAT = {
    "prefs.json": "your reading places, the settings that follow you between devices "
                  "and the chunks flagged to review later",
    "network.json": "who may reach Parseh: the networks, the port and the devices let in",
    "prompts.json": "your own prompts",
    "analysis.json": "where the linguistic analyzers are used",
    "latex.json": "your LaTeX themes",
    "speech.json": "the speech-to-text model chosen for each language",
    "lm-likelihood.json": "the likelihood scoring's setting",
}
