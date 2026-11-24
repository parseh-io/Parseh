#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The clip tray: the recordings cut out of a book's narration or a film, or
recorded from a YouTube video playing in the tab, and the frames captured
from a video, waiting to be put on a card.

    import clips
    rec = clips.cut("books/english/x/audio/a.mp3", 12.3, 13.1, "hello",
                    {"lang": "en", "label": "1.2", "source": {"kind": "book"}})
    rec["path"]      # "audio/hello-3fa9c2.mp3" -- paste it anywhere
    clips.listing(lang="en", kind="audio")

ONE FLAT FOLDER at the top of the toolbox, `clips/`, holding each clip and a
JSON file beside it saying where it came from:

    clips/<name>          the recording or the picture
    clips/<name>.json     {"lang", "label", "text", "source", "created", "duration"?}

A clip is made where the sentence is -- the book reader, the video player --
and used somewhere else: an Anki card, an exercise deck, a studio document.
None of those has the file, so each of them looks here for the names its
markdown mentions (store.adopt_media, decks.add_item, anki_store.add_card)
and copies the file in.  That is why a NAME IS UNIQUE ACROSS THE TOOLBOX,
`<clean stem of the hint>-<6 hex>.<ext>`: `audio/<name>` pasted into any
document or deck names this one file and no other, and a copy never has to
be renamed on arrival.

The kinds, by name:

    audio   audiofile.NAME_RE       a recording, in any format audiofile takes
    image   IMAGE_RE                a PNG or a JPEG (a captured frame)

The folder is personal and git-ignored (clips/README.md is the one tracked
file).  Nothing here deletes a clip on its own: a clip that went onto a card
was copied, so emptying the tray breaks nothing already made.  A person
deletes clips from the pages -- the tray's own page at /clips/ (one, or all
of them: `empty()`), and a studio document's Recordings... -- never from a
file manager.

Standard library only; lib/ imports nothing outside itself.
"""
import base64
import binascii
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import time

import audiofile
import synctouch     # the change log's hint, one set.add (docs/sync.md)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "clips")
# THE SHAPE OF clips/<name>.json, the file beside each clip saying where it
# came from, as a number (lib/version.py FORMATS); the file carries none.
# RAISE IT when the shape changes so that the Parseh before this one would
# read a clip's record wrong; a key an older reader ignores is not such a
# change.
INFO_FORMAT = 1

IMAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._\-]*\.(?:png|jpe?g)$")
IMAGE_MAX = 15 * 1024 * 1024        # a frame; the studio's own picture ceiling

# a clip is a word or a sentence, not a chapter: a window longer than this is
# a slip of the cursor, and cutting it would only fill the tray
MAX_SECONDS = 300

URL = "/clips/media/"               # where serve.py answers for the tray

_LABEL_MAX, _TEXT_MAX, _SOURCE_MAX = 200, 2000, 500
_SOURCE_KEYS = ("kind", "book", "narration", "video", "title", "url", "start", "end")


class ClipError(Exception):
    """A clip refused or not made; the message says why, to the person."""


def set_dir(path):
    """Point the tray somewhere else (the tests)."""
    global DIR
    DIR = str(path)


def kind_of(name):
    """"audio", "image", or None: what a tray name is, by its name alone."""
    if not isinstance(name, str) or "/" in name or "\\" in name:
        return None
    if audiofile.NAME_RE.match(name):
        return "audio"
    if IMAGE_RE.match(name):
        return "image"
    return None


def path(name):
    """The file of one clip; KeyError for a name that is no clip's."""
    if not kind_of(name):
        raise KeyError(name)
    p = os.path.join(DIR, name)
    if not os.path.isfile(p):
        raise KeyError(name)
    return p


def delete(name):
    """Take one clip out of the tray, its JSON with it."""
    p = path(name)
    os.remove(p)
    try:
        os.remove(p + ".json")
    except OSError:
        pass
    synctouch.touch(p)


def empty():
    """Take every clip out of the tray -- the tray page's "Empty the tray".
    Only clips go: clips/README.md, a file still being written, anything
    else somebody put there stays.  Returns how many went."""
    gone = 0
    for rec in listing():
        try:
            delete(rec["name"])
            gone += 1
        except (KeyError, OSError):
            pass            # gone meanwhile, or not ours to remove
    return gone


