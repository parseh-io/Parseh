# SPDX-License-Identifier: GPL-3.0-or-later
"""One writer at a time for each book and each video (TO-DO §3.10).

An edit to a book or a video reads its file, changes one chunk and writes the
whole file back.  The server answers each request on a thread of its own, so
two tabs -- or a phone and the computer -- editing two chunks of one chapter
at once both read the same file, and the later write erased the earlier's
edit; and both wrote through ONE temporary name (`path + ".tmp"`), so the
second `open` truncated what the first was about to move into place.

So every write path for a book or a video holds `held(<its folder>)` around its
whole read-change-write -- one re-entrant lock per folder, so a route holding
it may call a library function that takes it again -- and writes through
`tmp(path)`, a temporary name no other write shares (process, then a number).
Two different books never wait for each other.

Standard library only.
"""
import contextlib
import itertools
import os
import threading

_LOCKS = {}
_GUARD = threading.Lock()
_SEQ = itertools.count(1)


def key(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(str(path))))


def lock(path):
    """The one lock of this folder (or file), made the first time it is asked."""
    k = key(path)
    with _GUARD:
        got = _LOCKS.get(k)
        if got is None:
            got = _LOCKS[k] = threading.RLock()
        return got


@contextlib.contextmanager
def held(path):
    """`with held(book_dir):` -- nobody else's write to it can fall inside."""
    if not path:
        yield
        return
    with lock(path):
        yield


def tmp(path):
    """A temporary name beside `path` that no other write can share."""
    return "%s.%d.%d.tmp" % (path, os.getpid(), next(_SEQ))


def serialised(folder_of):
    """A decorator: the function's whole run holds the lock of
    `folder_of(*args, **kwargs)`."""
    def wrap(fn):
        import functools

        @functools.wraps(fn)
        def inside(*args, **kwargs):
            with held(folder_of(*args, **kwargs)):
                return fn(*args, **kwargs)
        return inside
    return wrap
