# SPDX-License-Identifier: GPL-3.0-or-later
"""The rules of sync (a0.7.0, lane C; docs/sync.md "The rules: lib/syncrules.py").

The exchange (lib/syncexchange.py) settles by itself what changed on one side
only.  Everything else is a situation handed to `syncexchange.RULES`, and this
module answers each one:

  setting, latest      the most recent wins, by the values' own times; never asked
  progress             the exercise state whose latest answer is newest wins; never asked
  additions            seen.json: the union; any other entry: the most recent wins
  both                 held as a QUESTION: this computer's version or the partner's
  deletion             held as a QUESTION: delete / restore, or send the edited version / delete

A question is answered once, on either computer, and the answer travels:
the answering side records a DECISION per unit (which install's version wins,
and for which pair of versions), the winner's vector is put ahead of both
(`synclog.chosen`), the loser takes the winner's version (`Pull.take(force)`),
and the partner is told (`rules.answer`; queued in an outbox when it cannot be
reached, and sent before the next pull).  A partner that meets the same
situation before the message came asks for the decision first (`rules.decided`),
so a question never comes back.  Whatever a choice discards is kept for a day
(synckeep.keep, by the take) and written as a diff file kept until deleted.

"Make this computer identical to <partner>", out of date, the kept versions
and the diff files are here too, as the Python API lane E's pages call.
Standard library only; this device's state in config/sync/rules.sqlite.
"""
import hashlib
import json
import os
import sqlite3
import sys
import threading
import time

LIB = os.path.dirname(os.path.abspath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)

import synckeep                                                # noqa: E402
import synclock                                                # noqa: E402
import synclog                                                 # noqa: E402
import syncunits                                               # noqa: E402
import syncexchange                                            # noqa: E402

CALL_TIMEOUT = 8.0          # seconds for a rules call (an answer waits in the outbox when it is not heard)
PREVIEW_MAX = 256 * 1024    # characters of a discard preview kept with a question
DECISION_DAYS = 60          # a decision nobody needs any more is dropped after this
PLOCK_WAIT = 20.0           # seconds an answer waits for a running sync with the partner
TEXT_MAX = 4 << 20         # a file bigger than this is shown as a file kept aside, not as text

# lane D fills these: jobs this computer has waiting for a partner, and how to cancel them
JOBS = []                   # fn(partner_id) -> [job dict]
CANCEL_JOBS = []            # fn(partner_id, [job dict])

_LOCK = threading.RLock()
_CONN = {"path": None, "conn": None}
_GROUPS = {}                # id(pull) -> the grouped deletion question of that pull


# ------------------------------------------------------------------ this device's state
def _db():
    path = os.path.join(synclog.home(), "rules.sqlite")
    if _CONN["path"] != path:
        if _CONN["conn"] is not None:
            try:
                _CONN["conn"].close()
            except sqlite3.Error:
                pass
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=30)
        conn.executescript("""
CREATE TABLE IF NOT EXISTS questions (id TEXT PRIMARY KEY, kind TEXT, partner TEXT, units TEXT,
  mine TEXT, theirs TEXT, preview TEXT, origin TEXT, at REAL);
CREATE TABLE IF NOT EXISTS decisions (unit TEXT, partner TEXT, winner TEXT, pair TEXT, at REAL,
  PRIMARY KEY (unit, partner));
CREATE TABLE IF NOT EXISTS outbox (n INTEGER PRIMARY KEY AUTOINCREMENT, partner TEXT, op TEXT,
  payload TEXT, at REAL);
CREATE TABLE IF NOT EXISTS diffs (name TEXT PRIMARY KEY, unit TEXT, title TEXT, at REAL);
CREATE TABLE IF NOT EXISTS outdated (unit TEXT PRIMARY KEY, what TEXT, hash TEXT, at REAL);
""")
        _CONN.update(path=path, conn=conn)
    return _CONN["conn"]


def close():
    with _LOCK:
        if _CONN["conn"] is not None:
            _CONN["conn"].close()
        _CONN.update(path=None, conn=None)
        _GROUPS.clear()


def _me():
    import syncid
    return syncid.install_id()


def partner_name(pid):
    try:
        import syncpeer
        if hasattr(syncpeer, "partner"):
            p = syncpeer.partner(pid)
            if p:
                return p.get("name") or pid
        for p in syncpeer.partners():
            if p.get("id") == pid:
                return p.get("name") or pid
    except Exception:                                  # noqa: BLE001
        pass
    return pid


def _my_name():
    try:
        import syncid
        return syncid.name()
    except Exception:                                  # noqa: BLE001
        return "this computer"


def _call(partner, op, payload, timeout=CALL_TIMEOUT):
    """-> the answer dict, or None when the partner was not heard / said no."""
    try:
        import syncpeer
        got, _ = syncpeer.call(partner, op, payload, timeout=timeout)
        return got if isinstance(got, dict) and got.get("ok", True) else None
    except Exception:                                  # noqa: BLE001 -- silence, refusal, an older Parseh
        return None


def _vstate(row):
    """A version as a decision names it: its hash, or "deleted"."""
    if row is None or row.get("deleted"):
        return "deleted"
    return row.get("hash") or "deleted"


