# SPDX-License-Identifier: GPL-3.0-or-later
"""Builds travel with their source (a0.7.0 lane G; docs/sync.md "Builds").

A second computer that receives a book's source and not its reader could
never read it without LaTeX -- and a phone never has LaTeX.  So a BUILD
travels too, as files that never change once written:

  * a book's reader (reader/) and its PDF (the *.pdf at the book's top);
  * a studio document's or a note's PDF, with its .tex (build/*.pdf|.tex|.html);
  * the drawings of LaTeX blocks (markdown/latex/), found by their content.

EVERY BUILD RECORDS THE SOURCE IT WAS MADE FROM.  At a build's end (bookbuild,
tex2html, the studio's build_pdf, a lent build written here) record() writes
`<unit folder>/.built-from.json`: per part ("reader", "pdf") the hash of the
source unit (syncunits.snapshot, the very hash sync compares) and when.  A
hidden name, so it is never part of the source unit itself.

THE MATCHING RULE.  A partner's build of a part is TAKEN when the source it
was built from is the source this computer now has, and this computer's own
build of that part is missing or was built from another source.  Never asked,
never a conflict: two builds of one source are the same reading.  A unit this
device leaves out ("holding") never has its build fetched.

OUT OF DATE (lane C's API, lib/syncrules.py) is read from the same records:
this computer's build was made from a source other than the current one, and
no partner has said it holds a build of the current one.  A partner's rebuild
arriving clears the mark by itself: the record then names the current source.

The rows a partner has ride `sync.have`'s answer ("builds", "drawings"); the
files come through `sync.blob` by sha256 (local_file below serves them), so
nothing here opens a connection of its own.  Standard library only.
"""
import json
import os
import secrets
import shutil
import sys
import threading
import time

LIB = os.path.dirname(os.path.abspath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import syncunits  # noqa: E402

SIDECAR = ".built-from.json"
PARTS = {"book": ("reader", "pdf"), "doc": ("pdf",), "note": ("pdf",)}
WORDS = {"reader": "the reader", "pdf": "the PDF"}
DOC_BUILT = (".pdf", ".tex", ".html")
ON_ARRIVED = []          # callbacks([uid, …]) after builds were written here (serve.py: the library page)
_LOCK = threading.RLock()
_SEEN = {}               # home -> {partner: {uid: {part: source hash}}}
_IDX = {"at": 0.0, "home": None, "map": {}}
IDX_TTL = 5.0


# ------------------------------------------------------------------ the files of a build
def _visible(name):
    return not (name.startswith(".") or name.endswith((".tmp", ".part", "~")))


def part_files(u, part):
    """{inner: absolute path} of one part of a unit's build on this disk."""
    out = {}
    w = u.where
    if u.kind == "book" and part == "reader":
        top = os.path.join(w, "reader")
        for here, dirs, files in os.walk(top):
            dirs[:] = sorted(d for d in dirs if _visible(d))
            for f in files:
                if _visible(f):
                    p = os.path.join(here, f)
                    out[os.path.relpath(p, w).replace(os.sep, "/")] = p
    elif u.kind == "book" and part == "pdf":
        try:
            for f in sorted(os.listdir(w)):
                p = os.path.join(w, f)
                if _visible(f) and f.endswith(".pdf") and os.path.isfile(p):
                    out[f] = p
        except OSError:
            pass
    elif u.kind in ("doc", "note") and part == "pdf":
        b = os.path.join(w, "build")
        try:
            for f in sorted(os.listdir(b)):
                p = os.path.join(b, f)
                if _visible(f) and f.endswith(DOC_BUILT) and os.path.isfile(p):
                    out["build/" + f] = p
        except OSError:
            pass
    return out


def _inner_ok(u, part, inner):
    bits = inner.split("/")
    if any(b in ("", ".", "..") or b.startswith(".") or os.sep in b for b in bits):
        return False
    if u.kind == "book" and part == "reader":
        return bits[0] == "reader" and len(bits) >= 2
    if u.kind == "book" and part == "pdf":
        return len(bits) == 1 and inner.endswith(".pdf")
    return len(bits) == 2 and bits[0] == "build" and inner.endswith(DOC_BUILT)


def _filehash(p):
    try:
        import synclog
        return synclog.filehash(p)
    except Exception:                                   # noqa: BLE001 -- no log: hash it
        return syncunits.sha256_file(p)


def source_hash(u):
    """The hash of the source unit as it is now (None when it is not here)."""
    snap = syncunits.snapshot(u, _filehash)
    return snap["hash"] if snap else None


# ------------------------------------------------------------------ the record
def _sidecar(u):
    return os.path.join(u.where, SIDECAR)


def read_record(u):
    try:
        with open(_sidecar(u), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    parts = doc.get("parts") if isinstance(doc, dict) else None
    return {k: v for k, v in (parts or {}).items() if isinstance(v, dict) and k in WORDS}


def _write_record(u, parts):
    path = _sidecar(u)
    tmp = "%s.%s.tmp" % (path, secrets.token_hex(4))
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"format": 1, "parts": parts}, fh, sort_keys=True)
    os.replace(tmp, path)


