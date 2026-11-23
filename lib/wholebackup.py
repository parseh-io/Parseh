# SPDX-License-Identifier: GPL-3.0-or-later
"""The backup of everything, for moving to a new computer (TO-DO §13.19).

ONE ZIP holding what every other backup holds, and what none did:

    parseh-everything.json   the list: every file below with its size and SHA-256
    settings.zip             config/, as Settings -> Backups gives it (lib/configbackup.py)
    books.zip                the books' own Backup (lib/shelf.py)
    videos.zip               the videos' own Backup (lib/shelf.py)
    studio.zip               the studio library's own Backup (markdown/app/store.py backup_files)
    decks.zip                the exercise decks' own Backup (markdown/app/decks.py backup_zip)
    cards/...                the Anki card store, youtube/anki/, file by file (TO-DO §10.6)
    clips/...                the clip tray, clips/, file by file (TO-DO §10.14)

A shelf with nothing on it is left out and named in the list (`empty`).

THE CARD STORE AND THE CLIP TRAY ARE IN IT because their data lives on this
computer's disk and no other backup holds it: a card waiting to go to Anki,
a deck made on the pages and never synced, a clip not yet on a card, exist
nowhere else (10.6, 10.14).  Of the card store, its `build/` (the .apkg files
made from it, made again on the next sync) and its `inbox/` (an .apkg dropped
there, which is a copy of something the person has) are left out, and so is
any name beginning with a dot (a crash's `.staging-*`).

LOADING IT is each part through its own door, IN THIS ORDER: the settings
first -- a language added on the old computer is what a book, a deck or a card
in that language needs to be taken in at all -- then the books, the videos,
the studio, the decks, the cards and the clips.  Each shelf keeps what it
already has and names it, as its own Load from backup does, unless `replace`;
the settings merge (lib/configbackup.py), and what differs and has no rule of
its own is kept as it is here and listed, for the person to choose on the
page.  The card store and the clip tray, which had no restore of their own,
follow the same rule: a deck already here, a clip already here, is kept.

THE WHOLE ZIP IS CHECKED BEFORE ANYTHING IS PUT BACK: every file against its
size and hash, read in pieces.  A damaged file anywhere refuses the whole
load, in words, with nothing written -- half a computer moved is worse than
none.

SIZE.  Nothing is held whole in memory here: each part is written to a
temporary file and copied into the zip from there, and taken out of it the
same way, a megabyte at a time.  The shelves' own packers and restores do
the same with each bundle, and the decks' packer with each file (TO-DO 3.9).
Every temporary file is in Parseh's own `.tmp/` (lib/scratch.py), never the
system's temp folder: a backup of a shelf of films is gigabytes, and that
folder is often a small one held in memory.  A book comes with its
recordings, as a video with its film (lib/shelf.py, TO-DO 6.16).

Every door is handed in (`Env`), so that this module knows no server and a
test can point each at a temporary tree.
"""
import hashlib
import json
import os
import shutil
import time
import uuid
import zipfile
from datetime import datetime

import configbackup
import scratch

FORMAT = "parseh-everything/1"
MANIFEST = "parseh-everything.json"
PARTS = ("settings", "books", "videos", "studio", "decks")     # the zips inside, in the order they go back
STORED = (".zip", ".mp3", ".m4a", ".ogg", ".opus", ".wav", ".flac", ".webm", ".mp4", ".png", ".jpg", ".jpeg",
          ".apkg", ".pdf")
MAX_ENTRIES = 500000
CHUNK = 1 << 20
ANKI_SKIP = ("build", "inbox", "README.md")      # at the top of the card store


class BackupError(Exception):
    """The backup of everything refused, in words."""


class Env(object):
    """The doors this module goes through.  `pack` {part: () -> (path, name) or
    None when the shelf is empty}; `restore` {part: (path, replace) -> {restored,
    kept, warnings}}; `anki` and `clips`, the card store's and the tray's folders."""

    def __init__(self, pack, restore, anki, clips):
        self.pack, self.restore, self.anki, self.clips = pack, restore, anki, clips