def _pair(a, b):
    return json.dumps(sorted([_vstate(a), _vstate(b)]))


# ------------------------------------------------------------------ titles and versions
def title(uid):
    """A unit in words, for the pages."""
    try:
        u = syncunits.locate(uid)
    except KeyError:
        return uid
    if u.key is None and os.path.isdir(u.where):
        for name in ("meta.json", "book.json", "video.json", "deck.json"):
            try:
                with open(os.path.join(u.where, name), encoding="utf-8") as fh:
                    doc = json.load(fh)
                t = doc.get("title") or doc.get("name")
                if isinstance(t, str) and t.strip():
                    return t.strip()
            except (OSError, ValueError, AttributeError):
                continue
    words = syncunits.KINDS.get(u.kind, ("", u.kind, ""))[1]
    return "%s: %s" % (words[:1].upper() + words[1:], uid.split(":", 1)[1] or u.kind)


def _mine_version(uid):
    """This computer's version -> None (not here) | {"value"} | {"files": {inner: path}}."""
    try:
        u = syncunits.locate(uid)
    except KeyError:
        return None
    if u.key is not None:
        v = syncunits.value_of(u)
        return None if v is None or syncunits.deleted_value(u, v) else {"value": v}
    files = syncunits.files_of(u)
    return {"files": files} if files else None


def _theirs_version(case_or_pull, uid=None):
    """The partner's version, fetched and checked -> None (a tombstone) | {"value"} | {"files"}."""
    if isinstance(case_or_pull, syncexchange.Case):
        info, staged = case_or_pull.info(), None
        if info.get("deleted"):
            return None
        if "value" in info and not info.get("files"):
            return {"value": info["value"]}
        return {"files": case_or_pull.staged()}
    pull = case_or_pull
    info = pull.info(uid)
    if info.get("deleted"):
        return None
    if "value" in info and not info.get("files"):
        return {"value": info["value"]}
    files = syncexchange._all_files(info)
    got = pull.stage(files)
    return {"files": {inner: got[sha] for inner, sha in files.items()}}


def _read(path):
    try:
        if os.path.getsize(path) > TEXT_MAX:
            return None
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return b""


def _as_text(data):
    if data is None or b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def diff_of(uid, kept, discarded, kept_label, discarded_label):
    """What keeping `kept` throws away of `discarded`, as git would show it:
    a unified diff for text, the changed fields for a structured file or a
    setting, a line naming a media file kept aside."""
    head = "# %s (%s)\n# kept: %s · discarded: %s\n" % (title(uid), uid, kept_label, discarded_label)
    if kept is None and discarded is None:
        return ""
    if (kept or {}).get("value") is not None or (discarded or {}).get("value") is not None:
        a = (kept or {}).get("value")
        b = (discarded or {}).get("value")
        lines = synckeep.fields_diff(a if a is not None else {}, b if b is not None else {})
        if discarded is None:
            lines = ["(the discarded side is a deletion)"] + lines
        return head + "".join(line + "\n" for line in lines) if lines else ""
    ka, da = (kept or {}).get("files") or {}, (discarded or {}).get("files") or {}
    out = []
    if discarded is None:
        out.append("# the discarded side is a deletion: nothing of it to put back\n")
    for inner in sorted(set(ka) | set(da)):
        a = _read(ka[inner]) if inner in ka else b""
        b = _read(da[inner]) if inner in da else b""
        if a == b and a is not None:
            continue
        ta, tb = _as_text(a), _as_text(b)
        if inner.endswith(".json") and ta is not None and tb is not None:
            try:
                ja = json.loads(ta) if ta.strip() else {}
                jb = json.loads(tb) if tb.strip() else {}
                lines = synckeep.fields_diff(ja, jb)
                if lines:
                    out.append("## %s\n%s" % (inner, "".join("%s\n" % x for x in lines)))
                continue
            except ValueError:
                pass
        if ta is not None and tb is not None:
            out.append(synckeep.text_diff(ta, tb, "%s/%s" % (kept_label, inner),
                                          "%s/%s" % (discarded_label, inner)))
        elif inner in da:
            out.append("## %s: a media file; the discarded version is kept aside for a day "
                       "(Settings → Devices, put back)\n" % inner)
    body = "".join(out)
    return head + body if body.strip() else ""


def _summary(row, version):
    if row is None or row.get("deleted") or version is None:
        return "deleted"
    if "value" in version:
        s = json.dumps(version["value"], ensure_ascii=False)
        return s if len(s) <= 80 else s[:77] + "…"
    n = len(version.get("files") or {})
    return "%d file%s" % (n, "" if n == 1 else "s")


def _when(row, partner=None, uid=None):
    """When a version was made: its log row's time (asked of the partner for its own)."""
    if partner is not None:
        got = _call(partner, "rules.when", {"units": [uid]})
        if got:
            return ((got.get("rows") or {}).get(uid) or {}).get("at")
        return None
    r = synclog.get(row) if isinstance(row, str) else row
    return (r or {}).get("at")