def unit_of_dir(folder):
    """The book, document or note whose folder this is, or None."""
    folder = os.path.realpath(os.fspath(folder))
    try:
        for u in syncunits.units_for(folder):
            if u.kind in PARTS and os.path.realpath(u.where) == folder:
                return u
    except Exception:                                   # noqa: BLE001
        return None
    return None


def record(folder, parts=None, source=None):
    """A build has just ended in `folder` (a book's, a document's, a note's):
    write which source each part was built from -> the record, or None.  Never
    raises: a build never fails for sync's sake."""
    try:
        u = folder if isinstance(folder, syncunits.Unit) else unit_of_dir(folder)
        if u is None:
            return None
        h = source if source is not None else source_hash(u)
        with _LOCK:
            rec = read_record(u)
            for part in parts or PARTS[u.kind]:
                if part in PARTS[u.kind] and part_files(u, part):
                    rec[part] = {"source": h, "at": time.time()}
            _write_record(u, rec)
        _INVALIDATE()
        _request_sync()
        return rec
    except Exception as e:                              # noqa: BLE001
        print("!! sync: a build's record could not be written: %s" % e, flush=True)
        return None


def note_taken(uid):
    """A partner's version of a source was written here (syncexchange.ON_TAKEN):
    a build that predates the records is marked as made from another source,
    so it shows out of date and a partner's matching build replaces it."""
    try:
        u = syncunits.locate(uid)
    except KeyError:
        return
    if u.kind not in PARTS:
        return
    with _LOCK:
        rec = read_record(u)
        changed = False
        for part in PARTS[u.kind]:
            if part not in rec and part_files(u, part):
                rec[part] = {"source": None, "at": time.time(), "unrecorded": True}
                changed = True
        if changed:
            _write_record(u, rec)


def _INVALIDATE():
    with _LOCK:
        _IDX["at"] = 0.0


def _request_sync():
    try:
        import syncexchange
        if syncexchange._SCHED["thread"] is not None and syncexchange._SCHED["thread"].is_alive():
            syncexchange.request(None, "a build made here")
    except Exception:                                   # noqa: BLE001
        pass


# ------------------------------------------------------------------ what this computer has
def _units():
    for w in (syncunits._books, syncunits._library):
        for u in w():
            if u.kind in PARTS:
                yield u


def here():
    """{uid: {part: {"source", "files": {inner: sha}}}} of every build here that
    records its source (the rows a partner reads)."""
    out = {}
    for u in _units():
        rec = read_record(u)
        if not rec:
            continue
        for part, r in rec.items():
            if not r.get("source"):
                continue
            files = part_files(u, part)
            if not files:
                continue
            shas = {}
            for inner, p in files.items():
                try:
                    shas[inner] = _filehash(p)
                except OSError:
                    continue
            out.setdefault(u.id, {})[part] = {"source": r["source"], "files": shas}
    return out


