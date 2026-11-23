# SPDX-License-Identifier: GPL-3.0-or-later
"""A whole shelf of books, or of videos, backed up and put back.

WHY THIS IS A ZIP OF ZIPS and not a zip of the tree.  Every book and every
video already has a bundle: lib/bundle.py decides what of it travels, and an
allowlist read in BOTH directions decides what may come back.  A flat zip of
`books/` would walk straight past that door -- and past the budgets it keeps,
which are per bundle: MAX_ENTRIES is five thousand and MAX_UNPACKED is sixty
megabytes of text, and one shelf of narrated books is more than either.  So a
backup holds one bundle per book, each with its own manifest, its own budget
and its own refusal, and a restore is bundle.install called once per bundle.

It also means a backup can be taken apart: the zip a backup gives holds the
very zips the "bring a book back" panel takes one at a time, so half a
restore is always possible by hand.

The studio says the same thing about its own documents, and got there first:
"A zip of zips is the only honest way to carry media for many documents at
once: their images/ and audio/ would otherwise land in one heap with every
name free to collide."

A BOOK COMES WITH ITS RECORDINGS (TO-DO 6.16).  Each book packs in the
`full` shape -- its audio/ folder, the timings, the review and the
corrections, book.json still naming them -- as a video packs with its film.
A backup is for putting a shelf back as it was, and a recording is the one
part of a narrated book nothing can make again.  `full` is as old as
bundles are (parseh-bundle/3 has always had it), so an older Parseh loads
such a backup as it is: the format numbers stay where they were.

WRITTEN TO DISK AND NOT TO MEMORY.  A narrated book is a couple of hundred
megabytes and a shelf is as many of those as somebody has.  Each bundle is
written to a file in Parseh's own `.tmp/` (lib/scratch.py, never the
system's temp folder, which can be a small tmpfs), copied into the outer zip
from there and deleted; and the outer zip is built in such a file too and
streamed from it.  A restore takes each bundle out to such a file in the
same way before bundle.install reads it.  So nothing is ever held whole in
memory: what is on the disk at once is the backup and one bundle.
"""
import io
import json
import os
import shutil
import zipfile
from datetime import datetime

import books as booklib
import bundle
import scratch

MANIFEST = "parseh-shelf.json"
FORMAT = "parseh-shelf/2"
KINDS = ("book", "video")

# A shelf is bigger than a bundle in every direction, and these are the only
# numbers that are the shelf's own: what one bundle may hold is bundle.py's
# to say, and it says it again for each of them on the way back in.
MAX_ITEMS = 2000


class ShelfError(Exception):
    """What a backup or a restore refuses, said as somebody would read it."""


def _stamp(now=None):
    return (now or datetime.now()).strftime("%Y%m%d-%H%M")


def _video_dirs():
    """Imported late: youtube/lib is on the path only once ytpages is."""
    import ytpages
    return [path for _folder, _vid, path in ytpages.video_dirs()]


def items(kind, root=None):
    """Every directory on the shelf, in a settled order."""
    if kind == "book":
        return sorted(booklib.book_dirs(
            os.path.join(root, "books") if root else booklib.BOOKS_DIR))
    if kind == "video":
        return sorted(_video_dirs())
    raise ShelfError("there is no shelf of %r" % kind)


def pack(kind, mode=None, root=None):
    """The whole shelf as one zip -> (path to a temporary file, filename).

    THE CALLER DELETES THE FILE.  It is written rather than returned as
    bytes, in Parseh's own `.tmp/` (lib/scratch.py; under `root` when one is
    given), and so is each bundle on its way into it.

    `mode` is the shape each item packs in (bundle.MODES), or None for the
    backup's own: `full` for a book -- its recordings with it (6.16) -- and
    for a video whatever it wants, its film where it has one.  A book with no
    narration reads the same in all three.
    """
    if kind not in KINDS:
        raise ShelfError("there is no shelf of %r" % kind)
    found = items(kind, root)
    if len(found) > MAX_ITEMS:
        raise ShelfError("this shelf holds more than %d %ss" % (MAX_ITEMS, kind))
    if kind == "book":
        def pack_one(d, to):
            return bundle.pack_book(d, mode or "full", to=to)
    else:
        def pack_one(d, to):
            return bundle.pack_video(d, mode, to=to)
    fd, path = scratch.mkstemp(prefix="parseh-shelf-", suffix=".zip", at=root)
    os.close(fd)
    listed, notes = [], []
    try:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
            for d in found:
                fd, one = scratch.mkstemp(prefix="parseh-bundle-", suffix=".zip", at=root)
                os.close(fd)
                try:
                    try:
                        _done, name = pack_one(d, one)
                    except bundle.BundleError as e:
                        # one book nobody can pack is not a reason to have no
                        # backup of the other forty
                        notes.append("%s: %s" % (os.path.basename(d), e))
                        continue
                    # STORED, not deflated: a bundle is a zip already, and
                    # deflating a zip costs the whole file's work for nothing
                    zf.write(one, name, zipfile.ZIP_STORED)
                finally:
                    _unlink(one)
                listed.append({"file": name, "name": os.path.basename(d)})
            zf.writestr(MANIFEST, json.dumps({
                "format": FORMAT, "software": "Parseh", "kind": kind,
                "exported": datetime.now().isoformat(timespec="seconds"),
                "shape": mode or ("full" if kind == "book" else ""), "items": listed, "notes": notes,
            }, ensure_ascii=False, indent=1).encode("utf-8"))
    except BaseException:
        _unlink(path)
        raise
    return path, "%ss-backup-%s.zip" % (kind, _stamp())


