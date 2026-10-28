# SPDX-License-Identifier: GPL-3.0-or-later
"""decks — the exercise decks: studio exercises studied like Anki cards.

Stdlib plus the studio's own modules, and no HTTP (deckroutes.py is the web
side).  A deck is a directory of small JSON files, one per exercise and one
per exercise's schedule, so a crash mid-write can lose at most the answer
being written and a deck can be read and repaired by hand:

    exercises/<language folder>/<deck slug>/
        deck.json            {"format", "id", "name", "lang", "created",
                              "updated", "settings": only what differs}
        items/<id>.json      {"id", "created", "updated", "markdown",
                              "footnotes", "origin", "tags", "link"?}
        schedule/<id>.json   {"state": srs state, "history": [...]}
                             (missing: the exercise is new)
        images/<name>        flashcard pictures, a PDF's .pdf.svg twin
        audio/<name>         recordings (lower case, audiofile.NAME_RE)
    exercises/.trash/<folder>--<slug>--<stamp>/   deleted or replaced decks

Every exercise is one `:::exercise` block in the deck's language, checked
by the same parser the studio renders with.  The pictures and recordings it
shows are the files its markdown and footnotes name (_media_refs), wherever
they are named.  A deck travels as a zip (export_zip / import_zip), with or
without its scheduling.
"""
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import stat
import threading
import unicodedata
import zipfile
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import htmlgen          # first: it puts exlex/ (mdparser, texgen) and lib/ on sys.path
import audiofile
import clips            # lib/, as audiofile: where the tray is served (preview_assets)
import languages
import mdparser
import srs
import store
import texgen

DIR = Path(__file__).resolve().parent.parent.parent / "exercises"
FORMAT = "parseh-exercise-deck/2"
MANIFEST = "parseh-exercise-deck.json"
# THE SHAPE OF schedule/<id>.json -- the srs state and the history of answers
# (answer() writes it) -- as a number (lib/version.py FORMATS).  The deck's
# own files carry FORMAT; a schedule carries no stamp, so its number is kept
# here.  RAISE IT when the shape changes so that the Parseh before this one
# would read a schedule wrong -- somebody's answers are the one thing in a
# deck that cannot be made again.
SCHEDULE_FORMAT = 1

# THE CLIP TRAY.  The book reader and the video player cut recordings and
# pictures into one flat folder at the toolbox's root (lib/clips.py), under
# names unique across the toolbox.  A card made there names `audio/<name>`
# and `images/<name>`; added to a deck, it brings those files in from here
# (add_item, update_item), as a studio document does (store.adopt_media).
CLIPS_DIR = DIR.parent / "clips"

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
ITEM_RE = re.compile(r"^[0-9a-f]{12}$")

MAX_MARKDOWN = 64 * 1024            # one exercise, and its footnotes
MAX_NAME = 200

# WHAT PARSEH WRITES, PARSEH READS BACK.  These are the import's ceilings,
# and they used to be 20 000 entries and 512 MB while the Backup button had
# no ceiling at all: a shelf of some ten thousand studied exercises -- with
# their pictures, their recordings and a schedule file each -- made a backup
# this refused, and the one thing a backup must never be is unreadable.  They
# are now far above anything a shelf of one person's making reaches, and the
# per-entry defences below (MAX_JSON, a picture's, a recording's) are
# untouched: they are what stops a crafted zip, and no honest entry comes
# near them.  A backup that passes BACKUP_WARN_* says so as it is written
# (backup_zip), long before either of these is in sight.
MAX_ENTRIES = 400000                # import limits
MAX_JSON = 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024 * 1024
BACKUP_WARN_ENTRIES = 20000         # "this is getting large", not a refusal
BACKUP_WARN_BYTES = 512 * 1024 * 1024

# the same control characters store strips on every ingest: \x00 and \x01
# are htmlgen's internal sentinels and would break the renderer
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
# a footnote definition, as mdparser reads one
_FN_DEF_RE = re.compile(r"^\[\^([^\]\s]+)\]:\s*(.*)$")
# an exercise field's key, at the start of its line (mdparser's _EX_FIELD_RE)
_FIELD_KEY_RE = re.compile(r"^([a-z][a-z0-9-]*):", re.I)
_ENTRY_ITEM_RE = re.compile(r"items/([0-9a-f]{12})\.json")
_ENTRY_SCHEDULE_RE = re.compile(r"schedule/([0-9a-f]{12})\.json")

NOT_AN_EXERCISE = "this is not an exercise: it must begin with a :::exercise line"
NOT_ALONE = ("this is not one exercise: only a single :::exercise … ::: block "
             "may be saved, with nothing around it")


class DeckError(Exception):
    """Something the user asked for that cannot be done (HTTP 400)."""


class NotFound(DeckError):
    """An unknown deck, exercise or image (HTTP 404)."""


class Conflict(DeckError):
    """The request collides with what is on disk (HTTP 409).

    kind: "exists" (an imported deck is already here), "duplicate" (the
    exercise is already in the deck), "stale" (the page copied from is out
    of date), "reviewed" (the answer is for a state the exercise has left:
    it was answered already, in another tab or by a retried request),
    "linked" (the exercise is one side of a linked pair, and what was asked
    changes it: say whether the other side goes with it -- `linked`, "both"
    or "alone").

    detail: what the page may need to ask the question well, sent beside the
    kind (a "linked" conflict names the other sides)."""

    def __init__(self, message, kind, detail=None):
        super().__init__(message)
        self.kind = kind
        self.detail = detail


def set_dir(path):
    """Point the store at another root; give back the previous one."""
    global DIR
    was, DIR = DIR, Path(path)
    return was


def set_clips_dir(path):
    """Point the clip tray elsewhere (the tests use a temporary one); give
    back the previous one."""
    global CLIPS_DIR
    was, CLIPS_DIR = CLIPS_DIR, Path(path)
    return was


# ---------------------------------------------------------------- small helpers

_LOCKS = {}
_LOCKS_GUARD = threading.Lock()
# held while a slug is chosen and its directory made, so two decks of one
# name (or an import racing a create) cannot claim the same directory
_PLACE = threading.RLock()


def _lock(d):
    """The per-deck lock; re-entrant, so a locked operation may call another."""
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(str(d), threading.RLock())


def _clock(now=None):
    if now is None:
        return datetime.now().astimezone()
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("now must be a timezone-aware datetime")
    return now


def _stamp(now):
    # microseconds always written, so two exercises added in one second
    # still keep the order they were added in
    return now.isoformat(timespec="microseconds")


# The span a stored time must fall in (in UTC).  datetime stops at years 1
# and 9999, and a time at either edge parses but overflows the moment it is
# moved to UTC or to the learner's timezone -- which srs does to every due.
# A year of margin on each side keeps every such conversion inside the range.
_EARLIEST = datetime(2, 1, 1, tzinfo=timezone.utc)
_LATEST = datetime(9998, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)


def _moment(text):
    """An ISO string as an aware datetime, or None -- also for a time that
    cannot be moved between timezones (see _EARLIEST)."""
    if not isinstance(text, str) or not text:
        return None
    try:
        dt = datetime.fromisoformat(text)
        if dt.utcoffset() is None:
            dt = dt.astimezone()
        utc = dt.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None
    return dt if _EARLIEST <= utc <= _LATEST else None


_LAST = datetime.max.replace(tzinfo=timezone.utc)


def _created_key(item):
    when = _moment(item.get("created"))
    return (when.astimezone(timezone.utc) if when else _LAST, item["id"])


def _text_ok(s):
    try:
        s.encode("utf-8")
        return True
    except UnicodeEncodeError:          # a lone surrogate from JSON
        return False


def _write_bytes(path, data):
    """Atomic: a sibling temp file then os.replace, so a reader never sees
    half a file and a crash never leaves one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(".%s.%s.tmp" % (path.name, secrets.token_hex(4)))
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _json_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _write_json(path, obj):
    _write_bytes(path, _json_bytes(obj))


def _read_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return None
    return data if isinstance(data, dict) else None


def _language(code):
    if not isinstance(code, str):
        raise DeckError("unknown language %r" % (code,))
    try:
        return languages.get(code)
    except KeyError:
        raise DeckError("unknown language %r (known: %s)"
                        % (code, ", ".join(languages.CODES)))


def _clean_name(name):
    if not isinstance(name, str) or not _text_ok(name):
        raise DeckError("a deck needs a name")
    name = " ".join(_CTRL_RE.sub("", name).split())
    if not name:
        raise DeckError("a deck needs a name")
    if len(name) > MAX_NAME:
        raise DeckError("a deck name is at most %d characters" % MAX_NAME)
    return name


def slugify(name):
    """A directory name for a deck name.

    Folded (Turkish İ and ı become i) and reduced to ASCII, as the studio's
    document ids are, so "Café" is cafe.  A name with no Latin letter or digit
    at all -- every Persian-named deck -- must not collapse to one constant,
    or they would all claim one directory: the hash keeps each its own."""
    name = str(name)
    s = unicodedata.normalize("NFKD", languages.fold(name))
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60].strip("-")
    return s or "deck-" + hashlib.sha1(name.encode("utf-8", "replace")).hexdigest()[:8]


def deck_dir(folder, slug):
    """The directory of a deck; NotFound for anything that is not a registry
    folder and a slug, so no path built from a URL can leave DIR."""
    L = languages.by_folder(folder) if isinstance(folder, str) else None
    if (L is None or L.folder != folder or not isinstance(slug, str)
            or not SLUG_RE.fullmatch(slug)):
        raise NotFound("deck not found")
    return DIR / L.folder / slug


def _read_deck(d):
    meta = _read_json(d / "deck.json")
    if (meta is None or not isinstance(meta.get("name"), str) or not meta["name"].strip()
            or not ITEM_RE.fullmatch(str(meta.get("id", "")))):
        return None
    return meta


def _need_deck(d):
    meta = _read_deck(d)
    if meta is None:
        raise NotFound("deck not found")
    return meta


def _deck_language(d):
    return languages.by_folder(d.parent.name)


def _settings(meta):
    # a hand-broken option must not make the deck unreadable: defaults instead
    try:
        return srs.settings(meta.get("settings") or {})
    except srs.SettingsError:
        return srs.settings()


def _sparse(full):
    return {k: v for k, v in full.items() if v != srs.DEFAULTS[k]}


def _free_slug(parent, base):
    slug, n = base, 2
    while (parent / slug).exists():
        slug, n = "%s-%d" % (base, n), n + 1
    return slug


def _find_deck(parent, deck_id):
    """(directory, meta) of the deck with this id in one language folder."""
    try:
        names = sorted(os.listdir(parent))
    except OSError:
        return None
    for name in names:
        if name.startswith(".") or not SLUG_RE.fullmatch(name):
            continue
        meta = _read_deck(parent / name)
        if meta is not None and meta["id"] == deck_id:
            return parent / name, meta
    return None


def _to_trash(d):
    """Move a deck under DIR/.trash/ and return where it went.  The name is
    made unique first: a move into an existing directory would bury the
    deck a level down."""
    trash = DIR / ".trash"
    trash.mkdir(parents=True, exist_ok=True)
    base = "%s--%s--%s" % (d.parent.name, d.name, datetime.now().strftime("%Y%m%d-%H%M%S"))
    dest, n = trash / base, 1
    while dest.exists():
        n += 1
        dest = trash / ("%s-%d" % (base, n))
    shutil.move(str(d), str(dest))
    return dest


def rename_doc_links(renames):
    """The exercises' own `[…](doc:Name)` links, following a rename in the
    studio's library: `renames` is {old name key: new name}, as
    store.rename_links has it -> how many exercises were rewritten.

    A deck's exercise is rendered against the studio's library (deckroutes),
    so a link in it names a studio document and must follow that document
    as the documents' own links do.  Each exercise is rewritten in place
    under its deck's lock, its `updated` and its schedule left alone: the
    exercise was not edited, a name it mentions was.  store.follow_renames
    is how it is told, from the server's start-up."""
    if not renames or not DIR.is_dir():
        return 0

    def fix(label, name):
        return renames.get(texgen.doc_name_key(name))
    changed = 0
    for L in languages.LANGS.values():
        try:
            names = sorted(os.listdir(DIR / L.folder))
        except OSError:
            continue
        for name in names:
            d = DIR / L.folder / name
            if name.startswith(".") or not SLUG_RE.fullmatch(name) or not d.is_dir():
                continue
            with _lock(d):
                for item_id in _item_ids(d):
                    path = d / "items" / (item_id + ".json")
                    raw = _read_json(path)
                    if raw is None:
                        continue
                    dirty = False
                    for field in ("markdown", "footnotes"):
                        text = raw.get(field)
                        if isinstance(text, str) and "doc:" in text:
                            text, n = store.rewrite_links(text, fix, front_matter=False,
                                                          lang=L.code)
                            if n:
                                raw[field], dirty = text, True
                    if dirty:
                        _write_json(path, raw)
                        changed += 1
    return changed


# ---------------------------------------------------------------- items on disk

def _item_ids(d):
    try:
        names = os.listdir(d / "items")
    except OSError:
        return []
    return [n[:-5] for n in names if n.endswith(".json") and ITEM_RE.fullmatch(n[:-5])]


def _read_item(d, item_id):
    item = _read_json(d / "items" / (item_id + ".json"))
    if item is None or not isinstance(item.get("markdown"), str):
        return None
    out = {"id": item_id,
           "created": item["created"] if isinstance(item.get("created"), str) else "",
           "updated": item["updated"] if isinstance(item.get("updated"), str) else "",
           "markdown": item["markdown"],
           "footnotes": item["footnotes"] if isinstance(item.get("footnotes"), str) else "",
           "origin": item["origin"] if isinstance(item.get("origin"), dict) else None,
           "tags": _clean_tags(item.get("tags"))}
    link = _clean_link(item.get("link"))
    if link:                # only a linked card carries the key: the files of the rest are as they were
        out["link"] = link
    return out