# ------------------------------------------------------------------ questions (the store)
def _qrow(r):
    return {"id": r[0], "kind": r[1], "partner": r[2], "units": json.loads(r[3]),
            "mine": json.loads(r[4]), "theirs": json.loads(r[5]), "preview": json.loads(r[6]),
            "origin": r[7], "at": r[8]}


def _questions(partner=None):
    q, args = "SELECT * FROM questions", []
    if partner:
        q += " WHERE partner=?"
        args.append(partner)
    with _LOCK:
        return [_qrow(r) for r in _db().execute(q + " ORDER BY at, id", args).fetchall()]


def _save_q(q):
    with _LOCK:
        _db().execute("INSERT OR REPLACE INTO questions VALUES (?,?,?,?,?,?,?,?,?)",
                      (q["id"], q["kind"], q["partner"], json.dumps(q["units"]), json.dumps(q["mine"]),
                       json.dumps(q["theirs"]), json.dumps(q["preview"]), q.get("origin") or "here",
                       q.get("at") or time.time()))


def _drop_units(partner, uids):
    """Take units out of their questions with `partner`; a question left empty goes."""
    uids = set(uids)
    with _LOCK:
        for q in _questions(partner):
            keep = [u for u in q["units"] if u["unit"] not in uids]
            if len(keep) == len(q["units"]):
                continue
            if not keep:
                _db().execute("DELETE FROM questions WHERE id=?", (q["id"],))
            else:
                q["units"] = keep
                _save_q(q)


def _question_of(uid, partner=None):
    for q in _questions(partner):
        if any(u["unit"] == uid for u in q["units"]):
            return q
    return None


def _qid(kind, partner, uids):
    pair = sorted([_me(), partner])
    return hashlib.sha256(json.dumps([kind, pair, sorted(uids)]).encode()).hexdigest()[:16]


def _public(q):
    units = [{"unit": u["unit"], "kind": u["kind"], "title": u.get("title")} for u in q["units"]]
    return {"id": q["id"], "kind": q["kind"], "units": units, "partner": q["partner"],
            "partner_name": partner_name(q["partner"]), "mine": q["mine"], "theirs": q["theirs"],
            "discard_preview": q["preview"], "at": q["at"]}


def _swap(q):
    """A question as the partner sees it."""
    out = dict(q, mine=q["theirs"], theirs=q["mine"],
               preview={"mine": q["preview"].get("theirs", ""), "theirs": q["preview"].get("mine", "")})
    for u in out["units"]:
        u["mine_state"], u["theirs_state"] = u.get("theirs_state"), u.get("mine_state")
        u["mine_vv"], u["theirs_vv"] = u.get("theirs_vv"), u.get("mine_vv")
        p = u.get("preview") or {}
        u["preview"] = {"mine": p.get("theirs", ""), "theirs": p.get("mine", "")}
    return out


# ------------------------------------------------------------------ decisions
def _decide(uid, partner, winner, pair):
    with _LOCK:
        _db().execute("INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?)",
                      (uid, partner, winner, pair, time.time()))
        _db().execute("DELETE FROM decisions WHERE at<?", (time.time() - DECISION_DAYS * 86400,))


def _decision(uid, partner, pair):
    with _LOCK:
        r = _db().execute("SELECT winner, pair FROM decisions WHERE unit=? AND partner=?",
                          (uid, partner)).fetchone()
    return r[0] if r and r[1] == pair else None


def _apply_decision(case, winner):
    """The answer reached this computer: settle the case by it -> True (settled)."""
    if winner == _me():
        try:
            synclog.chosen(case.unit, case.theirs.get("vv") or {})
        except KeyError:
            return False
        return True
    return case.take(why="deletion" if case.situation == "deletion" else "choice")


# ------------------------------------------------------------------ the handlers
def _settled_by_answer(case):
    """An answer already given, here or on the partner, settles the case -> True."""
    pair = _pair(case.mine, case.theirs)
    winner = _decision(case.unit, case.partner, pair)
    if winner is None:
        got = _call(case.partner, "rules.decided", {"unit": case.unit, "pair": pair})
        w = (got or {}).get("winner")
        if w:
            winner = w
            _decide(case.unit, case.partner, w, pair)
    if winner is None:
        return False
    if _apply_decision(case, winner):
        _drop_units(case.partner, [case.unit])
        return True
    return False


def _time_of_value(v):
    if isinstance(v, dict):
        try:
            return float(v.get("at"))
        except (TypeError, ValueError):
            return None
    return None


def _most_recent(case, mine_at, theirs_at):
    """The newer side wins; equal times: the larger hash (both computers agree)."""
    mine_at = mine_at or 0.0
    theirs_at = theirs_at or 0.0
    theirs_wins = (theirs_at, case.theirs.get("hash") or "") > (mine_at, (case.mine or {}).get("hash") or "")
    if theirs_wins:
        return "taken" if case.take(why="incoming") else syncexchange.HELD
    synclog.chosen(case.unit, case.theirs.get("vv") or {})
    return "kept"