def number(v):
    """A finite float of a JSON number, or None -- a bool is not a number,
    and neither is NaN, an infinity, or an integer too long for a float."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        f = float(v)
    except OverflowError:
        return None
    return f if math.isfinite(f) else None


def span(start, end, limit=MAX_SECONDS):
    """(start, end) as seconds, or ClipError: two numbers, the start at or
    after zero, the end after it, and no more than `limit` apart."""
    try:
        if isinstance(start, bool) or isinstance(end, bool):
            raise TypeError
        s, e = float(start), float(end)
    except (TypeError, ValueError, OverflowError):
        raise ClipError("start and end must be numbers of seconds")
    if not (math.isfinite(s) and math.isfinite(e)):
        raise ClipError("start and end must be numbers of seconds")
    s = max(0.0, s)
    if not e > s:
        raise ClipError("the end must come after the start")
    if e - s > limit:
        raise ClipError("a clip is at most %d seconds long" % limit)
    return round(s, 3), round(e, 3)


# ------------------------------------------------------------------ writing

def _clean_meta(meta):
    """What a clip's JSON may hold, and nothing else: short strings, a
    registry-shaped language code, a source of known keys."""
    meta = meta if isinstance(meta, dict) else {}

    def text(v, cap):
        return v.strip()[:cap] if isinstance(v, str) else ""
    lang = text(meta.get("lang"), 16).lower()
    if not re.match(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})?$", lang):
        lang = ""
    src = meta.get("source") if isinstance(meta.get("source"), dict) else {}
    source = {}
    for k in _SOURCE_KEYS:
        v = src.get(k)
        if number(v) is not None:
            source[k] = round(number(v), 3)
        elif isinstance(v, str) and v.strip():
            source[k] = v.strip()[:_SOURCE_MAX]
    return {"lang": lang, "label": text(meta.get("label"), _LABEL_MAX),
            "text": text(meta.get("text"), _TEXT_MAX), "source": source}


def _new_name(hint, ext):
    """`<clean stem>-<6 hex><ext>`, free in the tray."""
    stem = audiofile.clean_stem(hint or "", "clip", limit=48)
    while True:
        name = "%s-%s%s" % (stem, secrets.token_hex(3), ext)
        if not os.path.exists(os.path.join(DIR, name)):
            return name


def _temp(ext=""):
    """A scratch path inside the tray (a dot name: never listed, and a
    rename away from its place)."""
    return os.path.join(DIR, ".part-%s%s" % (secrets.token_hex(6), ext))


def _write_json(p, obj):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, p)
    synctouch.touch(p)


def plays(p):
    """How many seconds of sound the file `p` really holds: ffmpeg decodes
    it to the end and says how far it got.  ffprobe's duration is the
    container's word, which is an estimate for a VBR MP3 with no header (27 s
    of a 60 s file) and nothing at all for a header with no sound after it
    -- what ffmpeg writes for a window past the end of a recording, and what
    it makes of a browser recording that captured nothing.  0.0 when ffmpeg
    finds no sound; without ffmpeg, a WAV's header, else None."""
    exe = audiofile.ffmpeg()
    if not exe:
        return audiofile.duration(p)
    try:
        r = subprocess.run([exe, "-nostdin", "-v", "error", "-progress", "pipe:1",
                            "-i", str(p), "-vn", "-sn", "-dn", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return 0.0                  # not even opened: no sound in it
    got = re.findall(r"^out_time_(?:us|ms)=(\d+)\s*$", r.stdout, re.M)
    return int(got[-1]) / 1e6 if got else 0.0


# shorter than this is no recording: a click, or nothing at all
_LEAST = 0.01


def _place(tmp_path, name, meta, duration=None):
    """Move a finished file into the tray under `name`, write its JSON, and
    return its record."""
    info = _clean_meta(meta)
    info["created"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if duration is not None:
        info["duration"] = round(float(duration), 3)
    dest = os.path.join(DIR, name)
    _write_json(dest + ".json", info)
    os.replace(tmp_path, dest)
    return record(name)


def save_audio(data, hint="", meta=None):
    """Keep one recording -- a browser's own (a cut recorded where there is
    no ffmpeg, a YouTube video's sound recorded from its tab), or a file
    somebody chose.  The bytes decide what it is (audiofile.kind).  A WAV or
    a WebM, which is what a browser records, is re-encoded into the format
    ffmpeg writes best here, when there is an ffmpeg: a WAV is ten times the
    size and WebM does not play in Anki on every device.  Without one it is
    kept as it came."""
    data = bytes(data or b"")
    if not data:
        raise ClipError("empty upload")
    if len(data) > audiofile.MAX_BYTES:
        raise ClipError("recording larger than 30 MB")
    ext = audiofile.kind(data, hint or "")
    if not ext:
        raise ClipError("only " + audiofile.HUMAN + " recordings are supported")
    os.makedirs(DIR, exist_ok=True)
    raw = _temp(ext)
    with open(raw, "wb") as f:
        f.write(data)
    done = raw
    try:
        if ext in (".wav", ".webm") and audiofile.have_ffmpeg() \
                and audiofile.best_output()[0] != ext:
            try:
                done = audiofile.transcode(raw, _temp())
            except audiofile.AudioError:
                done = raw           # a recording is never lost to a codec
        # a capture that got no samples still has a header, and ffmpeg
        # re-encodes that into a file that plays nothing: not a clip
        length = plays(done)
        if length is not None and length < _LEAST:
            raise ClipError("the recording holds no sound")
        out_ext = os.path.splitext(done)[1]
        return _place(done, _new_name(hint, out_ext), meta,
                      length if length is not None else audiofile.duration(done))
    finally:
        for p in {raw, done}:
            if os.path.exists(p):
                os.remove(p)


def _image_bytes(data):
    """Bytes, or a `data:image/...;base64,` URL as text or bytes -> bytes."""
    if isinstance(data, (bytes, bytearray, memoryview)):
        data = bytes(data)
        if not data.startswith(b"data:"):
            return data
        data = data.decode("ascii", "replace")
    if isinstance(data, str):
        s = data.strip()
        if not s.startswith("data:image/") or ";base64," not in s[:64]:
            raise ClipError("only a PNG or JPEG picture can be kept")
        try:
            return base64.b64decode(s.split(",", 1)[1], validate=False)
        except (binascii.Error, ValueError):
            raise ClipError("the picture's data URL is not base64")
    raise ClipError("only a PNG or JPEG picture can be kept")


def save_image(data, hint="", meta=None):
    """Keep one picture -- a frame captured from a video.  PNG or JPEG, by
    its first bytes; a `data:` URL is taken as it comes off a canvas."""
    blob = _image_bytes(data)
    if not blob:
        raise ClipError("empty upload")
    if len(blob) > IMAGE_MAX:
        raise ClipError("picture larger than 15 MB")
    if blob.startswith(b"\x89PNG\r\n\x1a\n"):
        ext = ".png"
    elif blob.startswith(b"\xff\xd8\xff"):
        ext = ".jpg"
    else:
        raise ClipError("only a PNG or JPEG picture can be kept")
    os.makedirs(DIR, exist_ok=True)
    tmp = _temp(ext)
    try:
        with open(tmp, "wb") as f:
            f.write(blob)
        return _place(tmp, _new_name(hint, ext), meta)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def cut(src, start, end, hint="", meta=None):
    """Cut [start, end] seconds out of `src` (a narration, a film) into the
    tray, in the best format ffmpeg writes here."""
    s, e = span(start, end)
    if not os.path.isfile(str(src)):
        raise ClipError("the recording is not on this machine")
    if not audiofile.have_ffmpeg():
        raise ClipError("ffmpeg is not installed")
    os.makedirs(DIR, exist_ok=True)
    base = _temp()
    out = None
    try:
        try:
            out = audiofile.extract(str(src), s, e, base)
        except audiofile.AudioError as err:
            raise ClipError(str(err))
        # ffmpeg asked for a window past the end writes a file anyway -- a
        # header with no sound in it.  The output is what tells, not the
        # recording's length up front: ffprobe only estimates that for a
        # VBR MP3 with no header, and would refuse real cuts in its tail
        got = plays(out)
        if got is not None and got < _LEAST:
            raise ClipError("there is no sound at %.2f s: the recording ends before it" % s)
        meta = dict(meta) if isinstance(meta, dict) else {}
        source = dict(meta.get("source") or {}) if isinstance(meta.get("source"), dict) else {}
        source.setdefault("start", s)
        source.setdefault("end", e)
        meta["source"] = source
        return _place(out, _new_name(hint, os.path.splitext(out)[1]), meta,
                      got if got is not None else e - s)
    finally:
        if out and os.path.exists(out):
            os.remove(out)
        for leftover in (base + x for x in (".mp3", ".m4a", ".wav")):
            if os.path.exists(leftover):
                os.remove(leftover)


# ------------------------------------------------------------------ reading

def record(name):
    """One clip as the pages see it (KeyError when there is none)."""
    p = path(name)
    kind = kind_of(name)
    try:
        with open(p + ".json", encoding="utf-8") as f:
            info = json.load(f)
        if not isinstance(info, dict):
            info = {}
    except (OSError, ValueError):
        info = {}                   # a file dropped into the tray by hand
    st = os.stat(p)
    clean = _clean_meta(info)
    out = {"name": name, "kind": kind,
           "path": ("audio/" if kind == "audio" else "images/") + name,
           "url": URL + name, "size": st.st_size,
           "lang": clean["lang"], "label": clean["label"], "text": clean["text"],
           "source": clean["source"],
           "created": info.get("created") if isinstance(info.get("created"), str)
           else time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))}
    if number(info.get("duration")) is not None:
        out["duration"] = info["duration"]
    return out


def listing(lang=None, kind=None):
    """Every clip, newest first; `lang` and `kind` narrow it."""
    try:
        names = os.listdir(DIR)
    except OSError:
        return []
    out = []
    for name in names:
        k = kind_of(name)
        if not k or (kind and k != kind):
            continue
        try:
            rec = record(name)
        except (KeyError, OSError):
            continue
        if lang and rec["lang"] != lang:
            continue
        try:
            # the second a clip was made, and within one second the file's
            # own clock: two cuts in a row list in the order they were made
            mtime = os.stat(os.path.join(DIR, name)).st_mtime_ns
        except OSError:
            continue
        out.append((rec["created"], mtime, name, rec))
    out.sort(key=lambda t: t[:3], reverse=True)
    return [t[3] for t in out]


def copy_to(name, dest_dir, dest_name=None):
    """Copy a clip into another store's folder; returns the path written."""
    src = path(name)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, dest_name or name)
    tmp = dest + ".part"
    shutil.copyfile(src, tmp)
    os.replace(tmp, dest)
    return dest
