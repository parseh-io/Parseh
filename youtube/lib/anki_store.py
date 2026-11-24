#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The deck store both card dashboards write into.

One deck directory layout, one card schema, one place that mints ids and
GUIDs -- shared by the video player's server (youtube/serve.py) and the
book reader's server (../serve.py), so a card is a card wherever it was
made and every deck holds both.  The decks themselves stay under
youtube/anki/, where they have always lived; see youtube/anki/README.md.

A deck is filed under its LANGUAGE, like every other kind of content in
the toolbox (docs/languages.md section 2):

    anki/<language folder>/<deck slug>/    deck.json, cards/, media/, deleted/
    anki/notetypes.json  seen.json  inbox/  build/   collection-level

Two decks of different languages may carry the same name, and therefore
the same slug -- they are in different folders, so nothing addresses a
deck by slug alone any more: (lang, slug), or the `path` decks() hands
back, which is what os.path.join with the anki directory wants.

Standard library only.  Each function takes the anki directory explicitly,
because the two servers compute it from different roots.
"""
import hashlib
import json
import os
import re
import secrets
import sys
import time
import unicodedata

import anki_export  # sibling in youtube/lib/
import languages    # the registry; anki_export has put lib/ on the path
import clips        # the tray a card's recording is cut into (lib/clips.py)
import synctouch    # lib/: the change log's hint, one set.add (docs/sync.md)


def lang_code(v):
    """A card's language as a registry code.  Absent or empty means
    Persian -- the default for every card made before languages were
    declared, and for a dashboard that never learnt to send one.
    Anything else must be a registry code: a misspelled one raises
    ValueError (the callers answer 400) instead of being quietly filed
    as Persian, which would build the card into the wrong note type and
    drop its reading -- exactly what languages.get refuses to do in a
    tool that writes files.  One rule for the whole toolbox:
    anki_export.lang_for_code."""
    return anki_export.lang_for_code(v, "lang").code


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def slugify(name):
    """A filesystem slug for a deck name.

    A name with no Latin letters or digits at all -- every Persian-named
    deck -- must NOT collapse to the constant "deck", or they would all
    silently merge into one directory; the hash keeps each its own.  And
    "build" is reserved: anki/build/ is where the .apkg output lands.

    Folded, not lower-cased: a plain .lower() spells Turkish's İ as i plus
    a combining dot, which is not [a-z0-9] and became a hyphen -- a deck
    called "İngilizce" went to anki/turkish/i-ngilizce.
    """
    name = str(name)
    s = re.sub(r"[^a-z0-9]+", "-", languages.fold(name)).strip("-")[:60]
    if not s:
        s = "deck-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    if s in ("build", "inbox"):   # anki/build/ holds the .apkg output,
        s += "-deck"                 # anki/inbox/ the uploads to sync from
    return s


def write_json(path, obj):
    """Write atomically: a crash or full disk must never leave a truncated
    deck.json or card behind -- a corrupt deck.json makes the whole deck
    invisible to decks() while its directory squats on the slug."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)
    synctouch.touch(path)


def as_dict(v):
    return v if isinstance(v, dict) else {}


# the directories directly under anki/ that are NOT language folders and
# never a deck: the .apkg output and the sync wizard's uploads
COLLECTION_DIRS = ("build", "inbox")

# THE SHAPE OF THE STORE -- the layout in this module's docstring, deck.json,
# a card's cards/<id>.json, notetypes.json and seen.json -- as a number
# (lib/version.py FORMATS).  Both dashboards write through this module, so
# the number is kept here; the files carry none.  RAISE IT when the shape
# changes so that the Parseh before this one would read a deck or a card
# wrong; a field an older reader ignores is not such a change.
STORE_FORMAT = 1

# Placement complaints are said ONCE per process, however many times the
# decks are listed: both dashboards poll /anki/decks every time they open,
# and a legacy deck used to fill the log with the same line a hundred
# times an evening until nobody read the log at all.
_reported = set()


def _code(v):
    """A registry code out of a code, a Lang, or None -- so every caller
    may hand over whichever it has."""
    if v is None or v == "":
        return None
    return getattr(v, "code", None) or languages.get(v).code


def _report(msg, say=None):
    if msg in _reported:
        return
    _reported.add(msg)
    (say or (lambda s: print(s, file=sys.stderr)))(msg)


