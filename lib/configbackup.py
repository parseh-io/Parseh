# SPDX-License-Identifier: GPL-3.0-or-later
"""The backup of your settings, config/ (TO-DO §13.19): Backup, and Load from
backup, which MERGES and never overwrites silently.

    path, name = configbackup.pack()                 a zip in a temporary file; the caller deletes it
    got = configbackup.read(zip_bytes_or_path)       checked whole, or BackupError in words
    configbackup.plan(got)                           what loading it would do, store by store
    configbackup.apply(got, {"prompts.json:p1a2b3c4": "backup"})   do it

WHAT IS IN IT, store by store, and why (the page and the guide say the same,
from STORES and LEFT_OUT below):

  prefs.json      the reading places, the chunks flagged to review later, the
                  settings that follow you and the names you gave the levels
  prompts.json    your own prompts
  languages.json  the languages you added, WITH their files (lib/lang/<code>.tex
                  and its lookup rules, docs/lang/<code>.md, the studio's starter):
                  a row without its LaTeX file is a language no book can be built in
  latex.json      your LaTeX themes, the default one, how long a drawing may take
  analysis.json   where the optional analyzers are listened to (a choice for one
                  this computer has not got falls back, as it always does)
  speech.json     which speech model for which language, and the checks for
                  suspect words (the models themselves are fetched again)

WHAT IS LEFT OUT is what belongs to the computer and not to the person: who may
reach it and the devices it let in, with their tokens (network.json: a token
copied is a device let in on a computer that never let it in), what phones
keep, by this computer's paths (digests.json, wheres.json), what the updater
last found (updates.json), the paths of this computer's own interpreter and
model (lm-likelihood.json), the retired LLM connection that may hold a key
(llm.json), and the days of this computer's own backups (backups.json).

LOADING MERGES, BY EACH STORE'S OWN RULES.  What the backup has and this
computer has not is ADDED.  What both have alike is left.  What both have and
differs is decided either by the store's own rule -- a reading place, a
setting, a level's name: the later change wins, as between two devices; a
flag to review later: the rule of lib/later.py, tombstones and all, so a flag
removed on either side after the other made it stays removed -- or, where
there is no such rule (a prompt, a language, a LaTeX theme, a choice), BY THE
PERSON: plan() lists each, keeping yours unless the person picks the backup's.
Every write goes through each store's own writer and so through
lib/storeguard.py: whole, fsync'd, a damaged file set aside, never written over.

A BACKUP IS CHECKED WHOLE BEFORE ANYTHING IS WRITTEN: its list of files and
their SHA-256, each store parsed and of the shape its store is, each made by
this Parseh or an older one.  A file that does not match its hash, a store
that does not parse, one from a newer Parseh: refused in words, and nothing is
loaded.  An older store's shape is read the way this Parseh reads its own
older files (every store reads through its own cleaning); none is older yet.
"""
import copy
import hashlib
import io
import json
import os
import re
import secrets
import threading
import time
import zipfile
from datetime import datetime

import analysisconfig
import languages
import langprompts
import later
import latexthemes
import prefs
import prompts
import scratch
import speechconfig
import storeguard

FORMAT = "parseh-config/1"
MANIFEST = "parseh-config.json"
MAX_ENTRIES = 5000
MAX_TOTAL = 256 * 1024 * 1024       # prompts of 300,000 characters each would need hundreds to reach it
MAX_LISTED = 300                    # rows a plan lists per store; the rest are counted

STORES = (
    ("prefs.json", "Reading places, flags to review later, the settings that follow you, the names of the levels",
     lambda: prefs.STORE),
    ("prompts.json", "Your own prompts", lambda: prompts.STORE),
    ("languages.json", "The languages you added, with their files", lambda: languages.PERSONAL),
    ("latex.json", "Your LaTeX themes, the default one, how long a drawing may take", lambda: latexthemes.STORE),
    ("analysis.json", "Where the optional analyzers are used", lambda: analysisconfig.STORE),
    ("speech.json", "Which speech model for which language, and the checks for suspect words",
     lambda: str(speechconfig.CONFIG)),
)
NAMES = tuple(s[0] for s in STORES)
LABEL = {s[0]: s[1] for s in STORES}