def _clean_link(value):
    """The id two linked cards share (a both-repeat flashcard's front-first
    and back-first sides), or None.  A group id needs no partner to be
    valid: a card whose other side is gone is a group of one, which is not
    linked at all (_group_of)."""
    return value if isinstance(value, str) and ITEM_RE.fullmatch(value) else None


def _clean_tags(value):
    """Keep the studio's spelling and case rules for exercise tags."""
    if not isinstance(value, list):
        return []
    return sorted(set(languages.lower(tag.strip()) for tag in value
                      if isinstance(tag, str) and tag.strip() and _text_ok(tag)))


def _one_tag(value):
    if not isinstance(value, str) or not value.strip() or not _text_ok(value):
        raise DeckError("tag must be nonempty text")
    return languages.lower(value.strip())


def _need_item(d, item_id):
    item = None
    if isinstance(item_id, str) and ITEM_RE.fullmatch(item_id):
        item = _read_item(d, item_id)
    if item is None:
        raise NotFound("exercise not found")
    return item


def _load_items(d):
    items = [i for i in (_read_item(d, x) for x in _item_ids(d)) if i is not None]
    items.sort(key=_created_key)
    return items


def _groups(items):
    """{link id: the ids sharing it, in the order the items are given} for
    every link that more than one exercise holds."""
    found = {}
    for item in items:
        if item.get("link"):
            found.setdefault(item["link"], []).append(item["id"])
    return {link: ids for link, ids in found.items() if len(ids) > 1}


def _group_of(d, item):
    """The OTHER exercises linked with `item`, as items (oldest first);
    none for an exercise no other holds the link of."""
    link = item.get("link")
    if not link:
        return []
    found = [i for i in (_read_item(d, x) for x in _item_ids(d))
             if i is not None and i.get("link") == link and i["id"] != item["id"]]
    found.sort(key=_created_key)
    return found


def _unlink_lonely(d, links):
    """A group of one is no group: the last exercise still holding one of
    `links` lets go of it (its `updated` stays: it was not edited)."""
    links = set(x for x in links if x)
    if not links:
        return
    held = {}
    for x in _item_ids(d):
        item = _read_item(d, x)
        if item is not None and item.get("link") in links:
            held.setdefault(item["link"], []).append(item)
    for members in held.values():
        if len(members) == 1:
            members[0].pop("link", None)
            _write_json(d / "items" / (members[0]["id"] + ".json"), members[0])


def _read_schedule(d, item_id):
    sched = _read_json(d / "schedule" / (item_id + ".json")) or {}
    state, history = sched.get("state"), sched.get("history")
    return {"state": state if isinstance(state, dict) else srs.new_state(),
            "history": history if isinstance(history, list) else []}


def _state_name(state):
    name = state.get("state") if isinstance(state, dict) else None
    return name if name in srs.STATES else "new"


def _new_item_id(d):
    while True:
        item_id = secrets.token_hex(6)
        if not (d / "items" / (item_id + ".json")).exists() \
                and not (d / "schedule" / (item_id + ".json")).exists():
            return item_id


def _touch(d, meta, now):
    meta["updated"] = _stamp(now)
    _write_json(d / "deck.json", meta)


def _count(value):
    # capped where a JavaScript number still holds it exactly: the study page
    # sends reps back, and review() compares it with this same reading
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return min(value, 2 ** 53 - 1)
    return 0


# ---------------------------------------------------------------- exercise markdown

def _walk(blocks, steps=True):
    """Exercise blocks in render order: a box's exercises where the box is, and -- with `steps`, as the page numbers
    them -- a follow-up's steps after it, each an exercise of the page.  A deck's exercise is the follow-up as a whole:
    its steps are not exercises of the deck's."""
    for b in blocks:
        if b["type"] == "exercise":
            yield b
            if steps:
                yield from _walk(b.get("steps") or [])
        elif b["type"] == "box":
            yield from _walk(b["blocks"], steps)


def exercise_blocks(markdown):
    """(front matter, every exercise block in render order).

    htmlgen numbers exercises data-exercise="1", "2", ... walking the same
    blocks the same way, boxes included, so ordinal N is blocks[N-1]."""
    fm, blocks = mdparser.parse(markdown)
    return fm, list(_walk(blocks))


def _front(code):
    return "---\ntarget: %s\n---\n\n" % code