def restore(kind, source, replace=False, root=None):
    """A backup put back -> {"restored", "kept", "warnings", "dirs"}.

    `dirs` says where each one restored now lies, relative to the toolbox as
    bundle.install says it, for a caller with more to do to what came in
    (serve.py brings the notes that came with each up to names).

    A book or a video already on the shelf is KEPT and named in the answer
    unless `replace` says otherwise -- the studio's rule for its library,
    for the studio's reason: a restore is not a merge, and the backup is
    usually the older of the two.

    Each item goes in through bundle.install, which is the door that already
    refuses what may not come back, and which stages and swaps each one on
    its own -- so a restore that fails on the seventh leaves the first six
    installed and the seventh untouched.
    """
    if kind not in KINDS:
        raise ShelfError("there is no shelf of %r" % kind)
    try:
        zf = (zipfile.ZipFile(io.BytesIO(bytes(source)))
              if isinstance(source, (bytes, bytearray, memoryview))
              else zipfile.ZipFile(source))
    except FileNotFoundError:
        raise ShelfError("the backup to restore is not there")
    except (zipfile.BadZipFile, ValueError, OSError, EOFError):
        raise ShelfError("that is not a zip file")
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > MAX_ITEMS + 1:
            raise ShelfError("that backup holds more than %d %ss" % (MAX_ITEMS, kind))
        names = {i.filename: i for i in infos}
        if MANIFEST not in names:
            raise ShelfError("that zip is not a %s backup: it has no %s" % (kind, MANIFEST))
        try:
            doc = json.loads(zf.read(names[MANIFEST]).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ShelfError("that backup's %s is not readable" % MANIFEST)
        if not isinstance(doc, dict) or not _reads(doc.get("format"), FORMAT):
            raise ShelfError("that zip is not a shelf backup this version reads")
        if doc.get("kind") != kind:
            raise ShelfError("that is a backup of %ss; this is where %ss go"
                             % (doc.get("kind") or "something else", kind))
        restored, kept, warnings, dirs = [], [], [], []
        inner = sorted(n for n in names if n != MANIFEST)
        if not inner:
            raise ShelfError("that backup holds no %ss" % kind)
        for name in inner:
            # NOTHING IS TRUSTED BECAUSE THE MANIFEST LISTED IT.  Every
            # entry goes to bundle, which says what it is and whether it may
            # come back; a name is only ever used to say which one failed.
            # TAKEN OUT TO A FILE, not read into memory: a bundle may carry a
            # recording or a film of gigabytes (3.9), and bundle reads a path
            # as readily as bytes
            fd, data = scratch.mkstemp(prefix="parseh-bundle-", suffix=".zip", at=root)
            try:
                with os.fdopen(fd, "wb") as out, zf.open(names[name]) as src:
                    shutil.copyfileobj(src, out, 1 << 20)
            except (zipfile.BadZipFile, OSError, ValueError, EOFError) as e:
                _unlink(data)
                warnings.append("%s could not be read (%s)" % (name, e))
                continue
            try:
                what = bundle.inspect(data, **({"root": root} if root else {}))
                if what.get("kind") != kind:
                    warnings.append("%s holds a %s, not a %s"
                                    % (name, what.get("kind") or "something else", kind))
                    continue
                out = bundle.install(data, replace=replace,
                                     **({"root": root} if root else {}))
            except bundle.Exists:
                # the one refusal that is not a fault: it is here already,
                # and saying so is the whole of the kept-unless-asked rule
                kept.append(what.get("name") or name)
                continue
            except bundle.BundleError as e:
                warnings.append("%s: %s" % (name, e))
                continue
            except (OSError, ValueError) as e:
                warnings.append("%s could not be put back (%s)" % (name, e))
                continue
            finally:
                _unlink(data)
            restored.append(out.get("name") or name)
            if out.get("dir"):
                dirs.append(out["dir"])
        return {"restored": restored, "kept": kept, "warnings": warnings, "dirs": dirs}


def _unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _reads(stamp, fmt):
    """Is `stamp` one this Parseh reads -- its own, or any number before it
    (a0.4.0 raised them for the latex block, TO-DO §8.39: what an older
    Parseh wrote holds none, and is read as it always was)?"""
    name, _, n = fmt.rpartition("/")
    if not isinstance(stamp, str) or not stamp.startswith(name + "/"):
        return False
    have = stamp[len(name) + 1:]
    return have.isdigit() and 1 <= int(have) <= int(n)
