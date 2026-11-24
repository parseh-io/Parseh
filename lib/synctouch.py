# SPDX-License-Identifier: GPL-3.0-or-later
"""The cheap half of the change log (a0.7.0, docs/sync.md): "something was
written here".

Parseh writes its stores from many places, but they meet at a handful of
chokepoints -- lib/storeguard.py (every JSON store in config/), lib/pathlock.py
(every write to a book or a video), the studio store's document folder, the
decks', the clip tray's and the Anki store's own writers.  Each of them calls
`touch(path)` here with the file or folder it has just written, and that is
ALL it does: one set.add under a lock.  No hashing, no disk, no import of
anything but the standard library, so lib/storeguard.py and lib/pathlock.py
stay what they say they are ("standard library only") and Parseh's own suites,
which write those stores thousands of times, do not feel it.

The expensive half -- which unit the path belongs to, what its content hashes
to, whether that differs from what the log last recorded, the version vector
-- is lib/synclog.py's `flush()`, which drains what was touched here a short
while later (or at once, when a caller asks).  A touch is a HINT, never the
truth: a write that bypasses every chokepoint (a hand, an outside agent, a
subprocess) is caught by the scan, which compares hashes with the log.  So a
touch too many costs a stat or two; a touch missing costs only time.

    synctouch.touch("/…/books/persian/the-bell")      after the write
    synctouch.drain()  -> {"/…/books/persian/the-bell", ...}    (synclog only)
"""
import os
import threading

# More than this many distinct paths between two flushes is not a burst of
# editing but a whole shelf being restored or imported: rather than keep a
# list that large, say "look at everything" (synclog then scans).
LIMIT = 20000

_LOCK = threading.Lock()
_PATHS = set()
_OVERFLOW = [False]
# set whenever something is touched; the flusher thread waits on it
WOKEN = threading.Event()


def touch(path):
    """Note that `path` (a file or a folder) was just written or removed."""
    if not path:
        return
    p = os.path.abspath(os.fspath(path))
    with _LOCK:
        if len(_PATHS) < LIMIT:
            _PATHS.add(p)
        else:
            _OVERFLOW[0] = True
    WOKEN.set()


def drain():
    """Everything touched since the last drain -> (paths, overflowed)."""
    with _LOCK:
        got = set(_PATHS)
        _PATHS.clear()
        over = _OVERFLOW[0]
        _OVERFLOW[0] = False
        WOKEN.clear()
    return got, over


def pending():
    """How many paths wait to be flushed (for tests and the Devices page)."""
    with _LOCK:
        return len(_PATHS)