def _sha_file(path):
    h, n = hashlib.sha256(), 0
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                return h.hexdigest(), n
            h.update(b)
            n += len(b)


def _compress(name):
    return zipfile.ZIP_STORED if name.lower().endswith(STORED) else zipfile.ZIP_DEFLATED


def _walk(folder, skip_top=()):
    """(path, name relative to `folder` with /) of every file under it, in order;
    nothing whose name begins with a dot, nothing named in `skip_top` at the top."""
    out = []
    if not folder or not os.path.isdir(folder):
        return out
    for here, dirs, files in os.walk(folder):
        rel = os.path.relpath(here, folder)
        top = rel == "."
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and not (top and d in skip_top))
        for f in sorted(files):
            if f.startswith(".") or (top and f in skip_top) or f.endswith(".tmp"):
                continue
            p = os.path.join(here, f)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            out.append((p, (f if top else rel.replace(os.sep, "/") + "/" + f)))
    return out


def _settings_part():
    if not configbackup.present():
        return None
    return configbackup.pack()


# ------------------------------------------------------------------ backing up
def pack(env, version=""):
    """Everything as one zip -> (path to a temporary file, file name, notes);
    the caller deletes the file."""
    fd, out = scratch.mkstemp(prefix="parseh-everything-", suffix=".zip")
    os.close(fd)
    files, empty, notes = {}, [], []
    try:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
            for part in PARTS:
                try:
                    got = _settings_part() if part == "settings" else env.pack[part]()
                except Exception as e:          # noqa: BLE001  one shelf nobody can pack is said, not fatal
                    notes.append("%s could not be packed (%s): it is not in this backup" % (part, e))
                    continue
                if not got:
                    empty.append(part)
                    continue
                path = got[0]
                try:
                    name = part + ".zip"
                    sha, size = _sha_file(path)
                    zf.write(path, name, zipfile.ZIP_STORED)
                    files[name] = {"sha256": sha, "size": size}
                finally:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
            for prefix, folder, skip in (("cards", env.anki, ANKI_SKIP), ("clips", env.clips, ("README.md",))):
                found = _walk(folder, skip)
                if not found:
                    empty.append(prefix)
                for p, rel in found:
                    name = "%s/%s" % (prefix, rel)
                    sha, size = _sha_file(p)
                    zf.write(p, name, _compress(name))
                    files[name] = {"sha256": sha, "size": size}
            zf.writestr(MANIFEST, json.dumps({
                "format": FORMAT, "software": "Parseh", "version": version,
                "exported": datetime.now().isoformat(timespec="seconds"),
                "files": files, "empty": empty, "notes": notes,
                "left_out": [{"name": "config/" + n, "why": w} for n, w in configbackup.LEFT_OUT]},
                ensure_ascii=False, indent=1).encode("utf-8"), zipfile.ZIP_DEFLATED)
    except BaseException:
        try:
            os.unlink(out)
        except OSError:
            pass
        raise
    return out, "parseh-everything-%s.zip" % time.strftime("%Y%m%d-%H%M"), notes


# ------------------------------------------------------------------ reading it back
def _safe(rel):
    """A name inside cards/ or clips/ that may become a path -> its parts; None when it may not."""
    if not rel or "\\" in rel or "\x00" in rel or rel.startswith("/") or len(rel) > 400:
        return None
    parts = rel.split("/")
    if any(p in ("", ".", "..") or p.startswith(".") or ":" in p for p in parts):
        return None
    return parts


