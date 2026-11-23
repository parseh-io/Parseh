#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reverse-import a real .apkg back into the anki/ deck store.

    python3 lib/import_apkg.py "anki/Persian CI.apkg"

Why this exists: the store's own tools (anki_export.py) only go JSON ->
.apkg.  If a deck built here gets imported into Anki, studied, maybe
renamed or moved to a nested deck, and the .apkg folder is reset or the
device changes, the LIVE state of the deck is now inside Anki, not in
this repo -- and the repo needs to catch back up, under the same name
and the same Anki deck id, so that a card added from either website
lands in the deck the person is actually reviewing rather than spawning
a second, disconnected one.

It reads a modern Anki export (the "colpkg" format: a zstd-compressed
schema-18 SQLite database in collection.anki21b, with collection.anki2
as an inert compatibility stub), an Anki 2.1 export (a plain schema-11
collection.anki21 beside the same kind of stub), and a legacy schema-11
collection.anki2, and writes each note as a card JSON in the same shape
the dashboards save -- GUID preserved exactly, so re-exporting after
this import and re-importing into Anki updates the same notes rather
than duplicating them.

Only notes belonging to THIS project's own note types (the per-language
pairs in anki_export.MODELS) are converted -- a note of any other type
(a stock Basic card, say) is left untouched and reported, since guessing
at an unfamiliar field layout risks writing garbage.  Bring those over
by hand, or ask for the mapping to be taught.  The note type says which
language a card is in, so an imported card carries `lang` (and, for a
language with a reading, `kana` / `opp_kana` from the Reading fields).

Standard library plus the `zstandard` package (for the modern format
only; a legacy-only .apkg needs nothing extra).

This is the BOOTSTRAP tool, for a deck the store has never held.  For a
deck already in the store, use lib/sync_apkg.py instead: it matches notes
to existing cards by guid whatever their filenames, where re-running this
importer would write a second apkg-<guid> file beside any card the
dashboards created and so duplicate its note on the next build.

It is also how a package BUILT by this toolbox comes in -- the .apkg the
build button makes, from your other computer or from someone else who
made the cards with Parseh:

    python3 lib/import_apkg.py "shared.apkg"            # decks not held yet
    python3 lib/import_apkg.py "shared.apkg" --merge    # and the new cards of held ones