def on_setting(case):
    """A personal setting, or a reading place, changed on both: the most recent wins."""
    if case.mine is None:
        return "taken" if case.take() else syncexchange.HELD
    mine = _mine_version(case.unit)
    info = case.info()
    ma = _time_of_value((mine or {}).get("value"))
    ta = _time_of_value(info.get("value"))
    if ma is None or ta is None:
        ma, ta = _when(case.unit), _when(None, case.partner, case.unit)
    return _most_recent(case, ma, ta)


def _latest_answer(doc):
    best = ""
    if isinstance(doc, dict):
        for h in doc.get("history") or []:
            if isinstance(h, dict) and isinstance(h.get("at"), str):
                best = max(best, _iso(h["at"]))
        st = doc.get("state")
        if isinstance(st, dict) and isinstance(st.get("last_review"), str):
            best = max(best, _iso(st["last_review"]))
    return best


def _iso(s):
    """An ISO time as a sortable UTC string."""
    import datetime
    try:
        d = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=datetime.timezone.utc)
        return d.astimezone(datetime.timezone.utc).isoformat()
    except ValueError:
        return s


def _json_of(version):
    for p in ((version or {}).get("files") or {}).values():
        try:
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None
    return None


def on_progress(case):
    """The same exercise studied on both: the state whose latest answer is newest."""
    if case.mine is None:
        return "taken" if case.take() else syncexchange.HELD
    mine = _latest_answer(_json_of(_mine_version(case.unit)))
    theirs = _latest_answer(_json_of(_theirs_version(case)))
    theirs_wins = (theirs, case.theirs.get("hash") or "") > (mine, case.mine.get("hash") or "")
    if theirs_wins:
        return "taken" if case.take(why="incoming") else syncexchange.HELD
    synclog.chosen(case.unit, case.theirs.get("vv") or {})
    return "kept"


def on_additions(case):
    """An entry of a list changed on both.  seen.json: the union, written here and
    put ahead of both; any other entry: the most recent wins."""
    if case.mine is None:
        return "taken" if case.take() else syncexchange.HELD
    if syncunits.kind_of(case.unit) != "ankiseen":
        mine = _mine_version(case.unit)
        ma = _time_of_value((mine or {}).get("value"))
        ta = _time_of_value(case.info().get("value"))
        if ma is None or ta is None:
            ma, ta = _when(case.unit), _when(None, case.partner, case.unit)
        return _most_recent(case, ma, ta)
    a = _json_of(_mine_version(case.unit)) or {}
    b = _json_of(_theirs_version(case)) or {}
    union = dict(b)
    for k, v in a.items():
        union[k] = min(v, union[k]) if k in union and isinstance(v, str) and isinstance(union[k], str) else v
    u = syncunits.locate(case.unit)
    files = syncunits.files_of(u)
    try:
        with synclock.sync_write(case.unit):
            synckeep.keep(case.unit, "incoming", case.partner)
            for p in files.values():
                tmp = p + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(union, fh, ensure_ascii=False, indent=0, sort_keys=True)
                    fh.write("\n")
                os.replace(tmp, p)
    except synclock.Busy:
        return syncexchange.HELD
    synclog.refresh(case.unit)
    synclog.chosen(case.unit, case.theirs.get("vv") or {})
    return "combined"


def _deletion_kind(case):
    md = bool((case.mine or {}).get("deleted"))
    c = synclog.compare((case.mine or {}).get("vv"), case.theirs.get("vv"))
    if case.theirs.get("deleted") and not md and c == "behind":
        return "deletion"
    return "deletion-edited"


def on_question(case):
    """Changed on both sides, or a deletion: asked, unless already answered."""
    if _settled_by_answer(case):
        return "answered"
    pair = _pair(case.mine, case.theirs)
    old = _question_of(case.unit, case.partner)
    if old is not None:
        for u in old["units"]:
            if u["unit"] == case.unit and u.get("pair") == pair:
                return syncexchange.HELD           # asked already, nothing new
    kind = "choice" if case.situation != "deletion" else _deletion_kind(case)
    mine_v = _mine_version(case.unit)
    theirs_v = _theirs_version(case)
    me_label, them_label = _my_name(), partner_name(case.partner)
    entry = {"unit": case.unit, "kind": syncunits.kind_of(case.unit), "title": title(case.unit),
             "pair": pair, "mine_state": _vstate(case.mine), "theirs_state": _vstate(case.theirs),
             "mine_vv": (case.mine or {}).get("vv") or {}, "theirs_vv": case.theirs.get("vv") or {}}
    prev = {"mine": diff_of(case.unit, theirs_v, mine_v, them_label, me_label)[:PREVIEW_MAX],
            "theirs": diff_of(case.unit, mine_v, theirs_v, me_label, them_label)[:PREVIEW_MAX]}
    entry["preview"] = dict(prev)
    mine = {"at": _when(case.unit) if case.mine else None, "summary": _summary(case.mine, mine_v)}
    theirs = {"at": _when(None, case.partner, case.unit), "summary": _summary(case.theirs, theirs_v)}
    if old is not None:
        _drop_units(case.partner, [case.unit])
    group_key = (id(case._pull), case.partner)
    q = _GROUPS.get(group_key) if kind == "deletion" else None
    if q is not None and _question_of(q["units"][0]["unit"], case.partner) is not None:
        q = _question_of(q["units"][0]["unit"], case.partner)
        q["units"].append(entry)
        for side, v in (("mine", prev["mine"]), ("theirs", prev["theirs"])):
            q["preview"][side] = (q["preview"].get(side, "") + "\n" + v)[:PREVIEW_MAX]
        q["mine"]["summary"] = q["theirs"]["summary"] = "%d units" % len(q["units"])
    else:
        q = {"id": _qid(kind, case.partner, [case.unit]), "kind": kind, "partner": case.partner,
             "units": [entry], "mine": mine, "theirs": theirs, "preview": prev, "origin": "here",
             "at": time.time()}
        if kind == "deletion":
            _GROUPS[group_key] = q
    _save_q(q)
    _send(case.partner, "rules.ask", {"question": _swap(json.loads(json.dumps(q)))})
    return syncexchange.HELD


