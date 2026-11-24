# SPDX-License-Identifier: GPL-3.0-or-later
"""Undo for one day, and the diff files (a0.7.0, docs/sync.md).

EVERY VERSION A SYNC REPLACES OR DELETES on this computer is kept here first,
for one day: an incoming change, a choice, an answered deletion, "make this
computer identical".  Settings → Devices lists them and can put any back
(`put_back`); after a day `clean()` removes them -- at the server's start and
every hour (lib/synclog.start).

    config/sync/kept/<id>/entry.json   {"id", "unit", "why", "partner", "at",
                                        "until", "hash", "vv", "files": [inner…]
                                        | "value": the setting's value}
    config/sync/kept/<id>/files/<inner name>    the unit's files as they were

THE DIFF FILES -- what a choice discarded, as git would show it -- are kept in
config/sync/diffs/ until the PERSON deletes them; nothing here ever cleans
them.  `text_diff` and `fields_diff` make the two kinds the rules need (a
unified diff for text; the changed fields for a structured file); the rules
(lane C) decide what goes in one and call `write_diff`.

Both folders are this device's and never synced.  Standard library only.
"""
import difflib
import json
import os
import re
import secrets
import shutil
import sys
import time

LIB = os.path.dirname(os.path.abspath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import storeguard                                              # noqa: E402
import synclock                                                # noqa: E402
import synclog                                                 # noqa: E402
import syncunits                                               # noqa: E402

KEEP_FOR = 24 * 3600
WHY = ("incoming", "choice", "deletion", "identical")
_ID = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{8}$")
_DIFF = re.compile(r"^[\w.\-]{1,200}\.diff$")


def kept_dir():
    return os.path.join(synclog.home(), "kept")


def diffs_dir():
    return os.path.join(synclog.home(), "diffs")


def _entry_dir(entry_id):
    if not _ID.match(str(entry_id or "")):
        raise KeyError(entry_id)
    return os.path.join(kept_dir(), entry_id)


# ------------------------------------------------------------------ keeping
def keep(uid, why, partner=None, now=None):
    """Keep the unit as it is NOW, before sync replaces or deletes it -> the
    entry, or None when there is nothing here to keep."""
    if why not in WHY:
        raise ValueError(why)
    u = syncunits.locate(uid)
    now = time.time() if now is None else now
    entry = {"id": "%s-%s" % (time.strftime("%Y%m%d-%H%M%S", time.localtime(now)), secrets.token_hex(4)),
             "unit": uid, "why": why, "partner": partner, "at": now, "until": now + KEEP_FOR}
    row = synclog.get(uid)
    entry["hash"], entry["vv"] = (row["hash"], row["vv"]) if row else (None, {})
    d = os.path.join(kept_dir(), entry["id"])
    if u.key is not None:
        v = syncunits.value_of(u)
        if v is None:
            return None
        entry["value"] = v
        os.makedirs(d)
    else:
        files = syncunits.files_of(u)
        if not files:
            return None
        os.makedirs(os.path.join(d, "files"))
        for inner, p in sorted(files.items()):
            dst = os.path.join(d, "files", *inner.split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(p, dst)
        entry["files"] = sorted(files)
    storeguard.write_json(os.path.join(d, "entry.json"), entry)
    return entry


def entries(now=None):
    """The versions kept and not yet cleaned, newest first."""
    out = []
    try:
        names = os.listdir(kept_dir())
    except OSError:
        return out
    for n in names:
        if not _ID.match(n):
            continue
        try:
            with open(os.path.join(kept_dir(), n, "entry.json"), encoding="utf-8") as fh:
                e = json.load(fh)
        except (OSError, ValueError):
            continue
        out.append(e)
    out.sort(key=lambda e: e.get("at") or 0, reverse=True)
    return out


def drop(entry_id):
    shutil.rmtree(_entry_dir(entry_id), ignore_errors=True)


def clean(now=None):
    """Remove what was kept more than a day ago -> how many went.  An entry
    whose entry.json cannot be read is judged by its folder's time."""
    now = time.time() if now is None else now
    gone = 0
    try:
        names = os.listdir(kept_dir())
    except OSError:
        return 0
    for n in names:
        d = os.path.join(kept_dir(), n)
        if not _ID.match(n) or not os.path.isdir(d):
            continue
        try:
            with open(os.path.join(d, "entry.json"), encoding="utf-8") as fh:
                until = float(json.load(fh)["until"])
        except (OSError, ValueError, KeyError, TypeError):
            try:
                until = os.stat(d).st_mtime + KEEP_FOR
            except OSError:
                continue
        if until <= now:
            shutil.rmtree(d, ignore_errors=True)
            gone += 1
    return gone


# ------------------------------------------------------------------ putting back
def _set_key(path, key, value):
    """Put a value back at its key inside a config store, through
    storeguard; under the store's own module lock when it has one."""
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        doc = {}
    cur, keys = doc, list(key)
    while len(keys) > 1:
        k = keys.pop(0)
        if k.startswith("#"):
            field, want = k[1:], keys.pop(0)
            rows = cur if isinstance(cur, list) else []
            rows[:] = [r for r in rows if not (isinstance(r, dict) and r.get(field) == want)]
            rows.append(value)
            break
        cur = cur.setdefault(k, [] if keys[0].startswith("#") else {})
    else:
        cur[keys[0]] = value
    storeguard.write_json(path, doc)


def put_back(entry_id):
    """Put a kept version back in place of what is there now -> the unit id.
    It is THIS computer's change from then on (the log records it as one, and
    it travels).  Busy (lib/synclock.py) while an editor holds the unit."""
    d = _entry_dir(entry_id)
    with open(os.path.join(d, "entry.json"), encoding="utf-8") as fh:
        e = json.load(fh)
    u = syncunits.locate(e["unit"])
    held = synclock.editing(u.id)
    if held:
        raise synclock.Busy(u.id, held)
    if u.key is not None:
        _set_key(u.where, u.key, e["value"])
    else:
        now = syncunits.files_of(u)
        keep_names = set(e.get("files") or [])
        for inner in keep_names:
            src = os.path.join(d, "files", *inner.split("/"))
            dst = syncunits.path_of(u, inner)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            tmp = "%s.%s.tmp" % (dst, secrets.token_hex(4))
            shutil.copy2(src, tmp)
            os.replace(tmp, dst)
        for inner, p in now.items():
            if inner not in keep_names:
                try:
                    os.unlink(p)
                except OSError:
                    pass
        synclog.touch(u.where)
    synclog.refresh(u.id)
    return u.id


# ------------------------------------------------------------------ the diff files
def text_diff(kept, discarded, kept_label, discarded_label):
    """A unified diff that turns the version KEPT into the one discarded: what
    the person would add back by hand to have the other side's."""
    a = (kept or "").splitlines(keepends=True)
    b = (discarded or "").splitlines(keepends=True)
    out = "".join(difflib.unified_diff(a, b, kept_label, discarded_label))
    return out if out.endswith("\n") or not out else out + "\n"


def fields_diff(kept, discarded, path=""):
    """The changed fields of two structured values -> ["key.sub: kept → discarded"]."""
    out = []
    if isinstance(kept, dict) and isinstance(discarded, dict):
        for k in sorted(set(kept) | set(discarded), key=str):
            p = "%s.%s" % (path, k) if path else str(k)
            if k not in discarded:
                out.append("%s: %s → (none)" % (p, json.dumps(kept[k], ensure_ascii=False)))
            elif k not in kept:
                out.append("%s: (none) → %s" % (p, json.dumps(discarded[k], ensure_ascii=False)))
            else:
                out.extend(fields_diff(kept[k], discarded[k], p))
    elif kept != discarded:
        out.append("%s: %s → %s" % (path or "(value)", json.dumps(kept, ensure_ascii=False),
                                    json.dumps(discarded, ensure_ascii=False)))
    return out


def write_diff(uid, text, now=None):
    """Keep a diff file in the diffs folder -> {"name", "path"}."""
    now = time.time() if now is None else now
    slug = re.sub(r"[^\w.\-]+", "-", uid).strip("-")[:120] or "unit"
    name = "%s-%s.diff" % (time.strftime("%Y%m%d-%H%M%S", time.localtime(now)), slug)
    path = os.path.join(diffs_dir(), name)
    n = 2
    while os.path.exists(path):
        name = "%s-%s-%d.diff" % (time.strftime("%Y%m%d-%H%M%S", time.localtime(now)), slug, n)
        path, n = os.path.join(diffs_dir(), name), n + 1
    storeguard.write_text(path, text)
    return {"name": name, "path": path}


def diffs():
    """The diff files, newest first -> [{"name", "path", "size", "at"}]."""
    out = []
    try:
        names = os.listdir(diffs_dir())
    except OSError:
        return out
    for n in names:
        p = os.path.join(diffs_dir(), n)
        if _DIFF.match(n) and os.path.isfile(p):
            st = os.stat(p)
            out.append({"name": n, "path": p, "size": st.st_size, "at": st.st_mtime})
    out.sort(key=lambda r: r["at"], reverse=True)
    return out


def delete_diff(name):
    """The person deletes a diff file -> True when it was there."""
    if not _DIFF.match(str(name or "")):
        raise KeyError(name)
    try:
        os.unlink(os.path.join(diffs_dir(), name))
        return True
    except FileNotFoundError:
        return False
