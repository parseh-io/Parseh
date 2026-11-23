#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pull edits made INSIDE Anki back into the anki/ deck store.

    python3 lib/sync_apkg.py <deck exported from Anki>.apkg [--dry-run]

Why this exists.  The store is the ground truth the .apkg is built from,
and the build stamps every note "modified now" -- so importing a rebuilt
deck OVERWRITES, for every guid-matched note, whatever was edited inside
Anki since the last import.  The safe workflow is therefore pull before
push: export the deck from Anki (File > Export, "Anki Deck Package" --
scheduling does not matter, media included if images were edited), run
this script, and only then rebuild and re-import.  After a sync the store
says exactly what Anki says, so the re-import adds the new cards and
re-asserts identical content on the rest: no edit is lost, nothing
clashes.

What one sync does.  Notes are matched to store cards BY GUID, across
the WHOLE store -- a note moved to a different deck inside Anki is
updated where it lives here, and the move is reported:

  * guid known, note still one of this project's own note types (a
    language's vocab or opposites pair, anki_export.MODELS) and
    its fields still say only what the store can hold: the store card's
    content is UPDATED in place from the note -- fields, tags, the
    Reverse flag (emptying a note's Reverse inside Anki kills its
    reverse card, and that sticks), images and recordings (including one
    whose bytes changed under its old name).  The card keeps its file, its id
    and its provenance.
  * guid known, note converted to some OTHER note type inside Anki
    (Change Note Type -> Basic, say): the note has been TAKEN OVER by
    Anki.  The store card is rewritten as an "anki-owned" mirror -- guid
    and provenance kept, the note's model name and raw fields recorded --
    and anki_export.build_deck EXCLUDES owned cards from every future
    .apkg.  Since an Anki import never deletes notes, the note now lives
    in Anki alone, permanently out of this pipeline's reach.  This is the
    supported road to per-direction cards: inside Anki, duplicate the
    note and strip each copy to one direction (Change Note Type with the
    field mapping doing the work), then sync; both copies become owned
    mirrors here and no future export will touch or resurrect them.
  * guid known, note still a project note type but carrying formatting
    the store cannot represent (bold, colours, an extra field of HTML --
    anything a rebuild could not reproduce): treated exactly like a
    takeover, and reported as such.  Leaving it a normal card would mean
    the next export flattens the formatting; going anki-owned means Anki
    keeps it as made.  Strip the formatting inside Anki and the next
    sync reclaims the card automatically.
  * guid new, note of a project note type: a card created inside Anki --
    ADDED to the store as a normal card (file apkg-<guid>.json).
  * guid new, foreign note type (e.g. the duplicate made when splitting
    directions, which gets a fresh guid): added as an anki-owned mirror.
  * card in a synced deck whose guid the export does not carry anywhere:
    REPORTED, never deleted -- it is either a card added from the
    websites since the last import (fine, the next import adds it) or
    one deliberately deleted inside Anki (then delete the listed file by
    hand, or the next import resurrects it).  A script cannot tell the
    two apart, so it refuses to guess.