def deck_language(rel, meta, say=None):
    """The language of the deck whose directory is `rel` (relative to
    anki/), reporting a placement problem once.

    The folder says where the deck lives, deck.json's "lang" says what it
    is; absent it is the folder's language, and for a deck lying directly
    under anki/ -- the layout from before languages -- Persian, like every
    other piece of content written before languages were declared.  When
    the two disagree the JSON wins and the disagreement is reported, the
    same bargain books.Book strikes: the folder decides the URL, the JSON
    decides what the cards are built into, and a note type is far too
    expensive to get wrong.
    """
    folder = os.path.dirname(rel)
    L = languages.by_folder(folder) if folder else None
    declared = meta.get("lang") if isinstance(meta, dict) else None
    D = None
    if isinstance(declared, str) and declared.strip():
        try:
            D = languages.get(declared)
        except KeyError:
            _report("!! anki/%s: deck.json lang %r is not a registry code "
                    "(known: %s), read as %s"
                    % (rel, declared, ", ".join(languages.CODES),
                       (L or languages.get(languages.DEFAULT)).name), say)
    if L is None:                      # a deck directly under anki/
        out = D or languages.get(languages.DEFAULT)
        _report("note: anki/%s lies directly under anki/ -- move it to "
                "anki/%s/%s (nothing here will move it for you)"
                % (rel, out.folder, rel), say)
        return out
    if D is not None and D.code != L.code:
        _report("!! anki/%s is filed under anki/%s/ but its deck.json says "
                "language %s (anki/%s/)" % (rel, folder, D.code, D.folder), say)
        return D
    return L


def decks(anki_dir, lang=None, say=None):
    """Every deck in the store, in registry order and then by name.

    One dict per deck:

        {"lang": "ja", "folder": "japanese", "slug": "verbs",
         "path": "japanese/verbs",   # relative to anki/, for os.path.join
         "name": "Japanese::Verbs", "cards": 12, "legacy": False}

    `path` is the only handle that addresses a deck by itself: `slug` is
    not unique any more (two languages may hold a deck of the same name),
    and a legacy deck's path is its bare slug, since it sits directly
    under anki/ and no tool here moves it.  `lang` narrows the list to one
    language (the dashboards ask for their own language's decks first).
    """
    out = []
    if not os.path.isdir(anki_dir):
        return out
    want = _code(lang)
    for name in sorted(os.listdir(anki_dir)):
        if name in COLLECTION_DIRS or name.startswith("."):
            continue
        ddir = os.path.join(anki_dir, name)
        if not os.path.isdir(ddir):
            continue
        # a language folder wins over a deck of the same name: "persian/"
        # is where Persian decks live, and a deck slug that collided with
        # one would hide every deck under it
        if languages.by_folder(name):
            # ... but a legacy deck lying directly under anki/ may already
            # hold that slug, and the day a language is added its folder
            # takes the name from under it: a deck called "German", made
            # long before German was one of the languages here, is
            # anki/german/ and would simply vanish from every dashboard,
            # cards and all.  List it as the legacy deck it is, and say so.
            own = read_json(os.path.join(ddir, "deck.json"))
            if own is not None:
                _report("!! anki/%s is both the %s folder and a deck of its "
                        "own -- rename the deck in the dashboard so it moves "
                        "into its language's folder (its cards are listed "
                        "meanwhile)" % (name, languages.by_folder(name).name),
                        say)
                out.append(_deck_record(anki_dir, name, name, own, True, say))
            for sub in sorted(os.listdir(ddir)):
                meta = read_json(os.path.join(ddir, sub, "deck.json"))
                if meta is not None:
                    out.append(_deck_record(anki_dir, name + "/" + sub,
                                            sub, meta, False, say))
            continue
        meta = read_json(os.path.join(ddir, "deck.json"))
        if meta is not None:
            out.append(_deck_record(anki_dir, name, name, meta, True, say))
    order = {code: i for i, code in enumerate(languages.CODES)}
    out.sort(key=lambda d: (order.get(d["lang"], 99),
                            languages.fold(d["name"]), d["slug"]))
    return [d for d in out if want is None or d["lang"] == want]


