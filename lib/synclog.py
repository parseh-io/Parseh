# SPDX-License-Identifier: GPL-3.0-or-later
"""The change log (a0.7.0, docs/sync.md): what each unit is, here, and since when.

For every unit this computer holds (lib/syncunits.py) the log keeps ONE row:
its content hash, the names and hashes of its files, and its VERSION VECTOR
-- {install id: counter} -- which is how two installs tell "changed on one
side" from "changed on both":

    mine {A: 3, B: 1}   theirs {A: 2, B: 1}    -> mine is ahead: send it
    mine {A: 2, B: 1}   theirs {A: 2, B: 2}    -> theirs is ahead: take it
    mine {A: 3, B: 1}   theirs {A: 2, B: 2}    -> both changed: the rules ask

Each change made HERE adds one to this install's own counter.  Nothing in that
reasoning reads a clock: wall-clock time is kept beside each record only to be
shown, and the one rule that asks for "the most recent" (exercise progress)
reads the answers' own times, inside the schedule.

A deletion leaves the row with no hash, `deleted` set and its counter moved on:
a TOMBSTONE.  It stays until the rules (lane C) have asked about it and every
partner has it -- `forget()` -- so a deleted unit never comes back by accident
from a partner that still holds it.

And beside the rows, an append-only list of CHANGES (`changes_since(seq)`):
each with the unit, what it was done (put, add, delete, adopt, choose), the new
hash or, for an addition, what was added, the install that made it and the
vector after it.  The exchange (lane B) reads it to say what is new.

HOW CHANGES GET IN.  Two ways, and only the second is the truth:
  * the hooks at the write chokepoints call lib/synctouch.py's `touch(path)`;
    `flush()`, a moment later, works out the units under those paths and
    records whichever now hash differently;
  * `scan()` -- at start and before each sync -- walks every unit and compares
    its hash with the log: a store written outside Parseh (by hand, by an
    outside agent, by a subprocess that took no lock) is caught there.
A unit sync is busy writing (lib/synclock.py) is skipped by both and looked at
again when the write ends, so a version sync brings in is never recorded as
this computer's own change -- the exchange records it with `adopt()`.

WHERE.  config/sync/log.sqlite, beside config/sync/identity.json: this
device's, never synced, never in a settings backup.  The folder follows
prefs.STORE (a harness that points prefs at a temporary tree points this there
too), unless HOME is set.  sqlite3 is in the standard library of every Python
Parseh runs on, phones' included; nothing here runs a subprocess.
"""
import json
import os
import sqlite3
import sys
import threading
import time