def _index():
    """sha256 -> a path, over every recorded build and every drawing here."""
    import synclog
    with _LOCK:
        if _IDX["home"] == synclog.home() and time.time() - _IDX["at"] < IDX_TTL:
            return _IDX["map"]
    m = {}
    for uid, parts in here().items():
        u = syncunits.locate(uid)
        for part, b in parts.items():
            for inner, sha in b["files"].items():
                m.setdefault(sha, syncunits.path_of(u, inner))
    for ck, d in drawings_here().items():
        for name, sha in d["files"].items():
            m.setdefault(sha, _drawing_path(d["key"], name))
    with _LOCK:
        _IDX.update(at=time.time(), home=synclog.home(), map=m)
    return m


def local_file(sha):
    """A build's or a drawing's file with this sha256 here, or None (sync.blob)."""
    p = _index().get(sha)
    if p and os.path.isfile(p) and _filehash(p) == sha:
        return p
    if p:
        _INVALIDATE()
    return None


def rows():
    """What sync.have adds to its answer."""
    return {"builds": here(), "drawings": drawings_here()}


# ------------------------------------------------------------------ what partners have
def _seen_path():
    import synclog
    return os.path.join(synclog.home(), "builds-seen.json")


def _seen():
    import synclog
    h = synclog.home()
    with _LOCK:
        if h not in _SEEN:
            try:
                with open(_seen_path(), encoding="utf-8") as fh:
                    _SEEN[h] = json.load(fh) or {}
            except (OSError, ValueError):
                _SEEN[h] = {}
        return _SEEN[h]


def _note_seen(partner, builds, complete):
    small = {uid: {part: b.get("source") for part, b in (parts or {}).items() if isinstance(b, dict)}
             for uid, parts in (builds or {}).items() if isinstance(parts, dict)}
    with _LOCK:
        s = _seen()
        if complete:
            s[partner] = small
        else:
            s.setdefault(partner, {}).update(small)
        try:
            os.makedirs(os.path.dirname(_seen_path()), exist_ok=True)
            tmp = _seen_path() + ".%s.tmp" % secrets.token_hex(4)
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(s, fh)
            os.replace(tmp, _seen_path())
        except OSError:
            pass


def forget_partner(partner):
    with _LOCK:
        _seen().pop(partner, None)


# ------------------------------------------------------------------ taking a partner's builds
def _busy_here(u):
    if u.kind != "book":
        return False
    try:
        import bookbuild
        job = bookbuild.JOBS.get(os.path.realpath(u.where))
        return bool(job and job.get("state") == "running")
    except Exception:                                   # noqa: BLE001
        return False


def _copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = "%s.%s.tmp" % (dst, secrets.token_hex(4))
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


def _write_part(u, part, files, staged):
    """The partner's files of one part written here, whole: a reader is put in
    place in one rename, so a page never reads half of one."""
    w = u.where
    if u.kind == "book" and part == "reader":
        tok = secrets.token_hex(4)
        new, old = os.path.join(w, ".reader-in-" + tok), os.path.join(w, ".reader-old-" + tok)
        try:
            for inner, sha in files.items():
                dst = os.path.join(new, *inner.split("/")[1:])
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(staged[sha], dst)
            cur = os.path.join(w, "reader")
            if os.path.isdir(cur):
                os.replace(cur, old)
            os.replace(new, cur)
        finally:
            shutil.rmtree(new, ignore_errors=True)
            shutil.rmtree(old, ignore_errors=True)
        return
    for inner, sha in files.items():
        _copy(staged[sha], os.path.join(w, *inner.split("/")))


