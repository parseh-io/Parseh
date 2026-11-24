# SPDX-License-Identifier: GPL-3.0-or-later
"""The exchange of sync (a0.7.0, lane B; docs/sync.md, "The exchange").

Two paired installs bring each other up to date.  Every exchange is a PULL:
this install asks a partner what it has, per unit (its hash, its version
vector, whether it is a tombstone), compares each with its own change log
(lib/synclog.py) and takes what it lacks.  "Both directions" is a pull here
followed by a NUDGE, which makes the partner pull from this install in turn.
Only the receiving side ever writes, so a write is always under that side's
own locks (lib/synclock.py) and journal.

Per unit (synclog.compare of the two vectors, and the hashes):

  * equal hashes                -> agreement; the vectors are merged (adopt), nothing moves;
  * this side ahead, or same    -> nothing to do here (the partner takes it when it pulls);
  * this side behind, live      -> TAKEN, with no question: the plain case;
  * anything else               -> a SITUATION handed to RULES[situation] (lane C):
        "both"       a choice unit changed on both sides
        "setting"    a personal setting changed on both sides
        "progress"   an exercise's progress changed on both sides
        "additions"  an additions unit (a clip, a card, a Review-later flag) changed on both sides
        "latest"     a reading place set on both sides
        "deletion"   a tombstone on either side against a live version
    The default handler, hold(), leaves the unit as it is on both computers and
    the exchange lists it in pending().

Files travel by CONTENT: a unit's description names each file by its sha256.
A file whose sha this computer already has anywhere on its shelf is copied
locally, never sent; the others come in chunks (CHUNK bytes, each chunk's own
sha256 checked) into config/sync/incoming/<sha>.part, which a later sync
continues from where it stopped.  Only when every file of a unit is here and
checked is the unit written: inside synclock.sync_write(uid), the version it
replaces kept for a day (synckeep.keep(uid, "incoming", partner)), a journal
(config/sync/applying.json) written first so a write cut off by a crash is
finished by recover() before anything else looks at the shelf, then
synclog.adopt().  A sync cut off at any point therefore leaves each unit
either as it was or as the partner's, and the next sync goes on.

Holding: this device holds everything unless its own setting
(config/sync/holding.json, never synced) leaves out a language folder or a
whole book, video, deck, document or Anki deck.  What is left out is not
taken; a partner's live version of it is listed by elsewhere() as "on
<partner>", and fetch(uid, partner) brings it on demand (and holds it from
then on).

When it runs (start()/stop()): at start, when a partner becomes reachable,
CHANGE_DEBOUNCE seconds after the change log recorded a change made here
(synclog's own flush already waits for the writes to settle), and on
sync_now().  Never two syncs with the same partner at once.

The transport is lane A's: lib/syncpeer.py `call(partner_id, op, payload,
body=, timeout=)` and `partners()`, lib/syncroutes.py `register(op, handler)`.
This module only uses those names.
"""
import collections
import contextlib
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import sys
import threading
import time

LIB = os.path.dirname(os.path.abspath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import storeguard                                              # noqa: E402
import synckeep                                                # noqa: E402
import synclock                                                # noqa: E402
import synclog                                                 # noqa: E402
import syncunits                                               # noqa: E402

CHUNK = 1 << 20              # bytes per chunk of a file in transit
CHUNK_MAX = 8 << 20          # the most one sync.blob answers with
TIMEOUT = 30.0               # seconds for one call (lane A's deadline per call)
CHANGE_DEBOUNCE = 5.0        # seconds after a change made here before partners are synced
TICK = 2.0                   # how often the scheduler looks at partners and the log
PART_DAYS = 7                # a partial file not continued for this long is dropped

SITUATIONS = ("both", "setting", "progress", "additions", "latest", "deletion")
HELD = "held"

_LOCK = threading.RLock()
_CONN = {"path": None, "conn": None}


# ------------------------------------------------------------------ the seam for lane C
class Case:
    """One unit the exchange does not settle by itself, as given to a rule.

    unit, situation, partner, mine (this computer's log row or None),
    theirs (the partner's row: {"unit", "kind", "hash", "vv", "deleted"})."""

    def __init__(self, pull, uid, situation, mine, theirs):
        self._pull = pull
        self.unit, self.situation, self.partner = uid, situation, pull.partner
        self.mine, self.theirs = mine, theirs

    def info(self):
        """The partner's version now: {"unit", "hash", "vv", "deleted", "files"
        {inner: sha256} | "value", "lang_files"?}."""
        return self._pull.info(self.unit)

    def staged(self):
        """The partner's files, fetched and checked -> {inner: local path}
        (in config/sync/incoming; read them, never move them)."""
        info = self.info()
        files = _all_files(info)
        got = self._pull.stage(files)
        return {inner: got[sha] for inner, sha in files.items()}

    def take(self, why="incoming"):
        """Write the partner's version here (its deletion, if it is a
        tombstone): kept for a day, written, adopted.  -> True, or False when
        an editor holds the unit or it changed here meanwhile."""
        return self._pull.take(self.unit, why=why, force=True) == "taken"

    def hold(self):
        return HELD


def hold(case):
    """The default rule: leave the unit as it is on both computers; it is
    listed in pending() until a rule or the person settles it."""
    return HELD


# situation -> handler(case) -> HELD (listed in pending()) or anything else (settled)
RULES = {s: hold for s in SITUATIONS}
# callbacks(uid, partner) after a partner's version was written here (lane C: "out of date")
ON_TAKEN = []


# ------------------------------------------------------------------ this device's own state
def _home():
    return synclog.home()


def _db():
    path = os.path.join(_home(), "exchange.sqlite")
    if _CONN["path"] != path:
        if _CONN["conn"] is not None:
            try:
                _CONN["conn"].close()
            except sqlite3.Error:
                pass
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=30)
        conn.executescript("""
CREATE TABLE IF NOT EXISTS pending (unit TEXT, partner TEXT, situation TEXT, mine TEXT,
  theirs TEXT, at REAL, PRIMARY KEY (unit, partner));
CREATE TABLE IF NOT EXISTS elsewhere (unit TEXT, partner TEXT, hash TEXT, at REAL,
  PRIMARY KEY (unit, partner));
CREATE TABLE IF NOT EXISTS fetched (unit TEXT PRIMARY KEY, at REAL);
CREATE TABLE IF NOT EXISTS runs (partner TEXT PRIMARY KEY, doc TEXT);
""")
        _CONN.update(path=path, conn=conn)
    return _CONN["conn"]