Such a package cannot be SYNCED (it says nothing about what Anki holds,
see sync_apkg.py), but it can be brought in: a deck the store lacks is
created, and with --merge a deck already held is given the cards it
lacks.  Its cards are filed as pkg-<guid>.json -- a name that, unlike
apkg-<guid>.json, is NOT taken as Anki's word that the note exists --
so that a later genuine export lacking them reads as "not in Anki yet",
never as a deletion.  Images travel with it.
"""
import glob
import html
import io
import json
import os
import re
import sqlite3
import struct
import sys
import tempfile
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anki_export as ax
import anki_store
import languages    # the registry; anki_export has put lib/ on the path
import scratch      # where a package is opened: .tmp/ in Parseh's folder (lib/scratch.py)

IMG_RE = re.compile(r'<img\b[^>]*?\bsrc="([^"]*)"[^>]*>', re.I)
# a recording, which the exporter writes into the same field as the picture
# -- read by the tag the exporter's preview plays, so the two cannot disagree
SOUND_RE = ax.SOUND_RE
A_RE = re.compile(r'<a\s+href="([^"]*)">(.*?)</a>', re.I | re.S)


def unh(s):
    """The inverse of anki_export.h(): HTML text back to plain-ish text."""
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    return html.unescape(s)


def un_source(s):
    m = A_RE.match((s or "").strip())
    if m:
        return {"label": unh(m.group(2)), "url": html.unescape(m.group(1))}
    return {"label": unh(s), "url": ""}


def un_img(s):
    """The first picture's file in an image field, or None -- None too for a
    src that is no bare file name (ax.media_name): a path out of the deck's
    media/, a web address."""
    m = IMG_RE.search(s or "")
    return ax.media_name(m.group(1)) if m else None


def un_sound(s):
    """The first `[sound:file]` in an image field, or None -- None too for a
    name that is no bare file name (ax.media_name)."""
    m = SOUND_RE.search(s or "")
    return ax.media_name(html.unescape(m.group(1))) if m else None


def _pb_walk(data):
    """Minimal protobuf field walk: yields (field_no, wire_type, value)."""
    i, n = 0, len(data)
    while i < n:
        tag = 0
        shift = 0
        while True:
            b = data[i]; i += 1
            tag |= (b & 0x7f) << shift
            shift += 7
            if not b & 0x80:
                break
        field, wt = tag >> 3, tag & 7
        if wt == 0:                       # varint
            v = 0; shift = 0
            while True:
                b = data[i]; i += 1
                v |= (b & 0x7f) << shift
                shift += 7
                if not b & 0x80:
                    break
        elif wt == 2:                     # length-delimited
            ln = 0; shift = 0
            while True:
                b = data[i]; i += 1
                ln |= (b & 0x7f) << shift
                shift += 7
                if not b & 0x80:
                    break
            v = data[i:i + ln]; i += ln
        elif wt == 5:
            v = struct.unpack_from("<I", data, i)[0]; i += 4
        elif wt == 1:
            v = struct.unpack_from("<Q", data, i)[0]; i += 8
        else:
            return                        # unknown wire type: stop cleanly
        yield field, wt, v


def media_index(z):
    """{media file name: (zip member, compressed?)} from the package's
    "media" entry -- legacy JSON, or the modern zstd protobuf list.
    Returns {} when there is no readable map (fields still sync; images
    would then need copying by hand, and the report says so)."""
    try:
        raw = z.read("media")
    except KeyError:
        return {}
    try:                                   # legacy: {"0": "name.jpg", ...}
        return {name: (idx, False)
                for idx, name in json.loads(raw.decode("utf-8")).items()}
    except (ValueError, UnicodeDecodeError, AttributeError):
        pass                               # AttributeError: JSON, not a dict
    try:                                   # modern: zstd(MediaEntries proto)
        import zstandard
        data = zstandard.ZstdDecompressor().decompress(
            raw, max_output_size=64 * 1024 * 1024)
        out = {}
        i = 0
        for field, wt, v in _pb_walk(data):
            if field == 1 and wt == 2:     # one MediaEntry
                for f2, w2, v2 in _pb_walk(v):
                    if f2 == 1 and w2 == 2:
                        out[v2.decode("utf-8")] = (str(i), True)
                        break
                i += 1
        return out
    except Exception:
        return {}


def _read_member(z, index, name):
    """The package's bytes for one media file name, or None."""
    if name not in index or ax.media_name(name) is None:
        return None                       # unknown, or a path -- never write
    member, compressed = index[name]
    try:
        blob = z.read(member)
        if compressed:
            import zstandard
            blob = zstandard.ZstdDecompressor().decompress(
                blob, max_output_size=64 * 1024 * 1024)
        return blob
    except Exception:
        return None


def extract_media(z, index, name, dest_dir, dry_run):
    """(available, updated) -- see extract_media's contract.  A name that
    is no bare file name (ax.media_name) is neither: it is not looked for
    outside `dest_dir`, let alone written there."""
    if ax.media_name(name) is None:
        return False, False
    dest = os.path.join(dest_dir, name)
    blob = _read_member(z, index, name)
    exists = os.path.exists(dest)
    if exists and blob is not None:
        try:
            with open(dest, "rb") as f:
                if f.read() == blob:
                    return True, False
        except OSError:
            pass
        if not dry_run:
            tmp = dest + ".sync-tmp"
            with open(tmp, "wb") as f:
                f.write(blob)
            os.replace(tmp, dest)
        return True, True
    if exists:
        return True, False
    if blob is None:
        return False, False
    if not dry_run:
        os.makedirs(dest_dir, exist_ok=True)
        tmp = dest + ".sync-tmp"
        with open(tmp, "wb") as f:
            f.write(blob)
        os.replace(tmp, dest)
    return True, False


# {mid: (kind, [field names])} for every note type this toolbox writes,
# straight from the one table -- a note whose mid is not here is foreign
FIELD_MAP = {mid: (m["kind"], m["fields"]) for mid, m in ax.MODELS.items()}


# an <img>'s width attribute or a Source anchor's exact spacing must not
# count as formatting the store cannot hold
PARSED_FIELDS = {"FrontImage", "BackImage", "Source", "Reverse",
                 "ReverseOnly"}

BR_RE = re.compile(r"<br\s*/?>", re.I)


