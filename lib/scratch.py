# SPDX-License-Identifier: GPL-3.0-or-later
"""Where Parseh stages a temporary file: `.tmp/` inside its own folder, never the system's temp folder.

WHY NOT /tmp.  A backup of everything, a shelf of videos, a book downloaded with its recording, an upload too big to
hold: each is written to a file first and sent or read from there, and each can be gigabytes.  The system's temp
folder is often a small RAM-backed tmpfs (on the computer Parseh was written on it is, and its quota was once hit at
26 of 32 GB), which is the wrong place for gigabytes on any machine.  Parseh's own folder is where the shelves are,
so it has room for what is made of them; and a file staged there is on the same disk as the shelf it goes back to.

    fd, path = scratch.mkstemp(prefix="parseh-shelf-", suffix=".zip")
    work = scratch.mkdtemp(prefix="parseh-everything-load-")
    scratch.sweep()          # at start-up: what a killed server left, older than a day

The caller deletes what it made, as it did with tempfile's.  `.tmp/` is git-ignored, no release ships it, no update
may write into it (lib/updater.py NEVER), no backup or bundle walks it (they walk the shelves, never the root).

WHICH FOLDER.  `ROOT`, when somebody set it: serve.py's main() and the studio's own server set it to Parseh's folder
before they serve, and a test sets it to its temporary tree.  When nobody did, this is not a running Parseh but a test
or a script, and the answer follows serve.ROOT where a harness moved it (the way every harness points the shelves at
its tree); failing that, a folder of this process's own in the system temp folder, removed when the process ends --
never the checkout, which a test must not write into, and never anything a real backup goes through.
"""
import atexit
import os
import shutil
import sys
import tempfile
import time

NAME = ".tmp"
OWN = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = None                 # Parseh's folder, set by the server that runs it (or a test's tree)
AGE = 24 * 3600             # a leftover older than this is a killed server's, and goes at the next start
_private = []


def root():
    """The folder `.tmp/` is made in (see the docstring)."""
    if ROOT:
        return str(ROOT)
    srv = sys.modules.get("serve")
    moved = getattr(srv, "ROOT", None) if srv is not None else None
    if moved and os.path.realpath(str(moved)) != OWN:
        return str(moved)
    if not _private:
        _private.append(tempfile.mkdtemp(prefix="parseh-scratch-"))
        atexit.register(shutil.rmtree, _private[0], True)
    return _private[0]


def folder(at=None):
    """`.tmp/` under `at` (or root()), made when it is first wanted."""
    path = os.path.join(str(at) if at else root(), NAME)
    os.makedirs(path, exist_ok=True)
    return path


def mkstemp(prefix="parseh-", suffix="", at=None):
    """tempfile.mkstemp inside `.tmp/` -> (fd, path)."""
    return tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=folder(at))


def mkdtemp(prefix="parseh-", at=None):
    """tempfile.mkdtemp inside `.tmp/` -> path."""
    return tempfile.mkdtemp(prefix=prefix, dir=folder(at))


def sweep(at=None, age=AGE, now=None):
    """Remove what is in `.tmp/` and older than `age` seconds -> the names removed.

    Only the entries directly inside `.tmp/` are looked at, and only there is anything removed: a link is unlinked,
    never followed.  A folder's age is its own mtime.  Nothing outside `.tmp/` is touched, and a `.tmp/` that is not
    there is not made."""
    path = os.path.join(str(at) if at else root(), NAME)
    if not os.path.isdir(path) or os.path.islink(path):
        return []
    limit = (now if now is not None else time.time()) - age
    gone = []
    for name in sorted(os.listdir(path)):
        p = os.path.join(path, name)
        try:
            st = os.lstat(p)
            if st.st_mtime > limit:
                continue
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p)
            else:
                os.unlink(p)
            gone.append(name)
        except OSError:
            continue
    return gone
