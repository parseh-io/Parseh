# SPDX-License-Identifier: GPL-3.0-or-later
"""store — the document library on disk.

Layout:  library/<folder>/<id>/source.md   the markdown source (authoritative)
         library/<folder>/<id>/meta.json   title, tags, timestamps, build info
         library/<folder>/<id>/build/      xelatex working dir (main.tex/.pdf)
         library/_prompt.md                the custom LLM prompt of before a0.4.2, moved
                                           to the person's own prompts (move_prompt)

`<folder>` is the target language's folder from the registry (persian,
japanese, ...): a document is filed by its front matter's `target:` and
moved when a save changes it (docs/languages.md, 2 and 5).  A document
directly under library/ is from before languages were declared: it is
still read, as Persian, and reported once with a note to move it.

Ids are slug-of-title plus a random suffix, safe for URLs and paths, and
unique across the folders (the suffix is random, and _doc_dir looks
through every folder).
"""
import bisect
import hashlib
import io
import json
import math
import os
import posixpath
import re
import shutil
import sys
import tempfile
import threading
import time
import unicodedata
import uuid
import zipfile
from pathlib import Path

import audiofile
import clips          # lib/, as audiofile: the tray's decode check (holds_sound)
import htmlgen
import mdparser
import latexthemes  # noqa: E402  (lib/, as mdparser has it)
import prompts      # noqa: E402  the prompts a person wrote: the studio's one custom prompt is one
import languages
from texgen import set_target, cur_lang, is_latin_target, parse_mark_fields, clip_window
from texgen import (LEGACY_UID_RE, doc_name_key, escape_doc_name, find_doclinks,
                    unescape_doc_name, prepare_doc_index, lookup_doclink,
                    resolve_doclink)
from segcolour import (Piece as ColourPiece, find_runs as segmented_runs,
                       parse_at as parse_segmented, parse_marks,
                       normalise_colour, recolour_pieces,
                       serialize as serialize_colours, flatten as flatten_colours)

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "library"
# THE SHAPE OF A DOCUMENT ON THE DISK -- the layout above, source.md and
# meta.json -- as a number (lib/version.py FORMATS).  The notes written into
# a book or a video are documents of this same shape (notes.py), so the one
# number is theirs too; the files carry none.  RAISE IT when the shape
# changes so that the Parseh before this one would read a document wrong; a
# key an older reader ignores is not such a change.
LIBRARY_FORMAT = 2

# THE CLIP TRAY.  The book reader and the video player cut recordings and
# pictures into one flat folder at the toolbox's root (lib/clips.py), under
# names unique across the toolbox, so that a card's markdown naming
# `audio/<name>` can be pasted anywhere.  A document that names one it does
# not hold takes it from here (adopt_media).
CLIPS_DIR = ROOT.parent / "clips"


def set_clips_dir(path):
    """Point the tray elsewhere (the tests use a temporary one)."""
    global CLIPS_DIR
    CLIPS_DIR = Path(path)

# WHICH LIBRARY THIS REQUEST IS ABOUT.
#
# The studio has one library, `LIB`, and everything below used to read it
# directly.  It now serves a second kind: the notes that sit beside a book or
# a video, in that content's own `markdown/` directory.  They are studio
# documents in every respect -- the same store, the same editor, the same
# renderer -- and the only thing that differs is where they live, so the only
# thing that may differ is this.
#
# Held per THREAD, like texgen's DOC_INDEX and for the same reason: the
# server is a ThreadingHTTPServer, one request per thread, and two requests
# about two different books must not be able to read each other's notes.  A
# thread that never sets one gets the studio's own library, so the studio,
# the command line and every test go on working with no idea this exists.
_HERE = threading.local()


def lib():
    """The library this thread is working in."""
    return getattr(_HERE, "root", None) or LIB


def use_library(root):
    """Point this thread at another library for the rest of the request, and
    give back what it was so a caller can put it back."""
    was = getattr(_HERE, "root", None)
    _HERE.root = Path(root) if root else None
    return was
ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,80}$")

FENCE_RE = re.compile(r"```(?:markdown|md)?[ \t]*\n(.*?)\n[ \t]*```",
                      re.S | re.I)
# A FENCE OF FOUR BACKTICKS OR MORE, closed by a line of as many: the envelope the studio's prompt asks
# for when a chatbot cannot make a file.  It may hold a fence of three, which FENCE_RE would take for
# its end, cutting the document off there without a word.
LONG_FENCE_RE = re.compile(r"^[ \t]*(`{4,})(?:markdown|md)?[ \t]*\n(.*?)\n[ \t]*\1`*[ \t]*$",
                           re.S | re.I | re.M)

# C0 control chars are never meaningful in this markdown dialect, and two
# of them (\x00, \x01) are used internally as freeze/bold sentinels in
# htmlgen.inline — an untrusted document containing them literally would
# crash the renderer.  Strip all C0 except tab/newline on every ingest.
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class StoreError(Exception):
    """Storage-layer failure (e.g. corrupt meta.json).  Distinct from
    json.JSONDecodeError so the HTTP layer maps it to 500, not to the
    'bad JSON request body' 400."""


def _strip_controls(text):
    return _CTRL_RE.sub("", text.replace("\r\n", "\n"))


# Per-document lock guarding every read-modify-write of that document's
# meta.json / source.md.  Short-held (never across a build).
_DOC_LOCKS = {}
_DOC_LOCKS_GUARD = threading.Lock()


def _meta_lock(doc_id):
    with _DOC_LOCKS_GUARD:
        return _DOC_LOCKS.setdefault(doc_id, threading.RLock())


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _slug(title):
    # folded first so Turkish's dotless ı becomes i instead of being
    # dropped as un-ASCII: "Işıklar" is isiklar, not klar.  For every other
    # language the fold is what .lower() did anyway.
    s = unicodedata.normalize("NFKD", languages.fold(title or ""))
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40]
    return s or "doc"