def faithful(fresh, mid, flds):
    """Would rebuilding this note from `fresh` reproduce its fields?
    False means the note carries something the store cannot hold --
    formatting, an extra field -- and must go anki-owned rather than be
    flattened on the next export.  Image/Source/Reverse fields are
    compared on parsed meaning, not raw bytes."""
    names = FIELD_MAP[mid][1]
    if len(flds) > len(names):
        return False                       # extra fields: cannot hold them
    if len(flds) < len(names):
        flds = list(flds) + [""] * (len(names) - len(flds))
    rebuilt = ax.note_fields(fresh)
    for name, orig, mine in zip(names, flds, rebuilt):
        if name in PARSED_FIELDS:
            continue
        if BR_RE.sub("<br>", orig or "") != BR_RE.sub("<br>", mine or ""):
            return False
    return True


def owned_mirror(guid, mid, flds, tags, mname, fnames, prefix="apkg-"):
    """The card the store keeps for a note Anki owns -- a foreign note
    type, or a project note carrying formatting a rebuild could not
    reproduce (bold, colour, HTML typed inside Anki).  The guid and the
    raw fields are recorded and anki_export.build_deck leaves it out of
    every package, so the note lives on in Anki exactly as made.  The
    same shape sync_apkg writes when it meets one."""
    return {"id": prefix + re.sub(r"[^A-Za-z0-9_-]", "_", guid), "guid": guid,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "video": "", "book": "", "kind": "anki", "anki": "owned",
            "anki_model": mname,
            "anki_fields": (dict(zip(fnames, flds)) if len(fnames) >= len(flds)
                            else {str(i): v for i, v in enumerate(flds)}),
            "tags": [t for t in tags.split() if t]}


def stamp_of(con):
    """The deck slug a package built by this toolbox carries in col.conf
    (see anki_export.build_deck), or None for a real export from Anki."""
    try:
        (blob,) = con.execute("select conf from col").fetchone()
        conf = json.loads(blob) if isinstance(blob, str) else {}
    except Exception:
        return None
    return conf.get("frankStoreBuild") if isinstance(conf, dict) else None


def store_guids(anki_dir):
    """Every guid the store holds anywhere: cards/ and deleted/ of every
    deck.  Anki guids are collection-wide, so a note is either here or it
    is not, whichever deck it sits in."""
    out = set()
    for d in anki_store.decks(anki_dir) or []:
        for sub in ("cards", "deleted"):
            cdir = os.path.join(anki_dir, d["path"], sub)
            if not os.path.isdir(cdir):
                continue
            for fn in os.listdir(cdir):
                if fn.endswith(".json"):
                    card = anki_store.read_json(os.path.join(cdir, fn))
                    if isinstance(card, dict) and card.get("guid"):
                        out.add(card["guid"])
    return out


def open_collection(apkg_path, tmpdir):
    """A sqlite3 connection to the package's collection, whichever schema
    it turns out to be -- and how many notes the OTHER schema would have
    missed, so a quiet truncation cannot pass as a clean import."""
    z = zipfile.ZipFile(apkg_path)
    names = set(z.namelist())
    con19 = None
    if "collection.anki21b" in names:
        import zstandard
        raw = z.read("collection.anki21b")
        data = zstandard.ZstdDecompressor().decompress(
            raw, max_output_size=500 * 1024 * 1024)
        p = os.path.join(tmpdir, "col21.anki2")
        with open(p, "wb") as f:
            f.write(data)
        con19 = sqlite3.connect(p)
        con19.create_collation("unicase", lambda a, b: (a > b) - (a < b))
    con21 = None
    if "collection.anki21" in names:
        # Anki 2.1.x's own format (2.1.0 to 2.1.49, and later versions
        # exporting for them): a plain schema-11 collection under this
        # name, beside a collection.anki2 that holds nothing but one
        # "please update" note for clients older still.  Read this one, or
        # the whole export looks like a single note in "Default".
        z.extract("collection.anki21", tmpdir)
        con21 = sqlite3.connect(os.path.join(tmpdir, "collection.anki21"))
    con2 = None
    if "collection.anki2" in names:
        z.extract("collection.anki2", tmpdir)
        c = sqlite3.connect(os.path.join(tmpdir, "collection.anki2"))
        # a real (pre schema-18) collection has more than the toy
        # placeholder row modern Anki writes for old-client compatibility
        # (which may not even be a readable database -- if the modern
        # collection is already open, a broken stub must not sink it)
        try:
            c.execute("select count(*) from notes").fetchone()
            con2 = c                     # readable: usable (when con19 is
        except sqlite3.DatabaseError:    # present it wins below anyway, so
            if con19 is None:            # the modern stub never surfaces)
                raise
    if con19 is not None:
        return con19, "anki21b (modern)"
    if con21 is not None:
        return con21, "anki21 (Anki 2.1)"
    if con2 is not None:
        return con2, "anki2 (legacy)"
    sys.exit("no usable collection found in %s" % apkg_path)