def check(source):
    """Open and check the whole backup -> (ZipFile, manifest); BackupError in
    words for anything wrong, before anything is written.  The caller closes."""
    try:
        zf = zipfile.ZipFile(source)
    except (zipfile.BadZipFile, ValueError, OSError, EOFError):
        raise BackupError("that is not a zip file")
    try:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > MAX_ENTRIES:
            raise BackupError("that zip holds more than %d files" % MAX_ENTRIES)
        names = {i.filename: i for i in infos}
        if MANIFEST not in names:
            raise BackupError("that zip is not a backup of everything: it has no %s" % MANIFEST)
        try:
            manifest = json.loads(zf.read(names[MANIFEST]).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, zipfile.BadZipFile, OSError, EOFError):
            raise BackupError("that backup's %s cannot be read: the zip is damaged" % MANIFEST)
        fmt = manifest.get("format") if isinstance(manifest, dict) else None
        ok = configbackup._reads(fmt, FORMAT)
        if ok is None:
            raise BackupError("that zip is not a backup of everything this Parseh reads")
        if not ok:
            raise BackupError("that backup was made by a newer Parseh (it says %s, and this one reads %s): "
                              "update Parseh, then load it" % (fmt, FORMAT))
        listed = manifest.get("files")
        if not isinstance(listed, dict):
            raise BackupError("that backup's list of files cannot be read: the zip is damaged")
        for name, said in sorted(listed.items()):
            info = names.get(name)
            if info is None or not isinstance(said, dict):
                raise BackupError("%s is in that backup's list and not in the zip: the backup is damaged, and "
                                  "nothing was loaded" % name)
            if not (name in [p + ".zip" for p in PARTS] or
                    (name.startswith(("cards/", "clips/")) and _safe(name.split("/", 1)[1]))):
                raise BackupError("%s is not something a backup of everything holds: nothing was loaded" % name)
            h, n = hashlib.sha256(), 0
            try:
                with zf.open(info) as f:
                    while True:
                        b = f.read(CHUNK)
                        if not b:
                            break
                        h.update(b)
                        n += len(b)
            except (zipfile.BadZipFile, OSError, EOFError, ValueError):
                raise BackupError("%s in that backup cannot be read: the zip is damaged, and nothing was loaded"
                                  % name)
            if h.hexdigest() != said.get("sha256") or n != said.get("size"):
                raise BackupError("%s in that backup is not the file that was backed up (its checksum differs): "
                                  "the backup is damaged, and nothing was loaded" % name)
    except BaseException:
        zf.close()
        raise
    return zf, manifest