def extract_markdown(text):
    """Pull the exlex markdown out of a raw LLM answer.

    The dialect itself never contains code fences, so if the pasted
    text has fenced blocks, the longest one is the document (prefer
    fences that start with front matter).  Otherwise use the text as-is.
    A fence of four backticks or more (what the prompt asks for) is the
    envelope whatever fences of three it holds.
    """
    text = text.replace("\r\n", "\n").strip()
    fences = ([m.group(2) for m in LONG_FENCE_RE.finditer(text)] or FENCE_RE.findall(text))
    fences = [f for f in fences if f.strip()]
    if fences:
        with_fm = [f for f in fences if f.lstrip().startswith("---")]
        best = max(with_fm or fences, key=len)
        # A fence is the document only when it actually looks like one:
        # front matter, or a heading and a substantial share of the paste.
        # Otherwise the "document" was unfenced prose that merely quotes a
        # snippet — keep the whole text, don't throw it away.
        looks_like_doc = (
            best.lstrip().startswith("---")
            or (re.search(r"(?m)^##?\s", best) and len(best) >= len(text) // 2))
        if looks_like_doc:
            return best.strip() + "\n"
    return text + "\n"


_LEGACY_NOTED = set()


def _doc_dir(doc_id):
    """The directory of a document: under its language folder, or --
    for a document written before languages were declared -- directly
    under library/, which still works but is reported once."""
    if not ID_RE.match(doc_id or ""):
        raise KeyError(doc_id)
    for L in languages.LANGS.values():
        d = lib() / L.folder / doc_id
        if d.is_dir():
            return d
    d = lib() / doc_id
    if d.is_dir() and (d / "meta.json").exists():
        if doc_id not in _LEGACY_NOTED:
            _LEGACY_NOTED.add(doc_id)
            print("[store] note: %s sits directly under library/ -- move it "
                  "into library/%s/ (it is read as Persian meanwhile)"
                  % (doc_id, languages.get_or_default(None).folder),
                  file=sys.stderr)
        return d
    raise KeyError(doc_id)


def doc_dir(doc_id):
    """Public name of _doc_dir, for the server's file routes."""
    return _doc_dir(doc_id)


def folder_of(target):
    """The library folder a document of this target lives in."""
    return lib() / languages.get_or_default(target).folder


def _doc_dirs():
    """Every document directory, two levels down (library/<folder>/<id>)
    plus the legacy ones directly under library/, each with a note."""
    if not lib().is_dir():
        return
    for d in sorted(lib().iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        L = languages.by_folder(d.name)
        if L is not None:
            for dd in sorted(d.iterdir()):
                if dd.is_dir() and (dd / "meta.json").exists():
                    yield dd
        elif (d / "meta.json").exists():
            _doc_dir(d.name)         # the legacy note, once
            yield d


def _write_meta(d, meta):
    # atomic: write a sibling temp file then os.replace, so a concurrent
    # reader never sees a half-written file and a crash never corrupts it.
    payload = json.dumps(meta, ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(dir=str(d), prefix=".meta-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, d / "meta.json")
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# A document's `id` is its folder name, and it is built from the title, so
# it reads as though renaming ought to change it.  `uid` is the opaque,
# permanent name instead: assigned once at creation, never rewritten, and
# what a cross-document link stores — so a link keeps pointing at the same
# document however the title, and with it the id, is edited afterwards.
UID_RE = re.compile(r"^[0-9a-f]{12}$")


def _new_uid():
    return uuid.uuid4().hex[:12]


def _read_meta(d):
    try:
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise StoreError("corrupt meta.json in %s: %s" % (d.name, e))
    # documents written before uids existed are given one on first read
    dirty = False
    if not UID_RE.match(str(meta.get("uid", ""))):
        meta["uid"] = _new_uid()
        dirty = True
    # a meta.json from before languages: the source's own front matter
    # says the language (Persian when it says nothing, which is what a
    # document written before `target:` existed does) -- the same answer
    # the page renders with, whichever folder the files were moved into
    # by hand.  The folder and the target must agree, and a mismatch is
    # said once -- the JSON wins for rendering, the folder for where the
    # files are, until the next save moves them.
    if meta.get("target") not in languages.LANGS:
        try:
            fm, _ = mdparser.parse(
                (d / "source.md").read_text(encoding="utf-8"))
            meta["target"] = fm["target"]
        except OSError:
            by_dir = languages.detect_from_path(d)
            meta["target"] = by_dir.code if by_dir else languages.DEFAULT
        dirty = True
    if dirty:
        try:
            _write_meta(d, meta)
        except OSError:
            pass            # read-only library: still usable this session
    by_dir = languages.by_folder(d.parent.name)
    if by_dir is not None and by_dir.code != meta["target"] \
            and d.name not in _LEGACY_NOTED:
        _LEGACY_NOTED.add(d.name)
        print("[store] note: %s is filed under library/%s/ but its "
              "target is %s -- it will move at the next save"
              % (d.name, d.parent.name, meta["target"]), file=sys.stderr)
    return meta


def _source_hash(d):
    try:
        return hashlib.sha1(
            (d / "source.md").read_bytes()).hexdigest()
    except OSError:
        return ""


def _refresh_from_source(meta, markdown):
    fm, blocks = mdparser.parse(markdown)
    meta["title"] = fm.get("title", "") or meta.get("title") or UNTITLED
    meta["subtitle"] = fm.get("subtitle", "")
    meta["note"] = fm.get("note", "")
    meta["lang"] = fm.get("lang", htmlgen.DEFAULT_PROSE)
    meta["target"] = fm["target"]           # a registry code, always
    meta["stats"] = htmlgen.stats(markdown, blocks, target=fm["target"])
    return meta


def create(text, tags=None, renames=None, strict=False, file=None, since=None):
    """A new document from markdown -> its meta.

    Its name is made its own: a title another document of this library has
    already is given " 2", " 3"… (and no title at all is "Untitled"), in the
    front matter as in meta.json, so that a link by that name can only mean
    one document.  That is for everything that makes documents without a
    person to ask -- a new note, an example, a test.

    `strict` is the pages' way instead: a name already taken is refused with
    NameConflict and nothing is made, until `renames` (the dialog's answer,
    plan_names) settles it.  `file` is what the dialog calls the text (an
    upload's file name), and `since` the names_mark of the editor it was
    written in (save)."""
    lib().mkdir(parents=True, exist_ok=True)
    markdown = _strip_controls(extract_markdown(text))
    with _names_lock():
        if strict:
            markdown = latexthemes.catch_up(markdown, since)
        missed = renames_since(since) if strict else []
        if missed:
            markdown = catch_up(markdown, missed)
        fm, _ = mdparser.parse(markdown)
        title = fm.get("title", "")
        if not strict:
            name = _free_name(_name_keys(), title or UNTITLED)
            if name != title:
                markdown = set_title(markdown, name)
            return _create(markdown, tags)
        plan = plan_names([{"ref": NEW_REF, "title": title, "file": file}], renames)
        existing = _retitle(plan["existing"])
        rename_links(existing)
        final = plan["incoming"][NEW_REF]
        markdown = _named_as(markdown, title, final,
                             {doc_name_key(title): final} if title else {}, existing)
        return _create(markdown, tags)


def _create(markdown, tags):
    """create(), the name already settled by the caller (under _names_lock)."""
    fm, _ = mdparser.parse(markdown)
    doc_id = _slug(fm.get("title", "")) + "-" + uuid.uuid4().hex[:6]
    d = folder_of(fm["target"]) / doc_id
    d.mkdir(parents=True)
    (d / "source.md").write_text(markdown, encoding="utf-8")
    meta = {
        "id": doc_id,
        "uid": _new_uid(),          # permanent; never rewritten after this
        # languages.lower, not .lower(): İ lower-cases to i plus a
        # combining dot everywhere, and the tag would be stored with a
        # character nobody can type back.  ı is left alone -- this is
        # what gets displayed, so nothing may be folded away here.
        "tags": sorted(set(languages.lower(t.strip())
                           for t in (tags or []) if t.strip())),
        "created": _now(),
        "updated": _now(),
        "build": {"status": "none"},
    }
    _refresh_from_source(meta, markdown)
    _write_meta(d, meta)
    return meta


def create_exact(markdown, tags=None):
    """A document made of `markdown` EXACTLY as it is -> its meta.

    The library's own way in (create) is for text that comes from somewhere
    else and has to become a document of this library: it unwraps a fenced
    answer, gives a file with no header a title, and renames a title another
    document has.  A file the person opened from elsewhere on the computer
    (openfile.py) is none of that: it is theirs, it is written back to where
    it came from, and nothing may be added to it, taken out of it or renamed on
    the way.  So this writes the text as given -- the caller has settled its
    line ends and its control characters -- and builds the record from it.

    The name is not made unique either: the library it is made in is a library
    of this one document."""
    lib().mkdir(parents=True, exist_ok=True)
    with _names_lock():
        return _create(markdown, tags)


def get(doc_id):
    d = _doc_dir(doc_id)
    meta = _read_meta(d)
    markdown = (d / "source.md").read_text(encoding="utf-8")
    return meta, markdown


def save_markdown(doc_id, markdown):
    """save(), for the callers that want only the meta."""
    return save(doc_id, markdown)[0]


def save(doc_id, markdown, renames=None, since=None):
    """A document's text saved -> (meta, the markdown as written).

    A save whose title differs from the stored one RENAMES the document, and
    a rename is followed like Obsidian follows one: every link in this
    library that named the document by its old name is rewritten to the new
    one (rename_links), its label kept -- its own links to itself included,
    which is why what is written can differ from what was given, and why
    the answer says what was written.  A title changed only in case or in
    spacing is a rename too: a link always spells the name as it is.

    A new title another document of the library has already is refused
    with NameConflict, and nothing is written, until `renames` (what the
    name-conflict dialog answered, plan_names) settles it: the other
    document renamed, this one, or both.

    `since` is the editor's names_mark: the renames made in the library
    after it are followed in the text first (catch_up), so an editor left
    open cannot put back a name a rename elsewhere took away."""
    markdown = _strip_controls(markdown)
    with _names_lock():
        old = _read_meta(_doc_dir(doc_id)).get("title") or ""
        markdown = latexthemes.catch_up(markdown, since)
        missed = renames_since(since)
        if missed:
            markdown = catch_up(markdown, missed, old)
        typed = mdparser.parse(markdown)[0].get("title") or old
        final, existing = typed, {}
        if renames or doc_name_key(typed) != doc_name_key(old):
            plan = plan_names([{"ref": doc_id, "title": typed}], renames,
                              replacing={doc_id})
            final = plan["incoming"][doc_id]
            existing = _retitle(plan["existing"])
        if final != typed:
            markdown = set_title(markdown, final)
        follow = dict(existing)
        if old and final != old:
            follow[doc_name_key(old)] = final
        if follow:
            markdown = rewrite_links(markdown, lambda label, name:
                                     follow.get(doc_name_key(name)))[0]
        meta = _save_text(doc_id, markdown)
        if follow:
            rename_links(follow, skip={doc_id})
    return meta, markdown


def _save_text(doc_id, markdown):
    d = _doc_dir(doc_id)
    with _meta_lock(doc_id):
        meta = _read_meta(d)
        try:
            unchanged = (d / "source.md").read_text(encoding="utf-8") == markdown
        except OSError:
            unchanged = False
        if not unchanged:
            # A save that changes nothing must not invalidate a good PDF:
            # otherwise a re-save, or clearing a colour that was never
            # set, leaves the build falsely flagged "source changed".
            (d / "source.md").write_text(markdown, encoding="utf-8")
            meta["updated"] = _now()
            _refresh_from_source(meta, markdown)
            if meta.get("build", {}).get("status") == "ok":
                meta["build"]["stale"] = True
            _write_meta(d, meta)
        # a changed `target:` moves the document into its language's
        # folder -- one rename inside the same library, under the lock,
        # so the id stays and every link to it keeps working.  The same
        # rename files a document found under the wrong folder (the
        # "will move at the next save" of _read_meta), even when the
        # save changed no text.
        want = folder_of(meta["target"]) / doc_id
        if want != d:
            want.parent.mkdir(parents=True, exist_ok=True)
            if want.exists():
                raise StoreError("cannot move %s to library/%s/: a document "
                                 "with that id is already there"
                                 % (doc_id, want.parent.name))
            os.rename(d, want)
    return meta


def update_meta(doc_id, patch):
    """Tags, and the subtitle and the note of meta.json.  A title is the
    document's name, and a new one is a rename like any other: written into
    the front matter and followed by every link to it (save)."""
    d = _doc_dir(doc_id)
    if "tags" in patch and not isinstance(patch["tags"], list):
        raise StoreError("tags must be a list")
    if "title" in patch:
        title = _header_value(patch["title"])
        if not title:
            raise StoreError("a document needs a name")
        save(doc_id, set_title(get(doc_id)[1], title))
        patch = dict(patch)
        del patch["title"]
    with _meta_lock(doc_id):
        meta = _read_meta(d)
        if "tags" in patch:
            meta["tags"] = sorted(set(
                languages.lower(str(t).strip())
                for t in patch["tags"] if str(t).strip()))
        for k in ("subtitle", "note"):
            if k in patch:
                meta[k] = str(patch[k])
        meta["updated"] = _now()
        _write_meta(d, meta)
    return meta


def _blank_m(m):
    """Regex callback: blank a match, preserving newlines/offsets."""
    return re.sub(r"[^\n]", " ", m.group(0))


# A line break inside a paragraph, not the blank line (in a box, the `>`
# alone) that ends one: the renderers read a paragraph's lines as one text,
# and nothing they match runs on into the next paragraph.
_IN_PARA_NL = r"\n(?![ \t>]*(?:\n|$))"

# `^[a note]` as the renderers find it (texgen.FN_INLINE_RE: a mark or a
# link inside it included, so `^[see [کتاب]{teal}]` is ONE note), over the
# line breaks of its paragraph but never past its end.
_FN_INLINE_SRC_RE = re.compile(
    r"\^\[(?:[^\[\]\n]|%s|\[(?:[^\[\]\n]|%s)*\](?:\{[^{}]*\}|\([^()\s]*\))?)*\]"
    % (_IN_PARA_NL, _IN_PARA_NL))


def _blank_footnotes(src):
    """Blank what the page shows only inside a note, preserving offsets.

    A note's body is drawn twice (the cloud and the list at the end) and
    offers nothing to the page's hover editors, so the searches for the
    n-th word or block they name must not count it.  A definition is
    blanked where the parser reads one -- its indented lines going on
    under it, and one inside a box, included -- and an inline note as the
    renderers match it, a mark in it and all: blanked only up to its first
    inner bracket, it left the words after that bracket counted, and the
    colour meant for a word further down landed on one in the note."""
    fm, _ = mdparser.parse(src)
    spans = fm.get("_footnote_lines") or ()
    if spans:
        lines = src.split("\n")
        for first, last in spans:
            for k in range(first, last + 1):
                lines[k] = " " * len(lines[k])
        src = "\n".join(lines)
    return _FN_INLINE_SRC_RE.sub(_blank_m, src)


def _blank_cards(src):
    """Blank what a flashcard draws as blocks (mdparser.card_spans),
    preserving offsets: the page offers no word or block there to its
    editors, so the searches that find the n-th one must not count it."""
    spans = mdparser.card_spans(src)
    if not spans:
        return src
    lines = src.split("\n")
    for n, col in spans:
        lines[n] = lines[n][:col] + " " * (len(lines[n]) - col)
    return "\n".join(lines)


def _norm_rtl(s):
    """Content comparison key for RTL regions: whitespace collapsed and
    the spacing around ⏎ ignored -- the key the page counts target blocks
    under, too (htmlgen.tl_key)."""
    return htmlgen.tl_key(s)


def _target_of(src):
    """Set the current language from a markdown buffer's own front matter
    (every rewriter starts here: the regexes it uses are the language's)."""
    fm, _ = mdparser.parse(src)
    return set_target(fm["target"])


def _tl_marker(font=None, bg=None, vertical=False, height=None):
    """The generic marker, `{tl …}`.  Persian documents used to get
    `{fa}`; `{tl}` is written for every language now, and `{fa}` stays
    readable (docs/languages.md, 5)."""
    from texgen import TL_HEIGHT_DEFAULT
    parts = ["tl"]
    if font:
        parts.append("font=%s" % font)
    if bg:
        parts.append("bg=%s" % bg)
    if vertical:
        parts.append("vertical")
        if height and int(height) != TL_HEIGHT_DEFAULT:
            parts.append("height=%d" % int(height))
    return "{%s}" % " ".join(parts)


_rtl_marker = _tl_marker


def _tl_block_text(lines, font=None, bg=None, vertical=False, height=None):
    """Overlay lines -> markdown: single line stays inline-sized,
    several lines become the multiline form, joined by forced breaks:
        [
        امروز هوا آفتابی است.⏎
        به پارک رفتیم
        ]{tl font=nastaliq bg=quote}
    Styling attributes are written only when set.
    """
    marker = _tl_marker(font, bg, vertical, height)
    if len(lines) == 1:
        return "[%s]%s" % (lines[0], marker)
    return "[\n" + "⏎\n".join(lines) + "\n]" + marker


_rtl_block_text = _tl_block_text


def tl_edit_markdown(src, kind, content, occurrence, new_lines,
                     font=None, bg=None, vertical=False, height=None):
    """Pure rewrite for the target-text overlay editor.

    Replaces the `occurrence`-th target-language region whose
    (whitespace-normalised) content equals `content` with the new lines.
    `kind` is "mark" for an explicit `[…]{tl}` block, "auto" for a
    Latin-free paragraph rendered as a block without markup.  Line
    breaks typed in the overlay become ⏎; `font`/`bg`/`vertical`/`height`
    write the optional styling attributes -- `font` must be the
    language's alternate face, `vertical` is only for the languages that
    can be set vertically.
    """
    from texgen import RTL_BG, TL_HEIGHT_MIN, TL_HEIGHT_MAX
    L = _target_of(src)
    alt_key = L.fonts.get("alt_key")
    if font not in (None, "") and font != alt_key:
        raise StoreError("unknown font %r for %s" % (font, L.name))
    if bg not in (None, "") and bg not in RTL_BG:
        raise StoreError("unknown background %r" % bg)
    if vertical and not L.vertical:
        raise StoreError("%s cannot be set vertically" % L.name)
    font, bg = font or None, bg or None
    vertical = bool(vertical)
    if height not in (None, ""):
        try:
            height = max(TL_HEIGHT_MIN, min(TL_HEIGHT_MAX, int(height)))
        except (TypeError, ValueError):
            raise StoreError("bad height %r" % height)
    else:
        height = None
    # only ASCII whitespace is trimmed for a language without word separators:
    # a Japanese line may begin with an ideographic space (U+3000), the indent
    # of a verse or a paragraph, and str.strip would eat it on every round trip
    trim = (lambda t: t.strip(" \t")) if L.word_sep == "" else str.strip
    lines = [trim(re.sub(r"[\[\]]", "", l)) for l in (new_lines or [])]
    lines = [l for l in lines if l]
    if not lines:
        raise StoreError("the block cannot be empty")
    target = _norm_rtl(content)

    if kind == "mark":
        hits = [t for t in _tl_marks(src) if _norm_rtl(t[2]) == target]
        if occurrence < 0 or occurrence >= len(hits):
            raise StoreError("that block is no longer in the source")
        spread = hits[occurrence][3]
        if spread is not None:
            # a piece of a mark holding a blank: the mark is written out
            # spread over its pieces (the page is the same), and the piece
            # is a mark of its own to replace
            from texgen import spread_slots
            src = src[:spread.start()] + spread_slots(spread.group(0)) + src[spread.end():]
            hits = [t for t in _tl_marks(src) if _norm_rtl(t[2]) == target]
        s, e = hits[occurrence][:2]
        return src[:s] + _tl_block_text(lines, font, bg, vertical, height) + src[e:]

    # kind == "auto": the paragraph, as the parser groups it
    found = [(first, last + 1) for first, last, text in _tl_auto_paragraphs(src)
             if _norm_rtl(text) == target]
    if occurrence < 0 or occurrence >= len(found):
        raise StoreError("that paragraph is no longer in the source")
    i, j = found[occurrence]
    olines = src.split("\n")
    prefix = re.match(r"^[ \t]*(?:>[ \t]?)*", olines[i]).group(0)
    if font or bg or vertical or any(re.search(r"[A-Za-z]", l) for l in lines):
        # styling needs the explicit mark, and so does Latin content —
        # either way the paragraph is wrapped as [ … ]{tl …}
        new_text = _tl_block_text(lines, font, bg, vertical, height)
    else:
        new_text = "⏎\n".join(lines) if len(lines) > 1 else lines[0]
    new_lines_out = [prefix + l for l in new_text.split("\n")]
    return "\n".join(olines[:i] + new_lines_out + olines[j:])


def _tl_auto_paragraphs(src):
    """The paragraphs the page draws as a target-language block with no
    mark (data-tl-kind="auto"), as (first line, last line, text): a
    paragraph of the script with no Latin letter that is not a display
    line (htmlgen.render_blocks), grouped as the parser groups it."""
    from texgen import tl_re
    out = []
    for b, base in _walk_blocks(mdparser.parse(src)[1]):
        if (b["type"] == "para" and _opaque_para(b["text"])
                and not tl_re().fullmatch(b["text"].strip())):
            out.append((base + b["_line"], base + b["_end_line"], b["text"]))
    return out


def _tl_marks(src):
    """The `[…]{tl}` marks the page offers its target-text overlay
    (data-tl-kind="mark"), in the order of the source, as (start, end,
    content, spread): the span of the whole mark, what is inside it, and
    -- for a piece of a mark holding a blank in an exercise's field, whose
    span is the piece's text -- that mark (a _slotted_marks match), else
    None.

    For a script language, every mark the page draws as one: not one in a
    note or on a card (drawn there, but not offered), in a part of an
    exercise the page does not draw, as a lemma's headword (drawn as a
    run) or struck through with ✗ (drawn as a run in red); a mark wrapped
    over the lines of its paragraph is found as the page reads it.  For a
    Latin-script target, whose inline mark is a run, only a paragraph that
    is one mark."""
    from texgen import tl_re, UNGRAM_MARK_RE
    TL_RE = tl_re()
    blocks = mdparser.parse(src)[1]
    if is_latin_target():
        starts, out = _line_starts(src), []
        for b, base in _walk_blocks(blocks):
            whole = b["type"] == "para" and TL_RE.fullmatch(b["text"].strip())
            if not whole:
                continue
            last = base + b["_end_line"]
            end = starts[last + 1] - 1 if last + 1 < len(starts) else len(src)
            m = TL_RE.search(src, starts[base + b["_line"]], end)
            if m:
                out.append((m.start(), m.end(), whole.group(1), None))
        return out
    masked = _blank_lines(_blank_footnotes(_blank_cards(src)), _undrawn_lines(blocks))
    masked = _blank_spans(masked, _lemma_heads(src, blocks)
                          + [m.span() for m in
                             UNGRAM_MARK_RE.finditer(masked.replace("❌", "✗"))])
    flat, where = _flatten(masked, _joined_lines(blocks))
    out = [(where[m.start()], where[m.end() - 1] + 1, m.group(1), None)
           for m in TL_RE.finditer(flat)]
    out += [(s, e, masked[s:e], sm) for sm in _slotted_marks(masked, blocks)
            for s, e in _slotted_pieces(sm)]
    return sorted(out, key=lambda t: t[0])


def rtl_edit_markdown(src, kind, content, occurrence, new_lines,
                      font=None, bg=None):
    """The old name of tl_edit_markdown."""
    return tl_edit_markdown(src, kind, content, occurrence, new_lines,
                            font=font, bg=bg)


def _la_marker(width, offset, align, bg):
    parts = ["la"]
    if align != "left":
        parts.append("align=%s" % align)
    if bg:
        parts.append("bg=%s" % bg)
    if width != 100:
        parts.append("width=%d" % width)
    if offset != 0:
        parts.append("offset=%d" % offset)
    return "{%s}" % " ".join(parts)


def la_layout_markdown(src, content, occurrence, width, offset, align, bg):
    """Pure rewrite for the Latin-block layout panel: replace the attr
    marker of the `occurrence`-th `[…]{la}` block whose content matches,
    leaving the bracketed content byte-for-byte untouched."""
    from texgen import LA_RE, RTL_BG
    _target_of(src)
    if align not in ("left", "center", "right"):
        raise StoreError("bad align %r" % align)
    if bg not in (None, "") and bg not in RTL_BG:
        raise StoreError("unknown background %r" % bg)
    bg = bg or None
    width = max(10, min(100, int(width)))
    offset = max(-100, min(100, int(offset)))
    target = _norm_rtl(content)

    # Locate the block with the parser's own paragraphs, on the RAW source
    # (content may contain footnotes — nothing gets blanked): a footnote's
    # definition is none, and neither is a list item's indented line, so a
    # `{la}` written in either can never be picked up; nor can one on a
    # card, whose fields the main parse does not read as paragraphs.
    olines = src.split("\n")
    found = []
    for b, base in _walk_blocks(mdparser.parse(src)[1]):
        if b["type"] != "para":
            continue
        m = LA_RE.fullmatch(b["text"].strip())
        if m and _norm_rtl(m.group(1)) == target:
            found.append((base + b["_line"], base + b["_end_line"] + 1))
    if occurrence < 0 or occurrence >= len(found):
        raise StoreError("that Latin block is no longer in the source")
    i, j = found[occurrence]
    # only the trailing marker changes; every content byte stays put
    marker_re = re.compile(r"\]\{\s*(?:la|ltr)\b[^{}]*\}\s*$")
    if not marker_re.search(olines[j - 1]):
        raise StoreError("malformed Latin block")
    olines[j - 1] = marker_re.sub(
        "]" + _la_marker(width, offset, align, bg), olines[j - 1])
    return "\n".join(olines)


def set_la_layout(doc_id, content, occurrence, width, offset, align, bg):
    d = _doc_dir(doc_id)
    with _meta_lock(doc_id):
        src = (d / "source.md").read_text(encoding="utf-8")
        markdown = la_layout_markdown(src, content, occurrence,
                                      width, offset, align, bg)
    return save_markdown(doc_id, markdown)


# A `##` lemma heading, as mdparser reads it: an optional box prefix,
# the headword (bare, or inside a mark), a pipe, then the field that is
# the reading when the language has one.
_LEMMA_HEAD_RE = re.compile(
    r"(?m)^(?P<pre>[ \t]*(?:>[ \t]?)*##[ \t]+)(?P<head>[^|\n]*)\|(?P<kana>[^|\n]*)")


def _blank_lemma_reading(m):
    """Regex callback for _LEMMA_HEAD_RE: blank the reading field of a
    heading that is a lemma (its headword starts with the script)."""
    head = m.group("head").strip()
    mw = mdparser._HEAD_MARK.fullmatch(head)
    if mw:
        head = mw.group(1).strip()
    if not cur_lang().has_script(head[:1]):
        return m.group(0)
    return (m.group("pre") + m.group("head") + "|"
            + re.sub(r"[^\n]", " ", m.group("kana")))


def _blank_mark_fields(m):
    """Regex callback for TRANSLIT_RE: blank the key:value fields of a
    mark (`[漢字]{teal kana:かんじ translit:kanji}` -> the braces keep
    only their colour), preserving offsets."""
    s, e = m.start(3) - m.start(), m.end(3) - m.start()
    whole = m.group(0)
    return whole[:s] + re.sub(r"[^\n]", " ", whole[s:e]) + whole[e:]


def _walk_blocks(blocks, base=0):
    """Every block of a parse, with the source line its box starts on: a
    box's blocks count their lines from the box's first (mdparser)."""
    for b in blocks:
        yield b, base
        if b["type"] == "box":
            yield from _walk_blocks(b["blocks"], base + b["_line"])
        elif b["type"] == "exercise" and b.get("steps"):
            # a follow-up's steps are exercises of their own, on lines of the same document
            yield from _walk_blocks(b["steps"], base)


def _line_starts(src):
    starts = [0]
    for m in re.finditer("\n", src):
        starts.append(m.end())
    return starts


def _field_spans(src, blocks):
    """Where the fields of every exercise are, as (start, end) offsets of
    their lines: the text mdparser.parse_exercise reads each field from
    (a `key: |` block's lines included), and nothing of its rows."""
    starts = _line_starts(src)
    out = []
    for b, base in _walk_blocks(blocks):
        if b["type"] != "exercise":
            continue
        for first, last in (b.get("_field_lines") or {}).values():
            first, last = base + first, base + last
            if first >= len(starts) or last < first:
                continue
            end = starts[last + 1] - 1 if last + 1 < len(starts) else len(src)
            out.append((starts[first], end))
    return sorted(out)


def _slotted_marks(src, blocks):
    """Every target-language mark holding a blank, `[من [[x]] بابک]{tl}`,
    written in an exercise's field: the matches of texgen's own regex.  The
    parser spreads each over its pieces (texgen.spread_slots), and the page
    draws those pieces -- a run each for a Latin-script target, an opaque
    `{tl}` stretch each for any other -- but only in a field: anywhere else
    the mark is not one, and is drawn as the text it is."""
    from texgen import _slotted_re, SLOT_RE
    rx = _slotted_re()
    out = []
    for s, e in _field_spans(src, blocks):
        out.extend(m for m in rx.finditer(src, s, e) if SLOT_RE.search(m.group(1)))
    return out


def _slotted_pieces(m):
    """The pieces a slotted mark (a _slotted_marks match) is spread into,
    as (start, end) offsets of each one's text, trimmed as spread_slots
    trims it: the page's run is that text exactly."""
    from texgen import SLOT_SPLIT_RE
    pos, out = m.start(1), []
    for piece in SLOT_SPLIT_RE.split(m.group(1)):
        core = piece.strip()
        if core and not SLOT_SPLIT_RE.fullmatch(piece):
            s = pos + len(piece) - len(piece.lstrip())
            out.append((s, s + len(core)))
        pos += len(piece)
    return out


def _opaque_para(text):
    """Does the page draw this paragraph as one block no word of which is
    offered (htmlgen.render_blocks, in the same order): a whole-paragraph
    `[…]{tl}`, or a paragraph of the target script with no Latin letter.
    Not a `{la}` block, whose inside is ordinary markdown; not a display
    line, which is one run and is offered as one."""
    from texgen import LA_RE, tl_re, is_fa_only_paragraph, _is_pure_fa_paragraph
    t = text.strip()
    if LA_RE.fullmatch(t) or _is_pure_fa_paragraph(t):
        return False
    return bool(tl_re().fullmatch(t) or is_fa_only_paragraph(t))


def _undrawn_lines(blocks):
    """The lines of every exercise the page does not draw the text of
    (htmlgen.exercise_drawn): its fences, a comment, a field nothing reads,
    and the rows, sentence and card of one that shows its errors instead."""
    out = []
    for b, base in _walk_blocks(blocks):
        if b["type"] != "exercise":
            continue
        keys, rows = htmlgen.exercise_drawn(b)
        shown = set(b.get("_row_lines") or ()) if rows else set()
        for key, (first, last) in (b.get("_field_lines") or {}).items():
            if key in keys:
                shown.update(range(first, last + 1))
        # the lines of a follow-up's steps are said by the steps (they are walked as exercises too)
        for step in b.get("steps") or ():
            shown.update(range(step["_line"], step.get("_end_line", step["_line"]) + 1))
        out.extend(base + k for k in range(b["_line"], b.get("_end_line", b["_line"]) + 1)
                   if k not in shown)
    return out


def _lemma_heads(src, blocks):
    """The (start, end) offsets of every lemma heading's headword, mark
    and all (`## [کتاب]{tl} | …`): the page draws it as a run of its own,
    escaped, whatever mark it is written in (htmlgen.render_blocks)."""
    starts = _line_starts(src)
    out = []
    for b, base in _walk_blocks(blocks):
        if b["type"] == "voce" and base + b["_line"] < len(starts):
            m = _LEMMA_HEAD_RE.match(src, starts[base + b["_line"]])
            if m:
                out.append(m.span("head"))
    return out


def _blank_lines(src, numbers):
    lines = src.split("\n")
    for k in numbers:
        lines[k] = " " * len(lines[k])
    return "\n".join(lines)


def _blank_spans(src, spans):
    """`src` with every (start, end) span blanked, its line breaks kept."""
    chars = list(src)
    for s, e in spans:
        for k in range(s, e):
            if chars[k] != "\n":
                chars[k] = " "
    return "".join(chars)


def _mask_uncountable(src, parsed=None):
    """Blank out regions whose runs the word cloud never offers,
    preserving offsets: footnote bodies (rendered twice — cloud + end
    list), ✗-marked runs (their red is not overridable), `[…]{tl}`
    stretches, and auto-block paragraphs (both rendered opaquely).
    Keeping this in step with the renderer's `countable` rule is what
    makes occurrence indices agree between page and source.

    The current language must be set (the caller's `_target_of`).  For a
    Latin-script target the inline `[…]{tl}` IS a run, so only the
    whole-paragraph blocks are masked there.  For a language with a
    reading, the kana is text of the script that is never a run: the
    reading field of a lemma heading is printed as a plain line, and the
    `kana:` of a mark is data for the hover cloud -- both are blanked.

    So is the name a `[…](doc:…)` link points at, in any language: it is
    never on the page, and the title an empty label shows in its place is
    drawn uncounted (htmlgen.inline).

    What the page draws is the parser's to say, and it is asked
    (mdparser.parse, on the text as written; `parsed` is that parse when
    the caller has it already): which lines make a paragraph -- a list
    item going on over an indented line is one item, not a paragraph of
    that line, and a line that is nothing but a `[…]{tl}` mark there is a
    run of the item -- which lines of an exercise are drawn, which
    headings are lemmas, whose headword is a run in whatever mark it
    stands, and which lines are drawn as no words at all: a front-matter
    key that is not a title, a `#` heading that does not become the
    title, a formula."""
    from texgen import tl_re, run_re, TRANSLIT_RE, UNGRAM_MARK_RE
    L = cur_lang()
    TL_RE = tl_re()
    fm, blocks = parsed or mdparser.parse(src)
    hidden = _undrawn_lines(blocks) + list(fm.get("_silent_lines") or ())
    # the paragraphs the page draws as opaque blocks: an auto block of the
    # script (a display line stays offered), a whole-paragraph `[…]{tl}` --
    # for a Latin target the only mark that is not a run
    for b, base in _walk_blocks(blocks):
        if b["type"] == "para" and _opaque_para(b["text"]):
            hidden.extend(range(base + b["_line"], base + b["_end_line"] + 1))
    heads = _lemma_heads(src, blocks)
    slotted = [] if is_latin_target() else _slotted_marks(src, blocks)
    src = _blank_footnotes(_blank_cards(src))
    # every link the page shows, found as it finds them (a label holding a
    # mark included): a name blanked here is one the page never draws
    src = _blank_spans(src, [(link.target_start, link.target_end)
                             for link in find_doclinks(src)])
    if not is_latin_target():
        # every `{tl}` stretch but a lemma's headword; and a mark in a field
        # that holds a blank, whose pieces are `{tl}` stretches on the page
        # however TL_RE reads the whole
        src = _blank_spans(src, [m.span() for m in TL_RE.finditer(src)
                                 if not any(s <= m.start() and m.end() <= e
                                            for s, e in heads)]
                           + [m.span() for m in slotted])
        # ✗ before a run, and before a mark it strips down to one: the
        # renderer reads ❌ as ✗ first, then UNGRAM_MARK_RE (htmlgen.inline)
        src = _blank_spans(src, [m.span() for m in
                                 UNGRAM_MARK_RE.finditer(src.replace("❌", "✗"))])
        src = re.sub(r"[✗❌]" + run_re().pattern, _blank_m, src)
        if L.reading:
            src = _LEMMA_HEAD_RE.sub(_blank_lemma_reading, src)
            src = TRANSLIT_RE.sub(_blank_mark_fields, src)
    else:
        src = re.sub(r"[✗❌]\[[^\[\]]+\]\{[^{}]*\}", _blank_m, src)
    return _blank_lines(src, hidden)


# the attribute grammar of a run mark for a Latin-script target: a
# leading token (`tl`, the code, a colour, or any word) and/or the
# key:value fields -- but never `la`/`ltr`, which make a block
_LATIN_MARK_ATTRS = (r"\s*(?!(?:la|ltr)\b)(?:(?:#[0-9A-Fa-f]{6}|[A-Za-z]+)\b\s*)?"
                     r"(?:(?:translit|kana|reading):[^{}]*?)?\s*\}")


class _Hit:
    """A run found in the source: its span as written there (group 1 and
    group 0 alike, as _run_matches' callers read them) and its text."""
    __slots__ = ("_s", "_e", "_t")

    def __init__(self, s, e, text):
        self._s, self._e, self._t = s, e, text

    def start(self, group=0):
        return self._s

    def end(self, group=0):
        return self._e

    def span(self, group=0):
        return self._s, self._e

    def group(self, group=0):
        return self._t


def _joined_lines(blocks):
    """The line breaks the parser reads as a space, each by the index of
    the line it ends: between two lines of a paragraph, and before a line
    that carries on the list item above it."""
    out = set()
    for b, base in _walk_blocks(blocks):
        if b["type"] == "para":
            out.update(range(base + b["_line"], base + b["_end_line"]))
        elif b["type"] in ("list", "enum"):
            starts = set(b.get("_item_lines") or ())
            out.update(base + k - 1
                       for k in range(b["_line"] + 1, b["_end_line"] + 1)
                       if k not in starts)
    return out


def _flatten(text, joins):
    """`text` as the renderers read it at each joined line break (the
    spaces before the break, the break, and the indentation or box marks
    after it are one space: mdparser strips each line and joins them), and
    for every character of the result the offset it has in `text`."""
    lines = text.split("\n")
    out, where, pos = [], [], 0
    for k, line in enumerate(lines):
        a = (re.match(r"[ \t]*(?:>[ \t]?)*[ \t]*", line).end()
             if k - 1 in joins else 0)
        last = k == len(lines) - 1
        if k in joins and not last:
            b = max(a, len(line.rstrip(" \t\r")))
            out.append(line[a:b] + " ")
            where.extend(range(pos + a, pos + b))
            where.append(pos + len(line))              # the break itself
        else:
            out.append(line[a:] + ("" if last else "\n"))
            where.extend(range(pos + a, pos + len(line) + (0 if last else 1)))
        pos += len(line) + 1
    return "".join(out), where


def _blank_maths(flat, where, src, blocks):
    """`flat` (a _flatten of the masked source) with every `[…]{math}`
    formula blanked as the renderers find it: texgen.MATH_RE, in each
    text they draw inline -- a paragraph, a list item, a heading, a cell
    of a table, a field of a lemma heading -- after a note, a note's
    reference and a `{tl}` mark have been set aside (htmlgen.inline).  The page offers no word
    inside a formula.  A formula starts at its own `[`, so a mark written
    before it -- a colour the source editor has put round a word -- stays out
    of it, on the page and here alike (texgen.MATH_RE says where a formula
    begins; this reads it, and so never disagrees with the page)."""
    from texgen import MATH_RE, FN_REF_RE, tl_re
    probe = FN_REF_RE.sub(_blank_m, flat)
    if is_latin_target():
        probe = tl_re().sub(_blank_m, probe)
    starts = _line_starts(src)
    cells = set()                       # source lines cut at every `|`
    for b, base in _walk_blocks(blocks):
        if b["type"] == "table":
            cells.update(range(base + b["_line"], base + b["_line"] + 2 + len(b["rows"])))
        elif b["type"] == "voce":
            cells.add(base + b["_line"])
    out, pos = list(flat), 0
    for line in probe.split("\n"):
        pieces = [line]
        if line and bisect.bisect_right(starts, where[pos]) - 1 in cells:
            pieces = line.split("|")
        at = pos
        for piece in pieces:
            for m in MATH_RE.finditer(piece):
                for k in range(at + m.start(), at + m.end()):
                    out[k] = " "
            at += len(piece) + 1
        pos += len(line) + 1
    return "".join(out)


def _run_matches(src, text):
    """Every occurrence of `text` as a *maximal* run of the target
    language, in order; group 1 of each match is the run itself.  For a
    script language that is the text with nothing of the script on
    either side (docs/languages.md, 5); for a Latin target it is the
    bracketed content of a run mark -- so the group spans exactly the
    text and the wrapper logic of _remark_markdown sees the `[` before
    and the `]{…}` after it -- and, since the renderers count it as a
    run like any other, the bare headword of a `## bello | …` lemma
    heading (a script language's headword is a run by detection).

    The page's run is a run of the text the parser made, and a paragraph
    or a list item wrapped over several lines is one line to it: a run
    broken over a line break is found whole, as the page shows it, and
    its span runs across the break.  For a Latin target the pieces of a
    mark holding a blank in an exercise's field are runs too, as the page
    draws them (_slotted_marks)."""
    L = cur_lang()
    if not text:
        return []
    parsed = mdparser.parse(src)
    blocks = parsed[1]
    masked = _mask_uncountable(src, parsed)
    seg_nodes = list(segmented_runs(masked))
    # The inner pieces must never be found as independent source runs.
    # Keep offsets stable while the ordinary matcher does its work, then
    # add the complete flattened nodes beside its results.
    if seg_nodes:
        chars = list(masked)
        for node in seg_nodes:
            chars[node.start:node.end] = " " * (node.end - node.start)
        masked = "".join(chars)
    flat, where = _flatten(masked, _joined_lines(blocks))
    flat = _blank_maths(flat, where, src, blocks)

    def hit(m):
        s, e = where[m.start(1)], where[m.end(1) - 1] + 1
        return _Hit(s, e, src[s:e])

    if L.chars:
        fa = L.chars
        sep = re.escape(L.word_sep) if L.word_sep else ""
        pat = r"(?<![%s])%s(%s)(?![%s])%s" % (
            fa, ("(?<![%s]%s)" % (fa, sep)) if sep else "",
            re.escape(text), fa,
            ("(?!%s[%s])" % (sep, fa)) if sep else "")
        hits = [hit(m) for m in re.finditer(pat, flat)]
        hits += [_Hit(n.start, n.end, n.plain_text)
                 for n in seg_nodes if n.plain_text == text]
        return sorted(hits, key=lambda m: m.start())
    marks = re.finditer(r"(?<=\[)(%s)(?=\]\{%s)"
                        % (re.escape(text), _LATIN_MARK_ATTRS), flat)
    heads = re.finditer(r"(?m)^[ \t]*(?:>[ \t]?)*##[ \t]+(%s)[ \t]*\|"
                        % re.escape(text), flat)
    hits = [hit(m) for m in marks] + [hit(m) for m in heads]
    hits += [_Hit(s, e, src[s:e]) for m in _slotted_marks(masked, blocks)
             for s, e in _slotted_pieces(m) if masked[s:e] == text]
    hits += [_Hit(n.start, n.end, n.plain_text)
             for n in seg_nodes if n.plain_text == text]
    return sorted(hits, key=lambda m: m.start(1))


def _enclosing_mark(src, s, e):
    """The content span of the `[…]{…}` mark the run src[s:e] sits inside
    of, when the run is only part of that content (`[速い 車]{kana:…}`
    for Japanese, whose runs stop at a space; `[سلام! دنیا]{teal}` for
    Persian, whose runs stop at punctuation); None otherwise.  Only a
    run mark counts -- no token, a hex or a palette colour: the content
    of a `[...]{la}` paragraph is ordinary markdown whose runs are marked
    one by one, as they always were.  The mark may be wrapped over the
    lines of its paragraph, as the run itself may be."""
    from texgen import HEX_RE, PALETTE
    apart = r"[\[\]]|\n(?=[ \t>]*(?:\n|$))"     # a bracket, a paragraph's end
    i = src.rfind("[", 0, s)
    if i < 0 or re.search(apart, src[i + 1:s]):
        return None
    j = src.find("]", e)
    if j < 0 or re.search(apart, src[e:j]):
        return None
    after = _WRAPPED_RE.match(src, j)
    if not after or (i + 1, j) == (s, e):
        return None
    tok = after.group(1)
    if tok is not None and not (HEX_RE.match(tok) or tok.lower() in PALETTE):
        return None
    return i + 1, j


# a run wrapped as [run]{colour}, [run]{translit:…}, [run]{kana:…} or any
# combination; group 1 is the leading token, group 2 the key:value fields
_WRAPPED_RE = re.compile(
    r"\]\{\s*(?:(#[0-9A-Fa-f]{6}|[A-Za-z]+)\b\s*)?"
    r"((?:(?:translit|kana|reading):[^{}]*?)?)\s*\}")


# "leave this half of the mark exactly as it is" — distinct from None,
# which means "clear it".
_KEEP = object()


def _clean_mark_value(value, what):
    if value is _KEEP or value is None:
        return value
    value = " ".join(str(value).split())
    if not value:
        return None
    if re.search(r"[\[\]{}]", value):
        raise StoreError("a %s cannot contain brackets or braces" % what)
    return value


def _remark_markdown(src, text, occurrence, color=_KEEP, translit=_KEEP,
                     kana=_KEEP):
    """Pure rewrite of the `occurrence`-th run equal to `text` in `src`.

    A run carries one bracket mark holding up to three independent
    things, `[漢字]{teal kana:かんじ translit:kanji}`.  Whichever of
    `color`/`translit`/`kana` is left as _KEEP is carried over from the
    existing mark, so editing one never silently drops the others;
    passing None clears that part, and clearing all unwraps the run back
    to bare text -- except for a Latin-script target, whose run IS the
    mark: there the bare form is `[bello]{tl}`.

    A run that is only part of an ordinary mark's content is edited as the
    mark.  A segmented-colour run is handled as one flattened run above;
    changing its linguistic fields preserves all of its visual pieces.
    """
    from texgen import HEX_RE, PALETTE
    L = _target_of(src)
    latin = is_latin_target()
    if color is not _KEEP and color is not None:
        if HEX_RE.match(color):
            color = "#" + color[1:].upper()
        elif color not in htmlgen.PALETTE:
            raise StoreError("unknown colour %r" % color)
    translit = _clean_mark_value(translit, "transliteration")
    kana = _clean_mark_value(kana, "reading")
    if kana not in (_KEEP, None) and not L.reading:
        raise StoreError("%s has no reading field" % L.name)
    hits = _run_matches(src, text)
    if occurrence < 0 or occurrence >= len(hits):
        raise StoreError("that run is no longer in the source")
    m = hits[occurrence]
    s, e = m.start(1), m.end(1)
    segmented = parse_segmented(src, s)
    if segmented is not None and segmented.end == e:
        marks = dict(segmented.marks)
        if translit is not _KEEP:
            if translit:
                marks["translit"] = translit
            else:
                marks.pop("translit", None)
        if kana is not _KEEP:
            if kana:
                marks["kana"] = kana
            else:
                marks.pop("kana", None)
        pieces = segmented.pieces
        if color is not _KEEP:
            pieces = recolour_pieces(pieces, 0, len(segmented.plain_text), color)
        new = serialize_colours(pieces, marks, latin=latin)
        return src[:s] + new + src[e:]
    # A piece of a mark holding a blank (`[Mi chiamo [[x]] Anna]{tl}` in a
    # fill-in sentence) is marked as the page draws it: the mark is written
    # out spread over its pieces first (texgen.spread_slots, which the
    # parser applies anyway, so the page is the same), and the piece is
    # then a mark of its own like any other.  Spreading moves no run past
    # another, so the occurrence still names it.
    if latin:
        for sm in _slotted_marks(src, mdparser.parse(src)[1]):
            if sm.start() <= s < sm.end():
                from texgen import spread_slots
                src = src[:sm.start()] + spread_slots(sm.group(0)) + src[sm.end():]
                m = _run_matches(src, text)[occurrence]
                s, e = m.start(1), m.end(1)
                break
    whole = _enclosing_mark(src, s, e)
    if whole:
        s, e = whole
    # the run as the source spells it: one wrapped over two lines keeps its
    # line break (and, in a box, the box's mark) inside the new mark
    text = src[s:e]
    had_color, had_translit, had_kana = None, None, None
    after = _WRAPPED_RE.match(src, e)
    if after and s > 0 and src[s - 1] == "[":
        tok, fields = after.group(1), parse_mark_fields(after.group(2))
        # a colour token, a translit/kana, or both — but never a different
        # mark kind whose name merely looks like a colour ({fa}, {la}…);
        # for a Latin target the run marker (`tl`, the code) and any
        # other word are the mark itself, carrying no colour
        if latin:
            tok_ok = True
            if tok is not None and not (HEX_RE.match(tok) or tok.lower() in PALETTE):
                tok = None
        else:
            tok_ok = tok is None or HEX_RE.match(tok) or tok.lower() in PALETTE
        if (tok is not None or fields or latin) and tok_ok:
            s, e = s - 1, after.end()
            had_color = tok
            had_translit = fields.get("translit") or None
            had_kana = fields.get("kana") or None
    color = had_color if color is _KEEP else color
    translit = had_translit if translit is _KEEP else translit
    kana = had_kana if kana is _KEEP else kana
    parts = []
    if color:
        parts.append(color)
    if kana:
        parts.append("kana:" + kana)
    if translit:
        parts.append("translit:" + translit)
    if parts:
        new = "[%s]{%s}" % (text, " ".join(parts))
    elif latin:
        new = "[%s]{tl}" % text
    else:
        new = text
    return src[:s] + new + src[e:]


def recolor_markdown(src, text, occurrence, color):
    """Colour the `occurrence`-th run equal to `text`; keep its translit.

    `color` is a palette name, an arbitrary `#RRGGBB`, or None to clear.
    Shared by the reading view (which saves the file) and the editor
    (which rewrites its unsaved buffer).
    """
    return _remark_markdown(src, text, occurrence, color=color)


_SOURCE_MARK_RE = re.compile(r"\[([^\[\]\n]+)\]\{([^{}\n]+)\}")


def _ordinary_colour_mark(match, latin):
    """The semantic parts of an ordinary run mark, or None."""
    attrs = match.group(2).strip()
    fields_at = re.search(r"(?:^|\s)(?:translit|kana|reading):", attrs)
    head = attrs[:fields_at.start()].strip() if fields_at else attrs
    marks = parse_marks(attrs)
    colour = normalise_colour(head) if head else None
    if colour or marks:
        return colour, marks
    if latin and head and head.lower() not in ("la", "ltr", "math", "latex"):
        return None, {}
    return None


def _word_char(ch):
    cat = unicodedata.category(ch)
    return cat[:1] in ("L", "M", "N") or ch in "'’‌‍-"


def _word_at(src, caret):
    """Half-open Unicode word under/next to a source caret."""
    if not src:
        return None
    p = min(max(0, caret), len(src))
    if p == len(src) or (p < len(src) and not _word_char(src[p])):
        if p and _word_char(src[p - 1]):
            p -= 1
        else:
            return None
    a = p
    while a and _word_char(src[a - 1]):
        a -= 1
    b = p + 1
    while b < len(src) and _word_char(src[b]):
        b += 1
    return a, b


def colour_selection_markdown(src, start, end, colour):
    """Apply a foreground colour to the exact visible editor selection.

    The return value is ``(markdown, caret)``.  Existing ordinary and
    segmented run marks are parsed and serialised canonically; raw text is
    split only at lexical-word edges, so crossing a space cannot manufacture
    one fake word.  Browser code expands the two edges to grapheme boundaries
    before calling this function.
    """
    _target_of(src)
    latin = is_latin_target()
    try:
        start, end = int(start), int(end)
    except (TypeError, ValueError):
        raise StoreError("selection offsets must be integers")
    start, end = max(0, min(start, len(src))), max(0, min(end, len(src)))
    if end < start:
        start, end = end, start
    if colour:
        colour = normalise_colour(str(colour))
        if not colour:
            raise StoreError("unknown colour")
    if start == end:
        node_here = next((n for n in segmented_runs(src)
                          if n.start <= start <= n.end and n.positions), None)
        if node_here:
            start, end = node_here.positions[0], node_here.positions[-1] + 1
        else:
            marked_here = None
            in_mark_syntax = False
            for mark in _SOURCE_MARK_RE.finditer(src):
                parsed = _ordinary_colour_mark(mark, latin)
                if parsed is None:
                    continue
                if mark.start(1) <= start <= mark.end(1):
                    marked_here = (mark.start(1), mark.end(1))
                    break
                if mark.start() <= start <= mark.end():
                    in_mark_syntax = True
            if marked_here:
                start, end = marked_here
            else:
                word = None if in_mark_syntax else _word_at(src, start)
                if not word:
                    raise StoreError("Select text to colour")
                start, end = word

    # An existing segmented word: source positions of its visible code
    # points provide the source/plain mapping without treating markup as text.
    for node in segmented_runs(src):
        if end <= node.start or start >= node.end:
            continue
        picked = [i for i, pos in enumerate(node.positions)
                  if start <= pos < end]
        if start < node.start or end > node.end:
            continue                 # handled with the other crossed units below
        if not picked:
            raise StoreError("Select visible text, not its colour markup")
        pieces = recolour_pieces(node.pieces, min(picked), max(picked) + 1, colour)
        new = serialize_colours(pieces, dict(node.marks), latin=latin)
        out = src[:node.start] + new + src[node.end:]
        return out, node.start + len(new)

    # An ordinary whole-run mark becomes segmented only when the chosen
    # interval needs it.  Its colour and all linguistic fields are retained.
    for mark in _SOURCE_MARK_RE.finditer(src):
        body_a, body_b = mark.start(1), mark.end(1)
        if body_a <= start and end <= body_b:
            parsed = _ordinary_colour_mark(mark, latin)
            if parsed is None:
                break
            base, marks = parsed
            pieces = recolour_pieces((ColourPiece(mark.group(1), base),),
                                     start - body_a, end - body_a, colour)
            new = serialize_colours(pieces, marks, latin=latin)
            out = src[:mark.start()] + new + src[mark.end():]
            return out, mark.start() + len(new)

    chosen = src[start:end]
    # A clean complete word or phrase retains the compact ordinary syntax.
    left_ok = start == 0 or not _word_char(src[start - 1])
    right_ok = end == len(src) or not _word_char(src[end])
    if (colour and chosen and "\n" not in chosen and not re.search(r"[\[\]{}]", chosen)
            and left_ok and right_ok):
        new = "[%s]{%s}" % (chosen, colour)
        out = src[:start] + new + src[end:]
        return out, start + len(new)

    # Partial boundaries, including a selection crossing words: each lexical
    # unit is rewritten independently and only its intersecting interval is
    # coloured.  Spaces and punctuation remain byte-for-byte untouched.
    line_a = src.rfind("\n", 0, start) + 1
    nl = src.find("\n", end)
    line_b = len(src) if nl < 0 else nl
    replacements = []
    occupied = []

    # Semantic nodes intersected by a longer selection are rewritten as
    # units.  Their source markup is occupied so the raw-word pass below
    # cannot mistake colour names or linguistic field names for visible
    # text.  Visible code-point positions retain the exact selected slice.
    for node in segmented_runs(src):
        occupied.append((node.start, node.end))
        picked = [k for k, pos in enumerate(node.positions)
                  if start <= pos < end]
        if not picked:
            continue
        pieces = recolour_pieces(node.pieces, min(picked), max(picked) + 1, colour)
        new = serialize_colours(pieces, dict(node.marks), latin=latin)
        if new != src[node.start:node.end]:
            replacements.append((node.start, node.end, new))

    for mark in _SOURCE_MARK_RE.finditer(src):
        if any(a <= mark.start() and mark.end() <= b for a, b in occupied):
            continue                 # an inner piece of a segmented node
        parsed = _ordinary_colour_mark(mark, latin)
        if parsed is None:
            continue
        occupied.append((mark.start(), mark.end()))
        positions = range(mark.start(1), mark.end(1))
        picked = [k for k, pos in enumerate(positions) if start <= pos < end]
        if not picked:
            continue
        base, marks = parsed
        pieces = recolour_pieces((ColourPiece(mark.group(1), base),),
                                 min(picked), max(picked) + 1, colour)
        new = serialize_colours(pieces, marks, latin=latin)
        if new != mark.group(0):
            replacements.append((mark.start(), mark.end(), new))

    occupied.sort()
    occupied_i = 0
    i = line_a
    while i < line_b:
        while occupied_i < len(occupied) and occupied[occupied_i][1] <= i:
            occupied_i += 1
        if occupied_i < len(occupied) and occupied[occupied_i][0] <= i < occupied[occupied_i][1]:
            i = occupied[occupied_i][1]
            continue
        if not _word_char(src[i]):
            i += 1
            continue
        j = i + 1
        next_occupied = (occupied[occupied_i][0]
                         if occupied_i < len(occupied) else line_b)
        while j < line_b and j < next_occupied and _word_char(src[j]):
            j += 1
        a, b = max(i, start), min(j, end)
        if a < b:
            pieces = recolour_pieces((ColourPiece(src[i:j]),), a - i, b - i, colour)
            new = serialize_colours(pieces, latin=latin)
            if new != src[i:j]:
                replacements.append((i, j, new))
        i = j
    if not replacements:
        if colour is None:
            return src, end
        raise StoreError("Select text to colour")
    out = src
    caret = end
    for a, b, new in reversed(replacements):
        out = out[:a] + new + out[b:]
        if a < end:
            caret += len(new) - (b - a)
    return out, caret


def retranslit_markdown(src, text, occurrence, translit):
    """Set the transliteration of the `occurrence`-th run equal to `text`;
    keep its colour and reading.  `translit=None` (or blank) removes the
    annotation."""
    return _remark_markdown(src, text, occurrence, translit=translit)


def rekana_markdown(src, text, occurrence, kana):
    """Set the reading (kana) of the `occurrence`-th run equal to `text`;
    keep its colour and transliteration.  `kana=None` (or blank) removes
    it.  Only for a target language with a reading."""
    return _remark_markdown(src, text, occurrence, kana=kana)


def set_run_color(doc_id, text, occurrence, color):
    """Colour the `occurrence`-th run equal to `text`.

    The choice is written into the markdown as `[متن]{teal}`, so it is
    part of the document: it survives, reaches the PDF, and is visible to
    an LLM asked to revise the text.  `color=None` removes the mark.
    """
    d = _doc_dir(doc_id)
    with _meta_lock(doc_id):
        src = (d / "source.md").read_text(encoding="utf-8")
        markdown = recolor_markdown(src, text, occurrence, color)
    return save_markdown(doc_id, markdown), markdown


def set_run_translit(doc_id, text, occurrence, translit):
    """Annotate the `occurrence`-th run equal to `text` with a
    transliteration, written into the markdown as `[متن]{translit:tond}`.

    Like a colour mark this is part of the document — invisible in both
    renderings, shown on hover, harvested into the glossary, and visible
    to an LLM asked to revise the text.  `translit=None` removes it.
    """
    d = _doc_dir(doc_id)
    with _meta_lock(doc_id):
        src = (d / "source.md").read_text(encoding="utf-8")
        markdown = retranslit_markdown(src, text, occurrence, translit)
    return save_markdown(doc_id, markdown), markdown


def set_run_kana(doc_id, text, occurrence, kana):
    """Annotate the `occurrence`-th run equal to `text` with its reading,
    written into the markdown as `[漢字]{kana:かんじ}` beside whatever
    transliteration and colour it has.  `kana=None` removes it."""
    d = _doc_dir(doc_id)
    with _meta_lock(doc_id):
        src = (d / "source.md").read_text(encoding="utf-8")
        markdown = rekana_markdown(src, text, occurrence, kana)
    return save_markdown(doc_id, markdown), markdown


# ---- images -----------------------------------------------------------

IMG_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._\-]*\.(png|jpe?g|svg|pdf)$")
IMG_MAGIC = {b"\x89PNG\r\n\x1a\n": ".png", b"\xff\xd8\xff": ".jpg",
             b"%PDF-": ".pdf"}
IMG_MAX = 15 * 1024 * 1024

# Each of the two vector formats is unreadable by one of the two
# renderers, so each gets a sibling twin made where it is missing — and
# both twins stay vector, because a figure supplied as PDF or SVG was
# supplied that way precisely so it could be scaled without loss:
#   *.svg -> <name>.svg.pdf   at build time, for XeLaTeX (server.build_pdf)
#   *.pdf -> <name>.pdf.svg   at upload time, for the browser, which
#                             shows no PDF inside a figure
# Glyphs are written as outlines, so the SVG needs none of the original
# PDF's fonts to render exactly as the PDF does.
DERIVED_RE = re.compile(r"\.(?:pdf\.svg|pdf\.png|svg\.pdf)$")


def images_dir(doc_id):
    return _doc_dir(doc_id) / "images"


def _img_kind(data):
    for magic, ext in IMG_MAGIC.items():
        if data.startswith(magic):
            return ext
    # SVG is text: look for an <svg root in the first kilobyte
    head = data[:1024].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if head.startswith(b"<?xml") or head.startswith(b"<svg") \
            or b"<svg" in head:
        return ".svg"
    return None


def save_image(doc_id, name, data):
    """Store an uploaded image under library/<id>/images/, returning its
    final (collision-free, sanitised) name."""
    if not data:
        raise StoreError("empty upload")
    if len(data) > IMG_MAX:
        raise StoreError("image larger than 15 MB")
    ext = _img_kind(data)
    if ext is None:
        raise StoreError("only PNG, JPEG, SVG and PDF figures are supported")
    stem = unicodedata.normalize("NFKD", Path(name or "img").stem)
    stem = stem.encode("ascii", "ignore").decode("ascii").lower()
    stem = re.sub(r"[^a-z0-9._\-]+", "-", stem).strip("-.") or "img"
    d = images_dir(doc_id)
    d.mkdir(parents=True, exist_ok=True)
    final, n = stem + ext, 2
    while (d / final).exists():
        if (d / final).read_bytes() == data:   # same file: reuse it
            return final
        final, n = "%s-%d%s" % (stem, n, ext), n + 1
    (d / final).write_bytes(data)
    if ext == ".pdf":
        ensure_pdf_twin(d / final)
    return final


def pdf_twin(path):
    """The path of the SVG the browser shows for a PDF figure."""
    return path.with_name(path.name + ".svg")


def ensure_pdf_twin(path):
    """Write the PDF's first page beside it as vector SVG, if missing.

    Best-effort and idempotent: called at upload and again when the twin
    is asked for, so a figure uploaded before this existed — or one whose
    twin was deleted — repairs itself.  Without PyMuPDF the figure still
    reaches the PDF build, since XeLaTeX reads PDF natively.
    """
    twin = pdf_twin(path)
    if twin.exists() or not path.is_file():
        return twin.exists()
    try:
        import pymupdf
        with pymupdf.open(str(path)) as doc:
            if not doc.page_count:
                return False
            # text_as_path keeps the glyphs as outlines: no dependency on
            # fonts the browser does not have, and still fully scalable
            svg = doc[0].get_svg_image(text_as_path=True)
        twin.write_text(svg, encoding="utf-8")
        # an earlier version rastered the page instead; that file is now
        # dead weight, and nothing points at it any more
        stale = path.with_name(path.name + ".png")
        if stale.is_file():
            stale.unlink()
        return True
    except Exception:
        return False


def list_images(doc_id):
    d = images_dir(doc_id)
    if not d.is_dir():
        return []
    src = ""
    try:
        src = (_doc_dir(doc_id) / "source.md").read_text(encoding="utf-8")
    except OSError:
        pass
    shown = set(_named(src, "images"))
    out = []
    for f in sorted(d.iterdir()):
        if not (f.is_file() and IMG_NAME_RE.match(f.name)):
            continue
        if DERIVED_RE.search(f.name):    # a preview, not something uploaded
            continue
        out.append({"name": f.name, "size": f.stat().st_size,
                    "referenced": f.name in shown})
    return out


def delete_image(doc_id, name):
    if not IMG_NAME_RE.match(name or "") or DERIVED_RE.search(name or ""):
        raise KeyError(name)
    f = images_dir(doc_id) / name
    if not f.is_file():
        raise KeyError(name)
    f.unlink()
    for twin in (f.with_name(f.name + ".svg"),      # the PDF's vector twin
                 f.with_name(f.name + ".png")):     # a raster one from before
        if twin.is_file():
            twin.unlink()


def image_path(doc_id, name):
    if not IMG_NAME_RE.match(name or ""):
        raise KeyError(name)
    return images_dir(doc_id) / name


# ---- recordings --------------------------------------------------------
#
# A document's recordings sit beside its pictures, in audio/, and are named
# the way pictures are: the extension follows the bytes, the stem is folded
# to lower-case ASCII, a clash becomes -2, -3, and the same file uploaded
# twice is stored once.  What counts as a recording is audiofile's to say,
# so the studio, the decks and the clip tray take the same formats.

def audio_dir(doc_id):
    return _doc_dir(doc_id) / "audio"


def holds_sound(data, ext):
    """Whether these bytes decode to sound, as the clip tray asks of what it
    keeps (clips.plays): the first bytes say what a file claims to be
    (audiofile.kind), and only decoding shows an MP4 with no sound track in
    it, or a stream that is not one past its first frames.  True when there
    is no ffmpeg to ask (and the file is not a WAV whose header says it is
    empty): nothing is refused for want of a tool."""
    fd, tmp = tempfile.mkstemp(prefix="parseh-sound-", suffix=ext)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        got = clips.plays(tmp)
    finally:
        os.unlink(tmp)
    # the tray's own threshold: shorter than that is a click, or nothing
    return got is None or got >= clips._LEAST


NO_SOUND = "the recording holds no sound"


def save_audio(doc_id, name, data):
    """Store an uploaded recording under the document's audio/, returning
    its final (collision-free, sanitised) name.  What claims to be a
    recording and decodes to no sound (holds_sound) is refused."""
    if not data:
        raise StoreError("empty upload")
    if len(data) > audiofile.MAX_BYTES:
        raise StoreError("recording larger than %d MB" % (audiofile.MAX_BYTES // 2 ** 20))
    ext = audiofile.kind(data, name or "")
    if ext is None:
        raise StoreError("only " + audiofile.HUMAN + " recordings are supported")
    d = audio_dir(doc_id)
    final = audiofile.free_name(str(d), audiofile.clean_stem(name, "audio"), ext, data)
    if (d / final).exists():              # the same file, already here
        return final
    if not holds_sound(data, ext):
        raise StoreError(NO_SOUND)
    d.mkdir(parents=True, exist_ok=True)
    # beside it first, then renamed: a page asking for the file meanwhile
    # finds it whole or not at all
    tmp = d / (".upload-%s" % uuid.uuid4().hex)
    try:
        tmp.write_bytes(data)
        os.replace(str(tmp), str(d / final))
    finally:
        if tmp.exists():
            tmp.unlink()
    return final


def _named(markdown, kind):
    """The names under `kind` ("images" or "audio") a markdown names, in
    order, each once: the dialect's one finder (mdparser.media_refs), which
    the decks go by too -- a line of its own, a flashcard's front-audio, a
    jolly field, a footnote; never myimages/x.png or a web address's
    .../images/x.png, and a sentence's full stop is not part of a name."""
    return [name for k, name in mdparser.media_names([markdown or ""]) if k == kind]


def _audio_refs(markdown):
    """The recording names a markdown shows, in order, each once."""
    return _named(markdown, "audio")


def list_audio(doc_id):
    d = audio_dir(doc_id)
    if not d.is_dir():
        return []
    src = ""
    try:
        src = (_doc_dir(doc_id) / "source.md").read_text(encoding="utf-8")
    except OSError:
        pass
    shown = set(_audio_refs(src))
    return [{"name": f.name, "size": f.stat().st_size, "referenced": f.name in shown}
            for f in sorted(d.iterdir())
            if f.is_file() and audiofile.NAME_RE.match(f.name)]


def audio_path(doc_id, name):
    """The file of one recording; KeyError when the name is not one a
    recording may have or no such file is here."""
    if not audiofile.NAME_RE.match(name or ""):
        raise KeyError(name)
    f = audio_dir(doc_id) / name
    if not f.is_file():
        raise KeyError(name)
    return f


def delete_audio(doc_id, name):
    audio_path(doc_id, name).unlink()


# ---- the clip tray --------------------------------------------------------

def _tray_file_ok(kind, name, path):
    """Whether a file in the tray is what its name says: a recording under
    audiofile's rules, or a picture under the store's."""
    try:
        if kind == "audio":
            if not audiofile.NAME_RE.match(name) or path.stat().st_size > audiofile.MAX_BYTES:
                return False
            with open(path, "rb") as f:
                return audiofile.kind(f.read(4096), name) is not None
        if not IMG_NAME_RE.match(name) or DERIVED_RE.search(name) \
                or path.stat().st_size > IMG_MAX:
            return False
        with open(path, "rb") as f:
            return _img_kind(f.read(4096)) is not None
    except OSError:
        return False


def _copy_in(src, folder, name):
    """Copy `src` into `folder` as `name`, beside it first and then renamed:
    a page asking for the file meanwhile finds it whole or not at all.
    False when it could not be copied (nothing is left behind then)."""
    folder.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(folder), prefix=".adopt-")
    os.close(fd)
    try:
        shutil.copyfile(src, tmp)
        os.replace(tmp, folder / name)
    except OSError:
        return False
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return True


def adopt_media(doc_id, markdown=None):
    """Bring in from the clip tray what the markdown shows and the document
    lacks -> {"adopted": ["audio/x.mp3", ...], "missing": [...]}.

    A card cut from a book or a video names `audio/<name>` and
    `images/<name>` files that sit in the tray (CLIPS_DIR), not in any
    document.  Pasted or typed into a document, those names would show
    nothing; this copies each one in under the same name -- a tray name is
    unique across the toolbox, so it cannot stand for another file here --
    and leaves the tray as it was, since the same clip may go to a deck or
    another document too.  What neither the document nor the tray holds is
    named as missing.  `markdown` defaults to the saved source."""
    d = _doc_dir(doc_id)
    if markdown is None:
        markdown = (d / "source.md").read_text(encoding="utf-8")
    adopted, missing = [], []
    for kind, refs in (("audio", _named(markdown, "audio")),
                       ("images", _named(markdown, "images"))):
        for ref in refs:
            path = kind + "/" + ref
            if (d / kind / ref).is_file():
                continue
            src = Path(CLIPS_DIR) / ref
            if not (src.is_file() and _tray_file_ok(kind, ref, src)):
                missing.append(path)
                continue
            if not _copy_in(src, d / kind, ref):
                missing.append(path)
                continue
            adopted.append(path)
    return {"adopted": adopted, "missing": missing}


# ---- the starters' own pictures and recording ------------------------------
#
# A new document begins as its language's starter (server.new_template), and
# a starter shows everything the dialect does -- a picture and a recording on
# a line of their own, on a card, with an exercise.  A new document holds no
# images/ and no audio/ yet, so those lines would name files it does not
# have.  The few files the starters name ship beside them, in
# exlex/starters/assets/images/ and audio/, all called `starter-...`; the
# editor's preview of a document not saved yet shows them from there
# (server.api_preview), and a save gives the document its own copy of each
# one it names and lacks (adopt_starter_media) -- after which it is the
# document's file like any other, to delete or take away in a zip.
#
# LIKE ANY OTHER INCLUDES STAYING DELETED.  A save that found a starter's
# name missing and copied it in again would undo the owner's ✕ in Images…
# or Recordings… behind their back, while the page had just told them the
# embed would break.  So the document's meta.json lists, under
# "starter_media", the starter's files it has held
# ("images/starter-apple.svg"), and a name listed there is never copied in
# again: deleted, it is missing wherever the document is shown, as a file
# of the document's own would be, until the owner uploads one under that
# name or the line names something else.

STARTER_MEDIA = ROOT / "exlex" / "starters" / "assets"


def starter_media(kind, name):
    """The shipped file behind a starter's `images/<name>` or `audio/<name>`
    (`kind` "images" or "audio"), or None: no starter ships one by that
    name, or the name is not one a document's file may have."""
    if kind == "images":
        ok = IMG_NAME_RE.match(name or "") and not DERIVED_RE.search(name)
    elif kind == "audio":
        ok = audiofile.NAME_RE.match(name or "")
    else:
        ok = False
    if not ok:
        return None
    f = STARTER_MEDIA / kind / name
    return f if f.is_file() else None


def adopt_starter_media(doc_id, markdown=None):
    """Copy into the document each starter file its markdown names, it does
    not hold and has never held -> ["images/starter-apple.svg", ...].

    Under the same name and into the same place a picture or a recording of
    its own sits (images/, audio/), exactly as a clip comes in from the
    tray (adopt_media).  A file the document already holds under that name
    is never replaced: whatever the owner put there is theirs.  Each name
    it holds, copied now or found there, is kept in its meta.json
    (starter_media_held), and one kept there and gone since was deleted by
    the owner: it stays deleted.  `markdown` defaults to the saved source."""
    d = _doc_dir(doc_id)
    if markdown is None:
        markdown = (d / "source.md").read_text(encoding="utf-8")
    adopted = []
    with _meta_lock(doc_id):
        meta = _read_meta(d)
        was = _held_list(meta)
        held = set(was)
        for kind in ("images", "audio"):
            for ref in _named(markdown, kind):
                src, path = starter_media(kind, ref), kind + "/" + ref
                if src is None:
                    continue
                if (d / kind / ref).exists():
                    held.add(path)
                elif path not in held and _copy_in(src, d / kind, ref):
                    held.add(path)
                    adopted.append(path)
        if held != set(was):
            meta["starter_media"] = sorted(held)
            _write_meta(d, meta)
    return adopted


def _held_list(meta):
    """meta.json's "starter_media", as the paths it lists; anything else
    there (a hand-edited file) is read as none."""
    got = meta.get("starter_media")
    return [p for p in got if isinstance(p, str)] if isinstance(got, list) else []


def starter_media_held(doc_id):
    """The starter's files this document has held, as "images/<name>" and
    "audio/<name>" (adopt_starter_media) -- whether or not it holds them
    still.  An empty set for a document whose record cannot be read: the
    preview asking must still render."""
    try:
        return set(_held_list(_read_meta(_doc_dir(doc_id))))
    except (KeyError, OSError, StoreError):
        return set()


def _layout_attrs(width, align, offset, start=None, end=None):
    parts = []
    defaults = mdparser.IMAGE_DEFAULTS
    if (width, align, offset) != (defaults["width"], defaults["align"],
                                  defaults["offset"]) \
            or start is not None or end is not None:
        parts = ["width=%d" % width, "align=%s" % align, "offset=%d" % offset]
    if start is not None:
        parts.append("start=%s" % mdparser.clip_seconds(start))
    if end is not None:
        parts.append("end=%s" % mdparser.clip_seconds(end))
    return "{%s}" % " ".join(parts) if parts else ""


def _clip_window(start, end, whole):
    """start/end of a clip, cleaned: never negative, and then the dialect's
    one rule (texgen.clip_window, which the page and the paper draw by): an
    end that is not after the start dropped -- and with no start the clip
    starts at 0, so an end at 0 is dropped too (`#t=0,0` is a clip that
    never plays).  A YouTube video counts in whole seconds (its URL takes
    nothing else); a recording to the hundredth."""
    def clean(v):
        if v is None:
            return None
        v = float(v)
        if not math.isfinite(v):
            raise StoreError("bad clip time %r" % v)
        v = max(0.0, v)
        return int(v) if whole else round(v, 2)
    return clip_window(clean(start), clean(end))


def _unquote(line, depth):
    """The line inside `depth` levels of `>` box, or None when it is not
    inside that many (the box has ended)."""
    for _ in range(depth):
        m = re.match(r"^\s*>\s?", line)
        if not m:
            return None
        line = line[m.end():]
    return line


def image_layout_markdown(src, index, width, align, offset,
                          start=None, end=None):
    """Pure rewrite of the attribute block of the `index`-th embed (image,
    recording or video) line.  Lines are scanned in document order,
    including inside `>` boxes, so the index matches the data-idx the
    renderer assigns; start/end apply to videos (whole seconds) and to
    recordings (`![..](audio/..)`, to the hundredth).

    An `:::exercise` body is skipped whole, as the parser reads it: through
    its first `:::`, or to the end of the box it was opened in.  Pictures
    and recordings inside a flashcard's fields are part of the card, and the
    renderer gives them no number."""
    if align not in ("left", "center", "right"):
        raise StoreError("bad align %r" % align)
    width = max(5, min(100, int(width)))
    offset = max(-100, min(100, int(offset)))
    lines = src.split("\n")
    n = 0
    exercise = None                 # the box depth an open exercise is at
    for i, line in enumerate(lines):
        if exercise is not None:
            inner = _unquote(line, exercise)
            if inner is not None:
                if inner.strip() == ":::":
                    exercise = None
                continue
            exercise = None         # its box ended, and the exercise with it
        m = re.match(r"^((?:\s*>\s?)*\s*)(.*)$", line)
        prefix, body = m.group(1), m.group(2).strip()
        if mdparser.EXERCISE_OPEN_RE.match(body):
            exercise = prefix.count(">")
            continue
        im = mdparser.IMAGE_RE.match(body)
        vm = None if im else mdparser.VIDEO_RE.match(body)
        if not im and not vm:
            continue
        if n == index:
            if im and im.group(2).startswith("audio/"):
                attrs = _layout_attrs(width, align, offset,
                                      *_clip_window(start, end, whole=False))
                lines[i] = "%s![%s](%s)%s" % (prefix, im.group(1),
                                              im.group(2), attrs)
            elif im:
                attrs = _layout_attrs(width, align, offset)
                lines[i] = "%s![%s](%s)%s" % (prefix, im.group(1),
                                              im.group(2), attrs)
            else:
                attrs = _layout_attrs(width, align, offset,
                                      *_clip_window(start, end, whole=True))
                lines[i] = "%s@[%s](%s)%s" % (prefix, vm.group(1),
                                              vm.group(2), attrs)
            return "\n".join(lines)
        n += 1
    raise StoreError("embed %d not found in the source" % index)


def set_image_layout(doc_id, index, width, align, offset,
                     start=None, end=None):
    d = _doc_dir(doc_id)
    with _meta_lock(doc_id):
        src = (d / "source.md").read_text(encoding="utf-8")
        markdown = image_layout_markdown(src, index, width, align, offset,
                                         start, end)
    return save_markdown(doc_id, markdown)


def snapshot_hash(doc_id):
    """Hash of the current source, taken before a (long) build begins."""
    return _source_hash(_doc_dir(doc_id))


def set_build(doc_id, build, snap=None):
    """Record a build result.  If `snap` (a snapshot_hash taken before the
    build) is given, the build is flagged stale when the source changed
    while it ran — so a PDF built from now-outdated markdown never shows
    as fresh, even under a concurrent save."""
    d = _doc_dir(doc_id)
    with _meta_lock(doc_id):
        meta = _read_meta(d)
        if snap is not None and build.get("status") == "ok":
            build = dict(build, stale=(_source_hash(d) != snap))
        meta["build"] = build
        _write_meta(d, meta)
    return meta


def duplicate(doc_id):
    """A copy of the document, named "<title> (copy)" -- or "(copy 2)", "(copy
    3)"… when that is taken -- in its front matter as in its meta, so the
    two never disagree and a link by either name means one document."""
    d = _doc_dir(doc_id)
    meta = _read_meta(d)
    markdown = (d / "source.md").read_text(encoding="utf-8")
    title = meta.get("title") or UNTITLED
    with _names_lock():
        name = _free_name(_name_keys(), "%s (copy)" % title,
                          lambda n: "%s (copy %d)" % (title, n))
        copy = _create(set_title(markdown, name), meta.get("tags"))
    for sub in ("images", "audio"):      # the embeds point into these
        if (d / sub).is_dir():
            shutil.copytree(d / sub, _doc_dir(copy["id"]) / sub,
                            dirs_exist_ok=True)
    held = _held_list(meta)
    if held:
        # a starter's picture the original's owner deleted stays deleted in
        # the copy too (adopt_starter_media): the copy holds what it held
        cd = _doc_dir(copy["id"])
        with _meta_lock(copy["id"]):
            cm = _read_meta(cd)
            cm["starter_media"] = held
            _write_meta(cd, cm)
    return copy


# ------------------------------------------------------------------ names
# A DOCUMENT'S NAME is its title: the front matter's `title:` line, which
# meta.json mirrors.  A link to it says that name ([…](doc:Name), texgen), so
# a name is unique within one library -- the studio's, all its language
# folders together, or the notes of one book, or of one video -- compared by
# texgen.doc_name_key (case-blind, blanks collapsed).  The id and the uid stay
# what they were: the folder's permanent name and the record's, never shown
# in a link and never renamed.
#
# Whatever gives a document a name holds this library's lock while it looks
# at the others' and writes its own, so two requests cannot both take one.
# Always taken BEFORE a document's own lock (_meta_lock), never inside one.
UNTITLED = "Untitled"
_NAME_LOCKS = {}


def _names_lock():
    key = os.path.abspath(str(lib()))
    with _DOC_LOCKS_GUARD:
        return _NAME_LOCKS.setdefault(key, threading.RLock())


def _named_docs():
    """Every document of this library, as the names need it:
    [{"id", "uid", "title", "created"}], oldest first."""
    out = []
    for d in _doc_dirs():
        try:
            meta = _read_meta(d)
        except StoreError:
            continue
        out.append({"id": meta.get("id") or d.name, "uid": meta.get("uid") or "",
                    "title": meta.get("title") or "", "created": meta.get("created") or ""})
    out.sort(key=lambda e: (e["created"], e["id"]))
    return out


def _name_keys(exclude=()):
    return set(doc_name_key(e["title"]) for e in _named_docs()
               if e["id"] not in exclude)


def _free_name(taken, first, then=None):
    """`first`, or the first of then(2), then(3)… -- `first` + " 2", " 3"…
    unless said otherwise -- whose key is not in `taken`."""
    then = then or (lambda n: "%s %d" % (first, n))
    name, n = first, 2
    while doc_name_key(name) in taken:
        name, n = then(n), n + 1
    return name


def set_title(markdown, title):
    """The markdown with its front matter's title saying `title`: the line
    rewritten where it stands (the last, which is the one the parser reads),
    added to a header that has none, or a header made for a text that has
    none.  Everything else is left exactly as it was."""
    title = _header_value(title)
    lines = (markdown or "").split("\n")
    block = _header_block(lines)
    if not block:
        return "---\n%s\n---\n\n%s" % (_header_line("title", title),
                                         (markdown or "").lstrip("\n"))
    i, j = block
    for n in range(j - 1, i, -1):
        m = _HEADER_LINE_RE.match(lines[n])
        if m and m.group(1).lower() == "title":
            lines[n] = _header_line(m.group(1), title)
            break
    else:
        lines.insert(i + 1, _header_line("title", title))
    return "\n".join(lines)


def _body_start(lines):
    """Where the body begins: past the front matter, as mdparser.parse finds
    it (blank lines, a `---`, and up to the next `---` or the end)."""
    i, n = 0, len(lines)
    while i < n and not lines[i].strip():
        i += 1
    if i < n and lines[i].strip() == "---":
        j = i + 1
        while j < n and lines[j].strip() != "---":
            j += 1
        return j + 1 if j < n else n
    return 0


def rewrite_links(markdown, fix, front_matter=True, lang=None):
    """The markdown with every `[label](doc:…)` link in its BODY passed to
    `fix(label, name)`, which answers the new name for it or None to leave
    it as it is -> (markdown, how many were rewritten).  The front matter is
    not touched: a link there would be in a title, and a title is renamed on
    purpose or not at all.  `front_matter=False` says the text has none (an
    exercise in a deck), so a first line of `---` is a rule like any other,
    and `lang` which language it is in (a document says it itself).

    Only the name after `doc:` is rewritten, never the label: the links are
    found as the page finds them (texgen.find_doclinks), a label holding a
    mark included, and a link inside a footnote beside the link whose label
    holds that footnote."""
    if "doc:" not in markdown:
        # most documents link nowhere, and a rename or the migration asks
        # every document of the library this: they are answered at once
        return markdown, 0
    lines = markdown.split("\n")
    k = _body_start(lines) if front_matter else 0
    if k >= len(lines):
        return markdown, 0
    head, body = "\n".join(lines[:k]), "\n".join(lines[k:])
    if front_matter:
        lang = mdparser.parse(head)[0]["target"]
    out, last, count = [], 0, 0
    # by where each name stands: a link in a footnote inside another link's
    # label comes before that link, but its name before the other's
    for link in sorted(find_doclinks(body, lang), key=lambda l: l.target_start):
        new = fix(link.label, unescape_doc_name(link.target))
        if new is None or escape_doc_name(new) == link.target:
            continue
        out += [body[last:link.target_start], escape_doc_name(new)]
        last = link.target_end
        count += 1
    body = "".join(out) + body[last:]
    return (head + "\n" + body if k else body), count


def _write_source(d, markdown):
    # atomic, as _write_meta: a document rewritten because ANOTHER one was
    # renamed must never be left half-written by a crash
    fd, tmp = tempfile.mkstemp(dir=str(d), prefix=".source-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(markdown)
        os.replace(tmp, d / "source.md")
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _rewrite_source(doc_id, change, touch=False):
    """One document's source, changed by `change(markdown) -> markdown`
    under its lock, written atomically -> whether it changed.  Its build is
    marked stale when the text moved; `updated` is left alone unless `touch`
    says the change is the document's own (a rename of it) and not a link
    to some other document being put right."""
    d = _doc_dir(doc_id)
    with _meta_lock(doc_id):
        src = (d / "source.md").read_text(encoding="utf-8")
        new = change(src)
        if new == src:
            return False
        meta = _read_meta(d)
        _write_source(d, new)
        _refresh_from_source(meta, new)
        if touch:
            meta["updated"] = _now()
        if meta.get("build", {}).get("status") == "ok":
            meta["build"]["stale"] = True
        _write_meta(d, meta)
    return True


def migrate_links():
    """A library from before names, put right -> {"renamed": [(id, old, new)],
    "links": {id: n}}.  Idempotent: a second run finds nothing to do.

    First the names: two documents with one name (nothing forbade it once --
    a book's notes were all "A note") are told apart, the oldest by
    `created` keeping it and each later one getting " 2", " 3"… in its
    front matter and its meta, each said on stderr.  Nothing that links by
    that name has to follow: a link finds the oldest (texgen.prepare_doc_index)
    and that one kept it.

    Then the links: every `doc:<uid>` whose uid is a document of this
    library, and whose text is no document's name, is written as a link to
    that document's name, its label kept.  A uid nothing here has is left
    as it is -- it may be a document still to be restored."""
    renamed, links = [], {}
    with _names_lock():
        docs = _named_docs()
        taken, seen = set(), set()
        for e in docs:
            taken.add(doc_name_key(e["title"]))
        for e in docs:
            key = doc_name_key(e["title"])
            if key and key not in seen:
                seen.add(key)
                continue
            new = _free_name(taken, e["title"].strip() or UNTITLED)
            taken.add(doc_name_key(new))
            try:
                _rewrite_source(e["id"], lambda src, new=new: set_title(src, new))
            except (KeyError, OSError, StoreError) as err:
                print("[store] %s could not be renamed: %s" % (e["id"], err), file=sys.stderr)
                continue
            print("[store] %s: renamed %r to %r -- %s" % (
                e["id"], e["title"], new, "another document had that name first"
                if key else "a document needs a name"), file=sys.stderr)
            renamed.append((e["id"], e["title"], new))
            seen.add(doc_name_key(new))
            e["title"] = new
        by_uid = dict((e["uid"], e["title"]) for e in docs if e["uid"])

        def fix(label, name):
            if doc_name_key(name) in taken or not LEGACY_UID_RE.fullmatch(name):
                return None
            # a name from before names were checked may hold a "|", which
            # would split the table cell the link stands in: that link
            # keeps the uid, which reaches the same document
            new = by_uid.get(name.lower())
            return None if new is None or "|" in new else new
        for e in docs:
            n = [0]

            def change(src, n=n):
                out, n[0] = rewrite_links(src, fix)
                return out
            try:
                if _rewrite_source(e["id"], change):
                    links[e["id"]] = n[0]
            except (KeyError, OSError, StoreError) as err:
                print("[store] %s: its links could not be rewritten: %s" % (e["id"], err),
                      file=sys.stderr)
    return {"renamed": renamed, "links": links}


_MIGRATED = set()
_MIGRATED_GUARD = threading.Lock()


def migrate_once(again=False):
    """migrate_links, the first time this process meets this library (the
    studio's at start-up, a book's or a video's notes when they are first
    opened) -> its answer, or None when it has been done already.

    `again` says the library here is not the one met before, though it lies
    at the same place: a book's or a video's notes brought back whole by a
    bundle or a shelf's backup, which puts them there as they were written
    -- names shared, links by uid and all -- over notes this process may
    have opened, and migrated, already."""
    key = os.path.abspath(str(lib()))
    with _MIGRATED_GUARD:
        if key in _MIGRATED and not again:
            return None
    out = migrate_links()
    with _MIGRATED_GUARD:
        _MIGRATED.add(key)
    return out


# THE NAME-CONFLICT DIALOG'S SIDE OF THINGS.  Whatever adds a document to a
# library or renames one -- a save, a new document, an upload, a zip, a
# backup restored -- asks plan_names first.  A name already taken, by a
# document of the library or by another document coming in with this one,
# is refused with NameConflict and nothing is written; the page then asks,
# for each clash, for a new name for either document or both, and sends the
# same request again with `renames`:
#
#     {"existing": {<id>: "name", ...}, "incoming": {<ref>: "name", ...}}
#
# `ref` is what the request calls each incoming document (the saved
# document's id, NEW_REF for a new one, a file's path in a zip, a document's
# id in a backup).  Everything is checked again, all together, as the names
# will stand once written -- so two documents may swap names -- and a name
# still taken is answered with the same 409 and a problem for its field.
NEW_REF = "new"
_TAKEN = "“%s” is already the name of another document — choose another name"
_NO_NAME = "A document needs a name — give it one"
# A link to a document spells its name, and a link standing in a table
# cell (the dialect's tables are where the links of a grammar live) is cut
# at every "|" by the row's parser: a name holding one would split the
# cell -- and a rename would write it into documents nobody opened.
_NO_BAR = "A name cannot hold “|”: a link to it in a table would split the cell — choose another name"


class NameConflict(StoreError):
    """Names that clash: nothing was written.  `conflicts` pairs each
    incoming document that wants a taken name with the one holding it;
    `problems` maps a dialog field ("existing:<id>", "incoming:<ref>") to
    what is wrong with the name given for it, and `fields` says, for each
    of those, the document's title, the name it was to have and its file
    (an upload's) -- so that the dialog can ask for a field no pair
    brought it."""

    def __init__(self, conflicts, problems=None, fields=None):
        super().__init__("this name is already in use: choose another for one "
                         "of the two documents")
        self.conflicts = conflicts
        self.problems = problems or {}
        self.fields = fields or {}

    def answer(self):
        return {"ok": False, "error": str(self), "name_conflicts": self.conflicts,
                "problems": self.problems, "fields": self.fields}


def clean_renames(renames):
    """A request's `renames`, whatever came -> {"existing": {id: name},
    "incoming": {ref: name}}, every name one line."""
    out = {"existing": {}, "incoming": {}}
    if isinstance(renames, dict):
        for side in out:
            got = renames.get(side)
            if isinstance(got, dict):
                for k, v in got.items():
                    if isinstance(k, str) and isinstance(v, str):
                        out[side][k] = _header_value(v)
    return out


def plan_names(incoming, renames=None, replacing=()):
    """The names documents will have once `incoming` is written ->
    {"existing": {id: (old, new)}, "incoming": {ref: name}}, or NameConflict.

    `incoming` is [{"ref", "title", "file"?}]; `replacing` the ids of the
    library's documents they take the place of (a save, a backup replacing
    its own), which do not count as holding their names.  An incoming
    document with no title and no name given is "Untitled", made unique.
    Two documents of the library already sharing a name (a library not yet
    migrated) are nobody's clash here."""
    renames = clean_renames(renames)
    rows = []
    for e in _named_docs():
        if e["id"] in replacing:
            continue
        given = e["id"] in renames["existing"]
        rows.append({"field": "existing:" + e["id"], "id": e["id"], "title": e["title"],
                     "given": given,
                     "final": renames["existing"][e["id"]] if given else e["title"]})
    for i in incoming:
        given = i["ref"] in renames["incoming"]
        rows.append({"field": "incoming:" + i["ref"], "ref": i["ref"],
                     "title": i.get("title") or "", "file": i.get("file"), "given": given,
                     "final": renames["incoming"][i["ref"]] if given else (i.get("title") or "")})
    problems = dict((r["field"], _NO_NAME) for r in rows if r["given"] and not r["final"])
    for r in rows:
        if ("ref" in r or r["given"]) and "|" in r["final"]:
            problems.setdefault(r["field"], _NO_BAR)
    taken = set(doc_name_key(r["final"]) for r in rows if r["final"])
    for r in rows:
        if "ref" in r and not r["final"] and not r["given"]:
            r["final"] = _free_name(taken, UNTITLED)
            taken.add(doc_name_key(r["final"]))
    groups = {}
    for r in rows:
        if r["final"]:
            groups.setdefault(doc_name_key(r["final"]), []).append(r)
    conflicts = []
    for group in groups.values():
        if len(group) < 2 or not any("ref" in r or r["given"] for r in group):
            continue
        for r in group:
            if r["given"]:
                problems.setdefault(r["field"], _TAKEN % r["final"])
        # each document that wants the name, paired with the one holding it
        # (a document of the library keeping its own name, when there is
        # one) -- a name given in answer too, not only a title: a dialog
        # opened on this answer alone, as a backup's second pass is (sent
        # with the names its first pass was given), must have a field for
        # every name it refuses
        holder = (next((r for r in group if "id" in r and not r["given"]), None)
                  or next((r for r in group if not r["given"]), None) or group[0])
        for r in group:
            if r is holder or not ("ref" in r or r["given"]):
                continue
            conflicts.append({"incoming": _pair_side(r), "existing": _pair_side(holder, True)})
    if conflicts or problems:
        rows_by_field = dict((r["field"], r) for r in rows)
        raise NameConflict(conflicts, problems, dict(
            (f, {"title": rows_by_field[f]["title"], "name": rows_by_field[f]["final"],
                 "file": rows_by_field[f].get("file")}) for f in problems))
    return {"existing": dict((r["id"], (r["title"], r["final"])) for r in rows
                             if "id" in r and r["final"] != r["title"]),
            "incoming": dict((r["ref"], r["final"]) for r in rows if "ref" in r)}


def _pair_side(r, holding=False):
    """One document of a name-conflict pair, as the dialog reads it: a
    document of the library by its id, one coming in by its ref (as the
    pair's second one, `incoming_ref`), and the name it was given, when it
    was given one."""
    if "id" in r:
        side = {"id": r["id"], "title": r["title"]}
    else:
        side = {"incoming_ref" if holding else "ref": r["ref"], "title": r["title"],
                "file": r["file"]}
    if r["given"]:
        side["name"] = r["final"]
    return side


def _retitle(changes):
    """The library's documents a dialog renamed, renamed -- front matter and
    meta, their `updated` too, since the rename is theirs -> {old key: new
    name}, for rename_links to follow."""
    follow = {}
    for doc_id, (old, new) in changes.items():
        _rewrite_source(doc_id, lambda src, new=new: set_title(src, new), touch=True)
        if old:
            follow[doc_name_key(old)] = new
    return follow


def _named_as(markdown, title, final, own, existing):
    """An incoming document's text as it goes in: its title line saying the
    name it was given, and its links followed -- one to a document coming
    in with it follows THAT document (`own`, {name key in the batch: name
    given}: the link was written for it), one to a document of the library
    that the dialog renamed follows the library's (`existing`)."""
    if final != title:
        markdown = set_title(markdown, final)
    follow = dict(existing)
    follow.update(own)
    if follow:
        markdown = rewrite_links(markdown, lambda label, name:
                                 follow.get(doc_name_key(name)))[0]
    return markdown


# Who else holds links that resolve in the STUDIO's library: the exercise
# decks (deckroutes renders every exercise against it).  Told of each rename
# there, and only there -- a book's notes are no deck's library.  Registered
# by the server at start-up (server.main, serve.py) rather than at import,
# so that a test renaming documents in a library of its own can never
# rewrite the decks on this machine.
_FOLLOWERS = []


def follow_renames(fn):
    """`fn(renames)` is called with {old name key: new name} after every
    rename in the studio's library."""
    if fn not in _FOLLOWERS:
        _FOLLOWERS.append(fn)


# RENAMES AN OPEN EDITOR HAS NOT SEEN.  An editor sends its whole text at
# every save.  A rename made elsewhere while it was open (another tab, the
# names dialog of an upload, a backup restored) rewrote this document's
# links on disk, and the editor's text still spells the old names: saved as
# it is, it would put them back, dead -- and "Linked from" would lose them.
# So every batch of renames rename_links follows is logged, per library,
# under a number; the edit page is given the number as it reads the text
# (edit_view), sends it back with each save, and save() follows the renames
# logged since in the text it is given, as the text on disk followed them.
# In memory only: a server started since the page was read knows nothing of
# what came before it (the epoch in the mark says so), and the save is then
# what it always was.
_RENAME_EPOCH = uuid.uuid4().hex[:8]
_RENAME_LOGS = {}                  # library root -> [(n, {old key: new name})]
_RENAME_N = [0]
_RENAME_KEEP = 500                 # batches kept per library
_RENAME_GUARD = threading.Lock()


def _log_renames(renames):
    key = os.path.abspath(str(lib()))
    with _RENAME_GUARD:
        _RENAME_N[0] += 1
        log = _RENAME_LOGS.setdefault(key, [])
        log.append((_RENAME_N[0], dict(renames)))
        del log[:-_RENAME_KEEP]


def names_mark():
    """How far this library's renames go now, as a page carries it: the
    mark a save sends back to have the renames made since followed."""
    with _RENAME_GUARD:
        # and after a `~`, how far the LaTeX themes' renames go
        # (latexthemes.catch_up), which a save follows too
        return "%s:%d~%s" % (_RENAME_EPOCH, _RENAME_N[0], latexthemes.rename_mark())


def renames_since(mark):
    """The batches of renames made in this library after `mark` (names_mark),
    oldest first; none for a mark of another process, or none at all."""
    epoch, _, n = str(mark or "").split("~")[0].partition(":")
    if epoch != _RENAME_EPOCH or not n.isdigit():
        return []
    key = os.path.abspath(str(lib()))
    with _RENAME_GUARD:
        return [batch for k, batch in _RENAME_LOGS.get(key, ()) if k > int(n)]


def catch_up(markdown, batches, current=None):
    """A text written before `batches` of renames, brought up to them: its
    links follow each rename in turn, as the documents on disk did.  The
    document it is the text of may itself have been renamed meanwhile (the
    other document of a names dialog, the meta route): a title still
    spelling the name it had then is `current`, its name now -- the editor
    did not ask for the old one back.  A title changed in the editor is
    the editor's."""
    typed = title = mdparser.parse(markdown)[0].get("title") or ""
    for batch in batches:
        markdown = rewrite_links(markdown, lambda label, name, batch=batch:
                                 batch.get(doc_name_key(name)))[0]
        title = batch.get(doc_name_key(title), title)
    if current and title != typed and doc_name_key(title) == doc_name_key(current):
        markdown = set_title(markdown, current)
    return markdown


def names_held():
    """This library's names lock, for a caller that reads a names_mark
    together with what it did (server.api_save): nothing renamed between."""
    return _names_lock()


def edit_view(doc_id):
    """What the edit page opens with -> (meta, markdown, names_mark), read
    together: a rename between the two would otherwise be followed twice,
    or not at all."""
    with _names_lock():
        meta, markdown = get(doc_id)
        return meta, markdown, names_mark()


def rename_links(renames, skip=()):
    """Every link in this library that names a renamed document by its OLD
    name, rewritten to its new one: `renames` is {old name key: new name},
    for any number of documents renamed at once (a swap included: each link
    is rewritten once, by what it said before) -> {id: links rewritten}.

    Each document so changed is rewritten under its own lock, atomically,
    its label kept, its `updated` left alone (another document's rename is
    not an edit of this one, and the library's "recently updated" order
    stays as it was) and a built PDF marked stale.  Documents in `skip` are
    the caller's own, written by it already."""
    out = {}
    if not renames:
        return out

    def fix(label, name):
        return renames.get(doc_name_key(name))
    with _names_lock():
        _log_renames(renames)
        for e in _named_docs():
            if e["id"] in skip:
                continue
            n = [0]

            def change(src, n=n):
                text, n[0] = rewrite_links(src, fix)
                return text
            try:
                if _rewrite_source(e["id"], change):
                    out[e["id"]] = n[0]
            except (KeyError, OSError, StoreError) as err:
                print("[store] %s: its links could not follow a rename: %s"
                      % (e["id"], err), file=sys.stderr)
        if getattr(_HERE, "root", None) is None:
            for fn in list(_FOLLOWERS):
                try:
                    fn(renames)
                except Exception as err:     # noqa: BLE001 -- the rename stands
                    print("[store] a rename was not followed by %s: %s"
                          % (getattr(fn, "__name__", fn), err), file=sys.stderr)
    return out


def doc_index():
    """uid -> {id, title, created} for every document, to resolve
    `[…](doc:Name)` links (texgen.prepare_doc_index keys it by name too).

    A link stores the target's name, so the destination URL is looked up at
    render time, and so is the title an empty label shows; a link written
    before names stores a uid, and finds its document by that.
    """
    lib().mkdir(parents=True, exist_ok=True)
    idx = {}
    for d in _doc_dirs():
        try:                       # one bad document must not blind the rest
            meta = _read_meta(d)
        except StoreError:
            continue
        uid = meta.get("uid")
        if uid:
            idx[uid] = {"id": meta.get("id", d.name),
                        "title": meta.get("title") or d.name,
                        "created": meta.get("created") or ""}
    return idx


# ---------------------------------------------------------------- backlinks
# What the document page's "Linked from" drawer lists: the documents of the
# same library whose text links to this one, each with the words around
# every such link.  Found the way a page finds a link's document
# (texgen.lookup_doclink): by name, or through the uid a link written before
# names spells -- so the drawer and the pages never disagree about which
# links reach here, a link left hanging by a deletion included (it reaches
# nothing, and is listed nowhere, until a document of its name is back).
BACKLINK_CONTEXT = 70           # characters of plain text each side of a link


def _plain_line(text, L, index):
    import notes                 # notes imports store: it can only come here
    text = re.sub(r"^\s*(?:>\s*)*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)?", "", text)
    text = re.sub(r"^\s*[a-z][a-z0-9-]*:\s+", "", text)       # an exercise's field key
    # one line: a forced break (⏎, which _plain keeps as one) is a space here
    return notes._plain(re.sub(r"\s*\|\s*", " · ", text), L, index).replace("\n", " ")


def backlinks(doc_id):
    """The documents of this library that link here -> [{"id", "title",
    "target", "snippets": [{"before", "link", "after"}]}], by title.

    A snippet is plain text: the link as the page shows it (its label, or
    this document's title), with up to BACKLINK_CONTEXT characters of its
    line on either side, cut between two words.  A document's links to
    itself are not listed: it is the page being read."""
    import notes                 # notes imports store: it can only come here
    _doc_dir(doc_id)                                   # KeyError for none
    index = prepare_doc_index(doc_index())
    out = []
    for d in _doc_dirs():
        try:
            meta = _read_meta(d)
            if (meta.get("id") or d.name) == doc_id:
                continue
            src = (d / "source.md").read_text(encoding="utf-8")
        except (OSError, StoreError):
            continue
        if "doc:" not in src:
            continue
        lines = src.split("\n")
        body = "\n".join(lines[_body_start(lines):])
        L = languages.get_or_default(meta.get("target"))
        snippets = []
        for link in find_doclinks(body, L.code):
            info = lookup_doclink(link.target, index)
            if not info or info.get("id") != doc_id:
                continue
            start = body.rfind("\n", 0, link.start) + 1
            end = body.find("\n", link.end)
            end = len(body) if end < 0 else end
            # a table row's outer bars are no part of what it says; the
            # word joiners keep the spaces next to the link from being
            # trimmed away as the ends of a line
            before = _plain_line(re.sub(r"^\s*\|", "", body[start:link.start]) + "\u2060",
                                 L, index)[:-1]
            after = _plain_line("\u2060" + re.sub(r"\|\s*$", "", body[link.end:end]),
                                L, index)[1:]
            # the label as the page shows it: plain text, a mark in it
            # reduced to its words
            label = notes._plain(link.label, L, index) if link.label.strip() else ""
            snippets.append({"before": _tail(before, BACKLINK_CONTEXT),
                             "link": resolve_doclink(link.target, label, index)[0],
                             "after": _head(after, BACKLINK_CONTEXT)})
        if snippets:
            out.append({"id": meta.get("id") or d.name, "title": meta.get("title") or d.name,
                        "target": meta.get("target") or languages.DEFAULT,
                        "snippets": snippets})
    out.sort(key=lambda e: (languages.fold(e["title"]), e["id"]))
    return out


def _head(text, n):
    """The first `n` characters of `text`, cut between two words, "…" after."""
    if len(text) <= n:
        return text
    cut = text.rfind(" ", 0, n)
    return text[:cut if cut > n // 2 else n].rstrip() + "…"


def _tail(text, n):
    """The last `n` characters of `text`, cut between two words, "…" before."""
    if len(text) <= n:
        return text
    cut = text.find(" ", len(text) - n)
    start = cut + 1 if 0 <= cut < len(text) - n // 2 else len(text) - n
    return "…" + text[start:].lstrip()


def delete(doc_id):
    shutil.rmtree(_doc_dir(doc_id))


def _decorate(meta):
    m = dict(meta)
    m.setdefault("target", languages.DEFAULT)
    # the title may carry runs of the document's own script
    set_target(m["target"])
    m["title_html"] = htmlgen.inline(m.get("title", ""))
    m["subtitle_html"] = htmlgen.inline(m.get("subtitle", ""))
    return m


def list_docs(q="", tags=None, exclude_tags=None, intext=False, sort="updated"):
    """Every document, newest first by default; each item carries
    `target` (the registry code)."""
    lib().mkdir(parents=True, exist_ok=True)
    out = []
    # languages.fold on both sides of every comparison, never .lower():
    # source.md and the titles carry the target language, and for Turkish a
    # locale-blind lower-case spells İ as i + a combining dot -- so a search
    # for "iyi" missed every document whose text says "İyi", and one for
    # "isik" missed "Işık".  The stored tags keep their own spelling; only
    # the comparison is folded.
    ql = languages.fold((q or "").strip())
    want = set(languages.fold(t) for t in (tags or []) if t)
    reject = set(languages.fold(t) for t in (exclude_tags or []) if t)
    for d in _doc_dirs():
        # One unreadable or malformed document must never take down the
        # whole listing — isolate every per-document failure and skip it.
        try:
            meta = _read_meta(d)
            held = set(languages.fold(t) for t in meta.get("tags", []))
            if want and not want.issubset(held):
                continue
            if reject and reject.intersection(held):
                continue
            if ql:
                hay = languages.fold(" ".join(
                    [meta.get("title", ""), meta.get("subtitle", ""),
                     meta.get("note", ""), " ".join(meta.get("tags", []))]))
                hit = ql in hay
                if not hit and intext:
                    try:
                        hit = ql in languages.fold(flatten_colours(
                            (d / "source.md").read_text(encoding="utf-8")))
                    except OSError:
                        hit = False
                if not hit:
                    continue
            out.append(_decorate(meta))
        except (OSError, ValueError, StoreError, IndexError) as e:
            print("[store] skipping %s: %s" % (d.name, e))
            continue
    keys = {
        "updated": lambda m: m.get("updated", ""),
        "created": lambda m: m.get("created", ""),
        "title": lambda m: languages.fold(m.get("title", "")),
    }
    rev = sort in ("updated", "created")
    out.sort(key=keys.get(sort, keys["updated"]), reverse=rev)
    return out


def all_tags():
    counts = {}
    for m in list_docs(sort="title"):
        for t in m.get("tags", []):
            counts[t] = counts.get(t, 0) + 1
    return [{"tag": t, "count": c}
            for t, c in sorted(counts.items(),
                               key=lambda x: (-x[1], x[0]))]


def lang_counts():
    """code -> number of documents, for the library's chip row."""
    counts = {}
    for m in list_docs(sort="title"):
        code = m.get("target") or languages.DEFAULT
        counts[code] = counts.get(code, 0) + 1
    return counts


# ---- custom prompt override ------------------------------------------
# THE STUDIO'S ONE CUSTOM PROMPT lived here as library/_prompt.md until a0.4.2,
# and has lived in the person's own prompts since (lib/prompts.py, config/
# prompts.json): move_prompt() carries the file over, once, at the first start.
# The three functions below are the studio's old single-prompt routes, kept
# working on the prompt that was moved -- before the move they still read the
# file, so a tree the move has not reached yet behaves as it always did.

def prompt_path():
    return lib() / "_prompt.md"


def default_prompt():
    """The copy-paste part of PROMPT.md (everything after the first ---)."""
    src = (ROOT / "exlex" / "PROMPT.md").read_text(encoding="utf-8")
    lines = src.replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "---":
            return "\n".join(lines[i + 1:]).strip() + "\n"
    return src


def move_prompt():
    """The studio's library/_prompt.md into the person's own prompts, as "my
    studio prompt (from before a0.4.2)", once -> the prompt made, or None."""
    return prompts.move_studio_file(LIB / "_prompt.md")


def get_prompt():
    kept = prompts.studio_text()
    if kept is not None:
        return {"text": kept, "custom": True}
    p = prompt_path()
    if p.exists() and not prompts.moved(prompts.STUDIO_MARK):
        return {"text": p.read_text(encoding="utf-8"), "custom": True}
    return {"text": default_prompt(), "custom": False}


def set_prompt(text):
    move_prompt()
    try:
        prompts.set_studio_text(text)
    except prompts.PromptsError as e:
        raise StoreError(str(e))


def reset_prompt():
    prompts.drop_studio()
    p = prompt_path()
    if p.exists():
        p.unlink()


# ----------------------------------------------------- a document as files
# THE HEADER A DOCUMENT IS FILED BY: the front matter's basic lines
# (mdparser.FM_KEYS), in the order a new note writes them.  An upload that
# lacks them, or some of them, is asked for what is missing before it goes in
# (server.api_create, import_zip); one that has them all goes in as it is,
# whatever else its header holds.
HEADER_KEYS = ("title", "subtitle", "note", "lang", "target")
# the three that are no use empty -- the title a document is named by and its
# two languages; a subtitle or a note may be there and blank
HEADER_NEEDS_VALUE = ("title", "lang", "target")
_HEADER_LINE_RE = re.compile(r"^([A-Za-z_]+)\s*:\s*(.*)$")


class HeaderNeeded(StoreError):
    """An import that waits for these files' headers:
    [{"name", "present", "missing", "values", "defaults"}, ...]."""

    def __init__(self, files):
        super().__init__("some markdown files have an incomplete header")
        self.files = files


def _header_block(lines):
    """(opening, closing) line numbers of the front matter, or None -- found
    as mdparser.parse finds it: past blank lines, a `---` line, and the next
    `---` line closing it.  An opening that never closes is no header here."""
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or lines[i].strip() != "---":
        return None
    for j in range(i + 1, len(lines)):
        if lines[j].strip() == "---":
            return i, j
    return None


def header_state(markdown):
    """{"present", "values", "missing"}: whether the text has a header, the
    basic fields it gives, and the ones it lacks -- a field is there when its
    line is, with a value in it for title, lang and target."""
    lines = (markdown or "").replace("\r\n", "\n").split("\n")
    block = _header_block(lines)
    values = {}
    if block:
        for line in lines[block[0] + 1:block[1]]:
            m = _HEADER_LINE_RE.match(line)
            if m and m.group(1).lower() in HEADER_KEYS:
                values[m.group(1).lower()] = m.group(2).strip()
    missing = [k for k in HEADER_KEYS
               if k not in values or (k in HEADER_NEEDS_VALUE and not values[k])]
    return {"present": bool(block), "values": values, "missing": missing}


def header_defaults(markdown, filename=""):
    """What the dialog offers for each field: whatever the header already
    says; for a title, the text's own `# heading` or else the file's name;
    the language a new note is written in; the registry's first language."""
    title = ""
    for line in (markdown or "").split("\n"):
        m = re.match(r"^#\s+(.+?)\s*#*\s*$", line)
        if m and "|" not in m.group(1):          # a lemma heading is no title
            title = re.sub(r"\{[^}]*\}|[\[\]*_`]", "", m.group(1)).strip()
            break
    if not title and filename:
        title = re.sub(r"[-_\s]+", " ", Path(posixpath.basename(filename)).stem).strip()
        title = title[:1].upper() + title[1:]
    out = {"title": title, "subtitle": "", "note": "", "lang": "en",
           "target": languages.get_or_default(None).code}
    out.update({k: v for k, v in header_state(markdown)["values"].items() if v})
    return out


def _header_value(value):
    # one line, as the parser reads a value
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def _header_line(key, value):
    return ("%s: %s" % (key, value)).rstrip()


def fill_header(markdown, fields):
    """The text with its header's missing basic fields added from `fields`.

    A header that has them all is not touched, whatever else it holds.  One
    short of some gets those lines, before its closing `---`, and every line
    it had stays as it was -- save a title, lang or target line that is there
    but empty, which gets its value written in.  A text with no header gets
    one, in the order a new note writes it, above the text."""
    markdown = (markdown or "").replace("\r\n", "\n")
    state = header_state(markdown)
    if not state["missing"]:
        return markdown
    fields = fields if isinstance(fields, dict) else {}
    got = {k: _header_value(fields.get(k)) for k in state["missing"]}
    if "title" in got and not got["title"]:
        raise StoreError("the header needs a title")
    if "lang" in got and not got["lang"]:
        raise StoreError("the header needs the language the note is written in (lang)")
    if "target" in got:
        got["target"] = got["target"].lower()
        if got["target"] not in languages.LANGS:
            raise StoreError("the header needs a target language the toolbox teaches, not %r"
                             % got["target"])
    lines = markdown.split("\n")
    block = _header_block(lines)
    if not block:
        head = ["---"] + [_header_line(k, got.get(k, "")) for k in HEADER_KEYS] + ["---", ""]
        return "\n".join(head) + "\n" + markdown.lstrip("\n")
    i, j = block
    added = []
    for key in state["missing"]:
        for n in range(i + 1, j):
            m = _HEADER_LINE_RE.match(lines[n])
            if m and m.group(1).lower() == key:
                lines[n] = _header_line(m.group(1), got[key])     # there, but empty
                break
        else:
            added.append(_header_line(key, got[key]))
    lines[j:j] = added
    return "\n".join(lines)


ZIP_MAX_FILES = 2000
ZIP_MAX_BYTES = 200 * 1024 * 1024        # unpacked, every entry together
MD_MAX = 5 * 1024 * 1024


def doc_zip(doc_id, slug=None):
    """The document as a zip: <slug>.md, its tags beside it, images/ with
    every picture its markdown shows -- as uploaded: a PDF figure's derived
    SVG stays behind, since the upload makes it again -- and audio/ with
    every recording it names.

    A DOCUMENT'S TAGS ARE NOT IN ITS MARKDOWN.  They live in meta.json, which
    does not travel, so a zip that carried only the text lost them on the way
    back in: <slug>.tags.json carries them instead, {"tags": [...]}, and the
    upload reads it.  A document with no tags gets no such file, so its zip
    is exactly what it always was."""
    d = _doc_dir(doc_id)
    slug = slug or re.sub(r"-[0-9a-f]{6}$", "", doc_id) or doc_id
    tags = [str(t) for t in (_read_meta(d).get("tags") or []) if str(t).strip()]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(slug + ".md", (d / "source.md").read_bytes())
        if tags:
            zf.writestr(slug + ".tags.json",
                        json.dumps({"tags": tags}, ensure_ascii=False, indent=1))
        for img in list_images(doc_id):
            if img["referenced"]:
                zf.write(str(images_dir(doc_id) / img["name"]), "images/" + img["name"])
        for rec in list_audio(doc_id):
            if rec["referenced"]:
                # already compressed, as every format but WAV is: stored as is
                zf.write(str(audio_dir(doc_id) / rec["name"]), "audio/" + rec["name"],
                         compress_type=zipfile.ZIP_STORED)
    return buf.getvalue()


# WHAT PARSEH WRITES, PARSEH READS BACK.  The Backup button packs the whole
# library with no ceiling of its own, while the restore refused more than
# 20 000 files or 2 GB -- a library of a few hundred illustrated, narrated
# documents passes both, and a backup that cannot be put back is not one.
# These are now far beyond anything one person's library reaches; the
# per-file defences (MD_MAX, a picture's, a recording's) are untouched,
# since those are what stops a crafted zip.  A backup that passes
# LIB_WARN_* says so while it is being written (server.api_export).
LIB_MAX_FILES = 400000
LIB_MAX_BYTES = 16 * 1024 ** 3
LIB_WARN_FILES = 20000              # "this is getting large", not a refusal
LIB_WARN_BYTES = 2 * 1024 ** 3


def big_backup_note(what, files, nbytes):
    """The sentence a backup says about itself once it is large enough to be
    worth a word: the count and the size, in the words a person uses, so
    that nobody has to guess at what "a big zip" means.  Both backups say it
    the same way (decks.backup_zip says it about the exercise shelf)."""
    mb = nbytes / float(1024 * 1024)
    return ("%s is large: %s files, %s so far"
            % (what, format(files, ","),
               ("%.1f GB" % (mb / 1024)) if mb >= 1024 else ("%d MB" % round(mb))))


def import_library(source, replace=False, renames=None):
    """A backup put back -> {"restored", "kept", "warnings"}.

    THIS IS NOT import_zip.  That one reads markdown somebody wrote and makes
    NEW documents of it; this one puts back what the Backup button wrote --
    library/<folder>/<id>/ with its meta.json beside the source -- so the
    ids, the uids, the names every [...](doc:Name) link spells, the tags,
    the timestamps and the build state all come back as they were.  Importing a
    backup as markdown would lose every one of them.

    A document already here is KEPT and named in the answer unless `replace`
    says otherwise: a restore is not a merge, and quietly overwriting a
    week's work because the backup is older is not something to do unasked.
    It is the same document when its id is, in whatever language folder.

    A document with another id whose name is taken -- by one of the library,
    or by another of the backup -- is a name conflict: NameConflict before
    anything is written, and `renames` is the dialog's answer (plan_names).
    The backup's links follow its documents to the names they end up with.

    `source` is bytes, a path or an open file, as decks.import_zip takes one:
    a whole library is spooled to disk by the server rather than held in
    memory twice over.
    """
    try:
        zf = (zipfile.ZipFile(io.BytesIO(source))
              if isinstance(source, (bytes, bytearray))
              else zipfile.ZipFile(source))
    except (zipfile.BadZipFile, ValueError, OSError):
        raise StoreError("that is not a zip file")
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > LIB_MAX_FILES:
            raise StoreError("the backup holds more than %d files" % LIB_MAX_FILES)
        if sum(i.file_size for i in infos) > LIB_MAX_BYTES:
            raise StoreError("the backup unpacks to more than %d GB"
                             % (LIB_MAX_BYTES // 2 ** 30))
        docs, loose = {}, []
        for info in infos:
            name = info.filename.replace("\\", "/")
            parts = [p for p in name.split("/") if p not in ("", ".")]
            # nothing from outside the zip's own tree, no resource forks, no
            # hidden files -- the same rule the document import goes by
            if name.startswith("/") or ".." in parts or not parts \
                    or parts[0] == "__MACOSX" or any(p.startswith(".") for p in parts):
                continue
            if languages.by_folder(parts[0]) is not None and len(parts) >= 3 \
                    and ID_RE.match(parts[1]):
                docs.setdefault((parts[0], parts[1]), []).append((parts[2:], info))
            elif ID_RE.match(parts[0]) and len(parts) >= 2:
                # a library from before the language folders: library/<id>/
                docs.setdefault((None, parts[0]), []).append((parts[1:], info))
            elif len(parts) == 1:
                loose.append((parts[0], info))       # library/_prompt.md and its like
        if not docs:
            raise StoreError("that zip holds no library: nothing in it is a "
                             "<language>/<document>/ of one")
        restored, kept, warnings = [], [], []
        with _names_lock():
            # first, without writing anything: which documents go in, and
            # what they are called.  A document is HERE when its id is,
            # whichever language folder it sits in now.
            here = dict((e["id"], e["title"]) for e in _named_docs())
            going, called = [], {}
            for (folder, doc_id), items in sorted(docs.items(), key=lambda kv: kv[0][1]):
                d = (lib() / folder / doc_id) if folder else (lib() / doc_id)
                names = {"/".join(rest): info for rest, info in items}
                if "meta.json" not in names or "source.md" not in names:
                    warnings.append("%s: not a whole document in the backup, left out" % doc_id)
                    continue
                try:
                    meta = json.loads(zf.read(names["meta.json"]).decode("utf-8-sig"))
                except (ValueError, UnicodeDecodeError, OSError, KeyError):
                    meta = None
                was_here = doc_id in here or d.exists()
                if was_here and not replace:
                    kept.append(doc_id)
                    if isinstance(meta, dict):
                        called[doc_id] = str(meta.get("title") or "")
                    continue
                if meta is None:
                    warnings.append("%s: its meta.json is not readable, left out" % doc_id)
                    continue
                if not isinstance(meta, dict):
                    warnings.append("%s: its meta.json is not a record, left out" % doc_id)
                    continue
                try:
                    text = zf.read(names["source.md"]).decode("utf-8")
                except (UnicodeDecodeError, OSError, KeyError):
                    warnings.append("%s: its source.md is not UTF-8 text, left out" % doc_id)
                    continue
                title = mdparser.parse(text)[0].get("title") or str(meta.get("title") or "")
                called[doc_id] = title
                going.append({"folder": folder, "id": doc_id, "d": d, "names": names,
                              "meta": meta, "text": text, "title": title, "here": was_here})
            # a name taken is refused here, with nothing written yet
            plan = plan_names([{"ref": g["id"], "title": g["title"],
                                "file": "%s/%s" % (g["folder"], g["id"]) if g["folder"] else g["id"]}
                               for g in going], renames,
                              replacing=set(g["id"] for g in going if g["here"]))
            existing = _retitle(plan["existing"])
            now_called = dict((e["id"], e["title"]) for e in _named_docs())
            # every link in the backup meant a document OF the backup: it
            # follows that document to the name it has once this is done --
            # the one it was given here, or the one a kept document has now
            final = dict((g["id"], plan["incoming"][g["id"]]) for g in going)
            own = {}
            for doc_id, title in sorted(called.items()):
                name = final.get(doc_id) or now_called.get(doc_id)
                if title and name:
                    own.setdefault(doc_name_key(title), name)
            # a document replaced by its backup copy is renamed if the copy is
            # called otherwise, and the library's links to it follow
            follow = dict(existing)
            for g in going:
                was = here.get(g["id"]) or ""
                if g["here"] and was and was != final[g["id"]]:
                    follow[doc_name_key(was)] = final[g["id"]]
            rename_links(follow, skip=set(g["id"] for g in going))
            for g in going:
                doc_id, d, names, meta = g["id"], g["d"], g["names"], g["meta"]
                text = _named_as(g["text"], g["title"], final[doc_id], own, existing)
                # written beside the document and swapped in, so a restore that
                # fails half way leaves what was there rather than half of this
                tmp = d.with_name(d.name + ".restoring")
                if tmp.exists():
                    shutil.rmtree(tmp, ignore_errors=True)
                try:
                    for rel, info in sorted(names.items()):
                        bits = rel.split("/")
                        ok = (rel in ("meta.json", "source.md")
                              or (len(bits) == 2 and bits[0] == "images"
                                  and IMG_NAME_RE.match(bits[1]))
                              or (len(bits) == 2 and bits[0] == "audio"
                                  and audiofile.NAME_RE.match(bits[1]))
                              or bits == ["build", "main.pdf"])
                        if not ok:
                            warnings.append("%s: %s is no part of a document" % (doc_id, rel))
                            continue
                        out = tmp / rel
                        out.parent.mkdir(parents=True, exist_ok=True)
                        if rel == "source.md":
                            out.write_text(text, encoding="utf-8")
                        elif rel != "meta.json":
                            out.write_bytes(zf.read(info))
                    # the directory is what the document is called, whatever
                    # the record says, and the tags are normalised as create()
                    # does; the title is the name it goes in with
                    meta["id"] = doc_id
                    meta["title"] = final[doc_id]
                    meta["tags"] = sorted(set(
                        languages.lower(str(t).strip())
                        for t in (meta.get("tags") or []) if str(t).strip()))
                    _write_meta(tmp, meta)
                    if g["here"]:
                        try:                       # wherever it sits now
                            shutil.rmtree(_doc_dir(doc_id))
                        except KeyError:
                            pass
                    if d.exists():
                        shutil.rmtree(d)
                    d.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(str(tmp), str(d))
                except (OSError, ValueError) as e:
                    shutil.rmtree(tmp, ignore_errors=True)
                    warnings.append("%s: could not be written (%s)" % (doc_id, e))
                    continue
                restored.append(doc_id)
        # what the library keeps beside its documents (the prompt, say): put
        # back only what is missing, since these are not what a restore is for
        for name, info in loose:
            at = lib() / name
            if at.exists() and not replace:
                continue
            try:
                at.parent.mkdir(parents=True, exist_ok=True)
                at.write_bytes(zf.read(info))
            except (OSError, KeyError):
                warnings.append("%s could not be written" % name)
        migrate_after_import(warnings)
        return {"restored": restored, "kept": kept, "warnings": warnings}


def migrate_after_import(warnings):
    """migrate_links after documents came in: a link by uid in them, or one
    elsewhere in the library to a document just restored, is written by name
    now that its target is here.  Never a reason to fail the import."""
    try:
        migrate_links()
    except (OSError, StoreError) as e:
        warnings.append("the links could not be brought up to names (%s)" % e)


def _zip_tags(zf, entries, by_lower, name):
    """The tags lying beside a markdown file in a zip: <stem>.tags.json, as
    doc_zip writes it -- {"tags": [...]}, or a bare list of them.

    Anything else is read as no tags at all.  A zip somebody made by hand,
    or one from a studio that never wrote the file, must still install: tags
    are worth carrying and not worth a refusal.  create() does the rest --
    the trimming, the lower-casing and the sorting every tag gets.
    """
    stem = name[:name.rindex(".")] if "." in name else name
    want = stem + ".tags.json"
    path = want if want in entries else by_lower.get(want.lower())
    if not path:
        return []
    try:
        got = json.loads(zf.read(entries[path]).decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError, OSError, KeyError):
        return []
    if isinstance(got, dict):
        got = got.get("tags")
    return [str(t) for t in got if str(t).strip()] if isinstance(got, list) else []


def _zip_entries(zf):
    """The entries of a zip worth looking at: files, none of them from
    outside the zip's own tree, no Mac resource fork and nothing hidden --
    the rule import_zip goes by, in one place because the unwrapping below
    has to apply the very same one before it can say what a zip holds."""
    out = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = info.filename.replace("\\", "/")
        parts = name.split("/")
        if name.startswith("/") or ".." in parts or parts[0] == "__MACOSX" \
                or any(p.startswith(".") for p in parts):
            continue
        out.append((name, info))
    return out


def _unwrap_zip_of_zips(data):
    """A zip whose every entry is itself a zip -> (one flat zip of what they
    hold, how many were opened).  Anything else -> (None, 0).

    THE LIBRARY'S OWN "Markdown + media (.zip)" OF SEVERAL DOCUMENTS IS ONE
    OF THESE, and it could not be loaded back.  Media has to stay beside the
    markdown that names it -- several documents' images/ and audio/ would
    otherwise land in one heap with every name free to collide -- so the
    download writes each document's own zip inside one zip
    (server.api_download).  The import read only `.md` entries and answered
    "the zip holds no markdown (.md) file" about a file Parseh had just
    written itself.

    Each inner zip is opened under a folder named after it, which is exactly
    the shape the import already reads: a document's folder, with its
    images/ and its audio/ inside it.  Deterministic, down to the order and
    the names, because the header dialog sends the same zip back with its
    answers keyed by the names this gave them."""
    try:
        outer = zipfile.ZipFile(io.BytesIO(data or b""))
    except (zipfile.BadZipFile, ValueError, OSError):
        return None, 0
    with outer:
        entries = _zip_entries(outer)
        if not entries or not all(n.lower().endswith(".zip") for n, _i in entries):
            return None, 0
        if len(entries) > ZIP_MAX_FILES:
            raise StoreError("the zip holds more than %d files" % ZIP_MAX_FILES)
        if sum(i.file_size for _n, i in entries) > ZIP_MAX_BYTES:
            raise StoreError("the zip unpacks to more than %d MB" % (ZIP_MAX_BYTES // 2 ** 20))
        buf, taken, opened, total = io.BytesIO(), set(), 0, 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as flat:
            for name, info in entries:
                stem = posixpath.basename(name)[:-len(".zip")]
                stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-.") or "document"
                folder, n = stem, 1
                while folder.lower() in taken:
                    n += 1
                    folder = "%s-%d" % (stem, n)
                taken.add(folder.lower())
                try:
                    inner = zipfile.ZipFile(io.BytesIO(outer.read(info)))
                except (zipfile.BadZipFile, ValueError, OSError, KeyError, RuntimeError):
                    raise StoreError("%s inside the zip is not a zip that can be read"
                                     % posixpath.basename(name))
                with inner:
                    for held, held_info in _zip_entries(inner):
                        total += held_info.file_size
                        if total > ZIP_MAX_BYTES:
                            raise StoreError("the zip unpacks to more than %d MB"
                                             % (ZIP_MAX_BYTES // 2 ** 20))
                        try:
                            flat.writestr(folder + "/" + held, inner.read(held_info))
                        except (zipfile.BadZipFile, ValueError, OSError, KeyError,
                                RuntimeError) as e:
                            raise StoreError("%s inside the zip could not be read (%s)"
                                             % (posixpath.basename(name), e))
                opened += 1
        return buf.getvalue(), opened


def import_zip(data, headers=None, renames=None):
    """Documents out of a zip -> {"docs": [meta, ...], "warnings": [...]}.

    A ZIP OF ZIPS IS OPENED FIRST (_unwrap_zip_of_zips): that is the shape
    the library's own download of several documents with their media has,
    and the answer says how many were found in it.

    Every .md or .markdown file in it is a document, and the pictures it
    shows are read from beside it -- its folder's images/, or its folder --
    and stored with the document, and so are the recordings it names (its
    folder's audio/, or its folder); a name the store spells otherwise
    (Cat.PNG is kept as cat.png, a WAV called word.mp3 as word.wav) is
    written that way into the markdown.  A picture or a recording the
    markdown shows that the zip does not hold, or that the store refuses, is
    a warning and not a refusal -- unless it is one of the starters' own,
    which comes from where they ship (adopt_starter_media), as it does when
    the same markdown is uploaded on its own.

    `headers` maps a markdown file's path in the zip to the header fields to
    add to it, or to None to leave that file out.  A file whose header is
    incomplete, with no fields given for it, raises HeaderNeeded before
    anything is made -- naming every such file, with what it lacks and what
    to offer -- so the upload can ask for them all and send the zip again.

    Then the names: a file whose title is a document's of this library, or
    another file's in the zip, raises NameConflict before anything is made,
    and `renames` is the dialog's answer (plan_names)."""
    headers = headers if isinstance(headers, dict) else {}
    flat, opened = _unwrap_zip_of_zips(data)
    if flat is not None:
        out = import_zip(flat, headers, renames)
        out["warnings"].insert(0, "the zip held %d document zip%s, and each was opened"
                               % (opened, "" if opened == 1 else "s"))
        return out
    try:
        zf = zipfile.ZipFile(io.BytesIO(data or b""))
    except (zipfile.BadZipFile, ValueError, OSError):
        raise StoreError("that is not a zip file")
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > ZIP_MAX_FILES:
            raise StoreError("the zip holds more than %d files" % ZIP_MAX_FILES)
        if sum(i.file_size for i in infos) > ZIP_MAX_BYTES:
            raise StoreError("the zip unpacks to more than %d MB" % (ZIP_MAX_BYTES // 2 ** 20))
        entries = {}
        for info in infos:
            name = info.filename.replace("\\", "/")
            parts = name.split("/")
            # nothing from outside the zip's own tree, and none of a Mac's
            # resource forks or anybody's hidden files
            if name.startswith("/") or ".." in parts or parts[0] == "__MACOSX" \
                    or any(p.startswith(".") for p in parts):
                continue
            entries[name] = info
        by_lower = {}
        for name in entries:
            by_lower.setdefault(name.lower(), name)
        texts = sorted(n for n in entries if n.lower().endswith((".md", ".markdown")))
        if not texts:
            raise StoreError("the zip holds no markdown (.md) file")
        wanted, needs = [], []
        for name in texts:
            if name in headers and headers[name] is None:
                continue                              # left out in the dialog
            info = entries[name]
            if info.file_size > MD_MAX:
                raise StoreError("%s is larger than %d MB" % (name, MD_MAX // 2 ** 20))
            try:
                text = zf.read(info).decode("utf-8-sig")
            except UnicodeDecodeError:
                raise StoreError("%s is not UTF-8 text" % name)
            markdown = _strip_controls(extract_markdown(text))
            state = header_state(markdown)
            given = headers.get(name)
            if state["missing"] and not isinstance(given, dict):
                needs.append({"name": name, "present": state["present"],
                              "missing": state["missing"], "values": state["values"],
                              "defaults": header_defaults(markdown, name)})
                continue
            wanted.append((name, fill_header(markdown, given) if state["missing"] else markdown))
        if needs:
            raise HeaderNeeded(needs)
        # the names they will have: refused, before anything is made, while
        # one is taken (plan_names); links between the files follow them
        with _names_lock():
            titles = dict((name, mdparser.parse(md)[0].get("title", "")) for name, md in wanted)
            plan = plan_names([{"ref": name, "title": titles[name], "file": name}
                               for name, _md in wanted], renames)
            existing = _retitle(plan["existing"])
            rename_links(existing)
            own = {}
            for name, _md in wanted:
                if titles[name]:
                    own.setdefault(doc_name_key(titles[name]), plan["incoming"][name])
            made, warnings = [], []
            for name, markdown in wanted:
                markdown = _named_as(markdown, titles[name], plan["incoming"][name], own, existing)
                meta = _create(markdown, _zip_tags(zf, entries, by_lower, name))
                doc_id, folder = meta["id"], posixpath.dirname(name)
                renamed = {}
                for kind, keep in (("images", save_image), ("audio", save_audio)):
                    for ref in sorted(set(_named(markdown, kind))):
                        path = None
                        for cand in (posixpath.join(folder, kind, ref), posixpath.join(folder, ref)):
                            path = cand if cand in entries else by_lower.get(cand.lower())
                            if path:
                                break
                        if not path:
                            if starter_media(kind, ref) is None:
                                warnings.append("%s: %s/%s is not in the zip" % (name, kind, ref))
                            continue
                        try:
                            final = keep(doc_id, ref, zf.read(entries[path]))
                        except StoreError as e:
                            warnings.append("%s: %s/%s was not kept (%s)" % (name, kind, ref, e))
                            continue
                        if final != ref:
                            renamed[(kind, ref)] = final
                if renamed:
                    # in one pass: Cat.PNG kept as cat.png while a different
                    # cat.png became cat-2.png must not turn into cat-2.png too
                    meta = save_markdown(doc_id, mdparser.rename_media_refs(get(doc_id)[1], renamed))
                # what the zip left out of the starters' own files; one it
                # carries, even a different one, was stored above and stays
                try:
                    adopt_starter_media(doc_id)
                except OSError as e:
                    warnings.append("%s: the starters' pictures were not copied in (%s)" % (name, e))
                made.append(meta)
            migrate_after_import(warnings)
        return {"docs": made, "warnings": warnings}