def read_notes(con):
    """[(nid, guid, mid, [fields], tags, did)], did taken from the note's
    first card -- these decks never split one note across two decks, and
    a note that somehow is split simply follows its first card.  A card
    sitting in a filtered deck belongs to its home deck (odid), not to the
    filter it happens to be studied through today."""
    dids = {}
    for nid, did, odid in con.execute(
            "select nid, did, odid from cards order by nid, ord"):
        dids.setdefault(nid, odid or did)
    out = []
    for nid, guid, mid, flds, tags in con.execute(
            "select id, guid, mid, flds, tags from notes order by id"):
        out.append((nid, guid, mid, flds.split("\x1f"), tags.strip(),
                    dids.get(nid)))
    return out


def deck_names(con):
    # schema-18's decks.name joins levels with \x1f; the legacy JSON
    # blob in col.decks already uses "::" -- normalise both to "::"
    try:
        return {did: name.replace("\x1f", "::")
                for did, name in con.execute("select id, name from decks")}
    except sqlite3.OperationalError:
        (blob,) = con.execute("select decks from col").fetchone()
        return {int(k): v["name"] for k, v in json.loads(blob).items()}


def card_from_note(mid, flds, guid, tags, source_label, prefix="apkg-"):
    kind, names = FIELD_MAP[mid]
    model = ax.MODELS[mid]
    f = dict(zip(names, flds))
    # the text field is named after the language ("Persian", "Japanese");
    # the store keeps it under `fa` whatever the language (languages.md)
    if kind == "opposites":
        card = {"kind": "opposites", "lang": model["lang"],
                "fa": unh(f.get(model["field"])),
                "tr": unh(f.get("Transliteration")),
                "opp": unh(f.get("Opposite")),
                "opp_tr": unh(f.get("OppositeTr"))}
    else:
        card = {"kind": "vocab", "lang": model["lang"],
                "fa": unh(f.get(model["field"])),
                "tr": unh(f.get("Transliteration")),
                "en": unh(f.get("English")),
                "context": unh(f.get("Context"))}
    # the reading fields exist only on a reading language's note types;
    # a card of the others never gets the keys, as the dashboards' cards
    # of those languages carry them empty at most
    if "Reading" in names:
        card["kana"] = unh(f.get("Reading"))
    if "OppositeReading" in names:
        card["opp_kana"] = unh(f.get("OppositeReading"))
    card["notes"] = unh(f.get("Notes"))
    card["bidirectional"] = bool((f.get("Reverse") or "").strip())
    # vocab only: the opposites model has no ReverseOnly field
    card["reverse_only"] = (kind == "vocab"
                            and bool((f.get("ReverseOnly") or "").strip()))
    card["source"] = un_source(f.get("Source")) or {"label": source_label,
                                                     "url": ""}
    card["img_front"] = un_img(f.get("FrontImage"))
    card["img_back"] = un_img(f.get("BackImage"))
    # a recording has no field of its own: it is written after the picture
    # (anki_export.note_fields), and comes home from there
    card["snd_front"] = un_sound(f.get("FrontImage"))
    card["snd_back"] = un_sound(f.get("BackImage"))
    card["tags"] = [t for t in tags.split() if t]
    card["guid"] = guid
    # a stable id derived from the guid: re-running the import on the same
    # apkg overwrites the same file rather than accumulating duplicates.
    # The prefix says where the file came from: apkg- from an export out
    # of Anki (which sync_apkg.known_to_anki takes as Anki's word that the
    # note exists), pkg- from a package this toolbox built (which is not)
    card["id"] = prefix + re.sub(r"[^A-Za-z0-9_-]", "_", guid)
    card["created"] = time.strftime("%Y-%m-%d %H:%M:%S")
    card["video"] = ""
    card["book"] = ""
    return card


def deck_lang_of(items):
    """The language a deck coming out of a package is filed under: the
    one most of its notes' note types belong to (ax.MODELS is the single
    table saying which language a model id is), ties broken by registry
    order so the same package always lands in the same folder.  Nothing
    else in this file knows a language: the note type is the witness."""
    counts = {}
    for _guid, mid, _flds, _tags in items:
        code = ax.MODELS[mid]["lang"]
        counts[code] = counts.get(code, 0) + 1
    if not counts:
        return languages.get(languages.DEFAULT)
    order = {c: i for i, c in enumerate(languages.CODES)}
    return languages.get(
        sorted(counts, key=lambda c: (-counts[c], order.get(c, 99)))[0])