def _deck_record(anki_dir, rel, slug, meta, legacy, say=None):
    L = deck_language(rel, meta, say)
    cdir = os.path.join(anki_dir, rel, "cards")
    n = (len([f for f in os.listdir(cdir) if f.endswith(".json")])
         if os.path.isdir(cdir) else 0)
    # "language" is the registry's English name, carried so that a page
    # (the deck picker's headings, the sync wizard's list) can say which
    # language a deck is without holding a table of its own -- no page may
    # (docs/languages.md section 1)
    return {"lang": L.code, "folder": L.folder, "language": L.name,
            "slug": slug, "path": rel, "name": meta.get("name", slug),
            "cards": n, "legacy": legacy}


def find_deck(anki_dir, slug, folder=None, lang=None):
    """The deck with this slug, in this language folder when one is given.

    Returns (deck record, candidates): the record when exactly one deck
    answers, else None and the decks that share the slug -- two languages
    are allowed to, so the caller (the build URL) must say which it means
    rather than picking one.
    """
    code = _code(lang)
    hits = [d for d in decks(anki_dir)
            if d["slug"] == slug
            and (folder is None or d["folder"] == folder)
            and (code is None or d["lang"] == code)]
    return (hits[0] if len(hits) == 1 else None), hits


def clip_of(data):
    """The recording a dashboard sends with a card, `"clip": {"side":
    "front"|"back", "name": <tray name>}` -> (side, name), or None when there
    is none.  A name that is no recording's raises ValueError; one the tray
    does not hold, KeyError."""
    clip = as_dict(data.get("clip"))
    name = clip.get("name")
    if not name:
        return None
    if clips.kind_of(name) != "audio":
        raise ValueError("a card's recording must be a clip from the tray, not %r"
                         % (name,))
    clips.path(name)
    # front unless told otherwise: a recording is of the target language,
    # and that is the front of a card
    return ("back" if clip.get("side") == "back" else "front"), name


def preview(data, anki_dir=None):
    """Render the card being edited exactly as the .apkg will show it.

    Nothing is written to disk; a screenshot rides along as a data URL and
    is put straight into the image field, so the preview and the eventual
    export share every template and style.  A recording is still in the clip
    tray, and plays from there: its `[sound:]` names the tray's own URL, which
    preview_html turns into an <audio>.  Returns (json-able dict, status).
    """
    data = as_dict(data)
    raw = as_dict(data.get("card"))
    try:
        lang = lang_code(raw.get("lang"))
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    card = {
        "kind": "opposites" if raw.get("kind") == "opposites" else "vocab",
        "lang": lang,
        "fa": str(raw.get("fa") or ""),
        "kana": str(raw.get("kana") or ""),
        "tr": str(raw.get("tr") or ""),
        "en": str(raw.get("en") or ""),
        "context": str(raw.get("context") or ""),
        "opp": str(raw.get("opp") or ""),
        "opp_kana": str(raw.get("opp_kana") or ""),
        "opp_tr": str(raw.get("opp_tr") or ""),
        "notes": str(raw.get("notes") or ""),
        "bidirectional": bool(raw.get("bidirectional", True)),
        "reverse_only": (bool(raw.get("reverse_only"))
                         and raw.get("kind") != "opposites"),
        "source": as_dict(raw.get("source")),
        "img_front": None,
        "img_back": None,
        "snd_front": None,
        "snd_back": None,
    }
    shot = as_dict(data.get("shot"))
    blob = shot.get("data") or ""
    if blob.startswith("data:image/") and '"' not in blob:
        side = "front" if shot.get("side") == "front" else "back"
        card["img_" + side] = blob
    try:
        clip = clip_of(data)
    except (ValueError, KeyError):
        clip = None                     # the preview shows the card without it
    if clip:
        card["snd_" + clip[0]] = clips.URL + clip[1]
    return {"ok": True, "html": anki_export.preview_html(
        card, night=bool(data.get("night")), anki_dir=anki_dir)}, 200


def deck_for(anki_dir, name, lang):
    """Where a card of this language, posted to a deck of this name, goes:
    (path relative to anki/, slug, the deck record when it exists).

    The card's own language decides the folder -- a Japanese card never
    lands in the Persian folder, whatever deck the dashboard named -- and
    within that language a deck of the same name reuses its directory,
    INCLUDING a legacy one lying directly under anki/: it is the same
    deck, and filing beside it under persian/ would split one studied
    deck into two that Anki would then merge back by id.
    """
    L = languages.get(lang)
    for d in decks(anki_dir, L.code):
        if d["name"] == name:
            return d["path"], d["slug"], d
    slug = slugify(name)
    # two different NAMES must never share one directory: if the slug is
    # taken by a deck of another name (e.g. two Persian names that both
    # slugify away), append a stable hash of this name.  Two LANGUAGES
    # sharing a slug is fine and needs no hash -- they are in different
    # folders, which is the whole point of the layout.
    meta0 = read_json(os.path.join(anki_dir, L.folder, slug, "deck.json"))
    if meta0 is not None and meta0.get("name") != name:
        slug = (slug + "-" + hashlib.sha1(name.encode("utf-8"))
                .hexdigest()[:6])[:60]
    return L.folder + "/" + slug, slug, None