def take(pull, theirs, holds, only=None):
    """After a pull: the partner's builds that match this computer's sources,
    taken -> ["<uid> <part>", …].  `pull` stages files (syncexchange.Pull)."""
    taken = []
    for uid in sorted(theirs or {}):
        parts = theirs[uid]
        if not isinstance(parts, dict) or syncunits.kind_of(uid) not in PARTS:
            continue
        try:
            import syncexchange
            if only and syncexchange.owner_of(uid) != only:
                continue
            u = syncunits.locate(uid)
        except Exception:                               # noqa: BLE001
            continue
        if not holds(uid) or not os.path.isdir(u.where) or _busy_here(u):
            continue
        cur = source_hash(u)
        if cur is None:
            continue
        mine = read_record(u)
        for part in PARTS[u.kind]:
            b = parts.get(part)
            if not isinstance(b, dict) or b.get("source") != cur:
                continue
            m = mine.get(part)
            if m and m.get("source") == cur and part_files(u, part):
                continue
            files = b.get("files") or {}
            if not files or not all(isinstance(s, str) and _inner_ok(u, part, i) for i, s in files.items()):
                continue
            try:
                staged = pull.stage(files)
            except Exception as e:                      # noqa: BLE001 -- next time
                pull.out.setdefault("failed", {})["%s %s" % (uid, part)] = str(e)
                continue
            if source_hash(u) != cur:                   # changed meanwhile: next time
                continue
            with _LOCK:
                _write_part(u, part, files, staged)
                rec = read_record(u)
                rec[part] = {"source": cur, "at": time.time(), "from": pull.partner}
                _write_record(u, rec)
            taken.append("%s %s" % (uid, part))
    if taken:
        _INVALIDATE()
        for cb in list(ON_ARRIVED):
            try:
                cb(sorted({t.split(" ")[0] for t in taken}))
            except Exception as e:                      # noqa: BLE001
                print("!! sync: a listener of builds failed: %s" % e, flush=True)
    return taken


def after_pull(pull, got, holds, only=None):
    """syncexchange.Pull.run's last step: builds, then drawings."""
    builds = got.get("builds") if isinstance(got.get("builds"), dict) else {}
    _note_seen(pull.partner, builds, complete=only is None)
    out = take(pull, builds, holds, only)
    draws = got.get("drawings") if isinstance(got.get("drawings"), dict) else {}
    out += ["drawing %s" % ck for ck in take_drawings(pull, draws, holds)]
    return out


# ------------------------------------------------------------------ out of date
def stale_parts(uid):
    """The parts of this computer's build of uid made from another source than
    the current one, that no partner is known to hold a build of the current
    one for -> [part, …]."""
    try:
        u = syncunits.locate(uid)
    except KeyError:
        return []
    if u.kind not in PARTS:
        return []
    rec = read_record(u)
    if not rec:
        return []
    cur = None
    out = []
    for part in PARTS[u.kind]:
        r = rec.get(part)
        if r is None or not part_files(u, part):
            continue
        if cur is None:
            cur = source_hash(u)
        if cur is None or r.get("source") == cur:
            continue
        if any((p.get(uid) or {}).get(part) == cur for p in _seen().values()):
            continue                                    # a partner has one of the current source
        out.append(part)
    return out


def is_out_of_date(uid):
    return bool(stale_parts(uid))


def out_of_date(title=None):
    out = []
    for u in _units():
        if not os.path.isfile(_sidecar(u)):
            continue
        try:
            import syncexchange
            if not syncexchange.holds(u.id):
                continue
        except Exception:                               # noqa: BLE001
            pass
        st = stale_parts(u.id)
        if st:
            out.append({"unit": u.id, "title": title(u.id) if title else u.id,
                        "what": [WORDS[p] for p in st]})
    return out


# ------------------------------------------------------------------ drawings (markdown/latex/)
def _latexdraw():
    import latexdraw
    return latexdraw


def _drawing_path(key, name):
    ld = _latexdraw()
    p = ld.paths(key)
    return p["meta"] if name == "json" else p[name]


DRAWING_FILES = ("svg", "pdf", "json", "tex", "log")