def import_all(apkg_path, anki_dir, only_dids=None, merge_held=False):
    """Bring the package's decks into the store.

    `only_dids` restricts the work to those Anki deck ids -- the wizard's
    button names ONE deck, and re-importing the rest would write a file
    beside every card of decks the store already holds, leaving two files
    per note.  A deck the store already holds is skipped for the same
    reason (this is the bootstrap tool; sync_apkg.py updates a deck
    already here) -- unless `merge_held`, in which case it is given the
    cards it lacks and nothing else: the ordinary case for a package
    someone shares again after adding to it.

    Every image and recording a card names is copied out of the package
    into the deck's media/; one the package does not carry is reported.  A note carrying
    formatting the store cannot hold (HTML typed inside Anki) comes in as
    an anki-owned mirror, exactly as the sync would treat it, so that a
    rebuild never flattens it: it is counted as "kept".
    """
    import notetypes
    with tempfile.TemporaryDirectory(prefix="apkg-import-", dir=scratch.folder()) as tmp:
        con, fmt = open_collection(apkg_path, tmp)
        stamp = stamp_of(con)
        names = deck_names(con)
        notes = read_notes(con)
        snap = notetypes.snapshot(con)
        con.close()
    nt_changes = notetypes.capture(anki_dir, snap, apkg_path)
    # a build of this toolbox is not Anki's word that a note exists
    prefix = "pkg-" if stamp else "apkg-"

    by_deck, unknown_mid = {}, {}
    for nid, guid, mid, flds, tags, did in notes:
        if mid not in FIELD_MAP:
            unknown_mid[mid] = unknown_mid.get(mid, 0) + 1
            continue
        by_deck.setdefault(did, []).append((guid, mid, flds, tags))

    have = store_guids(anki_dir) if merge_held else set()
    z = zipfile.ZipFile(apkg_path)
    media_idx = media_index(z)
    media_copied, media_missing = 0, []

    def write_cards(ddir, deck_name, items, skip_guids):
        used, n, kept = {}, 0, 0
        for guid, mid, flds, tags in items:
            if guid in skip_guids:
                continue
            card = card_from_note(mid, flds, guid, tags, deck_name, prefix)
            # the media first: an owned note keeps its pictures and
            # recordings too
            for side in ax.MEDIA_KEYS:
                fn = card.get(side)
                if not fn:
                    continue
                ok, _ = extract_media(z, media_idx, fn,
                                      os.path.join(ddir, "media"), False)
                if ok:
                    nonlocal_counts[0] += 1
                else:
                    media_missing.append(fn)
            if not faithful(card, mid, flds):
                kind, fnames = FIELD_MAP[mid]
                mname = (snap.get(mid) or {}).get("name") or "mid %s" % mid
                card = owned_mirror(guid, mid, flds, tags, mname, fnames, prefix)
                kept += 1
            if used.get(card["id"], guid) != guid:
                import hashlib
                card["id"] += "-" + hashlib.sha1(
                    guid.encode("utf-8")).hexdigest()[:8]
            used[card["id"]] = guid
            anki_store.write_json(
                os.path.join(ddir, "cards", card["id"] + ".json"), card)
            n += 1
        nonlocal_counts[1] = kept
        return n
    nonlocal_counts = [0, 0]

    decks, merged, skipped_held = [], [], []
    for did, items in by_deck.items():
        if only_dids is not None and did not in set(only_dids):
            continue
        deck_name = names.get(did) or ("deck-%s" % did)
        # the language of the deck to be created: the note type says which
        # language every note is (ax.MODELS), and the deck goes under the
        # language most of its notes are in.  A deck of mixed languages
        # (one deck holding a Persian and a Japanese note) is filed under
        # the majority and its cards keep their own `lang` -- the folder
        # is where the deck lives, the card says what it is
        lang = deck_lang_of(items)
        slug = anki_store.slugify(deck_name)
        # match on the Anki deck id across the WHOLE store, every language:
        # a deck renamed inside Anki still lives under the directory it was
        # first given, so guessing the directory from today's name would
        # miss it and import the deck a second time
        held = None
        for d in (anki_store.decks(anki_dir) or []):
            meta = anki_store.read_json(
                os.path.join(anki_dir, d["path"], "deck.json")) or {}
            if meta.get("id") == did:
                held = d
                break
        if held and not merge_held:
            skipped_held.append({"name": deck_name, "slug": held["slug"],
                                 "path": held["path"], "lang": held["lang"],
                                 "folder": held["folder"]})
            continue
        if held:
            ddir = os.path.join(anki_dir, held["path"])
            os.makedirs(os.path.join(ddir, "cards"), exist_ok=True)
            os.makedirs(os.path.join(ddir, "media"), exist_ok=True)
            n = write_cards(ddir, deck_name, items, have)
            merged.append({"name": deck_name, "slug": held["slug"],
                           "path": held["path"], "lang": held["lang"],
                           "folder": held["folder"], "added": n,
                           "already": len(items) - n, "kept": nonlocal_counts[1]})
            continue
        rel = os.path.join(lang.folder, slug)
        ddir = os.path.join(anki_dir, rel)
        os.makedirs(os.path.join(ddir, "cards"), exist_ok=True)
        os.makedirs(os.path.join(ddir, "media"), exist_ok=True)
        dpath = os.path.join(ddir, "deck.json")
        existing = anki_store.read_json(dpath)
        if existing is None or existing.get("id") != did:
            # the deck id is preserved EXACTLY: it is what lets Anki
            # recognise a future rebuild as the very same deck on import,
            # instead of creating a sibling with the same name
            anki_store.write_json(dpath, {
                "name": deck_name, "lang": lang.code, "id": did,
                "created": (existing or {}).get(
                    "created", time.strftime("%Y-%m-%d"))})
        n = write_cards(ddir, deck_name, items, set())
        decks.append({"name": deck_name, "slug": slug,
                      "path": rel.replace(os.sep, "/"), "lang": lang.code,
                      "folder": lang.folder, "cards": n,
                      "kept": nonlocal_counts[1]})
    z.close()
    media_copied = nonlocal_counts[0]
    return {"format": fmt, "own_build": stamp, "decks": decks, "merged": merged,
            "notetypes": nt_changes, "already_held": skipped_held,
            "media": {"copied": media_copied, "missing": sorted(set(media_missing))},
            "skipped": [{"mid": m, "notes": n}
                        for m, n in unknown_mid.items()]}


