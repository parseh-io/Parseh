#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Word times for a transcript that has not become a video yet.

The panel is still Parseh's only subtitle interchange format.  This module
keeps an ordered tape of timed atoms behind it while a transcription is being
edited, and adopts that one document as ``wordtimes.json`` only when the panel
that creates the video is the panel the document describes.

It deliberately has no HTTP or browser code.  ``sync`` is the pure reducer:
given the current panel captions it keeps ordered matching atoms, makes honest
interpolated atoms for new wording, and partitions the tape into captions.
``hold``/``adopt`` mirror wavefile.py's lifecycle.
"""
import copy
import hashlib
import io
import json
import math
import os
import re
import time
import unicodedata

WORDTIMES_FORMAT = "parseh-wordtimes/1"
FORMAT = WORDTIMES_FORMAT
HOLD = ".words"
KEEP_DAYS = 30
HISTORY_BYTES = 640 << 20
MAX_ATOMS = 200000
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16}\Z")


def _videos():
    try:
        import ytpages
        return ytpages.VIDEOS
    except Exception:  # noqa: BLE001 - this module also has standalone tests
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "videos")


def hold_dir(videos=None):
    return os.path.join(videos or _videos(), HOLD)


def hold_path(token, videos=None):
    if not isinstance(token, str) or not TOKEN_RE.match(token):
        return None
    return os.path.join(hold_dir(videos), token + ".json")


def panel_hash(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _language(code):
    try:
        import languages
        return languages.get_or_default(code)
    except Exception:  # noqa: BLE001
        return None


def pieces(text, lang=""):
    """The speech atoms visible in text, in display order.

    Spaced languages use non-space runs with punctuation removed from their
    comparison form.  Chinese/Japanese use base characters; combining marks,
    variation selectors and joiners stay with their base.  This is intentionally
    shared by capture matching and every editing operation.
    """
    L = _language(lang)
    spaced = True if L is None else bool(getattr(L, "spaced", True))
    text = str(text or "")
    if spaced:
        out = []
        for value in text.split():
            core = "".join(ch for ch in value if not unicodedata.category(ch).startswith("P"))
            if core:
                out.append(value)
        return out
    out, current = [], ""
    for ch in text:
        cat = unicodedata.category(ch)
        if ch.isspace() or cat.startswith("P"):
            if current:
                out.append(current)
                current = ""
            continue
        if (cat.startswith("M") or ch in ("\u200c", "\u200d")
                or "VARIATION SELECTOR" in unicodedata.name(ch, "")) and current:
            current += ch
        else:
            if current:
                out.append(current)
            current = ch
    if current:
        out.append(current)
    return out


def key(text, lang=""):
    """A conservative comparison key; never changes text shown to the person."""
    value = unicodedata.normalize("NFC", str(text or ""))
    L = _language(lang)
    try:
        value = L.strip(value) if L is not None else value
    except Exception:  # noqa: BLE001
        pass
    value = "".join(ch for ch in value if not unicodedata.category(ch).startswith(("P", "M")))
    value = value.replace("\u0640", "").replace("\u200c", "").replace("\u200d", "")
    value = value.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک")
    return "".join(value.split()).casefold()


def _number(value, default=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    value = float(value)
    return value if math.isfinite(value) else default


def _atom(job, ordinal, text, start=None, end=None, source="guess", score=None, origin="capture"):
    start, end = _number(start), _number(end)
    if start is not None:
        start = max(0.0, round(start, 3))
    if end is not None:
        end = max(start if start is not None else 0.0, round(end, 3))
    return {"id": "w:%s:%06d" % (job, ordinal), "surface": str(text), "key": key(text),
            "start": start, "end": end, "time_source": source, "score": _number(score),
            "origin": origin}


def _capture_atoms(job, words, source, lang=""):
    out, ordinal = [], 0
    for row in (words or [])[:MAX_ATOMS]:
        if not isinstance(row, dict):
            continue
        text = row.get("text", row.get("word", ""))
        if not isinstance(text, str):
            continue
        # A Whisper "word" can still carry punctuation or several CJK
        # characters.  Sharing a returned span is less exact than a CTC
        # character aligner but is honest Whisper provenance.
        xs = pieces(text, lang)
        if not xs:
            continue
        a, b = _number(row.get("start")), _number(row.get("end"))
        for i, bit in enumerate(xs):
            left = a + (b - a) * i / len(xs) if a is not None and b is not None else a
            right = a + (b - a) * (i + 1) / len(xs) if a is not None and b is not None else b
            out.append(_atom(job, ordinal, bit, left, right, source, row.get("score")))
            ordinal += 1
    return out


def empty(job, lang, words, source="whisper", model=""):
    """A capture tape before it has been matched to the displayed captions."""
    atoms = _capture_atoms(job, words, source, lang)
    return {"format": FORMAT, "job": job, "clock": "video", "language": lang,
            "capture": {"source": source, "model": model or ""},
            "raw_atoms": copy.deepcopy(atoms), "atoms": atoms, "captions": [],
            "retired_atoms": [], "pins": {}, "revision": 0, "history": [],
            "history_bytes": 0, "panel_sha256": ""}


def _caption_rows(captions, lang):
    out, flat = [], []
    for c in captions or []:
        if not isinstance(c, dict):
            continue
        text = c.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        first = len(flat)
        for bit in pieces(text, lang):
            flat.append({"surface": bit, "key": key(bit, lang)})
        out.append({"text": text, "chapter": c.get("chapter"), "start": _number(c.get("start")),
                    "first": first, "last": len(flat)})
    return out, flat


def _interpolate(atoms):
    """Give only new atoms an honest non-recording time, between neighbours."""
    for i, atom in enumerate(atoms):
        if atom.get("start") is not None:
            continue
        left = next((a for a in reversed(atoms[:i]) if a.get("end") is not None), None)
        right = next((a for a in atoms[i + 1:] if a.get("start") is not None), None)
        if left and right and right["start"] >= left["end"]:
            # Assign the unanchored run together below.  This one-word form is
            # intentionally simple; a later pass fixes all members of a run.
            atom["start"], atom["end"] = left["end"], right["start"]
            atom["time_source"] = "interpolated"
        elif left:
            atom["start"], atom["end"] = left["end"], left["end"]
            atom["time_source"] = "estimated"
        elif right:
            atom["start"], atom["end"] = right["start"], right["start"]
            atom["time_source"] = "estimated"
        else:
            atom["start"], atom["end"] = None, None
            atom["time_source"] = "guess"


def _match(old, wanted, job, revision):
    """Linear, local order-preserving carry for an edit.

    A small look-ahead makes a normal insertion/deletion preserve surrounding
    identities while avoiding a global quadratic diff for an hour-long panel.
    Ambiguous repeated words simply match at their current ordered position.
    """
    old = [copy.deepcopy(a) for a in old]
    new, retired, i, j, made = [], [], 0, 0, 0
    window = 32
    while i < len(old) and j < len(wanted):
        if old[i].get("key") == wanted[j]["key"]:
            atom = old[i]
            atom["surface"], atom["key"] = wanted[j]["surface"], wanted[j]["key"]
            new.append(atom); i += 1; j += 1; continue
        near_old = next((k for k in range(i + 1, min(len(old), i + window))
                         if old[k].get("key") == wanted[j]["key"]), None)
        near_new = next((k for k in range(j + 1, min(len(wanted), j + window))
                         if wanted[k]["key"] == old[i].get("key")), None)
        if near_old is not None and (near_new is None or near_old - i <= near_new - j):
            retired.extend(old[i:near_old]); i = near_old; continue
        if near_new is not None:
            for want in wanted[j:near_new]:
                atom = _atom(job, 900000 + revision * 10000 + made, want["surface"], origin="edit")
                atom["id"] = "w:%s:e%d:%d" % (job, revision, made)
                new.append(atom); made += 1
            j = near_new; continue
        retired.append(old[i]); i += 1
        atom = _atom(job, 900000 + revision * 10000 + made, wanted[j]["surface"], origin="edit")
        atom["id"] = "w:%s:e%d:%d" % (job, revision, made)
        new.append(atom); made += 1; j += 1
    retired.extend(old[i:])
    for want in wanted[j:]:
        atom = _atom(job, 900000 + revision * 10000 + made, want["surface"], origin="edit")
        atom["id"] = "w:%s:e%d:%d" % (job, revision, made)
        new.append(atom); made += 1
    _interpolate(new)
    return new, retired


def sync(doc, captions, lang=None):
    """Purely make *doc* describe the captions now on screen -> copied doc."""
    doc = copy.deepcopy(doc or {})
    if doc.get("format") != FORMAT:
        raise ValueError("that is not Parseh word-time state")
    language = lang or doc.get("language") or ""
    rows, wanted = _caption_rows(captions, language)
    if len(wanted) > MAX_ATOMS:
        raise ValueError("that transcript has too many words to time")
    revision = int(doc.get("revision") or 0) + 1
    atoms, retired = _match(doc.get("atoms") or doc.get("raw_atoms") or [], wanted,
                            doc.get("job") or "held", revision)
    pins = dict(doc.get("pins") or {})
    caprows = _rows_for(doc, rows, atoms)
    doc.update({"language": language, "atoms": atoms, "captions": caprows,
                "retired_atoms": (doc.get("retired_atoms") or []) + retired,
                "pins": pins, "revision": revision})
    return doc


def _rows_for(doc, rows, atoms):
    pins = dict(doc.get("pins") or {})
    caprows = []
    for n, row in enumerate(rows):
        first, last = row["first"], row["last"]
        first_id = atoms[first]["id"] if first < last else ""
        caprows.append({"id": "c:%s" % first_id if first_id else "c:empty:%d" % n,
                        "first": first, "last": last, "text": row["text"],
                        "chapter": row["chapter"], "start_pin": pins.get(first_id)})
    return caprows


def repartition(doc, captions, lang=None):
    """The same words cut into other captions -> (copied doc, "same words")
    -- or, where the words are not the tape's any more, what `sync` makes of
    them -> (copied doc, "matched").

    A boundary moved between two captions of an added video (reflow.py) says
    no new word and loses none: the tape's atoms keep their identities and
    their times and only the partition changes, so nothing is retired, no
    revision is counted, and putting the boundary back gives back the very
    document it was (which is what makes the move's Undo exact here too).
    """
    doc = copy.deepcopy(doc or {})
    if doc.get("format") != FORMAT:
        raise ValueError("that is not Parseh word-time state")
    language = lang or doc.get("language") or ""
    rows, wanted = _caption_rows(captions, language)
    atoms = doc.get("atoms") or []
    if len(atoms) != len(wanted) or any(a.get("key") != w["key"]
                                        for a, w in zip(atoms, wanted)):
        return sync(doc, captions, lang), "matched"
    for atom, want in zip(atoms, wanted):
        atom["surface"] = want["surface"]
    doc["captions"] = _rows_for(doc, rows, atoms)
    return doc, "same words"


# what a time of a word may come from that was HEARD (the recording, or a
# person who set it by ear) -- never one worked out between neighbours
HEARD = ("interpolated", "estimated", "guess")


def heard(atom):
    """Does this atom carry a time taken from the sound?"""
    return isinstance(atom, dict) and atom.get("start") is not None \
        and (atom.get("time_source") or "guess") not in HEARD


def shift_all(doc, seconds):
    doc = copy.deepcopy(doc)
    by = _number(seconds)
    if by is None or not by:
        return doc
    if any(a.get("start") is not None and a["start"] + by < 0 for a in doc.get("atoms", [])):
        raise ValueError("that would take a word before the video begins")
    for atom in doc.get("atoms", []):
        for name in ("start", "end"):
            if atom.get(name) is not None:
                atom[name] = round(atom[name] + by, 3)
    doc["pins"] = {k: round(v + by, 3) for k, v in (doc.get("pins") or {}).items()}
    for cap in doc.get("captions", []):
        first = int(cap.get("first") or 0)
        if 0 <= first < len(doc.get("atoms") or []):
            cap["start_pin"] = doc["pins"].get(doc["atoms"][first]["id"])
    return doc


def set_pins(doc, pins):
    doc = copy.deepcopy(doc)
    known = {a.get("id") for a in doc.get("atoms", [])}
    # The editor sends the complete current set after it has loaded a
    # projection.  Replacement (rather than merge) is what makes an explicit
    # deletion or a confirmed join actually remove a person-set start.
    kept = {}
    for pin in pins or []:
        if not isinstance(pin, dict):
            continue
        atom, at = pin.get("atom"), _number(pin.get("start"))
        if isinstance(atom, str) and atom in known and at is not None and at >= 0:
            kept[atom] = round(at, 3)
    doc["pins"] = kept
    for cap in doc.get("captions", []):
        first = int(cap.get("first") or 0)
        if 0 <= first < len(doc.get("atoms") or []):
            cap["start_pin"] = kept.get(doc["atoms"][first]["id"])
    return doc


def orphaned_pins(doc):
    """Pins whose atoms are no longer caption starts, never silently ignored."""
    atoms = doc.get("atoms") or []
    starts = {atoms[int(c.get("first") or 0)].get("id")
              for c in doc.get("captions") or []
              if 0 <= int(c.get("first") or 0) < len(atoms)}
    return sorted(atom for atom in (doc.get("pins") or {}) if atom not in starts)


def caption_start(doc, cap):
    if cap.get("start_pin") is not None:
        return cap["start_pin"]
    first = int(cap.get("first") or 0)
    atoms = doc.get("atoms") or []
    return atoms[first].get("start") if 0 <= first < len(atoms) else None


def projection(doc):
    """The safe browser projection: caption atom starts and source counts."""
    atoms, rows = doc.get("atoms") or [], []
    counts = {}
    for atom in atoms:
        source = atom.get("time_source") or "guess"
        counts[source] = counts.get(source, 0) + 1
    for cap in doc.get("captions") or []:
        first, last = int(cap.get("first") or 0), int(cap.get("last") or 0)
        rows.append({"id": cap.get("id"), "atom": atoms[first]["id"] if first < len(atoms) else "",
                     "atoms": [a.get("id") for a in atoms[first:last]],
                     "starts": [a.get("start") for a in atoms[first:last]],
                     "ends": [a.get("end") for a in atoms[first:last]],
                     "sources": [a.get("time_source") for a in atoms[first:last]],
                     "start": caption_start(doc, cap), "pin": cap.get("start_pin")})
    return {"revision": doc.get("revision", 0), "captions": rows, "counts": counts,
            "source": (doc.get("capture") or {}).get("source", "whisper")}


def timed_stream(doc):
    """Words in panel order for tidy.py's recording-aware mode."""
    return [{"word": a.get("surface", ""), "start": a.get("start"), "end": a.get("end"),
             "source": a.get("time_source", "guess")} for a in doc.get("atoms") or []]


def _write(path, doc):
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def clean(doc):
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        return None
    if not isinstance(doc.get("atoms"), list) or len(doc["atoms"]) > MAX_ATOMS:
        return None
    return doc


def hold(token, doc, videos=None):
    path = hold_path(token, videos)
    if path is None or clean(doc) is None:
        raise ValueError("that is not word times for a transcription job")
    _write(path, doc)
    return len(doc.get("atoms") or [])


def load(token, videos=None):
    path = hold_path(token, videos)
    if not path:
        return None
    try:
        with io.open(path, encoding="utf-8") as f:
            return clean(json.load(f))
    except (OSError, ValueError, TypeError, RecursionError):
        return None


def save(token, doc, videos=None):
    return hold(token, doc, videos)


def held(token, videos=None):
    return load(token, videos) is not None


def drop(token, videos=None):
    path = hold_path(token, videos)
    gone = False
    for name in (path, path + ".tmp") if path else ():
        try:
            os.unlink(name); gone = True
        except OSError:
            pass
    return gone


def adopt(token, video_dir, panel, language, videos=None):
    """Move a matching held document beside a new video, or leave it alone."""
    doc = load(token, videos)
    if doc is None or doc.get("language") != language or doc.get("panel_sha256") != panel_hash(panel):
        return {"kept": False}
    path = os.path.join(video_dir, "wordtimes.json")
    try:
        _write(path, doc)
    except OSError:
        return {"kept": False}
    drop(token, videos)
    return {"kept": True, "words": len(doc.get("atoms") or []),
            "source": (doc.get("capture") or {}).get("source", "whisper")}


def sweep(days=KEEP_DAYS, videos=None, now=None):
    where, now, removed = hold_dir(videos), now or time.time(), 0
    try:
        names = os.listdir(where)
    except OSError:
        return 0
    for name in names:
        path = os.path.join(where, name)
        try:
            if name.endswith(".tmp") or now - os.path.getmtime(path) > days * 86400:
                os.unlink(path); removed += 1
        except OSError:
            pass
    return removed