# ------------------------------------------------------------------ the ops (what the partner calls)
def op_when(partner, payload, body):
    rows = {}
    for uid in (payload.get("units") or [])[:1000]:
        r = synclog.get(str(uid))
        if r:
            rows[uid] = {"at": r.get("at"), "hash": r.get("hash"), "deleted": r.get("deleted")}
    return {"ok": True, "rows": rows}, None


def op_decided(partner, payload, body):
    return {"ok": True, "winner": _decision(str(payload.get("unit")), partner, str(payload.get("pair")))}, None


def op_ask(partner, payload, body):
    """The partner holds a question this computer should see too."""
    q = payload.get("question") or {}
    if not isinstance(q, dict) or not q.get("id") or not isinstance(q.get("units"), list):
        return {"ok": False, "error": "not a question"}, None
    q["partner"], q["origin"] = partner, "told"
    for u in q["units"]:
        if _decision(u["unit"], partner, u.get("pair")):
            return {"ok": True, "answered": True}, None
    with _LOCK:
        for old in _questions(partner):
            if {u["unit"] for u in old["units"]} & {u["unit"] for u in q["units"]}:
                if old["id"] <= q["id"] and old["origin"] == "here":
                    return {"ok": True, "kept": old["id"]}, None
                _drop_units(partner, [u["unit"] for u in q["units"]])
        _save_q(q)
    return {"ok": True}, None


def op_answer(partner, payload, body):
    """The partner answered a question: the same answer here."""
    units = payload.get("units") or []
    for u in units:
        _decide(u["unit"], partner, u["winner"], u["pair"])
        syncexchange.clear_pending(u["unit"], partner)
    _drop_units(partner, [u["unit"] for u in units])
    if payload.get("diff") and units:
        _write_diff(units[0]["unit"] if len(units) == 1 else "sync-%d-units" % len(units),
                    payload["diff"], ", ".join(u.get("title") or u["unit"] for u in units))
    syncexchange.request(partner, "a question answered there")
    return {"ok": True}, None


def op_drop(partner, payload, body):
    """The partner took this computer's versions (make identical): its questions go."""
    uids = [str(u) for u in payload.get("units") or []]
    for uid in uids:
        syncexchange.clear_pending(uid, partner)
    _drop_units(partner, uids)
    return {"ok": True}, None


OPS = {"rules.when": op_when, "rules.decided": op_decided, "rules.ask": op_ask,
       "rules.answer": op_answer, "rules.drop": op_drop}


def _send(partner, op, payload):
    """Tell the partner now, or when it is next heard."""
    if _call(partner, op, payload) is None:
        with _LOCK:
            _db().execute("INSERT INTO outbox (partner, op, payload, at) VALUES (?,?,?,?)",
                          (partner, op, json.dumps(payload), time.time()))
        return False
    return True


def flush_outbox(partner):
    with _LOCK:
        rows = _db().execute("SELECT n, op, payload FROM outbox WHERE partner=? ORDER BY n",
                             (partner,)).fetchall()
    for n, op, payload in rows:
        if _call(partner, op, json.loads(payload)) is None:
            return False
        with _LOCK:
            _db().execute("DELETE FROM outbox WHERE n=?", (n,))
    return True


# ------------------------------------------------------------------ hooks into the exchange
def _before_pull(partner):
    flush_outbox(partner)


def _after_pull(partner, theirs, out):
    """Questions the two computers now agree on go (answered elsewhere, or by an edit)."""
    for k in [k for k in _GROUPS if k[1] == partner]:
        _GROUPS.pop(k, None)
    def agreed(uid):
        m, t = synclog.get(uid), theirs.get(uid)
        gone_m = m is None or m.get("deleted")
        gone_t = t is None or t.get("deleted")
        return (gone_m and gone_t) or (not gone_m and not gone_t and m.get("hash") == t.get("hash"))
    done = [u["unit"] for q in _questions(partner) for u in q["units"] if agreed(u["unit"])]
    if done:
        _drop_units(partner, done)
    # a decision lives until the two computers agree: a later conflict on the
    # same unit is a new one, asked again, even between the same two versions
    with _LOCK:
        decided = [r[0] for r in _db().execute("SELECT unit FROM decisions WHERE partner=?", (partner,))]
    for uid in decided:
        if agreed(uid):
            with _LOCK:
                _db().execute("DELETE FROM decisions WHERE unit=? AND partner=?", (uid, partner))