LEFT_OUT = (
    ("network.json", "who may reach Parseh, its port, its certificate and the devices it let in with their "
                     "tokens: a new computer decides its own, and a token copied would let a device in on a "
                     "computer that never let it in"),
    ("digests.json", "what phones keep, by this computer's own paths: made again when a phone keeps something"),
    ("wheres.json", "where a phone's kept recordings are, by this computer's own paths: made again likewise"),
    ("updates.json", "what this computer last found when it looked for a new Parseh"),
    ("lm-likelihood.json", "the paths of this computer's own interpreter and model files"),
    ("llm.json", "the LLM connection of a0.6.2 and before: no longer read, and it may hold a key"),
    ("backups.json", "the days of this computer's own backups"),
)

# a language's files, as they are named in the zip: lang/<code>.tex, lang/<code>.<piece>.json,
# docs/<code>.md, starters/<code>.md
_FILE = re.compile(r"^(lang|docs|starters)/([a-z][a-z0-9-]{1,15})\.(tex|md|[a-z]+\.json)$")
_CODE = re.compile(r"^[a-z][a-z0-9-]{1,15}$")
_WHERE = {"lang": lambda: langprompts.LANG_FILES, "docs": lambda: langprompts.LANG_DOCS,
          "starters": lambda: langprompts.STARTERS}


class BackupError(Exception):
    """A backup refused, in words for the person who chose it."""


# ------------------------------------------------------------------ helpers
def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _number(stamp, name):
    """A store's format number from what it carries (a number, or "name/N") -> int, or None."""
    if isinstance(stamp, bool):
        return None
    if isinstance(stamp, int):
        return stamp
    if isinstance(stamp, str):
        head, _s, n = stamp.rpartition("/")
        if head == name and n.isdigit():
            return int(n)
    return None


def _store_format(name, doc):
    """(the backup's number for this store, this Parseh's) -- None for the first when it says none."""
    if name == "prefs.json":
        return 1, prefs.STORE_FORMAT          # the file carries no number (lib/prefs.py says why)
    if name == "prompts.json":
        return _number(doc.get("format", 1), ""), prompts.STORE_FORMAT
    if name == "languages.json":
        ours = _number(languages.STORE_FORMAT, "parseh-languages")
        return _number(doc.get("_format", languages.STORE_FORMAT), "parseh-languages"), ours
    if name == "latex.json":
        return _number(doc.get("format", 1), ""), latexthemes.STORE_FORMAT
    if name == "analysis.json":
        return _number(doc.get("format"), ""), analysisconfig.STORE_FORMAT
    if name == "speech.json":
        return _number(doc.get("format_version"), ""), speechconfig.STORE_FORMAT
    return None, None


_SHAPE = {
    "prefs.json": lambda d: isinstance(d, dict),
    "prompts.json": lambda d: isinstance(d, dict) and isinstance(d.get("prompts"), list),
    "languages.json": lambda d: isinstance(d, dict),
    "latex.json": lambda d: isinstance(d, dict) and isinstance(d.get("themes"), list),
    "analysis.json": lambda d: isinstance(d, dict),
    "speech.json": lambda d: isinstance(d, dict),
}


def _language_files(code):
    """{name in the zip: path} of a language of the person's."""
    out = {}
    for kind, pattern in (("lang", code + ".tex"), ("docs", code + ".md"), ("starters", code + ".md")):
        p = os.path.join(_WHERE[kind](), pattern)
        if os.path.isfile(p):
            out["%s/%s" % (kind, pattern)] = p
    folder = _WHERE["lang"]()
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        names = []
    for n in names:
        if n.startswith(code + ".") and n.endswith(".json") and _FILE.match("lang/" + n) \
                and _FILE.match("lang/" + n).group(2) == code:
            out["lang/" + n] = os.path.join(folder, n)
    return out


def _file_path(zname):
    m = _FILE.match(zname)
    return os.path.join(_WHERE[m.group(1)](), "%s.%s" % (m.group(2), m.group(3)))


# ------------------------------------------------------------------ backing up
def present():
    """The stores of the person's this computer has -> [name]."""
    return [name for name, _label, where in STORES if os.path.isfile(where())]