def _same_front(text):
    """A card's front as Anki compares two notes' first fields: the same text, whatever its white space and
    its Unicode composition."""
    return " ".join(unicodedata.normalize("NFC", str(text or "")).split())


def duplicate_of(ddir, kind, fa):
    """The card of this deck directory that this one would duplicate -> its JSON, or None: the same note type
    (`kind`) with the same front, which is what Anki itself calls a duplicate when the deck is imported.  Every
    card file is read: a deck is hundreds of small files, and this runs on a press, not in a loop."""
    want = _same_front(fa)
    try:
        names = sorted(os.listdir(os.path.join(ddir, "cards")))
    except OSError:
        return None
    for name in names:
        if not name.endswith(".json"):
            continue
        c = as_dict(read_json(os.path.join(ddir, "cards", name)))
        if (c.get("kind") or "vocab") == kind and _same_front(c.get("fa")) == want:
            return c
    return None


def add_card(anki_dir, data):
    """Store one card (and its screenshot) under anki/<folder>/<deck>/.

    The card JSON on disk is the ground truth the .apkg is built from.
    The GUID minted here is what lets a rebuilt deck be re-imported into
    Anki without duplicating notes or disturbing their scheduling, so it
    is written once and never regenerated.  Returns (dict, status).

    The card goes to the deck of ITS OWN language.  When the dashboard
    named a deck of another language (`deck_lang` in the body, or a deck
    of that name found in exactly one other language), the answer carries
    "refiled" saying so, so the page can tell the user where the card
    actually went instead of leaving them to wonder why the count they
    were watching did not move.
    """
    import base64
    data = as_dict(data)
    raw = as_dict(data.get("card"))
    # the recording before anything is written: a name the tray does not
    # hold must not leave a deck directory behind it
    try:
        clip = clip_of(data)
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except KeyError:
        return {"ok": False, "error": "the recording %s is no longer in the clip tray"
                % as_dict(data.get("clip")).get("name")}, 400
    # the language first, before a directory is made for the deck: a
    # registry code (docs/languages.md), which picks the note type at
    # build AND the folder the deck lives in.  Absent means Persian; an
    # unknown code is refused.
    try:
        lang = lang_code(raw.get("lang"))
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    # the dashboards always name the deck; the fallback is for a bare POST
    # and is deliberately not a language's name, since a deck of every
    # language may be called this
    name = str(data.get("deck") or "").strip() or "Parseh"
    asked = None
    if data.get("deck_lang"):
        try:
            asked = lang_code(data.get("deck_lang"))
        except ValueError as e:
            return {"ok": False, "error": str(e)}, 400
    if asked is None:
        # no language sent with the deck (an older page, a bare POST):
        # a deck of that name in exactly one other language is what the
        # user was looking at
        elsewhere = {d["lang"] for d in decks(anki_dir) if d["name"] == name}
        if len(elsewhere) == 1 and lang not in elsewhere:
            asked = elsewhere.pop()
    rel, slug, held = deck_for(anki_dir, name, lang)
    ddir = os.path.join(anki_dir, rel)
    os.makedirs(os.path.join(ddir, "cards"), exist_ok=True)
    os.makedirs(os.path.join(ddir, "media"), exist_ok=True)
    dpath = os.path.join(ddir, "deck.json")
    if not os.path.exists(dpath):
        write_json(dpath, {"name": name, "lang": lang,
                           "id": (1 << 30) | secrets.randbits(30),
                           "created": time.strftime("%Y-%m-%d")})
    cid = time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)
    card = {
        "id": cid,
        "guid": secrets.token_urlsafe(8),
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        # vocab (the default) or opposites -- picks the note type at build
        "kind": "opposites" if raw.get("kind") == "opposites" else "vocab",
        # where the card was made: a video id, or a book slug -- one of the
        # two is empty.  Neither reaches the note; they are provenance.
        "video": str(raw.get("video") or ""),
        "book": str(raw.get("book") or ""),
        "time": raw.get("time") or 0,
        "lang": lang,
        # `fa` is the text in the target language whatever the language --
        # the key is named after Persian, the toolbox's first language
        "fa": str(raw.get("fa") or "").strip(),
        # the reading (kana) of the text and of the opposite: filled only
        # for a language with a reading; the others' note types have no
        # field for it and the value is simply never asked for
        "kana": str(raw.get("kana") or "").strip(),
        "tr": str(raw.get("tr") or "").strip(),
        "en": str(raw.get("en") or "").strip(),
        "context": str(raw.get("context") or "").strip(),
        "opp": str(raw.get("opp") or "").strip(),
        "opp_kana": str(raw.get("opp_kana") or "").strip(),
        "opp_tr": str(raw.get("opp_tr") or "").strip(),
        "notes": str(raw.get("notes") or "").strip(),
        "bidirectional": bool(raw.get("bidirectional", True)),
        # English -> Persian alone; vocab only (the opposites model has no
        # ReverseOnly field), and it implies the reverse template is on
        "reverse_only": (bool(raw.get("reverse_only"))
                         and raw.get("kind") != "opposites"),
        # Anki's tags field is space-separated, so a tag with spaces
        # would silently split into several on the next sync round-trip
        "tags": [re.sub(r"\s+", "_", t.strip())
                 for t in (raw.get("tags")
                           if isinstance(raw.get("tags"), list) else [])
                 if isinstance(t, str) and t.strip()][:16],
        "source": as_dict(raw.get("source")),
        "img_front": None,
        "img_back": None,
        # a recording on either side: a file in media/, which the export
        # puts in the image field as [sound:<file>] -- no field of its own,
        # because a note type's shape never changes (anki_export.note_fields)
        "snd_front": None,
        "snd_back": None,
    }
    if not card["fa"]:
        return {"ok": False, "error": "the %s field is empty"
                % languages.get(card["lang"]).name}, 400
    if card["kind"] == "opposites" and not card["opp"]:
        return {"ok": False,
                "error": "an opposites card needs the opposite written in"}, 400
    # A DUPLICATE IS ASKED ABOUT, NOT REFUSED (TO-DO 10.7), as an exercise deck asks (markdown/app/decks.py):
    # the answer says the deck has it, and the page's button then reads "add it again", which sends `force`
    if not data.get("force") and duplicate_of(ddir, card["kind"], card["fa"]):
        return {"ok": False, "conflict": "duplicate",
                "error": "this card is already in \u201c%s\u201d" % name}, 409
    shot = as_dict(data.get("shot"))
    if shot.get("data"):
        blob = base64.b64decode(shot["data"].split(",", 1)[-1])
        if len(blob) > 8 * 1024 * 1024:
            return {"ok": False, "error": "screenshot too large"}, 400
        side = "front" if shot.get("side") == "front" else "back"
        fname = "%s-%s.jpg" % (cid, side)
        with open(os.path.join(ddir, "media", fname), "wb") as f:
            f.write(blob)
        card["img_" + side] = fname
    if clip:
        # copied, not moved: the same clip may go onto a deck's card as well.
        # Named after the card like the screenshot, and never with a leading
        # underscore, which Anki keeps for the note types' own static media
        side, name = clip
        fname = "%s-%s-audio%s" % (cid, side, os.path.splitext(name)[1])
        try:
            clips.copy_to(name, os.path.join(ddir, "media"), fname)
        except (KeyError, OSError) as e:
            return {"ok": False, "error": "the recording could not be copied: %s" % e}, 400
        card["snd_" + side] = fname
    write_json(os.path.join(ddir, "cards", cid + ".json"), card)
    L = languages.get(lang)
    info = next((d for d in decks(anki_dir) if d["path"] == rel),
                {"lang": lang, "folder": L.folder, "slug": slug, "path": rel,
                 "name": name, "cards": 1, "legacy": False})
    out = {"ok": True, "deck": info}
    if asked and asked != lang:
        A = languages.get(asked)
        out["refiled"] = {"from": A.code, "from_name": A.name,
                          "to": L.code, "to_name": L.name,
                          "note": "filed under %s -- a %s card goes to the "
                                  "%s deck of that name" % (L.name, L.name,
                                                            L.name)}
    return out, 200