def drawings_here():
    """{content key: {"key", "compiler", "files": {svg|pdf|json|tex|log: sha}}}
    of every kept drawing whose content key is known here."""
    try:
        ld = _latexdraw()
    except Exception:                                   # noqa: BLE001 -- no studio: no drawings
        return {}
    out = {}
    for ck, a in ld.aliases().items():
        key = a.get("key")
        p = ld.paths(key)
        if not (os.path.isfile(p["svg"]) and os.path.isfile(p["pdf"]) and os.path.isfile(p["meta"])):
            continue
        files = {}
        for name in DRAWING_FILES:
            f = _drawing_path(key, name)
            if os.path.isfile(f):
                try:
                    files[name] = _filehash(f)
                except OSError:
                    pass
        out[ck] = {"key": key, "compiler": a.get("compiler") or "", "files": files}
    return out


_WANT = {}      # unit id -> (unit hash, {content keys})


def _sources_of(u):
    """The markdown a held document, note or exercise draws from."""
    if u.kind in ("doc", "note"):
        try:
            with open(os.path.join(u.where, "source.md"), encoding="utf-8") as fh:
                return [fh.read()]
        except OSError:
            return []
    if u.kind == "item":
        for inner, p in syncunits.files_of(u).items():
            if inner.startswith("items/") and inner.endswith(".json"):
                try:
                    with open(p, encoding="utf-8") as fh:
                        it = json.load(fh)
                    return [(it.get("markdown") or "") + "\n" + (it.get("footnotes") or "")]
                except (OSError, ValueError, AttributeError):
                    return []
    return []


def wanted_content_keys(holds):
    """The content keys of every LaTeX drawing a source held here names."""
    import synclog
    ld = _latexdraw()
    out = set()
    for w in (syncunits._books, syncunits._library, syncunits._videos, syncunits._decks):
        for u in w():
            if u.kind not in ("doc", "note", "item") or not holds(u.id):
                continue
            row = synclog.get(u.id) or {}
            h = row.get("hash")
            got = _WANT.get(u.id)
            if got is None or got[0] != h or h is None:
                keys = set()
                for md in _sources_of(u):
                    keys |= ld.content_keys(md)
                got = _WANT[u.id] = (h, keys)
            out |= got[1]
    return out


def take_drawings(pull, theirs, holds):
    """A partner's drawings this computer cannot make itself (it lacks the
    drawing's compiler) and has none for, that a source held here names."""
    if not theirs:
        return []
    try:
        ld = _latexdraw()
    except Exception:                                   # noqa: BLE001
        return []
    need = [ck for ck, d in theirs.items()
            if isinstance(d, dict) and ld.KEY_RE.match(ck or "") and ld.KEY_RE.match(d.get("key") or "")
            and ld.by_content(ck) is None and ld.compiler(d.get("compiler") or "") is None]
    if not need:
        return []
    wanted = wanted_content_keys(holds)
    got = []
    for ck in sorted(set(need) & wanted):
        d = theirs[ck]
        files = {n: s for n, s in (d.get("files") or {}).items() if n in DRAWING_FILES and isinstance(s, str)}
        if not all(n in files for n in ("svg", "pdf", "json")):
            continue
        try:
            staged = pull.stage(files)
        except Exception as e:                          # noqa: BLE001
            pull.out.setdefault("failed", {})["drawing %s" % ck[:12]] = str(e)
            continue
        put_drawing(ck, d["key"], d.get("compiler") or "", {n: staged[files[n]] for n in files})
        got.append(ck)
    if got:
        _INVALIDATE()
    return got


def put_drawing(ck, key, compiler_name, files):
    """A drawing another computer made, written here from `files` ({svg|pdf|
    json|tex|log: a local path}) and filed by its content key -> True.  The
    facts (json) go last, so a drawing is never found half written.  Also
    what a lent "latex-draw" job's result is written by (lib/syncjobs.py)."""
    ld = _latexdraw()
    if not (ld.KEY_RE.match(ck or "") and ld.KEY_RE.match(key or "")):
        return False
    files = {n: p for n, p in (files or {}).items() if n in DRAWING_FILES and p and os.path.isfile(p)}
    if not all(n in files for n in ("svg", "pdf", "json")):
        return False
    for name in sorted(files, key=lambda n: n == "json"):
        _copy(files[name], _drawing_path(key, name))
    ld.arrived(ck, key, compiler_name or "")
    _INVALIDATE()
    return True