def pack(stamp=None):
    """Your settings as one zip -> (path to a temporary file, file name), and
    the caller deletes the file.  A store that is not there is not in it; one
    that cannot be read is left out and said in the zip's list (`notes`)."""
    files, notes = {}, []
    for name, _label, where in STORES:
        path = where()
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except FileNotFoundError:
            continue
        except OSError as e:
            notes.append("config/%s could not be read (%s), and is not in this backup" % (name, e))
            continue
        try:
            doc = json.loads(data.decode("utf-8"))
            if not _SHAPE[name](doc):
                raise ValueError("not the shape of the store")
        except (ValueError, UnicodeDecodeError) as e:
            notes.append("config/%s cannot be read (%s), and is not in this backup" % (name, e))
            continue
        files["config/" + name] = data
        if name == "languages.json":
            for code in sorted(k for k in doc if not k.startswith("_")):
                if not _CODE.match(code):
                    continue
                for zname, p in _language_files(code).items():
                    try:
                        with open(p, "rb") as fh:
                            files[zname] = fh.read()
                    except OSError as e:
                        notes.append("%s could not be read (%s)" % (zname, e))
    import version
    manifest = {"format": FORMAT, "software": "Parseh", "version": version.VERSION,
                "exported": datetime.now().isoformat(timespec="seconds"),
                "files": {n: {"sha256": _sha(d), "size": len(d)} for n, d in files.items()},
                "left_out": [{"name": "config/" + n, "why": w} for n, w in LEFT_OUT],
                "notes": notes}
    fd, path = scratch.mkstemp(prefix="parseh-settings-", suffix=".zip")
    os.close(fd)
    try:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for n, d in sorted(files.items()):
                zf.writestr(n, d)
            zf.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8"))
    except BaseException:
        os.unlink(path)
        raise
    return path, "parseh-settings-backup-%s.zip" % (stamp or time.strftime("%Y%m%d-%H%M"))


# ------------------------------------------------------------------ reading one
class Backup(object):
    """A settings backup, read and checked: `stores` {name: document}, `files`
    {zip name: bytes} of the languages, the manifest, and `notes`."""

    def __init__(self, stores, files, manifest, notes):
        self.stores, self.files, self.manifest, self.notes = stores, files, manifest, notes


def _reads(stamp, fmt=FORMAT):
    name, _s, n = fmt.rpartition("/")
    if not isinstance(stamp, str) or not stamp.startswith(name + "/"):
        return None
    have = stamp[len(name) + 1:]
    if not have.isdigit():
        return None
    return int(have) <= int(n)


def read(source):
    """A settings backup -> Backup; BackupError, in words, for anything that
    is not one this Parseh can load whole.  `source` is bytes or a path."""
    try:
        zf = (zipfile.ZipFile(io.BytesIO(bytes(source)))
              if isinstance(source, (bytes, bytearray, memoryview)) else zipfile.ZipFile(source))
    except (zipfile.BadZipFile, ValueError, OSError, EOFError):
        raise BackupError("that is not a zip file")
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > MAX_ENTRIES:
            raise BackupError("that zip holds more than %d files: it is not a settings backup" % MAX_ENTRIES)
        if sum(i.file_size for i in infos) > MAX_TOTAL:
            raise BackupError("that zip is far larger than a settings backup can be")
        names = {i.filename: i for i in infos}
        if MANIFEST not in names:
            raise BackupError("that zip is not a backup of settings: it has no %s" % MANIFEST)
        try:
            manifest = json.loads(zf.read(names[MANIFEST]).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, zipfile.BadZipFile, OSError, EOFError):
            raise BackupError("that backup's %s cannot be read: the zip is damaged" % MANIFEST)
        fmt = manifest.get("format") if isinstance(manifest, dict) else None
        ok = _reads(fmt)
        if ok is None:
            raise BackupError("that zip is not a backup of settings this Parseh reads")
        if not ok:
            raise BackupError("that backup was made by a newer Parseh (it says %s, and this one reads %s): "
                              "update Parseh, then load it" % (fmt, FORMAT))
        listed = manifest.get("files")
        if not isinstance(listed, dict):
            raise BackupError("that backup's list of files cannot be read: the zip is damaged")
        data, notes = {}, []
        for zname, said in sorted(listed.items()):
            if not isinstance(said, dict) or zname not in names:
                raise BackupError("%s is in that backup's list and not in the zip: the backup is damaged, "
                                  "and nothing was loaded" % zname)
            try:
                raw = zf.read(names[zname])
            except (zipfile.BadZipFile, OSError, EOFError, ValueError):
                raise BackupError("%s in that backup cannot be read: the zip is damaged, and nothing was loaded"
                                  % zname)
            if _sha(raw) != said.get("sha256"):
                raise BackupError("%s in that backup is not the file that was backed up (its checksum differs): "
                                  "the backup is damaged, and nothing was loaded" % zname)
            data[zname] = raw
        stray = sorted(n for n in names if n != MANIFEST and n not in listed)
        if stray:
            notes.append("%d file(s) in the zip that its list does not name were not looked at" % len(stray))
    stores, files = {}, {}
    for name in NAMES:
        raw = data.get("config/" + name)
        if raw is None:
            continue
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise BackupError("config/%s in that backup is not readable: nothing was loaded" % name)
        if not _SHAPE[name](doc):
            raise BackupError("config/%s in that backup is not a store of that kind: nothing was loaded" % name)
        theirs, ours = _store_format(name, doc)
        if theirs is None:
            raise BackupError("config/%s in that backup says no shape this Parseh knows: nothing was loaded" % name)
        if theirs > ours:
            raise BackupError("config/%s in that backup was written by a newer Parseh (its shape %d, this one "
                              "reads %d): update Parseh, then load it" % (name, theirs, ours))
        stores[name] = doc
    rows = stores.get("languages.json") or {}
    for zname, raw in data.items():
        m = _FILE.match(zname)
        if not m:
            continue
        if m.group(2) not in rows:
            notes.append("%s belongs to no language in this backup, and was not looked at" % zname)
            continue
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            raise BackupError("%s in that backup is not text: nothing was loaded" % zname)
        files[zname] = raw
    if not stores:
        raise BackupError("that backup holds no settings at all")
    return Backup(stores, files, manifest, notes)


