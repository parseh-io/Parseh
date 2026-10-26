#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""What a thing is made of, as ADDRESSES: what a phone must keep to have it
when the computer cannot be reached (TO-DO §19.3).

    offline.book(book_dir, url_base)     a book: its reader, its text, its
                                         pictures, each recording, its notes
    offline.video(video_dir, vid)        a video: its page, the player's own
                                         sheet and script, its transcript and
                                         glosses, the film if there is one here,
                                         its notes
    offline.deck(folder, slug)           a deck: its pages, its exercises,
                                         their pictures and recordings
    offline.shared()                     what every page of the app needs:
                                         the sheets, the scripts, the fonts

One answer per thing, with a VERSION for the whole of it, so the phone can
keep exactly that and know when what it holds is old.  `lib/bundle.py` already
knows what a book or a video is made of -- this is the same knowledge said as
URLs rather than as files in a zip.

THREE LISTS, because the owner chose so.  `small` is the page, the text and
the pictures, which the phone renews by itself the next time it reaches the
computer; `media` is the heavy things -- a recording, a film -- each with its
size and what it covers, which are PICKED one by one when the thing is kept,
and which never renew themselves in silence (2026-09-22).  `notes` came
later (2026-09-23), when the owner asked that a kept book keep the notes
written into its seams: it is a half-record of its own -- `small` for the
note pages, their pictures and the seams' list, `shared` for what the studio
must lend the phone, `media` for the notes' own recordings, with a `count`,
an about-size and a `version` -- and the keep sheet draws the whole of it as
ONE TICK, because nobody wants to tick thirty-four notes one at a time and
nobody wants them kept without being asked either.

EVERY ENTRY IS ONE ADDRESS.  A record is read by the sheet, by the worker,
by the freeing sweep and by whatever is written next, and an entry that
stood for several addresses would have to be expanded correctly by all of
them.  The grouping belongs where the owner sees it: in lib/keep.js, which
draws one row and fetches every address behind it.

Nothing here reads a byte of a recording: a size is the file's size and a
version is a hash of names, sizes and modification times.  Asking what a
narrated book is made of must not cost what playing it costs.