Reads every .apkg shape (modern zstd anki21b, Anki 2.1's plain anki21,
legacy anki2), like import_apkg.py, whose helpers it shares.  import_apkg.py remains the
bootstrap tool for a deck the store has never seen; THIS is the tool for
a deck it already holds (import_apkg would duplicate any card whose file
is not named after its guid).  A package this toolbox BUILT is never
synced -- it says nothing about what Anki holds -- and run_sync answers
with what import_apkg can bring in from it instead.
"""
import argparse
import hashlib
import json
import os
import re
import struct
import sys
import tempfile
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anki_export as ax
import languages            # anki_export has put the toolbox's lib/ on the path
import scratch              # where a package is opened: .tmp/ in Parseh's folder (lib/scratch.py)
import anki_store
import import_apkg as ia
import notetypes
from import_apkg import (FIELD_MAP, BR_RE, PARSED_FIELDS, extract_media,  # noqa: F401
                         faithful, media_index, owned_mirror)

# the content a note carries; everything else on a card (id, guid,
# created, video, book, time) is store identity and survives an update.
# `lang` is content too: the note type says which language a note is in,
# so a note whose type was changed to another language's inside Anki
# (Change Note Type) comes home as that language's card
CONTENT_KEYS = ("kind", "lang", "fa", "kana", "tr", "en", "context", "opp",
                "opp_kana", "opp_tr", "notes", "bidirectional",
                "reverse_only", "tags", "source", "img_front", "img_back",
                "snd_front", "snd_back")
STR_KEYS = ("fa", "kana", "tr", "en", "context", "opp", "opp_kana", "opp_tr",
            "notes")

# fields compared on their PARSED meaning in the fidelity check: losing
def model_names_fields(con):
    """{mid: (name, [field names])} for every note type in the collection,
    whichever schema holds it."""
    out = {}
    try:                                   # schema 18: real tables
        names = dict(con.execute("select id, name from notetypes"))
        flds = {}
        for ntid, ord_, name in con.execute(
                "select ntid, ord, name from fields order by ntid, ord"):
            flds.setdefault(ntid, []).append(name)
        for mid, name in names.items():
            out[mid] = (name, flds.get(mid, []))
    except Exception:                      # legacy: one JSON blob in col
        (blob,) = con.execute("select models from col").fetchone()
        for mid, m in json.loads(blob).items():
            out[int(mid)] = (m.get("name", "?"),
                             [f["name"] for f in m.get("flds", [])])
    return out


# ---- the package's media map, both formats -------------------------------

# ---- the merge itself ----------------------------------------------------

SEEN_NAME = "seen.json"


def load_seen(anki_dir):
    """{guid: date} -- every note an export has ever shown us.

    This is what makes a DELETION distinguishable from a card Anki has
    simply not been given yet.  Losing this file is not catastrophic but
    it is not a no-op either: cards whose only witness was this file --
    the ones the dashboards named -- stop looking known to Anki and are
    never proposed for removal, while apkg-* cards still are, on their
    filename alone (see known_to_anki).
    """
    try:
        with open(os.path.join(anki_dir, SEEN_NAME), encoding="utf-8") as f:
            raw = json.load(f)
        return {k: v for k, v in raw.items()} if isinstance(raw, dict) else {}
    except (OSError, ValueError):
        return {}


def save_seen(anki_dir, seen):
    os.makedirs(anki_dir, exist_ok=True)
    path = os.path.join(anki_dir, SEEN_NAME)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=0, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def known_to_anki(card, fns, seen):
    """Has this note ever actually been in the collection?

    Two independent witnesses, either of which settles it:
      * a previous sync recorded its guid (seen.json), or
      * SOME file for this guid was WRITTEN from an export --
        apkg-<guid>.json -- so Anki demonstrably held the note.
    A note with neither has only ever existed here, which means its
    absence from an export says nothing at all.

    `fns` is every filename carrying this guid, not just the indexed one:
    when a note has two files the index keeps whichever sorts first, and
    that must not decide the question on its own.
    """
    if card.get("guid") in seen:
        return True
    return any(os.path.basename(f).startswith("apkg-") for f in fns)


def retire_card(anki_dir, path, fn, why):
    """Take a card out of the deck WITHOUT destroying it.

    The file moves to anki/<folder>/<slug>/deleted/ rather than being
    unlinked: build_deck only ever reads cards/, so the note stops being
    exported immediately, and a mistake costs a file move to undo rather
    than being unrecoverable.  Deleting notes is Anki's job; this only
    stops re-asserting them.  `path` is a deck's directory relative to
    anki/ (anki_store.decks()["path"]) -- never a bare slug, which two
    languages may share.
    """
    src = os.path.join(anki_dir, path, "cards", fn)
    ddir = os.path.join(anki_dir, path, "deleted")
    os.makedirs(ddir, exist_ok=True)
    dst = os.path.join(ddir, fn)
    if os.path.exists(dst):                # never overwrite an older
        stem, ext = os.path.splitext(fn)   # retirement of the same name
        base = time.strftime("%Y%m%d-%H%M%S")
        n = 0
        while os.path.exists(dst):
            n += 1
            dst = os.path.join(ddir, "%s-%s%s%s"
                               % (stem, base, "" if n == 1 else "-%d" % n, ext))
    card = anki_store.read_json(src)
    if isinstance(card, dict):
        card["retired"] = {"when": time.strftime("%Y-%m-%d %H:%M:%S"),
                           "why": why}
        anki_store.write_json(src, card)
    os.replace(src, dst)
    return os.path.relpath(dst, anki_dir)


def load_store(anki_dir, paths):
    """What the store holds, indexed by guid, collection-wide (Anki guids
    are collection-wide, and a note may have been moved between decks --
    between two LANGUAGES' decks now, which is the same thing to a guid).

    Returns (index, dups, retired), each keyed by guid and holding the
    deck's `path` (its directory relative to anki/, "japanese/verbs"):
      index   {guid: (path, filename, card)} -- the representative file
      dups    {guid: [(path, filename), ...]} -- EVERY file for that guid,
              because retiring only the first would leave the note still
              being exported by the second while the report claims it is
              gone
      retired {guid: (path, filename)} -- what sits under deleted/, so a
              guid that comes back in a later export can be un-retired
              instead of being minted afresh as a second file
    """
    out, dups, retired = {}, {}, {}
    for path in paths:
        cdir = os.path.join(anki_dir, path, "cards")
        if os.path.isdir(cdir):
            for fn in sorted(os.listdir(cdir)):
                if not fn.endswith(".json"):
                    continue
                card = anki_store.read_json(os.path.join(cdir, fn))
                if isinstance(card, dict) and card.get("guid"):
                    out.setdefault(card["guid"], (path, fn, card))
                    dups.setdefault(card["guid"], []).append((path, fn))
        ddir = os.path.join(anki_dir, path, "deleted")
        if os.path.isdir(ddir):
            for fn in sorted(os.listdir(ddir)):
                if not fn.endswith(".json"):
                    continue
                card = anki_store.read_json(os.path.join(ddir, fn))
                if isinstance(card, dict) and card.get("guid"):
                    retired.setdefault(card["guid"], (path, fn))
    return out, dups, retired


def unretire(anki_dir, path, fn):
    """Bring a retired card back to the deck it belongs to.

    A guid reappearing in an export means the note is in Anki again --
    undone there, or never really gone.  Minting a fresh file for it
    would leave TWO files for one guid (the note exported twice, its
    provenance stranded in deleted/), so the retired file is what comes
    back.
    """
    src = os.path.join(anki_dir, path, "deleted", fn)
    dst = os.path.join(anki_dir, path, "cards", fn)
    card = anki_store.read_json(src)
    if isinstance(card, dict):
        card.pop("retired", None)
        anki_store.write_json(src, card)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.replace(src, dst)
    return card if isinstance(card, dict) else None


def content_of(card):
    """The card's content in canonical form, so that None-vs-missing or
    an unset tag list can never masquerade as an edit."""
    out = {}
    for k in CONTENT_KEYS:
        v = card.get(k)
        if k in STR_KEYS:
            v = v or ""
        elif k == "tags":
            # Anki keeps tags as a set and alphabetises them on save, so
            # order can never count as an edit
            v = (sorted({t for t in v if isinstance(t, str)})
                 if isinstance(v, list) else [])
        elif k == "bidirectional":
            v = bool(card.get("bidirectional", True))
        elif k == "reverse_only":
            v = bool(v)
        elif k in ax.MEDIA_KEYS:
            # a card from before recordings has no snd_* key at all, and
            # the note it came from none either: the same thing, not an edit
            v = v or None
        elif k == "source":
            v = v if isinstance(v, dict) else {}
            v = {"label": v.get("label") or "", "url": v.get("url") or ""}
        elif k == "kind":
            v = v or "vocab"
        elif k == "lang":
            # a card written before languages were declared says nothing
            # and is Persian; the note it came back from says "fa" -- the
            # two must compare equal or every old card would look edited.
            # A value that is no registry code at all (a hand edit gone
            # wrong: "xx", a number) is kept as it is rather than read as
            # Persian or tripped over: this side of the comparison is
            # only ever COMPARED, the note's side is what gets written,
            # so the mismatch makes the sync repair the card from the
            # note's real language
            try:
                v = ax.lang_for_code(v).code
            except ValueError:
                pass
        out[k] = v
    return out


def minted_filename(cdir, guid):
    """apkg-<sanitised guid>, made injective: if the sanitised name is
    already taken by a DIFFERENT guid's card, a short hash of the exact
    guid keeps the two apart instead of silently clobbering one."""
    base = "apkg-" + re.sub(r"[^A-Za-z0-9_-]", "_", guid)
    other = anki_store.read_json(os.path.join(cdir, base + ".json"))
    if isinstance(other, dict) and other.get("guid") not in (None, guid):
        base += "-" + hashlib.sha1(guid.encode("utf-8")).hexdigest()[:8]
    return base


def new_report():
    return {"updated": [], "moved": [], "taken_over": [], "kept": [],
            "new": [], "new_owned": [], "reclaimed": [], "unretired": [],
            "unchanged": 0, "media_missing": [], "media_updated": []}


def sync_notes(anki_dir, path, notes, store, models, z, media_idx, dry_run,
               retired=None):
    """Merge one Anki deck's notes into the store.  `path` is the store
    deck's directory relative to anki/ ("persian/farsi-youtube").  `store`
    is the collection-wide guid index; cards are written where they LIVE,
    which is not always this deck -- and, since decks are filed by
    language, not always this language either: a note whose type was
    changed inside Anki keeps its file where it sits and comes home with
    the new language on the card.  `retired` maps a guid to the file
    waiting under deleted/, so a note that has come back is restored
    rather than minted a second time.  Returns (report, seen guids)."""
    rep = new_report()
    retired = retired or {}
    seen = set()

    for guid, mid, flds, tags in notes:
        seen.add(guid)
        existing = store.get(guid)
        if existing is None and guid in retired:
            # this note is in Anki again: bring its own file back rather
            # than minting a second one for the same guid
            r_path, r_fn = retired.pop(guid)
            if dry_run:
                existing = (r_path, r_fn, anki_store.read_json(
                    os.path.join(anki_dir, r_path, "deleted", r_fn)) or {})
            else:
                card = unretire(anki_dir, r_path, r_fn)
                existing = (r_path, r_fn, card or {})
            store[guid] = existing
            rep["unretired"].append("%s (in %s)" % (r_fn, r_path))
        home = existing[0] if existing else path
        cdir = os.path.join(anki_dir, home, "cards")
        mdir = os.path.join(anki_dir, home, "media")
        known = mid in FIELD_MAP
        fresh = None
        if known:
            fresh = ia.card_from_note(mid, flds, guid, tags, home)
            for side in ax.MEDIA_KEYS:
                fn = fresh.get(side)
                if fn:
                    ok, upd = extract_media(z, media_idx, fn, mdir, dry_run)
                    if not ok:
                        rep["media_missing"].append(fn)
                    elif upd:
                        rep["media_updated"].append(fn)

        if known and faithful(fresh, mid, flds):
            if existing is None:
                fresh["id"] = minted_filename(cdir, guid)
                if not dry_run:
                    os.makedirs(cdir, exist_ok=True)
                    anki_store.write_json(
                        os.path.join(cdir, fresh["id"] + ".json"), fresh)
                rep["new"].append(fresh["id"] + ".json")
                store[guid] = (home, fresh["id"] + ".json", fresh)
                continue
            _, fn, card = existing
            was_owned = card.get("anki") == "owned"
            moved = home != path
            if not was_owned and not moved \
                    and content_of(card) == content_of(fresh):
                rep["unchanged"] += 1
                continue
            merged = dict(card)
            merged.update(content_of(fresh))
            for k in ("anki", "anki_model", "anki_fields"):
                merged.pop(k, None)
            changed = content_of(card) != content_of(fresh) or was_owned
            if not dry_run and changed:
                anki_store.write_json(os.path.join(cdir, fn), merged)
            store[guid] = (home, fn, merged)
            label = "%s (in %s)" % (fn, home) if moved else fn
            if was_owned:
                rep["reclaimed"].append(label)
            elif moved:
                (rep["moved"] if changed else rep["moved"]).append(label)
            elif changed:
                rep["updated"].append(label)
            else:
                rep["unchanged"] += 1
            continue

        # Anki owns this note: a foreign note type, or a project note
        # carrying formatting a rebuild could not reproduce
        mname, fnames = models.get(mid, ("mid %s" % mid, []))
        mirror_fields = (dict(zip(fnames, flds)) if len(fnames) >= len(flds)
                         else {str(i): v for i, v in enumerate(flds)})
        new_tags = [t for t in tags.split() if t]
        if existing is not None:
            _, fn, card = existing
            mirror = dict(card)
            for k in CONTENT_KEYS:
                mirror.pop(k, None)
        else:
            base = minted_filename(cdir, guid)
            fn = base + ".json"
            mirror = {"id": base, "guid": guid,
                      "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                      "video": "", "book": ""}
        prev = (existing or (None, None, {}))[2]
        already = (prev.get("anki") == "owned"
                   and prev.get("anki_fields") == mirror_fields
                   and prev.get("anki_model") == mname
                   and (prev.get("tags") or []) == new_tags)
        mirror["kind"] = "anki"
        mirror["anki"] = "owned"
        mirror["anki_model"] = mname
        mirror["anki_fields"] = mirror_fields
        mirror["tags"] = new_tags
        if already:
            rep["unchanged"] += 1
            continue
        if not dry_run:
            os.makedirs(cdir, exist_ok=True)
            anki_store.write_json(os.path.join(cdir, fn), mirror)
        store[guid] = (home, fn, mirror)
        if existing is None:
            rep["new_owned"].append(fn)
        elif known:
            rep["kept"].append(fn)         # project type, unholdable content
        else:
            rep["taken_over"].append(fn)
    return rep, seen


REPORT_LABELS = (
    ("updated", "updated from Anki edits"),
    ("moved", "living in another store deck (updated there; moved in Anki?)"),
    ("new", "new, created inside Anki"),
    ("taken_over", "taken over (note type changed inside Anki; now "
     "anki-owned, excluded from future builds)"),
    ("kept", "kept in Anki (formatting or fields the store cannot hold; "
     "now anki-owned, excluded from future builds -- strip the "
     "formatting inside Anki and the next sync reclaims the card)"),
    ("new_owned", "new anki-owned mirrors (foreign note type)"),
    ("reclaimed", "reclaimed (back to plain content on a project note type)"),
    ("unretired", "back in Anki, so restored here from deleted/"),
)


def _deck_id(by_path, path):
    """How a report names one store deck: its path (the handle every tool
    uses), its slug, and its language -- the wizard shows the language
    beside the name, because two decks may now be called the same thing in
    two folders and the slug alone no longer says which one this is."""
    d = by_path.get(path) or {}
    L = languages.get(d.get("lang") or languages.DEFAULT)
    return {"path": path, "slug": d.get("slug") or os.path.basename(path),
            "lang": L.code, "folder": L.folder, "language": L.name,
            "legacy": bool(d.get("legacy"))}


def run_sync(apkg_path, anki_dir, dry_run=True, delete_missing=False):
    """The whole merge, as data -- so the CLI and the web wizard show the
    same thing and neither has to scrape the other's text."""
    all_decks = anki_store.decks(anki_dir) or []
    by_path = {d["path"]: d for d in all_decks}
    store_decks = {}                       # anki deck id -> (path, meta)
    for d in all_decks:
        meta = anki_store.read_json(
            os.path.join(anki_dir, d["path"], "deck.json")) or {}
        if meta.get("id") is not None:
            store_decks[meta["id"]] = (d["path"], meta)
    # matching by NAME is the fallback when the Anki deck id is unknown,
    # and a name is no longer unique: two languages may hold a deck called
    # "Videos".  An ambiguous name matches nothing rather than the first
    # one found -- syncing a deck's notes into the wrong language's deck
    # would be a mess to undo, and the report says the deck is unmatched,
    # which is true and actionable
    _named = {}
    for path, meta in store_decks.values():
        _named.setdefault(meta.get("name"), []).append((path, meta))
    by_name = {name: hits[0] for name, hits in _named.items()
               if len(hits) == 1}
    store, dups, retired = load_store(anki_dir, [d["path"] for d in all_decks])

    with tempfile.TemporaryDirectory(prefix="apkg-sync-", dir=scratch.folder()) as tmp:
        con, fmt = ia.open_collection(apkg_path, tmp)
        stamp = ia.stamp_of(con)
        if stamp:
            # A package THIS toolbox built -- the wizard's own download, or
            # one shared from another copy of Parseh.  It says nothing
            # about what Anki holds: syncing it would mark every card in it
            # as confirmed by Anki, after which the next genuine export,
            # lacking the ones never imported, would look like a mass
            # deletion.  So it is never synced -- but it can be BROUGHT IN
            # (import_apkg.import_all): a deck the store lacks is created,
            # a held one is given the cards it lacks.  Say what that would
            # be; the wizard and the CLI offer it.
            deck_of = ia.deck_names(con)
            notes = ia.read_notes(con)
            con.close()
            have = ia.store_guids(anki_dir)
            by_deck = {}
            for _, guid, mid, _, _, did in notes:
                if mid in FIELD_MAP:
                    by_deck.setdefault(did, []).append(guid)
            unmatched, held = [], []
            for did, guids in sorted(by_deck.items()):
                name = deck_of.get(did, "deck-%s" % did)
                hit = store_decks.get(did) or by_name.get(name)
                new = sum(1 for g in guids if g not in have)
                if hit is None:
                    unmatched.append({"name": name, "id": did,
                                      "notes": len(guids), "new": new})
                else:
                    held.append(dict(_deck_id(by_path, hit[0]),
                                     name=name, id=did,
                                     notes=len(guids), new=new))
            return {"format": fmt, "dry_run": bool(dry_run), "own_build": stamp,
                    "decks": [], "unmatched": unmatched, "held": held,
                    "notetypes": [], "delete_missing": bool(delete_missing)}
        deck_of = ia.deck_names(con)
        models = model_names_fields(con)
        notes = ia.read_notes(con)
        # a note type's CSS and templates live in the note type, not in
        # any note: without this the next rebuild would re-assert the
        # code's styling over whatever was set inside Anki
        snap = notetypes.snapshot(con)
        con.close()

        z = zipfile.ZipFile(apkg_path)
        media_idx = media_index(z)
        by_deck = {}
        for nid, guid, mid, flds, tags, did in notes:
            by_deck.setdefault(did, []).append((guid, mid, flds, tags))

        # Every guid the PACKAGE carries, not merely those in decks the
        # store holds.  A note moved inside Anki into some other deck --
        # the parent of a stored subdeck is the ordinary case -- is still
        # plainly present, and judging it deleted would retire a card that
        # is sitting right there in the file being read.
        seen_all = {guid for _, guid, _, _, _, _ in notes}
        synced, unmatched = [], []
        for did, deck_notes in sorted(by_deck.items()):
            name = deck_of.get(did, "deck-%s" % did)
            hit = store_decks.get(did) or by_name.get(name)
            if hit is None:
                unmatched.append({"name": name, "id": did,
                                  "notes": len(deck_notes)})
                continue
            path, meta = hit
            if path in {sl for _, sl, _ in synced}:
                # two export decks resolving onto one store deck: merge
                # them into the pass that already ran rather than letting
                # the retire loop walk the same deck twice
                rep, _ = sync_notes(anki_dir, path, deck_notes, store,
                                    models, z, media_idx, dry_run, retired)
                for i, (n0, s0, r0) in enumerate(synced):
                    if s0 == path:
                        for k in r0:
                            if isinstance(r0[k], list):
                                r0[k].extend(rep[k])
                            else:
                                r0[k] += rep[k]
                        break
                continue
            rep, _ = sync_notes(anki_dir, path, deck_notes, store,
                                models, z, media_idx, dry_run, retired)
            synced.append((name, path, rep))
        z.close()

    seen = load_seen(anki_dir)
    decks = []
    for name, path, rep in synced:
        d = dict(_deck_id(by_path, path), name=name,
                 unchanged=rep["unchanged"])
        for key, _ in REPORT_LABELS:
            d[key] = list(rep[key])
        d["media_updated"] = sorted(set(rep["media_updated"]))
        d["media_missing"] = sorted(set(rep["media_missing"]))
        # Cards of THIS deck the whole export lacks.  (A note moved to
        # another exported deck is a move, not a deletion -- seen_all is
        # collection-wide, so those never land here.)  Two very different
        # cases hide in that list, and only one is a deletion:
        #   * Anki has held this note before and no longer does -> the
        #     note was deleted inside Anki, and the store should follow;
        #   * Anki has never seen it -> it was made on the websites since
        #     the last import, and the NEXT import is what gives it to
        #     Anki.  Removing it here would throw away a new card.
        gone, pending = [], []
        for guid, (sl, fn, card) in sorted(store.items()):
            if sl != path or guid in seen_all:
                continue
            item = {"file": fn, "guid": guid,
                    "label": (card.get("fa") or card.get("anki_model")
                              or "?")[:60],
                    "made_here": bool(card.get("video") or card.get("book"))}
            fns = [f for (sl, f) in dups.get(guid, []) if sl == path] or [fn]
            (gone if known_to_anki(card, fns, seen) else pending).append(item)
        if delete_missing and not dry_run:
            for item in gone:
                # every file for this guid, not just the indexed one: a
                # second file would go on being exported while the report
                # claimed the note was gone
                files = [fn for (sl, fn) in dups.get(item["guid"], [])
                         if sl == path] or [item["file"]]
                moved = [retire_card(anki_dir, path, fn,
                                     "deleted inside Anki")
                         for fn in files
                         if os.path.exists(
                             os.path.join(anki_dir, path, "cards", fn))]
                item["moved_to"] = moved[0] if moved else None
                if len(moved) > 1:
                    item["also_moved"] = moved[1:]
                store.pop(item["guid"], None)   # cannot be walked twice
        d["deleted"] = gone
        d["pending_import"] = pending
        d["store_only"] = gone + pending          # kept for the CLI's sake
        d["changes"] = (sum(len(d[k]) for k, _ in REPORT_LABELS)
                        + len(d["media_updated"])
                        + (len(gone) if delete_missing else 0))
        decks.append(d)

    if not dry_run:
        # remember every note this export showed us, so that its ABSENCE
        # from a future export is meaningful
        today = time.strftime("%Y-%m-%d")
        for guid in seen_all:
            seen[guid] = today
        if seen_all:
            save_seen(anki_dir, seen)
    notetype_changes = ([] if dry_run
                        else notetypes.capture(anki_dir, snap, apkg_path))
    if dry_run:                            # say what WOULD be captured
        have = ax.load_overrides(anki_dir)
        for mid, sn in snap.items():
            old_sn = have.get(mid)
            if old_sn is None:
                notetype_changes.append({"mid": mid,
                                         "name": sn.get("name") or str(mid),
                                         "what": "first capture"})
            elif notetypes._core(old_sn) != notetypes._core(sn):
                what = []
                if (old_sn.get("css") or "") != (sn.get("css") or ""):
                    what.append("styling")
                if old_sn.get("templates") != sn.get("templates"):
                    what.append("templates")
                if old_sn.get("fields") != sn.get("fields"):
                    what.append("fields")
                notetype_changes.append({"mid": mid,
                                         "name": sn.get("name") or str(mid),
                                         "what": ", ".join(what) or "name"})
    return {"format": fmt, "dry_run": bool(dry_run), "decks": decks,
            "unmatched": unmatched, "notetypes": notetype_changes,
            "delete_missing": bool(delete_missing)}


def main():
    ap = argparse.ArgumentParser(
        description="pull Anki-side edits back into the deck store")
    ap.add_argument("apkg", help="a deck exported from Anki (.apkg)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change, write nothing")
    ap.add_argument("--delete-missing", action="store_true",
                    help="also retire cards Anki has held before and no "
                         "longer has (they move to anki/<folder>/<deck>/deleted/, "
                         "so the removal can be undone)")
    ap.add_argument("--anki-dir", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    anki_dir = args.anki_dir or os.path.join(root, "anki")
    try:
        res = run_sync(args.apkg, anki_dir, args.dry_run, args.delete_missing)
    except ValueError as e:                # a refusal is an answer, not a bug
        sys.exit("\n%s" % e)
    print("reading %s as %s%s" % (args.apkg, res["format"],
                                  " (dry run)" if args.dry_run else ""))
    if res.get("own_build"):
        print("\n%s is a package BUILT by Parseh (deck %r), not an export from "
              "Anki.\nIt says nothing about what Anki holds, so it is never "
              "synced -- but it can be\nbrought in:"
              % (os.path.basename(args.apkg), res["own_build"]))
        for u in res["unmatched"]:
            print("  %s: not in the store yet (%d cards)  ->  python3 "
                  "lib/import_apkg.py %r" % (u["name"], u["notes"], args.apkg))
        for d in res.get("held") or []:
            if d["new"]:
                print("  %s: already here as %s; %d of its %d cards are not yet"
                      "  ->  python3 lib/import_apkg.py %r --merge"
                      % (d["name"], d["path"], d["new"], d["notes"], args.apkg))
            else:
                print("  %s: already here as %s, and nothing in it is new here"
                      % (d["name"], d["path"]))
        return
    for u in res["unmatched"]:
        print("\n%s (Anki deck id %s): NOT in the store -- this tool only "
              "updates decks the store already holds.\n"
              "  a genuinely new deck comes in with:  "
              "python3 lib/import_apkg.py %r" % (u["name"], u["id"], args.apkg))
    for d in res["decks"]:
        print("\n%s  (%s, %s):" % (d["name"], d["path"], d["language"]))
        print("  unchanged: %d" % d["unchanged"])
        for key, label in REPORT_LABELS:
            if d[key]:
                print("  %s: %d" % (label, len(d[key])))
                for fn in d[key][:12]:
                    print("      %s" % fn)
                if len(d[key]) > 12:
                    print("      ... and %d more" % (len(d[key]) - 12))
        if d["media_updated"]:
            print("  pictures and recordings whose bytes changed inside Anki, pulled home: %d"
                  % len(d["media_updated"]))
            for fn in d["media_updated"]:
                print("      %s" % fn)
        if d["media_missing"]:
            print("  pictures and recordings referenced but not recoverable from this "
                  "export (re-export with media, or copy by hand):")
            for fn in d["media_missing"]:
                print("      %s" % fn)
        if d["deleted"]:
            if args.delete_missing and args.dry_run:
                print("  deleted inside Anki: %d card(s) -- these WOULD be "
                      "retired (moved to\n  anki/%s/deleted/) if you drop "
                      "--dry-run:" % (len(d["deleted"]), d["path"]))
            elif args.delete_missing:
                print("  deleted inside Anki, retired here: %d card(s) "
                      "(moved to anki/%s/deleted/, so this is undoable):"
                      % (len(d["deleted"]), d["path"]))
            else:
                print("  deleted inside Anki: %d card(s) -- Anki has held "
                      "these before and no\n  longer does. Pass "
                      "--delete-missing to retire them here too, or the "
                      "next\n  import will put them back:"
                      % len(d["deleted"]))
            for c in d["deleted"]:
                print("      %s   (%s)%s"
                      % (os.path.join("anki", d["path"], "cards", c["file"]),
                         c["label"],
                         "  ->  " + c["moved_to"] if c.get("moved_to") else ""))
        if d["pending_import"]:
            print("  here but not in Anki yet: %d card(s) -- made on the "
                  "websites since your\n  last import; the next import is "
                  "what gives them to Anki. Nothing to do:"
                  % len(d["pending_import"]))
            for c in d["pending_import"]:
                print("      %s   (%s)"
                      % (os.path.join("anki", d["path"], "cards", c["file"]),
                         c["label"]))

    for nt in res.get("notetypes") or []:
        print("\nnote type %r: %s %s"
              % (nt["name"], nt["what"],
                 "would be captured" if args.dry_run else "captured"))
        print("  (its styling and templates now come from your collection, "
              "so a rebuild\n   reproduces them instead of overwriting them)")

    if res["decks"] and not args.dry_run:
        print("\nnow rebuild and re-import:  the store and Anki agree, so "
              "the import only adds\nwhat is new here and disturbs nothing "
              "you edited there.")


if __name__ == "__main__":
    main()