# ------------------------------------------------------------------ merging, store by store
def _at(v, now):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0.0
    if v != v:
        return 0.0
    return min(max(v, 0.0), now + 60.0)


def _row(rows, store, rid, what, state, will, mine="", theirs="", why=""):
    rows.append({"id": "%s:%s" % (store, rid), "store": store, "what": what, "state": state,
                 "will": will, "mine": mine, "theirs": theirs, "why": why})


def _chose(choose, store, rid):
    return (choose or {}).get("%s:%s" % (store, rid)) == "backup"


NEWER = "the later change wins, as between two devices"


def _merge_prefs(theirs, choose):
    doc = copy.deepcopy(prefs._read())
    now = time.time()
    rows, changed = [], False
    ts = theirs.get("settings") if isinstance(theirs.get("settings"), dict) else {}
    for key, val in sorted(ts.items()):
        if not prefs.follows(key) or not isinstance(val, dict):
            continue
        v = prefs._value(key, val.get("v"))
        if v is None:
            continue
        rec = {"v": v, "at": _at(val.get("at"), now), "by": prefs._clean(val.get("by"), 60)}
        what = ("the name of the level %s" % key[len(prefs.LEVEL_PREFIX):]
                if key.startswith(prefs.LEVEL_PREFIX) else "the setting %s" % key)
        was = doc["settings"].get(key)
        if not isinstance(was, dict):
            _row(rows, "prefs.json", "setting:" + key, what, "added", "backup", theirs=v)
            doc["settings"][key], changed = rec, True
        elif was.get("v") == v:
            continue
        else:
            newer = rec["at"] > _at(was.get("at"), now)
            _row(rows, "prefs.json", "setting:" + key, what, "differs", "backup" if newer else "mine",
                 mine=str(was.get("v")), theirs=v, why=NEWER)
            if newer:
                doc["settings"][key], changed = rec, True
    tp = theirs.get("places") if isinstance(theirs.get("places"), dict) else {}
    for path, rec in sorted(tp.items()):
        path = prefs._clean(path, 300)
        if not path or not isinstance(rec, dict):
            continue
        try:
            i = int(rec.get("i"))
        except (TypeError, ValueError):
            continue
        if i < 0:
            continue
        new = {"i": i, "label": prefs._clean(rec.get("label"), 80), "at": _at(rec.get("at"), now),
               "by": prefs._clean(rec.get("by"), 60)}
        if rec.get("pct") is not None:
            try:
                new["pct"] = max(0, min(100, int(rec["pct"])))
            except (TypeError, ValueError):
                pass
        was = doc["places"].get(path)
        if not isinstance(was, dict):
            _row(rows, "prefs.json", "place:" + path, "the reading place in %s" % path, "added", "backup",
                 theirs=new["label"] or str(i))
            doc["places"][path], changed = new, True
        elif was.get("i") == i:
            continue
        else:
            newer = new["at"] > _at(was.get("at"), now)
            _row(rows, "prefs.json", "place:" + path, "the reading place in %s" % path, "differs",
                 "backup" if newer else "mine", mine=str(was.get("label") or was.get("i")),
                 theirs=new["label"] or str(i), why=NEWER)
            if newer:
                doc["places"][path], changed = new, True
    if len(doc["places"]) > prefs.MAX_PLACES:
        old = sorted(doc["places"].items(), key=lambda kv: float(kv[1].get("at") or 0))
        for k, _v in old[:len(doc["places"]) - prefs.MAX_PLACES]:
            doc["places"].pop(k, None)
    # THE FLAGS TO REVIEW LATER, by lib/later.py's own rule: each of the backup's
    # entries is the change a device would send -- a flag an `add`, a tombstone a
    # `remove` -- applied as that door applies them
    tl = theirs.get("later")
    titems = tl.get("items") if isinstance(tl, dict) and isinstance(tl.get("items"), dict) else {}
    items = later._items(doc)
    for rid, e in sorted(titems.items()):
        try:
            if later._is_tomb(e):
                later._parts(rid)
                op, rec = "remove", {"id": rid, "at": _at(e.get("gone"), now)}
            else:
                op, rec = "add", later.clean_record(dict(e, id=rid), now)
        except (ValueError, TypeError):
            continue
        before = copy.deepcopy(items.get(rid))
        result, moved = later._apply(items, op, rec)
        changed = changed or moved
        live_before = later._sound(rid, before) and not later._is_tomb(before)
        tomb_before = later._sound(rid, before) and later._is_tomb(before)
        what = "the flag on “%s”" % (rec.get("text") or (before or {}).get("text") or rid)[:80]
        if op == "add" and result == "added" and not later._sound(rid, before):
            _row(rows, "prefs.json", "later:" + rid, what, "added", "backup", theirs=rec.get("title", ""))
        elif op == "add" and result == "ignored" and tomb_before:
            _row(rows, "prefs.json", "later:" + rid, what, "differs", "mine", mine="removed here",
                 theirs="flagged", why="removed here after the backup's flag: it stays removed")
        elif op == "add" and result == "added" and tomb_before:
            _row(rows, "prefs.json", "later:" + rid, what, "differs", "backup", mine="removed here",
                 theirs="flagged", why="flagged again after it was removed here: it comes back")
        elif op == "remove" and result == "removed" and live_before:
            _row(rows, "prefs.json", "later:" + rid, what, "differs", "backup", mine="flagged",
                 theirs="removed", why="the backup removed it after it was flagged here: it goes")
    if later._tidy(items, now):
        changed = True
    if titems:
        lat = doc.get("later") if isinstance(doc.get("later"), dict) else {}
        lat["items"] = items
        doc["later"] = lat
    return rows, ((lambda: prefs._write(doc)) if changed else None)


