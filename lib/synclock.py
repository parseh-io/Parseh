# SPDX-License-Identifier: GPL-3.0-or-later
"""Nothing is edited while it syncs (a0.7.0, docs/sync.md): one lock per unit,
shared by the editors and the sync.

Two holders, and they exclude each other:

  * AN EDITOR holds a unit for as long as it is open -- the studio editor, a
    transcript's editor, a note, an exercise's form, a deck's options -- by a
    LEASE: `open_editor(unit)` gives a token, the page renews it while it is
    open (`keep(token)`, every half minute or so) and gives it back when it
    closes (`close_editor(token)`).  A page that dies without a word (a tab
    closed, a phone asleep) lets its lease run out after LEASE seconds, so a
    unit is never held forever.  Several editors may hold one unit at once
    (two tabs): they are each other's business, not sync's.
  * THE SYNC holds a unit only while it writes it: `with sync_write(unit):`.
    It refuses (Busy) when an editor holds the unit -- the incoming change
    waits, and when both sides changed it becomes a choice once the editor
    closes (`on_close` tells the rules) -- and while it writes, an editor
    asking to open the unit is refused with `retry_after`, and the page says
    so and opens a moment later.

For a unit that is a folder a route writes under lib/pathlock.py (a book, a
video), `sync_write` also holds that folder's pathlock, so a save already on
its way finishes before sync writes, and none starts while it does.

In-process only, like lib/pathlock.py: the server is one process, and so is
the sync inside it.  Standard library only.

    tok = synclock.open_editor("doc:persian/the-bell-3f2a1c", "studio")
    synclock.keep(tok); ...; synclock.close_editor(tok)

    with synclock.sync_write("doc:persian/the-bell-3f2a1c"):
        ... write the partner's version, synclog.adopt(...)
"""
import contextlib
import secrets
import sys
import os
import threading
import time

LIB = os.path.dirname(os.path.abspath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)

LEASE = 120.0          # seconds an editor's lease lasts without a renewal
RETRY = 2.0            # what an editor refused during a sync write is told to wait

_LOCK = threading.Lock()
_LEASES = {}           # token -> {"unit", "holder", "until"}
_WRITING = {}          # unit -> how many sync writes hold it (nested: re-entrant)
_CLOSED = []           # callbacks(unit) for "the last editor of this unit closed"


class Busy(Exception):
    """A unit held by the other side: `.unit`, `.by` ("sync" or the editors'
    names) and, for an editor refused, `.retry_after` seconds."""

    def __init__(self, unit, by, retry_after=None):
        self.unit, self.by, self.retry_after = unit, by, retry_after
        super().__init__("%s is held by %s" % (unit, by if isinstance(by, str) else ", ".join(by)))


def _expire(now):
    gone = [t for t, l in _LEASES.items() if l["until"] <= now]
    units = set()
    for t in gone:
        units.add(_LEASES.pop(t)["unit"])
    return [u for u in units if not any(l["unit"] == u for l in _LEASES.values())]


def _tell(units):
    for u in units:
        for cb in list(_CLOSED):
            try:
                cb(u)
            except Exception as e:                  # noqa: BLE001 -- a listener never breaks an editor
                print("!! sync: a listener failed on %s closing: %s" % (u, e), flush=True)


def open_editor(unit, holder="", lease=LEASE):
    """An editor opens `unit` -> its token.  Busy while sync writes it."""
    with _LOCK:
        freed = _expire(time.time())
        if _WRITING.get(unit):
            raise Busy(unit, "sync", RETRY)
        tok = secrets.token_hex(12)
        _LEASES[tok] = {"unit": unit, "holder": str(holder or "")[:60], "until": time.time() + lease}
    _tell(freed)
    return tok


def keep(token, lease=LEASE):
    """Renew a lease -> False when it had already run out (the page opens again)."""
    with _LOCK:
        l = _LEASES.get(token)
        if l is None or l["until"] <= time.time():
            return False
        l["until"] = time.time() + lease
        return True


def close_editor(token):
    """The editor closed -> its unit, or None for a token not held."""
    with _LOCK:
        l = _LEASES.pop(token, None)
        if l is None:
            return None
        last = not any(x["unit"] == l["unit"] for x in _LEASES.values())
    if last:
        _tell([l["unit"]])
    return l["unit"]


def on_close(callback):
    """Call `callback(unit)` whenever the last editor of a unit lets it go
    (closed or run out).  Lane C: a change that waited becomes a choice."""
    _CLOSED.append(callback)


def editing(unit):
    """The holders of the editors open on `unit` ([] when none)."""
    with _LOCK:
        freed = _expire(time.time())
        out = [l["holder"] for l in _LEASES.values() if l["unit"] == unit]
    _tell(freed)
    return out


def writing(unit):
    with _LOCK:
        return bool(_WRITING.get(unit))


def state(unit):
    return {"editing": editing(unit), "writing": writing(unit)}


def _folder(unit):
    """The folder a route's pathlock guards, for a unit that is one."""
    import syncunits
    if syncunits.kind_of(unit) not in ("book", "video"):
        return None
    try:
        return syncunits.locate(unit).where
    except KeyError:
        return None


@contextlib.contextmanager
def sync_write(unit):
    """Sync writes `unit` inside this.  Busy when an editor holds it."""
    with _LOCK:
        freed = _expire(time.time())
        holders = [l["holder"] or "an editor" for l in _LEASES.values() if l["unit"] == unit]
        if holders:
            raise Busy(unit, holders)
        _WRITING[unit] = _WRITING.get(unit, 0) + 1
    _tell(freed)
    folder = None
    try:
        folder = _folder(unit)
        if folder:
            import pathlock
            with pathlock.held(folder):
                yield
        else:
            yield
    finally:
        with _LOCK:
            n = _WRITING.get(unit, 1) - 1
            if n:
                _WRITING[unit] = n
            else:
                _WRITING.pop(unit, None)
        import synctouch
        if folder:
            synctouch.touch(folder)
