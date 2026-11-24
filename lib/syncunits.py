# SPDX-License-Identifier: GPL-3.0-or-later
"""What syncs, and in what UNITS (a0.7.0): the contract of docs/sync.md, in code.

A UNIT is what sync compares, chooses and replaces as a whole; two changes to
different units never meet.  This module knows every kind of unit Parseh has,
where each lives, which files make it up, which of the rules of sync it
follows -- and nothing else: it never writes, it never keeps state, and it has
no idea that there is a partner.  lib/synclog.py asks it "which units are
there?" and "what does this one hash to now?"; the exchange (lane B) asks it
"which files are this unit, and where?"; the rules (lane C) ask it which rule
a unit follows.

A UNIT ID IS THE SAME ON EVERY COMPUTER.  It names the unit by its place on the
shelf and never by a path on this disk -- `book:persian/the-bell`,
`video:english/street-market-a1b2c3`, `item:persian/verbs/x1y2`,
`setting:parseh_theme` -- so two installs that hold the same thing call it by
the same name wherever their checkouts are.  The files of a unit are named
INSIDE it (`chapter1.tex`, `images/cat.png`), likewise.

THE KINDS AND THEIR RULES (docs/sync.md says each in words):

  rule "choice"     changed on one side: it goes everywhere; on both: the person
                    chooses this computer's or the partner's, never merged
  rule "progress"   a deck's schedule/<id>.json: never asked; the state whose
                    latest answer is newest wins
  rule "latest"     a reading place: never asked; the one set last wins (the
                    reader already asks whether to jump to another device's)
  rule "additions"  an entry of a list (a clip, a Review-later flag, an Anki
                    card, the Anki store's seen notes): each side gets the
                    other's; a deletion is still asked
  rule "immutable"  a file that never changes once written (media nobody
                    edits): named by its hash, copied whole, cannot conflict

Everything not listed here is NEVER synced: caches, `.tmp`, built pages and
PDFs, runtimes, models, dictionaries, and this device's own settings.

Paths come from SHELVES, which `configure()` points at the folders the server
really uses (serve.py passes its modules' own constants, so a test tree that
moved them is followed); config files are found through each store's own
module, so a harness that pointed prefs.STORE at a temporary tree is followed
too.  Standard library only, and no subprocess: a phone will run this.
"""
import collections
import hashlib
import json
import os
import re
import sys

LIB = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(LIB)
if LIB not in sys.path:
    sys.path.insert(0, LIB)

CHOICE, PROGRESS, LATEST, ADDITIONS, IMMUTABLE = "choice", "progress", "latest", "additions", "immutable"
RULES = (CHOICE, PROGRESS, LATEST, ADDITIONS, IMMUTABLE)

# kind -> (rule, what it is in words, the editor that may hold it open or "")
KINDS = collections.OrderedDict([
    ("book",          (CHOICE,    "a book's source", "")),
    ("video",         (CHOICE,    "a video's own edited files", "transcript")),
    ("note",          (CHOICE,    "a note in a book or a video", "note")),
    ("doc",           (CHOICE,    "a studio document", "studio")),
    ("deck",          (CHOICE,    "a deck's options", "deck")),
    ("item",          (CHOICE,    "a deck's exercise", "exercise")),
    ("progress",      (PROGRESS,  "an exercise's progress", "")),
    ("deckfile",      (IMMUTABLE, "a picture or recording of a deck no exercise names", "")),
    ("clip",          (ADDITIONS, "a clip in the tray", "")),
    ("ankideck",      (CHOICE,    "an Anki deck's options", "")),
    ("card",          (ADDITIONS, "a card in the Anki store", "")),
    ("ankimedia",     (IMMUTABLE, "a picture or recording of the Anki store", "")),
    ("ankinotetypes", (CHOICE,    "the Anki store's note types", "")),
    ("ankiseen",      (ADDITIONS, "the notes the Anki store has seen in Anki", "")),
    ("setting",       (CHOICE,    "a personal setting", "")),
    ("place",         (LATEST,    "a reading place", "")),
    ("later",         (ADDITIONS, "a chunk flagged to review later", "")),
    ("prompt",        (CHOICE,    "a prompt", "")),
    ("latextheme",    (CHOICE,    "a LaTeX theme", "")),
    ("language",      (CHOICE,    "a language added on this computer", "")),
])

# A unit: its id, its kind, the rule it follows, where it lives on THIS disk
# (a folder, or for a setting the config file that holds it) and, for a unit
# that is part of a file, the key inside it.
Unit = collections.namedtuple("Unit", "id kind rule where key")