def _prompt_same(a, b):
    return all(a.get(k) == b.get(k) for k in ("surface", "name", "kind", "text", "languages"))


def _merge_prompts(theirs, choose):
    doc = copy.deepcopy(prompts._read())
    rows, changed = [], False
    for raw in theirs.get("prompts") or []:
        try:
            p = prompts.clean(raw)
            if not p["id"]:
                raise prompts.PromptsError("no id")
        except prompts.PromptsError:
            _row(rows, "prompts.json", "unread:%d" % len(rows), "a prompt this Parseh cannot read", "left out",
                 "mine", why="it is not a prompt this Parseh knows how to keep")
            continue
        at = next((i for i, q in enumerate(doc["prompts"]) if q["id"] == p["id"]), None)
        if at is None:
            name = prompts._unused(doc, p["surface"], p["name"])
            _row(rows, "prompts.json", p["id"], "the prompt %s" % p["name"], "added", "backup", theirs=name,
                 why=("a prompt of yours is called %s already: it comes in as %s" % (p["name"], name))
                 if name != p["name"] else "")
            doc["prompts"].append(dict(p, name=name))
            changed = True
            continue
        was = doc["prompts"][at]
        if _prompt_same(was, p):
            continue
        take = _chose(choose, "prompts.json", p["id"])
        _row(rows, "prompts.json", p["id"], "the prompt %s" % was["name"], "differs", "choose",
             mine="%s, changed %s" % (was["name"], was.get("updated", "")),
             theirs="%s, changed %s" % (p["name"], p.get("updated", "")))
        if take:
            del doc["prompts"][at]
            name = prompts._unused(doc, p["surface"], p["name"])
            doc["prompts"].insert(at, dict(p, name=name))
            changed = True
    moved = theirs.get("moved")
    if isinstance(moved, dict):
        for k, v in moved.items():
            if str(k) not in doc["moved"]:
                doc["moved"][str(k)] = str(v)
                changed = True
    return rows, ((lambda: prompts._write(doc)) if changed else None)