def _on_taken(uid, partner):
    """A partner's version written here: its question goes; a version a choice
    made here or there discarded is kept as the choice's, not as an incoming one."""
    with _LOCK:
        r = _db().execute("SELECT winner FROM decisions WHERE unit=? AND partner=?", (uid, partner)).fetchone()
    if r and r[0] == partner:
        for e in synckeep.entries():
            if e.get("unit") == uid and e.get("partner") == partner and time.time() - (e.get("at") or 0) < 300:
                if e.get("why") == "incoming":
                    import storeguard
                    e["why"] = "choice"
                    storeguard.write_json(os.path.join(synckeep.kept_dir(), e["id"], "entry.json"), e)
                break
    _drop_units(partner, [uid])
    _mark_out_of_date(uid)


def install():
    """Register the rules with the exchange and the ops with lane A's router (serve.py, tests)."""
    syncexchange.RULES.update({"both": on_question, "deletion": on_question, "setting": on_setting,
                               "latest": on_setting, "progress": on_progress, "additions": on_additions})
    for lst, fn in ((syncexchange.ON_TAKEN, _on_taken), (syncexchange.BEFORE_PULL, _before_pull),
                    (syncexchange.AFTER_PULL, _after_pull)):
        if fn not in lst:
            lst.append(fn)
    import syncroutes
    for op, h in OPS.items():
        syncroutes.register(op, h)


# ------------------------------------------------------------------ the API lane E's pages call
def questions():
    """Every question waiting on this computer, oldest first."""
    return [_public(q) for q in _questions()]


def question_for(uid):
    q = _question_of(uid)
    return _public(q) if q else None


CHOICES = {"choice": ("mine", "theirs"), "deletion": ("delete", "restore"),
           "deletion-edited": ("send-edited", "delete")}


def _winner_of(q, u, choice):
    """Which install's version wins for unit entry u."""
    me, them = _me(), q["partner"]
    if q["kind"] == "choice":
        return me if choice == "mine" else them
    mine_gone = u.get("mine_state") == "deleted"
    if choice == "delete":
        return me if mine_gone else them
    return them if mine_gone else me                     # restore / send-edited: the live side wins


def answer(qid, choice, unit=None):
    """Answer a question here and for the partner -> {"ok", "diff_id"}.
    unit: answer one unit of a grouped deletion ("go through them")."""
    q = next((x for x in _questions() if x["id"] == qid), None)
    if q is None:
        return {"ok": False, "error": "no such question (answered already?)", "diff_id": None}
    if choice not in CHOICES.get(q["kind"], ()):
        return {"ok": False, "error": "the answers here are %s" % " / ".join(CHOICES[q["kind"]]),
                "diff_id": None}
    entries = [u for u in q["units"] if unit is None or u["unit"] == unit]
    if not entries:
        return {"ok": False, "error": "that unit is not in the question", "diff_id": None}
    me, partner = _me(), q["partner"]
    why = "choice" if q["kind"] == "choice" else "deletion"
    told, texts, failed = [], [], {}
    near = _call(partner, "rules.when", {"units": []}) is not None   # heard now? else the decision waits
    # never beside a sync with the same partner (they would fetch the same files at once);
    # a sync running now settles the units itself, by the decisions recorded below
    plock = syncexchange._plock(partner)
    locked = near and plock.acquire(timeout=PLOCK_WAIT)
    try:
        return _answer(q, entries, choice, me, partner, why, told, texts, failed,
                       syncexchange.Pull(partner) if locked else None, near)
    finally:
        if locked:
            plock.release()


def _answer(q, entries, choice, me, partner, why, told, texts, failed, pull, near):
    for u in entries:
        uid = u["unit"]
        winner = _winner_of(q, u, choice)
        _decide(uid, partner, winner, u["pair"])
        syncexchange.clear_pending(uid, partner)
        prev = u.get("preview") or {}
        if winner == me:
            texts.append(prev.get("theirs", ""))
            try:
                synclog.chosen(uid, u.get("theirs_vv") or {})
            except KeyError:
                pass
        else:
            texts.append(prev.get("mine", ""))
            if pull is None:
                failed[uid] = ("%s cannot be reached now: taken at the next sync" % partner_name(partner)
                               if not near else "a sync with %s is running: it takes it" % partner_name(partner))
            else:
                try:
                    synclog.flush()
                    r = pull.take(uid, why=why, force=True)
                    if r != "taken":
                        failed[uid] = r
                except Exception as e:                # noqa: BLE001 -- taken at the next sync, by the decision
                    failed[uid] = str(e)
        told.append({"unit": uid, "winner": winner, "pair": u["pair"], "title": u.get("title")})
    _drop_units(partner, [u["unit"] for u in entries])
    text = "".join(t for t in texts if t)
    diff_id = None
    if text.strip():
        name_uid = entries[0]["unit"] if len(entries) == 1 else "sync-%d-units" % len(entries)
        diff_id = _write_diff(name_uid, text, ", ".join(u.get("title") or u["unit"] for u in entries))
    _send(partner, "rules.answer", {"units": told, "choice": choice, "diff": text})
    _call(partner, "sync.nudge", {})
    out = {"ok": True, "diff_id": diff_id}
    if failed:
        out["waiting"] = failed                   # settled by the next sync with the partner
    return out