def unit(uid, where, key=None):
    kind = uid.split(":", 1)[0]
    return Unit(uid, kind, KINDS[kind][0], where, key)


def kind_of(uid):
    return uid.split(":", 1)[0]


def rule_of(uid):
    return KINDS[kind_of(uid)][0]


# ------------------------------------------------------------------ where
SHELVES = {
    "books": os.path.join(ROOT, "books"),
    "videos": os.path.join(ROOT, "youtube", "videos"),
    "anki": os.path.join(ROOT, "youtube", "anki"),
    "library": os.path.join(ROOT, "markdown", "library"),
    "exercises": os.path.join(ROOT, "exercises"),
    "clips": os.path.join(ROOT, "clips"),
}


def configure(**dirs):
    """Point the shelves at the folders the server really uses."""
    for k, v in dirs.items():
        if k not in SHELVES:
            raise KeyError(k)
        if v:
            SHELVES[k] = os.path.abspath(os.fspath(v))


def config_files():
    """The personal config stores, by name -> their path now (each module's own,
    so a harness's redirect is followed).  A module that cannot be imported
    here (a stripped-down install) is simply left out."""
    out = {}
    for name, mod, attr in (("prefs.json", "prefs", "STORE"), ("prompts.json", "prompts", "STORE"),
                            ("latex.json", "latexthemes", "STORE"),
                            ("analysis.json", "analysisconfig", "STORE"),
                            ("speech.json", "speechconfig", "CONFIG"),
                            ("languages.json", "languages", "PERSONAL")):
        try:
            m = __import__(mod)
            out[name] = os.path.abspath(os.fspath(getattr(m, attr)))
        except Exception:                       # noqa: BLE001 -- see the docstring
            continue
    return out


def language_files_dirs():
    """Where a personal language's own files live: lib/lang, docs/lang, the
    studio's starters (lib/langprompts.py's constants)."""
    try:
        import langprompts
        return {"lang": langprompts.LANG_FILES, "docs": langprompts.LANG_DOCS,
                "starters": langprompts.STARTERS}
    except Exception:                           # noqa: BLE001
        return {"lang": os.path.join(LIB, "lang"), "docs": os.path.join(ROOT, "docs", "lang"),
                "starters": os.path.join(ROOT, "markdown", "exlex", "starters")}


# ------------------------------------------------------------------ what is never part of a unit
# anywhere: a hidden name (.trash, .staging-*, .reader-key, .meta-*.tmp, an
# agent's .claude/), a temporary or partial file, an editor's backup
def _skip(name):
    return (name.startswith(".") or name.endswith((".tmp", ".part", "~"))
            or ".damaged-" in name)


# per kind, top-level names inside the unit that are built, not made
_BOOK_BUILT_EXT = (".pdf", ".aux", ".log", ".out", ".toc", ".synctex.gz", ".fls",
                   ".fdb_latexmk", ".xdv", ".bbl", ".blg", ".idx", ".ind", ".ilg")
_DERIVED_TOP = {
    "book": {"reader", "markdown", "review.json", "review.html", "build"},
    "video": {"markdown", "waveform.json", "parts", "build"},
    "note": {"build"},
    "doc": {"build"},
}


def _files_under(folder, kind):
    """Every file of a folder unit -> {inner name: absolute path}."""
    out = {}
    top_skip = _DERIVED_TOP.get(kind, set())
    for here, dirs, files in os.walk(folder):
        rel_here = os.path.relpath(here, folder)
        at_top = rel_here == "."
        dirs[:] = sorted(d for d in dirs if not _skip(d) and not (at_top and d in top_skip))
        for f in files:
            if _skip(f) or (at_top and f in top_skip):
                continue
            if at_top and kind == "book" and f.endswith(_BOOK_BUILT_EXT):
                continue
            inner = f if at_top else os.path.join(rel_here, f).replace(os.sep, "/")
            out[inner] = os.path.join(here, f)
    return out


def _dirs(folder):
    try:
        return sorted(n for n in os.listdir(folder)
                      if not _skip(n) and os.path.isdir(os.path.join(folder, n)))
    except OSError:
        return []


def _names(folder):
    try:
        return sorted(n for n in os.listdir(folder)
                      if not _skip(n) and os.path.isfile(os.path.join(folder, n)))
    except OSError:
        return []


# ------------------------------------------------------------------ finding units
def _want(d, within):
    """Is folder `d` worth looking into for a write at `within` (None: all)?"""
    return within is None or _inside(d, within) or _inside(within, d)