def _shipped_rows():
    with open(languages.REGISTRY, encoding="utf-8") as f:
        raw = json.load(f)
    return {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, dict)}


def _merge_languages(theirs, choose, files):
    try:
        mine = languages.read_store()
        unreadable = False
    except (OSError, ValueError):
        mine, unreadable = {}, True
    mine = copy.deepcopy(mine)
    shipped = _shipped_rows()
    taken = {d.get("folder"): c for c, d in shipped.items()}
    taken.update({d.get("folder"): c for c, d in mine.items() if isinstance(d, dict)})
    rows, writes, changed = [], {}, False
    if unreadable:
        _row(rows, "languages.json", "yours", "your languages.json", "differs", "backup",
             why="yours cannot be read: it is set aside under a dated name, never written over, and the backup's "
                 "languages come in")
    for code, row in theirs.items():
        if code.startswith("_"):
            continue
        name = row.get("name", code) if isinstance(row, dict) else code
        if not isinstance(row, dict) or not _CODE.match(code):
            _row(rows, "languages.json", code, "the language %s" % code, "left out", "mine",
                 why="its row is not one this Parseh can read")
            continue
        if code in shipped:
            _row(rows, "languages.json", code, "the language %s" % name, "left out", "mine",
                 why="Parseh itself now has %s (%s), and its own is the one read" % (code, shipped[code].get("name")))
            continue
        owner = taken.get(row.get("folder"))
        if owner not in (None, code):
            _row(rows, "languages.json", code, "the language %s" % name, "left out", "mine",
                 why="its folder %s is %s's already" % (row.get("folder"), owner))
            continue
        own = {n: b for n, b in files.items() if _FILE.match(n).group(2) == code}
        on_disk = {}
        for n in own:
            try:
                with open(_file_path(n), "rb") as fh:
                    on_disk[n] = fh.read()
            except OSError:
                on_disk[n] = None
        have = mine.get(code)
        if have is None:
            _row(rows, "languages.json", code, "the language %s" % name, "added", "backup",
                 theirs="%d file(s) with it" % len(own))
            take = True
        elif have == row and all(on_disk[n] == b for n, b in own.items()):
            continue
        else:
            differ = [n for n, b in own.items() if on_disk[n] != b]
            _row(rows, "languages.json", code, "the language %s" % name, "differs", "choose",
                 mine="yours" + (" (its row)" if have != row else ""),
                 theirs="the backup's" + (" (%s)" % ", ".join(differ) if differ else ""))
            take = _chose(choose, "languages.json", code)
        if take:
            mine[code] = row
            taken[row.get("folder")] = code
            writes.update({n: b for n, b in own.items() if on_disk[n] != b})
            changed = True

    def write():
        for n, b in sorted(writes.items()):
            _write_file(_file_path(n), b)
        doc = {"_comment": languages.STORE_COMMENT, "_format": languages.STORE_FORMAT}
        doc.update(mine)
        storeguard.write_json(languages.PERSONAL, doc, ok=lambda d: isinstance(d, dict), indent=2)
        languages.reload()
    return rows, (write if changed else None)


def _write_file(path, data):
    """A language's file (LaTeX, Markdown, lookup rules), whole and durable as storeguard writes a store -- its
    own temporary name, fsync'd, then moved into place -- but with no "damaged" test: that test is a store's
    (it parses JSON), and a LaTeX file would fail it."""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    tmp = "%s.%s.tmp" % (path, secrets.token_hex(4))
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    storeguard._sync_dir(folder)