# ------------------------------------------------------------------ make this computer identical
def _plan(partner):
    got = _call(partner, "sync.have", {}, timeout=syncexchange.TIMEOUT)
    if not got:
        raise RuntimeError("%s cannot be reached now" % partner_name(partner))
    synclog.flush()
    synclog.scan()
    theirs = {r["unit"]: r for r in got.get("rows") or [] if isinstance(r, dict) and r.get("unit")}
    mine = {r["unit"]: r for r in synclog.rows()}
    holds = syncexchange.holder()
    plan = {"replace": [], "add": [], "delete": [], "lost": []}
    for uid in sorted(set(theirs) | set(mine)):
        try:
            syncunits.locate(uid)
        except KeyError:
            continue
        if not holds(uid):
            continue
        m, t = mine.get(uid), theirs.get(uid)
        m_live = m is not None and not m.get("deleted")
        t_live = t is not None and not t.get("deleted")
        if t_live and not m_live:
            plan["add"].append(uid)
        elif t_live and m_live and m.get("hash") != t.get("hash"):
            plan["replace"].append(uid)
        elif m_live and not t_live:
            plan["delete"].append(uid)
        else:
            continue
        if m_live and (t is None or synclog.compare(m.get("vv"), t.get("vv")) in ("ahead", "both")):
            plan["lost"].append(uid)
    return plan, theirs


def _jobs(partner):
    out = []
    for fn in list(JOBS):
        try:
            out.extend(fn(partner) or [])
        except Exception as e:                         # noqa: BLE001
            print("!! sync: a job list failed: %s" % e, flush=True)
    return out


def identical_summary(partner_id):
    """What "make this computer identical to <partner>" would change here."""
    plan, _ = _plan(partner_id)
    return {"replace": len(plan["replace"]), "add": len(plan["add"]), "delete": len(plan["delete"]),
            "lost": [{"unit": u, "title": title(u)} for u in plan["lost"]],
            "questions": len(_questions(partner_id)), "jobs": _jobs(partner_id)}


def make_identical(partner_id):
    """This computer takes the partner's state, with no question; the partner is
    not changed.  -> {"ok", "diff_id", "replaced", "added", "deleted", "failed"}."""
    partner = partner_id
    with syncexchange._plock(partner):
        plan, theirs = _plan(partner)
        pull = syncexchange.Pull(partner)
        texts, failed = [], {}
        lost = set(plan["lost"])
        uids = [u["unit"] for q in _questions(partner) for u in q["units"]]   # before a take drops them
        for uid in plan["replace"] + plan["add"] + plan["delete"]:
            mine_v = _mine_version(uid)
            t = theirs.get(uid)
            try:
                if uid in lost:
                    theirs_v = _theirs_version(pull, uid) if t is not None else None
                    texts.append(diff_of(uid, theirs_v, mine_v, partner_name(partner), _my_name()))
                if t is not None:
                    r = pull.take(uid, why="identical", force=True)
                else:                                   # the partner never had it: gone here
                    r = _delete_here(uid, partner)
                if r != "taken":
                    failed[uid] = r
            except Exception as e:                      # noqa: BLE001
                failed[uid] = str(e)
        uids += [u["unit"] for q in _questions(partner) for u in q["units"]]
        for uid in uids:
            syncexchange.clear_pending(uid, partner)
        _drop_units(partner, uids)
        for p in syncexchange.pending(partner):
            syncexchange.clear_pending(p["unit"], partner)
        if uids:
            _send(partner, "rules.drop", {"units": uids})
        jobs = _jobs(partner)
        for fn in list(CANCEL_JOBS):
            try:
                fn(partner, jobs)
            except Exception as e:                      # noqa: BLE001
                print("!! sync: cancelling jobs failed: %s" % e, flush=True)
    text = "".join(t for t in texts if t)
    diff_id = None
    if text.strip():
        diff_id = _write_diff("identical-to-%s" % partner_name(partner), text,
                              "made identical to %s" % partner_name(partner))
    return {"ok": not failed, "diff_id": diff_id, "replaced": len(plan["replace"]),
            "added": len(plan["add"]), "deleted": len(plan["delete"]), "failed": failed}


def _delete_here(uid, partner):
    u = syncunits.locate(uid)
    row = synclog.get(uid) or {}
    try:
        with synclock.sync_write(uid):
            synckeep.keep(uid, "identical", partner)
            syncexchange._apply(u, {"unit": uid, "deleted": True, "hash": None,
                                    "vv": row.get("vv") or {}}, {}, partner)
    except synclock.Busy:
        return "waiting"
    synclog.touch(u.where)
    return "taken"


# ------------------------------------------------------------------ kept for a day, diff files
def kept():
    out = []
    for e in synckeep.entries():
        out.append({"id": e["id"], "unit": e["unit"], "title": title(e["unit"]), "why": e.get("why"),
                    "partner": e.get("partner"), "partner_name": partner_name(e["partner"]) if e.get("partner")
                    else None, "at": e.get("at"), "until": e.get("until")})
    return out