def close():
    with _LOCK:
        if _CONN["conn"] is not None:
            _CONN["conn"].close()
        _CONN.update(path=None, conn=None)


def _incoming():
    d = os.path.join(_home(), "incoming")
    os.makedirs(d, exist_ok=True)
    return d


def _journal():
    return os.path.join(_home(), "applying.json")


def _me():
    import syncid
    return syncid.install_id()


# ------------------------------------------------------------------ pending (what waits)
def _record_pending(uid, partner, situation, mine, theirs):
    def small(r):
        return None if r is None else {k: r.get(k) for k in ("hash", "vv", "deleted")}
    with _LOCK:
        _db().execute("INSERT OR REPLACE INTO pending VALUES (?,?,?,?,?,?)",
                      (uid, partner, situation, json.dumps(small(mine)), json.dumps(small(theirs)),
                       time.time()))


def clear_pending(uid, partner=None):
    """A waiting unit settled (lane C, once answered) -> how many rows went."""
    with _LOCK:
        if partner is None:
            return _db().execute("DELETE FROM pending WHERE unit=?", (uid,)).rowcount
        return _db().execute("DELETE FROM pending WHERE unit=? AND partner=?", (uid, partner)).rowcount


def pending(partner=None, situation=None):
    """Every unit the exchange left as it is, waiting -> [{"unit", "kind",
    "rule", "situation", "partner", "mine", "theirs", "at"}], oldest first.
    situation is one of SITUATIONS, or "editing" (an editor held it here
    when the partner's version came: it is taken once the editor closes)."""
    q, args = "SELECT unit, partner, situation, mine, theirs, at FROM pending WHERE 1=1", []
    if partner:
        q += " AND partner=?"
        args.append(partner)
    if situation:
        q += " AND situation=?"
        args.append(situation)
    with _LOCK:
        got = _db().execute(q + " ORDER BY at, unit", args).fetchall()
    return [{"unit": r[0], "kind": syncunits.kind_of(r[0]), "rule": syncunits.rule_of(r[0]),
             "partner": r[1], "situation": r[2], "mine": json.loads(r[3]),
             "theirs": json.loads(r[4]), "at": r[5]} for r in got]


# ------------------------------------------------------------------ holding
_HOLD_KINDS = ("book", "video", "deck", "doc", "ankideck")


def _holding_path():
    return os.path.join(_home(), "holding.json")