def _theme_same(a, b):
    return all(a.get(k) == b.get(k) for k in ("name", "compiler", "packages", "languages", "font", "preamble"))


def _merge_latex(theirs, choose):
    doc = copy.deepcopy(latexthemes._read())
    rows, changed = [], False
    for t in theirs.get("themes") or []:
        try:
            t = latexthemes.clean(t)
        except (latexthemes.ThemeError, TypeError, ValueError, AttributeError):
            _row(rows, "latex.json", "unread:%d" % len(rows), "a LaTeX theme this Parseh cannot read", "left out",
                 "mine", why="it is not a theme this Parseh can use")
            continue
        key = latexthemes.name_key(t["name"])
        at = next((i for i, x in enumerate(doc["themes"]) if latexthemes.name_key(x["name"]) == key), None)
        if at is None:
            _row(rows, "latex.json", "theme:" + key, "the LaTeX theme %s" % t["name"], "added", "backup")
            doc["themes"].append(t)
            changed = True
        elif not _theme_same(doc["themes"][at], t):
            was = doc["themes"][at]
            _row(rows, "latex.json", "theme:" + key, "the LaTeX theme %s" % t["name"], "differs", "choose",
                 mine="changed %s" % (was.get("updated") or "at some point"),
                 theirs="changed %s" % (t.get("updated") or "at some point"))
            if _chose(choose, "latex.json", "theme:" + key):
                doc["themes"][at] = t
                changed = True
    names = {latexthemes.name_key(t["name"]): t["name"] for t in doc["themes"]}
    want = names.get(latexthemes.name_key(theirs.get("default") or ""))
    if want and latexthemes.name_key(want) != latexthemes.name_key(doc["default"]):
        _row(rows, "latex.json", "default", "the default LaTeX theme", "differs", "choose",
             mine=doc["default"], theirs=want)
        if _chose(choose, "latex.json", "default"):
            doc["default"], changed = want, True
    try:
        limit = max(latexthemes.TIMEOUT_MIN, min(latexthemes.TIMEOUT_MAX, int(theirs.get("timeout"))))
    except (TypeError, ValueError):
        limit = None
    if limit is not None and limit != doc["timeout"]:
        _row(rows, "latex.json", "timeout", "how long a drawing may take", "differs", "choose",
             mine="%d s" % doc["timeout"], theirs="%d s" % limit)
        if _chose(choose, "latex.json", "timeout"):
            doc["timeout"], changed = limit, True
    return rows, ((lambda: latexthemes._write(doc)) if changed else None)


def _merge_analysis(theirs, choose):
    mine = analysisconfig.load()
    here = os.path.isfile(analysisconfig.STORE)
    rows, changes = [], {}
    for k, allowed in analysisconfig.CHOICES.items():
        v = theirs.get(k)
        if v not in allowed or v == mine[k]:
            continue
        if not here:
            _row(rows, "analysis.json", k, "the analyzers for %s" % k, "added", "backup", mine=mine[k], theirs=v)
            changes[k] = v
        else:
            _row(rows, "analysis.json", k, "the analyzers for %s" % k, "differs", "choose", mine=mine[k], theirs=v)
            if _chose(choose, "analysis.json", k):
                changes[k] = v
    return rows, ((lambda: analysisconfig.save(changes)) if changes else None)


def _merge_speech(theirs, choose):
    mine = speechconfig.load()
    here = os.path.isfile(str(speechconfig.CONFIG))
    rows, out, changed = [], copy.deepcopy(mine), False
    sp = theirs.get("second_pass")
    if type(sp) is bool and sp != mine["second_pass"]:
        state = "added" if not here else "differs"
        _row(rows, "speech.json", "second_pass", "the checks for suspect words", state,
             "backup" if not here else "choose", mine="on" if mine["second_pass"] else "off",
             theirs="on" if sp else "off")
        if not here or _chose(choose, "speech.json", "second_pass"):
            out["second_pass"], changed = sp, True
    models = theirs.get("models_by_language")
    for lang, model in sorted((models if isinstance(models, dict) else {}).items()):
        try:
            speechconfig._selections({lang: model})
        except (ValueError, TypeError):
            _row(rows, "speech.json", "model:%s" % lang, "the speech model for %s" % lang, "left out", "mine",
                 why="%s is not a model this Parseh offers for it" % model)
            continue
        was = mine["models_by_language"].get(lang)
        if was == model:
            continue
        if was is None:
            _row(rows, "speech.json", "model:" + lang, "the speech model for %s" % lang, "added", "backup",
                 theirs=model, why="fetch it again on Settings → Speech to text")
            out["models_by_language"][lang], changed = model, True
        else:
            _row(rows, "speech.json", "model:" + lang, "the speech model for %s" % lang, "differs", "choose",
                 mine=was, theirs=model)
            if _chose(choose, "speech.json", "model:" + lang):
                out["models_by_language"][lang], changed = model, True
    patch = {"second_pass": out["second_pass"], "models_by_language": out["models_by_language"]}
    return rows, ((lambda: speechconfig.save(patch)) if changed else None)