def put_back(kept_id):
    try:
        uid = synckeep.put_back(kept_id)
    except synclock.Busy:
        return {"ok": False, "error": "it is open in an editor; close it and try again"}
    except (KeyError, OSError) as e:
        return {"ok": False, "error": "nothing kept by that name (%s)" % e}
    syncexchange.request(None, "a version put back")
    return {"ok": True, "unit": uid}


def _write_diff(uid, text, words):
    got = synckeep.write_diff(uid, text)
    with _LOCK:
        _db().execute("INSERT OR REPLACE INTO diffs VALUES (?,?,?,?)", (got["name"], uid, words, time.time()))
    return got["name"]


def diffs():
    with _LOCK:
        meta = {r[0]: r for r in _db().execute("SELECT name, unit, title, at FROM diffs").fetchall()}
    out = []
    for d in synckeep.diffs():
        m = meta.get(d["name"])
        out.append({"id": d["name"], "unit": m[1] if m else None, "title": m[2] if m else d["name"],
                    "at": m[3] if m else d["at"], "size": d["size"]})
    return out


def diff_path(diff_id):
    for d in synckeep.diffs():
        if d["name"] == diff_id:
            return d["path"]
    raise KeyError(diff_id)


def delete_diff(diff_id):
    gone = synckeep.delete_diff(diff_id)
    with _LOCK:
        _db().execute("DELETE FROM diffs WHERE name=?", (diff_id,))
    return {"ok": gone}


# ------------------------------------------------------------------ out of date
def _builds(uid):
    """The built files that depend on a unit -> {what: path}."""
    try:
        u = syncunits.locate(uid)
    except KeyError:
        return {}
    if u.key is not None:
        return {}
    w = u.where
    if u.kind == "book":
        cand = {"the PDF": os.path.join(w, "main.pdf"), "the reader": os.path.join(w, "reader", "index.html")}
    elif u.kind in ("doc", "note"):
        b = os.path.join(w, "build")
        cand = {}
        try:
            for n in sorted(os.listdir(b)):
                if n.endswith((".pdf", ".tex", ".html")):
                    cand["the %s" % ("PDF" if n.endswith(".pdf") else ".tex" if n.endswith(".tex") else "page")] = \
                        os.path.join(b, n)
        except OSError:
            pass
    else:
        return {}
    return {k: p for k, p in cand.items() if os.path.isfile(p)}


def _mark_out_of_date(uid):
    b = _builds(uid)
    if not b:
        return
    row = synclog.get(uid) or {}
    with _LOCK:
        _db().execute("INSERT OR REPLACE INTO outdated VALUES (?,?,?,?)",
                      (uid, json.dumps(sorted(b)), row.get("hash"), time.time()))


def is_out_of_date(uid):
    """A build of this unit was made before its source last changed through sync
    (a build newer than that change clears it)."""
    with _LOCK:
        r = _db().execute("SELECT at FROM outdated WHERE unit=?", (uid,)).fetchone()
    if r is None:
        return False
    b = _builds(uid)
    stale = [p for p in b.values() if os.path.getmtime(p) < r[0]]
    if not stale:
        with _LOCK:
            _db().execute("DELETE FROM outdated WHERE unit=?", (uid,))
        return False
    return True


def out_of_date():
    with _LOCK:
        rows = _db().execute("SELECT unit, what, at FROM outdated ORDER BY at").fetchall()
    out = []
    for uid, what, at in rows:
        if is_out_of_date(uid):
            stale = [w for w, p in _builds(uid).items() if os.path.getmtime(p) < at]
            out.append({"unit": uid, "title": title(uid), "what": stale})
    return out


# ------------------------------------------------------------------ one JSON door for the pages and tests
def json_api(body):
    """POST /settings/api/devices/rules {"do": …} -> the API above as JSON."""
    do = str(body.get("do") or "")
    if do == "questions":
        return {"ok": True, "questions": questions()}
    if do == "question_for":
        return {"ok": True, "question": question_for(str(body.get("unit") or ""))}
    if do == "answer":
        return answer(str(body.get("id") or ""), str(body.get("choice") or ""), body.get("unit") or None)
    if do == "identical_summary":
        return dict(identical_summary(str(body.get("partner") or "")), ok=True)
    if do == "make_identical":
        return make_identical(str(body.get("partner") or ""))
    if do == "kept":
        return {"ok": True, "kept": kept()}
    if do == "put_back":
        return put_back(str(body.get("id") or ""))
    if do == "diffs":
        return {"ok": True, "diffs": diffs()}
    if do == "diff":
        p = diff_path(str(body.get("id") or ""))
        with open(p, encoding="utf-8") as fh:
            return {"ok": True, "id": body.get("id"), "text": fh.read()}
    if do == "delete_diff":
        return delete_diff(str(body.get("id") or ""))
    if do == "out_of_date":
        return {"ok": True, "out_of_date": out_of_date()}
    raise ValueError("no such step: %s" % do)
