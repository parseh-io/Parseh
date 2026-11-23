# SPDX-License-Identifier: GPL-3.0-or-later
"""The day of each shelf's last backup (TO-DO §13.19): config/backups.json.

    backupdays.mark("book")          a backup of every book was just downloaded
    backupdays.days()                {"book": 1763900000.0, "video": None, ...}

One moment per thing that can be backed up -- the four shelves, the settings,
and the backup of everything -- written when the server has SENT the backup
whole (serve.py marks it after the answer, never when the button is pressed:
a download that failed half way is not a backup).  The backup of everything
holds the four shelves and the settings, so it marks each of them too.

KEPT BESIDE config/prefs.json, AND FOUND FROM IT.  The path is not a constant
of its own but prefs.STORE's folder, so that every test harness that points
the reading places at its temporary tree (tests/test_harness_stores.py) points
this file there too, without a line more.

Written through lib/storeguard.py like every store of the person's: whole,
fsync'd, and a file there that cannot be read is set aside under a dated name,
never written over.
"""
import json
import os
import threading
import time

import prefs
import storeguard

NAME = "backups.json"
STORE_FORMAT = 1
# what can be backed up, in the order the pages list them
SHELVES = ("book", "video", "studio", "decks", "settings", "everything")
# what the backup of everything holds, each marked when it is taken
IN_EVERYTHING = ("book", "video", "studio", "decks", "settings")
_LOCK = threading.Lock()


def store():
    return os.path.join(os.path.dirname(prefs.STORE), NAME)


def _ok(doc):
    return isinstance(doc, dict) and isinstance(doc.get("last"), dict)


def days():
    """{shelf: seconds or None} for every shelf, None where none was taken."""
    try:
        with open(store(), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        doc = None
    last = doc["last"] if _ok(doc) else {}
    out = {}
    for s in SHELVES:
        v = last.get(s)
        out[s] = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None
    return out


def mark(shelf, at=None):
    """`shelf` was backed up now (or at `at`) -> the days as they then stand.
    The backup of everything marks every shelf it holds."""
    if shelf not in SHELVES:
        raise ValueError("no shelf called %r" % (shelf,))
    at = time.time() if at is None else float(at)
    with _LOCK:
        have = days()
        for s in (shelf,) + (IN_EVERYTHING if shelf == "everything" else ()):
            have[s] = at
        storeguard.write_json(store(), {"format": STORE_FORMAT,
                                        "last": {k: v for k, v in have.items() if v}},
                              ok=_ok)
    return have


def said(at, now=None):
    """A day, in the words the pages use: "never", "today", "yesterday",
    "3 days ago", then the date."""
    if not at:
        return "never"
    now = time.time() if now is None else now
    today = time.localtime(now)
    then = time.localtime(at)
    gap = (time.mktime(today[:3] + (0, 0, 0, 0, 0, -1)) - time.mktime(then[:3] + (0, 0, 0, 0, 0, -1))) / 86400.0
    gap = int(round(gap))
    if gap <= 0:
        return "today"
    if gap == 1:
        return "yesterday"
    if gap < 30:
        return "%d days ago" % gap
    return time.strftime("%d %B %Y", then).lstrip("0")


def view(now=None):
    """What a page shows: {shelf: {"at": seconds or None, "said": words}}."""
    return {s: {"at": at, "said": said(at, now)} for s, at in days().items()}
