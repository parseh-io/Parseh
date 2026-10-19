# SPDX-License-Identifier: GPL-3.0-or-later
"""openfile -- a Markdown or zip file from anywhere on the computer, open in the studio.

    found = openfile.open_path("/home/me/notes/lesson.md")      # {"session": Session} or {"choose": [...]}
    sess = found["session"]
    with sess.scope():                       # the studio's own code, pointed at the working copy
        store.get(sess.doc_id)
    sess.save()                              # the one moment the original changes
    sess.close()                             # the working copy is deleted

THE IDEA.  A file opened from the computer is a studio library of ONE
document, in a temporary folder:

    markdown/open/<sid>/session.json          where the file is, what it looked like when it was opened
    markdown/open/<sid>/library/<language>/<id>/{source.md, meta.json, images/, audio/, build/}

The studio can already serve a library that is not its own: the notes beside a book or a video are served by the
studio's very routes with the library (store.use_library) and the prefix (server.use_mount) pointed elsewhere for the
length of the request.  This is the same with a third kind of library behind it, so the editor, the preview, the
document page, the PDF, the pictures and recordings, the exercises and the downloads all work on the file with no
change: none of them knew which library they were in.  What is here is only what is new -- opening (reading the file
into the working copy), the fingerprint that says whether the working copy holds something the file does not,
saving (the one moment the file changes), closing (the working copy goes), and the file browser.

WHAT KEEPS IT FROM BECOMING CHAOS, in order of importance:

  * The original is changed at ONE moment and by ONE act: save().  Opening reads it, editing writes the working copy,
    closing deletes the working copy.  The act is atomic -- a file beside the original, then os.replace -- so a
    crash, a full disk or a refused permission leaves the original whole.
  * Nothing is ever overwritten that somebody else wrote.  The original's bytes are fingerprinted when it is opened
    and after every save; if they are not what was seen, save() answers `conflict` and the person decides.
  * "Unsaved" is a fact about content, not a flag: the payload (text, tags, every picture and recording with its
    checksum) is fingerprinted and compared with what the file last held.  An upload, a recolouring from the document
    page, an edit in the editor all land in the same comparison, and a save of unchanged content writes nothing.
  * What is written back is what was read, but for what the person changed: the line ends (CRLF or LF) and the byte
    order mark are remembered and restored, no header is added, no title is made unique, nothing is "extracted"
    (store.create_exact); a zip's other entries are copied across byte for byte.
  * One file, one session: opening a path that is already open goes back to the session.
  * A Markdown file cannot hold pictures, recordings or tags.  Saving one that has gained any asks, naming what would
    be left out; the answer is a zip beside it (the studio's own "Markdown + media" layout), or the text only, or
    nothing.  The .md is never rewritten into something else.
  * A session that holds unsaved work survives a crash and is offered back (sweep); one that holds none is deleted.

Whoever may use the studio may use this: serve.py's gate decides who is let in, and the owner chose (2026-10-19) that a
device let in over a VPN or the Wi-Fi opens the files of the computer Parseh runs on as well -- the disk it shows is
always that computer's, not the device's.  This module trusts its caller on that and on nothing else: a path is checked
to be a regular file of an allowed kind under size limits and outside Parseh's own stores; a zip entry's name is never
used as a path on the disk.
"""
import contextlib
import errno
import getpass
import hashlib
import json
import os
import posixpath
import re
import shutil
import struct
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path

import audiofile
import languages
import store

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # markdown/
PARSEH = ROOT.parent
# where the working copies live: inside Parseh's own folder, like the library, so that a build (XeLaTeX runs inside
# the document's folder) goes where the library's builds go, and so that a session with unsaved work survives a
# reboot.  The tests point it at a temporary folder.
OPEN_DIR = ROOT / "open"
FORMAT = 1                              # session.json's shape

SID_RE = re.compile(r"^[0-9a-f]{12}$")
MD_SUFFIXES = (".md", ".markdown", ".txt")
ZIP_SUFFIXES = (".zip",)
OPENABLE = MD_SUFFIXES + ZIP_SUFFIXES

MD_MAX = store.MD_MAX                   # a Markdown file: the library's own limit
ZIP_MANAGED_MAX = store.ZIP_MAX_BYTES   # what is READ out of a zip: its document and its media, together
ZIP_ENTRIES_MAX = 20000                 # the entries of a zip (its directory is read, the rest is not)
LIST_MAX = 3000                         # the entries of a folder the browser lists
SWEEP_ORPHAN_SECONDS = 24 * 3600        # a session folder that cannot be read is deleted after this


class OpenError(Exception):
    """Something the person is told, in words.  `code` is for the page (it chooses what to offer); `more` is whatever
    else the page needs."""

    def __init__(self, say, code="refused", **more):
        super().__init__(say)
        self.say, self.code, self.more = say, code, more

    def answer(self):
        return dict(self.more, ok=False, error=self.say, code=self.code)


# ------------------------------------------------------------------------------------------------ small things
def _now():
    return time.time()