AND EVERY SMALL FILE CARRIES ITS DIGEST (the owner's decision A, 2026-09-23).
A tick in "Change what is kept" used to mean only "this address is a key in
some cache", which is true of a half-written body and true of a 503 the phone
was handed while the tunnel was going down.  So an entry the phone can afford
to check carries `digest`, the SHA-256 of the very bytes the server will send,
and the phone tests the body against it; a recording, which WebCrypto cannot
digest without holding whole in memory, carries none and is tested by its
length instead.  HOW BIG IT IS decides that, as he asked -- with a far lower
ceiling for a recording or a film (`DIGEST_MAX_MEDIA`), since those are what
get large and since the phone has to read a body whole to hash it.  A ceiling
of eight megabytes for everything had thirty-two of one book's fifty
narrations hashed at every press; a ceiling of two for them has none.

AND WHAT THE COMPUTER MAKES UP AS IT ANSWERS can have neither, and says so by
carrying `"check": "here"` (see `_door`): the phone may test that it HAS that
answer and must test nothing about it.  A page rendered from a template, a
stylesheet written out of the language registry, two files joined under one
name, a list of exercises with the scheduler's own numbers riding along in it
-- none of them has a length this file can predict, and a length nobody can
predict must not be offered as one to check against: it would have the phone
call a perfectly good page broken and leave that row unticked for ever.
Where such an entry still carries a size, the size is what the owner is being
asked to spend and not a claim about the body.
"""
import hashlib
import json
import os
import re
import sys
import threading

LIB = os.path.dirname(os.path.realpath(__file__))
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import books as booklib                                      # noqa: E402

# What every page of the app needs, whatever is kept: the palette, the tokens,
# the shared scripts and the faces that travel with the toolbox.  Kept ONCE
# for everything (the worker keeps them in a cache of their own), so a second
# book costs its own text and nothing more.
SHARED = (
    "/lib/parseh.css", "/lib/langs.css", "/lib/mobile.css", "/lib/parseh.js",
    "/lib/narrctl.js", "/lib/mobilereader.js", "/lib/mobileplayer.js",
    "/lib/wordtouch.js", "/lib/explain.js", "/lib/prefs.js", "/lib/activity.js",
    # THE GEAR (a0.5.0): the one panel every page opens for its own settings.  A kept page
    # carries the button and a panel built by this script, and a script or a sheet the phone
    # has not got is a page whose ⚙ does nothing -- or draws bare -- with the computer away
    "/lib/pagesettings.js", "/lib/pagesettings.css",
    # THE PAGE ZOOM, which parseh.js writes a tag for as the first thing on every
    # page and the studio's templates carry a tag of their own for: a kept page
    # must open offline with it, or its parser stops on a script nobody kept
    "/lib/pagezoom.js",
    # the chunks flagged to review later: the store, the sidebar and the page's
    # list.  The reader and the player load them, and /later/ is in the shell:
    # without them a phone could flag a chunk on the train and not see the list
    "/lib/later.js", "/lib/later.css",
    # and what the two pages give it: the cards made from the list (lib/later-cards.js, the
    # player's page loads it itself) and the book reader's four ways to flag, its marks and
    # its going to a chunk (lib/later-reader.js, which parseh.js loads into every reader)
    "/lib/later-cards.js", "/lib/later-reader.js",
    # what a reader of a book an agent is making adds to itself (parseh.js loads it
    # into every reader; it asks one question and does nothing for any other book)
    "/lib/making.js",
    # and the book reader's use of the gear: its groups and rows, the levels' names,
    # Diacritics (parseh.js loads it into every reader beside the toolkit; a kept book
    # without it has a ⚙ that opens on nothing)
    "/lib/gear-reader.js",
    # keeping, and the chip that says the computer cannot be reached: without
    # it a kept page would open offline and say nothing about being offline
    "/lib/keep.js",
    "/lib/wordline.js", "/lib/llm.js", "/lib/llmrow.js",
    # THE TRANSLATION HELPER, AND WHY IT IS NAMED HERE.  Every reader loads
    # /lib/mt.js as a PARSER-BLOCKING script in its head (lib/tex2html.py),
    # and it was in no list: offline the request missed every cache, the
    # parser stopped on that tag, and the document never reached its body --
    # so a kept book opened to a page half drawn and nothing of its own
    # script ever ran.  It was the one address missing, and it was missing
    # for every book on the shelf (the owner, in airplane mode, 2026-09-23).
    "/lib/mt.js",
    # a vocabulary line in the books' macros, drawn by the first and written
    # with the buttons of the second, on the player's page and in every reader
    "/lib/vocline.js", "/lib/vocbuttons.js",
    # what a reader's own script calls into as it starts: without these the
    # page opens offline and throws before it is drawn
    "/lib/decomposition.js", "/lib/decomposition.css",
    "/lib/cardkit.js", "/lib/cardkit.css", "/lib/timeline.js", "/lib/timeline.css",
    "/lib/fonts/Vazirmatn.woff2", "/lib/fonts/NotoNastaliqUrdu.woff2",
    "/lib/fonts/NotoNaskhArabic.woff2", "/lib/fonts/NotoSerifDevanagari.woff2",
    # the face that sets the NAME Parseh in the bar of every page and in the hub's
    # title (lib/parseh.css): 100 kB, once, so that a page opened with the computer
    # asleep writes the name as it is written when the computer is there
    "/lib/fonts/texgyrechorus-mediumitalic.otf",
    # THE ICON EVERY PAGE OF THE APP CARRIES.  lib/parseh.js (appHead) hangs
    # <link rel="apple-touch-icon" href="/lib/icons/apple-touch-icon.png"> in
    # the head of every page that was not built with the app's tags already,
    # and lib/mobile.py writes the same tag into the ones that were -- so a
    # reader, a player, a deck and the hub all ask for it, and not one list
    # named it.  Four and a half kilobytes, once for the whole phone.
    "/lib/icons/apple-touch-icon.png",
)

PICTURES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
SOUNDS = (".mp3", ".m4a", ".ogg", ".opus", ".wav", ".flac")
FILMS = (".mp4", ".webm", ".mkv", ".mov")
FACES = (".woff2", ".woff", ".otf", ".ttf")

# WHERE THE STUDIO KEEPS ITS OWN FILES ON THIS DISK.  Read here only to WEIGH
# them, to learn the faces' names and to measure the bare note page's wrapper:
# nothing in lib/ imports the studio, and nothing here will.  One path, so
# that a studio that moves moves this line and no other.
STUDIO_APP = os.path.join(os.path.dirname(LIB), "markdown", "app")
STUDIO_STATIC = os.path.join(STUDIO_APP, "static")


# ------------------------------------------------------------ the digests
# THE BIGGEST FILE WORTH DIGESTING.  The phone verifies with WebCrypto, which
# has no streaming digest: `crypto.subtle.digest` is handed a whole buffer, so
# checking a 228 MB narration would mean holding 228 MB in a phone's memory at
# once to learn something its length already tells us well enough.  Eight
# megabytes covers every page, every note, every picture and every rendered
# exercise on this shelf, and leaves the recordings and the films to the
# cheaper test (the owner's decision A, 2026-09-23).
DIGEST_MAX = 8 * 1024 * 1024

# AND A SIZE IS NOT WHAT DECIDES IT (the owner, 2026-09-23: "digest the SMALL
# files and check the LENGTH of big ones").  A ceiling alone reads him the
# rule backwards: thirty-two of the fifty recordings of `principles-
# environmental-engineering-sci` are under eight megabytes apiece, so the
# ceiling let 128.9 MB of his narration be hashed to answer one press of the
# keep sheet -- and the phone, whose ceiling is twelve megabytes, then read
# each of those recordings whole into its memory to check it.  A RECORDING IS
# A RECORDING WHATEVER IT WEIGHS, and so is a film: what they are tested by is
# their length, which costs a header.  The ceiling stays as the second net,
# for the page or the picture that turns out to be enormous.
# A RECORDING'S OWN CEILING, far lower than everything else's.  Exempting
# recordings outright read his decision one way -- "length for the big ones"
# -- and lost the other half of it: a 38 kB mp3 IS a small file, and the suite
# proved what that costs, flipping one byte in the middle of a kept recording
# without changing its length and watching the sheet call it whole (a length
# can never catch a corruption, only a truncation).  So the rule is the size,
# as he said, with a second ceiling for the things that get large: a recording
# or a film is hashed only while it is genuinely small, which spares the phone
# reading megabytes into memory to check one and spares this end the 128.9 MB
# that one book's fifty narrations cost under a single eight-megabyte ceiling.
MEDIA_KINDS = ("recording", "film")
DIGEST_MAX_MEDIA = 2 * 1024 * 1024

# WHERE THE DIGESTS ARE REMEMBERED.  One file for the whole machine, beside
# the other things the toolbox knows about itself, keyed by the file's own
# path -- and NEVER inside a book's, a video's or a deck's folder, which hold
# the owner's work and nothing of ours.  Hashing his library once costs a read
# of every small file in it; hashing it again at every keep sheet, every
# renewal and every offline probe would cost that read over and over, which is
# the difference between a door that answers at once and one he waits on.
DIGESTS = os.path.join(os.path.dirname(LIB), "config", "digests.json")
# its shape, as a number (lib/version.py FORMATS): RAISE IT when the shape
# changes so that the Parseh before this one would read the file wrong
DIGESTS_FORMAT = 1


def _store_read(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            got = json.load(fh)
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def _store_write(path, what):
    """Put one of this file's machine-local memories on the disk, and shrug if
    it cannot be put there.  -> whether it was written.

    BEST-EFFORT, ON PURPOSE.  A read-only disk, a config directory nobody
    made, two servers writing at once -- none of that may stop a person
    keeping a book.  What is lost when this fails is only the SECOND call's
    speed: what was learnt was learnt, and is already in the answer.

    Written to a neighbour and moved into place, so a reader never sees half
    a file: os.replace is atomic where it matters (both Windows and POSIX).
    THE NEIGHBOUR WEARS THIS PROCESS'S NUMBER, because the toolbox's server
    and the studio's can be up at the same time and two of them writing one
    scratch file would leave a third reading the pieces of both.  And a COPY
    is what is written out: this server answers on several threads, and a
    dict being added to while it is walked raises rather than serialises.

    TWO MEMORIES, TWO FILES, and this is what they have in common rather than
    one file holding both: the digests are keyed by a file's own path and the
    wheres by a book's, they are learnt at different moments, and a save of
    one must never be able to lose the other's last hour of work.
    """
    tmp = "%s.%d.tmp" % (path, os.getpid())
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(dict(what), fh)
        os.replace(tmp, path)
        return True
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


# Read on the first ask and kept for as long as the server runs; `_digests_new`
# says whether anything was learnt that is not on the disk yet.
_digests = None
_digests_new = False


def _digests_read():
    return _store_read(DIGESTS)


def _digests_save():
    """Remember what was hashed, if there is anything new to remember."""
    global _digests_new
    if not _digests_new or _digests is None:
        return
    if _store_write(DIGESTS, _digests):
        _digests_new = False


def _digest(path, kind="small"):
    """The SHA-256 of a file, lowercase hex, or "" for one that is not to be
    digested at all and for one that cannot be read.

    HOW BIG IT IS DECIDES IT, which is what the owner asked for -- with a far
    lower ceiling for a recording or a film (DIGEST_MAX_MEDIA), because those
    are the things that get large and because the phone must read a body whole
    to hash it.  A small recording is hashed like any other small file: a
    length catches a download cut short and nothing else, and a byte flipped
    in the middle of a kept recording is exactly what a digest is for.

    THE CACHE IS KEYED BY SIZE AND MODIFICATION TIME as well as by name, so a
    file rewritten in place is hashed again rather than believed.  That is the
    same pair `_stamp` decides a version by, so the two can never disagree
    about whether a file has changed.
    """
    global _digests, _digests_new
    try:
        st = os.stat(path)
    except OSError:
        return ""
    if st.st_size > (DIGEST_MAX_MEDIA if kind in MEDIA_KINDS else DIGEST_MAX):
        return ""
    if _digests is None:
        _digests = _digests_read()
    key = os.path.realpath(path)
    size, mtime = st.st_size, int(st.st_mtime)
    got = _digests.get(key)
    if isinstance(got, dict) and got.get("size") == size and got.get("mtime") == mtime:
        return str(got.get("sha256") or "")
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
    except OSError:
        return ""
    hexd = h.hexdigest()
    _digests[key] = {"size": size, "mtime": mtime, "sha256": hexd}
    _digests_new = True
    return hexd


def _size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _stamp(path):
    try:
        st = os.stat(path)
        return "%d:%d" % (st.st_size, int(st.st_mtime))
    except OSError:
        return "-"


def _version(parts):
    """A version for a whole thing: a hash of what it is made of, as it is on
    the disk now.  A rebuilt reader, an edited chapter, a recording replaced --
    any of them gives a different version, and the phone knows what it holds
    is old (§19.4)."""
    h = hashlib.sha1()
    for p in parts:
        h.update(("%s|%s\n" % (p[0], p[1])).encode("utf-8"))
    return h.hexdigest()[:16]


def _entry(url, path, kind="small", **more):
    """One address, weighed -- and digested where a phone can afford it.

    Everything that reaches here is a file the servers send BYTE FOR BYTE: a
    reader, a picture, a recording, one of /lib/'s scripts, a face, a note's
    media (serve.py's static handler and send_file both stream the file as it
    is).  That is what makes the digest worth carrying: what lands in the
    phone's cache is these bytes or it is not this file.  The one place where
    a served body is NOT the file on the disk is the studio's generated
    stylesheets and its spliced script, and they never come through here --
    see `_studio_entry`.
    """
    rec = {"url": url, "bytes": _size(path), "kind": kind}
    digest = _digest(path, kind)
    if digest:
        rec["digest"] = digest
    rec.update(more)
    return rec


def _door(url, weight=0, kind="small"):
    """An address whose answer the computer COMPOSES, and which therefore has
    neither a digest nor a length anybody here can promise.

    `weight` is what it is worth telling the owner it will cost him, where
    that can be said at all; it is not a claim about the body, which is what
    `check: "here"` is there to say.  A page rendered from a template, a list
    the server builds at the ask, a stylesheet written out of the registry:
    all of them land here, and the phone tests that it HAS them and nothing
    more.
    """
    return {"url": url, "bytes": weight, "kind": kind, "check": "here"}


def shared():
    """The files every kept thing leans on, with their sizes."""
    out = []
    for url in SHARED:
        path = os.path.join(os.path.dirname(LIB), url.lstrip("/"))
        if os.path.exists(path):
            out.append(_entry(url, path))
    _digests_save()
    return out


def book(book_dir, url_base, notes=None, studio_base="/studio"):
    """A book: everything a reader needs, each recording on its own, and the
    notes written beside it.

    `url_base` is the book's address under /books/ with a trailing slash --
    /books/<language>/<slug>/ -- which is what the reader is served from.
    `notes` is what the door found in this book's `markdown/` folder (see
    notes_group): None, or an empty list, for a book nobody has written a note
    beside, and then nothing about notes appears in the answer at all.
    """
    book_dir = os.path.abspath(book_dir)
    reader = os.path.join(book_dir, "reader")
    if not os.path.isdir(reader):
        return None
    meta = {}
    try:
        with open(os.path.join(book_dir, "book.json"), "r", encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        pass
    small, media, stamps = [], [], []
    # the reader itself and whatever it was built into: one page, or a page
    # and a file per chapter (lib/tex2html.py, one_chapter_at_a_time)
    for name in sorted(os.listdir(reader)):
        path = os.path.join(reader, name)
        if not os.path.isfile(path):
            continue
        low = name.lower()
        if low.endswith((".html", ".css", ".js", ".json")):
            url = url_base + "reader/" + name
            small.append(_entry(url, path))
            stamps.append((url, _stamp(path)))
            # THE READER IS OPENED AT THE DIRECTORY, not at index.html: a
            # phone that kept only the file would find nothing kept for the
            # address it is standing on (the two are the same page, and the
            # worker matches an address, not a file).  IT IS THE SAME BYTES
            # TWICE, so the second address is entered at nothing: a book
            # whose reader is one 916 kB page was quoted at 1.8 MB, and a
            # number a person is asked to decide on must be the number.
            #
            # IT DOES CARRY THE DIGEST, THOUGH, because the digest is not a
            # cost -- it is what says the body under that address is the whole
            # page and not half of one.  Nothing is counted twice and the page
            # the owner actually opens is the one that gets checked.
            if name == "index.html":
                alias = {"url": url_base + "reader/", "bytes": 0, "kind": "small"}
                digest = _digest(path)
                if digest:
                    alias["digest"] = digest
                small.append(alias)
        elif low.endswith(PICTURES):
            url = url_base + "reader/" + name
            small.append(_entry(url, path, "picture"))
            stamps.append((url, _stamp(path)))
    # the book's pictures, wherever the build left them
    for folder in ("images", "pictures", "img"):
        d = os.path.join(book_dir, folder)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.lower().endswith(PICTURES):
                path = os.path.join(d, name)
                url = url_base + folder + "/" + name
                small.append(_entry(url, path, "picture"))
                stamps.append((url, _stamp(path)))
    # THE TIMES, WHICH EVERY READER ASKS FOR.  The build bakes each
    # subparagraph's seconds into the page, and then the page fetches
    # ../timings.json and puts the file's times in place of them (the reader's
    # own script, lib/tex2html.py): that file is where a time fixed by hand
    # lives, and it is the only place it lives.  It was in no list, so a
    # narrated book kept on the phone played to the times it was built with
    # and none of the corrections the owner had made at the desk.  It is a
    # fifth of a megabyte beside a narration's hundreds, and it is the book's
    # own work rather than ours.
    for name in ("timings.json",):
        path = os.path.join(book_dir, name)
        if os.path.isfile(path):
            url = url_base + name
            small.append(_entry(url, path))
            stamps.append((url, _stamp(path)))
    # THE RECORDINGS, each its own thing to pick: a narrated book is hundreds
    # of megabytes and the owner chose to pick them one by one (§19.1)
    narrs = _narrations(book_dir, meta)
    wheres = _wheres(book_dir, meta, narrs)
    audio_dir = os.path.join(book_dir, "audio")
    seen = set()
    for n in narrs:
        path = n["path"]
        if not path or not os.path.exists(path):
            continue
        rel = os.path.relpath(path, book_dir).replace(os.sep, "/")
        url = url_base + rel
        seen.add(rel)
        covers = ""
        if n["from"] or n["to"]:
            covers = "%s – %s" % (n["from"] or "the start", n["to"] or "the end")
        # WHERE IT IS IN THE BOOK, said the way the reader says it, and the
        # paragraph addresses kept exactly as they were: the owner asked for
        # the chapter and the section because "7.1 – 36.1" tells him nothing
        # about which recording he is about to spend forty megabytes on
        # (2026-09-23).  The sheet draws `where` first and `covers` small
        # underneath it.
        media.append(_entry(url, path, "recording", id=n["id"],
                            covers=covers, where=wheres.get(n["id"], "")))
        stamps.append((url, _stamp(path)))
    # A RECORDING NOTHING DECLARED, found by looking.  A book.json may name
    # its sound in a shape this file has not met -- or name none at all while
    # the file sits in audio/ waiting to be aligned -- and a recording on the
    # disk that the sheet never offers is a recording the owner cannot keep.
    #
    # SOUNDS AND FILMS BOTH, because a container is not a kind of content:
    # `boof-e-koor`, the one fully narrated book on his shelf, is 228 MB of
    # audio in a .webm, which this scan skipped for being in the films' list
    # -- so the sheet offered him a 2.6 MB reader and no narration at all, and
    # he wrote that keeping it "didn't ask me and didn't download the audio
    # track".  (It is declared, by the older top-level "audio" key, and
    # `_narrations` now reads that too; the scan is the second net.)
    if os.path.isdir(audio_dir):
        for name in sorted(os.listdir(audio_dir)):
            rel = "audio/" + name
            if rel in seen or not name.lower().endswith(SOUNDS + FILMS):
                continue
            path = os.path.join(audio_dir, name)
            url = url_base + rel
            media.append(_entry(url, path, "recording", id="", covers="",
                                where=wheres.get("", "")))
            stamps.append((url, _stamp(path)))
    # THE NOTES, under the book's own notes mount (serve.py's `_notes`, whose
    # prefix is the book's path with /notes on the end)
    group, _ns = notes_group(url_base + "notes", notes, studio_base)
    # THE NOTES ARE THEIR OWN HALF OF THE RECORD, never mixed into the lists
    # the sheet keeps without asking: a tick that can be refused has to be
    # readable apart from what it can be refused against.  THEIR VERSION IS
    # THEIR OWN TOO (group["version"], stamped from the same note stamps):
    # folded into the thing's, a note written at the desk would tell somebody
    # who deliberately kept this book WITHOUT its notes that what he has is
    # out of date, and the press he was offered would fetch him nothing.  The
    # sheet compares the two apart (lib/keep.js, look()), so a note written
    # or edited at the desk offers the re-keep to whoever kept the notes and
    # says nothing at all to whoever did not (decision 7).
    rec = {"kind": "book", "title": meta.get("title_latin") or meta.get("title") or "",
           "page": url_base + "reader/", "small": small, "media": media,
           "version": _version(stamps)}
    if group:
        rec["notes"] = group
    _digests_save()
    _wheres_save()
    return rec


# ------------------------------------------------- what a book's sound is
def _narrations(book_dir, meta):
    """Every recording this book declares, WHATEVER SHAPE IT DECLARES IT IN
    -> [{"id", "path" (absolute), "from", "to"}].

    THE SHAPES ARE NOT A GUESS: lib/books.py has read them for years, and it
    is asked here rather than copied.  `Book.narrations` knows the list form
    ("narrations": [{id, audio, from, to}, ...]) and the older one -- a book
    recorded in one sitting names a top-level "audio" and nothing else -- and
    turns both into the same records with their paths already resolved
    against the book's directory.

    Reading the list out of book.json by hand, which is what this file used to
    do, missed the second shape entirely: `boof-e-koor` has 228 MB of
    narration named by that older key, and the keep sheet offered the owner
    its reader and no sound (2026-09-23).  The hand-read remains below for the
    book whose book.json is too broken for books.Book to open at all -- there
    is no reason to offer nothing when the recording can still be found.
    """
    try:
        return [{"id": n.get("id") or "", "path": n.get("audio") or "",
                 "from": n.get("from") or "", "to": n.get("to") or ""}
                for n in booklib.Book(book_dir).narrations]
    except Exception:
        pass
    out = []
    raw = meta.get("narrations")
    if isinstance(raw, list):
        for i, rec in enumerate(raw):
            if not isinstance(rec, dict):
                continue
            name = rec.get("audio") or rec.get("file") or ""
            if not name:
                continue
            path = os.path.join(book_dir, "audio", name)
            if not os.path.exists(path):
                path = os.path.join(book_dir, name)
            out.append({"id": str(rec.get("id") or "n%d" % (i + 1)), "path": path,
                        "from": str(rec.get("from") or "").strip(),
                        "to": str(rec.get("to") or "").strip()})
    elif meta.get("audio"):
        out.append({"id": "n1", "path": os.path.join(book_dir, meta["audio"]),
                    "from": "", "to": ""})
    return out


def _wheres(book_dir, meta, narrs):
    """Where in the book each recording is -> {narration id: one short line}.

    THE OWNER ASKED FOR THIS IN SO MANY WORDS: "indicate also chapters and
    section range that each narration covers in the rectangles instead of only
    the range of paragraphs" (2026-09-23).  A row reading "7.1 – 36.1" names
    two subparagraphs and nothing a person recognises; "chapter 7 · Hydrology"
    is the same stretch said in the words the reader's own contents panel uses
    for it (lib/tex2html.py's outline: "chapter <n>", the \\chapname under it,
    the \\secmark titles inside).

    IT COSTS THE SOURCES AND NOTHING ELSE, and only where there is a recording
    to name: the .tex is parsed once for the whole book (a tenth of a second
    over the longest book on this shelf) and never a byte of sound is read.  A
    book whose sources are gone, unreadable or written in a shape the parser
    does not know gives every recording an empty string and no error at all --
    the keep sheet then says what it has always said, which is the paragraph
    addresses, and nothing is worse than it was.

    AND IT IS PAID ONCE PER EDIT AND NOT ONCE PER PRESS.  The __offline door
    is not asked only when somebody presses *Keep on this phone*: lib/keep.js
    asks it again a second and a half after every open of a kept book, to see
    whether what the phone holds has gone stale -- so re-parsing the whole of
    a book's LaTeX here is reading the book to answer a question about
    keeping, which is the one thing docs/mobile.md forbids ("asking what a
    thing is made of must not cost what reading it costs").  What was worked
    out is put away in `WHERES` under the book's own path, and read back
    while the stamp stands.
    """
    if not narrs:
        return {}
    stamp = _wheres_stamp(book_dir, meta, narrs)
    got = _wheres_remembered(book_dir, stamp)
    if got is not None:
        return got
    try:
        import texparse                                       # noqa: E402
        import structure                                      # noqa: E402
        import languages                                      # noqa: E402
        main = os.path.join(book_dir, meta.get("main") or "main.tex")
        if not os.path.isfile(main):
            return {}
        chapters = texparse.parse_book(
            main, meta.get("language") or languages.detect_from_path(main))
    except Exception:
        return {}
    # Every subparagraph of the book in reading order, twice over: as the pair
    # region_bounds names a stretch by (its chapter and its label), and as the
    # words that stretch should be called by.  THE SECTION IS A PLACE AND NOT
    # A CONTAINER -- it opens at a paragraph and runs until the next one, and
    # it starts again empty in every chapter file -- which is exactly how the
    # reader's own build carries it (tex2html.build's sec_now).
    pairs, said = [], []
    try:
        for ch in chapters:
            cnum = texparse.latin_digits(ch.label or "").strip()
            cname = structure.plain(ch.name) if ch.name else ""
            sec = ""
            for para in ch.paragraphs:
                if para.section:
                    sec = structure.plain(para.section)
                for s in para.subs:
                    pairs.append((cnum, s.num))
                    said.append((cnum, cname, sec))
    except Exception:
        # the parse was already paid for by the time this went wrong, and it
        # will go wrong again in exactly the same way until the book is
        # edited: the nothing it gives is worth remembering, or every press
        # would pay that parse over for an answer already known to be empty
        _wheres_remember(book_dir, stamp, {})
        return {}
    out = {}
    for n in narrs:
        try:
            # a recording that names neither end covers the whole book, which
            # is what region_bounds answers for two empty ends
            i, j = texparse.region_bounds(pairs, n["from"], n["to"])
        except Exception:
            # a stretch naming a subparagraph this book has not got: the
            # recording is still offered, with no place said for it
            out[n["id"]] = ""
            continue
        out[n["id"]] = _say_where(said[i:j + 1])
    _wheres_remember(book_dir, stamp, out)
    return out


# --------------------------------------- and where they were last worked out
# WHERE THE PLACES ARE REMEMBERED.  A neighbour of `DIGESTS`, in the same
# machine-local config directory and never inside the owner's own book, for
# every reason written over that one.  It holds, per book, the stamp of what
# was parsed and the one short line each recording was given.
WHERES = os.path.join(os.path.dirname(LIB), "config", "wheres.json")
# its shape, as a number, as DIGESTS_FORMAT is DIGESTS's
WHERES_FORMAT = 1

_wheres_store = None
_wheres_store_new = False


def _wheres_stamp(book_dir, meta, narrs):
    """What `_wheres` would be looking at -> one short string.

    KEYED THE WAY THE DIGESTS ARE KEYED, which is to say by the size and the
    modification time of what was read: every .tex beside book.json, because
    those are the sources texparse.parse_book walks, and the two fields of
    book.json that say which of them it starts at and in what language.

    AND BY THE RECORDINGS' OWN ENDS, because the answer is not only the book:
    the same parse gives different lines for different stretches, so a
    recording re-cut at the desk -- `from` moved, `to` moved, one added --
    must send this round again even though not a character of the LaTeX has
    changed.
    """
    parts = ["%s|%s" % (meta.get("main") or "main.tex", meta.get("language") or "")]
    try:
        for name in sorted(os.listdir(book_dir)):
            if name.lower().endswith(".tex"):
                parts.append("%s|%s" % (name, _stamp(os.path.join(book_dir, name))))
    except OSError:
        # a book whose directory cannot be listed is a book `_wheres` will
        # fail on in a moment anyway: it gets a stamp nothing matches rather
        # than one that matches everything
        return ""
    for n in narrs:
        parts.append("%s|%s|%s" % (n["id"], n["from"], n["to"]))
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def _wheres_remembered(book_dir, stamp):
    """What was worked out for this book last time, or None to work it out.

    An empty stamp is never a hit: `_wheres_stamp` gives one to a book it
    could not look at, and a memory keyed on "I do not know" would hand one
    book's places to another.
    """
    global _wheres_store
    if not stamp:
        return None
    if _wheres_store is None:
        _wheres_store = _store_read(WHERES)
    got = _wheres_store.get(os.path.realpath(book_dir))
    if not isinstance(got, dict) or got.get("stamp") != stamp:
        return None
    places = got.get("wheres")
    return dict(places) if isinstance(places, dict) else None


def _wheres_remember(book_dir, stamp, places):
    global _wheres_store, _wheres_store_new
    if not stamp:
        return
    if _wheres_store is None:
        _wheres_store = _store_read(WHERES)
    _wheres_store[os.path.realpath(book_dir)] = {"stamp": stamp, "wheres": places}
    _wheres_store_new = True


def _wheres_save():
    """Put the places away, if anything new was worked out.

    Called where `_digests_save` is called and for the same reason: the door
    has finished answering, so this is the moment at which what was learnt is
    worth a write, and a write that fails costs only the next press's speed.
    """
    global _wheres_store_new
    if not _wheres_store_new or _wheres_store is None:
        return
    if _store_write(WHERES, _wheres_store):
        _wheres_store_new = False


def _say_where(span):
    """The shortest true line for a run of subparagraphs.

    One chapter is called by its number and its name; a run of them is called
    by its two ends, or listed where it is not a run at all (a recording may
    cover chapters 2 and 5 of a book whose files are out of order).  The
    sections inside come after, one of them named or the first and the last of
    them -- which is the "section range" the owner asked for.
    """
    chs, names, secs = [], {}, []
    for cnum, cname, sec in span:
        if cnum and cnum not in chs:
            chs.append(cnum)
        if cnum:
            names.setdefault(cnum, cname)
        if sec and sec not in secs:
            secs.append(sec)
    if not chs:
        head = ""
    elif len(chs) == 1:
        head = "chapter " + chs[0]
        if names.get(chs[0]):
            head += " · " + names[chs[0]]
    elif _a_run(chs):
        head = "chapters %s–%s" % (chs[0], chs[-1])
    else:
        head = "chapters " + ", ".join(chs)
    if secs:
        tail = secs[0] if len(secs) == 1 else "%s – %s" % (secs[0], secs[-1])
        head = (head + " · " + tail) if head else tail
    return head


def _a_run(chs):
    """Whether these chapter numbers are 2, 3, 4 and not 2, 5, 9: only then
    may the two ends stand for the whole of them."""
    try:
        nums = [int(c) for c in chs]
    except ValueError:
        return False
    return all(b - a == 1 for a, b in zip(nums, nums[1:]))


# WHAT THE PLAYER'S PAGE LOADS FROM ITS OWN MOUNT.  youtube/lib/player.html
# links exactly three files that are not the toolbox's: the player's
# stylesheet and the tab-capture script (the share of this tab and the
# recording of its sound, which the add page uses too), both in the head, and
# the player itself, the last tag of the body.  A fourth would be missing from
# a kept video the same way: tests/test_tabcapture.py holds this list to what
# the page links.  Named relative to the video mount for the same reason
# STUDIO_FILES is named relative to the studio's -- serve.py decides where the
# videos answer, and a "/youtube" written out here would be a second copy of
# that decision.
PLAYER_FILES = ("/lib/style.css", "/lib/tabcapture.js", "/lib/player.js")


def _player_entry(url_base, rel):
    """One of the player's own files, weighed.

    The address is the mount's, and the file behind it is found the way the
    server finds it: serve.py serves these straight off the disk at the
    path their address spells under the toolbox's directory (its STATIC_FILES
    and `directory=ROOT`), so what lands in the phone's cache is these bytes
    and the digest is worth carrying.
    """
    url = (url_base or "").rstrip("/") + rel
    return _entry(url, os.path.join(os.path.dirname(LIB), url.lstrip("/")))


def video(video_dir, vid, url_base, notes=None, studio_base="/studio"):
    """A video: its page and what the page reads, the film if one is on this
    machine (a YouTube video's own frame cannot be kept -- §18), and the notes
    written beside it.

    `notes` is the door's list, exactly as for a book: the two readers' note
    code is a mirror and so is this.
    """
    video_dir = os.path.abspath(video_dir)
    if not os.path.isdir(video_dir):
        return None
    meta = {}
    try:
        with open(os.path.join(video_dir, "video.json"), "r", encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        pass
    page = "%s/v/%s/" % (url_base.rstrip("/"), vid)
    # THE PLAYER'S PAGE IS BUILT AT THE ASK, so it is a door: what it costs is
    # near enough the annotations it carries -- which is why they are weighed
    # for it -- but those are not its bytes, and a digest taken off that file
    # would have the phone judge every kept video's page broken.
    small = [_door(page, _size(os.path.join(video_dir, "annotations.json")))]
    # AND WHAT THAT PAGE ASKS FOR THAT IS NOT UNDER /lib/.  Everything else
    # the player links is the toolbox's own and is in SHARED already; these
    # are the player's, they live under the video mount, and they were in
    # no list at all -- so a kept video opened away from the computer waited
    # on a stylesheet and a script that were never there and stopped at
    # "loading the annotations…", which is the line the page shows before
    # player.js has run (youtube/lib/player.html).  It is the same fault as
    # /lib/mt.js and it is the whole of what a kept video was missing.
    small.extend(_player_entry(url_base, rel) for rel in PLAYER_FILES)
    media, stamps = [], []
    files = "%s/videos/%s/%s/" % (url_base.rstrip("/"),
                                  os.path.basename(os.path.dirname(video_dir)), vid)
    for name in sorted(os.listdir(video_dir)):
        path = os.path.join(video_dir, name)
        if not os.path.isfile(path):
            continue
        low = name.lower()
        url = files + name
        if low.endswith((".json", ".txt")):
            small.append(_entry(url, path))
            stamps.append((url, _stamp(path)))
        elif low.endswith(PICTURES):
            small.append(_entry(url, path, "picture"))
            stamps.append((url, _stamp(path)))
        elif low.endswith(FILMS):
            media.append(_entry(url, path, "film", id=name, covers="the film itself"))
            stamps.append((url, _stamp(path)))
        elif low.endswith(SOUNDS):
            media.append(_entry(url, path, "recording", id=name, covers=""))
            stamps.append((url, _stamp(path)))
    # THE NOTES, under the video's own notes mount (serve.py's `_youtube`
    # hands /v/<id>/notes to the very same `_notes`)
    group, _ns = notes_group(page + "notes", notes, studio_base)
    # THE NOTES ARE THEIR OWN HALF OF THE RECORD, never mixed into the lists
    # the sheet keeps without asking: a tick that can be refused has to be
    # readable apart from what it can be refused against.  THEIR VERSION IS
    # THEIR OWN TOO (group["version"], stamped from the same note stamps):
    # folded into the thing's, a note written at the desk would tell somebody
    # who deliberately kept this book WITHOUT its notes that what he has is
    # out of date, and the press he was offered would fetch him nothing.  The
    # sheet compares the two apart (lib/keep.js, look()), so a note written
    # or edited at the desk offers the re-keep to whoever kept the notes and
    # says nothing at all to whoever did not (decision 7).
    rec = {"kind": "video", "title": meta.get("title") or vid, "page": page,
           "small": small, "media": media, "version": _version(stamps)}
    if group:
        rec["notes"] = group
    _digests_save()
    return rec


MEDIA_IN_MARKDOWN = None


# WHAT A STUDIO PAGE LOADS.  The deck pages are the studio's, and their
# sheets and scripts live under its own mount rather than under /lib/ -- so a
# deck kept on a phone has to carry them, or the page would open offline with
# no layout and no script at all.  (They are kept in the shared cache, like
# /lib/'s: two decks kept cost them once.)
STUDIO_FILES = ("/static/app.css", "/static/langs.css", "/static/mobile.css",
                "/static/app.js", "/static/exform.js", "/static/decks.js",
                "/static/mode.js", "/static/mathjax.css", "/static/mathjax.js",
                # THE GEAR'S ROWS (a0.5.0): what a document's, a deck's and an
                # exercise's own ⚙ holds -- the page links this last, and a kept
                # page without it has a button that does nothing (the toolkit it
                # opens is in SHARED, /lib/pagesettings.js)
                "/static/gear.js",
                # THE SHEET ON ITS OWN, which nothing named until now.  It was
                # split out of app.css for the bare note page, which links it
                # and nothing else (markdown/app/templates/note.html) -- so a
                # kept note whose sheet was left behind opens as unstyled
                # markup.  /static/app.css still answers with both files
                # joined, so naming this one costs a second small file and
                # buys every note its typography.
                "/static/sheet.css",
                # the drawings a document or a note opened without, made
                # afterwards (the owner, 2026-09-28): both pages load it
                "/static/latexwait.js")

# The bare note page loads exactly two of the above, and neither of them is
# the studio's chrome: a note is the sheet and the language tokens, and the
# rest of that list is for a page with an editor on it.
NOTE_FILES = ("/static/sheet.css", "/static/langs.css")

# WHAT A KEPT NOTE WEIGHS BEFORE ITS OWN TEXT IS COUNTED.  A note's page is
# the same wrapper every time -- the head, the typography it reads before
# anything is painted, the header and the little that a framed page has to do
# for itself -- and only then this note's words.  The wrapper is about ten
# kilobytes and it is MOST of what a note costs: the owner said so when he
# decided this ("a note's bare page is about 8 kB rendered"), and a sheet that
# counted the source.md alone would have told him a book's thirty-four notes
# cost fifty kilobytes when they cost a third of a megabyte.
#
# Measured off the templates rather than written down here, so that it cannot
# go stale the next time either page is edited.  A note holding an exercise is
# kept as the DOCUMENT page (decision 3), which is the larger wrapper of the
# two, so the two are weighed apart rather than averaged.
_WRAPPERS = {False: os.path.join(STUDIO_APP, "templates", "note.html"),
             True: os.path.join(STUDIO_APP, "templates", "doc.html")}


def _page_wrapper(exercise):
    n = _size(_WRAPPERS[bool(exercise)])
    return n - len("{{ARTICLE}}") if n else 0

# MathJax as the STUDIO serves it.  lib/mathjax.js is a small loader and it
# works the library's address out of its own `src` -- so a page that linked it
# under the studio's prefix goes on to ask for the two megabytes under that
# same prefix, and a phone that kept /lib/mathjax/tex-svg.js would sit waiting
# for an address nothing ever asks for.  Named as they are really asked for.
STUDIO_MATHJAX = ("/static/mathjax.css", "/static/mathjax.js",
                  "/static/mathjax/tex-svg.js")

# The two spellings of a formula in this toolbox's dialect: an inline mark
# ending `]{math}` (texgen.MATH_RE) and a block fenced by `:::math`
# (mdparser.MATH_OPEN_RE).  Used only where there is no rendered page to ask
# -- a note is decided from its render, which knows what a block became.
_MATHS_IN_SOURCE = re.compile(r"\]\{\s*math\s*\}|^:::math\s*$", re.I | re.M)
# a latex block's body is LaTeX for its own compile, never MathJax's: what it
# holds decides nothing about the two megabytes (and a `]{math}` in it is not
# a formula of the page's) -- true of an inline `[…]{latex}` mark's own body
# for the same reason (TO-DO §8.39's L8), so it is stripped here too, by the
# same light regex the full parser matches inline marks with (imported, not
# copied, so the two can never drift the way lib/latexthemes.blocks_in's own
# comment warns a copy would).
# (a fence of four colons or more, closed by its own: a drawing in a step of a follow-up has five)
_LATEX_BLOCK = re.compile(r"^[ \t>]*(:{4,})latex\b.*?^[ \t>]*\1[ \t]*$", re.I | re.M | re.S)


def _maths_in(markdown):
    import latexthemes
    text = _LATEX_BLOCK.sub("", markdown or "")
    text = latexthemes.LATEX_INLINE_RE.sub("", text)
    return bool(_MATHS_IN_SOURCE.search(text))


def _drawings(markdown, studio_base, have, stamps):
    """THE DRAWINGS OF A PAGE'S LATEX BLOCKS (TO-DO §8.39), each an entry with
    its digest, at the one address every page loads it from (the studio's).
    Each drawing's key stamps the version, so a block redrawn after a theme
    was edited, or after an update, is "updated" on the phone and never
    "damaged" (lib/keep.js).  Made here if it is not made yet: keeping is
    asked of the computer, which is the one that can draw."""
    import latexdraw
    import latexthemes

    def keep(r):
        if not r.get("ok"):
            return
        url = studio_base.rstrip("/") + latexdraw.url_of(r["key"])
        if url in have:
            return
        have.add(url)
        out.append(_entry(url, r["svg"], "picture"))
        stamps.append((url, r["key"]))

    out = []
    for b in latexthemes.blocks_in(markdown):
        if b["errors"] or not b["closed"]:
            continue
        keep(latexdraw.draw(b["tex"], b["theme"] or None))
    # inline marks (TO-DO §8.39's L8) live in text, not in a fence a light
    # reading finds the same way blocks_in does: swept straight from the
    # source, the reason inline_latex_pairs sits beside blocks_in at all.
    for tex, theme in latexthemes.inline_latex_pairs(markdown):
        keep(latexdraw.draw(tex, theme, inline=True))
    return out


# THE THREE THE STUDIO MAKES UP AS IT ANSWERS, and which therefore have
# neither a length nor a digest anybody here can give.  /static/langs.css is
# written out of the language registry at every ask (server.serve_langs_css);
# /static/app.css is static/sheet.css and static/app.js's neighbour joined
# under one name (serve_app_css), so the file of that name on the disk is
# HALF the answer; /static/app.js has the toolbox's one case fold spliced
# into it on the way out (serve_app_js), so it is longer than the file.
#
# They are named here and given a size of nothing, which is what this
# function's docstring has always said they had and what they have to have
# now that a size is a claim the phone TESTS: quoting the half-file's length
# at the worker would have it judge a perfectly good stylesheet broken and
# leave that row unticked for ever.
_STUDIO_MADE_UP = ("langs.css", "app.css", "app.js")


def _studio_entry(studio_base, rel):
    """One of the studio's own files, weighed where it is a file on the disk.

    What is weighed is what is worth weighing and what is really a file: the
    faces, the sheet, the deck and form scripts, and the two megabytes of
    MathJax -- all of which the studio streams as they are, so each carries
    its digest too.  The three it makes up as it answers stay at 0 and carry
    none (_STUDIO_MADE_UP).
    """
    tail = rel.split("/static/", 1)[-1]
    url = (studio_base or "").rstrip("/") + rel
    if tail in _STUDIO_MADE_UP:
        return _door(url)
    if tail.startswith("mathjax"):
        # the studio does not hold a copy: it answers for lib/'s (its
        # serve_math_js, serve_math_css, serve_math_lib)
        path = os.path.join(LIB, tail)
    else:
        path = os.path.join(STUDIO_STATIC, tail)
    return _entry(url, path)


def studio_files(studio_base="/studio"):
    return [_studio_entry(studio_base, rel) for rel in STUDIO_FILES]


def studio_faces(studio_base="/studio"):
    """THE THIRTEEN FACES THE STUDIO'S SHEET IS SET IN, as addresses.

    Nothing kept them, and nothing could have: they are named only inside
    `url()` calls in static/sheet.css, and a stylesheet's url() is not a link
    anything but a browser can see.  So a kept document -- and, until today, a
    kept note -- opened in whatever face the phone happened to have, which is
    not the studio's page however faithfully the rest of it was rendered.
    They travel ONCE for the whole phone (the owner's decision 4, 2026-09-23):
    1.83 MB, in the shared cache, not 1.83 MB per book.

    Read off the directory rather than written out here, because a face added
    to the sheet is added to that directory and would otherwise be forgotten
    by a list nobody thinks to look at.
    """
    base = (studio_base or "").rstrip("/")
    d = os.path.join(STUDIO_STATIC, "fonts")
    out = []
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            path = os.path.join(d, name)
            if os.path.isfile(path) and name.lower().endswith(FACES):
                out.append(_entry(base + "/static/fonts/" + name, path))
    return out


# ------------------------------------------------- the notes beside a thing
# THE NOTES TRAVEL WITH THEIR BOOK OR THEIR VIDEO (the owner, 2026-09-23:
# "the keep button in books and videos should also keep the notes rendered in
# bare page way").  Until today the records here never walked a `markdown/`
# folder at all, so a kept book kept its text and its recordings and left
# every note he had written behind.
#
# THE LIST IS GATHERED BY THE DOOR AND HANDED HERE, and that is a decision
# rather than an accident.  A note is a studio document: which notes there
# are, what each renders to, and whether that render holds an exercise are
# the studio's own knowledge (store.list_docs, htmlgen.render_document), and
# lib/ MUST NOT import the studio -- a book reader, a bundle and a launcher
# all lean on this directory and none of them has a studio to lean on.  The
# alternative was to teach this file the store's layout by hand, which is a
# second copy of somebody else's truth waiting to drift.  serve.py stands on
# both sides of that line, so serve.py looks; this file is handed
#
#     [{"id", "updated", "dir", "exercises": bool, "maths": bool}, ...]
#
# and does what it does everywhere else: turns it into addresses, weighs what
# is on the disk, and stamps it for the version.  `dir` is the note's own
# directory, so its source, its pictures and its recordings can be weighed
# here without a second word to the studio.

def notes_group(mount, notes, studio_base="/studio"):
    """The notes of one book or one video -> (group, recordings, shared, stamps).

    ONE TICK FOR ALL OF THEM (the owner's decision 1).  They are not folded
    into `small`, where they would be kept whether he wanted them or not, and
    not scattered through `media`, where thirty-four rows would bury the two
    narrations he came to the sheet for.  They are a GROUP: one row saying how
    many and about how much, carrying every address behind it.

    ABOUT how much, and the word is in the answer (`about`).  A kept note is
    its page, and a page is the same wrapper every time plus this note's own
    text: so the measure is the wrapper (_page_wrapper, ten kilobytes or so,
    which is most of what a note costs) and the `source.md` on the disk,
    which is the cheap honest measure of the text.  Weighing the render
    instead would mean rendering every note to answer a question about
    keeping, which is the one thing this file refuses to do -- asking what a
    thing is made of must not cost what reading it costs.  A note's pictures
    are weighed exactly, being files.

    A NOTE THAT HOLDS AN EXERCISE KEEPS ITS FULL STUDIO PAGE (decision 3).
    The bare page carries none of the studio's scripts, and an exercise
    without them is a box that cannot be answered, checked or copied; that is
    why page_note sends such a note to the document page at the desk, and away
    from the desk it must open exactly as it does there.  So its address in
    this group is the document page's, and the studio's own files go in
    `shared` -- once for the phone, never once per book.

    THE MARKS GO TOO (decision 2).  The reader draws a note's mark in the seam
    from `<mount>/api/marks` and from nothing else, so a kept note whose list
    stayed on the computer is a page nothing on the phone can reach.  It is a
    DOOR (lib/sw.js, isDoor): the computer is asked first and the kept copy
    stands behind it -- which is also what makes a note written AFTER the book
    was kept show its mark the moment the computer is there (decision 7).
    """
    mount = (mount or "").rstrip("/")
    notes = [n for n in (notes or []) if (n or {}).get("id")]
    if not notes:
        return None, []
    urls, stamps = [], []
    about, pictures = 0, 0
    sounds, sound_bytes = [], 0
    exercises = maths = False
    for n in notes:
        doc_id = n["id"]
        d = n.get("dir") or ""
        page = "%s/note/%s" % (mount, doc_id)
        wrap = _page_wrapper(n.get("exercises"))
        if n.get("exercises"):
            exercises = True
            # BOTH ADDRESSES, because both are asked for.  The mark opens the
            # BARE address -- that is the only one either reader knows (the
            # prefetch, and ntShow's first fetch) -- and at the desk the
            # server answers it with a redirect to the document page.  Away
            # from the desk there is nobody to redirect, so the document
            # page's own bytes are kept under the bare address as well: the
            # fetch that keeps it follows the redirect, and what lands in the
            # cache under the bare address IS the full page.  The document
            # address is kept too, for "open in the studio" and for a mark
            # tapped after a reload.
            urls.append(_door(page, wrap))
            urls.append(_door("%s/doc/%s" % (mount, doc_id), wrap))
        else:
            urls.append(_door(page, wrap))
        if n.get("maths"):
            maths = True
        about += wrap
        about += _size(os.path.join(d, "source.md")) if d else 0
        # THE NOTE'S OWN STAMP IS THE BOOK'S (decision 7): a note written,
        # edited or deleted since the book was kept moves the book's version,
        # and the out-of-date bar offers to keep it again in one tap.  The
        # store's `updated` is what document() already stamps a document by,
        # so the two agree about what "changed" means.
        stamps.append((page, str(n.get("updated") or "")))
        if not d:
            continue
        try:
            with open(os.path.join(d, "source.md"), encoding="utf-8") as fh:
                source = fh.read()
        except OSError:
            source = ""
        for x in _drawings(source, studio_base, set(u["url"] for u in urls), stamps):
            urls.append(x)
            about += x.get("bytes") or 0
        # A NOTE'S PICTURES COME WITH THE NOTES and its RECORDINGS DO NOT
        # (decision 6): a picture is part of reading the note, a recording is
        # megabytes nobody asked for.  The recordings are one row of their own
        # in the heavy list, beside the narrations.
        for kind, folder in (("images", "images"), ("audio", "audio")):
            sub = os.path.join(d, folder)
            if not os.path.isdir(sub):
                continue
            for name in sorted(os.listdir(sub)):
                path = os.path.join(sub, name)
                if not os.path.isfile(path):
                    continue
                url = "%s/media/%s/%s/%s" % (mount, doc_id, folder, name)
                low = name.lower()
                if kind == "images" and low.endswith(PICTURES):
                    urls.append(_entry(url, path, "picture"))
                    about += _size(path)
                    pictures += 1
                elif kind == "audio" and low.endswith(SOUNDS + FILMS):
                    # the note it is in, so a row in the sheet says which
                    # note it belongs to rather than only its file name
                    # WHOSE RECORDINGS THESE ARE.  The sheet draws them as
                    # one row and counts them; each entry still says where it
                    # came from, so a row asked about names the notes rather
                    # than a file name nobody chose.
                    sounds.append(_entry(url, path, "recording", id=name,
                                         covers="in the notes"))
                    sound_bytes += _size(path)
                else:
                    continue
                stamps.append((url, _stamp(path)))
    marks = mount + "/api/marks"
    urls.append(_door(marks))
    stamps.append((marks, "%d notes" % len(notes)))
    if exercises:
        # AND THE TAGS, WHEREVER A DOCUMENT PAGE IS WHAT IS KEPT.  A note that
        # holds an exercise opens the studio's full page (decision 3), and
        # that page asks its mount for `/api/tags` as it starts, exactly as
        # `document()` says.  A bare note page runs no script at all and asks
        # for nothing, so this is named only where the larger page travels.
        urls.append(_door(mount + "/api/tags"))
    # ONE ADDRESS PER ENTRY, and the grouping in the sheet.  The owner asked
    # for one tick (decision 1), and the tick is a thing a person sees: it
    # belongs to lib/keep.js, which draws one row for this whole list and
    # fetches every address behind it.  An entry that carried several
    # addresses would have to be expanded by the sheet, by the worker, by the
    # freeing sweep and by whatever reads a record next -- four places that
    # must agree, to save a loop in one.
    group = {"url": mount, "kind": "notes", "title": "its notes", "count": len(notes),
             "pictures": pictures, "bytes": about, "about": True,
             "small": urls, "shared": [], "media": [],
             "version": _version(stamps)}
    if sounds:
        # EACH RECORDING ITS OWN ENTRY, ticked as one row.  The sheet counts
        # them and says "the notes' recordings · N files"; keeping them as one
        # made-up address meant ticking it fetched a route that does not
        # exist and no sound reached the phone.
        group["media"] = sounds
    # WHAT THE STUDIO MUST LEND THE PHONE, once.  The sheet and the language
    # tokens for every note; the whole of the studio's chrome only where a
    # note holds an exercise, because only then is a document page kept; the
    # maths only where there is maths (decision 5).  All of it named at the
    # STUDIO'S canonical address and not at this book's mount, so two books'
    # notes share one copy -- which is what note.html already does with the
    # sheet, and what the document page must be made to do with the rest.
    shared = [_studio_entry(studio_base, rel) for rel in NOTE_FILES]
    if exercises:
        have = set(x["url"] for x in shared)
        shared.extend(x for x in studio_files(studio_base) if x["url"] not in have)
    if maths:
        have = set(x["url"] for x in shared)
        shared.extend(x for x in (_studio_entry(studio_base, rel)
                                  for rel in STUDIO_MATHJAX) if x["url"] not in have)
    shared.extend(studio_faces(studio_base))
    group["shared"] = shared
    # ONE ANSWER, not four.  The sheet asks the record for the notes and gets
    # everything about them in one place -- their pages, what the studio must
    # lend the phone, their recordings and a version of their own -- so that
    # nothing about the notes can be read from one list and kept from another.
    return group, stamps


# ------------------------------------------------------------ the app shell
# THE APP ITSELF, KEPT (the owner's choice, 2026-09-23; TO-DO §0).  Until now
# nothing but the offline page and the kept page was kept with the worker, and
# the app's start address -- /?mode=mobile, lib/mobile.py's manifest -- was in
# no cache at all: opened with the computer away it waited on its own splash
# for a socket that never settled.  So the WAY IN is kept as well: the hub, the
# shelves, the two libraries and Kept on this phone, with the sheets, the
# scripts and the faces they load.
#
# These pages are not a "Parseh cannot be reached" page.  They open as they
# always do, wearing the offline chip (lib/keep.js); what is on them and is not
# on this phone is drawn but cannot be tapped, as a book whose reader was never
# built already is.  What they SAY, though, is yesterday's, so lib/sw.js reads
# each of them again behind the page and the page puts the fresh list in place
# of the one it opened with.
SHELL_PAGES = ("/", "/?mode=mobile", "/m/books/", "/m/videos/", "/m/kept/", "/m/offline/",
               # the hub's Review later door opens it: an empty frame that lib/later.js
               # fills from the phone's own copy of the flags, so it opens with the
               # computer away and lists what was flagged on the train
               "/later/")

# The lists those two library pages draw themselves from: they are not written
# into the page, they are asked for.  The worker gives them the computer's
# answer when it comes within the deadline and the phone's last copy when it
# does not, so the page fills in by itself without knowing any of this.
SHELL_APIS = ("%(decks)s/api/decks", "%(studio)s/api/docs")

# What the app needs whatever is kept and is not in SHARED: its own
# description, which a phone re-reads, and the icon the hub draws.
SHELL_EXTRA = ("/manifest.webmanifest", "/lib/icons/parseh-192.png")


def shell(studio_base="/studio", decks_base="/exercises"):
    """THE WAY IN, as addresses: what lib/sw.js keeps so that the app opens
    with the computer asleep, off or a train away (TO-DO §0).

    One door, one list, so that a page added to the mobile interface is added
    here and nowhere else.  `pages` are navigated to; `apis` are the lists two
    of them ask for; `files` are the sheets and the scripts they all load --
    the same SHARED every kept book leans on, and the studio's own
    (STUDIO_FILES), which the deck and document pages load from its mount.

    AND `later` IS WHAT IS NOT THE WAY IN (the owner, 2026-09-23, after the
    app would no longer install).  The three lists above are how a person
    GETS somewhere: without them a tap opens nothing.  The studio's thirteen
    faces are not that -- they are what a STUDIO PAGE needs to look like
    itself, named only inside `url()` calls in its sheet -- and they are 1.83
    of the 3.26 megabytes this door used to name in one breath.  Kept with
    the rest, they were fetched by the worker's install event, which then sat
    installing for minutes on end over a tunnel; Chrome will not install a
    site whose worker never activates, so the faces were quietly costing the
    owner the app itself.

    They are still kept, and by the same worker into the same cache -- but
    afterwards, and only when a page that needs them asks (lib/sw.js, `warm`).
    Named here rather than in the worker, for the same reason as everything
    else in this file: a face added to the studio's fonts folder is added to
    this list by studio_faces and to nothing else.
    """
    st = (studio_base or "").rstrip("/")
    dk = (decks_base or "").rstrip("/")
    pages = list(SHELL_PAGES) + [dk + "/", st + "/"]
    apis = [a % {"decks": dk, "studio": st} for a in SHELL_APIS]
    files = [x["url"] for x in shared()]
    files.extend(x["url"] for x in studio_files(st))
    files.extend(SHELL_EXTRA)
    later = [x["url"] for x in studio_faces(st)]
    _digests_save()
    return {"ok": True, "pages": pages, "apis": apis, "files": files,
            "later": later}


# WHAT AN EXERCISE'S PAGE REALLY ASKS FOR.  A deck's pictures and recordings
# used to be looked for with a regex over the exercise's MARKDOWN, matching a
# markdown link -- `](/…)` -- and no exercise in this toolbox has ever been
# written that way.  A picture is `![](name.png)` with the deck's own folder
# left off, a recording is an `audio:` line inside a `:::exercise` block, a
# clip carries a window after it; and they are all relative, so the regex's
# leading slash could not match even in principle.  Over the owner's
# ninety-eight-exercise deck it found nothing, every time, which is why not
# one of his recordings was ever kept (2026-09-23).
#
# SO THE RENDER IS ASKED INSTEAD.  The exercise is rendered exactly as the
# cram page renders it, and the addresses are read off the html -- src, href
# and the data-src a lazy picture uses.  It cannot go stale when somebody
# invents a seventh way of writing a picture into an exercise, because the
# question it asks is no longer "what might this markdown mean" but "what did
# this page ask the server for".
_ASKS_FOR = re.compile(r'(?:\bsrc|\bhref|\bdata-src|\bposter)="([^"]+)"', re.I)

# WHAT AN EXERCISE RENDERED TO, LAST TIME ANYBODY ASKED:
# (asset base, language, id) -> (its `updated` stamp, the JSON length of its
# html, the addresses that html carried, whether there is a formula in it).
#
# THE RENDER ITSELF IS NOT REMEMBERED, and that is the point of the three.
# Those three facts are the whole of what this file ever wanted from a render
# -- what the cram door's answer will weigh, which pictures and recordings to
# offer, and whether MathJax must travel -- and they are a few dozen bytes
# where the html of one exercise is two kilobytes.  A shelf of decks costs
# this memory almost nothing and a re-render costs the door its speed.
#
# WHY IT IS NEEDED AT ALL.  The __offline door is asked again a second and a
# half after every open of a kept deck (lib/keep.js), and rendering ninety-
# eight exercises to answer it is reading the deck to answer a question about
# keeping -- docs/mobile.md: "asking what a thing is made of must not cost
# what reading it costs".
#
# THE STAMP IS WHAT IT IS REMEMBERED AGAINST, exactly as a note's render is
# in serve.py's `notes_to_keep`: `updated` is what the store already stamps an
# edit by and what this record's own version is built from, so a stamp that
# has not moved is an exercise whose html cannot have moved either.  It rides
# in the VALUE and not in the key, so an exercise edited REPLACES its own
# entry rather than leaving yesterday's beside today's.  The LANGUAGE and the
# ASSET BASE do belong to the key, because neither is the item's: a deck's
# language changed at the desk, or the exercises answered under another
# mount, is a different html for the very same stamp.
#
# BOUNDED, AND OLDEST OUT FIRST, for serve.py's reasons: a process that runs
# for weeks must not grow a memory without end, an exercise edited replaces
# its own entry rather than adding one, and a hit -- the case that must stay
# cheap -- costs no bookkeeping at all.  Four thousand is far more exercises
# than anybody's shelf holds.
_RENDERS = {}
_RENDERS_MAX = 4096
# Two phones asking two decks at once must not tear this dict; the lock
# covers the dict alone and never a render.
_RENDERS_LOCK = threading.Lock()


def _render(decks_mod, item, lang, asset_base):
    """The three facts about one exercise's render, from the memory or from
    the renderer -> (html JSON length, addresses, maths) or None.

    None is the exercise nobody can render, and it is not remembered: the
    failure may be the exercise's or it may be the moment's, and an exercise
    that would not render once should not be written off until somebody edits
    it.  It costs one render per press, for an exercise nobody has yet broken.
    """
    key = (asset_base, lang, item.get("id") or "")
    stamp = str(item.get("updated") or "")
    with _RENDERS_LOCK:
        got = _RENDERS.get(key)
    if got is not None and got[0] == stamp:
        return got[1:]
    try:
        html = decks_mod.render_item({"lang": lang}, item, asset_base, preview=False)
    except Exception:
        return None
    html = html or ""
    made = (stamp, len(json.dumps(html, ensure_ascii=False).encode("utf-8")),
            tuple(_ASKS_FOR.findall(html)),
            'class="math' in html)
    with _RENDERS_LOCK:
        _RENDERS.pop(key, None)
        _RENDERS[key] = made
        while len(_RENDERS) > _RENDERS_MAX:
            _RENDERS.pop(next(iter(_RENDERS)), None)
    return made[1:]


# THE SHAPE OF THE CRAM DOOR'S ANSWER, measured rather than written down.
# What that door sends is json.dumps({"ok": True, "cards": [...]}) with
# ensure_ascii off (markdown/app/deckroutes.py), and its length is the three
# numbers below plus the length of each card: the envelope around an empty
# list, the comma and space between two of them, and the wrapper of one
# `{"item": …, "html": …}` around its two halves.  They are asked of json
# here, at import, because they are json's business and not this file's --
# written out as 25, 2 and 20 they would be three magic numbers wrong the day
# anybody changed a separator.
_CRAM_EMPTY = len(json.dumps({"ok": True, "cards": []},
                             ensure_ascii=False).encode("utf-8"))
_CRAM_JOIN = (len(json.dumps({"ok": True, "cards": [0, 0]},
                             ensure_ascii=False).encode("utf-8"))
              - len(json.dumps({"ok": True, "cards": [0]},
                               ensure_ascii=False).encode("utf-8")) - 1)
_CARD_WRAP = len(json.dumps({"item": 0, "html": 0},
                            ensure_ascii=False).encode("utf-8")) - 2


def _deck_media(decks_mod, folder, slug, asks, asset_base, seen):
    """The pictures and recordings one rendered exercise asks for, as entries.

    `asks` is the list of addresses that exercise's html carried, which is
    what `_render` remembers of it: the render itself is not kept, because the
    addresses are the only thing about it this ever needed, and they are a few
    dozen bytes where the html is two kilobytes.

    Weighed for real, by asking the deck module for the file behind the
    address (its `image_file` and `audio_file`, which are the same two doors
    the server answers those addresses with -- name checked, no way out of
    the deck's own folder, and a PDF's missing .svg twin built before it is
    looked for, so the phone is offered the picture the page will draw).
    THE WEIGHING IS DONE AGAIN AT EVERY PRESS even where the addresses were
    remembered: a picture replaced at the desk keeps its name, and a size the
    phone is asked to check must be the size the file has now.
    """
    out = []
    for url in asks or ():
        url = url.split("?")[0].split("#")[0]
        if not url.startswith(asset_base) or url in seen:
            continue
        rest = url[len(asset_base):]
        folder_of, _, name = rest.partition("/")
        if not name or "/" in name:
            continue
        try:
            if folder_of == "images" and name.lower().endswith(PICTURES):
                path = str(decks_mod.image_file(folder, slug, name))
            elif folder_of == "audio" and name.lower().endswith(SOUNDS + FILMS):
                path = str(decks_mod.audio_file(folder, slug, name))
            else:
                continue
        except Exception:
            continue
        seen.add(url)
        out.append(_entry(url, path,
                          "picture" if folder_of == "images" else "recording"))
    return out


def deck(decks_mod, folder, slug, url_base="/exercises", studio_base="/studio"):
    """A deck: its pages, the exercises behind them, and their media.

    Cram needs nothing of the computer but these (§19.9); studying needs the
    deck checked out as well (§19.10).

    THE EXERCISES THEMSELVES TRAVEL WITH THE DECK, always, and that is the
    owner's decision B of 2026-09-23 after he found a kept deck stuck on
    "loading exercises…" with the computer away.  It could never have been
    anything else: the cram page asks for its exercises with a POST
    (markdown/app/static/decks.js), and there is no such thing as a cached
    POST -- the Cache API will not store one, so no amount of keeping could
    ever have put an exercise on his phone.  So the computer now answers the
    same thing at an address that CAN be kept (markdown/app/deckroutes.py's
    GET door beside the POST), this record names it, and it is in `small`:
    one tick, nothing to choose, a few hundred kilobytes for ninety-eight
    exercises -- the same order as the deck's own text, which he already
    keeps without being asked.

    Their pictures and recordings are in `small` for the same reason and by
    the same decision.  "Cramming away from the computer must then simply
    work", which is what he said keeping a deck was for.
    """
    try:
        d = decks_mod.get_deck(folder, slug)
        items = decks_mod.list_items(folder, slug)
    except Exception:
        return None
    root = url_base.rstrip("/")
    base = "%s/deck/%s/%s/" % (root, folder, slug)
    api = "%s/api/decks/%s/%s" % (root, folder, slug)
    # THE GET DOOR, at the address the record names and the page asks for.
    # No `ids` on it: it is the whole deck, because the whole deck is what is
    # kept, and because an address carrying a selection would be a different
    # address for every selection and none of them the one that was kept.
    cram = api + "/cram"
    asset_base = "%s/media/%s/%s/" % (root, folder, slug)
    small = [_door(base), _door(base + "cram"), _door(base + "study"), _door(api)]
    # THE CRAM PAGE AT THE ADDRESS THE OFFLINE OFFER SENDS HIM TO.  The worker
    # matches a request against the cache with `ignoreSearch: false`
    # (lib/sw.js), so `…/cram?all=1` is not `…/cram` and a kept page reached
    # with a query is a page nobody kept.  And that address is not a corner:
    # it is the link on "Studying needs the computer, and this deck is not
    # out" -- *Cram this deck* -- which is to say the one offer a kept deck
    # makes precisely when the computer is away (markdown/app/static/decks.js,
    # needsTheComputer).  Named here because it is one fixed address; the
    # `?selected=` addresses beside it carry a list of ids and cannot be, and
    # they belong to the worker's match rather than to this list.
    small.append(_door(base + "cram?all=1"))
    small.extend(studio_files(studio_base))
    # THE THIRTEEN FACES THE STUDIO'S SHEET IS SET IN.  A deck page and a cram
    # page ARE studio pages -- markdown/app/templates/deck.html and cram.html,
    # drawn in static/app.css like every other -- and the faces that sheet
    # names are named only inside its `url()` calls, which nothing but a
    # browser can see.  So a kept deck opened away from the computer read in
    # whatever face the phone happened to have.  `document()` has kept them
    # since the notes work; this is the same fault in the other studio page.
    # They are 1.83 MB and they travel ONCE for the whole phone, the worker
    # putting everything under the studio's `/static/` in the shared cache
    # (lib/sw.js, isShared), so a second deck costs them nothing.
    small.extend(studio_faces(studio_base))
    # THE VERSION IS THE EXERCISES' OWN.  It used to be the COUNT of them, so
    # an exercise corrected at the desk left every phone holding the old
    # wording and told nobody.  Each one's `updated` is what the store already
    # stamps an edit by, so the two agree about what "changed" means.
    stamps = [(api, "%d items" % len(items))]
    for it in items:
        stamps.append((api + "/" + (it.get("id") or "?"), str(it.get("updated") or "")))
    # `media` STAYS EMPTY, and that is the decision and not an oversight: a
    # deck has nothing left to pick one by one once the exercises and their
    # media travel with it, and the sheet draws a row for every entry it
    # finds here.  The key is still answered, because the sheet, the worker
    # and the freeing sweep all read it.
    media, seen = [], set()
    lang = (d.get("lang") or "").strip()
    # WHAT THE CRAM DOOR WILL REALLY SEND, to the byte, COUNTED AND NOT BUILT.
    # The answer is the one deckroutes builds and both servers write out
    # (json.dumps with ensure_ascii off, so Persian counts as Persian and not
    # as six characters a letter) -- but building the whole of it here meant
    # rendering ninety-eight exercises and then serialising 293,899 bytes of
    # them to learn a single integer, at every press of this door, an open of
    # a kept deck included.  So each card is measured instead: the half that
    # is its html is remembered against the exercise's own stamp (`_render`),
    # and the half that is the item is counted fresh, because the scheduler's
    # numbers really do move in it and what the owner is quoted should be what
    # he will spend.  Nothing is ever joined into one string.
    cost, counted, maths = _CRAM_EMPTY, 0, False
    for it in items:
        made = _render(decks_mod, it, lang, asset_base)
        if made is None:
            # one exercise nobody can render must not cost the deck its record
            continue
        html_bytes, asks, has_maths = made
        counted += 1
        maths = maths or has_maths
        cost += (_CARD_WRAP + html_bytes
                 + len(json.dumps(it, ensure_ascii=False).encode("utf-8")))
        small.extend(_deck_media(decks_mod, folder, slug, asks, asset_base, seen))
        small.extend(_drawings(it.get("markdown") or "", studio_base,
                               set(x["url"] for x in small), stamps))
    if counted > 1:
        cost += _CRAM_JOIN * (counted - 1)
    # THE MATHS, ONLY WHERE AN EXERCISE HAS ANY (the owner's decision 5, which
    # documents and notes are already kept by).  Both studio pages link
    # static/mathjax.js whatever is on them, and STUDIO_FILES above carries
    # that loader -- but the loader works the two megabytes of the library out
    # of its own `src` and asks for static/mathjax/tex-svg.js, which is in no
    # list.  A deck with a formula in it would have drawn the formula's TeX as
    # plain text and waited out the deadline on an address nobody kept.
    if maths:
        have = set(x["url"] for x in small)
        for rel in STUDIO_MATHJAX:
            x = _studio_entry(studio_base, rel)
            if x["url"] not in have:
                small.append(x)
    # A SIZE, AND NOT A LENGTH TO CHECK AGAINST.  `check: "here"` says the
    # body at this address is made up fresh at every ask -- the scheduler's
    # own numbers ride along in it and move whenever the deck is studied -- so
    # the phone may test that it HAS the answer and must not test its length
    # or its digest.  The bytes are still said, because the owner is being
    # asked to spend them and a sheet that quoted nothing for the exercises
    # would be quoting him a deck without its exercises in it.
    small.append(_door(cram, cost))
    _digests_save()
    return {"kind": "deck", "title": d.get("name") or slug, "page": base,
            "small": small, "media": media, "version": _version(stamps)}


def document(store_mod, doc_id, url_base="/studio", studio_base=None):
    """A studio document: its page, the pictures and recordings it shows, and
    the maths it needs where it has any (§19.8).

    The studio renders a document on the server, so keeping one means keeping
    the rendered PAGE -- there is nothing on a phone that could render it --
    and everything that page then asks for.

    `url_base` is the MOUNT the document is served from, which for a note
    beside a book is that book's notes prefix; `studio_base` is the studio's
    own, where its files answer for every mount at one address.  They are the
    same on the studio's own library, and only there.
    """
    studio_base = studio_base or url_base
    try:
        meta, markdown = store_mod.get(doc_id)
    except Exception:
        return None
    if meta is None:
        return None
    base = "%s/doc/%s" % (url_base.rstrip("/"), doc_id)
    media_base = "%s/media/%s/" % (url_base.rstrip("/"), doc_id)
    small = [_door(base)]
    # THE LIBRARY'S TAGS, WHICH THE PAGE ASKS FOR AS IT OPENS.  initDoc calls
    # refreshTagOptions the moment it runs (markdown/app/static/app.js), which
    # fetches `<mount>/api/tags` to fill the datalist behind the tag field --
    # at the MOUNT and not at the studio's own address, because that script
    # builds every call from the page's data-base, and for a note beside a
    # book the mount is that book's notes prefix.  It was in no list, so away
    # from the computer the one fetch a kept document page makes for itself
    # went to the network and sat out the worker's deadline.  A door, because
    # the computer composes that list out of the whole library.
    small.append(_door(url_base.rstrip("/") + "/api/tags"))
    small.extend(studio_files(studio_base))
    small.extend(studio_faces(studio_base))
    stamps = [(base, str(meta.get("updated") or ""))]
    media = []
    for kind, folder in (("images", "images"), ("audio", "audio")):
        try:
            d = (store_mod.images_dir(doc_id) if kind == "images"
                 else store_mod.audio_dir(doc_id))
        except Exception:
            continue
        d = str(d)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            path = os.path.join(d, name)
            if not os.path.isfile(path):
                continue
            url = media_base + folder + "/" + name
            low = name.lower()
            if low.endswith(PICTURES):
                small.append(_entry(url, path, "picture"))
            elif low.endswith(SOUNDS + FILMS):
                media.append(_entry(url, path, "recording", id=name, covers=""))
            else:
                continue
            stamps.append((url, _stamp(path)))
    # THE MATHS a document may use is read only by a browser, and only by one
    # whose document has a formula in it (the owner's decision 5).
    #
    # AT THE ADDRESS THE PAGE REALLY ASKS FOR, which is the studio's and not
    # /lib/'s: the page links <studio>/static/mathjax.js, and that loader
    # works the heavy library's address out of its own `src`, so what it goes
    # on to ask for is <studio>/static/mathjax/tex-svg.js.  Named as /lib/…,
    # as they were, the phone kept two files nothing ever asks for and sat
    # waiting on the two megabytes it had not kept.
    #
    # AND ASKED OF THE DIALECT AND NOT OF TeX.  A formula in this toolbox is
    # written `[a^2+b^2]{math}` or fenced between `:::math` and `:::`, and
    # there is no third spelling: `$` and `\(` are ordinary characters here,
    # so a document with a price in it kept two megabytes for nothing while
    # one full of mathematics kept none.  Said in one line here rather than
    # imported, because lib/ does not import the studio; a third spelling
    # would be a change to the dialect, which is a change to this line.
    small.extend(_drawings(markdown, studio_base, set(x["url"] for x in small), stamps))
    if _maths_in(markdown):
        have = set(x["url"] for x in small)
        for rel in STUDIO_MATHJAX:
            x = _studio_entry(studio_base, rel)
            if x["url"] not in have:
                small.append(x)
    _digests_save()
    return {"kind": "document", "title": meta.get("title") or doc_id, "page": base,
            "small": small, "media": media, "version": _version(stamps)}


def totals(rec):
    """What a thing costs, said in three parts: the page and its text, the
    groups that are one tick each (today, the notes), and the heavy things
    picked one by one.

    A group is counted on its own and not folded into the small parts,
    because it can be unticked -- and a sheet that said "its text is
    460 kB" and then took 280 kB off when the notes were unticked would be
    telling him the first number was never true.
    """
    small = sum(x.get("bytes") or 0 for x in rec.get("small") or [])
    notes = rec.get("notes") or {}
    groups = notes.get("bytes") or 0
    media = sum(x.get("bytes") or 0 for x in rec.get("media") or [])
    media += sum(x.get("bytes") or 0 for x in notes.get("media") or [])
    return {"small_bytes": small, "groups_bytes": groups, "media_bytes": media,
            "bytes": small + groups + media}