def _notes(owner_dir, prefix):
    """The notes kept in a book's or a video's own markdown/ library."""
    root = os.path.join(owner_dir, "markdown")
    for a in _dirs(root):
        d = os.path.join(root, a)
        if os.path.isfile(os.path.join(d, "meta.json")):          # a legacy note, flat
            yield unit("note:%s/%s" % (prefix, a), d)
            continue
        for b in _dirs(d):
            yield unit("note:%s/%s/%s" % (prefix, a, b), os.path.join(d, b))


def _books(within=None):
    root = SHELVES["books"]
    for L in _dirs(root):
        for slug in _dirs(os.path.join(root, L)):
            d = os.path.join(root, L, slug)
            if not _want(d, within):
                continue
            yield unit("book:%s/%s" % (L, slug), d)
            yield from _notes(d, "book/%s/%s" % (L, slug))


def _videos(within=None):
    root = SHELVES["videos"]
    for L in _dirs(root):
        for vid in _dirs(os.path.join(root, L)):
            d = os.path.join(root, L, vid)
            if not _want(d, within):
                continue
            yield unit("video:%s/%s" % (L, vid), d)
            yield from _notes(d, "video/%s/%s" % (L, vid))


def _library(within=None):
    root = SHELVES["library"]
    for a in _dirs(root):
        d = os.path.join(root, a)
        if not _want(d, within):
            continue
        if os.path.isfile(os.path.join(d, "meta.json")):          # a legacy document, flat
            yield unit("doc:%s" % a, d)
            continue
        for b in _dirs(d):
            if _want(os.path.join(d, b), within):
                yield unit("doc:%s/%s" % (a, b), os.path.join(d, b))


_MEDIA_NAME = re.compile(r"[\w.\-]+\.[A-Za-z0-9]{1,8}")


def _deck_media(d):
    """{name: inner path} of a deck's pictures and recordings."""
    out = {}
    for sub in ("images", "audio"):
        for n in _names(os.path.join(d, sub)):
            out.setdefault(n, "%s/%s" % (sub, n))
    return out