LIB = os.path.dirname(os.path.abspath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import synctouch                                               # noqa: E402
import syncunits                                               # noqa: E402

HOME = None          # config/sync, unless set (tests may set it)
DB_NAME = "log.sqlite"
DEBOUNCE = 2.0       # seconds after the last touch before the flush runs
CLEAN_EVERY = 3600   # seconds between two cleanings of the one-day store

_LOCK = threading.RLock()
_CONN = {"path": None, "conn": None}
_FH = {}             # path -> (size, mtime_ns, sha256): the file hash cache, in memory
_FH_DIRTY = {}

touch = synctouch.touch


def home():
    """The folder of this device's sync state (config/sync)."""
    if HOME:
        return HOME
    import prefs
    return os.path.join(os.path.dirname(os.path.abspath(prefs.STORE)), "sync")


# ------------------------------------------------------------------ the database
_SCHEMA = """
CREATE TABLE IF NOT EXISTS units (
  unit TEXT PRIMARY KEY, kind TEXT NOT NULL, place TEXT, hash TEXT,
  files TEXT, vv TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0,
  at REAL NOT NULL, seq INTEGER NOT NULL, key TEXT);
CREATE TABLE IF NOT EXISTS changes (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, unit TEXT NOT NULL, op TEXT NOT NULL,
  hash TEXT, added TEXT, install TEXT NOT NULL, vv TEXT NOT NULL, at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS changes_unit ON changes(unit);
CREATE TABLE IF NOT EXISTS filehash (
  path TEXT PRIMARY KEY, size INTEGER, mtime INTEGER, sha TEXT);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""


def _db():
    path = os.path.join(home(), DB_NAME)
    if _CONN["path"] != path:
        if _CONN["conn"] is not None:
            try:
                _CONN["conn"].close()
            except sqlite3.Error:
                pass
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript(_SCHEMA)
        _CONN.update(path=path, conn=conn)
        _FH.clear()
        _FH_DIRTY.clear()
        for p, size, mtime, sha in conn.execute("SELECT path, size, mtime, sha FROM filehash"):
            _FH[p] = (size, mtime, sha)
    return _CONN["conn"]


def close():
    """Close the database (tests that move HOME; the server never needs to)."""
    with _LOCK:
        if _CONN["conn"] is not None:
            _CONN["conn"].close()
        _CONN.update(path=None, conn=None)
        _FH.clear()
        _FH_DIRTY.clear()


def filehash(path):
    """sha256 of a file, read again only when its size or mtime moved."""
    st = os.stat(path)
    key = (st.st_size, st.st_mtime_ns)
    got = _FH.get(path)
    if got and (got[0], got[1]) == key:
        return got[2]
    sha = syncunits.sha256_file(path)
    _FH[path] = _FH_DIRTY[path] = (key[0], key[1], sha)
    return sha


def _save_filehashes(conn):
    if _FH_DIRTY:
        conn.executemany("INSERT OR REPLACE INTO filehash VALUES (?,?,?,?)",
                         [(p,) + v for p, v in _FH_DIRTY.items()])
        _FH_DIRTY.clear()


# ------------------------------------------------------------------ version vectors
def merge(a, b):
    """The element-wise maximum of two vectors."""
    out = dict(a or {})
    for k, v in (b or {}).items():
        if v > out.get(k, 0):
            out[k] = v
    return out


def compare(a, b):
    """"same", "ahead" (a has all of b and more), "behind" or "both"."""
    a, b = a or {}, b or {}
    more = any(v > b.get(k, 0) for k, v in a.items())
    less = any(v > a.get(k, 0) for k, v in b.items())
    if more and less:
        return "both"
    return "ahead" if more else "behind" if less else "same"


def bump(vv, install):
    out = dict(vv or {})
    out[install] = out.get(install, 0) + 1
    return out


def _me():
    import syncid
    return syncid.install_id()


# ------------------------------------------------------------------ rows
_COLS = "unit, kind, place, hash, files, vv, deleted, at, seq, key"


def _row(conn, uid):
    r = conn.execute("SELECT %s FROM units WHERE unit=?" % _COLS, (uid,)).fetchone()
    return _as_dict(r) if r else None


def _as_dict(r):
    return {"unit": r[0], "kind": r[1], "rule": syncunits.KINDS[r[1]][0], "place": r[2],
            "hash": r[3], "files": json.loads(r[4]) if r[4] else None, "vv": json.loads(r[5]),
            "deleted": bool(r[6]), "at": r[7], "seq": r[8],
            "key": tuple(json.loads(r[9])) if r[9] else None}


def _unit(row):
    """The syncunits.Unit a row stands for, as it was last seen here."""
    return syncunits.unit(row["unit"], row["place"], row["key"])


def _write(conn, uid, kind, place, op, hsh, files, vv, deleted, install, added=None, key=None):
    at = time.time()
    cur = conn.execute("INSERT INTO changes (unit, op, hash, added, install, vv, at) "
                       "VALUES (?,?,?,?,?,?,?)",
                       (uid, op, hsh, json.dumps(added, ensure_ascii=False, sort_keys=True)
                        if added is not None else None, install, json.dumps(vv, sort_keys=True), at))
    seq = cur.lastrowid
    conn.execute("INSERT OR REPLACE INTO units (%s) VALUES (?,?,?,?,?,?,?,?,?,?)" % _COLS,
                 (uid, kind, place, hsh, json.dumps(files, sort_keys=True) if files is not None else None,
                  json.dumps(vv, sort_keys=True), 1 if deleted else 0, at, seq,
                  json.dumps(list(key), ensure_ascii=False) if key else None))
    return {"seq": seq, "unit": uid, "op": op, "hash": hsh, "install": install, "vv": vv, "at": at,
            "added": added}


def _record(conn, u, snap, me):
    """Compare a unit as it is now with its row; write a change when it moved."""
    row = _row(conn, u.id)
    if snap is None:
        if row is None or row["deleted"]:
            return None
        return _write(conn, u.id, u.kind, u.where, "delete", None, None, bump(row["vv"], me), True, me,
                      key=u.key)
    if row is not None and not row["deleted"] and row["hash"] == snap["hash"]:
        if row["place"] != u.where:
            conn.execute("UPDATE units SET place=? WHERE unit=?", (u.where, u.id))
        return None
    new = row is None or row["deleted"]
    op = "add" if new and u.rule == syncunits.ADDITIONS else "put"
    added = None
    if op == "add":
        added = ({"value": syncunits.comparable(u, snap["value"])} if "value" in snap
                 else {"files": snap["files"]})
    return _write(conn, u.id, u.kind, u.where, op, snap["hash"], snap.get("files"),
                  bump(row["vv"] if row else {}, me), False, me, added, key=u.key)


def _writing(uid):
    import synclock
    return synclock.writing(uid)


def _snapshot(u):
    try:
        return syncunits.snapshot(u, filehash)
    except OSError:
        return None


def refresh(uid_or_unit):
    """Record one unit as it is now -> the change written, or None."""
    with _LOCK:
        conn = _db()
        u = uid_or_unit
        if isinstance(u, str):
            row = _row(conn, u)
            u = _unit(row) if row else next((x for x in syncunits.walk() if x.id == u), None)
            if u is None:
                return None
        got = _record(conn, u, _snapshot(u), _me())
        _save_filehashes(conn)
        return got


# ------------------------------------------------------------------ flush and scan
def _inside(path, folder):
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def _known_under(conn, path):
    """Units the log holds (not yet tombstoned) that a write at `path` may
    have removed: those living under it, and those with `path` as a file."""
    out = []
    for r in conn.execute("SELECT %s FROM units WHERE deleted=0" % _COLS):
        row = _as_dict(r)
        place, names = row["place"], row["files"] or {}
        if not place:
            continue
        if _inside(place, path):
            out.append(_unit(row))
        elif _inside(path, place):
            rel = os.path.relpath(path, place).replace(os.sep, "/")
            if rel in names or any(n.startswith(rel + "/") for n in names) \
                    or row["kind"] in ("book", "video", "note", "doc"):
                out.append(_unit(row))
    return out


def flush():
    """Record the units under every path touched since the last flush -> the
    changes written.  Too many touches at once means "look at everything"."""
    paths, over = synctouch.drain()
    if over:
        return scan()
    if not paths:
        return []
    out, later = [], []
    with _LOCK:
        conn = _db()
        me = _me()
        conn.execute("BEGIN")
        try:
            done = set()
            for p in sorted(paths):
                found = {u.id: u for u in syncunits.units_for(p)}
                for u in _known_under(conn, p):
                    found.setdefault(u.id, u)
                for uid, u in found.items():
                    if uid in done:
                        continue
                    if _writing(uid):
                        later.append(p)
                        continue
                    done.add(uid)
                    got = _record(conn, u, _snapshot(u), me)
                    if got:
                        out.append(got)
            _save_filehashes(conn)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    for p in later:                    # looked at again once the sync's write is over
        synctouch.touch(p)
    return out


def scan():
    """Walk every unit and record what moved, tombstones included -> the
    changes written.  At start, and before each sync (lane B calls it)."""
    out = []
    with _LOCK:
        conn = _db()
        me = _me()
        conn.execute("BEGIN")
        try:
            seen = set()
            for u in syncunits.walk():
                if u.id in seen:
                    continue
                seen.add(u.id)
                if _writing(u.id):
                    continue
                got = _record(conn, u, _snapshot(u), me)
                if got:
                    out.append(got)
            for r in conn.execute("SELECT %s FROM units WHERE deleted=0" % _COLS).fetchall():
                row = _as_dict(r)
                if row["unit"] in seen or _writing(row["unit"]):
                    continue
                got = _record(conn, _unit(row), None, me)
                if got:
                    out.append(got)
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('scanned', ?)", (str(time.time()),))
            _save_filehashes(conn)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    return out


# ------------------------------------------------------------------ what the other lanes read and say
def get(uid):
    """The log's row of a unit -> {"unit", "kind", "rule", "place", "hash",
    "files", "vv", "deleted", "at", "seq"} or None."""
    with _LOCK:
        return _row(_db(), uid)


def rows(prefix="", deleted=None):
    """Every row whose unit id starts with `prefix`; `deleted` True/False
    filters tombstones in or out."""
    with _LOCK:
        conn = _db()
        q = "SELECT %s FROM units WHERE unit >= ? AND unit < ?" % _COLS
        args = [prefix, prefix + "￿"]
        if deleted is not None:
            q += " AND deleted=?"
            args.append(1 if deleted else 0)
        return [_as_dict(r) for r in conn.execute(q + " ORDER BY unit", args)]


def changes_since(seq=0, limit=1000):
    """The changes after `seq`, oldest first."""
    with _LOCK:
        cur = _db().execute("SELECT seq, unit, op, hash, added, install, vv, at FROM changes "
                            "WHERE seq > ? ORDER BY seq LIMIT ?", (seq, limit))
        return [{"seq": r[0], "unit": r[1], "op": r[2], "hash": r[3],
                 "added": json.loads(r[4]) if r[4] else None, "install": r[5],
                 "vv": json.loads(r[6]), "at": r[7]} for r in cur]


def last_seq():
    with _LOCK:
        r = _db().execute("SELECT MAX(seq) FROM changes").fetchone()
        return r[0] or 0


def adopt(uid, hsh, vv, files=None, deleted=False, by=None, place=None):
    """A partner's version has just been written here (or its deletion carried
    out), by the exchange, inside synclock.sync_write(uid): the row takes its
    hash and the MERGED vector, with no count of this install's -- it is not a
    change made here, and the partner must not see it come back as one."""
    with _LOCK:
        conn = _db()
        row = _row(conn, uid)
        kind = syncunits.kind_of(uid)
        merged = merge(row["vv"] if row else {}, vv)
        return _write(conn, uid, kind, place or (row or {}).get("place"), "adopt",
                      None if deleted else hsh, None if deleted else files, merged, deleted,
                      by or "?", key=(row or {}).get("key"))


def chosen(uid, other_vv):
    """The person chose THIS computer's version over a partner's (or a rule
    did): the vector becomes both merged plus one of this install's, so it
    is ahead of either side and travels without a second question."""
    with _LOCK:
        conn = _db()
        row = _row(conn, uid)
        if row is None:
            raise KeyError(uid)
        me = _me()
        return _write(conn, uid, row["kind"], row["place"], "choose", row["hash"], row["files"],
                      bump(merge(row["vv"], other_vv), me), row["deleted"], me, key=row["key"])


def forget(uid):
    """Drop a tombstone once its deletion was answered and every partner has
    it -> True when there was one.  A live unit is never forgotten."""
    with _LOCK:
        cur = _db().execute("DELETE FROM units WHERE unit=? AND deleted=1", (uid,))
        return cur.rowcount > 0


# ------------------------------------------------------------------ running in the server
_RUN = {"thread": None, "stop": None}


def start(shelves=None, debounce=DEBOUNCE):
    """At the server's start: the identity made if missing, the one-day store
    cleaned, the whole shelf scanned, then a thread that flushes a moment
    after the last write and cleans the one-day store every hour.  Everything
    on that thread; nothing here holds the server's start up."""
    if shelves:
        syncunits.configure(**shelves)
    if _RUN["thread"] is not None and _RUN["thread"].is_alive():
        return _RUN["thread"]
    stop = threading.Event()

    def run():
        import synckeep
        import syncid
        try:
            syncid.ensure()
        except Exception as e:                       # noqa: BLE001 -- never stops Parseh
            print("!! sync: could not make this install's identity: %s" % e, flush=True)
        try:
            synckeep.clean()
            scan()
        except Exception as e:                       # noqa: BLE001
            print("!! sync: could not look through the shelf: %s" % e, flush=True)
        cleaned = time.time()
        while not stop.is_set():
            synctouch.WOKEN.wait(timeout=60)
            if stop.is_set():
                break
            if synctouch.pending():
                # wait for the writes to settle: a burst of saves is one flush
                while synctouch.pending() and not stop.is_set():
                    synctouch.WOKEN.clear()
                    if not synctouch.WOKEN.wait(timeout=debounce):
                        break
                try:
                    flush()
                except Exception as e:               # noqa: BLE001
                    print("!! sync: could not record a change: %s" % e, flush=True)
            else:
                synctouch.WOKEN.clear()
            if time.time() - cleaned > CLEAN_EVERY:
                cleaned = time.time()
                try:
                    synckeep.clean()
                except Exception as e:               # noqa: BLE001
                    print("!! sync: could not clean the versions kept for a day: %s" % e, flush=True)

    t = threading.Thread(target=run, name="synclog", daemon=True)
    _RUN.update(thread=t, stop=stop)
    t.start()
    return t


def stop():
    if _RUN["stop"] is not None:
        _RUN["stop"].set()
        synctouch.WOKEN.set()
        if _RUN["thread"] is not None:
            _RUN["thread"].join(timeout=10)
    _RUN.update(thread=None, stop=None)