def main():
    args = [a for a in sys.argv[1:] if a != "--merge"]
    if len(args) != 1:
        sys.exit(__doc__)
    apkg_path = args[0]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    res = import_all(apkg_path, os.path.join(root, "anki"),
                     merge_held="--merge" in sys.argv)
    print("reading %s as %s%s" % (apkg_path, res["format"],
                                  " -- a package built by Parseh (deck %r)"
                                  % res["own_build"] if res["own_build"] else ""))
    if res["skipped"]:
        print("skipped notes of an unrecognised note type (not this "
              "project's own -- bring these over by hand):")
        for sk in res["skipped"]:
            print("  mid %s: %d note(s)" % (sk["mid"], sk["notes"]))
    for d in res.get("already_held") or []:
        print("  %-40s (%s) -> already in the store; use lib/sync_apkg.py "
              "for an export from Anki, --merge for a package built by Parseh"
              % (d["name"], d.get("path") or d["slug"]))
    for d in res.get("merged") or []:
        print("  %-40s (%s) -> %d new card(s) added, %d already here"
              % (d["name"], d.get("path") or d["slug"], d["added"], d["already"]))
    if res["media"]["copied"]:
        print("  pictures and recordings copied out of the package: %d"
              % res["media"]["copied"])
    for fn in res["media"]["missing"]:
        print("  media named by a card but not in the package: %s" % fn)
    total = 0
    for d in res["decks"]:
        print("  %-40s (%s) -> %d card(s)%s"
              % (d["name"], d.get("path") or d["slug"], d["cards"],
                 " (%d kept in Anki)" % d["kept"] if d.get("kept") else ""))
        total += d["cards"]
    kept = sum(d.get("kept") or 0 for d in res["decks"] + (res.get("merged") or []))
    if kept:
        print("  kept in Anki: %d note(s) carry formatting the store cannot hold "
              "(HTML typed inside Anki).\n  They are mirrored as anki-owned and "
              "left out of every build, so a rebuild never\n  flattens them; strip "
              "the formatting inside Anki and the next sync reclaims them." % kept)
    print("total: %d card(s) across %d deck(s)" % (total, len(res["decks"])))
    print("verify with:  python3 lib/anki_export.py anki/<folder>/<slug>")


if __name__ == "__main__":
    main()