def _item_media(item_path, media):
    """The media an exercise names: every file name in its JSON that is one of
    the deck's pictures or recordings (decks.py's _media_refs reads the same
    names out of its markdown; reading the raw JSON catches the footnotes too)."""
    if not media:
        return []
    try:
        with open(item_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return []
    return sorted({media[n] for n in _MEDIA_NAME.findall(text) if n in media})


def _decks(within=None):
    root = SHELVES["exercises"]
    for L in _dirs(root):
        for slug in _dirs(os.path.join(root, L)):
            d = os.path.join(root, L, slug)
            if not _want(d, within):
                continue
            base = "%s/%s" % (L, slug)
            if os.path.isfile(os.path.join(d, "deck.json")):
                yield unit("deck:" + base, d)
            media = _deck_media(d)
            named = set()
            for f in _names(os.path.join(d, "items")):
                if f.endswith(".json"):
                    named.update(_item_media(os.path.join(d, "items", f), media))
                    yield unit("item:%s/%s" % (base, f[:-5]), d)
            for f in _names(os.path.join(d, "schedule")):
                if f.endswith(".json"):
                    yield unit("progress:%s/%s" % (base, f[:-5]), d)
            for inner in sorted(set(media.values()) - named):
                yield unit("deckfile:%s/%s" % (base, inner), d)


def _clips(within=None):
    root = SHELVES["clips"]
    names = [n for n in _names(root) if n != "README.md"]
    have = set(names)
    for n in names:
        if n.endswith(".json") and n[:-5] in have:
            continue                                   # the record of a clip, part of it
        yield unit("clip:%s" % (n[:-5] if n.endswith(".json") else n), root)


def _anki(within=None):
    root = SHELVES["anki"]
    if os.path.isfile(os.path.join(root, "notetypes.json")):
        yield unit("ankinotetypes:", root)
    if os.path.isfile(os.path.join(root, "seen.json")):
        yield unit("ankiseen:", root)
    for L in _dirs(root):
        if L in ("inbox", "build"):
            continue
        for slug in _dirs(os.path.join(root, L)):
            d = os.path.join(root, L, slug)
            if not _want(d, within):
                continue
            base = "%s/%s" % (L, slug)
            if os.path.isfile(os.path.join(d, "deck.json")):
                yield unit("ankideck:" + base, d)
            for f in _names(os.path.join(d, "cards")):
                if f.endswith(".json"):
                    yield unit("card:%s/%s" % (base, f[:-5]), d)
            for f in _names(os.path.join(d, "media")):
                yield unit("ankimedia:%s/%s" % (base, f), d)


# ---- the personal keys of config/ (docs/sync.md labels every key of every file)
def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _prefs_keys():
    import prefs
    return set(prefs.KEYS), prefs.LEVEL_KEY


def _config_units():
    files = config_files()
    p = files.get("prefs.json")
    doc = _load(p) if p else None
    if doc:
        keys, level = _prefs_keys()
        for k in sorted((doc.get("settings") or {})):
            if k in keys or level.fullmatch(k):
                yield unit("setting:%s" % k, p, ("settings", k))
        for k in sorted((doc.get("places") or {})):
            yield unit("place:%s" % k, p, ("places", k))
        items = (doc.get("later") or {}).get("items") or {}
        for k in sorted(items):
            if not (isinstance(items[k], dict) and "gone" in items[k]):   # a tombstone: not held
                yield unit("later:%s" % k, p, ("later", "items", k))
    p = files.get("prompts.json")
    doc = _load(p) if p else None
    if doc:
        for row in doc.get("prompts") or []:
            if isinstance(row, dict) and row.get("id"):
                yield unit("prompt:%s" % row["id"], p, ("prompts", "#id", row["id"]))
        if doc.get("moved"):
            yield unit("setting:prompts.moved", p, ("moved",))
    p = files.get("latex.json")
    doc = _load(p) if p else None
    if doc:
        for row in doc.get("themes") or []:
            if isinstance(row, dict) and row.get("name"):
                yield unit("latextheme:%s" % row["name"], p, ("themes", "#name", row["name"]))
        for k in ("default", "timeout"):
            if k in doc:
                yield unit("setting:latex.%s" % k, p, (k,))
    p = files.get("analysis.json")
    doc = _load(p) if p else None
    if doc:
        for k in sorted(doc):
            if not k.startswith("_") and k not in ("format", "format_version"):
                yield unit("setting:analysis.%s" % k, p, (k,))
    p = files.get("speech.json")
    doc = _load(p) if p else None
    if doc:
        if "second_pass" in doc:
            yield unit("setting:speech.second_pass", p, ("second_pass",))
        for lang in sorted(doc.get("models_by_language") or {}):
            yield unit("setting:speech.model.%s" % lang, p, ("models_by_language", lang))
    p = files.get("languages.json")
    doc = _load(p) if p else None
    if doc:
        for code in sorted(doc):
            if not code.startswith("_"):
                yield unit("language:%s" % code, p, (code,))


WALKERS = (_books, _videos, _library, _decks, _clips, _anki, _config_units)


def walk():
    """Every unit this computer holds now."""
    for w in WALKERS:
        yield from w()


# ------------------------------------------------------------------ a touched path -> its units
def _inside(path, folder):
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def units_for(path):
    """The units a write to `path` (a file or a folder) may have changed, that
    are on the disk now.  A unit that the write REMOVED is not found here --
    synclog adds the ones its log knows under the path."""
    path = os.path.abspath(os.fspath(path))
    files = config_files()
    for name, p in files.items():
        if path == p:
            return [u for u in _config_units() if u.where == p]
    out = []
    for w, shelf in ((_books, "books"), (_videos, "videos"), (_library, "library"),
                     (_decks, "exercises"), (_clips, "clips"), (_anki, "anki")):
        root = SHELVES[shelf]
        if _inside(root, path) or _inside(path, root):
            for u in w(path):
                if _inside(u.where, path):                   # the write covered the unit
                    out.append(u)
                elif _inside(path, u.where) and _claims(u, path):
                    out.append(u)
    return out


def _claims(u, path):
    """Is `path`, inside u.where, one of u's own files (a folder unit always;
    a deck's or the Anki store's per-file units only their own)?"""
    if u.kind in ("book", "video", "note", "doc"):
        return True
    rel = os.path.relpath(path, u.where).replace(os.sep, "/")
    if rel == "." or rel in files_of(u):
        return True
    # a folder of a deck or an Anki deck (items/, images/ ...) touched as a
    # whole: every unit with a file in it
    return "/" not in rel and any(f.startswith(rel + "/") for f in files_of(u))


# ------------------------------------------------------------------ a unit's files and its hash
def files_of(u):
    """{inner name: absolute path} of a file-made unit; {} for a setting."""
    k = u.kind
    if k in ("book", "video", "note", "doc"):
        return _files_under(u.where, k)
    name = u.id.split(":", 1)[1]
    if k in ("deck", "ankideck"):
        p = os.path.join(u.where, "deck.json")
        return {"deck.json": p} if os.path.isfile(p) else {}
    if k == "item":
        iid = name.rsplit("/", 1)[1]
        p = os.path.join(u.where, "items", iid + ".json")
        if not os.path.isfile(p):
            return {}
        out = {"items/%s.json" % iid: p}
        for inner in _item_media(p, _deck_media(u.where)):
            out[inner] = os.path.join(u.where, *inner.split("/"))
        return out
    if k == "progress":
        p = os.path.join(u.where, "schedule", name.rsplit("/", 1)[1] + ".json")
        return {"schedule/%s" % os.path.basename(p): p} if os.path.isfile(p) else {}
    if k == "deckfile":
        inner = name.split("/", 2)[2]
        p = os.path.join(u.where, *inner.split("/"))
        return {inner: p} if os.path.isfile(p) else {}
    if k == "clip":
        out = {}
        for n in (name, name + ".json"):
            p = os.path.join(u.where, n)
            if os.path.isfile(p):
                out[n] = p
        return out
    if k == "card":
        cid = name.rsplit("/", 1)[1]
        p = os.path.join(u.where, "cards", cid + ".json")
        return {"cards/%s.json" % cid: p} if os.path.isfile(p) else {}
    if k == "ankimedia":
        f = name.rsplit("/", 1)[1]
        p = os.path.join(u.where, "media", f)
        return {"media/" + f: p} if os.path.isfile(p) else {}
    if k in ("ankinotetypes", "ankiseen"):
        f = "notetypes.json" if k == "ankinotetypes" else "seen.json"
        p = os.path.join(u.where, f)
        return {f: p} if os.path.isfile(p) else {}
    if k == "language":
        code = u.key[0]
        out = {}
        dirs = language_files_dirs()
        pat = re.compile(r"^%s\.(tex|md|[a-z]+\.json)$" % re.escape(code))
        for tag, folder in sorted(dirs.items()):
            for n in _names(folder):
                if pat.match(n) and (tag == "lang" or n.endswith(".md")):
                    out["%s/%s" % (tag, n)] = os.path.join(folder, n)
        return out
    return {}


def value_of(u):
    """The value of a unit that is part of a config file, or None when it is
    not there (deleted); for a file-made unit, None."""
    if u.key is None:
        return None
    doc = _load(u.where)
    if doc is None:
        return None
    cur = doc
    keys = list(u.key)
    while keys:
        k = keys.pop(0)
        if k.startswith("#") and isinstance(cur, list):         # a row of a list, by a field
            field, want = k[1:], keys.pop(0)
            cur = next((r for r in cur if isinstance(r, dict) and r.get(field) == want), None)
        elif isinstance(cur, dict):
            cur = cur.get(k)
        else:
            return None
        if cur is None:
            return None
    return cur


# what in a value is about WHEN and BY WHOM, not WHAT: left out of its hash, so
# the same theme set on two computers at two moments is the same version
_VOLATILE = {"setting": ("at", "by"), "place": ("by",), "later": ("by",)}


def comparable(u, value):
    """The part of a config value its hash is taken over."""
    drop = _VOLATILE.get(u.kind)
    if drop and isinstance(value, dict):
        return {k: v for k, v in value.items() if k not in drop}
    return value


def deleted_value(u, value):
    """A Review-later tombstone ({"gone": …}) is the flag deleted."""
    return u.kind == "later" and isinstance(value, dict) and "gone" in value


def sha256_file(path, _bufsize=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(_bufsize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def snapshot(u, filehash=sha256_file):
    """What a unit is NOW -> None when it is not there, else
    {"hash", "files": {inner: sha256}} for a file-made unit or
    {"hash", "value"} for a config one.  `filehash` is synclog's cached one."""
    if u.key is not None:
        v = value_of(u)
        if v is None or deleted_value(u, v):
            return None
        c = json.dumps(comparable(u, v), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return {"hash": hashlib.sha256(c.encode("utf-8")).hexdigest(), "value": v}
    files = files_of(u)
    if not files:
        return None
    shas = {}
    for inner, p in files.items():
        try:
            shas[inner] = filehash(p)
        except OSError:
            continue
    if not shas:
        return None
    h = hashlib.sha256()
    for inner in sorted(shas):
        h.update(("%s\0%s\n" % (inner, shas[inner])).encode("utf-8"))
    return {"hash": h.hexdigest(), "files": shas}


def is_synced_path(path):
    """False for a path no unit can ever contain (config/sync, network.json ...)
    -- a quick answer for the hooks."""
    path = os.path.abspath(os.fspath(path))
    if any(path == p for p in config_files().values()):
        return True
    return any(_inside(path, r) or _inside(r, path) for r in SHELVES.values())


# ------------------------------------------------------------------ an id -> where it lives HERE
_KEYED = ("setting", "place", "later", "prompt", "latextheme", "language")


def locate(uid):
    """The Unit an id names on THIS computer, whether or not it is here yet --
    where the exchange writes a unit a partner sent.  KeyError for an id no
    rule of sync knows (and so for anything never synced, and for any id that
    tries to climb out of its shelf)."""
    kind, _, name = uid.partition(":")
    if kind not in KINDS:
        raise KeyError(uid)
    parts = name.split("/") if name else []
    if kind not in _KEYED and any(p in ("", ".", "..") or p.startswith(".") or os.sep in p
                                  or (os.altsep and os.altsep in p) for p in parts):
        raise KeyError(uid)
    S = SHELVES
    if kind in ("book", "video") and len(parts) == 2:
        return unit(uid, os.path.join(S["books" if kind == "book" else "videos"], *parts))
    if kind == "note" and parts and parts[0] in ("book", "video") and len(parts) in (4, 5):
        owner = os.path.join(S["books" if parts[0] == "book" else "videos"], parts[1], parts[2])
        return unit(uid, os.path.join(owner, "markdown", *parts[3:]))
    if kind == "doc" and len(parts) in (1, 2):
        return unit(uid, os.path.join(S["library"], *parts))
    if kind == "deck" and len(parts) == 2:
        return unit(uid, os.path.join(S["exercises"], *parts))
    if kind in ("item", "progress") and len(parts) == 3:
        return unit(uid, os.path.join(S["exercises"], parts[0], parts[1]))
    if kind == "deckfile" and len(parts) == 4 and parts[2] in ("images", "audio"):
        return unit(uid, os.path.join(S["exercises"], parts[0], parts[1]))
    if kind == "clip" and len(parts) == 1:
        return unit(uid, S["clips"])
    if kind == "ankideck" and len(parts) == 2:
        return unit(uid, os.path.join(S["anki"], *parts))
    if kind in ("card", "ankimedia") and len(parts) == 3:
        return unit(uid, os.path.join(S["anki"], parts[0], parts[1]))
    if kind in ("ankinotetypes", "ankiseen") and not name:
        return unit(uid, S["anki"])
    files = config_files()
    if kind == "setting":
        keys, level = _prefs_keys()
        if name in keys or level.fullmatch(name):
            return unit(uid, files["prefs.json"], ("settings", name))
        table = {"prompts.moved": ("prompts.json", ("moved",)),
                 "latex.default": ("latex.json", ("default",)),
                 "latex.timeout": ("latex.json", ("timeout",)),
                 "speech.second_pass": ("speech.json", ("second_pass",))}
        if name in table:
            f, key = table[name]
            return unit(uid, files[f], key)
        if name.startswith("analysis."):
            return unit(uid, files["analysis.json"], (name[len("analysis."):],))
        if name.startswith("speech.model."):
            return unit(uid, files["speech.json"], ("models_by_language", name[len("speech.model."):]))
    if kind == "place" and name:
        return unit(uid, files["prefs.json"], ("places", name))
    if kind == "later" and name:
        return unit(uid, files["prefs.json"], ("later", "items", name))
    if kind == "prompt" and name:
        return unit(uid, files["prompts.json"], ("prompts", "#id", name))
    if kind == "latextheme" and name:
        return unit(uid, files["latex.json"], ("themes", "#name", name))
    if kind == "language" and re.fullmatch(r"[a-z][a-z0-9-]{1,15}", name):
        return unit(uid, files["languages.json"], (name,))
    raise KeyError(uid)


def path_of(u, inner):
    """The absolute path of one of a unit's files on this disk.  Inner names
    are relative to u.where, except a language's: lang/, docs/ or starters/
    and the file's name."""
    parts = inner.split("/")
    if any(p in ("", ".", "..") or os.sep in p for p in parts):
        raise KeyError(inner)
    if u.kind == "language":
        return os.path.join(language_files_dirs()[parts[0]], *parts[1:])
    return os.path.join(u.where, *parts)