def _normalise(markdown):
    if not isinstance(markdown, str) or not _text_ok(markdown):
        raise DeckError("the exercise must be text")
    lines = _CTRL_RE.sub("", markdown.replace("\r\n", "\n").replace("\r", "\n")).split("\n")
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    text = "\n".join(lines[start:end])
    if not text:
        raise DeckError("the exercise is empty")
    if len(text.encode("utf-8")) > MAX_MARKDOWN:
        raise DeckError("the exercise is larger than %d KB" % (MAX_MARKDOWN // 1024))
    return text


def _examine(markdown, code):
    """(normalised markdown, its exercise block or None, errors, problem).

    `errors` is what an item summary lists; `problem` is the one message a
    refusal gives, None when the markdown is a single sound exercise."""
    md = _normalise(markdown)
    _fm, blocks = mdparser.parse(_front(code) + md)
    found = list(_walk(blocks, steps=False))
    if not found:
        return md, None, [NOT_AN_EXERCISE], NOT_AN_EXERCISE
    block = found[0]
    if len(found) > 1:
        problem = "this is not one exercise: it holds %d" % len(found)
    elif len(blocks) != 1 or blocks[0] is not block or block["source"] != md:
        # footnote definitions and rules make no block; the source check
        # catches them, and anything else around the exercise
        problem = NOT_ALONE
    elif block["errors"]:
        return (md, block, list(block["errors"]),
                "the exercise needs attention: " + "; ".join(block["errors"]))
    else:
        return md, block, [], None
    return md, block, [problem], problem


def validate_markdown(markdown, lang):
    """The exercise block, or DeckError unless the markdown is exactly one
    sound exercise (blank lines around it allowed) in `lang`."""
    code = _language(lang).code
    _md, block, _errors, problem = _examine(markdown, code)
    if problem:
        raise DeckError(problem)
    return block


def _dup_key(markdown):
    lines = markdown.replace("\r\n", "\n").split("\n")
    return "\n".join(l.rstrip() for l in lines).strip("\n")


def _footnote_defs(text):
    """id -> text of the `[^id]: text` lines (continuations joined), the
    last definition winning as in mdparser."""
    defs = {}
    lines = (text or "").replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        m = _FN_DEF_RE.match(lines[i].strip())
        i += 1
        if not m:
            continue
        body = m.group(2).strip()
        while i < len(lines) and lines[i].strip() and lines[i].startswith((" ", "\t")):
            body += " " + lines[i].strip()
            i += 1
        defs[m.group(1)] = body
    return defs


def _footnotes_for(markdown, defs):
    """The definition lines of the footnotes `markdown` refers to, in order,
    and of those their own text refers to: htmlgen renders a footnote's text
    inline, so `[^a]: see [^b]` shows b's note too.  `seen` stops a cycle."""
    out, seen = [], set()
    todo = list(htmlgen.FN_REF_RE.findall(markdown))
    while todo:
        fid = todo.pop(0)
        if fid in seen or fid not in defs:
            continue
        seen.add(fid)
        out.append("[^%s]: %s" % (fid, defs[fid]))
        todo.extend(htmlgen.FN_REF_RE.findall(defs[fid]))
    return "\n".join(out)


def _clean_footnotes(footnotes, markdown):
    if footnotes is None:
        footnotes = ""
    if not isinstance(footnotes, str) or not _text_ok(footnotes):
        raise DeckError("footnotes must be text")
    notes = _footnotes_for(markdown, _footnote_defs(_CTRL_RE.sub("", footnotes)))
    if len(notes.encode("utf-8")) > MAX_MARKDOWN:
        raise DeckError("the footnotes are larger than %d KB" % (MAX_MARKDOWN // 1024))
    return notes


# the URL prefix of a notes mount an exercise was copied from, such as
# /books/<folder>/<slug>/notes: the deck page builds a link from it, so it
# must stay a path on this server (not //host, not javascript:)
_SOURCE_RE = re.compile(r"/[A-Za-z0-9._~%-][A-Za-z0-9._~%/-]{0,299}")


def _source_ok(source):
    return (isinstance(source, str) and _SOURCE_RE.fullmatch(source) is not None
            and ".." not in source.split("/"))


# Where a card made in a book's reader or a video's player came from (their
# card sheets send it with the exercise): the book's address, the video's id,
# the moment in it (`label`, and a video's `time` in seconds) and `url`, a
# link back to that moment.  The deck page makes links of them, so a book is
# a path on this shelf, a video an id, and a url a path on this server (not
# //host, and nothing a browser would read as one: a backslash, a tab) or a
# YouTube address.
_BOOK_RE = re.compile(r"/books/[A-Za-z0-9_~%-][A-Za-z0-9._~%-]{0,99}"
                      r"/[A-Za-z0-9_~%-][A-Za-z0-9._~%-]{0,199}")
_VIDEO_RE = re.compile(r"(?!\.+$)[A-Za-z0-9._-]{1,90}")
_URL_RE = re.compile(r"(?:/(?![/\\])|https://www\.youtube\.com/)[^\s\\\x00-\x1f\x7f]*")


def _clean_origin(origin):
    if not isinstance(origin, dict):
        return None
    out = {}
    for key in ("doc_id", "doc_uid", "title"):
        if isinstance(origin.get(key), str) and _text_ok(origin[key]):
            out[key] = origin[key][:500]
    if _source_ok(origin.get("source")):
        out["source"] = origin["source"]
    if isinstance(origin.get("ordinal"), int) and not isinstance(origin["ordinal"], bool):
        out["ordinal"] = origin["ordinal"]
    if isinstance(origin.get("duplicate_of"), str) and ITEM_RE.fullmatch(origin["duplicate_of"]):
        out["duplicate_of"] = origin["duplicate_of"]
    book, video, url = origin.get("book"), origin.get("video"), origin.get("url")
    if isinstance(book, str) and _BOOK_RE.fullmatch(book) and ".." not in book.split("/"):
        out["book"] = book
    if isinstance(video, str) and _VIDEO_RE.fullmatch(video):
        out["video"] = video
    if isinstance(origin.get("label"), str) and _text_ok(origin["label"]):
        out["label"] = " ".join(_CTRL_RE.sub("", origin["label"]).split())[:200]
    when = origin.get("time")
    # compared, never converted: an integer of 400 digits is valid JSON, and
    # NaN and infinity fail the comparison
    if isinstance(when, (int, float)) and not isinstance(when, bool) and 0 <= when <= 1e9:
        out["time"] = when
    if isinstance(url, str) and len(url) <= 500 and _URL_RE.fullmatch(url) and _text_ok(url):
        out["url"] = url
    return out or None


# a picture, a recording or a video line, wherever a field's text holds one
_MEDIA_MARKUP_RE = re.compile(r"[!@]\[[^\[\]]*\]\(\s*[^()\s]*\s*\)(?:\{[^{}]*\})?")
# what starts a line of block content: a heading, a box, a list item
_BLOCK_MARK_RE = re.compile(r"^(?:#{1,6}\s+|>\s*|[-*+]\s+|\d+[.)]\s+)")
# a LaTeX drawing is a picture: its fence (four colons, or more in a step of a follow-up) and its line mark say no words
_DRAWING_FENCE_RE = re.compile(r"^(:{4,})latex\b", re.I)
_LATEX_MARK_RE = re.compile(r"\[[^\[\]]*\]\{\s*latex\b[^{}]*\}", re.I)


def _plain(text):
    """Exercise prose as a one-line plain excerpt of at most 160 characters:
    what it says, without the pictures and recordings it shows."""
    t = _MEDIA_MARKUP_RE.sub(" ", text or "")
    t = mdparser.MEDIA_REF_RE.sub(lambda m: " " if "." in m.group(2).rstrip(".") else m.group(0), t)
    if "⏎" in t:                    # a `key: |` field: its lines, less their block marks and the drawings it holds
        parts, fence = [], ""
        for part in t.split("⏎"):
            s = part.strip()
            if fence:
                fence = "" if s == fence else fence
                continue
            drawing = _DRAWING_FENCE_RE.match(s)
            if drawing:
                fence = drawing.group(1)
                continue
            parts.append(_BLOCK_MARK_RE.sub("", s))
        t = " ".join(parts)
    t = _LATEX_MARK_RE.sub("…", t)                              # [\ce{H2O}]{latex}: a picture, not words
    t = htmlgen.FN_INLINE_RE.sub("", t)
    t = htmlgen.FN_REF_RE.sub("", t)
    t = mdparser.SLOT_RE.sub("___", t)                          # fill-blanks slots
    t = re.sub(r"\[([^\[\]]*)\]\{[^{}]*\}", r"\1", t)           # [text]{…} marks
    t = re.sub(r"\[([^\[\]]*)\]\([^()\s]*\)", r"\1", t)         # links
    t = " ".join(t.replace("**", "").split())
    return t if len(t) <= 160 else t[:159].rstrip() + "…"


def _excerpt(block):
    if block is None:
        return ""
    if block["primitive"] == "chain" and block.get("steps"):
        # a follow-up's own prompt, else its first step's words: what the list says it opens with
        own = _plain(block["fields"].get("prompt"))
        return own or _excerpt(block["steps"][0])
    fields = block["fields"]
    keys = (("front", "target", "front-primary", "front-secondary", "prompt")
            if block["primitive"] == "flashcard" else ("prompt", "text"))
    for key in keys:
        # a field that only shows a picture or a recording says nothing
        text = _plain(fields.get(key))
        if text:
            return text
    if block["items"]:
        first = block["items"][0]
        return _plain(first.get("text") or first.get("left") or "")
    return ""


def _side(block):
    """The side a flashcard shows first, as it is written: "reverse",
    "both-random", "both-repeat", "forward" -- "" for an exercise that is
    not a flashcard or says nothing."""
    if block is None or block["primitive"] != "flashcard":
        return ""
    return (block["fields"].get("direction") or "").strip().lower()


def _item_summary(item, sched, code, mates=()):
    """`mates`: the ids of the exercises linked with this one.  A summary
    carries `link` only when there are some (a card whose other side is gone
    is not linked), and `direction`, the side written on a flashcard, for
    the badge that tells the two sides apart."""
    try:
        _md, block, errors, _problem = _examine(item["markdown"], code)
    except DeckError as e:
        block, errors = None, [str(e)]
    subtype = block["subtype"] if block else ""
    state = sched["state"]
    return {"id": item["id"], "subtype": subtype,
            "primitive": block["primitive"] if block else "",
            "direction": _side(block),
            "link": item.get("link") if mates else None, "mates": list(mates),
            "label": htmlgen.EXERCISE_LABELS.get(subtype, subtype or "Exercise"),
            "excerpt": _excerpt(block), "markdown": item["markdown"],
            "steps": len(block.get("steps") or []) if block else 0,
            "footnotes": item["footnotes"], "errors": errors,
            "tags": _clean_tags(item.get("tags")),
            "created": item["created"], "updated": item["updated"],
            "origin": item["origin"], "schedule": state,
            "reps": _count(state.get("reps")), "lapses": _count(state.get("lapses"))}


# ---------------------------------------------------------------- decks

def _buried(items, scheds, now, cfg):
    """The ids held back until the next day starts: the other side of a
    linked pair, when one side was answered today (srs.buried_today).  Read
    from the answers themselves, so a deck holds nothing more for it."""
    groups = list(_groups(items).values())
    if not groups:
        return set()
    return srs.buried_today(groups, {i: s["history"] for i, s in scheds.items()}, now, cfg)


def _deck_summary(d, meta, now):
    L = _deck_language(d)
    cfg = _settings(meta)
    counts = {"total": 0, "new": 0, "learning": 0, "review": 0}
    entries, histories, items, scheds = [], [], [], {}
    for item in _load_items(d):
        sched = _read_schedule(d, item["id"])
        name = _state_name(sched["state"])
        counts["total"] += 1
        counts["learning" if name == "relearning" else name] += 1
        entries.append((item["id"], item["created"], sched["state"]))
        histories.append(sched["history"])
        items.append(item)
        scheds[item["id"]] = sched
    q = srs.queue(entries, now, cfg, srs.today_counts(histories, now, cfg),
                  _buried(items, scheds, now, cfg))
    return {"id": meta["id"], "name": meta["name"], "lang": L.code, "language": L.name,
            "folder": L.folder, "slug": d.name, "path": "%s/%s" % (L.folder, d.name),
            "created": meta.get("created", ""), "updated": meta.get("updated", ""),
            "settings": cfg, "counts": counts, "study": q["counts"],
            "next_due": q["next_due"]}


def list_decks(lang=None, now=None):
    """Every deck (of one language, when given), by name.  Reads only: DIR
    is never created, dot directories (.trash, an import being staged) and
    directories without a readable deck.json are skipped."""
    now = _clock(now)
    wanted = [_language(lang)] if lang else list(languages.LANGS.values())
    if not DIR.is_dir():
        return []
    out = []
    for L in wanted:
        try:
            names = sorted(os.listdir(DIR / L.folder))
        except OSError:
            continue
        for name in names:
            d = DIR / L.folder / name
            if name.startswith(".") or not SLUG_RE.fullmatch(name) or not d.is_dir():
                continue
            meta = _read_deck(d)
            if meta is None:
                continue
            try:                # one broken deck must not blind the rest
                out.append(_deck_summary(d, meta, now))
            # ArithmeticError: a time or a number at the edge of what datetime
            # and float can hold (OverflowError)
            except (OSError, ValueError, TypeError, ArithmeticError) as e:
                print("[decks] skipping %s/%s: %s" % (L.folder, name, e))
    out.sort(key=lambda s: (languages.fold(s["name"]), s["folder"], s["slug"]))
    return out


def create_deck(name, lang):
    name = _clean_name(name)
    L = _language(lang)
    now = _clock()
    with _PLACE:
        parent = DIR / L.folder
        parent.mkdir(parents=True, exist_ok=True)
        d = parent / _free_slug(parent, slugify(name))
        d.mkdir()
        deck_id = secrets.token_hex(6)
        while _find_deck(parent, deck_id):
            deck_id = secrets.token_hex(6)
        meta = {"format": FORMAT, "id": deck_id, "name": name, "lang": L.code,
                "created": _stamp(now), "updated": _stamp(now), "settings": {}}
        _write_json(d / "deck.json", meta)
    return _deck_summary(d, meta, now)


def get_deck(folder, slug, now=None):
    d = deck_dir(folder, slug)
    return _deck_summary(d, _need_deck(d), _clock(now))


def update_deck(folder, slug, name=None, settings=None):
    """Rename (the slug, and so every URL, stays) and/or change options.
    `settings` is merged over the stored ones and checked whole."""
    d = deck_dir(folder, slug)
    now = _clock()
    with _lock(d):
        meta = _need_deck(d)
        if name is not None:
            meta["name"] = _clean_name(name)
        if settings is not None:
            if not isinstance(settings, dict):
                raise DeckError("settings must be an object of named options")
            stored = meta.get("settings")
            try:
                merged = dict(_sparse(srs.settings(stored or {})))
            except srs.SettingsError:
                merged = {}
            merged.update(settings)
            try:
                meta["settings"] = _sparse(srs.settings(merged))
            except srs.SettingsError as e:
                raise DeckError(str(e))
        _touch(d, meta, now)
        return _deck_summary(d, meta, now)


def delete_deck(folder, slug):
    """Move the deck to DIR/.trash/: a deck is months of answers."""
    d = deck_dir(folder, slug)
    with _lock(d):
        _need_deck(d)
        _to_trash(d)


# ---------------------------------------------------------------- exercises

def list_items(folder, slug):
    d = deck_dir(folder, slug)
    _need_deck(d)
    code = _deck_language(d).code
    items = _load_items(d)
    groups = _groups(items)
    return [_item_summary(item, _read_schedule(d, item["id"]), code,
                          [x for x in groups.get(item.get("link"), ()) if x != item["id"]])
            for item in items]


def get_item(folder, slug, item_id):
    d = deck_dir(folder, slug)
    _need_deck(d)
    item = _need_item(d, item_id)
    return _item_summary(item, _read_schedule(d, item["id"]), _deck_language(d).code,
                         [x["id"] for x in _group_of(d, item)])


def _refuse_duplicate(d, meta, *markdowns):
    keys = set(_dup_key(m) for m in markdowns)
    if any(_dup_key(item["markdown"]) in keys for item in _load_items(d)):
        raise Conflict('this exercise is already in "%s"' % meta["name"], "duplicate")


def _faces(md, block, code):
    """The markdown that goes into the deck for one exercise: itself, or --
    a flashcard written `direction: both-repeat` -- its two sides, the one
    that shows the front first and the one that shows the back first, each
    with the line written out.  Only a deck expands it: an exercise in a
    studio document is one exercise, whatever it says."""
    if _side(block) != "both-repeat":
        return [md]
    faces = []
    for side in ("forward", "reverse"):
        face, _block, _errors, problem = _examine(mdparser.set_block_direction(md, side), code)
        if problem:
            raise DeckError(problem)
        faces.append(face)
    return faces


def _insert(d, meta, md, notes, origin, now, tags=None, link=None, mates=(), item_id=None):
    item_id = item_id or _new_item_id(d)
    stamp = _stamp(now)
    item = {"id": item_id, "created": stamp, "updated": stamp, "markdown": md,
            "footnotes": notes, "origin": _clean_origin(origin), "tags": _clean_tags(tags)}
    if link:
        item["link"] = link
    _write_json(d / "items" / (item_id + ".json"), item)
    _touch(d, meta, now)
    return _item_summary(item, _read_schedule(d, item_id), _deck_language(d).code, mates)


def _insert_all(d, meta, faces, notes, origin, now, tags=None):
    """Every exercise goes into a deck through here: -> its summaries, one
    for an exercise, two -- linked, the front-first side before the
    back-first -- for a both-repeat flashcard (_faces).  The second is made
    one microsecond after the first, so Browse and the queue of new cards,
    which sort by that time, keep their order (two of one time would sort by
    their random ids)."""
    if len(faces) == 1:
        return [_insert(d, meta, faces[0], notes, origin, now, tags)]
    link, first_id = secrets.token_hex(6), _new_item_id(d)
    second_id = _new_item_id(d)
    while second_id == first_id:
        second_id = _new_item_id(d)
    first = _insert(d, meta, faces[0], notes, origin, now, tags, link, [second_id], first_id)
    second = _insert(d, meta, faces[1], notes, origin, now + timedelta(microseconds=1), tags,
                     link, [first_id], second_id)
    return [first, second]


def add_item(folder, slug, markdown, footnotes="", origin=None, force=False, now=None,
             tags=None):
    """Add one exercise; Conflict("duplicate") when the same markdown is
    already in the deck, unless forced.  A new exercise has no schedule file.

    The pictures and recordings it names that the deck lacks come in from the
    clip tray when they are there (_adopt); the answer's "warnings" name what
    is still missing.

    A flashcard written `direction: both-repeat` goes in as TWO exercises
    (_insert_all), linked: the answer is the first, with both under "items"
    (a key only such an answer has)."""
    if tags is not None and (not isinstance(tags, list) or
                             any(not isinstance(tag, str) or not _text_ok(tag)
                                 for tag in tags)):
        raise DeckError("tags must be a list of text")
    now = _clock(now)
    d = deck_dir(folder, slug)
    with _lock(d):
        meta = _need_deck(d)
        code = _deck_language(d).code
        md, block, _errors, problem = _examine(markdown, code)
        if problem:
            raise DeckError(problem)
        md, notes, copies = _adopt(d, md, _clean_footnotes(footnotes, md), code)
        faces = _faces(md, block, code)
        if not force:
            _refuse_duplicate(d, meta, *faces)
        _make_copies(d, copies)
        made = _insert_all(d, meta, faces, notes, origin, now, tags)
        summary = dict(made[0], warnings=_missing_media(d, md, notes))
        if len(made) > 1:
            summary["items"] = made
        return summary


# ---------------------------------------------------------------- pictures and recordings named

# which files an exercise names, and their names rewritten: the dialect's
# one finder, the same a studio document goes by (store.adopt_media)
_media_refs = mdparser.media_refs
_media_names = mdparser.media_names
_rename_refs = mdparser.rename_media_refs


def _field_of(text, pos):
    """The exercise field the character at `pos` is in -- the key starting
    its line, or the `key: |` whose indented block holds that line -- or
    None."""
    lines = text[:pos].split("\n")
    line = lines.pop()
    m = _FIELD_KEY_RE.match(line)
    if m:
        return m.group(1).lower()
    if not line.startswith((" ", "\t")):
        return None
    while lines:
        line = lines.pop()
        if line.strip() and not line.startswith((" ", "\t")):
            m = _FIELD_KEY_RE.match(line)
            return m.group(1).lower() if m else None
    return None


def _name_ok(kind, name):
    return bool((store.IMG_NAME_RE if kind == "images" else audiofile.NAME_RE).fullmatch(name))


def _in_deck(d, kind, name):
    folder = d / kind
    return ((folder / name).is_file()
            # a PDF's twin is built when it is first asked for
            or (kind == "images" and name.endswith(".pdf.svg") and (folder / name[:-4]).is_file()))


def _missing_media(d, markdown, footnotes=""):
    """Warnings for the pictures and recordings an exercise names that the
    deck cannot serve: saved as it is, the card would show a broken picture
    or play nothing.  Each names the field it is in, when it is in one."""
    out, seen = [], set()
    for is_notes, text in enumerate((markdown, footnotes)):
        for kind, name, start, _end in _media_refs(text):
            if (kind, name) in seen:
                continue
            seen.add((kind, name))
            field = None if is_notes else _field_of(text, start)
            where = "%s/%s" % (kind, name) if not field else "%s: %s/%s" % (field, kind, name)
            if kind == "images" and not _name_ok(kind, name):
                out.append("%s cannot be a deck picture: only lower-case PNG, JPEG, "
                           "SVG and PDF names are served" % where)
            elif kind == "images" and not _in_deck(d, kind, name):
                out.append("%s is not among this deck's pictures: upload it, "
                           "or the card shows a broken picture" % where)
            elif kind == "audio" and not _name_ok(kind, name):
                out.append("%s cannot be a deck recording: only lower-case %s names are served"
                           % (where, audiofile.HUMAN))
            elif kind == "audio" and not _in_deck(d, kind, name):
                out.append("%s is not among this deck's recordings: upload it, "
                           "or the card plays nothing" % where)
    return out


def _tray_file(d, kind, name):
    """The clip tray's file for a picture or recording an exercise names and
    the deck lacks, when the tray holds one of that name no larger than a
    deck takes; else None.  Whether its bytes are what its name says is
    _says_it."""
    if kind not in ("images", "audio") or _in_deck(d, kind, name) or not _name_ok(kind, name) \
            or (kind == "images" and store.DERIVED_RE.search(name)):
        return None
    path = Path(CLIPS_DIR) / name
    limit = store.IMG_MAX if kind == "images" else audiofile.MAX_BYTES
    try:
        if not path.is_file() or path.stat().st_size > limit:
            return None
    except OSError:
        return None
    return path


def _says_it(kind, name, data):
    """Whether bytes (the first 4096 are enough) are a recording or a
    picture, as `kind` and the name say."""
    return (audiofile.kind(data, name) if kind == "audio" else store._img_kind(data)) is not None


def _from_tray(d):
    """The fetch (_plan_media) of the clip tray: a file the exercise names,
    the deck lacks and the tray holds, when it is what its name says."""
    def fetch(kind, name):
        path = _tray_file(d, kind, name)
        try:
            data = path.read_bytes() if path is not None else None
        except OSError:
            return None
        return (data, None) if data is not None and _says_it(kind, name, data) else None
    return fetch


def preview_assets(folder, slug, base):
    """The asset base (htmlgen.render_document) of an exercise not saved yet:
    `base` and a file's path -- unless the deck lacks the file and the clip
    tray holds it, which saving brings in (add_item, update_item: _adopt).
    Such a file is loaded from where Parseh serves the tray (clips.URL), so a recording pasted
    into the form plays in its preview before the exercise is added, as it
    does in a studio document's."""
    d = deck_dir(folder, slug)

    def url(path):
        kind, _, name = path.partition("/")
        found = _tray_file(d, kind, name)
        if found is not None:
            try:
                with open(found, "rb") as f:
                    head = f.read(4096)
            except OSError:
                head = b""
            if _says_it(kind, name, head):
                return clips.URL + name
        return base + path
    return url


def _adopt(d, md, notes, code):
    """(markdown, footnotes, copies to make): what the exercise names and
    the deck lacks, taken from the clip tray.  A tray name is unique across
    the toolbox, so it comes in under that name; placed like a copy from a
    document all the same, and the markdown is checked again if a name had
    to change."""
    (new_md, new_notes), copies, _warnings = _plan_media(d, (md, notes), _from_tray(d))
    if new_md != md:
        new_md, _block, _errors, problem = _examine(new_md, code)
        if problem:
            raise DeckError(problem)
    if new_notes != notes:
        new_notes = _clean_footnotes(new_notes, new_md)
    return new_md, new_notes, copies


def _card_key(block):
    """What makes an exercise the card it is, but for the side it shows
    first: its type, its fields and its answers as the parser read them."""
    if block is None:
        return None
    return (block["subtype"],
            {k: v for k, v in block["fields"].items() if k != "direction"},
            {k: v for k, v in block["raw_fields"].items() if k != "direction"},
            block["items"])


def _mates_detail(mates, code):
    """What a "linked" conflict tells the page about the other sides."""
    rows = []
    for mate in mates:
        try:
            _md, block, _errors, _problem = _examine(mate["markdown"], code)
        except DeckError:
            block = None
        rows.append({"id": mate["id"], "excerpt": _excerpt(block),
                     "side": "back" if _side(block) == "reverse" else "front"})
    return {"mates": rows}


def _keep_side(md, side, code):
    """`md`, an exercise, showing `side` first ("" for a card that says
    nothing, which is the front)."""
    _md, block, _errors, _problem = _examine(md, code)
    if _side(block) == side:
        return md
    kept, _block, _errors, problem = _examine(
        mdparser.set_block_direction(md, side or "forward"), code)
    if problem:
        raise DeckError(problem)
    return kept


def _need_linked(linked):
    if linked not in (None, "both", "alone"):
        raise DeckError('linked must be "both" or "alone"')


def update_item(folder, slug, item_id, markdown, now=None, linked=None):
    """New markdown for an exercise.  Its origin and its schedule stay; the
    footnote definitions it no longer refers to go.  What it names and the
    deck lacks comes in from the clip tray, as on add_item.

    An exercise that is one side of a linked pair may not be changed without
    saying what becomes of the other: Conflict("linked") when the card
    itself changes and `linked` is not given.  "both" writes the change to
    the other side too -- each keeps the side it shows first; "alone"
    changes this one only, and the two are linked no more.  Formatting is not
    a change, and saves as it always did."""
    _need_linked(linked)
    now = _clock(now)
    d = deck_dir(folder, slug)
    with _lock(d):
        meta = _need_deck(d)
        code = _deck_language(d).code
        item = _need_item(d, item_id)
        md, block, _errors, problem = _examine(markdown, code)
        if problem:
            raise DeckError(problem)
        mates = _group_of(d, item)
        was = _examine(item["markdown"], code)[1]
        if mates and linked is None and (_card_key(was) != _card_key(block)
                                         or _side(was) != _side(block)):
            raise Conflict("this exercise is linked with another: is the change "
                           "for both of them?", "linked", _mates_detail(mates, code))
        both, alone = bool(mates) and linked == "both", bool(mates) and linked == "alone"
        defs = {}
        for x in (mates if both else []) + [item]:
            defs.update(_footnote_defs(x["footnotes"]))
        targets = [(item, _keep_side(md, _side(was), code) if both else md)]
        if both:
            targets += [(m, _keep_side(md, _side(_examine(m["markdown"], code)[1]), code))
                        for m in mates]
        for target, text in targets:
            text, notes, copies = _adopt(d, text, _footnotes_for(text, defs), code)
            _make_copies(d, copies)
            target.update(markdown=text, updated=_stamp(now), footnotes=notes)
            if alone and target is item:
                target.pop("link", None)
            _write_json(d / "items" / (target["id"] + ".json"), target)
        if alone:
            _unlink_lonely(d, [mates[0].get("link")])
        _touch(d, meta, now)
        summary = _item_summary(item, _read_schedule(d, item["id"]), code,
                                [m["id"] for m in mates] if not alone else [])
        summary["warnings"] = _missing_media(d, item["markdown"], item["footnotes"])
        return summary


def duplicate_item(folder, slug, item_id, now=None):
    """A copy with a new id and a fresh schedule; origin says what it copies.
    The copy is linked with nothing, whatever the original is."""
    now = _clock(now)
    d = deck_dir(folder, slug)
    with _lock(d):
        meta = _need_deck(d)
        src = _need_item(d, item_id)
        origin = dict(src["origin"] or {}, duplicate_of=src["id"])
        return _insert(d, meta, src["markdown"], src["footnotes"], origin, now,
                       src["tags"])


def _remove(d, item):
    (d / "items" / (item["id"] + ".json")).unlink()
    (d / "schedule" / (item["id"] + ".json")).unlink(missing_ok=True)


def delete_item(folder, slug, item_id, linked=None):
    """Delete one exercise -> the ids that went.  An exercise with another
    side is a Conflict("linked") until `linked` says whether that goes too
    ("both") or stays, linked with nothing ("alone")."""
    _need_linked(linked)
    d = deck_dir(folder, slug)
    with _lock(d):
        meta = _need_deck(d)
        item = _need_item(d, item_id)
        mates = _group_of(d, item)
        if mates and linked is None:
            raise Conflict("this exercise is linked with another: delete both?",
                           "linked", _mates_detail(mates, _deck_language(d).code))
        gone = [item] + (mates if linked == "both" else [])
        for x in gone:
            _remove(d, x)
        _unlink_lonely(d, [item.get("link")])
        _touch(d, meta, _clock())
        return [x["id"] for x in gone]


def _selected_items(d, ids):
    if not isinstance(ids, list) or not ids or len(ids) > MAX_ENTRIES \
            or any(not isinstance(i, str) or not ITEM_RE.fullmatch(i) for i in ids) \
            or len(set(ids)) != len(ids):
        raise DeckError("select distinct exercise ids from this deck")
    return [_need_item(d, item_id) for item_id in ids]


def _with_other_sides(d, chosen, linked):
    """`chosen`, for a deletion: an exercise picked while its other side is
    not is a Conflict("linked") -- once, for the whole selection -- until
    `linked` says the other sides go too ("both") or stay ("alone")."""
    if not any(item.get("link") for item in chosen):
        return chosen
    everything = {i["id"]: i for i in _load_items(d)}
    groups = _groups(everything.values())
    picked = set(i["id"] for i in chosen)
    outside = []
    for item in chosen:
        for x in groups.get(item.get("link"), ()):
            if x not in picked:
                picked.add(x)
                outside.append(everything[x])
    if not outside:
        return chosen
    if linked is None:
        # the page names a few of them, and says how many there are
        detail = _mates_detail(outside[:5], _deck_language(d).code)
        detail["count"] = len(outside)
        raise Conflict("the other side of %d of the selected exercises is not selected"
                       % len(outside), "linked", detail)
    return chosen + outside if linked == "both" else chosen


def bulk_items(folder, slug, ids, action, tag=None, linked=None):
    """Delete, reset scheduling, or change tags on selected exercises -> how
    many were changed (a deletion counts the other sides that went too).

    A deletion that would leave the other side of a linked pair behind is
    a Conflict("linked") until `linked` says ("both" or "alone") what
    becomes of them; only a deletion asks."""
    if action not in ("delete", "set-new", "add-tag", "remove-tag"):
        raise DeckError("unknown bulk exercise action")
    _need_linked(linked)
    cleaned = _one_tag(tag) if action in ("add-tag", "remove-tag") else None
    d = deck_dir(folder, slug)
    with _lock(d):
        meta = _need_deck(d)
        chosen = _selected_items(d, ids)
        if action == "delete":
            chosen = _with_other_sides(d, chosen, linked)
        for item in chosen:
            path = d / "items" / (item["id"] + ".json")
            if action == "delete":
                _remove(d, item)
            elif action == "set-new":
                (d / "schedule" / (item["id"] + ".json")).unlink(missing_ok=True)
            else:
                tags = set(item["tags"])
                if action == "add-tag":
                    tags.add(cleaned)
                else:
                    tags.discard(cleaned)
                item["tags"] = sorted(tags)
                _write_json(path, item)
        if action == "delete":
            _unlink_lonely(d, [item.get("link") for item in chosen])
        _touch(d, meta, _clock())
        return len(chosen)


def _from_deck(d):
    """Fetch one named media file when carrying an exercise to another deck."""
    def fetch(kind, name):
        path = "%s/%s" % (kind, name)
        if not _name_ok(kind, name):
            return "%s cannot be copied; the path was kept" % path
        f = d / kind / name
        if not f.is_file():
            return "%s is missing from the source deck; the path was kept" % path
        data = f.read_bytes()
        twin = store.pdf_twin(f) if kind == "images" and name.endswith(".pdf") else None
        return data, twin.read_bytes() if twin is not None and twin.is_file() else None
    return fetch


def transfer_items(folder, slug, ids, target_folder, target_slug, move=False):
    """Copy selected exercises to another deck; a move retains scheduling.

    Both sides of a linked pair among them arrive as a linked pair (under a
    link of their own: a link never crosses decks); a side chosen without
    the other arrives linked with nothing, and a move leaves the side it did
    not take unlinked."""
    src, dst = deck_dir(folder, slug), deck_dir(target_folder, target_slug)
    if src == dst:
        raise DeckError("choose another deck")
    first, second = sorted((src, dst), key=str)
    with _PLACE, _lock(first), _lock(second):
        src_meta, dst_meta = _need_deck(src), _need_deck(dst)
        if _deck_language(src).code != _deck_language(dst).code:
            raise DeckError("the destination deck must have the same language")
        chosen = _selected_items(src, ids)
        now = _clock()
        copied, warnings = [], []
        fetch = _from_deck(src)
        pairs = _groups(chosen)
        links = {link: secrets.token_hex(6) for link in pairs}
        for n, item in enumerate(sorted(chosen, key=_created_key) if pairs else chosen):
            (md, notes), media, warn = _plan_media(
                dst, (item["markdown"], item["footnotes"]), fetch)
            _make_copies(dst, media)
            # one microsecond apart when sides are carried: they keep their order
            made = _insert(dst, dst_meta, md, notes, item["origin"],
                           now + timedelta(microseconds=n) if pairs else now, item["tags"],
                           links.get(item.get("link")))
            if move:
                schedule = src / "schedule" / (item["id"] + ".json")
                if schedule.is_file():
                    _write_bytes(dst / "schedule" / (made["id"] + ".json"),
                                 schedule.read_bytes())
                (src / "items" / (item["id"] + ".json")).unlink()
                schedule.unlink(missing_ok=True)
            copied.append(made["id"])
            warnings.extend(warn)
        if move:
            _unlink_lonely(src, [item.get("link") for item in chosen])
            _touch(src, src_meta, now)
        return {"ids": copied, "warnings": warnings}


def cram_items(folder, slug, ids):
    """All selected exercises for an unscheduled practice session."""
    d = deck_dir(folder, slug)
    _need_deck(d)
    code = _deck_language(d).code
    out = []
    for item in _selected_items(d, ids):
        summary = _item_summary(item, _read_schedule(d, item["id"]), code)
        out.append(summary)
    return out


# ---------------------------------------------------------------- copying from a document

_OTHER = object()       # a name taken by something that is not a file
_DIFFERENT = object()   # a file of another size: not these bytes, and not read


def _held(dest, claimed, name, like=None):
    """What the deck's images/ or audio/ (`dest`) holds, or is about to
    hold, under `name`: its bytes, None for nothing, _OTHER for something
    that is not a file.  Given `like`, a file of another length is
    _DIFFERENT without being read -- a recording is megabytes."""
    if name in claimed:
        return claimed[name]
    there = dest / name
    if there.is_file():
        if like is not None and there.stat().st_size != len(like):
            return _DIFFERENT
        return there.read_bytes()
    return _OTHER if os.path.lexists(there) else None


def _free_image_name(dest, name, data, claimed, twin=None):
    """Where `data` goes in the deck's images/ or audio/: its own name when
    free or already holding these bytes, else <stem>-2<ext>, -3 ...

    A PDF is shown through the SVG beside it called <name>.pdf.svg, so the two
    names go together.  A PDF's name is free only while its twin's name is
    free too, or holds `twin` (the bytes of the PDF's own twin, None when it
    has none); an SVG may not take the twin's name of a PDF that is there --
    either way one picture would be shown for another.  A recording's name
    never ends so, and is placed by the first rule alone."""
    stem, ext = os.path.splitext(name)
    candidate, n = name, 2
    while True:
        held = _held(dest, claimed, candidate, data)
        if held is None and candidate.endswith(".pdf"):
            beside = _held(dest, claimed, candidate + ".svg", twin)
            if beside is None or (twin is not None and beside == twin):
                return candidate
        elif held is None and candidate.endswith(".pdf.svg"):
            if _held(dest, claimed, candidate[:-len(".svg")]) is None:
                return candidate
        elif held is None or held == data:
            return candidate
        candidate, n = "%s-%d%s" % (stem, n, ext), n + 1


def _plan_media(d, texts, fetch):
    """(the texts with renamed references, copies to make, warnings) for
    the pictures and recordings the texts -- an exercise's markdown and its
    footnotes -- name.

    `fetch(kind, name)` says what to bring into the deck for one of them:
    None (nothing), a warning, or (bytes, twin bytes or None).  Each file is
    placed by _free_image_name, and where it had to take another name, every
    reference to it is rewritten.  Nothing is written: the copies are made
    only once the exercise is known not to be refused (a duplicate)."""
    claimed = {"images": {}, "audio": {}}
    renamed, copies, warnings = {}, [], []
    for kind, name in _media_names(texts):
        got = fetch(kind, name)
        if got is None:
            continue
        if isinstance(got, str):
            warnings.append(got)
            continue
        data, twin = got
        dest = d / kind
        final = _free_image_name(dest, name, data, claimed[kind], twin)
        claimed[kind][final] = data
        if twin is not None and _held(dest, claimed[kind], final + ".svg") is None:
            claimed[kind][final + ".svg"] = twin
        copies.append((kind, final, data, twin))
        renamed[(kind, name)] = final
    return [_rename_refs(text, renamed) for text in texts], copies, warnings


def _from_doc(doc_id):
    """The fetch (_plan_media) of a studio document's own images/ and
    audio/ (of the library this thread reads)."""
    dirs = {"images": store.images_dir(doc_id), "audio": store.audio_dir(doc_id)}

    def fetch(kind, name):
        path = "%s/%s" % (kind, name)
        if not _name_ok(kind, name):
            return "%s: only lower-case %s names can be copied; the path was kept" % (
                path, "PNG, JPEG, SVG and PDF" if kind == "images" else audiofile.HUMAN)
        f = dirs[kind] / name
        if not f.is_file():
            return "%s is missing from the document; the path was kept" % path
        if kind == "audio":
            if f.stat().st_size > audiofile.MAX_BYTES:
                return "%s is larger than %d MB; the path was kept" % (
                    path, audiofile.MAX_BYTES // 2 ** 20)
            data = f.read_bytes()
            if audiofile.kind(data, name) is None:
                return "%s is not a recording; the path was kept" % path
            return data, None
        data = f.read_bytes()
        twin = store.pdf_twin(f) if name.endswith(".pdf") else None
        twin = twin.read_bytes() if twin is not None and twin.is_file() else None
        return data, twin
    return fetch


def _make_copies(d, copies):
    for kind, final, data, twin in copies:
        target = d / kind / final
        if not target.exists():
            _write_bytes(target, data)
        if twin is not None and not store.pdf_twin(target).exists():
            _write_bytes(store.pdf_twin(target), twin)


def add_image(folder, slug, name, data):
    """Store an uploaded picture in the deck's images/; give back its name.

    Checked as the studio checks a document's upload (store.save_image): the
    bytes say what the file is and the extension follows them, the name is
    reduced to what store.IMG_NAME_RE allows.  The same bytes already there
    are reused; another picture of that name makes this one <stem>-2<ext>."""
    d = deck_dir(folder, slug)
    _need_deck(d)
    if isinstance(data, (bytearray, memoryview)):
        data = bytes(data)
    if not isinstance(data, bytes) or not data:
        raise DeckError("the upload is empty: send the picture as the body")
    if len(data) > store.IMG_MAX:
        raise DeckError("the picture is larger than %d MB" % (store.IMG_MAX // 2 ** 20))
    ext = store._img_kind(data)
    if ext is None:
        raise DeckError("only PNG, JPEG, SVG and PDF pictures can be added")
    stem = Path(name).stem if isinstance(name, str) and _text_ok(name) else ""
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii").lower()
    stem = re.sub(r"[^a-z0-9._-]+", "-", stem)[:80]
    stem = re.sub(r"^[^a-z0-9]+", "", stem).rstrip("-.") or "img"
    if store.DERIVED_RE.search(stem + ext):
        # x.pdf.svg is the name of x.pdf's twin, and x.pdf.png the name of an
        # old raster twin the studio deletes: an upload takes neither
        stem = stem.replace(".", "-")
    final = stem + ext
    if not store.IMG_NAME_RE.fullmatch(final):
        final = "img" + ext
    with _lock(d):
        _need_deck(d)
        final = _free_image_name(d / "images", final, data, {})
        path = d / "images" / final
        if not path.is_file():
            _write_bytes(path, data)
        if ext == ".pdf":
            store.ensure_pdf_twin(path)     # best effort, as on the studio's upload
    return final


def add_audio(folder, slug, name, data):
    """Store an uploaded recording in the deck's audio/; give back its name.

    Checked as the studio checks a document's (store.save_audio): the bytes
    say what the file is and the extension follows them (audiofile.kind), and
    what decodes to no sound is refused (store.holds_sound); the stem is
    folded to lower-case ASCII.  The same bytes already there are reused;
    another recording of that name makes this one <stem>-2<ext>."""
    d = deck_dir(folder, slug)
    _need_deck(d)
    if isinstance(data, (bytearray, memoryview)):
        data = bytes(data)
    if not isinstance(data, bytes) or not data:
        raise DeckError("the upload is empty: send the recording as the body")
    if len(data) > audiofile.MAX_BYTES:
        raise DeckError("the recording is larger than %d MB" % (audiofile.MAX_BYTES // 2 ** 20))
    name = name if isinstance(name, str) and _text_ok(name) else ""
    ext = audiofile.kind(data, name)
    if ext is None:
        raise DeckError("only %s recordings can be added" % audiofile.HUMAN)
    final = audiofile.clean_stem(name, "audio") + ext
    if not audiofile.NAME_RE.fullmatch(final):
        final = "audio" + ext
    # decoded before the deck is locked: a long recording takes a while
    if not store.holds_sound(data, ext):
        raise DeckError(store.NO_SOUND)
    with _lock(d):
        _need_deck(d)
        final = _free_image_name(d / "audio", final, data, {})
        path = d / "audio" / final
        if not path.is_file():
            _write_bytes(path, data)
    return final


def _into_doc(d, doc_id, texts):
    """(the texts with renamed references, warnings) for an exercise copied
    the OTHER way: out of the deck and into a studio document.

    Each picture and recording the exercise names is read from the deck and
    put through the document's own door (store.save_image, store.save_audio)
    -- which sanitises the name, gives back the name already there when the
    bytes are the same, and takes <stem>-2 when they are not -- so a document
    that already holds a different cat.png keeps it.  Where the file landed
    under another name, every reference to it is rewritten (_rename_refs).

    Nothing here refuses the exercise: a picture the deck has lost is a
    warning and the path is kept, exactly as the copy into a deck does it,
    because a broken picture is easier to see and mend in the document than
    a refusal is to understand.
    """
    renamed, warnings = {}, []
    for kind, name in _media_names(texts):
        path = "%s/%s" % (kind, name)
        f = d / kind / name
        if not _name_ok(kind, name) or not f.is_file():
            warnings.append("%s is not among this deck's %s; the path was kept"
                            % (path, "pictures" if kind == "images" else "recordings"))
            continue
        try:
            data = f.read_bytes()
            final = (store.save_image if kind == "images"
                     else store.save_audio)(doc_id, name, data)
        except (OSError, store.StoreError) as e:
            warnings.append("%s: %s; the path was kept" % (path, e))
            continue
        # a PDF is shown through the SVG beside it.  save_image writes one
        # from the PDF, which wants PyMuPDF; the deck already has one, so
        # carry it over rather than leave the figure blank where that tool
        # is not installed
        if kind == "images" and final.endswith(".pdf"):
            twin, there = store.pdf_twin(f), store.pdf_twin(store.images_dir(doc_id) / final)
            if twin.is_file() and not there.is_file():
                _write_bytes(there, twin.read_bytes())
        if final != name:
            renamed[(kind, name)] = final
    return [_rename_refs(text, renamed) for text in texts], warnings


def copy_to_doc(folder, slug, item_id, doc_id, library=None):
    """One exercise of a deck as markdown to put into a studio document.

        {markdown, footnotes, warnings}

    The mirror of copy_from_doc, and the same two pieces: the exercise's own
    source, and the definitions of the footnotes it refers to (for whoever
    inserts it to place among the document's own).  The pictures and
    recordings it names are copied into that document's images/ and audio/
    first, so the exercise reads there as it read on the card.

    Nothing is written to the deck, and nothing to the document's source:
    the markdown is given back, and goes in where the cursor is.

    KeyError (unknown document) propagates.  `library` is the studio library
    the document is in when it is not the studio's own -- the notes beside a
    book or a video -- as it is for copy_from_doc.
    """
    d = deck_dir(folder, slug)
    deck = _need_deck(d)
    item = _need_item(d, item_id)
    if library is None:
        return _to_doc(d, deck, item, doc_id)
    was = store.use_library(library)
    try:
        return _to_doc(d, deck, item, doc_id)
    finally:
        store.use_library(was)


def _to_doc(d, deck, item, doc_id):
    meta, _markdown = store.get(doc_id)         # KeyError: no such document
    L = _deck_language(d)
    target = meta.get("target") or ""
    if target != L.code:
        raise DeckError('this deck is in %s, but the document is in %s'
                        % (L.name, languages.get_or_default(target).name))
    (markdown, notes), warnings = _into_doc(d, doc_id,
                                            (item["markdown"], item["footnotes"]))
    return {"markdown": markdown, "footnotes": notes, "warnings": warnings}


def _ordinal(value):
    if isinstance(value, bool):
        raise DeckError("ordinal must be a whole number")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        # ASCII only: str.isdigit() is true of "²", which int() refuses
        text = value.strip()
        if text.isascii() and text.isdigit():
            return int(text)
    raise DeckError("ordinal must be a whole number")


def copy_from_doc(folder, slug, doc_id, ordinal, subtype, updated, force=False, now=None,
                  library=None, source=None, ordinals=None):
    """Copy the `ordinal`-th exercise (1-based, render order) of a studio
    document into the deck, with the footnotes it refers to and the pictures
    and recordings they name.  A flashcard written `direction: both-repeat`
    goes in as two linked exercises (_insert_all): "items" holds every one
    that went in, "item" the first.

    KeyError (unknown document) propagates.  Conflict("stale") when the page
    the request came from no longer matches the document.

    `ordinals`, a list (and `ordinal` None), makes ONE follow-up of those exercises of the page, each a step, in the
    order given: the deck gets one exercise, with the files of every step (a0.5.4).

    `library`: the studio library the document is in, when it is not the
    studio's own -- the notes beside a book or a video; `source` is the URL
    prefix those notes are served under, kept in the origin so the deck page
    links back to them."""
    now = _clock(now)
    d = deck_dir(folder, slug)
    _need_deck(d)                       # an unknown deck is a 404, not a stale page
    if source is not None and not _source_ok(source):
        raise DeckError("those notes are not on this shelf")
    copy = (lambda: _copy(d, doc_id, ordinal, subtype, updated, force, now, source)) if ordinals is None else \
           (lambda: _copy_chain(d, doc_id, ordinals, updated, force, now, source))
    if library is None:
        return copy()
    # store.use_library is per thread: the document and its pictures are
    # read from the notes, and this thread is given back its own library
    was = store.use_library(library)
    try:
        return copy()
    finally:
        store.use_library(was)


def _copy(d, doc_id, ordinal, subtype, updated, force, now, prefix):
    meta, markdown = store.get(doc_id)
    stale = "the document has changed since the page was loaded: reload it, then copy"
    if updated and updated != meta.get("updated"):
        raise Conflict(stale, "stale")
    n = _ordinal(ordinal)
    fm, blocks = exercise_blocks(markdown)
    if subtype == "gloss-flashcard":
        glosses = htmlgen.glosses(markdown)
        if not 1 <= n <= len(glosses):
            raise Conflict(stale, "stale")
        gloss = glosses[n - 1]
        # A gloss is generated from the saved document, never from fields
        # supplied by the browser. This is the same vocab card the glossary
        # shows, with reading and transliteration when available.
        fields = [("target", gloss["fa"]), ("reading", gloss["kana"]),
                  ("transliteration", gloss["translit"]), ("meaning", gloss["tr"])]
        source = ":::exercise flashcard\ncard-type: vocab\n" + "".join(
            "%s: %s\n" % (key, value) for key, value in fields if value) + ":::"
        with _lock(d):
            deck = _need_deck(d)
            L = _deck_language(d)
            if fm["target"] != L.code:
                raise DeckError('this gloss is in %s, but the deck "%s" is for %s'
                                % (languages.get_or_default(fm["target"]).name, deck["name"], L.name))
            md, _b, _e, problem = _examine(source, L.code)
            if problem:
                raise DeckError(problem)
            if not force:
                _refuse_duplicate(d, deck, md)
            origin = {"doc_id": meta.get("id", doc_id), "doc_uid": meta.get("uid"),
                      "title": meta.get("title", ""), "label": "Gloss: " + gloss["fa"]}
            if prefix is not None:
                origin["source"] = prefix
            made = _insert_all(d, deck, [md], "", origin, now, meta.get("tags"))
            return {"item": made[0], "items": made, "warnings": []}
    if not 1 <= n <= len(blocks) or blocks[n - 1]["subtype"] != subtype:
        raise Conflict(stale, "stale")
    block = blocks[n - 1]
    with _lock(d):
        deck = _need_deck(d)
        L = _deck_language(d)
        if fm["target"] != L.code:
            raise DeckError('this exercise is in %s, but the deck "%s" is for %s'
                            % (languages.get_or_default(fm["target"]).name, deck["name"], L.name))
        if block["errors"]:
            raise DeckError("the exercise needs attention: " + "; ".join(block["errors"]))
        notes = _footnotes_for(block["source"], fm.get("_footnotes") or {})
        (source, notes), copies, warnings = _plan_media(d, (block["source"], notes),
                                                        _from_doc(doc_id))
        md, made_block, _e, problem = _examine(source, L.code)
        if problem:
            raise DeckError(problem)
        notes = _clean_footnotes(notes, md)
        faces = _faces(md, made_block, L.code)
        if not force:
            _refuse_duplicate(d, deck, *faces)
        _make_copies(d, copies)
        origin = {"doc_id": meta.get("id", doc_id), "doc_uid": meta.get("uid"),
                  "title": meta.get("title", ""), "ordinal": n}
        if prefix is not None:
            origin["source"] = prefix
        made = _insert_all(d, deck, faces, notes, origin, now, meta.get("tags"))
        return {"item": made[0], "items": made, "warnings": warnings}


def _copy_chain(d, doc_id, ordinals, updated, force, now, prefix):
    """The exercises of a page numbered `ordinals`, made the steps of ONE follow-up in the deck, in the order given.
    Everything a single exercise's copy does is done once, for the whole: its footnotes, its pictures and recordings
    (named by any step), the duplicate check."""
    meta, markdown = store.get(doc_id)
    stale = "the document has changed since the page was loaded: reload it, then copy"
    if updated and updated != meta.get("updated"):
        raise Conflict(stale, "stale")
    if (not isinstance(ordinals, list) or len(ordinals) < 2 or len(ordinals) > 100
            or len(set(map(str, ordinals))) != len(ordinals)):
        raise DeckError("a follow-up is made of at least two different exercises of the page")
    fm, blocks = exercise_blocks(markdown)
    chosen = []
    for raw in ordinals:
        n = _ordinal(raw)
        if not 1 <= n <= len(blocks):
            raise Conflict(stale, "stale")
        block = blocks[n - 1]
        if block["errors"]:
            raise DeckError("exercise %d needs attention: %s" % (n, "; ".join(block["errors"])))
        if block["primitive"] == "chain":
            raise DeckError("exercise %d is a follow-up already: a follow-up cannot be a step of another" % n)
        chosen.append(block)
    with _lock(d):
        deck = _need_deck(d)
        L = _deck_language(d)
        if fm["target"] != L.code:
            raise DeckError('this exercise is in %s, but the deck "%s" is for %s'
                            % (languages.get_or_default(fm["target"]).name, deck["name"], L.name))
        composed = ":::exercise follow-up\n" + "\n".join(mdparser.nest_step(b["source"]) for b in chosen) + "\n:::"
        notes = _footnotes_for(composed, fm.get("_footnotes") or {})
        (source, notes), copies, warnings = _plan_media(d, (composed, notes), _from_doc(doc_id))
        md, made_block, _e, problem = _examine(source, L.code)
        if problem:
            raise DeckError(problem)
        notes = _clean_footnotes(notes, md)
        faces = _faces(md, made_block, L.code)
        if not force:
            _refuse_duplicate(d, deck, *faces)
        _make_copies(d, copies)
        origin = {"doc_id": meta.get("id", doc_id), "doc_uid": meta.get("uid"), "title": meta.get("title", ""),
                  "label": "Follow-up of %d exercises" % len(chosen)}
        if prefix is not None:
            origin["source"] = prefix
        made = _insert_all(d, deck, faces, notes, origin, now, meta.get("tags"))
        return {"item": made[0], "items": made, "warnings": warnings}


# ---------------------------------------------------------------- studying

def render_item(deck, item, asset_base, preview=False, docs=None, report=None,
                latex_preview=False):
    """The exercise as document html (no colophon), in the deck's language,
    drawn as a deck's own card, so a both-repeat flashcard carries no note
    that a deck will ask both sides (htmlgen's `in_deck`).  `report`, a dict,
    is given "latex_failed": how many of its LaTeX drawings
    could not be made, counted by the renderer that tried (TO-DO §8.39)."""
    md = _front(languages.get(deck["lang"]).code) + item["markdown"]
    if item.get("footnotes"):
        md += "\n\n" + item["footnotes"]
    # `preview` means "show the exercise's answer" here (htmlgen's own
    # editor_preview, which _draw_exercise reads for exactly that) -- an
    # ALREADY-SAVED item shown solved, on a deck's study or cram page.  It is
    # not `latex_preview`, whether THIS render is itself unsaved (the add/edit
    # form's own live preview, deckroutes.py) and so belongs in LaTeX's
    # short-lived cache rather than being kept: the two are independent, and
    # conflating them into one flag silently stopped a solved exercise from
    # ever showing solved.
    out = htmlgen.render_document(md, colophon=False, asset_base=asset_base, docs=docs,
                                  editor_preview=preview, latex_preview=latex_preview,
                                  in_deck=True)
    if report is not None:
        report["latex_failed"] = out.get("latex_failed", 0)
    return out["html"]


def next_card(folder, slug, now=None, skip=None):
    """What to study now.  `skip`: ids to leave out (skipped this session);
    their answers given today still count against the daily limits."""
    now = _clock(now)
    d = deck_dir(folder, slug)
    meta = _need_deck(d)
    code = _deck_language(d).code
    cfg = _settings(meta)
    skip = set(skip or ())
    entries, histories, known, items, scheds = [], [], {}, [], {}
    for item in _load_items(d):
        sched = _read_schedule(d, item["id"])
        histories.append(sched["history"])
        items.append(item)
        scheds[item["id"]] = sched
        if item["id"] in skip:
            continue
        known[item["id"]] = (item, sched)
        entries.append((item["id"], item["created"], sched["state"]))
    q = srs.queue(entries, now, cfg, srs.today_counts(histories, now, cfg),
                  _buried(items, scheds, now, cfg))
    out = {"done": q["next"] is None, "item": None, "counts": q["counts"],
           "next_due": q["next_due"], "intervals": None, "buried": q["buried"]}
    if q["next"] is not None:
        item, sched = known[q["next"]]
        out["item"] = _item_summary(item, sched, code,
                                    [x for x in _groups(items).get(item.get("link"), ())
                                     if x != item["id"]])
        shown = srs.preview(sched["state"], now, cfg, seed=item["id"])
        out["intervals"] = {rating: v["label"] for rating, v in shown.items()}
    return out


def _clean_steps(value):
    """What a follow-up says of how its steps went, {"right": r, "of": n}, or None: the history row keeps it beside the
    rating.  Nothing else is taken from a client, and a count that does not add up is not kept."""
    if not isinstance(value, dict):
        return None
    right, of = value.get("right"), value.get("of")
    if (isinstance(right, int) and isinstance(of, int) and not isinstance(right, bool) and not isinstance(of, bool)
            and 0 <= right <= of <= 1000):
        return {"right": right, "of": of}
    return None


def review(folder, slug, item_id, rating, result=None, now=None, reps=None, by=None, steps=None):
    """Schedule an answer: `rating` one of srs.RATINGS, `result` whether a
    scored exercise was right (None for a flashcard).  A follow-up (a chain
    of steps) is one exercise to the scheduler: `result` is whether every
    scored step was right and `steps` says how many of them were.

    `reps`, when given, is the exercise's reps as it was shown.  An answer to
    a state the exercise has since left -- answered in another tab, or sent
    again after its reply was lost -- is refused with Conflict("reviewed"):
    scheduled a second time, a review card's interval would be multiplied
    again, far past the label the learner pressed."""
    now = _clock(now)
    # A DECK THAT IS OUT IS NOT STUDIED HERE (§19.10): the phone holding it is
    # the only place it is answered, and `by` is that phone replaying what it
    # answered while it was away.
    if by is None:
        studying_here(folder, slug)
    if not isinstance(rating, str) or rating not in srs.RATINGS:
        raise DeckError("rating must be one of %s" % ", ".join(srs.RATINGS))
    if result is not None and not isinstance(result, bool):
        raise DeckError("result must be true, false or null")
    d = deck_dir(folder, slug)
    with _lock(d):
        meta = _need_deck(d)
        item = _need_item(d, item_id)
        sched = _read_schedule(d, item["id"])
        if reps is not None and (not isinstance(reps, int) or isinstance(reps, bool)
                                 or reps != _count(sched["state"].get("reps"))):
            raise Conflict("this exercise was already answered — showing what comes next",
                           "reviewed")
        state = srs.answer(sched["state"], rating, now, _settings(meta), seed=item["id"])
        row = {"at": _stamp(now), "rating": rating, "result": result,
               "before": _state_name(sched["state"]), "interval": state["interval"],
               "ease": state["ease"], "due": state["due"]}
        if _clean_steps(steps):
            row["steps"] = _clean_steps(steps)
        history = sched["history"] + [row]
        sched = {"state": state, "history": history}
        _write_json(d / "schedule" / (item["id"] + ".json"), sched)
        return _item_summary(item, sched, _deck_language(d).code,
                             [x["id"] for x in _group_of(d, item)])


# ---------------------------------------------------------------- checked out
# STUDYING OFFLINE IS A CHECK-OUT (TO-DO §19.10, the owner's choice of
# 2026-09-22).  A phone that wants to study a deck on a train TAKES IT OUT:
# the deck goes with it, and the computer will not study or edit that deck
# until it comes back.  Nothing is merged and nothing can be lost to a
# conflict, because while it is out there is only one place it is answered.
#
#   * the phone sends every answer as soon as it can reach the computer, but
#     KEEPS THE DECK until "Give it back" -- so it can be studied day after
#     day away from the desk without checking it out again;
#   * the computer may still CRAM it: cramming never schedules (§18);
#   * "Take it back" is for a phone that will not come back (lost, broken,
#     left behind).  After it, that phone's answers are REFUSED and LISTED
#     rather than applied -- the owner chose that: once taken back, the
#     computer is the only truth, and nothing is applied behind the learner's
#     back.  Nothing is dropped in silence either: what was refused is kept
#     here and shown on the deck's page.
#
# WHY THERE IS NO JAVASCRIPT SCHEDULER.  The alternative that queued answers
# without ownership (§19.10 b) needed a port of srs.py on the phone, held
# equal to the Python by shared cases.  A check-out does not: the phone is
# handed the whole queue RENDERED, with the four interval labels the computer
# worked out (srs.preview, through /next), and every answer is replayed here,
# in the order it was given, through the very scheduler the computer always
# used.  One scheduler, no drift.
CHECKOUT = "checkout.json"


def _checkout_path(d):
    return d / CHECKOUT


def checkout_of(folder, slug):
    """Who has this deck out, or None.  Also the answers refused since (a
    phone that came back after "Take it back")."""
    d = deck_dir(folder, slug)
    _need_deck(d)
    rec = _read_json(_checkout_path(d))
    if not isinstance(rec, dict):
        return None
    out = {"device": str(rec.get("device") or ""), "id": str(rec.get("id") or ""),
           "since": str(rec.get("since") or ""), "out": bool(rec.get("out")),
           "refused": rec.get("refused") if isinstance(rec.get("refused"), list) else []}
    return out


def _write_checkout(d, rec):
    if rec is None:
        try:
            _checkout_path(d).unlink()
        except OSError:
            pass
        return None
    _write_json(_checkout_path(d), rec)
    return rec


def checkout(folder, slug, device, device_id, now=None):
    """The phone takes the deck out.  Already out to ANOTHER device: refused,
    saying which -- two phones studying one deck is the conflict this whole
    arrangement exists to avoid."""
    device = _clean_name(str(device or "a phone"))[:60]
    device_id = str(device_id or "").strip()[:64]
    if not device_id:
        raise DeckError("a device that takes a deck out has to say which it is")
    d = deck_dir(folder, slug)
    with _lock(d):
        _need_deck(d)
        rec = _read_json(_checkout_path(d)) or {}
        if rec.get("out") and str(rec.get("id")) != device_id:
            raise Conflict("this deck is already out on %s — take it back there, or on the "
                           "computer, before taking it here" % (rec.get("device") or "another device"),
                           "checked-out")
        rec.update(out=True, device=device, id=device_id, since=_stamp(_clock(now)))
        rec.setdefault("refused", [])
        _write_checkout(d, rec)
        return checkout_of(folder, slug)


def give_back(folder, slug, device_id):
    """The phone hands the deck back.  A phone that is not the one holding it
    is told so rather than freeing somebody else's deck."""
    d = deck_dir(folder, slug)
    with _lock(d):
        _need_deck(d)
        rec = _read_json(_checkout_path(d)) or {}
        if not rec.get("out"):
            return None
        if str(rec.get("id")) != str(device_id or ""):
            raise Conflict("this deck is out on %s, not on this device"
                           % (rec.get("device") or "another device"), "checked-out")
        rec["out"] = False
        rec["returned"] = _stamp(_clock())
        _write_checkout(d, rec)
        return checkout_of(folder, slug)


def take_back(folder, slug, now=None):
    """The computer takes the deck back from a phone that will not come back.
    That phone's later answers are refused; the deck is the computer's."""
    d = deck_dir(folder, slug)
    with _lock(d):
        _need_deck(d)
        rec = _read_json(_checkout_path(d)) or {}
        if not rec.get("out"):
            return None
        rec["out"] = False
        rec["taken_back"] = _stamp(_clock(now))
        # the device that had it: its answers are refused from now on
        rec["refuse_id"] = str(rec.get("id") or "")
        _write_checkout(d, rec)
        return checkout_of(folder, slug)


def studying_here(folder, slug):
    """Raises when this computer may not study or edit the deck: it is out."""
    rec = checkout_of(folder, slug)
    if rec and rec.get("out"):
        raise Conflict("this deck is on %s since %s — it can be crammed here, and studied "
                       "again when it comes back (or when you take it back)"
                       % (rec.get("device") or "a phone", (rec.get("since") or "")[:16]),
                       "checked-out")


def answers_from(folder, slug, device_id, answers):
    """Replay what a phone answered while the deck was out -- in the order it
    was answered, through the computer's own scheduler.

    -> {"applied": n, "refused": [{"item", "rating", "at", "why"}]}.  A phone
    whose deck was TAKEN BACK is refused whole, and what it sent is kept on
    the deck so the learner sees what was lost (nothing in silence)."""
    d = deck_dir(folder, slug)
    _need_deck(d)
    rec = _read_json(_checkout_path(d)) or {}
    device_id = str(device_id or "")
    if not isinstance(answers, list):
        raise DeckError("answers must be a list")
    rows = []
    for a in answers:
        if not isinstance(a, dict):
            continue
        rows.append({"item": str(a.get("item") or ""), "rating": str(a.get("rating") or ""),
                     "result": a.get("result") if isinstance(a.get("result"), bool) else None,
                     "steps": _clean_steps(a.get("steps")), "at": str(a.get("at") or "")})
    taken = rec.get("taken_back") and str(rec.get("refuse_id") or "") == device_id
    if taken:
        keep = (rec.get("refused") or []) + [dict(r, why="the deck was taken back on this "
                                                  "computer before these arrived") for r in rows]
        rec["refused"] = keep[-200:]
        with _lock(d):
            _write_checkout(d, rec)
        return {"applied": 0, "refused": [dict(r, why="taken back") for r in rows],
                "taken_back": True}
    if not rec.get("out") or str(rec.get("id")) != device_id:
        raise Conflict("this deck is not out on this device", "checked-out")
    # in the order they were given: a card answered twice offline must be
    # scheduled twice, in that order, or the second would multiply the first
    rows.sort(key=lambda r: r["at"] or "")
    applied, refused = 0, []
    for r in rows:
        when = _moment(r["at"]) if r["at"] else None
        try:
            review(folder, slug, r["item"], r["rating"], r["result"], now=when, by=device_id, steps=r["steps"])
            applied += 1
        except DeckError as e:
            refused.append(dict(r, why=str(e)))
    if refused:
        rec["refused"] = ((rec.get("refused") or []) + refused)[-200:]
        with _lock(d):
            _write_checkout(d, rec)
    return {"applied": applied, "refused": refused}


def forget_refused(folder, slug):
    """The learner has read what could not be applied: the list goes."""
    d = deck_dir(folder, slug)
    with _lock(d):
        _need_deck(d)
        rec = _read_json(_checkout_path(d)) or {}
        rec["refused"] = []
        _write_checkout(d, rec)
        return checkout_of(folder, slug)


def hub_stats(now=None):
    """Counts for the hub's door; never creates DIR."""
    out = {"decks": 0, "due": 0, "by_lang": {}}
    for deck in list_decks(now=now):
        due = deck["study"]["new"] + deck["study"]["learning"] + deck["study"]["review"]
        row = out["by_lang"].setdefault(deck["lang"], {"decks": 0, "due": 0})
        row["decks"] += 1
        row["due"] += due
        out["decks"] += 1
        out["due"] += due
    return out


def image_file(folder, slug, name):
    """The path of a deck picture (a missing .pdf.svg twin is built first)."""
    d = deck_dir(folder, slug)
    if not isinstance(name, str) or not store.IMG_NAME_RE.fullmatch(name):
        raise NotFound("image not found")
    _need_deck(d)
    path = d / "images" / name
    if not path.is_file() and name.endswith(".pdf.svg"):
        store.ensure_pdf_twin(path.with_name(name[:-len(".svg")]))
    if not path.is_file():
        raise NotFound("image not found")
    return path


def audio_file(folder, slug, name):
    """The path of a deck recording (NotFound for a name no recording may
    have: nothing but audio/ can be reached through it)."""
    d = deck_dir(folder, slug)
    if not isinstance(name, str) or not audiofile.NAME_RE.fullmatch(name):
        raise NotFound("recording not found")
    _need_deck(d)
    path = d / "audio" / name
    if not path.is_file():
        raise NotFound("recording not found")
    return path


# ---------------------------------------------------------------- export / import

def export_zip(folder, slug, scheduling):
    """(zip bytes, filename): the manifest, every exercise, the pictures and
    recordings they name, and with `scheduling` every schedule file."""
    scheduling = bool(scheduling)
    d = deck_dir(folder, slug)
    with _lock(d):
        meta = _need_deck(d)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(MANIFEST, _json_bytes({
                "format": FORMAT, "software": "Parseh", "exported": _stamp(_clock()),
                "scheduling": scheduling,
                "deck": {"id": meta["id"], "name": meta["name"],
                         "lang": _deck_language(d).code,
                         "settings": _sparse(_settings(meta)),
                         "created": meta.get("created", "")}}))
            names = []
            for item in _load_items(d):
                zf.writestr("items/%s.json" % item["id"], _json_bytes(item))
                names += [n for n in _media_names((item["markdown"], item["footnotes"]))
                          if n not in names and _name_ok(*n)]
                if scheduling and (d / "schedule" / (item["id"] + ".json")).is_file():
                    zf.writestr("schedule/%s.json" % item["id"],
                                _json_bytes(_read_schedule(d, item["id"])))
            # each entry once: an item may name both fig.pdf and fig.pdf.svg,
            # which is also fig.pdf's twin, and import refuses a name twice
            written = set()
            for kind, name in names:
                f = d / kind / name
                if not f.is_file():
                    continue
                files = [f]
                twin = store.pdf_twin(f)
                if kind == "images" and name.endswith(".pdf") and twin.is_file():
                    files.append(twin)
                for path in files:
                    entry = "%s/%s" % (kind, path.name)
                    if entry not in written:
                        written.add(entry)
                        # a recording is compressed already: stored as it is
                        zf.writestr(entry, path.read_bytes(),
                                    zipfile.ZIP_STORED if kind == "audio" else zipfile.ZIP_DEFLATED)
    suffix = "-with-scheduling" if scheduling else ""
    return buf.getvalue(), "exercises-%s%s.zip" % (d.name, suffix)


def _shown(name):
    return repr(name) if len(name) <= 80 else repr(name[:77] + "...")


def _entry_kind(name):
    if name == MANIFEST:
        return "manifest"
    if _ENTRY_ITEM_RE.fullmatch(name):
        return "item"
    if _ENTRY_SCHEDULE_RE.fullmatch(name):
        return "schedule"
    # a PDF's twin, <name>.pdf.svg, is itself a valid image name
    if name.startswith("images/") and store.IMG_NAME_RE.fullmatch(name[len("images/"):]):
        return "image"
    if name.startswith("audio/") and audiofile.NAME_RE.fullmatch(name[len("audio/"):]):
        return "audio"
    return None


# THE WHOLE SHELF, not one deck of it.  `exercises/<language folder>/<deck
# slug>/...` is what the store looks like on disk and what a backup is: the
# same entries a single deck's export has, each behind the two folders that
# say which deck it belongs to, plus `deck.json` itself -- which a per-deck
# export leaves out (it is rebuilt from the manifest, under a new id where
# the import asks for one) and a BACKUP must carry whole, because the id in
# it is the identity everything else is matched on.
SHELF_FORMAT = "parseh-exercise-shelf/2"
SHELF_MANIFEST = "parseh-exercise-shelf.json"


def _shelf_entry_kind(name):
    if name == SHELF_MANIFEST:
        return "manifest"
    parts = name.split("/")
    if len(parts) < 3:
        return None
    folder, slug = parts[0], parts[1]
    if languages.by_folder(folder) is None or not SLUG_RE.fullmatch(slug):
        return None
    rest = "/".join(parts[2:])
    if rest == "deck.json":
        return "deck"
    kind = _entry_kind(rest)
    # a manifest of a single deck has no business inside a shelf
    return None if kind == "manifest" else kind


def _shelf_split(name):
    """(folder, slug, the name inside that deck) for a shelf entry."""
    parts = name.split("/")
    return parts[0], parts[1], "/".join(parts[2:])


# what one entry of each kind may hold, uncompressed (anything else: MAX_JSON)
def _entry_limit(kind):
    return {"image": store.IMG_MAX, "audio": audiofile.MAX_BYTES}.get(kind, MAX_JSON)


def _open_zip(source):
    try:
        if isinstance(source, (bytes, bytearray, memoryview)):
            return zipfile.ZipFile(io.BytesIO(bytes(source)))
        if isinstance(source, (str, os.PathLike)):
            return zipfile.ZipFile(source)
        if hasattr(source, "read"):
            seekable = getattr(source, "seekable", None)
            if not (callable(seekable) and seekable()):
                source = io.BytesIO(source.read())
            return zipfile.ZipFile(source)
    except FileNotFoundError:
        raise DeckError("the file to import is not there")
    except (zipfile.BadZipFile, zlib.error, OSError, ValueError, EOFError):
        raise DeckError("this is not a deck export: the file is not a zip")
    raise DeckError("nothing to import")


def _check_entries(zf, kind_of=None):
    """name -> ZipInfo, refusing anything that is not part of a deck export.
    Only the directory's headers are read here; sizes are enforced again
    while reading, since a header can lie.

    `kind_of` is the grammar: one deck's by default, the whole shelf's
    (_shelf_entry_kind) for a backup, whose entries carry the language
    folder and the slug in front of the same names."""
    kind_of = kind_of or _entry_kind
    infos = zf.infolist()
    if len(infos) > MAX_ENTRIES:
        raise DeckError("the zip holds more than %d entries" % MAX_ENTRIES)
    entries, total = {}, 0
    for info in infos:
        name = info.filename
        if stat.S_ISLNK(info.external_attr >> 16):
            raise DeckError("the zip holds a symbolic link: %s" % _shown(name))
        kind = kind_of(name)
        if kind is None:
            raise DeckError("unexpected entry in the zip: %s" % _shown(name))
        if name in entries:
            raise DeckError("the zip holds %s twice" % name)
        limit = _entry_limit(kind)
        if info.file_size > limit:
            raise DeckError("%s is too large (at most %d bytes)" % (name, limit))
        total += info.file_size
        if total > MAX_TOTAL:
            raise DeckError("the zip is larger than %d MB uncompressed" % (MAX_TOTAL // 2 ** 20))
        entries[name] = info
    return entries


class _Reader:
    """Reads entries one by one, each capped, all together capped."""

    def __init__(self, zf):
        self.zf, self.total = zf, 0

    def read(self, info, limit):
        try:
            with self.zf.open(info) as fh:
                data = fh.read(limit + 1)
        except (zipfile.BadZipFile, zlib.error, NotImplementedError, RuntimeError,
                EOFError, OSError, ValueError) as e:
            raise DeckError("cannot read %s from the zip: %s" % (info.filename, e))
        if len(data) > limit:
            raise DeckError("%s is too large (at most %d bytes)" % (info.filename, limit))
        self.total += len(data)
        if self.total > MAX_TOTAL:
            raise DeckError("the zip is larger than %d MB uncompressed" % (MAX_TOTAL // 2 ** 20))
        return data

    def json(self, info):
        try:
            return json.loads(self.read(info, MAX_JSON).decode("utf-8"))
        except (ValueError, RecursionError):
            return None


def _iso_or(value, default):
    return value if _moment(value) is not None and _text_ok(value) else default


# The eases a deck can really hold: srs never lets one fall below
# minimum_ease (itself at least 1.0), and Easy adds 0.15 with no ceiling, so
# the top is generous.  Far beyond it (1e305) the interval arithmetic turns
# into infinity and studying the card fails.
_EASE_MAX = 1e6


def _clean_ease(value):
    # compared before float(): an integer of 400 digits is valid JSON, and
    # float() -- or math.isfinite -- of it raises OverflowError; NaN and
    # infinity fail the comparison
    if isinstance(value, (int, float)) and not isinstance(value, bool) \
            and 1.0 <= value <= _EASE_MAX:
        return float(value)
    return None


def _clean_state(raw):
    state = srs.new_state()
    if not isinstance(raw, dict):
        return state
    state["state"] = _state_name(raw)
    for key in ("step", "interval", "reps", "lapses"):
        state[key] = _count(raw.get(key))
    state["ease"] = _clean_ease(raw.get("ease"))
    for key in ("due", "last_review"):
        state[key] = _iso_or(raw.get(key), None)
    return state


def _clean_history(raw):
    out = []
    for h in raw if isinstance(raw, list) else ():
        if not isinstance(h, dict) or h.get("rating") not in srs.RATINGS \
                or _iso_or(h.get("at"), None) is None:
            continue
        row = {"at": h["at"], "rating": h["rating"],
               "result": h["result"] if isinstance(h.get("result"), bool) else None,
               "before": _state_name({"state": h.get("before")}),
               "interval": _count(h.get("interval")),
               "ease": _clean_ease(h.get("ease")),
               "due": _iso_or(h.get("due"), None)}
        if _clean_steps(h.get("steps")):
            row["steps"] = _clean_steps(h.get("steps"))
        out.append(row)
    return out


def _read_manifest(reader, entries):
    info = entries.get(MANIFEST)
    if info is None:
        raise DeckError("this is not a deck export: %s is missing" % MANIFEST)
    manifest = reader.json(info)
    if not isinstance(manifest, dict):
        raise DeckError("the deck manifest (%s) is not readable" % MANIFEST)
    if not _reads(manifest.get("format"), FORMAT):
        raise DeckError("unsupported deck format %r (expected %s)"
                        % (manifest.get("format"), FORMAT))
    deck = manifest.get("deck")
    if not isinstance(deck, dict):
        raise DeckError("the deck manifest describes no deck")
    if not isinstance(deck.get("id"), str) or not ITEM_RE.fullmatch(deck["id"]):
        raise DeckError("the deck manifest has no valid deck id")
    return manifest, deck


def _fill(stage, reader, entries, code, scheduling, now):
    """Write the zip's exercises (and schedules, pictures, recordings) into
    `stage`.  A recording's bytes must be a recording: a zip is anybody's,
    and the deck serves what it holds with an audio type."""
    imported, skipped = 0, []
    for name in sorted(n for n in entries if _entry_kind(n) == "item"):
        item_id = _ENTRY_ITEM_RE.fullmatch(name).group(1)
        raw = reader.json(entries[name])
        if not isinstance(raw, dict) or not isinstance(raw.get("markdown"), str):
            skipped.append({"id": item_id, "errors": ["the exercise file is not readable"]})
            continue
        try:
            md, _block, errors, problem = _examine(raw["markdown"], code)
            notes = "" if problem else _clean_footnotes(
                raw.get("footnotes") if isinstance(raw.get("footnotes"), str) else "", md)
        except DeckError as e:
            errors, problem = [str(e)], str(e)
        if problem:
            skipped.append({"id": item_id, "errors": errors})
            continue
        stamp = _stamp(now)
        created = _iso_or(raw.get("created"), stamp)
        kept = {"id": item_id, "created": created, "updated": _iso_or(raw.get("updated"), created),
                "markdown": md, "footnotes": notes, "origin": _clean_origin(raw.get("origin")),
                "tags": _clean_tags(raw.get("tags"))}
        if _clean_link(raw.get("link")):
            kept["link"] = raw["link"]
        _write_json(stage / "items" / (item_id + ".json"), kept)
        imported += 1
        info = entries.get("schedule/%s.json" % item_id)
        if scheduling and info is not None:
            sched = reader.json(info)
            if isinstance(sched, dict) and isinstance(sched.get("state"), dict):
                _write_json(stage / "schedule" / (item_id + ".json"),
                            {"state": _clean_state(sched["state"]),
                             "history": _clean_history(sched.get("history"))})
    for name in sorted(n for n in entries if _entry_kind(n) == "image"):
        _write_bytes(stage / name, reader.read(entries[name], store.IMG_MAX))
    for name in sorted(n for n in entries if _entry_kind(n) == "audio"):
        data = reader.read(entries[name], audiofile.MAX_BYTES)
        if audiofile.kind(data, name) is None:
            raise DeckError("%s is not a recording: only %s recordings can be imported"
                            % (name, audiofile.HUMAN))
        _write_bytes(stage / name, data)
    return imported, skipped


def import_zip(source, scheduling=True, mode="new"):
    """Import an exported deck (bytes, a file object or a path).

    `scheduling` False, or a zip exported without it, starts every exercise
    new.  A deck with the same id already in that language's folder is a
    Conflict("exists") in mode "new"; "replace" puts the old one in the trash
    and the import in its place (same slug); "copy" imports it beside, with a
    new id and "(copy)" after its name."""
    if mode not in ("new", "replace", "copy"):
        raise DeckError("mode must be new, replace or copy")
    now = _clock()
    with _open_zip(source) as zf:
        entries = _check_entries(zf)
        reader = _Reader(zf)
        manifest, deck = _read_manifest(reader, entries)
        L = _language(deck.get("lang"))
        name = _clean_name(deck.get("name"))
        try:
            settings = _sparse(srs.settings(deck.get("settings") or {}))
        except srs.SettingsError as e:
            raise DeckError("the deck's options cannot be used: %s" % e)
        use_sched = bool(scheduling) and manifest.get("scheduling") is True
        parent = DIR / L.folder
        found = _find_deck(parent, deck["id"])
        if found and mode == "new":
            raise Conflict('a deck with this id is already here: "%s"' % found[1]["name"],
                           "exists")

        parent.mkdir(parents=True, exist_ok=True)
        stage = parent / (".import-" + secrets.token_hex(6))
        stage.mkdir()
        try:
            imported, skipped = _fill(stage, reader, entries, L.code, use_sched, now)
            meta = {"format": FORMAT, "id": deck["id"], "name": name, "lang": L.code,
                    "created": _iso_or(deck.get("created"), _stamp(now)),
                    "updated": _stamp(now), "settings": settings}
            with _PLACE:
                # decided again under the lock: a deck may have arrived meanwhile
                found = _find_deck(parent, deck["id"])
                if found and mode == "new":
                    raise Conflict('a deck with this id is already here: "%s"'
                                   % found[1]["name"], "exists")
                if found and mode == "replace":
                    target = found[0]
                    _write_json(stage / "deck.json", meta)
                    with _lock(target):
                        dest = _to_trash(target)
                        try:
                            os.rename(stage, target)
                        except BaseException:
                            # the old deck goes back: a failed replace must
                            # leave the store as it found it
                            _restore(dest, target)
                            raise
                else:
                    if found:                           # mode "copy"
                        meta["id"] = secrets.token_hex(6)
                        while _find_deck(parent, meta["id"]):
                            meta["id"] = secrets.token_hex(6)
                        meta["name"] = name[:MAX_NAME - 7] + " (copy)"
                    target = parent / _free_slug(parent, slugify(meta["name"]))
                    _write_json(stage / "deck.json", meta)
                    os.rename(stage, target)
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise
    return {"deck": _installed_summary(target, meta, imported), "imported": imported,
            "skipped": skipped, "scheduling": use_sched}


def backup_zip(warn=None):
    """Every deck on the shelf as one zip -> (bytes, filename).

    `warn(sentence)`, when given, is called AS THE ZIP IS WRITTEN, once the
    backup passes BACKUP_WARN_ENTRIES files or BACKUP_WARN_BYTES, and again
    as it grows: a backup is a plain download started from a link, and the
    only place the person is looking while it packs is the Working… list,
    so that is where it says how large it is becoming (deckroutes.api_backup
    puts the sentence there).  Nothing is refused: the import's ceilings are
    far above this, and the warning is there so that a shelf growing towards
    them is noticed years before it reaches them.

    NOT export_zip OF EACH DECK, and the two differences are the whole
    reason this exists.  An export is made to be GIVEN to somebody: it
    carries the media its exercises name, rebuilds the deck from a manifest
    under whatever id the import decides, and offers to leave the
    scheduling behind, because a deck you send someone should start them
    new.  A backup is made to be PUT BACK, so:

      * deck.json travels whole.  Its id is what _find_deck matches on, and
        its created, its slug and its settings are the deck's own.
      * every picture and recording travels, named or not.  A file no
        exercise mentions today is one somebody unlinked yesterday and will
        link again tomorrow; an export drops it on purpose and a backup
        that did would quietly destroy it.
      * the scheduling always travels.  Months of answers cannot be worked
        out again from anything, and a backup that resets them is not one.

    .trash and a half-finished .import- are left where they are: the first
    is a tombstone that would make every backup bigger than the last, and
    the second is not a deck yet.
    """
    buf = io.BytesIO()
    shelf, now = [], _clock()
    files = raw = told = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder, slug, d, meta in _shelf_decks():
            shelf.append({"folder": folder, "slug": slug,
                          "id": meta.get("id", ""), "name": meta.get("name", "")})
            for path in sorted(x for x in d.rglob("*") if x.is_file()):
                rel = path.relative_to(d).as_posix()
                if any(part.startswith(".") for part in path.relative_to(d).parts):
                    continue
                name = "%s/%s/%s" % (folder, slug, rel)
                if _shelf_entry_kind(name) is None:
                    continue          # not part of a deck: not ours to carry
                # a recording is already compressed; deflating it again buys
                # nothing and costs the whole file's worth of work
                how = zipfile.ZIP_STORED if rel.startswith("audio/") else zipfile.ZIP_DEFLATED
                data = path.read_bytes()
                zf.writestr(name, data, how)
                files, raw = files + 1, raw + len(data)
                # said once on crossing, then as it keeps growing: the
                # figures are what is worth watching, not the crossing
                if warn and (files > BACKUP_WARN_ENTRIES or raw > BACKUP_WARN_BYTES) \
                        and (not told or files - told >= 500):
                    told = files
                    warn(store.big_backup_note(
                        "The backup of the exercise shelf", files, raw))
        zf.writestr(SHELF_MANIFEST, _json_bytes({
            "format": SHELF_FORMAT, "software": "Parseh",
            "exported": _stamp(now), "decks": shelf}))
    return buf.getvalue(), "exercises-backup-%s.zip" % now.strftime("%Y%m%d-%H%M")


def _shelf_decks():
    """(folder, slug, path, meta) for every deck on the shelf, in order."""
    out = []
    if not DIR.is_dir():
        return out
    for folder in sorted(x.name for x in DIR.iterdir() if x.is_dir()):
        if folder.startswith(".") or languages.by_folder(folder) is None:
            continue
        parent = DIR / folder
        for slug in sorted(x.name for x in parent.iterdir() if x.is_dir()):
            if slug.startswith(".") or not SLUG_RE.fullmatch(slug):
                continue
            meta = _read_json(parent / slug / "deck.json")
            if isinstance(meta, dict) and meta.get("id"):
                out.append((folder, slug, parent / slug, meta))
    return out


def restore_zip(source, replace=False):
    """A backup put back -> {"restored", "kept", "warnings"}.

    A deck already on the shelf is KEPT and named in the answer unless
    `replace` says otherwise -- the studio's own rule for a library, and for
    the same reason: a restore is not a merge, and the backup is usually the
    older of the two.  "Already here" means an id already in that language's
    folder, which is what a deck IS; a deck restored under a slug somebody
    has since given to another deck simply takes a free one.

    Each deck is staged and swapped in on its own, so a restore that fails
    half way leaves what was there rather than half of this.
    """
    zf = _open_zip(source)
    with zf:
        entries = _check_entries(zf, _shelf_entry_kind)
        manifest = entries.get(SHELF_MANIFEST)
        if manifest is None:
            raise DeckError("that zip is not an exercises backup: it has no %s"
                            % SHELF_MANIFEST)
        reader = _Reader(zf)
        doc = reader.json(manifest)
        if not isinstance(doc, dict) or not _reads(doc.get("format"), SHELF_FORMAT):
            raise DeckError("that zip is not an exercises backup this version reads")
        groups = {}
        for name in entries:
            if name == SHELF_MANIFEST:
                continue
            folder, slug, rest = _shelf_split(name)
            groups.setdefault((folder, slug), {})[rest] = entries[name]
        if not groups:
            raise DeckError("that backup holds no decks")
        restored, kept, warnings = [], [], []
        now = _clock()
        for (folder, slug), group in sorted(groups.items()):
            L = languages.by_folder(folder)
            meta = reader.json(group["deck.json"]) if "deck.json" in group else None
            if not isinstance(meta, dict) or not ITEM_RE.fullmatch(str(meta.get("id", ""))):
                warnings.append("%s/%s: its deck.json is not readable, left out"
                                % (folder, slug))
                continue
            parent = DIR / folder
            found = _find_deck(parent, meta["id"])
            if found and not replace:
                kept.append(meta.get("name") or slug)
                continue
            try:
                restored.append(_restore_one(parent, slug, meta, group, reader, L, now))
            except (DeckError, OSError, ValueError) as e:
                warnings.append("%s/%s: %s" % (folder, slug, e))
        return {"restored": restored, "kept": kept, "warnings": warnings}


def _restore_one(parent, slug, meta, group, reader, L, now):
    """One deck of a backup, staged beside the shelf and swapped in."""
    parent.mkdir(parents=True, exist_ok=True)
    stage = parent / (".import-" + secrets.token_hex(6))
    stage.mkdir()
    try:
        # the same filling an import does, so the same things are refused:
        # an exercise that will not parse, a recording whose bytes are not
        # one.  The scheduling is never left behind here.
        _fill(stage, reader, group, L.code, True, now)
        clean = {"format": FORMAT, "id": meta["id"],
                 "name": str(meta.get("name") or slug)[:MAX_NAME],
                 "lang": L.code,
                 "created": _iso_or(meta.get("created"), _stamp(now)),
                 "updated": _iso_or(meta.get("updated"), _stamp(now)),
                 "settings": _sparse(_settings(meta))}
        _write_json(stage / "deck.json", clean)
        with _PLACE:
            found = _find_deck(parent, meta["id"])
            target = found[0] if found else parent / _free_slug(parent, slug)
            if found:
                with _lock(target):
                    dest = _to_trash(target)
                    try:
                        os.rename(stage, target)
                    except BaseException:
                        _restore(dest, target)
                        raise
            else:
                os.rename(stage, target)
        return clean["name"]
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _restore(dest, target):
    """Move a deck import_zip sent to the trash back to where it was."""
    try:
        if os.path.lexists(target):
            print("[decks] the replaced deck stays in %s: %s is taken" % (dest, target))
        else:
            shutil.move(str(dest), str(target))
    except OSError as e:
        print("[decks] the replaced deck stays in %s: %s" % (dest, e))


def _installed_summary(d, meta, imported):
    """The summary of a deck import_zip has put in place.  The deck is there
    whatever happens now: a summary that cannot be computed must not report
    the import as failed (a retry would only be told the deck exists)."""
    try:
        return _deck_summary(d, meta, _clock())
    except Exception as e:
        print("[decks] imported %s/%s, but cannot count its exercises: %s: %s"
              % (d.parent.name, d.name, type(e).__name__, e))
    L = _deck_language(d)
    return {"id": meta["id"], "name": meta["name"], "lang": L.code, "language": L.name,
            "folder": L.folder, "slug": d.name, "path": "%s/%s" % (L.folder, d.name),
            "created": meta.get("created", ""), "updated": meta.get("updated", ""),
            "settings": _settings(meta),
            "counts": {"total": imported, "new": 0, "learning": 0, "review": 0},
            "study": {"new": 0, "learning": 0, "review": 0}, "next_due": None}


def _reads(stamp, fmt):
    """Is `stamp` one this Parseh reads -- its own, or any number before it
    (a0.4.0 raised them for the latex block, TO-DO §8.39: what an older
    Parseh wrote holds none, and is read as it always was)?"""
    name, _, n = fmt.rpartition("/")
    if not isinstance(stamp, str) or not stamp.startswith(name + "/"):
        return False
    have = stamp[len(name) + 1:]
    return have.isdigit() and 1 <= int(have) <= int(n)