def _extract(zf, name, dest):
    """One member to the file `dest`, a megabyte at a time, through a temporary name beside it."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = "%s.%s.tmp" % (dest, uuid.uuid4().hex[:8])
    try:
        with zf.open(name) as src, open(tmp, "wb") as out:
            shutil.copyfileobj(src, out, CHUNK)
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _same(zf, name, path):
    if not os.path.isfile(path):
        return False
    h = hashlib.sha256()
    with zf.open(name) as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest() == _sha_file(path)[0]


def _cards(zf, listed, anki, replace):
    """The card store, deck by deck: a deck folder already here is kept unless
    `replace`; a file of the whole store (notetypes.json, seen.json) already here
    and different is kept unless `replace`."""
    import languages
    units = {}
    for name in listed:
        if not name.startswith("cards/"):
            continue
        parts = _safe(name[len("cards/"):])
        if len(parts) == 1:
            unit = parts[0]
        elif languages.by_folder(parts[0]) is not None and len(parts) >= 3:
            unit = "/".join(parts[:2])
        else:
            unit = parts[0]
        units.setdefault(unit, []).append((name, parts))
    restored, kept, warnings = [], [], []
    for unit, members in sorted(units.items()):
        dest = os.path.join(anki, *unit.split("/"))
        if len(members) == 1 and members[0][1] == [unit]:
            name = members[0][0]
            if os.path.exists(dest):
                if _same(zf, name, dest):
                    continue
                if not replace:
                    kept.append(unit)
                    continue
            _extract(zf, name, dest)
            restored.append(unit)
            continue
        if os.path.exists(dest) and not replace:
            kept.append(unit)
            continue
        stage = os.path.join(anki, ".staging-restore-" + uuid.uuid4().hex[:8])
        try:
            depth = len(unit.split("/"))
            for name, parts in members:
                _extract(zf, name, os.path.join(stage, *parts[depth:]))
            old = None
            if os.path.exists(dest):
                old = os.path.join(anki, ".staging-old-" + uuid.uuid4().hex[:8])
                os.replace(dest, old)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            os.replace(stage, dest)
            if old:
                shutil.rmtree(old, ignore_errors=True)
            restored.append(unit)
        except OSError as e:
            warnings.append("%s could not be put back (%s)" % (unit, e))
        finally:
            shutil.rmtree(stage, ignore_errors=True)
    return {"restored": restored, "kept": kept, "warnings": warnings}


def _clips(zf, listed, folder):
    """The clip tray: a clip's name is unique across the toolbox, so one already here is the same clip and is kept."""
    import clips as cliptray
    restored, kept, warnings = [], [], []
    for name in sorted(listed):
        if not name.startswith("clips/"):
            continue
        rel = name[len("clips/"):]
        base = rel[:-len(".json")] if rel.endswith(".json") else rel
        if "/" in rel or cliptray.kind_of(base) is None:
            warnings.append("%s is not a clip, and was left out" % rel)
            continue
        dest = os.path.join(folder, rel)
        if os.path.exists(dest):
            if base == rel:
                kept.append(rel)
            continue
        try:
            _extract(zf, name, dest)
        except OSError as e:
            warnings.append("%s could not be put back (%s)" % (rel, e))
            continue
        if base == rel:
            restored.append(rel)
    return {"restored": restored, "kept": kept, "warnings": warnings}


def load(source, env, replace=False):
    """Put everything back, in order -> {"parts": [{part, restored, kept,
    warnings, error?}], "settings": configbackup.apply's answer or None,
    "token": the settings read, held for the choices, "empty", "made"}.
    BackupError before anything is written when the zip is not whole."""
    zf, manifest = check(source)
    listed = manifest["files"]
    out = {"parts": [], "settings": None, "token": None, "made": manifest.get("exported", ""),
           "version": manifest.get("version", ""), "empty": manifest.get("empty", [])}
    work = scratch.mkdtemp(prefix="parseh-everything-load-")
    try:
        with zf:
            # THE SETTINGS FIRST: a language of the person's is what the rest may need
            if "settings.zip" in listed:
                try:
                    got = configbackup.read(zf.read("settings.zip"))
                    out["settings"] = configbackup.apply(got, {})
                    out["token"] = configbackup.hold(got)
                    out["parts"].append({"part": "settings", "restored": out["settings"]["wrote"],
                                         "kept": [], "warnings": got.notes})
                except configbackup.BackupError as e:
                    out["parts"].append({"part": "settings", "error": str(e), "restored": [], "kept": [],
                                         "warnings": []})
            for part in PARTS[1:]:
                name = part + ".zip"
                if name not in listed:
                    continue
                path = os.path.join(work, name)
                _extract(zf, name, path)
                try:
                    r = env.restore[part](path, replace)
                    out["parts"].append({"part": part, "restored": list(r.get("restored", [])),
                                         "kept": list(r.get("kept", [])), "warnings": list(r.get("warnings", []))})
                except Exception as e:      # noqa: BLE001  each shelf's own refusal, said; the others go on
                    out["parts"].append({"part": part, "error": str(e), "restored": [], "kept": [], "warnings": []})
                finally:
                    os.unlink(path)
            if any(n.startswith("cards/") for n in listed):
                os.makedirs(env.anki, exist_ok=True)
                out["parts"].append(dict(_cards(zf, listed, env.anki, replace), part="cards"))
            if any(n.startswith("clips/") for n in listed):
                os.makedirs(env.clips, exist_ok=True)
                out["parts"].append(dict(_clips(zf, listed, env.clips), part="clips"))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out