def sha256_of(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


_SHA = {}
_SHA_MAX = 1024


def cached_sha(path):
    """The checksum of a file, remembered under what the disk says of it (size and mtime), so that a page asking
    every few seconds whether anything changed reads no picture twice."""
    st = os.stat(path)
    key = (str(path), st.st_size, st.st_mtime_ns)
    got = _SHA.get(key)
    if got is None:
        got = sha256_of(path)
        if len(_SHA) >= _SHA_MAX:
            _SHA.clear()
        _SHA[key] = got
    return got


def stat_fp(path):
    """What a file is, as far as "has somebody changed it" is concerned: its size, its mtime and its checksum."""
    st = os.stat(path)
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": sha256_of(path)}


def changed_on_disk(path, fp, fresh=False):
    """Whether the bytes of the file at `path` are not what `fp` saw: True or False, or None when it is not there.
    A file touched with the same bytes is not changed -- the size and the mtime are only a shortcut for the
    checksum.  The page asks every few seconds, so a checksum already worked out for a file in this very state (size
    and date) is not worked out again; `fresh` -- the moment before a save -- reads the file anew."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    if st.st_size == fp.get("size") and st.st_mtime_ns == fp.get("mtime_ns"):
        return False
    try:
        return (sha256_of(path) if fresh else cached_sha(path)) != fp.get("sha256")
    except OSError:
        return None


def real_path(path):
    """The place a path leads to, absolute, links followed -- or a refusal in words when it is not an absolute path
    (a typed `lesson.md` means nothing: from where?)."""
    text = os.path.expanduser(str(path or "").strip().strip('"'))
    if not text:
        raise OpenError("Choose a file, or type the whole path of one.", "path")
    if not os.path.isabs(text):
        raise OpenError("Type the whole path of the file (it starts with / or a drive letter), or choose it in the list.",
                        "path")
    return Path(os.path.realpath(text))


def kind_of(path):
    """md, zip, or None: what a path's name says it is."""
    suffix = Path(str(path)).suffix.lower()
    if suffix in MD_SUFFIXES:
        return "md"
    if suffix in ZIP_SUFFIXES:
        return "zip"
    return None


def _same(a, b):
    try:
        return os.path.samefile(str(a), str(b))
    except OSError:
        return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


def protected():
    """The folders of Parseh's own stores, as real paths: a file inside one is Parseh's to manage (a document of the
    library, a note beside a book, a deck, a setting), and editing it behind the back of the code that keeps it would
    break what that code keeps.  The notes beside a book or a video are inside the books' and videos' folders."""
    roots = [store.LIB, OPEN_DIR]
    roots += [PARSEH / "books", PARSEH / "youtube" / "videos", PARSEH / "exercises", PARSEH / "clips",
              PARSEH / "config", PARSEH / "markdown" / "library"]
    return [Path(os.path.realpath(str(r))) for r in roots]


def is_protected(real):
    real = Path(real)
    for root in protected():
        if _same_or_inside(real, root):
            return True
    return False


def _same_or_inside(path, root):
    a, b = os.path.normcase(str(path)), os.path.normcase(str(root))
    return a == b or a.startswith(b.rstrip(os.sep) + os.sep)


# --------------------------------------------------------------------------------------------------------- text
def decode_text(data, name):
    """The bytes of a Markdown file -> (text with "\\n" line ends, its shape, how many characters were left out).

    The shape is what is needed to write it back as it was found: a byte order mark and the line ends the file used
    (the studio's text has "\\n" only).  Control characters the dialect never means are dropped, as every ingest of the
    studio does; the count is told so that nothing disappears in silence."""
    bom = data.startswith(b"\xef\xbb\xbf")
    body = data[3:] if bom else data
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise OpenError("%s is not UTF-8 text, which is what the studio reads." % name, "encoding")
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    newline = "\r\n" if crlf > lf else "\n"
    text = text.replace("\r\n", "\n")
    clean = store._strip_controls(text)
    return clean, {"bom": bom, "newline": newline}, len(text) - len(clean)


def encode_text(text, shape):
    """The studio's text -> the bytes of the file, in the shape it was found in."""
    out = text.replace("\n", "\r\n") if (shape or {}).get("newline") == "\r\n" else text
    raw = out.encode("utf-8")
    return (b"\xef\xbb\xbf" + raw) if (shape or {}).get("bom") else raw


def _fingerprint(payload):
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _sha_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extra_without_zip64(extra):
    """A zip entry's extra fields, less the zip64 one (id 1): that one says how THIS archive holds the entry, and a
    copy is written afresh.  Anything that cannot be read as a list of fields is dropped whole."""
    out, at = b"", 0
    try:
        while at < len(extra):
            ident, size = struct.unpack("<HH", extra[at:at + 4])
            block = extra[at:at + 4 + size]
            if len(block) != 4 + size:
                return b""
            if ident != 1:
                out += block
            at += 4 + size
    except struct.error:
        return b""
    return out


def _beside_candidates(folder, rel):
    """Where a picture or recording named `images/cat.png` is looked for beside a Markdown file in `folder`: in its
    images/ (the layout a zip of the document unpacks to), or in the folder itself -- the two places the library's own
    zip import looks."""
    return [Path(folder) / rel, Path(folder) / rel.split("/", 1)[1]]


# ------------------------------------------------------------------------------------------- writing a file
def _io_words(dest, e):
    """An OSError, said to the person."""
    if isinstance(e, PermissionError) or getattr(e, "errno", None) in (errno.EACCES, errno.EPERM, errno.EROFS):
        return OpenError("Parseh may not write to %s: it is read-only, or open in another program. Save it somewhere "
                         "else (Save as…), or close the other program and save again." % dest, "denied")
    if getattr(e, "errno", None) == errno.ENOSPC:
        return OpenError("The disk is full: nothing was written, and the file is as it was.", "full")
    if isinstance(e, FileNotFoundError):
        return OpenError("The folder of %s is not there any more. Save it somewhere else (Save as…)." % dest, "gone")
    return OpenError("%s could not be written: %s" % (dest, e), "io")


def _temp_beside(dest):
    """A new, empty file beside `dest`, in the mode any program gives a new file (the person's own umask applied to
    0666), and not the owner-only mode tempfile.mkstemp gives: a file made by Save as… must be as readable as the
    others in its folder.  -> (fd, path)."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    for _ in range(100):
        path = os.path.join(str(Path(dest).parent), ".parseh-%s.tmp" % uuid.uuid4().hex[:12])
        try:
            return os.open(path, flags, 0o666), path
        except FileExistsError:
            continue
    raise OSError(errno.EEXIST, "no free name for a temporary file")


def write_file(dest, fill, like=None, stage_dir=None):
    """Write `dest` whole or not at all: `fill(f)` writes the bytes into a file beside it, which is flushed and then
    swapped in (os.replace), so a crash or a full disk leaves what was there.  The mode of `like` (the file it
    replaces) is kept.  A file that is read-only is not replaced: the person made it so.

    When the FOLDER refuses a new file but the file itself can be written, the bytes are written in place instead
    (from `stage_dir`): not atomic, but better than a refusal for a file in a folder somebody locked and a file
    somebody did not."""
    dest = Path(dest)
    if dest.exists() and not os.access(str(dest), os.W_OK):
        raise OpenError("%s is read-only. Save it somewhere else (Save as…), or make it writable first." % dest.name,
                        "readonly")
    try:
        fd, tmp = _temp_beside(dest)
    except OSError as e:
        if dest.exists() and os.access(str(dest), os.W_OK) and stage_dir is not None:
            return _write_in_place(dest, fill, stage_dir)
        raise _io_words(dest, e)
    done = False
    try:
        with os.fdopen(fd, "wb") as f:
            fill(f)
            f.flush()
            os.fsync(f.fileno())
        if like is not None and os.path.exists(str(like)):
            try:
                shutil.copymode(str(like), tmp)
            except OSError:
                pass
        os.replace(tmp, str(dest))
        done = True
    except OSError as e:
        raise _io_words(dest, e)
    finally:
        if not done and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _write_in_place(dest, fill, stage_dir):
    stage = Path(stage_dir) / ("stage-%s.tmp" % uuid.uuid4().hex[:8])
    try:
        with open(stage, "wb") as f:
            fill(f)
        shutil.copyfile(str(stage), str(dest))
    except OSError as e:
        raise _io_words(dest, e)
    finally:
        try:
            stage.unlink()
        except OSError:
            pass


# ----------------------------------------------------------------------------------------- the file browser
def places():
    """The places the browser starts from: [{"name", "path"}].  An empty path is the list of drives (Windows)."""
    out = []
    home = Path(os.path.expanduser("~"))
    out.append({"name": "Home", "path": str(home)})
    for name in ("Desktop", "Documents", "Downloads"):
        p = home / name
        if p.is_dir():
            out.append({"name": name, "path": str(p)})
    if os.name == "nt":
        out.append({"name": "This PC", "path": ""})
        return out
    out.append({"name": "Computer", "path": os.sep})
    try:
        user = getpass.getuser()
    except Exception:                    # noqa: BLE001 -- no user name is no reason to show no places
        user = ""
    for base in ("/Volumes", "/media/" + user, "/run/media/" + user, "/mnt"):
        try:
            for name in sorted(os.listdir(base))[:8]:
                p = os.path.join(base, name)
                if os.path.isdir(p) and not name.startswith("."):
                    out.append({"name": name, "path": p})
        except OSError:
            continue
    return out[:24]


def _natural(name):
    return [(0, int(t)) if t.isdigit() else (1, t.lower()) for t in re.split(r"(\d+)", name)]


def _hidden(entry):
    if entry.name.startswith("."):
        return True
    if os.name == "nt":
        try:
            return bool(entry.stat().st_file_attributes & 2)        # FILE_ATTRIBUTE_HIDDEN
        except (OSError, AttributeError):
            return False
    return False


def _crumbs(path):
    parts = Path(path).parts
    out, so_far = [], None
    for part in parts:
        so_far = part if so_far is None else os.path.join(so_far, part)
        out.append({"name": part, "path": so_far})
    return out


def listing(path="", hidden=False, everything=False):
    """One folder as the browser draws it -> {"ok", "path", "parent", "crumbs", "entries", "places", "sep"}.

    Folders first, then the files that can be opened (everything, with `everything`), each in its natural order.
    A path that is a FILE answers {"ok", "kind": "file", "path"}: the person typed one.  A path that is not there
    answers the nearest folder that is, with the reason."""
    out = {"ok": True, "sep": os.sep, "places": places(), "entries": []}
    text = os.path.expanduser(str(path or "").strip().strip('"'))
    if not text:
        if os.name == "nt":
            import string
            drives = ["%s:\\" % c for c in string.ascii_uppercase if os.path.exists("%s:\\" % c)]
            out.update({"path": "", "parent": None, "crumbs": [],
                        "entries": [{"name": d, "kind": "dir", "path": d} for d in drives]})
            return out
        text = os.path.expanduser("~")
    if not os.path.isabs(text):
        return {"ok": False, "error": "Type the whole path (it starts with / or a drive letter).", "code": "path",
                "path": os.path.expanduser("~"), "places": out["places"], "sep": os.sep}
    here = os.path.abspath(text)
    if os.path.isfile(here):
        out.update({"kind": "file", "path": here, "dir": os.path.dirname(here)})
        return out
    if not os.path.isdir(here):
        near = here
        while near and not os.path.isdir(near):
            up = os.path.dirname(near)
            if up == near:
                break
            near = up
        return {"ok": False, "error": "%s is not there." % here, "code": "gone", "path": near or os.path.expanduser("~"),
                "places": out["places"], "sep": os.sep}
    dirs, files, count, truncated = [], [], 0, False
    try:
        scan = os.scandir(here)
    except OSError as e:
        up = os.path.dirname(here)
        return {"ok": False, "error": "Parseh may not read %s (%s)." % (here, e.strerror or "denied"), "code": "denied",
                "path": up if up != here else os.path.expanduser("~"), "places": out["places"], "sep": os.sep}
    with scan:
        for entry in scan:
            try:
                entry.name.encode("utf-8")         # a name of undecodable bytes cannot be shown, and must not fail the list
                if not hidden and _hidden(entry):
                    continue
                if entry.is_dir():
                    dirs.append(entry)
                elif entry.is_file():
                    openable = kind_of(entry.name) is not None
                    if openable or everything:
                        files.append((entry, openable))
                count += 1
                if count > LIST_MAX:
                    truncated = True
                    break
            except (OSError, UnicodeEncodeError):
                continue
    dirs.sort(key=lambda e: _natural(e.name))
    files.sort(key=lambda p: _natural(p[0].name))
    entries = [{"name": e.name, "kind": "dir"} for e in dirs]
    for entry, openable in files:
        try:
            st = entry.stat()
        except OSError:
            continue
        entries.append({"name": entry.name, "kind": "file", "type": kind_of(entry.name) or "", "openable": openable,
                        "size": st.st_size, "mtime": st.st_mtime})
    up = os.path.dirname(here)
    out.update({"path": here, "parent": up if up != here else ("" if os.name == "nt" else None),
                "crumbs": _crumbs(here), "entries": entries, "truncated": truncated})
    return out


# ------------------------------------------------------------------------------------------------ the session
_SESSIONS = {}
_GUARD = threading.RLock()


class Session:
    """One file open in the studio: where it came from, its working copy, and what was last written to it."""

    def __init__(self, folder, record):
        self.dir = Path(folder)
        self.m = record
        self.lock = threading.RLock()

    # ---- what it is
    @property
    def sid(self):
        return self.m["sid"]

    @property
    def library(self):
        return self.dir / "library"

    @property
    def doc_id(self):
        return self.m["doc_id"]

    @property
    def path(self):
        return self.m["path"]

    @property
    def kind(self):
        return self.m["kind"]

    @property
    def name(self):
        return Path(self.m["path"]).name

    @contextlib.contextmanager
    def scope(self):
        """The studio's store, pointed at this working copy for the length of the block (and put back after)."""
        was = store.use_library(self.library)
        try:
            yield self
        finally:
            store.use_library(was)

    def keep(self):
        """session.json, written whole or not at all."""
        blob = json.dumps(self.m, ensure_ascii=False, indent=1)
        fd, tmp = tempfile.mkstemp(dir=str(self.dir), prefix=".session-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(blob)
            os.replace(tmp, str(self.dir / "session.json"))
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    @staticmethod
    def load(folder):
        record = json.loads((Path(folder) / "session.json").read_text(encoding="utf-8"))
        if record.get("format") != FORMAT or not SID_RE.match(str(record.get("sid"))) \
                or not isinstance(record.get("doc_id"), str) or record.get("kind") not in ("md", "zip"):
            raise ValueError("not a session of this Parseh")
        s = Session(folder, record)
        with s.scope():
            store.get(s.doc_id)                 # KeyError: the working copy is gone
        return s

    # ---- the working copy's content, and whether the file holds it
    def payload(self):
        """What a save would write: the text, the tags, and every picture and recording with its checksum.

        The starters' own pictures and recordings that the studio copies in because the text names them
        (store.adopt_starter_media, on every save of the editor) are not part of it unless the file carried them: they
        come from where Parseh ships them, as they do for a document of the library, and a file that never had them
        must not gain them -- nor be "changed" by the studio having copied them in."""
        with self.scope():
            meta, text = store.get(self.doc_id)
            shipped = store.starter_media_held(self.doc_id) - set(self.m.get("own") or [])
            media = {}
            for folder, items, base in (("images", store.list_images(self.doc_id), store.images_dir(self.doc_id)),
                                        ("audio", store.list_audio(self.doc_id), store.audio_dir(self.doc_id))):
                for item in items:
                    rel = "%s/%s" % (folder, item["name"])
                    if rel not in shipped:
                        media[rel] = cached_sha(base / item["name"])
            return {"text": text, "tags": sorted(meta.get("tags") or []), "media": media}

    def dirty(self):
        """Does the working copy hold something the file does not?"""
        return _fingerprint(self.payload()) != self.m.get("published")

    def can_write(self):
        dest = Path(self.path)
        try:
            if dest.exists():
                return os.access(str(dest), os.W_OK)
            return os.access(str(dest.parent), os.W_OK)
        except OSError:
            return False

    def state(self):
        """What the page shows of it."""
        dest = Path(self.path)
        changed = changed_on_disk(dest, self.m["origin"])
        try:
            dirty = self.dirty()
        except (KeyError, OSError, ValueError):
            dirty = True
        return {"sid": self.sid, "kind": self.kind, "path": str(dest), "name": dest.name, "dir": str(dest.parent),
                "entry": self.m.get("entry"), "doc_id": self.doc_id, "dirty": dirty,
                "missing": changed is None, "changed_on_disk": bool(changed), "can_write": self.can_write(),
                "opened": self.m.get("opened"), "saved": self.m.get("saved"),
                "recovered": bool(self.m.get("recovered")), "warnings": list(self.m.get("warnings") or [])}

    # ---- what a Markdown file cannot hold
    @staticmethod
    def _beside(dest, rel, sha):
        """Is `rel` ("images/cat.png") already beside the Markdown file `dest`, with these very bytes?  (Where
        _open_md looks for it: in images/ or audio/, or in the folder itself.)"""
        for f in _beside_candidates(Path(dest).parent, rel):
            try:
                if f.is_file() and cached_sha(f) == sha:
                    return True
            except OSError:
                continue
        return False

    def lost_in_md(self, dest, payload):
        """What a Markdown file at `dest` could not hold of the payload, as the page says it: [] when nothing, else
        [{"what": "media", "names": [...]}, {"what": "tags", "tags": [...]}].

        A picture already beside the file (the unzipped layout) is not lost, and what the person has already accepted
        to leave out is not asked about again until it changes."""
        accepted = self.m.get("accepted") or {}
        lost = []
        names = [n for n, sha in sorted(payload["media"].items())
                 if n not in (accepted.get("media") or []) and not self._beside(dest, n, sha)]
        if names:
            lost.append({"what": "media", "names": names})
        if payload["tags"] and payload["tags"] != (accepted.get("tags") or []):
            lost.append({"what": "tags", "tags": payload["tags"]})
        return lost

    # ---- saving
    def save(self, target=None, overwrite=False, force=False, accept_loss=False):
        """The one moment the file changes.

        `target`: another path (Save as…): the session then stands for that file, and the original is left as it
        was.  Without it, the file it came from.  Answers {"ok": True, ...} when it is written (or there was nothing
        to write), or {"ok": False, "need": ...} when the person has to say something first:

          conflict  the file was changed on the disk by somebody else since it was seen
          format    a Markdown file cannot hold what the document now has (`reasons`, `suggest`)
          exists    a path chosen for Save as… is already a file
          path      the file is not there any more

        and raises OpenError, in words, for what cannot be done at all."""
        with self.lock:
            payload = self.payload()
            fp = _fingerprint(payload)
            origin = Path(self.path)
            as_new = target is not None and not _same(os.path.expanduser(str(target)), origin)
            dest = self._new_target(target) if as_new else origin
            kind = kind_of(dest)
            if kind is None:
                raise OpenError("Save it as .md, .markdown, .txt or .zip.", "kind")
            if not as_new:
                changed = changed_on_disk(dest, self.m["origin"], fresh=True)
                if changed is None:
                    return {"ok": False, "need": "path", "why": "missing", "path": str(dest), "state": self.state()}
                if fp == self.m.get("published"):
                    return {"ok": True, "unchanged": True, "state": self.state()}
                if changed and not force:
                    return {"ok": False, "need": "conflict", "path": str(dest), "state": self.state()}
            elif dest.exists() and not overwrite:
                return {"ok": False, "need": "exists", "path": str(dest), "state": self.state()}
            lost = []
            if kind == "md":
                lost = self.lost_in_md(dest, payload)
                if lost and not accept_loss:
                    zip_at = dest.with_suffix(".zip")
                    return {"ok": False, "need": "format", "reasons": lost, "path": str(dest), "suggest": str(zip_at),
                            "suggest_exists": zip_at.exists(), "state": self.state()}
            wrote = True
            if kind == "md":
                wrote = self._write_md(dest, payload, as_new)
            elif self.kind == "zip":
                try:                                            # the zip it came from, copied across with the changes
                    self._write_zip_patched(dest, payload)
                except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as e:
                    raise OpenError("Parseh could not copy everything in the zip (%s): nothing was written." % e, "zip")
            else:
                self._write_zip_fresh(dest, payload)            # an md becoming a zip
            self._written(dest, kind, payload, fp, lost, as_new)
            return {"ok": True, "saved": {"path": str(dest), "name": dest.name, "kind": kind, "wrote": wrote,
                                          "bytes": dest.stat().st_size, "as_new": as_new, "left_out": lost},
                    "state": self.state()}

    def _new_target(self, target):
        text = os.path.expanduser(str(target or "").strip().strip('"'))
        if not os.path.isabs(text):
            raise OpenError("Type the whole path of the file to save (it starts with / or a drive letter).", "path")
        dest = Path(os.path.abspath(text))
        if dest.is_dir():
            raise OpenError("%s is a folder: add a file name to it." % dest, "path")
        if is_protected(dest.parent) or is_protected(dest):
            raise OpenError("That place belongs to Parseh's own folders: save it somewhere of yours.", "protected")
        if not dest.parent.is_dir():
            raise OpenError("The folder %s is not there." % dest.parent, "gone")
        if dest.is_symlink():
            dest = Path(os.path.realpath(str(dest)))
        return dest

    def _write_md(self, dest, payload, as_new):
        """The Markdown file, if its text is not what it holds already.  -> whether anything was written.

        The text of a file the person only looked at, or whose pictures alone were changed, is not rewritten: what is
        on the disk may differ from the studio's text in ways the studio normalised on opening (mixed line ends, a
        control character), and those are not the person's to have changed."""
        if not as_new and _sha_text(payload["text"]) == self.m.get("text_sha"):
            return False
        data = encode_text(payload["text"], self.m.get("shape") or {})
        write_file(dest, lambda f: f.write(data), like=dest, stage_dir=self.dir)
        return True

    def _media_path(self, rel):
        folder, name = rel.split("/", 1)
        return (store.images_dir if folder == "images" else store.audio_dir)(self.doc_id) / name

    @staticmethod
    def _tags_bytes(tags):
        return json.dumps({"tags": tags}, ensure_ascii=False, indent=1).encode("utf-8")

    @staticmethod
    def _store_kind(rel):
        """Recordings are already compressed, as every format but WAV is: stored as they are."""
        return zipfile.ZIP_STORED if rel.startswith("audio/") else zipfile.ZIP_DEFLATED

    def _write_zip_fresh(self, dest, payload):
        """A zip made of the document alone, in the studio's own layout (store.doc_zip): <stem>.md, <stem>.tags.json when
        there are tags, images/ and audio/ -- the layout "Upload .md / .zip" takes back."""
        stem = dest.stem
        text = encode_text(payload["text"], self.m.get("shape") or {})
        with self.scope():
            files = [(rel, self._media_path(rel)) for rel in sorted(payload["media"])]

        def fill(f):
            with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(stem + ".md", text)
                if payload["tags"]:
                    zf.writestr(stem + ".tags.json", self._tags_bytes(payload["tags"]))
                for rel, path in files:
                    zf.write(str(path), rel, compress_type=self._store_kind(rel))
        write_file(dest, fill, like=dest, stage_dir=self.dir)

    def _write_zip_patched(self, dest, payload):
        """The zip it came from, with only the document's own entries changed: its Markdown, its tags file and its
        pictures and recordings.  Everything else is copied across as it is, in its order, with its own dates and
        modes; an entry the document did not change is copied too, not rewritten; what the document gained is added at
        the end; what the person deleted is dropped.  `dest` is the zip itself, or -- Save as… -- a copy of it."""
        record = self.m
        entry = record["entry"]
        folder = posixpath.dirname(entry)
        tags_path = record.get("tags_at") or posixpath.join(folder, posixpath.splitext(posixpath.basename(entry))[0]
                                                            + ".tags.json")
        media_at = dict(record.get("media_at") or {})
        by_entry = {n: rel for rel, n in media_at.items()}
        old_media = dict(record.get("media_sha") or {})
        text_same = _sha_text(payload["text"]) == record.get("text_sha")
        tags_same = payload["tags"] == (record.get("tags_open") or [])
        text = encode_text(payload["text"], record.get("shape") or {})
        with self.scope():
            media_files = {rel: self._media_path(rel) for rel in payload["media"]}

        def fill(f):
            with zipfile.ZipFile(self.path) as zin, zipfile.ZipFile(f, "w") as zout:
                zout.comment = zin.comment
                seen = set()
                for info in zin.infolist():
                    name = info.filename.replace("\\", "/")
                    if name == entry:
                        if text_same:
                            self._copy(zin, info, zout)
                        else:
                            self._put(zout, info, text)
                        seen.add("md")
                    elif name == tags_path:
                        if tags_same:
                            self._copy(zin, info, zout)
                        elif payload["tags"]:
                            self._put(zout, info, self._tags_bytes(payload["tags"]))
                        # else: the person took every tag off
                        seen.add("tags")
                    elif name in by_entry:
                        rel = by_entry[name]
                        if rel in payload["media"]:
                            if payload["media"][rel] == old_media.get(rel):
                                self._copy(zin, info, zout)
                            else:
                                with open(media_files[rel], "rb") as src:
                                    self._put(zout, info, src.read())
                            seen.add(rel)
                        # else: the person deleted it
                    else:
                        self._copy(zin, info, zout)
                # what the document gained
                if "tags" not in seen and payload["tags"]:
                    zout.writestr(tags_path, self._tags_bytes(payload["tags"]), compress_type=zipfile.ZIP_DEFLATED)
                for rel in sorted(payload["media"]):
                    if rel not in seen:
                        zout.write(str(media_files[rel]), media_at.get(rel) or posixpath.join(folder, rel),
                                   compress_type=self._store_kind(rel))
        write_file(dest, fill, like=self.path, stage_dir=self.dir)

    @staticmethod
    def _put(zout, info, data):
        """A changed entry written under the name and place the original had."""
        zi = zipfile.ZipInfo(info.filename, time.localtime()[:6])
        zi.compress_type = info.compress_type if info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) \
            else zipfile.ZIP_DEFLATED
        zi.external_attr = info.external_attr
        zi.create_system = info.create_system
        zout.writestr(zi, data)

    @staticmethod
    def _copy(zin, info, zout):
        """An entry carried across as it is: name, order, date, mode, comment, compression, and what else a copy can
        keep of it (its extra fields -- an exact modification time, who owns it -- but not the zip64 one, which is
        about how this archive stores it)."""
        zi = zipfile.ZipInfo(info.filename, info.date_time)
        zi.compress_type = info.compress_type
        zi.external_attr = info.external_attr
        zi.internal_attr = info.internal_attr
        zi.create_system = info.create_system
        zi.comment = info.comment
        zi.extra = _extra_without_zip64(info.extra)
        if info.is_dir():
            zout.writestr(zi, b"")
            return
        with zin.open(info) as src, zout.open(zi, "w", force_zip64=info.file_size > zipfile.ZIP64_LIMIT) as dst:
            shutil.copyfileobj(src, dst, 1 << 20)

    def _written(self, dest, kind, payload, fp, lost, as_new):
        """What the session knows once the file holds the payload."""
        m = self.m
        converted = kind != m["kind"]
        if converted or as_new:
            m["path"] = str(dest)
        if converted:
            # an md became a zip (the layout of store.doc_zip, so the zip's own entries are all the document's), or a
            # zip became an md (it holds none of the zip's entries any more)
            m["kind"] = kind
            m["stem"] = dest.stem
            if kind == "zip":
                m["entry"], m["tags_at"] = dest.stem + ".md", dest.stem + ".tags.json"
                m["media_at"] = {rel: rel for rel in payload["media"]}
            else:
                m["entry"], m["tags_at"], m["media_at"], m["media_sha"] = None, None, {}, {}
        if kind == "zip":
            where = posixpath.dirname(m["entry"])
            m["media_at"] = {rel: (m["media_at"].get(rel) or posixpath.join(where, rel)) for rel in payload["media"]}
            m["media_sha"] = dict(payload["media"])
            m["tags_open"] = list(payload["tags"])
        m["text_sha"] = _sha_text(payload["text"])
        m["own"] = sorted(payload["media"])
        m["origin"] = stat_fp(dest)
        m["published"] = fp
        m["saved"] = _now()
        m.pop("recovered", None)
        if kind == "md":
            # what the person accepted to leave out of a Markdown file is not asked about again, unless it changes
            was = m.get("accepted") or {}
            m["accepted"] = {
                "media": sorted(set(was.get("media") or []) | {n for l in lost if l["what"] == "media" for n in l["names"]}),
                "tags": payload["tags"] if any(l["what"] == "tags" for l in lost) else (was.get("tags") or [])}
        else:
            m["accepted"] = {}
        self.keep()

    # ---- closing
    def close(self, discard=False):
        """The working copy goes.  Answers {"ok": False, "need": "unsaved"} while it holds something the file does
        not, unless the person said to discard it."""
        with self.lock:
            if not discard:
                try:
                    dirty = self.dirty()
                except (KeyError, OSError, ValueError, store.StoreError):
                    dirty = False               # the working copy is gone: there is nothing left to keep
                if dirty:
                    return {"ok": False, "need": "unsaved", "state": self.state()}
            self._remove()
            return {"ok": True}

    def _remove(self):
        with _GUARD:
            _SESSIONS.pop(self.sid, None)
        shutil.rmtree(str(self.dir), ignore_errors=True)


# ----------------------------------------------------------------------------------------------- opening
def get(sid):
    """The session of an id, from memory or -- after Parseh was stopped and started again -- from its folder.
    KeyError when there is none."""
    if not SID_RE.match(sid or ""):
        raise KeyError(sid)
    with _GUARD:
        s = _SESSIONS.get(sid)
        if s is not None:
            return s
        folder = OPEN_DIR / sid
        if not (folder / "session.json").is_file():
            raise KeyError(sid)
        try:
            s = Session.load(folder)
        except (OSError, ValueError, KeyError):
            raise KeyError(sid)
        _SESSIONS[sid] = s
        return s


def live():
    """Every session there is, the ones in memory and the ones a stopped Parseh left in OPEN_DIR."""
    out = []
    if OPEN_DIR.is_dir():
        for d in sorted(OPEN_DIR.iterdir()):
            if d.is_dir() and SID_RE.match(d.name):
                try:
                    out.append(get(d.name))
                except KeyError:
                    continue
    return out


def find(real):
    """The session of this very file, if there is one."""
    for s in live():
        if _same(s.path, real):
            return s
    return None


def _check_openable(path):
    real = real_path(path)
    if not real.exists():
        raise OpenError("%s is not there." % real, "gone")
    if real.is_dir():
        raise OpenError("%s is a folder. Choose a file in it." % real.name, "path")
    if not real.is_file():
        raise OpenError("%s is not a file the studio can open." % real.name, "kind")
    kind = kind_of(real)
    if kind is None:
        raise OpenError("The studio opens Markdown (.md, .markdown, .txt) and zip files, not %s." % (real.suffix or "this"),
                        "kind")
    if is_protected(real):
        raise OpenError("%s is one of Parseh's own files. Open it from where it belongs: a document from the library, a "
                        "note from its book or video." % real.name, "protected")
    if not os.access(str(real), os.R_OK):
        raise OpenError("Parseh may not read %s." % real.name, "denied")
    return real, kind


_OPEN_LOCK = threading.Lock()           # one file is read into a working copy at a time; getting a session is not blocked


def open_path(path, entry=None):
    """Open a file -> {"session": Session, "again": bool}, or {"choose": [...], "name"} for a zip holding several
    Markdown files (open again with `entry`), or an OpenError in words."""
    real, kind = _check_openable(path)
    with _OPEN_LOCK:
        old = find(real)
        if old is not None:
            if entry and old.kind == "zip" and old.m.get("entry") != entry:
                # two sessions on one zip would each patch it, and the second would take the first one's changes away
                raise OpenError("%s is already open, on %s. Close that first to open %s from it."
                                % (real.name, old.m.get("entry"), entry), "busy", sid=old.sid)
            return {"session": old, "again": True}
        OPEN_DIR.mkdir(parents=True, exist_ok=True)
        sid = uuid.uuid4().hex[:12]
        folder = OPEN_DIR / sid
        try:
            folder.mkdir()
            if kind == "md":
                s = _open_md(folder, sid, real)
            else:
                got = _open_zip(folder, sid, real, entry)
                if "choose" in got:
                    shutil.rmtree(str(folder), ignore_errors=True)
                    return got
                s = got["session"]
        except BaseException:
            shutil.rmtree(str(folder), ignore_errors=True)
            raise
        with _GUARD:
            s = _SESSIONS.setdefault(sid, s)
        return {"session": s, "again": False}


def _name_ok(folder, name):
    """Is `name` one a document's picture (folder "images") or recording ("audio") may have?  The studio's own rules for
    what it stores, applied before a file of that name is touched."""
    if folder == "images":
        return bool(store.IMG_NAME_RE.match(name) and not store.DERIVED_RE.search(name))
    return bool(audiofile.NAME_RE.match(name))


def _size_max(folder):
    return store.IMG_MAX if folder == "images" else audiofile.MAX_BYTES


def _media_ok(folder, name, data):
    """May these bytes stand as a picture / a recording of a document under this name?"""
    if not _name_ok(folder, name) or len(data) > _size_max(folder):
        return False
    if folder == "images":
        return store._img_kind(data) is not None
    return audiofile.kind(data[:4096], name) is not None


def _put_media(doc_id, rel, data):
    folder, name = rel.split("/", 1)
    d = (store.images_dir if folder == "images" else store.audio_dir)(doc_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(data)
    if name.endswith(".pdf"):
        store.ensure_pdf_twin(d / name)


def _unchanged(real, st):
    """The file was not touched while it was being read: a record made of half of one version and half of another
    would be a document nobody wrote."""
    now = os.stat(real)
    if (now.st_size, now.st_mtime_ns) != (st.st_size, st.st_mtime_ns):
        raise OpenError("%s was changed while it was being opened. Open it again." % Path(real).name, "busy")


def _settle(folder, sid, kind, real, origin, text, shape, tags, media, warnings, extra):
    """The working copy made and the session recorded: the one place both kinds go through."""
    m = {"format": FORMAT, "sid": sid, "kind": kind, "path": str(real), "stem": real.stem, "doc_id": "", "shape": shape,
         "origin": origin, "published": "", "opened": _now(), "saved": None, "accepted": {}, "warnings": warnings,
         "own": sorted(media)}
    m.update(extra)
    s = Session(folder, m)
    with s.scope():
        meta = store.create_exact(text, tags)
        m["doc_id"] = meta["id"]
        for rel, data in sorted(media.items()):
            _put_media(meta["id"], rel, data)
    # what the studio holds now is what the file holds: the baseline every later "has it changed?" compares with
    # (taken from the working copy, not from `text`: the store may read a lone CR as a line end, and the tags are its
    # lower-cased ones)
    first = s.payload()
    m["published"] = _fingerprint(first)
    m["text_sha"] = _sha_text(first["text"])
    m["tags_open"] = first["tags"]
    s.keep()
    return s


def _plural(n, one, many):
    return one if n == 1 else many


def _open_md(folder, sid, real):
    st = os.stat(real)
    if st.st_size > MD_MAX:
        raise OpenError("%s is larger than %d MB, which is more than the studio opens." % (real.name, MD_MAX // 2 ** 20),
                        "size")
    try:
        data = real.read_bytes()
    except OSError as e:
        raise OpenError("Parseh could not read %s (%s)." % (real.name, e.strerror or "denied"), "denied")
    _unchanged(real, st)
    origin = {"size": len(data), "mtime_ns": st.st_mtime_ns, "sha256": hashlib.sha256(data).hexdigest()}
    text, shape, dropped = decode_text(data, real.name)
    warnings = []
    if dropped:
        warnings.append("%d control character%s the Markdown never means %s left out of the text."
                        % (dropped, _plural(dropped, "", "s"), _plural(dropped, "was", "were")))
    # the pictures and recordings that sit beside the file when it names them -- in images/ and audio/ (the layout a zip
    # of it unpacks to) or in its own folder: read, never written, never deleted
    media, missing = {}, []
    for folder_name in ("images", "audio"):
        for ref in store._named(text, folder_name):
            rel = "%s/%s" % (folder_name, ref)
            if not _name_ok(folder_name, ref):
                warnings.append("%s is not a name the studio keeps a %s under (lower-case letters, digits, . - _)."
                                % (rel, "picture" if folder_name == "images" else "recording"))
                continue
            found = next((f for f in _beside_candidates(real.parent, rel) if f.is_file()), None)
            if found is None:
                if store.starter_media(folder_name, ref) is None:
                    missing.append(rel)
                continue                  # a starter's own comes from where Parseh ships it
            try:
                if found.stat().st_size > _size_max(folder_name):
                    warnings.append("%s beside the file is too large for the studio to show." % rel)
                    continue
                blob = found.read_bytes()
            except OSError:
                missing.append(rel)
                continue
            if _media_ok(folder_name, ref, blob):
                media[rel] = blob
            else:
                warnings.append("%s beside the file is not a %s the studio can show."
                                % (rel, "picture" if folder_name == "images" else "recording"))
    if missing:
        warnings.append("It names %s, which %s not beside it." % (", ".join(sorted(missing)),
                                                                   _plural(len(missing), "is", "are")))
    return _settle(folder, sid, "md", real, origin, text, shape, [], media, warnings, {"entry": None})


def _read_entry(zf, info):
    """What an entry holds -- or a sentence for each way a damaged or unusual one can fail to be read: a checksum that does
    not match what was stored, a compression Python does not have, a password."""
    try:
        return zf.read(info)
    except (OSError, zipfile.BadZipFile, NotImplementedError, RuntimeError) as e:
        raise OpenError("%s could not be read out of the zip (%s)." % (info.filename, e), "zip")


def _zip_names(zf):
    """name (with "/") -> ZipInfo, for the files of a zip that mean something to the studio: nothing from outside the
    zip's tree, no resource fork, nothing hidden -- the rule the library's own import goes by."""
    out = {}
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = info.filename.replace("\\", "/")
        parts = name.split("/")
        if name.startswith("/") or ".." in parts or parts[0] == "__MACOSX" or any(p.startswith(".") for p in parts):
            continue
        out.setdefault(name, info)
    return out


def _is_backup(names):
    """Is this the Backup button's zip of a whole library (store.import_library's layout: <language folder>/<id>/ with a
    meta.json beside each source.md)?  Opened as a document, a save would change one source.md and leave its meta.json
    saying the old thing."""
    for n in names:
        parts = n.split("/")
        if len(parts) >= 3 and parts[-1] == "meta.json" and languages.by_folder(parts[0]) is not None \
                and store.ID_RE.match(parts[1]):
            return True
    return False


BACKUP_WORDS = ("That zip is a backup of a whole library. Put it back with Load from backup on the studio's library "
                "page, or open one document of it.")


def _why_no_markdown(names):
    """What to tell somebody who opened a zip with no Markdown file in it."""
    if names and all(n.lower().endswith(".zip") for n in names):
        return "That zip holds other zips, one for each document. Unpack it and open the one you want."
    return "That zip holds no Markdown file (.md), so there is nothing in it for the studio to open."


def _open_zip(folder, sid, real, entry):
    st = os.stat(real)
    try:
        zf = zipfile.ZipFile(str(real))
    except (zipfile.BadZipFile, OSError):
        raise OpenError("%s is not a zip file the studio can read." % real.name, "zip")
    with zf:
        infos = zf.infolist()
        if len(infos) > ZIP_ENTRIES_MAX:
            raise OpenError("%s holds more than %d files." % (real.name, ZIP_ENTRIES_MAX), "size")
        if any(i.flag_bits & 0x1 for i in infos):
            raise OpenError("%s is password-protected: the studio cannot read it." % real.name, "zip")
        names = _zip_names(zf)
        if _is_backup(names):
            raise OpenError(BACKUP_WORDS, "zip")
        texts = sorted(n for n in names if n.lower().endswith((".md", ".markdown")))
        if not texts:
            raise OpenError(_why_no_markdown(list(names)), "zip")
        if entry is None and len(texts) > 1:
            return {"choose": [{"path": n, "size": names[n].file_size, "title": _title_of(zf, names[n])} for n in texts],
                    "name": real.name}
        entry = entry or texts[0]
        if entry not in texts:
            raise OpenError("%s holds no %s." % (real.name, entry), "zip")
        info = names[entry]
        if info.file_size > MD_MAX:
            raise OpenError("%s inside the zip is larger than %d MB." % (entry, MD_MAX // 2 ** 20), "size")
        text, shape, dropped = decode_text(_read_entry(zf, info), entry)
        warnings = []
        if dropped:
            warnings.append("%d control character%s left out of the text." % (dropped, _plural(dropped, "", "s")))
        stem = posixpath.splitext(posixpath.basename(entry))[0]
        where = posixpath.dirname(entry)
        by_lower = {}
        for n in names:
            by_lower.setdefault(n.lower(), n)

        def find_entry(*candidates):
            for cand in candidates:
                if cand in names:
                    return cand
                low = by_lower.get(cand.lower())
                if low:
                    return low
            return None

        # what the document shows, and what else its images/ and audio/ hold (the Images and Recordings lists show them)
        wanted, missing = {}, []
        for folder_name in ("images", "audio"):
            for ref in store._named(text, folder_name):
                at = find_entry(posixpath.join(where, folder_name, ref), posixpath.join(where, ref))
                if at:
                    wanted["%s/%s" % (folder_name, ref)] = at
                elif store.starter_media(folder_name, ref) is None:
                    missing.append("%s/%s" % (folder_name, ref))
            prefix = posixpath.join(where, folder_name) + "/" if where else folder_name + "/"
            for n in names:
                if n.startswith(prefix) and "/" not in n[len(prefix):]:
                    wanted.setdefault("%s/%s" % (folder_name, n[len(prefix):]), n)
        tags_path = find_entry(posixpath.join(where, stem + ".tags.json"))
        tags = []
        if tags_path:
            if names[tags_path].file_size > 1 << 20:
                warnings.append("%s is too large to be a list of tags: it was left alone." % tags_path)
                tags_path = None
            else:
                try:
                    got = json.loads(_read_entry(zf, names[tags_path]).decode("utf-8-sig"))
                    got = got.get("tags") if isinstance(got, dict) else got
                    tags = [str(t) for t in got if str(t).strip()] if isinstance(got, list) else []
                except (ValueError, UnicodeDecodeError, OSError, KeyError):
                    tags = []
                except OpenError as e:               # tags are worth carrying and not worth a refusal
                    tags = []
                    warnings.append("%s could not be read, so the tags in it were left alone (%s)" % (tags_path, e.say))
        # what is READ out of the zip is bounded: the document and what it shows
        total = info.file_size
        media, media_at, claimed = {}, {}, set()
        for rel, at in sorted(wanted.items()):
            folder_name, name = rel.split("/", 1)
            if not _name_ok(folder_name, name):
                warnings.append("%s is not a name the studio keeps a %s under: it was left alone."
                                % (at, "picture" if folder_name == "images" else "recording"))
                continue
            if names[at].file_size > _size_max(folder_name):
                warnings.append("%s is too large for the studio to show: it was left alone." % at)
                continue
            if at in claimed:
                continue
            total += names[at].file_size
            if total > ZIP_MANAGED_MAX:
                raise OpenError("The document in %s and its pictures and recordings add up to more than %d MB."
                                % (real.name, ZIP_MANAGED_MAX // 2 ** 20), "size")
            data = _read_entry(zf, names[at])
            if _media_ok(folder_name, name, data):
                media[rel] = data
                media_at[rel] = names[at].filename.replace("\\", "/")
                claimed.add(at)
            else:
                warnings.append("%s is not a %s the studio can show: it was left alone."
                                % (at, "picture" if folder_name == "images" else "recording"))
        if missing:
            warnings.append("It names %s, which %s not in the zip." % (", ".join(sorted(missing)),
                                                                      _plural(len(missing), "is", "are")))
    # fingerprinted after it was read, and the file must not have moved meanwhile: its checksum is what a later save
    # compares the disk with
    _unchanged(real, st)
    origin = {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": sha256_of(real)}
    _unchanged(real, st)
    s = _settle(folder, sid, "zip", real, origin, text, shape, tags, media, warnings, {
        "entry": entry, "stem": stem, "tags_at": tags_path or posixpath.join(where, stem + ".tags.json"),
        "media_at": media_at, "media_sha": {rel: hashlib.sha256(data).hexdigest() for rel, data in media.items()}})
    return {"session": s}


def _title_of(zf, info):
    """A Markdown file's title for the list of a zip's files: its `title:` line, or its first heading."""
    try:
        with zf.open(info) as f:
            head = f.read(4096).decode("utf-8", "replace")
    except (OSError, KeyError, RuntimeError, zipfile.BadZipFile, NotImplementedError):
        return ""
    m = re.search(r"(?m)^title:\s*(.+?)\s*$", head) or re.search(r"(?m)^#\s+(.+?)\s*$", head)
    return m.group(1).strip("\"'") if m else ""


# ------------------------------------------------------------------------------------- start and stop
def sweep(now=None):
    """When Parseh starts: the sessions a stopped Parseh left.  One holding nothing unsaved is deleted; one holding
    something is kept and offered back (marked `recovered`); a folder whose record cannot be read is deleted once it
    is a day old (younger, it may be being made).  -> {"kept": [...], "removed": [...]}"""
    now = now or _now()
    kept, removed = [], []
    if not OPEN_DIR.is_dir():
        return {"kept": kept, "removed": removed}
    for d in sorted(OPEN_DIR.iterdir()):
        if not d.is_dir() or not SID_RE.match(d.name):
            continue
        try:
            s = get(d.name)
        except KeyError:
            # A folder whose record cannot be read is thrown away once it is a day old -- unless it has a record that
            # reads as one and a working copy beside it: that is somebody's unsaved work which this Parseh cannot open
            # (made by another version, say), and the only copy there is.  It is left where it is.
            try:
                old = now - d.stat().st_mtime > SWEEP_ORPHAN_SECONDS
            except OSError:
                old = False
            if old and not _holds_work(d):
                shutil.rmtree(str(d), ignore_errors=True)
                removed.append(d.name)
            continue
        try:
            dirty = s.dirty()
        except Exception:                # noqa: BLE001 -- unsure is not a reason to delete somebody's work
            dirty = True
        if dirty:
            s.m["recovered"] = True
            try:
                s.keep()
            except OSError:
                pass
            kept.append(d.name)
        else:
            s._remove()
            removed.append(d.name)
    return {"kept": kept, "removed": removed}


def _holds_work(folder):
    """Could this folder be a session of somebody's with a working copy in it?  A record that reads as JSON and a
    `library/` beside it."""
    try:
        json.loads((Path(folder) / "session.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (Path(folder) / "library").is_dir()


def shutdown():
    """When Parseh stops: the sessions holding nothing unsaved are deleted (sweep does the same at the next start, for
    a Parseh that did not stop in order)."""
    removed = []
    for s in live():
        try:
            if not s.dirty():
                s._remove()
                removed.append(s.sid)
        except Exception:                # noqa: BLE001
            continue
    return removed