def holding():
    """This device's choice of what it holds -> {"leave_out": {"languages":
    [language folders], "units": [book/video/deck/doc/ankideck ids]}}."""
    try:
        with open(_holding_path(), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        doc = {}
    lo = doc.get("leave_out") if isinstance(doc, dict) else None
    lo = lo if isinstance(lo, dict) else {}
    return {"leave_out": {"languages": sorted(set(lo.get("languages") or [])),
                          "units": sorted(set(lo.get("units") or []))}}


def set_holding(languages=None, units=None):
    """Leave out these language folders and these whole things (None keeps
    what is set) -> holding().  Leaving something out deletes nothing here."""
    cur = holding()["leave_out"]
    if languages is not None:
        cur["languages"] = sorted({str(x) for x in languages if x})
    if units is not None:
        bad = [u for u in units if syncunits.kind_of(u) not in _HOLD_KINDS]
        if bad:
            raise ValueError("only a whole book, video, deck, document or Anki deck can be left out: %s"
                             % ", ".join(bad))
        cur["units"] = sorted(set(units))
    storeguard.write_json(_holding_path(), {"leave_out": cur})
    return holding()


def owner_of(uid):
    """The whole thing a unit belongs to: a note -> its book or video, an
    exercise / its progress / a deck's file -> the deck, a card -> its Anki deck."""
    kind, _, name = uid.partition(":")
    p = name.split("/")
    if kind == "note" and len(p) >= 3:
        return "%s:%s/%s" % (p[0], p[1], p[2])
    if kind in ("item", "progress", "deckfile") and len(p) >= 2:
        return "deck:%s/%s" % (p[0], p[1])
    if kind in ("card", "ankimedia") and len(p) >= 2:
        return "ankideck:%s/%s" % (p[0], p[1])
    return uid


def language_of(uid):
    """The language folder a unit sits in, or None (settings, clips...)."""
    kind, _, name = uid.partition(":")
    p = name.split("/")
    if kind == "note" and len(p) >= 2:
        return p[1]
    if kind in ("book", "video", "deck", "item", "progress", "deckfile", "ankideck", "card", "ankimedia"):
        return p[0] if len(p) >= 2 else None
    if kind == "doc" and len(p) == 2:
        return p[0]
    return None


def holder():
    """holds() as a function over one reading of the setting (for a whole run)."""
    lo = holding()["leave_out"]
    units, langs = set(lo["units"]), set(lo["languages"])
    with _LOCK:
        fetched = {r[0] for r in _db().execute("SELECT unit FROM fetched")}

    def holds_(uid):
        owner = owner_of(uid)
        if owner in fetched:
            return True
        return owner not in units and language_of(uid) not in langs
    return holds_


def holds(uid):
    """True when this device takes this unit from its partners."""
    return holder()(uid)


def elsewhere(partner=None):
    """What this device leaves out and a partner holds -> [{"unit", "kind",
    "owner", "partners": [ids]}]: shown as "on <partner>"."""
    q, args = "SELECT unit, partner FROM elsewhere", []
    if partner:
        q += " WHERE partner=?"
        args.append(partner)
    with _LOCK:
        got = _db().execute(q + " ORDER BY unit, partner", args).fetchall()
    out = collections.OrderedDict()
    for uid, p in got:
        e = out.setdefault(uid, {"unit": uid, "kind": syncunits.kind_of(uid), "owner": owner_of(uid),
                                 "partners": []})
        e["partners"].append(p)
    return list(out.values())


def fetch(uid, partner):
    """Bring a left-out unit, or a whole book/video/deck/document and all its
    units, from a partner now; it is held from then on -> the summary of
    the pull (see sync_from)."""
    owner = owner_of(uid)
    with _LOCK:
        _db().execute("INSERT OR REPLACE INTO fetched VALUES (?,?)", (owner, time.time()))
    return sync_from(partner, only=owner)


# ------------------------------------------------------------------ the partner's side: the ops
def _row_out(r):
    return {"unit": r["unit"], "kind": r["kind"], "hash": r["hash"], "vv": r["vv"],
            "deleted": r["deleted"]}


def op_have(partner, payload, body):
    """What this install has: every row of its change log (tombstones too)."""
    recover()
    synclog.flush()
    synclog.scan()
    return {"ok": True, "install": _me(), "rows": [_row_out(r) for r in synclog.rows()]}, None


def _filehashes(files):
    out = {}
    for inner, p in files.items():
        try:
            out[inner] = synclog.filehash(p)
        except OSError:
            continue
    return out


def describe(uid):
    """This install's version of one unit, as the partner receives it."""
    try:
        u = syncunits.locate(uid)
    except KeyError:
        return {"ok": False, "error": "unknown unit"}
    if not synclock.writing(uid):
        synclog.refresh(uid)
    row = synclog.get(uid)
    if row is None:
        return {"ok": False, "error": "not here"}
    out = {"ok": True, "unit": uid, "hash": row["hash"], "vv": row["vv"], "deleted": row["deleted"]}
    if row["deleted"]:
        return out
    if u.key is not None:
        snap = syncunits.snapshot(u, synclog.filehash)
        if snap is None or snap["hash"] != row["hash"]:
            return {"ok": False, "error": "changing"}
        out["value"] = snap["value"]
        if u.kind == "language":
            out["lang_files"] = _filehashes(syncunits.files_of(u))
    else:
        out["files"] = row["files"] or {}
    return out


def op_unit(partner, payload, body):
    return describe(str(payload.get("unit") or "")), None


_INDEX = {"key": None, "map": None}


def _index():
    """sha256 -> [(unit, inner)] over every live unit here (and a personal
    language's own files)."""
    with _LOCK:
        key = (_home(), synclog.last_seq())
        if _INDEX["key"] == key:
            return _INDEX["map"]
        m = {}
        for r in synclog.rows(deleted=False):
            files = r["files"] or {}
            if r["kind"] == "language":
                try:
                    files = _filehashes(syncunits.files_of(syncunits.locate(r["unit"])))
                except KeyError:
                    files = {}
            for inner, sha in files.items():
                m.setdefault(sha, []).append((r["unit"], inner))
        _INDEX.update(key=key, map=m)
        return m


def local_file(sha):
    """A file on this shelf whose content has this sha256 now, or None."""
    for uid, inner in _index().get(sha, ()):
        try:
            u = syncunits.locate(uid)
            p = syncunits.path_of(u, inner)
            if os.path.isfile(p) and synclog.filehash(p) == sha:
                return p
        except (KeyError, OSError):
            continue
    return None


def op_blob(partner, payload, body):
    """One chunk of a file, named by its sha256 -> ({"ok", "size", "chunk":
    sha256 of the bytes}, bytes).  Only a file of a synced unit is served."""
    sha = str(payload.get("sha") or "")
    try:
        offset = max(0, int(payload.get("offset") or 0))
        length = min(CHUNK_MAX, max(1, int(payload.get("length") or CHUNK)))
    except (TypeError, ValueError):
        return {"ok": False, "error": "bad request"}, None
    p = local_file(sha)
    if p is None:
        return {"ok": False, "error": "no such file"}, None
    with open(p, "rb") as fh:
        size = os.fstat(fh.fileno()).st_size
        fh.seek(offset)
        data = fh.read(length)
    return {"ok": True, "size": size, "chunk": hashlib.sha256(data).hexdigest()}, data


def op_nudge(partner, payload, body):
    """The partner has just pulled from here: pull from it in turn."""
    if _SCHED["thread"] is not None and _SCHED["thread"].is_alive():
        request(partner, "nudge")
        return {"ok": True, "queued": True}, None
    got = sync_from(partner)
    return {"ok": True, "queued": False, "complete": got.get("complete")}, None


OPS = {"sync.have": op_have, "sync.unit": op_unit, "sync.blob": op_blob, "sync.nudge": op_nudge}


def register():
    """Give lane A's router this module's ops."""
    import syncroutes
    for op, h in OPS.items():
        syncroutes.register(op, h)


# ------------------------------------------------------------------ this side: the pull
class Failed(Exception):
    """The partner could not be reached, refused, or sent something wrong.
    `transport` is True when the link itself failed: the run stops there."""

    def __init__(self, msg, transport=False):
        super().__init__(msg)
        self.transport = transport


def _call(partner, op, payload, timeout=None):
    import syncpeer
    try:
        got, body = syncpeer.call(partner, op, payload, timeout=timeout or TIMEOUT)
    except (syncpeer.Unreachable, syncpeer.Refused) as e:
        raise Failed("%s: %s" % (type(e).__name__, e), transport=True) from e
    if not isinstance(got, dict):
        raise Failed("an answer that is not an object")
    return got, body


def _all_files(info):
    if info.get("deleted"):
        return {}
    files = dict(info.get("files") or {})
    for inner, sha in (info.get("lang_files") or {}).items():
        files["lang:" + inner] = sha
    return files


def _safe_inner(inner):
    parts = inner.split("/")
    return not any(p in ("", ".", "..") or p.startswith(".") or "\\" in p for p in parts)


class _Moved(Exception):
    """The unit changed here since the exchange looked at it."""


class Pull:
    def __init__(self, partner):
        self.partner = partner
        self.infos = {}
        self.staged = {}
        self.out = {"partner": partner, "taken": [], "adopted": [], "held": [], "waiting": [],
                    "elsewhere": [], "failed": {}, "complete": False, "error": None,
                    "blobs": {"chunks": 0, "bytes": 0, "local": 0, "present": 0}}

    # -- the partner's version of a unit
    def info(self, uid):
        if uid not in self.infos:
            got, _ = _call(self.partner, "sync.unit", {"unit": uid})
            if not got.get("ok"):
                raise Failed("%s: %s" % (uid, got.get("error") or "refused"))
            self.infos[uid] = got
        return self.infos[uid]

    # -- files, by content
    def stage(self, files):
        """{inner: sha} -> {sha: a checked local path}, fetching what is missing."""
        got = {}
        for sha in sorted(set(files.values())):
            got[sha] = self._blob(sha)
        return got

    def _blob(self, sha):
        if sha in self.staged:
            return self.staged[sha]
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise Failed("a file name that is not a sha256")
        d = _incoming()
        final = os.path.join(d, sha)
        if os.path.isfile(final) and syncunits.sha256_file(final) == sha:
            self.staged[sha] = final
            return final
        here = local_file(sha)
        if here is not None:                       # a file both have: never sent
            tmp = final + ".%s.tmp" % secrets.token_hex(4)
            shutil.copyfile(here, tmp)
            if syncunits.sha256_file(tmp) == sha:
                os.replace(tmp, final)
                self.out["blobs"]["local"] += 1
                self.staged[sha] = final
                return final
            os.unlink(tmp)
        part = final + ".part"
        offset = os.path.getsize(part) if os.path.isfile(part) else 0
        size = None
        with open(part, "ab") as fh:
            while size is None or offset < size:
                meta, data = _call(self.partner, "sync.blob",
                                   {"sha": sha, "offset": offset, "length": CHUNK})
                if not meta.get("ok"):
                    raise Failed("file %s…: %s" % (sha[:12], meta.get("error") or "refused"))
                size = int(meta.get("size") or 0)
                data = data or b""
                if hashlib.sha256(data).hexdigest() != meta.get("chunk"):
                    raise Failed("file %s…: a chunk arrived damaged" % sha[:12])
                if not data and offset < size:
                    raise Failed("file %s…: the partner sent nothing" % sha[:12])
                fh.write(data)
                fh.flush()
                offset += len(data)
                self.out["blobs"]["chunks"] += 1
                self.out["blobs"]["bytes"] += len(data)
            os.fsync(fh.fileno())
        if syncunits.sha256_file(part) != sha:
            os.unlink(part)                        # begun again next time
            raise Failed("file %s…: its content does not match its name" % sha[:12])
        os.replace(part, final)
        self.staged[sha] = final
        return final

    # -- one unit
    def take(self, uid, why="incoming", force=False):
        """Write the partner's version of uid here -> "taken", "waiting"
        (an editor holds it), "moved" (it changed here meanwhile) or "same"."""
        info = self.info(uid)
        u = syncunits.locate(uid)
        mine = synclog.get(uid)
        if not force and mine is not None and synclog.compare(mine["vv"], info["vv"]) != "behind":
            return "same"                          # it moved on the partner meanwhile: next time
        files = _all_files(info)
        for inner in files:
            if not _safe_inner(inner[5:] if inner.startswith("lang:") else inner):
                raise Failed("%s: a file name that climbs out: %s" % (uid, inner))
        staged = self.stage(files)
        try:
            with synclock.sync_write(uid):
                snap = syncunits.snapshot(u, synclog.filehash)
                was = None if mine is None or mine["deleted"] else mine["hash"]
                if (snap["hash"] if snap else None) != was:
                    raise _Moved(uid)
                if snap is not None:
                    synckeep.keep(uid, "deletion" if info["deleted"] else why, self.partner)
                job = {"unit": uid, "partner": self.partner, "info": info,
                       "staged": {s: p for s, p in staged.items()}, "at": time.time()}
                storeguard.write_json(_journal(), job)
                _apply(u, info, staged, self.partner)
                os.unlink(_journal())
        except synclock.Busy:
            return "waiting"
        except _Moved:
            return "moved"
        synclog.touch(u.where)
        for cb in list(ON_TAKEN):
            try:
                cb(uid, self.partner)
            except Exception as e:                  # noqa: BLE001 -- a listener never stops sync
                print("!! sync: a listener failed on %s: %s" % (uid, e), flush=True)
        return "taken"

    # -- the whole exchange
    def run(self, only=None):
        recover()
        synclog.flush()
        synclog.scan()
        got, _ = _call(self.partner, "sync.have", {})
        if not got.get("ok"):
            raise Failed(got.get("error") or "refused")
        theirs = {r["unit"]: r for r in got.get("rows") or [] if isinstance(r, dict) and r.get("unit")}
        mine = {r["unit"]: r for r in synclog.rows()}
        holds = holder()
        seen_pending, there = set(), {}
        todo = []
        for uid in sorted(theirs):
            if only and owner_of(uid) != only:
                continue
            t = theirs[uid]
            try:
                syncunits.locate(uid)
            except KeyError:
                self.out["failed"][uid] = "a unit this Parseh does not know"
                continue
            m = mine.get(uid)
            if not holds(uid):
                if not t.get("deleted"):
                    there[uid] = t.get("hash")
                continue
            what = decide(m, t)
            if what is None:
                clear_pending(uid, self.partner)
            elif what == "adopt":
                with contextlib.suppress(synclock.Busy), synclock.sync_write(uid):
                    synclog.adopt(uid, t["hash"], t["vv"], deleted=t["deleted"], by=self.partner,
                                  place=(m or {}).get("place"), files=(m or {}).get("files"))
                    self.out["adopted"].append(uid)
                clear_pending(uid, self.partner)
            elif what == "take":
                todo.append(uid)
            else:
                verdict = RULES.get(what, hold)(Case(self, uid, what, m, t))
                if verdict == HELD:
                    _record_pending(uid, self.partner, what, m, t)
                    seen_pending.add(uid)
                    self.out["held"].append(uid)
                else:
                    clear_pending(uid, self.partner)
        with _LOCK:
            conn = _db()
            if only is None:
                conn.execute("DELETE FROM elsewhere WHERE partner=?", (self.partner,))
            for uid, h in there.items():
                conn.execute("INSERT OR REPLACE INTO elsewhere VALUES (?,?,?,?)",
                             (uid, self.partner, h, time.time()))
            for uid in theirs:
                if holds(uid) and uid in mine:
                    conn.execute("DELETE FROM elsewhere WHERE unit=?", (uid,))
        self.out["elsewhere"] = sorted(there)
        for uid in todo:
            try:
                r = self.take(uid)
            except Failed as e:
                if e.transport:
                    raise
                self.out["failed"][uid] = str(e)
                continue
            if r == "taken":
                self.out["taken"].append(uid)
                clear_pending(uid, self.partner)
                with _LOCK:
                    _db().execute("DELETE FROM elsewhere WHERE unit=?", (uid,))
            elif r == "waiting":
                _record_pending(uid, self.partner, "editing", mine.get(uid), theirs[uid])
                seen_pending.add(uid)
                self.out["waiting"].append(uid)
            elif r == "moved":
                self.out["failed"][uid] = "it changed here while it came; next time"
        if only is None:
            with _LOCK:
                conn = _db()
                for (uid,) in conn.execute("SELECT unit FROM pending WHERE partner=?",
                                           (self.partner,)).fetchall():
                    if uid not in seen_pending:
                        conn.execute("DELETE FROM pending WHERE unit=? AND partner=?", (uid, self.partner))
            if not self.out["failed"]:
                _sweep_incoming()
        self.out["complete"] = True
        return self.out


def decide(mine, theirs):
    """What the exchange does with one unit -> None (nothing here), "adopt"
    (the same content: merge the vectors), "take" (the plain case), or one
    of SITUATIONS (lane C's)."""
    if theirs is None:
        return None
    if mine is None:
        return None if theirs.get("deleted") else "take"
    md, td = bool(mine.get("deleted")), bool(theirs.get("deleted"))
    c = synclog.compare(mine.get("vv"), theirs.get("vv"))
    if md == td and (md or mine.get("hash") == theirs.get("hash")):
        return "adopt" if synclog.merge(mine.get("vv"), theirs.get("vv")) != mine.get("vv") else None
    if c in ("same", "ahead"):
        return None
    if c == "behind":
        return "deletion" if td else "take"
    if md or td:
        return "deletion"
    rule = syncunits.rule_of(theirs["unit"])
    if rule == syncunits.PROGRESS:
        return "progress"
    if rule == syncunits.ADDITIONS:
        return "additions"
    if rule == syncunits.LATEST:
        return "latest"
    if syncunits.kind_of(theirs["unit"]) == "setting":
        return "setting"
    return "both"


def _prune(folder, stop):
    """Remove empty folders from `folder` up to (not including) `stop`."""
    folder, stop = os.path.abspath(folder), os.path.abspath(stop)
    while folder != stop and folder.startswith(stop + os.sep):
        try:
            os.rmdir(folder)
        except OSError:
            return
        folder = os.path.dirname(folder)


def _del_key(path, key):
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return
    cur, keys = doc, list(key)
    while len(keys) > 1:
        k = keys.pop(0)
        if k.startswith("#"):
            field, want = k[1:], keys.pop(0)
            if isinstance(cur, list):
                cur[:] = [r for r in cur if not (isinstance(r, dict) and r.get(field) == want)]
            break
        cur = cur.get(k) if isinstance(cur, dict) else None
        if cur is None:
            return
    else:
        if isinstance(cur, dict):
            cur.pop(keys[0], None)
    storeguard.write_json(path, doc)


def _place(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = "%s.%s.tmp" % (dst, secrets.token_hex(4))
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


def _write_files(u, want, staged, top):
    """The unit's files become `want` {inner: sha}: missing or different ones
    placed from `staged` {sha: path}, the others removed."""
    now = syncunits.files_of(u)
    for inner, sha in sorted(want.items()):
        dst = syncunits.path_of(u, inner)
        if os.path.isfile(dst) and synclog.filehash(dst) == sha:
            continue
        _place(staged[sha], dst)
    for inner, p in now.items():
        if inner not in want:
            with contextlib.suppress(OSError):
                os.unlink(p)
            if top:
                _prune(os.path.dirname(p), top)


def _apply(u, info, staged, partner):
    """Make unit u here what `info` says, from the staged files, and record
    it as the partner's version.  Idempotent: recover() runs it again after
    a crash.  Inside synclock.sync_write(u.id)."""
    gone = bool(info.get("deleted"))
    files = None
    if u.key is not None:
        if gone:
            _del_key(u.where, u.key)
        else:
            synckeep._set_key(u.where, u.key, info["value"])
        if u.kind == "language":
            _write_files(u, {} if gone else (info.get("lang_files") or {}), staged, None)
    else:
        files = {} if gone else (info.get("files") or {})
        _write_files(u, files, staged, _shelf_of(u))
    snap = syncunits.snapshot(u, synclog.filehash)
    if (snap["hash"] if snap else None) != (None if gone else info["hash"]):
        raise Failed("%s: written, but it does not match the partner's version" % u.id)
    synclog.adopt(u.id, info["hash"], info["vv"], files=None if gone else files,
                  deleted=gone, by=partner, place=u.where)


def _shelf_of(u):
    for top in syncunits.SHELVES.values():
        if u.where == top or u.where.startswith(top.rstrip(os.sep) + os.sep):
            return top
    return None


def _sweep_incoming():
    """After a complete sync: the finished files are no longer needed; a
    partial one is kept for PART_DAYS for the next sync to continue."""
    d = _incoming()
    now = time.time()
    for n in os.listdir(d):
        p = os.path.join(d, n)
        try:
            if not n.endswith(".part") or now - os.path.getmtime(p) > PART_DAYS * 86400:
                os.unlink(p)
        except OSError:
            continue


def recover():
    """Finish a unit whose write a crash cut off (config/sync/applying.json),
    before anything records the half-written state as this computer's own
    change.  -> the unit finished, or None."""
    j = _journal()
    if not os.path.isfile(j):
        return None
    try:
        with open(j, encoding="utf-8") as fh:
            job = json.load(fh)
        uid, info, staged = job["unit"], job["info"], job["staged"]
        u = syncunits.locate(uid)
        if all(os.path.isfile(p) for p in staged.values()):
            with synclock.sync_write(uid):
                _apply(u, info, staged, job.get("partner"))
            os.unlink(j)
            return uid
    except (OSError, ValueError, KeyError, Failed, synclock.Busy) as e:
        print("!! sync: could not finish a write cut off earlier: %s" % e, flush=True)
        return None
    os.unlink(j)                                   # nothing to finish it with: the scan sees what is there
    return None


# ------------------------------------------------------------------ one sync with one partner
_PLOCKS = {}
_STATUS = {}


def _plock(partner):
    with _LOCK:
        return _PLOCKS.setdefault((_home(), partner), threading.Lock())


def _note(partner, **kw):
    with _LOCK:
        st = _STATUS.setdefault((_home(), partner), {"partner": partner, "state": "idle", "last_ok": None,
                                                     "last_error": None, "last": None, "why": None})
        st.update(kw)


def sync_from(partner, only=None, why="", wait=True):
    """Pull from one partner -> {"partner", "taken", "adopted", "held",
    "waiting", "elsewhere", "failed" {uid: reason}, "complete", "error",
    "blobs" {"chunks", "bytes", "local", "present"}}.  {"busy": True} when a
    sync with that partner is already running (and wait is False)."""
    lock = _plock(partner)
    if not lock.acquire(blocking=wait):
        return {"partner": partner, "busy": True, "complete": False}
    p = Pull(partner)
    try:
        _note(partner, state="running", why=why or None, started=time.time())
        try:
            # synclog's writes from this thread are this install's; the sqlite
            # connection is shared, so the lock keeps them in one order
            p.run(only=only)
        except Failed as e:
            p.out["error"] = str(e)
    finally:
        p.out["at"] = time.time()
        _note(partner, state="idle", last=p.out,
              **({"last_ok": p.out["at"]} if p.out["complete"] else {"last_error": p.out["error"]}))
        with _LOCK:
            _db().execute("INSERT OR REPLACE INTO runs VALUES (?,?)",
                          (partner, json.dumps(p.out, ensure_ascii=False)))
        lock.release()
    return p.out


def sync_with(partner, why=""):
    """Both directions: pull from the partner, then nudge it to pull from here."""
    got = sync_from(partner, why=why)
    if got.get("complete"):
        try:
            ans, _ = _call(partner, "sync.nudge", {})
            got["nudged"] = ans
        except Failed as e:
            got["nudged"] = {"ok": False, "error": str(e)}
    return got


def status():
    """For the pages: {"running" (the scheduler), "partners": {id: {"state"
    idle|running, "last_ok", "last_error", "last" (the last summary), "why"}},
    "pending": count, "elsewhere": count}."""
    home = _home()
    with _LOCK:
        parts = {k[1]: dict(v) for k, v in _STATUS.items() if k[0] == home}
        for partner, doc in _db().execute("SELECT partner, doc FROM runs").fetchall():
            if partner not in parts:
                last = json.loads(doc)
                parts[partner] = {"partner": partner, "state": "idle", "last": last,
                                  "last_ok": last.get("at") if last.get("complete") else None,
                                  "last_error": last.get("error"), "why": None}
    return {"running": bool(_SCHED["thread"] and _SCHED["thread"].is_alive()), "partners": parts,
            "pending": len(pending()), "elsewhere": len(elsewhere())}


# ------------------------------------------------------------------ when it runs
_SCHED = {"thread": None, "stop": None, "wake": threading.Event(), "wanted": {}, "workers": {}}


def _partners():
    try:
        import syncpeer
        return [p for p in syncpeer.partners() if isinstance(p, dict) and p.get("id")]
    except Exception:                                 # noqa: BLE001 -- no transport yet: no partner
        return []


def request(partner=None, why=""):
    """Ask for a sync with one partner (or every partner) soon."""
    with _LOCK:
        ids = [partner] if partner else [p["id"] for p in _partners()]
        for pid in ids:
            _SCHED["wanted"].setdefault(pid, why)
    _SCHED["wake"].set()


def sync_now(partner=None, wait=False):
    """"Sync now": every partner (or one).  wait=True runs it here and returns
    {partner: summary}; otherwise it is queued and status() is returned."""
    if wait:
        ids = [partner] if partner else [p["id"] for p in _partners()]
        return {pid: sync_with(pid, why="sync now") for pid in ids}
    request(partner, "sync now")
    if not (_SCHED["thread"] and _SCHED["thread"].is_alive()):
        return sync_now(partner, wait=True)
    return status()


def _on_close(uid):
    for p in pending(situation="editing"):
        if p["unit"] == uid:
            request(p["partner"], "an editor closed")


def start(tick=None, change_debounce=None):
    """The scheduler, on a thread: a sync with every partner at start, with a
    partner as it becomes reachable, a moment after a change made here, and on
    request.  -> the thread."""
    if _SCHED["thread"] is not None and _SCHED["thread"].is_alive():
        return _SCHED["thread"]
    tick = TICK if tick is None else tick
    debounce = CHANGE_DEBOUNCE if change_debounce is None else change_debounce
    with contextlib.suppress(Exception):
        register()
    synclock.on_close(_on_close)
    stop_ev = threading.Event()
    home = _home()

    def worker(pid, why):
        try:
            sync_with(pid, why=why)
        except Exception as e:                         # noqa: BLE001 -- never stops Parseh
            _note(pid, state="idle", last_error="%s" % e)
            print("!! sync with %s: %s" % (pid, e), flush=True)

    def run():
        reach = {}
        seen = synclog.last_seq()
        changed_at = None
        request(None, "start")
        while not stop_ev.is_set():
            if _home() != home:                       # a test moved the stores away
                break
            for p in _partners():
                r = bool(p.get("reachable"))
                if r and reach.get(p["id"]) is False:
                    request(p["id"], "reachable")
                reach[p["id"]] = r
            last = synclog.last_seq()
            if last > seen:
                if any(c["op"] != "adopt" for c in synclog.changes_since(seen, limit=10000)):
                    changed_at = time.time()
                seen = last
            if changed_at is not None and time.time() - changed_at >= debounce:
                changed_at = None
                request(None, "a change here")
            with _LOCK:
                wanted, _SCHED["wanted"] = _SCHED["wanted"], {}
            for pid, why in wanted.items():
                w = _SCHED["workers"].get(pid)
                if w is not None and w.is_alive():     # never two at once: ask again after it
                    with _LOCK:
                        _SCHED["wanted"].setdefault(pid, why)
                    continue
                t = threading.Thread(target=worker, args=(pid, why), name="sync-%s" % pid, daemon=True)
                _SCHED["workers"][pid] = t
                t.start()
            _SCHED["wake"].wait(timeout=tick)
            _SCHED["wake"].clear()

    t = threading.Thread(target=run, name="syncexchange", daemon=True)
    _SCHED.update(thread=t, stop=stop_ev)
    t.start()
    return t


def stop(timeout=10):
    if _SCHED["stop"] is not None:
        _SCHED["stop"].set()
        _SCHED["wake"].set()
        if _SCHED["thread"] is not None:
            _SCHED["thread"].join(timeout=timeout)
        for w in list(_SCHED["workers"].values()):
            w.join(timeout=timeout)
    with _LOCK:
        _SCHED.update(thread=None, stop=None, workers={}, wanted={})
    with contextlib.suppress(ValueError):
        synclock._CLOSED.remove(_on_close)