def _locks():
    return {"prefs.json": prefs.LOCK, "prompts.json": prompts._LOCK, "languages.json": _LANG_LOCK,
            "latex.json": latexthemes._LOCK, "analysis.json": analysisconfig.LOCK, "speech.json": speechconfig.LOCK}


_LANG_LOCK = threading.RLock()


def _merge(name, got, choose):
    doc = got.stores[name]
    if name == "prefs.json":
        return _merge_prefs(doc, choose)
    if name == "prompts.json":
        return _merge_prompts(doc, choose)
    if name == "languages.json":
        return _merge_languages(doc, choose, got.files)
    if name == "latex.json":
        return _merge_latex(doc, choose)
    if name == "analysis.json":
        return _merge_analysis(doc, choose)
    return _merge_speech(doc, choose)


def _section(name, rows):
    count = {}
    for r in rows:
        count[r["state"]] = count.get(r["state"], 0) + 1
    return {"store": name, "label": LABEL[name], "counts": count,
            "choose": [r for r in rows if r["will"] == "choose"],
            "rows": rows[:MAX_LISTED], "more": max(0, len(rows) - MAX_LISTED)}


def plan(got):
    """What loading `got` would do, writing nothing -> {"stores": [section, ...],
    "missing": [names the backup has not], "left_out", "notes", "made", "version"}."""
    out = []
    for name in NAMES:
        if name not in got.stores:
            continue
        with _locks()[name]:
            rows, _write = _merge(name, got, {})
        out.append(_section(name, rows))
    return {"stores": out, "missing": [n for n in NAMES if n not in got.stores],
            "left_out": [{"name": "config/" + n, "why": w} for n, w in LEFT_OUT],
            "notes": list(got.notes), "made": got.manifest.get("exported", ""),
            "version": got.manifest.get("version", "")}


def apply(got, choose=None):
    """Load `got`, merging -> the same as plan() says, after it is done;
    `choose` names the rows whose backup side is taken ({row id: "backup"}),
    and every row it does not name keeps yours."""
    out, wrote = [], []
    for name in NAMES:
        if name not in got.stores:
            continue
        with _locks()[name]:
            rows, write = _merge(name, got, choose or {})
            if write:
                write()
                wrote.append(name)
        out.append(_section(name, rows))
    return {"stores": out, "wrote": wrote, "notes": list(got.notes)}


# ------------------------------------------------------------------ the read held between the two steps
# Loading is two steps on the page: the zip is read and checked and the plan shown,
# then the person's choices are sent.  What was read is held here, in memory (a
# settings backup is small), for an hour, under a token the page sends back.
_HELD, _HELD_LOCK, HOLD_SECONDS, HOLD_MAX = {}, threading.Lock(), 3600, 8


def hold(got):
    now = time.time()
    with _HELD_LOCK:
        for k in [k for k, (t, _g) in _HELD.items() if t < now - HOLD_SECONDS]:
            del _HELD[k]
        while len(_HELD) >= HOLD_MAX:
            del _HELD[min(_HELD, key=lambda k: _HELD[k][0])]
        token = secrets.token_hex(12)
        _HELD[token] = (now, got)
    return token


def held(token):
    with _HELD_LOCK:
        t = _HELD.get(token) if isinstance(token, str) else None
        if t is None or t[0] < time.time() - HOLD_SECONDS:
            return None
        return t[1]


def drop(token):
    with _HELD_LOCK:
        _HELD.pop(token, None)
